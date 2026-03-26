# Source Matrix

## Production Data Source Hierarchy

| Priority | Source | Role | Key Required | Status |
|----------|--------|------|-------------|--------|
| **PRIMARY** | FMP (stable API) | EOD prices, financials, profile | `FMP_API_KEY` | **Active** |
| **PRIMARY** | SEC EDGAR | Filings, companyfacts, PIT truth | No (User-Agent only) | **Active** |
| **SECONDARY** | Massive/Polygon | Raw EOD bars, splits, dividends | `MASSIVE_API_KEY` | **Configured** |
| **ENRICHMENT** | OpenFIGI | Identifier mapping (FIGI) | Optional (higher rate with key) | **Active** |
| **DEV ONLY** | yfinance_dev | Dev/test convenience loader | None | **Dev only** |
| **SKELETON** | BEA | GDP, macro indicators | `BEA_API_KEY` | Skeleton |
| **SKELETON** | BLS | Employment, CPI | `BLS_API_KEY` | Skeleton |
| **SKELETON** | Treasury | Interest rates, fiscal | None (public) | Skeleton |
| **SKELETON** | Trading 212 | Broker readonly sync | `T212_API_KEY` | Skeleton |

## Adapter Details

| Source | Adapter File | Endpoints Used | Free Tier |
|--------|-------------|----------------|-----------|
| FMP | `fmp_adapter.py` | `/stable/profile`, `/stable/historical-price-eod/full`, `/stable/income-statement`, `/stable/balance-sheet-statement`, `/stable/cash-flow-statement` | 250 req/day |
| SEC | `sec_adapter.py` | company_tickers, submissions, companyfacts | Unlimited (10 req/s) |
| Polygon | `massive_adapter.py` | `/v2/aggs`, `/v3/reference/splits`, `/v3/reference/dividends` | 5 req/min |
| OpenFIGI | `openfigi_adapter.py` | `/v3/mapping` | 25 req/min (no key) |
| yfinance | `dev_load_prices.py` | Python yfinance library | N/A (unofficial) |

## Current Data in Database

| Data Type | Primary Source | Fallback Source | Tagged As | Production-Safe |
|-----------|---------------|----------------|-----------|-----------------|
| EOD prices | **FMP** | yfinance_dev (legacy) | `fmp` / `yfinance_dev` | FMP: Yes |
| Splits/dividends | Polygon | yfinance_dev (legacy) | `yfinance_dev` | Polygon: pending validation |
| Filings | SEC EDGAR | — | `sec` | Yes |
| Fundamentals | **FMP** + SEC | — | `fmp` / `sec` | Yes |
| Earnings | yfinance_dev | FMP (paid tier) | `yfinance_dev` | FMP free tier: limited |
| Identifiers | SEC + OpenFIGI | — | `sec` / `openfigi` | Yes |
| Calendar | Internal | — | `internal_calendar` | Yes |

## CLI Commands for Data Ingestion

| Command | Source | Production Path |
|---------|--------|----------------|
| `sync-eod-fmp` | FMP | **Yes — recommended** |
| `sync-fundamentals-fmp` | FMP | **Yes — recommended** |
| `bootstrap-security-master` | SEC + OpenFIGI | Yes |
| `populate-calendar` | Internal | Yes |
| `sync-eod-prices` | Massive/Polygon | Yes (when key configured) |
| `dev-load-prices` | yfinance | **No — dev only** |

## Important Notes

1. **yfinance_dev is NOT a production source.** It is an unofficial wrapper that may break without notice. Data tagged `source='yfinance_dev'` should be replaced with FMP or Polygon data for production use.

2. **FMP free tier limitations:** Earnings calendar and historical splits/dividends are not available on the free plan. Use Polygon for splits/dividends.

3. **Source coexistence:** FMP and yfinance_dev data can coexist in the same tables (differentiated by `source` column). Queries should prefer FMP data when available.
