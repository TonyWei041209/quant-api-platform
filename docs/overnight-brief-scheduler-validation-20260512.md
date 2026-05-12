# Overnight Brief Scheduler — Validation (2026-05-12 read-only audit)

**Status:** read-only validation report. No production changes, no
deploy, no migration, no scheduler modification, no broker operation,
no DB write.

This document records the first two auto-fires of the
`quant-market-brief-overnight-schedule` Cloud Scheduler after it was
resumed from `PAUSED` → `ENABLED` at the end of the 2026-05-10
Continuation Push.

---

## 1. Scheduler state (audit time)

| Field | Value |
|---|---|
| Name | `quant-market-brief-overnight-schedule` |
| Region | `asia-east2` |
| State | **`ENABLED`** |
| Schedule | `30 6 * * 1-5` |
| Time zone | `UTC` |
| Last attempt | `2026-05-12T06:30:05.018724Z` |
| Next scheduleTime | `2026-05-13T06:30:04.057148Z` |
| Target | Cloud Run Job `quant-market-brief-overnight` (asia-east2) |
| Target command | `python -m apps.cli.main generate-market-brief --mode=overnight --write-snapshot --db-target=production --days=7 --scanner-limit=50 --news-top-n=5 --news-limit-per-ticker=3` |
| Pause / rollback | `gcloud scheduler jobs pause quant-market-brief-overnight-schedule --location=asia-east2` |

Sibling schedulers (intentionally **not** modified in this audit):

| Name | State | Schedule |
|---|---|---|
| `quant-sync-t212-schedule` | `ENABLED` | `0 8,21 * * 1-5` |
| `quant-sync-eod-prices-schedule` | `ENABLED` | `30 21 * * 1-5` |

---

## 2. First auto-run — 2026-05-11T06:30 UTC

| Field | Value |
|---|---|
| Cloud Run Job execution | `quant-market-brief-overnight-cnnkp` |
| Trigger source | Cloud Scheduler (auto) |
| Created | `2026-05-11T06:30:01.311Z` |
| Started | `2026-05-11T06:30:05.356Z` |
| Completed | `2026-05-11T06:30:27.617Z` |
| Runtime | ~22 s |
| Exit code | `0` |
| Succeeded / Failed | `1 / 0` |

**Structured stdout (verbatim from Cloud Logging):**

```
status=ok
ticker_count=24
universe_scope.days_window=7
universe_scope.effective_news_top_n=5
universe_scope.merged_ticker_count=24
universe_scope.mirror_ticker_count=14
universe_scope.news_fanout_top_n=5
universe_scope.requested_news_top_n=5
universe_scope.scanner_matched=14
universe_scope.scanner_scanned=43
universe_scope.scanner_universe=scanner-research-36
news_section_state=ok
side_effects.broker_writes=NONE
side_effects.db_writes=NONE
side_effects.execution_objects=NONE
side_effects.live_submit=LOCKED (FEATURE_T212_LIVE_SUBMIT=false)
side_effects.scheduler_changes=NONE

status=snapshot_done
ok=True
skipped=False
rows_written=25
run_id=a95ceb37-9fba-49af-bd49-771f2832f4a0
```

Notable transient events (caught by P0/P2.1 hardening, not failures):

* 5 per-ticker FMP news timeouts on `MU / NOK / AMD / INTC / AMZN`
  — section-budget tripped; Polygon-Massive filled in;
  `news_section_state` stayed `ok`.

---

## 3. Second auto-run — 2026-05-12T06:30 UTC

| Field | Value |
|---|---|
| Cloud Run Job execution | `quant-market-brief-overnight-28x6r` |
| Trigger source | Cloud Scheduler (auto) |
| Created | `2026-05-12T06:30:05.199Z` |
| Started | `2026-05-12T06:30:09.221Z` |
| Completed | `2026-05-12T06:30:33.359Z` |
| Runtime | ~24 s |
| Exit code | `0` |
| Succeeded / Failed | `1 / 0` |

**Structured stdout (verbatim):**

```
status=ok
ticker_count=26
universe_scope.days_window=7
universe_scope.effective_news_top_n=5
universe_scope.merged_ticker_count=26
universe_scope.mirror_ticker_count=15
universe_scope.news_fanout_top_n=5
universe_scope.requested_news_top_n=5
universe_scope.scanner_matched=15
universe_scope.scanner_scanned=43
universe_scope.scanner_universe=scanner-research-36
news_section_state=ok
side_effects.broker_writes=NONE
side_effects.db_writes=NONE
side_effects.execution_objects=NONE
side_effects.live_submit=LOCKED (FEATURE_T212_LIVE_SUBMIT=false)
side_effects.scheduler_changes=NONE

status=snapshot_done
ok=True
skipped=False
rows_written=27
run_id=cd994ed6-44d0-41a4-b091-9459f527f184
```

The +1 `mirror_ticker_count` (14 → 15) and +1 `scanner_matched`
(14 → 15) reflect a Mirror-side change picked up by the regular
T212 sync between the two scheduled fires — not driven by this
audit.

---

## 4. Persistence — read-only DB audit

Counts captured by a transient one-shot Cloud Run Job (`quant-ops-audit-rowcounts`, created, executed, **deleted after success**, no source files committed).

| Table | Count | Note |
|---|---|---|
| `market_brief_run` (total) | **5** | |
| `market_brief_run` source='overnight' | **4** | 2 scheduled auto-runs + 2 prior manual validations |
| `market_brief_run` source='interactive' | 1 | one interactive request between the validation rounds |
| `market_brief_candidate_snapshot` (total) | **122** | |
| `scanner_run` | 2 | unrelated to brief; from earlier scanner calls |
| `scanner_candidate_snapshot` | 29 | |
| `instrument` | 43 | unchanged since mirror bootstrap (+7 over 36 baseline) |
| `instrument_identifier` (total) | 59 | |
| `ticker_history` | 43 | |
| `price_bar_raw` | 13404 | **unchanged by the brief Job** ✓ |
| `broker_position_snapshot` | 123 | **unchanged by the brief Job** ✓ |
| `broker_order_snapshot` | 2350 | **unchanged by the brief Job** ✓ |
| `broker_account_snapshot` | 47 | **unchanged by the brief Job** ✓ |
| **`order_intent`** | **`0`** | ✓ |
| **`order_draft`** | **`0`** | ✓ |

**Latest 5 `market_brief_run` rows (read-only `SELECT`, no mutations):**

```
run_id=cd994ed6-44d0-41a4-b091-9459f527f184  source=overnight    ticker_count=26 generated_at=2026-05-12T06:30:30Z news=ok                   <- 2nd auto
run_id=a95ceb37-9fba-49af-bd49-771f2832f4a0  source=overnight    ticker_count=24 generated_at=2026-05-11T06:30:24Z news=ok                   <- 1st auto
run_id=0c5be84f-0fa3-48cd-acdb-c4662e64225f  source=overnight    ticker_count=24 generated_at=2026-05-11T03:22:36Z news=ok                   (prior manual validation)
run_id=dd1efecf-10f7-4f5a-a8dd-7db09b561fe1  source=interactive  ticker_count=24 generated_at=2026-05-11T02:36:05Z news=ok                   (interactive request)
run_id=3685a390-ce5f-4204-908f-4a89ec6f869a  source=overnight    ticker_count=24 generated_at=2026-05-10T02:58:31Z news=rate_limited_cached  (mega-push validation)
```

Candidate-count per run:

| run_id | candidate_count |
|---|---|
| `cd994ed6-44d0-41a4-b091-9459f527f184` (2nd auto) | **26** |
| `a95ceb37-9fba-49af-bd49-771f2832f4a0` (1st auto) | **24** |
| `0c5be84f-0fa3-48cd-acdb-c4662e64225f` | 24 |
| `dd1efecf-10f7-4f5a-a8dd-7db09b561fe1` | 24 |
| `3685a390-ce5f-4204-908f-4a89ec6f869a` | 24 |

---

## 5. API surface (read-only HTTP probe)

Cloud Run revision: `quant-api-00052-t5j` (unchanged this run).

| Endpoint | Unauth result |
|---|---|
| `/api/health` | `{"status":"ok","service":"quant-api-platform","version":"0.1.0"}` |
| `/api/market-brief/latest` | `HTTP 401` (auth-gated; correct) |
| `/api/market-brief/history` | `HTTP 401` (correct) |
| `/api/market-brief/cd994ed6-…` (2nd auto run_id) | `HTTP 401` (route registered; reachable when authenticated) |

---

## 6. Side-effect attestations (this validation audit)

| Property | Status |
|---|---|
| `FEATURE_T212_LIVE_SUBMIT` (Cloud Run revision env) | `false` ✓ |
| `order_intent` rows | **0** ✓ |
| `order_draft` rows | **0** ✓ |
| `broker_*` tables unchanged by brief Job | ✓ |
| `price_bar_raw` unchanged by brief Job | ✓ |
| T212 endpoint write | NONE ✓ |
| T212 / EOD scheduler changes this audit | NONE ✓ |
| `quant-market-brief-overnight-schedule` mutation this audit | NONE ✓ |
| Cloud Run service deploy this audit | NONE (revision still `quant-api-00052-t5j`) ✓ |
| Migration this audit | NONE ✓ |
| Sync job execution triggered this audit | NONE ✓ |
| Transient one-shot audit Job | created + deleted in-run; no persistent footprint |
| Secrets in any log line surfaced | NONE — DB URL appears as `quantuser:***@…`, no API keys / Bearer tokens / private key blocks |
| `.firebase` cache committed | NO |

---

## 7. Decision

| Question | Answer |
|---|---|
| Did the scheduler successfully auto-generate the brief? | **YES — both auto-fires landed exit 0 with snapshot persisted.** |
| Auto-run #1 run_id | `a95ceb37-9fba-49af-bd49-771f2832f4a0` (25 rows: 1 run + 24 candidates) |
| Auto-run #2 run_id | `cd994ed6-44d0-41a4-b091-9459f527f184` (27 rows: 1 run + 26 candidates) |
| Should the scheduler be paused? | **NO.** All attestations green; isolation contract holds. |
| Can it stay ENABLED? | **YES — recommended.** Next fire `2026-05-13T06:30:04Z`. |
| Rollback command (one line) | `gcloud scheduler jobs pause quant-market-brief-overnight-schedule --location=asia-east2` |
