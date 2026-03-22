# Data Quality Framework

## Severity Levels
- **INFO**: Observation, no action needed
- **WARNING**: Potential issue, review recommended
- **ERROR**: Data integrity violation, must be resolved
- **CRITICAL**: Severe issue blocking downstream processing

## Rules

| Code | Description | Table | Severity |
|------|-------------|-------|----------|
| DQ-1 | OHLC logic: high >= max(O,C,L), low <= min(O,C,H) | price_bar_raw | ERROR |
| DQ-2 | Non-negative: price >= 0, volume >= 0 | price_bar_raw | ERROR |
| DQ-3 | Duplicate accession numbers | filing | ERROR |
| DQ-4 | Trading day consistency (trade_date in calendar) | price_bar_raw | WARNING |
| DQ-5 | Corporate action validity (ratio > 0, div >= 0, ex_date required) | corporate_action | ERROR |
| DQ-6 | PIT: reported_at must exist and be reasonable | financial_period | ERROR |

## Execution
- All rules run via CLI: `make cli-run-dq`
- Issues written to `data_issue` table
- Each issue includes: rule_code, severity, table_name, record_key, details (JSONB)

## Future Rules (Phase 2+)
- Ticker history interval overlap
- Raw/adjusted contamination detection
- Cross-source price divergence threshold
- Stale data detection
