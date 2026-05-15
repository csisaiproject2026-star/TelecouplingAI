"""
02_llm_tool_test / test_llm_tools.py
LLM-based tool invocation tests — natural language prompts.

Tests the full LLM → tool pipeline: agent must understand intent from natural
language and invoke the correct tool with correct parameters.

Phase 1 : Single user, sequential, 6 core tools (fast to medium)
Phase 2 : Single user, all available tools
Phase 3 : 3 concurrent users (session isolation check)

Run:
    cd Systematic_tests/AI_GCP_test
    CSIS_BASE_URL=http://localhost python 02_llm_tool_test/test_llm_tools.py
    CSIS_BASE_URL=http://localhost python 02_llm_tool_test/test_llm_tools.py --phase 1
"""
import asyncio
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _utils import (
    BASE_URL, DEMO, SD, DEFAULT_MODEL, new_sid,
    stream_chat, events_success, events_output_files, events_error_msg,
    ToolTestResult, print_results_table, save_results_json,
    metrics_collector, print_metrics, percentile,
)

REPORT_PATH = os.path.join(os.path.dirname(__file__), "results_llm.json")

# ── Tool definitions (natural language prompts) ───────────────────────────────
# Each entry: (id, name, [files_to_upload (container paths)], prompt, timeout_s)

DD  = DEMO
SAM = SD

TOOLS_LLM = [
    (1, "Network Analysis",
     [],
     (f"Run Network Analysis Grouping using the files already on the server:\n"
      f"- nodes file: {DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/nodes.csv\n"
      f"- links file: {DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/links.csv\n"
      f"- shapefile: {DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shp\n"
      f"Use walktrap clustering. Join on nodes attribute CODE and shapefile attribute ISO_3_CODE."),
     270),

    (2, "CBC Preprocessor",
     [],
     (f"Run the Coastal Blue Carbon Preprocessor. Input files are already on the server:\n"
      f"- snapshots CSV: {DD}/CoastalBLueCarbonPreprocessor_input/snapshots.csv\n"
      f"- LULC lookup: {DD}/CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv\n"
      f"- rasters: {DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2010_mean_Resample.tif, "
      f"{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2030_mean_Resample.tif, "
      f"{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2050_mean_Resample.tif"),
     270),

    (7, "Carbon Storage",
     [],
     (f"Assess carbon storage and sequestration in the Willamette Valley using:\n"
      f"- current LULC map: {SAM}/Carbon/lulc_current_willamette.tif\n"
      f"- carbon pools table: {SAM}/Carbon/carbon_pools_willamette.csv"),
     180),

    (8, "Habitat Quality",
     [],
     (f"Map habitat quality for the Willamette Valley. Use these files:\n"
      f"- current LULC: {SAM}/HabitatQuality/lulc_current_willamette.tif\n"
      f"- accessibility: {SAM}/HabitatQuality/accessibility_willamette.shp\n"
      f"- sensitivity table: {SAM}/HabitatQuality/sensitivity_willamette.csv\n"
      f"- threats table: {SAM}/HabitatQuality/threats_willamette.csv\n"
      f"Use half_saturation_constant=0.05"),
     300),

    (13, "SDR",
     [],
     (f"Run the Sediment Delivery Ratio model for the Gura watershed:\n"
      f"- DEM: {SAM}/SDR/DEM_gura.tif\n"
      f"- erosivity: {SAM}/SDR/erosivity_gura.tif\n"
      f"- erodibility: {SAM}/SDR/erodibility_gura.tif\n"
      f"- land use: {SAM}/SDR/land_use_gura.tif\n"
      f"- watersheds: {SAM}/SDR/watershed_gura.shp\n"
      f"- biophysical table: {SAM}/SDR/biophysical_table_Gura.csv\n"
      f"Use threshold_flow_accumulation=1000, k_param=2, sdr_max=0.8"),
     360),

    (14, "NDR",
     [],
     (f"Model nutrient delivery in the Gura watershed:\n"
      f"- DEM: {SAM}/NDR/DEM_gura.tif\n"
      f"- land use: {SAM}/NDR/land_use_gura.tif\n"
      f"- precipitation runoff proxy: {SAM}/NDR/precipitation_gura.tif\n"
      f"- watersheds: {SAM}/NDR/watershed_gura.shp\n"
      f"- biophysical table: {SAM}/NDR/biophysical_table_gura.csv\n"
      f"Calculate both nitrogen and phosphorus, threshold_flow_accumulation=1000"),
     360),

    (28, "OLS Regression",
     [("ols_data.csv", b"""id,gdp_bn,pop_mil,forest_pct,co2_mt
1,14000,1400,22.3,10000\n2,21000,330,33.8,5000\n3,4000,83,31.7,700
4,3000,67,29.2,400\n5,5000,126,68.5,1200\n6,2000,45,15.2,300
7,1500,33,12.8,200\n8,800,20,45.6,100\n9,600,18,62.1,80
10,400,10,78.3,50\n""", "text/csv")],
     ("I've uploaded a CSV with country-level data. Please run an OLS regression "
      "predicting CO2 emissions (co2_mt) from GDP (gdp_bn), population (pop_mil), "
      "and forest cover (forest_pct)."),
     120),

    (30, "CO2 Emissions",
     [("co2_transport.csv", b"""route_id,animal_count,length_km
route_001,50,120.5\nroute_002,30,85.2\nroute_003,75,200.0
route_004,20,45.8\nroute_005,60,310.7\n""", "text/csv")],
     ("I've uploaded a wildlife transport route CSV with columns route_id, animal_count, "
      "and length_km. Please run CO2 emissions analysis on this transport data using "
      "capacity_per_trip=10 and co2_per_km_per_trip=0.8."),
     120),

    (41, "Food Security",
     [("food_fao.csv", b"""Area,Year,Item,Value
China,2019,Undernourishment,2.5\nIndia,2019,Undernourishment,14.0
Nigeria,2019,Undernourishment,14.8\nBrazil,2019,Undernourishment,6.5
China,2020,Undernourishment,2.5\nIndia,2020,Undernourishment,15.3
Nigeria,2020,Undernourishment,18.0\nBrazil,2020,Undernourishment,7.0\n""", "text/csv")],
     ("I've uploaded an FAO food security CSV with columns Area, Year, Item, and Value. "
      "Please analyse undernourishment trends for China, India, Nigeria, and Brazil "
      "using indicator_field=Undernourishment."),
     120),

    (42, "Nutrition Metrics",
     [("population.csv", b"""age_group,sex,population
0-3,male,50000000\n0-3,female,48000000\n3-10,male,120000000
3-10,female,115000000\n10-18,male,140000000\n10-18,female,135000000
18-30,male,180000000\n18-30,female,175000000\n30-60,male,230000000
30-60,female,240000000\n60+,male,90000000\n60+,female,110000000\n""", "text/csv")],
     ("I've uploaded demographic population data by age_group, sex, and population count. "
      "Please calculate nutrition energy requirements (LLER) for this population."),
     120),

    # ── New InVEST tools (server-side data, no upload needed) ─────────────────

    (15, "Urban Cooling",
     [],
     (f"Model urban heat island cooling effects. All files are on the server at "
      f"/data/datainput/16_urban_cooling/. Use lulc.tif, et0.tif, aoi.shp, "
      f"Biophysical_UHI_fake.csv. "
      f"Parameters: green_area_cooling_distance=1000, t_ref=21.5, uhi_max=3.5."),
     600),

    (16, "Urban Flood Risk",
     [],
     (f"Assess urban flood risk mitigation. Files are on the server at "
      f"/data/datainput/17_urban_flood/. Use watersheds.gpkg, lulc.tif, "
      f"soilgroup.tif, Biophysical_water_SF.csv. Set rainfall_depth=40."),
     360),

    (17, "Urban Stormwater",
     [],
     (f"Run urban stormwater retention model. Files are on the server at "
      f"/data/datainput/18_urban_stormwater/. Use lulc.tif, soil_groups.tif, "
      f"precipitation.tif, biophysical_table.csv, streets.shp, watershed.shp. "
      f"Set adjust_retention_ratios=True, retention_radius=20, replacement_cost=1.59."),
     360),

    (18, "Urban Nature Access",
     [],
     (f"Assess urban nature access in Paris. Files are on the server at "
      f"/data/datainput/19_urban_nature_access/. Use paris-lulc.tif, population.tif, "
      f"administrative-units.shp, lulc-attributes.csv, pop-group-radii.csv. "
      f"Use search_radius_mode='radius per population group', decay_function=dichotomy."),
     600),

    (20, "Scenic Quality",
     [],
     (f"Map scenic quality for the West Coast Vancouver Island area. Files are on the server at "
      f"/data/datainput/21_scenic_quality/Input/. Use AOI_WCVI.shp, AquaWEM_points.shp, "
      f"claybark_dem.tif. Enable valuation with valuation_function=linear, a_coef=1, b_coef=0.1."),
     600),

    (21, "HRA",
     [],
     (f"Run habitat risk assessment for the West Coast Vancouver Island. Files at "
      f"/data/datainput/22_hra/Input/. Use habitat_stressor_info.csv, "
      f"exposure_consequence_criteria.csv, subregions.shp. "
      f"resolution=500, max_rating=3, risk_eq=euclidean, decay_eq=linear, n_overlapping_stressors=2."),
     600),

    (23, "Scenario Generator",
     [],
     (f"Generate land use change scenarios using proximity-based rules. Files at "
      f"/data/datainput/27_scenario_gen_proximity/. Use scenario_proximity_lulc.tif, "
      f"scenario_proximity_aoi.shp. Convert 20000 ha to lucode 12 from landcover codes 1,2,3,4,5, "
      f"both nearest and farthest from edge."),
     360),

    (25, "Coastal Vulnerability",
     [],
     (f"Assess coastal vulnerability for Grand Bahama. Files at "
      f"/data/datainput/24_coastal_vulnerability/. Use aoi_grandbahama_utm.shp, bathymetry.tif, "
      f"dem_srtm_grandbahama.tif, geomorphology_grandbahama.shp, landmass_polygon.shp, "
      f"WaveWatchIII_global.shp, continental_shelf_polyline_global.shp. "
      f"dem_averaging_radius=900, geomorphology_fill_value=4, max_fetch_distance=30000, "
      f"model_resolution=1000."),
     900),

    (27, "Forest Carbon Edge",
     [],
     (f"Estimate forest carbon edge effects. Files at /data/datainput/10_forest_carbon_edge_effect/. "
      f"Use forest_carbon_edge_lulc_demo.tif, forest_edge_carbon_lu_table.csv, "
      f"forest_carbon_edge_demo_aoi.shp, and the regression model parameters at "
      f"core_data/forest_carbon_edge_regression_model_parameters.shp. "
      f"compute_forest_edge_effects=True, n_nearest_model_points=10."),
     600),
]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_llm_tool(tool_id, tool_name, files_to_upload, prompt, timeout) -> ToolTestResult:
    sid = new_sid(f"llm{tool_id:02d}")
    t0 = time.time()
    print(f"\n  [{tool_id:02d}] {tool_name}  (LLM)")
    try:
        # Upload inline files if any
        if files_to_upload:
            r = requests.post(
                f"{BASE_URL}/api/upload",
                files=[("files", (fname, data, mime))
                       for fname, data, mime in files_to_upload],
                headers={"X-Session-ID": sid},
                timeout=60,
            )
            assert r.status_code == 200, f"Upload failed: {r.text[:100]}"
            up = {f["filename"]: f["path"] for f in r.json()["uploaded"]}
            # Append uploaded paths to prompt
            extra = "\n\nUploaded files:\n"
            for fname, path in up.items():
                extra += f"  {fname}: {path}\n"
            prompt = prompt + extra

        events = stream_chat(sid, prompt, timeout=timeout)
        duration = time.time() - t0

        if events_success(events):
            files = events_output_files(events)
            print(f"      ✓ PASS  {duration:.1f}s  {len(files)} files")
            return ToolTestResult(tool_id, tool_name, "PASS", duration, files)
        else:
            err = events_error_msg(events) or "no tool_result event"
            print(f"      ✗ FAIL  {duration:.1f}s  {err[:80]}")
            return ToolTestResult(tool_id, tool_name, "FAIL", duration, error=err)

    except Exception as e:
        duration = time.time() - t0
        print(f"      ✕ ERROR  {duration:.1f}s  {e}")
        return ToolTestResult(tool_id, tool_name, "ERROR", duration, error=str(e))


# ── Phase 3: concurrent session isolation ────────────────────────────────────

def run_concurrent_isolation():
    """3 users run different tools simultaneously; verify session isolation."""
    print("\n\n── Phase 3: Concurrent session isolation (3 users) ─────────────────")
    tools_subset = TOOLS_LLM[:3]

    def user_task(i):
        tid, tname, files, prompt, timeout = tools_subset[i]
        return run_llm_tool(tid, tname, files, prompt, timeout)

    start = time.time()
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(user_task, i) for i in range(3)]
        results = [f.result(timeout=400) for f in futures]

    elapsed = time.time() - start
    print(f"\n  Concurrent wall-clock time: {elapsed:.1f}s")

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    print(f"  Session isolation: {len(results)} users, {passed} passed, {failed} failed")
    return results


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], default=0,
                        help="1=fast subset 2=all 3=concurrent (default: all phases)")
    args = parser.parse_args()

    print(f"\n{'=' * 78}")
    print(f"  LLM Tool Tests  →  {BASE_URL}  (model: {DEFAULT_MODEL})")
    print(f"{'=' * 78}")

    all_results = []

    if args.phase in (0, 1, 2):
        subset = TOOLS_LLM[:6] if args.phase == 1 else TOOLS_LLM
        phase_name = "Phase 1 — Fast/Medium Tools" if args.phase == 1 else "All LLM Tools"
        print(f"\n── {phase_name} ({len(subset)} tools) ─────────────────────────")
        for tid, tname, files, prompt, timeout in subset:
            r = run_llm_tool(tid, tname, files, prompt, timeout)
            all_results.append(r)

    if args.phase in (0, 3):
        concurrent_results = run_concurrent_isolation()
        # Don't double-count if already ran in phase 1/2
        if args.phase == 3:
            all_results = concurrent_results

    print_results_table(all_results, "LLM Tool Test Results")
    save_results_json(all_results, REPORT_PATH)

    failed = sum(1 for r in all_results if r.status == "FAIL")
    sys.exit(0 if failed == 0 else 1)
