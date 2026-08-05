import json
from pathlib import Path

from shared.tool_file_specs import TOOL_FILE_SPECS
from workflow.catalog import CAPABILITY_CATALOG
from workflow.engine import validate_plan
from workflow.schema import plan_from_dict


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_plan(relative_path: str):
    path = REPO_ROOT / relative_path
    return plan_from_dict(json.loads(path.read_text(encoding="utf-8")))


def test_workflow_catalog_exposes_add_agents_and_updated_examples():
    assert "run_add_agents_interactively" in CAPABILITY_CATALOG
    assert "up to 5 steps" in CAPABILITY_CATALOG
    assert "up to 6 steps" in CAPABILITY_CATALOG
    assert CAPABILITY_CATALOG.count("run_add_agents_interactively") >= 3


def test_soybean_plan_has_five_valid_steps_with_agents():
    plan = _load_plan(
        "usecaseLevel_workflow/SoybeanTelecoupling_Workflow/soybean_plan.json"
    )

    assert [step.tool for step in plan.steps] == [
        "run_draw_systems_from_table",
        "run_add_agents_interactively",
        "run_draw_radial_flows",
        "run_crop_production_percentile",
        "run_habitat_quality",
    ]
    assert validate_plan(plan, set(TOOL_FILE_SPECS)) == []


def test_tourism_plan_has_six_valid_steps_with_agents():
    plan = _load_plan(
        "usecaseLevel_workflow/TourismTelecoupling_Workflow/tourism_plan.json"
    )

    assert [step.tool for step in plan.steps] == [
        "run_draw_systems_from_table",
        "run_network_analysis_grouping",
        "run_add_agents_interactively",
        "run_draw_radial_flows",
        "run_co2_emissions",
        "run_factor_analysis_mixed_data",
    ]
    assert validate_plan(plan, set(TOOL_FILE_SPECS)) == []
