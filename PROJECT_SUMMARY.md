# Project Summary

## quant-api-platform

API-first, PIT-aware quantitative stock analysis, research, backtesting, and controlled execution platform for US equities.

## Current State: v1.5.0 Production Release (All Phases Complete)

### Platform Capabilities

1. **Data Layer**: 25-table PostgreSQL schema with UUID PKs and timestamptz. Security Master with identifier and ticker history. Exchange calendar (NYSE/NASDAQ, 2020-2026). Raw unadjusted EOD prices from FMP (source-tagged, raw_payload preserved). Corporate actions from Polygon. SEC filings and companyfacts. Source run tracking and data issue persistence.
2. **Research Layer**: 9 factor primitives (returns, volatility, drawdown, momentum, valuation, etc.), 4 screeners (liquidity, returns, fundamentals, composite rank), earnings event study (1/3/5/10 day windows), PIT-safe financial views (reported_at enforcement), split-adjusted and total-return-adjusted prices. All functions require explicit `asof_date`.
3. **Execution Layer**: Signal → Intent → Draft → Approval → Submit pipeline, 7 risk checks (positive qty, limit price, max position, max notional, duplicate order, stale intent, trading day), Trading 212 readonly verified, live submission disabled by default (`FEATURE_T212_LIVE_SUBMIT=false`).
4. **Backtest Layer**: Bar-by-bar simulation engine, cost model (commission + slippage), portfolio construction (equal weight, max positions), walk-forward/expanding time splits, persistent runs with metrics/trades/NAV series, queryable via API.
5. **Strategy Layer**: Abstract interfaces (UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay) with concrete implementations (momentum, equal weight, max position cap).
6. **DQ Layer**: 11 rules (OHLC, non-negative, duplicates, trading days, corporate actions, PIT, cross-source, stale, overlap, orphan, raw/adj contamination), automated issue tracking, REST API for issues and source runs.
7. **Observability**: CLI status/report commands, structured logging, source run tracking with counters.
8. **Frontend**: React 18 + Vite + Tailwind CSS with 7 pages (Dashboard, Instruments, Research, Backtests, Execution, Data Quality, Settings). Bilingual (EN/中文). Dark mode. Responsive layout.
9. **Daily Research Layer**: Daily Research Home dashboard, watchlist groups with instrument management, saved presets for reusable screener/backtest/research configurations, research notes (thesis, observation, risk, follow-up), recent activity feed, continue-where-you-left-off flow.

### Key Metrics
- 160 tests passing
- 4 real instruments with data (AAPL, MSFT, NVDA, SPY)
- 25 database tables
- 11 DQ rules running
- 25+ REST API endpoints
- 15+ CLI commands
- 7 React frontend pages
- Live order submission disabled by default

### Data Source Status

| Source | Role | Status |
|--------|------|--------|
| FMP (Financial Modeling Prep) | Primary: EOD prices, financials, profiles | **Production** |
| SEC EDGAR | Truth: filings, companyfacts, PIT validation | **Production** |
| Polygon / Massive | Primary: corporate actions; Secondary: raw price validation | **Production** |
| OpenFIGI | Identifier enrichment (FIGI mapping) | **Production** |
| Trading 212 | Broker: readonly account/positions/orders | **Verified (Basic Auth)** |
| BEA / BLS / Treasury | Macro data skeletons | Phase 2 |

### Architecture
- **Frontend**: React 18 + Vite + Tailwind CSS (port 3000 dev, static build for production)
- **Backend**: FastAPI + Typer CLI
- **Database**: PostgreSQL 16 + SQLAlchemy + Alembic
- **Testing**: pytest (unit + integration + smoke), 160 tests
- **Containerization**: Docker Compose for PostgreSQL

### What Works Without Any External API Keys
- Full database setup and migrations
- API server and all endpoints
- Frontend (all 7 pages)
- Exchange calendar generation
- SEC filings and fundamentals ingestion (no key needed)
- All 11 DQ rules and reporting
- All research factor primitives and screeners
- Full backtest engine with persistence (on existing data)
- Complete execution pipeline (dry run mode)
- All CLI commands (with graceful degradation)
- Watchlists, presets, notes, recent activity

### What Requires API Keys
- Production EOD prices and financials (FMP key)
- Corporate actions (Polygon key)
- Higher-rate identifier enrichment (OpenFIGI key)
- Macro data pipeline (BEA, BLS keys)
- Broker integration and live trading (Trading 212 key + `FEATURE_T212_LIVE_SUBMIT=true`)
