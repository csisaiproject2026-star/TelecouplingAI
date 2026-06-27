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

# Coordinate / id columns that are never a meaningful "flow magnitude".
_COORD_EXACT = {
    "x", "y", "lon", "lat", "long", "longitude", "latitude",
    "fid", "objectid", "id",
}
_COORD_SUFFIX = ("_x", "_y", "_lon", "_lat", "_long", "_longitude", "_latitude")


def _is_coord_col(name: str) -> bool:
    n = name.lower()
    return n in _COORD_EXACT or n.endswith(_COORD_SUFFIX)


def _to_web_jpeg(png_path: str, quality: int = 85) -> str:
    """Re-encode a render PNG as a compact JPEG for fast loading over slow links
    (basemap-heavy PNGs are multi-MB; the same image as JPEG is ~10-15x smaller
    and visually identical). Any transparency is flattened onto white. Returns
    the .jpg path; on any failure returns the original PNG path unchanged."""
    try:
        from PIL import Image
        img = Image.open(png_path)
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        jpg_path = png_path[:-4] + ".jpg" if png_path.lower().endswith(".png") else png_path + ".jpg"
        img.save(jpg_path, "JPEG", quality=quality, optimize=True)
        if jpg_path != png_path:
            try:
                os.remove(png_path)
            except OSError:
                pass
        return jpg_path
    except Exception:
        return png_path


def _layer_tc_role(file_path: str) -> str | None:
    """Read the tc_role value (first feature) from a vector file via ogr."""
    if Path(file_path).suffix.lower() not in {".shp", ".geojson", ".gpkg"}:
        return None
    try:
        from osgeo import ogr
    except Exception:
        return None
    ds = ogr.Open(file_path)
    if ds is None:
        return None
    lyr = ds.GetLayer(0)
    defn = lyr.GetLayerDefn()
    idx = next((i for i in range(defn.GetFieldCount())
                if defn.GetFieldDefn(i).GetName().lower() == "tc_role"), None)
    if idx is None:
        return None
    feat = lyr.GetNextFeature()
    if feat is None:
        return None
    try:
        v = feat.GetField(idx)
        return str(v).strip().lower() if v is not None else None
    except Exception:
        return None


def _is_flow_render(file_path: str, render_as: str | None) -> bool:
    """Will this render use flow styling? (=> it needs a magnitude column.)
    True when render_as says flow, or the file carries tc_role == flow_type."""
    if render_as and str(render_as).strip().lower() in {"flow", "flows"}:
        return True
    return _layer_tc_role(file_path) == "flow_type"


def _numeric_field_candidates(file_path: str) -> list[str]:
    """List numeric attribute columns (excluding coordinate/id columns) so the
    user can choose which one represents the flow magnitude."""
    try:
        from osgeo import ogr
    except Exception:
        return []
    ds = ogr.Open(file_path)
    if ds is None:
        return []
    defn = ds.GetLayer(0).GetLayerDefn()
    out = []
    for i in range(defn.GetFieldCount()):
        fd = defn.GetFieldDefn(i)
        if fd.GetType() in (ogr.OFTInteger, ogr.OFTInteger64, ogr.OFTReal):
            name = fd.GetName()
            if not _is_coord_col(name):
                out.append(name)
    return out


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

    magnitude_field = (params.get("magnitude_field") or "").strip() or None
    category_field = (params.get("category_field") or "").strip() or None
    render_as = (params.get("render_as") or "").strip() or None

    # Flow layers are colored & sized by a magnitude column. The user must pick
    # which column that is — they know their data, we don't guess. If none was
    # supplied, stop and present the candidate columns to choose from.
    if _is_flow_render(file_path, render_as) and not magnitude_field:
        candidates = _numeric_field_candidates(file_path)
        if candidates:
            opts = ", ".join(candidates)
            # NOT an error — we just need one piece of info. Return a normal
            # result (no files) so the UI shows no red error; the assistant
            # relays this and asks the user which column to use.
            return {
                "files": [],
                "content": (
                    "Almost ready to render this flow map — I just need to know which "
                    "numeric column should set each flow line's color and width (the flow "
                    f"magnitude). Available column(s): {opts}. Please ask the user which one "
                    "to use (or, if there is only one, confirm it with them), then call "
                    "render_spatial_file again with magnitude_field set to that column."
                ),
            }

    progress_callback(10, f"Preparing to render {Path(file_path).name}...")

    workspace_dir, _ = generate_output_dir("render_tif", session_id)
    stem = Path(file_path).stem
    output_png = os.path.join(workspace_dir, f"{stem}_render.png")

    progress_callback(30, "Launching QGIS renderer...")
    try:
        await zoom_render(
            file_path, output_png, width=1920, height=1080, padding=0.1,
            magnitude_field=magnitude_field, category_field=category_field,
            render_as=render_as,
        )
    except Exception as e:
        raise CSISError(f"QGIS render failed: {e}", "QGIS_FAILED")

    if not os.path.isfile(output_png):
        raise CSISError("Render produced no output file.", "QGIS_FAILED")

    # Re-encode as a compact JPEG so the preview loads reliably over slow links
    # (the satellite-basemap PNG is multi-MB; the JPEG is ~10-15x smaller).
    progress_callback(95, "Optimizing preview...")
    output_img = _to_web_jpeg(output_png)

    progress_callback(100, "Render complete")

    return {
        "success": True,
        "files": [
            {
                "filename": Path(output_img).name,
                "path": output_img,
                "render_type": "image",
            }
        ],
    }
