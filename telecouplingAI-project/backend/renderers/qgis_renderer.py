"""
QGIS renderer — async subprocess wrapper.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

QGIS_PYTHON = settings.QGIS_PYTHON_PATH
QGIS_PYTHON_BINDINGS = settings.QGIS_PYTHON_BINDINGS
_semaphore = asyncio.Semaphore(int(os.environ.get("QGIS_MAX_CONCURRENT", "3")))
WORKER_SCRIPT       = str(Path(__file__).parent / "_qgis_render_worker.py")
ZOOM_WORKER_SCRIPT  = str(Path(__file__).parent / "_qgis_zoom_render_worker.py")
SCENE_WORKER_SCRIPT = str(Path(__file__).parent / "_qgis_scene_render_worker.py")


async def render_file(file_path: str, output_path: str, width: int = 1920, height: int = 1080) -> str:
    """Render a spatial file (SHP/TIF) to PNG. Returns output_path."""
    async with _semaphore:
        return await _run({
            "file_path": file_path,
            "output_path": output_path,
            "width": width,
            "height": height,
        }, WORKER_SCRIPT)


async def render_with_extent(
    file_path: str, output_path: str, extent: list[float],
    width: int = 1920, height: int = 1080,
) -> str:
    """Render with a specific bounding box extent [xmin, ymin, xmax, ymax]."""
    async with _semaphore:
        return await _run({
            "file_path": file_path,
            "output_path": output_path,
            "width": width,
            "height": height,
            "extent": extent,
        }, WORKER_SCRIPT)


async def zoom_render(
    file_path: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    padding: float = 0.1,
    magnitude_field: str | None = None,
    category_field: str | None = None,
    render_as: str | None = None,
) -> str:
    """Render a spatial file (SHP/TIF) overlaid on a world basemap, zoomed to
    the file's extent.

    The world basemap (QGIS built-in world_map.gpkg countries layer) is placed
    at the bottom; the user's layer is rendered on top. The map is zoomed to
    the user layer's extent with an optional padding ratio (default 10%).

    Args:
        file_path:   Path to the SHP or TIF file to render.
        output_path: Path where the output PNG will be saved.
        width:       Output image width in pixels.
        height:      Output image height in pixels.
        padding:     Fractional padding around the user layer extent (0.1 = 10%).

    Returns:
        output_path
    """
    async with _semaphore:
        params = {
            "file_path": file_path,
            "output_path": output_path,
            "width": width,
            "height": height,
            "padding": padding,
        }
        if magnitude_field:
            params["magnitude_field"] = magnitude_field
        if category_field:
            params["category_field"] = category_field
        if render_as:
            params["render_as"] = render_as
        return await _run(params, ZOOM_WORKER_SCRIPT)


async def scene_render(
    output_path: str,
    flows_path: str | None = None,
    systems_path: str | None = None,
    agents_path: str | None = None,
    causes_path: str | None = None,
    magnitude_field: str | None = None,
    category_field: str | None = None,
    width: int = 1600,
    height: int = 1000,
    padding: float = 0.12,
) -> str:
    """Composite telecoupling scene: overlay flows + systems + agents (any
    subset) into one Fig.10-style map. Returns output_path."""
    async with _semaphore:
        params: dict = {
            "output_path": output_path,
            "width": width,
            "height": height,
            "padding": padding,
        }
        for key, val in (
            ("flows_path", flows_path),
            ("systems_path", systems_path),
            ("agents_path", agents_path),
            ("causes_path", causes_path),
            ("magnitude_field", magnitude_field),
            ("category_field", category_field),
        ):
            if val:
                params[key] = val
        return await _run(params, SCENE_WORKER_SCRIPT)


async def _run(params: dict, worker_script: str) -> str:
    """Launch a QGIS worker subprocess and return output_path.

    Params are written to a temp file to avoid shell quoting issues
    with JSON strings containing spaces and special characters.

    Success is determined by valid JSON in stdout (not returncode),
    because QGIS on Windows may exit with non-zero code even on success.
    """
    existing_pypath = os.environ.get("PYTHONPATH", "")
    new_pypath = (
        QGIS_PYTHON_BINDINGS + os.pathsep + existing_pypath
        if existing_pypath
        else QGIS_PYTHON_BINDINGS
    )
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": new_pypath}

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    try:
        json.dump(params, tmp)
        tmp.close()

        if sys.platform == "win32" and QGIS_PYTHON.lower().endswith(".bat"):
            cmd_str = f'"{QGIS_PYTHON}" "{worker_script}" "{tmp.name}"'
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                QGIS_PYTHON, worker_script, tmp.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            from shared.utils import CSISError
            raise CSISError("QGIS render timeout (120s)", "QGIS_TIMEOUT")

    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    stdout = out.decode().strip()

    if stdout:
        try:
            result = json.loads(stdout)
            if "error" in result:
                from shared.utils import CSISError
                raise CSISError(f"QGIS layer error: {result['error']}", "QGIS_FAILED")
            return result["output_path"]
        except (json.JSONDecodeError, KeyError):
            pass

    from shared.utils import CSISError
    stderr_msg = err.decode()[:500] if err else "(no stderr)"
    raise CSISError(f"QGIS render failed:\n{stderr_msg}", "QGIS_FAILED")
