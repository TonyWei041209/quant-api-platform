# Project Summary

## Project Name
quant-api-platform

## Positioning
- API-first, official-data-only quantitative stock analysis and research platform
- US equities as primary market

## Current Phase: Phase 2A — Price & Event Study Closed Loop

### What has been REALLY integrated and verified:
- SEC EDGAR: company tickers, submissions, companyfacts (no key needed)
- OpenFIGI: identifier mapping (free tier, no key needed)
- Exchange calendar: NYSE/NASDAQ 2020-2026 (3654 trading days)
- Real price data: 6248 EOD bars for AAPL/MSFT/NVDA/SPY (2020-present)
- Corporate actions: 20 splits + 367 dividends (real data)
- Earnings events: 75 events with EPS actual/estimate
- SEC fundamentals: 2636 financial facts across 195 periods
- Split-adjusted prices: verified on NVDA 10:1 split
- Total-return-adjusted prices: verified with AAPL dividends
- Event study: post-earnings returns on real data (1/3/5/10-day windows)
- DQ framework: 6 rules running on real data, 0 issues
- API: instruments, research summary, prices, event study all serving real DB data
- Tests: 60+ passing (unit + smoke + integration with real data)

### Data source note:
Phase 2A uses yfinance as a DEV-ONLY data loader. All price/earnings/corporate action data is real market data, tagged with source='yfinance_dev'. Production deployment will use Massive/Polygon or FMP with proper API keys. The schema, pipeline, and research layer are production-ready — only the data source adapter will change.

### Key Architecture Decisions:
- `instrument_id` (UUID) is the universal join key, never ticker
- All data retains `source`, `ingested_at`, `raw_payload`
- Point-in-time (PIT) enforced via `reported_at` timestamps
- Raw/split-adjusted/total-return prices strictly layered
- Research and execution layers fully decoupled
- Live trading disabled by default (FEATURE_T212_LIVE_SUBMIT=false)
