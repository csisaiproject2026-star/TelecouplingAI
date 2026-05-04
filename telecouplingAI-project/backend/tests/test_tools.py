"""
Tests for tool modules — unit tests that don't require InVEST/R execution.
Tests parameter validation, SUPPORTED_CROPS checking, and task_queue dispatch.
"""
import csv
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.utils import CSISError

MODEL_DATA = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CropProductionPercentile_input\model_data"


# --- Tool 1: Network Analysis validation ---

class TestNetworkAnalysis:
    def test_required_keys(self):
        from tools.network_analysis import REQUIRED_KEYS
        expected = ["nodes_table", "links_table", "shapefile_path",
                    "nodes_join_attri", "layer_join_attri", "clustering_algorithm"]
        assert REQUIRED_KEYS == expected

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.network_analysis import run_network_analysis
        with pytest.raises(CSISError) as exc_info:
            await run_network_analysis({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


# --- Tool 2: CBC Preprocessor validation ---

class TestCBCPreprocessor:
    def test_required_keys(self):
        from tools.cbc_preprocessor import REQUIRED_KEYS
        assert "landcover_snapshot_csv" in REQUIRED_KEYS
        assert "landcover_lookup_table" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.cbc_preprocessor import run_cbc_preprocessor
        with pytest.raises(CSISError) as exc_info:
            await run_cbc_preprocessor({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


# --- Tool 3: CBC Main validation ---

class TestCBCMain:
    def test_required_keys(self):
        from tools.cbc_main import REQUIRED_KEYS
        assert "landcover_snapshot_csv" in REQUIRED_KEYS
        assert "landcover_transitions_table" in REQUIRED_KEYS
        assert "biophysical_table_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.cbc_main import run_cbc_main
        with pytest.raises(CSISError) as exc_info:
            await run_cbc_main({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"

    @pytest.mark.asyncio
    async def test_missing_one_param_raises(self):
        """Missing any single required param should raise MISSING_PARAMS with param name."""
        from tools.cbc_main import run_cbc_main
        with pytest.raises(CSISError) as exc_info:
            await run_cbc_main(
                {
                    "landcover_snapshot_csv":      "dummy.csv",
                    "landcover_transitions_table": "dummy.csv",
                    # biophysical_table_path intentionally omitted
                },
                "sess", "tid", lambda p, m: None,
            )
        assert exc_info.value.error_code == "MISSING_PARAMS"
        assert "biophysical_table_path" in exc_info.value.message

    def test_optional_economic_params_not_required(self):
        """Optional economic params should not appear in REQUIRED_KEYS."""
        from tools.cbc_main import REQUIRED_KEYS
        assert "do_economic_analysis" not in REQUIRED_KEYS
        assert "price" not in REQUIRED_KEYS
        assert "discount_rate" not in REQUIRED_KEYS
        assert "inflation_rate" not in REQUIRED_KEYS


# --- Tool 4: Seasonal Water Yield validation ---

class TestSeasonalWaterYield:
    def test_required_keys(self):
        from tools.seasonal_water_yield import REQUIRED_KEYS
        assert "precip_dir" in REQUIRED_KEYS
        assert "et0_dir" in REQUIRED_KEYS
        assert "threshold_flow_accumulation" in REQUIRED_KEYS

    def test_prepare_monthly_dir_missing_month(self, tmp_path):
        from tools.seasonal_water_yield import prepare_monthly_dir
        with pytest.raises(CSISError) as exc_info:
            prepare_monthly_dir(str(tmp_path), "precip_m")
        assert exc_info.value.error_code == "FILE_NOT_FOUND"
        assert "month 1" in exc_info.value.message.lower() or "Month 1" in exc_info.value.message

    def test_prepare_monthly_dir_success(self, tmp_path):
        from tools.seasonal_water_yield import prepare_monthly_dir
        for m in range(1, 13):
            (tmp_path / f"precip_gura_{m}.tif").touch()
        result_dir = prepare_monthly_dir(str(tmp_path), "precip_m")
        try:
            for m in range(1, 13):
                assert os.path.exists(os.path.join(result_dir, f"precip_m{m}.tif"))
        finally:
            import shutil
            shutil.rmtree(result_dir, ignore_errors=True)


# --- Tool 5: Crop Percentile validation ---

class TestCropPercentile:
    def test_required_keys(self):
        # model_data_path is taken from MODEL_DATA_PATH env var (not user input)
        from tools.crop_percentile import REQUIRED_KEYS
        assert "landcover_raster_path" in REQUIRED_KEYS
        assert "landcover_to_crop_table_path" in REQUIRED_KEYS
        assert "model_data_path" not in REQUIRED_KEYS

    def test_get_supported_crops_from_model_data(self):
        """Dynamically loaded crops should include 172 crops from percentile tables."""
        from tools.crop_percentile import get_supported_crops
        supported = get_supported_crops(MODEL_DATA)
        assert "maize" in supported.values()
        assert "rice" in supported.values()
        assert "cassava" in supported.values()
        assert "oilpalm" in supported.values()
        assert "sugarbeet" in supported.values()
        assert len(supported) > 10

    def test_get_supported_crops_invalid_path(self, tmp_path):
        """Missing model_data_path should raise CSISError."""
        from tools.crop_percentile import get_supported_crops
        with pytest.raises(CSISError) as exc_info:
            get_supported_crops(str(tmp_path))
        assert exc_info.value.error_code == "INVALID_PARAMS"

    def test_normalize_variants(self):
        """Various spellings should normalize to the same key."""
        from tools.crop_percentile import _normalize
        assert _normalize("oil palm") == _normalize("oilpalm") == _normalize("Oil Palm")
        assert _normalize("sugar beet") == _normalize("sugarbeet") == _normalize("Sugar Beet")

    @pytest.mark.asyncio
    async def test_unsupported_crop_raises(self, tmp_path):
        """Crop not in model_data should raise INVALID_PARAMS."""
        from tools.crop_percentile import run_crop_percentile
        lulc_path = tmp_path / "lulc.csv"
        with open(lulc_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["crop_name", "lucode"])
            writer.writeheader()
            writer.writerow({"crop_name": "unicorncrop", "lucode": 1})
        params = {
            "landcover_raster_path":        "dummy.tif",
            "landcover_to_crop_table_path": str(lulc_path),
            "model_data_path":              MODEL_DATA,
        }
        with pytest.raises(CSISError) as exc_info:
            await run_crop_percentile(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"
        assert "unicorncrop" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_supported_crop_passes_validation(self, tmp_path):
        """cassava (percentile only) and oilpalm should both pass validation."""
        from tools.crop_percentile import run_crop_percentile
        lulc_path = tmp_path / "lulc.csv"
        with open(lulc_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["crop_name", "lucode"])
            writer.writeheader()
            writer.writerow({"crop_name": "cassava", "lucode": 1})
            writer.writerow({"crop_name": "oilpalm", "lucode": 2})
        params = {
            "landcover_raster_path":        "dummy.tif",
            "landcover_to_crop_table_path": str(lulc_path),
            "model_data_path":              MODEL_DATA,
        }
        with pytest.raises((CSISError, Exception)) as exc_info:
            await run_crop_percentile(params, "sess", "tid", lambda p, m: None)
        if hasattr(exc_info.value, "error_code"):
            assert exc_info.value.error_code != "INVALID_PARAMS"


# --- Tool 6: Crop Regression ---

class TestCropRegression:

    def test_get_supported_crops_from_model_data(self):
        """Dynamically loaded crops should include all 10 expected crops."""
        from tools.crop_regression import get_supported_crops
        supported = get_supported_crops(MODEL_DATA)
        assert "maize" in supported.values()
        assert "rice" in supported.values()
        assert "wheat" in supported.values()
        assert "oilpalm" in supported.values()
        assert "sugarbeet" in supported.values()
        assert "sugarcane" in supported.values()
        assert len(supported) == 10

    def test_get_supported_crops_invalid_path(self, tmp_path):
        """Missing model_data_path should raise CSISError."""
        from tools.crop_regression import get_supported_crops
        with pytest.raises(CSISError) as exc_info:
            get_supported_crops(str(tmp_path))
        assert exc_info.value.error_code == "INVALID_PARAMS"

    def test_normalize_variants(self):
        """Various spellings of the same crop should all normalize to the same key."""
        from tools.crop_regression import _normalize
        assert _normalize("oil palm")   == _normalize("oilpalm")   == _normalize("Oil Palm")
        assert _normalize("sugar beet") == _normalize("sugarbeet")  == _normalize("Sugar Beet")
        assert _normalize("sugar cane") == _normalize("sugarcane")  == _normalize("Sugar Cane")

    @pytest.mark.asyncio
    async def test_unsupported_crop_raises(self, tmp_path):
        """Crop not in model_data should raise INVALID_PARAMS."""
        from tools.crop_regression import run_crop_regression
        fert_path = tmp_path / "fert.csv"
        with open(fert_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["crop_name", "nitrogen_rate", "phosphorus_rate", "potassium_rate"])
            writer.writeheader()
            writer.writerow({"crop_name": "cassava", "nitrogen_rate": 50, "phosphorus_rate": 20, "potassium_rate": 30})
        lulc_path = tmp_path / "lulc.csv"
        with open(lulc_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["crop_name", "lucode"])
            writer.writeheader()
            writer.writerow({"crop_name": "cassava", "lucode": 1})
        params = {
            "landcover_raster_path":         "dummy.tif",
            "landcover_to_crop_table_path":  str(lulc_path),
            "fertilization_rate_table_path": str(fert_path),
            "model_data_path":               MODEL_DATA,
        }
        with pytest.raises(CSISError) as exc_info:
            await run_crop_regression(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"
        assert "cassava" in exc_info.value.message
        assert "Tool 5" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_crop_name_normalized_in_output(self, tmp_path):
        """'oilpalm', 'sugarbeet', 'sugarcane' should be accepted and pass crop validation."""
        from tools.crop_regression import run_crop_regression
        fert_path = tmp_path / "fert.csv"
        with open(fert_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["crop_name", "nitrogen_rate", "phosphorus_rate", "potassium_rate"])
            writer.writeheader()
            writer.writerow({"crop_name": "maize",    "nitrogen_rate": 50, "phosphorus_rate": 20, "potassium_rate": 30})
            writer.writerow({"crop_name": "oilpalm",  "nitrogen_rate": 50, "phosphorus_rate": 20, "potassium_rate": 30})
            writer.writerow({"crop_name": "sugarbeet", "nitrogen_rate": 50, "phosphorus_rate": 20, "potassium_rate": 30})
        lulc_path = tmp_path / "lulc.csv"
        with open(lulc_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["crop_name", "lucode"])
            writer.writeheader()
            writer.writerow({"crop_name": "maize",   "lucode": 1})
            writer.writerow({"crop_name": "oilpalm", "lucode": 2})
        params = {
            "landcover_raster_path":         "dummy.tif",
            "landcover_to_crop_table_path":  str(lulc_path),
            "fertilization_rate_table_path": str(fert_path),
            "model_data_path":               MODEL_DATA,
        }
        with pytest.raises((CSISError, Exception)) as exc_info:
            await run_crop_regression(params, "sess", "tid", lambda p, m: None)
        if hasattr(exc_info.value, "error_code"):
            assert exc_info.value.error_code != "INVALID_PARAMS"


# --- task_queue: execute_tool dispatch ---

class TestTaskQueue:
    def test_unknown_tool_raises(self):
        from workers.task_queue import execute_tool
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("nonexistent_tool", {}, "sess", "tid", lambda p, m: None)

    def test_tool_map_has_all_tools(self):
        """Verify all 21 tool names are in the dispatch map."""
        from workers.task_queue import execute_tool
        expected_tools = [
            "run_network_analysis_grouping",
            "run_coastal_blue_carbon_preprocessor",
            "run_coastal_blue_carbon",
            "run_seasonal_water_yield",
            "run_crop_production_percentile",
            "run_crop_production_regression",
            "run_carbon_storage",
            "run_habitat_quality",
            "run_annual_water_yield",
            "run_forest_carbon_edge_effect",
            "run_crop_pollination",
            "run_delineateit",
            "run_routedem",
            "run_sdr",
            "run_ndr",
            "run_urban_cooling",
            "run_urban_flood_risk_mitigation",
            "run_urban_stormwater_retention",
            "run_urban_nature_access",
            "run_urban_mental_health",
            "run_scenario_gen_proximity",
        ]
        for tool_name in expected_tools:
            try:
                execute_tool(tool_name, {}, "sess", "tid", lambda p, m: None)
            except ValueError:
                pytest.fail(f"Tool {tool_name} not found in tool_map")
            except Exception:
                pass  # Other errors (missing params etc.) are expected


# --- New InVEST tools: parameter validation ---

class TestCarbon:
    def test_required_keys(self):
        from tools.carbon import REQUIRED_KEYS
        assert "lulc_cur_path" in REQUIRED_KEYS
        assert "carbon_pools_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.carbon import run_carbon
        with pytest.raises(CSISError) as exc_info:
            await run_carbon({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"

    @pytest.mark.asyncio
    async def test_valuation_missing_params_raises(self, tmp_path):
        from tools.carbon import run_carbon
        with pytest.raises(CSISError) as exc_info:
            await run_carbon(
                {"lulc_cur_path": "x.tif", "carbon_pools_path": "x.csv",
                 "lulc_fut_path": "y.tif", "do_valuation": True},
                "sess", "tid", lambda p, m: None,
            )
        assert exc_info.value.error_code in ("MISSING_PARAMS", "INVALID_PARAMS")


class TestHabitatQuality:
    def test_required_keys(self):
        from tools.habitat_quality import REQUIRED_KEYS
        assert "lulc_cur_path" in REQUIRED_KEYS
        assert "threats_table_path" in REQUIRED_KEYS
        assert "sensitivity_table_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.habitat_quality import run_habitat_quality
        with pytest.raises(CSISError) as exc_info:
            await run_habitat_quality({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestAnnualWaterYield:
    def test_required_keys(self):
        from tools.annual_water_yield import REQUIRED_KEYS
        assert "lulc_path" in REQUIRED_KEYS
        assert "watersheds_path" in REQUIRED_KEYS
        assert "biophysical_table_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.annual_water_yield import run_annual_water_yield
        with pytest.raises(CSISError) as exc_info:
            await run_annual_water_yield({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestForestCarbonEdge:
    def test_required_keys(self):
        from tools.forest_carbon_edge_effect import REQUIRED_KEYS
        assert "lulc_raster_path" in REQUIRED_KEYS
        assert "biophysical_table_path" in REQUIRED_KEYS
        assert "tropical_forest_edge_carbon_model_vector_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.forest_carbon_edge_effect import run_forest_carbon_edge
        with pytest.raises(CSISError) as exc_info:
            await run_forest_carbon_edge({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestPollination:
    def test_required_keys(self):
        from tools.pollination import REQUIRED_KEYS
        assert "landcover_raster_path" in REQUIRED_KEYS
        assert "guild_table_path" in REQUIRED_KEYS
        assert "landcover_biophysical_table_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.pollination import run_pollination
        with pytest.raises(CSISError) as exc_info:
            await run_pollination({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestDelineateIt:
    def test_required_keys(self):
        from tools.delineateit import REQUIRED_KEYS
        assert "dem_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_outlet_and_no_pour_points_raises(self):
        from tools.delineateit import run_delineateit
        with pytest.raises(CSISError) as exc_info:
            await run_delineateit(
                {"dem_path": "dem.tif", "detect_pour_points": False},
                "sess", "tid", lambda p, m: None,
            )
        assert exc_info.value.error_code == "INVALID_PARAMS"


class TestRouteDEM:
    def test_required_keys(self):
        from tools.routedem import REQUIRED_KEYS
        assert "dem_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.routedem import run_routedem
        with pytest.raises(CSISError) as exc_info:
            await run_routedem({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestSDR:
    def test_required_keys(self):
        from tools.sdr import REQUIRED_KEYS
        assert "dem_path" in REQUIRED_KEYS
        assert "erosivity_path" in REQUIRED_KEYS
        assert "erodibility_path" in REQUIRED_KEYS
        assert "watersheds_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.sdr import run_sdr
        with pytest.raises(CSISError) as exc_info:
            await run_sdr({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestNDR:
    def test_required_keys(self):
        from tools.ndr import REQUIRED_KEYS
        assert "dem_path" in REQUIRED_KEYS
        assert "runoff_proxy_path" in REQUIRED_KEYS
        assert "watersheds_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_no_nutrient_selected_raises(self):
        from tools.ndr import run_ndr
        params = {k: "x" for k in ["dem_path", "lulc_path", "runoff_proxy_path",
                                     "watersheds_path", "biophysical_table_path",
                                     "threshold_flow_accumulation"]}
        params["calc_n"] = False
        params["calc_p"] = False
        with pytest.raises(CSISError) as exc_info:
            await run_ndr(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"


class TestUrbanCooling:
    def test_required_keys(self):
        from tools.urban_cooling import REQUIRED_KEYS
        assert "lulc_raster_path" in REQUIRED_KEYS
        assert "t_ref" in REQUIRED_KEYS
        assert "uhi_max" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.urban_cooling import run_urban_cooling
        with pytest.raises(CSISError) as exc_info:
            await run_urban_cooling({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestUrbanFlood:
    def test_required_keys(self):
        from tools.urban_flood import REQUIRED_KEYS
        assert "aoi_watersheds_path" in REQUIRED_KEYS
        assert "rainfall_depth" in REQUIRED_KEYS
        assert "curve_number_table_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_missing_params_raises(self):
        from tools.urban_flood import run_urban_flood
        with pytest.raises(CSISError) as exc_info:
            await run_urban_flood({}, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "MISSING_PARAMS"


class TestUrbanStormwater:
    def test_required_keys(self):
        from tools.urban_stormwater import REQUIRED_KEYS
        assert "lulc_path" in REQUIRED_KEYS
        assert "soil_group_path" in REQUIRED_KEYS
        assert "biophysical_table" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_adjust_retention_missing_radius_raises(self):
        from tools.urban_stormwater import run_urban_stormwater
        params = {k: "x" for k in ["lulc_path", "soil_group_path",
                                     "precipitation_path", "biophysical_table"]}
        params["adjust_retention_ratios"] = True
        with pytest.raises(CSISError) as exc_info:
            await run_urban_stormwater(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"


class TestUrbanNatureAccess:
    def test_required_keys(self):
        from tools.urban_nature_access import REQUIRED_KEYS
        assert "lulc_raster_path" in REQUIRED_KEYS
        assert "population_raster_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_uniform_mode_missing_radius_raises(self):
        from tools.urban_nature_access import run_urban_nature_access
        params = {k: "x" for k in ["lulc_raster_path", "lulc_attribute_table",
                                     "population_raster_path", "admin_boundaries_vector_path"]}
        params["search_radius_mode"] = "uniform radius"
        # search_radius intentionally omitted
        with pytest.raises(CSISError) as exc_info:
            await run_urban_nature_access(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"


class TestUrbanMentalHealth:
    def test_required_keys(self):
        from tools.urban_mental_health import REQUIRED_KEYS
        assert "lulc_raster_path" in REQUIRED_KEYS
        assert "population_raster_path" in REQUIRED_KEYS
        assert "admin_boundaries_vector_path" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_uniform_mode_missing_radius_raises(self):
        from tools.urban_mental_health import run_urban_mental_health
        params = {k: "x" for k in ["lulc_raster_path", "lulc_attribute_table",
                                     "population_raster_path", "admin_boundaries_vector_path"]}
        params["search_radius_mode"] = "uniform radius"
        # search_radius intentionally omitted
        with pytest.raises(CSISError) as exc_info:
            await run_urban_mental_health(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"


class TestScenarioGenProximity:
    def test_required_keys(self):
        from tools.scenario_gen_proximity import REQUIRED_KEYS
        assert "base_lulc_path" in REQUIRED_KEYS
        assert "replacement_lucode" in REQUIRED_KEYS
        assert "area_to_convert" in REQUIRED_KEYS

    @pytest.mark.asyncio
    async def test_no_conversion_direction_raises(self):
        from tools.scenario_gen_proximity import run_scenario_gen_proximity
        params = {k: "x" for k in ["base_lulc_path", "replacement_lucode",
                                     "area_to_convert", "focal_landcover_codes",
                                     "convertible_landcover_codes"]}
        params["convert_nearest_to_edge"]  = False
        params["convert_farthest_from_edge"] = False
        with pytest.raises(CSISError) as exc_info:
            await run_scenario_gen_proximity(params, "sess", "tid", lambda p, m: None)
        assert exc_info.value.error_code == "INVALID_PARAMS"
