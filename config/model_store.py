"""Persistence of discovered provider models and editable keyword aliases.

Two JSON files live under ``~/.fcc/``:

- ``models.json`` -- the accumulated catalog of models each provider has
  advertised. Refreshing a provider merges its current model list into this
  catalog (union, deduplicated); models are never dropped so the catalog acts
  as a stable lookup table.
- ``model-aliases.json`` -- a user-editable map of friendly keyword -> model
  reference (``provider_id/model_id``). On refresh we *seed* a suggested alias
  for every catalogued model that does not yet have one, but we never modify or
  remove entries the user already curated. A keyword is meant to be used at the
  start of a prompt as ``-<keyword>`` to force that model.

All writes are atomic (temp file + ``os.replace``) and best-effort: a failure to
persist must never break a model refresh.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from loguru import logger

from .paths import model_aliases_path, models_catalog_path

_CATALOG_HELP = (
    "Models advertised by each provider, accumulated and deduplicated on every "
    "Refresh. This is a lookup table; edit at your own risk."
)
_ALIASES_HELP = (
    "Map a friendly keyword to a provider/model reference. Use it at the start "
    "of a prompt as -<keyword> to force that model. Suggestions are seeded on "
    "Refresh and never overwrite or delete your own entries."
)

# Keyword slug: lowercase, keep alphanumerics and dots (e.g. 'k2.7'), collapse
# every other run of characters into a single dash.
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9.]+")


def model_ref(provider_id: str, model_id: str) -> str:
    """Return the direct-routing reference understood by the model router."""
    return f"{provider_id}/{model_id}"


def suggest_keyword(model_id: str) -> str:
    """Derive a default keyword slug from a model id (without the ``-`` sigil)."""
    slug = _SLUG_STRIP_RE.sub("-", model_id.lower()).strip("-")
    return slug or "model"


def load_catalog(path: Path | None = None) -> dict[str, list[str]]:
    """Load the discovered-models catalog as ``{provider_id: [model_id, ...]}``."""
    data = _read_json(path or models_catalog_path())
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, dict):
        return {}
    catalog: dict[str, list[str]] = {}
    for provider_id, models in providers.items():
        if not isinstance(models, list):
            continue
        catalog[str(provider_id)] = [str(m) for m in models if str(m).strip()]
    return catalog


def merge_catalog(
    existing: Mapping[str, Iterable[str]], new: Mapping[str, Iterable[str]]
) -> dict[str, list[str]]:
    """Union new model ids into the existing catalog, deduplicated and sorted."""
    merged: dict[str, set[str]] = {
        provider_id: {str(m) for m in models if str(m).strip()}
        for provider_id, models in existing.items()
    }
    for provider_id, models in new.items():
        bucket = merged.setdefault(provider_id, set())
        bucket.update(str(m) for m in models if str(m).strip())
    return {provider_id: sorted(models) for provider_id, models in merged.items()}


def load_aliases(path: Path | None = None) -> dict[str, str]:
    """Load the keyword -> model-reference alias map."""
    data = _read_json(path or model_aliases_path())
    aliases = data.get("aliases") if isinstance(data, dict) else None
    if not isinstance(aliases, dict):
        return {}
    return {
        str(keyword): str(ref)
        for keyword, ref in aliases.items()
        if str(keyword).strip() and str(ref).strip()
    }


def seed_aliases(
    catalog: Mapping[str, Iterable[str]], existing: Mapping[str, str]
) -> dict[str, str]:
    """Return aliases with a suggested keyword added for every uncovered model.

    Existing user entries are preserved verbatim. A model already reachable via
    some keyword is skipped. Keyword collisions between distinct models are
    disambiguated by prefixing the provider id, then a numeric suffix.
    """
    aliases = dict(existing)
    covered_refs = set(aliases.values())

    for provider_id in sorted(catalog):
        for model_id in sorted(catalog[provider_id]):
            ref = model_ref(provider_id, model_id)
            if ref in covered_refs:
                continue
            keyword = _unique_keyword(suggest_keyword(model_id), provider_id, aliases)
            aliases[keyword] = ref
            covered_refs.add(ref)
    return aliases


def persist_refreshed_models(
    refreshed: Mapping[str, Iterable[str]],
    *,
    catalog_path: Path | None = None,
    aliases_path: Path | None = None,
) -> dict[str, int]:
    """Merge refreshed models into the catalog and seed alias suggestions.

    Best-effort: returns a summary on success, an empty dict on failure (logged).
    """
    catalog_file = catalog_path or models_catalog_path()
    aliases_file = aliases_path or model_aliases_path()
    try:
        existing_catalog = load_catalog(catalog_file)
        merged = merge_catalog(existing_catalog, refreshed)
        new_models = sum(len(merged[p]) for p in merged) - sum(
            len(existing_catalog.get(p, [])) for p in merged
        )
        _write_json(catalog_file, {"_help": _CATALOG_HELP, "providers": merged})

        existing_aliases = load_aliases(aliases_file)
        seeded = seed_aliases(merged, existing_aliases)
        _write_json(aliases_file, {"_help": _ALIASES_HELP, "aliases": seeded})

        return {
            "providers": len(merged),
            "models": sum(len(models) for models in merged.values()),
            "new_models": max(0, new_models),
            "aliases": len(seeded),
            "new_aliases": len(seeded) - len(existing_aliases),
        }
    except OSError as exc:
        logger.warning("Could not persist refreshed models: {}", exc)
        return {}


def _unique_keyword(base: str, provider_id: str, aliases: Mapping[str, str]) -> str:
    """Return a keyword not already used by a different model reference."""
    if base not in aliases:
        return base
    prefixed = f"{suggest_keyword(provider_id)}-{base}"
    if prefixed not in aliases:
        return prefixed
    counter = 2
    while f"{prefixed}-{counter}" in aliases:
        counter += 1
    return f"{prefixed}-{counter}"


def _read_json(path: Path) -> Any:
    """Return parsed JSON, or ``None`` when the file is missing/unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _write_json(path: Path, data: Any) -> None:
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
