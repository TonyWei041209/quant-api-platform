# Status

## Last Updated: 2026-03-22 (Phase 2A)

### Phase 2A — Price & Event Study Minimum Closed Loop

#### Completed (Real, Verified)
- [x] Real EOD prices ingested: AAPL, MSFT, NVDA, SPY (6248 bars, 2020-present)
- [x] Corporate actions ingested: 20 splits + 367 dividends
- [x] Earnings events ingested: 75 events (AAPL/MSFT/NVDA) with EPS actual/estimate
- [x] DQ-1 through DQ-6 all running on real data (6 rules, 0 issues)
- [x] Split-adjusted prices verified: NVDA 10:1 split (Jun 2024) adj_factor=10.0
- [x] Total-return-adjusted prices verified: AAPL with dividend adjustment
- [x] Event study on real data: AAPL/MSFT/NVDA post-earnings 1/3/5/10-day returns
- [x] API serving real prices, financials, event study results
- [x] 60+ tests passing (unit + smoke + integration)

#### Real Data in Database
| Table | Count | Source |
|-------|-------|--------|
| instrument | 4 | SEC |
| instrument_identifier | ~20 | SEC + OpenFIGI |
| ticker_history | 4 | SEC |
| exchange_calendar | 3654 | Internal (NYSE/NASDAQ 2020-2026) |
| price_bar_raw | 6248 | yfinance_dev (raw unadjusted) |
| corporate_action | 387 | yfinance_dev (20 splits, 367 dividends) |
| filing | ~3286 | SEC EDGAR |
| earnings_event | 75 | yfinance_dev |
| financial_period | 195 | SEC companyfacts |
| financial_fact_std | 2636 | SEC companyfacts |
| source_run | ~20 | All jobs |
| data_issue | 0 | DQ (clean data) |

#### Data Source Note
Phase 2A uses `yfinance` as a DEV-ONLY data loader for prices, corporate actions, and earnings. This is NOT a production data source. All data is tagged with `source='yfinance_dev'`. Production will use Massive/Polygon or FMP with proper API keys.

#### Blockers
- No Massive/Polygon API key — production price source not yet configured
- No FMP API key — production earnings source not yet configured
- No T212 API key — broker integration not yet testable

### Next Steps
1. Obtain Massive/Polygon API key → replace yfinance_dev with production source
2. Obtain FMP API key → production earnings calendar
3. Wire up T212 demo API key → test read-only broker sync
4. Add factor computation (Phase 3)
