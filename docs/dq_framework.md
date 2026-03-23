# Data Quality Framework

## Severity Levels
- **INFO**: Observation, no action needed
- **WARNING**: Potential issue, review recommended
- **ERROR**: Data integrity violation, must be resolved
- **CRITICAL**: Severe issue blocking downstream processing

## Rules (11 Active)

| Code | Description | Table | Severity | Module |
|------|-------------|-------|----------|--------|
| DQ-1 | OHLC logic: high >= max(O,C,L), low <= min(O,C,H) | price_bar_raw | ERROR | `price_rules.py` |
| DQ-2 | Non-negative: price >= 0, volume >= 0 | price_bar_raw | ERROR | `price_rules.py` |
| DQ-3 | Duplicate accession numbers | filing | ERROR | `filing_rules.py` |
| DQ-4 | Trading day consistency (trade_date in exchange_calendar) | price_bar_raw | WARNING | `price_rules.py` |
| DQ-5 | Corporate action validity (ratio > 0, div >= 0, ex_date required) | corporate_action | ERROR | `corporate_action_rules.py` |
| DQ-6 | PIT: reported_at must exist and be reasonable | financial_period | ERROR | `pit_rules.py` |
| DQ-7 | Cross-source price divergence (flags discrepancies between sources) | price_bar_raw | WARNING | `price_rules.py` |
| DQ-8 | Stale price data gaps (identifies instruments with missing recent data) | price_bar_raw | WARNING | `price_rules.py` |
| DQ-9 | Ticker history overlap (overlapping date ranges for same ticker) | ticker_history | ERROR | `identifier_rules.py` |
| DQ-10 | Orphan identifiers (identifiers referencing non-existent instruments) | instrument_identifier | ERROR | `identifier_rules.py` |
| DQ-11 | Raw/adjusted contamination (flags rows where source indicates adjusted data in raw table) | price_bar_raw | ERROR | `price_rules.py` |

## Rule Modules

```
libs/dq/
  rules.py                   # Orchestrator: runs all rules, records issues
  price_rules.py             # DQ-1, DQ-2, DQ-4, DQ-7, DQ-8, DQ-11
  filing_rules.py            # DQ-3
  corporate_action_rules.py  # DQ-5
  pit_rules.py               # DQ-6
  identifier_rules.py        # DQ-9, DQ-10
  reporting.py               # record_issue() helper
```

## Execution

```bash
# Run all DQ checks (results written to data_issue table)
python -m apps.cli.main run-dq

# Run DQ and show detailed report
python -m apps.cli.main dq-report

# Check status including DQ summary
python -m apps.cli.main status
```

Or via Makefile:
```bash
make cli-run-dq
```

## Issue Tracking

Issues are written to the `data_issue` table with:
- `rule_code`: Which rule flagged it (e.g., DQ-1)
- `severity`: INFO / WARNING / ERROR / CRITICAL
- `table_name`: Which table the issue relates to
- `record_key`: Identifier for the specific record
- `details`: JSONB with additional context
- `resolved_flag`: Boolean, default false
- `issue_time`: When the issue was detected

## Notes on Current Data

With yfinance_dev as the data source for prices, corporate actions, and earnings:
- DQ-7 (cross-source divergence) has limited utility since there is only one source per data type
- DQ-8 (stale prices) may flag gaps in yfinance data
- DQ-11 (raw/adjusted contamination) validates that yfinance_dev data is correctly stored as raw unadjusted prices

When production sources (Massive/Polygon, FMP) are configured, DQ-7 becomes critical for validating consistency between sources during migration.
