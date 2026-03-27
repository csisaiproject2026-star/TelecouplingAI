"""
Integration tests against live Docker stack at http://localhost.

Run AFTER docker compose up:
    pip install pytest requests httpx
    python -m pytest tests/test_integration.py -v --tb=short
"""
import io
import json
import time
import uuid

import pytest
import requests

BASE = "http://localhost"
TIMEOUT = 15


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def new_sid():
    return f"integ_{uuid.uuid4().hex[:8]}"


def sse_lines(resp):
    """Parse SSE response text into a list of data payloads."""
    payloads = []
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            raw = line[len("data:"):].strip()
            try:
                payloads.append(json.loads(raw))
            except json.JSONDecodeError:
                payloads.append({"raw": raw})
    return payloads


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

def test_health():
    r = requests.get(f"{BASE}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. Upload
# ---------------------------------------------------------------------------

def test_upload_single_file():
    sid = new_sid()
    content = b"col1,col2\n1,2\n3,4\n"
    r = requests.post(
        f"{BASE}/api/upload",
        files=[("files", ("smoke.csv", io.BytesIO(content), "text/csv"))],
        headers={"X-Session-ID": sid},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sid
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["filename"] == "smoke.csv"


def test_upload_assigns_session_id_if_missing():
    r = requests.post(
        f"{BASE}/api/upload",
        files=[("files", ("auto.csv", io.BytesIO(b"x,y\n1,2\n"), "text/csv"))],
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 4


def test_upload_multiple_files():
    sid = new_sid()
    r = requests.post(
        f"{BASE}/api/upload",
        files=[
            ("files", ("a.csv", io.BytesIO(b"a\n1\n"), "text/csv")),
            ("files", ("b.csv", io.BytesIO(b"b\n2\n"), "text/csv")),
        ],
        headers={"X-Session-ID": sid},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    assert len(r.json()["uploaded"]) == 2


# ---------------------------------------------------------------------------
# 3. Delete session
# ---------------------------------------------------------------------------

def test_delete_session():
    sid = new_sid()
    r = requests.delete(f"{BASE}/api/sessions/{sid}", timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "deleted"
    assert data["session_id"] == sid


# ---------------------------------------------------------------------------
# 4. Download — missing file → 404
# ---------------------------------------------------------------------------

def test_download_missing_file():
    r = requests.get(f"{BASE}/download/{new_sid()}/nonexistent.csv", timeout=TIMEOUT)
    assert r.status_code == 404


def test_download_path_traversal_blocked():
    r = requests.get(f"{BASE}/download/x/../../../etc/passwd", timeout=TIMEOUT)
    assert r.status_code in (400, 403, 404)


# ---------------------------------------------------------------------------
# 5. Chat SSE — simple greeting (no tools triggered)
# ---------------------------------------------------------------------------

def test_chat_sse_returns_stream():
    """Send a plain greeting — expect SSE stream with at least one text_chunk."""
    sid = new_sid()
    r = requests.post(
        f"{BASE}/api/chat",
        data={"message": "Hello, just say hi back in one word."},
        headers={"X-Session-ID": sid},
        timeout=60,
        stream=False,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    payloads = sse_lines(r)
    types = [p.get("type") for p in payloads if isinstance(p, dict)]
    assert "text_chunk" in types or "done" in types, f"Unexpected SSE payloads: {payloads}"


def test_chat_sse_assigns_session_id_if_missing():
    """No X-Session-ID header → backend assigns one and echoes it."""
    r = requests.post(
        f"{BASE}/api/chat",
        data={"message": "Hi"},
        timeout=60,
        stream=False,
    )
    assert r.status_code == 200
    assert "X-Session-ID" in r.headers


# ---------------------------------------------------------------------------
# 6. Render zoom — missing file → 404
# ---------------------------------------------------------------------------

def test_render_zoom_missing_file():
    r = requests.post(
        f"{BASE}/api/render/zoom",
        data={
            "file_path": "/nonexistent/path/layer.tif",
            "output_path": "/tmp/out.png",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 404


def test_render_zoom_success():
    """
    Render a real TIF (already mounted at /data/datainput) and verify
    the response contains a download URL.
    """
    sid = new_sid()
    r = requests.post(
        f"{BASE}/api/render/zoom",
        data={
            "file_path": "/data/datainput/CoastalBlueCarbon_input/GBJC_2010_mean_Resample.tif",
            "output_path": f"/data/outputs/{sid}/render_test.png",
            "width": "800",
            "height": "600",
        },
        headers={"X-Session-ID": sid},
        timeout=60,
    )
    assert r.status_code == 200, f"render/zoom failed: {r.text}"
    body = r.json()
    assert "url" in body, f"No 'url' in response: {body}"
    assert body["url"].startswith("http"), f"Unexpected url: {body['url']}"


def test_render_zoom_with_extent():
    """
    Render a TIF with a specific bounding box extent.
    """
    sid = new_sid()
    r = requests.post(
        f"{BASE}/api/render/zoom",
        data={
            "file_path": "/data/datainput/CoastalBlueCarbon_input/GBJC_2010_mean_Resample.tif",
            "output_path": f"/data/outputs/{sid}/render_extent.png",
            "extent": "[120.5, 29.0, 122.0, 31.0]",
            "width": "800",
            "height": "600",
        },
        headers={"X-Session-ID": sid},
        timeout=60,
    )
    assert r.status_code == 200, f"render/zoom with extent failed: {r.text}"
    body = r.json()
    assert "url" in body


# ---------------------------------------------------------------------------
# 7. Celery / Redis connectivity — submit a task that requires params check
# ---------------------------------------------------------------------------

def test_celery_missing_params_returns_error_via_sse():
    """
    Trigger a tool call with missing params.  The agent should respond via SSE
    with an error or ask for parameters — not a 500.
    """
    sid = new_sid()
    r = requests.post(
        f"{BASE}/api/chat",
        data={"message": "Run network analysis tool now with no files."},
        headers={"X-Session-ID": sid},
        timeout=60,
        stream=False,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
