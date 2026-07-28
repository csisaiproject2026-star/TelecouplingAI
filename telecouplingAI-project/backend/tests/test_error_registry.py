"""Focused tests for structured error capture and Admin access."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from admin_errors import _preserve_evidence_atomic, router
from config import settings
from shared.error_events import (
    build_error_event,
    collect_file_metadata,
    publish_error_event,
)
from shared.error_runtime import ErrorRegistryRuntime
from shared.error_store import ErrorStore, error_store


def test_error_event_redacts_secrets_and_has_stable_fingerprint(
    monkeypatch, tmp_path
):
    source = tmp_path / "input.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(settings, "ERROR_ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "RELEASE_VERSION", "test-release")

    first = build_error_event(
        ValueError(
            "Invalid input password=hunter2 "
            "postgresql://user:db-password@database/errors "
            "Authorization: Basic dXNlcjpwYXNz "
            '"password": "json secret with spaces", '
            "POSTGRES_PASSWORD=postgres-secret "
            "ADMIN_PASSWORD_HASH=argon-secret "
            "GOOGLE_API_KEY=google-secret"
        ),
        service="celery:test",
        tool="run_test",
        session_id="csis_abc123",
        params={"input_csv": str(source), "api_key": "AIzaSecretValue123456789012345"},
        context={"authorization": "Bearer hidden-token-value"},
        traceback_text=(
            'File "/app/tools/test.py", line 42\n'
            "ValueError: invalid 123 for "
            "11111111-1111-4111-8111-111111111111"
        ),
    )
    second = build_error_event(
        ValueError("Invalid input for csis_other"),
        service="celery:test",
        tool="run_test",
        session_id="csis_other",
        params={"input_csv": str(source)},
        traceback_text=(
            'File "/app/tools/test.py", line 99\n'
            "ValueError: invalid 999 for "
            "22222222-2222-4222-8222-222222222222"
        ),
    )

    assert first["category"] == "validation"
    assert first["severity"] == "info"
    assert first["environment"] == "test"
    assert first["fingerprint"] == second["fingerprint"]
    assert first["context"]["authorization"] == "[REDACTED]"
    assert first["context"]["parameter_names"] == ["api_key", "input_csv"]
    assert first["files"] == [
        {
            "name": "input.csv",
            "extension": ".csv",
            "size_bytes": source.stat().st_size,
        }
    ]
    assert "AIza" not in json.dumps(first)
    assert "hunter2" not in json.dumps(first)
    assert "db-password" not in json.dumps(first)
    assert "dXNlcjpwYXNz" not in json.dumps(first)
    assert "json secret" not in json.dumps(first)
    assert "postgres-secret" not in json.dumps(first)
    assert "argon-secret" not in json.dumps(first)
    assert "google-secret" not in json.dumps(first)


def test_collect_file_metadata_is_bounded(monkeypatch, tmp_path):
    paths = []
    for index in range(3):
        path = tmp_path / f"{index}.csv"
        path.write_text(str(index), encoding="utf-8")
        paths.append(str(path))
    monkeypatch.setattr(settings, "ERROR_MAX_FILE_METADATA", 2)

    files = collect_file_metadata({"input_paths": paths})

    assert len(files) == 2
    assert all("source_path" not in item for item in files)


def test_publish_error_event_uses_redis_stream(monkeypatch):
    redis_client = MagicMock()
    monkeypatch.setattr(settings, "ERROR_REGISTRY_ENABLED", True)
    monkeypatch.setattr(settings, "ERROR_STREAM_KEY", "test:error-events")
    monkeypatch.setattr(settings, "ERROR_STREAM_MAXLEN", 1000)
    event = {"event_id": "event-1", "message": "safe"}

    publish_error_event(redis_client, event)

    redis_client.xadd.assert_called_once()
    args, kwargs = redis_client.xadd.call_args
    assert args[0] == "test:error-events"
    assert json.loads(args[1]["payload"]) == event
    assert kwargs["maxlen"] == 1000


@pytest.mark.asyncio
async def test_error_group_search_uses_numbered_parameters():
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=0)
    pool.fetch = AsyncMock(return_value=[])
    store = ErrorStore()
    store.pool = pool

    result = await store.list_groups(
        status="new",
        search="render",
        page=2,
        page_size=25,
    )

    count_query, *count_values = pool.fetchval.await_args.args
    list_query, *list_values = pool.fetch.await_args.args
    assert "g.last_seen >= NOW() - ($1::int" in count_query
    assert "g.title ILIKE $2" in count_query
    assert "g.error_code ILIKE $3" in count_query
    assert "g.fingerprint ILIKE $4" in count_query
    assert "g.tool ILIKE $5" in count_query
    assert "g.status = $6" in count_query
    assert count_values == [
        24,
        "%render%",
        "%render%",
        "%render%",
        "%render%",
        "new",
    ]
    assert "LIMIT $7 OFFSET $8" in list_query
    assert list_values == count_values + [25, 25]
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_stale_stream_claim_follows_redis_cursor():
    runtime = ErrorRegistryRuntime()
    runtime.redis = MagicMock()
    runtime.redis.xautoclaim = AsyncMock(
        side_effect=[
            ("21-0", [], []),
            ("42-0", [("1-0", {"payload": "{}"})], []),
            ("0-0", [("2-0", {"payload": "{}"})], []),
        ]
    )
    runtime._consume = AsyncMock()

    await runtime._claim_stale()

    assert runtime.redis.xautoclaim.await_count == 3
    assert runtime.redis.xautoclaim.await_args_list[0].kwargs["start_id"] == "0-0"
    assert runtime.redis.xautoclaim.await_args_list[1].kwargs["start_id"] == "21-0"
    assert runtime.redis.xautoclaim.await_args_list[2].kwargs["start_id"] == "42-0"
    assert runtime._consume.await_count == 2


def test_evidence_preservation_rejects_unsafe_session_id(monkeypatch, tmp_path):
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path / "outputs"))

    with pytest.raises(ValueError, match="session ID"):
        _preserve_evidence_atomic(
            {
                "event_id": "11111111-1111-4111-8111-111111111111",
                "session_id": "../../outside",
                "files": [],
            },
            evidence_root / "11111111-1111-4111-8111-111111111111",
        )

    assert not list(evidence_root.glob(".*.tmp"))


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setattr(settings, "ERROR_REGISTRY_ENABLED", True)
    monkeypatch.setattr(settings, "ADMIN_ENABLED", True)
    monkeypatch.setattr(settings, "ADMIN_COOKIE_SECURE", False)
    error_store.pool = MagicMock()
    error_store.verify_user = AsyncMock(return_value=True)
    expires = datetime.now(timezone.utc) + timedelta(hours=8)
    error_store.create_admin_session = AsyncMock(
        return_value=("session-token", "csrf-token", expires)
    )
    error_store.authenticate_admin_session = AsyncMock(
        return_value={
            "username": "admin",
            "csrf_token": "csrf-token",
            "expires_at": expires,
        }
    )
    error_store.delete_admin_session = AsyncMock()
    error_store.audit = AsyncMock()
    error_store.list_groups = AsyncMock(
        return_value={"items": [], "total": 0, "page": 1, "page_size": 50}
    )
    error_store.get_group = AsyncMock(return_value=None)
    error_store.update_group = AsyncMock(
        return_value={
            "fingerprint": "abc",
            "status": "acknowledged",
            "assignee": "admin",
            "admin_notes": "Investigating",
        }
    )
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        yield client
    error_store.pool = None


def test_admin_login_sets_http_only_cookie(admin_client):
    response = admin_client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["csrf_token"] == "csrf-token"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie


def test_admin_errors_require_login(monkeypatch, admin_client):
    error_store.authenticate_admin_session = AsyncMock(return_value=None)

    response = admin_client.get("/api/admin/errors")

    assert response.status_code == 401


def test_admin_api_can_be_disabled_separately(monkeypatch, admin_client):
    monkeypatch.setattr(settings, "ADMIN_ENABLED", False)

    response = admin_client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "correct-password"},
    )

    assert response.status_code == 404


def test_admin_update_requires_csrf(admin_client):
    admin_client.cookies.set(settings.ADMIN_COOKIE_NAME, "session-token")

    rejected = admin_client.patch(
        "/api/admin/errors/abc",
        json={
            "status": "acknowledged",
            "assignee": "admin",
            "admin_notes": "Investigating",
        },
    )
    accepted = admin_client.patch(
        "/api/admin/errors/abc",
        headers={"X-CSRF-Token": "csrf-token"},
        json={
            "status": "acknowledged",
            "assignee": "admin",
            "admin_notes": "Investigating",
        },
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "acknowledged"
