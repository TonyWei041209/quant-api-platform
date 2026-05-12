# EOD Freshness Lag Diagnosis — 2026-05-12

**Status:** Diagnosis complete. Root cause = **provider T-1 delivery lag**,
NOT a sync code bug. Add-on freshness invariant landed as observable
diagnostics (no behaviour change to the sync core).
**Audit window (UTC):** `2026-05-13T03:30Z`–`2026-05-13T04:20Z`
**Cloud Run service revision:** `quant-api-00052-t5j` (unchanged — no
deploy in this audit window).

---

## 1. Symptom

The premarket prediction `docs/premarket-shadow-prediction-20260512.json`
(commit `597156e`, pre-registered `2026-05-12T12:46:43Z`) cannot be
evaluated because `price_bar_raw` does not yet carry the eval target
trade date `2026-05-12`.

`max(trade_date) = 2026-05-11` as of audit time (one trading day behind
expectation).

The EOD sync Cloud Run Job
(`quant-sync-eod-prices`) reports `succeeded=1`/`exit 0` on every fire,
including the runs at `2026-05-11T21:30Z` (cfbqn) and `2026-05-12T21:30Z`
(qjxqk). Yet neither inserted a `2026-05-12` bar.

## 2. Diagnosis (read-only)

### 2.1 Sync job execution history

| Execution | Fire (UTC) | Runtime | exit | succeeded |
|---|---|---|---|---|
| `quant-sync-eod-prices-qjxqk` | `2026-05-12T21:30:11Z` | 8m6s | 0 | 1 |
| `quant-sync-eod-prices-cfbqn` | `2026-05-11T21:30:10Z` | 8m6s | 0 | 1 |
| `quant-sync-eod-prices-c58zx` | `2026-05-08T21:30:09Z` | 8m8s | 0 | 1 |
| `quant-sync-eod-prices-ctgww` | `2026-05-07T21:30:09Z` | 8m8s | 0 | 1 |
| `quant-sync-eod-prices-8tt2f` | `2026-05-06T21:30:09Z` | 8m8s | 0 | 1 |

All five jobs completed cleanly with no failed-count.

### 2.2 SYNC RESULT block — qjxqk (2026-05-12T21:30Z)

```
SYNC RESULT — universe='scanner-research'  mode=WRITE_PRODUCTION
  ticker_count                  : 36
  succeeded                     : 36
  failed                        : 0
  bars_inserted_total           : 36
  bars_existing_or_skipped_total: 216
  runtime_seconds               : 480.4
  db_target                     : production
  Side-effect attestations:
    Broker write                 : NONE
    Live submit                  : LOCKED (FEATURE_T212_LIVE_SUBMIT=false)
```

`216 = 36 tickers × 6 existing trade days` (2026-05-01, 04, 05, 06, 07,
08). `36 inserted = 36 tickers × 1 new trade day`. The "1 new day" was
**`2026-05-11`** — the previous trading day, NOT `2026-05-12`.

Same shape on the prior fire (cfbqn): inserted `2026-05-08` (the prior
Friday) because by Monday 21:30Z the upstream feed had finally
published Friday's bar.

### 2.3 Provider HTTP probe (read-only via temporary Cloud Run Job)

Provider window asked: `/v2/aggs/ticker/NVDA/range/1/day/2026-05-04/2026-05-12`

Provider returned dates: `['2026-05-04', '2026-05-05', '2026-05-06', '2026-05-07', '2026-05-08', '2026-05-11']`

Same shape for `MU`. **`2026-05-12` is NOT in the provider response at
audit time**, despite being inside the requested window. This is
upstream T-1 delivery — the provider publishes "today's" EOD bar some
time between T+0 21:00Z and T+1 04:00Z, and the sync job at T+0 21:30Z
runs inside that publication window.

### 2.4 DB state (read-only)

```
overall max(trade_date) = 2026-05-11
total price_bar_raw rows  = 13 404

rows by trade_date:
  2026-05-01: 36
  2026-05-04: 36
  2026-05-05: 36
  2026-05-06: 36
  2026-05-07: 36
  2026-05-08: 36
  2026-05-11: 36
  (no row for 2026-05-12)

tickers with bars      = 36 (all scanner-research-36, uniformly max=2026-05-11)
tickers without bars   = 7 (NOK, AAOI, ORCL, VACQ, CRWV, CRCL, TEM —
                            mirror-bootstrapped 2026-05-11, scaffolding-only)
```

### 2.5 source_run table — stale

`source_run` last row is from `2026-03-27`. The current
`sync_eod_prices_universe.execute_sync` path does NOT write to
`source_run` (separate diagnostic gap — flagged below as item 7.2 but
not actioned in this audit).

## 3. Root cause

**Upstream provider T-1 EOD delivery.** Confirmed by direct adapter
probe — provider returns through `2026-05-11` at `2026-05-13T03:54Z`,
six hours after the most recent sync fire. The sync code is functioning
correctly:

* Date window is correct (`2026-05-01..2026-05-12` includes today).
* On-conflict-do-nothing upsert is correct.
* Per-bar parsing path is correct.
* The `bars_inserted_total` counter is technically accurate but
  misleading without trade-date context: it counts "rows newly written
  this fire", not "rows for `today`".

The 2026-05-12 bar will land at the **next scheduled fire**
(`quant-sync-eod-prices-schedule` cron `30 21 * * 1-5 UTC`,
next run `2026-05-13T21:30Z`).

## 4. Fix landed in this audit

**No behaviour change to the sync core.** Per the user's policy
("如果只是 provider lag，先不改逻辑，只加 diagnostics/tests"):

### 4.1 New module `libs/ingestion/eod_freshness.py`

Pure-function helper (no DB call, no provider HTTP) that classifies
the freshness of the EOD pipeline into one of four statuses:

| Status | Meaning | Decision |
|---|---|---|
| `fresh` | `db_max(trade_date) ≥ expected_min_trade_date` | downstream consumers may proceed |
| `provider_lag` | DB is 1–`stale_after_days` calendar days behind | transient — wait one more sync |
| `stale` | DB is `> stale_after_days` behind | ops investigation required |
| `partial` | some tickers fresh, some stale | typically immediately after a mirror bootstrap |

`expected_min_trade_date` is computed as the **previous weekday** of
`today` (calendar approximation — does NOT subtract holidays; the
canonical exchange calendar lives elsewhere in the codebase). The
helper never raises and never exits the process.

An opt-in environment flag `EOD_FRESHNESS_STRICT_MODE=true` is plumbed
through to `FreshnessReport.strict_mode`; the helper itself does NOT
use this flag — it only surfaces it so a caller (e.g. a future
strict-mode Cloud Run Job) can choose to exit non-zero. **Default
behaviour for the current scheduled job is unchanged** — exit 0 with
`provider_lag` is still acceptable.

### 4.2 SyncResult extension

`SyncResult.freshness: dict | None` carries the freshness report dict.
`render_sync_result()` prints a new `Freshness invariant:` block right
after the side-effect attestations. The block includes
`freshness_status`, `today`, `expected_min_trade_date`,
`latest_trade_date`, per-ticker counts, and the warning message when
status ≠ `fresh`.

`execute_sync()` calls `compute_freshness_report` after the per-ticker
loop completes. Failures of the freshness check are isolated — they
log a warning but never break the sync return.

### 4.3 Tests

`tests/unit/test_eod_freshness.py` — **34 hermetic tests** covering all
four statuses, the `stale_after_days` boundary, the empty-DB edge case,
mirror-bootstrap bar-less handling, strict-mode env-flag plumbing, the
render block fields, logging contract, and source-grep guards.

Full backend unit suite: **544 / 544 passing** (was 510 before; +34
new).

## 5. Affected ticker context

| Group | Tickers | Latest bar | Note |
|---|---|---|---|
| Scanner research-36 | All 36 | `2026-05-11` | Fresh-up-to-T-1 |
| Mirror bootstrap-7 | NOK, AAOI, ORCL, VACQ, CRWV, CRCL, TEM | none | Bar-less by design — scaffolding-only |
| Predictions in target run | 26 (15 with full input, 11 weak-data) | — | Eval pending the 2026-05-12 close |

## 6. Recommendation — wait for the next scheduled fire

The eval will become possible once:

1. `quant-sync-eod-prices-schedule` fires at `2026-05-13T21:30Z` (cron
   `30 21 * * 1-5 UTC`).
2. The job's new freshness block reports `freshness_status=fresh`
   (i.e., `db_max(trade_date) ≥ 2026-05-12`).
3. The premarket-shadow-prediction-20260512-eval procedure becomes
   runnable. Results will be appended to that doc's §7.

**No manual EOD sync triggered in this audit.** The user's prompt
explicitly forbade it without separate authorization. The provider lag
will clear naturally.

## 7. Other items flagged (informational — NOT actioned in this audit)

### 7.1 `bars_inserted_total` counter is misleading

The counter is technically correct but operationally confusing — it
reports rows-written-this-fire, not rows-for-today. A future hardening
could add a `bars_inserted_by_trade_date: dict[date, int]` breakdown
to the SyncResult so the operator immediately sees which date each
new bar belongs to.

### 7.2 `source_run` table is stale (last write 2026-03-27)

The modern `execute_sync` path does not write to `source_run` even
though the schema is in place. This is a diagnostic-only gap (the
job still writes its rows to `price_bar_raw`) and is recorded here as
follow-up work, not actioned now.

### 7.3 Mirror-bootstrap tickers have no bars

The 7 mirror-bootstrap-source tickers (NOK / AAOI / ORCL / VACQ / CRWV
/ CRCL / TEM) carry zero `price_bar_raw` rows. This is by design —
`execute_bootstrap` is scaffolding-only. The new freshness helper
correctly classifies these as `bar_less`, not `stale`. A future phase
could either (a) extend the EOD sync universe to include them, or
(b) run a one-shot historical seed; both options stay deferred.

### 7.4 Strict-mode wiring is opt-in

`EOD_FRESHNESS_STRICT_MODE` is plumbed but not wired to a non-zero exit
in any current job. If we ever want the scheduled job to fail loud
when freshness is `stale`, the caller pattern is documented at the top
of `libs/ingestion/eod_freshness.py`.

## 8. Strict side-effect attestations (this audit + fix)

| Property | Status |
|---|---|
| `FEATURE_T212_LIVE_SUBMIT` | `false` ✓ (verified at start, preserved end-to-end) |
| T212 write endpoint called | NONE |
| Broker submit | NONE |
| `order_intent` / `order_draft` created | 0 (unchanged) |
| Production DB write driven by this audit | NONE — every query was `SELECT`-only; the new `eod_freshness.py` module also only reads |
| Production DB write driven by the scheduled sync (yesterday) | `price_bar_raw` only, `+36` rows for `trade_date=2026-05-11` (Mirror sync run, NOT this audit) |
| Cloud Run service deploy | NONE — revision still `quant-api-00052-t5j`. The new freshness module is committed but NOT deployed in this audit window. |
| Cloud Run Jobs created during audit | `quant-ops-freshness-audit`, `quant-ops-provider-probe` (both read-only SELECT + provider GET; both **deleted in-run** — no persistent footprint) |
| Schedulers modified | NONE — all 3 schedulers (`quant-market-brief-overnight-schedule`, `quant-sync-eod-prices-schedule`, `quant-sync-t212-schedule`) untouched |
| Manual EOD sync triggered | NO — explicitly deferred to the regular schedule |
| Migration | NONE |
| Cloud SQL backup | NONE (read-only audit, no backup required) |
| Provider HTTP volume | 2 probe GETs (NVDA + MU EOD bars). No write endpoint. No order endpoint. |
| External web source used as primary data | NO — strict platform-DB-and-provider-adapter only |
| API key printed in any log line | NONE — DB URL printed as `quantuser:***@…` redacted form; provider key never logged |
| `.firebase/` cache committed | NO |
| Files modified in this commit | `libs/ingestion/eod_freshness.py` (new), `libs/ingestion/sync_eod_prices_universe.py` (additive — `freshness` field on SyncResult, `Freshness invariant:` block in render, post-loop helper call), `tests/unit/test_eod_freshness.py` (new), this doc. |
| Source-grep on the new/changed files | CLEAN |

## 9. Next manual verification steps

1. Wait for `quant-sync-eod-prices-schedule` next fire at
   `2026-05-13T21:30Z`. The new freshness block should appear in the
   SYNC RESULT log.
2. After that fire, re-query `max(trade_date) from price_bar_raw`. If
   it reports `2026-05-12`, the prediction eval procedure in
   `docs/premarket-shadow-prediction-20260512-eval.md §1` can run.
3. **(Optional)** to make the new freshness block visible on the next
   fire, deploy a fresh image first via `scripts\deploy-api.ps1`
   followed by syncing `quant-sync-eod-prices` to the same digest. If
   skipped, the EOD job will keep using the previous image and the
   freshness block won't print until the next deploy aligns the EOD
   job. The diagnosis report above is independent of that deploy.
