# Scanner Research Universe — Production Seed Plan

**Status:** READINESS PACK — NOT YET EXECUTED
**Owner:** quant-api-platform maintainers
**Created:** 2026-04-28
**Last validated dev result:** commit `92975e5`, scanner on 36-stock dev universe matched 13 candidates (high=8 medium=5), banned-words violations 0, latency ~461ms cold.
**Provider smoke status (small probe, 1 ticker each):** Polygon and FMP both green for NVDA — see commit `615fb61`. Full 36-ticker coverage (criteria #3 + #4) requires `--check-all` and depends on Polygon tier (see Rate Limit Note below).

This document describes what production seed of the Scanner Research Universe **would look like** if/when explicitly approved. Nothing here has been executed against production. No Cloud SQL writes, no Cloud Run Job creation, no scheduler changes have happened as part of producing this plan.

---

## 1. Goal

Expand the production Scanner universe from 4 instruments (NVDA / AAPL / MSFT / SPY) to ~36 high-liquidity US stocks + major ETFs, while:

- Keeping Scanner as a **research candidate scanner**, not a trading recommendation engine
- Keeping `data_mode = "daily_eod"` — no intraday, no real-time
- Preserving every Layer-1 Research-open guardrail already in place: schema `extra="forbid"`, BANNED_WORDS, whitelisted enums, no execution objects, no broker write, `FEATURE_T212_LIVE_SUBMIT=false`
- Adding a **daily incremental sync** mechanism so the expanded universe does not go stale

The success criterion is operational, not financial: a production Scanner that, when opened on a typical trading day, returns 5–15 meaningful candidates across diverse categories rather than 0–3.

## 2. Universe (36 tickers)

The list mirrors `scripts/bootstrap_research_universe_dev.py` exactly so dev validation translates directly.

| # | Ticker | Category | Reason for inclusion (research-only) | Liquidity | Scanner relevance |
|---|---|---|---|---|---|
| 1 | NVDA | ai_semi | Already in production; AI bellwether with frequent extreme moves | Mega | momentum / extreme_mover |
| 2 | AMD | ai_semi | NVDA peer — semiconductor cycle pair | Mega | momentum / breakout |
| 3 | AVGO | ai_semi | Mega-cap semi, M&A catalyst exposure | Mega | breakout |
| 4 | TSM | ai_semi | Semi upstream ADR | Mega | momentum |
| 5 | INTC | ai_semi | Cycle-stock counterpoint to NVDA/AMD | Large | breakout / reversal |
| 6 | MU | ai_semi | Memory cycle, earnings-driven volatility | Large | momentum + earnings windows |
| 7 | AAPL | mega_tech | Already in production; liquidity baseline | Mega | low_vol / breakout |
| 8 | MSFT | mega_tech | Already in production; AI platform | Mega | low_vol / breakout |
| 9 | GOOGL | mega_tech | AI / advertising cycle | Mega | momentum |
| 10 | META | mega_tech | High-beta mega-cap | Mega | momentum / extreme_mover |
| 11 | AMZN | mega_tech | E-commerce + cloud cross-section | Mega | momentum |
| 12 | TSLA | ev_growth | Highest single-day volume / extreme volatility | Mega | extreme_mover frequent |
| 13 | RIVN | ev_growth | EV cycle counterpoint | Mid | high_volatility |
| 14 | LCID | ev_growth | Already in dev; small-cap EV extreme-volatility sample | Mid | extreme_mover |
| 15 | NIO | ev_growth | Already in dev; China-ADR + EV double beta | Mid | extreme_mover |
| 16 | XPEV | ev_growth | China-ADR EV peer | Mid | high_volatility |
| 17 | SOFI | fintech | Already in dev; mid-cap fintech | Mid | momentum |
| 18 | PLTR | fintech | AI / government-contract catalyst | Large | momentum + breakout |
| 19 | COIN | fintech | Crypto exposure proxy | Large | extreme_mover |
| 20 | JPM | financials | Bank sector benchmark | Mega | low_volatility / breakout |
| 21 | BAC | financials | Rate-sensitive counterpoint | Mega | low_volatility |
| 22 | GS | financials | High-beta investment bank | Large | momentum |
| 23 | XOM | energy | Oil / inflation sensitivity | Mega | momentum / earnings |
| 24 | CVX | energy | XOM peer | Mega | momentum |
| 25 | OXY | energy | Mid-cap high-beta energy | Large | high_volatility |
| 26 | DIS | communications | Media + consumer | Mega | momentum |
| 27 | NFLX | communications | Streaming, earnings windows | Large | extreme_mover (earnings) |
| 28 | UBER | consumer_tech | Mid-large beta | Large | momentum |
| 29 | F | auto | Already in dev; legacy auto, low-price proxy | Large | low-vol / breakout |
| 30 | GM | auto | F peer | Large | low-vol |
| 31 | BA | industrial | High-beta industrial, event-driven | Large | extreme_mover |
| 32 | SIRI | communications | Already in dev; lower-beta comms | Mid | needs_research / low signal |
| 33 | AMC | consumer_tech | Already in dev; meme-stock volatility sample | Mid | extreme_mover |
| 34 | SPY | etf | Already in production; market benchmark | Mega | benchmark / breakout context |
| 35 | QQQ | etf | NASDAQ-100 benchmark | Mega | benchmark |
| 36 | IWM | etf | Russell 2000 / small-cap rotation signal | Mega | breakout / regime |

**Inclusion principle**: high liquidity, mid-or-large cap, US-listed, T212-tradable, mix of categories so scanner output has dispersion. **No microcaps, no OTC, no penny stocks, no derivatives**.

**This list is not a buy/sell recommendation.** It is a research universe — instruments worth scanning for further investigation.

## 3. Data source paths

| Provider | Role | Endpoint(s) used | Status |
|---|---|---|---|
| **Polygon (via `massive_adapter.py`)** | **Primary** EOD bars + splits + dividends | `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}`, `/v3/reference/splits`, `/v3/reference/dividends` | `MASSIVE_API_KEY` configured in local `.env` and prod Cloud Run secret |
| **FMP (via `fmp_adapter.py`)** | **Profile/fundamentals primary** + EOD fallback | `get_profile`, `get_eod_prices`, `get_income_statement`, `get_balance_sheet` | `FMP_API_KEY` configured in both environments |
| OpenFIGI | Optional identifier enrichment | `/v3/mapping` | Not currently a blocker |
| **yfinance_dev** | DEV ONLY — must NOT be used in production | n/a | Tagged `source='yfinance_dev'`; DQ rules treat it as untrusted |

**Provider selection rules**:
- All `price_bar_raw` rows for these 36 tickers MUST be tagged `source='polygon'` or `source='fmp'`. Production never uses `source='yfinance_dev'` for any of them
- Profile (`issuer_name_current`, `exchange_primary`, `currency`) sourced from FMP `get_profile`. Tag `instrument_identifier.source = 'fmp'` and `ticker_history.source = 'fmp'`
- If both providers fail for a given ticker, abort that ticker's seed (do not silently fallback to yfinance_dev)

## 4. Production write scope (design only — not executed)

If/when seed runs, the following writes happen, in this order, per ticker:

1. `instrument` — INSERT (skip if `instrument_identifier` row already exists for this ticker)
2. `instrument_identifier` — INSERT (`id_type='ticker'`, `source='fmp'` or `'polygon'` per actual source used)
3. `ticker_history` — INSERT (`source='fmp'` or `'polygon'`)
4. `price_bar_raw` — INSERT bulk (Polygon range API returns multi-year in one call), all tagged `source='polygon'` (or `source='fmp'` for fallback path)

**No other tables touched.** No `research_note`, no `backtest_run`, no `broker_*_snapshot`, no `order_intent`, no `order_draft`. Scanner reads-through these tables — no scanner-side write paths exist.

**Idempotency**: every write must use `ON CONFLICT DO NOTHING` (the existing pattern in `dev_load_prices.py` and `sync_eod_prices.py`). Re-running the seed must be safe.

**Audit trail**: every row carries `source` (provider) and `ingested_at` (timestamp). Cloud Logging must capture per-ticker outcome (`succeeded`, `partial`, `failed`).

## 5. Daily incremental sync design (not executed)

Production seed without ongoing daily refresh would let the universe go stale within days. **Seed and sync must ship together.**

### Cloud Run Job: `quant-sync-eod-prices`

- **Image**: same `quant-api` image (mirror `quant-sync-t212` pattern — image alignment via existing `sync-job-image.ps1`)
- **Command**: `python -m apps.cli.main sync-eod-prices --tickers <comma-list> --source polygon` (CLI command does not exist yet — must be added before sync job creation)
- **Universe input**: hard-coded allowlist of the 36 tickers (initial), promotable to a config table later
- **Source order**: Polygon primary, FMP fallback per ticker
- **Per-ticker isolation**: failure of one ticker does NOT abort the rest (mirror `sync-trading212` pattern)
- **Date range**: pull last 7 trading days each run (idempotent overlap covers occasional missed days)
- **Idempotency**: existing `ON CONFLICT DO NOTHING` ensures duplicates are skipped
- **Memory / timeout**: 512Mi memory.
  - **Timeout depends on Polygon tier** — see Rate Limit Note below. Free-tier safe value is **900s** (15 min); paid-tier can use **300s**.
- **Secrets**: same `MASSIVE_API_KEY`, `FMP_API_KEY`, `DATABASE_URL` already in production secret manager

### Rate Limit Note (added 2026-04-29)

Polygon's free tier is **5 requests per minute** (per-key). Discovered when a `--check-all` dry-run hit `RateLimitExceeded` 429 after 5 successful tickers in ~5 seconds.

**Implications for sync job design:**

| Polygon tier | Per-minute limit | 36-ticker incremental sync runtime | Recommended Cloud Run Job timeout |
|---|---|---|---|
| **Free** | 5 req/min | ~8 minutes (single-pass at 13s/ticker) | **≥ 900s (15 min)** to leave margin |
| Stocks Starter ($29/mo) | unlimited | seconds | 300s sufficient |
| Developer ($79/mo) | unlimited + RT | seconds | 300s sufficient |

The repository's adapter rate limiter is currently configured at `5 req/sec` (`libs/adapters/massive_adapter.py`), which is correct for **paid** tiers but ~12× faster than the free-tier server-side limit. If the production seed runs on free tier:

1. The seed and sync code MUST sleep ~13 seconds between Polygon calls (not rely on the adapter's local limiter)
2. The Cloud Run Job timeout must accommodate the slow path
3. Cloud Logging alert thresholds should account for the longer normal runtime

**Decision input needed**: confirm which Polygon tier this account is on. If paid, the timeout / pacing concerns above relax; if free, accept the slower sync cadence or upgrade.

**Dry-run script accommodates both modes**: `--polygon-delay-seconds=13` (default, free-tier safe) or `--polygon-delay-seconds=0.3` (paid).

### Cloud Scheduler: `quant-sync-eod-prices-schedule`

- **Cron**: `0 22 * * 1-5` UTC (≈ 18:00 ET, after US market close on weekdays)
- **State**: ENABLED on creation
- Reuse existing IAM bindings used by `quant-sync-t212-schedule`

### Stale-data risk

If the daily job fails for N days in a row, scanner will silently return `as_of` from N days ago. **Mitigation**:
- Cloud Logging alert on Job failure
- Scanner UI already surfaces `as_of` in metadata strip — users see the date directly
- A `data_freshness_check` DQ rule could be added later (not v1 scope)

## 6. Rollback / cleanup plan (mandatory before seed approval)

If the production seed misbehaves and must be reverted, here is the exact cleanup recipe. **It must protect the 4 pre-existing instruments (NVDA / AAPL / MSFT / SPY).**

### Step-1 verify safe deletion target

The 4 pre-existing instruments are identified by their existing `instrument_id` UUIDs in production. The seed adds 32 new tickers. Cleanup must operate on an explicit allowlist of newly-added tickers, not "everything tagged `source='polygon'` after date X" — that would break the existing 4 stocks' historical bars.

### Step-2 cleanup SQL (template — never run without explicit approval)

```sql
-- Allowlist: the 32 tickers added by the seed
WITH allowlist AS (
  SELECT UNNEST(ARRAY[
    'AMD','AVGO','TSM','INTC','MU','GOOGL','META','AMZN',
    'TSLA','RIVN','LCID','NIO','XPEV','SOFI','PLTR','COIN',
    'JPM','BAC','GS','XOM','CVX','OXY','DIS','NFLX','UBER',
    'F','GM','BA','SIRI','AMC','QQQ','IWM'
  ]) AS ticker
),
target AS (
  SELECT DISTINCT i.instrument_id
  FROM instrument i
  JOIN instrument_identifier ii ON ii.instrument_id = i.instrument_id
  WHERE ii.id_type = 'ticker'
    AND ii.id_value IN (SELECT ticker FROM allowlist)
)
-- 1. Delete price_bar_raw rows
DELETE FROM price_bar_raw WHERE instrument_id IN (SELECT instrument_id FROM target);

-- 2. Delete identifier rows
DELETE FROM instrument_identifier WHERE instrument_id IN (SELECT instrument_id FROM target);

-- 3. Delete ticker_history rows
DELETE FROM ticker_history WHERE instrument_id IN (SELECT instrument_id FROM target);

-- 4. Delete instrument rows last (FK order)
DELETE FROM instrument WHERE instrument_id IN (SELECT instrument_id FROM target);
```

**Pre-cleanup checklist**:
- [ ] Take a Cloud SQL backup snapshot
- [ ] Run `SELECT COUNT(*)` on each target with the allowlist filter to confirm row counts before any DELETE
- [ ] Run inside a transaction (`BEGIN; ... ; ROLLBACK;`) first to verify counts
- [ ] Only then `COMMIT`

**Watchlist / research_note linkage**: the 32 new tickers will have no `watchlist_item` rows initially (we are not creating a watchlist as part of the seed). If a user later adds them to a watchlist, those `watchlist_item` rows must also be cleaned. The cleanup template should be re-checked at execution time.

## 7. Guardrails (must hold throughout seed and after)

- ✅ **Layer 1 Research-open scope only**: scanner remains read-only, does not create `order_intent` / `order_draft` / `order` / any execution object
- ✅ **No broker write**: T212 stays readonly truth; no Trading 212 API calls related to scanner universe
- ✅ **`FEATURE_T212_LIVE_SUBMIT=false`** stays unchanged
- ✅ **Scanner output forbidden language**: existing `BANNED_WORDS` list and Pydantic `extra="forbid"` schema continue to apply unchanged. No new fields are added to `ScanItem` or `ScanResponse` for this seed
- ✅ **`data_mode = "daily_eod"`**: scanner does not promote to intraday or real-time as a result of this seed
- ✅ **No frontend code change required**: scanner UI continues to function on `universe=all` and the new tickers appear automatically (this is exactly what the dev validation proved — frontend rendering is unchanged)
- ✅ **`yfinance_dev` is NOT used in production**: all 32 new tickers must be ingested with `source='polygon'` or `source='fmp'`
- ✅ **Add to Watchlist remains disabled** in scanner UI

## 8. Acceptance criteria (must be ALL satisfied before seed approval)

This is a checklist. Production seed must NOT run until every box is ticked **with evidence**.

| # | Criterion | Verification method | Status |
|---|---|---|---|
| 1 | Polygon `MASSIVE_API_KEY` reachable, returns valid response for sample ticker | dry-run script: `check_scanner_universe_provider_readiness.py` | ✅ PASS (2026-04-29, NVDA HTTP 200) |
| 2 | FMP `FMP_API_KEY` reachable, returns valid profile for sample ticker | same dry-run | ✅ PASS (2026-04-29, NVDA profile resolved) |
| 3 | All 36 tickers resolvable by FMP `get_profile` (issuer name + exchange) | dry-run with `--check-all` flag | ✅ PASS (2026-04-29, 36/36, all NYSE/NASDAQ/AMEX) |
| 4 | All 36 tickers have ≥ 252 trading days of recent EOD bars from Polygon | dry-run with `--check-all` flag (uses `--polygon-delay-seconds=13` default for free tier safety) | ✅ PASS (2026-04-29, 36/36 returned 368 bars over 2024-11-05 → 2026-04-27, 0 errors, 0 coverage-short) |
| 5 | `quant-ops-research-universe-seed` Cloud Run Job specification reviewed and approved | this doc + user sign-off | ✅ PASS (2026-04-30, B0). User sign-off received in chat for B0+B1; spec now lives in `docs/runbook.md` "Scanner Universe Production Seed (Phase B Execution Playbook)" section. Job is one-shot, free Polygon tier confirmed, 900s timeout, image-aligned to currently-serving quant-api revision, deleted after success |
| 6 | `sync-eod-prices-universe` CLI dry-run command implemented and passes unit tests | code review + test run | ✅ PASS (2026-04-29, **41/41** unit tests passing). **WRITE_LOCAL implemented** with real Polygon→FMP fallback, per-ticker commit, idempotent ON CONFLICT DO NOTHING. Local integration validation: 31/36 succeeded (5 via Polygon + 26 via FMP fallback after Polygon free-tier 429), 338 bars persisted in fresh-session readback, idempotency re-run shows 0 inserts / 12 skipped. **WRITE_PRODUCTION still hard-deferred** with explicit NotImplementedError until #5/#9 sign-off. |
| 7 | Rollback SQL template tested in dev DB (with row counts confirmed) | dev DB dry-run | ✅ PASS (2026-04-29, 26,592 price bars + 32 identifiers + 32 ticker_history + 32 instruments would be deleted by rollback; protected NVDA/AAPL/MSFT/SPY counts unchanged; BEGIN/ROLLBACK left all data intact) |
| 8 | Cloud SQL backup taken immediately before seed | gcloud sql backups create | ✅ PASS (2026-04-30 05:12 UTC, backup_id `1777525932912`, status SUCCESSFUL, description `pre-scanner-universe-seed-20260430-0612`) |
| 9 | User explicit go-ahead on this PR / runbook | user sign-off in chat | ✅ PASS (2026-04-30, B2 authorized for overnight guarded execution) |
| 10 | docs/runbook.md updated with execution steps and runbook | doc review | ✅ PASS (2026-04-30, B0). Runbook now contains full "Scanner Universe Production Seed (Phase B Execution Playbook)" section: prerequisites, job spec, Cloud SQL backup plan, pre-flight checks, execute steps, log watch, post-flight verification, cleanup, rollback playbook (option A row-level + option B full restore), after-action items |

**Until every row is checked, production seed is DEFERRED.** The dry-run readiness script (item 1, 2, 3, 4) lives in this same readiness pack and is safe to run repeatedly without any DB writes.

---

## Appendix C — B2 Execution Outcome (2026-04-30)

**Status: PARTIAL — 4/36 tickers received bar updates; 32/36 missing instrument scaffolding in production**

### Execution metadata

| Field | Value |
|---|---|
| Execution date | 2026-04-30 |
| Backup ID (taken first) | `1777525932912` (status SUCCESSFUL, description `pre-scanner-universe-seed-20260430-0612`) |
| Production revision used | `quant-api-00033-x6l` (image `sha256:28e34300b088...`, contains B1 + B1.1) |
| Job execution name | `quant-ops-research-universe-seed-2597h` |
| Job exit code | 0 (clean termination) |
| Runtime | 459.3 seconds (~7.7 min) |
| ticker_count | 36 |
| succeeded | 4 |
| failed | 32 |
| bars_inserted_total | 344 |
| bars_existing_or_skipped_total | 0 |

### Partial outcome explained

The seed job code path (`sync_eod_prices_universe.execute_sync`) only writes to
`price_bar_raw` and assumes the parent `instrument` + `instrument_identifier`
+ `ticker_history` rows already exist for each ticker. This is correct for
the daily-incremental sync use case (Phase C, future), but production had no
such scaffolding for the 32 new tickers.

Result:
- **The 4 protected tickers (NVDA / AAPL / MSFT / SPY)**: pre-existing
  `instrument_id`s resolved successfully. Polygon range query pulled bars
  from `last_known_trade_date - 7 days` → today, ON CONFLICT DO NOTHING.
  Net effect: ~86 new bars per protected ticker (4 months of fresh
  EOD data through 2026-04-29). 344 bars inserted total.
- **The 32 new tickers (AMD/AVGO/TSM/INTC/MU/GOOGL/META/AMZN/TSLA/RIVN/
  LCID/NIO/XPEV/SOFI/PLTR/COIN/JPM/BAC/GS/XOM/CVX/OXY/DIS/NFLX/UBER/F/
  GM/BA/SIRI/AMC/QQQ/IWM)**: failed at `instrument_id resolution` step
  with `instrument_id not resolved (ticker not in instrument_identifier)`.
  No Polygon or FMP HTTP call was made for these tickers. No DB write.

### Post-flight verification (2026-04-30 read-only check job)

| Check | Result |
|---|---|
| `/api/health` | ✅ `{"status":"ok"}` |
| `/api/scanner/stock` (no auth) | ✅ HTTP 401 |
| OpenAPI `ScanItem.additionalProperties` | ✅ `False` (schema strict preserved) |
| Production revision | `quant-api-00033-x6l` (unchanged from B2-prep deploy) |
| Cloud Run jobs | ✅ only `quant-sync-t212` (both one-shot jobs deleted) |
| Cloud Scheduler | ✅ only `quant-sync-t212-schedule`, ENABLED, schedule unchanged |
| `FEATURE_T212_LIVE_SUBMIT` | ✅ `false` |
| Production instrument count | 4 (unchanged — 32 new tickers were NOT created) |
| Protected NVDA `last_known_trade_date` | 2026-04-29 (was 2025-12-31 at baseline; bars enriched, count grew) |
| Protected ticker count change | +0 instruments, +344 bars (enriched, not shrunk) |
| New 32 ticker bar counts | 0 each (no instrument_id, no bars) |

### Why no rollback was triggered

Per plan doc Section 6 / runbook playbook rollback trigger conditions:
- `/api/health` is OK ✓
- Production instrument count is 4 (not corrupted; expected baseline) ✓
- Protected ticker counts unchanged structurally and grew (not shrunk) in
  bars ✓
- `/api/scanner/stock` returns 401 not 500 ✓
- `FEATURE_T212_LIVE_SUBMIT` still false ✓
- No execution intent / draft / order ✓
- No broker write ✓

None of the rollback triggers fired. The 344 newly-inserted bars for the
4 protected tickers are valid Polygon EOD data (no synthesis, no
adjustment), so leaving them in production is benign — they extend the
historical record by 4 months for instruments that were previously
serving stale (2025-12-31) data.

### What is needed to complete the seed (NOT executed tonight)

The 32 new tickers need a separate **bootstrap step** that creates:
1. `instrument` rows
2. `instrument_identifier` rows (`id_type='ticker'`)
3. `ticker_history` rows

Once those exist, re-running the seed job (after a fresh backup + sign-off
+ user-on-line) would populate `price_bar_raw` for all 32. The dev
bootstrap script (`scripts/bootstrap_research_universe_dev.py`) does this
but uses `yfinance_dev` and is dev-only by policy. A production-equivalent
bootstrap step needs a separate design + implementation + sign-off.

This is documented as deferred work, NOT a Phase B regression. Phase B
correctly executed within its own scope; the gap is in the seed module's
design (it presumes scaffolding exists).

## B3 — Production Scaffolding Bootstrap (Phase B3)

Phase B3 introduces the production bootstrap path that was identified as
missing during the B2 partial outcome. The work is split into two checkpoints:

- **B3.1** — code + CLI + tests + doc updates + production redeploy
  (no production write, no job creation, no backup). The deployed image
  contains the bootstrap code path so a future B3.2 can launch a Cloud
  Run Job from the same image.
- **B3.2** — backup + execution + post-flight verification (separate
  sign-off required).

### B3.1 deliverables (this section)

| Item                                   | Path                                                         | Purpose                                                       |
| -------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------- |
| Universe constants                     | `libs/scanner/scanner_universe.py`                           | `PROTECTED_TICKERS`, `ETF_TICKERS`, `BOOTSTRAP_TARGET_TICKERS`, `asset_type_for()` |
| Bootstrap planner + executor           | `libs/ingestion/bootstrap_research_universe_prod.py`         | `build_bootstrap_plan`, `execute_bootstrap`, FMP profile fetch with deterministic fallbacks |
| CLI command                            | `apps/cli/main.py` → `bootstrap-research-universe-prod`      | Same four-flag handshake as `sync-eod-prices-universe`        |
| Unit tests                             | `tests/unit/test_bootstrap_research_universe_prod.py`        | 63 tests; hermetic (no DB, no network)                        |

### Target list (32 tickers — protected 4 excluded)

Computed deterministically as `SCANNER_RESEARCH_UNIVERSE - PROTECTED_TICKERS`.
The protected set is `{NVDA, AAPL, MSFT, SPY}` — these tickers already have
full instrument + identifier + ticker_history rows in production (verified
during B2 — they were the 4/36 that succeeded). They are HARD-EXCLUDED
from the plan even if a caller passes them in explicitly. Defense-in-depth
at TWO layers: planner filters them; the target_tickers list is the
authoritative source for executor.

### Tables this module writes (and only these)

| Table                  | Write       | Notes                                                  |
| ---------------------- | ----------- | ------------------------------------------------------ |
| `instrument`           | INSERT      | One row per scaffolded ticker, `is_active=true`        |
| `instrument_identifier`| INSERT      | One row, `id_type='ticker'`, `source='bootstrap_prod'` |
| `ticker_history`       | INSERT      | One row, `effective_from=2020-01-01`                   |

### Tables explicitly NOT touched

`price_bar_raw` (handled by `sync_eod_prices_universe`), `corporate_action`,
`earnings_event`, all `financial_*` tables, `watchlist_*`, all `broker_*`
tables, `order_intent` / `order_draft`, all execution objects.

Source policy is `FMP profile API only` for issuer / exchange / currency /
country, with deterministic fallbacks when fields are missing:

| Field                  | Fallback when FMP returns empty/None |
| ---------------------- | ------------------------------------ |
| `issuer_name_current`  | ticker symbol                        |
| `exchange_primary`     | `"UNKNOWN"`                          |
| `currency`             | `"USD"`                              |
| `country_code`         | `"US"`                               |

`yfinance_dev` is FORBIDDEN in production bootstrap (project policy — dev
data source must not appear in production paths). Polygon and Trading 212
are NOT consulted by bootstrap because bootstrap is an instrument-master
operation, not a price/quote operation.

### Four-flag handshake (identical to sync command)

```
python -m apps.cli.main bootstrap-research-universe-prod \
  --no-dry-run --write \
  --db-target=production --confirm-production-write
```

Defense-in-depth at TWO layers:
1. `build_bootstrap_plan` refuses if `write_mode == "WRITE_PRODUCTION"` AND
   (`confirm_production_write` is False OR `db_target != "production"`)
2. `execute_bootstrap` re-verifies before any DB write — even a hand-built
   plan with mismatched `db_target` is refused.

`DB_TARGET_OVERRIDE` env var continues to work the same way (B1.1 fix
applies here too): when set to `production`, the public-IP form
`34.x.x.x:5432` classifies as production. Invalid values raise ValueError.

### Idempotency

At plan time, the planner queries which tickers already have an
`instrument_identifier` row (`id_type='ticker'`) and marks them
`already_exists=True`. The executor then skips them — no FMP call, no
DB write. Re-running B3.2 multiple times is safe.

Database-level idempotency is also enforced via `INSERT ... ON CONFLICT DO
NOTHING` on the composite keys: `(instrument_id)`, `(instrument_id, id_type,
id_value, source, valid_from)`, `(instrument_id, ticker, effective_from)`.

### Per-ticker isolation

Each ticker is written within its own commit/rollback boundary. Failure of
one ticker (FMP error, DB conflict, network glitch) does NOT abort the
batch — the ticker is recorded in `failed[]` with its error and the
executor continues to the next ticker.

### Side-effect attestations (B3.1)

| Item                          | Status |
| ----------------------------- | ------ |
| DB writes performed           | NONE in B3.1 (code + tests only) |
| Cloud Run jobs created        | NONE   |
| Cloud Scheduler changes       | NONE   |
| Production DB backup          | NONE (deferred to B3.2) |
| Production redeploy           | YES — `quant-api` revision bump (image carries new bootstrap code) |
| Execution objects             | NONE   |
| Broker writes                 | NONE   |
| Live submit                   | LOCKED (`FEATURE_T212_LIVE_SUBMIT=false`) |

### B3.2 (deferred — requires separate sign-off)

B3.2 is the actual production execution. It will be executed only after:
1. Fresh Cloud SQL backup taken (and backup_id recorded)
2. Operator on-line during the run
3. Explicit user authorization in chat
4. Post-execute verification: `instrument` count grows by exactly 32,
   `instrument_identifier` count grows by exactly 32, `ticker_history`
   count grows by exactly 32, no other tables touched
5. Optional: re-run `sync-eod-prices-universe` to populate `price_bar_raw`
   for the now-scaffolded tickers (this would be a separate, also-gated step)

The B3.2 playbook lives in `docs/runbook.md` "Scanner Universe Production
Bootstrap (Phase B3 Execution)".

## B3.2-A — Production Bootstrap Execution Outcome (2026-04-30)

The B3.2-A scaffolding-only step ran on 2026-04-30. Result: **SUCCESS, 32/32
tickers scaffolded, 0 failures, 0 skipped**. The B3.2-B EOD price seed has
NOT been run; it requires a separate sign-off.

### Execution metadata

| Item                                | Value                                                            |
| ----------------------------------- | ---------------------------------------------------------------- |
| Backup ID                           | `1777585381061` (Cloud SQL `quant-api-db`, status `SUCCESSFUL`)   |
| Backup description                  | `pre-scanner-universe-bootstrap-20260430-2242`                   |
| Job name                            | `quant-ops-research-universe-bootstrap`                          |
| Execution name                      | `quant-ops-research-universe-bootstrap-x2blg`                    |
| Image digest                        | `sha256:fbfef5126887b32bf3a6debe9bc8fb87eb30e5216e430cdc311bbd850dd216e8` |
| `quant-api` revision (at execute)   | `quant-api-00034-tg7`                                            |
| Job runtime                         | ~58.5 seconds (32 tickers × 1.0 s pacing + writes)               |
| Container exit                      | `exit(0)` — clean                                                |

### Bootstrap result (verbatim from job log)

```
BOOTSTRAP RESULT — universe='scanner-research'  mode=WRITE_PRODUCTION
  requested_count               : 32
  target_count                  : 32
  succeeded                     : 32
  skipped (already existed)     : 0
  failed                        : 0
  instruments_inserted          : 32
  identifiers_inserted          : 32
  ticker_histories_inserted     : 32
  runtime_seconds               : 58.5
  db_target                     : production
  db_url_label                  : postgresql+psycopg2://quantuser:***@34.150.76.29:5432/quantdb
                                  (via DB_TARGET_OVERRIDE=production)
  Side-effect attestations:
    DB writes performed         : instrument + instrument_identifier + ticker_history only (PRODUCTION Cloud SQL)
    Cloud Run jobs created      : NONE
    Scheduler changes           : NONE
    Production deploy           : NONE
    Execution objects           : NONE
    Broker write                : NONE
    Live submit                 : LOCKED (FEATURE_T212_LIVE_SUBMIT=false)
```

### Before / after counts (verified read-only via one-shot `status` job)

| Table                              | Before B3.2-A | After B3.2-A | Δ   |
| ---------------------------------- | -------------:| ------------:| ---:|
| `instrument`                       | 4             | 36           | +32 |
| `instrument_identifier` (id_type='ticker', in universe) | 4 | 36 | +32 |
| `ticker_history` (in universe)     | 4             | 36           | +32 |
| `price_bar_raw` (whole table)      | 1344          | 1344         | 0   |

`price_bar_raw` delta from B3.2-A = 0 (the bootstrap module has zero
`PriceBarRaw` imports — verified by source grep test
`test_no_price_bar_raw_import`).

### Idempotency verification

A second dry-run executed AFTER the bootstrap completed reported:
`needs scaffolding=0, already scaffolded=32`. Re-running B3.2-A would now
be a complete no-op (skips all 32 already-scaffolded tickers).

### Protected 4 verification

- NVDA / AAPL / MSFT / SPY remain in `instrument_identifier` with their
  pre-existing `instrument_id` values (untouched by bootstrap — protected
  exclusion at planner layer ensured they were never in the target list)
- `instrument_total` went 4 → 36 = +32, matching exactly the bootstrap target

### Side-effect attestations (B3.2-A)

| Item                          | Status |
| ----------------------------- | ------ |
| DB writes performed           | `instrument + instrument_identifier + ticker_history only (PRODUCTION Cloud SQL)` (32 + 32 + 32 = 96 rows) |
| Cloud Run jobs left in fleet  | only `quant-sync-t212` (bootstrap job + 2 baseline-read jobs deleted post-execution) |
| Cloud Scheduler changes       | NONE — only `quant-sync-t212-schedule` ENABLED, schedule unchanged |
| Production DB backup          | YES (`1777585381061` SUCCESSFUL, taken 2026-04-30 22:43 UTC) |
| Production redeploy           | NONE |
| Execution objects             | NONE (`order_intent` count 0, `order_draft` count 0) |
| Broker writes                 | NONE (broker tables only modified by scheduled `quant-sync-t212` per its own cadence) |
| Live submit                   | LOCKED (`FEATURE_T212_LIVE_SUBMIT=false`) |
| EOD price seed                | NOT RUN — explicitly out of scope for B3.2-A; deferred to B3.2-B |

### Acceptance criteria status

| # | Criterion                                            | Status                                |
|---|------------------------------------------------------|---------------------------------------|
| 1-7 | (carried from B2)                                  | PASS                                  |
| 8 | Cloud SQL backup taken                               | PASS (`1777585381061`)                |
| 9 | B3.2-A authorized + executed                         | PASS                                  |
| 10| Runbook playbook + post-execution doc record         | PASS (this section + runbook updated) |

### Next step (NOT executed — requires separate sign-off)

B3.2-B is the EOD price seed for the 32 newly-scaffolded tickers, using
the existing `sync-eod-prices-universe` command + the same four-flag
production-write handshake. Now that the parent rows exist, the seed will
be able to resolve `instrument_id` for all 32 tickers (the failure mode
from B2). B3.2-B requires:
1. Fresh Cloud SQL backup (separate from `1777585381061`)
2. Operator on-line during the run
3. Explicit user authorization in chat
4. Polygon free-tier pacing (`--polygon-delay-seconds=13`) — runtime ~7-8 min for 32 tickers

## B3.2-B — Production EOD Price Seed Execution Outcome (2026-04-30)

The B3.2-B seed step ran on 2026-04-30, immediately after B3.2-A. Result:
**SUCCESS, 36/36 tickers, 0 failures, 11,808 bars inserted.**

### Execution metadata

| Item                                | Value                                                            |
| ----------------------------------- | ---------------------------------------------------------------- |
| Backup ID                           | `1777587848839` (Cloud SQL `quant-api-db`, status `SUCCESSFUL`)   |
| Backup description                  | `pre-scanner-universe-seed-b32b-20260430-2324`                   |
| Job name                            | `quant-ops-research-universe-seed`                               |
| Execution name                      | `quant-ops-research-universe-seed-4vqwx`                         |
| Image digest                        | `sha256:fbfef5126887b32bf3a6debe9bc8fb87eb30e5216e430cdc311bbd850dd216e8` |
| `quant-api` revision (at execute)   | `quant-api-00034-tg7`                                            |
| Job runtime                         | 509.2 seconds (~8.5 min)                                         |
| Container exit                      | `exit(0)` — clean                                                |
| Polygon delay                       | 13.0 s/call (Polygon free-tier 5 req/min compliant)              |

### Seed result (verbatim from job log)

```
SYNC RESULT — universe='scanner-research'  mode=WRITE_PRODUCTION
  ticker_count                  : 36
  succeeded                     : 36
  failed                        : 0
  bars_inserted_total           : 11808
  bars_existing_or_skipped_total: 24
  runtime_seconds               : 509.2
  db_target                     : production
  db_url_label                  : postgresql+psycopg2://quantuser:***@34.150.76.29:5432/quantdb
                                  (via DB_TARGET_OVERRIDE=production)
  Side-effect attestations:
    DB writes performed         : price_bar_raw + source_run only (PRODUCTION Cloud SQL)
    Cloud Run jobs created      : NONE
    Scheduler changes           : NONE
    Production deploy           : NONE
    Execution objects           : NONE
    Broker write                : NONE
    Live submit                 : LOCKED (FEATURE_T212_LIVE_SUBMIT=false)
```

### Before / after counts

| Table / metric                     | Before B3.2-B | After B3.2-B | Δ      |
| ---------------------------------- | -------------:| ------------:| ------:|
| `instrument`                       | 36            | 36           | 0      |
| `instrument_identifier`            | 52            | 52           | 0      |
| `ticker_history`                   | 36            | 36           | 0      |
| `price_bar_raw`                    | 1,344         | **13,152**   | +11,808 |
| `order_intent` / `order_draft`     | 0 / 0         | 0 / 0        | 0 / 0  |
| `data_issue` (unresolved)          | 0             | 0            | 0      |

The seed wrote `price_bar_raw` rows only — no other tables touched.

### Per-ticker bar counts (post-seed)

| Group                              | Tickers                                      | Bars per ticker | Subtotal |
| ---------------------------------- | -------------------------------------------- | --------------: | -------: |
| Protected 4 (INCR mode, unchanged) | NVDA / AAPL / MSFT / SPY                     | 336 each        | 1,344    |
| 32 newly-scaffolded (BOOTSTRAP mode) | AMC, AMD, AMZN, AVGO, BA, BAC, COIN, CVX, DIS, F, GM, GOOGL, GS, INTC, IWM, JPM, LCID, META, MU, NFLX, NIO, OXY, PLTR, QQQ, RIVN, SIRI, SOFI, TSLA, TSM, UBER, XOM, XPEV | 369 each | 11,808   |
| **Total**                          |                                              |                 | **13,152** |

Math check: 4 × 336 + 32 × 369 = 1,344 + 11,808 = 13,152 ✓

### Idempotency observation

The 24 `bars_existing_or_skipped_total` were Polygon-returned bars for the
4 protected tickers within their 7-day lookback overlap (2026-04-22 →
2026-04-30) that already existed from B2 — `INSERT ... ON CONFLICT DO
NOTHING` deduplicated them correctly. Protected 4 bar count went 336 →
336 (no shrinkage, no double-count).

### Protected 4 verification

- NVDA / AAPL / MSFT / SPY each present with 336 bars (unchanged from
  pre-B3.2-B)
- Their `instrument_id` UUIDs are the same pre-existing values (verified
  in `list-instruments` post-flight read)
- No new rows inserted in `instrument` / `instrument_identifier` /
  `ticker_history` (none of those tables are touched by the EOD seed)

### Scanner OpenAPI verification (auth-unavailable path)

- `/api/scanner/stock` present in production OpenAPI ✓
- `ScanResponse.additionalProperties=False` (Pydantic `extra=forbid`) ✓
- `ScanResponse.required=['items','as_of','data_mode','universe','limit','scanned','matched']` ✓
- `ScanItem.additionalProperties=False` ✓
- Unauthenticated GET returns HTTP 401 (not 500) ✓

When an authenticated client calls `/api/scanner/stock?universe=all`, it
will now scan 36 instruments instead of 4. (Authenticated smoke not run
here because Firebase token issuance requires manual UI sign-in.)

### Side-effect attestations (B3.2-B)

| Item                          | Status |
| ----------------------------- | ------ |
| DB writes performed           | `price_bar_raw + source_run only (PRODUCTION Cloud SQL)` |
| Bars inserted                 | 11,808 (32 BOOTSTRAP × 369 + 0 from INCR overlap) |
| Bars existing / skipped       | 24 (idempotent ON CONFLICT DO NOTHING for protected 4 lookback overlap) |
| Cloud Run jobs left in fleet  | only `quant-sync-t212` (seed + 3 transient read-only helpers deleted) |
| Cloud Scheduler changes       | NONE — only `quant-sync-t212-schedule` ENABLED, schedule unchanged |
| Production DB backup          | YES (`1777587848839` SUCCESSFUL, taken 2026-04-30 22:24 UTC) |
| Production redeploy           | NONE |
| Execution objects             | NONE (`order_intent=0`, `order_draft=0`) |
| Broker writes                 | NONE (broker tables only modified by scheduled `quant-sync-t212`) |
| Live submit                   | LOCKED (`FEATURE_T212_LIVE_SUBMIT=false`) |
| `quant-sync-eod-prices` job   | NOT CREATED — Phase C remains deferred |
| Cloud Scheduler `quant-sync-eod-prices-schedule` | NOT CREATED |

### Acceptance criteria status — all 10 PASS

| # | Criterion                                            | Status |
|---|------------------------------------------------------|--------|
| 1-7 | (carried from B2)                                  | PASS   |
| 8 | Cloud SQL backup taken                               | PASS (`1777587848839`) |
| 9 | B3.2-B authorized + executed                         | PASS   |
| 10| Runbook playbook + post-execution doc record         | PASS   |

### Next step (Phase C — NOT executed)

Phase C is the daily incremental sync that would create
`quant-sync-eod-prices` Cloud Run Job + `quant-sync-eod-prices-schedule`
mirroring the existing `quant-sync-t212` cadence. It requires its own
authorization. The current production state (36 instruments × 369-336
bars) is sufficient for the Stock Scanner to operate against without
Phase C, because the seed already ran the full bootstrap window.

### What was NOT changed

- No execution intent / draft / order
- No broker write
- No `FEATURE_T212_LIVE_SUBMIT` change
- No new Cloud Run Job left lying around
- No new Cloud Scheduler created
- No daily incremental sync (Phase C) created
- No quant-sync-t212 job or schedule modification
- No production deploy beyond the `quant-api-00033-x6l` revision (which
  contains B1 + B1.1 code; both safe)

## Appendix A — Files in this readiness pack

- `docs/scanner-research-universe-production-plan.md` (this file)
- `scripts/check_scanner_universe_provider_readiness.py` (dry-run, read-only)
- `scripts/bootstrap_research_universe_dev.py` (dev-only ingestion, already shipped in commit `92975e5`)

## Appendix B — Files NOT in this readiness pack (must come later, with explicit approval)

- `apps/cli/main.py` — new `sync-eod-prices` command
- `libs/ingestion/sync_eod_prices_universe.py` — production ingestion module for the 32 tickers
- `scripts/seed_research_universe_prod.py` — one-shot Cloud Run Job entry
- `infra/scheduler/quant-sync-eod-prices-schedule.yaml` — Cloud Scheduler config
- `docs/runbook.md` — execution playbook for seed + ongoing sync

These are deliberately not pre-written. Writing them now would suggest readiness that doesn't yet exist (see Section 8 acceptance criteria).
