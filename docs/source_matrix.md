# Source Matrix

## Adapter Status

| Source | Adapter File | Purpose | Status | Notes |
|--------|-------------|---------|--------|-------|
| SEC EDGAR | `sec_adapter.py` | Company master, filings, XBRL companyfacts | **Production** | 10 req/s, no key needed |
| OpenFIGI | `openfigi_adapter.py` | Identifier mapping (FIGI, composite FIGI) | **Production** | No key configured (unauthenticated rate limit) |
| yfinance (DEV ONLY) | `dev_load_prices.py` | EOD bars, splits, dividends, earnings | **Dev only** | Tagged `source='yfinance_dev'`. NOT for production. |
| Massive/Polygon | `massive_adapter.py` | EOD bars (raw), splits, dividends | **Skeleton** | Adapter exists. Needs `MASSIVE_API_KEY`. Not configured. |
| FMP | `fmp_adapter.py` | Financials, earnings calendar, prices | **Skeleton** | Adapter exists. Needs `FMP_API_KEY`. Not configured. |
| BEA | `bea_adapter.py` | GDP, PCE, macro indicators | **Skeleton** | Adapter exists. Needs `BEA_API_KEY`. Not configured. |
| BLS | `bls_adapter.py` | Employment, CPI, PPI | **Skeleton** | Adapter exists. Needs `BLS_API_KEY`. Not configured. |
| Treasury | `treasury_adapter.py` | Interest rates, fiscal data | **Skeleton** | Adapter exists. Public endpoint, no key needed. |
| Trading 212 | `trading212_adapter.py` | Account, positions, orders (read-only) | **Skeleton** | Adapter exists. Needs `T212_API_KEY`. Not configured. |

## Current Data in Database

| Data Type | Source Used | Tagged As | Production Source | Verified |
|-----------|-----------|-----------|-------------------|----------|
| EOD prices | yfinance | `yfinance_dev` | Massive/Polygon | Yes -- ~6248 bars for 4 instruments |
| Splits | yfinance | `yfinance_dev` | Massive/Polygon | Yes -- NVDA 10:1 verified |
| Dividends | yfinance | `yfinance_dev` | Massive/Polygon | Yes -- AAPL quarterly verified |
| Earnings | yfinance | `yfinance_dev` | FMP | Yes -- ~75 events with EPS |
| Filings | SEC EDGAR | `sec` | SEC EDGAR | Yes -- ~3286 filings |
| Fundamentals | SEC companyfacts | `sec` | SEC companyfacts | Yes -- ~2636 facts, ~195 periods |
| Identifiers | SEC + OpenFIGI | `sec` / `openfigi` | SEC + OpenFIGI | Yes -- FIGI enriched |
| Calendar | Internal | `internal` | Internal | Yes -- NYSE/NASDAQ 2020-2026 |
| Macro | Not loaded | -- | BEA/BLS/Treasury | Not started |
| Broker data | Not loaded | -- | Trading 212 | Not started |

## Production vs Dev Classification

**Production-ready data (real sources, no replacement needed)**:
- SEC EDGAR filings
- SEC companyfacts financials
- OpenFIGI identifiers
- Exchange calendar

**Dev-only data (yfinance_dev -- MUST be replaced for production)**:
- EOD prices -> replace with Massive/Polygon
- Corporate actions (splits, dividends) -> replace with Massive/Polygon
- Earnings events -> replace with FMP

**Not yet loaded (skeleton adapters only)**:
- Macro data (BEA, BLS, Treasury)
- Broker account data (Trading 212)

## Blocker: API Keys Required

To move from dev to production data, the following API keys must be configured in `.env`:

| Key | Purpose | Replaces |
|-----|---------|----------|
| `MASSIVE_API_KEY` | Polygon.io EOD prices, splits, dividends | yfinance_dev prices/corporate_actions |
| `FMP_API_KEY` | Earnings calendar, additional financials | yfinance_dev earnings |
| `OPENFIGI_API_KEY` | Higher rate limit for identifier enrichment | Unauthenticated access |
| `T212_API_KEY` | Broker integration | No broker data |
| `BEA_API_KEY` | Macro: GDP, PCE | No macro data |
| `BLS_API_KEY` | Macro: employment, CPI | No macro data |
