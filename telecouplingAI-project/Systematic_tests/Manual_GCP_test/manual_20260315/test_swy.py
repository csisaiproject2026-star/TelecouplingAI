"""手动测试：工具 4 — Seasonal Water Yield"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.seasonal_water_yield import run_seasonal_water_yield

DATA = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\SeasonalWaterYield_input"
OUT  = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\swy"
os.makedirs(OUT, exist_ok=True)

import tools.seasonal_water_yield as _na
def _mock_gen(tool_name, session_id):
    os.makedirs(OUT, exist_ok=True)
    return OUT, "test/swy"
_na.generate_output_dir = _mock_gen


def progress(pct, msg):
    print(f"  [{pct:3d}%] {msg}")


async def main():
    params = {
        "aoi_path":                    os.path.join(DATA, "watershed_gura.shp"),
        "lulc_raster_path":            os.path.join(DATA, "land_use_gura.tif"),
        "dem_raster_path":             os.path.join(DATA, "DEM_gura.tif"),
        "soil_group_path":             os.path.join(DATA, "soil_group_gura.tif"),
        "biophysical_table_path":      os.path.join(DATA, "biophysical_table_gura_SWY.csv"),
        "precip_dir":                  os.path.join(DATA, "Precipitation_monthly"),
        "et0_dir":                     os.path.join(DATA, "ET0_monthly"),
        "rain_events_table_path":      os.path.join(DATA, "rain_events_gura.csv"),
        "threshold_flow_accumulation": 1000,
        "alpha_m":                     0.083333,
        "beta_i":                      1.0,
        "gamma":                       1.0,
    }

    print("Running Seasonal Water Yield (this may take a few minutes)...")
    result = await run_seasonal_water_yield(params, "manual_session", "manual_test", progress)

    print(f"\nSuccess: {result['success']}")
    print(f"Output files ({len(result['files'])}):")
    for f in result["files"]:
        exists = os.path.exists(f["path"])
        print(f"  {f['filename']} [{f['render_type']}] — {'EXISTS' if exists else 'MISSING'}")

    print("\n✓ SWY completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
