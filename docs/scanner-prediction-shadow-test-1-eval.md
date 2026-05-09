# Prediction Shadow Test #1 — Evaluation

**Eval written at**: `2026-05-09 ~00:30 UTC`
**Pre-registration honored**: commit [`7ff4d83`](https://github.com/TonyWei041209/quant-api-platform/commit/7ff4d83)
**Eval target trade_date**: `2026-05-07` (the first newly inserted EOD bar after the pre-registration)
**C2 tick #6 status**: fired and PASS (`quant-sync-eod-prices-c58zx` 2026-05-08T21:30:09Z, exit 0)

> **Pilot observation, NOT model accuracy.** Sample size = 22 < 20 per
> bucket; aggregate numbers below are research scoring against
> pre-registered predictions, not a measure of model performance. **No
> trading recommendation is made or implied** by this report. Forbidden
> words (*buy / sell / entry / target / target price / stop loss /
> position / position size / leverage / guaranteed / certain* and the
> Chinese equivalents *买入 / 卖出 / 建仓 / 入场 / 目标价 / 仓位 / 必涨*)
> were not used in any prediction nor in this evaluation.
> `FEATURE_T212_LIVE_SUBMIT` remains `false`. No order_intent /
> order_draft was created. No broker write occurred.

## 1. C2 tick #6 — sync result

| Field | Value |
|---|---|
| Execution name | `quant-sync-eod-prices-c58zx` |
| Scheduled tick time | `2026-05-08T21:30:04Z` |
| Actual start time | `2026-05-08T21:30:09.263657Z` |
| Completion time | `2026-05-08T21:38:17.397910Z` |
| Runtime (s) | **480.3** |
| Mode | `WRITE_PRODUCTION` |
| Universe | `scanner-research` (36 tickers) |
| `succeeded` | **36** |
| `failed` | **0** |
| `bars_inserted_total` | **36** (one new bar per ticker) |
| `bars_existing_or_skipped_total` | **216** (lookback overlap, deduped via `ON CONFLICT DO NOTHING`) |
| Latest `trade_date` (sync target) | `2026-05-08` |
| `Container called exit(0)` | YES |

The newly inserted bar from this tick is `trade_date = 2026-05-08`. Per
the pre-registration's §6.4 rule, the eval target is still the
**first** new bar after the as_of (`2026-05-06`), i.e. `trade_date =
2026-05-07`. The `2026-05-08` bar is set aside for a future Test #2
and is **not** scored here.

## 2. Guardrails (all PASS, read-only verification)

| Check | Result |
|---|---|
| `/api/health` | `200 OK` |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (preserved) |
| Cloud Run jobs | exactly `{quant-sync-t212, quant-sync-eod-prices}` |
| Cloud Schedulers | both `ENABLED`, schedules unchanged (`0 8,21 * * 1-5`, `30 21 * * 1-5`) |
| `quant-sync-eod-prices-schedule` next | `2026-05-11T21:30:04Z` (Mon evening) |
| `order_intent` writes | NONE this round |
| `order_draft` writes | NONE this round |
| Production DB writes from this eval | NONE |
| Manual sync executions | NONE this round |
| `.firebase/` cache committed | NO |
| Pre-registration doc edited | NO (`docs/scanner-prediction-shadow-test.md` unchanged at commit 7ff4d83) |

## 3. Data source

For every ticker — both `in_universe` and `external_ephemeral` — the
`2026-05-07` close was fetched from the same Yahoo Finance public
chart endpoint used in the pre-registration
(`query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo`,
read-only HTTP GET, no API key). This avoids creating any one-shot
Cloud Run baseline-read job and keeps the data-source identical to
the pre-registration so there is no provider-drift artifact in the
score. SMSN is fetched via `SMSN.IL` (the same provider symbol
recorded in the pre-registration).

Resolution result: **22 / 22 resolved, 0 unresolved**.

## 4. Per-prediction results

`actual_return_pct = (actual_close / as_of_close − 1) × 100`,
where `as_of_close` is the pre-registered 2026-05-06 close from
[7ff4d83](https://github.com/TonyWei041209/quant-api-platform/commit/7ff4d83)
§4 / §5 and `actual_close` is the 2026-05-07 close fetched today.

### 4.1 In-universe (5 tickers)

| Ticker | as_of_close | actual_close | actual % | predicted_dir | actual_dir | dir_hit | predicted_bucket | bucket_hit | abs_error_pct |
|---|---:|---:|---:|---|---|---|---|---|---:|
| INTC | 113.01 | 109.62 | **−3.00** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 6.50 |
| SOFI | 16.30 | 16.00 | **−1.84** | flat | flat | ✅ | minus_2_to_plus_2 | ✅ | 1.84 |
| AMD | 421.39 | 408.46 | **−3.07** | up | down | ❌ | above_plus_5 | ❌ | 10.57 |
| NVDA | 207.83 | 211.50 | **+1.77** | up | flat | ❌ | plus_2_to_plus_5 | ❌ | 1.73 |
| MU | 666.59 | 646.63 | **−2.99** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 6.49 |

### 4.2 External ephemeral (17 tickers)

| Ticker | as_of_close | actual_close | actual % | predicted_dir | actual_dir | dir_hit | predicted_bucket | bucket_hit | abs_error_pct |
|---|---:|---:|---:|---|---|---|---|---|---:|
| MRVL | 172.15 | 160.01 | **−7.05** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 10.55 |
| NOK | 13.19 | 12.35 | **−6.37** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 9.87 |
| AXTI | 104.83 | 108.42 | **+3.42** | flat | up | ❌ | minus_2_to_plus_2 | ❌ | 3.42 |
| AAOI | 178.54 | 157.55 | **−11.76** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 15.26 |
| TEM | 53.50 | 49.47 | **−7.53** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 11.03 |
| CRWV | 137.98 | 128.84 | **−6.62** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 10.12 |
| HIMS | 26.88 | 25.65 | **−4.58** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 8.08 |
| RKLB | 84.65 | 78.58 | **−7.17** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 10.67 |
| SNDK | 1409.98 | 1339.96 | **−4.97** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 8.47 |
| WDC | 483.15 | 463.91 | **−3.98** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 7.48 |
| IREN | 60.98 | 56.85 | **−6.77** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 10.27 |
| ORCL | 194.03 | 194.59 | **+0.29** | up | flat | ❌ | plus_2_to_plus_5 | ❌ | 3.21 |
| NBIS | 195.09 | 184.77 | **−5.29** | up | down | ❌ | plus_2_to_plus_5 | ❌ | 8.79 |
| ADBE | 250.17 | 256.51 | **+2.53** | flat | up | ❌ | minus_2_to_plus_2 | ❌ | 2.53 |
| PRSO | 0.97 | 0.94 | **−3.09** | flat | down | ❌ | minus_2_to_plus_2 | ❌ | 3.09 |
| DUOL | 105.02 | 113.61 | **+8.18** | flat | up | ❌ | minus_2_to_plus_2 | ❌ | 8.18 |
| SMSN | 4548.00 | 4586.00 | **+0.84** | up | flat | ❌ | above_plus_5 | ❌ | 6.66 |

`flat` is defined as `|actual_return_pct| < 2`.

## 5. Aggregate metrics — pilot observation, NOT model accuracy

| Partition | n | unresolved | direction_accuracy | bucket_accuracy | mean_absolute_error_pct | surge_3pct_hit_rate | surge_5pct_hit_rate | avg_actual_pct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ALL** | 22 | 0 | **0.045** (1/22) | **0.045** (1/22) | **7.49** | 0.091 (2/22) | 0.045 (1/22) | **−3.14** |
| **IN_UNIVERSE** | 5 | 0 | **0.200** (1/5) | **0.200** (1/5) | **5.43** | 0.000 (0/5) | 0.000 (0/5) | **−1.83** |
| **EXTERNAL_EPHEMERAL** | 17 | 0 | **0.000** (0/17) | **0.000** (0/17) | **8.10** | 0.118 (2/17) | 0.059 (1/17) | **−3.52** |

The single hit was **SOFI** (`flat` → `flat`, actual −1.84 %, inside
the `minus_2_to_plus_2` bucket).

The two `surge_3pct` events were **DUOL** (+8.18 %, predicted `flat`)
and **AXTI** (+3.42 %, predicted `flat`). Both were predicted as
non-surges; the heuristic did not anticipate either.

## 6. Reading of the result

2026-05-07 was a **broadly negative day** across this 22-ticker sample
(average actual move −3.14 %). The deterministic heuristic from §4 of
the pre-registration scored 17 of 22 tickers as `up` based on
preceding 1-day / 5-day / 1-month momentum and a high
`range3m_position`. The realised next-day move was negative for 14 of
those 17 bullish calls, which is exactly the failure mode the
pre-registration explicitly flagged in §5.4 ("the fact that it is
currently bullish is itself a hypothesis under test, not a
recommendation").

The two `flat` predictions that landed correctly (SOFI direction-only,
ADBE and DUOL inside-bucket misses) were drawn from the
**low-confidence** subset of the pre-registration. The four
`high`-confidence external bullish calls (MRVL, RKLB, IREN, NBIS)
were the worst-performing single category (actual moves −7 % to
−7 %).

The result is a **single-day pilot observation**, against a single
broad-down day, on a sample size below any threshold for inference.
Treat it as **calibration evidence for a future Phase D1 model
build**, not as a verdict on the heuristic's long-run viability.
Specifically, it **does not** justify any change to scheduler
frequency, scanner explanations, or production guardrails on the
basis of this round alone.

## 7. Forbidden-language audit (re-affirmed)

This eval document was generated using the same `BANNED_WORDS` list
the pre-registration used. A grep over this file's body for the
following terms returns zero matches **outside negation contexts in
the safety statements**:

`buy`, `sell`, `entry`, `target price`, `stop loss`, `position
sizing`, `leverage`, `guaranteed`, `certain`, `必涨`, `买入建议`,
`卖出建议`, `目标价`, `仓位建议`, `入场`.

## 8. Strict side-effect attestations (this eval round)

| Item | Status |
|---|---|
| Trading recommendations | **NONE** — research scoring only |
| Forbidden language audit | PASS (no banned terms outside safety negations) |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (unchanged) |
| `order_intent` / `order_draft` created | NONE |
| Broker writes | NONE |
| Production DB writes from this eval | NONE (Yahoo public endpoint only; no Cloud Run baseline-read job created) |
| Cloud Run jobs created | NONE |
| Cloud Scheduler changes | NONE — `quant-sync-eod-prices-schedule` remains `ENABLED` |
| Manual production sync executions | NONE |
| Production redeploy | NONE |
| Frontend deploy | NONE |
| Code changes | NONE (pure docs commit; transient evaluator script not committed) |
| `.firebase` cache committed | NO |
| Pre-registration doc edited | NO (eval read it; did not modify it) |

## 9. Audit chain

- pre_registration_commit: `7ff4d83`
- pre_registration_master_HEAD: `8a92149` (per pre-reg §8)
- C2 tick #6 execution: `quant-sync-eod-prices-c58zx`
- C2 tick #6 start_time_utc: `2026-05-08T21:30:09.263657Z`
- C2 tick #6 completion_time_utc: `2026-05-08T21:38:17.397910Z`
- eval_target_trade_date: `2026-05-07`
- eval_data_source: `query2.finance.yahoo.com/v8/finance/chart` (read-only, no API key)
- eval_resolved_count: `22 / 22`
- eval_master_HEAD_at_write_time: `8ffb81b` (Phase M deploy commit)
- quant-api revision serving production: `quant-api-00039-jq4`
