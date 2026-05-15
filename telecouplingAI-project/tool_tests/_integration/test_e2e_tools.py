"""
End-to-end tool tests against live Docker stack.

Simulates a real user session:
  1. Upload input files via POST /api/upload
  2. Send a chat message triggering the tool via POST /api/chat (SSE)
  3. Read SSE stream until "done" or "error"
  4. Verify output files were created inside the container

Run:
    python -m pytest tests/test_e2e_tools.py -v -s --timeout=300

Tools tested:
  - Tool 1: Network Analysis Grouping  (R + igraph, fastest ~30s)
  - Tool 2: CBC Preprocessor           (natcap.invest, ~60s)
  - Tool 5: Crop Production Percentile (natcap.invest, ~120s)
"""
import io
import json
import os
import time
import uuid

import pytest
import requests

BASE = "http://localhost"
DEMO = "/data/datainput"          # container path (mounted read-only)
OUTPUTS = "/data/outputs"         # container path for results

# Paths as seen INSIDE the Docker container
NA_DIR   = f"{DEMO}/NetworkAnalysisGrouping_input/Network Analysis Grouping"
CBC_DIR  = f"{DEMO}/CoastalBLueCarbonPreprocessor_input"
CROP_DIR = f"{DEMO}/CropProductionPercentile_input/sample_user_data"


# ── helpers ────────────────────────────────────────────────────────────────

def new_sid():
    return f"e2e_{uuid.uuid4().hex[:10]}"


def upload_files(sid: str, file_specs: list[tuple[str, str, bytes, str]]) -> dict:
    """
    Upload files to the API.
    file_specs: list of (field, filename, content_bytes, mimetype)
    Returns the upload response JSON.
    """
    r = requests.post(
        f"{BASE}/api/upload",
        files=[("files", (fname, io.BytesIO(content), mime))
               for _, fname, content, mime in file_specs],
        headers={"X-Session-ID": sid},
        timeout=30,
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    return r.json()


def read_local(path: str) -> bytes:
    """Read a file from the host machine (Windows demo data folder)."""
    return open(path, "rb").read()


def stream_chat(sid: str, message: str, timeout: int = 300) -> list[dict]:
    """
    POST /api/chat with SSE streaming.
    Returns list of all event dicts received before 'done' or 'error'.
    """
    events = []
    start = time.time()
    with requests.post(
        f"{BASE}/api/chat",
        data={"message": message},
        headers={"X-Session-ID": sid},
        timeout=timeout,
        stream=True,
    ) as r:
        assert r.status_code == 200, f"Chat returned {r.status_code}: {r.text[:200]}"
        assert "text/event-stream" in r.headers.get("content-type", "")

        for raw_line in r.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            try:
                payload = json.loads(raw_line[5:].strip())
            except json.JSONDecodeError:
                continue

            elapsed = time.time() - start
            etype = payload.get("type", "?")
            # Print progress so the test runner shows live output (-s flag)
            if etype == "text_chunk":
                print(f"  [{elapsed:.1f}s] AI: {payload.get('content','')[:120]}")
            elif etype == "tool_call":
                print(f"  [{elapsed:.1f}s] TOOL CALL: {payload.get('tool_name','?')}")
            elif etype == "progress":
                print(f"  [{elapsed:.1f}s] PROGRESS {payload.get('percent',0)}%: {payload.get('message','')}")
            elif etype == "tool_result":
                print(f"  [{elapsed:.1f}s] TOOL RESULT: {str(payload)[:200]}")
            elif etype in ("done", "error"):
                print(f"  [{elapsed:.1f}s] EVENT: {etype}")
                events.append(payload)
                break
            events.append(payload)

    return events


def assert_outputs_exist(sid: str, min_files: int = 1):
    """Check that output files were created in the container for this session."""
    result = requests.get(
        f"{BASE}/download/{sid}/",
        timeout=10,
    )
    # Even a 404 tells us the dir doesn't exist — we instead exec into container
    # and list the outputs directory.
    import subprocess
    ls = subprocess.run(
        ["docker", "exec", "tele-backend",
         "find", f"{OUTPUTS}/{sid}", "-type", "f"],
        capture_output=True, text=True,
    )
    files = [f for f in ls.stdout.strip().splitlines() if f]
    print(f"  Output files ({len(files)}):")
    for f in files:
        print(f"    {f}")
    assert len(files) >= min_files, (
        f"Expected ≥{min_files} output file(s) for session {sid}, found {len(files)}"
    )
    return files


# ── Tool 1: Network Analysis ───────────────────────────────────────────────

@pytest.mark.timeout(300)
def test_e2e_network_analysis():
    """
    Upload nodes.csv + links.csv, then ask the agent to run Network Analysis.
    Shapefile is referenced by its container path (already mounted).
    """
    print("\n\n=== Tool 1: Network Analysis Grouping ===")
    sid = new_sid()

    # 1. Upload CSV inputs
    demo_root = (
        r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
        r"\telecouplingAI-project\datainput_for_demo"
        r"\NetworkAnalysisGrouping_input\Network Analysis Grouping"
    )
    nodes_bytes = read_local(os.path.join(demo_root, "nodes.csv"))
    links_bytes = read_local(os.path.join(demo_root, "links.csv"))
    upload_resp = upload_files(sid, [
        ("files", "nodes.csv", nodes_bytes, "text/csv"),
        ("files", "links.csv", links_bytes, "text/csv"),
    ])
    print(f"  Uploaded: {[f['filename'] for f in upload_resp['uploaded']]}")

    # Resolve container upload paths from the response
    uploaded = {f["filename"]: f["path"] for f in upload_resp["uploaded"]}
    nodes_path = uploaded["nodes.csv"]
    links_path = uploaded["links.csv"]
    shp_path   = f"{NA_DIR}/World_countries_2002.shp"

    # 2. Send chat message with all required parameters
    message = (
        "Please run the Network Analysis Grouping tool with the following parameters:\n"
        f"- nodes_table: {nodes_path}\n"
        f"- links_table: {links_path}\n"
        f"- shapefile_path: {shp_path}\n"
        "- nodes_join_attri: CODE\n"
        "- layer_join_attri: ISO_3_CODE\n"
        "- clustering_algorithm: walktrap\n"
        "Run the tool now without asking for confirmation."
    )
    print(f"  Session: {sid}")
    events = stream_chat(sid, message, timeout=300)

    # 3. Verify no error event
    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Tool returned error: {error_events}"

    # 4. Verify output files created
    output_files = assert_outputs_exist(sid, min_files=1)
    assert any("network" in f.lower() or ".csv" in f.lower() or ".html" in f.lower()
               for f in output_files), f"No expected output files found: {output_files}"
    print("  [PASS] Network Analysis")


# ── Tool 2: CBC Preprocessor ───────────────────────────────────────────────

@pytest.mark.timeout(300)
def test_e2e_cbc_preprocessor():
    """
    Upload snapshots.csv + lulc_lookup.csv, reference raster TIFs from container.
    Ask agent to run CBC Preprocessor.
    """
    print("\n\n=== Tool 2: CBC Preprocessor ===")
    sid = new_sid()

    demo_root = (
        r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
        r"\telecouplingAI-project\datainput_for_demo"
        r"\CoastalBLueCarbonPreprocessor_input"
    )
    snapshots_bytes = read_local(os.path.join(demo_root, "snapshots.csv"))
    lookup_bytes    = read_local(os.path.join(demo_root, "lulc_lookup.csv"))
    tif2010_bytes   = read_local(os.path.join(demo_root, "GBJC_2010_mean_Resample.tif"))
    tif2030_bytes   = read_local(os.path.join(demo_root, "GBJC_2030_mean_Resample.tif"))
    tif2050_bytes   = read_local(os.path.join(demo_root, "GBJC_2050_mean_Resample.tif"))
    upload_resp = upload_files(sid, [
        ("files", "snapshots.csv",              snapshots_bytes, "text/csv"),
        ("files", "lulc_lookup.csv",            lookup_bytes,    "text/csv"),
        ("files", "GBJC_2010_mean_Resample.tif", tif2010_bytes,  "image/tiff"),
        ("files", "GBJC_2030_mean_Resample.tif", tif2030_bytes,  "image/tiff"),
        ("files", "GBJC_2050_mean_Resample.tif", tif2050_bytes,  "image/tiff"),
    ])
    print(f"  Uploaded: {[f['filename'] for f in upload_resp['uploaded']]}")

    uploaded = {f["filename"]: f["path"] for f in upload_resp["uploaded"]}

    message = (
        "Please run the Coastal Blue Carbon Preprocessor tool with:\n"
        f"- landcover_snapshot_csv: {uploaded['snapshots.csv']}\n"
        f"- landcover_lookup_table: {uploaded['lulc_lookup.csv']}\n"
        f"- lulc_snapshot_list (in order matching the snapshot CSV rows):\n"
        f"    {uploaded['GBJC_2010_mean_Resample.tif']}\n"
        f"    {uploaded['GBJC_2030_mean_Resample.tif']}\n"
        f"    {uploaded['GBJC_2050_mean_Resample.tif']}\n"
        "Run the tool now without asking for confirmation."
    )
    print(f"  Session: {sid}")
    events = stream_chat(sid, message, timeout=300)

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Tool returned error: {error_events}"

    output_files = assert_outputs_exist(sid, min_files=1)
    print("  [PASS] CBC Preprocessor")


# ── Tool 5: Crop Production Percentile ─────────────────────────────────────

@pytest.mark.timeout(360)
def test_e2e_crop_percentile():
    """
    Upload landcover_to_crop_table.csv, reference landcover.tif from container.
    model_data is at /data/model_data (already set via MODEL_DATA_PATH env var).
    """
    print("\n\n=== Tool 5: Crop Production Percentile ===")
    sid = new_sid()

    demo_root = (
        r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
        r"\telecouplingAI-project\datainput_for_demo"
        r"\CropProductionPercentile_input\sample_user_data"
    )
    table_bytes = read_local(os.path.join(demo_root, "landcover_to_crop_table.csv"))
    upload_resp = upload_files(sid, [
        ("files", "landcover_to_crop_table.csv", table_bytes, "text/csv"),
    ])
    print(f"  Uploaded: {[f['filename'] for f in upload_resp['uploaded']]}")

    uploaded = {f["filename"]: f["path"] for f in upload_resp["uploaded"]}
    lulc_path  = f"{CROP_DIR}/landcover.tif"
    table_path = uploaded["landcover_to_crop_table.csv"]

    message = (
        "Please run the Crop Production Percentile tool with:\n"
        f"- landcover_raster_path: {lulc_path}\n"
        f"- landcover_to_crop_table_path: {table_path}\n"
        "The model data path is already configured in the system.\n"
        "Run the tool now without asking for confirmation."
    )
    print(f"  Session: {sid}")
    events = stream_chat(sid, message, timeout=360)

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Tool returned error: {error_events}"

    output_files = assert_outputs_exist(sid, min_files=1)
    print("  [PASS] Crop Percentile")


# ── Tool 3: Coastal Blue Carbon Main ───────────────────────────────────────

@pytest.mark.timeout(600)
def test_e2e_cbc_main():
    """
    Upload transitions + biophysical tables.
    snapshots.csv is rewritten with absolute container paths for the TIFs
    (already mounted at /data/datainput/CoastalBlueCarbon_input/).
    """
    print("\n\n=== Tool 3: Coastal Blue Carbon Main ===")
    sid = new_sid()

    cbc_root = (
        r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
        r"\telecouplingAI-project\datainput_for_demo\CoastalBlueCarbon_input"
    )
    preproc_root = os.path.join(cbc_root, "outputs_preprocessor")
    container_cbc = "/data/datainput/CoastalBlueCarbon_input"

    # Build snapshots.csv with absolute container paths
    snapshots_content = (
        '"snapshot_year","raster_path"\n'
        f'2010,{container_cbc}/GBJC_2010_mean_Resample.tif\n'
        f'2030,{container_cbc}/GBJC_2030_mean_Resample.tif\n'
        f'2050,{container_cbc}/GBJC_2050_mean_Resample.tif\n'
    ).encode()

    transitions_bytes  = read_local(os.path.join(preproc_root, "transitions_sample.csv"))
    biophysical_bytes  = read_local(os.path.join(preproc_root, "biophysical_table_sample.csv"))

    upload_resp = upload_files(sid, [
        ("files", "snapshots.csv",            snapshots_content, "text/csv"),
        ("files", "transitions_sample.csv",   transitions_bytes, "text/csv"),
        ("files", "biophysical_table_sample.csv", biophysical_bytes, "text/csv"),
    ])
    print(f"  Uploaded: {[f['filename'] for f in upload_resp['uploaded']]}")

    uploaded = {f["filename"]: f["path"] for f in upload_resp["uploaded"]}

    message = (
        "Please run the Coastal Blue Carbon Main Model tool with:\n"
        f"- landcover_snapshot_csv: {uploaded['snapshots.csv']}\n"
        f"- landcover_transitions_table: {uploaded['transitions_sample.csv']}\n"
        f"- biophysical_table_path: {uploaded['biophysical_table_sample.csv']}\n"
        "Run the tool now without asking for confirmation."
    )
    print(f"  Session: {sid}")
    events = stream_chat(sid, message, timeout=600)

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Tool returned error: {error_events}"

    output_files = assert_outputs_exist(sid, min_files=1)
    print("  [PASS] CBC Main")


# ── Tool 4: Seasonal Water Yield ────────────────────────────────────────────

@pytest.mark.timeout(600)
def test_e2e_seasonal_water_yield():
    """
    All input files are already mounted at /data/datainput/SeasonalWaterYield_input/.
    No uploads needed — just reference container paths directly in the chat message.
    """
    print("\n\n=== Tool 4: Seasonal Water Yield ===")
    sid = new_sid()

    swy = "/data/datainput/SeasonalWaterYield_input"

    message = (
        "Please run the Seasonal Water Yield tool with:\n"
        f"- aoi_path: {swy}/watershed_gura.shp\n"
        f"- lulc_raster_path: {swy}/land_use_gura.tif\n"
        f"- dem_raster_path: {swy}/DEM_gura.tif\n"
        f"- soil_group_path: {swy}/soil_group_gura.tif\n"
        f"- biophysical_table_path: {swy}/biophysical_table_gura_SWY.csv\n"
        f"- precip_dir: {swy}/Precipitation_monthly\n"
        f"- et0_dir: {swy}/ET0_monthly\n"
        f"- rain_events_table_path: {swy}/rain_events_gura.csv\n"
        "- threshold_flow_accumulation: 1000\n"
        "Run the tool now without asking for confirmation."
    )
    print(f"  Session: {sid}")
    events = stream_chat(sid, message, timeout=600)

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Tool returned error: {error_events}"

    output_files = assert_outputs_exist(sid, min_files=1)
    print("  [PASS] Seasonal Water Yield")


# ── Tool 6: Crop Production Regression ─────────────────────────────────────

@pytest.mark.timeout(360)
def test_e2e_crop_regression():
    """
    Upload landcover_to_crop_table.csv + crop_fertilization_rates.csv.
    landcover.tif and model_data referenced from container mounts.
    """
    print("\n\n=== Tool 6: Crop Production Regression ===")
    sid = new_sid()

    reg_demo = (
        r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
        r"\telecouplingAI-project\datainput_for_demo"
        r"\CropProductionRegression_input\sample_user_data"
    )
    table_bytes  = read_local(os.path.join(reg_demo, "landcover_to_crop_table.csv"))
    fert_bytes   = read_local(os.path.join(reg_demo, "crop_fertilization_rates.csv"))

    upload_resp = upload_files(sid, [
        ("files", "landcover_to_crop_table.csv", table_bytes, "text/csv"),
        ("files", "crop_fertilization_rates.csv", fert_bytes, "text/csv"),
    ])
    print(f"  Uploaded: {[f['filename'] for f in upload_resp['uploaded']]}")

    uploaded = {f["filename"]: f["path"] for f in upload_resp["uploaded"]}
    container_reg = "/data/datainput/CropProductionRegression_input/sample_user_data"

    message = (
        "Please run the Crop Production Regression tool with:\n"
        f"- landcover_raster_path: {container_reg}/landcover.tif\n"
        f"- landcover_to_crop_table_path: {uploaded['landcover_to_crop_table.csv']}\n"
        f"- fertilization_rate_table_path: {uploaded['crop_fertilization_rates.csv']}\n"
        "The model data path is already configured in the system.\n"
        "Run the tool now without asking for confirmation."
    )
    print(f"  Session: {sid}")
    events = stream_chat(sid, message, timeout=360)

    error_events = [e for e in events if e.get("type") == "error"]
    assert not error_events, f"Tool returned error: {error_events}"

    output_files = assert_outputs_exist(sid, min_files=1)
    print("  [PASS] Crop Regression")
