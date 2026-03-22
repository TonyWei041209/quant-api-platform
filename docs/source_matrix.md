# Source Matrix

| Source | Purpose | Layer | Status | Notes |
|--------|---------|-------|--------|-------|
| SEC EDGAR | Company master, filings, XBRL facts | Ingestion | **Live** | 10 req/s, no key needed |
| OpenFIGI | Identifier mapping (FIGI, composite FIGI) | Ingestion | **Live** | Free tier, no key needed |
| yfinance (DEV ONLY) | EOD bars, splits, dividends, earnings | Ingestion | **Dev** | NOT production; tagged source='yfinance_dev' |
| Massive/Polygon | EOD bars (raw), splits, dividends | Ingestion | Skeleton | Needs MASSIVE_API_KEY |
| FMP | Financials, earnings calendar, prices | Ingestion | Skeleton | Needs FMP_API_KEY |
| BEA | GDP, PCE, macro indicators | Ingestion | Skeleton | Phase 3 |
| BLS | Employment, CPI, PPI | Ingestion | Skeleton | Phase 3 |
| Treasury | Interest rates, fiscal data | Ingestion | Skeleton | Phase 3 |
| Trading 212 | Account/positions/orders (read-only) | Execution | Skeleton | Needs T212_API_KEY |

## Phase 2A Data Provenance

| Data Type | Source Used | Production Source | Verified |
|-----------|-----------|-------------------|----------|
| EOD prices | yfinance_dev | Massive/Polygon | Yes — 6248 bars |
| Splits | yfinance_dev | Massive/Polygon | Yes — NVDA 10:1 verified |
| Dividends | yfinance_dev | Massive/Polygon | Yes — AAPL quarterly verified |
| Earnings | yfinance_dev | FMP | Yes — 75 events with EPS |
| Filings | SEC EDGAR | SEC EDGAR | Yes — 3286 filings |
| Fundamentals | SEC companyfacts | SEC companyfacts + FMP | Yes — 2636 facts |
| Identifiers | SEC + OpenFIGI | SEC + OpenFIGI | Yes — FIGI enriched |
