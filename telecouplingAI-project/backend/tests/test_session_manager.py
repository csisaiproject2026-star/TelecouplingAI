"""Session capacity and continuity tests using an async in-memory Redis double."""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings
from shared import session_manager as session_module
from shared.session_manager import SessionExpiredError, SessionManager


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.commands = []

    def __getattr__(self, name):
        def enqueue(*args, **kwargs):
            self.commands.append((name, args, kwargs))
            return self
        return enqueue

    async def execute(self):
        results = []
        for name, args, kwargs in self.commands:
            results.append(await getattr(self.client, name)(*args, **kwargs))
        return results


class FakeAsyncRedis:
    def __init__(self):
        self.hashes = {}
        self.zsets = {}

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def hset(self, name, key=None, value=None, mapping=None):
        target = self.hashes.setdefault(name, {})
        if mapping is not None:
            target.update({str(k): str(v) for k, v in mapping.items()})
        elif key is not None:
            target[str(key)] = str(value)
        return 1

    async def hget(self, name, key):
        return self.hashes.get(name, {}).get(str(key))

    async def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    async def expire(self, name, ttl):
        return int(name in self.hashes)

    async def exists(self, name):
        return int(name in self.hashes)

    async def delete(self, name):
        return int(self.hashes.pop(name, None) is not None)

    async def zadd(self, name, mapping):
        self.zsets.setdefault(name, {}).update({
            str(member): float(score) for member, score in mapping.items()
        })
        return len(mapping)

    async def zcard(self, name):
        return len(self.zsets.get(name, {}))

    async def zrem(self, name, member):
        return int(self.zsets.setdefault(name, {}).pop(str(member), None) is not None)

    async def scan_iter(self, match=None, count=None):
        prefix = (match or "").removesuffix("*")
        for key in list(self.hashes):
            if key.startswith(prefix):
                yield key

    async def eval(self, script, numkeys, *args):
        keys = list(args[:numkeys])
        argv = list(args[numkeys:])
        if script == session_module._TOUCH_SCRIPT:
            session_key, index_key = keys
            session_id, now, ttl = argv
            if session_key not in self.hashes:
                await self.zrem(index_key, session_id)
                return 0
            await self.hset(session_key, "last_active", now)
            await self.expire(session_key, ttl)
            await self.zadd(index_key, {session_id: now})
            return 1

        if script == session_module._MARK_ACTIVE_SCRIPT:
            session_key, active_key = keys
            session_id, active_until = argv
            if session_key not in self.hashes:
                return 0
            await self.zadd(active_key, {session_id: active_until})
            return 1

        if script == session_module._APPEND_JSON_LIST_SCRIPT:
            session_key, index_key = keys
            session_id, field, additions_json, now, ttl, max_items = argv
            if session_key not in self.hashes:
                return 0
            values = json.loads(self.hashes[session_key].get(field, "[]"))
            values.extend(json.loads(additions_json))
            if int(max_items) > 0:
                values = values[-int(max_items):]
            await self.hset(session_key, field, json.dumps(values))
            await self.hset(session_key, "last_active", now)
            await self.expire(session_key, ttl)
            await self.zadd(index_key, {session_id: now})
            return 1

        if script == session_module._SET_JSON_FIELD_SCRIPT:
            session_key, index_key = keys
            session_id, field, value_json, now, ttl = argv
            if session_key not in self.hashes:
                return 0
            await self.hset(session_key, field, value_json)
            await self.hset(session_key, "last_active", now)
            await self.expire(session_key, ttl)
            await self.zadd(index_key, {session_id: now})
            return 1

        if script == session_module._EVICT_SCRIPT:
            index_key, active_key = keys
            max_sessions, now, prefix = int(argv[0]), float(argv[1]), argv[2]
            active = self.zsets.setdefault(active_key, {})
            for session_id, expiry in list(active.items()):
                if expiry <= now:
                    active.pop(session_id)
            active_sessions = {lease.split("|", 1)[0] for lease in active}
            evicted = []
            index = self.zsets.setdefault(index_key, {})
            while len(index) > max_sessions:
                candidates = sorted(index, key=index.get)
                victim = next((sid for sid in candidates if sid not in active_sessions), None)
                if victim is None:
                    break
                index.pop(victim)
                self.hashes.pop(f"{prefix}{victim}", None)
                evicted.append(victim)
            return evicted

        if script == session_module._DELETE_SCRIPT:
            index_key, active_key = keys
            session_id, prefix = argv
            self.hashes.pop(f"{prefix}{session_id}", None)
            self.zsets.setdefault(index_key, {}).pop(session_id, None)
            active = self.zsets.setdefault(active_key, {})
            for lease in list(active):
                if lease.startswith(f"{session_id}|"):
                    active.pop(lease)
            return 1

        if script == session_module._COUNT_SCRIPT:
            index_key, active_key = keys
            prefix = argv[0]
            index = self.zsets.setdefault(index_key, {})
            active = self.zsets.setdefault(active_key, {})
            for session_id in list(index):
                if f"{prefix}{session_id}" not in self.hashes:
                    index.pop(session_id)
            return len(index)

        raise AssertionError("Unexpected Redis script")

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_250_sessions_keep_independent_history(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MAX_SESSIONS", 500)
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path))
    manager = SessionManager(redis_client=FakeAsyncRedis())

    for index in range(250):
        session_id = f"user-{index:03d}"
        await manager.create_session(session_id)
        await manager.add_chat_turn(session_id, "user", f"marker-{index:03d}")

    assert await manager.count_sessions() == 250
    existence = await manager.sessions_exist([f"user-{index:03d}" for index in range(250)])
    assert all(existence.values())
    for index in range(250):
        history = await manager.get_chat_history(f"user-{index:03d}")
        assert history == [{"role": "user", "text": f"marker-{index:03d}"}]


@pytest.mark.asyncio
async def test_eviction_skips_in_flight_session(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MAX_SESSIONS", 3)
    monkeypatch.setattr(settings, "SESSION_ACTIVE_LEASE_SECONDS", 3600)
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path))
    client = FakeAsyncRedis()
    manager = SessionManager(redis_client=client)

    for session_id in ("active-oldest", "inactive-old", "inactive-new"):
        await manager.create_session(session_id)

    await client.zadd(session_module._SESSION_INDEX_KEY, {
        "active-oldest": 1,
        "inactive-old": 2,
        "inactive-new": 3,
    })
    await manager.mark_session_active("active-oldest")
    await manager.create_session("new-arrival")

    assert await manager.get_session("active-oldest") is not None
    assert await manager.get_session("inactive-old") is None
    assert await manager.get_session("inactive-new") is not None
    assert await manager.get_session("new-arrival") is not None
    assert await manager.count_sessions() == 3


@pytest.mark.asyncio
async def test_touch_does_not_recreate_evicted_session(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path))
    client = FakeAsyncRedis()
    manager = SessionManager(redis_client=client)
    await manager.create_session("expired")
    client.hashes.pop("session:expired")

    assert await manager.touch_session("expired") is False
    assert "session:expired" not in client.hashes
    assert await manager.count_sessions() == 0
    with pytest.raises(SessionExpiredError):
        await manager.add_uploaded_file("expired", "late.csv")
    assert "session:expired" not in client.hashes


@pytest.mark.asyncio
async def test_overlapping_stream_leases_release_independently(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MAX_SESSIONS", 2)
    monkeypatch.setattr(settings, "SHARED_DIR", str(tmp_path))
    client = FakeAsyncRedis()
    manager = SessionManager(redis_client=client)
    await manager.create_session("shared")
    await manager.create_session("other")
    await client.zadd(session_module._SESSION_INDEX_KEY, {"shared": 1, "other": 2})

    first_lease = await manager.mark_session_active("shared")
    second_lease = await manager.mark_session_active("shared")
    await manager.mark_session_inactive(first_lease)
    await manager.create_session("new")

    assert await manager.get_session("shared") is not None
    assert await manager.get_session("other") is None
    assert second_lease in client.zsets[session_module._ACTIVE_SESSION_KEY]
