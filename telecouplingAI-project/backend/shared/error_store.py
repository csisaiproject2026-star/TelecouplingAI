"""PostgreSQL persistence and Admin authentication for the error registry."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asyncpg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from config import settings

logger = logging.getLogger(__name__)
_password_hasher = PasswordHasher()

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS error_groups (
    fingerprint TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    service TEXT NOT NULL,
    tool TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL,
    exception_type TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    occurrence_count BIGINT NOT NULL DEFAULT 1,
    environment TEXT NOT NULL,
    release_version TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT '',
    admin_notes TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_occurrences (
    event_id UUID PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    environment TEXT NOT NULL,
    release_version TEXT NOT NULL DEFAULT '',
    service TEXT NOT NULL,
    tool TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    request_id TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    exception_type TEXT NOT NULL,
    user_message TEXT NOT NULL DEFAULT '',
    internal_message TEXT NOT NULL DEFAULT '',
    traceback TEXT NOT NULL DEFAULT '',
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    files JSONB NOT NULL DEFAULT '[]'::jsonb,
    preserved BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_path TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS error_occurrences_fingerprint_time_idx
    ON error_occurrences (fingerprint, occurred_at DESC);
CREATE INDEX IF NOT EXISTS error_occurrences_session_idx
    ON error_occurrences (session_id) WHERE session_id <> '';
CREATE INDEX IF NOT EXISTS error_groups_last_seen_idx
    ON error_groups (last_seen DESC);
CREATE INDEX IF NOT EXISTS error_groups_status_idx
    ON error_groups (status, last_seen DESC);

CREATE TABLE IF NOT EXISTS admin_users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES admin_users(username) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS admin_sessions_expiry_idx ON admin_sessions (expires_at);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    username TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS admin_audit_time_idx
    ON admin_audit_log (occurred_at DESC);
"""


class ErrorStoreUnavailable(RuntimeError):
    pass


def _as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _public_file_metadata(files: list[dict]) -> list[dict]:
    return [
        {
            key: value
            for key, value in item.items()
            if key != "source_path"
        }
        for item in files
    ]


class ErrorStore:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None
        self._connect_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self.pool is not None

    async def connect(self) -> None:
        if self.pool is not None:
            return
        if not settings.ERROR_DATABASE_URL:
            raise ErrorStoreUnavailable("ERROR_DATABASE_URL is not configured")
        async with self._connect_lock:
            if self.pool is not None:
                return
            self.pool = await asyncpg.create_pool(
                settings.ERROR_DATABASE_URL,
                min_size=1,
                max_size=settings.ERROR_DB_POOL_SIZE,
                command_timeout=30,
            )
            try:
                async with self.pool.acquire() as connection:
                    await connection.execute(_SCHEMA_SQL)
                await self._bootstrap_admin()
            except Exception:
                await self.pool.close()
                self.pool = None
                raise
            logger.info("Error registry database connected")

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def _require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise ErrorStoreUnavailable("Error registry database is unavailable")
        return self.pool

    async def _bootstrap_admin(self) -> None:
        if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD_HASH:
            logger.warning(
                "Admin bootstrap credentials are not configured; "
                "/admin/errors login will remain unavailable"
            )
            return
        pool = self._require_pool()
        await pool.execute(
            """
            INSERT INTO admin_users (username, password_hash)
            VALUES ($1, $2)
            ON CONFLICT (username) DO UPDATE SET
                password_hash=EXCLUDED.password_hash,
                active=TRUE,
                updated_at=NOW()
            """,
            settings.ADMIN_USERNAME,
            settings.ADMIN_PASSWORD_HASH,
        )

    async def ingest(self, event: dict) -> bool:
        pool = self._require_pool()
        occurred_at = datetime.fromisoformat(
            event["occurred_at"].replace("Z", "+00:00")
        )
        files = event.get("files") or []
        async with pool.acquire() as connection:
            async with connection.transaction():
                inserted = await connection.fetchval(
                    """
                    INSERT INTO error_occurrences (
                        event_id, fingerprint, occurred_at, environment,
                        release_version, service, tool, session_id, task_id,
                        request_id, error_code, category, severity,
                        exception_type, user_message, internal_message,
                        traceback, context, files
                    )
                    VALUES (
                        $1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18::jsonb,
                        $19::jsonb
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING event_id
                    """,
                    event["event_id"],
                    event["fingerprint"],
                    occurred_at,
                    event.get("environment", ""),
                    event.get("release_version", ""),
                    event.get("service", ""),
                    event.get("tool", ""),
                    event.get("session_id", ""),
                    event.get("task_id", ""),
                    event.get("request_id", ""),
                    event.get("error_code", ""),
                    event.get("category", "application"),
                    event.get("severity", "error"),
                    event.get("exception_type", "Exception"),
                    event.get("user_message", ""),
                    event.get("internal_message", ""),
                    event.get("traceback", ""),
                    _as_json(event.get("context") or {}),
                    _as_json(files),
                )
                if inserted is None:
                    return False
                title = (
                    f"{event.get('tool')}: {event.get('user_message')}"
                    if event.get("tool")
                    else event.get("user_message") or event.get("error_code")
                )
                await connection.execute(
                    """
                    INSERT INTO error_groups (
                        fingerprint, title, category, severity, service, tool,
                        error_code, exception_type, first_seen, last_seen,
                        environment, release_version
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9, $10, $11)
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        title = EXCLUDED.title,
                        category = EXCLUDED.category,
                        severity = CASE
                            WHEN error_groups.severity = 'critical' THEN 'critical'
                            WHEN EXCLUDED.severity = 'critical' THEN 'critical'
                            WHEN error_groups.severity = 'error' THEN 'error'
                            ELSE EXCLUDED.severity
                        END,
                        last_seen = GREATEST(error_groups.last_seen, EXCLUDED.last_seen),
                        occurrence_count = error_groups.occurrence_count + 1,
                        environment = EXCLUDED.environment,
                        release_version = EXCLUDED.release_version,
                        updated_at = NOW()
                    """,
                    event["fingerprint"],
                    title[:500],
                    event.get("category", "application"),
                    event.get("severity", "error"),
                    event.get("service", ""),
                    event.get("tool", ""),
                    event.get("error_code", ""),
                    event.get("exception_type", "Exception"),
                    occurred_at,
                    event.get("environment", ""),
                    event.get("release_version", ""),
                )
        return True

    async def verify_user(self, username: str, password: str) -> bool:
        pool = self._require_pool()
        row = await pool.fetchrow(
            "SELECT password_hash FROM admin_users WHERE username=$1 AND active",
            username,
        )
        if row is None:
            _password_hasher.hash(password)
            return False
        try:
            return _password_hasher.verify(row["password_hash"], password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    async def create_admin_session(
        self,
        username: str,
        *,
        ip_address: str,
        user_agent: str,
    ) -> tuple[str, str, datetime]:
        token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        csrf_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.ADMIN_SESSION_HOURS
        )
        pool = self._require_pool()
        await pool.execute(
            """
            INSERT INTO admin_sessions (
                token_hash, username, csrf_token, expires_at, ip_address, user_agent
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            token_hash,
            username,
            csrf_token,
            expires_at,
            ip_address,
            user_agent[:500],
        )
        return token, csrf_token, expires_at

    async def authenticate_admin_session(self, token: str) -> dict | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        pool = self._require_pool()
        row = await pool.fetchrow(
            """
            UPDATE admin_sessions AS s
            SET last_seen=NOW()
            FROM admin_users AS u
            WHERE s.token_hash=$1
              AND s.username=u.username
              AND s.expires_at > NOW()
              AND u.active
            RETURNING s.username, s.csrf_token, s.expires_at
            """,
            token_hash,
        )
        return dict(row) if row else None

    async def delete_admin_session(self, token: str) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await self._require_pool().execute(
            "DELETE FROM admin_sessions WHERE token_hash=$1", token_hash
        )

    async def audit(
        self,
        *,
        username: str,
        action: str,
        target: str = "",
        details: dict | None = None,
        ip_address: str = "",
    ) -> None:
        await self._require_pool().execute(
            """
            INSERT INTO admin_audit_log
                (username, action, target, details, ip_address)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            username,
            action,
            target,
            _as_json(details or {}),
            ip_address,
        )

    async def list_groups(
        self,
        *,
        search: str = "",
        environment: str = "",
        tool: str = "",
        category: str = "",
        severity: str = "",
        status: str = "",
        hours: int = 24,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        clauses = ["g.last_seen >= NOW() - ($1::int * INTERVAL '1 hour')"]
        values: list[Any] = [hours]

        def add_clause(sql: str, value: Any) -> None:
            values.append(value)
            clauses.append(sql.replace("?", f"${len(values)}"))

        if search:
            pattern = f"%{search}%"
            placeholders = []
            for _ in range(4):
                values.append(pattern)
                placeholders.append(f"${len(values)}")
            clauses.append(
                f"(g.title ILIKE {placeholders[0]} OR "
                f"g.error_code ILIKE {placeholders[1]} OR "
                f"g.fingerprint ILIKE {placeholders[2]} OR "
                f"g.tool ILIKE {placeholders[3]})"
            )
        for column, value in (
            ("environment", environment),
            ("tool", tool),
            ("category", category),
            ("severity", severity),
            ("status", status),
        ):
            if value:
                add_clause(f"g.{column} = ?", value)

        where = " AND ".join(clauses)
        pool = self._require_pool()
        total = await pool.fetchval(
            f"SELECT COUNT(*) FROM error_groups g WHERE {where}", *values
        )
        offset = (page - 1) * page_size
        values.extend([page_size, offset])
        rows = await pool.fetch(
            f"""
            SELECT g.*,
                (
                    SELECT COUNT(DISTINCT NULLIF(o.session_id, ''))
                    FROM error_occurrences o
                    WHERE o.fingerprint=g.fingerprint
                ) AS affected_sessions
            FROM error_groups g
            WHERE {where}
            ORDER BY
                CASE g.severity
                    WHEN 'critical' THEN 0
                    WHEN 'error' THEN 1
                    WHEN 'warning' THEN 2
                    ELSE 3
                END,
                g.last_seen DESC
            LIMIT ${len(values) - 1} OFFSET ${len(values)}
            """,
            *values,
        )
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_group(self, fingerprint: str) -> dict | None:
        pool = self._require_pool()
        group = await pool.fetchrow(
            "SELECT * FROM error_groups WHERE fingerprint=$1", fingerprint
        )
        if group is None:
            return None
        occurrences = await pool.fetch(
            """
            SELECT * FROM error_occurrences
            WHERE fingerprint=$1
            ORDER BY occurred_at DESC
            LIMIT 100
            """,
            fingerprint,
        )
        occurrence_items = []
        for row in occurrences:
            item = dict(row)
            if isinstance(item["context"], str):
                item["context"] = json.loads(item["context"])
            if isinstance(item["files"], str):
                item["files"] = json.loads(item["files"])
            item["files"] = _public_file_metadata(item["files"])
            occurrence_items.append(item)
        return {"group": dict(group), "occurrences": occurrence_items}

    async def update_group(
        self,
        fingerprint: str,
        *,
        status: str,
        assignee: str,
        admin_notes: str,
    ) -> dict | None:
        row = await self._require_pool().fetchrow(
            """
            UPDATE error_groups
            SET status=$2, assignee=$3, admin_notes=$4, updated_at=NOW()
            WHERE fingerprint=$1
            RETURNING *
            """,
            fingerprint,
            status,
            assignee[:200],
            admin_notes[:10000],
        )
        return dict(row) if row else None

    async def get_occurrence_internal(self, event_id: str) -> dict | None:
        row = await self._require_pool().fetchrow(
            "SELECT * FROM error_occurrences WHERE event_id=$1::uuid", event_id
        )
        if row is None:
            return None
        item = dict(row)
        for field in ("context", "files"):
            if isinstance(item[field], str):
                item[field] = json.loads(item[field])
        return item

    async def mark_preserved(self, event_id: str, evidence_path: str) -> None:
        await self._require_pool().execute(
            """
            UPDATE error_occurrences
            SET preserved=TRUE, evidence_path=$2
            WHERE event_id=$1::uuid
            """,
            event_id,
            evidence_path,
        )

    async def cleanup(self) -> None:
        pool = self._require_pool()
        await pool.execute(
            "DELETE FROM admin_sessions WHERE expires_at <= NOW()"
        )
        await pool.execute(
            """
            DELETE FROM error_occurrences
            WHERE occurred_at < NOW() - ($1::int * INTERVAL '1 day')
              AND NOT preserved
            """,
            settings.ERROR_RETENTION_DAYS,
        )
        await pool.execute(
            """
            DELETE FROM error_groups g
            WHERE NOT EXISTS (
                SELECT 1 FROM error_occurrences o
                WHERE o.fingerprint=g.fingerprint
            )
            """
        )


error_store = ErrorStore()
