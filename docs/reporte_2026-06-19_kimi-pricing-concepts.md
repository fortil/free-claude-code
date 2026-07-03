# Report: Moonshot / Kimi billing concepts — BatchJob vs Recharge & Rate Limiting vs Promotion

**Date:** 2026-06-19
**Author:** William Penagos

## Summary

Moonshot (Kimi) mixes three unrelated ideas under "pricing". They answer different
questions and never overlap:

| Concept | Question it answers | Axis |
|---|---|---|
| **BatchJob (Batch API)** | *How much does a token cost, and in what processing mode?* | Price + execution mode |
| **Recharge & Rate Limiting** | *How fast / how much can I send right now?* | Throughput limits |
| **Promotion** | *What do I get for putting money in?* | Credits + tier upgrades |

FCC's Usage tab models only the **standard, real-time, cache-miss** price. It does
not model batch discounts, cache-hit discounts, or rate-limit tiers — those are
Moonshot-side billing/throughput concepts, not per-request token costs.

## Detail

### 1. BatchJob (Batch API) — a cheaper, offline processing mode

- **Price:** Batch inference costs **60% of the standard model price** (a 40%
  discount). Example: `kimi-k2.7-code` standard output is $4.00/1M, batch is $2.40/1M.
- **Use case:** large-scale tasks with **low real-time requirements** — bulk/offline
  jobs you submit and collect later, not interactive coding.
- **Not real-time:** batch jobs are **not subject to the real-time concurrency / RPM
  limits**; instead each task must finish inside a `completion_window` or it
  **expires**.
- **Coverage:** `kimi-k2.7-code`, `kimi-k2.6`, `kimi-k2.5`.
- **Takeaway:** Batch changes *price and how the work is scheduled*. It is a
  different endpoint/mode, not a different rate limit.

### 2. Recharge & Rate Limiting — throughput tied to how much you've paid in

- Rate limits are tied to your **cumulative recharge amount** (total money added to
  the account), bucketed into tiers **Tier0 → Tier5**.
- Each tier sets four throughput knobs:
  - **Concurrency** — max simultaneous in-flight requests.
  - **RPM** — requests per minute.
  - **TPM** — tokens per minute.
  - **TPD** — tokens per day.
- Examples: **Tier0** ($1) → concurrency 1, RPM 3, TPM 500k, TPD 1.5M.
  **Tier5** ($3,000) → concurrency 1,000, RPM 10,000, TPM 5M, TPD unlimited.
- **Takeaway:** This governs *speed and volume*, never the per-token price. Spending
  more money raises your ceilings; it does not change what a token costs.

### 3. Promotion — incentives and tier upgrades for recharging

Two promotional mechanics, both keyed off recharge:

- **Voucher / credit promo:** you must recharge at least **$1** to start using the
  API, and once cumulative recharge reaches **$5** you receive a **$5 voucher**
  (free credit).
- **Tier promotion:** recharging more money **promotes** you up the rate-limit tiers
  (Section 2), unlocking higher concurrency/RPM/TPM/TPD. The "promotion" is the
  upgrade path, not a discount on tokens.
- **Takeaway:** Promotion is about *incentives to recharge* (free credit) and *the
  reward for recharging* (higher limits) — orthogonal to both batch pricing and the
  per-token price.

### How this maps to FCC

- FCC's `~/.fcc/model-pricing.json` stores one **input** and one **output** price per
  1M tokens. We use the **cache-miss (full) input** rate from the standard tables —
  not cache-hit, not batch.
- The Usage tab therefore reports a **standard real-time cost estimate**. Real bills
  can be **lower** if you hit prompt cache (cache-hit input is much cheaper, e.g.
  $0.19 vs $0.95 for `kimi-k2.7-code`) or use the Batch API (×0.60).
- Rate-limit tiers and vouchers are **not** reflected in FCC cost numbers; they
  affect throughput and account credit on Moonshot's side only.

## Conclusions

- **BatchJob = price/mode**, **Recharge & Rate Limiting = throughput**, **Promotion =
  credits + tier upgrades**. They are independent and answer different questions.
- FCC tracks tokens and estimates cost at the **standard cache-miss** rate; treat the
  Usage tab as an upper-bound estimate that ignores cache and batch discounts.
- If you run large offline jobs, the Batch API (60% price, `completion_window`,
  relaxed concurrency) is the lever for cost; if you are throttled, recharging to a
  higher tier is the lever for speed.
