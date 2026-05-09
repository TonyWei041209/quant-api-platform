# Overnight Taxonomy Market Brief — Plan

Status: design + scaffolded code (not executed). Production job/scheduler creation deferred to a separate authorization.

## 1. Goal

Produce a next-morning research brief that ranks anomaly candidates across the broad market using the taxonomy from `libs/scanner/market_taxonomy.py`. The brief is **research-only** and feeds the Scanner / Market Events surfaces — never the execution layer.

## 2. Proposed job

| Field | Value |
|---|---|
| Job name | `quant-scan-taxonomy-overnight` |
| Region | `asia-east2` |
| Image | pinned to current `quant-api` digest at create time |
| `max_retries` | **0** |
| `task_timeout` | **3600s** (60 min) |
| Memory | 1Gi (provider fan-out + scoring) |
| Env | `APP_ENV=production`, `DB_TARGET_OVERRIDE=production`, `PYTHONPATH=/app`, `FEATURE_OVERNIGHT_BRIEF_PERSIST=false` |
| Secrets | `DATABASE_URL_OVERRIDE`, `FMP_API_KEY`, `MASSIVE_API_KEY` (existing) |
| Scheduler | `quant-scan-taxonomy-overnight-schedule`, cron `15 22 * * 1-5` UTC (45 min after EOD sync), **initial state PAUSED** |

## 3. Flow

1. Read provider universe metadata (FMP profile + Massive grouped EOD where supported).
2. Pull bulk/grouped EOD bars for last 30 trading days. **Hard cap** at 5 000 tickers per call.
3. Earnings calendar for next 7 days (single FMP call, capped).
4. News for the **top 50 preliminary candidates** only (never unbounded all-market news).
5. Compute anomaly scores per the formula in §4.
6. Persist:
   - Top 100 global → `scanner_run` + `scanner_candidate_snapshot`
   - Top 20 per broad category
   - Top 10 per subcategory
7. Render the next-morning brief into a static markdown / JSON artifact for the Dashboard widget. **No trading instructions.**

## 4. Anomaly score (research-only)

Features:
```
ret_1d, ret_5d, ret_1m,
volume_ratio_20d,
volatility_20d,
range_52w_position,
distance_to_52w_high,
momentum_acceleration = ret_5d - 0.2*ret_1m,
relative_strength_vs_spy, relative_strength_vs_qqq,
earnings_within_7d (bool),
recent_news_count, news_recency_hours,
mirror_source_tags, mapping_status
```

Outputs:
- `anomaly_score_global` ∈ [0, 100]
- `anomaly_score_within_category` ∈ [0, 100]
- `anomaly_score_within_subcategory` ∈ [0, 100]
- `research_priority` ∈ {1, 2, 3, 4, 5}
- `catalyst_score` ∈ [0, 100]  (earnings_within_7d + news activity)
- `risk_flags` (list of strings: `low_volume`, `high_volatility`, `gap_recent`, `pump_pattern_warning`, etc.)

Scoring is purely deterministic and rule-based. **Not a prediction.** Documented in this doc and pinned by tests.

## 5. Language policy (banned phrases reaffirmed)

The brief **must not** contain: `buy`, `sell`, `entry`, `target price`, `position sizing`, `guaranteed`, `必涨`, `买入建议`, `目标价`, `仓位建议`, `入场`, `建仓` (or any close synonym) outside negation-disclaimer sentences. Allowed positive language: `research candidate`, `unusual relative to peer group`, `requires validation`, `catalyst watch`.

## 6. Side-effect attestations (when run)

| | Status when run |
|---|---|
| Production DB writes | ONLY `scanner_run` + `scanner_candidate_snapshot` rows (P6 schema). Never `price_bar_raw`, `corporate_action`, `earnings_event`, broker tables, watchlist tables, order tables. |
| Cloud Run jobs created | Just the one (`quant-scan-taxonomy-overnight`) on first run. |
| Scheduler | Stays PAUSED until first manual run validates. |
| Live submit | LOCKED throughout. |
| Broker write | NONE. |
| Order objects | NONE. |
| Provider HTTP calls | bounded — see §3 caps. |

## 7. Production gate

The job **may** be created tonight by a separate authorization, but only after:
1. P6 (scanner_run + scanner_candidate_snapshot) migration is applied.
2. The taxonomy module is exercised in production via the read-only routes (P1 deployed, ✓).
3. A first **manual bounded run** (limit=100, scope=mirror) succeeds.

Until those preconditions are met, the brief job and scheduler do **not** exist in production.

## 8. Rollback

The job is delete-then-recreate at the resource level; the scheduler can be deleted in one gcloud call. The persisted rows (P6) carry a per-run `scanner_run.id` allowing surgical row-level deletion if a single run is invalidated.
