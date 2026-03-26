# Quant API Platform

**v1.5.7 — Production Release**

API-first, PIT-aware quantitative stock analysis, research, backtesting, and controlled execution platform for US equities.

> **This is a controlled research platform, not an auto-trading bot.**
> Live broker submission is disabled by default. All orders require manual approval.

## First-Run Checklist

If this is your first time, follow these steps:

1. **Configure** — Copy `.env.example` to `.env`, add at minimum `FMP_API_KEY` (see [Key Setup](#api-key-priority))
2. **Start** — `make up` (PostgreSQL) → `pip install -e ".[dev]"` → `make db-upgrade`
3. **Bootstrap** — `python -m apps.cli.main populate-calendar` → `python -m apps.cli.main bootstrap-security-master --tickers AAPL,MSFT,NVDA,SPY`
4. **Ingest** — `python -m apps.cli.main sync-eod-fmp` → `python -m apps.cli.main sync-fundamentals-fmp`
5. **Launch** — `make api` (backend at :8000) → `cd frontend-react && npm run dev` (frontend at :3002)
6. **Explore** — Open Dashboard → Settings → Research → run a screener or event study

### API Key Priority

| Priority | Key | What It Unlocks | Free Tier |
|----------|-----|-----------------|-----------|
| **1 (Start here)** | `FMP_API_KEY` | EOD prices, financials, company profiles | ✅ 250 req/day |
| 2 | `MASSIVE_API_KEY` | Corporate actions (splits, dividends), raw price validation | ✅ 5 req/min |
| 3 | `T212_API_KEY` | Broker portfolio monitoring (readonly) | ✅ With account |
| Optional | `OPENFIGI_API_KEY` | Faster identifier enrichment | ✅ Works without key |
| Phase 2 | `BEA_API_KEY` / `BLS_API_KEY` | Macro data | ✅ Free gov data |

**Without any keys**: Database, API, frontend, CLI, DQ engine, backtest engine (on existing data), execution pipeline, watchlists, presets, notes all still work.

## Project Principles

1. **instrument_id is the join key** -- ticker is NOT a primary key
2. All critical data retains `source`, `ingested_at`, `raw_payload`
3. Point-in-time (PIT) for all fundamentals and events
4. Raw / split-adjusted / total-return-adjusted prices are layered, never mixed
5. Research and execution layers are decoupled
6. All research functions require explicit `asof_date` to prevent look-ahead bias
7. Demo/paper first, live later (live submission disabled by default)
8. Engineering verifiability, replayability, auditability

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- PostgreSQL 16 (via Docker)

### Local Setup

```bash
# 1. Clone and enter project
cd quant-api-platform

# 2. Copy env file
cp .env.example .env
# Edit .env with your API keys (see docs/api_keys.md)

# 3. Start PostgreSQL
make up

# 4. Install Python dependencies
pip install -e ".[dev]"

# 5. Run database migrations
make db-upgrade

# 6. Bootstrap data
python -m apps.cli.main populate-calendar
python -m apps.cli.main bootstrap-security-master --tickers AAPL,MSFT,NVDA,SPY

# 7. Ingest production data (requires API keys)
python -m apps.cli.main sync-eod-fmp           # EOD prices from FMP
python -m apps.cli.main sync-fundamentals-fmp   # Financials from FMP
python -m apps.cli.main sync-filings --cik <CIK> --instrument-id <UUID>

# 8. Start the API server
make api
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# 9. Start the frontend (development)
cd frontend-react && npm run dev
# Frontend at http://localhost:3002

# 10. Run tests
make test
```

## Data Source Matrix

| Source | Role | Status |
|--------|------|--------|
| FMP (Financial Modeling Prep) | Primary: EOD prices, financials, profiles | Production |
| SEC EDGAR | Truth: filings, companyfacts, PIT validation | Production |
| Polygon / Massive | Primary: corporate actions; Secondary: raw price validation | Production |
| OpenFIGI | Identifier enrichment (FIGI mapping) | Production |
| Trading 212 | Broker: readonly account/positions/orders | Verified (Basic Auth) |
| BEA / BLS / Treasury | Macro data skeletons | Phase 2 |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend: React 18 + Vite + Tailwind CSS               │
│  7 pages | Bilingual (EN/中文) | Dark mode               │
├─────────────────────────────────────────────────────────┤
│  API Layer: FastAPI (25+ endpoints, OpenAPI docs)        │
│  CLI: Typer (15+ commands)                               │
├──────────┬──────────┬───────────┬───────────┬───────────┤
│ Research │ Backtest │ Execution │ Daily     │ DQ/Obs    │
│ 9 factors│ Bar-by-  │ Intent →  │ Watchlist │ 11 rules  │
│ 4 screens│ bar sim  │ Draft →   │ Presets   │ Source    │
│ Event    │ Cost     │ Approve → │ Notes     │ tracking  │
│ study    │ model    │ Submit    │ Activity  │ Issues    │
├──────────┴──────────┴───────────┴───────────┴───────────┤
│  Data Layer: PostgreSQL 16 + SQLAlchemy + Alembic        │
│  25 tables | UUID PKs | timestamptz | PIT-safe           │
├─────────────────────────────────────────────────────────┤
│  Adapters: FMP | SEC EDGAR | Polygon | OpenFIGI | T212   │
└─────────────────────────────────────────────────────────┘
```

## CLI Commands

All commands are run via `python -m apps.cli.main <command>`.

| Command | Description | Notes |
|---------|-------------|-------|
| `bootstrap-security-master` | Bootstrap instruments from SEC + OpenFIGI | `--tickers AAPL,MSFT` to filter |
| `sync-eod-fmp` | Sync EOD prices from FMP | Production primary path |
| `sync-fundamentals-fmp` | Sync financials from FMP | Production primary path |
| `sync-eod-prices` | Sync raw EOD prices | Legacy / dev path |
| `sync-corporate-actions` | Sync splits and dividends | Requires Polygon API key |
| `sync-filings` | Sync SEC EDGAR filings | `--cik <CIK> --instrument-id <UUID>` |
| `sync-earnings` | Sync earnings events | Requires FMP API key |
| `sync-fundamentals` | Sync financial statements | `--symbol <TICKER> --instrument-id <UUID>` |
| `sync-macro` | Sync macroeconomic data | Skeleton (Phase 2) |
| `sync-trading212` | Sync T212 account/positions | Requires T212 API key |
| `run-dq` | Run all 11 data quality checks | Results in `data_issue` table |
| `dq-report` | Run DQ and show detailed report | Grouped by rule and severity |
| `populate-calendar` | Populate exchange calendar | `--start-year 2020 --end-year 2026` |
| `status` | Show DB table counts and DQ summary | Quick health check |
| `run-backtest` | Run a backtest with persistence | `--strategy momentum --tickers AAPL,MSFT` |

## API Endpoints

### Core
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/instruments` | List instruments (paginated) |
| GET | `/instruments/{id}` | Instrument detail + identifiers |

### Research
| Method | Path | Description |
|--------|------|-------------|
| GET | `/research/instrument/{id}/summary` | Price + PIT financial summary |
| GET | `/research/instrument/{id}/prices` | Split-adjusted prices |
| GET | `/research/instrument/{id}/performance` | Performance statistics |
| GET | `/research/instrument/{id}/valuation` | Valuation snapshot (PIT-safe) |
| GET | `/research/instrument/{id}/drawdown` | Drawdown analysis |
| GET | `/research/screener/liquidity` | Screen by average daily volume |
| GET | `/research/screener/returns` | Screen by N-day return |
| GET | `/research/screener/fundamentals` | Screen by fundamental metrics |
| GET | `/research/screener/rank` | Composite factor rank |
| POST | `/research/event-study/earnings` | Post-earnings event study |
| POST | `/research/event-study/earnings/summary` | Grouped event study summary |

### Execution
| Method | Path | Description |
|--------|------|-------------|
| GET | `/execution/intents` | List order intents |
| POST | `/execution/intents` | Create order intent |
| GET | `/execution/drafts` | List order drafts |
| POST | `/execution/drafts/from-intent/{id}` | Create draft from intent |
| POST | `/execution/drafts/{id}/approve` | Approve a draft |
| POST | `/execution/drafts/{id}/reject` | Reject a draft |
| GET | `/execution/drafts/{id}/risk-check` | Run risk checks on draft |
| POST | `/execution/drafts/expire-stale` | Expire stale pending drafts |

### Backtest
| Method | Path | Description |
|--------|------|-------------|
| POST | `/backtest/run` | Run and persist a backtest |
| GET | `/backtest/runs` | List past backtest runs |
| GET | `/backtest/runs/{id}` | Get run detail with metrics |
| GET | `/backtest/runs/{id}/trades` | Get trades for a run |
| GET | `/backtest/runs/{id}/nav` | Get NAV series for a run |

### Data Quality
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dq/issues` | List DQ issues (filterable) |
| GET | `/dq/source-runs` | Source run history |
| POST | `/dq/run` | Trigger DQ check run |

### Daily Workflow
| Method | Path | Description |
|--------|------|-------------|
| GET | `/daily/brief` | Daily research brief |
| GET | `/daily/recent-activity` | Recent platform activity |
| CRUD | `/watchlist/*` | Watchlist group and item management |
| CRUD | `/presets/*` | Saved preset management |
| CRUD | `/notes/*` | Research note management |

## Security Boundaries

This platform is a **controlled research and execution system**, not an unrestricted trading bot.

- Live order submission is **disabled by default** (`FEATURE_T212_LIVE_SUBMIT=false`)
- All orders must pass through the approval gate
- Research and execution layers are decoupled
- Risk checks are mandatory before any broker submission
- Trading 212 integration is readonly by default
- Demo/paper trading is prioritized over live trading

## Testing

```bash
make test              # All tests (160 passing)
make test-unit         # Unit tests only
make test-integration  # Integration tests (requires DB with data)
make test-smoke        # Smoke tests
make lint              # Run linter (ruff)
make fmt               # Format code (ruff)
```

## What Works Without Any External API Keys

- Database schema and migrations
- API server and all endpoints
- Frontend (all 7 pages)
- CLI commands (with graceful degradation)
- DQ engine (on existing data)
- Backtest engine (on existing data)
- Execution pipeline (intent/draft/approval flow)
- Watchlists, presets, notes, recent activity

## Documentation

- [Release Notes v1.5.0](docs/release-v1.5.0.md) -- Production release notes
- [Architecture](docs/architecture.md) -- System layers and data flow
- [Data Contract](docs/data_contract.md) -- Iron rules for data handling
- [Source Matrix](docs/source_matrix.md) -- Data source details and status
- [DQ Framework](docs/dq_framework.md) -- All 11 data quality rules
- [PIT Rules](docs/pit_rules.md) -- Point-in-time enforcement
- [Execution Policy](docs/execution_policy.md) -- Order flow and safety controls
- [Daily Workflow](docs/daily-workflow.md) -- Daily research habit guide
- [Runbook](docs/runbook.md) -- Operational procedures
- [API Keys](docs/api_keys.md) -- API key setup guide
- [Config](docs/config.md) -- Configuration reference
