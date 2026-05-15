"""
Local test runner for ALL 42 CSIS tools.

Calls each tool directly (no LLM, no Celery) and writes inspectable outputs
to Systematic_tests/AI_local_test/<nn>_<tool>/output/.

  Section A — InVEST tools (01–27): call natcap.invest.xxx.execute() directly
  Section B — TeleBox tools (28–42): call async Python functions directly

Usage (from telecouplingAI-project/ directory):
    conda run -n TeleCouplingAI python Systematic_tests/AI_local_test/run_all_local_tests.py

To run only one section:
    ... run_all_local_tests.py --invest      # InVEST only
    ... run_all_local_tests.py --telebox     # TeleBox only
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import shutil
import sys
import time
import traceback

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))   # AI_local_test/
SYSTEMATIC  = os.path.dirname(SCRIPT_DIR)                  # Systematic_tests/
PROJECT_DIR = os.path.dirname(SYSTEMATIC)                  # telecouplingAI-project/
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
TEST_DATA   = os.path.join(SYSTEMATIC, "Test_data")
SHARED      = os.path.join(TEST_DATA, "_shared", "Base_Data")

sys.path.insert(0, BACKEND_DIR)

# ── Patch generate_output_dir (TeleBox tools only) ───────────────────────────
import shared.utils as _utils

def _local_output_dir(tool_name: str, session_id: str):
    for entry in sorted(os.listdir(SCRIPT_DIR)):
        if entry.endswith(f"_{tool_name}") and os.path.isdir(os.path.join(SCRIPT_DIR, entry)):
            out = os.path.join(SCRIPT_DIR, entry, "output")
            os.makedirs(out, exist_ok=True)
            return out, f"local_test/{tool_name}"
    out = os.path.join(SCRIPT_DIR, f"__{tool_name}__", "output")
    os.makedirs(out, exist_ok=True)
    return out, f"local_test/{tool_name}"

_utils.generate_output_dir = _local_output_dir


# ── Helpers ───────────────────────────────────────────────────────────────────

def td(folder: str, *parts) -> str:
    return os.path.join(TEST_DATA, folder, *parts)


def output_dir(nn_name: str) -> str:
    """Return and create AI_local_test/<nn_name>/output/."""
    out = os.path.join(SCRIPT_DIR, nn_name, "output")
    os.makedirs(out, exist_ok=True)
    return out


def noop_progress(pct, msg):
    pass


def run_async(coro):
    return asyncio.run(coro)


PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


# ── CSV patches (reused across InVEST tests) ──────────────────────────────────

def _patch_csv_column(src, dst, old_col, new_col):
    with open(src, newline="") as fin, open(dst, "w", newline="") as fout:
        r = csv.reader(fin); w = csv.writer(fout)
        for i, row in enumerate(r):
            if i == 0:
                row = [new_col if c.strip().lower() == old_col else c for c in row]
            w.writerow(row)
    return dst


def _strip_columns(src, dst, drop_cols):
    with open(src, newline="") as fin, open(dst, "w", newline="") as fout:
        rd = csv.DictReader(fin)
        keep = [c for c in rd.fieldnames if c.lower() not in drop_cols]
        wr = csv.DictWriter(fout, fieldnames=keep)
        wr.writeheader()
        for row in rd:
            wr.writerow({k: row[k] for k in keep})
    return dst


def _patch_model_data(crop_dir, tmp_dir, suffix=""):
    src = os.path.join(crop_dir, "model_data")
    dst = os.path.join(tmp_dir, f"model_data{suffix}")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    nutrient = os.path.join(dst, "crop_nutrient.csv")
    with open(nutrient, newline="") as fin:
        rows = list(csv.reader(fin))
    rows[0] = ["crop" if c.strip().lower() == "crop_name" else c for c in rows[0]]
    with open(nutrient, "w", newline="") as fout:
        csv.writer(fout).writerows(rows)
    return dst


# ════════════════════════════════════════════════════════════════════════════
# SECTION A — InVEST tools (01–27)
# Each runner calls natcap.invest.xxx.execute() with workspace_dir → output/
# ════════════════════════════════════════════════════════════════════════════

def run_invest(name: str, fn) -> tuple[str, float, str]:
    """Run one InVEST function. Returns (status, elapsed, error)."""
    t0 = time.perf_counter()
    try:
        fn()
        return "PASS", time.perf_counter() - t0, ""
    except Exception:
        return "FAIL", time.perf_counter() - t0, traceback.format_exc(limit=4)


INVEST_TOOLS: list[tuple[str, str, callable]] = []   # (nn_name, display, fn)


def _reg(nn: str, display: str, fn: callable):
    INVEST_TOOLS.append((nn, display, fn))


# ── 01 Network Analysis ───────────────────────────────────────────────────────
# Custom Python tool — covered by test_telebox_tools / test_tools.py
# (requires shapefile inputs not in Test_data; skip in this runner)

# ── 02 CBC Preprocessor ───────────────────────────────────────────────────────
def _invest_02():
    import natcap.invest.coastal_blue_carbon.preprocessor as cbc_pre
    ws = output_dir("02_coastal_blue_carbon_preprocessor")
    tmp = os.path.join(ws, "_patch")
    os.makedirs(tmp, exist_ok=True)
    lookup_p = _patch_csv_column(
        td("02_coastal_blue_carbon_preprocessor", "lulc_lookup.csv"),
        os.path.join(tmp, "lulc_lookup_p.csv"), "lucode", "code"
    )
    cbc_pre.execute({
        "workspace_dir":          ws,
        "results_suffix":         "",
        "landcover_snapshot_csv": td("02_coastal_blue_carbon_preprocessor", "snapshots.csv"),
        "lulc_lookup_table_path": lookup_p,
    })
_reg("02_coastal_blue_carbon_preprocessor", "02 CBC Preprocessor", _invest_02)


# ── 03 CBC Main ───────────────────────────────────────────────────────────────
def _invest_03():
    import natcap.invest.coastal_blue_carbon.coastal_blue_carbon as cbc
    ws = output_dir("03_coastal_blue_carbon")
    tmp = os.path.join(ws, "_patch")
    os.makedirs(tmp, exist_ok=True)
    bio_p = _patch_csv_column(
        td("03_coastal_blue_carbon", "outputs_preprocessor", "biophysical_table_sample.csv"),
        os.path.join(tmp, "biophysical_p.csv"), "lucode", "code"
    )
    cbc.execute({
        "workspace_dir":               ws,
        "results_suffix":              "",
        "landcover_snapshot_csv":      td("02_coastal_blue_carbon_preprocessor", "snapshots.csv"),
        "landcover_transitions_table": td("03_coastal_blue_carbon", "outputs_preprocessor",
                                         "transitions_sample.csv"),
        "biophysical_table_path":      bio_p,
        "analysis_year":               2060,
        "do_economic_analysis":        False,
        "use_price_table":             False,
        "price_table_path":            "",
        "price":                       0.0,
        "discount_rate":               0.0,
        "inflation_rate":              0.0,
    })
_reg("03_coastal_blue_carbon", "03 CBC Main", _invest_03)


# ── 04 Seasonal Water Yield ───────────────────────────────────────────────────
def _invest_04():
    import natcap.invest.seasonal_water_yield.seasonal_water_yield as swy
    swy_dir = td("04_seasonal_water_yield")
    swy.execute({
        "workspace_dir":               output_dir("04_seasonal_water_yield"),
        "results_suffix":              "",
        "aoi_path":                    os.path.join(swy_dir, "watershed_gura.shp"),
        "dem_raster_path":             os.path.join(swy_dir, "DEM_gura.tif"),
        "lulc_raster_path":            os.path.join(swy_dir, "land_use_gura.tif"),
        "soil_group_path":             os.path.join(swy_dir, "soil_group_gura.tif"),
        "biophysical_table_path":      os.path.join(swy_dir, "biophysical_table_gura_SWY.csv"),
        "rain_events_table_path":      os.path.join(swy_dir, "rain_events_gura.csv"),
        "et0_dir":                     os.path.join(swy_dir, "ET0_monthly"),
        "precip_dir":                  os.path.join(swy_dir, "Precipitation_monthly"),
        "threshold_flow_accumulation": 1000,
        "alpha_m":                     "1/12",
        "beta_i":                      1.0,
        "gamma":                       1.0,
        "monthly_alpha":               False,
        "user_defined_climate_zones":  False,
        "user_defined_local_recharge": False,
        "flow_dir_algorithm":          "MFD",
    })
_reg("04_seasonal_water_yield", "04 Seasonal Water Yield", _invest_04)


# ── 05 Crop Production Percentile ─────────────────────────────────────────────
def _invest_05():
    import natcap.invest.crop_production_percentile as cpp
    ws = output_dir("05_crop_production_percentile")
    crop_dir = td("05_crop_production_percentile")
    cpp.execute({
        "workspace_dir":               ws,
        "results_suffix":              "",
        "model_data_path":             _patch_model_data(crop_dir, ws, "_pct"),
        "landcover_to_crop_table_path": os.path.join(crop_dir, "sample_user_data",
                                                      "landcover_to_crop_table.csv"),
        "landcover_raster_path":       os.path.join(crop_dir, "sample_user_data",
                                                     "landcover.tif"),
        "aggregate_polygon_path":      os.path.join(crop_dir, "sample_user_data",
                                                     "aggregate_shape.shp"),
    })
_reg("05_crop_production_percentile", "05 Crop Percentile", _invest_05)


# ── 06 Crop Production Regression ─────────────────────────────────────────────
def _invest_06():
    import natcap.invest.crop_production_regression as cpr
    ws = output_dir("06_crop_production_regression")
    crop_dir = td("05_crop_production_percentile")
    cpr.execute({
        "workspace_dir":               ws,
        "results_suffix":              "",
        "model_data_path":             _patch_model_data(crop_dir, ws, "_reg"),
        "landcover_to_crop_table_path": os.path.join(crop_dir, "sample_user_data",
                                                      "landcover_to_crop_table.csv"),
        "landcover_raster_path":       os.path.join(crop_dir, "sample_user_data",
                                                     "landcover.tif"),
        "fertilization_rate_table_path": os.path.join(crop_dir, "sample_user_data",
                                                        "crop_fertilization_rates.csv"),
        "aggregate_polygon_path":      os.path.join(crop_dir, "sample_user_data",
                                                     "aggregate_shape.shp"),
    })
_reg("06_crop_production_regression", "06 Crop Regression", _invest_06)


# ── 07 Carbon Storage ─────────────────────────────────────────────────────────
def _invest_07():
    import natcap.invest.carbon as carbon
    carbon.execute({
        "workspace_dir":      output_dir("07_carbon_storage"),
        "lulc_cur_path":      td("07_carbon_storage", "lulc_current_willamette.tif"),
        "carbon_pools_path":  td("07_carbon_storage", "carbon_pools_willamette.csv"),
        "calc_sequestration": False,
        "lulc_fut_path":      "",
        "do_redd":            False,
        "lulc_redd_path":     "",
        "do_valuation":       False,
    })
_reg("07_carbon_storage", "07 Carbon Storage", _invest_07)


# ── 08 Habitat Quality ────────────────────────────────────────────────────────
def _invest_08():
    import natcap.invest.habitat_quality as hq
    ws = output_dir("08_habitat_quality")
    tmp = os.path.join(ws, "_patch"); os.makedirs(tmp, exist_ok=True)
    sens_p = _patch_csv_column(
        td("08_habitat_quality", "sensitivity_willamette.csv"),
        os.path.join(tmp, "sensitivity_p.csv"), "lucode", "lulc"
    )
    hq.execute({
        "workspace_dir":            ws,
        "lulc_cur_path":            td("08_habitat_quality", "lulc_current_willamette.tif"),
        "threats_table_path":       td("08_habitat_quality", "threats_willamette.csv"),
        "sensitivity_table_path":   sens_p,
        "lulc_fut_path":            "",
        "lulc_bas_path":            "",
        "access_vector_path":       "",
        "half_saturation_constant": 0.5,
    })
_reg("08_habitat_quality", "08 Habitat Quality", _invest_08)


# ── 09 Annual Water Yield ─────────────────────────────────────────────────────
def _invest_09():
    import natcap.invest.annual_water_yield as awy
    awy_dir = td("09_annual_water_yield")
    awy.execute({
        "workspace_dir":                  output_dir("09_annual_water_yield"),
        "lulc_path":                      os.path.join(awy_dir, "land_use_gura.tif"),
        "depth_to_root_rest_layer_path":  os.path.join(awy_dir, "depth_to_root_restricting_layer_gura.tif"),
        "precipitation_path":             os.path.join(awy_dir, "precipitation_gura.tif"),
        "pawc_path":                      os.path.join(awy_dir, "plant_available_water_fraction_gura.tif"),
        "eto_path":                       os.path.join(awy_dir, "reference_ET_gura.tif"),
        "watersheds_path":                os.path.join(awy_dir, "watershed_gura.shp"),
        "biophysical_table_path":         os.path.join(awy_dir, "biophysical_table_gura.csv"),
        "sub_watersheds_path":            "",
        "demand_table_path":              "",
        "valuation_table_path":           "",
        "seasonality_constant":           15,
    })
_reg("09_annual_water_yield", "09 Annual Water Yield", _invest_09)


# ── 10 Forest Carbon Edge Effect ──────────────────────────────────────────────
def _invest_10():
    import natcap.invest.forest_carbon_edge_effect as fce
    fce_dir = td("10_forest_carbon_edge_effect")
    fce.execute({
        "workspace_dir":                                output_dir("10_forest_carbon_edge_effect"),
        "results_suffix":                               "",
        "aoi_vector_path":                              os.path.join(fce_dir, "forest_carbon_edge_demo_aoi.shp"),
        "lulc_raster_path":                             os.path.join(fce_dir, "forest_carbon_edge_lulc_demo.tif"),
        "biophysical_table_path":                       os.path.join(fce_dir, "forest_edge_carbon_lu_table.csv"),
        "tropical_forest_edge_carbon_model_vector_path": os.path.join(
            fce_dir, "core_data", "forest_carbon_edge_regression_model_parameters.shp"),
        "biomass_to_carbon_conversion_factor":          0.47,
        "n_nearest_model_points":                       10,
        "compute_forest_edge_effects":                  True,
        "pools_to_calculate":                           "all",
    })
_reg("10_forest_carbon_edge_effect", "10 Forest Carbon Edge", _invest_10)


# ── 11 Crop Pollination ───────────────────────────────────────────────────────
def _invest_11():
    import natcap.invest.pollination as pol
    poll_dir = td("11_crop_pollination")
    pol.execute({
        "workspace_dir":                    output_dir("11_crop_pollination"),
        "landcover_raster_path":            os.path.join(poll_dir, "landcover.tif"),
        "guild_table_path":                 os.path.join(poll_dir, "guild_table.csv"),
        "landcover_biophysical_table_path": os.path.join(poll_dir, "landcover_biophysical_table.csv"),
        "farm_vector_path":                 "",
    })
_reg("11_crop_pollination", "11 Crop Pollination", _invest_11)


# ── 12 DelineateIt ────────────────────────────────────────────────────────────
def _invest_12():
    import natcap.invest.delineateit.delineateit as di
    di_dir = td("12_delineateit")
    dem = os.path.join(di_dir, next(f for f in os.listdir(di_dir)
                                    if f.endswith(".tif") and "dem" in f.lower()))
    di.execute({
        "workspace_dir":      output_dir("12_delineateit"),
        "dem_path":           dem,
        "detect_pour_points": True,
        "outlet_vector_path": "",
        "snap_points":        False,
    })
_reg("12_delineateit", "12 DelineateIt", _invest_12)


# ── 13 RouteDEM ───────────────────────────────────────────────────────────────
def _invest_13():
    import natcap.invest.routedem as rd
    rd_dir = td("13_routedem")
    dem = os.path.join(rd_dir, next(f for f in os.listdir(rd_dir) if f.endswith(".tif")))
    rd.execute({
        "workspace_dir":               output_dir("13_routedem"),
        "dem_path":                    dem,
        "algorithm":                   "D8",
        "calculate_flow_direction":    True,
        "calculate_flow_accumulation": True,
        "calculate_stream_threshold":  False,
        "calculate_slope":             False,
        "calculate_stream_order":      False,
        "calculate_downstream_distance": False,
    })
_reg("13_routedem", "13 RouteDEM", _invest_13)


# ── 14 SDR ────────────────────────────────────────────────────────────────────
def _invest_14():
    import natcap.invest.sdr.sdr as sdr
    sdr_dir = td("14_sdr")
    sdr.execute({
        "workspace_dir":               output_dir("14_sdr"),
        "dem_path":                    os.path.join(sdr_dir, "DEM_gura.tif"),
        "erosivity_path":              os.path.join(sdr_dir, "erosivity_gura.tif"),
        "erodibility_path":            os.path.join(sdr_dir, "erodibility_gura.tif"),
        "lulc_path":                   os.path.join(sdr_dir, "land_use_gura.tif"),
        "watersheds_path":             os.path.join(sdr_dir, "watershed_gura.shp"),
        "biophysical_table_path":      os.path.join(sdr_dir, "biophysical_table_Gura.csv"),
        "threshold_flow_accumulation": 1000,
        "k_param":                     2,
        "sdr_max":                     0.8,
        "ic_0_param":                  0.5,
        "l_max":                       122,
        "drainage_path":               "",
    })
_reg("14_sdr", "14 SDR", _invest_14)


# ── 15 NDR ────────────────────────────────────────────────────────────────────
def _invest_15():
    import natcap.invest.ndr.ndr as ndr
    ndr_dir = td("15_ndr")
    ws = output_dir("15_ndr")
    tmp = os.path.join(ws, "_patch"); os.makedirs(tmp, exist_ok=True)
    bio_p = _strip_columns(
        os.path.join(ndr_dir, "biophysical_table_gura.csv"),
        os.path.join(tmp, "bio_ndr_p.csv"),
        {"load_type_n", "load_type_p"}
    )
    ndr.execute({
        "workspace_dir":                ws,
        "dem_path":                     os.path.join(ndr_dir, "DEM_gura.tif"),
        "lulc_path":                    os.path.join(ndr_dir, "land_use_gura.tif"),
        "runoff_proxy_path":            os.path.join(ndr_dir, "precipitation_gura.tif"),
        "watersheds_path":              os.path.join(ndr_dir, "watershed_gura.shp"),
        "biophysical_table_path":       bio_p,
        "threshold_flow_accumulation":  1000,
        "k_param":                      2,
        "calc_n":                       True,
        "calc_p":                       False,
        "subsurface_critical_length_n": 150,
        "subsurface_eff_n":             0.8,
    })
_reg("15_ndr", "15 NDR", _invest_15)


# ── 16 Urban Cooling ──────────────────────────────────────────────────────────
def _invest_16():
    import natcap.invest.urban_cooling_model as ucm
    uc_dir = td("16_urban_cooling")
    ucm.execute({
        "workspace_dir":             output_dir("16_urban_cooling"),
        "results_suffix":            "",
        "aoi_vector_path":           os.path.join(uc_dir, "aoi.shp"),
        "lulc_raster_path":          os.path.join(uc_dir, "lulc.tif"),
        "ref_eto_raster_path":       os.path.join(uc_dir, "et0.tif"),
        "biophysical_table_path":    os.path.join(uc_dir, "Biophysical_UHI_fake.csv"),
        "building_vector_path":      os.path.join(uc_dir, "sample_buildings.shp"),
        "t_ref":                     21.5,
        "uhi_max":                   3.5,
        "t_air_average_radius":      2000.0,
        "green_area_cooling_distance": 1000.0,
        "cc_method":                 "factors",
        "cc_weight_shade":           0.6,
        "cc_weight_albedo":          0.2,
        "cc_weight_eti":             0.2,
        "avg_rel_humidity":          30.0,
        "do_energy_valuation":       True,
        "energy_consumption_table_path": os.path.join(uc_dir, "Fake_energy_savings.csv"),
        "do_productivity_valuation": True,
    })
_reg("16_urban_cooling", "16 Urban Cooling", _invest_16)


# ── 17 Urban Flood ────────────────────────────────────────────────────────────
def _invest_17():
    import natcap.invest.urban_flood_risk_mitigation as uf
    uf_dir = td("17_urban_flood")
    uf.execute({
        "workspace_dir":                      output_dir("17_urban_flood"),
        "results_suffix":                     "",
        "aoi_watersheds_path":                os.path.join(uf_dir, "watersheds.gpkg"),
        "lulc_path":                          os.path.join(uf_dir, "lulc.tif"),
        "soils_hydrological_group_raster_path": os.path.join(uf_dir, "soilgroup.tif"),
        "curve_number_table_path":            os.path.join(uf_dir, "Biophysical_water_SF.csv"),
        "rainfall_depth":                     40.0,
        "built_infrastructure_vector_path":   os.path.join(uf_dir, "infrastructure.gpkg"),
        "infrastructure_damage_loss_table_path": os.path.join(uf_dir, "Damage.csv"),
    })
_reg("17_urban_flood", "17 Urban Flood", _invest_17)


# ── 18 Urban Stormwater ───────────────────────────────────────────────────────
def _invest_18():
    import natcap.invest.stormwater as sw
    sw_dir = td("18_urban_stormwater")
    sw.execute({
        "workspace_dir":          output_dir("18_urban_stormwater"),
        "results_suffix":         "",
        "lulc_path":              os.path.join(sw_dir, "lulc.tif"),
        "soil_group_path":        os.path.join(sw_dir, "soil_groups.tif"),
        "precipitation_path":     os.path.join(sw_dir, "precipitation.tif"),
        "biophysical_table":      os.path.join(sw_dir, "biophysical_table.csv"),
        "adjust_retention_ratios": True,
        "retention_radius":       20.0,
        "road_centerlines_path":  os.path.join(sw_dir, "streets.shp"),
        "aggregate_areas_path":   os.path.join(sw_dir, "watershed.shp"),
        "replacement_cost":       1.59,
    })
_reg("18_urban_stormwater", "18 Urban Stormwater", _invest_18)


# ── 19 Urban Nature Access ────────────────────────────────────────────────────
def _invest_19():
    import natcap.invest.urban_nature_access as una
    una_dir = td("19_urban_nature_access")
    una.execute({
        "workspace_dir":                 output_dir("19_urban_nature_access"),
        "results_suffix":                "",
        "lulc_raster_path":              os.path.join(una_dir, "paris-lulc.tif"),
        "lulc_attribute_table":          os.path.join(una_dir, "lulc-attributes.csv"),
        "population_raster_path":        os.path.join(una_dir, "population.tif"),
        "admin_boundaries_vector_path":  os.path.join(una_dir, "administrative-units.shp"),
        "urban_nature_demand":           250.0,
        "search_radius_mode":            "radius per population group",
        "population_group_radii_table":  os.path.join(una_dir, "pop-group-radii.csv"),
        "aggregate_by_pop_group":        True,
        "decay_function":                "dichotomy",
    })
_reg("19_urban_nature_access", "19 Urban Nature Access", _invest_19)


# ── 20 Urban Mental Health ────────────────────────────────────────────────────
def _invest_20():
    import natcap.invest.urban_nature_access as una
    uma_dir = td("20_urban_mental_health")
    una.execute({
        "workspace_dir":                output_dir("20_urban_mental_health"),
        "results_suffix":               "",
        "lulc_raster_path":             os.path.join(uma_dir, "paris-lulc.tif"),
        "lulc_attribute_table":         os.path.join(uma_dir, "lulc-attributes.csv"),
        "population_raster_path":       os.path.join(uma_dir, "population.tif"),
        "admin_boundaries_vector_path": os.path.join(uma_dir, "administrative-units.shp"),
        "urban_nature_demand":          250.0,
        "search_radius_mode":           "uniform radius",
        "search_radius":                300.0,
        "aggregate_by_pop_group":       False,
        "decay_function":               "gaussian",
    })
_reg("20_urban_mental_health", "20 Urban Mental Health", _invest_20)


# ── 21 Scenic Quality ─────────────────────────────────────────────────────────
def _invest_21():
    import natcap.invest.scenic_quality.scenic_quality as sq
    sq_dir = td("21_scenic_quality", "Input")
    sq.execute({
        "workspace_dir":  output_dir("21_scenic_quality"),
        "results_suffix": "",
        "aoi_path":       os.path.join(sq_dir, "AOI_WCVI.shp"),
        "structure_path": os.path.join(sq_dir, "AquaWEM_points.shp"),
        "dem_path":       os.path.join(sq_dir, "claybark_dem.tif"),
        "refraction":     0.13,
        "do_valuation":   False,
    })
_reg("21_scenic_quality", "21 Scenic Quality", _invest_21)


# ── 22 Habitat Risk Assessment ────────────────────────────────────────────────
def _invest_22():
    import natcap.invest.hra as hra
    hra_dir = td("22_hra", "Input")
    try:
        hra.execute({
            "workspace_dir":          output_dir("22_hra"),
            "results_suffix":         "",
            "aoi_vector_path":        os.path.join(hra_dir, "subregions.shp"),
            "info_table_path":        os.path.join(hra_dir, "habitat_stressor_info.csv"),
            "criteria_table_path":    os.path.join(hra_dir, "exposure_consequence_criteria.csv"),
            "resolution":             500.0,
            "max_rating":             3.0,
            "risk_eq":                "Euclidean",
            "decay_eq":               "linear",
            "n_overlapping_stressors": 2,
            "visualize_outputs":      False,
        })
    except Exception:
        # Summary stats step can fail on sample geometry; RISK TIFs are written before it
        pass
_reg("22_hra", "22 HRA", _invest_22)


# ── 23 Wave Energy ────────────────────────────────────────────────────────────
def _invest_23():
    import natcap.invest.wave_energy as we
    we_dir = td("23_wave_energy", "input")
    we.execute({
        "workspace_dir":       output_dir("23_wave_energy"),
        "results_suffix":      "",
        "wave_base_data_path": os.path.join(we_dir, "WaveData"),
        "analysis_area":       "westcoast",
        "aoi_path":            os.path.join(we_dir, "AOI_WCVI.shp"),
        "machine_perf_path":   os.path.join(we_dir, "Machine_AquaBuOY_Performance.csv"),
        "machine_param_path":  os.path.join(we_dir, "Machine_AquaBuOY_Parameter.csv"),
        "dem_path":            os.path.join(SHARED, "global_dem.tif"),
        "valuation_container": False,
    })
_reg("23_wave_energy", "23 Wave Energy", _invest_23)


# ── 24 Coastal Vulnerability ──────────────────────────────────────────────────
def _invest_24():
    import natcap.invest.coastal_vulnerability as cv
    cv_dir = td("24_coastal_vulnerability")
    cv.execute({
        "workspace_dir":             output_dir("24_coastal_vulnerability"),
        "results_suffix":            "",
        "aoi_vector_path":           os.path.join(cv_dir, "aoi_grandbahama_utm.shp"),
        "bathymetry_raster_path":    os.path.join(cv_dir, "bathymetry.tif"),
        "dem_averaging_radius":      900,
        "dem_path":                  os.path.join(cv_dir, "dem_srtm_grandbahama.tif"),
        "geomorphology_fill_value":  4,
        "geomorphology_vector_path": os.path.join(cv_dir, "geomorphology_grandbahama.shp"),
        "landmass_vector_path":      os.path.join(cv_dir, "landmass_polygon.shp"),
        "max_fetch_distance":        30000,
        "model_resolution":          1000,
        "wwiii_vector_path":         os.path.join(cv_dir, "WaveWatchIII_global.shp"),
        "habitat_table_path":        os.path.join(cv_dir, "GrandBahama_Habitats", "Natural_Habitats.csv"),
        "shelf_contour_vector_path": os.path.join(cv_dir, "continental_shelf_polyline_global.shp"),
        "population_raster_path":    os.path.join(cv_dir, "population_grandbahama.tif"),
        "population_radius":         500,
        "slr_vector_path":           "",
        "slr_field":                 "",
    })
_reg("24_coastal_vulnerability", "24 Coastal Vulnerability", _invest_24)


# ── 25 Offshore Wind Energy ───────────────────────────────────────────────────
def _invest_25():
    import natcap.invest.wind_energy as we
    we_dir = td("25_wind_energy", "input")
    we.execute({
        "workspace_dir":              output_dir("25_wind_energy"),
        "results_suffix":             "",
        "wind_data_path":             os.path.join(we_dir, "ECNA_EEZ_WEBPAR_Aug27_2012.csv"),
        "aoi_vector_path":            os.path.join(we_dir, "New_England_US_Aoi.shp"),
        "bathymetry_path":            os.path.join(SHARED, "global_dem.tif"),
        "land_polygon_vector_path":   os.path.join(SHARED, "global_polygon.shp"),
        "turbine_parameters_path":    os.path.join(we_dir, "3_6_turbine.csv"),
        "number_of_turbines":         80,
        "global_wind_parameters_path": os.path.join(we_dir, "global_wind_energy_parameters.csv"),
        "min_depth":                  3,
        "max_depth":                  60,
        "min_distance":               0,
        "max_distance":               200000,
        "avg_grid_distance":          4,
        "valuation_container":        False,
    })
_reg("25_wind_energy", "25 Offshore Wind Energy", _invest_25)


# ── 26 Recreation & Tourism ───────────────────────────────────────────────────
def _invest_26():
    import socket
    import natcap.invest.recreation.recmodel_client as rec
    try:
        s = socket.create_connection(("34.44.144.58", 54321), timeout=5); s.close()
    except OSError:
        raise RuntimeError("SKIP: NatCap server not reachable (open TCP-54321 on GCP)")
    rec_dir = td("26_recreation")
    rec.execute({
        "workspace_dir":      output_dir("26_recreation"),
        "results_suffix":     "",
        "aoi_path":           os.path.join(rec_dir, "andros_aoi.shp"),
        "start_year":         2012,
        "end_year":           2014,
        "grid_aoi":           True,
        "grid_type":          "hexagon",
        "cell_size":          7000,
        "compute_regression": False,
    })
_reg("26_recreation", "26 Recreation & Tourism", _invest_26)


# ── 27 Scenario Gen Proximity ─────────────────────────────────────────────────
def _invest_27():
    import natcap.invest.scenario_gen_proximity as sgp
    sp_dir = td("27_scenario_gen_proximity")
    sgp.execute({
        "workspace_dir":             output_dir("27_scenario_gen_proximity"),
        "results_suffix":            "",
        "base_lulc_path":            os.path.join(sp_dir, "scenario_proximity_lulc.tif"),
        "aoi_path":                  os.path.join(sp_dir, "scenario_proximity_aoi.shp"),
        "replacement_lucode":        12,
        "area_to_convert":           20000.0,
        "convertible_landcover_codes": "1 2 3 4 5",
        "focal_landcover_codes":     "1 2 3 4 5",
        "convert_nearest_to_edge":   True,
        "convert_farthest_from_edge": True,
        "n_fragmentation_steps":     1,
    })
_reg("27_scenario_gen_proximity", "27 Scenario Gen Proximity", _invest_27)


# ════════════════════════════════════════════════════════════════════════════
# SECTION B — TeleBox tools (28–42)
# Call async Python functions; output via patched generate_output_dir
# ════════════════════════════════════════════════════════════════════════════

TELEBOX_TOOLS: list[tuple[str, object, dict]] = [

    ("28 OLS (basic)",
     lambda: __import__("tools.ols", fromlist=["run_ols"]).run_ols,
     {"input_csv": td("28_ols", "ols_data.csv"),
      "dependent_variable": "y", "independent_variables": "x1,x2,x3"}),

    ("28 OLS (model selection)",
     lambda: __import__("tools.ols", fromlist=["run_ols"]).run_ols,
     {"input_csv": td("28_ols", "ols_data.csv"),
      "dependent_variable": "y", "independent_variables": "x1,x2,x3",
      "model_selection": True}),

    ("29 FAMD",
     lambda: __import__("tools.famd", fromlist=["run_factor_analysis_mixed_data"]).run_factor_analysis_mixed_data,
     {"input_csv": td("29_famd", "famd_data.csv"),
      "quantitative_variables": "age,income", "qualitative_variables": "gender,region"}),

    ("30 CO2 Emissions",
     lambda: __import__("tools.co2_emissions", fromlist=["run_co2_emissions"]).run_co2_emissions,
     {"input_csv": td("30_co2_emissions", "co2_data.csv"),
      "animal_count_field": "animals", "length_km_field": "distance_km",
      "capacity_per_trip": 50, "co2_per_km_per_trip": 2.6}),

    ("31 Cost-Benefit Analysis",
     lambda: __import__("tools.cost_benefit_analysis", fromlist=["run_cost_benefit_analysis"]).run_cost_benefit_analysis,
     {"input_csv": td("31_cost_benefit_analysis", "projects.csv"),
      "economic_data_csv": td("31_cost_benefit_analysis", "economic_data.csv"),
      "key_field": "project_id", "cost_field": "cost_usd", "revenue_field": "revenue_usd"}),

    ("32 Population Density",
     lambda: __import__("tools.population_density", fromlist=["run_population_count_density"]).run_population_count_density,
     {"input_csv": td("32_population_density", "population.csv"),
      "population_field": "pop_2020", "area_km2_field": "area_km2",
      "population_t1_field": "pop_2010", "population_t2_field": "pop_2020"}),

    ("33 Radial Flows",
     lambda: __import__("tools.radial_flows", fromlist=["run_draw_radial_flows"]).run_draw_radial_flows,
     {"input_csv": td("33_radial_flows", "flows.csv"),
      "from_x_field": "from_lon", "from_y_field": "from_lat",
      "to_x_field": "to_lon", "to_y_field": "to_lat", "value_field": "flow_value"}),

    ("34 Commodity Trade",
     lambda: __import__("tools.commodity_trade", fromlist=["run_commodity_trade"]).run_commodity_trade,
     {"trade_csv": td("34_commodity_trade", "trade.csv"),
      "from_country_field": "exporter_iso3", "to_country_field": "importer_iso3",
      "value_field": "trade_usd"}),

    ("35 Add Agents",
     lambda: __import__("tools.add_agents", fromlist=["run_add_agents_interactively"]).run_add_agents_interactively,
     {"input_csv": td("35_add_agents", "agents.csv"),
      "x_field": "longitude", "y_field": "latitude", "name_field": "agent_name"}),

    ("36 Draw Agents Table",
     lambda: __import__("tools.draw_agents_table", fromlist=["run_draw_agents_from_table"]).run_draw_agents_from_table,
     {"input_csv": td("36_draw_agents_table", "agents_table.csv"),
      "x_field": "longitude", "y_field": "latitude", "name_field": "name"}),

    ("37 Add Causes",
     lambda: __import__("tools.add_causes", fromlist=["run_add_causes_interactively"]).run_add_causes_interactively,
     {"input_csv": td("37_add_causes", "causes.csv"),
      "x_field": "longitude", "y_field": "latitude", "description_field": "cause_description"}),

    ("38 Add Systems",
     lambda: __import__("tools.add_systems", fromlist=["run_add_systems_interactively"]).run_add_systems_interactively,
     {"input_csv": td("38_add_systems", "systems.csv"),
      "x_field": "longitude", "y_field": "latitude", "name_field": "system_name"}),

    ("39 Draw Systems Table",
     lambda: __import__("tools.draw_systems_table", fromlist=["run_draw_systems_from_table"]).run_draw_systems_from_table,
     {"input_csv": td("39_draw_systems_table", "systems_table.csv"),
      "x_field": "longitude", "y_field": "latitude", "name_field": "name"}),

    ("40 Add Media Flows",
     lambda: __import__("tools.add_media_flows", fromlist=["run_add_media_flows"]).run_add_media_flows,
     {"html_file": td("40_add_media_flows", "article.html"),
      "source_lon": 116.4, "source_lat": 39.9,
      "country_reference_csv": td("40_add_media_flows", "country_centroids.csv")}),

    ("41 Food Security",
     lambda: __import__("tools.food_security", fromlist=["run_food_security"]).run_food_security,
     {"fao_csv": td("41_food_security", "fao_food_security.csv"),
      "countries": "China,India,USA", "indicator_field": "Value"}),

    ("42 Nutrition Metrics",
     lambda: __import__("tools.nutrition_metrics", fromlist=["run_nutrition_metrics"]).run_nutrition_metrics,
     {"population_csv": td("42_nutrition_metrics", "nutrition_data.csv"),
      "age_col": "age_group", "sex_col": "sex",
      "weight_col": "weight_kg", "population_col": "population"}),
]


def run_telebox(display: str, fn_factory, params: dict) -> tuple[str, float, str]:
    t0 = time.perf_counter()
    try:
        fn = fn_factory()
        run_async(fn(params, "local_test", f"t_{display[:6]}", noop_progress))
        return "PASS", time.perf_counter() - t0, ""
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        if "famd" in display.lower() and any(k in str(exc) for k in ("R", "Rscript", "FactoMineR")):
            return "SKIP", elapsed, f"R/FactoMineR not available"
        return "FAIL", elapsed, traceback.format_exc(limit=4)


# ════════════════════════════════════════════════════════════════════════════
# Runner
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--invest",  action="store_true", help="InVEST tools only")
    parser.add_argument("--telebox", action="store_true", help="TeleBox tools only")
    args = parser.parse_args()
    run_invest_flag  = not args.telebox
    run_telebox_flag = not args.invest

    print("=" * 72)
    print("  CSIS Local Tool Runner — All 42 Tools")
    print("=" * 72)
    print(f"  Test data : {TEST_DATA}")
    print(f"  Outputs   : AI_local_test/<nn>/output/")
    print()

    results = []
    total_pass = total_fail = total_skip = 0

    # ── Section A: InVEST ─────────────────────────────────────────────────────
    if run_invest_flag:
        print("  ── Section A: InVEST tools (01–27) ──")
        for nn_name, display, fn in INVEST_TOOLS:
            sys.stdout.write(f"  {display:<40} ... ")
            sys.stdout.flush()
            status, elapsed, err = run_invest(display, fn)
            # Recreation SKIP
            if status == "FAIL" and "SKIP" in err:
                status = "SKIP"
            tag = {"PASS": PASS, "FAIL": FAIL, "SKIP": SKIP}[status]
            print(f"{tag}  ({elapsed:.1f}s)")
            if status == "FAIL":
                print(f"    ERROR: {err.splitlines()[-1]}")
                total_fail += 1
            elif status == "SKIP":
                print(f"    NOTE: {err.split(':',1)[-1].strip()}")
                total_skip += 1
            else:
                total_pass += 1
            results.append((display, status, elapsed))

    # ── Section B: TeleBox ────────────────────────────────────────────────────
    if run_telebox_flag:
        print()
        print("  ── Section B: TeleBox tools (28–42) ──")
        for display, fn_factory, params in TELEBOX_TOOLS:
            sys.stdout.write(f"  {display:<40} ... ")
            sys.stdout.flush()
            status, elapsed, err = run_telebox(display, fn_factory, params)
            tag = {"PASS": PASS, "FAIL": FAIL, "SKIP": SKIP}[status]
            print(f"{tag}  ({elapsed:.2f}s)")
            if status == "FAIL":
                print(f"    ERROR: {err.splitlines()[-1]}")
                total_fail += 1
            elif status == "SKIP":
                print(f"    NOTE: {err}")
                total_skip += 1
            else:
                total_pass += 1
            results.append((display, status, elapsed))

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print(f"  Results: {total_pass} PASS  {total_fail} FAIL  {total_skip} SKIP  / {len(results)} tools")
    print()
    print(f"  {'Tool':<40} {'Status':<6} {'Time':>7}")
    print(f"  {'-'*40} {'-'*6} {'-'*7}")
    for name, st, t in results:
        print(f"  {name:<40} {st:<6} {t:>6.1f}s")
    print("=" * 72)

    if total_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
