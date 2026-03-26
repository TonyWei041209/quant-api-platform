# Quant API Platform v1.5.0 Release Notes

**Release Date**: 2026-03-26
**Version**: v1.5.0
**Status**: Production Release

---

## Overview

Quant API Platform v1.5.0 is the first production release of an API-first, PIT-aware quantitative stock analysis and research platform focused on US equities.

This release delivers a complete research-to-execution platform with:
- Canonical data layer with multi-source ingestion
- PIT-safe research and analysis tools
- Backtest engine with persistence and metrics
- Controlled execution pipeline with mandatory approval gates
- Daily research workflow with watchlists, presets, and notes
- React-based frontend with bilingual support (EN/中文)

---

## Data Source Matrix

| Source | Role | Status |
|--------|------|--------|
| FMP (Financial Modeling Prep) | Primary: EOD prices, financials, profiles | Production |
| SEC EDGAR | Truth: filings, companyfacts, PIT validation | Production |
| Polygon / Massive | Primary: corporate actions; Secondary: raw price validation | Production |
| OpenFIGI | Identifier enrichment (FIGI mapping) | Production |
| Trading 212 | Broker: readonly account/positions/orders | Verified (Basic Auth) |
| BEA / BLS / Treasury | Macro data skeletons | Phase 2 |

---

## Core Capabilities

### Data Layer
- 19 canonical database tables with UUID PKs and timestamptz
- Security Master with identifier history and ticker history
- Exchange calendar (NYSE/NASDAQ 2020-2026)
- Raw unadjusted EOD prices (source-tagged, raw_payload preserved)
- Corporate actions (splits, dividends) from Polygon
- SEC filings and companyfacts
- Financial periods and standardized facts
- Source run tracking and data issue persistence

### Research Layer
- 9 factor primitives (returns, volatility, drawdown, momentum, valuation, etc.)
- 4 screeners (liquidity, returns, fundamentals, composite rank)
- Earnings event study (1/3/5/10 day windows)
- PIT-safe financial views (reported_at enforcement)
- Split-adjusted and total-return-adjusted price derivation

### Backtest Layer
- Bar-by-bar simulation engine
- Cost model (commission + slippage)
- Portfolio construction (equal weight, max positions)
- Time splits (simple, walk-forward, expanding window)
- Persistent backtest runs with metrics, trades, NAV series
- Queryable results via API

### Execution Layer
- Controlled pipeline: Signal → Intent → Draft → Approval → Submit
- Risk checks: position size, notional, duplicates, stale intents, trading day
- Approval gate cannot be bypassed
- Trading 212 integration: readonly verified, live submit disabled by default
- FEATURE_T212_LIVE_SUBMIT=false by default

### Daily Workflow
- Daily Research Home dashboard
- Watchlist groups with instrument management
- Saved research/backtest presets
- Research notes (thesis, observation, risk, follow-up)
- Recent activity and continue-where-you-left-off flow

### Observability
- 11 DQ rules (OHLC, non-negative, duplicates, trading days, corporate actions, PIT, cross-source, stale, overlap, orphan, raw/adj contamination)
- Source run tracking with counters
- Data issue persistence and reporting
- CLI status and reporting commands

### Frontend
- React 18 + Vite + Tailwind CSS
- 7 pages: Dashboard, Instruments, Research, Backtests, Execution, Data Quality, Settings
- Bilingual support (English / 中文)
- Dark mode support
- Responsive layout

### API & CLI
- 25+ REST API endpoints
- 15+ CLI commands (ingestion, DQ, status, reporting, backtest)
- FastAPI with automatic OpenAPI documentation

---

## Security Boundaries

This platform is a **controlled research and execution system**, not an unrestricted trading bot.

- Live order submission is **disabled by default**
- All orders must pass through the approval gate
- Research and execution layers are decoupled
- Risk checks are mandatory before any broker submission
- Trading 212 integration is readonly by default
- Demo/paper trading is prioritized over live trading

---

## Known Limitations

1. **External API keys required**: FMP, Polygon, and Trading 212 keys must be configured for full functionality
2. **Macro data**: BEA/BLS/Treasury adapters are skeletons (Phase 2)
3. **Market scope**: US equities only (no crypto, futures, options, multi-market)
4. **Data granularity**: Daily EOD only (no intraday/tick/HFT)
5. **FMP free tier**: Earnings calendar and some endpoints require paid plan
6. **Trading 212**: Live submit requires explicit feature flag enablement

## What Works Without Any External API Keys

- Database schema and migrations
- API server and all endpoints
- Frontend (all pages)
- CLI commands (with graceful degradation)
- DQ engine (on existing data)
- Backtest engine (on existing data)
- Execution pipeline (intent/draft/approval flow)
- Watchlists, presets, notes, recent activity

---

## Test Summary

- **160 tests passing** (unit, integration, smoke, API, DQ, PIT, backtest, execution)
- Frontend build verified
- All API endpoints verified
- Real data ingestion validated (AAPL, MSFT, NVDA, SPY)
- Trading 212 live readonly validated

---

## Version History

| Version | Milestone |
|---------|-----------|
| Phase 1 | Project skeleton, Docker, schema, Alembic |
| Phase 1.5 | Real PostgreSQL + SEC/OpenFIGI + DQ hardening |
| Phase 2A | Real prices + earnings + event study |
| Phase 2B | Research layer enhancement |
| Phase 2C | Execution layer + risk control |
| Phase 3A | Backtest engine |
| Phase 3B | Observability + DQ expansion |
| Phase 4 | Constitution compliance + backtest persistence |
| Phase 5 | Production readiness + DQ API |
| Phase 6 | Daily workflow infrastructure |
| Phase 7 | Real usage validation + friction fixing |
| Phase 8 | Production data cutover + broker validation |
| **v1.5.0** | **Production release** |
