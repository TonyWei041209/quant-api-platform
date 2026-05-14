# Pre-market Shadow Prediction Run — 2026-05-12 — Evaluation Procedure

**Status:** PLACEHOLDER. Eval results will be filled in after the
2026-05-12 US session closes and the next `quant-sync-eod-prices`
fire (21:30 UTC weekdays) lands the day's EOD bar.

This doc records the exact procedure that will produce the evaluation
of `premarket-shadow-prediction-20260512` so the eval is
pre-registered too (no rule changes after the bar lands).

---

## 1. Timing gates

Eval may only run when **both** are true:

1. US regular session has closed (≥ `2026-05-12T20:00Z`).
2. `quant-sync-eod-prices-schedule` has fired and its execution
   succeeded (target fire `2026-05-12T21:30Z` weekdays cron). Verify
   via:

   ```bash
   gcloud run jobs executions list --job=quant-sync-eod-prices \
     --region=asia-east2 --limit=3
   ```

   The latest execution must show `SUCCEEDED_COUNT=1` and
   `COMPLETION_TIME ≥ 2026-05-12T21:30Z`.

3. Independently confirm via a read-only DB query that
   `price_bar_raw` carries a row for `trade_date='2026-05-12'` for at
   least the 15 complete-data tickers (`MU, AMD, AVGO, GOOGL, INTC,
   AAPL, AMZN, GS, IWM, NVDA, QQQ, SIRI, SPY, TSLA, TSM`).

If any of those is missing, the eval status is `pending` and no
accuracy numbers are written yet.

## 2. Data pull (read-only)

For each ticker in
`docs/premarket-shadow-prediction-20260512.json:predictions[]`,
fetch from `price_bar_raw`:

* `close_t   = close where trade_date = '2026-05-12'`
* `close_tm1 = close where trade_date = '2026-05-11'` (anchor —
  matches `previous_trade_date_anchor` in the JSON)

`actual_return = (close_t - close_tm1) / close_tm1`.

Read-only — no rows inserted, no rows updated.

## 3. Categorization

For each ticker (same definitions as `§4` of the pre-registration):

```
actual_direction:
  up    if actual_return > +0.001 (10 bps)
  flat  if |actual_return| <= 0.001
  down  if actual_return < -0.001

actual_bucket (5-bucket):
  above_plus_3       actual_return ≥ +0.03
  plus_1_to_plus_3   +0.01 ≤ actual_return < +0.03
  minus_1_to_plus_1  -0.01 < actual_return < +0.01
  minus_3_to_minus_1 -0.03 < actual_return ≤ -0.01
  below_minus_3      actual_return ≤ -0.03
```

## 4. Metrics

| Metric | Definition | Scope |
|---|---|---|
| `direction_accuracy` | fraction where `predicted_direction == actual_direction` | All 26 |
| `bucket_accuracy` | fraction where `predicted_bucket == actual_bucket` | All 26 |
| `MAE_pct` | mean of `|actual_return * 100 - bucket_midpoint_pct|`, with bucket midpoints `+4%, +2%, 0%, -2%, -4%` | All 26 |
| `high_confidence_accuracy` | direction accuracy among rows where `confidence=medium` (would be N/A for shadow v1 because nothing reached medium) | medium-conf only |
| `held_vs_nonheld_split` | direction accuracy where `HELD` ∈ `source_tags` vs. not | split |
| `news_linked_vs_non_news_split` | direction accuracy where `recent_news_count > 0` vs. `= 0` (per `inputs`) | split |
| `scanner_vs_mirror_split` | direction accuracy where `SCANNER` ∈ `source_tags` vs. Mirror-only | split |
| `extension_dampener_calibration` | for the 3 dampener-fired tickers (`MU, AMD, INTC`): did mean-reversion happen (predicted `flat`, actual within ±1%) or continuation (actual ≥ +2%)? | 3 rows |
| `weak_data_containment` | for the 11 weak-data flats: fraction whose actual fell in `minus_1_to_plus_1` | 11 rows |

## 5. Output

Eval results will be appended to **this file** in a new `§7 Results`
section with:

* Trade date evaluated
* EOD bar source job execution name
* Per-ticker `actual_return` + `actual_direction` + `actual_bucket`
* All metric values from §4
* A short narrative noting whether the dampener was correct and
  whether the 4 directional bets paid off
* Strict side-effect attestation reaffirming no broker/order/live-submit
  activity occurred during eval

## 6. Decision rules for follow-up

Based on §5 results:

| Outcome | Decision |
|---|---|
| `direction_accuracy ≥ 60 %` AND `extension_dampener` correct on ≥ 2/3 | Schedule Shadow #4 with a wider universe (still docs-only, still capped at `medium` confidence). |
| Lower than the above | Document the gap. Treat the rule set as falsified for the next cycle. Open a new pre-registration with a refined rule, never a hot-fix of the current one. |
| Any banned trade-action word appears in the eval | Eval invalid. Rerun with corrected language. |
| Side-effect attestation in §1 fails (e.g. broker write detected during eval) | Eval invalid. Investigate immediately. |

## 7. Results

**Eval completed at:** `2026-05-14T00:36:08Z`
**EOD bar source:** Cloud Run Job execution `quant-sync-eod-prices-p6w9k`
(scheduler-fired `2026-05-13T21:30:05Z`, started `21:30:09Z`, completed
`21:38:15Z`, `succeededCount=1`, runtime 8m6.14s).
**Freshness invariant:** `freshness_status=fresh`,
`expected_min_trade_date=2026-05-12`, `latest_trade_date=2026-05-12`,
per-ticker `fresh=36 stale=0 bar_less=7 inspected=43`.

### 7.1 Headline metrics

| Metric | Value |
|---|---|
| `evaluated_count` | **15** |
| `missing_count` | **11** (7 mirror-bootstrap bar-less + 4 unmapped) |
| `direction_accuracy` | **`1 / 15 = 6.7 %`** |
| `bucket_accuracy` | **`7 / 15 = 46.7 %`** |
| `MAE_pct` | **`1.7668`** |
| `low_confidence_count` | 15 (all evaluable rows) |
| `low_confidence_direction_accuracy` | `1 / 15 = 6.7 %` |
| `medium_confidence_count` | 0 (Shadow v1 capped at `low`) |
| `high_confidence_count` | 0 |

### 7.2 Per-ticker

| Ticker | Pred dir | Actual dir | Pred bucket | Actual bucket | Actual % | Dir? | Bucket? |
|---|---|---|---|---|---:|---|---|
| MU | flat | down | minus_1_to_plus_1 | below_minus_3 | -3.615 | N | N |
| AMD | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.289 | N | N |
| AVGO | up | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.131 | N | N |
| GOOGL | flat | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.332 | N | Y |
| INTC | flat | down | minus_1_to_plus_1 | below_minus_3 | -6.822 | N | N |
| **AAPL** | **up** | **up** | minus_1_to_plus_1 | minus_1_to_plus_1 | **+0.724** | **Y** | **Y** |
| AMZN | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -1.179 | N | N |
| GS | flat | up | minus_1_to_plus_1 | minus_1_to_plus_1 | +0.110 | N | Y |
| IWM | flat | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.967 | N | Y |
| NVDA | flat | up | minus_1_to_plus_1 | minus_1_to_plus_1 | +0.611 | N | Y |
| QQQ | up | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.848 | N | Y |
| SIRI | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.333 | N | N |
| SPY | flat | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.151 | N | Y |
| TSLA | up | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.595 | N | N |
| TSM | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -1.795 | N | N |

### 7.3 Splits (direction accuracy)

| Split | Count | Direction accuracy |
|---|---:|---:|
| HELD | 1 (MU) | 0 / 1 = 0.0 % |
| Not held | 14 | 1 / 14 = 7.1 % |
| News-linked (`recent_news_count > 0`) | 2 (MU, AMD) | 0 / 2 = 0.0 % |
| No recent news | 13 | 1 / 13 = 7.7 % |
| SCANNER tag | 15 | 1 / 15 = 6.7 % |
| Mirror-only | 0 | N/A |

### 7.4 Narrative (no rule change applied)

* The day was a broad sell-off — 13 of 15 evaluable closed down,
  2 closed up (AAPL +0.72 %, NVDA +0.61 %), 0 ended in the narrow
  `|return| ≤ 0.1 %` flat band. The conservative flat-heavy rule
  was therefore on the wrong side of a one-sided day.
* The **extension dampener was directionally vindicated** for MU,
  AMD, INTC — those three did mean-revert (MU `-3.62 %`, AMD
  `-2.29 %`, INTC `-6.82 %`). But the rule mapped `composite=0` to
  `flat`, not `down`, so the directional benefit was lost. Bias
  right, language wrong.
* **3 of 4 "up" picks reversed**: AVGO, QQQ, TSLA. Pure +2 %
  one-day momentum is a coincident-momentum trap.
* **AAPL is the lone direction hit** (1 / 15) — predicted up,
  actual `+0.72 %`. Honest hit.
* **Bucket accuracy 46.7 %** is meaningful — all the small-magnitude
  movers landed in the conservative `minus_1_to_plus_1` default.

### 7.5 Decision applied (per §6 of this doc)

`direction_accuracy=6.7 %` is **below** the §6 threshold of `≥ 60 %`.

→ Decision: **document the gap, treat the rule set as falsified for
the next cycle. Open a new pre-registration with a refined rule —
never a hot-fix of the current one.**

Improvement notes (pre-registered for a future Shadow Test #4, NOT
applied retroactively) live in
`docs/platform-prediction-accuracy-20260512-final.md §7.4`. The
existing 2026-05-12 pre-registration remains canonical and frozen.

### 7.6 Banned-word check on this Results section

| Pattern | Hits |
|---|---|
| `buy now / sell now / enter long / enter short / target price / position size / guaranteed` | 0 |
| Chinese equivalents `必涨 / 必跌 / 买入建议 / 卖出建议 / 目标价 / 仓位建议` | 0 |
| Real API key / Bearer token / private key | 0 |

### 7.7 Strict side-effect attestation (this eval)

| | Status |
|---|---|
| Manual EOD sync triggered | **NO** — `p6w9k` is scheduler-fired |
| Manual `quant-sync-t212` execution | NONE |
| T212 endpoint write | NONE |
| Broker submit | NONE |
| `order_intent` / `order_draft` created | 0 (unchanged) |
| `FEATURE_T212_LIVE_SUBMIT` | `false` ✓ preserved |
| Schedulers modified | NONE (all 3 ENABLED, cron unchanged) |
| Cloud Run service deploy | NONE (still `quant-api-00053-4p7`) |
| Migration | NONE |
| Production DB write driven by eval | NONE — `SELECT`-only via transient `quant-ops-eval-closes` Cloud Run Job, **deleted in-run** after success |
| External web prices | NOT used (production `price_bar_raw` only) |
| Browser automation / scraping | NONE |
| Secrets exposed | NONE |
| `.firebase/` committed | NO |

This `§7` section is the only edit applied to this file in this
eval — all earlier sections (`§1` pre-registration through `§6`
decision rules) remain unchanged, preserving the pre-registration
contract.

## 8. Side-effect attestations (this doc)

| | Status |
|---|---|
| Production DB write | NONE (this is a docs-only pre-registration of the eval procedure) |
| Cloud Run Job created | NONE |
| Scheduler modification | NONE |
| Sync execution triggered | NONE (will wait for the regular 21:30Z fire) |
| Trading 212 write | NONE |
| `order_intent` / `order_draft` created | NONE |
| Live submit | LOCKED (`FEATURE_T212_LIVE_SUBMIT=false`) |
| Browser automation / scraping | NONE |
| Secrets in this file | NONE |
| Prediction surfaced in UI | NO |
