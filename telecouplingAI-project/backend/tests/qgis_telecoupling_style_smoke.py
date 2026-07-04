"""Run with the QGIS Python runtime to validate telecoupling cartography."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (
    QgsApplication,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant


app = QgsApplication([], False)
app.initQgis()

from renderers.telecoupling_style import style_flows, style_systems


def flow_layer():
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", "flows", "memory")
    layer.dataProvider().addAttributes([QgsField("tc_role", QVariant.String)])
    layer.updateFields()
    coordinates = [
        ((2.35, 48.85), (5.37, 43.30)),
        ((2.35, 48.85), (13.40, 52.52)),
        ((2.35, 48.85), (-77.04, 38.91)),
    ]
    features = []
    for origin, destination in coordinates:
        feature = QgsFeature(layer.fields())
        feature["tc_role"] = "flow_type"
        feature.setGeometry(QgsGeometry.fromPolylineXY([
            QgsPointXY(*origin),
            QgsPointXY(*destination),
        ]))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.updateExtents()
    return layer


def system_layer():
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "systems", "memory")
    layer.dataProvider().addAttributes([QgsField("type", QVariant.String)])
    layer.updateFields()
    features = []
    for role, coordinate in zip(
        ("Sending", "Receiving", "Spillover"),
        ((2.35, 48.85), (13.40, 52.52), (-77.04, 38.91)),
    ):
        feature = QgsFeature(layer.fields())
        feature["type"] = role
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*coordinate)))
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.updateExtents()
    return layer


styled_flows, flow_legend = style_flows(flow_layer())
_, system_legend = style_systems(system_layer(), "type")

flow_labels = {entry[0] for entry in flow_legend["entries"]}
system_colors = {entry[0]: entry[1:4] for entry in system_legend["entries"]}

print(json.dumps({
    "flows": sorted(flow_labels),
    "systems": system_colors,
    "flow_features": styled_flows.featureCount(),
}))

assert flow_labels == {
    "Domestic",
    "Adjacent countries",
    "Non-adjacent countries",
}
assert len(set(system_colors.values())) == 3

app.exitQgis()
