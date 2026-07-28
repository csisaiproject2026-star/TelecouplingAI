"""Protected Admin API for querying and managing structured errors."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import tempfile
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from config import settings
from shared.error_store import ErrorStoreUnavailable, error_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin-errors"])

_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_VALID_STATUSES = {"new", "acknowledged", "resolved", "ignored"}
_VALID_CATEGORIES = {
    "validation",
    "application",
    "capacity",
    "external",
    "infrastructure",
}
_VALID_SEVERITIES = {"info", "warning", "error", "critical"}
_SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=1000)


class ErrorGroupUpdate(BaseModel):
    status: str
    assignee: str = Field(default="", max_length=200)
    admin_notes: str = Field(default="", max_length=10000)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-real-ip", "").strip()
    if forwarded:
        return forwarded[:100]
    return request.client.host if request.client else ""


def _ensure_registry_available() -> None:
    if not settings.ADMIN_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    if not settings.ERROR_REGISTRY_ENABLED:
        raise HTTPException(status_code=503, detail="Error registry is disabled")
    if not error_store.available:
        raise HTTPException(
            status_code=503,
            detail="Error registry database is temporarily unavailable",
        )


async def require_admin(request: Request) -> dict:
    _ensure_registry_available()
    token = request.cookies.get(settings.ADMIN_COOKIE_NAME, "")
    try:
        session = await error_store.authenticate_admin_session(token)
    except ErrorStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if session is None:
        raise HTTPException(status_code=401, detail="Admin login required")
    return session


async def require_csrf(request: Request, admin: dict = Depends(require_admin)) -> dict:
    provided = request.headers.get("x-csrf-token", "")
    if not provided or provided != admin["csrf_token"]:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return admin


def _check_login_rate_limit(ip_address: str) -> None:
    now = time.monotonic()
    attempts = _login_attempts[ip_address]
    while attempts and now - attempts[0] > settings.ADMIN_LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= settings.ADMIN_LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )
    attempts.append(now)


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    _ensure_registry_available()
    ip_address = _client_ip(request)
    _check_login_rate_limit(ip_address)
    if not await error_store.verify_user(payload.username, payload.password):
        await error_store.audit(
            username=payload.username,
            action="login_failed",
            ip_address=ip_address,
        )
        await asyncio.sleep(0.35)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, csrf_token, expires_at = await error_store.create_admin_session(
        payload.username,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent", ""),
    )
    _login_attempts.pop(ip_address, None)
    response.set_cookie(
        key=settings.ADMIN_COOKIE_NAME,
        value=token,
        max_age=settings.ADMIN_SESSION_HOURS * 3600,
        httponly=True,
        secure=settings.ADMIN_COOKIE_SECURE,
        samesite="strict",
        path="/api/admin",
    )
    await error_store.audit(
        username=payload.username,
        action="login",
        ip_address=ip_address,
    )
    return {
        "username": payload.username,
        "csrf_token": csrf_token,
        "expires_at": expires_at,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    admin: dict = Depends(require_csrf),
):
    token = request.cookies.get(settings.ADMIN_COOKIE_NAME, "")
    await error_store.delete_admin_session(token)
    response.delete_cookie(
        settings.ADMIN_COOKIE_NAME,
        path="/api/admin",
    )
    await error_store.audit(
        username=admin["username"],
        action="logout",
        ip_address=_client_ip(request),
    )
    return {"status": "ok"}


@router.get("/session")
async def admin_session(admin: dict = Depends(require_admin)):
    return {
        "username": admin["username"],
        "csrf_token": admin["csrf_token"],
        "expires_at": admin["expires_at"],
    }


@router.get("/errors")
async def list_errors(
    search: str = Query(default="", max_length=300),
    environment: str = Query(default="", max_length=100),
    tool: str = Query(default="", max_length=200),
    category: str = Query(default="", max_length=50),
    severity: str = Query(default="", max_length=50),
    status: str = Query(default="", max_length=50),
    hours: int = Query(default=24, ge=1, le=24 * 365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(require_admin),
):
    if category and category not in _VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if severity and severity not in _VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="Invalid severity")
    if status and status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    return await error_store.list_groups(
        search=search,
        environment=environment,
        tool=tool,
        category=category,
        severity=severity,
        status=status,
        hours=hours,
        page=page,
        page_size=page_size,
    )


@router.get("/errors/{fingerprint}")
async def error_detail(fingerprint: str, admin: dict = Depends(require_admin)):
    result = await error_store.get_group(fingerprint)
    if result is None:
        raise HTTPException(status_code=404, detail="Error group not found")
    return result


@router.patch("/errors/{fingerprint}")
async def update_error_group(
    fingerprint: str,
    payload: ErrorGroupUpdate,
    request: Request,
    admin: dict = Depends(require_csrf),
):
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await error_store.update_group(
        fingerprint,
        status=payload.status,
        assignee=payload.assignee,
        admin_notes=payload.admin_notes,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Error group not found")
    await error_store.audit(
        username=admin["username"],
        action="update_error_group",
        target=fingerprint,
        details={
            "status": payload.status,
            "assignee": payload.assignee,
        },
        ip_address=_client_ip(request),
    )
    return result


def _tree_size(paths: list[Path]) -> int:
    total = 0
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("Evidence sources may not contain symbolic links")
            if path.is_file():
                total += path.stat().st_size
                if total > settings.ERROR_EVIDENCE_MAX_BYTES:
                    return total
    return total


def _session_source(root_value: str, session_id: str) -> Path:
    if not _SAFE_SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("The recorded session ID is not safe for evidence access")
    root = Path(root_value).resolve()
    source = (root / session_id).resolve()
    if source.parent != root:
        raise ValueError("The evidence source is outside the configured data root")
    return source


def _copy_evidence(occurrence: dict, destination: Path) -> None:
    session_id = occurrence.get("session_id", "")
    source_roots = []
    if session_id:
        source_roots = [
            ("uploads", _session_source(settings.UPLOADS_DIR, session_id)),
            ("outputs", _session_source(settings.SHARED_DIR, session_id)),
        ]
    size = _tree_size([path for _, path in source_roots])
    if size > settings.ERROR_EVIDENCE_MAX_BYTES:
        raise ValueError(
            f"Evidence is {size} bytes, above the configured preservation limit"
        )
    destination.mkdir(parents=True, exist_ok=False)
    for label, source in source_roots:
        if source.is_dir():
            shutil.copytree(source, destination / label)
    manifest = {
        key: value
        for key, value in occurrence.items()
        if key not in {"evidence_path"}
    }
    manifest["files"] = [
        {key: value for key, value in item.items() if key != "source_path"}
        for item in manifest.get("files", [])
    ]
    (destination / "error.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )


def _preserve_evidence_atomic(
    occurrence: dict,
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_dir() and (destination / "error.json").is_file():
        return
    temp_destination = destination.parent / (
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        _copy_evidence(occurrence, temp_destination)
        try:
            temp_destination.rename(destination)
        except OSError:
            if not (
                destination.is_dir()
                and (destination / "error.json").is_file()
            ):
                raise
    finally:
        if temp_destination.exists():
            shutil.rmtree(temp_destination, ignore_errors=True)


@router.post("/occurrences/{event_id}/preserve")
async def preserve_evidence(
    event_id: UUID,
    request: Request,
    admin: dict = Depends(require_csrf),
):
    event_id_text = str(event_id)
    occurrence = await error_store.get_occurrence_internal(event_id_text)
    if occurrence is None:
        raise HTTPException(status_code=404, detail="Error occurrence not found")
    if occurrence["preserved"] and occurrence["evidence_path"]:
        return {"status": "preserved", "event_id": event_id_text}
    destination = Path(settings.ERROR_EVIDENCE_DIR) / event_id_text
    try:
        await asyncio.to_thread(
            _preserve_evidence_atomic,
            occurrence,
            destination,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    await error_store.mark_preserved(event_id_text, str(destination))
    await error_store.audit(
        username=admin["username"],
        action="preserve_evidence",
        target=event_id_text,
        ip_address=_client_ip(request),
    )
    return {"status": "preserved", "event_id": event_id_text}


def _build_evidence_zip(source: Path, event_id: str) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="csis-error-download-"))
    try:
        archive_base = temp_dir / f"csis-error-{event_id}"
        archive = shutil.make_archive(str(archive_base), "zip", source)
        return Path(archive)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@router.get("/occurrences/{event_id}/evidence")
async def download_evidence(
    event_id: UUID,
    request: Request,
    admin: dict = Depends(require_admin),
):
    event_id_text = str(event_id)
    occurrence = await error_store.get_occurrence_internal(event_id_text)
    if occurrence is None:
        raise HTTPException(status_code=404, detail="Error occurrence not found")
    if not occurrence["preserved"] or not occurrence["evidence_path"]:
        raise HTTPException(
            status_code=409,
            detail="Preserve the evidence before downloading it",
        )
    source = Path(occurrence["evidence_path"]).resolve()
    evidence_root = Path(settings.ERROR_EVIDENCE_DIR).resolve()
    if source.parent != evidence_root or not source.is_dir():
        raise HTTPException(status_code=404, detail="Evidence files are unavailable")
    archive = await asyncio.to_thread(
        _build_evidence_zip,
        source,
        event_id_text,
    )
    try:
        await error_store.audit(
            username=admin["username"],
            action="download_evidence",
            target=event_id_text,
            ip_address=_client_ip(request),
        )
        return FileResponse(
            archive,
            filename=archive.name,
            media_type="application/zip",
            background=BackgroundTask(shutil.rmtree, archive.parent, True),
        )
    except Exception:
        shutil.rmtree(archive.parent, ignore_errors=True)
        raise
