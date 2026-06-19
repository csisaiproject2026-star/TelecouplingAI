"""
WorkflowPlan data model (pure, no heavy deps — safe to import anywhere / unit-test).

A plan = ordered steps, each calling one existing tool. Every tool input is one of:
  * input   -> a file from the plan's required_inputs manifest (user upload)
  * literal -> a literal value (field name, numeric param, algorithm name, ...)
  * step    -> a file produced by an upstream step (output -> input wiring)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InputSource:
    source: str                      # "input" | "literal" | "step"
    ref: str | None = None           # input_id (source=input) or step_id (source=step)
    value: Any = None                # the value (source=literal)
    file: str | None = None          # which produced file to take (source=step); substring match

    @staticmethod
    def from_dict(d: dict) -> "InputSource":
        return InputSource(
            source=d["source"], ref=d.get("ref"),
            value=d.get("value"), file=d.get("file"),
        )


@dataclass
class WorkflowStep:
    id: str
    tool: str
    component: str = ""
    inputs: dict[str, InputSource] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    rationale: str = ""

    @staticmethod
    def from_dict(d: dict) -> "WorkflowStep":
        return WorkflowStep(
            id=d["id"], tool=d["tool"], component=d.get("component", ""),
            inputs={k: InputSource.from_dict(v) for k, v in d.get("inputs", {}).items()},
            depends_on=list(d.get("depends_on", [])),
            produces=list(d.get("produces", [])),
            rationale=d.get("rationale", ""),
        )


@dataclass
class RequiredInput:
    id: str
    label: str
    file_kind: str = "table"         # table | vector | raster | html | shapefile-set
    description: str = ""

    @staticmethod
    def from_dict(d: dict) -> "RequiredInput":
        return RequiredInput(
            id=d["id"], label=d.get("label", d["id"]),
            file_kind=d.get("file_kind", "table"), description=d.get("description", ""),
        )


@dataclass
class WorkflowPlan:
    case_name: str
    description: str
    required_inputs: list[RequiredInput] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)

    @property
    def input_ids(self) -> set[str]:
        return {ri.id for ri in self.required_inputs}

    @property
    def step_ids(self) -> set[str]:
        return {s.id for s in self.steps}


def plan_from_dict(d: dict) -> WorkflowPlan:
    return WorkflowPlan(
        case_name=d["case_name"],
        description=d.get("description", ""),
        required_inputs=[RequiredInput.from_dict(x) for x in d.get("required_inputs", [])],
        steps=[WorkflowStep.from_dict(x) for x in d.get("steps", [])],
    )
