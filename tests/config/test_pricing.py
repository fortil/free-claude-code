"""Tests for config/pricing.py (hybrid pricing + cost computation)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from config.pricing import (
    ModelPrice,
    build_usage_report,
    compute_cost,
    load_pricing_overrides,
    resolve_price,
    seed_pricing_template,
)


def test_compute_cost_math() -> None:
    price = ModelPrice(input_per_million=2.5, output_per_million=10.0)
    # 1M input + 0.5M output = 2.5 + 5.0 = 7.5
    assert compute_cost(1_000_000, 500_000, price) == pytest.approx(7.5)


def test_load_overrides_parses_and_skips_nulls(tmp_path) -> None:
    path = tmp_path / "model-pricing.json"
    path.write_text(
        json.dumps(
            {
                "prices": {
                    "kimi/kimi-k2.7-code": {
                        "input_per_million": 0.6,
                        "output_per_million": 2.5,
                    },
                    "kimi/unpriced": {
                        "input_per_million": None,
                        "output_per_million": None,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    overrides = load_pricing_overrides(path)
    assert overrides == {"kimi/kimi-k2.7-code": ModelPrice(0.6, 2.5)}


def test_override_wins_over_tokencost() -> None:
    overrides = {"openai/gpt-4o": ModelPrice(1.0, 2.0)}
    price = resolve_price("openai", "gpt-4o", overrides=overrides)
    assert price == ModelPrice(1.0, 2.0)


def test_tokencost_fallback_for_known_model() -> None:
    # gpt-4o in tokencost: input 2.5e-06/token -> 2.5/M, output 1e-05/token -> 10/M.
    price = resolve_price("openai", "gpt-4o", overrides={})
    assert price is not None
    assert price.input_per_million == pytest.approx(2.5)
    assert price.output_per_million == pytest.approx(10.0)


def test_gemini_models_prefix_maps_to_tokencost() -> None:
    price = resolve_price("gemini", "models/gemini-1.5-pro", overrides={})
    assert price is not None
    assert price.input_per_million > 0


def test_unknown_model_returns_none() -> None:
    assert resolve_price("kimi", "kimi-k2.7-code-highspeed", overrides={}) is None


def test_build_usage_report_joins_tokens_and_cost() -> None:
    snapshot = {
        "providers": {
            "kimi": {
                "models": {
                    "priced": {
                        "input_tokens": 1_000_000,
                        "output_tokens": 0,
                        "requests": 1,
                    },
                    "free": {"input_tokens": 500, "output_tokens": 200, "requests": 2},
                },
                "daily": {
                    "2026-06-19": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "requests": 1,
                    }
                },
            }
        }
    }
    overrides = {"kimi/priced": ModelPrice(3.0, 6.0)}
    report = build_usage_report(snapshot, overrides=overrides)

    provider = report["providers"][0]
    assert provider["provider_id"] == "kimi"
    assert provider["input_tokens"] == 1_000_500
    # Only the priced model contributes cost: 1M input * $3/M = $3.
    assert provider["cost_usd"] == pytest.approx(3.0)
    models = {m["model_id"]: m for m in provider["models"]}
    assert models["priced"]["cost_usd"] == pytest.approx(3.0)
    assert models["free"]["cost_usd"] is None
    assert provider["daily"][0]["day"] == "2026-06-19"
    assert report["totals"]["cost_usd"] == pytest.approx(3.0)


def test_build_usage_report_all_unpriced_total_is_none() -> None:
    snapshot = {
        "providers": {
            "kimi": {
                "models": {"m": {"input_tokens": 1, "output_tokens": 1, "requests": 1}}
            }
        }
    }
    report = build_usage_report(snapshot, overrides={})
    assert report["providers"][0]["cost_usd"] is None
    assert report["totals"]["cost_usd"] is None
    assert report["totals"]["input_tokens"] == 1


def test_seed_pricing_template_keeps_existing(tmp_path) -> None:
    path = tmp_path / "model-pricing.json"
    path.write_text(
        json.dumps(
            {
                "prices": {
                    "kimi/kimi-k2.7-code": {
                        "input_per_million": 0.6,
                        "output_per_million": 2.5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    seed_pricing_template(
        {"kimi": ["kimi-k2.7-code", "kimi-k2.6"], "openai": ["gpt-4o"]}, path
    )
    doc = json.loads(path.read_text(encoding="utf-8"))
    prices = doc["prices"]
    # Curated price preserved.
    assert prices["kimi/kimi-k2.7-code"]["input_per_million"] == 0.6
    # New models seeded with null placeholders.
    assert prices["kimi/kimi-k2.6"] == {
        "input_per_million": None,
        "output_per_million": None,
    }
    assert "openai/gpt-4o" in prices


def test_load_overrides_corrupt_file_warns_visibly(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with patch("config.json_store.logger.bind") as mock_bind:
        assert load_pricing_overrides(bad) == {}
    mock_bind.assert_called_once_with(console=True)


def test_seed_pricing_template_write_failure_warns_visibly(tmp_path) -> None:
    path = tmp_path / "model-pricing.json"
    with (
        patch("config.pricing.write_json", side_effect=OSError("disk full")),
        patch("config.pricing.logger.bind") as mock_bind,
    ):
        result = seed_pricing_template({"kimi": ["kimi-k2.7-code"]}, path)
    assert result is False
    mock_bind.assert_called_once_with(console=True)
