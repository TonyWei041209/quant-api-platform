# Project Summary

## Project Name
quant-api-platform

## Positioning
- API-first, official-data-only quantitative stock analysis and research platform
- US equities as primary market
- Phase 1 focus: data layer, research layer, controlled execution skeleton

## Current Phase: Phase 1 — Foundation

### What Phase 1 IS:
- Complete database schema for securities, prices, fundamentals, and events
- Four production adapters: SEC, OpenFIGI, Massive/Polygon, FMP
- Eight ingestion jobs covering security master, prices, corporate actions, filings, earnings, fundamentals
- Data quality framework with 6+ rules
- Research layer: PIT views, adjusted prices, earnings event study
- Trade 212 read-only integration (account/positions/orders sync)
- Order intent → draft → approval workflow
- Full API surface for instruments, research, and execution

### What Phase 1 is NOT:
- NOT an automated trading bot
- NOT a live trading system (live submit disabled by default)
- NOT a web scraping platform — all data from official APIs only
- NOT a frontend application
- NOT a minute-level data system
- NOT a complex strategy optimizer

### Trade 212 Phase 1 Boundary:
1. Account/cash/positions/orders: read-only sync only
2. Instrument metadata fetch (if API permits)
3. order_intent + order_draft data models
4. Demo adapter skeleton
5. Live submit disabled by default (FEATURE_T212_LIVE_SUBMIT=false)
6. Human approval required for all order drafts

### Key Architecture Decisions:
- `instrument_id` (UUID) is the universal join key, never ticker
- All data retains `source`, `ingested_at`, `raw_payload`
- Point-in-time (PIT) enforced via `reported_at` timestamps
- Raw/split-adjusted/total-return prices are strictly layered
- Research and execution layers fully decoupled
