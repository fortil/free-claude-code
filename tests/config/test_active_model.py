"""Tests for config/active_model.py (persistent -keyword model override)."""

from __future__ import annotations

from unittest.mock import patch

from config.active_model import (
    ActiveModelStore,
    clear_active_model,
    load_active_model,
    save_active_model,
)


def test_load_missing_returns_none(tmp_path) -> None:
    assert load_active_model(tmp_path / "absent.json") is None


def test_save_load_round_trips(tmp_path) -> None:
    path = tmp_path / "active-model.json"
    save_active_model("kimi/kimi-k2.7-code", path)
    assert load_active_model(path) == "kimi/kimi-k2.7-code"


def test_clear_removes_file(tmp_path) -> None:
    path = tmp_path / "active-model.json"
    save_active_model("kimi/kimi-k2.7-code", path)
    clear_active_model(path)
    assert load_active_model(path) is None
    assert not path.exists()


def test_clear_missing_file_is_a_noop(tmp_path) -> None:
    clear_active_model(tmp_path / "absent.json")  # must not raise


def test_load_corrupt_file_returns_none_and_warns_visibly(tmp_path) -> None:
    """Regression: a corrupted active-model.json silently reverted a deliberate
    sticky selection to the configured default, with zero logging anywhere."""
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with patch("config.json_store.logger.bind") as mock_bind:
        assert load_active_model(bad) is None
    mock_bind.assert_called_once_with(console=True)


def test_save_write_failure_warns_visibly(tmp_path) -> None:
    path = tmp_path / "active-model.json"
    with (
        patch("config.active_model.write_json", side_effect=OSError("disk full")),
        patch("config.active_model.logger.bind") as mock_bind,
    ):
        save_active_model("kimi/kimi-k2.7-code", path)
    mock_bind.assert_called_once_with(console=True)


def test_store_loads_persisted_value_on_construction(tmp_path) -> None:
    path = tmp_path / "active-model.json"
    save_active_model("kimi/kimi-k2.7-code", path)
    store = ActiveModelStore(path=path)
    assert store.load() == "kimi/kimi-k2.7-code"


def test_store_save_updates_memory_and_disk(tmp_path) -> None:
    path = tmp_path / "active-model.json"
    store = ActiveModelStore(path=path)
    store.save("zai/glm-5.2")
    assert store.load() == "zai/glm-5.2"
    assert load_active_model(path) == "zai/glm-5.2"


def test_store_clear_updates_memory_and_disk(tmp_path) -> None:
    path = tmp_path / "active-model.json"
    store = ActiveModelStore(path=path)
    store.save("zai/glm-5.2")
    store.clear()
    assert store.load() is None
    assert load_active_model(path) is None
