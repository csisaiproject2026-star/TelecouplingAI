"""
Output router — classify tool output files and decide render type.
For SHP/TIF files (render_type='qgis'), a satellite basemap preview PNG is
generated alongside the original file. The original is kept as 'download',
the preview is added as 'image'.
"""
from __future__ import annotations
import asyncio
import fnmatch
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Directories to always skip during output scanning
# Covers various InVEST naming conventions for intermediate/cache directories
SKIP_DIRS = {
    "intermediate_outputs",   # SWY, CBC Preprocessor etc.
    "intermediate_output",    # Crop Percentile, Crop Regression
    "intermediate",           # CBC Main
    "taskgraph_cache",        # All InVEST models
}

PATTERNS: dict[str, dict[str, list[str]]] = {
    "seasonal_water_yield": {
        "qgis": ["QF_*.tif", "B_*.tif", "L_avail_*.tif", "L_*.tif", "P_*.tif",
                 "aggregated_results_swy_*.shp"],
        "csv": [],
    },
    "coastal_blue_carbon_preprocessor": {
        "qgis": ["aligned_lulc_*.tif"],
        "csv": ["transitions_*.csv", "carbon_pool_transient_template_*.csv"],
    },
    "coastal_blue_carbon": {
        "qgis": ["carbon-stock-at-*.tif", "carbon-accumulation-*.tif",
                 "carbon-emissions-*.tif", "total-net-carbon-sequestration*.tif",
                 "net-present-value*.tif"],
        "csv": [],
    },
    "crop_production_percentile": {
        "qgis": ["*_yield_*percentile_*.tif", "*_yield_*production*.tif"],
        "csv": ["result_table_*.csv", "result_table.csv",
                "aggregate_results_*.csv", "aggregate_results.csv"],
    },
    "crop_production_regression": {
        "qgis": ["*_regression_production_*.tif"],
        "csv": ["result_table_*.csv", "result_table.csv",
                "aggregate_results_*.csv", "aggregate_results.csv"],
    },
    "network_analysis": {
        "qgis": ["output_*.shp"],
        "csv": ["network_stats_*.csv"],
        "download": ["network_plot_*.pdf"],
    },
}

EXT_FALLBACK: dict[str, str] = {
    ".tif": "qgis", ".tiff": "qgis", ".shp": "qgis",
    ".csv": "csv", ".png": "image", ".jpg": "image",
}


def classify_file(filename: str, tool_name: str) -> str:
    """Return render type ('qgis', 'csv', 'image', 'download') for a given output file."""
    tool_patterns = PATTERNS.get(tool_name, {})
    for render_type, patterns in tool_patterns.items():
        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern):
                return render_type
    ext = Path(filename).suffix.lower()
    return EXT_FALLBACK.get(ext, "download")


def _preview_path(file_path: str) -> str:
    """Return the path for the preview PNG alongside the original file."""
    p = Path(file_path)
    return str(p.parent / (p.stem + "_preview.png"))


async def _generate_preview(file_path: str, output_path: str) -> bool:
    """
    Generate a zoom_render preview PNG for a SHP or TIF file.
    Returns True if successful, False on any error.
    """
    try:
        from renderers.qgis_renderer import zoom_render
        await zoom_render(file_path, output_path, width=1920, height=1080, padding=0.1)
        return os.path.exists(output_path)
    except Exception as e:
        logger.warning(f"Preview generation failed for {file_path}: {e}")
        return False


async def route_outputs_async(workspace_dir: str, tool_name: str) -> list[dict]:
    """
    Async version of route_outputs. Use this when already inside an async context.
    Scan workspace_dir, classify each output file, and return a list of
    {"filename": ..., "path": ..., "render_type": ...} dicts.

    For files classified as 'qgis' (SHP/TIF):
      - The original file is kept with render_type='download' (for user download)
      - A satellite basemap preview PNG is generated with render_type='image'

    Skips directories in SKIP_DIRS and existing *_preview.png files.
    """
    raw_files = []
    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in files:
            if filename.endswith("_preview.png"):
                continue
            full_path = os.path.join(root, filename)
            render_type = classify_file(filename, tool_name)
            raw_files.append({
                "filename": filename,
                "path": full_path,
                "render_type": render_type,
            })

    results = []
    preview_tasks = []

    for f in raw_files:
        if f["render_type"] == "qgis":
            results.append({**f, "render_type": "download"})
            preview_out = _preview_path(f["path"])
            preview_tasks.append((f["path"], preview_out, Path(f["filename"]).stem))
        else:
            results.append(f)

    if preview_tasks:
        task_coroutines = [_generate_preview(src, out) for src, out, _ in preview_tasks]
        successes = await asyncio.gather(*task_coroutines, return_exceptions=True)

        for (src, out, stem), ok in zip(preview_tasks, successes):
            if ok and not isinstance(ok, Exception) and os.path.exists(out):
                results.append({
                    "filename": Path(out).name,
                    "path": out,
                    "render_type": "image",
                })
            else:
                logger.warning(f"Skipping preview for {stem}: generation failed or file missing")

    return results


def route_outputs(workspace_dir: str, tool_name: str) -> list[dict]:
    """
    Sync wrapper around route_outputs_async.
    Use this when called from a non-async context (e.g. tests, task_queue).
    """
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                lambda: asyncio.run(route_outputs_async(workspace_dir, tool_name))
            )
            return future.result()
    except RuntimeError:
        return asyncio.run(route_outputs_async(workspace_dir, tool_name))
