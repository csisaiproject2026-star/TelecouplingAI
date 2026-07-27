"""Gemini calls cannot hold a capacity slot indefinitely."""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent
from shared.gemini_capacity import GeminiCapacityGate


class HangingModels:
    async def generate_content(self, **kwargs):
        await asyncio.Event().wait()

    async def generate_content_stream(self, **kwargs):
        await asyncio.Event().wait()


@pytest.fixture
def bounded_gate(monkeypatch):
    gate = GeminiCapacityGate(
        max_concurrent=1,
        max_queue=1,
        input_tpm_limit=0,
        tpm_utilization=1,
        estimated_input_tokens=1,
    )
    monkeypatch.setattr(agent, "gemini_capacity_gate", gate)
    monkeypatch.setattr(agent, "_GEMINI_STALL_TIMEOUT", 0.01)
    return gate


@pytest.mark.asyncio
async def test_stream_initialization_timeout_releases_capacity_slot(bounded_gate):
    client = SimpleNamespace(aio=SimpleNamespace(models=HangingModels()))

    with pytest.raises(asyncio.TimeoutError):
        await agent._generate_streaming(
            client,
            "test-model",
            [],
            {},
            lambda event: None,
            max_retries=1,
        )

    snapshot = await bounded_gate.snapshot()
    assert snapshot.active == 0
    assert snapshot.waiting == 0


@pytest.mark.asyncio
async def test_nonstreaming_timeout_releases_capacity_slot(bounded_gate):
    client = SimpleNamespace(aio=SimpleNamespace(models=HangingModels()))

    with pytest.raises(asyncio.TimeoutError):
        await agent._generate_with_retry(
            client,
            "test-model",
            [],
            {},
            max_retries=1,
        )

    snapshot = await bounded_gate.snapshot()
    assert snapshot.active == 0
    assert snapshot.waiting == 0


@pytest.mark.asyncio
async def test_watchdog_detaches_without_leaking_capacity_or_events(
    monkeypatch,
    bounded_gate,
):
    attempts = 0
    release_cancelled = asyncio.Event()
    detached_tasks = []
    emitted = []

    async def hanging_stream(client, model_name, contents, config, emit):
        nonlocal attempts
        attempts += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            detached_tasks.append(asyncio.current_task())
            await release_cancelled.wait()
            await emit({"type": "text_chunk", "content": "stale"})
            return SimpleNamespace(), True

    async def capture_event(event):
        emitted.append(event)

    monkeypatch.setattr(agent, "_consume_gemini_stream", hanging_stream)
    monkeypatch.setattr(agent, "_GEMINI_ATTEMPT_TIMEOUT", 0.01)

    with pytest.raises(asyncio.TimeoutError):
        await agent._generate_streaming(
            SimpleNamespace(),
            "test-model",
            [],
            {},
            capture_event,
            max_retries=3,
        )

    assert attempts == 3
    await asyncio.sleep(0)
    assert len(detached_tasks) == 3
    snapshot = await bounded_gate.snapshot()
    assert snapshot.active == 0
    assert snapshot.waiting == 0
    release_cancelled.set()
    await asyncio.gather(*detached_tasks)
    assert emitted == []
