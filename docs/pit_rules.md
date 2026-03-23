# Point-in-Time (PIT) Rules

## What is `reported_at`?
`reported_at` is the timestamp when a financial fact became publicly available. It is stored on `financial_period` and represents the moment when an investor could first have known this data.

## The asof_date Rule

**All research queries, factor computations, screeners, event studies, and strategy signals MUST use an explicit `asof_date` parameter.**

This is enforced at the function signature level. Every research and strategy function requires `asof_date` as a parameter. There is no default that silently uses "today's date."

### Where asof_date is enforced:

| Layer | Functions | Enforcement |
|-------|-----------|-------------|
| Research: Factors | `daily_returns`, `rolling_volatility`, `cumulative_return`, `drawdown`, `relative_strength`, `momentum`, `valuation_snapshot`, `performance_summary` | Required `asof_date` parameter |
| Research: Screeners | `screen_by_liquidity`, `screen_by_returns`, `screen_by_fundamentals`, `rank_universe` | Required `asof_date` parameter |
| Research: Event Study | `earnings_event_study`, `earnings_event_study_summary` | Required `asof_date` parameter |
| Research: PIT Views | `get_latest_financials_pit` | Filters by `reported_at <= asof_date` |
| Strategy: Signals | `SignalProvider.generate_signals` | Required `asof_date` parameter |
| Strategy: Universe | `UniverseProvider.get_universe` | Required `asof_date` parameter |

### API endpoint enforcement:

All research and backtest API endpoints accept an `asof` query parameter. If not provided, they default to `date.today()` at the API boundary -- but the underlying functions always receive an explicit date.

## PIT Query Pattern

```sql
-- Correct: only see financials that were public as of the query date
SELECT * FROM financial_period fp
JOIN financial_fact_std ffs ON ffs.period_id = fp.period_id
WHERE fp.instrument_id = :iid
  AND fp.reported_at <= :asof_date
ORDER BY fp.period_end DESC;
```

```sql
-- WRONG: this uses period_end which creates look-ahead bias
SELECT * FROM financial_period fp
WHERE fp.period_end <= :some_date;  -- DO NOT DO THIS
```

## How reported_at is determined

1. **Primary source (production)**: SEC EDGAR `acceptedDate` from filing metadata
2. **SEC companyfacts**: `filed` date from XBRL facts
3. **Last resort**: `ingested_at` (clearly marked as approximation)

## Fields that MUST NOT be mixed
- `period_end` (when the fiscal period ended) is NOT the same as `reported_at` (when data became public)
- A Q4 2025 report might have `period_end=2025-12-31` but `reported_at=2026-02-15`
- Using `period_end` instead of `reported_at` creates look-ahead bias

## Why This Matters for Backtesting

The backtest engine calls the same research functions used for live analysis. Because all functions require explicit `asof_date`, the backtest naturally avoids look-ahead bias:

1. On each simulation date, the engine passes that date as `asof_date`
2. Factor computations only see prices up to that date
3. Financial data only includes facts that were publicly reported by that date
4. Screener rankings reflect only information available at that point in time

This means a strategy that screens for low P/E stocks on 2024-01-15 will only see Q3 2023 financials (reported in October/November) -- not Q4 2023 financials that were filed in February 2024.

## Macro PIT (Future)

- Macro observations will use `realtime_start` / `realtime_end` for vintage tracking
- Initial releases are often revised -- each revision would be a separate observation
- Not yet implemented (macro adapters are skeletons)
