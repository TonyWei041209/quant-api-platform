"""Research-only prediction rule library.

Pure-function rule engines for premarket shadow predictions. NEVER
imports from `libs.execution`, NEVER touches broker / order /
execution tables, NEVER mutates `FEATURE_T212_LIVE_SUBMIT`, NEVER
calls a Trading 212 endpoint, NEVER calls a provider HTTP endpoint.

Rule modules accept a structured input dict (per-ticker brief
candidate + market regime input), apply deterministic categorical
thresholds documented in `docs/premarket-shadow-test-*-rule-*-pre-registration.md`,
and return a prediction dict. Production wiring is intentionally
deferred — a downstream caller decides whether to persist the
prediction to a docs JSON; this package itself never persists.

Active modules:

  * rule_v2 — Shadow Test #4 ruleset
    (`docs/premarket-shadow-test-4-rule-v2-pre-registration.md`)
"""
from libs.prediction.rule_v2 import (
    Regime,
    PerTickerInput,
    PredictionRow,
    compute_market_regime,
    compute_per_ticker,
    bucket_midpoint_pct,
    actual_direction_band,
    direction_correct,
    # v2.1 amendment additions (additive — v2 surface unchanged)
    MAX_ANCHOR_LAG_TRADING_DAYS,
    V21_HORIZON_LABEL,
    is_eligible_latest_anchor,
    compute_per_ticker_v21,
)

__all__ = [
    "Regime",
    "PerTickerInput",
    "PredictionRow",
    "compute_market_regime",
    "compute_per_ticker",
    "bucket_midpoint_pct",
    "actual_direction_band",
    "direction_correct",
    "MAX_ANCHOR_LAG_TRADING_DAYS",
    "V21_HORIZON_LABEL",
    "is_eligible_latest_anchor",
    "compute_per_ticker_v21",
]
