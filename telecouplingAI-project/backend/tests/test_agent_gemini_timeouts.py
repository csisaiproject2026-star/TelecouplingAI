"""Gemini calls cannot hold a capacity slot indefinitely."""
import asyncio
import json
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


class FakePubSub:
    def __init__(self):
        self.channel = None
        self.subscription_confirmed = False
        self.messages = []
        self.unsubscribed = False
        self.block_forever = False

    async def subscribe(self, channel):
        self.channel = channel

    async def get_message(self, *, ignore_subscribe_messages, timeout):
        assert ignore_subscribe_messages is False
        self.subscription_confirmed = True
        return {
            "type": "subscribe",
            "channel": self.channel,
            "data": 1,
        }

    async def unsubscribe(self, channel):
        assert channel == self.channel
        self.unsubscribed = True

    async def listen(self):
        yield {"type": "subscribe", "data": 1}
        for message in self.messages:
            yield {"type": "message", "data": json.dumps(message)}
        if self.block_forever:
            await asyncio.Event().wait()


class FakeRedis:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.closed = False

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_tool_subscription_exists_before_fast_dispatch(monkeypatch):
    pubsub = FakePubSub()
    redis_client = FakeRedis(pubsub)
    emitted = []

    class FastDispatcher:
        def apply_async(self, *, args, queue, task_id):
            assert pubsub.channel == f"progress:{args[2]}:{task_id}"
            assert pubsub.subscription_confirmed is True
            pubsub.messages.extend([
                {
                    "type": "tool_result",
                    "task_id": task_id,
                    "files": [{"filename": "result.csv"}],
                },
                {"type": "done", "task_id": task_id},
            ])
            return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        agent.aioredis,
        "from_url",
        lambda *args, **kwargs: redis_client,
    )

    task_id, result = await agent._dispatch_tool_and_relay(
        FastDispatcher(),
        tool_name="run_fast_tool",
        tool_input={"value": 1},
        session_id="session-1",
        queue="q_fast",
        event_callback=emitted.append,
    )

    assert result["files"] == [{"filename": "result.csv"}]
    assert [event["type"] for event in emitted] == [
        "tool_start",
        "tool_result",
        "done",
    ]
    assert all(event["task_id"] == task_id for event in emitted)
    assert pubsub.unsubscribed is True
    assert redis_client.closed is True


@pytest.mark.asyncio
async def test_tool_event_timeout_fires_without_new_pubsub_messages(monkeypatch):
    pubsub = FakePubSub()
    pubsub.block_forever = True
    redis_client = FakeRedis(pubsub)

    class Dispatcher:
        def apply_async(self, *, args, queue, task_id):
            return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        agent.aioredis,
        "from_url",
        lambda *args, **kwargs: redis_client,
    )
    monkeypatch.setattr(agent, "_TOOL_EVENT_TIMEOUT", 0.01)

    with pytest.raises(TimeoutError, match="timed out after 0.01s"):
        await agent._dispatch_tool_and_relay(
            Dispatcher(),
            tool_name="run_silent_tool",
            tool_input={},
            session_id="session-2",
            queue="q_silent",
            event_callback=lambda event: None,
        )

    assert pubsub.unsubscribed is True
    assert redis_client.closed is True
