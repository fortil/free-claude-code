"""Build an OpenAI Responses request body from an Anthropic Messages request.

This is the outbound counterpart to ``core/openai_responses/input.py`` (which
converts the other way). It flattens an Anthropic ``MessagesRequest`` into the
``input`` item list plus ``instructions``/``tools``/``reasoning`` fields that
``client.responses.create(...)`` expects. Every Anthropic tool is represented as
a Responses *function* tool, so each ``tool_use`` becomes a ``function_call`` and
each ``tool_result`` a ``function_call_output`` — consistent and round-trippable
without needing the original custom-tool metadata.
"""

from __future__ import annotations

import json
from typing import Any


def build_responses_request_body(
    request: Any, *, thinking_enabled: bool
) -> dict[str, Any]:
    """Convert an Anthropic request into an OpenAI Responses request body."""
    body: dict[str, Any] = {
        "model": getattr(request, "model", ""),
        "input": _build_input_items(getattr(request, "messages", []) or []),
        "store": False,
    }

    if instructions := _system_text(getattr(request, "system", None)):
        body["instructions"] = instructions

    if tools := _convert_tools(getattr(request, "tools", None)):
        body["tools"] = tools
    if (
        tool_choice := _convert_tool_choice(getattr(request, "tool_choice", None))
    ) is not None:
        body["tool_choice"] = tool_choice

    if (max_tokens := getattr(request, "max_tokens", None)) is not None:
        body["max_output_tokens"] = max_tokens
    if (temperature := getattr(request, "temperature", None)) is not None:
        body["temperature"] = temperature
    if (top_p := getattr(request, "top_p", None)) is not None:
        body["top_p"] = top_p

    if thinking_enabled:
        body["reasoning"] = {"effort": "medium", "summary": "auto"}

    return body


def _build_input_items(messages: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        items.extend(
            _message_to_items(
                getattr(message, "role", "user"),
                getattr(message, "content", ""),
            )
        )
    return items


def _message_to_items(role: str, content: Any) -> list[dict[str, Any]]:
    text_type = "output_text" if role == "assistant" else "input_text"
    if isinstance(content, str):
        return [_message_item(role, content, text_type)] if content else []

    items: list[dict[str, Any]] = []
    text_parts: list[str] = []

    def flush_text() -> None:
        if text_parts:
            items.append(_message_item(role, "".join(text_parts), text_type))
            text_parts.clear()

    for block in content or []:
        block_type = _field(block, "type")
        if block_type == "text":
            text_parts.append(str(_field(block, "text") or ""))
        elif block_type == "tool_use":
            flush_text()
            items.append(
                {
                    "type": "function_call",
                    "call_id": str(_field(block, "id") or ""),
                    "name": str(_field(block, "name") or ""),
                    "arguments": json.dumps(_field(block, "input") or {}),
                }
            )
        elif block_type == "tool_result":
            flush_text()
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": str(_field(block, "tool_use_id") or ""),
                    "output": _tool_result_output(_field(block, "content")),
                }
            )
        # thinking / redacted_thinking / image / document blocks are dropped:
        # they are FCC-internal or unsupported on the Responses input surface.
    flush_text()
    return items


def _message_item(role: str, text: str, text_type: str) -> dict[str, Any]:
    return {
        "type": "message",
        "role": role,
        "content": [{"type": text_type, "text": text}],
    }


def _tool_result_output(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            text = _field(part, "text")
            parts.append(str(text) if text is not None else json.dumps(_jsonable(part)))
        return "".join(parts)
    return json.dumps(_jsonable(content))


def _convert_tools(tools: Any) -> list[dict[str, Any]]:
    if not tools:
        return []
    converted: list[dict[str, Any]] = []
    for tool in tools:
        name = _field(tool, "name")
        if not name:
            continue
        # Skip Anthropic server tools (web_search, etc.) that carry a provider type
        # and no JSON schema; OpenAI cannot service those here.
        tool_type = _field(tool, "type")
        schema = _field(tool, "input_schema")
        if tool_type and schema is None:
            continue
        converted.append(
            {
                "type": "function",
                "name": str(name),
                "description": str(_field(tool, "description") or ""),
                "parameters": _jsonable(schema) or {"type": "object", "properties": {}},
                "strict": False,
            }
        )
    return converted


def _convert_tool_choice(tool_choice: Any) -> Any:
    if not isinstance(tool_choice, dict):
        return None
    choice_type = tool_choice.get("type")
    if choice_type == "auto":
        return "auto"
    if choice_type == "any":
        return "required"
    if choice_type == "tool" and tool_choice.get("name"):
        return {"type": "function", "name": tool_choice["name"]}
    return None


def _system_text(system: Any) -> str:
    if system is None:
        return ""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts = [str(_field(block, "text") or "") for block in system]
        return "\n\n".join(part for part in parts if part)
    return ""


def _field(obj: Any, name: str) -> Any:
    """Read a field from a pydantic block or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _jsonable(obj: Any) -> Any:
    """Return a JSON-serializable copy of a pydantic model or plain value."""
    if obj is None or isinstance(obj, (str, int, float, bool, list, dict)):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return str(obj)
