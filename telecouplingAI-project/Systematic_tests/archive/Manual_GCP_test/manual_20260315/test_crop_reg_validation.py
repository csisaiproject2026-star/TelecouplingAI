"""手动测试：测试 G.1 — Crop Regression 不支持作物验证"""
import asyncio
import csv
import os
import sys
import tempfile

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.crop_regression import run_crop_regression
from shared.utils import CSISError

MODEL_DATA = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CropProductionPercentile_input\model_data"


async def main():
    # 创建包含不支持作物的临时 CSV
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(tmp, fieldnames=["crop_name", "nitrogen_rate", "phosphorus_rate", "potassium_rate"])
    writer.writeheader()
    writer.writerow({"crop_name": "cassava", "nitrogen_rate": 50, "phosphorus_rate": 20, "potassium_rate": 30})
    tmp.close()

    try:
        await run_crop_regression(
            {
                "landcover_raster_path":         "dummy.tif",
                "landcover_to_crop_table_path":  "dummy.csv",
                "fertilization_rate_table_path": tmp.name,
                "model_data_path":               MODEL_DATA,
            },
            "sess", "tid", lambda p, m: None,
        )
        print("ERROR: Should have raised CSISError!")
        sys.exit(1)
    except CSISError as e:
        print(f"Correctly rejected: {e.message}")
        assert "cassava" in e.message, f"Expected 'cassava' in message, got: {e.message}"
        assert "Tool 5" in e.message, f"Expected 'Tool 5' in message, got: {e.message}"
        print("\n✓ SUPPORTED_CROPS validation works!")
    finally:
        os.unlink(tmp.name)


if __name__ == "__main__":
    asyncio.run(main())
