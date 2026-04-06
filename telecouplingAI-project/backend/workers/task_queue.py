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

import redis
from celery import Celery
from config import settings

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
    from tools.read_file import run_read_file

    tool_map = {
        "run_network_analysis_grouping":        run_network_analysis,
        "run_coastal_blue_carbon_preprocessor": run_cbc_preprocessor,
        "run_coastal_blue_carbon":              run_cbc_main,
        "run_seasonal_water_yield":             run_seasonal_water_yield,
        "run_crop_production_percentile":       run_crop_percentile,
        "run_crop_production_regression":       run_crop_regression,
        "render_spatial_file":                  run_render_tif,
        "read_file_content":                    run_read_file,
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
        publish(r, session_id, tid, {
            "type": "error",
            "task_id": tid,
            "message": str(e),
        })
    finally:
        r.close()
