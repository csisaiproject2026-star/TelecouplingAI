from renderers.telecoupling_classification import (
    country_relation,
    find_flow_relation_field,
    normalize_flow_relation,
    system_style,
)


def test_system_roles_have_distinct_colors_and_shapes():
    sending = system_style("Sending")
    receiving = system_style("Receiving")
    spillover = system_style("Spillover")

    assert len({sending[0], receiving[0], spillover[0]}) == 3
    assert sending[4] == "triangle_up"
    assert receiving[4] == "triangle_down"
    assert spillover[4] == "circle"


def test_relation_field_detection_accepts_shapefile_truncation():
    assert find_flow_relation_field(["value", "flow_relat"]) == "flow_relat"
    assert find_flow_relation_field(["id", "is_adjacent"]) == "is_adjacent"


def test_relation_values_are_normalized():
    assert normalize_flow_relation(True) == "Adjacent systems"
    assert normalize_flow_relation("non_adjacent") == "Distant systems"
    assert normalize_flow_relation("Non-adjacent countries") == "Distant systems"
    assert normalize_flow_relation("domestic") == "Domestic systems"
    assert normalize_flow_relation("Domestic systems") == "Domestic systems"


def test_country_relation_classification():
    assert country_relation(4, 4) == "Domestic systems"
    assert country_relation(4, 7, touches=True) == "Adjacent systems"
    assert country_relation(4, 7, distance=0.01) == "Adjacent systems"
    assert country_relation(4, 7, distance=5) == "Distant systems"
    assert country_relation(None, 7) == "Distant systems"
