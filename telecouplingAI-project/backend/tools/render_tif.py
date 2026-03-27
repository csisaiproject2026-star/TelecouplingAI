"""
Render TIF/SHP tool — renders a spatial raster or vector file to a PNG image
using the QGIS zoom_render renderer.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Callable

from shared.utils import CSISError, generate_output_dir

logger = logging.getLogger(__name__)

REQUIRED_KEYS = ["file_path"]


async def run_render_tif(
    params: dict,
    session_id: str,
    task_id: str,
    progress_callback: Callable[[int, str], None],
) -> dict:
    """Render a TIF or SHP file to a PNG image using QGIS zoom_render."""
    from renderers.qgis_renderer import zoom_render

    file_path = params.get("file_path", "").strip()
    if not file_path:
        raise CSISError("Missing required parameter: file_path", "MISSING_PARAMS")

    if not os.path.isfile(file_path):
        raise CSISError(
            f"File not found: {file_path}. "
            "Please provide the absolute path to the file on disk.",
            "FILE_NOT_FOUND",
        )

    ext = Path(file_path).suffix.lower()
    if ext not in {".tif", ".tiff", ".shp", ".geojson", ".gpkg"}:
        raise CSISError(
            f"Unsupported file type '{ext}'. Supported: .tif, .tiff, .shp, .geojson, .gpkg",
            "UNSUPPORTED_TYPE",
        )

    progress_callback(10, f"Preparing to render {Path(file_path).name}...")

    workspace_dir, _ = generate_output_dir("render_tif", session_id)
    stem = Path(file_path).stem
    output_png = os.path.join(workspace_dir, f"{stem}_render.png")

    progress_callback(30, "Launching QGIS renderer...")
    try:
        await zoom_render(file_path, output_png, width=1920, height=1080, padding=0.1)
    except Exception as e:
        raise CSISError(f"QGIS render failed: {e}", "QGIS_FAILED")

    if not os.path.isfile(output_png):
        raise CSISError("Render produced no output file.", "QGIS_FAILED")

    progress_callback(100, "Render complete")

    return {
        "success": True,
        "files": [
            {
                "filename": Path(output_png).name,
                "path": output_png,
                "render_type": "image",
            }
        ],
    }
