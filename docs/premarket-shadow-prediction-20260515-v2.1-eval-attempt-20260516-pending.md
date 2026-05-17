# Shadow Test #4 Rule v2.1 — Eval attempt 2026-05-16 — **PENDING**

**Status:** Eval **NOT** computed. Stopped at the
`docs/premarket-shadow-prediction-20260515-v2.1-eval.md §1` timing
gate. **No accuracy numbers written. No edits to that eval doc.**

The pending-state is **by design** — the v2.1 amendment and v2.1
eval doc both explicitly stated that the earliest eval window is
Tuesday `2026-05-19T00:00Z` UTC, after Monday's `21:30Z`
`quant-sync-eod-prices-schedule` fire delivers Friday's
`2026-05-15` bars under the platform's T-1 provider lag.

| | Value |
|---|---|
| Audit time (UTC) | `2026-05-16T23:57Z` (Saturday) |
| Prediction artifact | `docs/premarket-shadow-prediction-20260515-v2.1.json` (commit `4b41dfc`, frozen) |
| `target_trade_date` | `2026-05-15` (Friday) |
| `anchor_trade_date` | `2026-05-13` (Wednesday) |
| `horizon` | `latest_db_close_to_target_close` |
| Next opportunity for eval | Tuesday `2026-05-19T00:00Z` UTC (after Monday `2026-05-18T21:30Z` EOD sync) |

---

## 1. Eval gate result (per `…-eval.md §1`)

| Gate | Status |
|---|---|
| (1) US `2026-05-15` regular session closed (≥ `2026-05-15T20:00Z`) | ✓ PASS (closed ~52h before this audit) |
| (3) Anchor `2026-05-13` already in `price_bar_raw` | ✓ PASS (36 scanner rows, including all 17 candidate tickers) |
| **(2) Target `2026-05-15` rows in `price_bar_raw`** | **✗ FAIL — `count(*) = 0`** |

Read-only DB probe (transient Cloud Run Job
`quant-ops-v21-eval-check-gcs68`, created + executed + **deleted
in-run** — no persistent footprint):

```
OVERALL_MAX_TRADE_DATE = 2026-05-14
TOTAL_ROWS             = 13548
ROWS_2026-05-13        = 36   (anchor — present)
ROWS_2026-05-14        = 36   (intermediate weekday)
ROWS_2026-05-15        = 0    (target — missing)

per-candidate gate (17 eligible tickers from the v2.1 prediction):
  AAPL  anchor=1 target=0      INTC  anchor=1 target=0
  AMC   anchor=1 target=0      IWM   anchor=1 target=0
  AMD   anchor=1 target=0      LCID  anchor=1 target=0
  AMZN  anchor=1 target=0      MU    anchor=1 target=0
  AVGO  anchor=1 target=0      NVDA  anchor=1 target=0
  GOOGL anchor=1 target=0      QQQ   anchor=1 target=0
  GS    anchor=1 target=0      SIRI  anchor=1 target=0
                               SPY   anchor=1 target=0
                               TSLA  anchor=1 target=0
                               TSM   anchor=1 target=0
```

Every candidate has the anchor but is missing the target. **Zero
candidates can be evaluated. Eval denominator would be zero.**

## 2. Latest EOD sync fired cleanly — this is provider lag, not infra failure

Friday's scheduled fire executed cleanly. Its `Freshness invariant:`
block confirms `fresh` status against its own `expected_min`, but
the data delivered is one trading day behind the v2.1 target:

| Field | Value |
|---|---|
| Execution name | `quant-sync-eod-prices-ghhq6` |
| Created | `2026-05-15T21:30:05.920Z` (scheduler-fired) |
| Completed | `2026-05-15T21:38:15.202Z` (8m9s) |
| `succeededCount` | `1` |
| `failedCount` | `None` |
| `freshness_status` | `fresh` |
| `expected_min_trade_date` | `2026-05-14` |
| `latest_trade_date` | `2026-05-14` (**Thursday**, not Friday) |
| Per-ticker | `fresh=36 stale=0 bar_less=7 inspected=43` |

The "fresh" classification is honest within the EOD invariant's own
contract — it compares against `previous_weekday(today)`. The v2.1
eval needs **the actual target `T = 2026-05-15`** in DB, which is one
trading day beyond what the invariant tracks. Under the platform's
T-1 provider feed, target-day close lands on the NEXT weekday's
`21:30Z` fire (Monday `2026-05-18T21:30Z` for this prediction).

## 3. What would have been computed if the gate passed (NOT computed; recorded for transparency)

| Quantity | Value if eval ran |
|---|---|
| `evaluated_count` | up to 16 (the v2.1 eligible set; the 17th anchor-probed ticker SIRI is in scanner-research but was already in the eligible 16 — recheck shows 16 = 16 eligible) |
| `direction_accuracy` | **N/A — pending** |
| `bucket_accuracy` | **N/A — pending** |
| `MAE_pct` | **N/A — pending** |
| `low_confidence_direction_accuracy` | **N/A — pending** (all 16 eligible are `confidence=low`; this is the only stratum with data) |
| `medium_confidence_direction_accuracy` | **N/A** (0 medium rows in the v2.1 capture) |
| `high_confidence_direction_accuracy` | **N/A** (0 high rows) |
| Splits (held / news_linked / scanner) | **N/A — pending** |

## 4. Decision

Per the user instruction "必须等 EOD freshness_status=fresh 后再算":

* The most recent EOD fire IS `freshness_status=fresh` from the
  invariant's POV, BUT that freshness reports
  `latest_trade_date=2026-05-14`, not `2026-05-15`.
* The v2.1 eval's own gate (`…-eval.md §1.2`) explicitly requires
  `2026-05-15` rows, which the freshness invariant does not yet
  guarantee.
* The two conditions therefore disagree this turn. Per the user's
  forward instructions and the v2.1 eval doc §1, **the v2.1 eval
  doc's explicit gate is the binding contract**. That gate fails →
  eval is **pending**.

**No eval numbers computed. No edits to `docs/premarket-shadow-prediction-20260515-v2.1-eval.md`.** That doc's `§7 Results` placeholder remains empty per its own append-only contract — fill it only when eval can run with real numbers.

## 5. Next eval window

| | Value |
|---|---|
| Next `quant-sync-eod-prices-schedule` fire | `2026-05-18T21:30Z` (Monday) — cron `30 21 * * 1-5 UTC` |
| Expected `bars_inserted` for that fire (under T-1 lag) | bars for `trade_date='2026-05-15'` (Friday) |
| Earliest eval execution window | Tuesday `2026-05-19T00:00Z` UTC (~10 minutes after Monday's fire completes; full procedure in `…-eval.md §1–§6`) |
| Eval doc to append `§7 Results` into | `docs/premarket-shadow-prediction-20260515-v2.1-eval.md` |

When eval runs at that window, the procedure is exactly the one
documented in `docs/premarket-shadow-prediction-20260515-v2.1-eval.md
§2–§5` — no procedural changes required.

## 6. Strict side-effect attestations (this pending attempt)

| Property | Status |
|---|---|
| Manual EOD sync triggered | **NO** — eval gate failure does NOT authorise a manual sync (would taint the metric and violate operator policy) |
| Manual `quant-sync-t212` execution | NONE |
| Manual brief job execution | NONE |
| Scheduler create / update / pause / resume | NONE (all 3 ENABLED, cron unchanged) |
| T212 endpoint / broker submit | NONE |
| `order_intent` / `order_draft` created | 0 (unchanged) |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (verified) |
| Production DB write | NONE — only a read-only `SELECT` Cloud Run Job (`quant-ops-v21-eval-check-gcs68`), **deleted in-run** after success |
| Cloud Run service deploy | NONE (still `quant-api-00053-4p7`) |
| Migration | NONE |
| External web prices | NEVER consulted (production `price_bar_raw` only — and even that came back empty for the target date) |
| Browser automation / scraping | NONE |
| Secrets exposed in committed text | NONE |
| `.firebase/` cache committed | NO |
| v1 artifacts (`docs/*20260512*`) | UNCHANGED |
| v2 pre-registration | UNCHANGED |
| v2.1 amendment | UNCHANGED |
| v2.1 prediction artifact (`docs/*20260515-v2.1.json`) | UNCHANGED |
| v2.1 eval doc `§1–§6` | UNCHANGED |
| v2.1 eval doc `§7 Results` | UNCHANGED (still empty placeholder; will be filled by the operator OR a future agent turn after Monday's sync) |

## 7. References

* Canonical v2.1 prediction: `docs/premarket-shadow-prediction-20260515-v2.1.json` (commit `4b41dfc`)
* Canonical v2.1 eval procedure: `docs/premarket-shadow-prediction-20260515-v2.1-eval.md` (commit `4b41dfc`)
* v2.1 amendment: `docs/premarket-shadow-test-4-rule-v2.1-amendment.md`
* EOD freshness invariant: `libs/ingestion/eod_freshness.py`
* Runbook §15 (eval procedure) + §16 (v2.1 operator notes): `docs/runbook.md`

This document records the eval attempt's gate-failure evidence so the
next eval turn (Tuesday or later) has full audit context without
having to re-probe the DB.
