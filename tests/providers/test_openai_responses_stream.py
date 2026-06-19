"""Tests for the OpenAI Responses streaming path (codex/pro models)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.models.anthropic import Message, MessagesRequest
from providers.base import ProviderConfig
from providers.openai import OpenAIProvider


def _ev(event_type: str, **kwargs) -> SimpleNamespace:
    return SimpleNamespace(type=event_type, **kwargs)


@pytest.fixture
def provider():
    return OpenAIProvider(ProviderConfig(api_key="test", enable_thinking=True))


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.transports.openai_chat.transport.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


def _request(content="hello", model="gpt-5.3-codex"):
    return MessagesRequest(
        model=model,
        max_tokens=128,
        messages=[Message(role="user", content=content)],
    )


def _patch_responses(provider, events):
    async def _stream():
        for event in events:
            yield event

    return patch.object(
        provider._client.responses,
        "create",
        new=AsyncMock(return_value=_stream()),
    )


@pytest.mark.asyncio
async def test_responses_text_stream(provider):
    events = [
        _ev("response.output_text.delta", delta="Hello"),
        _ev("response.output_text.delta", delta=" world"),
        _ev(
            "response.completed",
            response=SimpleNamespace(
                usage=SimpleNamespace(output_tokens=7), incomplete_details=None
            ),
        ),
    ]
    with _patch_responses(provider, events):
        out = [e async for e in provider.stream_response(_request())]

    joined = "".join(out)
    assert '"message_start"' in joined
    assert '"text_delta"' in joined and "Hello" in joined and " world" in joined
    assert '"end_turn"' in joined
    assert '"message_stop"' in joined


@pytest.mark.asyncio
async def test_responses_function_tool_stream(provider):
    item_added = SimpleNamespace(
        type="function_call", call_id="call_1", name="github_search", id="fc_1"
    )
    item_done = SimpleNamespace(type="function_call", arguments='{"q":"fcc"}')
    events = [
        _ev("response.output_item.added", item=item_added, output_index=0),
        _ev("response.function_call_arguments.delta", delta='{"q":', output_index=0),
        _ev("response.function_call_arguments.delta", delta='"fcc"}', output_index=0),
        _ev("response.output_item.done", item=item_done, output_index=0),
        _ev(
            "response.completed",
            response=SimpleNamespace(
                usage=SimpleNamespace(output_tokens=3), incomplete_details=None
            ),
        ),
    ]
    with _patch_responses(provider, events):
        out = [e async for e in provider.stream_response(_request())]

    joined = "".join(out)
    assert '"tool_use"' in joined
    assert "github_search" in joined and "call_1" in joined
    assert "input_json_delta" in joined and "fcc" in joined
    assert '"stop_reason": "tool_use"' in joined
    assert '"message_stop"' in joined


@pytest.mark.asyncio
async def test_responses_custom_tool_wraps_input(provider):
    item_added = SimpleNamespace(
        type="custom_tool_call", call_id="call_2", name="apply_patch"
    )
    item_done = SimpleNamespace(type="custom_tool_call", input="*** Begin Patch")
    events = [
        _ev("response.output_item.added", item=item_added, output_index=0),
        _ev(
            "response.custom_tool_call_input.delta",
            delta="*** Begin Patch",
            output_index=0,
        ),
        _ev("response.output_item.done", item=item_done, output_index=0),
        _ev(
            "response.completed",
            response=SimpleNamespace(usage=None, incomplete_details=None),
        ),
    ]
    with _patch_responses(provider, events):
        out = [e async for e in provider.stream_response(_request())]

    joined = "".join(out)
    assert "apply_patch" in joined and "call_2" in joined
    # Custom tool input is wrapped as {"input": ...} JSON for Anthropic.
    assert '\\"input\\"' in joined or '"input"' in joined


@pytest.mark.asyncio
async def test_responses_failed_event_emits_error(provider):
    events = [
        _ev(
            "response.failed",
            response=SimpleNamespace(error=SimpleNamespace(message="model exploded")),
        ),
    ]
    with _patch_responses(provider, events):
        out = [e async for e in provider.stream_response(_request())]

    joined = "".join(out)
    assert "model exploded" in joined
    assert '"message_stop"' in joined


@pytest.mark.asyncio
async def test_chat_model_does_not_use_responses_path(provider):
    """A normal chat model must NOT hit the Responses runner."""
    responses_create = AsyncMock()

    async def _chunks():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="hi", reasoning_content=None, tool_calls=None
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(completion_tokens=1, prompt_tokens=1),
        )

    with (
        patch.object(provider._client.responses, "create", responses_create),
        patch.object(
            provider._client.chat.completions, "create", new_callable=AsyncMock
        ) as chat_create,
    ):
        chat_create.return_value = _chunks()
        out = [e async for e in provider.stream_response(_request(model="gpt-4o"))]

    assert "".join(out)
    responses_create.assert_not_called()
