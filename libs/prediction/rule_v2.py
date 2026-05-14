"""Premarket Shadow Test #4 — Rule v2 (pure-function helper).

Canonical pre-registration:
``docs/premarket-shadow-test-4-rule-v2-pre-registration.md``.

The module implements three deterministic pieces:

  * ``compute_market_regime``     — one signal per run from SPY+QQQ
  * ``compute_per_ticker``        — per-ticker prediction dict
  * ``actual_direction_band`` /
    ``direction_correct``         — eval-side classifier

Every function in this module is **pure**: no DB call, no HTTP, no
file I/O, no logging side-effect on success path. Production wiring
(which brief to read, where to persist the prediction JSON, when to
commit) is intentionally deferred — the operator-led runbook decides
that per cycle.

Strict scope guards (anchored by ``tests/unit/test_prediction_rule_v2.py``):

  * No reference to ``OrderIntent`` / ``OrderDraft`` / ``submit_*_order``.
  * No reference to ``FEATURE_T212_LIVE_SUBMIT``.
  * No call to any provider adapter or HTTP client.
  * No buy/sell/target/position-sizing language in any field name,
    label, or returned string.
  * No mutation of any pre-existing 2026-05-12 v1 artifact (this is
    a separate module — by construction the v1 artifacts are not
    re-touched).

The module ships *forward-looking only*. Applying it to historical
v1 data would be retroactive backfill and is explicitly forbidden by
the pre-registration §13.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal


# ---------------------------------------------------------------------------
# Tunable thresholds — these mirror the pre-registration doc verbatim.
# They are exposed as module constants so a downstream tool can read
# the canonical values without re-parsing markdown.
# ---------------------------------------------------------------------------

# §5 Market regime
REGIME_NEGATIVE_THRESHOLD = -1.0   # %  SPY+QQQ 1D both <= this → negative
REGIME_POSITIVE_THRESHOLD = +1.0   # %  SPY+QQQ 1D both >= this → positive
REGIME_5D_NEG = -2.0               # %  fallback to negative_5d when 1D mixed
REGIME_5D_POS = +2.0               # %  (not used as a direction signal alone)

# §6 Momentum / extension / news
MOMENTUM_UP_PCT = +2.0
MOMENTUM_DOWN_PCT = -2.0

EXTENSION_HIGH_W52 = 95.0
EXTENSION_HIGH_D1 = +8.0
EXTENSION_LOW_W52 = 5.0
EXTENSION_LOW_D1 = -8.0

NEWS_STRONG_COUNT = 5
NEWS_STRONG_VOLR = 1.5
NEWS_STRONG_PRIORITY = 4
NEWS_MEDIUM_COUNT = 3
NEWS_MEDIUM_VOLR = 1.2

# §7 Eval-side classification
ACTUAL_DIRECTION_EPSILON_PCT = 0.5  # ±50 bps relaxed from v1's 10 bps
ACTUAL_FLAT_BAND_PCT = 0.1          # |return| < 0.1 % is "flat-flat"


Regime = Literal["negative", "negative_5d", "neutral", "positive", "unknown"]
DirectionLabel = Literal["up", "flat-up", "flat-down", "down"]
ConfidenceLabel = Literal["low", "medium", "high"]
BucketLabel = Literal[
    "above_plus_3",
    "plus_1_to_plus_3",
    "minus_1_to_plus_1",
    "minus_3_to_minus_1",
    "below_minus_3",
]


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass
class PerTickerInput:
    """Structured per-ticker input. Either constructed by hand in
    tests, or built from a persisted brief candidate row by the
    operator-led runbook.

    All fields are nullable to model real-world missing data — the
    rule decides what to do when fields are missing.
    """
    ticker: str
    change_1d_pct: float | None = None
    change_5d_pct: float | None = None
    change_1m_pct: float | None = None
    week52_position_pct: float | None = None
    volume_ratio: float | None = None
    signal_strength: str | None = None  # "low"|"medium"|"high"|None
    risk_flags: tuple[str, ...] = ()
    scan_types: tuple[str, ...] = ()
    recent_news_count: int = 0
    upcoming_earnings_count: int = 0
    research_priority: int = 1
    source_tags: tuple[str, ...] = ()
    mapping_status: str = "unmapped"

    @property
    def data_quality(self) -> str:
        """Pure classification — mirrors the v1 helper."""
        if self.change_1d_pct is None:
            return "weak"
        if (self.recent_news_count == 0
                and self.upcoming_earnings_count == 0
                and self.signal_strength is None):
            return "partial"
        return "complete"


@dataclass
class PredictionRow:
    """One ticker's prediction. The fields here match what a future
    ``docs/premarket-shadow-prediction-YYYYMMDD-v2.json`` will carry
    in its ``predictions[]`` array. NO buy/sell/target/position-sizing
    keys.
    """
    ticker: str
    eligible: bool
    not_eligible_reason: str | None = None
    momentum_signal: int = 0
    extension_signal: int = 0
    news_signal: int = 0
    regime_signal: int = 0
    composite: int = 0
    predicted_direction: DirectionLabel | None = None
    predicted_return_bucket: BucketLabel | None = None
    confidence: ConfidenceLabel | None = None
    data_quality: str = "weak"
    rationale_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "eligible": self.eligible,
            "not_eligible_reason": self.not_eligible_reason,
            "decision": {
                "momentum_signal": self.momentum_signal,
                "extension_signal": self.extension_signal,
                "news_signal": self.news_signal,
                "regime_signal": self.regime_signal,
                "composite": self.composite,
            },
            "predicted_direction": self.predicted_direction,
            "predicted_return_bucket": self.predicted_return_bucket,
            "confidence": self.confidence,
            "data_quality": self.data_quality,
            "rationale_factors": list(self.rationale_factors),
        }


# ---------------------------------------------------------------------------
# §5 — Market regime
# ---------------------------------------------------------------------------


def compute_market_regime(
    spy_change_1d_pct: float | None,
    qqq_change_1d_pct: float | None,
    spy_change_5d_pct: float | None = None,
    qqq_change_5d_pct: float | None = None,
) -> Regime:
    """Classify the broad-market regime for the run. One signal per
    run, not per ticker. Inputs are read once from the brief snapshot's
    SPY and QQQ rows.

    Returns ``"unknown"`` (fail-safe — do NOT bias direction) when
    either 1D input is None.
    """
    if spy_change_1d_pct is None or qqq_change_1d_pct is None:
        return "unknown"
    if (spy_change_1d_pct <= REGIME_NEGATIVE_THRESHOLD
            and qqq_change_1d_pct <= REGIME_NEGATIVE_THRESHOLD):
        return "negative"
    if (spy_change_1d_pct >= REGIME_POSITIVE_THRESHOLD
            and qqq_change_1d_pct >= REGIME_POSITIVE_THRESHOLD):
        return "positive"
    if (spy_change_5d_pct is not None and qqq_change_5d_pct is not None
            and spy_change_5d_pct <= REGIME_5D_NEG
            and qqq_change_5d_pct <= REGIME_5D_NEG):
        return "negative_5d"
    return "neutral"


def _regime_signal(regime: Regime) -> int:
    """Map regime label to a numeric composite contribution."""
    if regime == "negative" or regime == "negative_5d":
        return -1
    if regime == "positive":
        return +1
    # neutral / unknown → 0 (fail-safe; do not bias)
    return 0


# ---------------------------------------------------------------------------
# §3 — Eligibility filter
# ---------------------------------------------------------------------------


def is_eligible(
    inp: PerTickerInput,
    has_t_minus_1_close: bool,
) -> tuple[bool, str | None]:
    """Decide whether a ticker enters the prediction set."""
    if inp.mapping_status != "mapped":
        return False, f"mapping_status={inp.mapping_status} (not mapped)"
    if not has_t_minus_1_close:
        return False, "no T-1 close in price_bar_raw"
    if inp.change_1d_pct is None:
        return False, "change_1d_pct missing"
    return True, None


# ---------------------------------------------------------------------------
# §6 — Per-ticker factor signals (pure)
# ---------------------------------------------------------------------------


def _momentum(inp: PerTickerInput) -> int:
    d1d = inp.change_1d_pct
    if d1d is None:
        return 0
    if d1d >= MOMENTUM_UP_PCT:
        return +1
    if d1d <= MOMENTUM_DOWN_PCT:
        return -1
    return 0


def _extension(inp: PerTickerInput) -> int:
    """v2: BOTH-SIDES dampener.

    -1 = extended after big up move (mean-reversion bias)
    +1 = capitulation after big down move (bounce bias)
     0 = neither
    """
    w52 = inp.week52_position_pct
    d1d = inp.change_1d_pct
    if w52 is None or d1d is None:
        return 0
    if w52 >= EXTENSION_HIGH_W52 and d1d >= EXTENSION_HIGH_D1:
        return -1
    if w52 <= EXTENSION_LOW_W52 and d1d <= EXTENSION_LOW_D1:
        return +1
    return 0


def _news(inp: PerTickerInput) -> int:
    n = inp.recent_news_count
    volr = inp.volume_ratio or 0.0
    pri = inp.research_priority
    if (n >= NEWS_STRONG_COUNT and pri >= NEWS_STRONG_PRIORITY
            and volr >= NEWS_STRONG_VOLR):
        return +1
    if n >= NEWS_MEDIUM_COUNT and volr >= NEWS_MEDIUM_VOLR:
        return +1
    if n == 0:
        return 0
    return 0


# ---------------------------------------------------------------------------
# §7 — Direction + §8 bucket + §9 confidence
# ---------------------------------------------------------------------------


def _direction(
    composite: int,
    extension: int,
    regime: Regime,
) -> DirectionLabel:
    """Map composite + extension + regime to a 4-state direction."""
    if extension == -1 and regime in ("negative", "negative_5d"):
        return "down"               # downside override
    if extension == -1:
        return "flat-down"          # dampener fired, regime not opposing
    if composite >= +2:
        return "up"
    if composite == +1:
        return "flat-up"
    if composite == 0:
        if regime in ("negative", "negative_5d"):
            return "flat-down"
        return "flat-up"
    if composite == -1:
        return "flat-down"
    # composite <= -2
    return "down"


def _bucket(
    direction: DirectionLabel,
    composite: int,
    regime: Regime,
) -> BucketLabel:
    if direction == "up" and composite >= +3 and regime == "positive":
        return "above_plus_3"
    if direction == "up":
        return "plus_1_to_plus_3"
    if direction == "flat-up":
        return "minus_1_to_plus_1"
    if direction == "flat-down":
        return "minus_1_to_plus_1"
    if (direction == "down" and composite <= -3
            and regime in ("negative", "negative_5d")):
        return "below_minus_3"
    # direction == "down" otherwise
    return "minus_3_to_minus_1"


def _regime_aligns(direction: DirectionLabel, regime: Regime) -> bool:
    if regime == "unknown":
        return False
    if direction in ("up", "flat-up"):
        return regime in ("positive", "neutral")
    # direction in ("down", "flat-down")
    return regime in ("negative", "negative_5d", "neutral")


def _confidence(
    data_quality: str,
    composite: int,
    direction: DirectionLabel,
    signal_strength: str | None,
    risk_flags: Iterable[str],
    regime: Regime,
) -> ConfidenceLabel:
    if data_quality != "complete":
        return "low"
    if (abs(composite) >= 3
            and signal_strength == "high"
            and not tuple(risk_flags)
            and _regime_aligns(direction, regime)):
        return "high"
    if abs(composite) >= 2:
        return "medium"
    return "low"


def _rationale_factors(
    inp: PerTickerInput,
    momentum: int,
    extension: int,
    news_signal: int,
    regime_signal: int,
) -> list[str]:
    out: list[str] = []
    if momentum != 0:
        out.append(f"momentum={momentum:+d}")
    if extension != 0:
        out.append(f"extension={extension:+d}")
    if news_signal != 0:
        out.append(f"news={news_signal:+d}")
    if regime_signal != 0:
        out.append(f"regime={regime_signal:+d}")
    if inp.recent_news_count > 0:
        out.append("has_news")
    if inp.upcoming_earnings_count > 0:
        out.append("earnings_nearby")
    if "HELD" in inp.source_tags:
        out.append("mirror_held")
    if "WATCHED" in inp.source_tags:
        out.append("mirror_watched")
    if "RECENTLY_TRADED" in inp.source_tags:
        out.append("mirror_recently_traded")
    if inp.data_quality != "complete":
        out.append(f"data_quality={inp.data_quality}")
    return out


def compute_per_ticker(
    inp: PerTickerInput,
    *,
    regime: Regime,
    has_t_minus_1_close: bool,
) -> PredictionRow:
    """Single deterministic entry point. Pure function."""
    eligible, reason = is_eligible(inp, has_t_minus_1_close)
    if not eligible:
        return PredictionRow(
            ticker=inp.ticker,
            eligible=False,
            not_eligible_reason=reason,
            data_quality=inp.data_quality,
        )

    m = _momentum(inp)
    e = _extension(inp)
    n = _news(inp)
    r = _regime_signal(regime)
    composite = m + e + n + r

    direction = _direction(composite, e, regime)
    bucket = _bucket(direction, composite, regime)
    confidence = _confidence(
        data_quality=inp.data_quality,
        composite=composite,
        direction=direction,
        signal_strength=inp.signal_strength,
        risk_flags=inp.risk_flags,
        regime=regime,
    )

    return PredictionRow(
        ticker=inp.ticker,
        eligible=True,
        momentum_signal=m,
        extension_signal=e,
        news_signal=n,
        regime_signal=r,
        composite=composite,
        predicted_direction=direction,
        predicted_return_bucket=bucket,
        confidence=confidence,
        data_quality=inp.data_quality,
        rationale_factors=_rationale_factors(inp, m, e, n, r),
    )


# ---------------------------------------------------------------------------
# Eval-side helpers — bucket midpoints, actual direction band,
# direction-correct collapse rule.
# ---------------------------------------------------------------------------


_BUCKET_MIDPOINT_PCT: dict[BucketLabel, float] = {
    "above_plus_3": +4.0,
    "plus_1_to_plus_3": +2.0,
    "minus_1_to_plus_1": 0.0,
    "minus_3_to_minus_1": -2.0,
    "below_minus_3": -4.0,
}


def bucket_midpoint_pct(bucket: BucketLabel) -> float:
    return _BUCKET_MIDPOINT_PCT[bucket]


# Actual-direction band labels (for eval). The labels are intentionally
# distinct from the predicted labels — eval has 5 bands, prediction has 4.
ActualDirectionBand = Literal[
    "up", "flat-up", "flat-flat", "flat-down", "down",
]


def actual_direction_band(actual_return_pct: float) -> ActualDirectionBand:
    """Classify a single ticker's actual same-day return into one of
    five informational bands. Used at eval time only."""
    if actual_return_pct > ACTUAL_DIRECTION_EPSILON_PCT:
        return "up"
    if actual_return_pct >= ACTUAL_FLAT_BAND_PCT:
        return "flat-up"
    if actual_return_pct > -ACTUAL_FLAT_BAND_PCT:
        return "flat-flat"
    if actual_return_pct >= -ACTUAL_DIRECTION_EPSILON_PCT:
        return "flat-down"
    return "down"


# Collapse table — predicted direction X actual direction band ⇒ correct?
_DIRECTION_HIT_TABLE: dict[DirectionLabel, set[ActualDirectionBand]] = {
    "up": {"up"},
    "flat-up": {"up", "flat-up", "flat-flat"},
    "flat-down": {"down", "flat-down", "flat-flat"},
    "down": {"down"},
}


def direction_correct(
    predicted: DirectionLabel,
    actual: ActualDirectionBand,
) -> bool:
    return actual in _DIRECTION_HIT_TABLE[predicted]
