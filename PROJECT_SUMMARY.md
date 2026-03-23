# Project Summary

## quant-api-platform

API-first quantitative stock analysis, research, backtesting, and controlled execution platform for US equities.

## Current State: v1 Complete (Phases 1 through 4E)

### Platform Capabilities

1. **Data Layer**: 21-table PostgreSQL schema, SEC/OpenFIGI integration (production), yfinance dev data (DEV ONLY), exchange calendar
2. **Research Layer**: Factor primitives (8 functions), stock screeners (4 types), PIT-safe financial views, event studies with grouped summaries, split-adjusted and total-return-adjusted prices -- all require explicit `asof_date`
3. **Execution Layer**: Intent -> draft -> approval -> risk check -> submit pipeline, 7 risk checks, Trading 212 adapter (skeleton, no API key), live submission disabled by default
4. **Backtest Layer**: Vectorized bar-by-bar engine, cost model (commission + slippage), portfolio construction (equal weight, max positions), walk-forward/expanding time splits, DB persistence of runs and trades
5. **Strategy Layer**: Abstract interfaces (UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay) with concrete implementations (momentum, equal weight, max position cap)
6. **DQ Layer**: 11 rules running, automated issue tracking in `data_issue` table
7. **Observability**: CLI status/report commands, structured logging, source run tracking

### Key Metrics
- 103 tests passing
- 4 real instruments with data (AAPL, MSFT, NVDA, SPY)
- 21 database tables
- 11 DQ rules running
- 16+ research/backtest API endpoints
- 13 CLI commands
- Live order submission disabled by default (`FEATURE_T212_LIVE_SUBMIT=false`)

### Data Source Status
- **Production**: SEC EDGAR (filings), SEC companyfacts (financials), OpenFIGI (identifiers)
- **Dev only (yfinance_dev)**: EOD prices, corporate actions, earnings -- requires real API keys (Massive/Polygon, FMP) to replace
- **Skeleton adapters exist but no keys configured**: Massive/Polygon, FMP, BEA, BLS, Treasury, Trading 212

### Architecture
- **Backend**: FastAPI + Typer CLI
- **Database**: PostgreSQL 16 + SQLAlchemy + Alembic
- **Testing**: pytest (unit + integration + smoke)
- **Containerization**: Docker Compose for PostgreSQL

### What This Platform Does NOT Do (Yet)
- No live trading (disabled by design)
- No real-time data streaming
- No automated rebalancing or stop-loss
- No production price/earnings data (blocked on API keys)
- No macro data loaded (adapters are skeletons)
- No UI/dashboard
