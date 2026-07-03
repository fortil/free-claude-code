"""Persistence of accumulated token usage per provider, model, and day.

Stored as JSON under ``~/.fcc/usage.json``. Only **token counts** are kept here;
dollar cost is derived at read time from the pricing layer so price edits re-cost
historical usage. Writes are atomic (temp file + ``os.replace``) and best-effort:
a failure to persist must never break a request.

Schema::

    {
      "providers": {
        "<provider_id>": {
          "models": {"<model_id>": {"input_tokens", "output_tokens", "requests"}},
          "daily":  {"<YYYY-MM-DD>": {"input_tokens", "output_tokens", "requests"}}
        }
      }
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from .json_store import read_json, write_json
from .paths import usage_store_path


def load_usage(path: Path | None = None) -> dict[str, Any]:
    """Load the usage store, returning an empty ``{"providers": {}}`` on absence."""
    data = read_json(path or usage_store_path())
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, dict):
        return {"providers": {}}
    return {"providers": providers}


def record_usage(
    usage: dict[str, Any],
    *,
    provider_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    day: str,
) -> dict[str, Any]:
    """Return ``usage`` with one request's tokens added to the model and day buckets."""
    providers = usage.setdefault("providers", {})
    provider = providers.setdefault(provider_id, {})
    models = provider.setdefault("models", {})
    daily = provider.setdefault("daily", {})
    _add(models.setdefault(model_id or "unknown", {}), input_tokens, output_tokens)
    _add(daily.setdefault(day, {}), input_tokens, output_tokens)
    return usage


def save_usage(usage: dict[str, Any], path: Path | None = None) -> bool:
    """Atomically persist the usage store. Returns False on failure (logged)."""
    try:
        write_json(path or usage_store_path(), usage)
        return True
    except OSError as exc:
        logger.bind(console=True).warning("Could not persist usage store: {}", exc)
        return False


def _add(bucket: dict[str, Any], input_tokens: int, output_tokens: int) -> None:
    bucket["input_tokens"] = int(bucket.get("input_tokens", 0)) + max(0, input_tokens)
    bucket["output_tokens"] = int(bucket.get("output_tokens", 0)) + max(
        0, output_tokens
    )
    bucket["requests"] = int(bucket.get("requests", 0)) + 1
