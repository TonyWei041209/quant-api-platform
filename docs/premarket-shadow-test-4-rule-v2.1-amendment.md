# Premarket Shadow Test #4 — Rule v2.1 Amendment

**Type:** forward-looking amendment to the v2 pre-registration.
**Pre-registered at (UTC):** `2026-05-15T00:05:00Z`
**Applies to:** captures from this commit forward. **Does NOT touch
v2 pre-registration §3, the v1 artifacts, or any historical eval.**

The v2 pre-registration
(`docs/premarket-shadow-test-4-rule-v2-pre-registration.md`) is left
**unchanged**. This amendment adds a sibling ruleset (`v2.1`) that
can be tested in parallel. Predictions produced under v2.1 are
explicitly labelled `v2.1` in their artifact filenames and JSON
`schema_version` field — they are NOT mixed with hypothetical v2
predictions in any aggregate metric.

> **Research-only.** v2.1 inherits all of v2's strict no-trade-advice
> guarantees. No buy/sell/target/position-sizing language. No
> broker / order / live-submit operation. No `order_intent` or
> `order_draft` created. `FEATURE_T212_LIVE_SUBMIT` remains `false`.

---

## 1. Why v2 was blocked

Capture attempt on `2026-05-14T23:47Z` (documented in
`docs/shadow-test-4-v2-capture-attempt-20260514-blocked.md`) stopped at
v2 §3 because the upstream provider feed is consistently T-1 lagged:

* Tonight's `quant-sync-eod-prices-schedule` fire at `2026-05-14T21:30Z`
  succeeded (execution `hbwnh`, exit 0, `succeededCount=1`).
* `freshness_status=fresh` per the EOD invariant — because
  `latest_trade_date = 2026-05-13 = expected_min_trade_date` (the
  previous weekday).
* BUT `count(*) = 0` rows for `trade_date='2026-05-14'` (Thursday's
  close) in `price_bar_raw`.
* v2 §3 strictly requires `T-1` for target `T` to be in DB. With
  `T = 2026-05-15` (Friday), `T-1 = 2026-05-14` is missing.

The next sync fire at `2026-05-15T21:30Z` would land Thursday's
close — but **after** Friday's open at `13:30Z`. So **no pre-open
window can ever satisfy "T-1 in DB" under the current provider
feed timing**. v2 §3, as written, is structurally unachievable.

## 2. v2.1 change set

Exactly three things change relative to v2. Everything else
(regime, momentum, extension, news, direction mapping, bucket
mapping, confidence calibration, side-effect attestations) is
inherited from v2 verbatim and is NOT restated here.

### 2.1 Anchor definition (replaces v2 §3 eligibility for v2.1 only)

**v2 (frozen, unchanged):**
> ticker is eligible if `price_bar_raw` contains a row for
> `trade_date = T-1`.

**v2.1 (new, additive):**
> Ticker is eligible if it has a recent close in `price_bar_raw` whose
> `trade_date` is **at most `MAX_ANCHOR_LAG_TRADING_DAYS`** earlier
> than target `T`. The chosen anchor is the **most recent** such
> close. The per-ticker `anchor_trade_date` MUST be recorded in the
> prediction row so the eval at close-of-`T` knows exactly which
> historical close to compare against.

`MAX_ANCHOR_LAG_TRADING_DAYS = 3`. A ticker whose most recent DB
close is more than 3 weekdays earlier than `T` goes to
`watch_only[]` with reason `anchor_too_stale`.

Other reasons for `watch_only[]` carry over from v2:
* `mapping_status != "mapped"` → `unmapped`
* no `price_bar_raw` row at all → `no_close_in_db`

### 2.2 Horizon label (NEW field in v2.1)

v2 uses `prediction_horizon = "next_close_vs_previous_close"`. That
phrasing was honest under the v2 §3 contract (T-1 → T), but it is
**not** honest under v2.1 where the anchor may be T-2 or T-3.

v2.1 introduces a distinct, explicit horizon label:

```
prediction_horizon = "latest_db_close_to_target_close"
```

The eval at close-of-`T` MUST use this label to decide which
historical close to compare against. The eval MUST NOT claim
"next-day return" unless `anchor_trade_date == T-1`.

When `anchor_trade_date < T-1`, the prediction spans **more than one
trading day** (e.g. anchor = Wed close, target = Fri close = 2-day
return). Direction accuracy expectations should be calibrated
accordingly — see §3 below.

### 2.3 Decision rule (parallel to v2 §11, with relaxed threshold)

v2 §11 sets `direction_accuracy ≥ 50 %` as the "not falsified this
cycle" threshold. v2.1 inherits that threshold but acknowledges that
multi-day prediction is harder than single-day:

| Outcome | v2.1 decision |
|---|---|
| `direction_accuracy ≥ 45 %` AND `confidence=high` accuracy `≥ 60 %` (when `N ≥ 3`) AND `bucket_accuracy ≥ 45 %` | Rule v2.1 not falsified this cycle. |
| `direction_accuracy ≥ 30 %` only | Single data point. Run more cycles before deciding. |
| Below the above | v2.1 falsified. Open a separate Shadow Test #5 (do NOT in-place edit v2.1). |

The thresholds are slightly relaxed vs v2 to reflect the harder
prediction surface (2-day vs 1-day return). v2 and v2.1 cycles are
evaluated **independently**; aggregate metrics across versions are
prohibited.

## 3. Anchor application for this capture cycle

| | Value |
|---|---|
| `target_trade_date` | `2026-05-15` (Friday) |
| Latest `price_bar_raw` close at capture time | `2026-05-13` (Wednesday) |
| `anchor_trade_date` (under v2.1 §2.1) | `2026-05-13` |
| Anchor lag (trading days from T) | 2 (Friday minus Thursday minus Wednesday) |
| Anchor lag ≤ `MAX_ANCHOR_LAG_TRADING_DAYS = 3` | ✓ PASS |
| `prediction_horizon` label | `latest_db_close_to_target_close` |
| Trading-day span | 2 |

## 4. What v2.1 inherits verbatim from v2

(Not re-stated to avoid drift. Read v2 for the full text.)

* §1 Hypothesis (with the v2.1 thresholds substituted in §11)
* §2 Data sources
* §4 Prediction generation time gate
* §5 Market regime feature (SPY+QQQ 1D/5D from latest DB close)
* §6 Per-ticker factor definitions (momentum / extension / news /
  regime composite)
* §7 Direction mapping (4-state)
* §8 Bucket mapping
* §9 Confidence calibration
* §10 Evaluation metrics
* §12 Missing-data policy
* §13 Strict side-effect attestations
* §14 No-trading-advice disclaimer (verbatim, MUST be preserved in
  every v2.1 artifact)

## 5. Concrete implementation surface

* `libs/prediction/rule_v2.py` gains two NEW public functions:
  * `is_eligible_latest_anchor(inp, anchor_trade_date, target_trade_date)`
    — pure boolean + reason. Computes `lag_trading_days =
    weekdays_between(anchor_trade_date, target_trade_date)` and
    returns False with reason `anchor_too_stale` when `lag >
    MAX_ANCHOR_LAG_TRADING_DAYS`.
  * `compute_per_ticker_v21(inp, *, regime, anchor_trade_date,
    target_trade_date)` — wraps `compute_per_ticker` but:
    * uses `is_eligible_latest_anchor(...)` instead of
      `is_eligible(...)`
    * sets `prediction_horizon = "latest_db_close_to_target_close"`
      on the returned dict
    * carries `anchor_trade_date` + `target_trade_date` +
      `anchor_lag_trading_days` on the row
* `MAX_ANCHOR_LAG_TRADING_DAYS = 3` is a module constant exposed
  for inspection.
* **No v2 function is removed or renamed.** v2 tests continue to
  pass.

## 6. Strict side-effect attestations (this amendment)

| Property | Status |
|---|---|
| v2 pre-registration | **NOT MODIFIED** |
| v1 artifacts | **NOT MODIFIED** |
| `libs/prediction/rule_v2.py` existing functions | **NOT REMOVED / NOT RENAMED** — additive only |
| v2 tests | **NOT MODIFIED** — new v2.1 tests added in same file |
| Production DB write | NONE |
| Cloud Run service deploy | NONE |
| Migration | NONE |
| Manual EOD sync triggered | NONE |
| Manual `quant-sync-t212` execution | NONE |
| Scheduler change | NONE |
| T212 endpoint / broker submit | NONE |
| `order_intent` / `order_draft` created | 0 |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (preserved) |
| External web prices | NEVER |
| Browser automation / scraping | NONE |
| `.firebase/` cache committed | NO |

## 7. References

* v2 pre-registration (frozen): `docs/premarket-shadow-test-4-rule-v2-pre-registration.md`
* v2 capture blocked report: `docs/shadow-test-4-v2-capture-attempt-20260514-blocked.md`
* v1 artifacts (all frozen): `docs/premarket-shadow-prediction-20260512.{json,md}`, `docs/premarket-shadow-prediction-20260512-eval.md`, `docs/platform-prediction-accuracy-20260512-final.md`
* Pure helper: `libs/prediction/rule_v2.py`
* EOD freshness invariant: `libs/ingestion/eod_freshness.py`
* Runbook (procedure for evaluating any premarket prediction): `docs/runbook.md §15`
