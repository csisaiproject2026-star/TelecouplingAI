"""
QGIS telecoupling SCENE render worker (Phase B) — composites flows + systems +
agents into ONE map in the Tonini & Liu 2017 Fig.10 style.

Reuses the shared cartography in telecoupling_style.py (single source of truth
with the single-file render worker), then stacks the layers over a satellite
basemap, zooms to their combined extent, and draws a combined legend.

Input:  sys.argv[1] = path to a JSON file with:
    output_path     : str   — output PNG path (required)
    flows_path      : str   — radial_flows.shp           (optional)
    systems_path    : str   — systems_from_table.shp     (optional)
    agents_path     : str   — agents_from_table.shp      (optional)
    magnitude_field : str   — flow color/width column    (optional)
    category_field  : str   — system type column         (optional)
    width/height    : int   — output size (default 1600x1000)
    padding         : float — extent padding (default 0.12)
    basemap_path    : str   — offline MBTiles override    (optional)
At least one of flows_path / systems_path / agents_path must be given.
Output: JSON result to stdout.
"""
import sys
import os
import json
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QGIS_PREFIX_PATH", "/usr")

with open(sys.argv[1], encoding="utf-8") as f:
    p = json.load(f)

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
)
from qgis.PyQt.QtCore import QSize

app = QgsApplication([], False)
app.initQgis()

import telecoupling_style as tc


def _fail(msg):
    print(json.dumps({"error": msg}))
    app.exitQgis()
    sys.exit(1)


# ------------------------------------------------------------------
# 1. Basemap — online Google Satellite, fallback offline MBTiles, else none
# ------------------------------------------------------------------
basemap_layer = None
basemap_source = "none"
online_url = (
    "type=xyz"
    "&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D"
    "&zmax=19&zmin=0&crs=EPSG3857"
)
online_layer = QgsRasterLayer(online_url, "satellite_online", "wms")
if online_layer.isValid():
    basemap_layer = online_layer
    basemap_source = "online (Google Satellite)"
if not basemap_layer:
    default_mbtiles = str(Path(__file__).parent.parent.parent / "data" / "basemap" / "world_satellite.mbtiles")
    mbtiles_path = p.get("basemap_path", default_mbtiles)
    if os.path.isfile(mbtiles_path):
        off = QgsRasterLayer(f"type=mbtiles&url={mbtiles_path}", "satellite_offline", "wms")
        if off.isValid():
            basemap_layer = off
            basemap_source = f"offline MBTiles ({mbtiles_path})"

# ------------------------------------------------------------------
# 2. Load + style each provided layer (reusing the shared cartography)
# ------------------------------------------------------------------
flow_legend = None
system_legend = None
cause_legend = None
has_agents = False
# Drawn top -> bottom: agents/causes on top, then systems, then flows, then basemap.
top_layers = []

flows_path = p.get("flows_path")
systems_path = p.get("systems_path")
agents_path = p.get("agents_path")
causes_path = p.get("causes_path")
if not any([flows_path, systems_path, agents_path, causes_path]):
    _fail("Provide at least one of flows_path / systems_path / agents_path / causes_path.")

# Agents (top)
if agents_path:
    la = QgsVectorLayer(agents_path, "agents", "ogr")
    if la.isValid():
        la, _ = tc.style_agents(la)
        top_layers.append(la)
        has_agents = True

# Causes (top)
if causes_path:
    lc = QgsVectorLayer(causes_path, "causes", "ogr")
    if lc.isValid():
        lc, cause_legend = tc.style_causes(lc)
        top_layers.append(lc)

# Systems (middle)
if systems_path:
    ls = QgsVectorLayer(systems_path, "systems", "ogr")
    if ls.isValid():
        ls, system_legend = tc.style_systems(ls, p.get("category_field"))
        top_layers.append(ls)

# Flows (bottom of the thematic stack)
flow_layer = None
if flows_path:
    lf = QgsVectorLayer(flows_path, "flows", "ogr")
    if lf.isValid():
        lf, flow_legend = tc.style_flows(lf, p.get("magnitude_field"))
        flow_layer = lf
        top_layers.append(lf)

if not top_layers:
    _fail("None of the provided layers could be loaded.")

layers = top_layers + ([basemap_layer] if basemap_layer else [])

# ------------------------------------------------------------------
# 3. Combined extent (union) reprojected to EPSG:3857 + padding
# ------------------------------------------------------------------
dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
rect = None
for lyr in top_layers:
    tr = QgsCoordinateTransform(lyr.crs(), dest_crs, QgsProject.instance())
    e = tr.transformBoundingBox(lyr.extent())
    if rect is None:
        rect = QgsRectangle(e)
    else:
        rect.combineExtentWith(e)

padding = p.get("padding", 0.12)
rect.grow(max(rect.width(), rect.height()) * padding)

# ------------------------------------------------------------------
# 4. Render
# ------------------------------------------------------------------
width = p.get("width", 1600)
height = p.get("height", 1000)
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
# 5. Combined legend (flow color bar + system categories + agent icon)
# ------------------------------------------------------------------
try:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(p["output_path"]).convert("RGBA")
    iw, ih = img.size
    scale = 1.7

    def _s(x):
        return int(round(x * scale))

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", _s(14))
        font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", _s(12))
    except Exception:
        font = ImageFont.load_default()
        font_s = font

    def _halo(xy, text, fnt):
        x, y = xy
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ImageDraw.Draw(img).text((x + dx, y + dy), text, fill=(255, 255, 255, 230), font=fnt)
        ImageDraw.Draw(img).text((x, y), text, fill=(0, 0, 0, 255), font=fnt)

    def _fmt(v):
        if not isinstance(v, (int, float)):
            return str(v)
        av = abs(v)
        return f"{v:.0f}" if (av == 0 or av >= 1) else f"{v:.2f}"

    # --- flow color bar (right-center) ---
    if flow_legend and flow_legend.get("kind") == "graduated":
        ramp = flow_legend["ramp"]
        vmin, vmax = flow_legend["min"], flow_legend["max"]
        bar_w, bar_h = _s(24), int(ih * 0.45)
        bar_x = iw - _s(72)
        bar_y = (ih - bar_h) // 2
        bar = Image.new("RGBA", (bar_w, bar_h))
        bd = ImageDraw.Draw(bar)
        for y in range(bar_h):
            c = ramp.color(1.0 - y / max(bar_h - 1, 1))
            bd.line([(0, y), (bar_w - 1, y)], fill=(c.red(), c.green(), c.blue(), 255))
        bd.rectangle([(0, 0), (bar_w - 1, bar_h - 1)], outline=(0, 0, 0, 220), width=1)
        img.paste(bar, (bar_x, bar_y), bar)
        tx = bar_x + bar_w + _s(6)
        _halo((tx, bar_y), _fmt(vmax), font)
        _halo((tx, bar_y + bar_h // 2 - _s(7)), _fmt((vmin + vmax) / 2), font)
        _halo((tx, bar_y + bar_h - _s(14)), _fmt(vmin), font)
        _halo((bar_x - _s(2), bar_y - _s(22)), str(flow_legend.get("field", "flow")), font_s)

    # --- systems categories + agent entry (upper-right panel) ---
    rows = []
    if system_legend and system_legend.get("kind") == "categorical":
        for e in system_legend["entries"]:
            gshape = e[4] if len(e) > 4 else "rect"
            rows.append((e[0], (e[1], e[2], e[3]), gshape))
    if cause_legend and cause_legend.get("kind") == "categorical":
        for e in cause_legend["entries"]:
            gshape = e[4] if len(e) > 4 else "rect"
            rows.append((e[0], (e[1], e[2], e[3]), gshape))
    if has_agents:
        rows.append(("Agent", (34, 34, 34), "person"))

    if rows:
        sw = _s(18)
        row_h = sw + _s(6)
        panel_w = _s(165)
        pad = _s(8)
        title_h = _s(22)
        panel_h = title_h + row_h * len(rows) + pad
        px = iw - _s(16) - panel_w
        py = _s(16)
        backdrop = Image.new("RGBA", (panel_w, panel_h), (255, 255, 255, 205))
        img.paste(backdrop, (px, py), backdrop)
        ImageDraw.Draw(img).rectangle([(px, py), (px + panel_w - 1, py + panel_h - 1)],
                                      outline=(0, 0, 0, 220), width=1)
        field = system_legend["field"] if system_legend else "Legend"
        _halo((px + pad, py + _s(4)), str(field), font_s)
        cy = py + title_h
        for label, rgb, shape in rows:
            x0, y0, x1, y1 = px + pad, cy, px + pad + sw, cy + sw
            xm = (x0 + x1) // 2
            _d = ImageDraw.Draw(img)
            if shape == "person":
                # small person glyph: head + body
                cx = px + pad + sw // 2
                _d.ellipse([(cx - _s(3), cy + _s(1)), (cx + _s(3), cy + _s(7))], fill=(34, 34, 34, 255))
                _d.rectangle([(cx - _s(4), cy + _s(8)), (cx + _s(4), cy + sw)], fill=(34, 34, 34, 255))
            elif shape == "triangle_up":
                _d.polygon([(xm, y0), (x1, y1), (x0, y1)], fill=rgb + (255,), outline=(0, 0, 0, 220))
            elif shape == "triangle_down":
                _d.polygon([(x0, y0), (x1, y0), (xm, y1)], fill=rgb + (255,), outline=(0, 0, 0, 220))
            elif shape == "circle":
                _d.ellipse([(x0, y0), (x1, y1)], fill=rgb + (255,), outline=(0, 0, 0, 220))
            elif shape == "star":
                import math as _m
                _cx, _cy, _R = (x0 + x1) / 2, (y0 + y1) / 2, sw / 2
                _pts = [((_cx + (_R if k % 2 == 0 else _R * 0.42) * _m.cos(-_m.pi / 2 + k * _m.pi / 5)),
                         (_cy + (_R if k % 2 == 0 else _R * 0.42) * _m.sin(-_m.pi / 2 + k * _m.pi / 5)))
                        for k in range(10)]
                _d.polygon(_pts, fill=rgb + (255,), outline=(0, 0, 0, 220))
            else:
                _d.rectangle([(x0, y0), (x1, y1)], fill=rgb + (230,), outline=(0, 0, 0, 200), width=1)
            _halo((px + pad + sw + _s(6), cy + 1),
                  (label if len(label) < 20 else label[:20] + "…"), font_s)
            cy += row_h

    img.save(p["output_path"], "PNG")
except Exception as e:
    sys.stderr.write(f"[scene legend] skipped: {e}\n")

print(json.dumps({
    "output_path": p["output_path"],
    "extent": [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()],
    "basemap": basemap_source,
    "layers": {"flows": bool(flows_path), "systems": bool(systems_path),
               "agents": bool(agents_path), "causes": bool(causes_path)},
}))
app.exitQgis()
