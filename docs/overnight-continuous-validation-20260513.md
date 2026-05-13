# Overnight Continuous Validation + Safe Hardening — 2026-05-13

**Operator:** automated agent (Claude)
**Branch:** `master`
**Starting commit:** `14973a2` (`feat: add EOD freshness invariant (diagnostic only, no behaviour change)`)
**Cloud Run revision (start):** `quant-api-00053-4p7`
**FEATURE_T212_LIVE_SUBMIT:** `false` (verified)
**Scope:** read-only validation, regression tests, low-risk docs polish.
**Strict bounds:** no manual EOD/T212 sync; no scheduler change; no
broker/order/live-submit; no external web prices as primary eval.

**Runtime reality check:** the EOD fire is at `2026-05-13T21:30Z` —
roughly **19.6 hours** from this run's start (`01:54:51Z`). A single
conversation turn cannot literally wait that long. This document
records everything that can be done now (Phase 0, Phase 1 cycle 1,
Phases 4 / 5 / 6 / 7) and leaves a **precise runbook** for Phase 2 +
Phase 3 to execute after the natural fire.

---

## Phase 0 — Baseline (DONE)

| Check | Result |
|---|---|
| UTC now | `2026-05-13T01:54:51Z` |
| Time until next EOD fire | ~19h 35min |
| `git status -sb` | `master...origin/master` clean (only `.firebase` cache modified locally — won't be committed) |
| HEAD | `14973a2` |
| `gh run list --workflow CI` | latest 5 runs all `success` |
| `/api/health` | `{"status":"ok","service":"quant-api-platform","version":"0.1.0"}` |
| Cloud Run revision | `quant-api-00053-4p7` |
| API service digest | `sha256:f48f59e790e07311e90217866e111171ffb17dca41c34b2324f5d1dcdfa7182f` |
| `quant-sync-eod-prices` job image | `f48f59e790e0...` ✓ **aligned** (carries freshness invariant) |
| `quant-sync-t212` job image | `f48f59e790e0...` ✓ aligned |
| `quant-market-brief-overnight` job image | `7c9ccc3c0687...` (older — does NOT carry freshness module; intentionally untouched since the brief doesn't use freshness) |
| `quant-sync-eod-prices-schedule` | ENABLED, cron `30 21 * * 1-5 UTC` |
| `quant-market-brief-overnight-schedule` | ENABLED, cron `30 6 * * 1-5 UTC` |
| `quant-sync-t212-schedule` | ENABLED, cron `0 8,21 * * 1-5 UTC` |
| `FEATURE_T212_LIVE_SUBMIT` | `false` ✓ |

## Phase 4 — Overnight brief scheduler health soak (DONE)

| Field | Value |
|---|---|
| Brief job executions (last 4) | all exit 0, `succeeded=1` |
| Most recent execution | `quant-market-brief-overnight-28x6r` (2026-05-12T06:30Z, runtime 28s) |
| Next scheduled fire | `2026-05-13T06:30Z` (~4.5h from baseline) |
| Brief job image | `7c9ccc3c0687...` (older than API service image — intentionally; brief doesn't use the freshness module) |
| `quant-market-brief-overnight-schedule` state | `ENABLED` unchanged |
| `/api/market-brief/latest` (unauth) | 401 ✓ |
| `/api/market-brief/history?limit=5` (unauth) | 401 ✓ |
| `/api/market-brief/cd994ed6-…` (unauth) | 401 ✓ |
| `order_intent` / `order_draft` rows | `0 / 0` (unchanged) |
| Broker writes from brief job | NONE (per side-effect attestation in each persisted run) |
| Recommendation | **Keep scheduler ENABLED.** No remedial action. |

## Phase 5 — Market Events / News provider soak (DONE)

| Endpoint (unauth) | Result |
|---|---|
| `/api/market-events/feed` | 401 ✓ |
| `/api/market-events/ticker/MU` | 401 ✓ |
| `/api/market-events/news` | 401 ✓ |
| `/api/market-events/earnings` | 401 ✓ |
| `/api/market-brief/latest` | 401 ✓ |
| `/api/market-brief/history` | 401 ✓ |

No 5xx anywhere. No authenticated probe performed (no Firebase ID token
available to the agent — operator can do this manually if desired).

**Provider statuses from the most recent persisted brief**
(`market_brief_run.run_id = cd994ed6-44d0-41a4-b091-9459f527f184`,
2026-05-12T06:30Z — captured in prior session's DB harvest, no new
provider call this turn):

| Provider | Status | Counts |
|---|---|---|
| FMP news | `empty` | raw=0 parsed=0 skipped=0 |
| Polygon-Massive news | `ok` | raw=13 parsed=13 skipped=0 |
| Merged news | `ok` | pre_dedup=13, deduped=8, dropped=5 |
| Math invariant `pre_dedup == deduped + dropped` | ✓ `13 == 8 + 5` | |
| Earnings | `unavailable` | (no plan access this window — expected) |

No providers rate-limited at last persisted check. All down ≠ true.

## Phase 6 — Regression tests + source-grep + frontend build (DONE)

| Item | Result |
|---|---|
| `tests/unit/test_eod_freshness.py` | **34 / 34 passing** in 0.10s |
| Full `tests/unit` suite | **544 / 544 passing** in 65.72s |
| `frontend-react/` `npm run build` | clean, bundle `index-p8b2eN3y.js` (610.44 kB / gzip 160.53 kB) |
| Integration tests | **deliberately not run** — known to require Postgres + Firebase token unavailable to this agent. Not in CI scope. |

### Source-grep — classified summary

The pattern scan reported 38 raw "hits" total. **Every one is either a
known-gated code path, a documentation negation, a test fixture
placeholder, or a public Firebase web SDK key — i.e. all are false
positives or pre-existing intentional state.** Detailed classification:

| Class | Count | Status |
|---|---|---|
| `submit_*_order` / `OrderIntent()` / `OrderDraft()` in `libs/adapters/` `libs/execution/` `libs/db/models/` | 8 | EXISTING gated code path. Locked behind `FEATURE_T212_LIVE_SUBMIT=false`. `order_intent` and `order_draft` tables are EMPTY (0 rows, verified). |
| OrderIntent/OrderDraft mentions in `docs/overnight-*.md` | 6 | NEGATION CONTEXT — attestation tables saying these were NOT called. |
| `FEATURE_T212_LIVE_SUBMIT=true` in `PROJECT_SUMMARY.md` | 1 | DOCS TEXT describing what the gate would mean if enabled. Not the actual setting. |
| DSN with placeholder creds (`YOUR_PASSWORD`, `PASSWORD`) in `docs/deployment.md` | 2 | Placeholder strings for operator examples. |
| DSN test fixtures (`q:p@...`) in `tests/unit/test_bootstrap_research_universe_prod.py` | 5 | Test fixtures with fake creds. |
| Firebase Web SDK `apiKey` in `frontend-react/src/firebase.js` | 1 | **PUBLIC** Firebase web key — by Firebase design intentionally embedded in client; identifies project, not a credential. |
| Real `.env` secret (Gemini API key, line 30) | 1 | **Security note** — see below. |
| `.firebase/hosting.*.cache` tracked file | 1 | Pre-existing from before `.gitignore` was updated. Contains only Firebase deploy file-hash metadata, no secrets. |

#### `.env` security note (action recommended)

`.env` is correctly `.gitignore`d AND `git ls-files .env` returns
nothing — the file has **never been committed**. However, the scan
touched the file content (because the grep walks the working
directory) and the key value briefly appeared in the agent's stdout
transcript. **As a precaution, recommend rotating the Gemini API key**
(replace the value in `.env` locally — no commit needed since it's
already gitignored).

The key has **not** been written to any committed file, has **not**
been used to call any external API, and has **not** been transmitted
anywhere by this agent. No further mitigation required beyond rotation.

## Phase 7 — Low-risk docs polish (DONE)

| File | Change |
|---|---|
| `docs/runbook.md` | Added new §14 "EOD Freshness Invariant — interpreting `freshness_status`" with the 4-status decision matrix, provider T-1 lag explanation, log-reading recipe, and opt-in strict-mode procedure |
| `docs/runbook.md` | Added new §15 "Evaluating a Pre-market Shadow Prediction" with the pre-flight gates, read-actuals SQL, classification rules, full metric list, missing-bars handling, and append-only commit convention |
| `docs/overnight-continuous-validation-20260513.md` | This run log (per-phase results + Phase 2/3 runbook below) |

(Mirror-bootstrap rollback source-label correction was already landed
in commit `a4eafc1` in a prior session; no additional change needed
here.)

## Phase 2 + Phase 3 — PENDING runbook (for after the natural 21:30Z EOD fire)

These two phases cannot run in this turn because the EOD fire is ~19.6h
away. Below is the **exact procedure** the next agent turn (or the
operator manually) should execute when the natural fire has completed.

### Phase 2 — EOD freshness check (run starting `2026-05-13T21:40Z`)

```bash
# Step 1 — find the most recent EOD execution
gcloud run jobs executions list --job=quant-sync-eod-prices \
  --region=asia-east2 --limit=2 \
  --format="table(name,createTime,completionTime,succeededCount,failedCount)"
```

Confirm it was scheduler-fired (createTime within ~10s of `21:30:00Z`),
not manually triggered. If anything looks off (succeededCount=0,
failedCount>0, runtime substantially different from prior ~8m6s),
STOP and report — do NOT auto-re-trigger.

```bash
# Step 2 — read the SYNC RESULT + Freshness invariant block
EXEC=<execution-name-from-step-1>
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"quant-sync-eod-prices\" AND timestamp>\"2026-05-13T21:30:00Z\"" \
  --limit=300 --order=asc --format="value(textPayload)" \
  | grep -A 40 "SYNC RESULT"
```

Extract from that block:

* `ticker_count`, `succeeded`, `failed`, `bars_inserted_total`,
  `bars_existing_or_skipped_total`, `runtime_seconds`
* From the new `Freshness invariant:` sub-block: `today`,
  `expected_min_trade_date`, `latest_trade_date`,
  `freshness_status`, per-ticker breakdown, warning_message

### Phase 2 read-only DB confirm (one-shot Cloud Run Job)

Use the same base64-payload pattern from prior sessions — create a
short-lived `quant-ops-freshness-confirm` Job with payload:

```python
from sqlalchemy import text
from libs.db.session import get_sync_session

s = get_sync_session()
TICKERS = ['MU','AMD','AVGO','GOOGL','INTC','AAPL','AMZN','GS','IWM','LITE',
           'NOK','NVDA','QQQ','SIRI','SPY','TSLA','TSM','AAOI','CRCL','CRWV',
           'IPOE','OAC','ORCL','SNDK1','TEM','VACQ']

# overall max
r = s.execute(text("select max(trade_date), count(*) from price_bar_raw")).fetchone()
print(f"OVERALL_MAX={r[0]} TOTAL_ROWS={r[1]}")

# rows for 2026-05-12
r = s.execute(text(
    "select count(*) from price_bar_raw where trade_date='2026-05-12'"
)).scalar()
print(f"ROWS_2026_05_12={r}")

# distinct tickers with 2026-05-12 bars
r = s.execute(text(
    "select count(distinct pbr.instrument_id) from price_bar_raw pbr "
    "where pbr.trade_date='2026-05-12'"
)).scalar()
print(f"DISTINCT_TICKERS_2026_05_12={r}")

# per-ticker missing list for the 26 prediction tickers
rows = s.execute(text(
    "select ii.id_value, "
    "max(case when pbr.trade_date='2026-05-12' then 1 else 0 end) "
    "from instrument_identifier ii "
    "left join price_bar_raw pbr on pbr.instrument_id=ii.instrument_id "
    "where ii.id_type='ticker' and ii.id_value = any(:t) "
    "group by ii.id_value order by ii.id_value"
), {"t": TICKERS}).fetchall()
print("PER_TICKER_BEGIN")
for r in rows:
    print(f"  {r[0]:<8} has_2026_05_12={r[1]}")
print("PER_TICKER_END")
s.close()
```

**Delete the Job immediately after success.**

### Decision tree

| Phase 2 finding | Action |
|---|---|
| `freshness_status=fresh` AND `ROWS_2026_05_12 ≥ 15` (at least the 15 scanner-research tickers with full prediction inputs) | Proceed to Phase 3. |
| `freshness_status=provider_lag` AND `ROWS_2026_05_12 < 15` | Eval stays PENDING. Wait for the next sync. **Do not** trigger a manual sync. |
| `freshness_status=stale` | Eval stays PENDING. Investigate provider / sync. Open a separate diagnosis. |
| `succeededCount=0` or `failedCount>0` | Eval stays PENDING. Do NOT auto-re-trigger. Report to operator. |
| `freshness_status=partial` | Inspect per-ticker; if the 15 scanner-research prediction tickers are all fresh, proceed with the available subset; else PENDING. |

### Phase 3 — Platform-native prediction accuracy (only if Phase 2 → fresh)

```python
# Pseudocode for the eval script — should be run as a docs-only audit,
# read-only against price_bar_raw, no provider HTTP, no external web.
import json, csv, sys
from sqlalchemy import text
from libs.db.session import get_sync_session

pred = json.load(open("docs/premarket-shadow-prediction-20260512.json"))
assert pred["preregistered_at"] < "2026-05-12T13:30:00Z"  # pre-open gate
assert pred["eval_target_trade_date"] == "2026-05-12"
assert pred["previous_trade_date_anchor"] == "2026-05-11"

s = get_sync_session()
rows = []
for p in pred["predictions"]:
    ticker = p["ticker"]
    r = s.execute(text(
        "select pbr.trade_date, pbr.close "
        "from price_bar_raw pbr "
        "join instrument_identifier ii on ii.instrument_id=pbr.instrument_id "
        "where ii.id_type='ticker' and ii.id_value=:t "
        "  and pbr.trade_date in ('2026-05-11','2026-05-12') "
        "order by pbr.trade_date"
    ), {"t": ticker}).fetchall()
    closes = {str(r0): float(r1) for r0, r1 in rows}
    # ... compute actual_return, actual_direction, actual_bucket ...
    # ... match against p["predicted_direction"] / p["predicted_return_bucket"] ...
```

Match the rules already enumerated in `docs/runbook.md §15` and the
eval doc `docs/premarket-shadow-prediction-20260512-eval.md §4`.

Compute and write:

* `evaluated_tickers_count` (denominator)
* `missing_data_tickers_count` with reasons (typically the 7 mirror
  bootstrap tickers + 4 unmapped tickers — total 11 expected to lack
  bars)
* `direction_accuracy` / `bucket_accuracy` / `MAE_pct`
* Confidence-stratified accuracy (note: all 26 predictions have
  `confidence=low` for this Test #3 run; the stratified table is
  documented for completeness even if only `low` has samples)
* Split metrics: held vs non-held; scanner vs mirror; news-linked vs
  not; mapped vs unmapped

Write the results to **two files**:

1. **New**: `docs/platform-prediction-accuracy-20260512-final.md`
   (canonical, full per-ticker table)
2. **Append to existing**: `docs/premarket-shadow-prediction-20260512-eval.md`
   adding only a new `§7 Results` section. **Do not rewrite** the
   pre-registration sections.

Commit: `docs: evaluate platform prediction accuracy 20260512`
Push.

### Strict invariants for Phase 2 + Phase 3 (carry from this run)

* **No manual EOD sync execution.**
* **No `quant-sync-t212` execution.**
* **No scheduler change.**
* **No T212 endpoint / broker / order / live-submit.**
* **No external web data used as primary actuals** — must be `price_bar_raw`.
* **No DB write** except via the routine natural scheduled job.
* **`FEATURE_T212_LIVE_SUBMIT=false` preserved.**
* The transient `quant-ops-freshness-confirm` Job (if created) must be
  **deleted in-run** after success — no persistent footprint.

## Phase 1 — Pre-EOD validation cycle 1 (DONE; cycles 2+ deferred)

| Field | Value at cycle 1 |
|---|---|
| Cycle timestamp UTC | `2026-05-13T01:54:51Z` |
| Latest `quant-sync-eod-prices` execution | `quant-sync-eod-prices-qjxqk` (2026-05-12T21:38Z, exit 0, succeeded=1, runtime 8m6s) |
| `price_bar_raw.max(trade_date)` | `2026-05-11` (no 2026-05-12 yet — expected per provider T-1 lag) |
| Rows for `2026-05-12` | `0` |
| Latest `market_brief_run` | `cd994ed6-44d0-41a4-b091-9459f527f184` (overnight, 2026-05-12T06:30Z, ticker_count=26) |
| `quant-market-brief-overnight-schedule` state | ENABLED (unchanged) |
| `/api/health` | OK |
| Cloud Run job failures last 2h | NONE |
| GitHub CI latest | `success` (`14973a2`) |
| Prediction eval `pending` | **YES** (target trade_date `2026-05-12` not yet in DB) |

