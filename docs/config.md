# Configuration Reference

## Environment Variables

All environment variables are defined in `.env.example`. Copy to `.env` and configure for your environment.

### Database

| Variable | Description | Required | Default | Module |
|----------|-------------|----------|---------|--------|
| `POSTGRES_USER` | PostgreSQL user name | Yes | `quant` | `libs/db/session.py` |
| `POSTGRES_PASSWORD` | PostgreSQL password | Yes | `quant_dev_password` | `libs/db/session.py` |
| `POSTGRES_DB` | Database name | Yes | `quant_platform` | `libs/db/session.py` |
| `POSTGRES_HOST` | Database host | Yes | `localhost` | `libs/db/session.py` |
| `POSTGRES_PORT` | Database port | Yes | `5432` | `libs/db/session.py` |

### Application

| Variable | Description | Required | Default | Module |
|----------|-------------|----------|---------|--------|
| `APP_ENV` | Environment name (`development`, `production`) | Optional | `development` | `libs/core/logging.py` |
| `APP_LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | Optional | `INFO` | `libs/core/logging.py` |

### Data Source API Keys

| Variable | Description | Required | Default | Module |
|----------|-------------|----------|---------|--------|
| `SEC_USER_AGENT` | SEC EDGAR user agent string (required by SEC fair-use policy, format: `YourName your@email.com`) | Yes (for SEC ingestion) | None | `libs/adapters/sec_adapter.py` |
| `OPENFIGI_API_KEY` | OpenFIGI API key for higher rate limits | Optional | Empty (unauthenticated access) | `libs/adapters/openfigi_adapter.py` |
| `MASSIVE_API_KEY` | Polygon.io / Massive API key for production EOD prices, splits, dividends | Optional | Empty (adapter non-functional) | `libs/adapters/massive_adapter.py` |
| `FMP_API_KEY` | Financial Modeling Prep API key for earnings data | Optional | Empty (adapter non-functional) | `libs/adapters/fmp_adapter.py` |
| `BEA_API_KEY` | Bureau of Economic Analysis API key for macro data (GDP, PCE) | Optional | Empty (adapter non-functional) | `libs/adapters/bea_adapter.py` |
| `BLS_API_KEY` | Bureau of Labor Statistics API key for employment, CPI, PPI | Optional | Empty (adapter non-functional) | `libs/adapters/bls_adapter.py` |
| `TREASURY_API_BASE_URL` | US Treasury fiscal data API base URL | Optional | `https://api.fiscaldata.treasury.gov/services/api/fiscal_service` | `libs/adapters/treasury_adapter.py` |

### Trading 212 (Broker)

| Variable | Description | Required | Default | Module |
|----------|-------------|----------|---------|--------|
| `T212_API_KEY` | Trading 212 API key | Optional | Empty (adapter non-functional) | `libs/adapters/trading212_adapter.py` |
| `T212_API_SECRET` | Trading 212 API secret | Optional | Empty | `libs/adapters/trading212_adapter.py` |
| `T212_DEMO_BASE_URL` | Trading 212 demo API base URL | Optional | `https://demo.trading212.com/api/v0` | `libs/adapters/trading212_adapter.py` |
| `T212_LIVE_BASE_URL` | Trading 212 live API base URL | Optional | `https://live.trading212.com/api/v0` | `libs/adapters/trading212_adapter.py` |

---

## Feature Flags

| Flag | Default | Description | Module |
|------|---------|-------------|--------|
| `FEATURE_T212_LIVE_SUBMIT` | `false` | Controls whether approved order drafts are actually submitted to Trading 212. When `false` (default), the entire execution pipeline works (intent, draft, risk check, approve) but no live order is sent to the broker. Set to `true` only when ready for live trading with all safeguards in place. | `libs/execution/broker_router.py`, `libs/adapters/trading212_adapter.py` |
| `FEATURE_AUTO_REBALANCE` | `false` | Controls automatic portfolio rebalancing. When `false`, rebalancing must be triggered manually. | Settings / future use |
| `FEATURE_DQ_AUTO_QUARANTINE` | `true` | Controls whether data quality failures automatically quarantine affected records. When `true`, records failing DQ checks are flagged and excluded from downstream calculations. | `libs/dq/rules.py` |

---

## Data Source Dependencies

### SEC EDGAR (Production)

- **API key**: None required (public API). `SEC_USER_AGENT` must be set per SEC fair-use policy.
- **Functionality**: Company master data, filings sync, XBRL companyfacts for standardized financials.
- **If missing**: `SEC_USER_AGENT` must be configured or SEC requests will fail. No API key needed.
- **Required for core**: Yes -- provides the instrument master and fundamentals.

### OpenFIGI (Production)

- **API key**: `OPENFIGI_API_KEY` (optional, improves rate limits).
- **Functionality**: Identifier enrichment (FIGI, composite FIGI mapping).
- **If missing**: Falls back to unauthenticated access with lower rate limits (approx 5 req/min vs 250 req/min with key). Enrichment still works, just slower.
- **Required for core**: No -- instruments work without FIGI enrichment.

### Massive / Polygon.io (Skeleton)

- **API key**: `MASSIVE_API_KEY` (required for adapter to function).
- **Functionality**: Production EOD prices, splits, dividends.
- **If missing**: Adapter exists but is non-functional. System falls back to `yfinance_dev` data for prices and corporate actions. All price-dependent features (research, backtest) work with dev data.
- **Required for core**: No for development; Yes for production deployment.

### FMP - Financial Modeling Prep (Skeleton)

- **API key**: `FMP_API_KEY` (required for adapter to function).
- **Functionality**: Production earnings calendar and event data.
- **If missing**: Adapter exists but is non-functional. System falls back to `yfinance_dev` earnings data. Event studies work with dev data.
- **Required for core**: No for development; Yes for production deployment.

### BEA - Bureau of Economic Analysis (Skeleton)

- **API key**: `BEA_API_KEY` (required for adapter to function).
- **Functionality**: Macro indicators (GDP, PCE, investment).
- **If missing**: Adapter is skeleton only. Macro tables remain empty. No other features depend on macro data currently.
- **Required for core**: No.

### BLS - Bureau of Labor Statistics (Skeleton)

- **API key**: `BLS_API_KEY` (required for adapter to function).
- **Functionality**: Macro indicators (employment, CPI, PPI).
- **If missing**: Adapter is skeleton only. Macro tables remain empty.
- **Required for core**: No.

### US Treasury (Skeleton)

- **API key**: None required (public API).
- **Functionality**: Interest rates, fiscal data.
- **If missing**: Adapter is skeleton only. Macro tables remain empty.
- **Required for core**: No.

### Trading 212 (Skeleton)

- **API key**: `T212_API_KEY` + `T212_API_SECRET` (required for adapter to function).
- **Functionality**: Broker account snapshots, position snapshots, order snapshots, order submission.
- **If missing**: Adapter exists but is non-functional. Execution pipeline still works end-to-end (intent -> draft -> risk check -> approve) but no broker data is synced and no orders are submitted.
- **Required for core**: No. The execution layer works in simulation mode without a broker key.

---

## Production vs Development Paths

### Production-Safe (Real Data Sources)

| Path | Source | Notes |
|------|--------|-------|
| SEC filings ingestion | SEC EDGAR | No API key needed, just `SEC_USER_AGENT` |
| SEC fundamentals ingestion | SEC companyfacts | No API key needed |
| OpenFIGI enrichment | OpenFIGI | Works unauthenticated (slow) or with key (fast) |
| Exchange calendar | Internal generation | No external dependency |
| DQ checks | Internal rules engine | Runs against whatever data is loaded |
| Backtest engine | DB-backed prices | Works with any price data in DB |
| Research factors | DB-backed prices + financials | Works with any data in DB |
| Execution pipeline (dry run) | Internal | Full pipeline minus broker submission |

### Dev-Only Fallbacks

| Path | Source | Replacement |
|------|--------|-------------|
| EOD price loading | `yfinance_dev` | Massive/Polygon (`MASSIVE_API_KEY`) |
| Corporate action loading | `yfinance_dev` | Massive/Polygon (`MASSIVE_API_KEY`) |
| Earnings event loading | `yfinance_dev` | FMP (`FMP_API_KEY`) |

Dev data is tagged with `source='yfinance_dev'` in the database. It must not be used in production. Replace by configuring the corresponding API keys and running the production ingestion CLI commands.

### What Works Without Any External API Keys

The system provides significant functionality without any API keys configured:

1. **Database setup**: Full schema creation and migrations
2. **Exchange calendar**: NYSE/NASDAQ calendar generation (2020-2026)
3. **Dev data loading**: yfinance prices, corporate actions, earnings (dev tagged)
4. **DQ checks**: All 11 rules run against loaded data
5. **Research layer**: All 8 factor primitives, 4 screeners, event studies
6. **Backtest engine**: Full simulation with cost model, walk-forward, persistence
7. **Execution pipeline**: Intent -> draft -> risk check -> approve (no live submission)
8. **API server**: All endpoints functional with loaded data
9. **React frontend**: Full dashboard UI (served via Vite dev server or production build)
10. **CLI**: All commands (status, dq-report, run-backtest, etc.)

The only things that require API keys are: production-quality price/earnings data, macro data, broker integration, and live order submission.
