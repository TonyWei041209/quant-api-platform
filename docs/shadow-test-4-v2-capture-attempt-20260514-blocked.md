# Shadow Test #4 — Rule v2 capture attempt 2026-05-14 — **BLOCKED**

**Status:** Capture **NOT** performed. Stopped at the v2
pre-registration `§3 Eligibility` gate. No prediction artifact
written. No amendment to the pre-registration applied. No retroactive
modification of any v1 artifact. Final decision deferred to the
operator (see §5).

**Audit window (UTC):** `2026-05-14T23:47Z`–`2026-05-15T00:00Z`
**Target trade-date the run was attempting:** `2026-05-15` (Friday)
**Anchor required by v2 §3:** `T-1 = 2026-05-14` (Thursday close)
**Latest close actually in `price_bar_raw`:** `2026-05-13` (Wednesday)

---

## 1. Gate-by-gate result

| Gate | Source | Status |
|---|---|---|
| `now < target_open` (`2026-05-15T13:30Z`) | system clock `2026-05-14T23:47Z`, ~13.7h pre-open | ✓ PASS |
| `git status` clean and HEAD includes v2 pre-reg | HEAD = `4f7f8e3` `feat: preregister shadow test 4 rule v2 + pure-function helper` | ✓ PASS |
| CI green | latest 3 runs all `success` | ✓ PASS |
| `/api/health` | `{"status":"ok","service":"quant-api-platform","version":"0.1.0"}` | ✓ PASS |
| Schedulers unchanged | 3 ENABLED, cron unchanged | ✓ PASS |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (verified) | ✓ PASS |
| v1 artifacts unchanged | all 4 diff-clean | ✓ PASS |
| EOD sync fired tonight | `quant-sync-eod-prices-hbwnh`, scheduler-fired `2026-05-14T21:30:05Z`, completed `21:38:20Z`, `succeededCount=1` | ✓ PASS |
| `freshness_status` from tonight's sync | **`fresh`** — `expected_min_trade_date=2026-05-13`, `latest_trade_date=2026-05-13`, per-ticker `fresh=36 stale=0 bar_less=7 inspected=43` | ✓ PASS (by invariant's own contract) |
| **v2 §3: `T-1` anchor close (`2026-05-14`) in `price_bar_raw`** | `count(*) = 0` rows for `trade_date='2026-05-14'` | **✗ FAIL** |
| **User's strict precondition #2: anchor `T-1` close present** | same as above | **✗ FAIL** |

Two gates fail simultaneously and they say the same thing: tonight's
EOD sync delivered Wednesday's close (`2026-05-13`), not Thursday's
(`2026-05-14`). The freshness invariant correctly reports `fresh`
because it compares against `expected_min_trade_date = previous_weekday(today)`,
which is also `2026-05-13`. The v2 eligibility rule, by contrast,
requires the **anchor relative to the FUTURE target trade-date**, which
is one full trading day ahead of what the invariant tracks.

## 2. Why both gates fail despite a successful EOD sync

Same as the original root cause documented in
`docs/eod-freshness-lag-diagnosis-20260512.md`: the upstream
Polygon/Massive feed publishes day-`T` EOD bars on a T+0 21:00Z – T+1
04:00Z schedule that does NOT consistently align with our scheduled
`T 21:30Z` sync fire. The sync at `T 21:30Z` reliably lands `T-1`
bars (yesterday). It does NOT land `T` bars.

Read-only DB probe results (via transient Cloud Run Job
`quant-ops-v2-phase1`, executed and deleted in-run):

```
OVERALL_MAX_TRADE_DATE=2026-05-13   TOTAL_ROWS=13512
ROWS_2026_05_14 = 0    (target anchor T-1 — required by v2 §3)
ROWS_2026_05_13 = 36   (most recent DB close = T-2 relative to Friday)
TICKERS_WITH_T_2_CLOSE = 36 (all scanner-research-36)
TICKERS_WITH_T_1_CLOSE = 0
```

Read-only provider probe is not repeated here — the structural pattern
is the same one already validated in
`docs/eod-freshness-lag-diagnosis-20260512.md §2.3`.

## 3. Why this is structural, not transient

* Tonight's `quant-sync-eod-prices-schedule` fire at `2026-05-14T21:30Z`
  succeeded. Runtime 8m6s. Exit 0. Provider HTTP returned `200` for
  all 36 tickers.
* The next EOD sync fire is `2026-05-15T21:30Z` — that lands Thursday
  `2026-05-14` bars, but ARRIVES AFTER Friday's open at `13:30Z`. So
  Thursday's close is not available before Friday's pre-open under
  the current feed timing.
* Monday `2026-05-18T21:30Z` is the next fire that would land
  Friday's close (`2026-05-15`).

This means **no pre-open window for any next trading day can satisfy
the v2 §3 "T-1 in DB" rule under the current provider feed**. The
rule, as written, is structurally unachievable.

## 4. What the v2 prediction WOULD look like if the gate were forced

The agent computed (read-only, in-memory only — **not persisted**):

* **Market regime input** (from §1 read-only DB probe):
  * `SPY 1D (5/13 vs 5/12) = +0.560%`
  * `SPY 5D (5/13 vs 5/8)  = +0.636%`
  * `QQQ 1D (5/13 vs 5/12) = +1.056%`
  * `QQQ 5D (5/13 vs 5/8)  = +0.489%`
  * Per `compute_market_regime`: `regime = "neutral"` (QQQ 1D ≥ +1.0 % but SPY 1D < +1.0 %; rule requires BOTH).
* All 36 scanner-research tickers have `change_1d_pct` available from
  the latest brief snapshot (`63907e12-09ed-4f86-adf2-4249766280a1`,
  2026-05-14 06:30Z), but those values are **anchored to 2026-05-12
  close vs 2026-05-11** (i.e. brief generated before tonight's sync
  landed 2026-05-13). Predictions built on those values would be
  even further removed from a Friday-target anchor.

**These values are documented for transparency only. They are NOT
written to any `docs/premarket-shadow-prediction-*-v2.json` file.**
No prediction artifact is being produced under the un-amended v2
pre-registration.

## 5. Decision options for the operator

The agent stops here. The choice between the three options below is a
research-design decision that must be made by the operator, not by
the agent on its own initiative:

### Option A — Hold v2 capture indefinitely (recommended if you want strict adherence)

Do nothing tonight. The v2 pre-registration as written cannot be
exercised until the upstream provider feed publishes day-`T` bars on
the same trading day. Until then, **all v2 capture attempts will
block at §3.** No prediction artifact will ever be written under the
current contract.

Trade-offs:
* ✓ Honours the pre-registration verbatim.
* ✗ Calibration never runs. The v2 ruleset is never tested.

### Option B — Amend v2 §3 in a forward-looking supplement (recommended if you want to start calibrating)

Write a small forward-looking amendment doc (e.g.
`docs/premarket-shadow-test-4-rule-v2.1-amendment.md`) that:

1. Documents the structural mismatch between v2 §3 and the T-1
   provider feed.
2. Replaces "T-1 in DB" with "most recent close in DB", and adds an
   explicit `anchor_trade_date` field to each prediction row so the
   eval at close knows which date to compare against.
3. Notes that under T-1 provider lag, the typical anchor will be
   `T-2` of the target, making each prediction a 2-trading-day
   return rather than 1.
4. Is forward-looking only — does **not** retroactively change v1 or
   the original v2 pre-registration.

After the amendment lands, generate `docs/premarket-shadow-prediction-20260514-v2.json`
with `anchor_trade_date=2026-05-13`, `target_trade_date=2026-05-15`.

Trade-offs:
* ✓ Calibration starts now.
* ✗ The prediction is a 2-day return, not the 1-day return the
  pre-registration originally described. Direction accuracy
  expectations should be relaxed accordingly.
* ✗ Requires the operator to acknowledge that the §3 contract is
  being widened.

### Option C — Open Shadow Test #5 from scratch

Treat v2 as "designed but not testable under current feed" and write
a completely separate Shadow Test #5 pre-registration that bakes the
T-1 provider lag into its eligibility rule from the start.

Trade-offs:
* ✓ Clean separation — v2 stays frozen as a design artifact, v3 has
  its own contract.
* ✗ More overhead than Option B.

## 6. Strict side-effect attestations (this attempt)

| Property | Status |
|---|---|
| v2 pre-registration `docs/premarket-shadow-test-4-rule-v2-pre-registration.md` | **NOT MODIFIED** |
| `libs/prediction/rule_v2.py` / `tests/unit/test_prediction_rule_v2.py` | **NOT MODIFIED** |
| Any v1 artifact (2026-05-12 prediction / md / eval / final accuracy) | **NOT MODIFIED** |
| `docs/premarket-shadow-prediction-20260514-v2.json` | **NOT CREATED** (would have violated §3) |
| `docs/premarket-shadow-prediction-20260514-v2.md` | **NOT CREATED** |
| `docs/premarket-shadow-prediction-20260514-v2-eval.md` | **NOT CREATED** |
| Production DB write | NONE (read-only `SELECT` only via one-shot `quant-ops-v2-phase1` Job, **deleted in-run**) |
| Cloud Run service deploy | NONE — still `quant-api-00053-4p7` |
| Migration | NONE |
| Manual EOD sync triggered | NONE |
| Manual `quant-sync-t212` execution | NONE |
| Manual brief job execution | NONE |
| Scheduler create / update / pause / resume | NONE |
| T212 endpoint / broker submit | NONE |
| `order_intent` / `order_draft` created | 0 (unchanged) |
| `FEATURE_T212_LIVE_SUBMIT` | `false` ✓ preserved |
| External web prices | NEVER |
| Browser automation / scraping | NONE |
| Secrets exposed in committed text | NONE |
| `.firebase/` cache committed | NO |

## 7. Recommendation for the next agent turn / operator action

If the operator chooses **Option B**, the next agent turn should:

1. Create `docs/premarket-shadow-test-4-rule-v2.1-amendment.md` with
   the four bullets in §5 Option B above.
2. Update `libs/prediction/rule_v2.py:is_eligible` to take a generic
   `has_recent_close_in_db` argument (rename or keep the parameter
   name; document that it covers either T-1 or T-2 depending on
   provider state).
3. Re-run the v2 tests; expect them to still pass since the function
   signature change is additive.
4. Generate the prediction artifact for `target_trade_date=2026-05-15`
   with `anchor_trade_date=2026-05-13` (or, if a fresh capture is run
   on Friday morning, `target=2026-05-18 Monday` with
   `anchor=2026-05-14 Thursday` once that's in DB after Friday's
   21:30Z sync).
5. Commit + push **before** the target's US open.

If the operator chooses **Option A or C**, no further capture work
should happen tonight.

This document is the only artifact produced by tonight's attempt.
