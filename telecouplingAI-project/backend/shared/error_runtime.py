"""Redis Stream consumer that persists structured errors to PostgreSQL."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
import uuid

import redis.asyncio as aioredis

from config import settings
from shared.error_store import ErrorStoreUnavailable, error_store

logger = logging.getLogger(__name__)


class ErrorRegistryRuntime:
    def __init__(self) -> None:
        self.redis = None
        self.task: asyncio.Task | None = None
        self.consumer = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not settings.ERROR_REGISTRY_ENABLED or self.task is not None:
            return
        self.redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        try:
            await self.redis.xgroup_create(
                settings.ERROR_STREAM_KEY,
                settings.ERROR_STREAM_GROUP,
                id="0-0",
                mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self.task = asyncio.create_task(
            self._run(),
            name="error-registry-collector",
        )

    async def stop(self) -> None:
        self._stopping.set()
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None
        await error_store.close()

    async def _ensure_store(self) -> bool:
        if error_store.available:
            return True
        try:
            await error_store.connect()
            return True
        except Exception as exc:
            logger.warning("Error registry database unavailable: %s", exc)
            return False

    async def _ingest_message(self, message_id: str, fields: dict) -> bool:
        payload = fields.get("payload")
        if not payload:
            logger.error("Error stream message %s has no payload", message_id)
            return True
        try:
            event = json.loads(payload)
            await error_store.ingest(event)
            return True
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.exception("Invalid structured error event %s", message_id)
            return True
        except ErrorStoreUnavailable:
            return False
        except Exception:
            logger.exception("Failed to persist error event %s", message_id)
            await error_store.close()
            return False

    async def _consume(self, streams: list) -> None:
        for _, messages in streams or []:
            for message_id, fields in messages:
                if await self._ingest_message(message_id, fields):
                    await self.redis.xack(
                        settings.ERROR_STREAM_KEY,
                        settings.ERROR_STREAM_GROUP,
                        message_id,
                    )

    async def _claim_stale(self) -> None:
        try:
            start_id = "0-0"
            for _ in range(20):
                claimed = await self.redis.xautoclaim(
                    settings.ERROR_STREAM_KEY,
                    settings.ERROR_STREAM_GROUP,
                    self.consumer,
                    min_idle_time=settings.ERROR_STREAM_CLAIM_IDLE_MS,
                    start_id=start_id,
                    count=50,
                )
                next_start = claimed[0] if claimed else "0-0"
                messages = claimed[1] if len(claimed) > 1 else []
                if messages:
                    await self._consume(
                        [(settings.ERROR_STREAM_KEY, messages)]
                    )
                if next_start == "0-0":
                    break
                start_id = next_start
        except Exception:
            logger.exception("Failed to claim stale error stream messages")

    async def _run(self) -> None:
        last_cleanup = 0.0
        last_claim = 0.0
        claim_interval = max(
            5.0,
            min(60.0, settings.ERROR_STREAM_CLAIM_IDLE_MS / 1000),
        )
        while not self._stopping.is_set():
            if not await self._ensure_store():
                await asyncio.sleep(settings.ERROR_DB_RETRY_SECONDS)
                continue
            try:
                now = time.monotonic()
                if now - last_cleanup >= 3600:
                    await error_store.cleanup()
                    last_cleanup = now
                if now - last_claim >= claim_interval:
                    await self._claim_stale()
                    last_claim = now
                streams = await self.redis.xreadgroup(
                    settings.ERROR_STREAM_GROUP,
                    self.consumer,
                    {settings.ERROR_STREAM_KEY: ">"},
                    count=50,
                    block=5000,
                )
                await self._consume(streams)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error registry collector loop failed")
                await asyncio.sleep(settings.ERROR_DB_RETRY_SECONDS)


error_registry_runtime = ErrorRegistryRuntime()
