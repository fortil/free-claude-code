"""Tests for config/model_store.py (catalog persistence + alias seeding)."""

from __future__ import annotations

import json
from unittest.mock import patch

from config.model_store import (
    load_aliases,
    load_catalog,
    merge_catalog,
    persist_refreshed_models,
    seed_aliases,
    suggest_keyword,
)


def test_suggest_keyword_slug_rules() -> None:
    assert suggest_keyword("kimi-k2.7-code") == "kimi-k2.7-code"
    assert suggest_keyword("01-ai/yi-large") == "01-ai-yi-large"
    assert suggest_keyword("models/aqa") == "models-aqa"
    assert suggest_keyword("GPT-4o") == "gpt-4o"
    assert suggest_keyword("  ") == "model"


def test_merge_catalog_unions_and_dedupes() -> None:
    existing = {"kimi": ["kimi-k2.6"], "openai": ["gpt-4o"]}
    new = {"kimi": ["kimi-k2.6", "kimi-k2.7-code"], "gemini": ["models/aqa"]}
    merged = merge_catalog(existing, new)
    assert merged["kimi"] == ["kimi-k2.6", "kimi-k2.7-code"]  # deduped + sorted
    assert merged["openai"] == ["gpt-4o"]  # untouched
    assert merged["gemini"] == ["models/aqa"]  # new provider added


def test_merge_catalog_drops_blank_model_ids() -> None:
    merged = merge_catalog({}, {"kimi": ["kimi-k2.6", "", "  "]})
    assert merged["kimi"] == ["kimi-k2.6"]


def test_load_catalog_missing_or_malformed_returns_empty(tmp_path) -> None:
    assert load_catalog(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert load_catalog(bad) == {}


def test_load_catalog_corrupt_file_warns_visibly(tmp_path) -> None:
    """A corrupt models.json must not look identical to "nothing discovered yet"."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with patch("config.json_store.logger.bind") as mock_bind:
        load_catalog(bad)
    mock_bind.assert_called_once_with(console=True)


def test_load_aliases_corrupt_file_warns_visibly(tmp_path) -> None:
    """Regression: a corrupted model-aliases.json made every -keyword look
    unrecognized with zero signal as to why."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with patch("config.json_store.logger.bind") as mock_bind:
        assert load_aliases(bad) == {}
    mock_bind.assert_called_once_with(console=True)


def test_persist_refreshed_models_write_failure_warns_visibly(tmp_path) -> None:
    catalog_path = tmp_path / "models.json"
    aliases_path = tmp_path / "model-aliases.json"
    with (
        patch("config.model_store.write_json", side_effect=OSError("disk full")),
        patch("config.model_store.logger.bind") as mock_bind,
    ):
        result = persist_refreshed_models(
            {"kimi": ["kimi-k2.7-code"]},
            catalog_path=catalog_path,
            aliases_path=aliases_path,
        )
    assert result == {}
    mock_bind.assert_called_once_with(console=True)


def test_seed_aliases_adds_suggestions_and_keeps_user_entries() -> None:
    catalog = {"kimi": ["kimi-k2.7-code"], "openai": ["gpt-4o"]}
    existing = {"kimi2.7": "kimi/kimi-k2.7-code"}  # user-curated, covers that model
    seeded = seed_aliases(catalog, existing)
    # User's keyword is preserved verbatim.
    assert seeded["kimi2.7"] == "kimi/kimi-k2.7-code"
    # The already-covered model is not given a second keyword.
    assert sum(v == "kimi/kimi-k2.7-code" for v in seeded.values()) == 1
    # The uncovered model gets a seeded suggestion.
    assert seeded["gpt-4o"] == "openai/gpt-4o"


def test_seed_aliases_disambiguates_keyword_collisions() -> None:
    catalog = {"openai": ["gpt-4o"], "azure": ["gpt-4o"]}
    seeded = seed_aliases(catalog, {})
    # Both models are addressable under distinct keywords (no clobbering).
    assert set(seeded.values()) == {"openai/gpt-4o", "azure/gpt-4o"}
    assert len(seeded) == 2
    # One keeps the base slug; the other is disambiguated with a provider prefix.
    assert "gpt-4o" in seeded
    assert {"openai-gpt-4o", "azure-gpt-4o"} & set(seeded)


def test_persist_round_trip_and_incremental_merge(tmp_path) -> None:
    catalog_path = tmp_path / "models.json"
    aliases_path = tmp_path / "model-aliases.json"

    summary = persist_refreshed_models(
        {"kimi": ["kimi-k2.6"]},
        catalog_path=catalog_path,
        aliases_path=aliases_path,
    )
    assert summary["new_models"] == 1
    assert summary["new_aliases"] == 1
    assert load_catalog(catalog_path) == {"kimi": ["kimi-k2.6"]}

    # A second refresh adds a new model without duplicating the old one.
    summary2 = persist_refreshed_models(
        {"kimi": ["kimi-k2.6", "kimi-k2.7-code"]},
        catalog_path=catalog_path,
        aliases_path=aliases_path,
    )
    assert load_catalog(catalog_path)["kimi"] == ["kimi-k2.6", "kimi-k2.7-code"]
    assert summary2["new_models"] == 1


def test_persist_preserves_user_edited_alias_across_refresh(tmp_path) -> None:
    catalog_path = tmp_path / "models.json"
    aliases_path = tmp_path / "model-aliases.json"
    persist_refreshed_models(
        {"kimi": ["kimi-k2.7-code"]},
        catalog_path=catalog_path,
        aliases_path=aliases_path,
    )
    # Simulate the user curating a short, friendly keyword.
    data = json.loads(aliases_path.read_text(encoding="utf-8"))
    data["aliases"] = {"kimi2.7": "kimi/kimi-k2.7-code"}
    aliases_path.write_text(json.dumps(data), encoding="utf-8")

    persist_refreshed_models(
        {"kimi": ["kimi-k2.7-code", "kimi-k2.6"]},
        catalog_path=catalog_path,
        aliases_path=aliases_path,
    )
    aliases = load_aliases(aliases_path)
    # User's curated keyword survives, and the covered model is not re-seeded.
    assert aliases["kimi2.7"] == "kimi/kimi-k2.7-code"
    assert sum(v == "kimi/kimi-k2.7-code" for v in aliases.values()) == 1
    # The newly discovered model gets its own suggestion.
    assert "kimi-k2.6" in aliases


def test_persist_writes_help_text_and_sorted_json(tmp_path) -> None:
    catalog_path = tmp_path / "models.json"
    aliases_path = tmp_path / "model-aliases.json"
    persist_refreshed_models(
        {"kimi": ["b-model", "a-model"]},
        catalog_path=catalog_path,
        aliases_path=aliases_path,
    )
    catalog_doc = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert "_help" in catalog_doc
    assert catalog_doc["providers"]["kimi"] == ["a-model", "b-model"]
    aliases_doc = json.loads(aliases_path.read_text(encoding="utf-8"))
    assert "_help" in aliases_doc
    assert isinstance(aliases_doc["aliases"], dict)
