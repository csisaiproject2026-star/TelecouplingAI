"""
_generate_guides.py
Generates one subfolder per tool (42 total) under Manual_ClientToGCP_test/,
each containing a how_to_test.md file.
Also writes a top-level README.md for the directory.

Run from Windows PowerShell:
    python _generate_guides.py
"""

import os
from pathlib import Path

# Base directory = directory this script lives in
BASE_DIR = Path(__file__).parent.resolve()

GCP_URL = "http://34.42.83.50/"
TEST_DATA_GCP = "/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data"
PATCH_DATA_GCP = "/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/AI_GCP_direct_test"
SHARED_DATA_GCP = "/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data/_shared/Base_Data"

# ---------------------------------------------------------------------------
# Tool definitions
# Each entry:
#   id          : int (01-42)
#   name        : str
#   folder      : str (subfolder name)
#   call_name   : str
#   category    : "InVEST" | "TeleBox"
#   files       : list[str]  — displayed verbatim
#   prompt      : str
#   outputs     : list[str]
#   notes       : str | None
# ---------------------------------------------------------------------------

TOOLS = [
    # ------------------------------------------------------------------ InVEST
    dict(
        id=1,
        name="Network Analysis",
        folder="01_network_analysis",
        call_name="run_network_analysis",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/01_network_analysis/Network Analysis Grouping/`:",
            "- `nodes.csv`",
            "- `links.csv`",
            "- `World_countries_2002.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
        ],
        prompt="Run Network Analysis on the uploaded files. nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap.",
        outputs=["Network graph JSON", "Clustering result CSV"],
        notes=None,
    ),
    dict(
        id=2,
        name="CBC Preprocessor",
        folder="02_coastal_blue_carbon_preprocessor",
        call_name="run_cbc_preprocessor",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/02_coastal_blue_carbon_preprocessor/`:",
            "- `snapshots.csv`",
            "",
            "From GCP **patch** path `AI_GCP_direct_test/02_coastal_blue_carbon_preprocessor/output/_patch/`:",
            "- `lulc_lookup_p.csv`  *(patched version required)*",
        ],
        prompt="Run Coastal Blue Carbon Preprocessor on the uploaded files.",
        outputs=["transitions.csv", "Carbon lookup table"],
        notes=(
            "`lulc_lookup_p.csv` is a patched lookup table from the AI_GCP_direct_test output. "
            "Download it from the patch path above; do NOT use the original."
        ),
    ),
    dict(
        id=3,
        name="Coastal Blue Carbon",
        folder="03_coastal_blue_carbon",
        call_name="run_coastal_blue_carbon",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/02_coastal_blue_carbon_preprocessor/`:",
            "- `snapshots.csv`",
            "",
            "From GCP server path `Test_data/03_coastal_blue_carbon/outputs_preprocessor/`:",
            "- `transitions_sample.csv`",
            "",
            "From GCP **patch** path `AI_GCP_direct_test/03_coastal_blue_carbon/output/_patch/`:",
            "- `biophysical_p.csv`  *(patched version required)*",
        ],
        prompt="Run Coastal Blue Carbon main model on the uploaded files. analysis_year=2060, do_economic_analysis=false, use_price_table=false.",
        outputs=["Carbon stock rasters", "Net sequestration CSV"],
        notes=(
            "`biophysical_p.csv` is a patched biophysical table from the AI_GCP_direct_test output. "
            "Download it from the patch path above."
        ),
    ),
    dict(
        id=4,
        name="Seasonal Water Yield",
        folder="04_seasonal_water_yield",
        call_name="run_seasonal_water_yield",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/04_seasonal_water_yield/`:",
            "- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `DEM_gura.tif`",
            "- `land_use_gura.tif`",
            "- `soil_group_gura.tif`",
            "- `biophysical_table_gura_SWY.csv`",
            "- `rain_events_gura.csv`",
            "- All 12 files in `ET0_monthly/` directory",
            "- All 12 files in `Precipitation_monthly/` directory",
        ],
        prompt=(
            "Run Seasonal Water Yield on the uploaded files. "
            "threshold_flow_accumulation=1000, alpha_m=1/12, beta_i=1, gamma=1, "
            "monthly_alpha=false, user_defined_climate_zones=false, "
            "user_defined_local_recharge=false, flow_dir_algorithm=MFD."
        ),
        outputs=["QF rasters (monthly)", "B rasters", "L raster"],
        notes="Upload the 24 monthly rasters individually (12 ET0 + 12 precipitation). Total file count is large; allow extra time for upload.",
    ),
    dict(
        id=5,
        name="Crop Percentile",
        folder="05_crop_production_percentile",
        call_name="run_crop_percentile",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/05_crop_production_percentile/sample_user_data/`:",
            "- `landcover.tif`",
            "- `landcover_to_crop_table.csv`",
            "- `aggregate_shape.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "",
            "From GCP **patch** path `AI_GCP_direct_test/05_crop_production_percentile/output/model_data_pct/`:",
            "- All files in that directory  *(patched model data required)*",
        ],
        prompt="Run Crop Production Percentile on the uploaded files.",
        outputs=["Yield CSV per crop", "Aggregate yield rasters"],
        notes=(
            "The `model_data_pct/` folder contains patched crop model data. "
            "Download all files from the patch path and upload them alongside the user data files."
        ),
    ),
    dict(
        id=6,
        name="Crop Regression",
        folder="06_crop_production_regression",
        call_name="run_crop_regression",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/05_crop_production_percentile/sample_user_data/`:",
            "- `landcover.tif`",
            "- `landcover_to_crop_table.csv`",
            "- `crop_fertilization_rates.csv`",
            "- `aggregate_shape.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "",
            "From GCP **patch** path `AI_GCP_direct_test/05_crop_production_percentile/output/model_data_reg/`:",
            "- All files in that directory  *(patched model data required)*",
        ],
        prompt="Run Crop Production Regression on the uploaded files.",
        outputs=["Regression yield CSV", "Regression rasters"],
        notes=(
            "The `model_data_reg/` folder contains patched regression model data. "
            "Download all files from the patch path and upload them."
        ),
    ),
    dict(
        id=7,
        name="Carbon Storage",
        folder="07_carbon_storage",
        call_name="run_carbon_storage",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/07_carbon_storage/`:",
            "- `lulc_current_willamette.tif`",
            "- `carbon_pools_willamette.csv`",
        ],
        prompt="Run Carbon Storage on the uploaded files. calc_sequestration=false, do_valuation=false.",
        outputs=["Total carbon stock raster", "Carbon pool summary CSV"],
        notes=None,
    ),
    dict(
        id=8,
        name="Habitat Quality",
        folder="08_habitat_quality",
        call_name="run_habitat_quality",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/08_habitat_quality/`:",
            "- `lulc_current_willamette.tif`",
            "- `threats_willamette.csv`",
            "",
            "From GCP **patch** path `AI_GCP_direct_test/08_habitat_quality/output/_patch/`:",
            "- `sensitivity_p.csv`  *(patched version required)*",
        ],
        prompt="Run Habitat Quality on the uploaded files. half_saturation_constant=0.5.",
        outputs=["Habitat quality raster", "Habitat degradation raster"],
        notes=(
            "`sensitivity_p.csv` is a patched sensitivity table. "
            "Download it from the patch path above."
        ),
    ),
    dict(
        id=9,
        name="Annual Water Yield",
        folder="09_annual_water_yield",
        call_name="run_annual_water_yield",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/09_annual_water_yield/`:",
            "- `reference_ET_gura.tif`",
            "- `precipitation_gura.tif`",
            "- `depth_to_root_restricting_layer_gura.tif`",
            "- `plant_available_water_fraction_gura.tif`",
            "- `land_use_gura.tif`",
            "- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `biophysical_table_gura.csv`",
        ],
        prompt="Run Annual Water Yield on the uploaded files. seasonality_constant=15.",
        outputs=["Annual yield raster", "Per-watershed yield table"],
        notes=None,
    ),
    dict(
        id=10,
        name="Forest Carbon Edge",
        folder="10_forest_carbon_edge_effect",
        call_name="run_forest_carbon_edge",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/10_forest_carbon_edge_effect/`:",
            "- `forest_carbon_edge_lulc_demo.tif`",
            "- `forest_edge_carbon_lu_table.csv`",
            "- `forest_carbon_edge_demo_aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `core_data/forest_carbon_edge_regression_model_parameters.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
        ],
        prompt=(
            "Run Forest Carbon Edge Effect on the uploaded files. "
            "n_nearest_model_points=10, biomass_to_carbon_conversion_factor=0.47, "
            "compute_forest_edge_effects=true, pools_to_calculate=all."
        ),
        outputs=["Carbon stock raster", "Edge effect raster"],
        notes=(
            "The regression model parameters shapefile lives in a `core_data/` subdirectory. "
            "Upload all sidecar files (.dbf .shx .prj) for both shapefiles."
        ),
    ),
    dict(
        id=11,
        name="Crop Pollination",
        folder="11_crop_pollination",
        call_name="run_crop_pollination",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/11_crop_pollination/`:",
            "- `landcover.tif`",
            "- `guild_table.csv`",
            "- `landcover_biophysical_table.csv`",
        ],
        prompt="Run Crop Pollination on the uploaded files.",
        outputs=["Pollinator abundance raster", "Crop yield raster"],
        notes=None,
    ),
    dict(
        id=12,
        name="DelineateIt",
        folder="12_delineateit",
        call_name="run_delineateit",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/12_delineateit/`:",
            "- `DEM_gura.tif`",
        ],
        prompt="Run DelineateIt on the uploaded DEM. detect_pour_points=true.",
        outputs=["Watershed shapefile", "Pour points shapefile"],
        notes=None,
    ),
    dict(
        id=13,
        name="RouteDEM",
        folder="13_routedem",
        call_name="run_routedem",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/13_routedem/`:",
            "- `DEM_gura.tif`",
        ],
        prompt="Run RouteDEM on the uploaded DEM. algorithm=D8, calculate_flow_direction=true, calculate_flow_accumulation=true.",
        outputs=["Flow direction raster", "Flow accumulation raster"],
        notes=None,
    ),
    dict(
        id=14,
        name="SDR",
        folder="14_sdr",
        call_name="run_sdr",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/14_sdr/`:",
            "- `DEM_gura.tif`",
            "- `erosivity_gura.tif`",
            "- `erodibility_gura.tif`",
            "- `land_use_gura.tif`",
            "- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `biophysical_table_Gura.csv`",
        ],
        prompt=(
            "Run Sediment Delivery Ratio (SDR) on the uploaded files. "
            "threshold_flow_accumulation=1000, k_param=2, sdr_max=0.8, "
            "ic_0_param=0.5, l_max=122."
        ),
        outputs=["SDR raster", "Sediment export raster", "Per-watershed summary CSV"],
        notes=None,
    ),
    dict(
        id=15,
        name="NDR",
        folder="15_ndr",
        call_name="run_ndr",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/15_ndr/`:",
            "- `DEM_gura.tif`",
            "- `land_use_gura.tif`",
            "- `precipitation_gura.tif`",
            "- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "",
            "From GCP **patch** path `AI_GCP_direct_test/15_ndr/output/_patch/`:",
            "- `bio_ndr_p.csv`  *(patched biophysical table required)*",
        ],
        prompt=(
            "Run Nutrient Delivery Ratio (NDR) on the uploaded files. "
            "threshold_flow_accumulation=1000, k_param=2, calc_n=true, calc_p=false, "
            "subsurface_critical_length_n=150, subsurface_eff_n=0.8."
        ),
        outputs=["N export raster", "NDR raster", "Per-watershed nutrient table"],
        notes=(
            "`bio_ndr_p.csv` is a patched biophysical table. "
            "Download it from the patch path and upload it with the other files."
        ),
    ),
    dict(
        id=16,
        name="Urban Cooling",
        folder="16_urban_cooling",
        call_name="run_urban_cooling",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/16_urban_cooling/`:",
            "- `lulc.tif`",
            "- `et0.tif`",
            "- `aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `Biophysical_UHI_fake.csv`",
            "- `sample_buildings.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `Fake_energy_savings.csv`",
        ],
        prompt=(
            "Run Urban Cooling on the uploaded files. "
            "t_ref=21.5, uhi_max=3.5, t_air_average_radius=2000, "
            "green_area_cooling_distance=1000, cc_method=factors, "
            "cc_weight_shade=0.6, cc_weight_albedo=0.2, cc_weight_eti=0.2, "
            "avg_rel_humidity=30, do_energy_valuation=true, do_productivity_valuation=true."
        ),
        outputs=["HM raster", "T_air raster", "Energy savings CSV", "Work productivity CSV"],
        notes=None,
    ),
    dict(
        id=17,
        name="Urban Flood",
        folder="17_urban_flood",
        call_name="run_urban_flood",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/17_urban_flood/`:",
            "- `watersheds.gpkg`",
            "- `lulc.tif`",
            "- `soilgroup.tif`",
            "- `Biophysical_water_SF.csv`",
            "- `infrastructure.gpkg`",
            "- `Damage.csv`",
        ],
        prompt="Run Urban Flood Risk Mitigation on the uploaded files. rainfall_depth=40.",
        outputs=["Runoff raster", "Retention raster", "Infrastructure damage CSV"],
        notes="Input files are GeoPackage (.gpkg) format — upload as-is.",
    ),
    dict(
        id=18,
        name="Urban Stormwater",
        folder="18_urban_stormwater",
        call_name="run_urban_stormwater",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/18_urban_stormwater/`:",
            "- `lulc.tif`",
            "- `soil_groups.tif`",
            "- `precipitation.tif`",
            "- `biophysical_table.csv`",
            "- `streets.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `watershed.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
        ],
        prompt=(
            "Run Urban Stormwater Retention on the uploaded files. "
            "adjust_retention_ratios=true, retention_radius=20, replacement_cost=1.59."
        ),
        outputs=["Retention ratio raster", "Runoff raster", "Replacement cost raster"],
        notes=None,
    ),
    dict(
        id=19,
        name="Urban Nature Access",
        folder="19_urban_nature_access",
        call_name="run_urban_nature_access",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/19_urban_nature_access/`:",
            "- `paris-lulc.tif`",
            "- `lulc-attributes.csv`",
            "- `population.tif`",
            "- `administrative-units.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `pop-group-radii.csv`",
        ],
        prompt=(
            "Run Urban Nature Access on the uploaded files. "
            "search_radius_mode=radius per population group, decay_function=dichotomy, "
            "urban_nature_demand=250, aggregate_by_pop_group=true."
        ),
        outputs=["Nature access raster", "Per-admin-unit supply/demand CSV"],
        notes=None,
    ),
    dict(
        id=20,
        name="Urban Mental Health",
        folder="20_urban_mental_health",
        call_name="run_urban_mental_health",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/20_urban_mental_health/`:",
            "- `paris-lulc.tif`",
            "- `lulc-attributes.csv`",
            "- `population.tif`",
            "- `administrative-units.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
        ],
        prompt=(
            "Run Urban Mental Health on the uploaded files. "
            "search_radius_mode=uniform radius, search_radius=300, "
            "decay_function=gaussian, urban_nature_demand=250."
        ),
        outputs=["Mental health index raster", "Per-admin-unit summary CSV"],
        notes=None,
    ),
    dict(
        id=21,
        name="Scenic Quality",
        folder="21_scenic_quality",
        call_name="run_scenic_quality",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/21_scenic_quality/Input/`:",
            "- `AOI_WCVI.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `AquaWEM_points.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `claybark_dem.tif`",
        ],
        prompt="Run Scenic Quality on the uploaded files. refraction=0.13, do_valuation=false.",
        outputs=["Viewshed raster", "Scenic quality raster"],
        notes=None,
    ),
    dict(
        id=22,
        name="HRA",
        folder="22_hra",
        call_name="run_habitat_risk_assessment",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/22_hra/Input/`:",
            "- `habitat_stressor_info.csv`",
            "- `exposure_consequence_criteria.csv`",
            "- `subregions.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
        ],
        prompt=(
            "Run Habitat Risk Assessment (HRA) on the uploaded files. "
            "resolution=500, max_rating=3, risk_eq=Euclidean, decay_eq=linear, "
            "n_overlapping_stressors=2, visualize_outputs=false."
        ),
        outputs=["Risk rasters per habitat", "Risk summary CSV"],
        notes=None,
    ),
    dict(
        id=23,
        name="Wave Energy",
        folder="23_wave_energy",
        call_name="run_wave_energy_production",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/23_wave_energy/input/`:",
            "- `Machine_AquaBuOY_Performance.csv`",
            "- `Machine_AquaBuOY_Parameter.csv`",
            "- `AOI_WCVI.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "",
            "WaveData (~811 MB) and the global DEM are **not** uploaded — the tool uses "
            "the server's built-in copies automatically. No server paths needed.",
        ],
        prompt=(
            "Run Wave Energy on the uploaded files. "
            "analysis_area=West Coast of North America and Hawaii, "
            "valuation_container=false."
        ),
        outputs=["Wave energy raster", "Captured wave energy raster"],
        notes=(
            "Do not pass wave_base_data_path or bathymetry_path — omit them and the tool "
            "automatically uses the server's built-in WaveData and global DEM, then notes "
            "in its reply that the built-in defaults were used."
        ),
    ),
    dict(
        id=24,
        name="Coastal Vulnerability",
        folder="24_coastal_vulnerability",
        call_name="run_coastal_vulnerability",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/24_coastal_vulnerability/`:",
            "- `aoi_grandbahama_utm.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `bathymetry.tif`",
            "- `dem_srtm_grandbahama.tif`",
            "- `geomorphology_grandbahama.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `landmass_polygon.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `WaveWatchIII_global.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `GrandBahama_Habitats/Natural_Habitats.csv`",
            "- `continental_shelf_polyline_global.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `population_grandbahama.tif`",
        ],
        prompt=(
            "Run Coastal Vulnerability on the uploaded files. "
            "dem_averaging_radius=900, geomorphology_fill_value=4, "
            "max_fetch_distance=30000, model_resolution=1000, population_radius=500."
        ),
        outputs=["Coastal exposure index raster", "Habitat protection raster", "Summary CSV"],
        notes="Several global shapefiles (WaveWatchIII, continental shelf) are large — allow extra upload time.",
    ),
    dict(
        id=25,
        name="Offshore Wind Energy",
        folder="25_wind_energy",
        call_name="run_offshore_wind_energy",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/25_wind_energy/input/`:",
            "- `New_England_US_Aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
            "- `global_wind_energy_parameters.csv`",
            "- `3_6_turbine.csv`",
            "- `ECNA_EEZ_WEBPAR_Aug27_2012.csv`",
            "",
            "The global DEM and global land polygon are **not** uploaded — the tool uses "
            "the server's built-in copies automatically. No server paths needed.",
        ],
        prompt=(
            "Run Offshore Wind Energy on the uploaded files. "
            "number_of_turbines=80, min_depth=3, max_depth=60, "
            "min_distance=0, max_distance=200000, avg_grid_distance=4, valuation_container=false."
        ),
        outputs=["Wind energy density raster", "Harvested energy raster", "Turbine site shapefile"],
        notes=(
            "Do not pass bathymetry_path or land_polygon_vector_path — omit them and the tool "
            "automatically uses the server's built-in global DEM and land polygon, then notes "
            "in its reply that the built-in defaults were used."
        ),
    ),
    dict(
        id=26,
        name="Recreation & Tourism",
        folder="26_recreation",
        call_name="run_recreation_tourism",
        category="InVEST",
        files=[],
        prompt="(SKIPPED — see Notes)",
        outputs=[],
        notes=(
            "**SKIP THIS TEST.** Recreation & Tourism requires an external NatCap recmodel server "
            "at `34.44.144.58:54321` which may not be available. "
            "This tool cannot be tested end-to-end via the client UI without that server."
        ),
    ),
    dict(
        id=27,
        name="Scenario Gen Proximity",
        folder="27_scenario_gen_proximity",
        call_name="run_scenario_gen_proximity",
        category="InVEST",
        files=[
            "From GCP server path `Test_data/27_scenario_gen_proximity/`:",
            "- `scenario_proximity_lulc.tif`",
            "- `scenario_proximity_aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)",
        ],
        prompt=(
            "Run Scenario Generator Proximity on the uploaded files. "
            "replacement_lucode=12, area_to_convert=20000, "
            "focal_landcover_codes=1 2 3 4 5, convertible_landcover_codes=1 2 3 4 5, "
            "convert_nearest_to_edge=true, convert_farthest_from_edge=true, n_steps=1."
        ),
        outputs=["Modified LULC raster", "Conversion statistics CSV"],
        notes=None,
    ),
    # ------------------------------------------------------------------ TeleBox
    dict(
        id=28,
        name="OLS Regression",
        folder="28_ols",
        call_name="run_ols_regression",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/28_ols/`:",
            "- `ols_data.csv`",
        ],
        prompt="Run OLS Regression on the uploaded CSV. dependent_variable=y, independent_variables=x1,x2,x3.",
        outputs=["Regression summary JSON", "Coefficient table"],
        notes=None,
    ),
    dict(
        id=29,
        name="FAMD",
        folder="29_famd",
        call_name="run_famd",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/29_famd/`:",
            "- `famd_data.csv`",
        ],
        prompt="Run FAMD factor analysis on the uploaded CSV. quantitative_variables=age,income, qualitative_variables=gender,region.",
        outputs=["FAMD component scores CSV", "Variance explained chart"],
        notes=None,
    ),
    dict(
        id=30,
        name="CO2 Emissions",
        folder="30_co2_emissions",
        call_name="run_co2_emissions",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/30_co2_emissions/`:",
            "- `co2_data.csv`",
        ],
        prompt=(
            "Run CO2 Emissions analysis on the uploaded CSV. "
            "animal_count_field=animals, length_km_field=distance_km, "
            "capacity_per_trip=50, co2_per_km_per_trip=2.6."
        ),
        outputs=["CO2 emissions summary CSV", "Bar chart"],
        notes=None,
    ),
    dict(
        id=31,
        name="Cost-Benefit Analysis",
        folder="31_cost_benefit_analysis",
        call_name="run_cost_benefit_analysis",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/31_cost_benefit_analysis/`:",
            "- `projects.csv`",
            "- `economic_data.csv`",
        ],
        prompt=(
            "Run Cost-Benefit Analysis on the uploaded CSVs. "
            "key_field=project_id, cost_field=cost_usd, revenue_field=revenue_usd."
        ),
        outputs=["NPV table", "BCR summary CSV"],
        notes=None,
    ),
    dict(
        id=32,
        name="Population Density",
        folder="32_population_density",
        call_name="run_population_density",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/32_population_density/`:",
            "- `population.csv`",
        ],
        prompt="Run Population Density analysis on the uploaded CSV. population_field=pop_2020, area_km2_field=area_km2.",
        outputs=["Density summary CSV", "Choropleth map data"],
        notes=None,
    ),
    dict(
        id=33,
        name="Radial Flows",
        folder="33_radial_flows",
        call_name="run_radial_flows",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/33_radial_flows/`:",
            "- `flows.csv`",
        ],
        prompt=(
            "Draw Radial Flows from the uploaded CSV. "
            "from_x_field=from_lon, from_y_field=from_lat, "
            "to_x_field=to_lon, to_y_field=to_lat, value_field=flow_value."
        ),
        outputs=["Radial flow map rendering"],
        notes=None,
    ),
    dict(
        id=34,
        name="Commodity Trade",
        folder="34_commodity_trade",
        call_name="run_commodity_trade",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/34_commodity_trade/`:",
            "- `trade.csv`",
        ],
        prompt=(
            "Run Commodity Trade analysis on the uploaded CSV. "
            "from_country_field=exporter_iso3, to_country_field=importer_iso3, value_field=trade_usd."
        ),
        outputs=["Trade flow map", "Summary trade table"],
        notes=None,
    ),
    dict(
        id=35,
        name="Add Agents",
        folder="35_add_agents",
        call_name="run_add_agents",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/35_add_agents/`:",
            "- `agents.csv`",
        ],
        prompt="Add agents from the uploaded CSV. x_field=longitude, y_field=latitude, name_field=agent_name.",
        outputs=["Agent layer added to map"],
        notes=None,
    ),
    dict(
        id=36,
        name="Draw Agents Table",
        folder="36_draw_agents_table",
        call_name="run_draw_agents_table",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/36_draw_agents_table/`:",
            "- `agents_table.csv`",
        ],
        prompt="Draw agents from the uploaded table. x_field=longitude, y_field=latitude, name_field=name.",
        outputs=["Agent table rendered on map"],
        notes=None,
    ),
    dict(
        id=37,
        name="Add Causes",
        folder="37_add_causes",
        call_name="run_add_causes",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/37_add_causes/`:",
            "- `causes.csv`",
        ],
        prompt="Add causes from the uploaded CSV. x_field=longitude, y_field=latitude, description_field=cause_description.",
        outputs=["Cause markers added to map"],
        notes=None,
    ),
    dict(
        id=38,
        name="Add Systems",
        folder="38_add_systems",
        call_name="run_add_systems",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/38_add_systems/`:",
            "- `systems.csv`",
        ],
        prompt="Add systems from the uploaded CSV. x_field=longitude, y_field=latitude, name_field=system_name.",
        outputs=["System markers added to map"],
        notes=None,
    ),
    dict(
        id=39,
        name="Draw Systems Table",
        folder="39_draw_systems_table",
        call_name="run_draw_systems_table",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/39_draw_systems_table/`:",
            "- `systems_table.csv`",
        ],
        prompt="Draw systems from the uploaded table. x_field=longitude, y_field=latitude, name_field=name.",
        outputs=["Systems table rendered on map"],
        notes=None,
    ),
    dict(
        id=40,
        name="Add Media Flows",
        folder="40_add_media_flows",
        call_name="run_add_media_flows",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/40_add_media_flows/`:",
            "- `article.html`",
            "- `country_centroids.csv`",
        ],
        prompt="Add media flows from the uploaded HTML article. source_lon=116.4, source_lat=39.9.",
        outputs=["Media flow arcs rendered on map"],
        notes=None,
    ),
    dict(
        id=41,
        name="Food Security",
        folder="41_food_security",
        call_name="run_food_security",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/41_food_security/`:",
            "- `fao_food_security.csv`",
        ],
        prompt=(
            "Run Food Security analysis on the uploaded CSV. "
            "countries=China,India,USA, "
            "indicator_field=Prevalence of undernourishment."
        ),
        outputs=["Food security index CSV", "Country comparison chart"],
        notes=None,
    ),
    dict(
        id=42,
        name="Nutrition Metrics",
        folder="42_nutrition_metrics",
        call_name="run_nutrition_metrics",
        category="TeleBox",
        files=[
            "From GCP server path `Test_data/42_nutrition_metrics/`:",
            "- `nutrition_data.csv`",
        ],
        prompt=(
            "Run Nutrition Metrics on the uploaded CSV. "
            "age_col=age_group, sex_col=sex, weight_col=weight_kg, population_col=population."
        ),
        outputs=["Nutrition summary CSV", "Demographic breakdown chart"],
        notes=None,
    ),
]


# ---------------------------------------------------------------------------
# Template renderer
# ---------------------------------------------------------------------------

def render_guide(tool: dict) -> str:
    num = f"{tool['id']:02d}"
    name = tool["name"]
    call = tool["call_name"]
    cat = tool["category"]
    folder = tool["folder"]

    lines = [
        f"# Tool {num}: {name}",
        "",
        f"**Tool call name**: `{call}`  ",
        f"**Category**: {cat}  ",
        f"**GCP URL**: {GCP_URL}",
        "",
        "---",
        "",
    ]

    # Files section
    if tool["files"]:
        lines += [
            "## Files to Upload",
            "",
        ]
        lines += tool["files"]
        lines += [
            "",
            "*(Download these files via SCP from the GCP server, or use the GCP browser directly)*",
            "",
            "---",
            "",
        ]
    else:
        lines += [
            "## Files to Upload",
            "",
            "*(None — this test is skipped)*",
            "",
            "---",
            "",
        ]

    # Prompt section
    lines += [
        "## Prompt",
        "",
        "Copy and paste this into the chat box:",
        "",
        "```",
        tool["prompt"],
        "```",
        "",
        "---",
        "",
    ]

    # Expected result
    lines += [
        "## Expected Result",
        "",
        "- Blue card appears → LLM called the tool  ✓",
        "- Green card → computation complete  ✓",
    ]
    if tool["outputs"]:
        lines.append("- Output files:")
        for o in tool["outputs"]:
            lines.append(f"  - {o}")
    lines += ["", "---", ""]

    # Notes
    if tool["notes"]:
        lines += [
            "## Notes",
            "",
            tool["notes"],
            "",
        ]
    else:
        lines += [
            "## Notes",
            "",
            "No special notes.",
            "",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# README renderer
# ---------------------------------------------------------------------------

def render_readme(tools: list) -> str:
    invest_tools = [t for t in tools if t["category"] == "InVEST"]
    telebox_tools = [t for t in tools if t["category"] == "TeleBox"]

    lines = [
        "# Manual Client-to-GCP Test Suite",
        "",
        f"**GCP URL**: {GCP_URL}  ",
        f"**Test data on GCP**: `{TEST_DATA_GCP}`  ",
        f"**Patch data on GCP**: `{PATCH_DATA_GCP}`  ",
        f"**Shared data on GCP**: `{SHARED_DATA_GCP}`",
        "",
        "Each subfolder contains a `how_to_test.md` with step-by-step instructions for manually",
        "testing that tool via the browser chat interface.",
        "",
        "---",
        "",
        "## Test Directory",
        "",
        f"### InVEST Tools ({len(invest_tools)} tools)",
        "",
        "| # | Name | Folder | Skip? |",
        "|---|------|--------|-------|",
    ]
    for t in invest_tools:
        skip = "SKIP" if not t["files"] else ""
        lines.append(f"| {t['id']:02d} | {t['name']} | `{t['folder']}/` | {skip} |")

    lines += [
        "",
        f"### TeleBox Tools ({len(telebox_tools)} tools)",
        "",
        "| # | Name | Folder |",
        "|---|------|--------|",
    ]
    for t in telebox_tools:
        lines.append(f"| {t['id']:02d} | {t['name']} | `{t['folder']}/` |")

    lines += [
        "",
        "---",
        "",
        "## How to Run a Test",
        "",
        "1. Open the relevant `<folder>/how_to_test.md`.",
        "2. SCP (or browser-download) the listed files from the GCP server.",
        "3. Open the GCP URL in your browser.",
        "4. Upload the files using the drag-and-drop or file picker.",
        "5. Paste the prompt exactly as written.",
        "6. Observe the result cards and compare to Expected Result.",
        "",
        "---",
        "",
        "## Patch Files",
        "",
        "Several tools require **patched** CSV files that were generated by a previous AI run",
        f"and live at `{PATCH_DATA_GCP}`.  ",
        "These are listed explicitly in each tool's `how_to_test.md` under Files to Upload.",
        "",
        "---",
        "",
        "## Server-Side Large Files",
        "",
        "Tools 23 (Wave Energy) and 25 (Offshore Wind Energy) use large datasets",
        "pre-installed on the GCP server. Pass their server-side absolute paths in the prompt",
        "instead of uploading them from your local machine.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    created_dirs = []
    created_files = []

    for tool in TOOLS:
        tool_dir = BASE_DIR / tool["folder"]
        tool_dir.mkdir(parents=True, exist_ok=True)
        created_dirs.append(str(tool_dir))

        guide_path = tool_dir / "how_to_test.md"
        content = render_guide(tool)
        guide_path.write_text(content, encoding="utf-8")
        created_files.append(str(guide_path))

    # Top-level README
    readme_path = BASE_DIR / "README.md"
    readme_content = render_readme(TOOLS)
    readme_path.write_text(readme_content, encoding="utf-8")
    created_files.append(str(readme_path))

    print(f"Created {len(created_dirs)} tool directories.")
    print(f"Created {len(created_files)} files (including README.md).")
    print("\nDirectories:")
    for d in created_dirs:
        print(f"  {d}")
    print(f"\nREADME: {readme_path}")


if __name__ == "__main__":
    main()
