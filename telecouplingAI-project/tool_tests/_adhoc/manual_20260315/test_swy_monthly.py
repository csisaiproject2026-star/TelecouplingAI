"""手动测试：工具 4 — SWY 月度文件重命名预检 (测试 E.1)"""
import os
import shutil
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.seasonal_water_yield import prepare_monthly_dir

PRECIP_DIR = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly"


def main():
    print("Verifying monthly precipitation file renaming...")
    tmp = prepare_monthly_dir(PRECIP_DIR, "precip_m")
    print(f"Temp dir: {tmp}")

    all_ok = True
    for m in range(1, 13):
        f = os.path.join(tmp, f"precip_m{m}.tif")
        exists = os.path.exists(f)
        print(f"  precip_m{m}.tif: {'OK' if exists else 'MISSING'}")
        if not exists:
            all_ok = False

    shutil.rmtree(tmp)
    print("Cleanup done.")

    if all_ok:
        print("\n✓ All 12 months verified successfully")
    else:
        print("\n✗ Some months are missing — check your Precipitation_monthly directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
