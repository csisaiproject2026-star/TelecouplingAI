"""
01_direct_tool_test / test_api_basics.py
API-level integration tests — no tool execution, no LLM.

Tests: health, upload, delete session, download, render zoom, chat SSE basics.

Run:
    cd Systematic_tests/AI_GCP_test
    python -m pytest 01_direct_tool_test/test_api_basics.py -v --tb=short
  or standalone:
    python 01_direct_tool_test/test_api_basics.py
"""
import io
import json
import sys
import os
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _utils import BASE_URL, new_sid

TIMEOUT = 15


# ── Helpers ───────────────────────────────────────────────────────────────────

def sse_payloads(text: str) -> list:
    result = []
    for line in text.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            try:
                result.append(json.loads(raw))
            except json.JSONDecodeError:
                result.append({"raw": raw})
    return result


# ── 1. Health ─────────────────────────────────────────────────────────────────

def test_health():
    r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── 2. Upload ─────────────────────────────────────────────────────────────────

def test_upload_single_file():
    sid = new_sid("basic")
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files=[("files", ("smoke.csv", io.BytesIO(b"col1,col2\n1,2\n"), "text/csv"))],
        headers={"X-Session-ID": sid},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sid
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["filename"] == "smoke.csv"


def test_upload_multiple_files():
    sid = new_sid("basic")
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files=[
            ("files", ("a.csv", io.BytesIO(b"a\n1\n"), "text/csv")),
            ("files", ("b.csv", io.BytesIO(b"b\n2\n"), "text/csv")),
        ],
        headers={"X-Session-ID": sid},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    assert len(r.json()["uploaded"]) == 2


def test_upload_assigns_session_id_if_missing():
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files=[("files", ("auto.csv", io.BytesIO(b"x,y\n1,2\n"), "text/csv"))],
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 4


# ── 3. Delete session ─────────────────────────────────────────────────────────

def test_delete_session():
    sid = new_sid("basic")
    r = requests.delete(f"{BASE_URL}/api/sessions/{sid}", timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "deleted"
    assert data["session_id"] == sid


# ── 4. Download ───────────────────────────────────────────────────────────────

def test_download_missing_file():
    r = requests.get(f"{BASE_URL}/download/{new_sid()}/nonexistent.csv", timeout=TIMEOUT)
    assert r.status_code == 404


def test_download_path_traversal_blocked():
    r = requests.get(f"{BASE_URL}/download/x/../../../etc/passwd", timeout=TIMEOUT)
    assert r.status_code in (400, 403, 404)


# ── 5. Chat SSE ───────────────────────────────────────────────────────────────

def test_chat_sse_returns_stream():
    sid = new_sid("basic")
    r = requests.post(
        f"{BASE_URL}/api/chat",
        data={"message": "Hello, reply with one word only."},
        headers={"X-Session-ID": sid},
        timeout=60,
        stream=False,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    payloads = sse_payloads(r.text)
    types = [p.get("type") for p in payloads if isinstance(p, dict)]
    assert "text_chunk" in types or "done" in types, f"No text_chunk or done: {payloads}"


def test_chat_sse_assigns_session_id():
    r = requests.post(
        f"{BASE_URL}/api/chat",
        data={"message": "Hi"},
        timeout=60,
        stream=False,
    )
    assert r.status_code == 200
    assert "X-Session-ID" in r.headers


# ── 6. Render zoom ────────────────────────────────────────────────────────────

def test_render_zoom_missing_file():
    r = requests.post(
        f"{BASE_URL}/api/render/zoom",
        data={
            "file_path":   "/nonexistent/path/layer.tif",
            "output_path": "/tmp/out.png",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 404


def test_render_zoom_success():
    sid = new_sid("basic")
    r = requests.post(
        f"{BASE_URL}/api/render/zoom",
        data={
            "file_path":   "/data/datainput/CoastalBlueCarbon_input/GBJC_2010_mean_Resample.tif",
            "output_path": f"/data/outputs/{sid}/render_test.png",
            "width":       "800",
            "height":      "600",
        },
        headers={"X-Session-ID": sid},
        timeout=60,
    )
    assert r.status_code == 200, f"render/zoom failed: {r.text}"
    body = r.json()
    assert "url" in body
    assert body["url"].startswith("http")


# ── 7. Celery / Redis connectivity ────────────────────────────────────────────

def test_missing_params_returns_sse_not_500():
    sid = new_sid("basic")
    r = requests.post(
        f"{BASE_URL}/api/chat",
        data={"message": "Run network analysis tool now with no files."},
        headers={"X-Session-ID": sid},
        timeout=60,
        stream=False,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("health",                     test_health),
        ("upload_single",              test_upload_single_file),
        ("upload_multiple",            test_upload_multiple_files),
        ("upload_auto_session_id",     test_upload_assigns_session_id_if_missing),
        ("delete_session",             test_delete_session),
        ("download_missing_404",       test_download_missing_file),
        ("download_traversal_blocked", test_download_path_traversal_blocked),
        ("chat_sse_stream",            test_chat_sse_returns_stream),
        ("chat_sse_auto_sid",          test_chat_sse_assigns_session_id),
        ("render_zoom_missing_404",    test_render_zoom_missing_file),
        ("render_zoom_success",        test_render_zoom_success),
        ("celery_redis_connectivity",  test_missing_params_returns_sse_not_500),
    ]

    print(f"\n{'=' * 60}")
    print(f"  API Basics Tests  →  {BASE_URL}")
    print(f"{'=' * 60}")

    passed = failed = 0
    for name, fn in tests:
        t0 = time.time()
        try:
            fn()
            elapsed = time.time() - t0
            print(f"  ✓  {name:<40}  {elapsed:.2f}s")
            passed += 1
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ✗  {name:<40}  {elapsed:.2f}s  → {e}")
            failed += 1

    print(f"\n  {passed + failed} tests: {passed} passed, {failed} failed")
    print(f"{'=' * 60}\n")
    sys.exit(0 if failed == 0 else 1)
