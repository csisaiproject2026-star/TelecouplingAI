"""
Workflow engine: validate a WorkflowPlan and run it step-by-step against the
existing tools. Deterministic — no LLM here. The LLM only proposes the plan.

run_plan() reuses the same dispatch the Celery worker uses (workers.task_queue.
execute_tool), so a workflow step runs a tool exactly like a normal single-tool call.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Awaitable, Callable

from shared.tool_file_specs import TOOL_FILE_SPECS
from .schema import WorkflowPlan, WorkflowStep

logger = logging.getLogger(__name__)

EventCb = Callable[[dict], None]


# ---------------------------------------------------------------------------
# Validation (pure — no tool execution)
# ---------------------------------------------------------------------------
def _topological_order(plan: WorkflowPlan) -> list[WorkflowStep] | None:
    """Kahn's algorithm over depends_on. Returns None if there is a cycle."""
    by_id = {s.id: s for s in plan.steps}
    indeg = {s.id: 0 for s in plan.steps}
    for s in plan.steps:
        for dep in s.depends_on:
            if dep in by_id:
                indeg[s.id] += 1
    # seed with the plan's own order to keep output stable/intuitive
    ready = [s.id for s in plan.steps if indeg[s.id] == 0]
    order: list[str] = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for s in plan.steps:
            if cur in s.depends_on:
                indeg[s.id] -= 1
                if indeg[s.id] == 0:
                    ready.append(s.id)
    if len(order) != len(plan.steps):
        return None
    return [by_id[i] for i in order]


def validate_plan(plan: WorkflowPlan, available_tools: set[str]) -> list[str]:
    """Return a list of human-readable errors; empty means the plan is runnable."""
    errors: list[str] = []
    seen_steps: set[str] = set()

    step_ids = [step.id for step in plan.steps]
    if not step_ids:
        errors.append("Plan must contain at least one step.")
    if any(not step_id for step_id in step_ids):
        errors.append("Every plan step must have a non-empty id.")
    duplicate_ids = sorted({
        step_id
        for step_id in step_ids
        if step_id and step_ids.count(step_id) > 1
    })
    if duplicate_ids:
        errors.append(f"Plan has duplicate step ids: {', '.join(duplicate_ids)}.")

    if not step_ids or any(not step_id for step_id in step_ids) or duplicate_ids:
        order = plan.steps
    else:
        order = _topological_order(plan)
        if order is None:
            errors.append("Plan has a dependency cycle (depends_on).")
            order = plan.steps  # fall back so we still report per-step issues

    for step in order:
        # tool exists
        if step.tool not in available_tools:
            errors.append(f"[{step.id}] unknown tool '{step.tool}'.")

        # required file params for this tool are all supplied as inputs
        for spec in TOOL_FILE_SPECS.get(step.tool, []):
            param, required = spec[0], spec[1]
            if required and param not in step.inputs:
                errors.append(f"[{step.id}] missing required file input '{param}' for {step.tool}.")

        # each input source resolves to something real
        for param, src in step.inputs.items():
            if src.source == "input":
                if not src.ref:
                    errors.append(f"[{step.id}] input '{param}' with source=input is missing ref.")
                elif src.ref not in plan.input_ids:
                    errors.append(f"[{step.id}] input '{param}' references unknown upload '{src.ref}'.")
            elif src.source == "step":
                if not src.ref:
                    errors.append(f"[{step.id}] input '{param}' with source=step is missing ref.")
                elif src.ref not in plan.step_ids:
                    errors.append(f"[{step.id}] input '{param}' references unknown step '{src.ref}'.")
                elif src.ref not in seen_steps:
                    errors.append(f"[{step.id}] input '{param}' uses output of '{src.ref}' which runs later (order/depends_on).")
            elif src.source == "literal":
                if src.value is None:
                    errors.append(f"[{step.id}] input '{param}' with source=literal is missing value.")
            else:
                errors.append(f"[{step.id}] input '{param}' has invalid source '{src.source}'.")

        seen_steps.add(step.id)

    return errors


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
def _resolve_param(step: WorkflowStep, param: str, src, inputs: dict[str, str],
                   step_outputs: dict[str, list[dict]]) -> object:
    if src.source == "literal":
        return src.value
    if src.source == "input":
        if src.ref not in inputs:
            raise KeyError(f"[{step.id}] required upload '{src.ref}' (for '{param}') was not provided.")
        return inputs[src.ref]
    if src.source == "step":
        files = step_outputs.get(src.ref, [])
        if not files:
            raise KeyError(f"[{step.id}] upstream step '{src.ref}' produced no files for '{param}'.")
        if src.file:
            for f in files:
                if src.file in str(f.get("filename", "")) or src.file in str(f.get("path", "")):
                    return f.get("path")
            raise KeyError(f"[{step.id}] no output of '{src.ref}' matches '{src.file}'.")
        return files[0].get("path")
    raise ValueError(f"[{step.id}] invalid source '{src.source}' for '{param}'.")


def run_plan(plan: WorkflowPlan, inputs: dict[str, str], session_id: str,
             event_cb: EventCb | None = None) -> dict:
    """
    Execute a validated plan. `inputs` maps required-input id -> file path on disk.
    Returns a run context: per-step status/outputs/errors, all files, and warnings.
    Stops at the first failing step (v0.1 policy).
    """
    from workers.task_queue import execute_tool  # lazy: avoids celery import at module load

    def emit(ev: dict) -> None:
        if event_cb:
            try:
                event_cb(ev)
            except Exception:  # event sink must never break the run
                logger.exception("workflow event_cb failed")

    order = _topological_order(plan) or plan.steps
    ctx: dict = {"case_name": plan.case_name, "steps": {}, "files": [], "warnings": []}

    emit({"type": "workflow_start", "case_name": plan.case_name,
          "n_steps": len(order), "steps": [s.id for s in order]})

    # Calibrate the plan's column/field mappings against the REAL uploaded files
    # (the planner guessed them blind). Auto-fix case-only diffs; block on the rest
    # so we never run a tool against a column that does not exist.
    from .reconcile import reconcile_plan
    rec = reconcile_plan(plan, inputs)
    if rec["fixes"]:
        emit({"type": "plan_reconciled", "fixes": rec["fixes"]})
    if rec["mismatches"]:
        ctx["status"] = "reconcile_error"
        ctx["mismatches"] = rec["mismatches"]
        emit({"type": "plan_reconcile_failed", "mismatches": rec["mismatches"]})
        emit({"type": "workflow_done", "status": "reconcile_error",
              "mismatches": rec["mismatches"]})
        return ctx

    for idx, step in enumerate(order, 1):
        task_id = uuid.uuid4().hex
        emit({"type": "step_started", "step": step.id, "tool": step.tool,
              "component": step.component, "index": idx, "total": len(order),
              "rationale": step.rationale})
        try:
            params = {p: _resolve_param(step, p, src, inputs, {k: v["outputs"] for k, v in ctx["steps"].items()})
                      for p, src in step.inputs.items()}
            result = execute_tool(
                step.tool, params, session_id, task_id,
                progress_callback=lambda p, m, _s=step.id: emit(
                    {"type": "step_progress", "step": _s, "progress": p, "message": m}),
            )
            files = result.get("files", []) if isinstance(result, dict) else []
            warns = result.get("warnings", []) if isinstance(result, dict) else []
            ctx["steps"][step.id] = {"status": "done", "tool": step.tool,
                                     "outputs": files, "warnings": warns}
            ctx["files"].extend(files)
            ctx["warnings"].extend(f"[{step.id}] {w}" for w in warns)
            emit({"type": "step_done", "step": step.id, "files": files, "warnings": warns})
        except Exception as e:  # noqa: BLE001 — surface, don't crash the whole engine
            ctx["steps"][step.id] = {"status": "error", "tool": step.tool,
                                     "outputs": [], "error": str(e)}
            emit({"type": "step_error", "step": step.id, "error": str(e)})
            ctx["status"] = "error"
            ctx["failed_step"] = step.id
            emit({"type": "workflow_done", "status": "error", "failed_step": step.id})
            return ctx

    ctx["status"] = "done"
    emit({"type": "workflow_done", "status": "done",
          "n_files": len(ctx["files"]), "warnings": ctx["warnings"]})
    return ctx


async def run_plan_async(plan: WorkflowPlan, inputs: dict[str, str], session_id: str,
                         emit: Callable[[dict], Awaitable[None]]) -> dict:
    """
    Async wrapper: run_plan executes tools in-process (execute_tool uses asyncio.run),
    which can't run inside the live event loop — so run it in a worker thread and bridge
    its events to the async `emit` via a thread-safe queue. Returns the run context.
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def thread_cb(ev: dict) -> None:
        loop.call_soon_threadsafe(q.put_nowait, ev)

    def worker() -> dict:
        try:
            return run_plan(plan, inputs, session_id, event_cb=thread_cb)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, _SENTINEL)

    fut = loop.run_in_executor(None, worker)
    while True:
        ev = await q.get()
        if ev is _SENTINEL:
            break
        await emit(ev)
    return await fut
