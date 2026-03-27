"""
Redis-based session manager for CSIS.
"""
from __future__ import annotations
import json
import logging
import os
import shutil
import time

import redis
from config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Redis-based session manager.
    Each session is stored in a Redis hash: key = session:{session_id}
    """

    def __init__(self):
        self.r = redis.from_url(settings.REDIS_URL)
        self.ttl = settings.SESSION_TTL_HOURS * 3600

    def create_session(self, session_id: str) -> dict:
        """Create a new session and set TTL."""
        data = {
            "created_at": str(time.time()),
            "last_active": str(time.time()),
            "tool_runs": "[]",
            "uploaded_files": "[]",
        }
        self.r.hset(f"session:{session_id}", mapping=data)
        self.r.expire(f"session:{session_id}", self.ttl)
        self._enforce_max_sessions()
        return data

    def get_session(self, session_id: str) -> dict | None:
        """Return session data dict, or None if not found."""
        raw = self.r.hgetall(f"session:{session_id}")
        if not raw:
            return None
        return {k.decode(): v.decode() for k, v in raw.items()}

    def touch_session(self, session_id: str) -> None:
        """Update last_active and renew TTL."""
        self.r.hset(f"session:{session_id}", "last_active", str(time.time()))
        self.r.expire(f"session:{session_id}", self.ttl)

    def add_tool_run(self, session_id: str, tool_name: str, task_id: str) -> None:
        """Record a tool run in the session."""
        raw = self.r.hget(f"session:{session_id}", "tool_runs")
        runs = json.loads(raw.decode()) if raw else []
        runs.append({"tool": tool_name, "task_id": task_id, "time": time.time()})
        self.r.hset(f"session:{session_id}", "tool_runs", json.dumps(runs))
        self.touch_session(session_id)

    def add_uploaded_file(self, session_id: str, file_path: str) -> None:
        """Record an uploaded file path in the session."""
        raw = self.r.hget(f"session:{session_id}", "uploaded_files")
        files = json.loads(raw.decode()) if raw else []
        files.append(file_path)
        self.r.hset(f"session:{session_id}", "uploaded_files", json.dumps(files))
        self.touch_session(session_id)

    def add_output_files(self, session_id: str, files: list[dict]) -> None:
        """Record tool output file paths in the session (for multi-turn context)."""
        raw = self.r.hget(f"session:{session_id}", "output_files")
        existing = json.loads(raw.decode()) if raw else []
        existing.extend(files)
        self.r.hset(f"session:{session_id}", "output_files", json.dumps(existing))
        self.touch_session(session_id)

    def get_output_files(self, session_id: str) -> list[dict]:
        """Return all tool output files recorded for this session."""
        raw = self.r.hget(f"session:{session_id}", "output_files")
        return json.loads(raw.decode()) if raw else []

    def delete_session(self, session_id: str) -> None:
        """Delete session and clean up output directory."""
        self.r.delete(f"session:{session_id}")
        output_dir = os.path.join(settings.SHARED_DIR, session_id)
        if os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
            logger.info(f"Cleaned up output dir for session {session_id}")

    def _enforce_max_sessions(self) -> None:
        """Evict least-recently-active sessions if total > MAX_SESSIONS."""
        keys = self.r.keys("session:*")
        if len(keys) <= settings.MAX_SESSIONS:
            return
        sessions = []
        for key in keys:
            last_active = self.r.hget(key, "last_active")
            if last_active:
                sessions.append((float(last_active.decode()), key.decode()))
        sessions.sort()
        to_evict = len(sessions) - settings.MAX_SESSIONS
        for _, key in sessions[:to_evict]:
            sid = key.replace("session:", "")
            self.delete_session(sid)
            logger.info(f"Evicted session: {sid}")
