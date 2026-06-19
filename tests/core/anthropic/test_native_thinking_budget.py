"""Tests for the native Anthropic thinking-budget invariant helper."""

from __future__ import annotations

import pytest

from core.anthropic.native_messages_request import (
    ANTHROPIC_MIN_THINKING_BUDGET_TOKENS as MIN,
)
from core.anthropic.native_messages_request import (
    resolve_native_thinking_payload,
)


def test_injects_min_budget_when_absent() -> None:
    assert resolve_native_thinking_payload({"type": "enabled"}, max_tokens=8000) == {
        "type": "enabled",
        "budget_tokens": MIN,
    }


def test_floors_sub_minimum_budget() -> None:
    assert resolve_native_thinking_payload(
        {"type": "enabled", "budget_tokens": 100}, max_tokens=8000
    ) == {"type": "enabled", "budget_tokens": MIN}


def test_preserves_valid_budget() -> None:
    assert resolve_native_thinking_payload(
        {"type": "enabled", "budget_tokens": 2000}, max_tokens=8000
    ) == {"type": "enabled", "budget_tokens": 2000}


def test_clamps_budget_strictly_below_max_tokens() -> None:
    assert resolve_native_thinking_payload(
        {"type": "enabled", "budget_tokens": 5000}, max_tokens=1500
    ) == {"type": "enabled", "budget_tokens": 1499}


@pytest.mark.parametrize("max_tokens", [50, MIN])
def test_drops_thinking_when_max_tokens_cannot_fit_min_budget(max_tokens: int) -> None:
    assert (
        resolve_native_thinking_payload({"type": "enabled"}, max_tokens=max_tokens)
        is None
    )


def test_boundary_max_tokens_just_above_min() -> None:
    # max_tokens = MIN + 1 leaves exactly room for budget == MIN (< max_tokens).
    assert resolve_native_thinking_payload({"type": "enabled"}, max_tokens=MIN + 1) == {
        "type": "enabled",
        "budget_tokens": MIN,
    }


@pytest.mark.parametrize("cfg", [None, "enabled", 123, []])
def test_non_dict_config_returns_none(cfg: object) -> None:
    assert resolve_native_thinking_payload(cfg, max_tokens=8000) is None
