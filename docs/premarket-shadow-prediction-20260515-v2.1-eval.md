# Premarket Shadow Prediction — 2026-05-15 (Rule v2.1) — Evaluation Procedure

**Status:** PLACEHOLDER. Results to be appended in `§7 Results` once
all timing gates fire. Sections `§1–§6` are append-only canonical
procedure — do NOT rewrite after first commit.

| Field | Value |
|---|---|
| Prediction source | [`docs/premarket-shadow-prediction-20260515-v2.1.json`](premarket-shadow-prediction-20260515-v2.1.json) |
| Narrative | [`docs/premarket-shadow-prediction-20260515-v2.1.md`](premarket-shadow-prediction-20260515-v2.1.md) |
| Rule pre-registration | [`docs/premarket-shadow-test-4-rule-v2-pre-registration.md`](premarket-shadow-test-4-rule-v2-pre-registration.md) |
| Rule amendment | [`docs/premarket-shadow-test-4-rule-v2.1-amendment.md`](premarket-shadow-test-4-rule-v2.1-amendment.md) |
| Target trade-date | `2026-05-15` (Friday) |
| Anchor trade-date | `2026-05-13` (Wednesday) |
| Horizon label | `latest_db_close_to_target_close` (a **2-trading-day** return, NOT next-day) |
| Decision thresholds (v2.1 §2.3) | `direction_acc ≥ 45 %` AND `confidence=high acc ≥ 60 %` (when `N ≥ 3`) AND `bucket_acc ≥ 45 %` for not-falsified |

---

## 1. Timing gates

Eval can run only when all three are true:

1. US `2026-05-15` regular session closed (≥ `2026-05-15T20:00Z`).
2. Production `price_bar_raw` has rows for `trade_date='2026-05-15'`.
   Under the platform's T-1 provider lag, this normally arrives at
   the next-Monday `2026-05-18T21:30Z` `quant-sync-eod-prices` fire.
3. Production `price_bar_raw` already has the anchor `2026-05-13` —
   confirmed at pre-open time and **must not regress**.

The earliest the eval can run is **Tuesday `2026-05-19T00:00Z` UTC**,
once Monday's `21:30Z` fire completes. If any gate fails, the eval
status is `pending`.

## 2. Data pull (read-only)

For each ticker in `predictions[]`:

```sql
SELECT pbr.trade_date, pbr.close
FROM price_bar_raw pbr
JOIN instrument_identifier ii ON ii.instrument_id = pbr.instrument_id
WHERE ii.id_type = 'ticker' AND ii.id_value = :ticker
  AND pbr.trade_date IN ('2026-05-13', '2026-05-15')
ORDER BY pbr.trade_date;
```

For `watch_only[]` rows: no fetch (excluded from denominator).

If any eligible ticker is missing the `2026-05-13` or `2026-05-15`
close at eval time, mark `missing_at_eval` and exclude it from the
denominator. **Never substitute external web prices.**

## 3. Classification

```
actual_return = (close_2026_05_15 - close_2026_05_13) / close_2026_05_13
```

`actual_direction_band(actual_return_pct)` per
`libs/prediction/rule_v2.py:actual_direction_band` (5-band: `up`,
`flat-up`, `flat-flat`, `flat-down`, `down`).

`actual_bucket` (5-band): same scheme as the prediction JSON
(`above_plus_3 / plus_1_to_plus_3 / minus_1_to_plus_1 /
minus_3_to_minus_1 / below_minus_3`).

## 4. Metrics

| Metric | Definition |
|---|---|
| `evaluated_count` | tickers in `predictions[]` with both anchor + target closes in DB |
| `direction_accuracy` | per `libs/prediction/rule_v2.py:direction_correct` collapse table (4-pred × 5-actual) |
| `bucket_accuracy` | exact bucket match |
| `MAE_pct` | mean of `|actual_return_pct - bucket_midpoint_pct|` (midpoints `±4 / ±2 / 0`) |
| `low_confidence_direction_accuracy` | direction-acc within `confidence=low` subset |
| `medium_confidence_direction_accuracy` | within `medium` subset (N=0 expected this cycle) |
| `high_confidence_direction_accuracy` | within `high` subset (N=0 expected this cycle) |
| `held_vs_nonheld_split` | by `HELD ∈ source_tags` |
| `news_linked_vs_non_news_split` | by `recent_news_count > 0` (from prediction JSON's per-row decision metadata) |
| `scanner_vs_mirror_only_split` | by `SCANNER ∈ source_tags` |
| `mapped_with_close_vs_missing_split` | by anchor presence at eval time |

## 5. Decision rule (per v2.1 amendment §2.3)

| Outcome | Decision |
|---|---|
| `direction_acc ≥ 45 %` AND `bucket_acc ≥ 45 %` AND `confidence=high acc ≥ 60 %` (when `N ≥ 3`) | v2.1 not falsified this cycle |
| `direction_acc ≥ 30 %` only | single noisy data point; run more cycles |
| Below the above | v2.1 falsified; open Shadow Test #5 with separate pre-registration |
| Any banned trade-action word in prediction text | run invalid; rerun with corrected language |
| Any side-effect attestation in §6 fails | run invalid; investigate |

## 6. Side-effect attestations (this eval procedure)

* Production DB write: NONE (`SELECT`-only).
* Cloud Run Job: transient one-shot, deleted in-run after success.
* No external web prices.
* No browser automation / scraping.
* No T212 endpoint write / broker submit.
* No `order_intent` / `order_draft` created.
* `FEATURE_T212_LIVE_SUBMIT` remains `false`.
* No scheduler change.
* `.firebase/` cache not committed.
* v1 + v2 + v2.1 artifacts not retroactively modified — only this
  doc's `§7 Results` section is appended.

## 7. Results

_Empty until the §1 timing gates fire. Once filled, the entire
section is append-only — no edits to `§1–§6` after that._
