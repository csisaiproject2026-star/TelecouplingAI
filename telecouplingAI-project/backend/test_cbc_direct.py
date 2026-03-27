"""直接测试 CBC Preprocessor，诊断路径问题。"""
import sys, os
sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

import natcap.invest.coastal_blue_carbon.preprocessor as cbc_pre

SESSION_DIR = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\uploads\csis_b41343a8-aaf8-46c7-ae63-b4490fba4e9c"
OUT_DIR = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\outputs\test_cbc_direct"
os.makedirs(OUT_DIR, exist_ok=True)

args = {
    "landcover_snapshot_csv": os.path.join(SESSION_DIR, "snapshots.csv"),
    "lulc_lookup_table_path": os.path.join(SESSION_DIR, "lulc_lookup.csv"),
    "results_suffix": "",
    "workspace_dir": OUT_DIR,
}

print("Running InVEST CBC Preprocessor...")
print(f"snapshots.csv: {args['landcover_snapshot_csv']}")

try:
    cbc_pre.execute(args)
    print("SUCCESS - check output at:", OUT_DIR)
    for f in os.listdir(os.path.join(OUT_DIR, "outputs_preprocessor")):
        print(" -", f)
except Exception as e:
    print(f"FAILED: {e}")
