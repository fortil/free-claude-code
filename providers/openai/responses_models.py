"""Detect OpenAI models that are only served by the Responses API.

Some first-party OpenAI models (the ``*-codex`` family and the ``-pro`` reasoning
models) are not available on ``/v1/chat/completions`` and return HTTP 404
("This is not a chat model ..."). Those must be routed to ``/v1/responses``
instead. Detection is by model-name pattern so the request goes straight to the
right endpoint without a wasted round-trip.
"""

from __future__ import annotations

import re

# Lowercased patterns matched against the bare model id (provider prefix stripped):
# - any codex model (gpt-5-codex, gpt-5.3-codex, codex-mini, gpt-5.1-codex-max)
# - o-series pro reasoning models (o1-pro, o3-pro, o4-pro, ...)
# - gpt pro reasoning models (gpt-5-pro, gpt-5.1-pro, ...)
_RESPONSES_ONLY_PATTERNS = (
    re.compile(r"codex"),
    re.compile(r"(?:^|[^a-z0-9])o\d+-pro\b"),
    re.compile(r"gpt-[\d.]+-pro\b"),
)


def model_requires_responses_api(model: str) -> bool:
    """Return whether ``model`` must be served via the OpenAI Responses API."""
    if not model:
        return False
    name = model.rsplit("/", 1)[-1].lower()
    return any(pattern.search(name) for pattern in _RESPONSES_ONLY_PATTERNS)
