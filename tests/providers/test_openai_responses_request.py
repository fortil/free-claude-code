"""Tests for the Anthropic -> OpenAI Responses request builder."""

from __future__ import annotations

import json
from typing import Any

from api.models.anthropic import MessagesRequest
from providers.openai.responses_request import build_responses_request_body


def _request(**kwargs: Any) -> MessagesRequest:
    payload: dict[str, Any] = {
        "model": "gpt-5.3-codex",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "hello"}],
    }
    payload.update(kwargs)
    return MessagesRequest.model_validate(payload)


def test_basic_text_request() -> None:
    body = build_responses_request_body(
        _request(system="You are helpful"), thinking_enabled=False
    )
    assert body["model"] == "gpt-5.3-codex"
    assert body["store"] is False
    assert body["instructions"] == "You are helpful"
    assert body["max_output_tokens"] == 256
    assert body["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        }
    ]
    assert "reasoning" not in body


def test_thinking_enabled_adds_reasoning() -> None:
    body = build_responses_request_body(_request(), thinking_enabled=True)
    assert body["reasoning"] == {"effort": "medium", "summary": "auto"}


def test_tool_use_and_result_become_function_items() -> None:
    messages = [
        {"role": "user", "content": "search please"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "calling"},
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "github_search",
                    "input": {"q": "fcc"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": "result text",
                }
            ],
        },
    ]
    body = build_responses_request_body(
        _request(messages=messages), thinking_enabled=False
    )
    items = body["input"]
    assert items[0] == {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "search please"}],
    }
    assert items[1] == {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "calling"}],
    }
    assert items[2]["type"] == "function_call"
    assert items[2]["call_id"] == "call_1"
    assert items[2]["name"] == "github_search"
    assert json.loads(items[2]["arguments"]) == {"q": "fcc"}
    assert items[3] == {
        "type": "function_call_output",
        "call_id": "call_1",
        "output": "result text",
    }


def test_tools_convert_to_function_tools() -> None:
    body = build_responses_request_body(
        _request(
            tools=[
                {
                    "name": "github_search",
                    "description": "Search GitHub",
                    "input_schema": {
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                    },
                }
            ],
            tool_choice={"type": "auto"},
        ),
        thinking_enabled=False,
    )
    assert body["tools"] == [
        {
            "type": "function",
            "name": "github_search",
            "description": "Search GitHub",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            "strict": False,
        }
    ]
    assert body["tool_choice"] == "auto"


def test_tool_choice_specific_tool() -> None:
    body = build_responses_request_body(
        _request(
            tools=[{"name": "t", "input_schema": {"type": "object", "properties": {}}}],
            tool_choice={"type": "tool", "name": "t"},
        ),
        thinking_enabled=False,
    )
    assert body["tool_choice"] == {"type": "function", "name": "t"}
