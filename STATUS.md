# Status

## Last Updated: 2026-03-23 (v1 Complete through Phase 4E)

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
- **103 tests passing**

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

### Known Blockers
- No Massive/Polygon API key: prices, splits, dividends stuck on yfinance_dev
- No FMP API key: earnings data stuck on yfinance_dev
- No OpenFIGI API key configured: enrichment limited to unauthenticated rate
- No Trading 212 API key: broker integration untested
- Macro adapters (BEA, BLS, Treasury) are skeleton implementations
