"""
Tool: Offshore Wind Energy (natcap.invest.wind_energy).

Required: aoi_vector_path, bathymetry_path, global_wind_parameters_path,
          land_polygon_vector_path, number_of_turbines,
          turbine_parameters_path, wind_data_path.
Optional: avg_grid_distance (km, default 4), max_depth (m, default 60),
          max_distance (m, default 200000), min_depth (m, default 3),
          min_distance (m, default 0), valuation_container (bool).
          If valuation_container=True also requires: foundation_cost,
          discount_rate, dollar_per_kWh, number_of_turbines,
          grid_points_path, land_points_path.
"""
from __future__ import annotations
import logging
from typing import Callable

import natcap.invest.wind_energy

from shared.utils import CSISError, validate_required, generate_output_dir, scan_output_directory

logger = logging.getLogger(__name__)

REQUIRED_KEYS = [
    "aoi_vector_path",
    "bathymetry_path",
    "global_wind_parameters_path",
    "land_polygon_vector_path",
    "number_of_turbines",
    "turbine_parameters_path",
    "wind_data_path",
]


async def run_offshore_wind_energy(
    params: dict,
    session_id: str,
    task_id: str,
    progress_callback: Callable[[int, str], None],
) -> dict:
    validate_required(params, REQUIRED_KEYS)

    valuation = bool(params.get("valuation_container", False))
    progress_callback(5, "Validated parameters")

    workspace_dir, _ = generate_output_dir("wind_energy", session_id)
    progress_callback(10, "Created output directory")

    invest_args = {
        "workspace_dir":              workspace_dir,
        "results_suffix":             params.get("results_suffix", ""),
        "wind_data_path":             params["wind_data_path"],
        "aoi_vector_path":            params["aoi_vector_path"],
        "bathymetry_path":            params["bathymetry_path"],
        "land_polygon_vector_path":   params["land_polygon_vector_path"],
        "turbine_parameters_path":    params["turbine_parameters_path"],
        "number_of_turbines":         int(params["number_of_turbines"]),
        "global_wind_parameters_path": params["global_wind_parameters_path"],
        "min_depth":                  float(params.get("min_depth", 3)),
        "max_depth":                  float(params.get("max_depth", 60)),
        "min_distance":               float(params.get("min_distance", 0)),
        "max_distance":               float(params.get("max_distance", 200000)),
        "avg_grid_distance":          float(params.get("avg_grid_distance", 4)),
        "valuation_container":        valuation,
    }

    progress_callback(20, "Running InVEST Offshore Wind Energy model...")
    try:
        natcap.invest.wind_energy.execute(invest_args)
    except Exception as e:
        raise CSISError(f"Offshore Wind Energy model failed: {e}", "TOOL_FAILED")
    progress_callback(85, "InVEST model completed")

    progress_callback(90, "Scanning outputs...")
    files = await scan_output_directory(workspace_dir, "wind_energy")
    progress_callback(100, "Done")

    return {"success": True, "files": files}
