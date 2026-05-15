"""
Local test runner for all 15 new non-InVEST tools (tools #28–#42).

Calls each tool's async Python function directly with Test_data/ inputs.
Outputs land in Systematic_tests/AI_local_test/xx/output/ for inspection.

Usage (from telecouplingAI-project/ directory):
    conda run -n TeleCouplingAI python Systematic_tests/AI_local_test/run_all_local_tests.py

To also run InVEST integration tests (tools 01–27):
    conda run -n TeleCouplingAI pytest backend/tests/test_invest_integration.py -v

To also run the new-tools pytest suite:
    conda run -n TeleCouplingAI pytest backend/tests/test_new_tools.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # AI_local_test/
SYSTEMATIC  = os.path.dirname(SCRIPT_DIR)                         # Systematic_tests/
PROJECT_DIR = os.path.dirname(SYSTEMATIC)                         # telecouplingAI-project/
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
TEST_DATA   = os.path.join(SYSTEMATIC, "Test_data")

sys.path.insert(0, BACKEND_DIR)

# ── Patch generate_output_dir before any tool import ─────────────────────────
import shared.utils as _utils

_orig_gen_output_dir = _utils.generate_output_dir


def _local_output_dir(tool_name: str, session_id: str):
    """Route tool outputs to AI_local_test/<nn>_<tool>/output/."""
    # Find the matching numbered folder
    for entry in sorted(os.listdir(SCRIPT_DIR)):
        if entry.endswith(f"_{tool_name}") and os.path.isdir(os.path.join(SCRIPT_DIR, entry)):
            out = os.path.join(SCRIPT_DIR, entry, "output")
            os.makedirs(out, exist_ok=True)
            return out, f"local_test/{tool_name}"
    # Fallback: create ad-hoc
    out = os.path.join(SCRIPT_DIR, f"__{tool_name}__", "output")
    os.makedirs(out, exist_ok=True)
    return out, f"local_test/{tool_name}"


_utils.generate_output_dir = _local_output_dir


# ── Helpers ───────────────────────────────────────────────────────────────────

def td(folder: str, *parts) -> str:
    return os.path.join(TEST_DATA, folder, *parts)


def noop_progress(pct, msg):
    pass


def run_async(coro):
    return asyncio.run(coro)


PASS  = "\033[92mPASS\033[0m"
FAIL  = "\033[91mFAIL\033[0m"
SKIP  = "\033[93mSKIP\033[0m"


# ── Tool registry ─────────────────────────────────────────────────────────────
# Each entry: (display_name, callable_factory, params_dict)
# callable_factory is a zero-arg lambda that imports and returns the function
# so imports happen lazily (avoids loading all libraries at startup).

TOOLS: list[tuple[str, object, dict]] = [

    # 28 — OLS Model Selection
    ("28 OLS (basic)",
     lambda: __import__("tools.ols", fromlist=["run_ols"]).run_ols,
     {
         "input_csv":             td("28_ols", "ols_data.csv"),
         "dependent_variable":    "y",
         "independent_variables": "x1,x2,x3",
     }),

    ("28 OLS (model selection)",
     lambda: __import__("tools.ols", fromlist=["run_ols"]).run_ols,
     {
         "input_csv":             td("28_ols", "ols_data.csv"),
         "dependent_variable":    "y",
         "independent_variables": "x1,x2,x3",
         "model_selection":       True,
     }),

    # 29 — FAMD
    ("29 FAMD",
     lambda: __import__("tools.famd", fromlist=["run_factor_analysis_mixed_data"]).run_factor_analysis_mixed_data,
     {
         "input_csv":              td("29_famd", "famd_data.csv"),
         "quantitative_variables": "age,income",
         "qualitative_variables":  "gender,region",
     }),

    # 30 — CO2 Emissions
    ("30 CO2 Emissions",
     lambda: __import__("tools.co2_emissions", fromlist=["run_co2_emissions"]).run_co2_emissions,
     {
         "input_csv":           td("30_co2_emissions", "co2_data.csv"),
         "animal_count_field":  "animals",
         "length_km_field":     "distance_km",
         "capacity_per_trip":   50,
         "co2_per_km_per_trip": 2.6,
     }),

    # 31 — Cost-Benefit Analysis
    ("31 Cost-Benefit Analysis",
     lambda: __import__("tools.cost_benefit_analysis", fromlist=["run_cost_benefit_analysis"]).run_cost_benefit_analysis,
     {
         "input_csv":         td("31_cost_benefit_analysis", "projects.csv"),
         "economic_data_csv": td("31_cost_benefit_analysis", "economic_data.csv"),
         "key_field":         "project_id",
         "cost_field":        "cost_usd",
         "revenue_field":     "revenue_usd",
     }),

    # 32 — Population Density
    ("32 Population Density",
     lambda: __import__("tools.population_density", fromlist=["run_population_count_density"]).run_population_count_density,
     {
         "input_csv":        td("32_population_density", "population.csv"),
         "population_field": "pop_2020",
         "area_km2_field":   "area_km2",
     }),

    ("32 Population Density (growth)",
     lambda: __import__("tools.population_density", fromlist=["run_population_count_density"]).run_population_count_density,
     {
         "input_csv":           td("32_population_density", "population.csv"),
         "population_field":    "pop_2020",
         "area_km2_field":      "area_km2",
         "population_t1_field": "pop_2010",
         "population_t2_field": "pop_2020",
     }),

    # 33 — Radial Flows
    ("33 Radial Flows",
     lambda: __import__("tools.radial_flows", fromlist=["run_draw_radial_flows"]).run_draw_radial_flows,
     {
         "input_csv":    td("33_radial_flows", "flows.csv"),
         "from_x_field": "from_lon",
         "from_y_field": "from_lat",
         "to_x_field":   "to_lon",
         "to_y_field":   "to_lat",
         "value_field":  "flow_value",
     }),

    # 34 — Commodity Trade
    ("34 Commodity Trade",
     lambda: __import__("tools.commodity_trade", fromlist=["run_commodity_trade"]).run_commodity_trade,
     {
         "trade_csv":          td("34_commodity_trade", "trade.csv"),
         "from_country_field": "exporter_iso3",
         "to_country_field":   "importer_iso3",
         "value_field":        "trade_usd",
     }),

    # 35 — Add Agents
    ("35 Add Agents",
     lambda: __import__("tools.add_agents", fromlist=["run_add_agents_interactively"]).run_add_agents_interactively,
     {
         "input_csv":  td("35_add_agents", "agents.csv"),
         "x_field":    "longitude",
         "y_field":    "latitude",
         "name_field": "agent_name",
     }),

    # 36 — Draw Agents Table
    ("36 Draw Agents Table",
     lambda: __import__("tools.draw_agents_table", fromlist=["run_draw_agents_from_table"]).run_draw_agents_from_table,
     {
         "input_csv":  td("36_draw_agents_table", "agents_table.csv"),
         "x_field":    "longitude",
         "y_field":    "latitude",
         "name_field": "name",
     }),

    # 37 — Add Causes
    ("37 Add Causes",
     lambda: __import__("tools.add_causes", fromlist=["run_add_causes_interactively"]).run_add_causes_interactively,
     {
         "input_csv":         td("37_add_causes", "causes.csv"),
         "x_field":           "longitude",
         "y_field":           "latitude",
         "description_field": "cause_description",
     }),

    # 38 — Add Systems
    ("38 Add Systems",
     lambda: __import__("tools.add_systems", fromlist=["run_add_systems_interactively"]).run_add_systems_interactively,
     {
         "input_csv":  td("38_add_systems", "systems.csv"),
         "x_field":    "longitude",
         "y_field":    "latitude",
         "name_field": "system_name",
     }),

    # 39 — Draw Systems Table
    ("39 Draw Systems Table",
     lambda: __import__("tools.draw_systems_table", fromlist=["run_draw_systems_from_table"]).run_draw_systems_from_table,
     {
         "input_csv":  td("39_draw_systems_table", "systems_table.csv"),
         "x_field":    "longitude",
         "y_field":    "latitude",
         "name_field": "name",
     }),

    # 40 — Add Media Flows
    ("40 Add Media Flows",
     lambda: __import__("tools.add_media_flows", fromlist=["run_add_media_flows"]).run_add_media_flows,
     {
         "html_file":             td("40_add_media_flows", "article.html"),
         "source_lon":            116.4,
         "source_lat":            39.9,
         "country_reference_csv": td("40_add_media_flows", "country_centroids.csv"),
     }),

    # 41 — Food Security
    ("41 Food Security",
     lambda: __import__("tools.food_security", fromlist=["run_food_security"]).run_food_security,
     {
         "fao_csv":         td("41_food_security", "fao_food_security.csv"),
         "countries":       "China,India,USA",
         "indicator_field": "Value",
     }),

    # 42 — Nutrition Metrics
    ("42 Nutrition Metrics",
     lambda: __import__("tools.nutrition_metrics", fromlist=["run_nutrition_metrics"]).run_nutrition_metrics,
     {
         "population_csv": td("42_nutrition_metrics", "nutrition_data.csv"),
         "age_col":        "age_group",
         "sex_col":        "sex",
         "weight_col":     "weight_kg",
         "population_col": "population",
     }),
]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_one(display_name: str, fn_factory, params: dict) -> tuple[str, float, str, list[str]]:
    """Run a single tool. Returns (status, elapsed_s, error_msg, output_files)."""
    try:
        fn = fn_factory()
        t0 = time.perf_counter()
        result = run_async(fn(params, "local_test", f"t_{display_name[:8]}", noop_progress))
        elapsed = time.perf_counter() - t0
        files = [f["filename"] for f in result.get("files", [])]
        return "PASS", elapsed, "", files
    except Exception as exc:
        elapsed = time.perf_counter() - t0 if "t0" in dir() else 0.0
        # FAMD: skip gracefully if R not available
        if "famd" in display_name.lower() and any(k in str(exc) for k in ("R", "Rscript", "FactoMineR")):
            return "SKIP", elapsed, f"R/FactoMineR not available: {exc}", []
        return "FAIL", elapsed, traceback.format_exc(limit=5), []


def main():
    print("=" * 70)
    print("  CSIS Local Tool Test Runner — New Tools (28–42)")
    print("=" * 70)
    print(f"  Test data : {TEST_DATA}")
    print(f"  Output    : AI_local_test/<nn>/output/")
    print()

    results = []
    total_pass = total_fail = total_skip = 0

    for display_name, fn_factory, params in TOOLS:
        sys.stdout.write(f"  Running {display_name:<35} ... ")
        sys.stdout.flush()
        status, elapsed, error_msg, files = run_one(display_name, fn_factory, params)
        tag = {"PASS": PASS, "FAIL": FAIL, "SKIP": SKIP}[status]
        print(f"{tag}  ({elapsed:.2f}s)")
        if status == "FAIL":
            print(f"    ERROR: {error_msg.splitlines()[-1] if error_msg else 'unknown'}")
            total_fail += 1
        elif status == "SKIP":
            print(f"    NOTE: {error_msg.split(':')[0]}")
            total_skip += 1
        else:
            total_pass += 1
        results.append((display_name, status, elapsed, files))

    # Summary table
    print()
    print("=" * 70)
    print(f"  Results: {total_pass} PASS  {total_fail} FAIL  {total_skip} SKIP  "
          f"/ {len(TOOLS)} tests")
    print()
    print(f"  {'Tool':<35} {'Status':<6} {'Time':>7}  Output files")
    print(f"  {'-'*35} {'-'*6} {'-'*7}  {'-'*20}")
    for name, st, t, files in results:
        flist = ", ".join(files[:3]) + ("..." if len(files) > 3 else "")
        print(f"  {name:<35} {st:<6} {t:>6.2f}s  {flist}")
    print("=" * 70)

    if total_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
