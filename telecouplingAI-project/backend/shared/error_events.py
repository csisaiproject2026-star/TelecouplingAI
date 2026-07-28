"""Structured error events shared by the API and Celery workers."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import traceback as traceback_module
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from shared.utils import sanitize_error_message

logger = logging.getLogger(__name__)

_SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|authorization|cookie|password|secret|token)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16})",
    re.IGNORECASE,
)
_AUTH_VALUE_RE = re.compile(
    r"\b(Basic|Bearer|Digest)\s+[0-9A-Za-z._~+/=-]{8,}",
    re.IGNORECASE,
)
_URL_CREDENTIAL_RE = re.compile(
    r"(?P<prefix>[a-z][a-z0-9+.-]*://[^:/@\s]+:)[^@\s/]+@",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>(?<![A-Za-z0-9_])[\"']?"
    r"(?:[A-Za-z0-9]+[_-])*"
    r"(?:api[_-]?key|authorization|cookie|database[_-]?url|dsn|"
    r"password(?:[_-]?hash)?|passwd|secret|token|access[_-]?key)"
    r"[\"']?\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s,;&}\])]+)",
    re.IGNORECASE,
)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_SESSION_RE = re.compile(r"\bcsis_[0-9A-Za-z_-]+\b")
_NUMBER_RE = re.compile(r"\b\d+\b")
_PATH_PARAMETER_RE = re.compile(
    r"(?:_path|_paths|_file|_files|_csv|_raster|_vector)$"
)
_VALID_CATEGORIES = {
    "validation",
    "application",
    "capacity",
    "external",
    "infrastructure",
}
_VALID_SEVERITIES = {"info", "warning", "error", "critical"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_text(value: str) -> str:
    value = _URL_CREDENTIAL_RE.sub(r"\g<prefix>[REDACTED]@", value)
    value = _AUTH_VALUE_RE.sub(lambda match: f"{match.group(1)} [REDACTED]", value)
    value = _SECRET_VALUE_RE.sub("[REDACTED]", value)

    def redact_assignment(match: re.Match) -> str:
        secret_value = match.group("value")
        quote = (
            secret_value[0]
            if secret_value[:1] in {'"', "'"}
            else ""
        )
        return f'{match.group("prefix")}{quote}[REDACTED]{quote}'

    return _SECRET_ASSIGNMENT_RE.sub(redact_assignment, value)


def redact_mapping(value: Any) -> Any:
    """Recursively redact secrets before context is persisted."""
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _SECRET_KEY_RE.search(str(key))
                else redact_mapping(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_mapping(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return repr(value)


def _iter_candidate_paths(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from _iter_candidate_paths(child_value, str(child_key))
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_candidate_paths(child, key)
    elif isinstance(value, str) and (
        _PATH_PARAMETER_RE.search(key)
        or value.startswith(("/data/uploads/", "/data/outputs/"))
    ):
        yield value


def collect_file_metadata(params: dict | None) -> list[dict]:
    """Collect bounded file metadata without storing file contents or hashes."""
    files = []
    seen: set[str] = set()
    for raw_path in _iter_candidate_paths(params or {}):
        try:
            path = Path(raw_path)
            resolved = str(path.resolve())
        except (OSError, RuntimeError):
            continue
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "name": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
            }
        )
        if len(files) >= settings.ERROR_MAX_FILE_METADATA:
            break
    return files


def classify_error(
    exception: BaseException,
    *,
    error_code: str | None = None,
) -> tuple[str, str]:
    """Return the default (category, severity) for an exception."""
    code = (error_code or "").upper()
    name = type(exception).__name__.lower()
    message = str(exception).lower()

    if any(
        marker in code
        for marker in ("INVALID", "MISSING", "FILE_NOT_FOUND", "UNSUPPORTED")
    ):
        return "validation", "info"
    if isinstance(exception, (ValueError, FileNotFoundError, KeyError)):
        return "validation", "info"
    if isinstance(exception, TimeoutError) or "timeout" in name or "timed out" in message:
        return "capacity", "warning"
    if any(
        marker in message
        for marker in ("gemini", "resource_exhausted", "429", "waf", "upstream")
    ):
        return "external", "warning"
    if any(
        marker in name
        for marker in ("workerlost", "connection", "operational")
    ):
        return "infrastructure", "error"
    return "application", "error"


def _fingerprint_text(
    *,
    exception_type: str,
    error_code: str,
    service: str,
    tool: str,
    internal_message: str,
    traceback_text: str,
) -> str:
    source = "|".join(
        (
            exception_type,
            error_code,
            service,
            tool,
            traceback_text or internal_message,
        )
    )
    source = _UUID_RE.sub("<uuid>", source)
    source = _SESSION_RE.sub("<session>", source)
    source = _NUMBER_RE.sub("<n>", source)
    source = re.sub(r"/data/(?:uploads|outputs)/[^/\s]+", "/data/<session>", source)
    source = re.sub(r"\s+", " ", source).strip().lower()
    return hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()


def build_error_event(
    exception: BaseException,
    *,
    service: str,
    tool: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    request_id: str | None = None,
    error_code: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    params: dict | None = None,
    context: dict | None = None,
    traceback_text: str | None = None,
) -> dict:
    """Build a redacted, versioned event suitable for Redis and JSON logs."""
    traceback_text = traceback_text or "".join(
        traceback_module.format_exception(
            type(exception), exception, exception.__traceback__
        )
    )
    inferred_category, inferred_severity = classify_error(
        exception, error_code=error_code
    )
    category = category if category in _VALID_CATEGORIES else inferred_category
    severity = severity if severity in _VALID_SEVERITIES else inferred_severity
    internal_message = _redact_text(str(exception) or type(exception).__name__)
    user_message = sanitize_error_message(internal_message)
    code = error_code or type(exception).__name__.upper()
    tool_name = tool or ""
    event = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": _utc_now(),
        "environment": settings.ERROR_ENVIRONMENT,
        "release_version": settings.RELEASE_VERSION,
        "service": service,
        "tool": tool_name,
        "session_id": session_id or "",
        "task_id": task_id or "",
        "request_id": request_id or "",
        "error_code": code,
        "category": category,
        "severity": severity,
        "exception_type": type(exception).__name__,
        "user_message": user_message,
        "internal_message": internal_message,
        "traceback": _redact_text(traceback_text)[-settings.ERROR_MAX_TRACEBACK_CHARS :],
        "context": redact_mapping(
            {
                **(context or {}),
                "parameter_names": sorted((params or {}).keys()),
            }
        ),
        "files": collect_file_metadata(params),
    }
    event["fingerprint"] = _fingerprint_text(
        exception_type=event["exception_type"],
        error_code=event["error_code"],
        service=service,
        tool=tool_name,
        internal_message=internal_message,
        traceback_text=event["traceback"],
    )
    return event


def _fallback_log(event: dict) -> None:
    logger.error("CSIS_ERROR_EVENT %s", json.dumps(event, ensure_ascii=False))


def publish_error_event(redis_client, event: dict) -> None:
    """Publish synchronously from Celery, always retaining a JSON-log fallback."""
    _fallback_log(event)
    if not settings.ERROR_REGISTRY_ENABLED:
        return
    try:
        redis_client.xadd(
            settings.ERROR_STREAM_KEY,
            {"payload": json.dumps(event, ensure_ascii=False)},
            maxlen=settings.ERROR_STREAM_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.exception("Failed to enqueue structured error event")


async def publish_error_event_async(redis_client, event: dict) -> None:
    """Publish asynchronously from FastAPI with the same fallback semantics."""
    _fallback_log(event)
    if not settings.ERROR_REGISTRY_ENABLED:
        return
    try:
        await redis_client.xadd(
            settings.ERROR_STREAM_KEY,
            {"payload": json.dumps(event, ensure_ascii=False)},
            maxlen=settings.ERROR_STREAM_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.exception("Failed to enqueue structured error event")
