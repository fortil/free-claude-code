"""OpenAI provider implementation.

Chat-completions models go through ``OpenAIChatTransport``. Models that OpenAI
only serves on the Responses API (the ``*-codex`` and ``-pro`` families) are
detected by name and streamed via the Responses runner instead, so they no
longer fail with HTTP 404 ("This is not a chat model ...").
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from providers.base import ProviderConfig
from providers.defaults import OPENAI_DEFAULT_BASE
from providers.transports.openai_chat import OpenAIChatTransport

from .request import build_request_body
from .responses_models import model_requires_responses_api
from .responses_request import build_responses_request_body
from .responses_stream import OpenAIResponsesStreamRunner


class OpenAIProvider(OpenAIChatTransport):
    """OpenAI API: ``/v1/chat/completions`` for chat models, ``/v1/responses`` for codex/pro."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OPENAI",
            base_url=config.base_url or OPENAI_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )

    def preflight_stream(
        self, request: Any, *, thinking_enabled: bool | None = None
    ) -> None:
        """Eagerly validate the upstream request before opening the stream."""
        if model_requires_responses_api(getattr(request, "model", "")):
            build_responses_request_body(
                request,
                thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
            )
            return
        super().preflight_stream(request, thinking_enabled=thinking_enabled)

    async def stream_response(
        self,
        request: Any,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        thinking_enabled: bool | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response, routing Responses-only models to ``/v1/responses``."""
        if model_requires_responses_api(getattr(request, "model", "")):
            runner = OpenAIResponsesStreamRunner(
                self,
                request=request,
                input_tokens=input_tokens,
                request_id=request_id,
                thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
            )
            async for event in runner.run():
                yield event
            return

        async for event in super().stream_response(
            request,
            input_tokens,
            request_id=request_id,
            thinking_enabled=thinking_enabled,
        ):
            yield event
