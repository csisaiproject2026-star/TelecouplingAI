"""Comprehensive test of the deployed input-validation pre-flight.

For EVERY tool in TOOL_FILE_SPECS, exercise the exact functions agent.py runs
before dispatch (validate_file_params_exist then validate_input_files) under:
  - correct   : all spec'd params point at valid files of the right type  -> must ALLOW
  - missing   : a required param omitted                                   -> must BLOCK
  - wrong-path: a required param -> nonexistent path (right extension)     -> must BLOCK
  - wrong-type: a required param -> a real file of the WRONG type          -> must BLOCK

Validation only checks existence + extension, so empty placeholder files of
each kind fully exercise the logic. No model runs, no Gemini, deterministic.

Run inside the backend container:  cd /app && python /tmp/_validation_full_test.py
Writes JSON to /tmp/validation_report.json and prints a summary.
"""
import json
import os
import tempfile

from shared.utils import validate_file_params_exist, validate_input_files, CSISError
from shared.tool_file_specs import TOOL_FILE_SPECS

TMP = tempfile.mkdtemp(prefix="valtest_")
DUMMY = {}
for kind, ext in (("raster", ".tif"), ("vector", ".shp"), ("table", ".csv")):
    p = os.path.join(TMP, f"dummy{ext}")
    open(p, "w").close()
    DUMMY[kind] = p
# a real file of the WRONG kind (raster<->table, vector->table)
WRONG = {"raster": DUMMY["table"], "vector": DUMMY["table"], "table": DUMMY["raster"]}


def run_preflight(params, specs):
    """Exactly what agent.py does before dispatch. Returns (blocked, code, msg)."""
    try:
        validate_file_params_exist(params)          # Step 1: existence (*_path)
        validate_input_files(params, specs)         # Step 2: existence + type
        return False, None, ""
    except CSISError as e:
        return True, e.error_code, e.message.replace("\n", " | ")


def valid_params(specs):
    return {k: DUMMY[kind] for (k, _req, kind) in specs}


results = []
for tool, specs in TOOL_FILE_SPECS.items():
    required = [(k, kind) for (k, req, kind) in specs if req]

    # 1) correct -> must ALLOW
    blocked, code, msg = run_preflight(valid_params(specs), specs)
    results.append({"tool": tool, "case": "correct (all valid)", "expect": "allow",
                    "blocked": blocked, "code": code, "msg": msg,
                    "verdict": "PASS" if not blocked else "FAIL"})

    # 2) per required param: missing / wrong-path / wrong-type -> must BLOCK
    for (k, kind) in required:
        p = valid_params(specs); p.pop(k, None)
        blocked, code, msg = run_preflight(p, specs)
        results.append({"tool": tool, "case": f"missing required '{k}'", "expect": "block",
                        "blocked": blocked, "code": code, "msg": msg,
                        "verdict": "PASS" if blocked else "FAIL"})

        p = valid_params(specs); p[k] = os.path.join(TMP, "NOT_UPLOADED" + os.path.splitext(DUMMY[kind])[1])
        blocked, code, msg = run_preflight(p, specs)
        results.append({"tool": tool, "case": f"wrong-path '{k}'", "expect": "block",
                        "blocked": blocked, "code": code, "msg": msg,
                        "verdict": "PASS" if blocked else "FAIL"})

        p = valid_params(specs); p[k] = WRONG[kind]
        blocked, code, msg = run_preflight(p, specs)
        results.append({"tool": tool, "case": f"wrong-type '{k}' ({kind}<-{os.path.basename(WRONG[kind])})",
                        "expect": "block", "blocked": blocked, "code": code, "msg": msg,
                        "verdict": "PASS" if blocked else "FAIL"})

total = len(results)
passed = sum(1 for r in results if r["verdict"] == "PASS")
n_tools = len(TOOL_FILE_SPECS)
out = {"n_tools": n_tools, "total_cases": total, "passed": passed, "failed": total - passed,
       "results": results}
with open("/tmp/validation_report.json", "w") as f:
    json.dump(out, f, indent=2)

print(f"TOOLS={n_tools}  CASES={total}  PASS={passed}  FAIL={total - passed}")
for r in results:
    if r["verdict"] != "PASS":
        print(f"  !!FAIL {r['tool']} | {r['case']} | expect={r['expect']} blocked={r['blocked']} code={r['code']}")
print("ALL PASS" if passed == total else f"{total - passed} CASES FAILED (see above)")
