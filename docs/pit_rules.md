# Point-in-Time (PIT) Rules

## What is `reported_at`?
`reported_at` is the timestamp when a financial fact became publicly available. It is stored on `financial_period` and represents the moment when an investor could first have known this data.

## PIT Query Rule
**All research queries MUST enforce: `reported_at <= asof_time`**

This prevents look-ahead bias in backtesting and ensures research results reflect only information that was available at the time.

## How PIT is determined
1. **Primary source**: SEC EDGAR `acceptedDate` from filing metadata
2. **Fallback**: FMP `fillingDate` or `acceptedDate`
3. **Last resort**: `ingested_at` (clearly marked as approximation)

## Fields that MUST NOT be mixed
- `period_end` (when the fiscal period ended) ≠ `reported_at` (when data became public)
- A Q4 2025 report might have period_end=2025-12-31 but reported_at=2026-02-15
- Using period_end instead of reported_at creates look-ahead bias

## Macro PIT
- Macro observations use `realtime_start` / `realtime_end` for vintage tracking
- Initial releases are often revised — each revision is a separate observation
- Phase 2 will implement full vintage support
