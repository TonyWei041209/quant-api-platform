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

## 7. Results (TO BE FILLED)

_Empty until the timing gates in §1 fire. Once filled, the entire
section is append-only — no edits to earlier subsections._

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
