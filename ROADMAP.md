# Roadmap

## v1 -- Completed

### Phase 1: Foundation
- 19-table PostgreSQL schema with Alembic migrations
- Adapters: SEC EDGAR, OpenFIGI, Massive/Polygon (skeleton), FMP (skeleton), BEA/BLS/Treasury (skeleton), Trading 212 (skeleton)
- Dev data loading via yfinance (tagged `source='yfinance_dev'`)
- Initial 6 DQ rules
- FastAPI server with health, instruments, basic research endpoints
- Typer CLI for ingestion commands

### Phase 2A: Real Data Ingestion
- SEC companyfacts integration for standardized financials
- SEC EDGAR filings sync
- yfinance_dev data for prices, corporate actions, earnings
- OpenFIGI identifier enrichment
- Exchange calendar population (NYSE/NASDAQ)

### Phase 2B: Research Layer Enhancement
- Factor primitives: daily_returns, rolling_volatility, cumulative_return, drawdown, relative_strength, momentum, valuation_snapshot, performance_summary
- Stock screeners: liquidity, returns, fundamentals, composite rank
- Enhanced event study with grouped summaries
- 9 new research API endpoints

### Phase 2C: Execution Layer Hardening
- 7 risk checks (positive qty, limit price, max position, max notional, duplicate order, stale intent, trading day)
- Draft lifecycle: approve, reject, expire stale
- Execution API: risk-check, reject, expire-stale endpoints

### Phase 3A: Backtest Engine
- Bar-by-bar vectorized simulation with DB-backed prices
- Cost model: commission + slippage
- Portfolio config: equal weight, max positions, rebalance frequency
- Time splits: simple split, walk-forward, expanding window
- Metrics: total/annualized return, volatility, Sharpe, max drawdown, turnover, costs

### Phase 3B: Observability & DQ Hardening
- DQ expanded to 11 rules (cross-source divergence, stale prices, ticker overlap, orphan identifiers, raw/adjusted contamination)
- CLI status and dq-report commands

### Phase 4A-E: Backtest Persistence, API, Strategy, CLI
- 2 new DB tables: backtest_run, backtest_trade (21 total)
- Backtest API: run, list, detail, trades, NAV series
- Strategy interfaces: UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay
- Concrete strategies: momentum signal, equal weight, max position risk overlay
- CLI run-backtest command
- Documentation updated to v1 state

---

## v2 -- Planned Directions

### Production Data Sources (Blocker: API Keys Required)
- Configure Massive/Polygon API key for production EOD prices, splits, dividends
- Configure FMP API key for production earnings data
- Configure Trading 212 API key for broker integration
- Migrate from `yfinance_dev` tagged data to production sources
- Cross-source reconciliation between dev and production data

### Macro Data Pipeline
- Implement BEA adapter (GDP, PCE, investment)
- Implement BLS adapter (employment, CPI, PPI)
- Implement Treasury adapter (interest rates, fiscal data)
- Load macro series and observations into DB

### Research Expansion
- Multi-factor models (value, momentum, quality, size composites)
- Sector/industry classification and relative analysis
- Custom factor framework for user-defined factors
- Portfolio risk decomposition (factor attribution)

### Backtest Enhancement
- Multiple strategy implementations beyond momentum
- Benchmark comparison (vs SPY, sector indices)
- Monte Carlo simulation / bootstrap confidence intervals
- Out-of-sample validation framework
- Strategy parameter optimization with walk-forward

### Execution Pipeline
- Trading 212 demo account integration (with API key)
- Position sizing algorithms
- Execution quality monitoring (slippage analysis)
- Order routing logic for multi-broker support

### Production Hardening
- Airflow/Prefect migration for scheduled ingestion
- Monitoring and alerting (ingestion failures, DQ regressions)
- Performance optimization (query caching, materialized views)
- API authentication and rate limiting
- Live trading enablement (with comprehensive safeguards)

### UI / Dashboard
- Web dashboard for portfolio monitoring
- Backtest result visualization
- DQ issue browser
- Research factor explorer
