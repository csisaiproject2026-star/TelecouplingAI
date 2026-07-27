"""
Tests for FastAPI endpoints in main.py.

Run:
    cd backend
    python -m pytest tests/test_api.py -v
"""
import io
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_env(monkeypatch, tmp_path):
    """Set required env vars and override dirs to tmp_path for all tests."""
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-for-testing")
    monkeypatch.setenv("SHARED_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    from config import settings
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "fake-key-for-testing")
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    os.makedirs(str(tmp_path / "outputs"), exist_ok=True)
    os.makedirs(str(tmp_path / "uploads"), exist_ok=True)


@pytest.fixture
def mock_session_manager():
    """Return a mock SessionManager that doesn't need Redis."""
    sm = MagicMock()
    sm.get_session = AsyncMock(return_value={"created_at": 0.0, "last_active": 0.0})
    sm.create_session = AsyncMock(return_value={})
    sm.touch_session = AsyncMock(return_value=True)
    sm.mark_session_active = AsyncMock(return_value=True)
    sm.mark_session_inactive = AsyncMock(return_value=None)
    sm.add_uploaded_file = AsyncMock(return_value=None)
    sm.get_uploaded_files = AsyncMock(return_value=[])
    sm.get_chat_history = AsyncMock(return_value=[])
    sm.add_chat_turn = AsyncMock(return_value=None)
    sm.add_output_files = AsyncMock(return_value=None)
    sm.delete_session = AsyncMock(return_value=None)
    sm.count_sessions = AsyncMock(return_value=1)
    sm.sessions_exist = AsyncMock(return_value={"capacity-user": True})
    sm.close = AsyncMock(return_value=None)
    return sm


@pytest.fixture
def client(mock_session_manager):
    """Create a TestClient with session_manager and startup check mocked."""
    with patch("main.get_session_manager", return_value=mock_session_manager):
        from fastapi.testclient import TestClient
        import main as _main
        # Override settings dirs to tmp values already set via env
        from config import settings
        with TestClient(_main.app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_capacity_health(client):
    resp = client.get("/health/capacity")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["release_version"]
    assert data["sessions"]["current"] == 1
    assert data["sessions"]["maximum"] >= 200
    assert data["gemini"]["max_queue"] >= 200


def test_capacity_session_probe(client):
    resp = client.post(
        "/health/capacity/sessions",
        json={"session_ids": ["capacity-user"]},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "requested": 1,
        "retained": 1,
        "missing": [],
    }


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------

def test_upload_single_file(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    os.makedirs(str(tmp_path / "uploads"), exist_ok=True)

    content = b"col1,col2\n1,2\n"
    resp = client.post(
        "/api/upload",
        files=[("files", ("test.csv", io.BytesIO(content), "text/csv"))],
        headers={"X-Session-ID": "test_session_001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test_session_001"
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["filename"] == "test.csv"


def test_upload_assigns_session_id_if_missing(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    os.makedirs(str(tmp_path / "uploads"), exist_ok=True)

    resp = client.post(
        "/api/upload",
        files=[("files", ("data.csv", io.BytesIO(b"a,b\n"), "text/csv"))],
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"].startswith("csis_")


def test_upload_multiple_files(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    os.makedirs(str(tmp_path / "uploads"), exist_ok=True)

    resp = client.post(
        "/api/upload",
        files=[
            ("files", ("a.csv", io.BytesIO(b"x\n"), "text/csv")),
            ("files", ("b.csv", io.BytesIO(b"y\n"), "text/csv")),
        ],
        headers={"X-Session-ID": "multi_sess"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["uploaded"]) == 2


# ---------------------------------------------------------------------------
# GET /download/{session_id}/{file_path}
# ---------------------------------------------------------------------------

def test_download_existing_file(client, tmp_path, monkeypatch):
    from config import settings
    shared = tmp_path / "outputs"
    shared.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "SHARED_DIR", str(shared))

    # Create a real file to serve
    session_dir = shared / "sess123"
    session_dir.mkdir()
    (session_dir / "result.csv").write_text("a,b\n1,2\n")

    resp = client.get("/download/sess123/result.csv")
    assert resp.status_code == 200
    assert b"a,b" in resp.content


def test_download_missing_file(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path / "outputs"))

    resp = client.get("/download/sess_x/nonexistent.csv")
    assert resp.status_code == 404


def test_download_path_traversal_blocked(client, tmp_path, monkeypatch):
    """Path traversal attack should return 403 or 404."""
    from config import settings
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path / "outputs"))

    resp = client.get("/download/sess/../../../etc/passwd")
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# DELETE /api/sessions/{session_id}
# ---------------------------------------------------------------------------

def test_delete_session(client):
    resp = client.delete("/api/sessions/my_session_99")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"
    assert data["session_id"] == "my_session_99"


# ---------------------------------------------------------------------------
# POST /api/chat — SSE streaming
# ---------------------------------------------------------------------------

def test_chat_sse_returns_text_chunk(client, mock_session_manager):
    """Mock the agent to emit a text_chunk and done event, verify SSE format."""

    async def fake_agent(message, session_id, files, event_callback, model=None,
                         chat_history=None, session_manager=None):
        await event_callback({"type": "text_chunk", "content": "Hello from CSIS!"})
        await event_callback({"type": "done"})

    with patch("agent.run_agent", side_effect=fake_agent):
        with patch("main.get_session_manager", return_value=mock_session_manager):
            resp = client.post(
                "/api/chat",
                data={"message": "hello"},
                headers={"X-Session-ID": "chat_test_01"},
            )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "text_chunk" in body
    assert "Hello from CSIS!" in body
    assert "done" in body


def test_chat_sse_error_event_on_agent_failure(client, mock_session_manager):
    """If agent raises, SSE should contain an error event (not a 500)."""

    async def failing_agent(message, session_id, files, event_callback, model=None,
                            chat_history=None, session_manager=None):
        raise RuntimeError("Simulated agent crash")

    with patch("agent.run_agent", side_effect=failing_agent):
        with patch("main.get_session_manager", return_value=mock_session_manager):
            resp = client.post(
                "/api/chat",
                data={"message": "crash me"},
                headers={"X-Session-ID": "chat_err_01"},
            )

    assert resp.status_code == 200  # SSE always returns 200
    body = resp.text
    assert "error" in body


def test_chat_sse_assigns_session_id_if_missing(client, mock_session_manager):
    """If no X-Session-ID header, backend should assign one and return it."""

    async def fake_agent(message, session_id, files, event_callback, model=None,
                         chat_history=None, session_manager=None):
        await event_callback({"type": "done"})

    with patch("agent.run_agent", side_effect=fake_agent):
        with patch("main.get_session_manager", return_value=mock_session_manager):
            resp = client.post("/api/chat", data={"message": "hi"})

    assert resp.status_code == 200
    assert "X-Session-ID" in resp.headers
    assert resp.headers["X-Session-ID"].startswith("csis_")


# ---------------------------------------------------------------------------
# POST /api/render/zoom
# ---------------------------------------------------------------------------

def test_render_zoom_missing_file(client):
    resp = client.post(
        "/api/render/zoom",
        data={
            "file_path": "/nonexistent/path/file.tif",
            "output_path": "/tmp/out.png",
        },
    )
    assert resp.status_code == 404


def test_render_zoom_success(client, tmp_path, monkeypatch):
    from config import settings
    shared = tmp_path / "outputs"
    shared.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "SHARED_DIR", str(shared))
    monkeypatch.setattr(settings, "FILE_SERVER_URL", "http://localhost:8001/download/")

    # Create a fake source file
    src = tmp_path / "dem.tif"
    src.write_bytes(b"fake tif content")
    out = str(shared / "out.png")

    with patch("renderers.qgis_renderer.render_file", new_callable=AsyncMock) as mock_render:
        mock_render.return_value = out
        # create the output file so path checks pass
        (shared / "out.png").write_bytes(b"fake png")

        resp = client.post(
            "/api/render/zoom",
            data={"file_path": str(src), "output_path": out},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "output_path" in data
    assert "url" in data


def test_render_zoom_with_extent(client, tmp_path, monkeypatch):
    from config import settings
    shared = tmp_path / "outputs"
    shared.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "SHARED_DIR", str(shared))
    monkeypatch.setattr(settings, "FILE_SERVER_URL", "http://localhost:8001/download/")

    src = tmp_path / "layer.shp"
    src.write_bytes(b"fake shp")
    out = str(shared / "zoomed.png")
    (shared / "zoomed.png").write_bytes(b"fake png")

    with patch("renderers.qgis_renderer.render_with_extent", new_callable=AsyncMock) as mock_re:
        mock_re.return_value = out
        resp = client.post(
            "/api/render/zoom",
            data={
                "file_path": str(src),
                "output_path": out,
                "extent": json.dumps([100.0, 20.0, 110.0, 30.0]),
            },
        )

    assert resp.status_code == 200
    assert resp.json()["output_path"] == out
