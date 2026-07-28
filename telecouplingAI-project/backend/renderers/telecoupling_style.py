"""
Shared telecoupling cartography (flows / systems / agents).

Used by BOTH the single-file render worker (`_qgis_zoom_render_worker.py`) and
the composite scene worker (`_qgis_scene_render_worker.py`) so the styling has a
single source of truth — tweak a color/width/icon here and both renders follow.

This styling mirrors the Tonini & Liu 2017 Fig.10 cartography:
  * flows   — straight O-D lines bent into arcs, color + width graduated by a
              magnitude field, with origin/destination markers.
  * systems — categorized by a type field: Sending = hollow green triangle,
              Receiving = solid green triangle, Spillover = orange circle.
  * agents  — a person icon instead of a plain dot.

It only activates for OUR tool outputs (matched by filename + geometry type via
`detect_kind`) and can be disabled wholesale with env TELECOUPLING_STYLE=0.
"""
from __future__ import annotations
import os
from pathlib import Path

from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsMarkerLineSymbolLayer,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsWkbTypes,
    Qgis,
    QgsGradientColorRamp,
    QgsApplication,
    QgsSpatialIndex,
    QgsCoordinateTransform,
    QgsProject,
    QgsField,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from renderers.telecoupling_classification import (
    FLOW_RELATION_STYLES,
    country_relation,
    find_flow_relation_field,
    normalize_flow_relation,
    system_style,
)

TELECOUPLING_ENABLED = os.environ.get("TELECOUPLING_STYLE", "1").strip() != "0"
PERSON_SVG = str(Path(__file__).parent / "assets" / "agent_person.svg")


def flow_ramp() -> QgsGradientColorRamp:
    """Pink -> magenta gradient used for flow magnitude (matches Fig.10)."""
    return QgsGradientColorRamp(QColor(255, 190, 225), QColor(120, 0, 75))


# tc_role column value (written by our tools) -> render kind.
_ROLE_MAP = {
    "flow_type": "flows", "system_type": "systems",
    "agent_type": "agents", "cause_type": "causes",
}
# render_as override (passed when a user uploads a standalone shp) -> kind.
_RENDER_AS_MAP = {
    "flow": "flows", "flows": "flows",
    "system": "systems", "systems": "systems",
    "agent": "agents", "agents": "agents",
    "cause": "causes", "causes": "causes",
}
_LINE_KINDS = {"flows"}
_POINT_KINDS = {"systems", "agents", "causes"}


def _read_tc_role(layer):
    """Read the value of the 'tc_role' attribute from the first feature, or None
    if the layer has no such column."""
    try:
        field_names = [f.name() for f in layer.fields()]
        match = next((n for n in field_names if n.lower() == "tc_role"), None)
        if match is None:
            return None
        for feat in layer.getFeatures():
            v = feat[match]
            if v is not None:
                return str(v).strip().lower()
    except Exception:
        return None
    return None


def detect_kind(file_path, layer, force_role=None):
    """Return 'flows' | 'systems' | 'agents' | 'causes' | None.

    Detection is by an explicit telecoupling signal — NOT the filename:
      priority 1: ``force_role`` (the render_as param, set when a user uploads a
                  standalone shp and asks to render it as a given type);
      priority 2: the ``tc_role`` column our tools write into their outputs.
    A file with neither returns None -> generic rendering path, unchanged
    (so no other tool's output is ever touched). The geometry must match the
    kind (line for flows, point for the rest) or we fall back to None.
    """
    if not TELECOUPLING_ENABLED:
        return None
    kind = None
    if force_role:
        kind = _RENDER_AS_MAP.get(str(force_role).strip().lower())
    if kind is None:
        role = _read_tc_role(layer)
        if role:
            kind = _ROLE_MAP.get(role)
    if kind is None:
        return None
    try:
        geom = layer.geometryType()
    except Exception:
        return None
    # geometry sanity: don't force flow styling on points, or point styling on lines
    if kind in _LINE_KINDS and geom != QgsWkbTypes.LineGeometry:
        return None
    if kind in _POINT_KINDS and geom != QgsWkbTypes.PointGeometry:
        return None
    return kind


def _curve(geom, bend=0.18, seg=26):
    """Bend a straight 2-point line into a quadratic-bezier arc (display only)."""
    if geom.isMultipart():
        parts = geom.asMultiPolyline()
        pts = parts[0] if parts else []
    else:
        pts = geom.asPolyline()
    if len(pts) < 2:
        return geom
    a, b = pts[0], pts[-1]
    mx, my = (a.x() + b.x()) / 2, (a.y() + b.y()) / 2
    dx, dy = b.x() - a.x(), b.y() - a.y()
    cx, cy = mx - dy * bend, my + dx * bend
    out = []
    for i in range(seg + 1):
        t = i / seg
        x = (1 - t) ** 2 * a.x() + 2 * (1 - t) * t * cx + t * t * b.x()
        y = (1 - t) ** 2 * a.y() + 2 * (1 - t) * t * cy + t * t * b.y()
        out.append(QgsPointXY(x, y))
    return QgsGeometry.fromPolylineXY(out)


def _world_countries_layer():
    path = Path(QgsApplication.pkgDataPath()) / "resources" / "data" / "world_map.gpkg"
    if not path.is_file():
        return None
    layer = QgsVectorLayer(f"{path}|layername=countries", "countries", "ogr")
    return layer if layer.isValid() else None


def _country_for_point(point, features, index):
    point_geometry = QgsGeometry.fromPointXY(point)
    for feature_id in index.intersects(point_geometry.boundingBox()):
        feature = features.get(feature_id)
        if feature and feature.geometry().intersects(point_geometry):
            return feature_id
    nearest = index.nearestNeighbor(point, 1)
    if nearest:
        feature = features.get(nearest[0])
        if feature and feature.geometry().distance(point_geometry) <= 1.0:
            return nearest[0]
    return None


def _flow_relations(src):
    field_names = [field.name() for field in src.fields()]
    explicit_field = find_flow_relation_field(field_names)
    source_features = list(src.getFeatures())
    if explicit_field:
        return [normalize_flow_relation(feature[explicit_field]) for feature in source_features]

    countries = _world_countries_layer()
    if countries is None:
        return ["Distant systems"] * len(source_features)
    country_features = {feature.id(): feature for feature in countries.getFeatures()}
    country_index = QgsSpatialIndex()
    for country_feature in country_features.values():
        country_index.addFeature(country_feature)
    transform = QgsCoordinateTransform(src.crs(), countries.crs(), QgsProject.instance())
    pair_cache = {}
    relations = []
    for feature in source_features:
        geometry = feature.geometry()
        points = geometry.asMultiPolyline()[0] if geometry.isMultipart() else geometry.asPolyline()
        if len(points) < 2:
            relations.append("Distant systems")
            continue
        origin = transform.transform(QgsPointXY(points[0]))
        destination = transform.transform(QgsPointXY(points[-1]))
        origin_id = _country_for_point(origin, country_features, country_index)
        destination_id = _country_for_point(destination, country_features, country_index)
        pair = tuple(sorted(
            (origin_id, destination_id),
            key=lambda value: -1 if value is None else value,
        ))
        if pair not in pair_cache:
            touches = False
            distance = None
            if origin_id is not None and destination_id is not None and origin_id != destination_id:
                origin_geometry = country_features[origin_id].geometry()
                destination_geometry = country_features[destination_id].geometry()
                touches = origin_geometry.touches(destination_geometry)
                distance = origin_geometry.distance(destination_geometry)
            pair_cache[pair] = country_relation(origin_id, destination_id, touches, distance)
        relations.append(pair_cache[pair])
    return relations


def build_curved(src):
    """Return an in-memory copy of the flow layer with curved geometries,
    keeping all attributes so graduated styling still works."""
    mem = QgsVectorLayer("LineString?crs=%s" % src.crs().authid(), "flows_curved", "memory")
    dp = mem.dataProvider()
    relations = _flow_relations(src)
    dp.addAttributes(src.fields())
    dp.addAttributes([QgsField("tc_relation", QVariant.String)])
    mem.updateFields()
    feats = []
    for index, f in enumerate(src.getFeatures()):
        nf = QgsFeature(mem.fields())
        nf.setAttributes(f.attributes() + [relations[index]])
        nf.setGeometry(_curve(f.geometry()))
        feats.append(nf)
    dp.addFeatures(feats)
    mem.updateExtents()
    return mem


def flow_symbol(color, width, mcolor):
    """A line symbol with the given color/width PLUS a marker at the first and
    last vertex (origin + destination of each flow)."""
    sym = QgsLineSymbol.createSimple({"color": color.name(), "width": str(width)})
    for placement in (Qgis.MarkerLinePlacement.FirstVertex, Qgis.MarkerLinePlacement.LastVertex):
        ml = QgsMarkerLineSymbolLayer()
        ml.setPlacement(placement)
        ms = QgsMarkerSymbol.createSimple({
            "name": "circle", "color": mcolor.name(),
            "size": "3.2", "outline_color": "black", "outline_width": "0.3",
        })
        ml.setSubSymbol(ms)
        sym.appendSymbolLayer(ml)
    return sym


def style_flows(layer, magnitude_field=None):
    """Color curved flows by country relation, with magnitude fallback."""
    layer = build_curved(layer)
    relation_values = {
        str(feature["tc_relation"])
        for feature in layer.getFeatures()
        if feature["tc_relation"] not in (None, "")
    }
    if relation_values:
        categories, entries = [], []
        for label, rgb in FLOW_RELATION_STYLES.items():
            if label not in relation_values:
                continue
            red, green, blue = rgb
            color = QColor(red, green, blue)
            categories.append(
                QgsRendererCategory(label, flow_symbol(color, 1.4, color), label)
            )
            entries.append((label, red, green, blue, "line"))
        layer.setRenderer(QgsCategorizedSymbolRenderer("tc_relation", categories))
        return layer, {
            "kind": "categorical",
            "field": "System relation",
            "entries": entries,
        }

    fr = flow_ramp()
    mag = (magnitude_field or "").strip()
    fields = [f.name() for f in layer.fields()]
    if mag and mag in fields:
        idx = layer.fields().indexOf(mag)
        vmin, vmax = layer.minimumValue(idx), layer.maximumValue(idx)
        if vmin is None or vmax is None or vmin == vmax:
            vmax = (vmin or 0) + 1e-9
        n = 4
        step = (vmax - vmin) / n
        widths = [0.3, 0.75, 1.4, 2.1]
        ranges = []
        for i in range(n):
            lo, hi = vmin + i * step, vmin + (i + 1) * step
            c = fr.color((i + 0.5) / n)
            ranges.append(QgsRendererRange(lo, hi, flow_symbol(c, widths[i], c),
                                           "%.0f – %.0f" % (lo, hi)))
        layer.setRenderer(QgsGraduatedSymbolRenderer(mag, ranges))
        legend = {"kind": "graduated", "field": mag, "min": vmin, "max": vmax, "ramp": fr}
    else:
        c = QColor(200, 30, 120)
        layer.setRenderer(QgsSingleSymbolRenderer(flow_symbol(c, 0.9, c)))
        # uniform (no magnitude field) -> one-entry legend so the flow line is
        # explained, instead of no legend at all
        legend = {"kind": "categorical", "field": "Flows",
                  "entries": [("Flow", 200, 30, 120, "line")]}
    return layer, legend


def style_systems(layer, category_field=None):
    """Categorize by the system-type field: Sending = upright solid green
    triangle, Receiving = inverted (180°) solid green triangle, Spillover =
    orange circle. (Inverted triangle is the upright one rotated 180°, since
    QGIS has no dedicated downward-triangle marker shape.)"""
    cf = (category_field or "").strip()
    if not cf:
        for f in layer.fields():
            nm = f.name().lower()
            if nm == "tc_role":            # our own tag, never a category
                continue
            if any(k in nm for k in ("type", "system", "role", "category", "class")):
                cf = f.name()
                break
    if not cf:
        ms = QgsMarkerSymbol.createSimple({
            "name": "triangle", "color": "#3fae3f",
            "size": "4.5", "outline_color": "black", "outline_width": "0.5"})
        layer.setRenderer(QgsSingleSymbolRenderer(ms))
        return layer, None
    vals = sorted({f[cf] for f in layer.getFeatures() if f[cf] is not None}, key=str)
    cats, entries = [], []
    for v in vals:
        col, mshape, size, angle, gshape = system_style(v)
        ms = QgsMarkerSymbol.createSimple({
            "name": mshape, "color": "#%02x%02x%02x" % col, "size": size,
            "angle": angle, "outline_color": "black", "outline_width": "0.6"})
        cats.append(QgsRendererCategory(v, ms, str(v)))
        entries.append((str(v), col[0], col[1], col[2], gshape))
    layer.setRenderer(QgsCategorizedSymbolRenderer(cf, cats))
    return layer, {"kind": "categorical", "field": cf, "entries": entries}


def style_agents(layer):
    """Replace the default dot with a person icon."""
    if os.path.isfile(PERSON_SVG):
        sl = QgsSvgMarkerSymbolLayer(PERSON_SVG)
        sl.setSize(13)
        sym = QgsMarkerSymbol()
        sym.changeSymbolLayer(0, sl)
    else:
        sym = QgsMarkerSymbol.createSimple({
            "name": "pentagon", "color": "#333333",
            "size": "7", "outline_color": "white", "outline_width": "0.6"})
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    # one-entry legend so the person marker is explained (matches causes)
    return layer, {"kind": "categorical", "field": "Agents",
                   "entries": [("Agent", 51, 51, 51, "person")]}


def style_causes(layer):
    """Telecoupling causes (drivers) -> red star markers."""
    ms = QgsMarkerSymbol.createSimple({
        "name": "star", "color": "#d62728",
        "size": "11", "outline_color": "black", "outline_width": "0.5"})
    layer.setRenderer(QgsSingleSymbolRenderer(ms))
    # one-entry legend so the star is explained
    return layer, {"kind": "categorical", "field": "Causes",
                   "entries": [("Cause", 214, 39, 40, "star")]}


def apply_style(kind, layer, magnitude_field=None, category_field=None):
    if kind == "flows":
        return style_flows(layer, magnitude_field)
    if kind == "systems":
        return style_systems(layer, category_field)
    if kind == "agents":
        return style_agents(layer)
    if kind == "causes":
        return style_causes(layer)
    return layer, None
