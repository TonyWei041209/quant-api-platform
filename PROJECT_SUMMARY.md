# Project Summary

## Project Name
quant-api-platform

## Positioning
- API-first, official-data-only quantitative stock analysis and research platform
- US equities as primary market
- Phase 1.5: foundation hardened with real data integration

## Current Phase: Phase 1.5 — Hardened Foundation

### What has been REALLY integrated and verified:
- SEC EDGAR: company tickers, submissions, companyfacts (XBRL) — no API key needed
- OpenFIGI: identifier mapping — working with free tier (no key)
- PostgreSQL 16: local install, Alembic migration applied, 19 tables
- Exchange calendar: NYSE/NASDAQ 2020-2026 populated
- Real data in DB: 4 instruments (AAPL, MSFT, NVDA, SPY), ~3286 filings, 2636 financial facts
- API serving real data from database
- DQ rules running against real data (6 rules, 0 stubs)
- 46 tests passing (unit + smoke + integration)

### What is still SKELETON / needs API keys:
- EOD prices (needs Massive/Polygon or FMP key)
- Corporate actions (needs Massive key)
- Earnings events (needs FMP key)
- Trading 212 sync (needs T212 key)
- Macro data (Phase 2)

### Key Architecture Decisions:
- `instrument_id` (UUID) is the universal join key, never ticker
- All data retains `source`, `ingested_at`, `raw_payload`
- Point-in-time (PIT) enforced via `reported_at` timestamps
- Raw/split-adjusted/total-return prices are strictly layered
- Research and execution layers fully decoupled
- Live trading disabled by default (FEATURE_T212_LIVE_SUBMIT=false)
