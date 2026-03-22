# Runbook

## Local Development Setup

```bash
# Start PostgreSQL (if using Docker)
make up

# Or use local PostgreSQL (Windows: winget install PostgreSQL.PostgreSQL.16)
# Create user and database:
# PGPASSWORD=postgres psql -U postgres -h localhost -c "CREATE USER quant WITH PASSWORD 'quant_dev_password' SUPERUSER;"
# PGPASSWORD=postgres psql -U postgres -h localhost -c "CREATE DATABASE quant_platform OWNER quant;"

# Install dependencies
pip install -e ".[dev]"
pip install yfinance  # dev-only data loader

# Copy env and configure
cp .env.example .env

# Run migrations
make db-upgrade

# Start API server
make api
```

## Database Operations

```bash
# Create new migration
make db-migrate msg="describe your change"

# Apply migrations
make db-upgrade

# Rollback one migration
make db-downgrade

# Rebuild database from scratch
# DROP DATABASE quant_platform; CREATE DATABASE quant_platform OWNER quant;
make db-upgrade
```

## Data Ingestion — Complete Pipeline

```bash
# 1. Populate exchange calendar (one-time)
PYTHONPATH=. python -c "
from libs.db.session import get_sync_session
from libs.ingestion.populate_exchange_calendar import populate_exchange_calendar
session = get_sync_session()
populate_exchange_calendar(session)
session.close()
"

# 2. Bootstrap security master (SEC + OpenFIGI)
PYTHONPATH=. python -m apps.cli.main bootstrap-security-master --tickers AAPL,MSFT,NVDA,SPY

# 3. Sync SEC filings
PYTHONPATH=. python -m apps.cli.main sync-filings --cik 320193 --instrument-id <AAPL_UUID>

# 4. Sync SEC fundamentals
PYTHONPATH=. python -c "
import asyncio
from libs.db.session import get_sync_session
from libs.ingestion.sync_fundamentals_sec import sync_fundamentals_sec
session = get_sync_session()
asyncio.run(sync_fundamentals_sec(session, cik='320193', instrument_id='<UUID>'))
session.close()
"

# 5. Load prices (dev-only via yfinance)
PYTHONPATH=. python -c "
from libs.db.session import get_sync_session
from libs.ingestion.dev_load_prices import load_eod_prices, load_corporate_actions, load_earnings_events
session = get_sync_session()
load_eod_prices(session, 'AAPL', start='2020-01-01')
load_corporate_actions(session, 'AAPL')
load_earnings_events(session, 'AAPL')
session.close()
"
```

## Data Quality

```bash
# Run all DQ checks
make cli-run-dq

# Or via Python
PYTHONPATH=. python -c "
from libs.db.session import get_sync_session
from libs.dq.rules import run_all_rules
session = get_sync_session()
run_all_rules(session)
session.close()
"

# Check results in data_issue table
```

## Research

```bash
# Event study via API
curl -X POST http://localhost:8000/research/event-study/earnings \
  -H "Content-Type: application/json" \
  -d '{"instrument_id": "<UUID>", "windows": [1,3,5,10]}'

# Instrument summary
curl http://localhost:8000/research/instrument/<UUID>/summary

# Prices
curl http://localhost:8000/research/instrument/<UUID>/prices?start=2024-01-01
```

## Testing

```bash
make test           # All tests
make test-unit      # Unit only
make test-integration  # Integration (needs DB with data)
make lint           # Lint check
make fmt            # Auto-format
```
