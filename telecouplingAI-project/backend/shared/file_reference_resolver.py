from __future__ import annotations

import os
from typing import Any


_TOOL_FILE_KEYS = {
    "render_spatial_file": ("file_path",),
    "render_telecoupling_scene": (
        "flows_file",
        "systems_file",
        "agents_file",
        "causes_file",
    ),
    "read_file_content": ("file_path",),
}


def _resolve_file_reference(value: Any, candidates: list[dict]) -> Any:
    if not isinstance(value, str) or not value.strip() or os.path.isfile(value):
        return value

    requested_name = os.path.basename(value).casefold()
    for candidate in reversed(candidates):
        path = candidate.get("path")
        if not isinstance(path, str) or not os.path.isfile(path):
            continue
        candidate_name = candidate.get("filename") or os.path.basename(path)
        if str(candidate_name).casefold() == requested_name:
            return path
    return value


def resolve_tool_file_references(
    tool_name: str,
    tool_input: dict,
    candidates: list[dict],
) -> dict:
    resolved = dict(tool_input)
    for key in _TOOL_FILE_KEYS.get(tool_name, ()):
        if key in resolved:
            resolved[key] = _resolve_file_reference(resolved[key], candidates)

    if tool_name == "render_telecoupling_scene" and "layers" in resolved:
        layers = resolved["layers"]
        if isinstance(layers, list):
            resolved["layers"] = [
                _resolve_file_reference(value, candidates) for value in layers
            ]
        elif isinstance(layers, str):
            resolved["layers"] = _resolve_file_reference(layers, candidates)
    return resolved


def resolve_render_file_references(
    tool_name: str,
    tool_input: dict,
    candidates: list[dict],
) -> dict:
    """Backward-compatible wrapper for existing render callers."""
    return resolve_tool_file_references(tool_name, tool_input, candidates)
