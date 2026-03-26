# Status

## Last Updated: 2026-03-26 (v1.4.1-rc — FMP Production Primary — Phases 1-8.1 Complete)

### Overall Completion: ~99%

The platform has reached enhanced Release Candidate status through Phase 8.1. FMP has been formally promoted to production primary path for prices and financials. yfinance_dev has been explicitly demoted to dev-only fallback. Production CLI commands (sync-eod-fmp, sync-fundamentals-fmp) are now available. Source matrix fully updated.

### Phase 8.1: FMP Production Primary Path Promotion (COMPLETED)
- FMP promoted to production primary for EOD prices + financial statements
- New ingestion module: sync_eod_prices_fmp.py with price + fundamentals sync
- New CLI commands: sync-eod-fmp, sync-fundamentals-fmp
- yfinance_dev explicitly demoted to dev-only in all documentation
- Source matrix rewritten with clear PRIMARY/SECONDARY/DEV hierarchy
- Polygon/Massive key configured for splits/dividends (secondary path)
- 224 FMP price bars + 756 FMP financial facts verified in DB
- All downstream chains (DQ/Research/Backtest/Dashboard) validated on FMP data

### Phase 8: Production Data Cutover + 7-Day Dogfooding (COMPLETED)
- Full data path audit: 9 adapter paths assessed for production readiness
- 7-day dogfooding simulation across all workflow scenarios
- Data freshness threshold fixed (3 → 7 days, accounts for weekends)
- Daily brief enriched with instrument names and days_since_update
- All 12 API endpoint groups validated (200 OK)
- 10 friction points documented with severity/frequency assessment
- Production data paths clearly documented in source_matrix.md
- Platform classified as Release Candidate (RC)

### Phase 7: Real Daily Usage Validation & Friction Fixing (COMPLETED)
- 6-scenario real usage validation (Dashboard, Watchlist, Presets, Notes, Research→Backtest, Execution)
- 10 friction points identified, priority fixes applied
- Notes API: instrument name resolution (no more raw UUIDs)
- Recent activity: preset usage context included
- docs/daily-workflow.md created with daily research habit guide

### Phase 6.6: Watchlist / Presets / Notes / Continue Flow (COMPLETED)
- Research page: watchlist universe selector, saved presets panel, research notes inline
- Dashboard: "Continue Where You Left Off" section with recent presets and notes
- Research → Backtest flow: "Run as Backtest" button in results area
- apiPut/apiDelete added to frontend API hook
- All 160 tests passing, Vite build successful

### Phase 6.5: Frontend Daily Workflow Productization (COMPLETED)
- Dashboard rewritten as Daily Research Home with /daily/brief API integration
- Data freshness, upcoming earnings, platform status cards on first screen
- Watchlist management with create/view on Dashboard
- Recent activity feed with typed icons and relative timestamps
- Quick Actions grid for fast navigation to Research/Backtest/Screener/Execution
- Professional empty states for all sections
- 160 tests passing, Vite build successful

---

### Completed Phases

#### Phase 1 -- Foundation
- 19-table PostgreSQL schema (instrument, identifiers, ticker_history, prices, corporate_actions, filings, earnings, financials, macro, exchange_calendar, source_run, data_issue, execution tables, broker snapshots)
- Adapters: SEC EDGAR, OpenFIGI, Massive/Polygon (skeleton), FMP (skeleton), BEA (skeleton), BLS (skeleton), Treasury (skeleton), Trading 212 (skeleton)
- Dev data loading via yfinance (tagged `source='yfinance_dev'`)
- 6 initial DQ rules
- CLI ingestion commands
- FastAPI with health, instruments, and research endpoints

#### Phase 2A -- Real Data Ingestion
- SEC companyfacts integration for standardized financials (production source)
- SEC EDGAR filings sync (production source)
- yfinance_dev data for prices, corporate actions, earnings (DEV ONLY)
- OpenFIGI identifier enrichment
- Exchange calendar population (NYSE/NASDAQ, 2020-2026)
- 4 instruments bootstrapped: AAPL, MSFT, NVDA, SPY

#### Phase 2B -- Research Layer Enhancement
- Factor primitives: daily_returns, rolling_volatility, cumulative_return, drawdown, relative_strength, momentum, valuation_snapshot, performance_summary
- Stock screeners: by liquidity, returns, fundamentals, composite rank
- Enhanced event study: grouped summary across instruments with per-ticker breakdowns
- 9 research API endpoints: performance, valuation, drawdown, screeners (4), event study summary
- All research functions require explicit `asof_date` to prevent look-ahead bias

#### Phase 2C -- Execution Layer Hardening
- Risk checks: 7 rules (positive qty, limit price, max position, max notional, duplicate order, stale intent, trading day)
- Draft lifecycle: approve, reject, expire stale
- Execution API: risk-check endpoint, reject endpoint, expire-stale endpoint
- Structured audit logging on all execution actions
- Live order submission disabled by default (`FEATURE_T212_LIVE_SUBMIT=false`)

#### Phase 3A -- Backtest/Simulation Engine
- Core engine: bar-by-bar vectorized simulation with DB-backed prices
- Cost model: commission + slippage (configurable, default 5 bps)
- Portfolio config: equal weight, max positions, rebalance frequency (daily/weekly/monthly)
- Time splits: simple split, walk-forward, expanding window
- Metrics: total/annualized return, volatility, Sharpe, max drawdown, turnover, costs

#### Phase 3B -- Observability & DQ Hardening
- DQ expanded to 11 rules: added cross-source divergence, stale prices, ticker overlap, orphan identifiers, raw/adjusted contamination
- CLI: `status` command (table counts, recent runs, DQ summary), `dq-report` command

#### Phase 4A -- Backtest Persistence
- 2 new DB tables: `backtest_run`, `backtest_trade` (21 total tables)
- Persist backtest results: metrics, config, NAV series, individual trades
- `run_and_persist_backtest` convenience wrapper
- Load/list persisted backtest runs

#### Phase 4B -- Backtest API
- POST `/backtest/run` -- run and persist a backtest
- GET `/backtest/runs` -- list past runs with filtering
- GET `/backtest/runs/{run_id}` -- full run detail with metrics
- GET `/backtest/runs/{run_id}/trades` -- trade-level detail
- GET `/backtest/runs/{run_id}/nav` -- NAV series

#### Phase 4C -- Strategy Interface
- Abstract strategy interfaces: UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay
- Concrete implementations: AllActiveUniverse, EqualWeightConstructor, MaxPositionRiskOverlay, MomentumSignalProvider
- All strategy interfaces enforce explicit `asof_date` parameters

#### Phase 4D -- CLI Backtest Command
- `run-backtest` CLI command with full parameterization (strategy, tickers, dates, costs, positions, rebalance)
- Ticker resolution via instrument_identifier lookup
- Formatted output with key metrics

#### Phase 4E -- Documentation & Cleanup
- All documentation updated to reflect v1 state

#### Phase 5A -- React Frontend
- Full React 19 + Vite + Tailwind CSS frontend replacing legacy vanilla JS dashboard
- 7 pages: Dashboard, Instruments, Research, Backtest, Execution, Data Quality, Settings
- Vite dev proxy to FastAPI backend (port 3000 -> 8001)
- Production build served by FastAPI static file mount
- Legacy vanilla JS frontend archived to `_archive/frontend-legacy/`

#### Phase 5B -- DQ API & Observability
- DQ REST endpoints: GET `/dq/issues`, GET `/dq/source-runs`, POST `/dq/run`
- DQ issue filtering by severity and resolution status
- Source run history with status and counters
- Frontend Data Quality page connected to DQ API

#### Phase 6 -- Daily Research Platform
- Added 4 new database tables: `watchlist_group`, `watchlist_item`, `saved_preset`, `research_note`
- Added 15+ new API endpoints across 4 new routers: `/daily`, `/watchlist`, `/presets`, `/notes`
- Daily brief endpoint provides research context (data freshness, upcoming earnings, DQ status, recent backtests, execution status)
- Recent activity feed aggregates platform events
- Watchlist management for maintaining daily focus universe
- Saved presets for reusable screener/backtest/research configurations
- Research notes for thesis snapshots and annotations
- 19 new integration tests (total: 160 passing)

---

### Database Summary (25 Tables)

| Table | Approx Count | Source |
|-------|-------------|--------|
| instrument | 4 | SEC |
| instrument_identifier | ~20 | SEC + OpenFIGI |
| ticker_history | varies | SEC |
| exchange_calendar | ~3654 | Internal (NYSE/NASDAQ) |
| price_bar_raw | ~6248 | yfinance_dev (DEV ONLY) |
| corporate_action | ~387 | yfinance_dev (DEV ONLY) |
| earnings_event | ~75 | yfinance_dev (DEV ONLY) |
| filing | ~3286 | SEC EDGAR |
| financial_period | ~195 | SEC companyfacts |
| financial_fact_std | ~2636 | SEC companyfacts |
| macro_series | 0 | Skeleton only |
| macro_observation | 0 | Skeleton only |
| source_run | varies | Internal tracking |
| data_issue | varies | DQ engine |
| order_intent | 0 | Execution layer |
| order_draft | 0 | Execution layer |
| broker_account_snapshot | 0 | T212 (no key configured) |
| broker_position_snapshot | 0 | T212 (no key configured) |
| broker_order_snapshot | 0 | T212 (no key configured) |
| backtest_run | varies | Backtest engine |
| backtest_trade | varies | Backtest engine |
| watchlist_group | varies | Daily research |
| watchlist_item | varies | Daily research |
| saved_preset | varies | Daily research |
| research_note | varies | Daily research |

### Test Suite
- **160 tests passing**

### What Works Without Any External API Keys

The following features are fully functional using only the dev data pipeline (yfinance) and public APIs (SEC EDGAR):

1. Full database schema setup and migrations
2. Exchange calendar generation (NYSE/NASDAQ, 2020-2026)
3. Instrument bootstrapping from SEC EDGAR
4. SEC filings and fundamentals ingestion (production-quality)
5. Dev price/earnings/corporate action loading via yfinance
6. All 11 DQ rules and reporting
7. All 8 research factor primitives and 4 screeners
8. Event studies with grouped summaries
9. Full backtest engine with persistence
10. Complete execution pipeline (dry run, no live submission)
11. All API endpoints (45+ endpoints across 10 routers)
12. React frontend dashboard with all 7 pages
13. All CLI commands (15 commands)

### External Blockers (API Keys Required for Production Data)

| Blocker | Key Needed | Impact |
|---------|-----------|--------|
| No Massive/Polygon API key | `MASSIVE_API_KEY` | Prices, splits, dividends stuck on yfinance_dev |
| No FMP API key | `FMP_API_KEY` | Earnings data stuck on yfinance_dev |
| No OpenFIGI API key | `OPENFIGI_API_KEY` | Identifier enrichment limited to unauthenticated rate |
| No Trading 212 API key | `T212_API_KEY` | Broker integration untested, no live trading |
| No BEA API key | `BEA_API_KEY` | Macro data (GDP, PCE) unavailable |
| No BLS API key | `BLS_API_KEY` | Macro data (employment, CPI) unavailable |

### Production vs Dev Data

| Data Type | Current Source | Production Source | Status |
|-----------|--------------|-------------------|--------|
| Filings | SEC EDGAR | SEC EDGAR | **Production** |
| Fundamentals | SEC companyfacts | SEC companyfacts | **Production** |
| Identifiers | SEC + OpenFIGI | SEC + OpenFIGI | **Production** |
| EOD Prices | yfinance_dev | Massive/Polygon | **DEV ONLY -- blocker** |
| Corporate Actions | yfinance_dev | Massive/Polygon | **DEV ONLY -- blocker** |
| Earnings | yfinance_dev | FMP | **DEV ONLY -- blocker** |
| Macro | Not loaded | BEA/BLS/Treasury | **Skeleton only** |
| Broker Data | Not loaded | Trading 212 | **No API key** |
