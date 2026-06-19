"""
Use-case level workflow engine (v0.1).

Lets a multi-step telecoupling analysis be expressed as a WorkflowPlan (a DAG of
existing-tool calls) and executed deterministically: the LLM only *proposes* the
plan; this package *validates* and *runs* it. See usecaseLevel_workflow/WORKFLOW_DESIGN.md.
"""
from .schema import WorkflowPlan, WorkflowStep, RequiredInput, plan_from_dict
from .engine import validate_plan, run_plan

__all__ = [
    "WorkflowPlan", "WorkflowStep", "RequiredInput", "plan_from_dict",
    "validate_plan", "run_plan",
]
