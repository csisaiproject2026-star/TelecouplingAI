from shared import file_reference_resolver
from shared.file_reference_resolver import resolve_render_file_references


def test_resolves_single_render_basename(monkeypatch):
    output = "/outputs/quality_c.tif"
    monkeypatch.setattr(file_reference_resolver.os.path, "isfile", lambda path: path == output)

    result = resolve_render_file_references(
        "render_spatial_file",
        {"file_path": "quality_c.tif"},
        [{"filename": "quality_c.tif", "path": output}],
    )

    assert result["file_path"] == output


def test_resolves_scene_slots_and_layers(monkeypatch):
    systems = "/outputs/systems_from_table.shp"
    flows = "/outputs/radial_flows.shp"
    monkeypatch.setattr(
        file_reference_resolver.os.path,
        "isfile",
        lambda path: path in {systems, flows},
    )
    candidates = [
        {"filename": "systems_from_table.shp", "path": systems},
        {"filename": "radial_flows.shp", "path": flows},
    ]

    result = resolve_render_file_references(
        "render_telecoupling_scene",
        {
            "systems_file": "systems_from_table.shp",
            "flows_file": "radial_flows.shp",
            "layers": ["systems_from_table.shp", "radial_flows.shp"],
        },
        candidates,
    )

    assert result["systems_file"] == systems
    assert result["flows_file"] == flows
    assert result["layers"] == [systems, flows]


def test_preserves_existing_and_unknown_paths(monkeypatch):
    existing = "/outputs/existing.tif"
    monkeypatch.setattr(file_reference_resolver.os.path, "isfile", lambda path: path == existing)

    result = resolve_render_file_references(
        "render_spatial_file",
        {"file_path": existing},
        [{"filename": "other.tif", "path": "/outputs/missing.tif"}],
    )

    assert result["file_path"] == existing
