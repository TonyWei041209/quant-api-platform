# API Keys Setup

## Required API Keys

### SEC EDGAR
- **Variable**: `SEC_USER_AGENT`
- **Format**: `YourName your@email.com`
- **How to get**: No registration needed, but SEC requires a User-Agent identifying you
- **Rate limit**: 10 requests/second (fair access policy)

### OpenFIGI
- **Variable**: `OPENFIGI_API_KEY`
- **How to get**: https://www.openfigi.com/api
- **Rate limit**: 20 requests/minute (unauthenticated), higher with key

### Massive/Polygon
- **Variable**: `MASSIVE_API_KEY`
- **How to get**: https://polygon.io/ (free tier available)
- **Rate limit**: 5 requests/minute (free), higher with paid plan

### Financial Modeling Prep (FMP)
- **Variable**: `FMP_API_KEY`
- **How to get**: https://financialmodelingprep.com/developer/docs/
- **Rate limit**: Varies by plan

### Trading 212
- **Variable**: `T212_API_KEY`
- **How to get**: Trading 212 app → Settings → API
- **Note**: Demo and Live are separate API keys

### BEA (Phase 2)
- **Variable**: `BEA_API_KEY`
- **How to get**: https://apps.bea.gov/API/signup/

### BLS (Phase 2)
- **Variable**: `BLS_API_KEY`
- **How to get**: https://data.bls.gov/registrationEngine/

### Treasury (Phase 2)
- **Variable**: `TREASURY_API_BASE_URL`
- **Note**: No API key needed, public endpoint
