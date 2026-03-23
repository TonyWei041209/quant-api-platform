# Quant API Platform

API-first quantitative stock analysis, research, backtesting, and controlled execution platform for US equities.

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
pip install yfinance  # dev-only data loader

# 5. Run database migrations
make db-upgrade

# 6. Bootstrap data
python -m apps.cli.main populate-calendar
python -m apps.cli.main bootstrap-security-master --tickers AAPL,MSFT,NVDA,SPY

# 7. Start the API server
make api
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# 8. Run tests
make test
```

## CLI Commands

All commands are run via `python -m apps.cli.main <command>`.

| Command | Description | Notes |
|---------|-------------|-------|
| `bootstrap-security-master` | Bootstrap instruments from SEC + OpenFIGI | `--tickers AAPL,MSFT` to filter |
| `sync-eod-prices` | Sync raw EOD prices | Requires Massive API key or dev loader |
| `sync-corporate-actions` | Sync splits and dividends | Requires Massive API key or dev loader |
| `sync-filings` | Sync SEC EDGAR filings | `--cik <CIK> --instrument-id <UUID>` |
| `sync-earnings` | Sync earnings events | Requires FMP API key or dev loader |
| `sync-fundamentals` | Sync financial statements | `--symbol <TICKER> --instrument-id <UUID>` |
| `sync-macro` | Sync macroeconomic data | Skeleton -- adapters not yet functional |
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

## Testing

```bash
make test              # All tests (103 passing)
make test-unit         # Unit tests only
make test-integration  # Integration tests (requires DB with data)
make test-smoke        # Smoke tests
make lint              # Run linter (ruff)
make fmt               # Format code (ruff)
```

## Data Source Status

| Source | Status | Notes |
|--------|--------|-------|
| SEC EDGAR | **Production** | Filings, company master. No key needed. |
| SEC companyfacts | **Production** | Standardized financials. No key needed. |
| OpenFIGI | **Production** | Identifier enrichment. No key configured (unauthenticated rate). |
| yfinance | **DEV ONLY** | Prices, splits, dividends, earnings. Tagged `source='yfinance_dev'`. NOT for production. |
| Massive/Polygon | Skeleton | Adapter exists. Needs `MASSIVE_API_KEY`. |
| FMP | Skeleton | Adapter exists. Needs `FMP_API_KEY`. |
| BEA | Skeleton | Adapter exists. Needs `BEA_API_KEY`. |
| BLS | Skeleton | Adapter exists. Needs `BLS_API_KEY`. |
| Treasury | Skeleton | Adapter exists. Public endpoint. |
| Trading 212 | Skeleton | Adapter exists. Needs `T212_API_KEY`. |

**Known blocker**: Prices, corporate actions, and earnings are currently sourced from `yfinance_dev`. This is a development-only data source. Production use requires configuring Massive/Polygon and FMP API keys.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full architecture overview.

## Documentation

- [Architecture](docs/architecture.md) -- System layers and data flow
- [Data Contract](docs/data_contract.md) -- Iron rules for data handling
- [Source Matrix](docs/source_matrix.md) -- Data source details and status
- [DQ Framework](docs/dq_framework.md) -- All 11 data quality rules
- [PIT Rules](docs/pit_rules.md) -- Point-in-time enforcement
- [Execution Policy](docs/execution_policy.md) -- Order flow and safety controls
- [Runbook](docs/runbook.md) -- Operational procedures
- [API Keys](docs/api_keys.md) -- API key setup guide
