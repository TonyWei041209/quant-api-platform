# Mirror Bootstrap — Execution Plan (2026-05-10 run)

**Run reference:** Overnight Continuation Push run B
**Operator:** automated agent (Claude)
**Authorization recorded in:** session prompt allowing mirror
instrument bootstrap production write under strict allowlist.

This is the **execution evidence** document for the 2026-05-10
mirror-bootstrap production write. The procedure is the one
already documented in
`docs/mirror-bootstrap-allowlist-report.md` §8 — this doc records
the actual numbers + commands.

---

## 1. Dry-run plan (captured before the write)

Source: one-shot Cloud Run Job
`quant-ops-mirror-bootstrap-dryrun-rlkbb`, image
`sha256:c85b38025c27...`, executed `2026-05-11T03:12:12Z` UTC,
exit 0. Job deleted after success.

| | Count |
|---|---|
| Total Mirror tickers | 14 |
| Already mapped | 4 |
| Unmapped (no provider info attempted) | 0 |
| **NEWLY_RESOLVABLE** | **7** |
| Unresolved (no FMP profile) | 3 |
| Ambiguous | 0 |
| Protected (NVDA/AAPL/MSFT/SPY family) excluded | 1 |

## 2. Allowlist for production write

Only the seven `newly_resolvable` tickers below will be written.
Every row has a complete FMP profile (company_name + exchange +
currency + asset_type implied EQUITY):

| Ticker | Company | Exchange | Currency | Source tags |
|---|---|---|---|---|
| `NOK` | Nokia Oyj | NYSE | USD | HELD, RECENTLY_TRADED, UNMAPPED |
| `AAOI` | Applied Optoelectronics, Inc. | NASDAQ | USD | RECENTLY_TRADED, UNMAPPED |
| `ORCL` | Oracle Corporation | NYSE | USD | RECENTLY_TRADED, UNMAPPED |
| `VACQ` | Vector Acquisition Corporation | NASDAQ | USD | RECENTLY_TRADED, UNMAPPED |
| `CRWV` | CoreWeave, Inc. Class A | NASDAQ | USD | RECENTLY_TRADED, UNMAPPED |
| `CRCL` | Circle Internet Group | NYSE | USD | RECENTLY_TRADED, UNMAPPED |
| `TEM` | Tempus AI, Inc. | NASDAQ | USD | RECENTLY_TRADED, UNMAPPED |

## 3. Explicitly excluded

| Ticker | Why |
|---|---|
| `SNDK1` | `unresolved` — FMP returned no profile. Numbered-suffix variant of SNDK; symbol ambiguity not resolved this round. **Deferred.** |
| `IPOE` | `unresolved` — historical SPAC ticker, no FMP profile. **Deferred.** |
| `OAC` | `unresolved` — historical SPAC ticker, no FMP profile. **Deferred.** |
| (protected) | `NVDA/AAPL/MSFT/SPY` filter (hard-coded `PROTECTED_TICKERS`) — never overwritten by a mirror bootstrap. |

## 4. Tables that will be written

For each of the 7 allowlist tickers:

| Table | Rows | Columns populated |
|---|---|---|
| `instrument` | 1 | instrument_id (new UUID), asset_type='EQUITY', issuer_name_current, exchange_primary, currency, country_code, is_active=true |
| `instrument_identifier` | 1 | instrument_id, id_type='ticker', id_value=<TICKER>, source='mirror_bootstrap', valid_from='2020-01-01', valid_to=NULL, is_primary=true |
| `ticker_history` | 1 | instrument_id, ticker=<TICKER>, effective_from='2020-01-01', issuer_name, exchange, effective_to=NULL, source='mirror_bootstrap' |

Expected total deltas: **+7 instrument**, **+7 instrument_identifier**,
**+7 ticker_history**.

## 5. Tables explicitly NOT touched

| Table | Status |
|---|---|
| `price_bar_raw` | **NOT written** — the bootstrap module's table allowlist hard-excludes this; no EOD bars are seeded. |
| `corporate_action` | not written |
| `earnings_event` | not written |
| `financial_*` | not written |
| `watchlist_*` | not written |
| `broker_account_snapshot` | not written |
| `broker_position_snapshot` | not written |
| `broker_order_snapshot` | not written |
| `order_intent` | not created |
| `order_draft` | not created |
| `backtest_run`, `backtest_trade` | not written |

## 6. Pre-flight backup

Captured before the production write (see §7). Backup ID + status
recorded below in the run-log section.

## 7. Production write — actual run

**Pre-flight backup**

| | Value |
|---|---|
| Backup ID | **`1778469239212`** |
| Description | `pre-mirror-bootstrap-20260511-0313` |
| Start | `2026-05-11T03:13:59.262Z` |
| End | `2026-05-11T03:15:20.398Z` |
| Status | **`SUCCESSFUL`** |

**Cloud Run Write Job**

| | Value |
|---|---|
| Job name | `quant-ops-mirror-bootstrap-write` (created + deleted in-run) |
| Image | `sha256:c85b38025c27...` (current API revision image) |
| Command | `python -m apps.cli.main bootstrap-mirror-instruments --no-dry-run --write --db-target=production --confirm-production-write --fetch-profiles --lookback-days=7` |
| Env | `APP_ENV=production`, `FEATURE_T212_LIVE_SUBMIT=false`, `DB_TARGET_OVERRIDE=production`, `PYTHONPATH=/app` |
| Cloud SQL annotation | `secret-medium-491502-n8:asia-east2:quant-api-db` |
| Execution name | `quant-ops-mirror-bootstrap-write-z7ht4` |
| Exit code | `0` |
| Runtime | 12.0 s |

**Bootstrap result block (verbatim summary)**

```
requested_count               : 7
target_count                  : 7
succeeded                     : 7
skipped (already existed)     : 0
failed                        : 0
instruments_inserted          : 7
identifiers_inserted          : 7
ticker_histories_inserted     : 7
db_target                     : production
db_url_label                  : postgresql+psycopg2://quantuser:***@34.150.76.29:5432/quantdb
                                (via DB_TARGET_OVERRIDE=production)
Side-effect attestations:
  DB writes performed: instrument + instrument_identifier + ticker_history only (PRODUCTION Cloud SQL)
  Cloud Run jobs created: NONE
  Scheduler changes: NONE
  Production deploy: NONE
  Execution objects: NONE
  Broker write: NONE
  Live submit: LOCKED (FEATURE_T212_LIVE_SUBMIT=false)
```

## 8. Verification

Re-run dry-run via `quant-ops-mirror-verify-jcdrr` after the write:

| Metric | Pre-write | Post-write | Delta |
|---|---|---|---|
| Mirror tickers (total) | 14 | 14 | 0 |
| `mapped` | **4** | **11** | **+7** |
| `unmapped` | 0 | 0 | 0 |
| `newly_resolvable` | **7** | **0** | **-7** |
| `unresolved` | 3 | 3 | 0 (correctly deferred) |
| `ambiguous` | 0 | 0 | 0 |
| `protected_excluded` | 1 | 1 | 0 |

Each of the 7 written tickers (`NOK`, `AAOI`, `ORCL`, `VACQ`,
`CRWV`, `CRCL`, `TEM`) now classifies as `mapped` with the
`[existing]` annotation — confirms the rows landed in
`instrument_identifier`. The three deferred unresolved tickers
(`SNDK1`, `IPOE`, `OAC`) are unchanged.

**Implied row deltas in production DB** (from the bootstrap result):

| Table | Delta |
|---|---|
| `instrument` | **+7** |
| `instrument_identifier` (source='mirror_bootstrap') | **+7** |
| `ticker_history` (source='mirror_bootstrap') | **+7** |
| `price_bar_raw` | **0** (excluded by module) |
| `broker_position_snapshot` | **0** (not in module's write set) |
| `broker_order_snapshot` | **0** |
| `broker_account_snapshot` | **0** |
| `order_intent` | **0** |
| `order_draft` | **0** |
| `watchlist_*` | **0** |
| `corporate_action` | **0** |
| `earnings_event` | **0** |

The dry-run job (`quant-ops-mirror-bootstrap-dryrun-rlkbb`), the
write job (`quant-ops-mirror-bootstrap-write-z7ht4`), and the
verify job (`quant-ops-mirror-verify-jcdrr`) were all deleted
after completion. No persistent one-shot Job artifact remains in
the asia-east2 Cloud Run Jobs list.

## 9. Rollback (if ever needed)

Inverse of §4, scoped to `source='mirror_bootstrap'`. See
`docs/mirror-bootstrap-allowlist-report.md` §6 for the canonical
DELETE statements.

## 10. Side-effect attestations (this doc)

| | Status |
|---|---|
| Production DB write | LIMITED to the 7-ticker allowlist (§2) across the 3 tables (§4) |
| Cloud SQL backup taken | YES — recorded in §7 |
| Cloud Run write Job created | YES — recorded in §7 (deleted after success) |
| Production migration | NONE (no schema change in this run) |
| Production sync execution | NONE for this phase |
| Scheduler change | NONE for this phase |
| Trading 212 write | NONE |
| Live submit | LOCKED (`FEATURE_T212_LIVE_SUBMIT=false`) |
| order_intent / order_draft created | NONE |
| `.firebase` cache committed | NO |
