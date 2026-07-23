from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from loguru import logger

from api import dependencies
from api.app import create_app
from api.models.anthropic import Message, MessagesRequest
from api.models.openai_responses import OpenAIResponsesRequest
from api.request_pipeline import ApiRequestPipeline
from config.logging_config import configure_logging
from config.settings import Settings
from providers.base import BaseProvider, ProviderConfig
from providers.kimi import KimiProvider


class FakeProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(ProviderConfig(api_key="test"))
        self.preflight_calls: list[tuple[Any, bool | None]] = []
        self.requests: list[Any] = []
        self.stream_kwargs: list[dict[str, Any]] = []

    def preflight_stream(
        self, request: Any, *, thinking_enabled: bool | None = None
    ) -> None:
        self.preflight_calls.append((request, thinking_enabled))

    async def cleanup(self) -> None:
        return None

    async def list_model_ids(self) -> frozenset[str]:
        return frozenset({"test-model"})

    async def stream_response(
        self,
        request: Any,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        thinking_enabled: bool | None = None,
    ) -> AsyncIterator[str]:
        self.requests.append(request)
        self.stream_kwargs.append(
            {
                "input_tokens": input_tokens,
                "request_id": request_id,
                "thinking_enabled": thinking_enabled,
            }
        )
        yield 'event: message_start\ndata: {"type":"message_start"}\n\n'
        yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'


async def _streaming_body_text(response: StreamingResponse) -> str:
    parts: list[str] = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            parts.append(chunk.decode("utf-8"))
        else:
            parts.append(str(chunk))
    return "".join(parts)


@pytest.mark.asyncio
async def test_pipeline_prompt_keyword_overrides_routed_model(monkeypatch):
    """A leading -keyword reroutes the request and is stripped from the prompt."""
    monkeypatch.setattr(
        "api.prompt_model_keyword.load_aliases",
        lambda: {"kimi2.7": "kimi/kimi-k2.7-code"},
    )
    seen: dict[str, str] = {}
    provider = FakeProvider()

    def _getter(provider_id: str) -> FakeProvider:
        seen["provider_id"] = provider_id
        return provider

    pipeline = ApiRequestPipeline(Settings(), provider_getter=_getter)
    request = MessagesRequest(
        model="nvidia_nim/test-model",
        max_tokens=100,
        messages=[Message(role="user", content="-kimi2.7 refactor this")],
    )

    response = pipeline.create_message(request)
    assert isinstance(response, StreamingResponse)
    await _streaming_body_text(response)

    # Routed to the aliased provider + downstream model, token stripped.
    assert seen["provider_id"] == "kimi"
    assert provider.requests[0].model == "kimi-k2.7-code"
    assert provider.requests[0].messages[-1].content == "refactor this"


@pytest.mark.asyncio
async def test_pipeline_active_model_persists_across_requests(monkeypatch, tmp_path):
    """A keyword sets a persisted model that later keyword-less requests reuse."""
    monkeypatch.setattr(
        "api.prompt_model_keyword.load_aliases",
        lambda: {"kimi2.7": "kimi/kimi-k2.7-code"},
    )
    from config.active_model import ActiveModelStore

    store = ActiveModelStore(path=tmp_path / "active-model.json")
    seen: list[str] = []
    provider = FakeProvider()

    def _getter(provider_id: str) -> FakeProvider:
        seen.append(provider_id)
        return provider

    pipeline = ApiRequestPipeline(
        Settings(), provider_getter=_getter, active_store=store
    )

    # Turn 1: keyword selects + persists kimi.
    r1 = pipeline.create_message(
        MessagesRequest(
            model="nvidia_nim/test-model",
            max_tokens=100,
            messages=[Message(role="user", content="-kimi2.7 start")],
        )
    )
    assert isinstance(r1, StreamingResponse)
    await _streaming_body_text(r1)

    # Turn 2: no keyword (e.g. after compaction) still routes to the persisted model.
    r2 = pipeline.create_message(
        MessagesRequest(
            model="nvidia_nim/test-model",
            max_tokens=100,
            messages=[Message(role="user", content="plain follow up")],
        )
    )
    assert isinstance(r2, StreamingResponse)
    await _streaming_body_text(r2)

    assert seen == ["kimi", "kimi"]
    assert provider.requests[0].model == "kimi-k2.7-code"
    assert provider.requests[1].model == "kimi-k2.7-code"


@pytest.mark.asyncio
async def test_pipeline_records_usage_under_active_override():
    """Usage is attributed to the active-override model, not the request's nominal one.

    Regression: a persisted -keyword (e.g. kimi-k2.6) silently routes every request
    to that model; the Usage tab must then show kimi-k2.6, which is what is really used.
    """
    recorded: list[tuple] = []

    class _Store:
        def load(self) -> str | None:
            return "kimi/kimi-k2.6"

        def save(self, model_ref: str) -> None:
            pass

        def clear(self) -> None:
            pass

    class UsageProvider(FakeProvider):
        async def stream_response(
            self,
            request: Any,
            input_tokens: int = 0,
            *,
            request_id: str | None = None,
            thinking_enabled: bool | None = None,
        ) -> AsyncIterator[str]:
            self.requests.append(request)
            yield (
                'event: message_start\ndata: {"type":"message_start",'
                '"message":{"usage":{"input_tokens":50,"output_tokens":1}}}\n\n'
            )
            yield (
                'event: message_delta\ndata: {"type":"message_delta",'
                '"usage":{"input_tokens":50,"output_tokens":9}}\n\n'
            )
            yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'

    provider = UsageProvider()
    pipeline = ApiRequestPipeline(
        Settings(),
        provider_getter=lambda _: provider,
        usage_recorder=lambda p, m, i, o: recorded.append((p, m, i, o)),
        active_store=_Store(),
    )
    # The request nominally asks for nvidia_nim/test-model, but the active override wins.
    request = MessagesRequest(
        model="nvidia_nim/test-model",
        max_tokens=100,
        messages=[Message(role="user", content="plain prompt, no keyword")],
    )

    response = pipeline.create_message(request)
    assert isinstance(response, StreamingResponse)
    await _streaming_body_text(response)

    assert recorded == [("kimi", "kimi-k2.6", 50, 9)]
    assert provider.requests[0].model == "kimi-k2.6"


@pytest.mark.asyncio
async def test_pipeline_records_token_usage():
    """A completed request reports (provider_id, provider_model, in, out) tokens."""
    recorded: list[tuple] = []

    class UsageProvider(FakeProvider):
        async def stream_response(
            self,
            request: Any,
            input_tokens: int = 0,
            *,
            request_id: str | None = None,
            thinking_enabled: bool | None = None,
        ) -> AsyncIterator[str]:
            yield (
                'event: message_start\ndata: {"type":"message_start",'
                '"message":{"usage":{"input_tokens":80,"output_tokens":1}}}\n\n'
            )
            yield (
                'event: message_delta\ndata: {"type":"message_delta",'
                '"usage":{"input_tokens":80,"output_tokens":12}}\n\n'
            )
            yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'

    provider = UsageProvider()
    pipeline = ApiRequestPipeline(
        Settings(),
        provider_getter=lambda _: provider,
        usage_recorder=lambda p, m, i, o: recorded.append((p, m, i, o)),
    )
    request = MessagesRequest(
        model="nvidia_nim/test-model",
        max_tokens=100,
        messages=[Message(role="user", content="hi")],
    )

    response = pipeline.create_message(request)
    assert isinstance(response, StreamingResponse)
    await _streaming_body_text(response)

    assert recorded == [("nvidia_nim", "test-model", 80, 12)]


@pytest.mark.asyncio
async def test_pipeline_provider_execution_passes_routed_request_and_stream_metadata():
    provider = FakeProvider()
    pipeline = ApiRequestPipeline(Settings(), provider_getter=lambda _: provider)
    request = MessagesRequest(
        model="nvidia_nim/test-model",
        max_tokens=100,
        messages=[Message(role="user", content="hi")],
    )

    response = pipeline.create_message(request)
    assert isinstance(response, StreamingResponse)

    body = await _streaming_body_text(response)
    assert "message_start" in body
    assert provider.requests[0].model == "test-model"
    assert provider.stream_kwargs[0]["input_tokens"] > 0
    assert provider.stream_kwargs[0]["request_id"].startswith("req_")
    assert provider.stream_kwargs[0]["thinking_enabled"] is True
    assert len(provider.preflight_calls) == 1


def test_pipeline_message_optimization_intercepts_before_provider_execution():
    provider_getter = MagicMock()
    pipeline = ApiRequestPipeline(Settings(), provider_getter=provider_getter)
    request = MessagesRequest(
        model="nvidia_nim/test-model",
        max_tokens=100,
        messages=[Message(role="user", content="quota check")],
    )
    optimized = object()

    with patch("api.request_pipeline.try_optimizations", return_value=optimized):
        assert pipeline.create_message(request) is optimized

    provider_getter.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_logs_active_model_and_tags_provider_stream(tmp_path):
    """The active downstream model is logged once per request and tags stream logs.

    Verifies the provider-agnostic chokepoint: a concise console line names the
    model, and every log line the provider emits while streaming carries the
    model field (works regardless of transport family).
    """
    log_file = tmp_path / "pipeline.log"
    configure_logging(str(log_file), force=True)

    class LoggingProvider(FakeProvider):
        async def stream_response(
            self,
            request: Any,
            input_tokens: int = 0,
            *,
            request_id: str | None = None,
            thinking_enabled: bool | None = None,
        ) -> AsyncIterator[str]:
            logger.debug("provider streaming a chunk")
            yield 'event: message_start\ndata: {"type":"message_start"}\n\n'
            yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'

    provider = LoggingProvider()
    pipeline = ApiRequestPipeline(Settings(), provider_getter=lambda _: provider)
    request = MessagesRequest(
        model="nvidia_nim/test-model",
        max_tokens=100,
        messages=[Message(role="user", content="hi")],
    )

    response = pipeline.create_message(request)
    assert isinstance(response, StreamingResponse)
    await _streaming_body_text(response)
    logger.complete()

    rows = [
        json.loads(line)
        for line in Path(log_file).read_text(encoding="utf-8").strip().split("\n")
        if line
    ]
    # Concise routing line names the active downstream model.
    console_rows = [
        r for r in rows if r.get("message", "").startswith("model: test-model")
    ]
    assert console_rows and console_rows[0]["model"] == "test-model"
    # The provider's own mid-stream log line is tagged with the active model.
    provider_rows = [
        r for r in rows if r.get("message") == "provider streaming a chunk"
    ]
    assert provider_rows and provider_rows[0]["model"] == "test-model"


@pytest.mark.asyncio
async def test_pipeline_passthrough_bare_name_raises_400():
    """MODEL empty + bare unmapped name -> InvalidRequestError (400), no provider call."""
    from providers.exceptions import InvalidRequestError

    settings = Settings()
    settings.model = None
    settings.model_opus = settings.model_sonnet = settings.model_haiku = None
    provider = FakeProvider()
    pipeline = ApiRequestPipeline(settings, provider_getter=lambda _: provider)
    request = MessagesRequest(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[Message(role="user", content="hi")],
    )

    with pytest.raises(InvalidRequestError) as exc_info:
        pipeline.create_message(request)

    assert exc_info.value.status_code == 400
    assert "MODEL is empty" in str(exc_info.value)
    assert provider.requests == []


@pytest.mark.asyncio
async def test_pipeline_passthrough_provider_model_streams():
    """MODEL empty + client provider/model -> routes through and streams normally."""
    settings = Settings()
    settings.model = None
    provider = FakeProvider()
    pipeline = ApiRequestPipeline(settings, provider_getter=lambda _: provider)
    request = MessagesRequest(
        model="kimi/kimi-k2.7-code",
        max_tokens=100,
        messages=[Message(role="user", content="hi")],
    )

    response = pipeline.create_message(request)
    assert isinstance(response, StreamingResponse)
    await _streaming_body_text(response)

    assert provider.requests[0].model == "kimi-k2.7-code"


@pytest.mark.asyncio
async def test_pipeline_responses_bypass_message_only_optimizations():
    provider = FakeProvider()
    pipeline = ApiRequestPipeline(Settings(), provider_getter=lambda _: provider)

    with patch(
        "api.request_pipeline.try_optimizations",
        side_effect=AssertionError("Responses must not use message optimizations"),
    ):
        response = await pipeline.create_response(
            request_data=OpenAIResponsesRequest(
                model="nvidia_nim/test-model",
                input="quota check",
            )
        )

    assert isinstance(response, StreamingResponse)
    body = await _streaming_body_text(response)
    assert "response.completed" in body
    assert provider.requests[0].messages[0].content == "quota check"


# =============================================================================
# End-to-end User-Agent forwarding guardrail (real FastAPI/ASGI stack)
#
# `get_request_pipeline` (api/routes.py) MUST stay `async def`: FastAPI runs
# sync dependencies in a threadpool, where a contextvars.ContextVar `.set()`
# is confined to that worker thread's context copy and never reaches the
# request's own asyncio task, so the inbound User-Agent would be set and
# silently discarded (the stream would see UNSET, forwarding nothing).
# Verified empirically before this test was written: a sync dependency here
# makes the assertions below fail with the httpx default UA instead of the
# forwarded one. Unit tests on KimiProvider alone can't catch this regression
# because they never go through a real FastAPI dependency-injection threadpool
# boundary -- only a TestClient hitting the real ASGI app can.
# =============================================================================


_KIMI_SUBSCRIPTION_BASE = "https://api.kimi.com/coding/v1"
_TERMINAL_SSE_BODY = (
    b"event: message_start\n"
    b'data: {"type":"message_start","message":{"usage":{"input_tokens":1,'
    b'"output_tokens":0}}}\n\n'
    b"event: message_stop\n"
    b'data: {"type":"message_stop"}\n\n'
)


@pytest.fixture
def _kimi_provider_with_captured_headers():
    """A real KimiProvider (subscription base) whose outgoing send is captured.

    Only ``httpx.AsyncClient.send`` is replaced (no network I/O); ``build_request``
    stays real so the actual httpx client-vs-request header merge runs, which is
    exactly the behavior under test (omitted key -> httpx's own default UA wins;
    present key -> it overrides the default).
    """
    config = ProviderConfig(
        api_key="test-kimi-subscription-key",
        base_url=_KIMI_SUBSCRIPTION_BASE,
        rate_limit=50,
        rate_window=60,
    )
    provider = KimiProvider(config)
    captured: list[httpx.Request] = []

    async def _fake_send(request: httpx.Request, **_kwargs: Any) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, request=request, content=_TERMINAL_SSE_BODY)

    provider._client.send = AsyncMock(side_effect=_fake_send)

    @asynccontextmanager
    async def _slot():
        yield

    with patch(
        "providers.transports.anthropic_messages.transport.GlobalRateLimiter"
    ) as mock_limiter:
        instance = mock_limiter.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield provider, captured


def _haiku_payload() -> dict[str, Any]:
    return {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "hi"}],
    }


def test_kimi_subscription_forwards_inbound_user_agent_end_to_end(
    _kimi_provider_with_captured_headers,
):
    """Haiku -> kimi/k3[1m] (subscription base): outbound UA == inbound UA, byte-exact."""
    provider, captured = _kimi_provider_with_captured_headers
    settings = Settings()
    settings.model_haiku = "kimi/k3[1m]"
    settings.kimi_base_url = _KIMI_SUBSCRIPTION_BASE
    settings.kimi_api_key = "test-kimi-subscription-key"

    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[dependencies.get_settings] = lambda: settings

    try:
        with (
            patch("api.dependencies.resolve_provider", return_value=provider),
            TestClient(app) as client,
        ):
            response = client.post(
                "/v1/messages",
                headers={"User-Agent": "claude-cli/1.2.3 (external, cli)"},
                json=_haiku_payload(),
            )

            assert response.status_code == 200
            assert len(captured) == 1
            assert (
                captured[0].headers["user-agent"] == "claude-cli/1.2.3 (external, cli)"
            )
    finally:
        app.dependency_overrides.clear()


def test_kimi_subscription_omits_user_agent_header_when_none_inbound(
    _kimi_provider_with_captured_headers,
):
    """No inbound UA -> FCC never fabricates one; httpx's own default UA is sent."""
    provider, captured = _kimi_provider_with_captured_headers
    settings = Settings()
    settings.model_haiku = "kimi/k3[1m]"
    settings.kimi_base_url = _KIMI_SUBSCRIPTION_BASE
    settings.kimi_api_key = "test-kimi-subscription-key"

    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[dependencies.get_settings] = lambda: settings

    try:
        with (
            patch("api.dependencies.resolve_provider", return_value=provider),
            TestClient(app) as client,
        ):
            del client.headers["user-agent"]

            response = client.post("/v1/messages", json=_haiku_payload())

            assert response.status_code == 200
            assert len(captured) == 1
            outgoing_ua = captured[0].headers.get("user-agent", "")
            assert outgoing_ua.startswith("python-httpx/")
            assert "claude" not in outgoing_ua.lower()
    finally:
        app.dependency_overrides.clear()
