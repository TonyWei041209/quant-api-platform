# Scanner Research Universe — Production Seed Plan

**Status:** READINESS PACK — NOT YET EXECUTED
**Owner:** quant-api-platform maintainers
**Created:** 2026-04-28
**Last validated dev result:** commit `92975e5`, scanner on 36-stock dev universe matched 13 candidates (high=8 medium=5), banned-words violations 0, latency ~461ms cold.

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
- **Memory / timeout**: 512Mi memory, 300s timeout (similar to existing sync job)
- **Secrets**: same `MASSIVE_API_KEY`, `FMP_API_KEY`, `DATABASE_URL` already in production secret manager

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
| 1 | Polygon `MASSIVE_API_KEY` reachable, returns valid response for sample ticker | dry-run script: `check_scanner_universe_provider_readiness.py` | ⬜ |
| 2 | FMP `FMP_API_KEY` reachable, returns valid profile for sample ticker | same dry-run | ⬜ |
| 3 | All 36 tickers resolvable by FMP `get_profile` (issuer name + exchange) | dry-run with `--check-all` flag | ⬜ |
| 4 | All 36 tickers have ≥ 252 trading days of recent EOD bars from Polygon | dry-run with `--check-all` flag | ⬜ |
| 5 | `quant-sync-eod-prices` Cloud Run Job specification reviewed and approved | this doc + user sign-off | ⬜ |
| 6 | `sync-eod-prices` CLI command implemented and passes unit tests | code review + test run | ⬜ |
| 7 | Rollback SQL template tested in dev DB (with row counts confirmed) | dev DB dry-run | ⬜ |
| 8 | Cloud SQL backup taken immediately before seed | gcloud sql backups create | ⬜ |
| 9 | User explicit go-ahead on this PR / runbook | user sign-off in chat | ⬜ |
| 10 | docs/runbook.md updated with execution steps and runbook | doc review | ⬜ |

**Until every row is checked, production seed is DEFERRED.** The dry-run readiness script (item 1, 2, 3, 4) lives in this same readiness pack and is safe to run repeatedly without any DB writes.

---

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
