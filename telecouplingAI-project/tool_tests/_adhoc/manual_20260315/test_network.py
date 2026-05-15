"""手动测试：工具 1 — Network Analysis Grouping (R + igraph)"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.network_analysis import run_network_analysis

DATA = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping"
OUT  = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\network"
os.makedirs(OUT, exist_ok=True)

import tools.network_analysis as _na
def _mock_gen(tool_name, session_id):
    os.makedirs(OUT, exist_ok=True)
    return OUT, "test/network"
_na.generate_output_dir = _mock_gen


def progress(pct, msg):
    print(f"  [{pct:3d}%] {msg}")


async def main():
    params = {
        "nodes_table":             os.path.join(DATA, "nodes.csv"),
        "links_table":             os.path.join(DATA, "links.csv"),
        "shapefile_path":          os.path.join(DATA, "World_countries_2002.shp"),
        "nodes_join_attri":        "CODE",
        "layer_join_attri":        "ISO_3_CODE",
        "clustering_algorithm":    "walktrap",
        "weight_within_clusters":  10,
        "weight_between_clusters": 2,
        "color_set":               "Set3",
        "node_size":               0.05,
        "edge_width":              0.833333,
        "label_size":              0.8,
    }

    print("Running Network Analysis...")
    result = await run_network_analysis(params, "manual_session", "manual_test", progress)

    print(f"\nSuccess: {result['success']}")
    print(f"Output files ({len(result['files'])}):")
    for f in result["files"]:
        exists = os.path.exists(f["path"])
        print(f"  {f['filename']} [{f['render_type']}] — {'EXISTS' if exists else 'MISSING'}")

    print("\n✓ Network Analysis completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
