"""Resolve a leading ``-<keyword>`` in a user prompt to a sticky model override.

A user may prefix a prompt with ``-<keyword>`` (e.g. ``-kimi2.7 refactor this``)
to force the model mapped to that keyword in ``~/.fcc/model-aliases.json``.

The selection is **session-sticky**: because clients resend the full conversation
each turn (and keep the original keyword text), the active model is taken from the
*most recent* recognized keyword anywhere in the history. So a keyword keeps
applying to later turns until a different keyword overrides it. The reserved
keyword ``-default`` clears the selection and reverts to the configured default
model. Recognized keyword tokens are stripped from every user message so the model
never sees the directive; unknown keywords (and prompts without a leading token)
are left untouched.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from config.model_store import load_aliases

from .models.anthropic import ContentBlockText, Message, MessagesRequest

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
) -> MessagesRequest:
    """Return a request whose model is overridden by the most recent keyword.

    The original request is returned unchanged when no user message leads with a
    recognized keyword. Aliases are read only when a leading ``-<token>`` is
    actually present, so the common path never touches disk.
    """
    candidates = _keyword_candidates(request.messages)
    if not candidates:
        return request

    aliases = (load_aliases if aliases_loader is None else aliases_loader)()

    # The most recent recognized keyword decides the active model, so the choice
    # sticks across turns until a different keyword appears later. A recognized
    # keyword is either an alias or the reserved ``default`` sentinel (which
    # reverts to the request's configured model). Unknown tokens are skipped so a
    # later typo cannot clear an earlier selection.
    matched = False
    model_ref: str | None = None
    for _index, keyword in reversed(candidates):
        if keyword in _DEFAULT_KEYWORDS:
            matched = True
            break
        if resolved := aliases.get(keyword):
            matched = True
            model_ref = resolved
            break
    if not matched:
        return request

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
