"""
Reconcile a WorkflowPlan's column/field mappings against the REAL uploaded files.

The planner proposes field names (e.g. from_x_field='FROM_X') without seeing the
data, so it can guess wrong (e.g. 'FROM_LON'). Before executing we read the actual
column headers and:
  * auto-fix safe mismatches (case-insensitive exact match: 'from_x' -> 'FROM_X'),
  * hard-flag the rest (with the available columns + a closest-match suggestion),
so a tool is never run against a column that does not exist.
"""
from __future__ import annotations

import difflib
import logging

from .schema import WorkflowPlan

logger = logging.getLogger(__name__)

# Literal params whose VALUE is a column name (so we validate it against the data).
_COLUMN_SUFFIXES = ("_field", "_attri", "_col")
_COLUMN_LIST_PARAMS = {"quantitative_variables", "qualitative_variables"}


def _is_column_param(param: str) -> bool:
    return param.endswith(_COLUMN_SUFFIXES) or param in _COLUMN_LIST_PARAMS


def _split_values(param: str, value) -> list[str]:
    if param in _COLUMN_LIST_PARAMS:
        return [v.strip() for v in str(value).split(",") if v.strip()]
    return [str(value).strip()]


def read_columns(path: str, file_kind: str | None) -> list[str] | None:
    """Return column/field names of a table or vector file, or None if not introspectable."""
    fk = (file_kind or "").lower()
    p = path.lower()
    try:
        if fk == "table" or p.endswith(".csv"):
            import pandas as pd
            return list(pd.read_csv(path, nrows=0).columns)
        if fk == "vector" or p.endswith((".shp", ".geojson", ".gpkg")):
            import geopandas as gpd
            try:
                g = gpd.read_file(path, rows=1)
            except Exception:
                g = gpd.read_file(path)
            return [c for c in g.columns if c != "geometry"]
    except Exception as e:  # unreadable file -> can't validate, don't block
        logger.warning("reconcile: could not read columns of %s: %s", path, e)
    return None


def _ci_exact(value: str, columns: set[str]) -> str | None:
    for c in columns:
        if c.lower() == value.lower():
            return c
    return None


def reconcile_plan(plan: WorkflowPlan, inputs: dict[str, str]) -> dict:
    """
    Check each step's column-name literals against the real columns of that step's
    input files. Returns:
      { "fixes":      [ {step,param,from,to} ],          # safe case-insensitive auto-fixes
        "mismatches": [ {step,param,value,available,suggestion} ],  # unresolved -> block
        "checked": <int> }
    Auto-fixes are applied in place to the plan's InputSource.value.
    """
    file_kinds = {ri.id: ri.file_kind for ri in plan.required_inputs}
    fixes: list[dict] = []
    mismatches: list[dict] = []
    checked = 0

    for step in plan.steps:
        # union of columns across this step's available input files
        cols: set[str] = set()
        for src in step.inputs.values():
            if src.source == "input" and src.ref in inputs:
                ck = read_columns(inputs[src.ref], file_kinds.get(src.ref))
                if ck:
                    cols.update(ck)
        if not cols:
            continue  # files not provided yet / raster — skip (can't validate)

        for param, src in step.inputs.items():
            if src.source != "literal" or not _is_column_param(param):
                continue
            for val in _split_values(param, src.value):
                checked += 1
                if val in cols:
                    continue
                fixed = _ci_exact(val, cols)
                if fixed:
                    # safe auto-fix (only differs by case)
                    if param in _COLUMN_LIST_PARAMS:
                        parts = [(_ci_exact(v, cols) or v) for v in _split_values(param, src.value)]
                        src.value = ",".join(parts)
                    else:
                        src.value = fixed
                    fixes.append({"step": step.id, "param": param, "from": val, "to": fixed})
                else:
                    sugg = difflib.get_close_matches(val, list(cols), n=1, cutoff=0.5)
                    mismatches.append({
                        "step": step.id, "param": param, "value": val,
                        "available": sorted(cols),
                        "suggestion": sugg[0] if sugg else None,
                    })

    return {"fixes": fixes, "mismatches": mismatches, "checked": checked}
