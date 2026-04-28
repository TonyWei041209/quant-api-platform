# API Keys Setup

## Current Configuration Status (updated 2026-04-16)

| Key | Variable | Configured | Required For |
|-----|----------|-----------|--------------|
| SEC EDGAR | `SEC_USER_AGENT` | Yes (no key needed) | Filings, company master |
| OpenFIGI | `OPENFIGI_API_KEY` | **No** | Higher rate limit for identifier enrichment |
| Massive/Polygon | `MASSIVE_API_KEY` | **Yes** | **Production EOD prices, splits, dividends — primary path** |
| FMP | `FMP_API_KEY` | **Yes** | **Production profile / fundamentals / earnings; fallback EOD** |
| Trading 212 | `T212_API_KEY` | Yes | Broker readonly truth (positions, orders, account) |
| BEA | `BEA_API_KEY` | **No** | Macro: GDP, PCE |
| BLS | `BLS_API_KEY` | **No** | Macro: employment, CPI |
| Treasury | `TREASURY_API_BASE_URL` | Yes (public) | Macro: interest rates |

**Status**: With `MASSIVE_API_KEY` and `FMP_API_KEY` configured, the platform CAN run on production data. `yfinance_dev` is **dev-only** and must NEVER be used as a production data source.

## Source Hierarchy (production)

For new ingestion, prefer:
1. **Polygon (Massive)** — primary path for EOD bars, splits, dividends
2. **FMP** — primary path for profile/fundamentals; fallback path for EOD
3. **SEC EDGAR** — primary path for filings and XBRL fundamentals
4. **yfinance_dev** — DEV ONLY, never production. Tagged `source='yfinance_dev'` for traceability so DQ rules can reject it from any production-grade view.

For Scanner Research Universe expansion (planned but not yet shipped to prod), use Polygon as the primary EOD source and FMP for profile lookups; do NOT use yfinance_dev.

## Key Details

### SEC EDGAR (Production -- Active)
- **Variable**: `SEC_USER_AGENT`
- **Format**: `YourName your@email.com`
- **How to get**: No registration needed, but SEC requires a User-Agent string identifying you
- **Rate limit**: 10 requests/second (fair access policy)
- **Status**: Working. Filings and companyfacts are production data.

### OpenFIGI (Production -- Limited)
- **Variable**: `OPENFIGI_API_KEY`
- **How to get**: https://www.openfigi.com/api
- **Rate limit**: 20 requests/minute (unauthenticated), higher with key
- **Status**: Working at unauthenticated rate. Key would increase throughput. Not currently a blocker for any production flow.

### Massive/Polygon (Production -- Active)
- **Variable**: `MASSIVE_API_KEY`
- **How to get**: https://polygon.io/ (free tier available; Stocks Starter $29/mo for unlimited + RT)
- **Adapter base URL**: `api.polygon.io`
- **Adapter**: `libs/adapters/massive_adapter.py`
- **Endpoints used**:
  - `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}` — daily aggregate bars
  - `/v3/reference/splits` — splits
  - `/v3/reference/dividends` — dividends
- **Rate limit**: configured at 5 req/sec in code (`RateLimiter(max_requests=5, period_seconds=1.0)`)
- **Status**: Configured in both local `.env` and production Cloud Run secret. `sync_eod_prices.py` ingestion module wired. Production EOD data partially loaded for the 4 large caps; expansion to 30-50 instruments is pending an explicit decision.

### Financial Modeling Prep / FMP (Production -- Active)
- **Variable**: `FMP_API_KEY`
- **How to get**: https://financialmodelingprep.com/developer/docs/
- **Adapter**: `libs/adapters/fmp_adapter.py` (uses FMP `stable` endpoints, not legacy v3)
- **Endpoints used**:
  - `get_eod_prices(symbol, from, to)` — EOD prices (fallback)
  - `get_profile(symbol)` — issuer name, exchange, sector, currency
  - `get_income_statement` / `get_balance_sheet` / `get_cash_flow` — fundamentals
  - `get_earnings_calendar(from, to)` — earnings events
- **Rate limit**: configured at 5 req/sec in code
- **Status**: Configured in both local `.env` and production Cloud Run secret. Used as fallback EOD source and primary profile/fundamentals source.

### Trading 212 (Production -- Readonly)
- **Variable**: `T212_API_KEY` (and `T212_API_SECRET` if present)
- **How to get**: Trading 212 app -> Settings -> API
- **Note**: Demo and Live are separate API keys. Production uses Live with `--no-demo` flag in the sync job.
- **Status**: Configured. Used by `quant-sync-t212` Cloud Run Job (schedule `0 8,21 * * 1-5` ENABLED) to populate `broker_*_snapshot` tables. **Live submission stays disabled by `FEATURE_T212_LIVE_SUBMIT=false` regardless of key validity.**

### BEA (Not Configured)
- **Variable**: `BEA_API_KEY`
- **How to get**: https://apps.bea.gov/API/signup/
- **Status**: Adapter exists (`bea_adapter.py`) as skeleton. Not yet functional. Macro data is not currently exposed via any API endpoint.

### BLS (Not Configured)
- **Variable**: `BLS_API_KEY`
- **How to get**: https://data.bls.gov/registrationEngine/
- **Status**: Adapter exists (`bls_adapter.py`) as skeleton. Not yet functional.

### Treasury (Public Endpoint)
- **Variable**: `TREASURY_API_BASE_URL`
- **Note**: No API key needed, public endpoint
- **Status**: Adapter exists (`treasury_adapter.py`) as skeleton. Not yet functional.

## .env Configuration

Add keys to your `.env` file:

```bash
# Required (already working)
SEC_USER_AGENT="YourName your@email.com"

# Production data sources
MASSIVE_API_KEY=...   # Polygon
FMP_API_KEY=...

# Broker (readonly only — live submit gated separately)
T212_API_KEY=...

# Nice to have
OPENFIGI_API_KEY=...
BEA_API_KEY=...
BLS_API_KEY=...

# Feature flags — DO NOT change without explicit deliberation
FEATURE_T212_LIVE_SUBMIT=false
```

## Forward note: Scanner Research Universe production seed

If/when production seed of an expanded Scanner universe (~30-50 instruments) is approved:

- **Use Polygon** for historical and incremental daily EOD bars — primary path
- **Use FMP `get_profile`** for issuer name / exchange / sector enrichment — primary path
- **Do NOT use yfinance_dev** — it is dev-only by policy. DQ rules treat `source='yfinance_dev'` as untrusted
- A daily incremental Cloud Run Job (mirroring `quant-sync-t212`'s pattern) is required to keep prices fresh; one-shot seed without ongoing sync would let the universe go stale and degrade Scanner quality
