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

    map_img = Image.open(p["output_path"]).convert("RGB")
    iw, ih = map_img.size

    def _fmt(v):
        if not isinstance(v, (int, float)):
            return str(v)
        av = abs(v)
        return f"{v:.0f}" if (av == 0 or av >= 1) else f"{v:.2f}"

    # Gather category rows (flows, systems, causes, and agents).
    flow_rows = []
    if flow_legend and flow_legend.get("kind") == "categorical":
        for e in flow_legend["entries"]:
            flow_rows.append((e[0], (e[1], e[2], e[3]), e[4] if len(e) > 4 else "line"))
    rows = []
    if system_legend and system_legend.get("kind") == "categorical":
        for e in system_legend["entries"]:
            rows.append((e[0], (e[1], e[2], e[3]), e[4] if len(e) > 4 else "rect"))
    if cause_legend and cause_legend.get("kind") == "categorical":
        for e in cause_legend["entries"]:
            rows.append((e[0], (e[1], e[2], e[3]), e[4] if len(e) > 4 else "rect"))
    if has_agents:
        rows.append(("Agent", (34, 34, 34), "person"))
    has_bar = bool(flow_legend and flow_legend.get("kind") == "graduated")

    # Draw the legend in a WHITE PANEL to the RIGHT of the map (never overlaps the
    # map, so it can't cover any point), with ~2x larger text for readability.
    if has_bar or flow_rows or rows:
        PANEL_W = 460
        canvas = Image.new("RGB", (iw + PANEL_W, ih), (255, 255, 255))
        canvas.paste(map_img, (0, 0))
        canvas.paste((220, 220, 220), (iw, 0, iw + 2, ih))  # thin divider line
        draw = ImageDraw.Draw(canvas)

        def _font(sz):
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", sz)
            except Exception:
                return ImageFont.load_default()
        F_TITLE, F_ENTRY = _font(44), _font(38)

        x0 = iw + 40
        cy = 50

        # --- flow color bar ---
        if has_bar:
            ramp = flow_legend["ramp"]
            vmin, vmax = flow_legend["min"], flow_legend["max"]
            draw.text((x0, cy), str(flow_legend.get("field", "flow")), fill=(0, 0, 0), font=F_TITLE)
            cy += 66
            bar_w, bar_h = 56, int(ih * 0.34)
            bar = Image.new("RGB", (bar_w, bar_h))
            bd = ImageDraw.Draw(bar)
            for y in range(bar_h):
                c = ramp.color(1.0 - y / max(bar_h - 1, 1))
                bd.line([(0, y), (bar_w - 1, y)], fill=(c.red(), c.green(), c.blue()))
            bd.rectangle([(0, 0), (bar_w - 1, bar_h - 1)], outline=(0, 0, 0), width=2)
            canvas.paste(bar, (x0, cy))
            tx = x0 + bar_w + 18
            draw.text((tx, cy - 16), _fmt(vmax), fill=(0, 0, 0), font=F_ENTRY)
            draw.text((tx, cy + bar_h // 2 - 20), _fmt((vmin + vmax) / 2), fill=(0, 0, 0), font=F_ENTRY)
            draw.text((tx, cy + bar_h - 26), _fmt(vmin), fill=(0, 0, 0), font=F_ENTRY)
            cy += bar_h + 60

        # --- categorical flows (country relationship) ---
        if flow_rows:
            draw.text(
                (x0, cy),
                str(flow_legend.get("field", "Flows")),
                fill=(0, 0, 0),
                font=F_TITLE,
            )
            cy += 70
            gw = 46
            row_h = gw + 24
            for label, rgb, _shape in flow_rows:
                mid_y = cy + gw // 2
                draw.line([(x0, mid_y), (x0 + gw, mid_y)], fill=rgb, width=10)
                draw.ellipse(
                    [(x0 - 5, mid_y - 5), (x0 + 5, mid_y + 5)],
                    fill=rgb,
                    outline=(0, 0, 0),
                )
                draw.ellipse(
                    [(x0 + gw - 5, mid_y - 5), (x0 + gw + 5, mid_y + 5)],
                    fill=rgb,
                    outline=(0, 0, 0),
                )
                draw.text((x0 + gw + 20, cy + 4), str(label), fill=(0, 0, 0), font=F_ENTRY)
                cy += row_h
            cy += 20

        # --- categories (systems / causes / agent) ---
        if rows:
            field = system_legend["field"] if system_legend else "Legend"
            draw.text((x0, cy), str(field), fill=(0, 0, 0), font=F_TITLE)
            cy += 70
            gw = 46                       # glyph box size
            row_h = gw + 24
            for label, rgb, shape in rows:
                x1, y1 = x0 + gw, cy + gw
                xm = (x0 + x1) // 2
                if shape == "person":
                    cx = x0 + gw // 2
                    draw.ellipse([(cx - 9, cy + 2), (cx + 9, cy + 22)], fill=(34, 34, 34))
                    draw.rectangle([(cx - 13, cy + 24), (cx + 13, cy + gw)], fill=(34, 34, 34))
                elif shape == "triangle_up":
                    draw.polygon([(xm, cy), (x1, y1), (x0, y1)], fill=rgb, outline=(0, 0, 0))
                elif shape == "triangle_down":
                    draw.polygon([(x0, cy), (x1, cy), (xm, y1)], fill=rgb, outline=(0, 0, 0))
                elif shape == "circle":
                    draw.ellipse([(x0, cy), (x1, y1)], fill=rgb, outline=(0, 0, 0))
                elif shape == "star":
                    import math as _m
                    _cx, _cy, _R = (x0 + x1) / 2, (cy + y1) / 2, gw / 2
                    _pts = [((_cx + (_R if k % 2 == 0 else _R * 0.42) * _m.cos(-_m.pi / 2 + k * _m.pi / 5)),
                             (_cy + (_R if k % 2 == 0 else _R * 0.42) * _m.sin(-_m.pi / 2 + k * _m.pi / 5)))
                            for k in range(10)]
                    draw.polygon(_pts, fill=rgb, outline=(0, 0, 0))
                elif shape == "line":
                    draw.line([(x0, cy + gw // 2), (x1, cy + gw // 2)], fill=rgb, width=10)
                else:
                    draw.rectangle([(x0, cy), (x1, y1)], fill=rgb, outline=(0, 0, 0))
                draw.text((x1 + 20, cy + 4), str(label), fill=(0, 0, 0), font=F_ENTRY)
                cy += row_h

        canvas.save(p["output_path"], "PNG")
    else:
        map_img.save(p["output_path"], "PNG")
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
