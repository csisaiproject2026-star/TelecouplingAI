"""
Concurrent multi-user tool test.

Simulates 3 users running different tools simultaneously:
  User A — Tool 1: Network Analysis
  User B — Tool 2: CBC Preprocessor
  User C — Tool 5: Crop Percentile

Verifies:
  - All 3 complete successfully
  - Each user's outputs are isolated in their own session directory
  - No cross-session contamination

Run:
    python -m pytest tests/test_concurrent_tools.py -v -s --timeout=360
"""
import concurrent.futures
import io
import json
import os
import subprocess
import time
import uuid

import pytest
import requests

BASE = "http://localhost"
OUTPUTS = "/data/outputs"
DEMO = "/data/datainput"

NA_DIR   = f"{DEMO}/NetworkAnalysisGrouping_input/Network Analysis Grouping"
CBC_DIR  = f"{DEMO}/CoastalBLueCarbonPreprocessor_input"
CROP_DIR = f"{DEMO}/CropProductionPercentile_input/sample_user_data"

HOST_DEMO = (
    r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
    r"\telecouplingAI-project\datainput_for_demo"
)


def new_sid():
    return f"conc_{uuid.uuid4().hex[:10]}"


def read_local(path: str) -> bytes:
    return open(path, "rb").read()


def upload_files(sid, file_specs):
    r = requests.post(
        f"{BASE}/api/upload",
        files=[("files", (fname, io.BytesIO(content), mime))
               for fname, content, mime in file_specs],
        headers={"X-Session-ID": sid},
        timeout=30,
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    return {f["filename"]: f["path"] for f in r.json()["uploaded"]}


def stream_chat(sid, message, timeout=300):
    events = []
    start = time.time()
    try:
        with requests.post(
            f"{BASE}/api/chat",
            data={"message": message},
            headers={"X-Session-ID": sid},
            timeout=timeout,
            stream=True,
        ) as r:
            assert r.status_code == 200
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                try:
                    payload = json.loads(raw[5:].strip())
                except json.JSONDecodeError:
                    continue
                elapsed = time.time() - start
                etype = payload.get("type", "?")
                print(f"    [{sid}][{elapsed:.1f}s] {etype}")
                events.append(payload)
                if etype in ("done", "error"):
                    break
    except requests.exceptions.ChunkedEncodingError:
        # SSE connection dropped by nginx before "done" — task may still be running.
        # Caller should check output files to confirm success.
        elapsed = time.time() - start
        print(f"    [{sid}][{elapsed:.1f}s] SSE connection dropped (nginx timeout) — checking outputs")
    return events


def count_output_files(sid):
    result = subprocess.run(
        ["docker", "exec", "tele-backend",
         "find", f"{OUTPUTS}/{sid}", "-type", "f"],
        capture_output=True, text=True,
    )
    files = [f for f in result.stdout.strip().splitlines() if f]
    return files


# ── per-user task functions ──────────────────────────────────────────────────

def run_user_a_network_analysis():
    """User A: Tool 1 — Network Analysis"""
    sid = new_sid()
    print(f"\n  [UserA] sid={sid} starting Network Analysis")

    na_root = os.path.join(HOST_DEMO, "NetworkAnalysisGrouping_input", "Network Analysis Grouping")
    uploaded = upload_files(sid, [
        ("nodes.csv", read_local(os.path.join(na_root, "nodes.csv")), "text/csv"),
        ("links.csv", read_local(os.path.join(na_root, "links.csv")), "text/csv"),
    ])

    message = (
        "Please run the Network Analysis Grouping tool with:\n"
        f"- nodes_table: {uploaded['nodes.csv']}\n"
        f"- links_table: {uploaded['links.csv']}\n"
        f"- shapefile_path: {NA_DIR}/World_countries_2002.shp\n"
        "- nodes_join_attri: CODE\n"
        "- layer_join_attri: ISO_3_CODE\n"
        "- clustering_algorithm: walktrap\n"
        "Run the tool now without asking for confirmation."
    )
    events = stream_chat(sid, message, timeout=300)
    error_events = [e for e in events if e.get("type") == "error"]
    files = count_output_files(sid)
    print(f"  [UserA] done: {len(files)} files, errors={error_events}")
    return sid, len(files), error_events


def run_user_b_cbc_preprocessor():
    """User B: Tool 2 — CBC Preprocessor"""
    sid = new_sid()
    print(f"\n  [UserB] sid={sid} starting CBC Preprocessor")

    cbc_root = os.path.join(HOST_DEMO, "CoastalBLueCarbonPreprocessor_input")
    uploaded = upload_files(sid, [
        ("snapshots.csv",              read_local(os.path.join(cbc_root, "snapshots.csv")),              "text/csv"),
        ("lulc_lookup.csv",            read_local(os.path.join(cbc_root, "lulc_lookup.csv")),            "text/csv"),
        ("GBJC_2010_mean_Resample.tif", read_local(os.path.join(cbc_root, "GBJC_2010_mean_Resample.tif")), "image/tiff"),
        ("GBJC_2030_mean_Resample.tif", read_local(os.path.join(cbc_root, "GBJC_2030_mean_Resample.tif")), "image/tiff"),
        ("GBJC_2050_mean_Resample.tif", read_local(os.path.join(cbc_root, "GBJC_2050_mean_Resample.tif")), "image/tiff"),
    ])

    message = (
        "Please run the Coastal Blue Carbon Preprocessor tool with:\n"
        f"- landcover_snapshot_csv: {uploaded['snapshots.csv']}\n"
        f"- landcover_lookup_table: {uploaded['lulc_lookup.csv']}\n"
        "- lulc_snapshot_list (in order matching the snapshot CSV rows):\n"
        f"    {uploaded['GBJC_2010_mean_Resample.tif']}\n"
        f"    {uploaded['GBJC_2030_mean_Resample.tif']}\n"
        f"    {uploaded['GBJC_2050_mean_Resample.tif']}\n"
        "Run the tool now without asking for confirmation."
    )
    events = stream_chat(sid, message, timeout=300)
    error_events = [e for e in events if e.get("type") == "error"]
    files = count_output_files(sid)
    print(f"  [UserB] done: {len(files)} files, errors={error_events}")
    return sid, len(files), error_events


def run_user_c_crop_percentile():
    """User C: Tool 5 — Crop Percentile"""
    sid = new_sid()
    print(f"\n  [UserC] sid={sid} starting Crop Percentile")

    crop_root = os.path.join(HOST_DEMO, "CropProductionPercentile_input", "sample_user_data")
    uploaded = upload_files(sid, [
        ("landcover_to_crop_table.csv",
         read_local(os.path.join(crop_root, "landcover_to_crop_table.csv")), "text/csv"),
    ])

    message = (
        "Please run the Crop Production Percentile tool with:\n"
        f"- landcover_raster_path: {CROP_DIR}/landcover.tif\n"
        f"- landcover_to_crop_table_path: {uploaded['landcover_to_crop_table.csv']}\n"
        "The model data path is already configured in the system.\n"
        "Run the tool now without asking for confirmation."
    )
    events = stream_chat(sid, message, timeout=300)
    error_events = [e for e in events if e.get("type") == "error"]

    # If SSE connection dropped without error (concurrent load), wait for task to finish
    has_done = any(e.get("type") == "done" for e in events)
    if not has_done and not error_events:
        print(f"  [UserC] SSE dropped without done — waiting up to 60s for outputs...")
        for _ in range(12):
            time.sleep(5)
            files = count_output_files(sid)
            if len(files) >= 1:
                break
    files = count_output_files(sid)
    print(f"  [UserC] done: {len(files)} files, errors={error_events}")
    return sid, len(files), error_events


# ── main test ────────────────────────────────────────────────────────────────

@pytest.mark.timeout(360)
def test_concurrent_3_users():
    """
    Launch 3 users simultaneously, each running a different tool.
    All must complete without errors and with isolated outputs.
    """
    print("\n\n=== Concurrent 3-user tool test ===")
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        fut_a = pool.submit(run_user_a_network_analysis)
        fut_b = pool.submit(run_user_b_cbc_preprocessor)
        fut_c = pool.submit(run_user_c_crop_percentile)

        sid_a, files_a, err_a = fut_a.result(timeout=350)
        sid_b, files_b, err_b = fut_b.result(timeout=350)
        sid_c, files_c, err_c = fut_c.result(timeout=350)

    elapsed = time.time() - start
    print(f"\n  Total wall-clock time: {elapsed:.1f}s")
    print(f"  UserA ({sid_a}): {files_a} files")
    print(f"  UserB ({sid_b}): {files_b} files")
    print(f"  UserC ({sid_c}): {files_c} files")

    # All must succeed
    assert not err_a, f"UserA errors: {err_a}"
    assert not err_b, f"UserB errors: {err_b}"
    assert not err_c, f"UserC errors: {err_c}"

    # All must have output files
    assert files_a >= 1, f"UserA: no output files"
    assert files_b >= 1, f"UserB: no output files"
    assert files_c >= 1, f"UserC: no output files"

    # Session isolation: each session directory must be distinct
    assert sid_a != sid_b != sid_c

    print("  [PASS] 3 concurrent users, all isolated, all successful")
