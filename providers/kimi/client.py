"""Kimi (Moonshot) provider using native Anthropic-compatible Messages."""

from __future__ import annotations

from typing import Any

import httpx

from core.http_context import get_inbound_user_agent
from providers.base import ProviderConfig
from providers.defaults import KIMI_DEFAULT_BASE
from providers.transports.anthropic_messages import AnthropicMessagesTransport

from .request import build_request_body

_MOONSHOT_OPENAI_MODELS_URL = "https://api.moonshot.ai/v1/models"
_ANTHROPIC_VERSION = "2023-06-01"


class KimiProvider(AnthropicMessagesTransport):
    """Kimi provider using Anthropic-compatible Messages at api.moonshot.ai/anthropic/v1."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="KIMI",
            default_base_url=KIMI_DEFAULT_BASE,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )

    def _request_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        # The Kimi Code subscription endpoint allowlists known coding-agent
        # clients (Claude Code among them) by User-Agent. Forward the inbound
        # client's UA byte-exact when present; never fabricate one -- if there
        # is no inbound UA (e.g. startup model discovery), omit the header and
        # let httpx send its own honest default.
        inbound_user_agent = get_inbound_user_agent()
        if inbound_user_agent:
            headers["User-Agent"] = inbound_user_agent
        return headers

    async def _send_model_list_request(self) -> httpx.Response:
        """Query the model-list endpoint matching the configured base URL.

        The default open-platform base (``api.moonshot.ai/anthropic/v1``) lists
        models from a separate OpenAI-compat root, not under ``/anthropic/v1``.
        Any overridden base (e.g. the Kimi Code subscription at
        ``api.kimi.com/coding/v1``) lists models at ``{base_url}/models``, so we
        delegate to the shared transport implementation for that case.
        """
        if self._base_url == KIMI_DEFAULT_BASE.rstrip("/"):
            return await self._client.get(
                _MOONSHOT_OPENAI_MODELS_URL,
                headers=self._model_list_headers(),
            )
        return await super()._send_model_list_request()

    def _model_list_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}
