"""In-memory token-usage tracker backing the Admin Usage view.

``UsageTracker`` accumulates per-provider/model/day token counts in memory (so the
Admin Usage view reads instantly) and persists them to ``~/.fcc/usage.json``,
throttled to avoid per-request disk I/O and flushed on process exit. The SSE
usage-capture wrapper lives in :func:`core.trace.record_usage_stream`.
"""

from __future__ import annotations

import atexit
import copy
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.usage_store import load_usage, record_usage, save_usage

_FLUSH_INTERVAL_SECONDS = 2.0


class UsageTracker:
    """Accumulate token usage in memory and persist it best-effort."""

    def __init__(self, *, path: Path | None = None) -> None:
        self._path = path
        self._usage = load_usage(path)
        self._dirty = False
        self._last_flush = time.monotonic()
        atexit.register(self.flush)

    def record(
        self, provider_id: str, model_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        """Add one completed request's tokens, then flush if the interval elapsed."""
        record_usage(
            self._usage,
            provider_id=provider_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            day=datetime.now(UTC).date().isoformat(),
        )
        self._dirty = True
        if time.monotonic() - self._last_flush >= _FLUSH_INTERVAL_SECONDS:
            self.flush()

    def snapshot(self) -> dict[str, Any]:
        """Return a deep copy of the current usage totals."""
        return copy.deepcopy(self._usage)

    def flush(self) -> None:
        """Persist the accumulated usage when there are unsaved changes."""
        if not self._dirty:
            return
        if save_usage(self._usage, self._path):
            self._dirty = False
            self._last_flush = time.monotonic()
