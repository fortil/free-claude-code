from unittest.mock import patch

import pytest

from api.model_router import ModelRouter
from api.models.anthropic import Message, MessagesRequest, TokenCountRequest
from config.settings import Settings
from providers.exceptions import InvalidRequestError


@pytest.fixture
def settings():
    settings = Settings()
    settings.model = "nvidia_nim/fallback-model"
    settings.model_opus = None
    settings.model_sonnet = None
    settings.model_haiku = None
    settings.enable_model_thinking = True
    settings.enable_opus_thinking = None
    settings.enable_sonnet_thinking = None
    settings.enable_haiku_thinking = None
    return settings


def test_model_router_resolves_default_model(settings):
    resolved = ModelRouter(settings).resolve("claude-3-opus")

    assert resolved.original_model == "claude-3-opus"
    assert resolved.provider_id == "nvidia_nim"
    assert resolved.provider_model == "fallback-model"
    assert resolved.provider_model_ref == "nvidia_nim/fallback-model"
    assert resolved.thinking_enabled is True


def test_model_router_applies_opus_override(settings):
    settings.model_opus = "open_router/deepseek/deepseek-r1"

    request = MessagesRequest(
        model="claude-opus-4-20250514",
        max_tokens=100,
        messages=[Message(role="user", content="hello")],
    )
    routed = ModelRouter(settings).resolve_messages_request(request)

    assert routed.request.model == "deepseek/deepseek-r1"
    assert routed.resolved.provider_model_ref == "open_router/deepseek/deepseek-r1"
    assert routed.resolved.original_model == "claude-opus-4-20250514"
    assert routed.resolved.thinking_enabled is True
    assert request.model == "claude-opus-4-20250514"


def test_model_router_resolves_per_model_thinking(settings):
    settings.enable_model_thinking = False
    settings.enable_opus_thinking = True
    settings.enable_haiku_thinking = False

    router = ModelRouter(settings)

    assert router.resolve("claude-opus-4-20250514").thinking_enabled is True
    assert router.resolve("claude-sonnet-4-20250514").thinking_enabled is False
    assert router.resolve("claude-3-haiku-20240307").thinking_enabled is False
    assert router.resolve("claude-2.1").thinking_enabled is False


def test_model_router_applies_haiku_override(settings):
    settings.model_haiku = "lmstudio/qwen2.5-7b"

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "qwen2.5-7b"
    assert routed.resolved.provider_model_ref == "lmstudio/qwen2.5-7b"


def test_model_router_applies_sonnet_override(settings):
    settings.model_sonnet = "nvidia_nim/meta/llama-3.3-70b-instruct"

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "meta/llama-3.3-70b-instruct"
    assert (
        routed.resolved.provider_model_ref == "nvidia_nim/meta/llama-3.3-70b-instruct"
    )


def test_model_router_routes_prefixed_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="deepseek/deepseek-chat",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-chat"
    assert routed.resolved.original_model == "deepseek/deepseek-chat"
    assert routed.resolved.provider_id == "deepseek"
    assert routed.resolved.provider_model == "deepseek-chat"
    assert routed.resolved.provider_model_ref == "deepseek/deepseek-chat"


def test_model_router_routes_wafer_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="wafer/DeepSeek-V4-Pro",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "DeepSeek-V4-Pro"
    assert routed.resolved.provider_id == "wafer"
    assert routed.resolved.provider_model == "DeepSeek-V4-Pro"
    assert routed.resolved.provider_model_ref == "wafer/DeepSeek-V4-Pro"


def test_model_router_routes_gateway_encoded_provider_model_directly(settings):
    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-ai/deepseek-v4-pro"
    assert (
        routed.resolved.original_model
        == "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )
    assert routed.resolved.provider_id == "nvidia_nim"
    assert routed.resolved.provider_model == "deepseek-ai/deepseek-v4-pro"
    assert (
        routed.resolved.provider_model_ref
        == "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )


def test_model_router_routes_no_thinking_gateway_model_directly(settings):
    settings.enable_model_thinking = True

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="claude-3-freecc-no-thinking/nvidia_nim/deepseek-ai/deepseek-v4-pro",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.request.model == "deepseek-ai/deepseek-v4-pro"
    assert (
        routed.resolved.original_model
        == "claude-3-freecc-no-thinking/nvidia_nim/deepseek-ai/deepseek-v4-pro"
    )
    assert routed.resolved.provider_id == "nvidia_nim"
    assert routed.resolved.provider_model == "deepseek-ai/deepseek-v4-pro"
    assert routed.resolved.thinking_enabled is False


def test_model_router_direct_prefixed_model_uses_provider_model_for_thinking(settings):
    settings.enable_model_thinking = False
    settings.enable_opus_thinking = True

    resolved = ModelRouter(settings).resolve("open_router/anthropic/claude-opus-4")

    assert resolved.provider_id == "open_router"
    assert resolved.provider_model == "anthropic/claude-opus-4"
    assert resolved.thinking_enabled is True


def test_model_router_routes_token_count_request(settings):
    settings.model_haiku = "lmstudio/qwen2.5-7b"

    request = TokenCountRequest(
        model="claude-3-haiku-20240307",
        messages=[Message(role="user", content="hello")],
    )
    routed = ModelRouter(settings).resolve_token_count_request(request)

    assert routed.request.model == "qwen2.5-7b"
    assert request.model == "claude-3-haiku-20240307"


def test_model_router_logs_mapping(settings):
    with patch("api.model_router.logger.debug") as mock_log:
        ModelRouter(settings).resolve("claude-2.1")

    mock_log.assert_called()
    args = mock_log.call_args[0]
    assert "MODEL MAPPING" in args[0]
    assert args[1] == "claude-2.1"
    assert args[2] == "fallback-model"


# ---- Passthrough mode (MODEL empty) ----


def test_passthrough_routes_prefixed_provider_model(settings):
    """MODEL empty: a provider/model from the client still routes directly (PATH A)."""
    settings.model = None

    routed = ModelRouter(settings).resolve_messages_request(
        MessagesRequest(
            model="kimi/kimi-k2.7-code",
            max_tokens=100,
            messages=[Message(role="user", content="hello")],
        )
    )

    assert routed.resolved.provider_id == "kimi"
    assert routed.resolved.provider_model == "kimi-k2.7-code"
    assert routed.request.model == "kimi-k2.7-code"


def test_passthrough_routes_gateway_model_id(settings):
    """MODEL empty: a gateway-advertised model id still decodes and routes (PATH A)."""
    settings.model = None

    resolved = ModelRouter(settings).resolve("anthropic/kimi/kimi-k2.7-code")

    assert resolved.provider_id == "kimi"
    assert resolved.provider_model == "kimi-k2.7-code"


def test_passthrough_honors_tier_override_for_bare_name(settings):
    """MODEL empty but MODEL_HAIKU set: classified bare names still route (background tasks)."""
    settings.model = None
    settings.model_haiku = "kimi/kimi-k2.7-code-highspeed"

    resolved = ModelRouter(settings).resolve("claude-3-5-haiku-20241022")

    assert resolved.provider_id == "kimi"
    assert resolved.provider_model == "kimi-k2.7-code-highspeed"


def test_passthrough_bare_name_without_route_raises_400(settings):
    """MODEL empty + bare name + no tier override -> actionable InvalidRequestError (400)."""
    settings.model = None

    with pytest.raises(InvalidRequestError) as exc_info:
        ModelRouter(settings).resolve("claude-sonnet-4-20250514")

    assert exc_info.value.status_code == 400
    assert "MODEL is empty" in str(exc_info.value)


def test_configured_model_still_maps_bare_name(settings):
    """Regression: with MODEL set, a bare name maps to the fallback as before."""
    resolved = ModelRouter(settings).resolve("claude-sonnet-4-20250514")

    assert resolved.provider_id == "nvidia_nim"
    assert resolved.provider_model == "fallback-model"


# ---- Malformed provider prefix must error, never silently misroute ----


def test_typo_provider_prefix_raises_instead_of_substring_matching(settings):
    """Regression: a slash-shaped string with an unsupported provider must error,
    not silently fall through to tier substring matching.

    A one-character typo ("antrhopic" for "anthropic") meant the string was
    treated as a bare Claude name instead of a rejected direct route, and it
    silently routed to MODEL_OPUS just because "opus" is a substring of the
    (mistyped) model string -- a completely different provider/model than
    either the literal string or the caller intended.
    """
    settings.model_opus = "kimi/kimi-k2.7-thinking"

    with pytest.raises(InvalidRequestError) as exc_info:
        ModelRouter(settings).resolve("antrhopic/claude-opus-4-20250514")

    assert exc_info.value.status_code == 400
    assert "antrhopic/claude-opus-4-20250514" in str(exc_info.value)


def test_gateway_shaped_id_with_unsupported_provider_raises(settings):
    """A well-formed gateway id (anthropic/<provider>/<model>) whose inner
    provider is unsupported must also error, not substring-match a tier."""
    settings.model_sonnet = "kimi/kimi-k2.7-thinking"

    with pytest.raises(InvalidRequestError):
        ModelRouter(settings).resolve("anthropic/not_a_provider/claude-sonnet-x")
