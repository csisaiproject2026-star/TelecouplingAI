"""手动测试：QGIS zoom_render — 世界底图 + 用户图层叠加渲染"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from renderers.qgis_renderer import zoom_render

# 用 SWY 的流域 shapefile 测试
SHP     = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\SeasonalWaterYield_input\watershed_gura.shp"
DEM     = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\SeasonalWaterYield_input\DEM_gura.tif"
OUT_DIR = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\qgis"


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Test 1: SHP on world basemap
    out_shp = os.path.join(OUT_DIR, "zoom_render_shp.png")
    print(f"Test 1 — SHP: {SHP}")
    result = await zoom_render(SHP, out_shp, width=1920, height=1080, padding=0.2)
    size_kb = os.path.getsize(result) / 1024
    print(f"  ✓ {result} ({size_kb:.1f} KB)\n")

    # Test 2: TIF on world basemap
    out_tif = os.path.join(OUT_DIR, "zoom_render_tif.png")
    print(f"Test 2 — TIF: {DEM}")
    result = await zoom_render(DEM, out_tif, width=1920, height=1080, padding=0.1)
    size_kb = os.path.getsize(result) / 1024
    print(f"  ✓ {result} ({size_kb:.1f} KB)\n")

    print("✓ zoom_render completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
