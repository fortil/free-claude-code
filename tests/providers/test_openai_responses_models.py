"""Tests for OpenAI Responses-only model detection."""

from __future__ import annotations

import pytest

from providers.openai.responses_models import model_requires_responses_api


@pytest.mark.parametrize(
    "model",
    [
        "gpt-5.3-codex",
        "gpt-5-codex",
        "gpt-5.1-codex-max",
        "codex-mini-latest",
        "openai/gpt-5.3-codex",
        "o1-pro",
        "o3-pro",
        "o3-pro-2025-06-10",
        "gpt-5-pro",
        "gpt-5.1-pro",
    ],
)
def test_responses_only_models_detected(model: str) -> None:
    assert model_requires_responses_api(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "gpt-4o",
        "gpt-4.1",
        "openai/gpt-4o",
        "o3",
        "o3-mini",
        "gpt-5",
        "gpt-5-mini",
        "chatgpt-4o-latest",
        "",
    ],
)
def test_chat_models_not_detected(model: str) -> None:
    assert model_requires_responses_api(model) is False
