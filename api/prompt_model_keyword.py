"""Resolve a leading ``-<keyword>`` in a user prompt to a model override.

A user may prefix a prompt with ``-<keyword>`` (e.g. ``-kimi2.7 refactor this``)
to force the model mapped to that keyword in ``~/.fcc/model-aliases.json``.

When an :class:`~config.active_model.ActiveModelStore` is supplied, the choice is
**persisted** (``~/.fcc/active-model.json``): a recognized keyword saves the model
and applies it to every later request — even after the client compacts the
conversation and the keyword text is gone — until a new ``-keyword`` or
``-default`` changes it. ``-default`` clears the persisted selection and reverts
to the configured default. Without a store, the keyword only affects the current
request. Recognized keyword tokens are stripped so the model never sees the
directive; unknown keywords keep the persisted active model (if any) instead of
dropping a deliberate selection on a typo, and always log a visible console
warning — a silent fallback is indistinguishable from the keyword having
worked. An unrecognized ``-<token>`` is deliberately left in the prompt: there
is no reliable way to tell a failed directive (``-qwen``) apart from ordinary
text that merely starts with a hyphen (``-1``, ``-Werror``, ``-inf``), and
silently discarding user content is worse than a stray token reaching the
model.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Protocol

from loguru import logger

from config.model_store import load_aliases

from .models.anthropic import ContentBlockText, Message, MessagesRequest


class ActiveModel(Protocol):
    """Minimal interface for the persisted active-model selection."""

    def load(self) -> str | None: ...
    def save(self, model_ref: str) -> None: ...
    def clear(self) -> None: ...


# Leading optional whitespace, then '-' and a keyword that starts alphanumeric
# and may contain word characters, dots and dashes; it must be terminated by
# whitespace or the end of the text so a bare "-flag" word is matched cleanly.
_KEYWORD_RE = re.compile(r"^\s*-([A-Za-z0-9][\w.\-]*)(?:\s+|$)")

# Reserved keywords that clear a sticky selection and revert to the configured
# default model instead of mapping to an alias.
_DEFAULT_KEYWORDS = frozenset({"default"})


def apply_prompt_model_keyword(
    request: MessagesRequest,
    *,
    aliases_loader: Callable[[], Mapping[str, str]] | None = None,
    active_store: ActiveModel | None = None,
) -> MessagesRequest:
    """Return a request with the model resolved from the keyword / persisted active model.

    Precedence: the most recent ``-keyword`` in the current prompt wins — a known
    alias overrides the model and (with a store) becomes the persisted active
    model; ``-default`` clears it. When the prompt carries no usable keyword, the
    persisted active model (if any) is applied, which is what survives client
    context compaction.
    """
    candidates = _keyword_candidates(request.messages)

    if candidates:
        keyword = candidates[-1][1]
        aliases = (load_aliases if aliases_loader is None else aliases_loader)()
        if keyword in _DEFAULT_KEYWORDS:
            if active_store is not None:
                active_store.clear()
            return _apply_model(request, candidates, aliases, model_ref=None)
        model_ref = aliases.get(keyword)
        if model_ref is not None:
            if active_store is not None:
                active_store.save(model_ref)
            return _apply_model(request, candidates, aliases, model_ref=model_ref)
        # Unrecognized keyword: do not change the model here; fall through to the
        # persisted active model so a typo doesn't drop a deliberate selection.
        # Always logged loudly — a silent fallback here is indistinguishable
        # from the keyword having worked. The token itself is intentionally
        # NOT stripped (see module docstring): there is no reliable way to
        # tell a failed directive apart from ordinary hyphen-prefixed text.
        fallback = active_store.load() if active_store is not None else None
        logger.bind(console=True).warning(
            "keyword '-{}' not found in model-aliases.json ({})",
            keyword,
            f"using active model: {fallback}"
            if fallback
            else "no active override, using requested model",
        )
        if fallback:
            updated = request.model_copy(deep=True)
            updated.model = fallback
            return updated
        return request

    active_model = active_store.load() if active_store is not None else None
    if active_model:
        updated = request.model_copy(deep=True)
        updated.model = active_model
        return updated
    return request


def _apply_model(
    request: MessagesRequest,
    candidates: list[tuple[int, str]],
    aliases: Mapping[str, str],
    *,
    model_ref: str | None,
) -> MessagesRequest:
    updated = request.model_copy(deep=True)
    if model_ref is not None:
        updated.model = model_ref
    _strip_recognized_keywords(updated, candidates, aliases)
    return updated


def _strip_recognized_keywords(
    request: MessagesRequest,
    candidates: list[tuple[int, str]],
    aliases: Mapping[str, str],
) -> None:
    """Remove every recognized keyword token so the model only sees prompt text."""
    for index, keyword in candidates:
        if keyword not in _DEFAULT_KEYWORDS and keyword not in aliases:
            continue
        leading = _leading_text(request.messages[index])
        if leading is None:
            continue
        if stripped := _KEYWORD_RE.match(leading):
            _set_leading_text(request.messages[index], leading[stripped.end() :])


def _keyword_candidates(messages: list[Message]) -> list[tuple[int, str]]:
    """Return ``(index, keyword)`` for each user message that leads with ``-<token>``."""
    candidates: list[tuple[int, str]] = []
    for index, message in enumerate(messages):
        if message.role != "user":
            continue
        leading = _leading_text(message)
        if leading is None:
            continue
        if match := _KEYWORD_RE.match(leading):
            candidates.append((index, match.group(1)))
    return candidates


def _leading_text(message: Message) -> str | None:
    """Return the leading text of a message, or None when it does not start with text."""
    content = message.content
    if isinstance(content, str):
        return content
    if content and isinstance(content[0], ContentBlockText):
        return content[0].text
    return None


def _set_leading_text(message: Message, text: str) -> None:
    content = message.content
    if isinstance(content, str):
        message.content = text
        return
    if content and isinstance(content[0], ContentBlockText):
        content[0].text = text
