"""Deterministic capacity tests that do not call the external Gemini API."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.gemini_capacity import GeminiCapacityGate, GeminiQueueFullError


@pytest.mark.asyncio
async def test_gate_admits_200_clients_with_bounded_concurrency():
    gate = GeminiCapacityGate(
        max_concurrent=8,
        max_queue=500,
        input_tpm_limit=0,
        tpm_utilization=0.9,
        estimated_input_tokens=45_000,
    )
    active = 0
    peak_active = 0
    completed = 0
    wait_events = []
    state_lock = asyncio.Lock()

    async def on_wait(event):
        wait_events.append(event)

    async def client():
        nonlocal active, peak_active, completed
        async with gate.slot(45_000, on_wait=on_wait):
            async with state_lock:
                active += 1
                peak_active = max(peak_active, active)
            await asyncio.sleep(0.002)
            async with state_lock:
                active -= 1
                completed += 1

    await asyncio.gather(*(client() for _ in range(200)))

    snapshot = await gate.snapshot()
    assert completed == 200
    assert peak_active == 8
    assert wait_events
    assert snapshot.active == 0
    assert snapshot.waiting == 0


@pytest.mark.asyncio
async def test_gate_rejects_only_when_wait_queue_is_full():
    gate = GeminiCapacityGate(
        max_concurrent=1,
        max_queue=1,
        input_tpm_limit=0,
        tpm_utilization=1,
        estimated_input_tokens=1,
    )
    release = asyncio.Event()
    first_started = asyncio.Event()

    async def first():
        async with gate.slot(1):
            first_started.set()
            await release.wait()

    async def second():
        async with gate.slot(1):
            return

    first_task = asyncio.create_task(first())
    await first_started.wait()
    second_task = asyncio.create_task(second())
    await asyncio.sleep(0)

    with pytest.raises(GeminiQueueFullError):
        async with gate.slot(1):
            pass

    release.set()
    await asyncio.gather(first_task, second_task)


@pytest.mark.asyncio
async def test_gate_paces_requests_to_input_token_budget():
    gate = GeminiCapacityGate(
        max_concurrent=3,
        max_queue=10,
        input_tpm_limit=10,
        tpm_utilization=1,
        estimated_input_tokens=5,
        window_seconds=0.05,
    )
    started = []

    async def client():
        async with gate.slot(5):
            started.append(asyncio.get_running_loop().time())

    await asyncio.gather(client(), client(), client())

    assert len(started) == 3
    assert max(started) - min(started) >= 0.04


def test_estimate_includes_actual_assembled_request_size():
    gate = GeminiCapacityGate(
        max_concurrent=1,
        max_queue=1,
        input_tpm_limit=3_000_000,
        tpm_utilization=0.9,
        estimated_input_tokens=10,
    )

    estimate = gate.estimate_input_tokens(["x" * 900], {"tools": ["y" * 900]})

    assert estimate >= 600
