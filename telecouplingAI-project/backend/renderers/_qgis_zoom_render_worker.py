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
    # --- telecoupling (flows/systems/agents) styling ---
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsMarkerLineSymbolLayer,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsGradientColorRamp,
    Qgis,
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

app = QgsApplication([], False)
app.initQgis()

# ==================================================================
# Telecoupling cartography (flows / systems / agents) — shared module.
# Styling lives in telecoupling_style.py so the single-file render and the
# composite scene render share ONE source of truth. OPT-IN + ISOLATED: only
# OUR tool outputs match (detect_kind); env TELECOUPLING_STYLE=0 disables it
# (instant rollback to the generic renderer, no redeploy).
# ==================================================================
from telecoupling_style import detect_kind as _tc_detect_kind, apply_style as _tc_apply_style


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
# 2c. Telecoupling override (ADDITIVE) — only our flow/system/agent outputs.
#     Runs after the generic styling above and overrides the result for
#     matched layers. For every other file _tc_kind is None and nothing here
#     executes, so generic rendering is byte-for-byte unchanged. Guarded so a
#     failure silently falls back to whatever the generic block produced.
# ------------------------------------------------------------------
_tc_kind = _tc_detect_kind(p["file_path"], user_layer, p.get("render_as")) if ext in VECTOR_EXTS else None
if _tc_kind:
    try:
        user_layer, vector_legend = _tc_apply_style(
            _tc_kind, user_layer,
            p.get("magnitude_field"), p.get("category_field"))
    except Exception as e:
        sys.stderr.write("[telecoupling style] fell back to generic: %s\n" % e)

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

        # EVERY legend — generic InVEST rasters AND telecoupling
        # systems/agents/causes/flows — now uses the SAME big, readable overlay:
        # 2x scale + BOLD BLACK DejaVuSans. (The telecoupling branch used to be
        # frozen at 1.7x regular face, which made its legend visibly smaller and
        # lighter than the raster legend; user asked for consistency.) Generic
        # rasters still get a dedicated white gutter (below); telecoupling keeps
        # its compact legend box drawn over the map — same font size + weight.
        _lg_scale = 2.0

        def _s(x):
            return int(round(x * _lg_scale))

        _fs, _fs_s = _s(14), _s(12)
        # The system dejavu dir is empty in this image (PIL was silently falling
        # back to the tiny bitmap default), so pull DejaVuSans-Bold from
        # matplotlib's bundled fonts — BOLD for every legend now.
        try:
            import matplotlib as _mpl
            _MPL_TTF = os.path.join(_mpl.get_data_path(), "fonts", "ttf")
        except Exception:
            _MPL_TTF = ("/opt/conda/envs/TeleCouplingAI/lib/python3.12/"
                        "site-packages/matplotlib/mpl-data/fonts/ttf")

        _font_paths = [
            os.path.join(_MPL_TTF, "DejaVuSans-Bold.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            os.path.join(_MPL_TTF, "DejaVuSans.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        def _load_font(size):
            for _fp in _font_paths:
                try:
                    return ImageFont.truetype(_fp, size)
                except Exception:
                    continue
            return ImageFont.load_default()

        font = _load_font(_fs)
        font_small = _load_font(_fs_s)

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

        # Human-readable title for raster color bars. Run-2 testers said the bar
        # had "no title/units", only 3 bare numbers. We derive a label from the
        # source filename (always safe — just reformatting the real name) and
        # append a unit ONLY for a small high-confidence set of InVEST outputs
        # (otherwise no unit, so we never assert a wrong one).
        import re as _re
        _RASTER_UNITS = [
            ("wyield", "mm"), ("quickflow", "mm"), ("baseflow", "mm"),
            ("sed_export", "t"), ("sed_retention", "t"),
            # NDR nutrient exports (surface/subsurface/total, N or P) are kg/yr
            ("surface_export", "kg/yr"), ("subsurface_export", "kg/yr"),
            ("total_export", "kg/yr"), ("n_export", "kg/yr"), ("p_export", "kg/yr"),
            ("filled_dem", "m"),
        ]

        def _raster_title(fp):
            base = os.path.splitext(os.path.basename(fp))[0]
            unit = next((u for key, u in _RASTER_UNITS if key in base.lower()), "")
            # drop a trailing session/uuid hex chunk if the filename carries one
            base = _re.sub(r"[_-][0-9a-f]{6,}(-[0-9a-f]+)*$", "", base)
            label = base.replace("_", " ").replace("-", " ").strip().title()
            if len(label) > 30:
                label = label[:29] + "…"
            return f"{label} ({unit})" if unit else label

        kind = _legend.get("kind") if isinstance(_legend, dict) else None

        # EVERY legend gets a white gutter on the RIGHT so the 2x legend never
        # overlaps the map/data — telecoupling included now (user: put the legend
        # on the right like the raster, don't cover the map). Sized to the widest
        # of {title, bar+gap+widest number} or the fixed categorical panel width.
        if True:
            _gap = _s(6)
            _bar_w0 = _s(24)
            if raster_legend is not None or kind == "graduated":
                _vmin, _vmax = _legend["min"], _legend["max"]
                _lbls = [_fmt(_vmax), _fmt((_vmin + _vmax) / 2), _fmt(_vmin)]
                try:
                    _mlw = max(font.getlength(t) for t in _lbls)
                except Exception:
                    _mlw = _fs * 5
                _num_gutter = int(_bar_w0 + _gap + _mlw + _s(40))
                # A raster title (filename-derived) can contain a single word
                # wider than the number block (e.g. "Production"); words can't
                # break, so size the gutter to the WIDEST title word too — else
                # the title clips off the right edge.
                _title_word_w = 0
                if "field" not in _legend:
                    try:
                        _title_word_w = max(
                            (font.getlength(w) for w in _raster_title(p["file_path"]).split()),
                            default=0)
                    except Exception:
                        _title_word_w = 0
                _gutter = max(_num_gutter, int(_title_word_w + _s(28)))
            elif kind == "categorical":
                _gutter = _s(200) + _s(28)
            else:
                _gutter = 0
            if _gutter > 0:
                _canvas = Image.new("RGBA", (iw + _gutter, ih), (250, 250, 250, 255))
                _canvas.paste(img, (0, 0))
                img = _canvas
                iw += _gutter

        draw = ImageDraw.Draw(img)

        if raster_legend is not None or kind == "graduated":
            # Continuous color bar
            bar_w = _s(24)
            bar_h = int(ih * 0.55)

            ramp = _legend["ramp"]
            vmin, vmax = _legend["min"], _legend["max"]

            # Size the right margin to the widest numeric label so the bigger 2x
            # fonts never clip off the right edge (telecoupling flow legends live
            # in the gutter like everything else now).
            _gap = _s(6)
            _labels = [_fmt(vmax), _fmt((vmin + vmax) / 2), _fmt(vmin)]
            try:
                _max_lw = max(draw.textlength(t, font=font) for t in _labels)
            except Exception:
                _max_lw = _fs * 4
            margin_r = int(bar_w + _gap + _max_lw + _s(10))
            bar_x = iw - margin_r
            bar_y = (ih - bar_h) // 2

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

            text_x = bar_x + bar_w + _gap
            for ly, text in [
                (bar_y,                       _fmt(vmax)),
                (bar_y + bar_h // 2 - _s(7),  _fmt((vmin + vmax) / 2)),
                (bar_y + bar_h - _s(14),      _fmt(vmin)),
            ]:
                _halo_text((text_x, ly), text, font)
            if "field" in _legend:
                # graduated vector: keep the field-name header above the bar
                _halo_text((bar_x - 4, bar_y - _s(22)), _legend["field"], font_small)
            else:
                # raster: no field name -> filename-derived title, wrapped to the
                # gutter INTERIOR and drawn LEFT-aligned from the gutter's left
                # edge. The gutter was sized above to fit the widest title word,
                # so no word can clip off the right edge.
                _title = _raster_title(p["file_path"])
                _tx = iw - _gutter + _s(10)        # gutter left edge + pad
                _avail = _gutter - _s(18)
                _lines, _cur = [], ""
                for _wd in _title.split():
                    _cand = (_cur + " " + _wd).strip()
                    try:
                        _fit = draw.textlength(_cand, font=font) <= _avail
                    except Exception:
                        _fit = len(_cand) * _fs * 0.5 <= _avail
                    if _fit or not _cur:
                        _cur = _cand
                    else:
                        _lines.append(_cur)
                        _cur = _wd
                if _cur:
                    _lines.append(_cur)
                _ty = _s(10)
                for _ln in _lines:
                    _halo_text((_tx, _ty), _ln, font)
                    _ty += _fs + _s(6)

        elif kind == "categorical":
            # Stacked swatches + labels in the upper-right
            entries = _legend["entries"]
            max_show = 16
            shown = entries[:max_show]
            sw = _s(18)            # swatch size
            row_h = sw + _s(4)     # gap
            panel_w = _s(200)
            pad = _s(8)
            panel_h = row_h * len(shown) + (_s(24) if len(entries) > max_show else 0) + _s(24)
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

            _halo_text((px + pad, py + _s(4)), f"{_legend['field']}", font_small)
            cy = py + _s(22)
            for entry in shown:
                label, r, g, b = entry[0], entry[1], entry[2], entry[3]
                # entry[4] (if present) is a glyph hint: triangle_up/triangle_down/
                # circle. Generic categorical entries are 4-tuples -> "rect", which
                # reproduces the original filled square exactly (byte-identical).
                gshape = entry[4] if len(entry) > 4 else "rect"
                x0, y0, x1, y1 = px + pad, cy, px + pad + sw, cy + sw
                xm = (x0 + x1) // 2
                _d = ImageDraw.Draw(img)
                if gshape == "triangle_up":
                    _d.polygon([(xm, y0), (x1, y1), (x0, y1)],
                               fill=(r, g, b, 255), outline=(0, 0, 0, 220))
                elif gshape == "triangle_down":
                    _d.polygon([(x0, y0), (x1, y0), (xm, y1)],
                               fill=(r, g, b, 255), outline=(0, 0, 0, 220))
                elif gshape == "circle":
                    _d.ellipse([(x0, y0), (x1, y1)],
                               fill=(r, g, b, 255), outline=(0, 0, 0, 220))
                elif gshape == "star":
                    import math as _m
                    _cx, _cy, _R = (x0 + x1) / 2, (y0 + y1) / 2, sw / 2
                    _pts = [((_cx + (_R if k % 2 == 0 else _R * 0.42) * _m.cos(-_m.pi / 2 + k * _m.pi / 5)),
                             (_cy + (_R if k % 2 == 0 else _R * 0.42) * _m.sin(-_m.pi / 2 + k * _m.pi / 5)))
                            for k in range(10)]
                    _d.polygon(_pts, fill=(r, g, b, 255), outline=(0, 0, 0, 220))
                elif gshape == "person":
                    # Render the ACTUAL agent SVG so the legend glyph matches the
                    # map marker exactly. Fall back to a drawn silhouette if the
                    # SVG can't be rasterized.
                    _person_ok = False
                    try:
                        from qgis.PyQt.QtSvg import QSvgRenderer as _QSvg
                        from qgis.PyQt.QtGui import QImage as _QI, QPainter as _QP
                        from qgis.PyQt.QtCore import QRectF as _QR, Qt as _Qt
                        _svgp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "assets", "agent_person.svg")
                        if os.path.isfile(_svgp):
                            _qi = _QI(sw, sw, _QI.Format_ARGB32)
                            _qi.fill(_Qt.transparent)
                            _qp = _QP(_qi)
                            _QSvg(_svgp).render(_qp, _QR(0, 0, float(sw), float(sw)))
                            _qp.end()
                            _pic = Image.frombytes("RGBA", (sw, sw),
                                                   _qi.bits().asstring(sw * sw * 4),
                                                   "raw", "BGRA")
                            img.paste(_pic, (int(x0), int(y0)), _pic)
                            _person_ok = True
                    except Exception:
                        _person_ok = False
                    if not _person_ok:
                        _cx = (x0 + x1) / 2
                        _hr = sw * 0.17
                        _hy = y0 + sw * 0.24
                        _d.ellipse([(_cx - _hr, _hy - _hr), (_cx + _hr, _hy + _hr)],
                                   fill=(r, g, b, 255), outline=(0, 0, 0, 220))
                        _by = _hy + _hr
                        _d.polygon([(_cx - sw * 0.30, y1), (_cx + sw * 0.30, y1),
                                    (_cx + sw * 0.15, _by), (_cx - sw * 0.15, _by)],
                                   fill=(r, g, b, 255), outline=(0, 0, 0, 220))
                elif gshape == "line":
                    # thick colored line for flows
                    _ly = (y0 + y1) // 2
                    _d.line([(x0, _ly), (x1, _ly)], fill=(r, g, b, 255),
                            width=max(2, sw // 4))
                else:  # rect — generic categorical, unchanged
                    _d.rectangle([(x0, y0), (x1, y1)],
                                 fill=(r, g, b, 230), outline=(0, 0, 0, 200), width=1)
                _halo_text((px + pad + sw + _s(6), cy + 1),
                           (label if len(label) < 22 else label[:22] + "…"),
                           font_small)
                cy += row_h
            if len(entries) > max_show:
                _halo_text((px + pad, cy + 2),
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
