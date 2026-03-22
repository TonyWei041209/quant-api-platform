# Source Matrix

| Source | Purpose | Layer | Phase 1 Status | Notes |
|--------|---------|-------|----------------|-------|
| SEC EDGAR | Company master, filings, XBRL facts | Ingestion | Implemented | 10 req/s fair access |
| OpenFIGI | Identifier mapping (FIGI, composite FIGI) | Ingestion | Implemented | 20 req/min unauthenticated |
| Massive/Polygon | EOD bars (raw), splits, dividends | Ingestion | Implemented | adjusted=false enforced |
| FMP | Financials, earnings calendar, prices (fallback) | Ingestion | Implemented | API key required |
| BEA | GDP, PCE, macro indicators | Ingestion | Skeleton | Phase 2 |
| BLS | Employment, CPI, PPI | Ingestion | Skeleton | Phase 2 |
| Treasury | Interest rates, fiscal data | Ingestion | Skeleton | Phase 2 |
| Trading 212 | Account/positions/orders (read-only) | Execution | Implemented (read-only) | Live submit disabled |
