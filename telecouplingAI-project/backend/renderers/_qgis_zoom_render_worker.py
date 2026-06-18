"""
QGIS zoom render worker — executed as a subprocess by qgis_renderer.py.
Renders a user file (SHP/TIF) on top of a satellite world basemap,
zoomed to the user file's extent.

Basemap strategy (in order of priority):
  1. Online: Google Satellite XYZ tiles (requires internet)
  2. Offline fallback: local MBTiles (data/basemap/world_satellite.mbtiles)
  3. No basemap: render user layer only

Input:  sys.argv[1] = path to a JSON file with render parameters
Output: JSON result to stdout

Parameters (JSON):
    file_path   : str   — path to the SHP or TIF file
    output_path : str   — path to save the output PNG
    width       : int   — output image width  (default 1920)
    height      : int   — output image height (default 1080)
    padding     : float — fractional padding around the user layer extent
                          (default 0.1 = 10%)
    basemap_path: str   — optional override for the offline MBTiles path
"""
import sys
import json
import os
from pathlib import Path

with open(sys.argv[1], encoding="utf-8") as f:
    p = json.load(f)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QGIS_PREFIX_PATH", "/usr")  # Docker default; override via env

from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsMapSettings,
    QgsMapRendererParallelJob,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsSingleBandPseudoColorRenderer,
    QgsRasterShader,
    QgsColorRampShader,
    QgsStyle,
    QgsRasterBandStats,
    QgsSymbol,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

app = QgsApplication([], False)
app.initQgis()

# ------------------------------------------------------------------
# 1. Load basemap — online first, fallback to local MBTiles
# ------------------------------------------------------------------
basemap_layer = None
basemap_source = "none"

# Strategy 1: Online Google Satellite XYZ tiles
online_url = (
    "type=xyz"
    "&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D"
    "&zmax=19&zmin=0&crs=EPSG3857"
)
online_layer = QgsRasterLayer(online_url, "satellite_online", "wms")
if online_layer.isValid():
    basemap_layer = online_layer
    basemap_source = "online (Google Satellite)"

# Strategy 2: Offline MBTiles fallback
if not basemap_layer:
    default_mbtiles = str(
        Path(__file__).parent.parent.parent  # backend/ -> project root
        / "data" / "basemap" / "world_satellite.mbtiles"
    )
    mbtiles_path = p.get("basemap_path", default_mbtiles)
    if os.path.isfile(mbtiles_path):
        uri = f"type=mbtiles&url={mbtiles_path}"
        offline_layer = QgsRasterLayer(uri, "satellite_offline", "wms")
        if offline_layer.isValid():
            basemap_layer = offline_layer
            basemap_source = f"offline MBTiles ({mbtiles_path})"

# ------------------------------------------------------------------
# 2. Load user layer (SHP or TIF)
# ------------------------------------------------------------------
VECTOR_EXTS = {".shp", ".geojson", ".gpkg", ".json"}
RASTER_EXTS = {".tif", ".tiff"}

ext = os.path.splitext(p["file_path"])[1].lower()
if ext in VECTOR_EXTS:
    user_layer = QgsVectorLayer(p["file_path"], "user_layer", "ogr")
elif ext in RASTER_EXTS:
    user_layer = QgsRasterLayer(p["file_path"], "user_layer")
else:
    print(json.dumps({"error": f"Unsupported file extension: {ext}"}))
    sys.exit(1)

if not user_layer.isValid():
    print(json.dumps({"error": f"Failed to load user file: {user_layer.error().message()}"}))
    sys.exit(1)

# ------------------------------------------------------------------
# 2b. Style raster with a Viridis pseudo-color ramp so the output has a
#     real legend and NoData reads as transparent (instead of solid black).
# ------------------------------------------------------------------
raster_legend = None    # populated for rasters; drives the PIL colorbar later
vector_legend = None    # populated for vectors; drives the PIL category/colorbar later
ramp = QgsStyle.defaultStyle().colorRamp("Viridis")
if ramp is None:
    ramp = QgsStyle.defaultStyle().colorRamp("Spectral")

if ext in RASTER_EXTS:
    provider = user_layer.dataProvider()
    band = 1
    stats = provider.bandStatistics(band, QgsRasterBandStats.All)
    vmin, vmax = stats.minimumValue, stats.maximumValue
    if vmax == vmin:
        vmax = vmin + 1e-9

    shader_fn = QgsColorRampShader(vmin, vmax, ramp, QgsColorRampShader.Interpolated)
    shader_fn.classifyColorRamp(classes=5, band=band, extent=user_layer.extent(), input=provider)
    rshader = QgsRasterShader()
    rshader.setRasterShaderFunction(shader_fn)
    user_layer.setRenderer(QgsSingleBandPseudoColorRenderer(provider, band, rshader))

    raster_legend = {"min": vmin, "max": vmax, "ramp": ramp}

elif ext in VECTOR_EXTS:
    # Auto-pick a colouring field: prefer cluster/community/category-style
    # categoricals, fall back to the first non-id numeric field for a
    # graduated ramp. Wrapped in try/except so a styling failure never
    # blocks the render — we just fall through to the default solid color.
    try:
        CAT_KW = ("cluster", "community", "group", "category", "class", "label",
                  "type", "zone", "region_id", "lisa")
        SKIP_KW = ("objectid", "fid", "shape_", "geometry")
        fields = list(user_layer.fields())

        chosen, chosen_kind = None, None
        # 1) keyword-driven categorical
        for f in fields:
            if any(k in f.name().lower() for k in CAT_KW):
                chosen, chosen_kind = f.name(), "categorical"
                break
        # 2) first numeric non-id field
        if chosen is None:
            for f in fields:
                nm = f.name().lower()
                if any(k in nm for k in SKIP_KW):
                    continue
                if "id" in nm or "code" in nm or "name" in nm:
                    continue
                if f.isNumeric():
                    chosen, chosen_kind = f.name(), "graduated"
                    break
        # 3) any numeric field
        if chosen is None:
            for f in fields:
                if f.isNumeric():
                    chosen, chosen_kind = f.name(), "graduated"
                    break

        geom_type = user_layer.geometryType()

        if chosen and chosen_kind == "categorical":
            unique_vals = sorted({
                feat[chosen] for feat in user_layer.getFeatures()
                if feat[chosen] is not None
            }, key=lambda v: (str(type(v)), v))
            n = max(len(unique_vals), 1)
            categories = []
            legend_entries = []
            for i, v in enumerate(unique_vals):
                c = ramp.color((i + 0.5) / n)
                sym = QgsSymbol.defaultSymbol(geom_type)
                sym.setColor(c)
                if geom_type == QgsWkbTypes.PolygonGeometry and sym.symbolLayerCount() > 0:
                    sym.symbolLayer(0).setStrokeWidth(0.2)
                categories.append(QgsRendererCategory(v, sym, str(v)))
                legend_entries.append((str(v), c.red(), c.green(), c.blue()))
            user_layer.setRenderer(QgsCategorizedSymbolRenderer(chosen, categories))
            vector_legend = {"kind": "categorical", "field": chosen, "entries": legend_entries}

        elif chosen and chosen_kind == "graduated":
            idx = user_layer.fields().indexOf(chosen)
            vmin = user_layer.minimumValue(idx)
            vmax = user_layer.maximumValue(idx)
            if vmin is None or vmax is None or vmin == vmax:
                vmax = (vmin or 0) + 1e-9
            n_classes = 5
            step = (vmax - vmin) / n_classes
            ranges = []
            for i in range(n_classes):
                lo = vmin + i * step
                hi = vmin + (i + 1) * step
                c = ramp.color((i + 0.5) / n_classes)
                sym = QgsSymbol.defaultSymbol(geom_type)
                sym.setColor(c)
                if geom_type == QgsWkbTypes.PolygonGeometry and sym.symbolLayerCount() > 0:
                    sym.symbolLayer(0).setStrokeWidth(0.2)
                ranges.append(QgsRendererRange(lo, hi, sym, f"{lo:.2f} – {hi:.2f}"))
            user_layer.setRenderer(QgsGraduatedSymbolRenderer(chosen, ranges))
            vector_legend = {"kind": "graduated", "field": chosen,
                             "min": vmin, "max": vmax, "ramp": ramp}
    except Exception as e:
        sys.stderr.write(f"[vector styling] skipped: {e}\n")

# ------------------------------------------------------------------
# 3. Layer order: user layer on top, basemap at bottom
# ------------------------------------------------------------------
layers = [user_layer, basemap_layer] if basemap_layer else [user_layer]

# ------------------------------------------------------------------
# 4. Destination CRS — EPSG:3857 (Web Mercator, matches XYZ/MBTiles)
# ------------------------------------------------------------------
dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")

# ------------------------------------------------------------------
# 5. Zoom extent = user layer extent reprojected to EPSG:3857 + padding
# ------------------------------------------------------------------
user_crs = user_layer.crs()
if user_crs != dest_crs:
    transform = QgsCoordinateTransform(user_crs, dest_crs, QgsProject.instance())
    rect = transform.transformBoundingBox(user_layer.extent())
else:
    rect = QgsRectangle(user_layer.extent())

padding = p.get("padding", 0.1)
rect.grow(max(rect.width(), rect.height()) * padding)

# ------------------------------------------------------------------
# 6. Render
# ------------------------------------------------------------------
width  = p.get("width",  1920)
height = p.get("height", 1080)

s = QgsMapSettings()
s.setLayers(layers)
s.setDestinationCrs(dest_crs)
s.setExtent(rect)
s.setOutputSize(QSize(width, height))

os.makedirs(os.path.dirname(os.path.abspath(p["output_path"])), exist_ok=True)

job = QgsMapRendererParallelJob(s)
job.start()
job.waitForFinished()
job.renderedImage().save(p["output_path"], "PNG")

# ------------------------------------------------------------------
# 7. Overlay a legend for the user so they can interpret the colors.
#    - Raster:                 vertical color bar with min / mid / max
#    - Vector (graduated):     same vertical color bar with min / mid / max
#    - Vector (categorical):   stacked swatch + label list
#    PIL is used so we can position labels precisely without dragging in
#    QGIS layout objects (which are heavyweight for a single PNG).
# ------------------------------------------------------------------
_legend = raster_legend or vector_legend
if _legend is not None:
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(p["output_path"]).convert("RGBA")
        iw, ih = img.size
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except Exception:
            font = ImageFont.load_default()
            font_small = font

        def _fmt(v):
            av = abs(v) if isinstance(v, (int, float)) else 0
            if not isinstance(v, (int, float)):
                return str(v)
            if av == 0 or 0.01 <= av < 10000:
                return f"{v:.2f}"
            return f"{v:.2e}"

        def _halo_text(xy, text, fnt):
            x, y = xy
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                draw.text((x + dx, y + dy), text, fill=(255, 255, 255, 230), font=fnt)
            draw.text((x, y), text, fill=(0, 0, 0, 255), font=fnt)

        kind = _legend.get("kind") if isinstance(_legend, dict) else None

        if raster_legend is not None or kind == "graduated":
            # Continuous color bar
            bar_w = 24
            bar_h = int(ih * 0.55)
            margin_r = 70
            bar_x = iw - margin_r
            bar_y = (ih - bar_h) // 2

            ramp = _legend["ramp"]
            vmin, vmax = _legend["min"], _legend["max"]

            bar = Image.new("RGBA", (bar_w, bar_h))
            bar_draw = ImageDraw.Draw(bar)
            for y in range(bar_h):
                fraction = 1.0 - y / max(bar_h - 1, 1)
                c = ramp.color(fraction)
                bar_draw.line([(0, y), (bar_w - 1, y)],
                              fill=(c.red(), c.green(), c.blue(), 255))
            bar_draw.rectangle([(0, 0), (bar_w - 1, bar_h - 1)],
                               outline=(0, 0, 0, 220), width=1)
            img.paste(bar, (bar_x, bar_y), bar)

            text_x = bar_x + bar_w + 6
            for ly, text in [
                (bar_y,                   _fmt(vmax)),
                (bar_y + bar_h // 2 - 7,  _fmt((vmin + vmax) / 2)),
                (bar_y + bar_h - 14,      _fmt(vmin)),
            ]:
                _halo_text((text_x, ly), text, font)
            if "field" in _legend:
                _halo_text((bar_x - 4, bar_y - 22), _legend["field"], font_small)

        elif kind == "categorical":
            # Stacked swatches + labels in the upper-right
            entries = _legend["entries"]
            max_show = 16
            shown = entries[:max_show]
            sw = 18           # swatch size
            row_h = sw + 4    # gap
            panel_w = 200
            panel_h = row_h * len(shown) + (24 if len(entries) > max_show else 0) + 24
            margin_r, margin_t = 16, 16
            px = iw - margin_r - panel_w
            py = margin_t

            # semi-transparent backdrop for readability
            backdrop = Image.new("RGBA", (panel_w, panel_h), (255, 255, 255, 200))
            img.paste(backdrop, (px, py), backdrop)
            ImageDraw.Draw(img).rectangle(
                [(px, py), (px + panel_w - 1, py + panel_h - 1)],
                outline=(0, 0, 0, 220), width=1,
            )

            _halo_text((px + 8, py + 4), f"{_legend['field']}", font_small)
            cy = py + 22
            for label, r, g, b in shown:
                # swatch
                ImageDraw.Draw(img).rectangle(
                    [(px + 8, cy), (px + 8 + sw, cy + sw)],
                    fill=(r, g, b, 230), outline=(0, 0, 0, 200), width=1,
                )
                _halo_text((px + 8 + sw + 6, cy + 1),
                           (label if len(label) < 22 else label[:22] + "…"),
                           font_small)
                cy += row_h
            if len(entries) > max_show:
                _halo_text((px + 8, cy + 2),
                           f"… +{len(entries) - max_show} more",
                           font_small)

        img.save(p["output_path"], "PNG")
    except Exception as e:
        # Don't fail the whole render just because the legend overlay broke
        sys.stderr.write(f"[legend overlay] skipped: {e}\n")

_legend_summary = None
if raster_legend is not None:
    _legend_summary = {"kind": "raster",
                       "min": raster_legend["min"], "max": raster_legend["max"]}
elif vector_legend is not None:
    if vector_legend.get("kind") == "categorical":
        _legend_summary = {"kind": "categorical",
                           "field": vector_legend["field"],
                           "n_categories": len(vector_legend["entries"])}
    elif vector_legend.get("kind") == "graduated":
        _legend_summary = {"kind": "graduated",
                           "field": vector_legend["field"],
                           "min": vector_legend["min"],
                           "max": vector_legend["max"]}

print(json.dumps({
    "output_path": p["output_path"],
    "extent": [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()],
    "basemap": basemap_source,
    "legend": _legend_summary,
}))

app.exitQgis()
