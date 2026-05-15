"""手动测试：测试 J — Output Router 文件分类验证"""
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from renderers.output_router import classify_file

CASES = [
    ("network_plot_abc.pdf",                  "network_analysis",                    "download"),
    ("network_stats_abc.csv",                 "network_analysis",                    "csv"),
    ("output_abc.shp",                        "network_analysis",                    "qgis"),
    ("QF_abc.tif",                            "seasonal_water_yield",                "qgis"),
    ("transitions_abc.csv",                   "coastal_blue_carbon_preprocessor",    "csv"),
    ("maize_yield_25percentile_abc.tif",      "crop_production_percentile",          "qgis"),
    ("result_table_abc.csv",                  "crop_production_percentile",          "csv"),
    ("random.xyz",                            "unknown",                             "download"),
]


def main():
    all_ok = True
    for filename, tool, expected in CASES:
        result = classify_file(filename, tool)
        ok = result == expected
        status = "OK" if ok else f"FAIL (got '{result}', expected '{expected}')"
        if not ok:
            all_ok = False
        print(f"  {filename:<45} [{tool:<40}] -> {result:<10} {status}")

    if all_ok:
        print("\n✓ Output Router: ALL OK")
    else:
        print("\n✗ Output Router: SOME FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
