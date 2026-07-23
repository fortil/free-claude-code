"""Tests for the task-local inbound User-Agent ContextVar accessors."""

from __future__ import annotations

import asyncio

import pytest

from core.http_context import get_inbound_user_agent, set_inbound_user_agent


def test_default_is_none_when_unset():
    """A brand-new context (no ``set_inbound_user_agent`` call) reads as None."""
    assert get_inbound_user_agent() is None


def test_set_then_get_returns_the_exact_value():
    set_inbound_user_agent("claude-cli/1.2.3")
    try:
        assert get_inbound_user_agent() == "claude-cli/1.2.3"
    finally:
        set_inbound_user_agent(None)


def test_set_none_explicitly_clears_a_previous_value():
    set_inbound_user_agent("claude-cli/1.2.3")
    set_inbound_user_agent(None)
    assert get_inbound_user_agent() is None


async def _set_and_read(value: str | None) -> str | None:
    set_inbound_user_agent(value)
    # Yield control so a concurrently scheduled task could interleave if the
    # ContextVar leaked across tasks instead of staying task-local.
    await asyncio.sleep(0)
    return get_inbound_user_agent()


@pytest.mark.asyncio
async def test_concurrent_tasks_do_not_leak_values_to_each_other():
    """Each asyncio task gets its own copy of the context; no cross-request leakage."""
    results = await asyncio.gather(
        _set_and_read("agent-a"),
        _set_and_read("agent-b"),
        _set_and_read(None),
    )
    assert results == ["agent-a", "agent-b", None]


@pytest.mark.asyncio
async def test_child_task_inherits_parent_value_set_before_creation():
    """A task created after the parent sets a value starts with a copy of it.

    Mirrors the FastAPI shape: the request task sets the ContextVar, then a
    child task (e.g. ``StreamingResponse``'s body iterator) is spawned and
    should see that value without the parent needing to pass it explicitly.
    """
    set_inbound_user_agent("claude-cli/9.9.9")
    try:

        async def _child() -> str | None:
            return get_inbound_user_agent()

        result = await asyncio.create_task(_child())
        assert result == "claude-cli/9.9.9"
    finally:
        set_inbound_user_agent(None)
