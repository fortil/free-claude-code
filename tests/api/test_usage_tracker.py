"""Tests for the usage tracker and the SSE usage-capture wrapper."""

from __future__ import annotations

import json

import pytest

from api.usage_tracker import UsageTracker
from core.trace import record_usage_stream


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream(chunks):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
async def test_capture_extracts_input_and_output_from_sse() -> None:
    chunks = [
        _sse(
            "message_start",
            {"message": {"usage": {"input_tokens": 120, "output_tokens": 1}}},
        ),
        _sse("content_block_delta", {"delta": {"type": "text_delta", "text": "hi"}}),
        _sse("message_delta", {"usage": {"input_tokens": 120, "output_tokens": 45}}),
        _sse("message_stop", {}),
    ]
    recorded: list[tuple] = []

    out = [
        c
        async for c in record_usage_stream(
            _stream(chunks),
            on_usage=lambda p, m, i, o: recorded.append((p, m, i, o)),
            provider_id="kimi",
            model_id="kimi-k2.7-code",
        )
    ]

    # Stream is passed through unchanged.
    assert out == chunks
    assert recorded == [("kimi", "kimi-k2.7-code", 120, 45)]


@pytest.mark.asyncio
async def test_capture_handles_split_chunks_native_style() -> None:
    """Usage events split across chunk boundaries are still parsed (native passthrough)."""
    full = _sse(
        "message_start",
        {"message": {"usage": {"input_tokens": 50, "output_tokens": 1}}},
    )
    full += _sse("message_delta", {"usage": {"output_tokens": 7}})
    # Slice mid-event to simulate a provider's raw byte chunks.
    chunks = [full[:30], full[30:80], full[80:]]
    recorded: list[tuple] = []

    async for _ in record_usage_stream(
        _stream(chunks),
        on_usage=lambda p, m, i, o: recorded.append((p, m, i, o)),
        provider_id="deepseek",
        model_id="deepseek-chat",
    ):
        pass

    assert recorded == [("deepseek", "deepseek-chat", 50, 7)]


@pytest.mark.asyncio
async def test_capture_no_usage_records_nothing() -> None:
    recorded: list[tuple] = []
    async for _ in record_usage_stream(
        _stream([_sse("ping", {})]),
        on_usage=lambda *a: recorded.append(a),
        provider_id="p",
        model_id="m",
    ):
        pass
    assert recorded == []


def test_tracker_accumulates_and_persists(tmp_path) -> None:
    path = tmp_path / "usage.json"
    tracker = UsageTracker(path=path)
    tracker.record("kimi", "kimi-k2.7-code", 100, 20)
    tracker.record("kimi", "kimi-k2.7-code", 50, 10)
    tracker.flush()

    snap = tracker.snapshot()
    model = snap["providers"]["kimi"]["models"]["kimi-k2.7-code"]
    assert model == {"input_tokens": 150, "output_tokens": 30, "requests": 2}

    # Reloads accumulated state from disk.
    reloaded = UsageTracker(path=path)
    assert reloaded.snapshot() == snap
