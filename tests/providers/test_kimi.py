"""Tests for Kimi (Moonshot) native Anthropic Messages provider."""

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.anthropic import Message, MessagesRequest
from config.constants import ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS
from core.anthropic.native_messages_request import ANTHROPIC_MIN_THINKING_BUDGET_TOKENS
from core.http_context import set_inbound_user_agent
from core.openai_responses import OpenAIResponsesAdapter
from providers.base import ProviderConfig
from providers.defaults import KIMI_DEFAULT_BASE
from providers.exceptions import InvalidRequestError
from providers.kimi import KimiProvider

_KIMI_CODING_SUBSCRIPTION_BASE = "https://api.kimi.com/coding/v1"


@pytest.fixture(autouse=True)
def _reset_inbound_user_agent():
    """Isolate the inbound User-Agent ContextVar between tests."""
    set_inbound_user_agent(None)
    yield
    set_inbound_user_agent(None)


@pytest.fixture
def kimi_config():
    return ProviderConfig(
        api_key="test_kimi_key",
        base_url=KIMI_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    @asynccontextmanager
    async def _slot():
        yield

    with patch(
        "providers.transports.anthropic_messages.transport.GlobalRateLimiter"
    ) as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


@pytest.fixture
def kimi_provider(kimi_config):
    return KimiProvider(kimi_config)


def test_init(kimi_config):
    with patch("httpx.AsyncClient") as mock_client:
        provider = KimiProvider(kimi_config)
    assert provider._api_key == "test_kimi_key"
    assert provider._base_url == KIMI_DEFAULT_BASE
    assert mock_client.called


def test_request_headers(kimi_provider):
    h = kimi_provider._request_headers()
    assert h["Authorization"] == "Bearer test_kimi_key"
    assert h["anthropic-version"] == "2023-06-01"


def test_request_headers_omits_user_agent_when_no_inbound_context(kimi_provider):
    """No inbound UA set (e.g. startup discovery) -> no User-Agent key at all.

    httpx then sends its own honest default; FCC never fabricates a UA.
    """
    h = kimi_provider._request_headers()
    assert "User-Agent" not in h


def test_request_headers_forwards_inbound_user_agent_byte_exact(kimi_provider):
    """The inbound client's User-Agent is forwarded verbatim, never rewritten."""
    set_inbound_user_agent("claude-cli/1.2.3 (external, cli)")
    h = kimi_provider._request_headers()
    assert h["User-Agent"] == "claude-cli/1.2.3 (external, cli)"


def test_build_request_body_native(kimi_provider):
    request = MessagesRequest(
        model="kimi-k2.5",
        max_tokens=50,
        messages=[Message(role="user", content="hi")],
    )
    body = kimi_provider._build_request_body(request)
    assert body["model"] == "kimi-k2.5"
    assert body["stream"] is True
    assert body["messages"][0]["role"] == "user"


def test_build_request_body_default_max_tokens(kimi_provider):
    request = MessagesRequest(
        model="m",
        messages=[Message(role="user", content="x")],
    )
    body = kimi_provider._build_request_body(request)
    assert body["max_tokens"] == ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS


def _kimi_request(*, max_tokens, thinking):
    return MessagesRequest.model_validate(
        {
            "model": "kimi-k2.7-code",
            "max_tokens": max_tokens,
            "thinking": thinking,
            "messages": [{"role": "user", "content": "hi"}],
        }
    )


def test_build_request_body_preserves_valid_thinking_budget(kimi_provider):
    body = kimi_provider._build_request_body(
        _kimi_request(
            max_tokens=8000, thinking={"type": "enabled", "budget_tokens": 2000}
        )
    )
    assert body["thinking"] == {"type": "enabled", "budget_tokens": 2000}


def test_build_request_body_injects_min_budget_when_absent(kimi_provider):
    # Moonshot kimi-k2.7-code requires a budget on an enabled block.
    body = kimi_provider._build_request_body(
        _kimi_request(max_tokens=8000, thinking={"type": "enabled"})
    )
    assert body["thinking"] == {
        "type": "enabled",
        "budget_tokens": ANTHROPIC_MIN_THINKING_BUDGET_TOKENS,
    }


def test_build_request_body_clamps_budget_below_max_tokens(kimi_provider):
    # budget must stay strictly below max_tokens (Anthropic contract).
    body = kimi_provider._build_request_body(
        _kimi_request(
            max_tokens=1500, thinking={"type": "enabled", "budget_tokens": 5000}
        )
    )
    assert body["thinking"] == {"type": "enabled", "budget_tokens": 1499}


def test_build_request_body_drops_thinking_when_max_tokens_too_small(kimi_provider):
    # No valid budget exists when max_tokens <= the minimum; drop thinking
    # instead of emitting an Anthropic-invalid (and Moonshot-rejected) body.
    body = kimi_provider._build_request_body(
        _kimi_request(
            max_tokens=50, thinking={"type": "enabled", "budget_tokens": 1024}
        )
    )
    assert "thinking" not in body
    assert body["max_tokens"] == 50


def test_responses_reasoning_reaches_kimi_thinking_budget(kimi_provider):
    # Codex `/v1/responses` reasoning must reach Moonshot's wire body as an
    # enabled thinking block with a valid budget; otherwise kimi-k2.7-code 400s.
    payload = OpenAIResponsesAdapter().to_anthropic_payload(
        {
            "model": "kimi/kimi-k2.7-code",
            "input": "Hello",
            "reasoning": {"effort": "low"},
        }
    )
    request = MessagesRequest(**payload)
    body = kimi_provider._build_request_body(request)
    assert body["thinking"] == {
        "type": "enabled",
        "budget_tokens": ANTHROPIC_MIN_THINKING_BUDGET_TOKENS,
    }


def test_build_request_body_rejects_extra_body(kimi_provider):
    request = MessagesRequest.model_validate(
        {
            "model": "m",
            "messages": [{"role": "user", "content": "x"}],
            "extra_body": {"x": 1},
        }
    )
    with pytest.raises(InvalidRequestError, match="does not support extra_body"):
        kimi_provider._build_request_body(request)


@pytest.mark.asyncio
async def test_model_list_uses_moonshot_openai_url(kimi_provider):
    """With the default open-platform base, discovery uses the legacy OpenAI-compat URL."""
    called: dict[str, str] = {}

    async def fake_get(url: str, **_k):
        called["url"] = url
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"data": [{"id": "kimi-k2.5"}]}
        mock_resp.aclose = AsyncMock()
        return mock_resp

    kimi_provider._client.get = fake_get

    await kimi_provider.list_model_infos()

    assert called["url"] == "https://api.moonshot.ai/v1/models"


@pytest.mark.asyncio
async def test_model_list_uses_derived_url_when_base_overridden():
    """With KIMI_BASE_URL overridden to the subscription, discovery derives {base}/models."""
    config = ProviderConfig(
        api_key="test_kimi_key",
        base_url=_KIMI_CODING_SUBSCRIPTION_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )
    with patch("httpx.AsyncClient"):
        provider = KimiProvider(config)
    assert provider._base_url == _KIMI_CODING_SUBSCRIPTION_BASE

    called: dict[str, Any] = {}

    async def fake_get(url: str, **kwargs):
        called["url"] = url
        called["headers"] = kwargs.get("headers")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"data": [{"id": "k3[1m]"}]}
        mock_resp.aclose = AsyncMock()
        return mock_resp

    provider._client.get = AsyncMock(side_effect=fake_get)

    await provider.list_model_infos()

    assert called["url"] == "/models"
    assert called["headers"] == {"Authorization": "Bearer test_kimi_key"}


@pytest.mark.asyncio
async def test_send_stream_request_posts_to_overridden_subscription_base():
    """POST /messages resolves against the overridden subscription base URL."""
    config = ProviderConfig(
        api_key="test_kimi_key",
        base_url=_KIMI_CODING_SUBSCRIPTION_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )
    with patch("httpx.AsyncClient"):
        provider = KimiProvider(config)

    captured: dict[str, Any] = {}

    def fake_build_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return MagicMock()

    provider._client.build_request = MagicMock(side_effect=fake_build_request)
    provider._client.send = AsyncMock(return_value=MagicMock())

    await provider._send_stream_request({"model": "k3[1m]"})

    assert captured["method"] == "POST"
    assert captured["url"] == "/messages"
    provider._client.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_aclose(kimi_provider):
    kimi_provider._client = AsyncMock()

    await kimi_provider.cleanup()

    kimi_provider._client.aclose.assert_awaited_once()
