"""Async Redis-based session manager for CSIS."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid

import redis.asyncio as redis

from config import settings

logger = logging.getLogger(__name__)

_SESSION_PREFIX = "session:"
_SESSION_INDEX_KEY = "sessions:last_active"
_ACTIVE_SESSION_KEY = "sessions:active"


class SessionExpiredError(RuntimeError):
    """Raised when a mutation targets a session that no longer exists."""

_TOUCH_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    redis.call('ZREM', KEYS[2], ARGV[1])
    return 0
end
redis.call('HSET', KEYS[1], 'last_active', ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('ZADD', KEYS[2], ARGV[2], ARGV[1])
return 1
"""

_MARK_ACTIVE_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
redis.call('ZADD', KEYS[2], ARGV[2], ARGV[1])
return 1
"""

_APPEND_JSON_LIST_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
local current = redis.call('HGET', KEYS[1], ARGV[2])
local values = current and cjson.decode(current) or {}
local additions = cjson.decode(ARGV[3])
for _, item in ipairs(additions) do
    table.insert(values, item)
end
local max_items = tonumber(ARGV[6])
if max_items > 0 and #values > max_items then
    local trimmed = {}
    local start_at = #values - max_items + 1
    for index = start_at, #values do
        table.insert(trimmed, values[index])
    end
    values = trimmed
end
redis.call('HSET', KEYS[1], ARGV[2], cjson.encode(values))
redis.call('HSET', KEYS[1], 'last_active', ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
redis.call('ZADD', KEYS[2], ARGV[4], ARGV[1])
return 1
"""

_SET_JSON_FIELD_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
redis.call('HSET', KEYS[1], ARGV[2], ARGV[3])
redis.call('HSET', KEYS[1], 'last_active', ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
redis.call('ZADD', KEYS[2], ARGV[4], ARGV[1])
return 1
"""

_EVICT_SCRIPT = """
local session_index = KEYS[1]
local active_index = KEYS[2]
local max_sessions = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local prefix = ARGV[3]
local evicted = {}

redis.call('ZREMRANGEBYSCORE', active_index, '-inf', now)
local active_sessions = {}
local active_leases = redis.call('ZRANGE', active_index, 0, -1)
for _, lease in ipairs(active_leases) do
    local separator = string.find(lease, '|', 1, true)
    if separator then
        active_sessions[string.sub(lease, 1, separator - 1)] = true
    end
end

while redis.call('ZCARD', session_index) > max_sessions do
    local sessions = redis.call('ZRANGE', session_index, 0, -1)
    local victim = nil
    for _, session_id in ipairs(sessions) do
        if not active_sessions[session_id] then
            victim = session_id
            break
        end
    end
    if not victim then
        break
    end
    redis.call('ZREM', session_index, victim)
    redis.call('ZREM', active_index, victim)
    redis.call('DEL', prefix .. victim)
    table.insert(evicted, victim)
end
return evicted
"""

_DELETE_SCRIPT = """
local session_index = KEYS[1]
local active_index = KEYS[2]
local session_id = ARGV[1]
local prefix = ARGV[2]
redis.call('DEL', prefix .. session_id)
redis.call('ZREM', session_index, session_id)
local leases = redis.call('ZRANGE', active_index, 0, -1)
local lease_prefix = session_id .. '|'
for _, lease in ipairs(leases) do
    if string.sub(lease, 1, string.len(lease_prefix)) == lease_prefix then
        redis.call('ZREM', active_index, lease)
    end
end
return 1
"""

_COUNT_SCRIPT = """
local session_index = KEYS[1]
local active_index = KEYS[2]
local prefix = ARGV[1]
local sessions = redis.call('ZRANGE', session_index, 0, -1)
for _, session_id in ipairs(sessions) do
    if redis.call('EXISTS', prefix .. session_id) == 0 then
        redis.call('ZREM', session_index, session_id)
    end
end
return redis.call('ZCARD', session_index)
"""


class SessionManager:
    """Store session state in Redis hashes with indexed LRU eviction."""

    def __init__(self, redis_client=None):
        self.r = redis_client or redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        self.ttl = settings.SESSION_TTL_HOURS * 3600
        self._ready = False
        self._ready_lock = asyncio.Lock()

    async def _ensure_index(self) -> None:
        if self._ready:
            return
        async with self._ready_lock:
            if self._ready:
                return
            if await self.r.zcard(_SESSION_INDEX_KEY) == 0:
                pipe = self.r.pipeline(transaction=True)
                async for key in self.r.scan_iter(match=f"{_SESSION_PREFIX}*", count=500):
                    session_id = key[len(_SESSION_PREFIX):]
                    last_active = await self.r.hget(key, "last_active")
                    score = float(last_active) if last_active else time.time()
                    pipe.zadd(_SESSION_INDEX_KEY, {session_id: score})
                await pipe.execute()
            self._ready = True

    async def create_session(self, session_id: str) -> dict:
        """Create a new session and enforce the configured capacity."""
        await self._ensure_index()
        now = time.time()
        data = {
            "created_at": str(now),
            "last_active": str(now),
            "tool_runs": "[]",
            "uploaded_files": "[]",
        }
        pipe = self.r.pipeline(transaction=True)
        pipe.hset(f"{_SESSION_PREFIX}{session_id}", mapping=data)
        pipe.expire(f"{_SESSION_PREFIX}{session_id}", self.ttl)
        pipe.zadd(_SESSION_INDEX_KEY, {session_id: now})
        await pipe.execute()
        await self._enforce_max_sessions()
        return data

    async def get_session(self, session_id: str) -> dict | None:
        """Return session data, or None when it has expired."""
        await self._ensure_index()
        raw = await self.r.hgetall(f"{_SESSION_PREFIX}{session_id}")
        return raw or None

    async def touch_session(self, session_id: str) -> bool:
        """Renew an existing session without accidentally recreating an evicted one."""
        await self._ensure_index()
        touched = await self.r.eval(
            _TOUCH_SCRIPT,
            2,
            f"{_SESSION_PREFIX}{session_id}",
            _SESSION_INDEX_KEY,
            session_id,
            time.time(),
            self.ttl,
        )
        return bool(touched)

    async def mark_session_active(self, session_id: str) -> str | None:
        """Lease a session so LRU eviction cannot remove an in-flight SSE request."""
        await self._ensure_index()
        lease = f"{session_id}|{uuid.uuid4().hex}"
        active_until = time.time() + settings.SESSION_ACTIVE_LEASE_SECONDS
        marked = await self.r.eval(
            _MARK_ACTIVE_SCRIPT,
            2,
            f"{_SESSION_PREFIX}{session_id}",
            _ACTIVE_SESSION_KEY,
            lease,
            active_until,
        )
        return lease if marked else None

    async def mark_session_inactive(self, lease: str) -> None:
        await self.r.zrem(_ACTIVE_SESSION_KEY, lease)

    async def add_tool_run(self, session_id: str, tool_name: str, task_id: str) -> None:
        await self._append_json_list(
            session_id,
            "tool_runs",
            [{"tool": tool_name, "task_id": task_id, "time": time.time()}],
        )

    async def add_uploaded_file(self, session_id: str, file_path: str) -> None:
        await self._append_json_list(session_id, "uploaded_files", [file_path])

    async def add_output_files(self, session_id: str, files: list[dict]) -> None:
        await self._append_json_list(session_id, "output_files", files)

    async def get_output_files(self, session_id: str) -> list[dict]:
        raw = await self.r.hget(f"{_SESSION_PREFIX}{session_id}", "output_files")
        return json.loads(raw) if raw else []

    async def set_workflow_plan(self, session_id: str, plan: dict | None) -> None:
        await self._set_json_field(session_id, "workflow_plan", plan)

    async def get_workflow_plan(self, session_id: str) -> dict | None:
        raw = await self.r.hget(f"{_SESSION_PREFIX}{session_id}", "workflow_plan")
        return json.loads(raw) if raw else None

    async def set_workflow_scope(self, session_id: str, scope: dict) -> None:
        await self._set_json_field(session_id, "workflow_scope", scope)

    async def get_workflow_scope(self, session_id: str) -> dict | None:
        raw = await self.r.hget(f"{_SESSION_PREFIX}{session_id}", "workflow_scope")
        return json.loads(raw) if raw else None

    async def add_chat_turn(self, session_id: str, role: str, text: str) -> None:
        if not text.strip():
            return
        await self._append_json_list(
            session_id,
            "chat_history",
            [{"role": role, "text": text}],
            max_items=40,
        )

    async def get_chat_history(self, session_id: str) -> list[dict]:
        raw = await self.r.hget(f"{_SESSION_PREFIX}{session_id}", "chat_history")
        return json.loads(raw) if raw else []

    async def get_uploaded_files(self, session_id: str) -> list[dict]:
        raw = await self.r.hget(f"{_SESSION_PREFIX}{session_id}", "uploaded_files")
        paths = json.loads(raw) if raw else []
        return [{"filename": os.path.basename(path), "path": path} for path in paths]

    async def delete_session(self, session_id: str) -> None:
        await self._ensure_index()
        await self.r.eval(
            _DELETE_SCRIPT,
            2,
            _SESSION_INDEX_KEY,
            _ACTIVE_SESSION_KEY,
            session_id,
            _SESSION_PREFIX,
        )
        await self._cleanup_output_dir(session_id)

    async def count_sessions(self) -> int:
        await self._ensure_index()
        return int(await self.r.eval(
            _COUNT_SCRIPT,
            2,
            _SESSION_INDEX_KEY,
            _ACTIVE_SESSION_KEY,
            _SESSION_PREFIX,
        ))

    async def sessions_exist(self, session_ids: list[str]) -> dict[str, bool]:
        await self._ensure_index()
        pipe = self.r.pipeline(transaction=False)
        for session_id in session_ids:
            pipe.exists(f"{_SESSION_PREFIX}{session_id}")
        results = await pipe.execute()
        return {
            session_id: bool(exists)
            for session_id, exists in zip(session_ids, results)
        }

    async def close(self) -> None:
        await self.r.aclose()

    async def _append_json_list(
        self,
        session_id: str,
        field: str,
        additions: list,
        *,
        max_items: int = 0,
    ) -> None:
        await self._ensure_index()
        updated = await self.r.eval(
            _APPEND_JSON_LIST_SCRIPT,
            2,
            f"{_SESSION_PREFIX}{session_id}",
            _SESSION_INDEX_KEY,
            session_id,
            field,
            json.dumps(additions),
            time.time(),
            self.ttl,
            max_items,
        )
        if not updated:
            raise SessionExpiredError(f"Session expired: {session_id}")

    async def _set_json_field(self, session_id: str, field: str, value) -> None:
        await self._ensure_index()
        updated = await self.r.eval(
            _SET_JSON_FIELD_SCRIPT,
            2,
            f"{_SESSION_PREFIX}{session_id}",
            _SESSION_INDEX_KEY,
            session_id,
            field,
            json.dumps(value),
            time.time(),
            self.ttl,
        )
        if not updated:
            raise SessionExpiredError(f"Session expired: {session_id}")

    async def _enforce_max_sessions(self) -> None:
        evicted = await self.r.eval(
            _EVICT_SCRIPT,
            2,
            _SESSION_INDEX_KEY,
            _ACTIVE_SESSION_KEY,
            settings.MAX_SESSIONS,
            time.time(),
            _SESSION_PREFIX,
        )
        for session_id in evicted:
            await self._cleanup_output_dir(session_id)
            logger.info("Evicted inactive session: %s", session_id)

    async def _cleanup_output_dir(self, session_id: str) -> None:
        output_dir = os.path.join(settings.SHARED_DIR, session_id)
        if os.path.isdir(output_dir):
            await asyncio.to_thread(shutil.rmtree, output_dir, True)
            logger.info("Cleaned up output dir for session %s", session_id)
