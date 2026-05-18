"""
Manual Client-to-GCP Browser Test
Opens Chrome and tests all tools at http://34.42.83.50/ like a human.
Results saved to test_results.json and test_report.md in this directory.
"""

import sys
import json
import os
import time
import glob as glob_mod
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def _p(s: str) -> str:
    """Return string safe for cp1252 stdout (replace non-encodable chars)."""
    return s.encode('cp1252', errors='replace').decode('cp1252')

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).parent
SYST_DIR     = SCRIPT_DIR.parent
TEST_DATA    = SYST_DIR / "Test_data"
PATCH_DATA   = SYST_DIR / "AI_GCP_direct_test"
URL          = "http://34.42.83.50/"
TOOL_TIMEOUT = 25 * 60 * 1000   # 25 min per tool
CALL_TIMEOUT  = 5 * 60 * 1000   # 5 min to see the blue card
RETRY_FAILS  = True              # Re-run only FAIL/ERROR/TIMEOUT tools from existing results

# ---------------------------------------------------------------------------
# File path resolver
# ---------------------------------------------------------------------------
def resolve_files(specs: list[str]) -> tuple[list[str], list[str]]:
    """Return (resolved_paths, missing_specs)."""
    resolved, missing = [], []
    for spec in specs:
        if spec.endswith("/*"):
            dir_path = _spec_to_path(spec[:-2])
            if dir_path and Path(dir_path).is_dir():
                files = [str(p) for p in Path(dir_path).rglob("*") if p.is_file()]
                resolved.extend(files)
            else:
                missing.append(spec)
        else:
            path = _spec_to_path(spec)
            if path and Path(path).exists():
                resolved.append(path)
            else:
                missing.append(spec)
    return resolved, missing

def _spec_to_path(spec: str) -> str | None:
    if spec.startswith("Test_data/"):
        return str(TEST_DATA / spec[len("Test_data/"):])
    if spec.startswith("AI_GCP_direct_test/"):
        return str(PATCH_DATA / spec[len("AI_GCP_direct_test/"):])
    return None

# ---------------------------------------------------------------------------
# Tool definitions  (id, folder, prompt, file_specs, skip)
# skip=True  → skipped in test run
# For model_data_pct / model_data_reg: server has built-in default, do NOT upload
# ---------------------------------------------------------------------------
TOOLS = [
  ("01", "01_network_analysis",
   "Run Network Analysis on the uploaded files. nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap.",
   ["Test_data/01_network_analysis/Network Analysis Grouping/nodes.csv",
    "Test_data/01_network_analysis/Network Analysis Grouping/links.csv",
    "Test_data/01_network_analysis/Network Analysis Grouping/World_countries_2002.shp",
    "Test_data/01_network_analysis/Network Analysis Grouping/World_countries_2002.dbf",
    "Test_data/01_network_analysis/Network Analysis Grouping/World_countries_2002.shx",
    "Test_data/01_network_analysis/Network Analysis Grouping/World_countries_2002.prj"],
   False),

  ("02", "02_coastal_blue_carbon_preprocessor",
   "Run Coastal Blue Carbon Preprocessor on the uploaded files.",
   ["Test_data/02_coastal_blue_carbon_preprocessor/snapshots.csv",
    "Test_data/02_coastal_blue_carbon_preprocessor/GBJC_2010_mean_Resample.tif",
    "Test_data/02_coastal_blue_carbon_preprocessor/GBJC_2030_mean_Resample.tif",
    "Test_data/02_coastal_blue_carbon_preprocessor/GBJC_2050_mean_Resample.tif",
    "AI_GCP_direct_test/02_coastal_blue_carbon_preprocessor/output/_patch/lulc_lookup_p.csv"],
   False),

  ("03", "03_coastal_blue_carbon",
   "Run Coastal Blue Carbon main model on the uploaded files. The transitions CSV has already been manually edited. analysis_year=2060, do_economic_analysis=false, use_price_table=false.",
   ["Test_data/02_coastal_blue_carbon_preprocessor/snapshots.csv",
    "Test_data/03_coastal_blue_carbon/outputs_preprocessor/transitions_sample.csv",
    "AI_GCP_direct_test/03_coastal_blue_carbon/output/_patch/biophysical_p.csv"],
   False),

  ("04", "04_seasonal_water_yield",
   "Run Seasonal Water Yield on the uploaded files. threshold_flow_accumulation=1000, alpha_m=1/12, beta_i=1, gamma=1, monthly_alpha=false, user_defined_climate_zones=false, user_defined_local_recharge=false, flow_dir_algorithm=MFD.",
   ["Test_data/04_seasonal_water_yield/watershed_gura.shp",
    "Test_data/04_seasonal_water_yield/watershed_gura.dbf",
    "Test_data/04_seasonal_water_yield/watershed_gura.shx",
    "Test_data/04_seasonal_water_yield/watershed_gura.prj",
    "Test_data/04_seasonal_water_yield/DEM_gura.tif",
    "Test_data/04_seasonal_water_yield/land_use_gura.tif",
    "Test_data/04_seasonal_water_yield/soil_group_gura.tif",
    "Test_data/04_seasonal_water_yield/biophysical_table_gura_SWY.csv",
    "Test_data/04_seasonal_water_yield/rain_events_gura.csv",
    "Test_data/04_seasonal_water_yield/ET0_monthly/*",
    "Test_data/04_seasonal_water_yield/Precipitation_monthly/*"],
   False),

  ("05", "05_crop_production_percentile",
   "Run Crop Production Percentile on the uploaded files.",
   ["Test_data/05_crop_production_percentile/sample_user_data/landcover.tif",
    "Test_data/05_crop_production_percentile/sample_user_data/landcover_to_crop_table.csv",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.shp",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.dbf",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.shx",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.prj"],
   False),

  ("06", "06_crop_production_regression",
   "Run Crop Production Regression on the uploaded files.",
   ["Test_data/05_crop_production_percentile/sample_user_data/landcover.tif",
    "Test_data/05_crop_production_percentile/sample_user_data/landcover_to_crop_table.csv",
    "Test_data/05_crop_production_percentile/sample_user_data/crop_fertilization_rates.csv",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.shp",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.dbf",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.shx",
    "Test_data/05_crop_production_percentile/sample_user_data/aggregate_shape.prj"],
   False),

  ("07", "07_carbon_storage",
   "Run Carbon Storage on the uploaded files. calc_sequestration=false, do_valuation=false.",
   ["Test_data/07_carbon_storage/lulc_current_willamette.tif",
    "Test_data/07_carbon_storage/carbon_pools_willamette.csv"],
   False),

  ("08", "08_habitat_quality",
   "Run Habitat Quality on the uploaded files. half_saturation_constant=0.5.",
   ["Test_data/08_habitat_quality/lulc_current_willamette.tif",
    "Test_data/08_habitat_quality/lulc_future_willamette.tif",
    "Test_data/08_habitat_quality/threats_willamette.csv",
    "Test_data/08_habitat_quality/crops_c.tif",
    "Test_data/08_habitat_quality/crops_f.tif",
    "Test_data/08_habitat_quality/railroad_c.tif",
    "Test_data/08_habitat_quality/railroad_f.tif",
    "Test_data/08_habitat_quality/urban_c.tif",
    "Test_data/08_habitat_quality/urban_f.tif",
    "Test_data/08_habitat_quality/timber_c.tif",
    "Test_data/08_habitat_quality/timber_f.tif",
    "Test_data/08_habitat_quality/roads1_c.tif",
    "Test_data/08_habitat_quality/roads1_f.tif",
    "Test_data/08_habitat_quality/roads2_c.tif",
    "Test_data/08_habitat_quality/roads2_f.tif",
    "Test_data/08_habitat_quality/roads3_c.tif",
    "Test_data/08_habitat_quality/roads3_f.tif",
    "Test_data/08_habitat_quality/accessibility_willamette.shp",
    "Test_data/08_habitat_quality/accessibility_willamette.dbf",
    "Test_data/08_habitat_quality/accessibility_willamette.prj",
    "Test_data/08_habitat_quality/accessibility_willamette.shx",
    "AI_GCP_direct_test/08_habitat_quality/output/_patch/sensitivity_p.csv"],
   False),

  ("09", "09_annual_water_yield",
   "Run Annual Water Yield on the uploaded files. seasonality_constant=15.",
   ["Test_data/09_annual_water_yield/reference_ET_gura.tif",
    "Test_data/09_annual_water_yield/precipitation_gura.tif",
    "Test_data/09_annual_water_yield/depth_to_root_restricting_layer_gura.tif",
    "Test_data/09_annual_water_yield/plant_available_water_fraction_gura.tif",
    "Test_data/09_annual_water_yield/land_use_gura.tif",
    "Test_data/09_annual_water_yield/watershed_gura.shp",
    "Test_data/09_annual_water_yield/watershed_gura.dbf",
    "Test_data/09_annual_water_yield/watershed_gura.shx",
    "Test_data/09_annual_water_yield/watershed_gura.prj",
    "Test_data/09_annual_water_yield/biophysical_table_gura.csv"],
   False),

  ("10", "10_forest_carbon_edge_effect",
   "Run Forest Carbon Edge Effect on the uploaded files. n_nearest_model_points=10, biomass_to_carbon_conversion_factor=0.47, compute_forest_edge_effects=true, pools_to_calculate=all.",
   ["Test_data/10_forest_carbon_edge_effect/forest_carbon_edge_lulc_demo.tif",
    "Test_data/10_forest_carbon_edge_effect/forest_edge_carbon_lu_table.csv",
    "Test_data/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.shp",
    "Test_data/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.dbf",
    "Test_data/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.shx",
    "Test_data/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.prj",
    "Test_data/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.shp",
    "Test_data/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.dbf",
    "Test_data/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.shx",
    "Test_data/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.prj"],
   False),

  ("11", "11_crop_pollination",
   "Run Crop Pollination on the uploaded files.",
   ["Test_data/11_crop_pollination/landcover.tif",
    "Test_data/11_crop_pollination/guild_table.csv",
    "Test_data/11_crop_pollination/landcover_biophysical_table.csv"],
   False),

  ("12", "12_delineateit",
   "Run DelineateIt on the uploaded DEM. detect_pour_points=true.",
   ["Test_data/12_delineateit/DEM_gura.tif"],
   False),

  ("13", "13_routedem",
   "Run RouteDEM on the uploaded DEM. algorithm=D8, calculate_flow_direction=true, calculate_flow_accumulation=true.",
   ["Test_data/13_routedem/DEM_gura.tif"],
   False),

  ("14", "14_sdr",
   "Run Sediment Delivery Ratio (SDR) on the uploaded files. threshold_flow_accumulation=1000, k_param=2, sdr_max=0.8, ic_0_param=0.5, l_max=122.",
   ["Test_data/14_sdr/DEM_gura.tif",
    "Test_data/14_sdr/erosivity_gura.tif",
    "Test_data/14_sdr/erodibility_gura.tif",
    "Test_data/14_sdr/land_use_gura.tif",
    "Test_data/14_sdr/watershed_gura.shp",
    "Test_data/14_sdr/watershed_gura.dbf",
    "Test_data/14_sdr/watershed_gura.shx",
    "Test_data/14_sdr/watershed_gura.prj",
    "Test_data/14_sdr/biophysical_table_Gura.csv"],
   False),

  ("15", "15_ndr",
   "Run Nutrient Delivery Ratio (NDR) on the uploaded files. threshold_flow_accumulation=1000, k_param=2, calc_n=true, calc_p=false, subsurface_critical_length_n=150, subsurface_eff_n=0.8.",
   ["Test_data/15_ndr/DEM_gura.tif",
    "Test_data/15_ndr/land_use_gura.tif",
    "Test_data/15_ndr/precipitation_gura.tif",
    "Test_data/15_ndr/watershed_gura.shp",
    "Test_data/15_ndr/watershed_gura.dbf",
    "Test_data/15_ndr/watershed_gura.shx",
    "Test_data/15_ndr/watershed_gura.prj",
    "AI_GCP_direct_test/15_ndr/output/_patch/bio_ndr_p.csv"],
   False),

  ("16", "16_urban_cooling",
   "Run Urban Cooling on the uploaded files. t_ref=21.5, uhi_max=3.5, t_air_average_radius=2000, green_area_cooling_distance=1000, cc_method=factors, cc_weight_shade=0.6, cc_weight_albedo=0.2, cc_weight_eti=0.2, avg_rel_humidity=30, do_energy_valuation=true, do_productivity_valuation=true.",
   ["Test_data/16_urban_cooling/lulc.tif",
    "Test_data/16_urban_cooling/et0.tif",
    "Test_data/16_urban_cooling/aoi.shp",
    "Test_data/16_urban_cooling/aoi.dbf",
    "Test_data/16_urban_cooling/aoi.shx",
    "Test_data/16_urban_cooling/aoi.prj",
    "Test_data/16_urban_cooling/Biophysical_UHI_fake.csv",
    "Test_data/16_urban_cooling/sample_buildings.shp",
    "Test_data/16_urban_cooling/sample_buildings.dbf",
    "Test_data/16_urban_cooling/sample_buildings.shx",
    "Test_data/16_urban_cooling/sample_buildings.prj",
    "Test_data/16_urban_cooling/Fake_energy_savings.csv"],
   False),

  ("17", "17_urban_flood",
   "Run Urban Flood Risk Mitigation on the uploaded files. rainfall_depth=40.",
   ["Test_data/17_urban_flood/watersheds.gpkg",
    "Test_data/17_urban_flood/lulc.tif",
    "Test_data/17_urban_flood/soilgroup.tif",
    "Test_data/17_urban_flood/Biophysical_water_SF.csv",
    "Test_data/17_urban_flood/infrastructure.gpkg",
    "Test_data/17_urban_flood/Damage.csv"],
   False),

  ("18", "18_urban_stormwater",
   "Run Urban Stormwater Retention on the uploaded files. adjust_retention_ratios=true, retention_radius=20, replacement_cost=1.59.",
   ["Test_data/18_urban_stormwater/lulc.tif",
    "Test_data/18_urban_stormwater/soil_groups.tif",
    "Test_data/18_urban_stormwater/precipitation.tif",
    "Test_data/18_urban_stormwater/biophysical_table.csv",
    "Test_data/18_urban_stormwater/streets.shp",
    "Test_data/18_urban_stormwater/streets.dbf",
    "Test_data/18_urban_stormwater/streets.shx",
    "Test_data/18_urban_stormwater/streets.prj",
    "Test_data/18_urban_stormwater/watershed.shp",
    "Test_data/18_urban_stormwater/watershed.dbf",
    "Test_data/18_urban_stormwater/watershed.shx",
    "Test_data/18_urban_stormwater/watershed.prj"],
   False),

  ("19", "19_urban_nature_access",
   "Run Urban Nature Access on the uploaded files. search_radius_mode=radius per population group, decay_function=dichotomy, urban_nature_demand=250, aggregate_by_pop_group=true.",
   ["Test_data/19_urban_nature_access/paris-lulc.tif",
    "Test_data/19_urban_nature_access/lulc-attributes.csv",
    "Test_data/19_urban_nature_access/population.tif",
    "Test_data/19_urban_nature_access/administrative-units.shp",
    "Test_data/19_urban_nature_access/administrative-units.dbf",
    "Test_data/19_urban_nature_access/administrative-units.shx",
    "Test_data/19_urban_nature_access/administrative-units.prj",
    "Test_data/19_urban_nature_access/pop-group-radii.csv"],
   False),

  ("20", "20_urban_mental_health",
   "Run Urban Mental Health on the uploaded files. search_radius_mode=uniform radius, search_radius=300, decay_function=gaussian, urban_nature_demand=250.",
   ["Test_data/20_urban_mental_health/paris-lulc.tif",
    "Test_data/20_urban_mental_health/lulc-attributes.csv",
    "Test_data/20_urban_mental_health/population.tif",
    "Test_data/20_urban_mental_health/administrative-units.shp",
    "Test_data/20_urban_mental_health/administrative-units.dbf",
    "Test_data/20_urban_mental_health/administrative-units.shx",
    "Test_data/20_urban_mental_health/administrative-units.prj"],
   False),

  ("21", "21_scenic_quality",
   "Run Scenic Quality on the uploaded files. refraction=0.13, do_valuation=false.",
   ["Test_data/21_scenic_quality/Input/AOI_WCVI.shp",
    "Test_data/21_scenic_quality/Input/AOI_WCVI.dbf",
    "Test_data/21_scenic_quality/Input/AOI_WCVI.shx",
    "Test_data/21_scenic_quality/Input/AOI_WCVI.prj",
    "Test_data/21_scenic_quality/Input/AquaWEM_points.shp",
    "Test_data/21_scenic_quality/Input/AquaWEM_points.dbf",
    "Test_data/21_scenic_quality/Input/AquaWEM_points.shx",
    "Test_data/21_scenic_quality/Input/AquaWEM_points.prj",
    "Test_data/21_scenic_quality/Input/claybark_dem.tif"],
   False),

  ("22", "22_hra",
   "Run Habitat Risk Assessment (HRA) on the uploaded files. resolution=500, max_rating=3, risk_eq=Euclidean, decay_eq=linear, n_overlapping_stressors=2, visualize_outputs=false.",
   ["AI_GCP_direct_test/22_hra/output/_patch/habitat_stressor_info.csv",
    "AI_GCP_direct_test/22_hra/output/_patch/exposure_consequence_criteria.csv",
    "Test_data/22_hra/Input/subregions.shp",
    "Test_data/22_hra/Input/subregions.dbf",
    "Test_data/22_hra/Input/subregions.shx",
    "Test_data/22_hra/Input/subregions.prj",
    "Test_data/22_hra/Input/habitat_layers/eelgrass.tif",
    "AI_GCP_direct_test/22_hra/output/_patch/hardbottom.shp",
    "AI_GCP_direct_test/22_hra/output/_patch/hardbottom.dbf",
    "AI_GCP_direct_test/22_hra/output/_patch/hardbottom.shx",
    "AI_GCP_direct_test/22_hra/output/_patch/hardbottom.prj",
    "AI_GCP_direct_test/22_hra/output/_patch/kelp.shp",
    "AI_GCP_direct_test/22_hra/output/_patch/kelp.dbf",
    "AI_GCP_direct_test/22_hra/output/_patch/kelp.shx",
    "AI_GCP_direct_test/22_hra/output/_patch/kelp.prj",
    "AI_GCP_direct_test/22_hra/output/_patch/softbottom.shp",
    "AI_GCP_direct_test/22_hra/output/_patch/softbottom.dbf",
    "AI_GCP_direct_test/22_hra/output/_patch/softbottom.shx",
    "AI_GCP_direct_test/22_hra/output/_patch/softbottom.prj",
    "AI_GCP_direct_test/22_hra/output/_patch/FinfishAquacultureComm.shp",
    "AI_GCP_direct_test/22_hra/output/_patch/FinfishAquacultureComm.dbf",
    "AI_GCP_direct_test/22_hra/output/_patch/FinfishAquacultureComm.shx",
    "AI_GCP_direct_test/22_hra/output/_patch/FinfishAquacultureComm.prj",
    "AI_GCP_direct_test/22_hra/output/_patch/RecFishing.shp",
    "AI_GCP_direct_test/22_hra/output/_patch/RecFishing.dbf",
    "AI_GCP_direct_test/22_hra/output/_patch/RecFishing.shx",
    "AI_GCP_direct_test/22_hra/output/_patch/RecFishing.prj",
    "AI_GCP_direct_test/22_hra/output/_patch/ShellfishAquacultureComm.shp",
    "AI_GCP_direct_test/22_hra/output/_patch/ShellfishAquacultureComm.dbf",
    "AI_GCP_direct_test/22_hra/output/_patch/ShellfishAquacultureComm.shx",
    "AI_GCP_direct_test/22_hra/output/_patch/ShellfishAquacultureComm.prj",
    "Test_data/22_hra/Input/spatially_explicit_layers/eelgrass_connectivity_rate.tif"],
   False),

  ("23", "23_wave_energy",
   "Run Wave Energy on the uploaded files. analysis_area=West Coast of North America and Hawaii, valuation_container=false.",
   ["Test_data/23_wave_energy/input/Machine_AquaBuOY_Performance.csv",
    "Test_data/23_wave_energy/input/Machine_AquaBuOY_Parameter.csv",
    "Test_data/23_wave_energy/input/AOI_WCVI.shp",
    "Test_data/23_wave_energy/input/AOI_WCVI.dbf",
    "Test_data/23_wave_energy/input/AOI_WCVI.shx",
    "Test_data/23_wave_energy/input/AOI_WCVI.prj"],
   False),

  ("24", "24_coastal_vulnerability",
   "Run Coastal Vulnerability on the uploaded files. dem_averaging_radius=900, geomorphology_fill_value=4, max_fetch_distance=30000, model_resolution=1000, population_radius=500.",
   ["Test_data/24_coastal_vulnerability/aoi_grandbahama_utm.shp",
    "Test_data/24_coastal_vulnerability/aoi_grandbahama_utm.dbf",
    "Test_data/24_coastal_vulnerability/aoi_grandbahama_utm.shx",
    "Test_data/24_coastal_vulnerability/aoi_grandbahama_utm.prj",
    "Test_data/24_coastal_vulnerability/bathymetry.tif",
    "Test_data/24_coastal_vulnerability/dem_srtm_grandbahama.tif",
    "Test_data/24_coastal_vulnerability/geomorphology_grandbahama.shp",
    "Test_data/24_coastal_vulnerability/geomorphology_grandbahama.dbf",
    "Test_data/24_coastal_vulnerability/geomorphology_grandbahama.shx",
    "Test_data/24_coastal_vulnerability/geomorphology_grandbahama.prj",
    "Test_data/24_coastal_vulnerability/landmass_polygon.shp",
    "Test_data/24_coastal_vulnerability/landmass_polygon.dbf",
    "Test_data/24_coastal_vulnerability/landmass_polygon.shx",
    "Test_data/24_coastal_vulnerability/landmass_polygon.prj",
    "Test_data/24_coastal_vulnerability/WaveWatchIII_global.shp",
    "Test_data/24_coastal_vulnerability/WaveWatchIII_global.dbf",
    "Test_data/24_coastal_vulnerability/WaveWatchIII_global.shx",
    "Test_data/24_coastal_vulnerability/WaveWatchIII_global.prj",
    "Test_data/24_coastal_vulnerability/GrandBahama_Habitats/*",
    "Test_data/24_coastal_vulnerability/continental_shelf_polyline_global.shp",
    "Test_data/24_coastal_vulnerability/continental_shelf_polyline_global.dbf",
    "Test_data/24_coastal_vulnerability/continental_shelf_polyline_global.shx",
    "Test_data/24_coastal_vulnerability/continental_shelf_polyline_global.prj",
    "Test_data/24_coastal_vulnerability/population_grandbahama.tif"],
   False),

  ("25", "25_wind_energy",
   "Run Offshore Wind Energy on the uploaded files. number_of_turbines=80, min_depth=3, max_depth=60, min_distance=0, max_distance=200000, avg_grid_distance=4, valuation_container=false.",
   ["Test_data/25_wind_energy/input/New_England_US_Aoi.shp",
    "Test_data/25_wind_energy/input/New_England_US_Aoi.dbf",
    "Test_data/25_wind_energy/input/New_England_US_Aoi.shx",
    "Test_data/25_wind_energy/input/New_England_US_Aoi.prj",
    "Test_data/25_wind_energy/input/global_wind_energy_parameters.csv",
    "Test_data/25_wind_energy/input/3_6_turbine.csv",
    "Test_data/25_wind_energy/input/ECNA_EEZ_WEBPAR_Aug27_2012.csv"],
   False),

  ("26", "26_recreation", "(SKIPPED)", [], True),

  ("27", "27_scenario_gen_proximity",
   "Run Scenario Generator Proximity on the uploaded files. replacement_lucode=12, area_to_convert=20000, focal_landcover_codes=1 2 3 4 5, convertible_landcover_codes=1 2 3 4 5, convert_nearest_to_edge=true, convert_farthest_from_edge=true, n_steps=1.",
   ["Test_data/27_scenario_gen_proximity/scenario_proximity_lulc.tif"],
   False),

  ("28", "28_ols",
   "Run OLS Regression on the uploaded CSV. dependent_variable=y, independent_variables=x1,x2,x3.",
   ["Test_data/28_ols/ols_data.csv"],
   False),

  ("29", "29_famd",
   "Run FAMD factor analysis on the uploaded CSV. quantitative_variables=age,income, qualitative_variables=gender,region.",
   ["Test_data/29_famd/famd_data.csv"],
   False),

  ("30", "30_co2_emissions",
   "Run CO2 Emissions analysis on the uploaded CSV. animal_count_field=animals, length_km_field=distance_km, capacity_per_trip=50, co2_per_km_per_trip=2.6.",
   ["Test_data/30_co2_emissions/co2_data.csv"],
   False),

  ("31", "31_cost_benefit_analysis",
   "Run Cost-Benefit Analysis (CBA) to compute economic returns from the uploaded CSVs. key_field=project_id, cost_field=cost_usd, revenue_field=revenue_usd.",
   ["Test_data/31_cost_benefit_analysis/projects.csv",
    "Test_data/31_cost_benefit_analysis/economic_data.csv"],
   False),

  ("32", "32_population_density",
   "Run run_population_count_density on the uploaded CSV. population_field=pop_2020, area_km2_field=area_km2.",
   ["Test_data/32_population_density/population.csv"],
   False),

  ("33", "33_radial_flows",
   "Draw Radial Flows from the uploaded CSV. from_x_field=from_lon, from_y_field=from_lat, to_x_field=to_lon, to_y_field=to_lat, value_field=flow_value.",
   ["Test_data/33_radial_flows/flows.csv"],
   False),

  ("34", "34_commodity_trade",
   "Use the run_commodity_trade function on the uploaded CSV. from_country_field=from_country, to_country_field=to_country, value_field=trade_usd.",
   ["Test_data/34_commodity_trade/trade_flows_iso3.csv"],
   False),

  ("35", "35_add_agents",
   "Add agents from the uploaded CSV. x_field=longitude, y_field=latitude, name_field=agent_name.",
   ["Test_data/35_add_agents/agents.csv"],
   False),

  ("36", "36_draw_agents_table",
   "Use the run_draw_agents_from_table function on the uploaded CSV. x_field=longitude, y_field=latitude, name_field=name.",
   ["Test_data/36_draw_agents_table/agents_table.csv"],
   False),

  ("37", "37_add_causes",
   "Run run_add_causes_interactively on the uploaded CSV. x_field=longitude, y_field=latitude, description_field=cause_description.",
   ["Test_data/37_add_causes/causes.csv"],
   False),

  ("38", "38_add_systems",
   "Add systems from the uploaded CSV. x_field=longitude, y_field=latitude, name_field=system_name.",
   ["Test_data/38_add_systems/systems.csv"],
   False),

  ("39", "39_draw_systems_table",
   "Use the run_draw_systems_from_table function on the uploaded CSV. x_field=longitude, y_field=latitude, name_field=name.",
   ["Test_data/39_draw_systems_table/systems_table.csv"],
   False),

  ("40", "40_add_media_flows",
   "Add media flows from the uploaded HTML article. source_lon=116.4, source_lat=39.9.",
   ["Test_data/40_add_media_flows/article.html",
    "Test_data/40_add_media_flows/country_centroids.csv"],
   False),

  ("41", "41_food_security",
   "Run Food Security analysis on the uploaded CSV. countries=China,India,USA, indicator_field=Prevalence of undernourishment.",
   ["Test_data/41_food_security/fao_food_security.csv"],
   False),

  ("42", "42_nutrition_metrics",
   "Calculate nutrition energy requirements (LLER) by age group and sex from the uploaded CSV. age_col=age_group, sex_col=sex, weight_col=weight_kg, population_col=population.",
   ["Test_data/42_nutrition_metrics/nutrition_data.csv"],
   False),
]

# ---------------------------------------------------------------------------
# Core test function
# ---------------------------------------------------------------------------
def run_tool_test(page, tool_id, folder, prompt, file_specs, results, log_f):
    name = f"{tool_id}_{folder.split('_', 1)[1] if '_' in folder else folder}"
    ts = datetime.now().strftime("%H:%M:%S")
    msg = f"[{ts}] Testing {name} ..."
    print(msg); log_f.write(msg + "\n"); log_f.flush()

    files, missing = resolve_files(file_specs)

    if not files and file_specs:
        r = {"tool": name, "status": "DATA_MISSING", "error": f"Missing: {missing}", "time_s": 0, "ts": ts}
        results.append(r)
        print(_p(f"  [DATA_MISSING] {missing}"))
        log_f.write(f"  DATA_MISSING: {missing}\n"); log_f.flush()
        return

    t0 = time.time()

    try:
        # --- Create new chat ---
        try:
            new_chat_btn = page.locator('button:has-text("New Chat")').first
            new_chat_btn.click(timeout=5000)
            page.wait_for_timeout(800)
        except Exception:
            # Fallback: reload page
            page.reload(wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

        # --- Upload files ---
        if files:
            file_input = page.locator('input[type="file"]')
            # Playwright can set files on hidden inputs
            file_input.set_input_files(files)
            page.wait_for_timeout(1500)
            uploaded_msg = f"  Uploaded {len(files)} file(s): {[Path(f).name for f in files[:4]]}{'...' if len(files) > 4 else ''}"
            print(uploaded_msg); log_f.write(uploaded_msg + "\n"); log_f.flush()

        # --- Type prompt ---
        text_input = page.locator('input[placeholder="Enter a prompt here"]')
        text_input.click()
        text_input.fill(prompt)
        page.wait_for_timeout(300)

        # --- Send ---
        text_input.press("Enter")
        sent_ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{sent_ts}] Sent. Waiting for tool call ..."); log_f.flush()

        # --- Wait for blue card (tool called) ---
        tool_called = False
        try:
            page.wait_for_selector('.bg-blue-50', timeout=CALL_TIMEOUT)
            tool_called = True
            print("  Blue card appeared (tool called)")
        except PWTimeout:
            pass

        if not tool_called:
            # Check if there's just an assistant text response (no tool card)
            elapsed = time.time() - t0
            # Check for any error
            content = page.content()
            if "❌" in content:
                err_text = _extract_error(page)
                r = {"tool": name, "status": "FAIL", "error": err_text, "time_s": round(elapsed, 1), "ts": ts}
            else:
                r = {"tool": name, "status": "FAIL", "error": "LLM did not call tool (no blue card after 5 min)", "time_s": round(elapsed, 1), "ts": ts}
            results.append(r)
            print(_p(f"  [FAIL] {r['error']}"))
            log_f.write(f"  FAIL: {r['error']}\n"); log_f.flush()
            return

        # --- Wait for completion (green card or error) ---
        success = False
        error_msg = None
        deadline = TOOL_TIMEOUT - CALL_TIMEOUT  # remaining time

        try:
            page.wait_for_function(
                """() => {
                    const greenCards = document.querySelectorAll('.bg-green-50');
                    const bodyText = document.body.innerText;
                    const hasError = bodyText.includes('❌');
                    const streaming = document.querySelector('.animate-pulse');
                    if (greenCards.length > 0) return 'success';
                    if (hasError && !streaming) return 'error';
                    return false;
                }""",
                timeout=deadline
            )
        except PWTimeout:
            pass

        content = page.content()
        body_text = page.evaluate("() => document.body.innerText")

        if "bg-green-50" in content:
            success = True
        elif "❌" in body_text:
            error_msg = _extract_error(page)

        elapsed = time.time() - t0

        if success:
            r = {"tool": name, "status": "PASS", "time_s": round(elapsed, 1), "ts": ts}
            results.append(r)
            print(f"  [PASS] ({elapsed:.0f}s)")
            log_f.write(f"  PASS ({elapsed:.0f}s)\n"); log_f.flush()
        elif error_msg is not None:
            r = {"tool": name, "status": "FAIL", "error": error_msg, "time_s": round(elapsed, 1), "ts": ts}
            results.append(r)
            print(_p(f"  [FAIL] {error_msg}"))
            log_f.write(f"  FAIL: {error_msg}\n"); log_f.flush()
        else:
            r = {"tool": name, "status": "TIMEOUT", "error": "No result after 25 min", "time_s": round(elapsed, 1), "ts": ts}
            results.append(r)
            print("  [TIMEOUT]")
            log_f.write("  TIMEOUT\n"); log_f.flush()

    except Exception as e:
        elapsed = time.time() - t0
        r = {"tool": name, "status": "ERROR", "error": str(e)[:300], "time_s": round(elapsed, 1), "ts": ts}
        results.append(r)
        print(_p(f"  [ERROR] {e}"))
        log_f.write(f"  ERROR: {e}\n"); log_f.flush()


def _extract_error(page) -> str:
    try:
        body = page.evaluate("() => document.body.innerText")
        for line in body.split("\n"):
            if "❌" in line:
                return line.strip()[:300]
    except Exception:
        pass
    return "Error detected (could not extract text)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    report_path = SCRIPT_DIR / "test_results.json"
    log_path    = SCRIPT_DIR / "test_run.log"
    results = []
    resume_after_id = None
    retry_ids = None  # None = run all; set = run only these IDs

    if report_path.exists():
        try:
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if existing:
                if RETRY_FAILS:
                    # Find FAIL/ERROR/TIMEOUT tool IDs and strip them from results
                    retry_ids = {r["tool"].split("_")[0] for r in existing
                                 if r["status"] in ("FAIL", "ERROR", "TIMEOUT")}
                    results = [r for r in existing if r["tool"].split("_")[0] not in retry_ids]
                    print(f"RETRY_FAILS mode: retrying {len(retry_ids)} tool(s): {sorted(retry_ids)}")
                else:
                    results = existing
                    last_tid = results[-1]["tool"].split("_")[0]
                    resume_after_id = last_tid
                    print(f"Resuming after tool {resume_after_id} ({len(results)} already done)")
        except Exception:
            pass

    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"CSIS Manual Browser Test — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"URL: {URL}")
    print(f"{'='*60}\n")

    log_mode = "a" if (resume_after_id or retry_ids) else "w"
    with open(log_path, log_mode, encoding="utf-8") as log_f:
        if retry_ids:
            log_f.write(f"\n--- RETRY_FAILS at {start_time.isoformat()} — retrying: {sorted(retry_ids)} ---\n\n")
        elif resume_after_id:
            log_f.write(f"\n--- Resume at {start_time.isoformat()} (after {resume_after_id}) ---\n\n")
        else:
            log_f.write(f"CSIS Manual Browser Test — {start_time.isoformat()}\nURL: {URL}\n\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=50)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            # Open the site
            print("Loading http://34.42.83.50/ ...")
            page.goto(URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            print("Site loaded.\n")

            skipping = resume_after_id is not None
            for (tid, folder, prompt, file_specs, skip) in TOOLS:
                # RETRY_FAILS mode: only run tools in retry_ids
                if retry_ids is not None:
                    if tid not in retry_ids:
                        continue
                else:
                    # Normal resume mode
                    if skipping:
                        if tid == resume_after_id:
                            skipping = False
                        continue  # skip up to AND including the resume point

                if skip:
                    ts = datetime.now().strftime("%H:%M:%S")
                    results.append({"tool": f"{tid}_{folder.split('_',1)[1]}", "status": "SKIP", "time_s": 0, "ts": ts})
                    print(f"[{ts}] SKIP {tid}_{folder}")
                    log_f.write(f"SKIP {tid}_{folder}\n")
                    continue

                run_tool_test(page, tid, folder, prompt, file_specs, results, log_f)

                # Save intermediate results after each tool
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

                page.wait_for_timeout(2000)  # brief pause between tools

            browser.close()

    # Final JSON save
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate markdown report
    _write_markdown(results, start_time)

    # Print summary
    total  = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    errors  = sum(1 for r in results if r["status"] in ("ERROR","TIMEOUT","DATA_MISSING"))

    print(f"\n{'='*60}")
    print(f"DONE  —  {datetime.now().strftime('%H:%M:%S')}")
    print(f"  PASS   : {passed}")
    print(f"  FAIL   : {failed}")
    print(f"  ERROR  : {errors}")
    print(f"  SKIP   : {skipped}")
    print(f"  Total  : {total}")
    print(f"\nResults: {report_path}")
    print(f"Report : {SCRIPT_DIR / 'test_report.md'}")


def _write_markdown(results, start_time):
    lines = [
        f"# CSIS Manual Browser Test Report",
        f"",
        f"**Date**: {start_time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**URL**: {URL}  ",
        f"",
        f"| # | Tool | Status | Time (s) | Error |",
        f"|---|------|--------|----------|-------|",
    ]
    for i, r in enumerate(results, 1):
        status = r["status"]
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭", "TIMEOUT": "⏱",
                "ERROR": "💥", "DATA_MISSING": "📂"}.get(status, status)
        err = r.get("error", "")[:80].replace("|", "｜")
        lines.append(f"| {i} | {r['tool']} | {icon} {status} | {r.get('time_s',0)} | {err} |")

    passed  = sum(1 for r in results if r["status"] == "PASS")
    total   = sum(1 for r in results if r["status"] != "SKIP")
    lines += ["", f"**Result**: {passed}/{total} passed"]

    md_path = SCRIPT_DIR / "test_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
