# API Keys Setup

## Current Configuration Status

| Key | Variable | Configured | Required For |
|-----|----------|-----------|--------------|
| SEC EDGAR | `SEC_USER_AGENT` | Yes (no key needed) | Filings, company master |
| OpenFIGI | `OPENFIGI_API_KEY` | **No** | Higher rate limit for identifier enrichment |
| Massive/Polygon | `MASSIVE_API_KEY` | **No** | Production EOD prices, splits, dividends |
| FMP | `FMP_API_KEY` | **No** | Production earnings, additional financials |
| Trading 212 | `T212_API_KEY` | **No** | Broker integration |
| BEA | `BEA_API_KEY` | **No** | Macro: GDP, PCE |
| BLS | `BLS_API_KEY` | **No** | Macro: employment, CPI |
| Treasury | `TREASURY_API_BASE_URL` | Yes (public) | Macro: interest rates |

**Impact of missing keys**: Without Massive/Polygon and FMP keys, all price, corporate action, and earnings data comes from `yfinance_dev` (development only). This is the primary blocker for production use.

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
- **Status**: Working at unauthenticated rate. Key would increase throughput.

### Massive/Polygon (Not Configured -- Blocker)
- **Variable**: `MASSIVE_API_KEY`
- **How to get**: https://polygon.io/ (free tier available)
- **Rate limit**: 5 requests/minute (free), higher with paid plan
- **Status**: Adapter exists (`massive_adapter.py`) but not tested. This is a primary blocker: without it, all price data comes from yfinance_dev.

### Financial Modeling Prep / FMP (Not Configured -- Blocker)
- **Variable**: `FMP_API_KEY`
- **How to get**: https://financialmodelingprep.com/developer/docs/
- **Rate limit**: Varies by plan
- **Status**: Adapter exists (`fmp_adapter.py`) but not tested. This is a blocker for production earnings data.

### Trading 212 (Not Configured)
- **Variable**: `T212_API_KEY`
- **How to get**: Trading 212 app -> Settings -> API
- **Note**: Demo and Live are separate API keys. Demo should be used first.
- **Status**: Adapter exists (`trading212_adapter.py`) but not tested. Live submission is disabled by default regardless of key.

### BEA (Not Configured)
- **Variable**: `BEA_API_KEY`
- **How to get**: https://apps.bea.gov/API/signup/
- **Status**: Adapter exists (`bea_adapter.py`) as skeleton. Not yet functional.

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

# Primary blockers -- need these for production data
MASSIVE_API_KEY=your_polygon_key_here
FMP_API_KEY=your_fmp_key_here

# Nice to have
OPENFIGI_API_KEY=your_openfigi_key_here
T212_API_KEY=your_trading212_key_here
BEA_API_KEY=your_bea_key_here
BLS_API_KEY=your_bls_key_here

# Feature flags
FEATURE_T212_LIVE_SUBMIT=false  # Keep this false until ready for live trading
```
