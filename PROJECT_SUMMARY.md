# Project Summary

## quant-api-platform

API-first quantitative stock analysis, research, backtesting, and controlled execution platform for US equities.

## Current State: v1.1 Pre-Production (Phases 1 through 5 Complete)

### Platform Capabilities

1. **Data Layer**: 21-table PostgreSQL schema, SEC/OpenFIGI integration (production), yfinance dev data (DEV ONLY), exchange calendar (NYSE/NASDAQ, 2020-2026)
2. **Research Layer**: Factor primitives (8 functions), stock screeners (4 types), PIT-safe financial views, event studies with grouped summaries, split-adjusted and total-return-adjusted prices -- all require explicit `asof_date`
3. **Execution Layer**: Intent -> draft -> approval -> risk check -> submit pipeline, 7 risk checks, Trading 212 adapter (skeleton, no API key), live submission disabled by default
4. **Backtest Layer**: Vectorized bar-by-bar engine, cost model (commission + slippage), portfolio construction (equal weight, max positions), walk-forward/expanding time splits, DB persistence of runs and trades
5. **Strategy Layer**: Abstract interfaces (UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay) with concrete implementations (momentum, equal weight, max position cap)
6. **DQ Layer**: 11 rules running, automated issue tracking in `data_issue` table, REST API for issues and source runs
7. **Observability**: CLI status/report commands, structured logging, source run tracking
8. **Frontend**: React 19 + Vite + Tailwind CSS dashboard with 7 pages (Dashboard, Instruments, Research, Backtest, Execution, Data Quality, Settings). Vite dev proxy to FastAPI backend. Production build served by FastAPI static mount.

### Key Metrics
- 141 tests passing
- 4 real instruments with data (AAPL, MSFT, NVDA, SPY)
- 21 database tables
- 11 DQ rules running
- 20+ API endpoints across 6 routers (health, instruments, research, execution, backtest, dq)
- 15 CLI commands
- 7 React frontend pages
- Live order submission disabled by default (`FEATURE_T212_LIVE_SUBMIT=false`)

### Data Source Status
- **Production**: SEC EDGAR (filings), SEC companyfacts (financials), OpenFIGI (identifiers)
- **Dev only (yfinance_dev)**: EOD prices, corporate actions, earnings -- requires real API keys (Massive/Polygon, FMP) to replace
- **Skeleton adapters exist but no keys configured**: Massive/Polygon, FMP, BEA, BLS, Treasury, Trading 212

### Architecture
- **Frontend**: React 19 + Vite + Tailwind CSS (port 3000 dev, static build for production)
- **Backend**: FastAPI + Typer CLI
- **Database**: PostgreSQL 16 + SQLAlchemy + Alembic
- **Testing**: pytest (unit + integration + smoke), 141 tests
- **Containerization**: Docker Compose for PostgreSQL

### What Works Without Any External API Keys
- Full database setup and migrations
- Exchange calendar generation
- SEC filings and fundamentals ingestion (production-quality, no key needed)
- Dev data loading (prices, corporate actions, earnings via yfinance)
- All 11 DQ checks and reporting
- All research factors, screeners, and event studies
- Full backtest engine with persistence and walk-forward
- Complete execution pipeline (dry run mode)
- All API endpoints and CLI commands
- React frontend dashboard

### What Requires API Keys
- Production-quality price data (Massive/Polygon key)
- Production earnings data (FMP key)
- Higher-rate identifier enrichment (OpenFIGI key)
- Macro data pipeline (BEA, BLS keys)
- Broker integration and live trading (Trading 212 key + `FEATURE_T212_LIVE_SUBMIT=true`)
