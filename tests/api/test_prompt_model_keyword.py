"""Tests for api/prompt_model_keyword.py (prompt -keyword model override)."""

from __future__ import annotations

from unittest.mock import patch

from api.models.anthropic import ContentBlockText, Message, MessagesRequest
from api.prompt_model_keyword import apply_prompt_model_keyword

_ALIASES = {"kimi2.7": "kimi/kimi-k2.7-code", "fast": "groq/llama-3.3-70b"}


def _aliases():
    return _ALIASES


class FakeActiveStore:
    """In-memory stand-in for config.active_model.ActiveModelStore."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def load(self) -> str | None:
        return self.model

    def save(self, model_ref: str) -> None:
        self.model = model_ref

    def clear(self) -> None:
        self.model = None


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


def test_unknown_keyword_does_not_strip_ordinary_hyphen_prefixed_content() -> None:
    """Regression: an unresolved keyword-shaped token must not destroy user content.

    A prior fix (to stop "-qwen" from leaking into the prompt) unconditionally
    stripped every leading "-<token>", which also silently truncated ordinary
    text that merely starts with a hyphen (negative numbers, CLI flags) — there
    is no reliable way to tell these apart from a failed keyword directive, so
    unrecognized tokens must be left as-is.
    """
    cases = [
        "-1 is a negative number, explain floating point",
        "-v --help please explain this CLI flag",
        "-Werror is a gcc flag, what does it do",
        "-inf and +inf in IEEE754",
    ]
    for prompt in cases:
        out = apply_prompt_model_keyword(_request(prompt), aliases_loader=_aliases)
        assert out.messages[-1].content == prompt
        assert out.model == "nvidia_nim/test-model"


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


def test_unknown_latest_keyword_does_not_resurrect_prior_model() -> None:
    """A new but unrecognized keyword must not jump back to an earlier model.

    Regression: the user typed a fresh -keyword to switch, but because it was not
    a known alias the router used to fall back to a stale earlier keyword.
    """
    history = [
        Message(role="user", content="-fast did the plan"),
        Message(role="assistant", content="ok"),
    ]
    request = _request("-kimi-k2.6-code now switch", history=history)
    out = apply_prompt_model_keyword(request, aliases_loader=_aliases)
    # The request is left on its configured model, NOT the earlier groq choice.
    assert out is request
    assert out.model == "nvidia_nim/test-model"
    assert out.messages[-1].content == "-kimi-k2.6-code now switch"


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


# --- Persistent active model (Option A) -------------------------------------


def test_keyword_persists_to_active_store() -> None:
    store = FakeActiveStore()
    out = apply_prompt_model_keyword(
        _request("-kimi2.7 do it"), aliases_loader=_aliases, active_store=store
    )
    assert out.model == "kimi/kimi-k2.7-code"
    assert store.model == "kimi/kimi-k2.7-code"


def test_persisted_active_model_applies_without_keyword() -> None:
    """Survives compaction: a keyword-less prompt still routes to the active model."""
    store = FakeActiveStore("kimi/kimi-k2.7-code")
    out = apply_prompt_model_keyword(
        _request("plain follow-up after compaction"),
        aliases_loader=_aliases,
        active_store=store,
    )
    assert out.model == "kimi/kimi-k2.7-code"
    assert out.messages[-1].content == "plain follow-up after compaction"


def test_unknown_keyword_keeps_persisted_active_model() -> None:
    store = FakeActiveStore("kimi/kimi-k2.7-code")
    out = apply_prompt_model_keyword(
        _request("-typo keep going"), aliases_loader=_aliases, active_store=store
    )
    assert out.model == "kimi/kimi-k2.7-code"
    assert store.model == "kimi/kimi-k2.7-code"
    # The unresolved token is left as-is; only the model changes.
    assert out.messages[-1].content == "-typo keep going"


def test_unknown_keyword_with_active_model_logs_visible_console_warning() -> None:
    """Regression: a silent fallback is indistinguishable from the keyword working.

    -qwen resolved to nothing (Ollama was never refreshed into the alias file),
    so the request silently kept routing to a stale active model with no signal
    the operator could see. The fallback must now log a console-visible warning.
    """
    store = FakeActiveStore("zai/glm-5.2")
    with patch("api.prompt_model_keyword.logger.bind") as mock_bind:
        apply_prompt_model_keyword(
            _request("-qwen what can we do?"),
            aliases_loader=_aliases,
            active_store=store,
        )

    mock_bind.assert_called_once_with(console=True)
    mock_bind.return_value.warning.assert_called_once()
    args = mock_bind.return_value.warning.call_args[0]
    assert args[1] == "qwen"
    assert "zai/glm-5.2" in args[2]


def test_unknown_keyword_without_active_model_logs_visible_console_warning() -> None:
    with patch("api.prompt_model_keyword.logger.bind") as mock_bind:
        out = apply_prompt_model_keyword(
            _request("-qwen what can we do?"), aliases_loader=_aliases
        )

    assert out.model == "nvidia_nim/test-model"
    mock_bind.assert_called_once_with(console=True)
    args = mock_bind.return_value.warning.call_args[0]
    assert args[1] == "qwen"
    assert "no active override" in args[2]


def test_default_clears_active_store_and_reverts() -> None:
    store = FakeActiveStore("kimi/kimi-k2.7-code")
    out = apply_prompt_model_keyword(
        _request("-default back to config"),
        aliases_loader=_aliases,
        active_store=store,
    )
    assert out.model == "nvidia_nim/test-model"
    assert store.model is None
    # After clearing, a later keyword-less prompt uses the configured model.
    out2 = apply_prompt_model_keyword(
        _request("anything"), aliases_loader=_aliases, active_store=store
    )
    assert out2.model == "nvidia_nim/test-model"


def test_new_keyword_overwrites_active_store() -> None:
    store = FakeActiveStore("kimi/kimi-k2.7-code")
    out = apply_prompt_model_keyword(
        _request("-fast switch"), aliases_loader=_aliases, active_store=store
    )
    assert out.model == "groq/llama-3.3-70b"
    assert store.model == "groq/llama-3.3-70b"


def test_active_model_store_round_trips_on_disk(tmp_path) -> None:
    from config.active_model import ActiveModelStore

    path = tmp_path / "active-model.json"
    store = ActiveModelStore(path=path)
    apply_prompt_model_keyword(
        _request("-kimi2.7 do it"), aliases_loader=_aliases, active_store=store
    )
    # A fresh store loads the persisted selection (survives restart).
    assert ActiveModelStore(path=path).load() == "kimi/kimi-k2.7-code"
