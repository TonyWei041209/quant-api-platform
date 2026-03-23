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

## Data Ingestion -- Complete Pipeline

### Step 1: Populate Exchange Calendar

```bash
python -m apps.cli.main populate-calendar --start-year 2020 --end-year 2026
```

### Step 2: Bootstrap Security Master

```bash
python -m apps.cli.main bootstrap-security-master --tickers AAPL,MSFT,NVDA,SPY
```

This creates instruments from SEC EDGAR and enriches identifiers via OpenFIGI.

### Step 3: Sync SEC Filings

```bash
python -m apps.cli.main sync-filings --cik 320193 --instrument-id <AAPL_UUID>
```

### Step 4: Sync SEC Fundamentals

```bash
python -m apps.cli.main sync-fundamentals --symbol AAPL --instrument-id <AAPL_UUID>
```

### Step 5: Load Prices (Dev Only via yfinance)

Prices are currently loaded via yfinance dev scripts (not via CLI sync-eod-prices, which requires Massive API key):

```bash
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

Note: The CLI commands `sync-eod-prices`, `sync-corporate-actions`, and `sync-earnings` exist but require Massive/Polygon or FMP API keys to function. Without those keys, use the dev loader above.

### Step 6: Sync Macro (Skeleton)

```bash
python -m apps.cli.main sync-macro
```

Note: This is a skeleton. BEA, BLS, and Treasury adapters are not yet functional.

### Step 7: Sync Trading 212 (Requires API Key)

```bash
python -m apps.cli.main sync-trading212 --demo
```

Note: Requires `T212_API_KEY` in `.env`. Not currently configured.

## Data Quality

```bash
# Run all 11 DQ checks
python -m apps.cli.main run-dq

# Run DQ and show detailed report
python -m apps.cli.main dq-report

# Quick status check (table counts + DQ summary)
python -m apps.cli.main status
```

Or via Makefile:
```bash
make cli-run-dq
```

## Research (via API)

```bash
# Start API
make api

# Instrument summary (prices + PIT financials)
curl http://localhost:8000/research/instrument/<UUID>/summary

# Split-adjusted prices
curl "http://localhost:8000/research/instrument/<UUID>/prices?start=2024-01-01"

# Performance statistics
curl "http://localhost:8000/research/instrument/<UUID>/performance?start=2023-01-01&end=2024-12-31"

# Valuation snapshot
curl "http://localhost:8000/research/instrument/<UUID>/valuation?asof=2024-12-31"

# Drawdown analysis
curl "http://localhost:8000/research/instrument/<UUID>/drawdown?start=2023-01-01"

# Screeners
curl "http://localhost:8000/research/screener/liquidity?min_avg_volume=1000000&asof=2024-12-31"
curl "http://localhost:8000/research/screener/returns?lookback_days=63&asof=2024-12-31"
curl "http://localhost:8000/research/screener/fundamentals?max_pe=25&asof=2024-12-31"
curl "http://localhost:8000/research/screener/rank?asof=2024-12-31"

# Event study (single instrument)
curl -X POST http://localhost:8000/research/event-study/earnings \
  -H "Content-Type: application/json" \
  -d '{"instrument_id": "<UUID>", "asof_date": "2024-12-31", "windows": [1,3,5,10]}'

# Event study (grouped summary)
curl -X POST http://localhost:8000/research/event-study/earnings/summary \
  -H "Content-Type: application/json" \
  -d '{"asof_date": "2024-12-31", "windows": [1,3,5,10]}'
```

## Backtesting

### Via CLI

```bash
# Run a momentum backtest
python -m apps.cli.main run-backtest \
  --strategy momentum \
  --tickers AAPL,MSFT,NVDA,SPY \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --commission-bps 5 \
  --slippage-bps 5 \
  --max-positions 20 \
  --rebalance monthly
```

### Via API

```bash
# Run a backtest
curl -X POST http://localhost:8000/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"strategy": "momentum", "tickers": ["AAPL","MSFT","NVDA","SPY"], "start_date": "2023-01-01", "end_date": "2024-12-31"}'

# List past runs
curl http://localhost:8000/backtest/runs

# Get run details
curl http://localhost:8000/backtest/runs/<RUN_ID>

# Get trades for a run
curl http://localhost:8000/backtest/runs/<RUN_ID>/trades

# Get NAV series
curl http://localhost:8000/backtest/runs/<RUN_ID>/nav
```

## Execution Pipeline

```bash
# Create an order intent
curl -X POST http://localhost:8000/execution/intents \
  -H "Content-Type: application/json" \
  -d '{"strategy_name": "manual", "instrument_id": "<UUID>", "side": "buy", "target_qty": 10}'

# Create a draft from the intent
curl -X POST http://localhost:8000/execution/drafts/from-intent/<INTENT_ID> \
  -H "Content-Type: application/json" \
  -d '{"broker": "trading212", "order_type": "limit", "qty": 10, "limit_price": 150.0}'

# Run risk checks on the draft
curl http://localhost:8000/execution/drafts/<DRAFT_ID>/risk-check

# Approve the draft
curl -X POST http://localhost:8000/execution/drafts/<DRAFT_ID>/approve

# Reject a draft
curl -X POST "http://localhost:8000/execution/drafts/<DRAFT_ID>/reject?reason=changed+mind"

# Expire stale pending drafts
curl -X POST "http://localhost:8000/execution/drafts/expire-stale?max_age_hours=48"
```

Note: Actual broker submission is disabled. Even after approval, orders will not be sent to Trading 212 unless `FEATURE_T212_LIVE_SUBMIT=true` AND the draft has `is_live_enabled=true`.

## Testing

```bash
make test              # All tests (103 passing)
make test-unit         # Unit tests only
make test-integration  # Integration tests (needs DB with data)
make test-smoke        # Smoke tests
make lint              # Lint check (ruff)
make fmt               # Auto-format (ruff)
```
