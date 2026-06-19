"""Stream an OpenAI Responses API call and emit Anthropic SSE.

Mirrors ``OpenAIChatStreamRunner`` but consumes the typed events produced by
``client.responses.create(..., stream=True)`` instead of chat-completions
chunks. Used for OpenAI models that are only served by ``/v1/responses`` (the
``*-codex`` and ``-pro`` families).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from core.anthropic import SSEBuilder
from core.trace import trace_event
from providers.error_mapping import map_error

from .responses_request import build_responses_request_body


class OpenAIResponsesStreamRunner:
    """Own mutable state for one OpenAI Responses provider stream."""

    def __init__(
        self,
        transport: Any,
        *,
        request: Any,
        input_tokens: int,
        request_id: str | None,
        thinking_enabled: bool,
    ) -> None:
        self._transport = transport
        self._request = request
        self._input_tokens = input_tokens
        self._request_id = request_id
        self._thinking_enabled = thinking_enabled
        self._message_id = f"msg_{uuid.uuid4()}"

    def _new_sse(self) -> SSEBuilder:
        return SSEBuilder(
            self._message_id,
            self._request.model,
            self._input_tokens,
            log_raw_events=self._transport._config.log_raw_sse_events,
        )

    async def run(self) -> AsyncIterator[str]:
        tag = self._transport._provider_name
        req_tag = f" request_id={self._request_id}" if self._request_id else ""
        sse = self._new_sse()
        body = build_responses_request_body(
            self._request, thinking_enabled=self._thinking_enabled
        )
        trace_event(
            stage="provider",
            event="provider.request.sent",
            source="provider",
            provider=tag,
            gateway_model=self._request.model,
            downstream_model=body.get("model"),
            wire_api="responses",
            message_count=len(body.get("input", [])),
            tool_count=len(body.get("tools", [])),
        )

        yield sse.message_start()

        finish_reason = "end_turn"
        output_tokens: int | None = None
        # output_index -> {"tool_index", "kind", "buffer": list[str]}
        tools: dict[int, dict[str, Any]] = {}

        async with self._transport._global_rate_limiter.concurrency_slot():
            try:
                stream = await self._transport._global_rate_limiter.execute_with_retry(
                    self._transport._client.responses.create, **body, stream=True
                )
                async for event in stream:
                    event_type = getattr(event, "type", "")

                    if event_type == "response.output_text.delta":
                        for out in sse.ensure_text_block():
                            yield out
                        yield sse.emit_text_delta(_delta(event))

                    elif event_type in (
                        "response.reasoning_text.delta",
                        "response.reasoning_summary_text.delta",
                    ):
                        if self._thinking_enabled:
                            for out in sse.ensure_thinking_block():
                                yield out
                            yield sse.emit_thinking_delta(_delta(event))

                    elif event_type == "response.output_item.added":
                        item = getattr(event, "item", None)
                        kind = _tool_kind(getattr(item, "type", None))
                        if kind is not None:
                            for out in sse.close_content_blocks():
                                yield out
                            index = _output_index(event, len(tools))
                            call_id = (
                                getattr(item, "call_id", None)
                                or getattr(item, "id", None)
                                or f"call_{uuid.uuid4().hex[:24]}"
                            )
                            name = getattr(item, "name", "") or ""
                            tools[index] = {
                                "tool_index": index,
                                "kind": kind,
                                "buffer": [],
                            }
                            finish_reason = "tool_use"
                            yield sse.start_tool_block(index, str(call_id), str(name))

                    elif event_type in (
                        "response.function_call_arguments.delta",
                        "response.custom_tool_call_input.delta",
                    ):
                        state = tools.get(_output_index(event, -1))
                        if state is not None:
                            state["buffer"].append(_delta(event))

                    elif event_type == "response.output_item.done":
                        state = tools.get(_output_index(event, -1))
                        if state is not None:
                            yield sse.emit_tool_delta(
                                state["tool_index"],
                                _tool_arguments(state, getattr(event, "item", None)),
                            )
                            yield sse.stop_tool_block(state["tool_index"])

                    elif event_type == "response.completed":
                        response = getattr(event, "response", None)
                        output_tokens = _output_tokens(response)
                        finish_reason = _finish_reason(response, finish_reason)

                    elif event_type in ("response.failed", "error"):
                        message = _event_error_message(event)
                        trace_event(
                            stage="provider",
                            event="provider.response.error",
                            source="provider",
                            provider=tag,
                            error_message=message,
                        )
                        for out in sse.close_all_blocks():
                            yield out
                        for out in sse.emit_error(message):
                            yield out
                        yield sse.message_delta(
                            "end_turn", sse.estimate_output_tokens()
                        )
                        yield sse.message_stop()
                        return

            except asyncio.CancelledError, GeneratorExit:
                raise
            except Exception as error:
                self._transport._log_stream_transport_error(
                    tag, req_tag, error, request_id=self._request_id
                )
                error_message = self._transport._openai_error_message(
                    error, self._request_id
                )
                trace_event(
                    stage="provider",
                    event="provider.response.error",
                    source="provider",
                    provider=tag,
                    error_message=error_message,
                    mapped_error_type=type(
                        map_error(
                            error, rate_limiter=self._transport._global_rate_limiter
                        )
                    ).__name__,
                )
                for out in sse.emit_error(error_message):
                    yield out
                yield sse.message_delta("end_turn", sse.estimate_output_tokens())
                yield sse.message_stop()
                return

        for out in sse.close_all_blocks():
            yield out

        if not _has_content(sse):
            for out in sse.ensure_text_block():
                yield out
            yield sse.emit_text_delta(" ")
            yield sse.stop_text_block()

        resolved_tokens = (
            output_tokens if output_tokens is not None else sse.estimate_output_tokens()
        )
        trace_event(
            stage="provider",
            event="provider.response.completed",
            source="provider",
            provider=tag,
            finish_reason=finish_reason,
            output_tokens=resolved_tokens,
            prompt_tokens_estimate=self._input_tokens,
        )
        yield sse.message_delta(finish_reason, resolved_tokens)
        yield sse.message_stop()


def _delta(event: Any) -> str:
    return str(getattr(event, "delta", "") or "")


def _output_index(event: Any, default: int) -> int:
    value = getattr(event, "output_index", None)
    return value if isinstance(value, int) else default


def _tool_kind(item_type: Any) -> str | None:
    if item_type == "function_call":
        return "function"
    if item_type == "custom_tool_call":
        return "custom"
    return None


def _tool_arguments(state: dict[str, Any], item: Any) -> str:
    """Return the Anthropic ``input_json`` payload for a completed tool call."""
    if state["kind"] == "custom":
        text = getattr(item, "input", None)
        if text is None:
            text = "".join(state["buffer"])
        return json.dumps({"input": text})
    arguments = getattr(item, "arguments", None)
    if not arguments:
        arguments = "".join(state["buffer"])
    return arguments or "{}"


def _output_tokens(response: Any) -> int | None:
    usage = getattr(response, "usage", None)
    tokens = getattr(usage, "output_tokens", None) if usage is not None else None
    return tokens if isinstance(tokens, int) else None


def _finish_reason(response: Any, current: str) -> str:
    details = getattr(response, "incomplete_details", None)
    reason = getattr(details, "reason", None) if details is not None else None
    if reason == "max_output_tokens":
        return "max_tokens"
    return current


def _has_content(sse: SSEBuilder) -> bool:
    started_tool = any(state.started for state in sse.blocks.tool_states.values())
    return (
        sse.blocks.text_index != -1 or sse.blocks.thinking_index != -1 or started_tool
    )


def _event_error_message(event: Any) -> str:
    response = getattr(event, "response", None)
    error = getattr(response, "error", None) if response is not None else None
    message = getattr(error, "message", None) if error is not None else None
    if not message:
        message = getattr(event, "message", None)
    return str(message or "OpenAI Responses stream failed.")
