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
)
from qgis.PyQt.QtCore import QSize

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
ext = os.path.splitext(p["file_path"])[1].lower()
if ext == ".shp":
    user_layer = QgsVectorLayer(p["file_path"], "user_layer", "ogr")
else:
    user_layer = QgsRasterLayer(p["file_path"], "user_layer")

if not user_layer.isValid():
    print(json.dumps({"error": f"Failed to load user file: {user_layer.error().message()}"}))
    sys.exit(1)

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

print(json.dumps({
    "output_path": p["output_path"],
    "extent": [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()],
    "basemap": basemap_source,
}))

app.exitQgis()
