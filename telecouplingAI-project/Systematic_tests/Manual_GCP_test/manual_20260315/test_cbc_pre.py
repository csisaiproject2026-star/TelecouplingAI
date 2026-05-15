"""手动测试：工具 2 — Coastal Blue Carbon Preprocessor"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.cbc_preprocessor import run_cbc_preprocessor

DATA = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CoastalBLueCarbonPreprocessor_input"
OUT  = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\cbc_pre"
os.makedirs(OUT, exist_ok=True)

import tools.cbc_preprocessor as _na
def _mock_gen(tool_name, session_id):
    os.makedirs(OUT, exist_ok=True)
    return OUT, "test/cbc_pre"
_na.generate_output_dir = _mock_gen


def progress(pct, msg):
    print(f"  [{pct:3d}%] {msg}")


async def main():
    params = {
        "landcover_snapshot_csv": os.path.join(DATA, "snapshots.csv"),
        "landcover_lookup_table": os.path.join(DATA, "lulc_lookup.csv"),
    }

    print("Running CBC Preprocessor...")
    result = await run_cbc_preprocessor(params, "manual_session", "manual_test", progress)

    print(f"\nSuccess: {result['success']}")
    if result.get("warning"):
        print(f"Warning: {result['warning']}")
    print(f"Output files ({len(result['files'])}):")
    for f in result["files"]:
        exists = os.path.exists(f["path"])
        print(f"  {f['filename']} [{f['render_type']}] — {'EXISTS' if exists else 'MISSING'}")

    print("\n✓ CBC Preprocessor completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
