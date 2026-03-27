"""手动测试：QGIS 渲染器"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from renderers.qgis_renderer import render_file

DEM     = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\SeasonalWaterYield_input\DEM_gura.tif"
OUT_DIR = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\qgis"
OUT_PNG = os.path.join(OUT_DIR, "dem_render.png")


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Input:  {DEM}")
    print(f"Output: {OUT_PNG}")
    print("Rendering with QGIS (headless)...")

    result = await render_file(DEM, OUT_PNG, width=1920, height=1080)

    if os.path.exists(result):
        size_kb = os.path.getsize(result) / 1024
        print(f"\n✓ QGIS render OK — {result} ({size_kb:.1f} KB)")
    else:
        print(f"\n✗ Output file not found: {result}")


if __name__ == "__main__":
    asyncio.run(main())
