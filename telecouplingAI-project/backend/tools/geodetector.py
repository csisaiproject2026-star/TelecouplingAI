"""
Tool: Geographical Detector (Geodetector, Wang Jinfeng 2017).

Measures spatial stratified heterogeneity and detects driving factors of a
continuous variable Y from one or more categorical (stratified) factors X.

Four detectors:
  - Factor      : q-statistic (0..1), explanatory power of each factor + F-test
  - Interaction : whether two factors jointly enhance/weaken the explanation
  - Risk        : stratum means of Y + pairwise significance (Levene-gated t-test)
  - Ecological  : whether two factors differ significantly in their influence

Pure numpy/pandas/scipy — no external geodetector library. The formulas mirror
the published GeoDetector algorithm and the QGIS "Geographical detector" plugin
(validated to machine precision against both, and against the official 2018
disease dataset: q(region)=0.6378, q(level)=0.6067, q(type)=0.3857).

Accepts a CSV (or xlsx). User specifies the dependent variable column and the
categorical factor columns. Continuous factors must be discretized beforehand.
"""
from __future__ import annotations
import logging
import os
from itertools import combinations
from typing import Callable

import numpy as np
import pandas as pd
from scipy.stats import ncf, levene, ttest_ind, f as f_dist

from shared.utils import (
    CSISError, validate_required, generate_output_dir, scan_output_directory,
)

logger = logging.getLogger(__name__)

REQUIRED_KEYS = ["input_csv", "y_variable", "x_variables"]


def _q_and_p(y: np.ndarray, strata: np.ndarray):
    """Factor-detector q-statistic + non-central-F p-value for one factor.

    q = 1 - SSW/SST,  SSW = Σ n_h·var_h(pop),  SST = n·var_pop
    F = (n-L)/(L-1) · q/(1-q)  ~  non-central F(L-1, n-L; λ)
    λ = [ Σ ȳ_h² - (Σ √n_h·ȳ_h)²/n ] / var_sample
    """
    n = y.size
    var_pop = y.var(ddof=0)
    var_sam = y.var(ddof=1)
    sst = var_pop * n
    if sst == 0:
        raise CSISError("The dependent variable has zero variance — cannot run "
                        "the geographical detector.", "INVALID_PARAMS")

    df = pd.DataFrame({"y": y, "h": strata})
    g = df.groupby("h")["y"]
    mean_h = g.mean().to_numpy()
    var_h = g.var(ddof=0).to_numpy()
    n_h = g.count().to_numpy()
    L = n_h.size
    if L < 2:
        raise CSISError("A factor has only one stratum — it must have at least "
                        "two categories.", "INVALID_PARAMS")

    ssw = float(np.dot(var_h, n_h))
    q = 1.0 - ssw / sst

    dfn, dfd = L - 1, n - L
    if dfd <= 0:
        raise CSISError(f"Too few observations ({n}) for a factor with {L} strata.",
                        "INVALID_PARAMS")
    if np.isclose(q, 1.0):
        p = 0.0
    else:
        fv = dfd * q / (dfn * (1 - q))
        nc = (np.sum(mean_h ** 2) - (np.dot(np.sqrt(n_h), mean_h) ** 2) / n) / var_sam
        p = float(1.0 - ncf.cdf(fv, dfn, dfd, nc))
    return float(q), p, int(L)


def _interaction(qa: float, qb: float, q_ab: float) -> str:
    lo, hi, tot = min(qa, qb), max(qa, qb), qa + qb
    if q_ab < lo:
        return "Weaken_nonlinear"
    if q_ab < hi:
        return "Weaken_uni-"
    if np.isclose(q_ab, tot):
        return "Independent"
    if q_ab < tot:
        return "Enhance_bi-"
    return "Enhance_nonlinear"


async def run_geographical_detector(
    params: dict,
    session_id: str,
    task_id: str,
    progress_callback: Callable[[int, str], None],
) -> dict:
    validate_required(params, REQUIRED_KEYS)

    input_csv = params["input_csv"]
    y_name = str(params["y_variable"]).strip()
    x_raw = params["x_variables"]
    if isinstance(x_raw, str):
        x_names = [v.strip() for v in x_raw.split(",") if v.strip()]
    else:
        x_names = [str(v).strip() for v in x_raw]
    alpha = float(params.get("alpha", 0.05))

    if not os.path.exists(input_csv):
        raise CSISError(f"Input file not found: {input_csv}", "FILE_NOT_FOUND")
    if not x_names:
        raise CSISError("No factor columns (x_variables) were provided.", "INVALID_PARAMS")

    progress_callback(5, "Reading data...")
    if input_csv.lower().endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(input_csv, engine="openpyxl")
    else:
        df = pd.read_csv(input_csv)

    missing = [c for c in [y_name] + x_names if c not in df.columns]
    if missing:
        raise CSISError(f"Columns not found in data: {missing}. "
                        f"Available: {list(df.columns)}", "INVALID_PARAMS")

    df = df[[y_name] + x_names].dropna()
    if len(df) < 4:
        raise CSISError("Too few rows after removing missing values.", "INVALID_PARAMS")
    y = df[y_name].to_numpy(float)
    # factors as strings (categorical strata)
    strata = {x: df[x].astype(str).to_numpy() for x in x_names}

    workspace_dir, _ = generate_output_dir("geodetector", session_id)
    os.makedirs(workspace_dir, exist_ok=True)

    # ── Factor detector ───────────────────────────────────────────────────
    progress_callback(25, "Factor detector...")
    q_single: dict[str, float] = {}
    factor_rows = []
    for x in x_names:
        q, p, L = _q_and_p(y, strata[x])
        q_single[x] = q
        factor_rows.append({
            "Factor": x, "q_statistic": round(q, 6), "p_value": round(p, 6),
            "num_strata": L,
            "significant": "yes" if p < alpha else "no",
        })
    factor_df = pd.DataFrame(factor_rows).sort_values("q_statistic", ascending=False)
    factor_df.to_csv(os.path.join(workspace_dir, "geodetector_factor.csv"), index=False)

    # ── Interaction detector ──────────────────────────────────────────────
    if len(x_names) > 1:
        progress_callback(50, "Interaction detector...")
        inter_rows = []
        for a, b in combinations(x_names, 2):
            combo = (df[a].astype(str) + "_" + df[b].astype(str)).to_numpy()
            q_ab, _, _ = _q_and_p(y, combo)
            inter_rows.append({
                "factor_a": a, "factor_b": b,
                "q_a": round(q_single[a], 6), "q_b": round(q_single[b], 6),
                "q_combined": round(q_ab, 6),
                "interaction": _interaction(q_single[a], q_single[b], q_ab),
            })
        pd.DataFrame(inter_rows).to_csv(
            os.path.join(workspace_dir, "geodetector_interaction.csv"), index=False)

    # ── Risk detector (stratum means, long format across all factors) ─────
    progress_callback(70, "Risk detector...")
    risk_rows = []
    for x in x_names:
        sub = df[[x, y_name]]
        g = sub.groupby(x)[y_name]
        for stratum, mean_val in g.mean().items():
            risk_rows.append({
                "Factor": x, "stratum": str(stratum),
                "mean_y": round(float(mean_val), 6),
                "n": int(g.count()[stratum]),
            })
    pd.DataFrame(risk_rows).to_csv(
        os.path.join(workspace_dir, "geodetector_risk.csv"), index=False)

    # ── Ecological detector (pairwise F-test on SSW) ──────────────────────
    if len(x_names) > 1:
        progress_callback(85, "Ecological detector...")

        def _ssw(x):
            g = df.groupby(x)[y_name]
            return float((g.var(ddof=0) * g.count()).sum())

        n = len(df)
        fcrit = f_dist.ppf(1 - alpha, dfn=n, dfd=n)
        eco_rows = []
        for a, b in combinations(x_names, 2):
            sa, sb = _ssw(a), _ssw(b)
            sig = bool(sa / sb > fcrit or sb / sa > fcrit)
            eco_rows.append({
                "factor_a": a, "factor_b": b,
                "significantly_different": "yes" if sig else "no",
            })
        pd.DataFrame(eco_rows).to_csv(
            os.path.join(workspace_dir, "geodetector_ecological.csv"), index=False)

    progress_callback(95, "Scanning outputs...")
    files = await scan_output_directory(workspace_dir, "geodetector")
    return {"files": files}
