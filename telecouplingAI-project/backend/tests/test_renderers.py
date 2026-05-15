"""
Tests for renderers: output_router.py and csv_analyzer.py
Covers classify_file rules for all 42 tools + route_outputs logic + csv_analyzer.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from renderers.output_router import classify_file, route_outputs
from renderers.csv_analyzer import analyze_csv, suggest_chart


# --- classify_file ---

class TestClassifyFile:
    def test_network_analysis_pdf(self):
        assert classify_file("network_plot_abc.pdf", "network_analysis") == "download"

    def test_network_analysis_csv(self):
        assert classify_file("network_stats_abc.csv", "network_analysis") == "csv"

    def test_network_analysis_shp(self):
        assert classify_file("output_abc.shp", "network_analysis") == "qgis"

    def test_swy_tif(self):
        assert classify_file("QF_abc.tif", "seasonal_water_yield") == "qgis"

    def test_swy_shp(self):
        assert classify_file("aggregated_results_swy_abc.shp", "seasonal_water_yield") == "qgis"

    def test_cbc_preprocessor_csv(self):
        assert classify_file("transitions_abc.csv", "coastal_blue_carbon_preprocessor") == "csv"

    def test_cbc_preprocessor_tif(self):
        assert classify_file("aligned_lulc_abc.tif", "coastal_blue_carbon_preprocessor") == "qgis"

    def test_crop_percentile_tif(self):
        assert classify_file("maize_yield_25percentile_abc.tif", "crop_production_percentile") == "qgis"

    def test_crop_percentile_csv(self):
        assert classify_file("result_table_abc.csv", "crop_production_percentile") == "csv"

    def test_crop_regression_tif(self):
        assert classify_file("maize_regression_production_abc.tif", "crop_production_regression") == "qgis"

    def test_unknown_tool_fallback_tif(self):
        assert classify_file("anything.tif", "unknown_tool") == "qgis"

    def test_unknown_tool_fallback_csv(self):
        assert classify_file("anything.csv", "unknown_tool") == "csv"

    def test_unknown_tool_fallback_unknown_ext(self):
        assert classify_file("anything.xyz", "unknown_tool") == "download"

    # TeleBox tools 28–42
    def test_ols_csv(self):
        assert classify_file("ols_coefficients.csv", "ols") == "csv"

    def test_ols_diagnostics_csv(self):
        assert classify_file("ols_diagnostics.csv", "ols") == "csv"

    def test_famd_pdf(self):
        assert classify_file("famd_plots.pdf", "famd") == "download"

    def test_famd_csv(self):
        assert classify_file("famd_eigenvalues.csv", "famd") == "csv"

    def test_co2_csv(self):
        assert classify_file("co2_emissions_results.csv", "co2_emissions") == "csv"

    def test_cba_csv(self):
        assert classify_file("cba_results.csv", "cost_benefit_analysis") == "csv"

    def test_population_density_csv(self):
        assert classify_file("population_density_results.csv", "population_density") == "csv"

    def test_radial_flows_geojson(self):
        assert classify_file("radial_flows.geojson", "radial_flows") == "download"

    def test_radial_flows_shp(self):
        assert classify_file("radial_flows.shp", "radial_flows") == "qgis"

    def test_commodity_trade_geojson(self):
        assert classify_file("commodity_trade_flows.geojson", "commodity_trade") == "download"

    def test_add_agents_geojson(self):
        assert classify_file("agents.geojson", "add_agents") == "download"

    def test_add_agents_shp(self):
        assert classify_file("agents.shp", "add_agents") == "qgis"

    def test_add_causes_geojson(self):
        assert classify_file("causes.geojson", "add_causes") == "download"

    def test_add_systems_geojson(self):
        assert classify_file("systems.geojson", "add_systems") == "download"

    def test_media_flows_geojson(self):
        assert classify_file("media_flows.geojson", "add_media_flows") == "download"

    def test_media_flows_csv(self):
        assert classify_file("media_mention_frequency.csv", "add_media_flows") == "csv"

    def test_food_security_png(self):
        assert classify_file("food_security_trend.png", "food_security") == "image"

    def test_food_security_csv(self):
        assert classify_file("food_security_data.csv", "food_security") == "csv"

    def test_nutrition_png(self):
        assert classify_file("nutrition_ller_chart.png", "nutrition_metrics") == "image"

    def test_nutrition_csv(self):
        assert classify_file("nutrition_metrics_results.csv", "nutrition_metrics") == "csv"


# --- route_outputs ---

class TestRouteOutputs:
    def test_skips_intermediate_outputs(self, tmp_path):
        """intermediate_outputs subdir should always be skipped."""
        (tmp_path / "QF_test.tif").touch()
        inter = tmp_path / "intermediate_outputs"
        inter.mkdir()
        (inter / "should_skip.tif").touch()

        results = route_outputs(str(tmp_path), "seasonal_water_yield")

        filenames = [r["filename"] for r in results]
        assert "QF_test.tif" in filenames
        assert "should_skip.tif" not in filenames

    def test_qgis_file_becomes_download(self, tmp_path):
        """SHP/TIF files classified as qgis should be returned as 'download'."""
        (tmp_path / "QF_test.tif").touch()

        results = route_outputs(str(tmp_path), "seasonal_water_yield")

        tif_entry = next(r for r in results if r["filename"] == "QF_test.tif")
        assert tif_entry["render_type"] == "download"

    def test_no_auto_preview_generation(self, tmp_path):
        """Previews are NOT generated automatically; they require explicit render_spatial_file call."""
        tif_path = tmp_path / "QF_test.tif"
        tif_path.touch()

        results = route_outputs(str(tmp_path), "seasonal_water_yield")

        render_types = {r["filename"]: r["render_type"] for r in results}
        assert render_types.get("QF_test.tif") == "download"
        # No preview file should be created or listed
        assert not any("_preview.png" in r["filename"] for r in results)

    def test_csv_file_unaffected(self, tmp_path):
        """CSV files should not be touched by the preview logic."""
        (tmp_path / "result_table_x.csv").touch()

        results = route_outputs(str(tmp_path), "crop_production_percentile")
        assert len(results) == 1
        r = results[0]
        assert r["filename"] == "result_table_x.csv"
        assert r["render_type"] == "csv"

    def test_returns_correct_structure(self, tmp_path):
        """Every result entry must have filename, path, render_type."""
        (tmp_path / "result_table_x.csv").touch()
        results = route_outputs(str(tmp_path), "crop_production_percentile")
        assert len(results) == 1
        r = results[0]
        assert "filename" in r
        assert "path" in r
        assert "render_type" in r

    def test_skips_existing_preview_files(self, tmp_path):
        """Files ending in _preview.png should not be included in output scan."""
        (tmp_path / "QF_test_preview.png").touch()

        results = route_outputs(str(tmp_path), "seasonal_water_yield")

        # _preview.png files are skipped in the scan, so result should be empty
        assert len(results) == 0


# --- csv_analyzer ---

class TestCsvAnalyzer:
    def _write_csv(self, tmp_path, filename, content):
        path = tmp_path / filename
        path.write_text(content)
        return str(path)

    def test_analyze_csv_basic(self, tmp_path):
        path = self._write_csv(tmp_path, "data.csv", "name,value\nalice,10\nbob,20\n")
        result = analyze_csv(path)
        assert result["filename"] == "data.csv"
        assert result["columns"] == ["name", "value"]
        assert result["total_rows"] == 2
        assert len(result["rows"]) == 2

    def test_analyze_csv_max_rows(self, tmp_path):
        lines = "id,val\n" + "".join(f"{i},{i*2}\n" for i in range(100))
        path = self._write_csv(tmp_path, "big.csv", lines)
        result = analyze_csv(path)
        assert result["total_rows"] == 100
        assert len(result["rows"]) == 50  # MAX_PREVIEW_ROWS

    def test_suggest_chart_result_table(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({"crop_name": ["maize", "rice"], "production_mt": [100, 200]})
        chart = suggest_chart(df, "result_table_abc.csv")
        assert chart is not None
        assert chart["type"] == "bar"
        assert chart["x_field"] == "crop_name"

    def test_suggest_chart_network_stats(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({"node": ["A", "B"], "degree": [3, 5], "betweenness": [0.1, 0.2]})
        chart = suggest_chart(df, "network_stats_abc.csv")
        assert chart is not None
        assert chart["y_field"] == "degree"

    def test_suggest_chart_no_numeric(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({"name": ["a", "b"], "label": ["x", "y"]})
        chart = suggest_chart(df, "labels.csv")
        assert chart is None
