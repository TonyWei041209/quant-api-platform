# Quant API Platform

API-first quantitative stock analysis and research platform, targeting US equities as the primary market.

## Project Principles

1. **instrument_id is the join key** — ticker is NOT a primary key
2. All critical data retains `source`, `ingested_at`, `raw_payload`
3. Point-in-time (PIT) for all fundamentals and events
4. Raw / split-adjusted / total-return-adjusted prices are layered, never mixed
5. Research and execution layers are decoupled
6. Data and research first, automated execution later
7. Demo/paper first, live later
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
# Edit .env with your API keys

# 3. Start PostgreSQL
make up

# 4. Install Python dependencies
pip install -e ".[dev]"

# 5. Run database migrations
make db-upgrade

# 6. Start the API server
make api
# API available at http://localhost:8000
# Health check: http://localhost:8000/health

# 7. Run tests
make test
```

### CLI Commands

```bash
# Bootstrap security master from SEC
make cli-bootstrap-security-master

# Sync EOD prices
make cli-sync-eod

# Sync corporate actions
make cli-sync-corporate-actions

# Sync fundamentals
make cli-sync-fundamentals

# Run data quality checks
make cli-run-dq
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/instruments` | List instruments (paginated) |
| GET | `/instruments/{id}` | Instrument detail + identifiers |
| GET | `/research/instrument/{id}/summary` | Price + financial summary |
| GET | `/research/instrument/{id}/prices` | Split-adjusted prices |
| POST | `/research/event-study/earnings` | Post-earnings event study |
| GET | `/execution/intents` | List order intents |
| POST | `/execution/intents` | Create order intent |
| GET | `/execution/drafts` | List order drafts |
| POST | `/execution/drafts/from-intent/{id}` | Create draft from intent |
| POST | `/execution/drafts/{id}/approve` | Approve a draft |

### Testing

```bash
make test          # All tests
make test-unit     # Unit tests only
make test-integration  # Integration tests (requires DB)
make test-smoke    # Smoke tests
make lint          # Run linter
make fmt           # Format code
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for full architecture documentation.

## Data Sources

See [docs/source_matrix.md](docs/source_matrix.md) for the complete source matrix.
