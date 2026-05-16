#!/usr/bin/env python3
"""
AI_GCP_llm_test — Full LLM path test (no manual tool calls).

Sends natural language prompts to POST /api/chat (FastAPI at :8000),
streams SSE, checks tool_start + tool_result success for all 42 tools.

Run inside Docker container:
    docker exec tele-backend python \
        /home/csisaiproject2026/csis-platform/telecouplingAI-project/\
Systematic_tests/AI_GCP_llm_test/run_AI_GCP_llm_test.py
    docker exec tele-backend python ... --ids 1,7,29
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid

# ── Paths ────────────────────────────────────────────────────────────────────
BASE  = "/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests"
LDIR  = f"{BASE}/AI_GCP_llm_test"          # output / log root
D     = f"{BASE}/Test_data"                 # test data (mounted volume)
PATCH = f"{BASE}/AI_GCP_direct_test"        # patched CSVs from direct test
SH    = f"{D}/_shared/Base_Data"            # shared rasters

API_URL = "http://localhost:8000/api/chat"

results: list[dict] = []


# ── SSE client ────────────────────────────────────────────────────────────────

def stream_events(session_id: str, prompt: str, timeout: int) -> tuple[str | None, bool | None, int, list]:
    """POST to /api/chat, parse SSE stream, return (tool_name, success, n_files, events)."""
    payload = urllib.parse.urlencode({"message": prompt}).encode()
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "X-Session-ID": session_id,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    tool_name: str | None = None
    success:   bool | None = None
    n_files:   int = 0
    events:    list[dict] = []

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line.startswith("data: "):
                    continue
                try:
                    evt = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                events.append(evt)
                t = evt.get("type", "")
                if t == "tool_start":
                    tool_name = evt.get("tool_name") or evt.get("tool") or ""
                elif t == "tool_result":
                    success = evt.get("success")
                    n_files = len(evt.get("files", []))
                    break
                elif t == "error":
                    break
    except TimeoutError:
        events.append({"type": "timeout", "after_s": timeout})
    except Exception as exc:
        events.append({"type": "exception", "message": str(exc)})

    return tool_name, success, n_files, events


# ── Runner ────────────────────────────────────────────────────────────────────

def run_tool(tool_id: int, name: str, prompt: str, timeout: int, nn_dir: str) -> None:
    session_id = f"llm_test_{tool_id:02d}_{uuid.uuid4().hex[:8]}"
    sys.stdout.write(f"  [{tool_id:02d}] {name:<38} ... ")
    sys.stdout.flush()

    t0 = time.perf_counter()
    tool_name, success, n_files, events = stream_events(session_id, prompt, timeout)
    elapsed = time.perf_counter() - t0

    # Save SSE log
    log_path = os.path.join(LDIR, nn_dir, "log", "sse.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Determine status
    last_type = events[-1].get("type", "") if events else ""
    if not tool_name:
        status = "FAIL"
        note   = "LLM did not call any tool"
    elif last_type in ("timeout",):
        status = "FAIL"
        note   = f"Timeout after {timeout}s"
    elif success is False:
        status = "FAIL"
        note   = "tool_result success=False"
    elif success is None and last_type == "exception":
        status = "FAIL"
        note   = events[-1].get("message", "exception")[:60]
    else:
        status = "PASS"
        note   = f"tool={tool_name}"

    sym = "✓" if status == "PASS" else "✗"
    print(f"{sym}{status}  ({elapsed:.1f}s)  {n_files} files", flush=True)
    if status == "FAIL":
        print(f"       NOTE: {note}", flush=True)

    results.append({
        "id": tool_id, "name": name, "status": status,
        "seconds": round(elapsed, 1), "files": n_files,
        "tool_called": tool_name or "", "note": note if status == "FAIL" else "",
        "session_id": session_id,
    })


def skip_tool(tool_id: int, name: str, reason: str, nn_dir: str) -> None:
    sys.stdout.write(f"  [{tool_id:02d}] {name:<38} ... ")
    sys.stdout.flush()
    print(f"⊘SKIP   (0.0s)  {reason}", flush=True)
    results.append({
        "id": tool_id, "name": name, "status": "SKIP",
        "seconds": 0, "files": 0, "tool_called": "", "note": reason, "session_id": "",
    })


# ── Tool prompt definitions ───────────────────────────────────────────────────
#  D     = Test_data root (container path)
#  PATCH = AI_GCP_direct_test root (contains pre-patched CSVs)
#  SH    = _shared/Base_Data
#
# Format: (id, name, nn_dir, prompt, timeout_s)

TOOLS: list[tuple[int, str, str, str, int]] = [

    (1, "Network Analysis", "01_network_analysis",
     f"Please run Network Analysis with the following inputs. "
     f"nodes_table={D}/01_network_analysis/Network Analysis Grouping/nodes.csv, "
     f"links_table={D}/01_network_analysis/Network Analysis Grouping/links.csv, "
     f"shapefile_path={D}/01_network_analysis/Network Analysis Grouping/World_countries_2002.shp, "
     f"nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap.",
     120),

    (2, "CBC Preprocessor", "02_coastal_blue_carbon_preprocessor",
     f"Run Coastal Blue Carbon Preprocessor. "
     f"landcover_snapshot_csv={D}/02_coastal_blue_carbon_preprocessor/snapshots.csv, "
     f"landcover_lookup_table={PATCH}/02_coastal_blue_carbon_preprocessor/output/_patch/lulc_lookup_p.csv.",
     120),

    (3, "Coastal Blue Carbon", "03_coastal_blue_carbon",
     f"Run Coastal Blue Carbon main model. "
     f"landcover_snapshot_csv={D}/02_coastal_blue_carbon_preprocessor/snapshots.csv, "
     f"landcover_transitions_table={D}/03_coastal_blue_carbon/outputs_preprocessor/transitions_sample.csv, "
     f"biophysical_table_path={PATCH}/03_coastal_blue_carbon/output/_patch/biophysical_p.csv, "
     f"analysis_year=2060, do_economic_analysis=false, use_price_table=false.",
     180),

    (4, "Seasonal Water Yield", "04_seasonal_water_yield",
     f"Run Seasonal Water Yield for the Gura watershed. "
     f"aoi_path={D}/04_seasonal_water_yield/watershed_gura.shp, "
     f"dem_raster_path={D}/04_seasonal_water_yield/DEM_gura.tif, "
     f"lulc_raster_path={D}/04_seasonal_water_yield/land_use_gura.tif, "
     f"soil_group_path={D}/04_seasonal_water_yield/soil_group_gura.tif, "
     f"biophysical_table_path={D}/04_seasonal_water_yield/biophysical_table_gura_SWY.csv, "
     f"rain_events_table_path={D}/04_seasonal_water_yield/rain_events_gura.csv, "
     f"et0_dir={D}/04_seasonal_water_yield/ET0_monthly, "
     f"precip_dir={D}/04_seasonal_water_yield/Precipitation_monthly, "
     f"threshold_flow_accumulation=1000, alpha_m=1/12, beta_i=1, gamma=1, "
     f"monthly_alpha=false, user_defined_climate_zones=false, user_defined_local_recharge=false, "
     f"flow_dir_algorithm=MFD.",
     300),

    (5, "Crop Percentile", "05_crop_production_percentile",
     f"Run Crop Production Percentile. "
     f"model_data_path={PATCH}/05_crop_production_percentile/output/model_data_pct, "
     f"landcover_raster_path={D}/05_crop_production_percentile/sample_user_data/landcover.tif, "
     f"landcover_to_crop_table_path={D}/05_crop_production_percentile/sample_user_data/landcover_to_crop_table.csv, "
     f"aggregate_polygon_path={D}/05_crop_production_percentile/sample_user_data/aggregate_shape.shp.",
     180),

    (6, "Crop Regression", "06_crop_production_regression",
     f"Run Crop Production Regression. "
     f"model_data_path={PATCH}/05_crop_production_percentile/output/model_data_reg, "
     f"landcover_raster_path={D}/05_crop_production_percentile/sample_user_data/landcover.tif, "
     f"landcover_to_crop_table_path={D}/05_crop_production_percentile/sample_user_data/landcover_to_crop_table.csv, "
     f"fertilization_rate_table_path={D}/05_crop_production_percentile/sample_user_data/crop_fertilization_rates.csv, "
     f"aggregate_polygon_path={D}/05_crop_production_percentile/sample_user_data/aggregate_shape.shp.",
     180),

    (7, "Carbon Storage", "07_carbon_storage",
     f"Run Carbon Storage model. "
     f"lulc_cur_path={D}/07_carbon_storage/lulc_current_willamette.tif, "
     f"carbon_pools_path={D}/07_carbon_storage/carbon_pools_willamette.csv, "
     f"calc_sequestration=false, do_valuation=false.",
     120),

    (8, "Habitat Quality", "08_habitat_quality",
     f"Run Habitat Quality model. "
     f"lulc_cur_path={D}/08_habitat_quality/lulc_current_willamette.tif, "
     f"threats_table_path={D}/08_habitat_quality/threats_willamette.csv, "
     f"sensitivity_table_path={PATCH}/08_habitat_quality/output/_patch/sensitivity_p.csv, "
     f"half_saturation_constant=0.5.",
     180),

    (9, "Annual Water Yield", "09_annual_water_yield",
     f"Run Annual Water Yield for the Gura watershed. "
     f"eto_path={D}/09_annual_water_yield/reference_ET_gura.tif, "
     f"precipitation_path={D}/09_annual_water_yield/precipitation_gura.tif, "
     f"depth_to_root_rest_layer_path={D}/09_annual_water_yield/depth_to_root_restricting_layer_gura.tif, "
     f"pawc_path={D}/09_annual_water_yield/plant_available_water_fraction_gura.tif, "
     f"lulc_path={D}/09_annual_water_yield/land_use_gura.tif, "
     f"watersheds_path={D}/09_annual_water_yield/watershed_gura.shp, "
     f"biophysical_table_path={D}/09_annual_water_yield/biophysical_table_gura.csv, "
     f"seasonality_constant=15.",
     180),

    (10, "Forest Carbon Edge", "10_forest_carbon_edge_effect",
     f"Run Forest Carbon Edge Effect. "
     f"lulc_raster_path={D}/10_forest_carbon_edge_effect/forest_carbon_edge_lulc_demo.tif, "
     f"biophysical_table_path={D}/10_forest_carbon_edge_effect/forest_edge_carbon_lu_table.csv, "
     f"aoi_vector_path={D}/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.shp, "
     f"tropical_forest_edge_carbon_model_vector_path={D}/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.shp, "
     f"n_nearest_model_points=10, biomass_to_carbon_conversion_factor=0.47, "
     f"compute_forest_edge_effects=true, pools_to_calculate=all.",
     300),

    (11, "Crop Pollination", "11_crop_pollination",
     f"Run Crop Pollination model. "
     f"landcover_raster_path={D}/11_crop_pollination/landcover.tif, "
     f"guild_table_path={D}/11_crop_pollination/guild_table.csv, "
     f"landcover_biophysical_table_path={D}/11_crop_pollination/landcover_biophysical_table.csv.",
     300),

    (12, "DelineateIt", "12_delineateit",
     f"Run DelineateIt to delineate watersheds. "
     f"dem_path={D}/12_delineateit/DEM_gura.tif, detect_pour_points=true.",
     120),

    (13, "RouteDEM", "13_routedem",
     f"Run RouteDEM. "
     f"dem_path={D}/13_routedem/DEM_gura.tif, algorithm=D8, "
     f"calculate_flow_direction=true, calculate_flow_accumulation=true.",
     120),

    (14, "SDR", "14_sdr",
     f"Run Sediment Delivery Ratio (SDR). "
     f"dem_path={D}/14_sdr/DEM_gura.tif, "
     f"erosivity_path={D}/14_sdr/erosivity_gura.tif, "
     f"erodibility_path={D}/14_sdr/erodibility_gura.tif, "
     f"lulc_path={D}/14_sdr/land_use_gura.tif, "
     f"watersheds_path={D}/14_sdr/watershed_gura.shp, "
     f"biophysical_table_path={D}/14_sdr/biophysical_table_Gura.csv, "
     f"threshold_flow_accumulation=1000, k_param=2, sdr_max=0.8, ic_0_param=0.5, l_max=122.",
     300),

    (15, "NDR", "15_ndr",
     f"Run Nutrient Delivery Ratio (NDR). "
     f"dem_path={D}/15_ndr/DEM_gura.tif, "
     f"lulc_path={D}/15_ndr/land_use_gura.tif, "
     f"runoff_proxy_path={D}/15_ndr/precipitation_gura.tif, "
     f"watersheds_path={D}/15_ndr/watershed_gura.shp, "
     f"biophysical_table_path={PATCH}/15_ndr/output/_patch/bio_ndr_p.csv, "
     f"threshold_flow_accumulation=1000, k_param=2, calc_n=true, calc_p=false, "
     f"subsurface_critical_length_n=150, subsurface_eff_n=0.8.",
     300),

    (16, "Urban Cooling", "16_urban_cooling",
     f"Run Urban Cooling model. "
     f"lulc_raster_path={D}/16_urban_cooling/lulc.tif, "
     f"ref_eto_raster_path={D}/16_urban_cooling/et0.tif, "
     f"aoi_vector_path={D}/16_urban_cooling/aoi.shp, "
     f"biophysical_table_path={D}/16_urban_cooling/Biophysical_UHI_fake.csv, "
     f"building_vector_path={D}/16_urban_cooling/sample_buildings.shp, "
     f"t_ref=21.5, uhi_max=3.5, t_air_average_radius=2000, green_area_cooling_distance=1000, "
     f"cc_method=factors, cc_weight_shade=0.6, cc_weight_albedo=0.2, cc_weight_eti=0.2, "
     f"avg_rel_humidity=30, do_energy_valuation=true, "
     f"energy_consumption_table_path={D}/16_urban_cooling/Fake_energy_savings.csv, "
     f"do_productivity_valuation=true.",
     300),

    (17, "Urban Flood", "17_urban_flood",
     f"Run Urban Flood Risk Mitigation. "
     f"aoi_watersheds_path={D}/17_urban_flood/watersheds.gpkg, "
     f"lulc_path={D}/17_urban_flood/lulc.tif, "
     f"soils_hydrological_group_raster_path={D}/17_urban_flood/soilgroup.tif, "
     f"curve_number_table_path={D}/17_urban_flood/Biophysical_water_SF.csv, "
     f"rainfall_depth=40, "
     f"built_infrastructure_vector_path={D}/17_urban_flood/infrastructure.gpkg, "
     f"infrastructure_damage_loss_table_path={D}/17_urban_flood/Damage.csv.",
     180),

    (18, "Urban Stormwater", "18_urban_stormwater",
     f"Run Urban Stormwater Retention. "
     f"lulc_path={D}/18_urban_stormwater/lulc.tif, "
     f"soil_group_path={D}/18_urban_stormwater/soil_groups.tif, "
     f"precipitation_path={D}/18_urban_stormwater/precipitation.tif, "
     f"biophysical_table={D}/18_urban_stormwater/biophysical_table.csv, "
     f"adjust_retention_ratios=true, retention_radius=20, "
     f"road_centerlines_path={D}/18_urban_stormwater/streets.shp, "
     f"aggregate_areas_path={D}/18_urban_stormwater/watershed.shp, "
     f"replacement_cost=1.59.",
     180),

    (19, "Urban Nature Access", "19_urban_nature_access",
     f"Run Urban Nature Access model. "
     f"lulc_raster_path={D}/19_urban_nature_access/paris-lulc.tif, "
     f"lulc_attribute_table={D}/19_urban_nature_access/lulc-attributes.csv, "
     f"population_raster_path={D}/19_urban_nature_access/population.tif, "
     f"admin_boundaries_vector_path={D}/19_urban_nature_access/administrative-units.shp, "
     f"search_radius_mode=radius per population group, "
     f"population_group_radii_table={D}/19_urban_nature_access/pop-group-radii.csv, "
     f"decay_function=dichotomy, urban_nature_demand=250, aggregate_by_pop_group=true.",
     300),

    (20, "Urban Mental Health", "20_urban_mental_health",
     f"Run Urban Mental Health model. "
     f"lulc_raster_path={D}/20_urban_mental_health/paris-lulc.tif, "
     f"lulc_attribute_table={D}/20_urban_mental_health/lulc-attributes.csv, "
     f"population_raster_path={D}/20_urban_mental_health/population.tif, "
     f"admin_boundaries_vector_path={D}/20_urban_mental_health/administrative-units.shp, "
     f"search_radius_mode=uniform radius, search_radius=300, "
     f"decay_function=gaussian, urban_nature_demand=250.",
     300),

    (21, "Scenic Quality", "21_scenic_quality",
     f"Run Scenic Quality model. "
     f"aoi_path={D}/21_scenic_quality/Input/AOI_WCVI.shp, "
     f"structure_path={D}/21_scenic_quality/Input/AquaWEM_points.shp, "
     f"dem_path={D}/21_scenic_quality/Input/claybark_dem.tif, "
     f"refraction=0.13, do_valuation=false.",
     300),

    (22, "HRA", "22_hra",
     f"Run Habitat Risk Assessment (HRA). "
     f"info_table_path={D}/22_hra/Input/habitat_stressor_info.csv, "
     f"criteria_table_path={D}/22_hra/Input/exposure_consequence_criteria.csv, "
     f"aoi_vector_path={D}/22_hra/Input/subregions.shp, "
     f"resolution=500, max_rating=3, risk_eq=Euclidean, decay_eq=linear, "
     f"n_overlapping_stressors=2, visualize_outputs=false.",
     180),

    (23, "Wave Energy", "23_wave_energy",
     f"Run Wave Energy model. "
     f"wave_base_data_path={D}/23_wave_energy/input/WaveData, "
     f"analysis_area=West Coast of North America and Hawaii, "
     f"aoi_path={D}/23_wave_energy/input/AOI_WCVI.shp, "
     f"machine_perf_path={D}/23_wave_energy/input/Machine_AquaBuOY_Performance.csv, "
     f"machine_param_path={D}/23_wave_energy/input/Machine_AquaBuOY_Parameter.csv, "
     f"dem_path={SH}/global_dem.tif, valuation_container=false.",
     180),

    (24, "Coastal Vulnerability", "24_coastal_vulnerability",
     f"Run Coastal Vulnerability model. "
     f"aoi_vector_path={D}/24_coastal_vulnerability/aoi_grandbahama_utm.shp, "
     f"bathymetry_raster_path={D}/24_coastal_vulnerability/bathymetry.tif, "
     f"dem_averaging_radius=900, "
     f"dem_path={D}/24_coastal_vulnerability/dem_srtm_grandbahama.tif, "
     f"geomorphology_fill_value=4, "
     f"geomorphology_vector_path={D}/24_coastal_vulnerability/geomorphology_grandbahama.shp, "
     f"landmass_vector_path={D}/24_coastal_vulnerability/landmass_polygon.shp, "
     f"max_fetch_distance=30000, model_resolution=1000, "
     f"wwiii_vector_path={D}/24_coastal_vulnerability/WaveWatchIII_global.shp, "
     f"habitat_table_path={D}/24_coastal_vulnerability/GrandBahama_Habitats/Natural_Habitats.csv, "
     f"shelf_contour_vector_path={D}/24_coastal_vulnerability/continental_shelf_polyline_global.shp, "
     f"population_raster_path={D}/24_coastal_vulnerability/population_grandbahama.tif, "
     f"population_radius=500.",
     300),

    (25, "Offshore Wind Energy", "25_wind_energy",
     f"Run Offshore Wind Energy model. "
     f"aoi_vector_path={D}/25_wind_energy/input/New_England_US_Aoi.shp, "
     f"bathymetry_path={SH}/global_dem.tif, "
     f"land_polygon_vector_path={SH}/global_polygon.shp, "
     f"global_wind_parameters_path={D}/25_wind_energy/input/global_wind_energy_parameters.csv, "
     f"turbine_parameters_path={D}/25_wind_energy/input/3_6_turbine.csv, "
     f"wind_data_path={D}/25_wind_energy/input/ECNA_EEZ_WEBPAR_Aug27_2012.csv, "
     f"number_of_turbines=80, min_depth=3, max_depth=60, "
     f"min_distance=0, max_distance=200000, avg_grid_distance=4, valuation_container=false.",
     180),

    # Tool 26 Recreation requires external NatCap server — always skip
    # (26, "Recreation & Tourism", "26_recreation", ..., 300),

    (27, "Scenario Gen Proximity", "27_scenario_gen_proximity",
     f"Run Scenario Generator Proximity. "
     f"base_lulc_path={D}/27_scenario_gen_proximity/scenario_proximity_lulc.tif, "
     f"aoi_path={D}/27_scenario_gen_proximity/scenario_proximity_aoi.shp, "
     f"replacement_lucode=12, area_to_convert=20000, "
     f"focal_landcover_codes=1 2 3 4 5, convertible_landcover_codes=1 2 3 4 5, "
     f"convert_nearest_to_edge=true, convert_farthest_from_edge=true, n_steps=1.",
     180),

    (28, "OLS Regression", "28_ols",
     f"Run OLS Regression. "
     f"input_csv={D}/28_ols/ols_data.csv, "
     f"dependent_variable=y, independent_variables=x1,x2,x3.",
     60),

    (29, "FAMD", "29_famd",
     f"Run FAMD factor analysis on mixed data. "
     f"input_csv={D}/29_famd/famd_data.csv, "
     f"quantitative_variables=age,income, qualitative_variables=gender,region.",
     120),

    (30, "CO2 Emissions", "30_co2_emissions",
     f"Run CO2 Emissions analysis. "
     f"input_csv={D}/30_co2_emissions/co2_data.csv, "
     f"animal_count_field=animals, length_km_field=distance_km, "
     f"capacity_per_trip=50, co2_per_km_per_trip=2.6.",
     60),

    (31, "Cost-Benefit Analysis", "31_cost_benefit_analysis",
     f"Run Cost-Benefit Analysis. "
     f"input_csv={D}/31_cost_benefit_analysis/projects.csv, "
     f"economic_data_csv={D}/31_cost_benefit_analysis/economic_data.csv, "
     f"key_field=project_id, cost_field=cost_usd, revenue_field=revenue_usd.",
     60),

    (32, "Population Density", "32_population_density",
     f"Run Population Density analysis. "
     f"input_csv={D}/32_population_density/population.csv, "
     f"population_field=pop_2020, area_km2_field=area_km2, "
     f"population_t1_field=pop_2010, population_t2_field=pop_2020.",
     60),

    (33, "Radial Flows", "33_radial_flows",
     f"Draw Radial Flows on the map. "
     f"input_csv={D}/33_radial_flows/flows.csv, "
     f"from_x_field=from_lon, from_y_field=from_lat, "
     f"to_x_field=to_lon, to_y_field=to_lat, value_field=flow_value.",
     60),

    (34, "Commodity Trade", "34_commodity_trade",
     f"Run Commodity Trade analysis. "
     f"trade_csv={D}/34_commodity_trade/trade.csv, "
     f"from_country_field=exporter_iso3, to_country_field=importer_iso3, "
     f"value_field=trade_usd.",
     60),

    (35, "Add Agents", "35_add_agents",
     f"Add agents from CSV to the map. "
     f"input_csv={D}/35_add_agents/agents.csv, "
     f"x_field=longitude, y_field=latitude, name_field=agent_name.",
     60),

    (36, "Draw Agents Table", "36_draw_agents_table",
     f"Draw agents from table on the map. "
     f"input_csv={D}/36_draw_agents_table/agents_table.csv, "
     f"x_field=longitude, y_field=latitude, name_field=name.",
     60),

    (37, "Add Causes", "37_add_causes",
     f"Add causes from CSV to the telecoupling diagram. "
     f"input_csv={D}/37_add_causes/causes.csv, "
     f"x_field=longitude, y_field=latitude, description_field=cause_description.",
     60),

    (38, "Add Systems", "38_add_systems",
     f"Add systems from CSV to the map. "
     f"input_csv={D}/38_add_systems/systems.csv, "
     f"x_field=longitude, y_field=latitude, name_field=system_name.",
     60),

    (39, "Draw Systems Table", "39_draw_systems_table",
     f"Draw systems from table on the map. "
     f"input_csv={D}/39_draw_systems_table/systems_table.csv, "
     f"x_field=longitude, y_field=latitude, name_field=name.",
     60),

    (40, "Add Media Flows", "40_add_media_flows",
     f"Add media flows from HTML article. "
     f"html_file={D}/40_add_media_flows/article.html, "
     f"source_lon=116.4, source_lat=39.9, "
     f"country_reference_csv={D}/40_add_media_flows/country_centroids.csv.",
     120),

    (41, "Food Security", "41_food_security",
     f"Run Food Security analysis. "
     f"fao_csv={D}/41_food_security/fao_food_security.csv, "
     f"countries=China,India,USA, indicator_field=Prevalence of undernourishment.",
     60),

    (42, "Nutrition Metrics", "42_nutrition_metrics",
     f"Run Nutrition Metrics analysis. "
     f"population_csv={D}/42_nutrition_metrics/nutrition_data.csv, "
     f"age_col=age_group, sex_col=sex, weight_col=weight_kg, population_col=population.",
     60),
]

ID_MAP = {t[0]: t for t in TOOLS}


# ── Main ──────────────────────────────────────────────────────────────────────

def main(ids: list[int]) -> None:
    id_set = set(ids)
    selected = [t for t in TOOLS if t[0] in id_set]
    n = len(selected) + (1 if 26 in id_set else 0)

    print(f"\n{'='*72}", flush=True)
    print(f"  AI_GCP_llm_test  —  {n} tool(s) selected  (full LLM path)", flush=True)
    print(f"  API  : {API_URL}", flush=True)
    print(f"  Data : {D}", flush=True)
    print(f"  Logs : {LDIR}/<nn>/log/sse.jsonl", flush=True)
    print(f"{'='*72}", flush=True)

    for tool_id, name, nn_dir, prompt, timeout in TOOLS:
        if tool_id not in id_set:
            continue
        run_tool(tool_id, name, prompt, timeout, nn_dir)

    if 26 in id_set:
        skip_tool(26, "Recreation & Tourism",
                  "requires external NatCap recmodel server", "26_recreation")

    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    total   = len(results)

    print(f"\n{'='*72}", flush=True)
    print(f"  {'ID':<4} {'Tool':<38} {'Status':<6}  {'Sec':>6}  {'Files':>5}  Note", flush=True)
    print(f"  {'--':<4} {'----':<38} {'------':<6}  {'---':>6}  {'-----':>5}", flush=True)
    for r in results:
        sym  = "✓" if r["status"] == "PASS" else ("✗" if r["status"] == "FAIL" else "⊘")
        note = r["note"][:36] if r["note"] else r["tool_called"][:36]
        print(f"  {r['id']:<4} {r['name']:<38} {sym}{r['status']:<5}  "
              f"{r['seconds']:>6.1f}  {r['files']:>5}  {note}", flush=True)

    print(f"\n  Total: {total}  ✓ PASS: {passed}  ✗ FAIL: {failed}  ⊘ SKIP: {skipped}", flush=True)
    print(f"{'='*72}", flush=True)

    out = os.path.join(LDIR, "results_llm.json")
    with open(out, "w") as f:
        json.dump({"summary": {"total": total, "passed": passed,
                                "failed": failed, "skipped": skipped},
                   "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\n  → Results saved to {out}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default="",
                        help="Comma-separated tool IDs 1-42 (default: all)")
    args = parser.parse_args()
    ids = ([int(x.strip()) for x in args.ids.split(",") if x.strip()]
           if args.ids else list(range(1, 43)))
    main(ids)
