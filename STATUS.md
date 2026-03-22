# Status

## Last Updated: 2026-03-22 (Phase 3B)

### Completed Phases

#### Phase 2B — Research Layer Enhancement
- Factor primitives: daily_returns, rolling_volatility, cumulative_return, drawdown, relative_strength, momentum, valuation_snapshot, performance_summary
- Stock screeners: by liquidity, returns, fundamentals, composite rank
- Enhanced event study: grouped summary across instruments with per-ticker breakdowns
- 9 new research API endpoints: performance, valuation, drawdown, screeners, event study summary
- 14 new integration tests

#### Phase 2C — Execution Layer Hardening
- Risk checks: 7 rules (positive qty, limit price, max position, max notional, duplicate order, stale intent, trading day)
- Draft lifecycle: approve, reject, expire stale
- Execution API: risk-check endpoint, reject endpoint, expire-stale endpoint
- Structured audit logging on all execution actions
- 7 new tests (risk checks + order lifecycle + API)

#### Phase 3A — Backtest/Simulation Engine
- Core engine: bar-by-bar vectorized simulation with DB-backed prices
- Cost model: commission + slippage (configurable)
- Portfolio config: equal weight, max positions, rebalance frequency
- Time splits: simple split, walk-forward, expanding window
- Metrics: total/annualized return, volatility, Sharpe, max drawdown, turnover, costs
- 8 new tests (engine + time splits)

#### Phase 3B — Observability & DQ Hardening
- DQ expanded from 6 to 10 rules: added cross-source divergence, stale prices, ticker overlap, orphan identifiers
- CLI: `status` command (table counts, recent runs, DQ summary), `dq-report` command
- All 10 DQ rules running on real data

### Real Data Summary
| Table | Count | Source |
|-------|-------|--------|
| instrument | 4 | SEC |
| instrument_identifier | ~20 | SEC + OpenFIGI |
| price_bar_raw | 6248 | yfinance_dev |
| corporate_action | 387 | yfinance_dev |
| earnings_event | 75 | yfinance_dev |
| financial_period | 195 | SEC companyfacts |
| financial_fact_std | 2636 | SEC companyfacts |
| filing | ~3286 | SEC EDGAR |
| exchange_calendar | 3654 | Internal |

### Test Suite
- **93 tests passing** (34 unit + 5 smoke + 54 integration)

### Remaining Blockers
- No Massive/Polygon or FMP API key for production data source
- No T212 API key for broker integration testing
