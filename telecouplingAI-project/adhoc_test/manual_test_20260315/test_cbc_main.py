"""手动测试：工具 3 — Coastal Blue Carbon Main Model"""
import asyncio
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from tools.cbc_main import run_cbc_main

DATA    = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CoastalBlueCarbon_input"
PRE_OUT = os.path.join(DATA, "outputs_preprocessor")
OUT     = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs\cbc_main"
os.makedirs(OUT, exist_ok=True)

import tools.cbc_main as _na
def _mock_gen(tool_name, session_id):
    os.makedirs(OUT, exist_ok=True)
    return OUT, "test/cbc_main"
_na.generate_output_dir = _mock_gen


def progress(pct, msg):
    print(f"  [{pct:3d}%] {msg}")


async def main():
    params = {
        "landcover_snapshot_csv":      os.path.join(DATA, "snapshots.csv"),
        "landcover_transitions_table": os.path.join(PRE_OUT, "transitions_sample.csv"),
        "biophysical_table_path":      os.path.join(PRE_OUT, "biophysical_table_sample.csv"),
    }

    print("Running Coastal Blue Carbon Main Model...")
    result = await run_cbc_main(params, "manual_session", "manual_test", progress)

    print(f"\nSuccess: {result['success']}")
    print(f"Output files ({len(result['files'])}):")
    for f in result["files"]:
        exists = os.path.exists(f["path"])
        print(f"  {f['filename']} [{f['render_type']}] — {'EXISTS' if exists else 'MISSING'}")

    print("\n✓ CBC Main completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
