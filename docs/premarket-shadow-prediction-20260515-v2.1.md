# Premarket Shadow Prediction — 2026-05-15 (Rule v2.1)

**Status:** Pre-registered. Forward-looking only. NOT a trading
recommendation.

| Field | Value |
|---|---|
| `schema_version` | **`v2.1`** |
| `test_id` | `premarket-shadow-prediction-20260515-v2.1` |
| Rule pre-registration | [`docs/premarket-shadow-test-4-rule-v2-pre-registration.md`](premarket-shadow-test-4-rule-v2-pre-registration.md) (frozen — UNCHANGED) |
| Rule amendment | [`docs/premarket-shadow-test-4-rule-v2.1-amendment.md`](premarket-shadow-test-4-rule-v2.1-amendment.md) |
| Pre-registered at (UTC) | `2026-05-15T00:09:18Z` |
| Target trade-date | `2026-05-15` (Friday) |
| Anchor trade-date (intended) | `2026-05-13` (Wednesday, the latest DB close) |
| Anchor-lag for typical eligible row | 2 trading days |
| `prediction_horizon` | **`latest_db_close_to_target_close`** (NOT `next_close_vs_previous_close`) |
| US regular open of target | `2026-05-15T13:30Z` |

> **Research-only.** Predictions in this artifact live exclusively in
> `docs/*.json` and `docs/*.md`. They are never surfaced as a
> user-facing trading signal. No buy/sell/target-price/position-sizing
> language. No `order_intent` / `order_draft` created at any point.
> `FEATURE_T212_LIVE_SUBMIT` remains `false`.

---

## 1. Why this is v2.1 (not v2)

The original v2 pre-registration §3 required `T-1` close to be in
`price_bar_raw` before pre-open. Under the upstream provider's T-1
delivery cadence, `T-1` for any next-trading-day target is **never**
present in the platform DB before US open. The v2 capture attempt on
2026-05-14 stopped at that gate (documented in
`docs/shadow-test-4-v2-capture-attempt-20260514-blocked.md`).

The v2.1 amendment adds a sibling eligibility rule:

> Ticker is eligible if its most recent close in `price_bar_raw` is at
> most **3 trading days** before target `T`. Per-row
> `anchor_trade_date` MUST be recorded so the eval at close knows
> exactly which historical close to compare against.

**v2 is not modified.** v2.1 is the rule under which this artifact is
produced.

## 2. Anchor + horizon honesty

| | Value |
|---|---|
| `target_trade_date` | `2026-05-15` (Friday) |
| Most recent `price_bar_raw` close at capture time | `2026-05-13` (Wednesday) |
| `anchor_trade_date` on every eligible row | `2026-05-13` |
| `anchor_lag_trading_days` | **2** (Thu, Fri) |
| Honest description of horizon | "Wednesday close → Friday close" — a **2-trading-day return** |
| Misleading description (NEVER USED) | ~~"T-1 to T" or "next-day return"~~ |

The v2.1 `prediction_horizon` field is literally
`latest_db_close_to_target_close` for exactly this reason.

## 3. Market regime (computed from production DB)

Read-only from `price_bar_raw` SPY+QQQ closes:

| Indicator | Value | Threshold |
|---|---|---|
| SPY 1D (5/13 vs 5/12) | `+0.559 %` | < `+1.0 %` needed for `positive` |
| SPY 5D (5/13 vs 5/4) | `+1.156 %` | < `-2.0 %` for `negative_5d` |
| QQQ 1D (5/13 vs 5/12) | `+1.056 %` | ≥ `+1.0 %` (but SPY fails) |
| QQQ 5D (5/13 vs 5/4) | `+2.722 %` | < `-2.0 %` for `negative_5d` |

→ **`regime = "neutral"`** (the positive branch requires BOTH SPY 1D
and QQQ 1D ≥ `+1.0 %`; SPY is at `+0.56 %`).

Regime contribution to composite: `regime_signal = 0`.

## 4. Distribution

| | Count |
|---|---|
| **Eligible predictions** | **16** |
| **Watch-only excluded** | **11** |
| Total brief candidates considered | 27 |
| Direction `up` | 0 |
| Direction `flat-up` | 10 |
| Direction `flat-down` | 6 |
| Direction `down` | 0 |
| Bucket `minus_1_to_plus_1` | 16 |
| Bucket (any other) | 0 |
| Confidence `low` | 16 |
| Confidence `medium` / `high` | 0 |

## 5. Per-ticker predictions (16 eligible)

| Ticker | Direction | Bucket | Confidence | composite | anchor | lag |
|---|---|---|---|---:|---|---:|
| `MU` | flat-down | minus_1_to_plus_1 | low | `-1` | 2026-05-13 | 2 |
| `AMD` | flat-down | minus_1_to_plus_1 | low | `-1` | 2026-05-13 | 2 |
| `GOOGL` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `INTC` | flat-down | minus_1_to_plus_1 | low | `-1` | 2026-05-13 | 2 |
| `NVDA` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `AAPL` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `AMC` | flat-down | minus_1_to_plus_1 | low | `-1` | 2026-05-13 | 2 |
| `AMZN` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `AVGO` | flat-down | minus_1_to_plus_1 | low | `-1` | 2026-05-13 | 2 |
| `GS` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `IWM` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `LCID` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `QQQ` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `SPY` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |
| `TSLA` | flat-down | minus_1_to_plus_1 | low | `-1` | 2026-05-13 | 2 |
| `TSM` | flat-up | minus_1_to_plus_1 | low | `0` | 2026-05-13 | 2 |

## 6. Watch-only (11 excluded; not in accuracy denominator)

| Ticker | Reason |
|---|---|
| `LITE` | `unmapped` (no `instrument_identifier`) |
| `IPOE` | `unmapped` |
| `OAC` | `unmapped` |
| `SNDK1` | `unmapped` |
| `NOK` | `no_close_in_db` (mirror-bootstrap scaffolding-only) |
| `AAOI` | `no_close_in_db` |
| `CRCL` | `no_close_in_db` |
| `CRWV` | `no_close_in_db` |
| `ORCL` | `no_close_in_db` |
| `TEM` | `no_close_in_db` |
| `VACQ` | `no_close_in_db` |

## 7. Honest framing of the prediction signal

* The 16 eligible predictions all have `confidence=low` because no
  ticker's `|composite|` reached the `±2` medium-tier threshold.
* The brief snapshot read by this capture
  (`63907e12-09ed-4f86-adf2-4249766280a1`, generated
  `2026-05-14T06:30Z`) has `price_move` data computed from `2026-05-12`
  close vs `2026-05-11` — a now-old snapshot relative to the
  `2026-05-13` anchor used here.
* This is honest under v2.1 — the prediction is "where will Friday
  close vs Wednesday close land". With neutral regime and stale
  momentum signals, the rule's conservative `flat-up` / `flat-down`
  default is the correct expression of low confidence.

## 8. Eval procedure

After:
1. Friday `2026-05-15T20:00Z` US session closes
2. Friday `2026-05-15T21:30Z` `quant-sync-eod-prices` fire delivers
   Thursday `2026-05-14` bars (under T-1 lag pattern)
3. Monday `2026-05-18T21:30Z` fire delivers Friday `2026-05-15` bars

Eval can run on Tuesday `2026-05-19` morning. The eval procedure is
recorded in
`docs/premarket-shadow-prediction-20260515-v2.1-eval.md §1–§6`. Per
the v2.1 amendment §2.3 the decision thresholds are: `direction_acc
≥ 45 %` AND `confidence=high acc ≥ 60 %` AND `bucket_acc ≥ 45 %` for
not-falsified.

## 9. Side-effect attestations (this capture)

| Property | Status |
|---|---|
| v1 artifacts (2026-05-12 `.json/.md/-eval.md/-final.md`) | UNCHANGED |
| v2 pre-registration `docs/premarket-shadow-test-4-rule-v2-pre-registration.md` | **UNCHANGED** |
| `libs/prediction/rule_v2.py` v2 surface | UNCHANGED (additive v2.1 helpers only) |
| v2 tests | UNCHANGED (v2.1 tests appended) |
| Production DB write | NONE (read-only `SELECT` via one-shot Cloud Run Job, deleted in-run) |
| Cloud Run service deploy | NONE — still `quant-api-00053-4p7` |
| Migration | NONE |
| Manual EOD sync triggered | NONE |
| Manual `quant-sync-t212` execution | NONE |
| Scheduler change | NONE (all 3 ENABLED, cron unchanged) |
| T212 endpoint / broker submit | NONE |
| `order_intent` / `order_draft` created | 0 (unchanged) |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (preserved) |
| External web prices | NEVER |
| Browser automation / scraping | NONE |
| Secrets in committed text | NONE |
| `.firebase/` cache committed | NO |
