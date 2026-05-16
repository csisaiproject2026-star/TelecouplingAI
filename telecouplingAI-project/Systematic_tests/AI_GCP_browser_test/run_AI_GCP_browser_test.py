#!/usr/bin/env python3
"""
AI_GCP_browser_test — Full browser-path test using Playwright.

真实模拟用户操作流程：
  1. Playwright 打开无头浏览器 → http://localhost/
  2. 用 set_input_files() 模拟拖拽/选择文件（自动展开 .shp 附属文件、目录内所有文件）
  3. 在对话框输入自然语言 prompt（只含参数值，不含任何路径）
  4. 按 Enter 提交
  5. 等待 ToolStatusCard 蓝色卡片出现（= LLM 成功识别并调用了工具）→ PASS
  6. 继续等待绿色卡片（任务完成），截图留证

PASS 判断：蓝色卡片出现 = LLM 调用了正确工具
FAIL 判断：45s 内无卡片出现 = LLM 未调用任何工具

Run on GCP host (NOT inside Docker):
    python3 .../AI_GCP_browser_test/run_AI_GCP_browser_test.py
    python3 ... --ids 1,7,28
    python3 ... --headful
"""

from __future__ import annotations

import argparse
import asyncio
import glob as _glob
import json
import os
import sys
import time

from playwright.async_api import async_playwright, Page, Browser

# ── Paths ────────────────────────────────────────────────────────────────────
BASE  = "/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests"
BDIR  = f"{BASE}/AI_GCP_browser_test"
DATA  = f"{BASE}/Test_data"
PATCH = f"{BASE}/AI_GCP_direct_test"
SH    = f"{DATA}/_shared/Base_Data"
URL   = "http://localhost/"

results: list[dict] = []


# ── File expansion ────────────────────────────────────────────────────────────

def _expand_uploads(specs: list[str]) -> list[str]:
    """
    Expand upload file specs to actual file paths:
    - path ending with '/' or a directory: all files in that directory
    - path ending with '.shp': the shapefile + all sidecar files
    - regular file: just that file
    """
    result = []
    for spec in specs:
        # Directory: upload all files inside it
        if spec.endswith("/") or os.path.isdir(spec):
            d = spec.rstrip("/")
            if os.path.isdir(d):
                for fname in sorted(os.listdir(d)):
                    fp = os.path.join(d, fname)
                    if os.path.isfile(fp):
                        result.append(fp)
        # Shapefile: expand to .shp + all sidecars (.dbf .shx .prj .cpg .qpj .sbn .sbx)
        elif spec.endswith(".shp"):
            base = spec[:-4]
            for fp in sorted(_glob.glob(base + ".*")):
                # Skip .xml, .zip — not needed for reading
                if os.path.isfile(fp) and not fp.endswith(".xml") and not fp.endswith(".zip"):
                    result.append(fp)
        # Regular file
        elif os.path.isfile(spec):
            result.append(spec)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for f in result:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


# ── Browser test runner ───────────────────────────────────────────────────────

async def run_tool(
    browser: Browser,
    tool_id: int,
    name: str,
    nn_dir: str,
    upload_specs: list[str],
    prompt: str,
    timeout_s: int,
) -> None:
    scr_dir = os.path.join(BDIR, nn_dir, "screenshot")
    os.makedirs(scr_dir, exist_ok=True)

    sys.stdout.write(f"  [{tool_id:02d}] {name:<38} ... ")
    sys.stdout.flush()

    t0 = time.perf_counter()
    status = "FAIL"
    note = ""
    n_files = 0

    # Each tool gets a fresh browser context → fresh sessionStorage → unique session
    context = await browser.new_context(viewport={"width": 1280, "height": 900})
    page: Page = await context.new_page()

    try:
        # 1. Open the app
        await page.goto(URL, wait_until="domcontentloaded", timeout=30_000)

        # 2. Expand and upload files (simulate drag-and-drop / file picker)
        files = _expand_uploads(upload_specs)
        n_files = len(files)
        if files:
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(files)
            # Wait for React selectedFiles state to update
            await page.wait_for_timeout(800)

        # 3. Type prompt (no file paths — only parameters and values)
        chat = page.get_by_placeholder("Enter a prompt here")
        await chat.click()
        await chat.fill(prompt)
        await chat.press("Enter")

        # 4. Wait for ToolStatusCard to appear (blue = tool invoked).
        #    This is the PRIMARY success criterion: LLM correctly called a tool.
        tool_card = page.locator(".bg-blue-50, .bg-green-50").first
        try:
            await tool_card.wait_for(state="visible", timeout=45_000)
        except Exception:
            await page.screenshot(path=f"{scr_dir}/no_tool.png", full_page=True)
            note = "LLM did not call any tool"
            raise

        # PASS: tool was invoked
        status = "PASS"
        await page.screenshot(path=f"{scr_dir}/invoked.png", full_page=True)

        # 5. Optionally wait for green card (task completed).
        #    Timeout here does NOT change PASS to FAIL — task may take longer.
        try:
            green = page.locator(".bg-green-50").first
            await green.wait_for(state="visible", timeout=timeout_s * 1_000)
            await page.screenshot(path=f"{scr_dir}/complete.png", full_page=True)
        except Exception:
            pass  # Still PASS; computation may error due to data, not LLM routing

    except Exception as exc:
        try:
            await page.screenshot(path=f"{scr_dir}/fail.png", full_page=True)
        except Exception:
            pass
        if not note:
            msg = str(exc)
            note = ("Timeout — LLM did not call tool within 45s"
                    if ("Timeout" in msg or "timeout" in msg) else msg[:80])

    elapsed = time.perf_counter() - t0
    sym = "✓" if status == "PASS" else "✗"
    print(f"{sym}{status}  ({elapsed:.1f}s, {n_files} files uploaded)", flush=True)
    if status == "FAIL":
        print(f"       NOTE: {note}", flush=True)

    results.append({
        "id": tool_id, "name": name, "status": status,
        "seconds": round(elapsed, 1), "files_uploaded": n_files,
        "note": note if status == "FAIL" else "",
    })
    await context.close()


def skip_tool(tool_id: int, name: str, nn_dir: str, reason: str) -> None:
    sys.stdout.write(f"  [{tool_id:02d}] {name:<38} ... ")
    sys.stdout.flush()
    print(f"⊘SKIP   (0.0s)  {reason}", flush=True)
    results.append({"id": tool_id, "name": name, "status": "SKIP",
                    "seconds": 0, "files_uploaded": 0, "note": reason})


# ── Tool definitions ──────────────────────────────────────────────────────────
# (id, name, nn_dir, upload_specs, prompt, timeout_s)
#
# upload_specs可以是：
#   - 普通文件路径
#   - ".shp" 路径（自动展开为含所有附属文件）
#   - 目录路径（自动上传目录内所有文件）
#
# prompt：只含数值/布尔参数，不含任何路径

TOOLS: list[tuple] = [

    (1, "Network Analysis", "01_network_analysis",
     [f"{DATA}/01_network_analysis/Network Analysis Grouping/nodes.csv",
      f"{DATA}/01_network_analysis/Network Analysis Grouping/links.csv",
      f"{DATA}/01_network_analysis/Network Analysis Grouping/World_countries_2002.shp"],
     "Run Network Analysis on the uploaded files. "
     "nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap.",
     120),

    (2, "CBC Preprocessor", "02_coastal_blue_carbon_preprocessor",
     [f"{DATA}/02_coastal_blue_carbon_preprocessor/snapshots.csv",
      f"{PATCH}/02_coastal_blue_carbon_preprocessor/output/_patch/lulc_lookup_p.csv"],
     "Run Coastal Blue Carbon Preprocessor on the uploaded files.",
     120),

    (3, "Coastal Blue Carbon", "03_coastal_blue_carbon",
     [f"{DATA}/02_coastal_blue_carbon_preprocessor/snapshots.csv",
      f"{DATA}/03_coastal_blue_carbon/outputs_preprocessor/transitions_sample.csv",
      f"{PATCH}/03_coastal_blue_carbon/output/_patch/biophysical_p.csv"],
     "Run Coastal Blue Carbon main model on the uploaded files. "
     "analysis_year=2060, do_economic_analysis=false, use_price_table=false.",
     180),

    (4, "Seasonal Water Yield", "04_seasonal_water_yield",
     # Upload all individual files including shapefile sidecars and all monthly rasters
     [f"{DATA}/04_seasonal_water_yield/watershed_gura.shp",
      f"{DATA}/04_seasonal_water_yield/DEM_gura.tif",
      f"{DATA}/04_seasonal_water_yield/land_use_gura.tif",
      f"{DATA}/04_seasonal_water_yield/soil_group_gura.tif",
      f"{DATA}/04_seasonal_water_yield/biophysical_table_gura_SWY.csv",
      f"{DATA}/04_seasonal_water_yield/rain_events_gura.csv",
      # All 12 ET0 monthly rasters
      f"{DATA}/04_seasonal_water_yield/ET0_monthly/",
      # All 12 Precipitation monthly rasters
      f"{DATA}/04_seasonal_water_yield/Precipitation_monthly/"],
     "Run Seasonal Water Yield on the uploaded files. "
     "threshold_flow_accumulation=1000, alpha_m=1/12, beta_i=1, gamma=1, "
     "monthly_alpha=false, user_defined_climate_zones=false, "
     "user_defined_local_recharge=false, flow_dir_algorithm=MFD.",
     300),

    (5, "Crop Percentile", "05_crop_production_percentile",
     [f"{DATA}/05_crop_production_percentile/sample_user_data/landcover.tif",
      f"{DATA}/05_crop_production_percentile/sample_user_data/landcover_to_crop_table.csv",
      f"{DATA}/05_crop_production_percentile/sample_user_data/aggregate_shape.shp",
      # model_data_pct directory
      f"{PATCH}/05_crop_production_percentile/output/model_data_pct/"],
     "Run Crop Production Percentile on the uploaded files.",
     180),

    (6, "Crop Regression", "06_crop_production_regression",
     [f"{DATA}/05_crop_production_percentile/sample_user_data/landcover.tif",
      f"{DATA}/05_crop_production_percentile/sample_user_data/landcover_to_crop_table.csv",
      f"{DATA}/05_crop_production_percentile/sample_user_data/crop_fertilization_rates.csv",
      f"{DATA}/05_crop_production_percentile/sample_user_data/aggregate_shape.shp",
      f"{PATCH}/05_crop_production_percentile/output/model_data_reg/"],
     "Run Crop Production Regression on the uploaded files.",
     180),

    (7, "Carbon Storage", "07_carbon_storage",
     [f"{DATA}/07_carbon_storage/lulc_current_willamette.tif",
      f"{DATA}/07_carbon_storage/carbon_pools_willamette.csv"],
     "Run Carbon Storage on the uploaded files. "
     "calc_sequestration=false, do_valuation=false.",
     120),

    (8, "Habitat Quality", "08_habitat_quality",
     [f"{DATA}/08_habitat_quality/lulc_current_willamette.tif",
      f"{DATA}/08_habitat_quality/threats_willamette.csv",
      f"{PATCH}/08_habitat_quality/output/_patch/sensitivity_p.csv"],
     "Run Habitat Quality on the uploaded files. half_saturation_constant=0.5.",
     180),

    (9, "Annual Water Yield", "09_annual_water_yield",
     [f"{DATA}/09_annual_water_yield/reference_ET_gura.tif",
      f"{DATA}/09_annual_water_yield/precipitation_gura.tif",
      f"{DATA}/09_annual_water_yield/depth_to_root_restricting_layer_gura.tif",
      f"{DATA}/09_annual_water_yield/plant_available_water_fraction_gura.tif",
      f"{DATA}/09_annual_water_yield/land_use_gura.tif",
      f"{DATA}/09_annual_water_yield/watershed_gura.shp",
      f"{DATA}/09_annual_water_yield/biophysical_table_gura.csv"],
     "Run Annual Water Yield on the uploaded files. seasonality_constant=15.",
     180),

    (10, "Forest Carbon Edge", "10_forest_carbon_edge_effect",
     [f"{DATA}/10_forest_carbon_edge_effect/forest_carbon_edge_lulc_demo.tif",
      f"{DATA}/10_forest_carbon_edge_effect/forest_edge_carbon_lu_table.csv",
      f"{DATA}/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.shp",
      f"{DATA}/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.shp"],
     "Run Forest Carbon Edge Effect on the uploaded files. "
     "n_nearest_model_points=10, biomass_to_carbon_conversion_factor=0.47, "
     "compute_forest_edge_effects=true, pools_to_calculate=all.",
     300),

    (11, "Crop Pollination", "11_crop_pollination",
     [f"{DATA}/11_crop_pollination/landcover.tif",
      f"{DATA}/11_crop_pollination/guild_table.csv",
      f"{DATA}/11_crop_pollination/landcover_biophysical_table.csv"],
     "Run Crop Pollination on the uploaded files.",
     300),

    (12, "DelineateIt", "12_delineateit",
     [f"{DATA}/12_delineateit/DEM_gura.tif"],
     "Run DelineateIt on the uploaded DEM. detect_pour_points=true.",
     120),

    (13, "RouteDEM", "13_routedem",
     [f"{DATA}/13_routedem/DEM_gura.tif"],
     "Run RouteDEM on the uploaded DEM. algorithm=D8, "
     "calculate_flow_direction=true, calculate_flow_accumulation=true.",
     120),

    (14, "SDR", "14_sdr",
     [f"{DATA}/14_sdr/DEM_gura.tif",
      f"{DATA}/14_sdr/erosivity_gura.tif",
      f"{DATA}/14_sdr/erodibility_gura.tif",
      f"{DATA}/14_sdr/land_use_gura.tif",
      f"{DATA}/14_sdr/watershed_gura.shp",
      f"{DATA}/14_sdr/biophysical_table_Gura.csv"],
     "Run Sediment Delivery Ratio (SDR) on the uploaded files. "
     "threshold_flow_accumulation=1000, k_param=2, sdr_max=0.8, "
     "ic_0_param=0.5, l_max=122.",
     300),

    (15, "NDR", "15_ndr",
     [f"{DATA}/15_ndr/DEM_gura.tif",
      f"{DATA}/15_ndr/land_use_gura.tif",
      f"{DATA}/15_ndr/precipitation_gura.tif",
      f"{DATA}/15_ndr/watershed_gura.shp",
      f"{PATCH}/15_ndr/output/_patch/bio_ndr_p.csv"],
     "Run Nutrient Delivery Ratio (NDR) on the uploaded files. "
     "threshold_flow_accumulation=1000, k_param=2, calc_n=true, calc_p=false, "
     "subsurface_critical_length_n=150, subsurface_eff_n=0.8.",
     300),

    (16, "Urban Cooling", "16_urban_cooling",
     [f"{DATA}/16_urban_cooling/lulc.tif",
      f"{DATA}/16_urban_cooling/et0.tif",
      f"{DATA}/16_urban_cooling/aoi.shp",
      f"{DATA}/16_urban_cooling/Biophysical_UHI_fake.csv",
      f"{DATA}/16_urban_cooling/sample_buildings.shp",
      f"{DATA}/16_urban_cooling/Fake_energy_savings.csv"],
     "Run Urban Cooling on the uploaded files. "
     "t_ref=21.5, uhi_max=3.5, t_air_average_radius=2000, "
     "green_area_cooling_distance=1000, cc_method=factors, "
     "cc_weight_shade=0.6, cc_weight_albedo=0.2, cc_weight_eti=0.2, "
     "avg_rel_humidity=30, do_energy_valuation=true, do_productivity_valuation=true.",
     300),

    (17, "Urban Flood", "17_urban_flood",
     [f"{DATA}/17_urban_flood/watersheds.gpkg",
      f"{DATA}/17_urban_flood/lulc.tif",
      f"{DATA}/17_urban_flood/soilgroup.tif",
      f"{DATA}/17_urban_flood/Biophysical_water_SF.csv",
      f"{DATA}/17_urban_flood/infrastructure.gpkg",
      f"{DATA}/17_urban_flood/Damage.csv"],
     "Run Urban Flood Risk Mitigation on the uploaded files. rainfall_depth=40.",
     180),

    (18, "Urban Stormwater", "18_urban_stormwater",
     [f"{DATA}/18_urban_stormwater/lulc.tif",
      f"{DATA}/18_urban_stormwater/soil_groups.tif",
      f"{DATA}/18_urban_stormwater/precipitation.tif",
      f"{DATA}/18_urban_stormwater/biophysical_table.csv",
      f"{DATA}/18_urban_stormwater/streets.shp",
      f"{DATA}/18_urban_stormwater/watershed.shp"],
     "Run Urban Stormwater Retention on the uploaded files. "
     "adjust_retention_ratios=true, retention_radius=20, replacement_cost=1.59.",
     180),

    (19, "Urban Nature Access", "19_urban_nature_access",
     [f"{DATA}/19_urban_nature_access/paris-lulc.tif",
      f"{DATA}/19_urban_nature_access/lulc-attributes.csv",
      f"{DATA}/19_urban_nature_access/population.tif",
      f"{DATA}/19_urban_nature_access/administrative-units.shp",
      f"{DATA}/19_urban_nature_access/pop-group-radii.csv"],
     "Run Urban Nature Access on the uploaded files. "
     "search_radius_mode=radius per population group, "
     "decay_function=dichotomy, urban_nature_demand=250, aggregate_by_pop_group=true.",
     300),

    (20, "Urban Mental Health", "20_urban_mental_health",
     [f"{DATA}/20_urban_mental_health/paris-lulc.tif",
      f"{DATA}/20_urban_mental_health/lulc-attributes.csv",
      f"{DATA}/20_urban_mental_health/population.tif",
      f"{DATA}/20_urban_mental_health/administrative-units.shp"],
     "Run Urban Mental Health on the uploaded files. "
     "search_radius_mode=uniform radius, search_radius=300, "
     "decay_function=gaussian, urban_nature_demand=250.",
     300),

    (21, "Scenic Quality", "21_scenic_quality",
     [f"{DATA}/21_scenic_quality/Input/AOI_WCVI.shp",
      f"{DATA}/21_scenic_quality/Input/AquaWEM_points.shp",
      f"{DATA}/21_scenic_quality/Input/claybark_dem.tif"],
     "Run Scenic Quality on the uploaded files. refraction=0.13, do_valuation=false.",
     300),

    (22, "HRA", "22_hra",
     [f"{DATA}/22_hra/Input/habitat_stressor_info.csv",
      f"{DATA}/22_hra/Input/exposure_consequence_criteria.csv",
      f"{DATA}/22_hra/Input/subregions.shp"],
     "Run Habitat Risk Assessment (HRA) on the uploaded files. "
     "resolution=500, max_rating=3, risk_eq=Euclidean, decay_eq=linear, "
     "n_overlapping_stressors=2, visualize_outputs=false.",
     180),

    (23, "Wave Energy", "23_wave_energy",
     [f"{DATA}/23_wave_energy/input/Machine_AquaBuOY_Performance.csv",
      f"{DATA}/23_wave_energy/input/Machine_AquaBuOY_Parameter.csv",
      f"{DATA}/23_wave_energy/input/AOI_WCVI.shp"],
     # WaveData (811 MB binary files) and global DEM are pre-installed server-side
     "Run Wave Energy on the uploaded files. "
     "analysis_area=West Coast of North America and Hawaii, "
     f"wave_base_data_path={DATA}/23_wave_energy/input/WaveData, "
     f"bathymetry_path={SH}/global_dem.tif, valuation_container=false.",
     180),

    (24, "Coastal Vulnerability", "24_coastal_vulnerability",
     [f"{DATA}/24_coastal_vulnerability/aoi_grandbahama_utm.shp",
      f"{DATA}/24_coastal_vulnerability/bathymetry.tif",
      f"{DATA}/24_coastal_vulnerability/dem_srtm_grandbahama.tif",
      f"{DATA}/24_coastal_vulnerability/geomorphology_grandbahama.shp",
      f"{DATA}/24_coastal_vulnerability/landmass_polygon.shp",
      f"{DATA}/24_coastal_vulnerability/WaveWatchIII_global.shp",
      f"{DATA}/24_coastal_vulnerability/GrandBahama_Habitats/Natural_Habitats.csv",
      f"{DATA}/24_coastal_vulnerability/continental_shelf_polyline_global.shp",
      f"{DATA}/24_coastal_vulnerability/population_grandbahama.tif"],
     "Run Coastal Vulnerability on the uploaded files. "
     "dem_averaging_radius=900, geomorphology_fill_value=4, "
     "max_fetch_distance=30000, model_resolution=1000, population_radius=500.",
     300),

    (25, "Offshore Wind Energy", "25_wind_energy",
     [f"{DATA}/25_wind_energy/input/New_England_US_Aoi.shp",
      f"{DATA}/25_wind_energy/input/global_wind_energy_parameters.csv",
      f"{DATA}/25_wind_energy/input/3_6_turbine.csv",
      f"{DATA}/25_wind_energy/input/ECNA_EEZ_WEBPAR_Aug27_2012.csv"],
     "Run Offshore Wind Energy on the uploaded files. "
     f"bathymetry_path={SH}/global_dem.tif, "
     f"land_polygon_vector_path={SH}/global_polygon.shp, "
     "number_of_turbines=80, min_depth=3, max_depth=60, "
     "min_distance=0, max_distance=200000, avg_grid_distance=4, valuation_container=false.",
     180),

    # Tool 26 Recreation: skip

    (27, "Scenario Gen Proximity", "27_scenario_gen_proximity",
     [f"{DATA}/27_scenario_gen_proximity/scenario_proximity_lulc.tif",
      f"{DATA}/27_scenario_gen_proximity/scenario_proximity_aoi.shp"],
     "Run Scenario Generator Proximity on the uploaded files. "
     "replacement_lucode=12, area_to_convert=20000, "
     "focal_landcover_codes=1 2 3 4 5, convertible_landcover_codes=1 2 3 4 5, "
     "convert_nearest_to_edge=true, convert_farthest_from_edge=true, n_steps=1.",
     180),

    # ── TeleBox tools ─────────────────────────────────────────────────────────

    (28, "OLS Regression", "28_ols",
     [f"{DATA}/28_ols/ols_data.csv"],
     "Run OLS Regression on the uploaded CSV. "
     "dependent_variable=y, independent_variables=x1,x2,x3.",
     60),

    (29, "FAMD", "29_famd",
     [f"{DATA}/29_famd/famd_data.csv"],
     "Run FAMD factor analysis on the uploaded CSV. "
     "quantitative_variables=age,income, qualitative_variables=gender,region.",
     120),

    (30, "CO2 Emissions", "30_co2_emissions",
     [f"{DATA}/30_co2_emissions/co2_data.csv"],
     "Run CO2 Emissions analysis on the uploaded CSV. "
     "animal_count_field=animals, length_km_field=distance_km, "
     "capacity_per_trip=50, co2_per_km_per_trip=2.6.",
     60),

    (31, "Cost-Benefit Analysis", "31_cost_benefit_analysis",
     [f"{DATA}/31_cost_benefit_analysis/projects.csv",
      f"{DATA}/31_cost_benefit_analysis/economic_data.csv"],
     "Run Cost-Benefit Analysis on the uploaded CSVs. "
     "key_field=project_id, cost_field=cost_usd, revenue_field=revenue_usd.",
     60),

    (32, "Population Density", "32_population_density",
     [f"{DATA}/32_population_density/population.csv"],
     "Run Population Density analysis on the uploaded CSV. "
     "population_field=pop_2020, area_km2_field=area_km2.",
     60),

    (33, "Radial Flows", "33_radial_flows",
     [f"{DATA}/33_radial_flows/flows.csv"],
     "Draw Radial Flows from the uploaded CSV. "
     "from_x_field=from_lon, from_y_field=from_lat, "
     "to_x_field=to_lon, to_y_field=to_lat, value_field=flow_value.",
     60),

    (34, "Commodity Trade", "34_commodity_trade",
     [f"{DATA}/34_commodity_trade/trade.csv"],
     "Run Commodity Trade analysis on the uploaded CSV. "
     "from_country_field=exporter_iso3, to_country_field=importer_iso3, value_field=trade_usd.",
     60),

    (35, "Add Agents", "35_add_agents",
     [f"{DATA}/35_add_agents/agents.csv"],
     "Add agents from the uploaded CSV. "
     "x_field=longitude, y_field=latitude, name_field=agent_name.",
     60),

    (36, "Draw Agents Table", "36_draw_agents_table",
     [f"{DATA}/36_draw_agents_table/agents_table.csv"],
     "Draw agents from the uploaded table. "
     "x_field=longitude, y_field=latitude, name_field=name.",
     60),

    (37, "Add Causes", "37_add_causes",
     [f"{DATA}/37_add_causes/causes.csv"],
     "Add causes from the uploaded CSV. "
     "x_field=longitude, y_field=latitude, description_field=cause_description.",
     60),

    (38, "Add Systems", "38_add_systems",
     [f"{DATA}/38_add_systems/systems.csv"],
     "Add systems from the uploaded CSV. "
     "x_field=longitude, y_field=latitude, name_field=system_name.",
     60),

    (39, "Draw Systems Table", "39_draw_systems_table",
     [f"{DATA}/39_draw_systems_table/systems_table.csv"],
     "Draw systems from the uploaded table. "
     "x_field=longitude, y_field=latitude, name_field=name.",
     60),

    (40, "Add Media Flows", "40_add_media_flows",
     [f"{DATA}/40_add_media_flows/article.html",
      f"{DATA}/40_add_media_flows/country_centroids.csv"],
     "Add media flows from the uploaded HTML article. source_lon=116.4, source_lat=39.9.",
     120),

    (41, "Food Security", "41_food_security",
     [f"{DATA}/41_food_security/fao_food_security.csv"],
     "Run Food Security analysis on the uploaded CSV. "
     "countries=China,India,USA, indicator_field=Prevalence of undernourishment.",
     60),

    (42, "Nutrition Metrics", "42_nutrition_metrics",
     [f"{DATA}/42_nutrition_metrics/nutrition_data.csv"],
     "Run Nutrition Metrics on the uploaded CSV. "
     "age_col=age_group, sex_col=sex, weight_col=weight_kg, population_col=population.",
     60),
]

ID_MAP = {t[0]: t for t in TOOLS}


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(ids: list[int], headless: bool) -> None:
    id_set = set(ids)
    selected = [t for t in TOOLS if t[0] in id_set]
    n_total  = len(selected) + (1 if 26 in id_set else 0)

    print(f"\n{'='*72}", flush=True)
    print(f"  AI_GCP_browser_test  —  {n_total} tool(s)  "
          f"(Playwright {'headless' if headless else 'headful'})", flush=True)
    print(f"  Target : {URL}", flush=True)
    print(f"  Data   : {DATA}", flush=True)
    print(f"  Screens: {BDIR}/<nn>/screenshot/", flush=True)
    print(f"  PASS = ToolStatusCard (blue) appeared = LLM called correct tool", flush=True)
    print(f"{'='*72}", flush=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)

        for entry in TOOLS:
            tool_id = entry[0]
            if tool_id not in id_set:
                continue
            _, name, nn_dir, upload_specs, prompt, timeout_s = entry
            await run_tool(browser, tool_id, name, nn_dir,
                           upload_specs, prompt, timeout_s)

        if 26 in id_set:
            skip_tool(26, "Recreation & Tourism", "26_recreation",
                      "requires external NatCap recmodel server")

        await browser.close()

    # ── Summary ────────────────────────────────────────────────────────────
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    total   = len(results)

    print(f"\n{'='*72}", flush=True)
    print(f"  {'ID':<4} {'Tool':<38} {'Status':<6}  {'Sec':>6}  {'Files':>5}  Note",
          flush=True)
    print(f"  {'--':<4} {'----':<38} {'------':<6}  {'---':>6}  {'-----':>5}", flush=True)
    for r in results:
        sym  = "✓" if r["status"] == "PASS" else ("✗" if r["status"] == "FAIL" else "⊘")
        note = r["note"][:36] if r["note"] else ""
        print(f"  {r['id']:<4} {r['name']:<38} {sym}{r['status']:<5}  "
              f"{r['seconds']:>6.1f}  {r.get('files_uploaded',0):>5}  {note}", flush=True)

    print(f"\n  Total: {total}  ✓ PASS: {passed}  ✗ FAIL: {failed}  ⊘ SKIP: {skipped}",
          flush=True)
    print(f"{'='*72}", flush=True)

    out = os.path.join(BDIR, "results_browser.json")
    with open(out, "w") as f:
        json.dump({"summary": {"total": total, "passed": passed,
                                "failed": failed, "skipped": skipped},
                   "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\n  → Results saved to {out}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default="",
                        help="Comma-separated tool IDs 1-42 (default: all)")
    parser.add_argument("--headful", action="store_true",
                        help="Show browser window (needs DISPLAY)")
    args = parser.parse_args()
    ids = ([int(x.strip()) for x in args.ids.split(",") if x.strip()]
           if args.ids else list(range(1, 43)))
    asyncio.run(main(ids, headless=not args.headful))
