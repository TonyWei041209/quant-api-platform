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

### Scanner Research Universe — Daily EOD Sync

The Scanner Research Universe (36 high-liquidity instruments) has a CLI
command for incremental EOD sync. As of 2026-04-29:
- **Dry-run**: fully implemented (default mode)
- **WRITE_LOCAL**: fully implemented (against localhost dev DB)
- **WRITE_PRODUCTION**: hard-deferred (`NotImplementedError`) until acceptance
  criteria #5/#8/#9/#10 in `docs/scanner-research-universe-production-plan.md`
  are all green

#### Plan a sync run (always safe — no DB writes, no API calls)

```bash
# Default: --dry-run is implicit and prints the plan
python -m apps.cli.main sync-eod-prices-universe --universe scanner-research --dry-run
```

The dry-run reads the local DB (read-only) to compute the per-ticker
incremental window (latest_known_trade_date − lookback_days → today). It
emits provider strategy, rate-limit pacing, estimated runtime, and a
side-effect attestation block (`DB writes performed: NONE`, etc.).

#### Run a real sync against LOCAL dev DB (Polygon → FMP fallback)

```bash
# WRITE_LOCAL — writes only to localhost DB; refuses non-localhost
python -m apps.cli.main sync-eod-prices-universe \
  --universe scanner-research \
  --no-dry-run --write --db-target=local \
  --polygon-delay-seconds=13
```

What happens per ticker:
1. Look up `instrument_id` from `instrument_identifier` (read-only)
2. Try Polygon `/v2/aggs/.../range/1/day/...` (paced)
3. On Polygon failure → fall back to FMP `get_eod_prices`
4. Write to `price_bar_raw` with `INSERT ... ON CONFLICT DO NOTHING`
5. Commit per ticker (so partial progress persists if a later ticker fails)
6. Sleep `--polygon-delay-seconds` before next ticker

Per-ticker isolation: a single ticker's failure does NOT abort the batch.
Failed tickers are reported in the final summary with the last error. The
result includes `bars_inserted_total`, `bars_existing_or_skipped_total`,
`runtime_seconds`, and explicit attestations for Cloud Run jobs / Scheduler /
Production deploy / Execution objects / Broker write — all `NONE`.

Source tags: Polygon successes → `source='polygon'`. FMP fallback successes
→ `source='fmp'`. Both coexist with prior `source='yfinance_dev'` data
(distinct unique key includes `source`).

#### Production write — requires FOUR explicit flags

Production write is gated by **all four** flags simultaneously, plus the
DB URL must classify as production. Single-flag combinations are refused:

```bash
python -m apps.cli.main sync-eod-prices-universe \
  --no-dry-run \
  --write \
  --db-target=production \
  --confirm-production-write
```

The CLI also requires the `DATABASE_URL_OVERRIDE` secret to point at a
Cloud SQL connection (URL containing `/cloudsql/`). If the URL classifies
as anything other than `production`, the planner refuses before any
provider HTTP call is made.

This combination is **only intended to run inside the one-shot Cloud Run
Job described in the Phase B Execution Playbook below**. Do NOT invoke
this command from a developer laptop pointed at production via Cloud SQL
Auth Proxy — it works, but it bypasses the audit trail that comes from
running inside a uniquely-named one-shot Cloud Run Job.

### Scanner Universe Production Seed (Phase B Execution Playbook)

This section is the operator playbook for the one-shot production seed.
**It must be followed in order.** Each step has a verification checkpoint
that gates the next step. If any verification fails, do NOT proceed —
trigger the rollback playbook instead.

This playbook applies once: the goal is to bring production Cloud SQL from
4 instruments to 36 instruments + ~370 daily-EOD bars per new ticker. After
success, the daily-incremental Cloud Run Job + Scheduler (Phase C) is a
separate decision.

#### Prerequisites (must all be true before starting)

- Acceptance criteria #1–#7 already PASS (see plan doc Section 8)
- `execute_sync` `WRITE_PRODUCTION` code path is implemented (Phase B1) and
  the deployed `quant-api` revision contains it (verify by image digest
  matching the post-B1 deploy revision)
- The 32 new tickers (universe minus pre-existing NVDA / AAPL / MSFT / SPY)
  do NOT already exist in production `instrument_identifier` (would imply a
  partial prior seed; investigate before proceeding)
- Cloud Run Job `quant-ops-research-universe-seed` does NOT already exist
  (`gcloud run jobs list --region asia-east2`)
- A trusted operator window of ≥ 30 minutes is available to monitor and
  respond to verification checkpoints

#### Phase B Job Spec

```yaml
name: quant-ops-research-universe-seed
region: asia-east2
image: <SAME DIGEST as currently-serving quant-api revision>
command: python
args:
  - -m
  - apps.cli.main
  - sync-eod-prices-universe
  - --universe=scanner-research
  - --no-dry-run
  - --write
  - --db-target=production
  - --confirm-production-write
  - --polygon-delay-seconds=13
env:
  APP_ENV: production
  PYTHONPATH: /app
secrets:
  DATABASE_URL_OVERRIDE: DATABASE_URL:latest
  MASSIVE_API_KEY: MASSIVE_API_KEY:latest
  FMP_API_KEY: FMP_API_KEY:latest
memory: 512Mi
task_timeout: 900s         # 15 min, ≈7-min buffer over expected ~8-min runtime
max_retries: 0             # one-shot; failures need manual review
parallelism: 1
task_count: 1
```

**Image alignment policy**: image digest must match the currently-serving
`quant-api` revision (mirror the existing `sync-job-image.ps1` pattern).
Different image = different code path = unsafe. If a new `quant-api`
revision is deployed mid-execution, the running job is unaffected (it uses
the digest captured at job-create time).

**Cleanup policy**: delete the one-shot job immediately after successful
post-flight verification. Do NOT leave it lying around.

**`DB_TARGET_OVERRIDE` (added 2026-04-30, commit B1.1)**: production
`DATABASE_URL` secret currently uses the public-IP form
(`host=34.150.76.29:5432`) instead of the Cloud-SQL Unix-socket form
(`host=/cloudsql/PROJECT:REGION:INSTANCE`). The B1 `_classify_db_url`
function does not recognize the public-IP form as "production" by URL
pattern alone — for safety, anything other than `localhost`/`/cloudsql/`
classifies as `unknown`. The seed job MUST therefore set
`DB_TARGET_OVERRIDE=production` in its env vars. The override values are
restricted to `{"local","production"}`; any other value raises ValueError.
The override does NOT bypass the four-flag handshake or write-mode/db-target
matching — it only changes how the URL is classified for that one process.

#### Cloud SQL Backup Plan

```bash
# Take backup ≤ 30 min before seed execution
BACKUP_ID=$(gcloud sql backups create \
  --instance=quant-api-db \
  --description="pre-scanner-universe-seed-$(date +%Y%m%d-%H%M)" \
  --project=secret-medium-491502-n8 \
  --format="value(id)")
echo "Backup ID: $BACKUP_ID"

# Wait until backup is READY (gcloud returns RUNNING until done)
gcloud sql backups describe "$BACKUP_ID" \
  --instance=quant-api-db \
  --format="value(status)"
# repeat until status == SUCCESSFUL (or RUNNING → failed → abort)
```

Capture the backup ID in:
1. The chat log at execution time
2. The post-execution commit message
3. The runbook execution log entry (if maintained)

Backup must be ≤ 30 minutes before seed execution to minimize the
post-backup-write replay window if a full restore (option B rollback)
becomes necessary.

#### Pre-flight Checks

```bash
# 1. Production health
curl -fsw "\nhttp=%{http_code}\n" "https://quant-api-188966768344.asia-east2.run.app/api/health"
# expect: {"status":"ok"} HTTP 200

# 2. quant-api currently serving with B1 code (post-B1-deploy revision)
gcloud run services describe quant-api --region asia-east2 \
  --format "value(status.traffic[0].revisionName,spec.template.spec.containers[0].image)"

# 3. FEATURE_T212_LIVE_SUBMIT remains false
gcloud run services describe quant-api --region asia-east2 \
  --format "value(spec.template.spec.containers[0].env)" | grep -i live_submit
# expect: 'value': 'false'

# 4. quant-sync-t212 schedule still ENABLED (do not disrupt)
gcloud scheduler jobs describe quant-sync-t212-schedule \
  --location asia-east2 --format "value(state)"

# 5. quant-ops-research-universe-seed does NOT exist yet
gcloud run jobs list --region asia-east2 --format "value(name)"
# expect: only quant-sync-t212

# 6. Take Cloud SQL backup (see Backup Plan above)
```

If any pre-flight fails: do NOT proceed.

#### Execute (the irreversible step)

```bash
# 7. Capture currently-serving image digest
IMAGE=$(gcloud run services describe quant-api --region asia-east2 \
  --format "value(spec.template.spec.containers[0].image)")

# 8. Create the one-shot job
gcloud run jobs create quant-ops-research-universe-seed \
  --region=asia-east2 \
  --image="$IMAGE" \
  --command=python \
  --args=-m,apps.cli.main,sync-eod-prices-universe,--universe=scanner-research,--no-dry-run,--write,--db-target=production,--confirm-production-write,--polygon-delay-seconds=13 \
  --set-env-vars="APP_ENV=production,PYTHONPATH=/app" \
  --set-secrets="DATABASE_URL_OVERRIDE=DATABASE_URL:latest,MASSIVE_API_KEY=MASSIVE_API_KEY:latest,FMP_API_KEY=FMP_API_KEY:latest" \
  --max-retries=0 \
  --task-timeout=900

# 9. Execute and wait
gcloud run jobs execute quant-ops-research-universe-seed --region asia-east2 --wait
```

#### Log Watch (parallel terminal during execution)

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=quant-ops-research-universe-seed" \
  --limit=100 --format="value(timestamp,textPayload)" --freshness=20m \
  --project=secret-medium-491502-n8
```

Expected log signal:
- ~36 `adapter.fetch ... adapter=massive ... status=200` (Polygon success path)
- Possibly some `adapter.fetch ... adapter=fmp ...` (FMP fallback for any
  Polygon-temporary-failure tickers)
- Per-ticker `OK` lines from `render_sync_result`
- Final `SYNC RESULT — universe='scanner-research' mode=WRITE_PRODUCTION`
  block with `DB writes performed: price_bar_raw + source_run only (PRODUCTION)`

#### Post-flight Verification

```bash
# 10. /api/health still 200
curl -fsw "\nhttp=%{http_code}\n" "https://quant-api-188966768344.asia-east2.run.app/api/health"

# 11. Production now has 36 active instruments
# (via authenticated /api/instruments or via direct Cloud SQL query)
# expect: 36

# 12. price_bar_raw count for new 32 tickers > 0
# (each new ticker should have ~370 bars over the 540-day window)
# expect: total bars increase by ~12,000 (≈370 × 32)

# 13. Protected NVDA/AAPL/MSFT/SPY price_bar_raw counts UNCHANGED
# (these had bars before; the seed should not have touched them)

# 14. /api/scanner/stock?universe=all returns 200 with matched > 0
# expect: scanned=36, matched count plausibly increases vs the 4-instrument baseline

# 15. quant-sync-t212 job and schedule still untouched
gcloud run jobs list --region asia-east2 --format "value(name)"
gcloud scheduler jobs list --location asia-east2 --filter "name~quant"
# expect: quant-sync-t212 + quant-ops-research-universe-seed (the latter pending cleanup)

# 16. FEATURE_T212_LIVE_SUBMIT still false
gcloud run services describe quant-api --region asia-east2 \
  --format "value(spec.template.spec.containers[0].env)" | grep -i live_submit
```

If any post-flight check fails: trigger rollback (next section).

#### Cleanup (after successful post-flight)

```bash
# 17. Delete the one-shot job
gcloud run jobs delete quant-ops-research-universe-seed \
  --region asia-east2 --quiet

# 18. Verify only legitimate jobs remain
gcloud run jobs list --region asia-east2 --format "value(name)"
# expect: only quant-sync-t212
```

#### Rollback Playbook

##### Trigger conditions

Pull the trigger if **any** of these are observed in post-flight or during
execution:

- HTTP 502/503 on `/api/health`
- Production instrument count != 36
- Protected NVDA/AAPL/MSFT/SPY price_bar_raw counts changed (any direction)
- `/api/scanner/stock` returns 500 or schema validation errors
- `FEATURE_T212_LIVE_SUBMIT` flipped to true
- Cloud Logging shows un-isolated per-ticker errors (one ticker breaking
  the whole run instead of being isolated)
- Job execution exits with non-zero code

##### Option A — row-level rollback (preferred)

Surgical, fast, preserves all other production data. Uses the validated
SQL template from plan doc Section 6.

Run via a temporary read-write Cloud Run Job using the same `quant-api`
image (so the SQL goes through Cloud SQL Auth Proxy with proper
credentials), OR via direct `gcloud sql connect` from a trusted environment.

```sql
BEGIN;
-- 32-ticker allowlist (excludes the protected NVDA/AAPL/MSFT/SPY)
WITH allowlist AS (
  SELECT UNNEST(ARRAY[
    'AMD','AVGO','TSM','INTC','MU','GOOGL','META','AMZN',
    'TSLA','RIVN','LCID','NIO','XPEV','SOFI','PLTR','COIN',
    'JPM','BAC','GS','XOM','CVX','OXY','DIS','NFLX','UBER',
    'F','GM','BA','SIRI','AMC','QQQ','IWM'
  ]) AS ticker
),
target AS (
  SELECT DISTINCT i.instrument_id
  FROM instrument i
  JOIN instrument_identifier ii ON ii.instrument_id = i.instrument_id
  WHERE ii.id_type = 'ticker' AND ii.id_value IN (SELECT ticker FROM allowlist)
)
DELETE FROM price_bar_raw WHERE instrument_id IN (SELECT instrument_id FROM target);
DELETE FROM instrument_identifier WHERE instrument_id IN (SELECT instrument_id FROM target);
DELETE FROM ticker_history WHERE instrument_id IN (SELECT instrument_id FROM target);
DELETE FROM instrument WHERE instrument_id IN (SELECT instrument_id FROM target);

-- Verify rowcounts before COMMIT.
-- If protected counts changed in a separate SELECT, ROLLBACK and investigate.
-- Otherwise:
COMMIT;
```

The rollback SQL was validated in dev DB on 2026-04-29 inside a
BEGIN/ROLLBACK; protected ticker counts confirmed unchanged. See
`scripts/validate_scanner_universe_rollback_sql.py`.

##### Option B — full restore (last resort)

```bash
# WARNING: this drops ALL writes since the backup, including
# any post-backup quant-sync-t212 results.
gcloud sql backups restore $BACKUP_ID \
  --restore-instance=quant-api-db \
  --backup-instance=quant-api-db
```

Use only if option A fails or data corruption is suspected. After restore,
verify health + T212 sync + scanner endpoints.

#### Post-rollback Cleanup

```bash
gcloud run jobs delete quant-ops-research-universe-seed \
  --region asia-east2 --quiet
```

If rollback was option B (full restore), also re-run T212 sync to
re-populate broker_*_snapshot tables that were dropped:

```bash
gcloud run jobs execute quant-sync-t212 --region asia-east2 --wait
```

#### After-Action Items (success or failure)

- Update `docs/scanner-research-universe-production-plan.md` Section 8:
  - On success: mark #8 ✅ PASS with backup ID, mark #10 ✅ PASS,
    record execution timestamp + revision + bar counts
  - On rollback: mark #8 ✅ PASS but record incident, append a
    "what we learned" subsection

- Update `memory/project_quant_platform.md` with one summary line that
  records: outcome (succeeded / rolled back), backup ID, revision used,
  duration, ticker counts.

- If success: discuss whether to proceed to Phase C (daily incremental
  sync Cloud Run Job + Scheduler) — that is a separate sign-off, not
  implied by Phase B success.

#### Polygon tier matters — Cloud Run Job timeout planning

| Polygon tier | Per-minute limit | 36-ticker run time | Recommended Cloud Run Job timeout |
|---|---|---|---|
| **Free**          | 5 req/min      | ~8 min  | **≥ 900s (15 min)** |
| Stocks Starter    | unlimited      | seconds | 300s |
| Developer         | unlimited + RT | seconds | 300s |

The default `--polygon-delay-seconds=13` is safe under free tier. If a paid
tier is in use, lower the delay (e.g. `--polygon-delay-seconds=0.3`) and
shorten the planned Cloud Run Job timeout accordingly.

#### Rollback SQL dry-run (safe to re-run)

```bash
# Validates the rollback DELETE template against the local dev DB
# inside BEGIN ... ROLLBACK. No data is ever persisted.
python scripts/validate_scanner_universe_rollback_sql.py
```

#### NOT YET DEPLOYED in production

- ❌ `quant-sync-eod-prices` Cloud Run Job — not created
- ❌ `quant-sync-eod-prices-schedule` Cloud Scheduler — not created
- ❌ Production Cloud SQL still has 4 instruments (NVDA, AAPL, MSFT, SPY) only
- ❌ No production write has happened from this code path

Daily incremental sync goes live only after explicit user sign-off and
all 10 acceptance criteria are green.

### Scanner Universe Production Bootstrap (Phase B3 Execution)

This section describes the production scaffolding bootstrap that creates
`instrument` + `instrument_identifier` + `ticker_history` rows for the 32
tickers identified during the B2 partial outcome (the full universe minus
the 4 protected tickers that already exist in production).

The bootstrap is split into two checkpoints:

- **B3.1** — code + CLI + tests + production redeploy. Code path lives in
  the deployed image; nothing is created or written in production.
- **B3.2** — backup + execution + post-flight verification. **Requires
  separate user sign-off in chat.**

#### When to use this command

Use the bootstrap when the seed module
(`sync-eod-prices-universe`) reports `instrument_id not resolved` for a
batch of tickers. That error means the parent rows
(`instrument` / `instrument_identifier` / `ticker_history`) do not exist;
the seed only writes `price_bar_raw` and assumes scaffolding is in place.

#### Plan a bootstrap (always safe — no DB writes, no API calls)

```bash
# Plan against LOCAL dev DB (read-only inspection of which tickers
# already have scaffolding rows; produces 0 FMP calls)
python -m apps.cli.main bootstrap-research-universe-prod --dry-run

# What it computes:
#   - target list = SCANNER_RESEARCH_UNIVERSE - PROTECTED_TICKERS  (32 tickers)
#   - protected exclusion list (NVDA / AAPL / MSFT / SPY)
#   - per-ticker already_exists status from instrument_identifier
#   - estimated_fmp_calls = ticker count NOT already scaffolded
#   - estimated_runtime_secs = estimated_fmp_calls × fmp_delay_seconds
#   - DB target classification + masked URL
#   - banned-trading-language check on plan descriptors
```

#### Run a bootstrap against LOCAL dev DB

```bash
python -m apps.cli.main bootstrap-research-universe-prod \
  --no-dry-run --write --db-target=local
```

This writes scaffolding for any tickers in `BOOTSTRAP_TARGET_TICKERS` not
already present in local DB. Already-scaffolded tickers are skipped (no
FMP call, no DB write). Intended for dev validation; production path uses
the four-flag handshake below.

#### Production write — requires FOUR explicit flags

```bash
python -m apps.cli.main bootstrap-research-universe-prod \
  --no-dry-run --write \
  --db-target=production --confirm-production-write
```

All four flags are mandatory. Missing any one of them produces a `REFUSED`
exit. The CLI also requires `DATABASE_URL_OVERRIDE` to point at Cloud SQL
(URL containing `/cloudsql/` OR `DB_TARGET_OVERRIDE=production`).

This command is **only intended to run inside a one-shot Cloud Run Job**
(see B3.2 Job Spec below). Bare CLI invocation against production from a
laptop is supported but discouraged — the Cloud Run Job provides the
audit trail (Cloud Logging + uniquely-named one-shot job).

#### B3.2 Job Spec (deferred — requires separate sign-off)

```yaml
name: quant-ops-research-universe-bootstrap
region: asia-east2
image: <SAME DIGEST as currently-serving quant-api revision>
command: python
args:
  - -m
  - apps.cli.main
  - bootstrap-research-universe-prod
  - --no-dry-run
  - --write
  - --db-target=production
  - --confirm-production-write
  - --fmp-delay-seconds=1.0
env:
  APP_ENV: production
  DB_TARGET_OVERRIDE: production   # public-IP DATABASE_URL form
secrets:
  DATABASE_URL_OVERRIDE: DATABASE_URL:latest
  FMP_API_KEY: FMP_API_KEY:latest
memory: 512Mi
task_timeout: 300s        # 5 min — 32 tickers × 1s pacing ≈ 32s + buffer
max_retries: 0
parallelism: 1
task_count: 1
```

**Image alignment policy**: same as the seed playbook — image digest must
match the currently-serving `quant-api` revision. Different image =
different code path = unsafe.

**Cleanup policy**: delete the one-shot job immediately after successful
post-flight verification. Do NOT leave it lying around.

#### B3.2 Cloud SQL Backup Plan

```bash
BACKUP_ID=$(gcloud sql backups create \
  --instance=quant-api-db \
  --description="pre-scanner-universe-bootstrap-$(date +%Y%m%d-%H%M)" \
  --project=secret-medium-491502-n8 \
  --format="value(id)")
echo "Backup ID: $BACKUP_ID"
```

Backup must be ≤ 30 minutes before B3.2 execution.

#### B3.2 Pre-flight Checks (must all PASS before execute)

1. `quant-api` revision contains the bootstrap code path (verify import
   in deployed image: `gcloud run services describe quant-api ...`)
2. Production has 4 instruments (baseline; NVDA / AAPL / MSFT / SPY)
3. Production `instrument_identifier` count for `id_type='ticker'` = 4
4. None of the 32 target tickers already have an `instrument_identifier`
   row (would imply a partial prior bootstrap — investigate before proceeding)
5. Cloud Run Job `quant-ops-research-universe-bootstrap` does NOT already
   exist (`gcloud run jobs list --region asia-east2`)
6. `FEATURE_T212_LIVE_SUBMIT=false` on the running quant-api revision
7. Cloud SQL backup just taken and `status = SUCCESSFUL`
8. Operator on-line for the duration

#### B3.2 Post-flight Verification

After the bootstrap job completes:

```sql
-- Expected counts after a successful B3.2 run:
SELECT 'instrument' AS table_name, COUNT(*) FROM instrument
UNION ALL
SELECT 'instrument_identifier', COUNT(*) FROM instrument_identifier
WHERE id_type='ticker'
UNION ALL
SELECT 'ticker_history', COUNT(*) FROM ticker_history;
-- instrument: 4 → 36
-- instrument_identifier (ticker): 4 → 36
-- ticker_history: should grow by 32 (one row per scaffolded ticker)

-- Verify no other tables changed:
SELECT 'price_bar_raw', COUNT(*) FROM price_bar_raw;        -- unchanged
SELECT 'corporate_action', COUNT(*) FROM corporate_action;  -- unchanged
SELECT 'earnings_event', COUNT(*) FROM earnings_event;      -- unchanged
```

#### B3.2 Rollback (if pre-flight check fails or post-flight unexpected)

```sql
-- Row-level rollback: removes only the bootstrap_prod-tagged rows.
-- Protected tickers (NVDA/AAPL/MSFT/SPY) are NOT touched because their
-- identifier rows have source != 'bootstrap_prod'.
DELETE FROM ticker_history
WHERE source = 'bootstrap_prod';

DELETE FROM instrument_identifier
WHERE id_type = 'ticker'
  AND source = 'bootstrap_prod';

DELETE FROM instrument
WHERE instrument_id IN (
  SELECT instrument_id FROM instrument_identifier  -- (orphans only — should be empty after the above)
);
-- The instrument-row delete is structured this way because the FK is from
-- identifier→instrument, not the other way around. After deleting all
-- bootstrap_prod identifiers + histories, the parent instrument rows
-- (which only those bootstrap_prod identifiers reference) become unreferenced
-- and can be deleted.
```

After rollback: re-run the dry-run to confirm `target_count=32` and
`already scaffolded=0` again, indicating clean state.

#### B3.2-A Execution Record (2026-04-30) — SUCCESS, scaffolding only

The B3.2-A scaffolding step was executed on 2026-04-30 with explicit user
authorization. The B3.2-B EOD price seed was deliberately NOT run.

| Item                  | Value                                                           |
| --------------------- | --------------------------------------------------------------- |
| Backup ID             | `1777585381061` (status `SUCCESSFUL`)                           |
| Backup description    | `pre-scanner-universe-bootstrap-20260430-2242`                  |
| Job name              | `quant-ops-research-universe-bootstrap`                         |
| Execution name        | `quant-ops-research-universe-bootstrap-x2blg`                   |
| Image digest          | `sha256:fbfef5126887b32bf3a6debe9bc8fb87eb30e5216e430cdc311bbd850dd216e8` |
| Container exit        | `exit(0)`                                                       |
| Runtime               | ~58.5 seconds                                                   |
| Result                | succeeded=32, failed=0, skipped=0                               |
| `instrument` Δ        | +32 (4 → 36)                                                    |
| `instrument_identifier` (ticker, universe) Δ | +32 (4 → 36)                            |
| `ticker_history` (universe) Δ | +32 (4 → 36)                                            |
| `price_bar_raw` Δ     | 0 (bootstrap does not write to `price_bar_raw` by design)        |
| Protected 4 unchanged | YES (NVDA / AAPL / MSFT / SPY untouched, same instrument_ids)   |
| `/api/health`         | 200 throughout                                                  |
| `FEATURE_T212_LIVE_SUBMIT` | `false` throughout                                         |
| Scheduler             | unchanged (only `quant-sync-t212-schedule` ENABLED)             |
| Jobs after cleanup    | only `quant-sync-t212` (bootstrap + 2 baseline-read jobs deleted) |

The post-bootstrap dry-run confirms idempotency: re-running the bootstrap
would now skip all 32 tickers (`already scaffolded=32, needs scaffolding=0`).

**B3.2-B (EOD price seed) status: COMPLETE — see B3.2-B Execution Record below.**

#### B3.2-B Execution Record (2026-04-30) — SUCCESS, 36/36 tickers seeded

The B3.2-B EOD seed step was executed on 2026-04-30 immediately after
B3.2-A. The 32 newly-scaffolded tickers were populated with full
historical EOD bars; the protected 4 had their data idempotently re-checked
within the 7-day lookback overlap (no shrinkage, no double-count).

| Item                      | Value                                                           |
| ------------------------- | --------------------------------------------------------------- |
| Backup ID                 | `1777587848839` (status `SUCCESSFUL`)                           |
| Backup description        | `pre-scanner-universe-seed-b32b-20260430-2324`                  |
| Job name                  | `quant-ops-research-universe-seed`                              |
| Execution name            | `quant-ops-research-universe-seed-4vqwx`                        |
| Image digest              | `sha256:fbfef5126887b32bf3a6debe9bc8fb87eb30e5216e430cdc311bbd850dd216e8` |
| Container exit            | `exit(0)`                                                       |
| Runtime                   | 509.2 seconds (~8.5 min)                                        |
| Polygon delay             | 13.0 s/call                                                     |
| Result                    | succeeded=36, failed=0                                          |
| `bars_inserted_total`     | 11,808                                                          |
| `bars_existing_or_skipped_total` | 24 (protected 4 lookback overlap — `ON CONFLICT DO NOTHING`) |
| `price_bar_raw` Δ         | +11,808 (1,344 → 13,152)                                        |
| `instrument` / `identifier` / `ticker_history` Δ | 0 / 0 / 0 (seed does not touch these tables) |
| Protected 4 unchanged     | YES (NVDA / AAPL / MSFT / SPY each at 336 bars, same as B3.2-A) |
| `/api/health`             | 200 throughout                                                  |
| `FEATURE_T212_LIVE_SUBMIT`| `false` throughout                                              |
| Scheduler                 | unchanged (only `quant-sync-t212-schedule` ENABLED)             |
| Jobs after cleanup        | only `quant-sync-t212` (seed + 3 transient read jobs deleted)   |
| `quant-sync-eod-prices`   | NOT CREATED (Phase C deferred)                                  |

Per-ticker bar counts:
- 4 protected (INCR mode, unchanged): 336 bars each = 1,344 total
- 32 newly-scaffolded (BOOTSTRAP mode): 369 bars each = 11,808 total
- Universe total: 13,152 bars (= 4×336 + 32×369, exact match)

Scanner OpenAPI verification (auth-unavailable smoke path):
- `/api/scanner/stock` present in production OpenAPI ✓
- `ScanResponse` / `ScanItem` `additionalProperties: false` (Pydantic `extra=forbid`) ✓
- Unauthenticated GET returns 401 (not 500) ✓

**Phase C daily incremental sync remains DEFERRED**. Creating
`quant-sync-eod-prices` Cloud Run Job + `quant-sync-eod-prices-schedule`
Cloud Scheduler requires separate authorization. The current state is
self-sufficient for scanner operation without Phase C.

### Scanner Universe Daily EOD Sync (Phase C Execution Playbook)

**STATUS: Phase C0 = docs only (this section).** Phase C1 (resource creation
+ first manual run) requires separate authorization in chat. Phase C2 (let
the scheduler run for one trading week, then declare stable) requires
review of C1 outcomes.

This section is the operator playbook for the daily incremental EOD sync.
The sync mirrors the existing `quant-sync-t212` pattern: a one-shot Cloud
Run Job triggered by Cloud Scheduler, image-pinned to whatever digest
`quant-api` is currently serving, secrets fetched from Secret Manager.

The same `sync-eod-prices-universe` CLI command used for the B3.2-B seed
is reused in incremental mode: at non-bootstrap time, every ticker has
`last_known_trade_date` ≥ recent and the planner generates a 7-day
lookback range — fetching at most ~5 trading days per ticker per run, of
which most are already-existing rows that get deduped via
`INSERT ... ON CONFLICT DO NOTHING`.

#### Why this design

1. **Reuse existing code**: the `sync-eod-prices-universe` command was
   already implemented for B3.2-B and is shipped in the production image.
   No new Python module, no new CLI command, no deploy needed at C1 time
   (assuming the image being pinned still contains the command).
2. **Reuse existing four-flag handshake**: `--no-dry-run --write
   --db-target=production --confirm-production-write` plus
   `DB_TARGET_OVERRIDE=production` — same as B3.2-B.
3. **Per-ticker isolation**: failure of one ticker (provider 429, network
   blip) does not abort the rest; the failed ticker simply reports the
   error and the next run picks it up.
4. **Idempotency at two layers**: planner skips already-fresh tickers
   (incremental window aware of `last_known_trade_date`), DB-level
   `ON CONFLICT DO NOTHING` deduplicates re-fetched bars within the
   7-day lookback.

#### Phase C1 Cloud Run Job Spec

```yaml
name: quant-sync-eod-prices
region: asia-east2
image: <digest of currently-serving quant-api revision at C1 time>
command: python
args:
  - -m
  - apps.cli.main
  - sync-eod-prices-universe
  - --universe=scanner-research
  - --no-dry-run
  - --write
  - --db-target=production
  - --confirm-production-write
  - --polygon-delay-seconds=13
env:
  APP_ENV: production
  PYTHONPATH: /app
  DB_TARGET_OVERRIDE: production
secrets:
  DATABASE_URL_OVERRIDE: DATABASE_URL:latest
  MASSIVE_API_KEY: MASSIVE_API_KEY:latest
  FMP_API_KEY: FMP_API_KEY:latest
memory: 512Mi
task_timeout: 900s   # 15 min — generous over the ~7.8-min expected runtime
max_retries: 0       # one-shot; failures need manual review (no retry storm)
parallelism: 1
task_count: 1
```

**Image alignment policy**: same as `quant-sync-t212` — pin to the
currently-serving `quant-api` revision's image digest at job-create time.
Use `scripts/sync-job-image.ps1 -CheckOnly` afterwards to verify alignment.
After every `quant-api` redeploy, re-run `scripts/sync-job-image.ps1`
WITHOUT `-CheckOnly` to update both `quant-sync-t212` AND
`quant-sync-eod-prices` to the new digest. Different image = different
code path = unsafe.

**`DB_TARGET_OVERRIDE` requirement**: production `DATABASE_URL` uses the
public-IP form (`host=34.150.76.29:5432`), not the Cloud SQL Unix-socket
form. The B1.1 fix shipped in `_classify_db_url` only classifies the URL
as production when `DB_TARGET_OVERRIDE=production` is set; without it the
planner refuses with `db_target=unknown`. The override DOES NOT bypass
the four-flag handshake.

#### Phase C1 Cloud Scheduler Spec

```yaml
name: quant-sync-eod-prices-schedule
location: asia-east2
schedule: "30 21 * * 1-5"   # 21:30 UTC, Monday–Friday
time_zone: UTC
target:
  cloud_run_job: quant-sync-eod-prices
  region: asia-east2
attempt_deadline: 1000s    # > task_timeout=900s + provisioning buffer
retry_config:
  retry_count: 0           # don't auto-retry; rely on next-day lookback
state: PAUSED              # initial state at C1; resume after first manual run passes
```

**Why 21:30 UTC weekdays**:
- US equity regular session closes 20:00 UTC (16:00 ET) when DST is in
  effect, 21:00 UTC (16:00 ET) when DST is not. Polygon's daily-aggregate
  endpoint typically has a finalised EOD bar 30–60 minutes after close.
  21:30 UTC is comfortably after both close cases and gives Polygon time
  to finalise the bar before we pull.
- The legacy `quant-sync-t212` already runs at 21:00 UTC (post-close
  position snapshot). Running EOD prices 30 minutes later avoids the
  Cloud Run cold-start window contention and keeps the two streams
  visually distinct in Cloud Logging timestamps.

**Why no weekend runs**:
- US equities don't trade on Saturday/Sunday or US market holidays.
  Running the sync on a non-trading day produces 0 new bars (the planner
  asks Polygon for bars in `[last_known - 7d, today]`; if no new trading
  day exists in that window, every returned bar is already in DB and
  gets deduped). Running has no harm but burns Polygon API quota and
  adds noise to Cloud Logging.
- The 7-day `--lookback-days` window means a Friday-evening run captures
  Mon–Fri bars; Monday–Wednesday runs capture the previous weekend
  through the latest close; etc. **Lookback covers worst-case 4-day
  market closure (e.g. Christmas Eve close + weekend + holiday)**. Any
  longer outage would need a manual replay run with a larger lookback.

**Why initially PAUSED**:
- Operator should manually execute the job once at C1 time to verify
  output before letting the scheduler tick. After that successful manual
  run, set scheduler to `ENABLED`. This matches the `quant-sync-t212`
  pattern.

#### Phase C1 First-Run Plan

```bash
# ---- Pre-flight (must all PASS) ----
# 1. Cluster state
gcloud run services describe quant-api --region=asia-east2 \
  --format="value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)"
gcloud run jobs list --region=asia-east2 --format="value(JOB)"
# Expected: only quant-sync-t212

gcloud scheduler jobs list --location=asia-east2 --format="value(ID,STATE)"
# Expected: only quant-sync-t212-schedule ENABLED

# 2. Dry-run sync plan against production (read-only)
#    Reuses the bootstrap-read pattern: temporary one-shot job with
#    --dry-run, then deleted.
gcloud run jobs create quant-ops-eod-sync-dryrun \
  --image=<digest from above> \
  --region=asia-east2 \
  --max-retries=0 --task-timeout=120 --memory=512Mi \
  --set-env-vars="APP_ENV=production,DB_TARGET_OVERRIDE=production" \
  --set-secrets=DATABASE_URL_OVERRIDE=DATABASE_URL:latest,FMP_API_KEY=FMP_API_KEY:latest,MASSIVE_API_KEY=MASSIVE_API_KEY:latest \
  --command=python \
  --args="-m,apps.cli.main,sync-eod-prices-universe,--dry-run"

gcloud run jobs execute quant-ops-eod-sync-dryrun --region=asia-east2 --wait

# Expected dry-run output:
#   ticker_count            : 36
#   bootstrap (no prior bars) : 0
#   incremental (existing)    : 36
#   db_target               : production
#   estimated_runtime_secs  : ~468 (~7.8 min)

gcloud run jobs delete quant-ops-eod-sync-dryrun --region=asia-east2 --quiet

# ---- Backup (REQUIRED for C1) ----
# Take a fresh Cloud SQL backup before the first scheduled-style run.
# C2+ scheduled runs do NOT require a backup per execution because
# (a) they are read-mostly via lookback, (b) writes are limited to
# price_bar_raw rows that get deduped on conflict, and (c) the seed
# already proved bar inserts are non-destructive. C1 backup is a
# checkpoint, not a per-run requirement.
BACKUP_ID=$(gcloud sql backups create \
  --instance=quant-api-db \
  --description="pre-eod-sync-c1-$(date +%Y%m%d-%H%M)" \
  --project=secret-medium-491502-n8 \
  --format="value(id)")
echo "Backup ID: $BACKUP_ID"
gcloud sql backups describe "$BACKUP_ID" --instance=quant-api-db \
  --format="value(status)"
# Wait until SUCCESSFUL.

# ---- Create the production Cloud Run Job ----
gcloud run jobs create quant-sync-eod-prices \
  --image=<digest from pre-flight read> \
  --region=asia-east2 \
  --max-retries=0 --task-timeout=900 --memory=512Mi \
  --set-env-vars="APP_ENV=production,DB_TARGET_OVERRIDE=production" \
  --set-secrets=DATABASE_URL_OVERRIDE=DATABASE_URL:latest,MASSIVE_API_KEY=MASSIVE_API_KEY:latest,FMP_API_KEY=FMP_API_KEY:latest \
  --command=python \
  --args="-m,apps.cli.main,sync-eod-prices-universe,--universe=scanner-research,--no-dry-run,--write,--db-target=production,--confirm-production-write,--polygon-delay-seconds=13"

# ---- First manual execution ----
gcloud run jobs execute quant-sync-eod-prices --region=asia-east2 --wait

# ---- Logs ----
gcloud logging read \
  'resource.type=cloud_run_job AND resource.labels.job_name=quant-sync-eod-prices' \
  --limit=300 --format='value(timestamp,textPayload)' --freshness=15m

# ---- Post-flight expected ----
# - exit(0)
# - SYNC RESULT: ticker_count=36, succeeded=36, failed=0
# - bars_inserted_total: typically 36 on a normal trading day (one new
#   bar per ticker for today's session); could be 0 on a weekend/holiday
#   manual run, or up to ~5×36 = 180 on the first run after a long gap
# - bars_existing_or_skipped_total: ~150–250 depending on how many
#   lookback days overlapped with already-stored bars
# - DB writes performed: price_bar_raw + source_run only (PRODUCTION Cloud SQL)
# - Cloud Run jobs created: NONE (the job ITSELF exists; no new jobs)
# - Scheduler changes: NONE
# - Production deploy: NONE
# - Execution objects: NONE
# - Broker write: NONE
# - Live submit: LOCKED (FEATURE_T212_LIVE_SUBMIT=false)

# ---- Create the scheduler (initially PAUSED) ----
gcloud scheduler jobs create http quant-sync-eod-prices-schedule \
  --location=asia-east2 \
  --schedule="30 21 * * 1-5" --time-zone=UTC \
  --uri="https://asia-east2-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/secret-medium-491502-n8/jobs/quant-sync-eod-prices:run" \
  --http-method=POST \
  --oauth-service-account-email=<scheduler invoker SA> \
  --attempt-deadline=1000s
gcloud scheduler jobs pause quant-sync-eod-prices-schedule --location=asia-east2

# ---- Resume after first run validated ----
gcloud scheduler jobs resume quant-sync-eod-prices-schedule --location=asia-east2
```

#### Monitoring & Freshness Policy

**Scanner stale threshold**: research candidates against bars older than
**3 US business days** are considered stale. The Stock Scanner UI's
`as_of` field surfaces the most recent `trade_date` across the universe;
operators reading the dashboard should treat any `as_of` older than 3
business days as a yellow signal.

**Expected max data age**:
- During scheduler ENABLED + healthy: ≤ 1 business day (today's bar
  available by 22:00 UTC, scanner reflects it within 30 minutes of the
  job's 21:30 UTC kickoff).
- After a single failed run: ≤ 2 business days (next-day's run with
  `--lookback-days=7` re-pulls the missed day).
- After 3 consecutive failed runs: stale. Operator must intervene.

**What to check if a job fails**:
1. Cloud Logging:
   ```bash
   gcloud logging read \
     'resource.type=cloud_run_job AND resource.labels.job_name=quant-sync-eod-prices AND severity>=ERROR' \
     --limit=50 --freshness=2h --format='value(timestamp,textPayload)'
   ```
2. Most recent execution status:
   ```bash
   gcloud run jobs executions list --job=quant-sync-eod-prices \
     --region=asia-east2 --limit=5
   ```
3. Per-ticker failure list — the SYNC RESULT block at the end of the log
   lists `failed[]` with the per-ticker error (Polygon 429 / FMP error /
   instrument_id missing).
4. Provider status (Polygon / FMP) — if all 36 tickers failed with
   identical error text, suspect a provider outage rather than a
   per-ticker issue.

**Suggested DQ rule (NOT IMPLEMENTED in C0)**: future DQ rule
`scanner_universe_freshness` checking that `MAX(trade_date)` in
`price_bar_raw` for any of the 36 universe instruments is no older than
3 US business days. Implementation deferred — would live in
`libs/dq/rules.py` alongside the existing 11 checks.

**Suggested alert (NOT IMPLEMENTED in C0)**: Cloud Monitoring alert on
3 consecutive `quant-sync-eod-prices` job failures within 72 hours.
Implementation deferred — needs Cloud Monitoring alert policy + email
channel setup, separate from this playbook.

#### Failure Handling

| Failure mode                          | Behavior                                                                                                                         | Operator action                                                                  |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Polygon 429 (free-tier rate limit)    | Per-ticker isolation; the affected ticker(s) fall through to FMP fallback. If FMP also fails, ticker is marked failed and skipped. | Verify with logs; next-day's lookback covers the gap. Don't manually rerun. |
| FMP fallback also errors              | Ticker marked failed; other 35 tickers proceed.                                                                                   | Same as above; next day usually clears it.                                       |
| Provider transient network blip       | Per-ticker retry within the same run is NOT performed (max_retries=0). Affected tickers fail.                                     | Same as above.                                                                   |
| All 36 tickers fail (provider outage) | Job exits 0 with `succeeded=0, failed=36`. No bars written; DB unchanged.                                                         | Investigate provider; pause scheduler if outage > 24 h; resume after recovery.  |
| Job timeout (> 900 s)                 | Container killed; partial bars committed (per-ticker commit guarantees in-flight ticker's success persists).                      | Inspect logs to find which ticker hung; consider raising `task_timeout` or removing the offender from the universe (with sign-off). |
| `instrument_id not resolved`          | A scaffolding regression — should not occur after B3.2-A. Indicates `instrument_identifier` row was deleted/altered.              | STOP. Investigate scaffolding. Re-run B3.2-A bootstrap with sign-off. Pause scheduler. |
| Cloud SQL connection refused          | Job fails immediately at planner (DB target classification fails).                                                                | Check Cloud SQL instance + DATABASE_URL secret; pause scheduler until DB is healthy. |

**No-auto-rerun policy**: a failed run is NOT auto-retried in the same
window. The 7-day lookback on the next run is the recovery mechanism.
Manual rerun is permitted only when (a) the operator has investigated
logs, (b) the failure root cause is fixed, and (c) the user has explicitly
authorized.

**When to pause the scheduler**:
- 3 consecutive job failures within 72 hours
- Provider outage affecting all 36 tickers
- A regression in scaffolding (`instrument_id not resolved` for ≥ 1 ticker)
- Any unexpected DB write outside `price_bar_raw` / `source_run`
- Any execution object appearing in `order_intent` / `order_draft`

**When to run a manual dry-run**:
- After ANY pause / resume cycle, before re-enabling
- After any `quant-api` redeploy (to confirm image alignment held)
- Before adding a new ticker to the universe (capacity check)
- Quarterly, as a sanity smoke

**Escalation path**: anything not in the table above → STOP scheduler →
report to user → wait for sign-off before resuming.

#### Phase C Guardrails

| Item                                  | Status |
| ------------------------------------- | ------ |
| DB writes from C1+                    | Limited to `price_bar_raw` + `source_run` (verified by `sync_eod_prices_universe.execute_sync` source). |
| `instrument` writes                   | NEVER (only B3.2-A scaffolding writes instruments; the scheduler does NOT). |
| `instrument_identifier` writes        | NEVER. |
| `ticker_history` writes               | NEVER. |
| `corporate_action` / `earnings_event` | NEVER touched by this job. |
| `watchlist_*` writes                  | NEVER. |
| `broker_*` writes                     | NEVER (broker tables are only modified by the unrelated `quant-sync-t212` job). |
| `order_intent` / `order_draft`        | NEVER created. |
| `FEATURE_T212_LIVE_SUBMIT`            | Remains `false`; this job does NOT toggle it. |
| `BANNED_WORDS` set in scanner service | Unchanged by this job. |
| Scanner Pydantic schema strictness    | Unchanged. |
| Scanner explanation generator         | Unchanged. |

#### Phase C1 Acceptance Criteria

A C1 execution will be considered SUCCESSFUL only when ALL of the
following are TRUE:

| # | Criterion                                                                                                                                    |
|---|----------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | Phase C0 docs committed (this section + plan-doc Section C0 + memory) and pushed to `origin/master`.                                         |
| 2 | Production Scanner UI smoke (manual or via Chrome MCP) confirmed `scanned=36, matched>0, data_mode=daily_eod` since the last quant-api redeploy. |
| 3 | `quant-sync-eod-prices` Cloud Run Job created with image digest matching the currently-serving `quant-api` revision.                          |
| 4 | `quant-sync-eod-prices-schedule` Cloud Scheduler created in PAUSED state (resumed only after #5 passes).                                      |
| 5 | First manual execution of the job completed with exit(0), `succeeded=36, failed=0`, DB writes limited to `price_bar_raw + source_run`.        |
| 6 | `gcloud run jobs list --region=asia-east2` returns exactly `{quant-sync-t212, quant-sync-eod-prices}` — no other jobs.                        |
| 7 | `gcloud scheduler jobs list --location=asia-east2` returns exactly `{quant-sync-t212-schedule, quant-sync-eod-prices-schedule}`.              |
| 8 | `FEATURE_T212_LIVE_SUBMIT=false` on the running quant-api revision (unchanged from current state).                                            |
| 9 | Scanner endpoint still returns `scanned=36` after the first run (no instruments removed; only bars added).                                    |
| 10| Zero new rows in `order_intent` / `order_draft` / any broker table from this job (broker tables only change via scheduled `quant-sync-t212`). |

A failure on ANY criterion → C1 paused, root cause investigated, user
sign-off required to resume.

#### What Phase C0 EXPLICITLY Does NOT Do

> **Phase C0 is documentation only.** No Cloud Run Job is created. No
> Cloud Scheduler is created. No production deploy is performed. No DB
> writes happen. No sync is executed. No broker / execution / live-submit
> changes occur. Phase C1 (resource creation + first manual run) requires
> a separate, explicit sign-off in chat from the user.

#### Phase C1 Execution Record (2026-05-01) — SUCCESS, scheduler PAUSED

The C1 step was executed on 2026-05-01 with explicit user authorization.
Scope: create job + scheduler PAUSED, run job once manually, verify, leave
scheduler PAUSED until separate authorization to resume.

| Item                              | Value                                                                                                       |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Cloud Run Job created             | `quant-sync-eod-prices`                                                                                     |
| Cloud Scheduler created           | `quant-sync-eod-prices-schedule` (state: **PAUSED**)                                                        |
| Image digest                      | `sha256:f18896499acad06ef98cce2b0b4126c254429d7a6c4c12c09f1443098d6528ad` (matches `quant-api-00035-kpz`)   |
| Manual execution name             | `quant-sync-eod-prices-m55rt`                                                                               |
| Container exit                    | `exit(0)`                                                                                                    |
| Runtime                           | 480.2 seconds (~8 min)                                                                                       |
| Result                            | `succeeded=36, failed=0, bars_inserted_total=0, bars_existing_or_skipped_total=216`                         |
| `price_bar_raw` Δ                 | 0 (idempotent: 36 tickers × 6 lookback trading days ≈ 216 already-existing bars deduplicated via ON CONFLICT) |
| `instrument` / `instrument_identifier` / `ticker_history` Δ | 0 / 0 / 0 (seed does not touch these tables)                                              |
| Protected 4 unchanged             | YES (NVDA / AAPL / MSFT / SPY untouched)                                                                    |
| `/api/health`                     | 200 throughout                                                                                              |
| `FEATURE_T212_LIVE_SUBMIT`        | `false` throughout                                                                                          |
| `quant-sync-t212` + schedule      | UNCHANGED (`quant-sync-t212-schedule` still `ENABLED`)                                                      |
| Scheduler-triggered execution     | NONE (scheduler was paused before any 21:30 UTC tick fired)                                                  |
| Cleanup                           | Transient `quant-ops-status-read-pre-c1` deleted; production `quant-sync-eod-prices` job + scheduler retained |
| Final jobs list                   | `{quant-sync-t212, quant-sync-eod-prices}`                                                                  |
| Final scheduler list              | `quant-sync-t212-schedule (ENABLED)`, `quant-sync-eod-prices-schedule (PAUSED)`                             |

**Scheduler intentionally PAUSED** — the user has not yet authorized
resume. The first scheduled tick would be the next weekday 21:30 UTC.
Resume command (NOT executed):
```bash
gcloud scheduler jobs resume quant-sync-eod-prices-schedule \
  --location=asia-east2
```

The same-day manual re-run produced 0 net writes — exactly the
idempotency property doing its job. The first SCHEDULED run after the
next US trading session closes will produce `bars_inserted_total ≈ 36`
(one new bar per ticker for that session) plus the same 216 dedupe
overlap from the 7-day lookback.

**Phase C2 (observation window) status: NOT STARTED**. C2 requires the
scheduler to be `ENABLED` and observed for ≥ 5 scheduled runs (one full
US trading week). It requires separate authorization.

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
