"""Offline coverage for workflow generation isolation and strict plan validation."""
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent
from workflow.catalog import CAPABILITY_CATALOG, plan_from_llm_args
from workflow.engine import validate_plan
from workflow.schema import plan_from_dict


def test_workflow_scoped_uploads_excludes_previous_generation():
    uploaded = [
        {"filename": "old.csv", "path": "/uploads/old.csv"},
        {"filename": "new.csv", "path": "/uploads/new.csv"},
    ]
    plan = {"_workflow_scope": {"upload_start_index": 1}}

    assert agent._workflow_scoped_uploads(plan, uploaded) == [uploaded[1]]


def test_first_workflow_scope_defaults_to_all_uploads():
    uploaded = [{"filename": "input.csv", "path": "/uploads/input.csv"}]

    assert agent._workflow_scoped_uploads({}, uploaded) == uploaded


def test_guide_workflows_keep_agents_steps_in_planner_catalog():
    tourism = CAPABILITY_CATALOG.split(
        "## Few-shot: tourism telecoupling", 1
    )[1].split("## Few-shot: soybean telecoupling", 1)[0]
    soybean = CAPABILITY_CATALOG.split(
        "## Few-shot: soybean telecoupling", 1
    )[1]

    assert "up to 6 steps" in tourism
    assert tourism.index("run_add_agents_interactively") < tourism.index(
        "run_draw_radial_flows"
    )
    assert "up to 5 steps" in soybean
    assert soybean.index("run_add_agents_interactively") < soybean.index(
        "run_draw_radial_flows"
    )


@pytest.mark.parametrize(
    "message",
    [
        "I have NOT uploaded the files yet",
        "execute_workflow_plan: I have not uploaded the files yet.",
    ],
)
def test_not_uploaded_confirmation_is_non_executable(message):
    assert agent._workflow_files_not_uploaded(message)


@pytest.mark.parametrize(
    "item",
    [
        {"param": "input_csv", "source": "input"},
        {"param": "field", "source": "literal"},
        {"param": "upstream", "source": "step"},
        {"param": "field", "source": "literal,value:country"},
    ],
)
def test_plan_parser_rejects_malformed_sources(item):
    with pytest.raises(ValueError):
        plan_from_llm_args({
            "case_name": "invalid",
            "steps": [{"id": "s1", "tool": "tool", "inputs": [item]}],
        })


def test_plan_validation_rejects_empty_and_duplicate_steps():
    empty = plan_from_dict({"case_name": "empty", "steps": []})
    duplicate = plan_from_dict({
        "case_name": "duplicate",
        "steps": [
            {"id": "s1", "tool": "tool", "inputs": {}},
            {"id": "s1", "tool": "tool", "inputs": {}},
        ],
    })

    assert "Plan must contain at least one step." in validate_plan(empty, {"tool"})
    assert "Plan has duplicate step ids: s1." in validate_plan(duplicate, {"tool"})


def _shared_flows_plan():
    return plan_from_dict({
        "case_name": "tourism",
        "required_inputs": [
            {"id": "flows_csv", "label": "Flows CSV", "file_kind": "table"},
            {
                "id": "_ovr__co2__input_csv",
                "label": "CO2 CSV",
                "file_kind": "table",
            },
        ],
        "steps": [
            {
                "id": "flows",
                "tool": "run_draw_radial_flows",
                "inputs": {
                    "input_csv": {"source": "input", "ref": "flows_csv"},
                    "from_x_field": {"source": "literal", "value": "FROM_X"},
                    "from_y_field": {"source": "literal", "value": "FROM_Y"},
                    "to_x_field": {"source": "literal", "value": "TO_X"},
                    "to_y_field": {"source": "literal", "value": "TO_Y"},
                },
            },
            {
                "id": "co2",
                "tool": "run_co2_emissions",
                "inputs": {
                    "input_csv": {
                        "source": "input",
                        "ref": "_ovr__co2__input_csv",
                    },
                    "animal_count_field": {"source": "literal", "value": "Quantity"},
                    "length_km_field": {"source": "literal", "value": "length_km"},
                },
            },
        ],
    })


def test_explicit_csv_can_be_reused_when_shared_step_columns_match(tmp_path):
    flows = tmp_path / "flows_with_distance.csv"
    flows.write_text(
        "FROM_X,FROM_Y,TO_X,TO_Y,Quantity,length_km\n"
        "1,2,3,4,5,6\n",
        encoding="utf-8",
    )
    path = str(flows)

    mapped = agent._auto_map_inputs(
        _shared_flows_plan(),
        {"_ovr__co2__input_csv": path},
        [{"filename": flows.name, "path": path}],
        prefer_paths={path},
    )

    assert mapped["flows_csv"] == path
    assert mapped["_ovr__co2__input_csv"] == path


def test_explicit_csv_is_not_reused_when_shared_step_columns_do_not_match(tmp_path):
    co2_only = tmp_path / "co2_only.csv"
    co2_only.write_text("Quantity,length_km\n5,6\n", encoding="utf-8")
    path = str(co2_only)

    mapped = agent._auto_map_inputs(
        _shared_flows_plan(),
        {"_ovr__co2__input_csv": path},
        [{"filename": co2_only.name, "path": path}],
        prefer_paths={path},
    )

    assert "flows_csv" not in mapped


class _ScopeSessionManager:
    def __init__(self):
        self.uploaded = [{"filename": "old.csv", "path": "/uploads/old.csv"}]
        self.plan = {
            "case_name": "old",
            "description": "old plan",
            "required_inputs": [],
            "steps": [],
            "_workflow_scope": {
                "id": "scope-1",
                "upload_start_index": 0,
                "status": "active",
            },
        }
        self.scope = self.plan["_workflow_scope"]
        self.plan_writes = []

    async def get_uploaded_files(self, session_id):
        return list(self.uploaded)

    async def get_output_files(self, session_id):
        return [{"filename": "old-result.csv", "path": "/outputs/old-result.csv"}]

    async def get_workflow_plan(self, session_id):
        return self.plan

    async def get_workflow_scope(self, session_id):
        return self.scope

    async def set_workflow_plan(self, session_id, plan):
        self.plan_writes.append(plan)
        self.plan = plan

    async def set_workflow_scope(self, session_id, scope):
        self.scope = scope


def _proposal_response(case_name="tourism"):
    content = types.Content(
        role="model",
        parts=[
            types.Part.from_text(text="Here is the plan."),
            types.Part.from_function_call(
                name="propose_workflow_plan",
                args={
                    "case_name": case_name,
                    "description": "new plan",
                    "required_inputs": [],
                    "steps": [{
                        "id": "s1",
                        "tool": "run_network_analysis_grouping",
                        "inputs": [],
                    }],
                },
            ),
        ],
    )
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


@pytest.mark.asyncio
async def test_replacement_plan_uses_only_current_goal(monkeypatch):
    message = "Analyze a new tourism telecoupling workflow."
    manager = _ScopeSessionManager()
    events = []
    model_inputs = []

    async def fake_generate(client, model, contents, config, event_callback):
        model_inputs.append(list(contents))
        return _proposal_response()

    monkeypatch.setattr(agent, "_get_client", lambda: object())
    monkeypatch.setattr(agent, "_generate_streaming", fake_generate)
    monkeypatch.setattr(agent, "validate_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent, "_enrich_plan_for_ui", lambda plan: {})
    monkeypatch.setitem(
        sys.modules,
        "workers.task_queue",
        SimpleNamespace(run_tool_task=object()),
    )

    await agent.run_agent(
        message,
        "workflow-scope",
        [],
        events.append,
        chat_history=[{"role": "user", "text": "old soybean objective"}],
        session_manager=manager,
    )

    assert len(model_inputs) == 1
    assert len(model_inputs[0]) == 1
    assert model_inputs[0][0].role == "user"
    assert model_inputs[0][0].parts[0].text == message
    assert manager.plan_writes[0] is None
    assert manager.plan["_workflow_scope"]["upload_start_index"] == 1
    plan_event = next(event for event in events if event["type"] == "workflow_plan")
    assert "_workflow_scope" not in plan_event["plan"]


@pytest.mark.asyncio
async def test_auto_first_plan_keeps_preplanning_uploads(monkeypatch):
    manager = _ScopeSessionManager()
    manager.plan = None
    manager.scope = None

    async def fake_generate(client, model, contents, config, event_callback):
        return _proposal_response("first")

    monkeypatch.setattr(agent, "_get_client", lambda: object())
    monkeypatch.setattr(agent, "_generate_streaming", fake_generate)
    monkeypatch.setattr(agent, "validate_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent, "_enrich_plan_for_ui", lambda plan: {})
    monkeypatch.setitem(
        sys.modules,
        "workers.task_queue",
        SimpleNamespace(run_tool_task=object()),
    )

    await agent.run_agent(
        "Please help with this case.",
        "workflow-first",
        [],
        lambda event: None,
        session_manager=manager,
    )

    assert manager.plan["_workflow_scope"]["upload_start_index"] == 0


@pytest.mark.asyncio
async def test_unmapped_workflow_input_disables_follow_up_tools(monkeypatch):
    manager = _ScopeSessionManager()
    manager.uploaded = []
    manager.plan = {
        "case_name": "missing-input",
        "required_inputs": [
            {"id": "flows_csv", "label": "Flows CSV", "file_kind": "table"},
        ],
        "steps": [{
            "id": "flows",
            "tool": "run_draw_radial_flows",
            "inputs": {
                "input_csv": {"source": "input", "ref": "flows_csv"},
            },
        }],
        "_workflow_scope": {
            "id": "scope-1",
            "upload_start_index": 0,
            "status": "active",
        },
    }
    calls = 0

    async def fake_generate(client, model, contents, config, event_callback):
        nonlocal calls
        calls += 1
        if calls == 1:
            content = types.Content(
                role="model",
                parts=[types.Part.from_function_call(
                    name="execute_workflow_plan",
                    args={},
                )],
            )
            return SimpleNamespace(candidates=[SimpleNamespace(content=content)])
        if calls == 2:
            assert config.tool_config.function_calling_config.mode == "NONE"
            return SimpleNamespace(candidates=[SimpleNamespace(
                content=None,
                finish_reason="EMPTY",
            )])
        assert config.tool_config.function_calling_config.mode == "NONE"
        content = types.Content(
            role="model",
            parts=[types.Part.from_text(text="Please upload the flows CSV.")],
        )
        return SimpleNamespace(candidates=[SimpleNamespace(content=content)])

    monkeypatch.setattr(agent, "_get_client", lambda: object())
    monkeypatch.setattr(agent, "_generate_streaming", fake_generate)
    monkeypatch.setattr(agent.asyncio, "sleep", AsyncMock())
    monkeypatch.setitem(
        sys.modules,
        "workers.task_queue",
        SimpleNamespace(run_tool_task=object()),
    )

    await agent.run_agent(
        "Confirmed — run the saved workflow.",
        "workflow-missing-input",
        [],
        lambda event: None,
        session_manager=manager,
    )

    assert calls == 3
