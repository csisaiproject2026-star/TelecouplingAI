"""
Integration tests: run InVEST models directly with NatCap sample data.
These tests call natcap.invest.xxx.execute() directly — no CSIS infrastructure needed.

Sample data: C:/YPHOME/NatCapInvest_SampleData/  (downloaded via Workbench 3.17.2)
InVEST version in conda env + Docker: 3.14.3

Version note: sample data uses 'lucode' as the LULC index column in some tables,
but InVEST 3.14.3 sensitivity table expects 'lulc'. Tests patch this where needed.

Run with: conda run -n TeleCouplingAI pytest tests/test_invest_integration.py -v
"""
import csv
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_DATA = r"C:\YPHOME\NatCapInvest_SampleData"


def sample(model_folder, *parts):
    return os.path.join(SAMPLE_DATA, model_folder, *parts)


# ─── Carbon Storage ───────────────────────────────────────────────────────────

class TestCarbonIntegration:
    def test_carbon_basic_run(self, tmp_path):
        """Carbon: current LULC only → tot_c_cur.tif"""
        import natcap.invest.carbon as carbon
        args = {
            "workspace_dir":      str(tmp_path),
            "lulc_cur_path":      sample("Carbon", "lulc_current_willamette.tif"),
            "carbon_pools_path":  sample("Carbon", "carbon_pools_willamette.csv"),
            "calc_sequestration": False,
            "lulc_fut_path":      "",
            "do_redd":            False,
            "lulc_redd_path":     "",
            "do_valuation":       False,
        }
        carbon.execute(args)
        tifs = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tif")]
        assert any("tot_c_cur" in f for f in tifs), f"Expected tot_c_cur.tif. Got: {tifs}"

    def test_carbon_sequestration_run(self, tmp_path):
        """Carbon: current + future LULC → delta_cur_fut.tif"""
        import natcap.invest.carbon as carbon
        args = {
            "workspace_dir":      str(tmp_path),
            "lulc_cur_path":      sample("Carbon", "lulc_current_willamette.tif"),
            "carbon_pools_path":  sample("Carbon", "carbon_pools_willamette.csv"),
            "calc_sequestration": True,
            "lulc_fut_path":      sample("Carbon", "lulc_future_willamette.tif"),
            "do_redd":            False,
            "lulc_redd_path":     "",
            "do_valuation":       False,
        }
        carbon.execute(args)
        tifs = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tif")]
        assert any("delta_cur_fut" in f for f in tifs), f"Expected delta_cur_fut.tif. Got: {tifs}"


# ─── Habitat Quality ──────────────────────────────────────────────────────────

class TestHabitatQualityIntegration:
    def _patch_sensitivity_lulc_column(self, src_path, tmp_path):
        """InVEST 3.14.3 expects 'lulc' column; sample data has 'lucode'. Rename it."""
        dst = os.path.join(str(tmp_path), "sensitivity_patched.csv")
        with open(src_path, newline="") as fin, open(dst, "w", newline="") as fout:
            reader = csv.reader(fin)
            writer = csv.writer(fout)
            for i, row in enumerate(reader):
                if i == 0:
                    row = ["lulc" if c.strip().lower() == "lucode" else c for c in row]
                writer.writerow(row)
        return dst

    def test_habitat_quality_current_only(self, tmp_path):
        """Habitat Quality: current LULC → quality_c.tif + deg_sum_c.tif"""
        import natcap.invest.habitat_quality as hq
        sensitivity_path = self._patch_sensitivity_lulc_column(
            sample("HabitatQuality", "sensitivity_willamette.csv"), tmp_path
        )
        args = {
            "workspace_dir":            str(tmp_path),
            "lulc_cur_path":            sample("HabitatQuality", "lulc_current_willamette.tif"),
            "threats_table_path":       sample("HabitatQuality", "threats_willamette.csv"),
            "sensitivity_table_path":   sensitivity_path,
            "lulc_fut_path":            "",
            "lulc_bas_path":            "",
            "access_vector_path":       "",
            "half_saturation_constant": 0.5,
        }
        hq.execute(args)
        tifs = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tif")]
        assert any("quality_c" in f for f in tifs), f"Expected quality_c.tif. Got: {tifs}"
        assert any("deg_sum_c" in f for f in tifs), f"Expected deg_sum_c.tif. Got: {tifs}"


# ─── Annual Water Yield ───────────────────────────────────────────────────────

class TestAnnualWaterYieldIntegration:
    def test_annual_water_yield_run(self, tmp_path):
        """Annual Water Yield: basic run → per_pixel_wyield.tif"""
        import natcap.invest.annual_water_yield as awy
        awy_dir = sample("Annual_Water_Yield")
        args = {
            "workspace_dir":                  str(tmp_path),
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
            "seasonality_constant":           15,  # Zhang Z parameter (required in 3.14.3)
        }
        awy.execute(args)
        output_dir = os.path.join(str(tmp_path), "output")
        scan_dir = output_dir if os.path.isdir(output_dir) else str(tmp_path)
        outputs = []
        for root, _, files in os.walk(scan_dir):
            outputs.extend(files)
        assert any("wyield" in f or "aet" in f for f in outputs), \
            f"Expected water yield outputs. Got: {outputs}"


# ─── Pollination ──────────────────────────────────────────────────────────────

class TestPollinationIntegration:
    def test_pollination_run(self, tmp_path):
        """Pollination: basic run → pollinator_abundance_*.tif"""
        import natcap.invest.pollination as pol
        poll_dir = sample("pollination")
        args = {
            "workspace_dir":                    str(tmp_path),
            "landcover_raster_path":            os.path.join(poll_dir, "landcover.tif"),
            "guild_table_path":                 os.path.join(poll_dir, "guild_table.csv"),
            "landcover_biophysical_table_path": os.path.join(poll_dir, "landcover_biophysical_table.csv"),
            "farm_vector_path":                 "",
        }
        pol.execute(args)
        tifs = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tif")]
        assert len(tifs) > 0, f"No TIF outputs. Got: {os.listdir(str(tmp_path))}"


# ─── SDR ──────────────────────────────────────────────────────────────────────

class TestSDRIntegration:
    def test_sdr_run(self, tmp_path):
        """SDR: basic run → sed_export.tif / usle.tif"""
        import natcap.invest.sdr.sdr as sdr
        sdr_dir = sample("SDR")
        args = {
            "workspace_dir":               str(tmp_path),
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
        }
        sdr.execute(args)
        all_files = []
        for root, _, files in os.walk(str(tmp_path)):
            all_files.extend(files)
        tifs = [f for f in all_files if f.endswith(".tif")]
        assert any("sed_export" in f or "usle" in f or "rkls" in f for f in tifs), \
            f"Expected SDR outputs. Got: {tifs}"


# ─── NDR ──────────────────────────────────────────────────────────────────────

class TestNDRIntegration:
    def _strip_load_type_columns(self, src_path, tmp_path):
        """InVEST 3.14.3 biophysical table must not have load_type_n/load_type_p
        string columns introduced in 3.17.x. Strip them from a temp copy."""
        dst = os.path.join(str(tmp_path), "biophysical_ndr_patched.csv")
        drop_cols = {"load_type_n", "load_type_p"}
        with open(src_path, newline="") as fin, open(dst, "w", newline="") as fout:
            reader = csv.DictReader(fin)
            keep = [c for c in reader.fieldnames if c.lower() not in drop_cols]
            writer = csv.DictWriter(fout, fieldnames=keep)
            writer.writeheader()
            for row in reader:
                writer.writerow({k: row[k] for k in keep})
        return dst

    def test_ndr_nitrogen_run(self, tmp_path):
        """NDR nitrogen: basic run → n_export.tif"""
        import natcap.invest.ndr.ndr as ndr
        ndr_dir = sample("NDR")
        bio_path = self._strip_load_type_columns(
            os.path.join(ndr_dir, "biophysical_table_gura.csv"), tmp_path
        )
        args = {
            "workspace_dir":                str(tmp_path),
            "dem_path":                     os.path.join(ndr_dir, "DEM_gura.tif"),
            "lulc_path":                    os.path.join(ndr_dir, "land_use_gura.tif"),
            "runoff_proxy_path":            os.path.join(ndr_dir, "precipitation_gura.tif"),
            "watersheds_path":              os.path.join(ndr_dir, "watershed_gura.shp"),
            "biophysical_table_path":       bio_path,
            "threshold_flow_accumulation":  1000,
            "k_param":                      2,
            "calc_n":                       True,
            "calc_p":                       False,
            "subsurface_critical_length_n": 150,
            "subsurface_eff_n":             0.8,
        }
        ndr.execute(args)
        all_files = []
        for root, _, files in os.walk(str(tmp_path)):
            all_files.extend(files)
        tifs = [f for f in all_files if f.endswith(".tif")]
        assert any("n_export" in f or "export" in f for f in tifs), \
            f"Expected NDR outputs. Got: {tifs}"


# ─── RouteDEM ─────────────────────────────────────────────────────────────────

class TestRouteDEMIntegration:
    def test_routedem_flow_direction(self, tmp_path):
        """RouteDEM: flow direction + accumulation"""
        import natcap.invest.routedem as rd
        rd_dir = sample("RouteDEM")
        dem = os.path.join(rd_dir, next(
            f for f in os.listdir(rd_dir) if f.endswith(".tif")
        ))
        args = {
            "workspace_dir":               str(tmp_path),
            "dem_path":                    dem,
            "algorithm":                   "D8",
            "calculate_flow_direction":    True,
            "calculate_flow_accumulation": True,
            "calculate_stream_threshold":  False,
            "calculate_slope":             False,
            "calculate_stream_order":      False,
            "calculate_downstream_distance": False,
        }
        rd.execute(args)
        tifs = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tif")]
        assert any("flow_direction" in f or "flow_accumulation" in f for f in tifs), \
            f"Expected RouteDEM outputs. Got: {tifs}"


# ─── DelineateIt ──────────────────────────────────────────────────────────────

class TestDelineateItIntegration:
    def test_delineateit_detect_pour_points(self, tmp_path):
        """DelineateIt: auto-detect pour points from DEM."""
        import natcap.invest.delineateit.delineateit as di
        di_dir = sample("DelineateIt")
        dem = os.path.join(di_dir, next(
            f for f in os.listdir(di_dir)
            if f.endswith(".tif") and "dem" in f.lower()
        ))
        args = {
            "workspace_dir":      str(tmp_path),
            "dem_path":           dem,
            "detect_pour_points": True,
            "outlet_vector_path": "",
            "snap_points":        False,
        }
        di.execute(args)
        outputs = os.listdir(str(tmp_path))
        assert any(f.endswith(".gpkg") or f.endswith(".shp") for f in outputs), \
            f"Expected vector output. Got: {outputs}"
