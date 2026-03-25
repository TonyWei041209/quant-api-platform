# Status

## Last Updated: 2026-03-25 (v1.1 Pre-Production -- Phases 1-5 Complete)

### Overall Completion: ~95%

The platform is feature-complete through Phase 5. All core functionality works end-to-end. The remaining 5% is external API key configuration to replace dev data sources with production sources.

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

---

### Database Summary (21 Tables)

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

### Test Suite
- **141 tests passing**

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
11. All API endpoints (20+ endpoints across 6 routers)
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
