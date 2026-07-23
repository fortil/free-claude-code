"""Task-local inbound HTTP request context, shared across providers.

Currently carries the inbound client's ``User-Agent`` header so a provider
transport can forward it upstream byte-exact (see :mod:`providers.kimi.client`).
Values are set per request inside an ``async def`` FastAPI dependency
(:func:`api.routes.get_request_pipeline`) so each request's streaming task
inherits its own copy of the context -- never another request's value.
"""

from __future__ import annotations

from contextvars import ContextVar

_inbound_user_agent: ContextVar[str | None] = ContextVar(
    "inbound_user_agent", default=None
)


def set_inbound_user_agent(value: str | None) -> None:
    """Set the inbound request's ``User-Agent`` for the current task context."""
    _inbound_user_agent.set(value)


def get_inbound_user_agent() -> str | None:
    """Return the inbound request's ``User-Agent``, or ``None`` if unset/absent."""
    return _inbound_user_agent.get()
