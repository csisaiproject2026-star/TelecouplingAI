"""
Integration tests: run the 15 TeleBox (non-InVEST) tools directly (no LLM, no Celery).
Each test calls the tool's async function with sample data from Systematic_tests/Test_data/.

Test data: telecouplingAI-project/Systematic_tests/Test_data/
Run with: conda run -n TeleCouplingAI pytest tests/test_telebox_tools.py -v
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Path to unified test data directory
TEST_DATA = os.path.join(
    os.path.dirname(__file__), "..", "..", "Systematic_tests", "Test_data"
)

def td(tool_folder: str, *parts) -> str:
    """Return absolute path inside Test_data/tool_folder/."""
    return os.path.join(TEST_DATA, tool_folder, *parts)


def noop_progress(pct, msg):
    pass


def run(coro):
    return asyncio.run(coro)


def patch_output_dir(monkeypatch, tmp_path):
    """Redirect generate_output_dir to write into tmp_path."""
    import shared.utils as utils
    def _mock(tool_name: str, session_id: str):
        out = os.path.join(str(tmp_path), tool_name)
        os.makedirs(out, exist_ok=True)
        return out, f"pytest/{tool_name}"
    monkeypatch.setattr(utils, "generate_output_dir", _mock)


# ─── 28 OLS ───────────────────────────────────────────────────────────────────

class TestOLS:
    def test_ols_basic_run(self, tmp_path, monkeypatch):
        """OLS: basic regression + diagnostics CSVs produced."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.ols import run_ols
        params = {
            "input_csv":            td("28_ols", "ols_data.csv"),
            "dependent_variable":   "y",
            "independent_variables": "x1,x2,x3",
        }
        result = run(run_ols(params, "pytest", "t001", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("ols_coefficients" in f for f in files), f"No coefficients CSV. Got: {files}"
        assert any("ols_diagnostics" in f for f in files), f"No diagnostics CSV. Got: {files}"

    def test_ols_model_selection(self, tmp_path, monkeypatch):
        """OLS: model selection mode produces model_selection_results.csv."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.ols import run_ols
        params = {
            "input_csv":             td("28_ols", "ols_data.csv"),
            "dependent_variable":    "y",
            "independent_variables": "x1,x2,x3",
            "model_selection":       True,
        }
        result = run(run_ols(params, "pytest", "t002", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("model_selection" in f for f in files), f"No selection CSV. Got: {files}"


# ─── 29 FAMD ──────────────────────────────────────────────────────────────────

class TestFAMD:
    def test_famd_mixed_run(self, tmp_path, monkeypatch):
        """FAMD: mixed data → eigenvalues + coordinates CSVs."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.famd import run_factor_analysis_mixed_data
        params = {
            "input_csv":               td("29_famd", "famd_data.csv"),
            "quantitative_variables":  "age,income",
            "qualitative_variables":   "gender,region",
        }
        try:
            result = run(run_factor_analysis_mixed_data(params, "pytest", "t003", noop_progress))
            files = [f["filename"] for f in result["files"]]
            assert any("eigenvalues" in f for f in files), f"No eigenvalues CSV. Got: {files}"
        except Exception as e:
            if "R" in str(e) or "Rscript" in str(e) or "FactoMineR" in str(e):
                pytest.skip(f"R/FactoMineR not available: {e}")
            raise


# ─── 30 CO2 Emissions ─────────────────────────────────────────────────────────

class TestCO2Emissions:
    def test_co2_basic_run(self, tmp_path, monkeypatch):
        """CO2: route CSV → emissions results + summary CSVs."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.co2_emissions import run_co2_emissions
        params = {
            "input_csv":           td("30_co2_emissions", "co2_data.csv"),
            "animal_count_field":  "animals",
            "length_km_field":     "distance_km",
            "capacity_per_trip":   50,
            "co2_per_km_per_trip": 2.6,
        }
        result = run(run_co2_emissions(params, "pytest", "t004", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("co2_emissions_results" in f for f in files), f"No results CSV. Got: {files}"


# ─── 31 Cost-Benefit Analysis ─────────────────────────────────────────────────

class TestCostBenefitAnalysis:
    def test_cba_basic_run(self, tmp_path, monkeypatch):
        """CBA: merge costs + revenues → cba_results.csv with RETURNS column."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.cost_benefit_analysis import run_cost_benefit_analysis
        params = {
            "input_csv":         td("31_cost_benefit_analysis", "projects.csv"),
            "economic_data_csv": td("31_cost_benefit_analysis", "economic_data.csv"),
            "key_field":         "project_id",
            "cost_field":        "cost_usd",
            "revenue_field":     "revenue_usd",
        }
        result = run(run_cost_benefit_analysis(params, "pytest", "t005", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("cba_results" in f for f in files), f"No CBA results CSV. Got: {files}"


# ─── 32 Population Density ────────────────────────────────────────────────────

class TestPopulationDensity:
    def test_population_density_run(self, tmp_path, monkeypatch):
        """Population density: CSV → density results CSV."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.population_density import run_population_count_density
        params = {
            "input_csv":        td("32_population_density", "population.csv"),
            "population_field": "pop_2020",
            "area_km2_field":   "area_km2",
        }
        result = run(run_population_count_density(params, "pytest", "t006", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("population_density_results" in f for f in files), f"No results CSV. Got: {files}"

    def test_population_growth_run(self, tmp_path, monkeypatch):
        """Population density: with two time periods → growth % computed."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.population_density import run_population_count_density
        params = {
            "input_csv":             td("32_population_density", "population.csv"),
            "population_field":      "pop_2020",
            "area_km2_field":        "area_km2",
            "population_t1_field":   "pop_2010",
            "population_t2_field":   "pop_2020",
        }
        result = run(run_population_count_density(params, "pytest", "t007", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("population_density_results" in f for f in files), f"No results CSV. Got: {files}"


# ─── 33 Radial Flows ──────────────────────────────────────────────────────────

class TestRadialFlows:
    def test_radial_flows_run(self, tmp_path, monkeypatch):
        """Radial flows: OD CSV → GeoJSON + summary CSV."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.radial_flows import run_draw_radial_flows
        params = {
            "input_csv":    td("33_radial_flows", "flows.csv"),
            "from_x_field": "from_lon",
            "from_y_field": "from_lat",
            "to_x_field":   "to_lon",
            "to_y_field":   "to_lat",
            "value_field":  "flow_value",
        }
        result = run(run_draw_radial_flows(params, "pytest", "t008", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("radial_flows" in f and f.endswith(".geojson") for f in files), \
            f"No GeoJSON output. Got: {files}"


# ─── 34 Commodity Trade ───────────────────────────────────────────────────────

class TestCommodityTrade:
    def test_commodity_trade_run(self, tmp_path, monkeypatch):
        """Commodity trade: bilateral CSV → flow GeoJSON + summary."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.commodity_trade import run_commodity_trade
        params = {
            "trade_csv":          td("34_commodity_trade", "trade.csv"),
            "from_country_field": "exporter_iso3",
            "to_country_field":   "importer_iso3",
            "value_field":        "trade_usd",
        }
        result = run(run_commodity_trade(params, "pytest", "t009", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("commodity_trade_flows" in f for f in files), f"No trade flows output. Got: {files}"


# ─── 35 Add Agents ────────────────────────────────────────────────────────────

class TestAddAgents:
    def test_add_agents_run(self, tmp_path, monkeypatch):
        """Add agents: point CSV → GeoJSON + CSV."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.add_agents import run_add_agents_interactively
        params = {
            "input_csv": td("35_add_agents", "agents.csv"),
            "x_field":   "longitude",
            "y_field":   "latitude",
            "name_field": "agent_name",
        }
        result = run(run_add_agents_interactively(params, "pytest", "t010", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("agents" in f and f.endswith(".geojson") for f in files), \
            f"No agents GeoJSON. Got: {files}"


# ─── 36 Draw Agents Table ─────────────────────────────────────────────────────

class TestDrawAgentsTable:
    def test_draw_agents_table_run(self, tmp_path, monkeypatch):
        """Draw agents table: CSV → agents_from_table GeoJSON."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.draw_agents_table import run_draw_agents_from_table
        params = {
            "input_csv": td("36_draw_agents_table", "agents_table.csv"),
            "x_field":   "longitude",
            "y_field":   "latitude",
            "name_field": "name",
        }
        result = run(run_draw_agents_from_table(params, "pytest", "t011", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("agents_from_table" in f for f in files), f"No output. Got: {files}"


# ─── 37 Add Causes ────────────────────────────────────────────────────────────

class TestAddCauses:
    def test_add_causes_run(self, tmp_path, monkeypatch):
        """Add causes: point CSV → causes GeoJSON."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.add_causes import run_add_causes_interactively
        params = {
            "input_csv":         td("37_add_causes", "causes.csv"),
            "x_field":           "longitude",
            "y_field":           "latitude",
            "description_field": "cause_description",
        }
        result = run(run_add_causes_interactively(params, "pytest", "t012", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("causes" in f and f.endswith(".geojson") for f in files), \
            f"No causes GeoJSON. Got: {files}"


# ─── 38 Add Systems ───────────────────────────────────────────────────────────

class TestAddSystems:
    def test_add_systems_run(self, tmp_path, monkeypatch):
        """Add systems: point CSV → systems GeoJSON."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.add_systems import run_add_systems_interactively
        params = {
            "input_csv":  td("38_add_systems", "systems.csv"),
            "x_field":    "longitude",
            "y_field":    "latitude",
            "name_field": "system_name",
        }
        result = run(run_add_systems_interactively(params, "pytest", "t013", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("systems" in f and f.endswith(".geojson") for f in files), \
            f"No systems GeoJSON. Got: {files}"


# ─── 39 Draw Systems Table ────────────────────────────────────────────────────

class TestDrawSystemsTable:
    def test_draw_systems_table_run(self, tmp_path, monkeypatch):
        """Draw systems table: CSV → systems_from_table GeoJSON."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.draw_systems_table import run_draw_systems_from_table
        params = {
            "input_csv":  td("39_draw_systems_table", "systems_table.csv"),
            "x_field":    "longitude",
            "y_field":    "latitude",
            "name_field": "name",
        }
        result = run(run_draw_systems_from_table(params, "pytest", "t014", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("systems_from_table" in f for f in files), f"No output. Got: {files}"


# ─── 40 Add Media Flows ───────────────────────────────────────────────────────

class TestAddMediaFlows:
    def test_media_flows_run(self, tmp_path, monkeypatch):
        """Media flows: HTML → country mention flows GeoJSON + frequency CSV."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.add_media_flows import run_add_media_flows
        params = {
            "html_file":             td("40_add_media_flows", "article.html"),
            "source_lon":            116.4,
            "source_lat":            39.9,
            "country_reference_csv": td("40_add_media_flows", "country_centroids.csv"),
        }
        result = run(run_add_media_flows(params, "pytest", "t015", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("media_flows" in f and f.endswith(".geojson") for f in files), \
            f"No media flows GeoJSON. Got: {files}"
        assert any("media_mention_frequency" in f for f in files), \
            f"No frequency CSV. Got: {files}"


# ─── 41 Food Security ─────────────────────────────────────────────────────────

class TestFoodSecurity:
    def test_food_security_run(self, tmp_path, monkeypatch):
        """Food security: FAO CSV → trend PNG + data CSV."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.food_security import run_food_security
        params = {
            "fao_csv":         td("41_food_security", "fao_food_security.csv"),
            "countries":       "China,India,USA",
            "indicator_field": "Value",
        }
        result = run(run_food_security(params, "pytest", "t016", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("food_security_data" in f for f in files), f"No data CSV. Got: {files}"
        assert any(f.endswith(".png") for f in files), f"No trend PNG. Got: {files}"


# ─── 42 Nutrition Metrics ─────────────────────────────────────────────────────

class TestNutritionMetrics:
    def test_nutrition_metrics_run(self, tmp_path, monkeypatch):
        """Nutrition metrics: population CSV → LLER results CSV + chart PNG."""
        patch_output_dir(monkeypatch, tmp_path)
        from tools.nutrition_metrics import run_nutrition_metrics
        params = {
            "population_csv":  td("42_nutrition_metrics", "nutrition_data.csv"),
            "age_col":         "age_group",
            "sex_col":         "sex",
            "weight_col":      "weight_kg",
            "population_col":  "population",
        }
        result = run(run_nutrition_metrics(params, "pytest", "t017", noop_progress))
        files = [f["filename"] for f in result["files"]]
        assert any("nutrition_metrics_results" in f for f in files), f"No results CSV. Got: {files}"
