"""手动测试：工具 6 — Crop Production Regression"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.crop_regression import run_crop_regression

DATA       = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CropProductionRegression_input\sample_user_data"
MODEL_DATA = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CropProductionPercentile_input\model_data"
OUT        = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\crop_reg"
os.makedirs(OUT, exist_ok=True)

import tools.crop_regression as _na
def _mock_gen(tool_name, session_id):
    os.makedirs(OUT, exist_ok=True)
    return OUT, "test/crop_reg"
_na.generate_output_dir = _mock_gen


def progress(pct, msg):
    print(f"  [{pct:3d}%] {msg}")


async def main():
    params = {
        "landcover_raster_path":         os.path.join(DATA, "landcover.tif"),
        "landcover_to_crop_table_path":  os.path.join(DATA, "landcover_to_crop_table.csv"),
        "fertilization_rate_table_path": os.path.join(DATA, "crop_fertilization_rates.csv"),
        "aggregate_polygon_path":        os.path.join(DATA, "aggregate_shape.shp"),
        "model_data_path":               MODEL_DATA,
    }

    print("Running Crop Production Regression...")
    result = await run_crop_regression(params, "manual_session", "manual_test", progress)

    print(f"\nSuccess: {result['success']}")
    print(f"Output files ({len(result['files'])}):")
    for f in result["files"]:
        exists = os.path.exists(f["path"])
        print(f"  {f['filename']} [{f['render_type']}] — {'EXISTS' if exists else 'MISSING'}")

    print("\n✓ Crop Regression completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
