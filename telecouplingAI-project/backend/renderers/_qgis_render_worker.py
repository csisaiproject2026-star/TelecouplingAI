"""
QGIS render worker — executed as a subprocess by qgis_renderer.py.
This script runs inside QGIS Python environment.
Input: sys.argv[1] = path to a JSON file with render parameters
Output: JSON result to stdout
"""
import sys
import json
import os

# Read params from temp file (avoids shell quoting issues with JSON strings)
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
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage

app = QgsApplication([], False)
app.initQgis()

ext = os.path.splitext(p["file_path"])[1].lower()
if ext == ".shp":
    layer = QgsVectorLayer(p["file_path"], "l", "ogr")
else:
    layer = QgsRasterLayer(p["file_path"], "l")

if not layer.isValid():
    print(json.dumps({"error": layer.error().message()}))
    sys.exit(1)

e = p.get("extent")
if e:
    rect = QgsRectangle(e[0], e[1], e[2], e[3])
else:
    rect = layer.extent()

width = p.get("width", 1920)
height = p.get("height", 1080)

s = QgsMapSettings()
s.setLayers([layer])
s.setExtent(rect)
s.setOutputSize(QSize(width, height))

os.makedirs(os.path.dirname(os.path.abspath(p["output_path"])), exist_ok=True)

img = QImage(QSize(width, height), QImage.Format_ARGB32_Premultiplied)
img.fill(0xFFFFFFFF)

job = QgsMapRendererParallelJob(s)
job.start()
job.waitForFinished()
job.renderedImage().save(p["output_path"], "PNG")

print(json.dumps({
    "output_path": p["output_path"],
    "extent": [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()],
}))

app.exitQgis()
