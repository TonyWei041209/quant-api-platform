# Runbook

## Local Development Setup

```bash
# Start PostgreSQL
make up

# Install dependencies
pip install -e ".[dev]"

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
make down
make up
# Wait for postgres to start
make db-upgrade
```

## Ingestion Operations

```bash
# Bootstrap security master (first run)
make cli-bootstrap-security-master

# Sync EOD prices for a ticker
python -m apps.cli.main sync-eod-prices --ticker AAPL --instrument-id <UUID> --from-date 2024-01-01 --to-date 2024-12-31

# Sync corporate actions
python -m apps.cli.main sync-corporate-actions --ticker AAPL --instrument-id <UUID>

# Sync fundamentals
python -m apps.cli.main sync-fundamentals --symbol AAPL --instrument-id <UUID>

# Sync Trading 212 (read-only)
python -m apps.cli.main sync-trading212 --demo
```

## Data Quality

```bash
# Run all DQ checks
make cli-run-dq

# Check results
# SELECT * FROM data_issue ORDER BY issue_time DESC;
```

## Testing

```bash
make test           # All tests
make test-unit      # Unit only
make test-integration  # Integration (needs DB)
make lint           # Lint check
make fmt            # Auto-format
```

## Troubleshooting

### API won't start
1. Check PostgreSQL is running: `docker compose ps`
2. Check .env file exists and has correct DB credentials
3. Check migrations are applied: `make db-upgrade`

### Ingestion fails
1. Check API keys in .env
2. Check rate limits (logs will show 429 errors)
3. Check `source_run` table for error messages

### DQ finds issues
1. Check `data_issue` table for details
2. Review raw_payload in source table
3. Re-run ingestion if needed
