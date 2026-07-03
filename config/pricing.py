"""Resolve per-model prices and compute dollar cost from token counts.

Hybrid source: a user-editable override file ``~/.fcc/model-pricing.json`` (keyed
by ``provider_id/model_id``) takes precedence, falling back to the ``tokencost``
library for mainstream models (OpenAI/Anthropic/Gemini/...). FCC's exotic
providers (nvidia_nim, kimi, wafer, z.ai, ...) are not in ``tokencost`` and rely
on the override file. Prices are expressed in USD per 1,000,000 tokens. A model
with no known price yields ``None`` (tokens are still tracked, cost is unknown).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, NamedTuple

from loguru import logger

from .json_store import read_json, write_json
from .paths import model_pricing_path

_PRICING_HELP = (
    "USD price per 1,000,000 tokens, keyed by provider_id/model_id. Fill in "
    "input_per_million / output_per_million; null means unknown (cost not shown). "
    "These override the bundled tokencost price database."
)

_TOKENS_PER_MILLION = 1_000_000


class ModelPrice(NamedTuple):
    input_per_million: float
    output_per_million: float


def load_pricing_overrides(path: Path | None = None) -> dict[str, ModelPrice]:
    """Load the user price overrides as ``{provider/model: ModelPrice}``."""
    data = read_json(path or model_pricing_path())
    prices = data.get("prices") if isinstance(data, dict) else None
    if not isinstance(prices, dict):
        return {}
    out: dict[str, ModelPrice] = {}
    for ref, entry in prices.items():
        price = _price_from_entry(entry)
        if price is not None:
            out[str(ref)] = price
    return out


def resolve_price(
    provider_id: str,
    model_id: str,
    *,
    overrides: Mapping[str, ModelPrice] | None = None,
) -> ModelPrice | None:
    """Return the price for ``provider_id/model_id``: override first, then tokencost."""
    overrides = overrides if overrides is not None else load_pricing_overrides()
    override = overrides.get(f"{provider_id}/{model_id}")
    if override is not None:
        return override
    return _tokencost_price(provider_id, model_id)


def compute_cost(input_tokens: int, output_tokens: int, price: ModelPrice) -> float:
    """Return the USD cost for the given token counts at ``price``."""
    return (
        input_tokens * price.input_per_million
        + output_tokens * price.output_per_million
    ) / _TOKENS_PER_MILLION


def build_usage_report(
    snapshot: Mapping[str, Any], *, overrides: Mapping[str, ModelPrice] | None = None
) -> dict[str, Any]:
    """Join a usage snapshot with current prices into a per-provider report.

    Cost is computed at read time so editing prices re-costs historical usage. A
    model with no known price contributes ``cost_usd=None`` (tokens still shown);
    provider/total ``cost_usd`` is ``None`` only when nothing is priced.
    """
    overrides = overrides if overrides is not None else load_pricing_overrides()
    providers: list[dict[str, Any]] = []
    total_in = total_out = total_req = 0
    total_cost = 0.0
    any_priced = False

    for provider_id, pdata in sorted((snapshot.get("providers") or {}).items()):
        models: list[dict[str, Any]] = []
        p_in = p_out = p_req = 0
        p_cost = 0.0
        p_priced = False
        for model_id, bucket in sorted((pdata.get("models") or {}).items()):
            m_in = int(bucket.get("input_tokens", 0))
            m_out = int(bucket.get("output_tokens", 0))
            m_req = int(bucket.get("requests", 0))
            price = resolve_price(provider_id, model_id, overrides=overrides)
            cost = compute_cost(m_in, m_out, price) if price is not None else None
            models.append(
                {
                    "model_id": model_id,
                    "input_tokens": m_in,
                    "output_tokens": m_out,
                    "requests": m_req,
                    "cost_usd": cost,
                }
            )
            p_in += m_in
            p_out += m_out
            p_req += m_req
            if cost is not None:
                p_cost += cost
                p_priced = True
                any_priced = True
        daily = [
            {
                "day": day,
                "input_tokens": int(bucket.get("input_tokens", 0)),
                "output_tokens": int(bucket.get("output_tokens", 0)),
                "requests": int(bucket.get("requests", 0)),
            }
            for day, bucket in sorted((pdata.get("daily") or {}).items())
        ]
        providers.append(
            {
                "provider_id": provider_id,
                "input_tokens": p_in,
                "output_tokens": p_out,
                "requests": p_req,
                "cost_usd": p_cost if p_priced else None,
                "models": models,
                "daily": daily,
            }
        )
        total_in += p_in
        total_out += p_out
        total_req += p_req
        total_cost += p_cost

    return {
        "providers": providers,
        "totals": {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "requests": total_req,
            "cost_usd": total_cost if any_priced else None,
        },
    }


def seed_pricing_template(
    catalog: Mapping[str, Iterable[str]], path: Path | None = None
) -> bool:
    """Add null-priced placeholders for catalogued models, keeping user prices.

    Best-effort; returns False on write failure (logged). Existing entries are
    never overwritten, so curated prices survive a refresh.
    """
    pricing_path = path or model_pricing_path()
    try:
        document = read_json(pricing_path)
        prices = document.get("prices") if isinstance(document, dict) else None
        prices = dict(prices) if isinstance(prices, dict) else {}
        for provider_id in sorted(catalog):
            for model_id in sorted(catalog[provider_id]):
                prices.setdefault(
                    f"{provider_id}/{model_id}",
                    {"input_per_million": None, "output_per_million": None},
                )
        write_json(pricing_path, {"_help": _PRICING_HELP, "prices": prices})
        return True
    except OSError as exc:
        logger.bind(console=True).warning("Could not seed pricing template: {}", exc)
        return False


def _price_from_entry(entry: Any) -> ModelPrice | None:
    if not isinstance(entry, Mapping):
        return None
    in_price = entry.get("input_per_million")
    out_price = entry.get("output_per_million")
    if isinstance(in_price, (int, float)) and isinstance(out_price, (int, float)):
        return ModelPrice(float(in_price), float(out_price))
    return None


def _tokencost_price(provider_id: str, model_id: str) -> ModelPrice | None:
    try:
        from tokencost import TOKEN_COSTS
    except ImportError:
        return None
    for key in _tokencost_candidates(provider_id, model_id):
        entry = TOKEN_COSTS.get(key)
        if not isinstance(entry, Mapping):
            continue
        in_token = entry.get("input_cost_per_token")
        out_token = entry.get("output_cost_per_token")
        if isinstance(in_token, (int, float)) and isinstance(out_token, (int, float)):
            return ModelPrice(
                float(in_token) * _TOKENS_PER_MILLION,
                float(out_token) * _TOKENS_PER_MILLION,
            )
    return None


def _tokencost_candidates(provider_id: str, model_id: str) -> list[str]:
    """Return tokencost key candidates for an FCC provider/model, most specific first."""
    candidates = [model_id, f"{provider_id}/{model_id}"]
    if provider_id == "gemini":
        bare = model_id.removeprefix("models/")
        candidates += [bare, f"gemini/{bare}"]
    # Last path segment (e.g. moonshotai/kimi-k2.6 -> kimi-k2.6).
    tail = model_id.rsplit("/", 1)[-1]
    if tail != model_id:
        candidates.append(tail)
    seen: set[str] = set()
    return [c for c in candidates if c and not (c in seen or seen.add(c))]
