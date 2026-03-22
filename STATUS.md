# Status

## Last Updated: 2026-03-22 (Phase 1.5)

### Phase 1.5 — Engineering Hardening & Real Integration

#### Completed (Real, Verified)
- [x] PostgreSQL 16 installed and running locally
- [x] Alembic migration generated and applied — 19 tables created
- [x] Exchange calendar populated: NYSE/NASDAQ 2020-2026 (3654 days, 136 holidays)
- [x] Security master bootstrapped from SEC: AAPL, MSFT, NVDA, SPY
- [x] OpenFIGI enrichment completed — FIGI/composite/share-class identifiers written
- [x] SEC filings synced: ~3286 filings across 4 tickers
- [x] SEC companyfacts fundamentals synced: AAPL (907 facts/67 periods), MSFT (914/65), NVDA (815/63)
- [x] DQ framework running with all 6 rules (no stubs)
- [x] API returns real data: instruments, identifiers, PIT financials
- [x] 46 tests passing: 34 unit + 5 smoke + 7 integration

#### Real Data in Database
| Table | Count | Source |
|-------|-------|--------|
| instrument | 4 | SEC |
| instrument_identifier | ~20 | SEC + OpenFIGI |
| ticker_history | 4 | SEC |
| exchange_calendar | 3654 | Internal |
| filing | ~3286 | SEC EDGAR |
| financial_period | 195 | SEC companyfacts |
| financial_fact_std | 2636 | SEC companyfacts |
| source_run | ~10 | All jobs |

#### Not Yet Populated (Need API Keys)
- price_bar_raw — needs MASSIVE_API_KEY or FMP_API_KEY
- corporate_action — needs MASSIVE_API_KEY
- earnings_event — needs FMP_API_KEY
- broker_*_snapshot — needs T212_API_KEY

#### Blockers
- No Massive/Polygon API key — cannot sync EOD prices
- No FMP API key — cannot sync earnings calendar
- No Trading 212 API key — cannot sync broker data
- Docker not installed — using local PostgreSQL instead

### Next Steps
1. Obtain Massive/Polygon API key for EOD price ingestion
2. Obtain FMP API key for earnings calendar
3. Once prices are in: run full DQ checks and event study on real market data
4. Wire up Trading 212 demo API key
5. Install Docker for containerized deployment
