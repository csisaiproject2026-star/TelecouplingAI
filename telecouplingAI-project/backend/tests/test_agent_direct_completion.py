"""Deterministic completion for unambiguous single-tool requests."""
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Use the uploaded CSV and call run_ols.", "run_model_selection_ols"),
        ("Run the CO2 emissions tool.", "run_co2_emissions"),
        ("Run a cost-benefit analysis.", "run_cost_benefit_analysis"),
        (
            "Use the uploaded tables and call the single cost-benefit function.",
            "run_cost_benefit_analysis",
        ),
        ("Run food security with the uploaded table.", "run_food_security"),
        ("Run carbon storage.", "run_carbon_storage"),
    ],
)
def test_detects_unambiguous_direct_tool(message, expected):
    assert agent._direct_completion_tool_for_message(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "Run OLS and CO2 emissions.",
        "Run carbon storage and OLS.",
        "Run carbon storage, then render the result.",
        "Run carbon storage and explain the results.",
        "Run carbon storage and provide an explanation of the results.",
        "Run carbon storage and give me a summary of the results.",
        "Run carbon storage and provide an analysis of the results.",
        "Run carbon storage and provide a discussion of the results.",
        "Run carbon storage and provide a description of the results.",
        "Build a workflow with carbon storage.",
        "Call render_spatial_file for output.tif.",
        "Read the output with read_file_content.",
    ],
)
def test_ambiguous_or_follow_up_requests_keep_gemini_iteration(message):
    assert agent._direct_completion_tool_for_message(message) is None


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ([], "No output files were generated."),
        ([{"filename": "one.csv"}], "1 output file was generated."),
        (
            [{"filename": "one.csv"}, {"filename": "two.tif"}],
            "2 output files were generated.",
        ),
    ],
)
def test_formats_output_file_count(files, expected):
    text = agent._format_direct_tool_completion({"files": files})
    assert expected in text
    assert "Please interpret the results." in text


def test_exact_preprocessor_name_is_not_confused_with_main_tool():
    assert agent._direct_completion_tool_for_message(
        "Call run_coastal_blue_carbon_preprocessor."
    ) == "run_coastal_blue_carbon_preprocessor"


class _SessionManager:
    get_uploaded_files = AsyncMock(return_value=[])
    get_output_files = AsyncMock(return_value=[])
    get_workflow_plan = AsyncMock(return_value=None)


def _tool_response(tool_name: str):
    content = types.Content(
        role="model",
        parts=[
            types.Part.from_function_call(
                name=tool_name,
                args={"input_csv": "/data/uploads/test/input.csv"},
            )
        ],
    )
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


def _text_response():
    content = types.Content(
        role="model",
        parts=[types.Part.from_text(text="AI explanation")],
    )
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


async def _fake_dispatch(*args, event_callback, **kwargs):
    result = {
        "type": "tool_result",
        "files": [
            {"filename": "summary.csv", "path": "/data/outputs/summary.csv"},
            {"filename": "details.csv", "path": "/data/outputs/details.csv"},
        ],
    }
    await agent._maybe_await(event_callback(result))
    return "task-1", result


@pytest.mark.asyncio
async def test_successful_direct_tool_uses_one_gemini_call(monkeypatch):
    calls = 0
    events = []

    async def fake_generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise AssertionError("direct completion made an unnecessary Gemini call")
        await agent._maybe_await(args[4]({
            "type": "text_chunk",
            "content": "I will run the tool now.",
        }))
        return _tool_response("run_model_selection_ols")

    monkeypatch.setattr(agent.settings, "DIRECT_TOOL_COMPLETION_ENABLED", True)
    monkeypatch.setattr(agent, "_get_client", lambda: object())
    monkeypatch.setattr(agent, "_generate_streaming", fake_generate)
    monkeypatch.setattr(agent, "_dispatch_tool_and_relay", _fake_dispatch)
    monkeypatch.setattr(agent, "validate_file_params_exist", lambda *args: None)
    monkeypatch.setattr(agent, "validate_input_files", lambda *args: None)
    monkeypatch.setitem(
        sys.modules,
        "workers.task_queue",
        SimpleNamespace(run_tool_task=object()),
    )

    await agent.run_agent(
        "Use the uploaded CSV and call run_ols.",
        "session-1",
        [],
        events.append,
        session_manager=_SessionManager(),
    )

    assert calls == 1
    completion = [e for e in events if e.get("type") == "text_chunk"]
    assert len(completion) == 1
    assert "2 output files were generated." in completion[0]["content"]
    assert events[-1] == {"type": "done"}


@pytest.mark.asyncio
async def test_interpretation_request_keeps_second_gemini_call(monkeypatch):
    responses = iter([
        _tool_response("run_model_selection_ols"),
        _text_response(),
    ])
    calls = 0

    async def fake_generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        return next(responses)

    monkeypatch.setattr(agent.settings, "DIRECT_TOOL_COMPLETION_ENABLED", True)
    monkeypatch.setattr(agent, "_get_client", lambda: object())
    monkeypatch.setattr(agent, "_generate_streaming", fake_generate)
    monkeypatch.setattr(agent, "_dispatch_tool_and_relay", _fake_dispatch)
    monkeypatch.setattr(agent, "validate_file_params_exist", lambda *args: None)
    monkeypatch.setattr(agent, "validate_input_files", lambda *args: None)
    monkeypatch.setitem(
        sys.modules,
        "workers.task_queue",
        SimpleNamespace(run_tool_task=object()),
    )

    await agent.run_agent(
        "Use the uploaded CSV, call run_ols, and explain the results.",
        "session-2",
        [],
        lambda event: None,
        session_manager=_SessionManager(),
    )

    assert calls == 2


@pytest.mark.asyncio
async def test_failed_tool_keeps_second_gemini_call(monkeypatch):
    responses = iter([
        _tool_response("run_model_selection_ols"),
        _text_response(),
    ])
    calls = 0

    async def fake_generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        return next(responses)

    async def failing_dispatch(*args, **kwargs):
        raise RuntimeError("worker failed")

    monkeypatch.setattr(agent.settings, "DIRECT_TOOL_COMPLETION_ENABLED", True)
    monkeypatch.setattr(agent, "_get_client", lambda: object())
    monkeypatch.setattr(agent, "_generate_streaming", fake_generate)
    monkeypatch.setattr(agent, "_dispatch_tool_and_relay", failing_dispatch)
    monkeypatch.setattr(agent, "validate_file_params_exist", lambda *args: None)
    monkeypatch.setattr(agent, "validate_input_files", lambda *args: None)
    monkeypatch.setitem(
        sys.modules,
        "workers.task_queue",
        SimpleNamespace(run_tool_task=object()),
    )

    await agent.run_agent(
        "Use the uploaded CSV and call run_ols.",
        "session-3",
        [],
        lambda event: None,
        session_manager=_SessionManager(),
    )

    assert calls == 2
