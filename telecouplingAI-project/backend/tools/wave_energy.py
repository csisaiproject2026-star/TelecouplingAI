"""
Tool: Wave Energy Production (natcap.invest.wave_energy).

Required: wave_base_data_path, analysis_area, machine_perf_path,
          machine_param_path, bathymetry_path.
Optional: aoi_vector_path, do_valuation (requires grid_points_path,
          machine_econ_path), number_of_machines.
"""
from __future__ import annotations
import logging
from typing import Callable

import natcap.invest.wave_energy

from shared.utils import CSISError, validate_required, generate_output_dir, scan_output_directory

logger = logging.getLogger(__name__)

REQUIRED_KEYS = [
    "wave_base_data_path",
    "analysis_area",
    "machine_perf_path",
    "machine_param_path",
    "bathymetry_path",
]

VALID_ANALYSIS_AREAS = {
    "Australia",
    "East Coast of North America and Puerto Rico",
    "Global",
    "North Sea 10 meter resolution",
    "North Sea 4 meter resolution",
    "West Coast of North America and Hawaii",
}


async def run_wave_energy(
    params: dict,
    session_id: str,
    task_id: str,
    progress_callback: Callable[[int, str], None],
) -> dict:
    validate_required(params, REQUIRED_KEYS)

    analysis_area = params["analysis_area"]
    if analysis_area not in VALID_ANALYSIS_AREAS:
        raise CSISError(
            f"analysis_area must be one of: {sorted(VALID_ANALYSIS_AREAS)}",
            "INVALID_PARAMS",
        )

    do_valuation = bool(params.get("do_valuation", False))
    if do_valuation:
        for key in ["grid_points_path", "machine_econ_path"]:
            if not params.get(key):
                raise CSISError(
                    f"do_valuation=true requires '{key}'", "INVALID_PARAMS"
                )
    progress_callback(5, "Validated parameters")

    workspace_dir, _ = generate_output_dir("wave_energy", session_id)
    progress_callback(10, "Created output directory")

    invest_args = {
        "workspace_dir":       workspace_dir,
        "results_suffix":      params.get("results_suffix", ""),
        "wave_base_data_path": params["wave_base_data_path"],
        "analysis_area":       analysis_area,
        "machine_perf_path":   params["machine_perf_path"],
        "machine_param_path":  params["machine_param_path"],
        "bathymetry_path":     params["bathymetry_path"],
        "aoi_vector_path":     params.get("aoi_vector_path", ""),
        "do_valuation":        do_valuation,
    }

    if do_valuation:
        invest_args["grid_points_path"]   = params["grid_points_path"]
        invest_args["machine_econ_path"]  = params["machine_econ_path"]
        invest_args["number_of_machines"] = int(params.get("number_of_machines", 28))

    progress_callback(20, "Running InVEST Wave Energy model...")
    try:
        natcap.invest.wave_energy.execute(invest_args)
    except Exception as e:
        raise CSISError(f"Wave Energy model failed: {e}", "TOOL_FAILED")
    progress_callback(85, "InVEST model completed")

    progress_callback(90, "Scanning outputs...")
    files = await scan_output_directory(workspace_dir, "wave_energy")
    progress_callback(100, "Done")

    return {"success": True, "files": files}
