"""Tests for config/json_store.py (shared atomic JSON read/write helpers)."""

from __future__ import annotations

from unittest.mock import patch

from config.json_store import read_json, write_json


def test_read_json_missing_file_is_silent(tmp_path) -> None:
    with patch("config.json_store.logger.bind") as mock_bind:
        result = read_json(tmp_path / "absent.json")
    assert result is None
    mock_bind.assert_not_called()


def test_read_json_corrupt_file_returns_none_and_warns_visibly(tmp_path) -> None:
    """A file that exists but fails to parse must not be silently indistinguishable
    from "nothing configured yet" -- that hid a real bug (a corrupted
    model-aliases.json made every -keyword look unrecognized with zero signal)."""
    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json", encoding="utf-8")

    with patch("config.json_store.logger.bind") as mock_bind:
        result = read_json(path)

    assert result is None
    mock_bind.assert_called_once_with(console=True)
    args = mock_bind.return_value.warning.call_args[0]
    assert args[1] == path


def test_write_json_then_read_json_round_trips(tmp_path) -> None:
    path = tmp_path / "nested" / "data.json"
    write_json(path, {"hello": "world"})
    assert read_json(path) == {"hello": "world"}


def test_write_json_leaves_no_temp_file_behind(tmp_path) -> None:
    path = tmp_path / "data.json"
    write_json(path, {"a": 1})
    leftovers = [p for p in tmp_path.iterdir() if p.name != "data.json"]
    assert leftovers == []
