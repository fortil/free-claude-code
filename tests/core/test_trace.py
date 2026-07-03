"""Structured TRACE logging assertions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from loguru import logger

from config.logging_config import configure_logging
from core.trace import (
    TRACE_PAYLOAD_BINDING,
    log_context_stream,
    trace_event,
    traced_async_stream,
)


def _json_log_rows(log_file: str) -> list[dict]:
    logger.complete()
    text = Path(log_file).read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.split("\n")]


def test_trace_payload_merged_into_json_line(tmp_path) -> None:
    log_file = str(tmp_path / "t.log")
    configure_logging(log_file, force=True)
    trace_event(stage="s", event="e.v1", source="unit", hello="world", n=42)
    row = _json_log_rows(log_file)[-1]
    assert row["trace"] is True
    assert row["stage"] == "s"
    assert row["event"] == "e.v1"
    assert row["source"] == "unit"
    assert row["hello"] == "world"
    assert row["n"] == 42
    assert TRACE_PAYLOAD_BINDING == "trace_payload"


def test_sanitize_masks_nested_api_key_strings() -> None:
    """Credential-shaped keys redact without touching normal message text."""
    from core.trace import _sanitize_trace_value

    out = _sanitize_trace_value(
        {"outer": {"api_key": "secret", "text": "visible"}},
    )
    assert out["outer"]["api_key"] == "<redacted>"
    assert out["outer"]["text"] == "visible"


@pytest.mark.asyncio
async def test_traced_async_stream_logs_completion(tmp_path) -> None:
    log_file = str(tmp_path / "complete.log")
    configure_logging(log_file, force=True)

    async def source():
        yield "hello"
        yield " world"

    chunks = [
        chunk
        async for chunk in traced_async_stream(
            source(),
            stage="egress",
            source="unit",
            complete_event="stream.completed",
            interrupted_event="stream.interrupted",
            extra={"request_id": "req_complete"},
        )
    ]

    assert chunks == ["hello", " world"]
    rows = _json_log_rows(log_file)
    completed = [row for row in rows if row.get("event") == "stream.completed"]
    assert len(completed) == 1
    assert completed[0]["request_id"] == "req_complete"
    assert completed[0]["stream_chunks"] == 2
    assert completed[0]["outcome"] == "ok"


@pytest.mark.asyncio
async def test_traced_async_stream_logs_real_exception(tmp_path) -> None:
    log_file = str(tmp_path / "error.log")
    configure_logging(log_file, force=True)

    async def source():
        yield "before"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        async for _chunk in traced_async_stream(
            source(),
            stage="egress",
            source="unit",
            complete_event="stream.completed",
            interrupted_event="stream.interrupted",
            extra={"request_id": "req_error"},
        ):
            pass

    rows = _json_log_rows(log_file)
    interrupted = [row for row in rows if row.get("event") == "stream.interrupted"]
    assert len(interrupted) == 1
    assert interrupted[0]["request_id"] == "req_error"
    assert interrupted[0]["stream_chunks"] == 1
    assert interrupted[0]["outcome"] == "error"
    assert interrupted[0]["exc_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_log_context_stream_tags_provider_log_lines(tmp_path) -> None:
    """Log lines emitted while a stream is consumed carry the active model.

    Provider-agnostic: works for any transport because it wraps the stream at
    the API chokepoint, not inside a specific provider.
    """
    log_file = str(tmp_path / "model_ctx.log")
    configure_logging(log_file, force=True)

    async def provider_stream():
        # Stand in for a provider emitting log lines mid-stream.
        logger.debug("provider emitting chunk")
        yield "hello"
        trace_event(stage="provider", event="provider.mid", source="unit")
        yield " world"

    chunks = [
        chunk
        async for chunk in log_context_stream(
            provider_stream(), model="nvidia_nim/nemotron"
        )
    ]

    assert chunks == ["hello", " world"]
    rows = _json_log_rows(log_file)
    tagged = [row for row in rows if row.get("model") == "nvidia_nim/nemotron"]
    # Both the plain debug line and the trace_event row are tagged.
    messages = {row["message"] for row in tagged}
    assert "provider emitting chunk" in messages
    assert any(row.get("event") == "provider.mid" for row in tagged)


@pytest.mark.asyncio
async def test_log_context_stream_tags_traced_completion_event(tmp_path) -> None:
    """The egress completion event emitted by traced_async_stream is tagged too.

    Mirrors the real composition in ApiRequestPipeline._provider_stream:
    log_context_stream(traced_async_stream(...), model=...).
    """
    log_file = str(tmp_path / "model_ctx_traced.log")
    configure_logging(log_file, force=True)

    async def provider_stream():
        yield "a"
        yield "b"

    traced = traced_async_stream(
        provider_stream(),
        stage="egress",
        source="unit",
        complete_event="stream.completed",
        interrupted_event="stream.interrupted",
        extra={"request_id": "req_model"},
    )

    chunks = [
        chunk async for chunk in log_context_stream(traced, model="openai/gpt-4o")
    ]

    assert chunks == ["a", "b"]
    rows = _json_log_rows(log_file)
    completed = [row for row in rows if row.get("event") == "stream.completed"]
    assert len(completed) == 1
    assert completed[0]["model"] == "openai/gpt-4o"
    assert completed[0]["request_id"] == "req_model"


@pytest.mark.asyncio
async def test_log_context_stream_clears_context_after_stream(tmp_path) -> None:
    """The model context does not leak to log lines emitted after the stream."""
    log_file = str(tmp_path / "model_ctx_clear.log")
    configure_logging(log_file, force=True)

    async def provider_stream():
        yield "x"

    async for _chunk in log_context_stream(provider_stream(), model="leaky/model"):
        pass

    logger.debug("after stream finished")

    rows = _json_log_rows(log_file)
    after = [row for row in rows if row.get("message") == "after stream finished"]
    assert len(after) == 1
    assert "model" not in after[0]


@pytest.mark.asyncio
async def test_traced_async_stream_closes_quietly_on_generator_exit(tmp_path) -> None:
    log_file = str(tmp_path / "generator_exit.log")
    configure_logging(log_file, force=True)

    async def source():
        yield "first"
        yield "second"

    stream = traced_async_stream(
        source(),
        stage="egress",
        source="unit",
        complete_event="stream.completed",
        interrupted_event="stream.interrupted",
        extra={"request_id": "req_closed"},
    )

    assert await anext(stream) == "first"
    await stream.aclose()

    rows = _json_log_rows(log_file)
    events = {row.get("event") for row in rows}
    assert "stream.completed" not in events
    assert "stream.interrupted" not in events
