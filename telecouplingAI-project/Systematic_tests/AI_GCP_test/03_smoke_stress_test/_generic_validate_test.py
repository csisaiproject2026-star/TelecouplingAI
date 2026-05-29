"""Unit test for validate_file_params_exist() — the generic, tool-agnostic
existence pre-flight. Confirms it flags missing files but does NOT false-positive
on URLs / output paths / relative / non-path params. Run with cwd=/app."""
from shared.utils import validate_file_params_exist, CSISError

D = "/data/datainput/08_habitat_quality"
REAL = f"{D}/lulc_current_willamette.tif"

cases = {
    "valid existing file -> OK": ({"lulc_cur_path": REAL}, False),
    "missing file -> FLAG": ({"lulc_cur_path": f"{D}/NOPE.tif"}, True),
    "URL value -> skip (OK)": ({"server_path": "https://example.com/x.tif"}, False),
    "output path -> skip (OK)": ({"output_path": "/data/outputs/will_be_made.tif"}, False),
    "workspace dir -> skip (OK)": ({"workspace_dir": "/data/outputs/ws"}, False),
    "relative value -> skip (OK)": ({"lulc_cur_path": "relative/x.tif"}, False),
    "non-path param -> skip (OK)": ({"results_suffix": "run1", "n": "5"}, False),
    "mixed: one good one missing -> FLAG": (
        {"lulc_cur_path": REAL, "eto_path": f"{D}/MISSING_eto.tif"}, True),
}
ok = True
for name, (params, expect_flag) in cases.items():
    try:
        validate_file_params_exist(params)
        flagged = False
        msg = ""
    except CSISError as e:
        flagged = True
        msg = e.message.replace("\n", " | ")
    status = "PASS" if flagged == expect_flag else "**FAIL**"
    if flagged != expect_flag:
        ok = False
    print(f"[{status}] {name}" + (f"  -> {msg}" if flagged else ""))
print("\nALL OK" if ok else "\nSOME CASES FAILED")
