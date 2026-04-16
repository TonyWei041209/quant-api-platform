# Runbook

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm (for React frontend)
- PostgreSQL 16 (via Docker or local install)
- Git

---

## 1. Local Startup (Full Stack)

### Step 1: Start PostgreSQL

**Option A -- Docker Compose (recommended):**
```bash
make up
```

**Option B -- Local PostgreSQL (Windows):**
```bash
winget install PostgreSQL.PostgreSQL.16
# Then create user and database:
PGPASSWORD=postgres psql -U postgres -h localhost -c "CREATE USER quant WITH PASSWORD 'quant_dev_password' SUPERUSER;"
PGPASSWORD=postgres psql -U postgres -h localhost -c "CREATE DATABASE quant_platform OWNER quant;"
```

### Step 2: Install Python Dependencies

```bash
pip install -e ".[dev]"
pip install yfinance  # dev-only data loader
```

### Step 3: Configure Environment

```bash
cp .env.example .env
# Edit .env -- at minimum set SEC_USER_AGENT to your name and email
```

See `docs/config.md` for the full environment variable reference.

### Step 4: Run Database Migrations

```bash
make db-upgrade
```

### Step 5: Start the API Server

```bash
make api
# Runs on http://localhost:8000
```

### Step 6: Start the React Frontend (Dev)

```bash
cd frontend-react
npm install
npm run dev
# Runs on http://localhost:3000, proxies API calls to http://localhost:8001
```

Note: The Vite dev server proxies API requests to port 8001. If you want to use the Vite proxy, start the API on port 8001:
```bash
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8001
```

Alternatively, you can build the React frontend for production and serve it directly from FastAPI (see section 5 below).

---

## 2. Database Migration

```bash
# Apply all pending migrations
make db-upgrade

# Create a new migration after model changes
make db-migrate msg="describe your change"

# Rollback one migration
make db-downgrade

# Rebuild database from scratch
# DROP DATABASE quant_platform; CREATE DATABASE quant_platform OWNER quant;
make db-upgrade
```

The Alembic config is at `infra/alembic.ini`.

---

## 3. Running the API Server

```bash
# Default (port 8000, auto-reload)
make api

# Custom port (e.g., 8001 to match Vite proxy config)
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8001
```

The API serves:
- Health check: `GET /health`
- Instruments: `GET /instruments/...`
- Research: `GET /research/...`
- Backtest: `GET|POST /backtest/...`
- Execution: `GET|POST /execution/...`
- Data Quality: `GET|POST /dq/...`
- Interactive docs: `GET /docs` (Swagger UI)

If the React frontend has been built (see section 5), the API also serves the frontend at `GET /`.

---

## 4. Running the React Frontend Dev Server

```bash
cd frontend-react
npm install   # first time only
npm run dev
```

The dev server runs on `http://localhost:3000` and proxies API calls (`/health`, `/instruments`, `/research`, `/backtest`, `/execution`, `/dq`) to `http://localhost:8001`.

Pages available:
- Dashboard -- system overview
- Instruments -- browse loaded instruments
- Research -- factor analysis, screeners, event studies
- Backtest -- run and review backtests
- Execution -- order pipeline management
- Data Quality -- DQ issues and source run history
- Settings -- feature flags and configuration

---

## 5. Building the React Frontend for Production

```bash
cd frontend-react
npm run build
```

This outputs static files to `frontend-react/dist/`. The FastAPI server automatically detects and serves this directory at `GET /` when it exists.

No separate web server is needed in production -- FastAPI serves both the API and the frontend.

---

## 5.5. Production Deployment

### One-command deploy (API + Job sync)

```powershell
.\scripts\deploy-api.ps1
```

This script:
1. Deploys `quant-api` to Cloud Run from source
2. Automatically syncs `quant-sync-t212` job to the same image digest
3. Verifies alignment

### Deploy API only (skip job sync)
```powershell
.\scripts\deploy-api.ps1 -SkipJobSync
```

### Deploy frontend only
```powershell
cd frontend-react && npx vite build && cd ..
npx firebase deploy --only hosting
```

### Check API/Job image alignment
```powershell
.\scripts\sync-job-image.ps1 -CheckOnly
```

### Manual job image sync (if auto-sync was skipped or failed)
```powershell
.\scripts\sync-job-image.ps1
```

**Note on PowerShell + gcloud:** `gcloud` writes progress to stderr. With `$ErrorActionPreference="Stop"` and `2>&1`, PowerShell treats stderr as terminating errors. The scripts use `$ErrorActionPreference="Continue"` during gcloud calls with `2>$null`, and check `$LASTEXITCODE` for success/failure. Do not revert this pattern.

---

## 6. Running CLI Commands

All CLI commands are run via:
```bash
python -m apps.cli.main <command> [options]
```

### Data Ingestion Pipeline

```bash
# Step 1: Populate exchange calendar
python -m apps.cli.main populate-calendar --start-year 2020 --end-year 2026

# Step 2: Bootstrap instruments from SEC EDGAR
python -m apps.cli.main bootstrap-security-master --tickers AAPL,MSFT,NVDA,SPY

# Step 3: Sync SEC filings
python -m apps.cli.main sync-filings --cik 320193 --instrument-id <AAPL_UUID>

# Step 4: Sync SEC fundamentals
python -m apps.cli.main sync-fundamentals --symbol AAPL --instrument-id <AAPL_UUID>

# Step 5: Load dev prices (yfinance -- no API key needed)
PYTHONPATH=. python -c "
from libs.db.session import get_sync_session
from libs.ingestion.dev_load_prices import load_eod_prices, load_corporate_actions, load_earnings_events
session = get_sync_session()
load_eod_prices(session, 'AAPL', start='2020-01-01')
load_corporate_actions(session, 'AAPL')
load_earnings_events(session, 'AAPL')
session.close()
"

# Step 6: Sync macro data (skeleton -- not yet functional)
python -m apps.cli.main sync-macro

# Step 7: Sync Trading 212 (requires T212_API_KEY)
python -m apps.cli.main sync-trading212 --demo
```

Note: The CLI commands `sync-eod-prices`, `sync-corporate-actions`, and `sync-earnings` exist but require Massive/Polygon or FMP API keys. Without those keys, use the yfinance dev loader in step 5.

### System Status and Reporting

```bash
# Quick status (table counts, recent runs, DQ summary)
python -m apps.cli.main status

# Run all 11 DQ checks
python -m apps.cli.main run-dq

# DQ detailed report
python -m apps.cli.main dq-report
```

### Backtest

```bash
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

---

## 7. Running Tests

```bash
make test              # All tests (141 passing)
make test-unit         # Unit tests only
make test-integration  # Integration tests (needs DB with data)
make test-smoke        # Smoke tests
make lint              # Lint check (ruff)
make fmt               # Auto-format (ruff)
```

Integration tests require a running PostgreSQL with the schema applied and data loaded. Unit tests and smoke tests have no external dependencies.

---

## 8. Running DQ Checks

### Via CLI
```bash
# Run all 11 DQ rules
python -m apps.cli.main run-dq

# Generate a detailed report
python -m apps.cli.main dq-report

# Quick status (includes DQ summary)
python -m apps.cli.main status
```

### Via Makefile
```bash
make cli-run-dq
```

### Via API
```bash
# Trigger a DQ run
curl -X POST http://localhost:8000/dq/run

# List DQ issues (with optional filters)
curl "http://localhost:8000/dq/issues?severity=ERROR&resolved=false"

# List source runs
curl http://localhost:8000/dq/source-runs
```

The 11 DQ rules cover: missing prices, stale prices, cross-source divergence, ticker overlap, orphan identifiers, raw/adjusted contamination, filing gaps, earnings gaps, corporate action validation, financial period consistency, and calendar gaps.

---

## 9. Running a Backtest

### Via CLI
```bash
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
# Run and persist a backtest
curl -X POST http://localhost:8000/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"strategy": "momentum", "tickers": ["AAPL","MSFT","NVDA","SPY"], "start_date": "2023-01-01", "end_date": "2024-12-31"}'

# List past runs
curl http://localhost:8000/backtest/runs

# Get run details (metrics, config)
curl http://localhost:8000/backtest/runs/<RUN_ID>

# Get trade-level detail
curl http://localhost:8000/backtest/runs/<RUN_ID>/trades

# Get NAV time series
curl http://localhost:8000/backtest/runs/<RUN_ID>/nav
```

Backtest results are persisted in the `backtest_run` and `backtest_trade` tables. The engine uses DB-backed prices and works with whatever data is loaded (dev or production).

---

## 10. Which Modules Need API Keys

| Module | Key | What It Enables |
|--------|-----|----------------|
| SEC EDGAR | None (set `SEC_USER_AGENT` only) | Instrument master, filings, fundamentals |
| OpenFIGI | `OPENFIGI_API_KEY` (optional) | Higher rate limit for identifier enrichment |
| Massive/Polygon | `MASSIVE_API_KEY` | Production EOD prices, splits, dividends |
| FMP | `FMP_API_KEY` | Production earnings calendar |
| BEA | `BEA_API_KEY` | Macro data (GDP, PCE) |
| BLS | `BLS_API_KEY` | Macro data (employment, CPI) |
| Treasury | None (public API) | Interest rates, fiscal data (skeleton) |
| Trading 212 | `T212_API_KEY` | Broker account sync, order submission |

See `docs/config.md` for the complete configuration reference.

---

## 11. Features Disabled by Default

| Feature Flag | Default | What It Controls |
|-------------|---------|-----------------|
| `FEATURE_T212_LIVE_SUBMIT` | `false` | Live order submission to Trading 212. When false, the full execution pipeline works but no orders are sent to the broker. |
| `FEATURE_AUTO_REBALANCE` | `false` | Automatic portfolio rebalancing. When false, rebalancing must be triggered manually. |
| `FEATURE_DQ_AUTO_QUARANTINE` | `true` | Auto-quarantine of records failing DQ checks. This is enabled by default. |

To enable a feature, set the corresponding flag to `true` in your `.env` file.

---

## 12. What Works Without Any External API Keys

A new engineer can get the full system running and exercising all major features without configuring any API keys beyond `SEC_USER_AGENT` (which is just your name and email, not a paid key).

**Fully functional without keys:**
- PostgreSQL schema setup and Alembic migrations
- Exchange calendar generation (NYSE/NASDAQ)
- Instrument bootstrapping from SEC EDGAR (public, no key)
- SEC filings and fundamentals ingestion (public, no key)
- Dev data loading: yfinance prices, corporate actions, earnings
- All 11 DQ rules and reporting
- All research factor primitives (8) and screeners (4)
- Event studies with grouped summaries
- Full backtest engine with cost model, walk-forward, persistence
- Complete execution pipeline (intent -> draft -> risk check -> approve, no live submission)
- All 20+ API endpoints across 6 routers
- React frontend dashboard with all 7 pages
- All CLI commands

**Requires paid API keys:**
- Production-quality price data (Massive/Polygon)
- Production earnings data (FMP)
- Macro data pipeline (BEA, BLS)
- Broker integration and live trading (Trading 212)

**Optional improvement with key:**
- OpenFIGI identifier enrichment works without a key but at lower rate limits

---

## Trading 212 Readonly Sync (Production)

### Architecture

```
Cloud Scheduler (cron: 0 8,21 * * 1-5 UTC)
    → Cloud Run Job "quant-sync-t212" (asia-east2)
        → python -m apps.cli.main sync-trading212 --no-demo
            → Cloud SQL (broker_*_snapshot tables)
```

### What it does
- Fetches account summary, open positions, and recent orders from T212 API (readonly)
- Maps broker_ticker to internal instrument_id (e.g., NVDA_US_EQ → NVDA → instrument table)
- Writes snapshots to `broker_account_snapshot`, `broker_position_snapshot`, `broker_order_snapshot`
- Creates a `source_run` audit record
- **This is purely readonly — no broker write operations, no execution objects created**

### Schedule
- **Frequency:** Twice daily on weekdays — 08:00 UTC (pre-market) and 21:00 UTC (post-close)
- **Timezone:** UTC
- **Why this frequency:** T212 positions change only during trading hours; 2x/day is sufficient for research context

### Required Secrets (in Secret Manager)
- `DATABASE_URL` — Cloud SQL connection string
- `T212_API_KEY` — Trading 212 API key
- `T212_API_SECRET` — Trading 212 API secret

### Image Version Sync (API → Job)

After deploying a new version of `quant-api`, the Job still uses the old image.

```powershell
# Check if images are aligned
.\scripts\sync-job-image.ps1 -CheckOnly

# Sync Job image to match current API service
.\scripts\sync-job-image.ps1

# Then verify the Job works
gcloud run jobs execute quant-sync-t212 --region asia-east2 --wait
```

**Why not `:latest`?** Not auditable, not rollback-safe, can silently diverge. Explicit SHA digests ensure Job runs the exact same code as the API.

**After rolling back the API:** Run `.\scripts\sync-job-image.ps1` again — it reads whichever revision is currently serving and syncs the Job to match.

### Manual Trigger
```bash
gcloud run jobs execute quant-sync-t212 --region asia-east2 --wait
```

### View Logs
```bash
gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=quant-sync-t212' --limit 20 --format 'table(timestamp,textPayload)' --freshness=1h
```

### Expected Output
```
Trading 212 sync complete: {'account_snapshots': 1, 'positions': 3, 'orders': 50, 'errors': 0}
Container called exit(0).
```

### Failure Troubleshooting
1. Check logs: `gcloud logging read ...` (see above)
2. Common failures:
   - T212 API credentials expired → update `T212_API_KEY`/`T212_API_SECRET` in Secret Manager
   - Cloud SQL unreachable → check VPC/network config
   - Rate limit hit → T212 has 1 req/sec limit, sync respects this
3. The job is idempotent — safe to re-run. Creates new snapshots; dedup handled at read time via `DISTINCT ON`
4. Failed jobs do not affect the main API service
