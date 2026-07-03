"""Persistent 'active model' override selected by a prompt ``-keyword``.

Unlike the in-prompt keyword (which is lost when a client compacts/ summarizes
the conversation), this selection is stored at ``~/.fcc/active-model.json`` and
applied to every subsequent request until a new ``-keyword`` or ``-default``
changes it — so it survives context compaction and restarts. ``ActiveModelStore``
keeps the value in memory (read on every request) and writes through on change.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from loguru import logger

from .json_store import read_json, write_json
from .paths import active_model_path


def load_active_model(path: Path | None = None) -> str | None:
    """Return the persisted active model reference, or None when unset/invalid."""
    data = read_json(path or active_model_path())
    model = data.get("model") if isinstance(data, dict) else None
    return model if isinstance(model, str) and model.strip() else None


def save_active_model(model_ref: str, path: Path | None = None) -> None:
    """Persist the active model reference (best-effort; logs on failure)."""
    try:
        write_json(path or active_model_path(), {"model": model_ref})
    except OSError as exc:
        logger.bind(console=True).warning("Could not persist active model: {}", exc)


def clear_active_model(path: Path | None = None) -> None:
    """Remove the persisted active model (best-effort)."""
    with contextlib.suppress(OSError):
        (path or active_model_path()).unlink()


class ActiveModelStore:
    """In-memory, disk-backed holder for the active model selection."""

    def __init__(self, *, path: Path | None = None) -> None:
        self._path = path
        self._model = load_active_model(path)

    def load(self) -> str | None:
        return self._model

    def save(self, model_ref: str) -> None:
        self._model = model_ref
        save_active_model(model_ref, self._path)

    def clear(self) -> None:
        self._model = None
        clear_active_model(self._path)
