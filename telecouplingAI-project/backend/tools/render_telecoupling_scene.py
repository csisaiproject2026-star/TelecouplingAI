"""
Render Telecoupling Scene (Phase B) — composite ONE Fig.10-style map from any
subset of the telecoupling layers: flows (radial_flows.shp), systems
(systems_from_table.shp), agents (agents_from_table.shp).

Reuses the shared cartography (telecoupling_style.py) via the scene worker.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Callable

from shared.utils import CSISError, generate_output_dir
from tools.render_tif import _numeric_field_candidates, _to_web_jpeg, _layer_tc_role  # reuse helpers

logger = logging.getLogger(__name__)

REQUIRED_KEYS: list[str] = []  # at least one layer is required (checked below)

# tc_role tag (written by our tools) -> which scene slot the file belongs to.
_TC_ROLE_SLOT = {
    "flow_type": "flows", "system_type": "systems",
    "agent_type": "agents", "cause_type": "causes",
}


async def run_render_telecoupling_scene(
    params: dict,
    session_id: str,
    task_id: str,
    progress_callback: Callable[[int, str], None],
) -> dict:
    from renderers.qgis_renderer import scene_render

    # Explicit slots (the original path: LLM passes paths it found in chat history).
    slots = {
        "flows": (params.get("flows_file") or "").strip() or None,
        "systems": (params.get("systems_file") or "").strip() or None,
        "agents": (params.get("agents_file") or "").strip() or None,
        "causes": (params.get("causes_file") or "").strip() or None,
    }

    # ADDITIVE auto-routing: any files passed in `layers` are placed into the
    # right slot by reading their tc_role tag. Explicit slots win (only empty
    # slots are filled); files with no/unknown tc_role are skipped. This makes
    # "upload all the layer files + say 'combine these'" robust without relying
    # on the LLM to assign each file to the correct parameter. The explicit-slot
    # path above is untouched, so the existing chat-history flow is unaffected.
    layers = params.get("layers") or []
    if isinstance(layers, str):
        layers = [layers]
    skipped = []
    for fp in layers:
        fp = (fp or "").strip()
        if not fp:
            continue
        if not os.path.isfile(fp):
            skipped.append(os.path.basename(fp))
            continue
        slot = _TC_ROLE_SLOT.get((_layer_tc_role(fp) or ""))
        if slot is None:
            skipped.append(os.path.basename(fp))      # no tc_role -> can't auto-route
        elif not slots[slot]:
            slots[slot] = fp                           # explicit slot wins; fill only if empty

    flows, systems, agents, causes = slots["flows"], slots["systems"], slots["agents"], slots["causes"]
    if skipped:
        logger.info(f"[scene] skipped (no tc_role / not found): {skipped}")

    if not any([flows, systems, agents, causes]):
        raise CSISError(
            "Provide at least one telecoupling layer — either the explicit "
            "flows_file/systems_file/agents_file/causes_file, or a `layers` list of "
            "uploaded layer files (the tool auto-detects each file's role from its tc_role tag).",
            "MISSING_PARAMS",
        )

    for label, fp in (("flows_file", flows), ("systems_file", systems),
                      ("agents_file", agents), ("causes_file", causes)):
        if fp and not os.path.isfile(fp):
            raise CSISError(f"{label} not found: {fp}", "FILE_NOT_FOUND")

    magnitude_field = (params.get("magnitude_field") or "").strip() or None
    category_field = (params.get("category_field") or "").strip() or None

    # Flow lines are colored & sized by a magnitude column — the user must pick
    # it (same gate as render_spatial_file). Only blocks when flows are included.
    if flows and not magnitude_field:
        candidates = _numeric_field_candidates(flows)
        if candidates:
            opts = ", ".join(candidates)
            # Not an error — just need the magnitude column. Return a normal
            # result so the UI shows no red error; the assistant relays + asks.
            return {
                "files": [],
                "content": (
                    "Almost ready to composite the telecoupling scene — the flows layer is "
                    "colored and thickened by a numeric magnitude column. Available column(s): "
                    f"{opts}. Please ask the user which one to use (or confirm if there is only "
                    "one), then call render_telecoupling_scene again with magnitude_field set."
                ),
            }

    progress_callback(10, "Preparing telecoupling scene...")
    workspace_dir, _ = generate_output_dir("telecoupling_scene", session_id)
    out_png = os.path.join(workspace_dir, "telecoupling_scene.png")

    progress_callback(30, "Compositing flows / systems / agents...")
    try:
        await scene_render(
            out_png,
            flows_path=flows, systems_path=systems, agents_path=agents, causes_path=causes,
            magnitude_field=magnitude_field, category_field=category_field,
            width=1600, height=1000, padding=0.12,
        )
    except Exception as e:
        raise CSISError(f"Scene render failed: {e}", "QGIS_FAILED")

    if not os.path.isfile(out_png):
        raise CSISError("Scene render produced no output file.", "QGIS_FAILED")

    progress_callback(95, "Optimizing preview...")
    out_img = _to_web_jpeg(out_png)

    progress_callback(100, "Scene complete")
    return {
        "success": True,
        "files": [
            {"filename": Path(out_img).name, "path": out_img, "render_type": "image"}
        ],
    }
