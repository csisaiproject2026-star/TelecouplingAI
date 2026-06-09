"""
Tool: Spatial Autocorrelation — Moran's I (global + local LISA).

Answers "is this variable spatially clustered?" for a value attached to spatial
features (polygons or points).

  - Global Moran's I : one statistic for the whole study area (~ -1..+1) with a
                       permutation pseudo p-value. I>0 = clustering, I<0 =
                       dispersion, ~0 = random.
  - Local Moran (LISA): per-feature classification into HH (hot), LL (cold),
                        HL / LH (spatial outliers), or ns (not significant),
                        written back to a GeoJSON for map rendering.

Built on PySAL (libpysal weights + esda Moran/Moran_Local) — the same library
the QGIS "Hotspot Analysis" plugin uses, so results match QGIS on the same data
and weights. Validated against the canonical columbus dataset (Global I≈0.5002).

Accepts a vector file (shapefile / GeoJSON / GPKG) and the name of the numeric
field to analyse.
"""
from __future__ import annotations
import logging
import os
from typing import Callable

import numpy as np
import pandas as pd

from shared.utils import (
    CSISError, validate_required, generate_output_dir, scan_output_directory,
)

logger = logging.getLogger(__name__)

REQUIRED_KEYS = ["input_vector", "value_field"]

# esda Moran_Local quadrant codes -> human label
_LISA_LABELS = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}


async def run_spatial_autocorrelation_moran(
    params: dict,
    session_id: str,
    task_id: str,
    progress_callback: Callable[[int, str], None],
) -> dict:
    validate_required(params, REQUIRED_KEYS)

    input_vector = params["input_vector"]
    field = str(params["value_field"]).strip()
    weights_type = str(params.get("weights_type", "queen")).strip().lower()
    k_neighbors = int(params.get("k_neighbors", 8))
    permutations = int(params.get("permutations", 999))

    if not os.path.exists(input_vector):
        raise CSISError(f"Input vector not found: {input_vector}", "FILE_NOT_FOUND")

    progress_callback(5, "Reading vector data...")
    import geopandas as gpd
    from libpysal import weights as W
    import esda

    gdf = gpd.read_file(input_vector)
    if field not in gdf.columns:
        raise CSISError(
            f"Field '{field}' not found in the vector. Available numeric fields: "
            f"{[c for c in gdf.columns if c != gdf.geometry.name]}", "INVALID_PARAMS")

    # Keep only features with a valid value and geometry
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf[field] = pd.to_numeric(gdf[field], errors="coerce")
    gdf = gdf[gdf[field].notna()].reset_index(drop=True)
    if len(gdf) < 4:
        raise CSISError("Too few features with a valid value/geometry (need ≥ 4).",
                        "INVALID_PARAMS")

    y = gdf[field].to_numpy(float)

    # ── Spatial weights ───────────────────────────────────────────────────
    progress_callback(25, f"Building {weights_type} spatial weights...")
    geom_types = set(gdf.geom_type.unique())
    is_polygon = any("Polygon" in g for g in geom_types)
    note = None
    try:
        if weights_type in ("queen", "rook") and is_polygon:
            w = (W.Queen if weights_type == "queen" else W.Rook).from_dataframe(
                gdf, use_index=True)
        elif weights_type == "knn" or not is_polygon:
            if weights_type in ("queen", "rook") and not is_polygon:
                note = (f"Geometry is not polygonal; contiguity weights need polygons, "
                        f"so K-nearest-neighbours (k={k_neighbors}) was used instead.")
            w = W.KNN.from_dataframe(gdf, k=min(k_neighbors, len(gdf) - 1))
        else:
            raise CSISError(f"Unknown weights_type '{weights_type}'. "
                            f"Use queen, rook, or knn.", "INVALID_PARAMS")
    except CSISError:
        raise
    except Exception as e:
        raise CSISError(f"Could not build spatial weights: {e}", "INVALID_PARAMS")

    # Islands (features with no neighbours) break row-standardization
    if getattr(w, "islands", None):
        logger.info(f"[moran] {len(w.islands)} island feature(s) with no neighbours")
    w.transform = "r"  # row-standardize (QGIS Hotspot plugin default)

    workspace_dir, _ = generate_output_dir("spatial_moran", session_id)
    os.makedirs(workspace_dir, exist_ok=True)

    # ── Global Moran's I ──────────────────────────────────────────────────
    progress_callback(55, "Computing global Moran's I...")
    mi = esda.Moran(y, w, permutations=permutations)
    interp = ("significant spatial clustering" if (mi.I > mi.EI and mi.p_sim < 0.05)
              else "significant spatial dispersion" if (mi.I < mi.EI and mi.p_sim < 0.05)
              else "no significant spatial autocorrelation (random)")
    global_rows = [
        {"Statistic": "Moran's I", "Value": round(float(mi.I), 6)},
        {"Statistic": "Expected I (E[I])", "Value": round(float(mi.EI), 6)},
        {"Statistic": "Variance", "Value": round(float(mi.VI_norm), 6)},
        {"Statistic": "z-score", "Value": round(float(mi.z_norm), 6)},
        {"Statistic": "p-value (normal)", "Value": round(float(mi.p_norm), 6)},
        {"Statistic": f"p-value (permutation, {permutations})", "Value": round(float(mi.p_sim), 6)},
        {"Statistic": "Number of features", "Value": int(w.n)},
        {"Statistic": "Weights", "Value": f"{weights_type} (row-standardized)"},
        {"Statistic": "Interpretation", "Value": interp},
    ]
    pd.DataFrame(global_rows).to_csv(
        os.path.join(workspace_dir, "moran_global.csv"), index=False)

    # ── Local Moran's I (LISA) ────────────────────────────────────────────
    progress_callback(75, "Computing local Moran (LISA)...")
    lisa = esda.Moran_Local(y, w, permutations=permutations, seed=12345)
    sig = lisa.p_sim < 0.05
    cluster = [(_LISA_LABELS.get(int(q), "ns") if s else "ns")
               for q, s in zip(lisa.q, sig)]

    lisa_df = pd.DataFrame({
        "feature_id": range(len(gdf)),
        field: y,
        "local_I": np.round(lisa.Is, 6),
        "z_score": np.round(lisa.z_sim, 6),
        "p_value": np.round(lisa.p_sim, 6),
        "cluster": cluster,
    })
    lisa_df.to_csv(os.path.join(workspace_dir, "moran_local_lisa.csv"), index=False)

    # cluster-type summary
    summary = (pd.Series(cluster).value_counts()
               .rename_axis("cluster").reset_index(name="count"))
    summary.to_csv(os.path.join(workspace_dir, "moran_lisa_summary.csv"), index=False)

    # ── GeoJSON with LISA classification for map rendering ────────────────
    out_gdf = gdf.copy()
    out_gdf["local_I"] = np.round(lisa.Is, 6)
    out_gdf["lisa_p"] = np.round(lisa.p_sim, 6)
    out_gdf["cluster"] = cluster
    try:
        if out_gdf.crs is None:
            out_gdf.set_crs(epsg=4326, inplace=True, allow_override=True)
        out_gdf = out_gdf.to_crs(epsg=4326)
    except Exception as e:
        logger.info(f"[moran] CRS reproject skipped: {e}")
    out_gdf.to_file(os.path.join(workspace_dir, "moran_lisa.geojson"), driver="GeoJSON")

    progress_callback(95, "Scanning outputs...")
    files = await scan_output_directory(workspace_dir, "spatial_moran")
    result = {"files": files}
    if note:
        result["warning"] = note
    return result
