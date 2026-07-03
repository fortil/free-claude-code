"""Shared atomic JSON read/write helpers for the ``~/.fcc/`` config stores.

All FCC on-disk stores (models catalog, keyword aliases, active model, usage,
pricing) use the same pattern: best-effort atomic writes (temp file + ``os.replace``)
and tolerant reads that fall back to ``None`` when the file is missing or
unreadable. A missing file is a normal, expected first-run state and stays
silent; a file that exists but fails to parse is not — that state is
otherwise indistinguishable from "nothing configured yet" (e.g. a corrupted
``model-aliases.json`` makes every ``-keyword`` look unrecognized), so it is
logged loudly.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger


def read_json(path: Path) -> Any:
    """Return parsed JSON, or ``None`` when the file is missing/unreadable.

    A missing file is silent (normal on first run). A file that exists but
    fails to parse logs a console-visible warning, since silently treating
    corrupt state as "empty" is easy to mistake for nothing being configured.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.bind(console=True).warning(
            "Could not parse {} ({}); treating it as empty until fixed.", path, exc
        )
        return None


def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON to ``path`` (temp file in the same dir + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
