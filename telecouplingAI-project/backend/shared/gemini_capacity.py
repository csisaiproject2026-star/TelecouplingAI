"""In-process Gemini admission control for the single Uvicorn API process."""
from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Awaitable, Callable

from config import settings


class GeminiQueueFullError(RuntimeError):
    """Raised when the bounded Gemini wait queue cannot accept more work."""


@dataclass(frozen=True)
class CapacitySnapshot:
    active: int
    waiting: int
    max_concurrent: int
    max_queue: int
    input_tpm_limit: int
    input_tpm_budget: int
    reserved_input_tokens_last_minute: int

    def as_dict(self) -> dict[str, int]:
        return {
            "active": self.active,
            "waiting": self.waiting,
            "max_concurrent": self.max_concurrent,
            "max_queue": self.max_queue,
            "input_tpm_limit": self.input_tpm_limit,
            "input_tpm_budget": self.input_tpm_budget,
            "reserved_input_tokens_last_minute": self.reserved_input_tokens_last_minute,
        }


WaitCallback = Callable[[dict], Awaitable[None]]


class GeminiCapacityGate:
    """Bound concurrent calls and reserve a safe share of input TPM.

    The API intentionally runs one Uvicorn process, so this gate is global for
    all chat requests. Reservations remain for the whole rolling window because
    failed API attempts can still count against quota.
    """

    def __init__(
        self,
        *,
        max_concurrent: int,
        max_queue: int,
        input_tpm_limit: int,
        tpm_utilization: float,
        estimated_input_tokens: int,
        window_seconds: float = 60.0,
    ):
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.input_tpm_limit = input_tpm_limit
        self.input_tpm_budget = int(input_tpm_limit * tpm_utilization)
        self.estimated_input_tokens = estimated_input_tokens
        self.window_seconds = window_seconds

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._state_lock = asyncio.Lock()
        self._rate_lock = asyncio.Lock()
        self._reservations: deque[tuple[float, int]] = deque()
        self._active = 0
        self._waiting = 0

    @classmethod
    def from_settings(cls) -> "GeminiCapacityGate":
        return cls(
            max_concurrent=settings.GEMINI_MAX_CONCURRENT,
            max_queue=settings.GEMINI_MAX_QUEUE,
            input_tpm_limit=settings.GEMINI_INPUT_TPM_LIMIT,
            tpm_utilization=settings.GEMINI_TPM_UTILIZATION,
            estimated_input_tokens=settings.GEMINI_ESTIMATED_INPUT_TOKENS,
        )

    def estimate_input_tokens(self, contents, config) -> int:
        """Conservatively estimate the assembled request, including tools/history."""
        payload_chars = len(repr(contents)) + len(repr(config))
        size_estimate = math.ceil(payload_chars / 3)
        estimate = max(self.estimated_input_tokens, size_estimate)
        if self.input_tpm_budget > 0:
            return min(estimate, self.input_tpm_budget)
        return estimate

    def _prune_reservations(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._reservations and self._reservations[0][0] <= cutoff:
            self._reservations.popleft()

    async def _reserve_input_tokens(
        self,
        tokens: int,
        *,
        on_wait: WaitCallback | None = None,
        queue_position: int = 0,
    ) -> float:
        if self.input_tpm_budget <= 0:
            return 0.0

        started = time.monotonic()
        notified = False
        while True:
            async with self._rate_lock:
                now = time.monotonic()
                self._prune_reservations(now)
                used = sum(reserved for _, reserved in self._reservations)
                if used + tokens <= self.input_tpm_budget:
                    self._reservations.append((now, tokens))
                    return time.monotonic() - started
                wait_seconds = max(
                    0.01,
                    self._reservations[0][0] + self.window_seconds - now,
                )
            if on_wait is not None and not notified:
                notified = True
                await on_wait({
                    "type": "capacity_wait",
                    "queue_position": queue_position,
                    "message": (
                        "The platform is pacing requests to stay within the Gemini quota. "
                        "Your request will start automatically."
                    ),
                })
            await asyncio.sleep(wait_seconds)

    async def snapshot(self) -> CapacitySnapshot:
        async with self._state_lock:
            active = self._active
            waiting = self._waiting
        async with self._rate_lock:
            self._prune_reservations(time.monotonic())
            reserved = sum(tokens for _, tokens in self._reservations)
        return CapacitySnapshot(
            active=active,
            waiting=waiting,
            max_concurrent=self.max_concurrent,
            max_queue=self.max_queue,
            input_tpm_limit=self.input_tpm_limit,
            input_tpm_budget=self.input_tpm_budget,
            reserved_input_tokens_last_minute=reserved,
        )

    @asynccontextmanager
    async def slot(
        self,
        estimated_tokens: int,
        *,
        on_wait: WaitCallback | None = None,
    ):
        async with self._state_lock:
            if self._waiting >= self.max_queue:
                raise GeminiQueueFullError(
                    "The AI request queue is full. Please retry after current work completes."
                )
            self._waiting += 1
            queue_position = self._waiting
            should_notify = (
                self._active >= self.max_concurrent
                or queue_position > self.max_concurrent
            )

        acquired = False
        admitted = False
        try:
            if should_notify and on_wait is not None:
                await on_wait({
                    "type": "capacity_wait",
                    "queue_position": queue_position,
                    "message": (
                        "The platform is handling high demand. "
                        f"Your request is queued (approximately position {queue_position}) "
                        "and will start automatically."
                    ),
                })

            await self._semaphore.acquire()
            acquired = True
            await self._reserve_input_tokens(
                estimated_tokens,
                on_wait=None if should_notify else on_wait,
                queue_position=queue_position,
            )
            async with self._state_lock:
                self._waiting -= 1
                self._active += 1
                admitted = True
            yield
        finally:
            if admitted:
                async with self._state_lock:
                    self._active -= 1
            else:
                async with self._state_lock:
                    self._waiting -= 1
            if acquired:
                self._semaphore.release()


gemini_capacity_gate = GeminiCapacityGate.from_settings()
