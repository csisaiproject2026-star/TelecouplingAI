"""Fast test of the new validate_input_files() pre-flight (pure os.path + ext
checks; no natcap import). Run in a container with cwd=/app."""
from shared.utils import validate_input_files, CSISError

D = "/data/datainput/08_habitat_quality"
SPECS = [
    ("lulc_cur_path",          True,  "raster"),
    ("threats_table_path",     True,  "table"),
    ("sensitivity_table_path", True,  "table"),
    ("access_vector_path",     False, "vector"),
]
LULC = f"{D}/lulc_current_willamette.tif"
THREATS = f"{D}/threats_willamette.csv"
SENS = f"{D}/sensitivity_willamette.csv"

cases = {
    "forgot to upload the sensitivity table": {
        "lulc_cur_path": LULC, "threats_table_path": THREATS},
    "typo / wrong path for sensitivity table": {
        "lulc_cur_path": LULC, "threats_table_path": THREATS,
        "sensitivity_table_path": f"{D}/sensitivity_TYPO.csv"},
    "wrong file type: a CSV dropped into the lulc (raster) slot": {
        "lulc_cur_path": THREATS, "threats_table_path": THREATS,
        "sensitivity_table_path": SENS},
    "all correct (happy path)": {
        "lulc_cur_path": LULC, "threats_table_path": THREATS,
        "sensitivity_table_path": SENS},
}
for name, params in cases.items():
    print("=" * 64)
    print("CASE:", name)
    try:
        validate_input_files(params, SPECS)
        print("  -> OK, would proceed to run the model")
    except CSISError as e:
        print("  code:", e.error_code)
        for line in e.message.splitlines():
            print("   ", line)
