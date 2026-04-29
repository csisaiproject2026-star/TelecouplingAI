"""
Output router — classify tool output files and decide render type.
SHP/TIF files are classified as 'qgis' but returned as 'download' only.
Preview generation is triggered on-demand via render_spatial_file tool, not automatically.
"""
from __future__ import annotations
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




async def route_outputs_async(workspace_dir: str, tool_name: str) -> list[dict]:
    """
    Async version of route_outputs. Use this when already inside an async context.
    Scan workspace_dir, classify each output file, and return a list of
    {"filename": ..., "path": ..., "render_type": ...} dicts.

    For files classified as 'qgis' (SHP/TIF):
      - The original file is returned with render_type='download'
      - Preview generation is NOT automatic — use render_spatial_file tool on-demand

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
            # qgis files (TIF/SHP) are returned as 'download' only
            if render_type == "qgis":
                render_type = "download"
            raw_files.append({
                "filename": filename,
                "path": full_path,
                "render_type": render_type,
            })

    return raw_files


def route_outputs(workspace_dir: str, tool_name: str) -> list[dict]:
    """
    Scan workspace_dir and classify output files without generating previews.
    Works in both sync and async contexts via scan_output_directory.
    """
    raw_files = []
    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in files:
            if filename.endswith("_preview.png"):
                continue
            full_path = os.path.join(root, filename)
            render_type = classify_file(filename, tool_name)
            if render_type == "qgis":
                render_type = "download"
            raw_files.append({
                "filename": filename,
                "path": full_path,
                "render_type": render_type,
            })
    return raw_files
