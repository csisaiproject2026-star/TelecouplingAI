"""
Celery task queue for long-running tool execution.
"""
from __future__ import annotations
import asyncio
import sys
import os
# Ensure backend directory is on sys.path (needed when Celery auto-discovers tasks)
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
import json
import logging
import traceback

import redis
from celery import Celery
from config import settings
from shared.error_events import build_error_event, publish_error_event
from shared.utils import sanitize_error_message

logger = logging.getLogger(__name__)

app = Celery("csis", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
app.conf.update(
    task_soft_time_limit=1800,
    task_time_limit=2100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


def publish(r: redis.Redis, sid: str, tid: str, event: dict) -> None:
    """Publish a progress event to Redis pub/sub."""
    r.publish(f"progress:{sid}:{tid}", json.dumps(event))


def execute_tool(tool_name: str, params: dict, session_id: str, task_id: str, progress_callback) -> dict:
    """Dispatch to the correct tool function by name."""
    from tools.network_analysis import run_network_analysis
    from tools.cbc_preprocessor import run_cbc_preprocessor
    from tools.cbc_main import run_cbc_main
    from tools.seasonal_water_yield import run_seasonal_water_yield
    from tools.crop_percentile import run_crop_percentile
    from tools.crop_regression import run_crop_regression
    from tools.render_tif import run_render_tif
    from tools.render_telecoupling_scene import run_render_telecoupling_scene
    from tools.read_file import run_read_file
    from tools.carbon import run_carbon
    from tools.habitat_quality import run_habitat_quality
    from tools.annual_water_yield import run_annual_water_yield
    from tools.forest_carbon_edge_effect import run_forest_carbon_edge
    from tools.pollination import run_pollination
    from tools.delineateit import run_delineateit
    from tools.routedem import run_routedem
    from tools.sdr import run_sdr
    from tools.ndr import run_ndr
    from tools.urban_cooling import run_urban_cooling
    from tools.urban_flood import run_urban_flood
    from tools.urban_stormwater import run_urban_stormwater
    from tools.urban_nature_access import run_urban_nature_access
    from tools.urban_mental_health import run_urban_mental_health
    from tools.scenic_quality import run_scenic_quality
    from tools.hra import run_hra
    from tools.wave_energy import run_wave_energy
    from tools.scenario_gen_proximity import run_scenario_gen_proximity
    from tools.coastal_vulnerability import run_coastal_vulnerability
    from tools.wind_energy import run_offshore_wind_energy
    def run_recreation(*args, **kwargs):
        raise RuntimeError(
            "Recreation & Tourism is temporarily unavailable: "
            "the required external NatCap recmodel server (34.44.144.58:54321) "
            "is not accessible due to permission restrictions. "
            "This feature is not supported at this time."
        )

    from tools.ols import run_ols
    from tools.co2_emissions import run_co2_emissions
    from tools.cost_benefit_analysis import run_cost_benefit_analysis
    from tools.population_density import run_population_count_density
    from tools.radial_flows import run_draw_radial_flows
    from tools.commodity_trade import run_commodity_trade
    from tools.add_agents import run_add_agents_interactively
    from tools.draw_agents_table import run_draw_agents_from_table
    from tools.add_causes import run_add_causes_interactively
    from tools.add_systems import run_add_systems_interactively
    from tools.draw_systems_table import run_draw_systems_from_table
    from tools.add_media_flows import run_add_media_flows
    from tools.famd import run_factor_analysis_mixed_data
    from tools.food_security import run_food_security
    from tools.nutrition_metrics import run_nutrition_metrics
    from tools.geodetector import run_geographical_detector
    from tools.spatial_moran import run_spatial_autocorrelation_moran

    tool_map = {
        "run_network_analysis_grouping":        run_network_analysis,
        "run_coastal_blue_carbon_preprocessor": run_cbc_preprocessor,
        "run_coastal_blue_carbon":              run_cbc_main,
        "run_seasonal_water_yield":             run_seasonal_water_yield,
        "run_crop_production_percentile":       run_crop_percentile,
        "run_crop_production_regression":       run_crop_regression,
        "render_spatial_file":                  run_render_tif,
        "render_telecoupling_scene":            run_render_telecoupling_scene,
        "read_file_content":                    run_read_file,
        "run_carbon_storage":                   run_carbon,
        "run_habitat_quality":                  run_habitat_quality,
        "run_annual_water_yield":               run_annual_water_yield,
        "run_forest_carbon_edge_effect":        run_forest_carbon_edge,
        "run_crop_pollination":                 run_pollination,
        "run_delineateit":                      run_delineateit,
        "run_routedem":                         run_routedem,
        "run_Sediment_Delivery_Ratio_SDR":      run_sdr,
        "run_ndr":                              run_ndr,
        "run_urban_cooling":                    run_urban_cooling,
        "run_urban_flood_risk_mitigation":      run_urban_flood,
        "run_urban_stormwater_retention":       run_urban_stormwater,
        "run_urban_nature_access":              run_urban_nature_access,
        "run_urban_mental_health":              run_urban_mental_health,
        "run_scenic_quality":                   run_scenic_quality,
        "run_habitat_risk_assessment":          run_hra,
        "run_wave_energy_production":           run_wave_energy,
        "run_scenario_gen_proximity":           run_scenario_gen_proximity,
        "run_coastal_vulnerability":            run_coastal_vulnerability,
        "run_offshore_wind_energy":             run_offshore_wind_energy,
        "run_recreation_tourism":               run_recreation,
        "run_model_selection_ols":              run_ols,
        "run_co2_emissions":                    run_co2_emissions,
        "run_cost_benefit_analysis":            run_cost_benefit_analysis,
        "run_population_count_density":         run_population_count_density,
        "run_draw_radial_flows":                run_draw_radial_flows,
        "run_commodity_trade":                  run_commodity_trade,
        "run_add_agents_interactively":         run_add_agents_interactively,
        "run_draw_agents_from_table":           run_draw_agents_from_table,
        "run_add_causes_interactively":         run_add_causes_interactively,
        "run_add_systems_interactively":        run_add_systems_interactively,
        "run_draw_systems_from_table":          run_draw_systems_from_table,
        "run_add_media_flows":                  run_add_media_flows,
        "run_factor_analysis_mixed_data":       run_factor_analysis_mixed_data,
        "run_food_security":                    run_food_security,
        "run_nutrition_metrics":                run_nutrition_metrics,
        "run_geographical_detector":            run_geographical_detector,
        "run_spatial_autocorrelation_moran":    run_spatial_autocorrelation_moran,
    }
    func = tool_map.get(tool_name)
    if func is None:
        raise ValueError(f"Unknown tool: {tool_name}")

    return asyncio.run(func(params, session_id, task_id, progress_callback))


@app.task(bind=True)
def run_tool_task(self, tool_name: str, params: dict, session_id: str):
    """
    Celery task: executes a tool and publishes SSE progress events to Redis.
    NOTE: task_id is included in every event so the frontend can match
    progress updates to the correct ToolStatusCard.
    """
    r = redis.from_url(settings.REDIS_URL)
    tid = self.request.id
    try:
        # ✅ task_id included in every event
        publish(r, session_id, tid, {
            "type": "tool_start", "tool": tool_name, "task_id": tid,
            "message": f"Starting {tool_name}..."
        })
        result = execute_tool(
            tool_name, params, session_id, tid,
            progress_callback=lambda p, m: publish(
                r, session_id, tid, {
                    "type": "tool_progress",
                    "task_id": tid,          # ✅ added
                    "progress": p,
                    "message": m,
                }
            ),
        )
        publish(r, session_id, tid, {
            "type": "tool_result",
            "task_id": tid,
            "files": result.get("files", []),
            "content": result.get("content", ""),
        })
        if result.get("warning"):
            publish(r, session_id, tid, {
                "type": "warning",
                "task_id": tid,
                "message": result["warning"],
            })
        publish(r, session_id, tid, {"type": "done", "task_id": tid})
    except Exception as e:
        logger.exception(f"Tool task failed: {tool_name}")
        error_event = build_error_event(
            e,
            service=f"celery:{tool_name}",
            tool=tool_name,
            session_id=session_id,
            task_id=tid,
            error_code=getattr(e, "error_code", None) or "TOOL_FAILED",
            params=params,
            traceback_text=traceback.format_exc(),
        )
        publish_error_event(r, error_event)
        publish(r, session_id, tid, {
            "type": "error",
            "task_id": tid,
            "error_id": error_event["event_id"],
            "message": sanitize_error_message(str(e)),
        })
    finally:
        r.close()
