"""Tests for api/prompt_model_keyword.py (prompt -keyword model override)."""

from __future__ import annotations

from api.models.anthropic import ContentBlockText, Message, MessagesRequest
from api.prompt_model_keyword import apply_prompt_model_keyword

_ALIASES = {"kimi2.7": "kimi/kimi-k2.7-code", "fast": "groq/llama-3.3-70b"}


def _aliases():
    return _ALIASES


def _request(content, *, model="nvidia_nim/test-model", history=None):
    messages = list(history or [])
    messages.append(Message(role="user", content=content))
    return MessagesRequest(model=model, max_tokens=64, messages=messages)


def test_keyword_overrides_model_and_strips_token_str_content() -> None:
    request = _request("-kimi2.7 refactor this module")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "kimi/kimi-k2.7-code"
    assert out.messages[-1].content == "refactor this module"
    # Original request is left untouched.
    assert request.model == "nvidia_nim/test-model"
    assert request.messages[-1].content == "-kimi2.7 refactor this module"


def test_keyword_in_first_text_block_of_list_content() -> None:
    request = _request(
        [
            {"type": "text", "text": "-fast summarize"},
            {"type": "text", "text": "second block"},
        ]
    )
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "groq/llama-3.3-70b"
    blocks = out.messages[-1].content
    assert isinstance(blocks, list)
    first, second = blocks[0], blocks[1]
    assert isinstance(first, ContentBlockText) and first.text == "summarize"
    assert isinstance(second, ContentBlockText) and second.text == "second block"


def test_unknown_keyword_leaves_request_untouched() -> None:
    request = _request("-unknownmodel do something")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out is request
    assert out.messages[-1].content == "-unknownmodel do something"


def test_no_leading_keyword_is_untouched() -> None:
    request = _request("just a normal prompt without a keyword")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out is request


def test_dash_not_followed_by_keyword_is_untouched() -> None:
    request = _request("- bullet list item")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out is request


def test_leading_whitespace_before_keyword_is_handled() -> None:
    request = _request("  -kimi2.7 hello")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "kimi/kimi-k2.7-code"
    assert out.messages[-1].content == "hello"


def test_keyword_only_prompt_overrides_and_empties_text() -> None:
    request = _request("-kimi2.7")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "kimi/kimi-k2.7-code"
    assert out.messages[-1].content == ""


def test_keyword_persists_across_turns_from_history() -> None:
    """A keyword set earlier keeps applying to later turns that omit it."""
    history = [
        Message(role="user", content="-kimi2.7 earlier turn"),
        Message(role="assistant", content="ok"),
    ]
    request = _request("plain follow-up", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "kimi/kimi-k2.7-code"
    # The historical keyword token is stripped; later turns are unchanged.
    assert out.messages[0].content == "earlier turn"
    assert out.messages[-1].content == "plain follow-up"


def test_newer_keyword_overrides_older() -> None:
    """The most recent keyword wins when several appear across the session."""
    history = [
        Message(role="user", content="-kimi2.7 start with kimi"),
        Message(role="assistant", content="ok"),
    ]
    request = _request("-fast switch to fast", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "groq/llama-3.3-70b"
    # Both keyword tokens are stripped.
    assert out.messages[0].content == "start with kimi"
    assert out.messages[-1].content == "switch to fast"


def test_unknown_latest_keyword_falls_back_to_prior_recognized() -> None:
    """An unrecognized newer token does not clear a recognized earlier choice."""
    history = [
        Message(role="user", content="-kimi2.7 begin"),
        Message(role="assistant", content="ok"),
    ]
    request = _request("-notakeyword keep going", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "kimi/kimi-k2.7-code"
    assert out.messages[0].content == "begin"
    # The unrecognized token is left intact (it is real prompt text).
    assert out.messages[-1].content == "-notakeyword keep going"


def test_keyword_resolved_against_last_user_after_assistant() -> None:
    history = [Message(role="assistant", content="previous answer")]
    request = _request("-fast now go", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "groq/llama-3.3-70b"
    assert out.messages[-1].content == "now go"


def test_default_keyword_reverts_to_configured_model() -> None:
    """-default clears a prior sticky selection and keeps the request model."""
    history = [
        Message(role="user", content="-kimi2.7 start with kimi"),
        Message(role="assistant", content="ok"),
    ]
    request = _request("-default back to normal", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    # Reverts to the original configured model (no override).
    assert out.model == "nvidia_nim/test-model"
    # Both the alias token and the -default token are stripped.
    assert out.messages[0].content == "start with kimi"
    assert out.messages[-1].content == "back to normal"


def test_default_then_new_keyword_selects_new_model() -> None:
    """A model keyword after -default takes over again."""
    history = [
        Message(role="user", content="-kimi2.7 first"),
        Message(role="assistant", content="ok"),
        Message(role="user", content="-default second"),
        Message(role="assistant", content="ok"),
    ]
    request = _request("-fast third", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "groq/llama-3.3-70b"
    assert out.messages[-1].content == "third"


def test_default_keyword_alone_strips_token_and_keeps_model() -> None:
    request = _request("-default just chatting")
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    assert out.model == "nvidia_nim/test-model"
    assert out.messages[-1].content == "just chatting"
