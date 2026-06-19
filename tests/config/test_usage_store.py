"""Tests for config/usage_store.py (token usage persistence)."""

from __future__ import annotations

import json

from config.usage_store import load_usage, record_usage, save_usage


def test_load_missing_or_malformed_returns_empty(tmp_path) -> None:
    assert load_usage(tmp_path / "absent.json") == {"providers": {}}
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert load_usage(bad) == {"providers": {}}


def test_record_accumulates_model_and_day_buckets() -> None:
    usage: dict = {"providers": {}}
    record_usage(
        usage,
        provider_id="kimi",
        model_id="kimi-k2.7-code",
        input_tokens=100,
        output_tokens=20,
        day="2026-06-19",
    )
    record_usage(
        usage,
        provider_id="kimi",
        model_id="kimi-k2.7-code",
        input_tokens=50,
        output_tokens=10,
        day="2026-06-19",
    )
    model = usage["providers"]["kimi"]["models"]["kimi-k2.7-code"]
    assert model == {"input_tokens": 150, "output_tokens": 30, "requests": 2}
    day = usage["providers"]["kimi"]["daily"]["2026-06-19"]
    assert day == {"input_tokens": 150, "output_tokens": 30, "requests": 2}


def test_record_separates_providers_models_and_days() -> None:
    usage: dict = {"providers": {}}
    record_usage(
        usage,
        provider_id="kimi",
        model_id="a",
        input_tokens=1,
        output_tokens=1,
        day="2026-06-18",
    )
    record_usage(
        usage,
        provider_id="openai",
        model_id="b",
        input_tokens=2,
        output_tokens=3,
        day="2026-06-19",
    )
    providers = usage["providers"]
    assert set(providers) == {"kimi", "openai"}
    assert providers["openai"]["models"]["b"] == {
        "input_tokens": 2,
        "output_tokens": 3,
        "requests": 1,
    }
    assert set(providers["kimi"]["daily"]) == {"2026-06-18"}
    assert set(providers["openai"]["daily"]) == {"2026-06-19"}


def test_negative_tokens_are_clamped_to_zero() -> None:
    usage: dict = {"providers": {}}
    record_usage(
        usage,
        provider_id="p",
        model_id="m",
        input_tokens=-5,
        output_tokens=-1,
        day="2026-06-19",
    )
    assert usage["providers"]["p"]["models"]["m"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 1,
    }


def test_save_and_reload_round_trip(tmp_path) -> None:
    path = tmp_path / "usage.json"
    usage: dict = {"providers": {}}
    record_usage(
        usage,
        provider_id="kimi",
        model_id="kimi-k2.7-code",
        input_tokens=10,
        output_tokens=5,
        day="2026-06-19",
    )
    assert save_usage(usage, path) is True
    reloaded = load_usage(path)
    assert reloaded == usage
    # File is valid pretty JSON.
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["providers"]["kimi"]["models"]["kimi-k2.7-code"]["input_tokens"] == 10
