import sys
import os

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QGIS_PREFIX_PATH'] = r'C:\Program Files\QGIS 3.40.14'

from qgis.core import (
    QgsApplication,
    QgsRasterLayer,
    QgsMapSettings,
    QgsMapRendererParallelJob
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage

app = QgsApplication([], False)
app.initQgis()
print("✅ Step 1: QgsApplication init OK")

tif_path = r'C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\test_headless_QGIS\UTM2GTIF.tiff'
layer = QgsRasterLayer(tif_path, 'test_layer')

if not layer.isValid():
    print(f"❌ Step 2: Layer invalid — {layer.error().message()}")
    sys.exit(1)
print(f"✅ Step 2: Layer loaded OK — extent: {layer.extent()}")

settings = QgsMapSettings()
settings.setLayers([layer])
settings.setExtent(layer.extent())
settings.setOutputSize(QSize(800, 600))

image = QImage(QSize(800, 600), QImage.Format_ARGB32_Premultiplied)
image.fill(0xFFFFFFFF)

job = QgsMapRendererParallelJob(settings)
job.start()
job.waitForFinished()

output_path = r'C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\test_headless_QGIS\output.png'
job.renderedImage().save(output_path, 'PNG')
print(f"✅ Step 3: Render OK → {output_path}")

app.exitQgis()
print("✅ 全部通过，QGIS 渲染可用")