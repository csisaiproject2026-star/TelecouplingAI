"""Pure classification helpers shared by telecoupling renderers."""
from __future__ import annotations


SYSTEM_STYLES = {
    "sending": ((0, 184, 217), "triangle", "5.5", "0", "triangle_up"),
    "receiving": ((232, 62, 140), "triangle", "5.5", "180", "triangle_down"),
    "spillover": ((255, 176, 0), "circle", "4.5", "0", "circle"),
}

FLOW_RELATION_STYLES = {
    "Domestic": (255, 209, 102),
    "Adjacent countries": (0, 213, 255),
    "Non-adjacent countries": (255, 59, 141),
}

FLOW_RELATION_FIELDS = (
    "flow_relation",
    "country_relation",
    "adjacency",
    "adjacent",
    "neighbour",
    "neighbor",
)


def system_style(value):
    text = str(value or "").strip().lower()
    if "spill" in text:
        return SYSTEM_STYLES["spillover"]
    if "receiv" in text or "reciev" in text:
        return SYSTEM_STYLES["receiving"]
    return SYSTEM_STYLES["sending"]


def find_flow_relation_field(field_names):
    names = list(field_names)
    lowered = {str(name).lower(): name for name in names}
    for candidate in FLOW_RELATION_FIELDS:
        if candidate in lowered:
            return lowered[candidate]
    for name in names:
        lowered_name = str(name).lower()
        if lowered_name.startswith("flow_relat") or any(
            token in lowered_name for token in ("adjacen", "neighbou", "neighbor")
        ):
            return name
    return None


def normalize_flow_relation(value):
    if isinstance(value, bool):
        return "Adjacent countries" if value else "Non-adjacent countries"
    text = str(value or "").strip().lower().replace("_", "-")
    if not text:
        return "Non-adjacent countries"
    if text in {"domestic", "same", "same-country", "internal", "within-country"}:
        return "Domestic"
    if text in {"1", "true", "yes", "y"}:
        return "Adjacent countries"
    if text in {"0", "false", "no", "n"}:
        return "Non-adjacent countries"
    if any(token in text for token in ("non-adjacent", "nonadjacent", "not-adjacent", "distant")):
        return "Non-adjacent countries"
    if any(token in text for token in ("adjacent", "neighbour", "neighbor", "border")):
        return "Adjacent countries"
    return "Non-adjacent countries"


def country_relation(origin_id, destination_id, touches=False, distance=None):
    if origin_id is None or destination_id is None:
        return "Non-adjacent countries"
    if origin_id == destination_id:
        return "Domestic"
    if touches or (distance is not None and 0 <= distance <= 0.02):
        return "Adjacent countries"
    return "Non-adjacent countries"
