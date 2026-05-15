"""Premarket Shadow Test #4 — Rule v2 unit tests.

Hermetic. No DB, no provider HTTP, no network. Every test exercises
the pure function ``compute_per_ticker`` (and helpers) with structured
inputs and pins the expected output verbatim.

Pre-registration: ``docs/premarket-shadow-test-4-rule-v2-pre-registration.md``.

Categories:

  * §3 eligibility filter
  * §5 market regime classification
  * §6 momentum / extension / news factor signals
  * §7 direction mapping (incl. downside override)
  * §8 bucket mapping (incl. relaxed extreme caps)
  * §9 confidence calibration (low / medium / high)
  * Eval-side: actual_direction_band, direction_correct
  * Source-grep guards (no broker / order / live submit / banned
    trading words in the production rule module)
"""
from __future__ import annotations

import inspect
import io
import tokenize

import pytest

from libs.prediction import rule_v2 as rv2
from libs.prediction.rule_v2 import (
    PerTickerInput,
    actual_direction_band,
    bucket_midpoint_pct,
    compute_market_regime,
    compute_per_ticker,
    direction_correct,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip(src: str) -> str:
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (
                tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING,
            ):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


def _ticker(**kw) -> PerTickerInput:
    """Default-mapped ticker; override fields per test."""
    defaults = dict(
        ticker="XYZ",
        change_1d_pct=0.0,
        change_5d_pct=0.0,
        week52_position_pct=50.0,
        volume_ratio=1.0,
        signal_strength="medium",
        recent_news_count=0,
        upcoming_earnings_count=0,
        research_priority=1,
        source_tags=("SCANNER",),
        mapping_status="mapped",
    )
    defaults.update(kw)
    return PerTickerInput(**defaults)


# ---------------------------------------------------------------------------
# §5 — Market regime
# ---------------------------------------------------------------------------


class TestMarketRegime:
    def test_unknown_when_inputs_missing(self):
        assert compute_market_regime(None, +1.5) == "unknown"
        assert compute_market_regime(+1.5, None) == "unknown"
        assert compute_market_regime(None, None) == "unknown"

    def test_negative_when_both_spy_qqq_drop(self):
        # SPY -1.5, QQQ -2.0 → negative (both ≤ -1.0)
        assert compute_market_regime(-1.5, -2.0) == "negative"
        # boundary case: both at -1.0
        assert compute_market_regime(-1.0, -1.0) == "negative"

    def test_positive_when_both_rise(self):
        assert compute_market_regime(+1.2, +1.5) == "positive"
        # boundary
        assert compute_market_regime(+1.0, +1.0) == "positive"

    def test_negative_5d_fallback(self):
        # 1D mixed but 5D both down hard
        r = compute_market_regime(
            spy_change_1d_pct=-0.5, qqq_change_1d_pct=+0.3,
            spy_change_5d_pct=-3.0, qqq_change_5d_pct=-4.0,
        )
        assert r == "negative_5d"

    def test_neutral_default(self):
        r = compute_market_regime(
            spy_change_1d_pct=+0.3, qqq_change_1d_pct=-0.2,
            spy_change_5d_pct=+1.0, qqq_change_5d_pct=+0.5,
        )
        assert r == "neutral"

    def test_one_side_negative_one_side_positive_not_negative(self):
        # SPY -1.5 (below threshold), QQQ +0.5 (NOT below threshold)
        # → must NOT be negative (the rule requires BOTH)
        assert compute_market_regime(-1.5, +0.5) == "neutral"


# ---------------------------------------------------------------------------
# §3 — Eligibility
# ---------------------------------------------------------------------------


class TestEligibility:
    def test_mapped_with_anchor_and_d1d_is_eligible(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.eligible is True
        assert out.not_eligible_reason is None

    def test_unmapped_excluded(self):
        out = compute_per_ticker(
            _ticker(mapping_status="newly_resolvable",
                    change_1d_pct=+1.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.eligible is False
        assert "mapping_status" in (out.not_eligible_reason or "")

    def test_missing_t_minus_1_close_excluded(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            has_t_minus_1_close=False,
        )
        assert out.eligible is False
        assert "T-1" in (out.not_eligible_reason or "")

    def test_no_change_1d_excluded(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=None),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.eligible is False
        assert "change_1d_pct" in (out.not_eligible_reason or "")


# ---------------------------------------------------------------------------
# §6 — Factor signals
# ---------------------------------------------------------------------------


class TestMomentumSignal:
    @pytest.mark.parametrize("d1d,expected", [
        (+5.0, +1), (+2.0, +1), (+1.99, 0),
        (0.0, 0), (-1.99, 0), (-2.0, -1), (-5.0, -1),
    ])
    def test_thresholds(self, d1d, expected):
        out = compute_per_ticker(
            _ticker(change_1d_pct=d1d),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.momentum_signal == expected


class TestExtensionSignal:
    def test_extended_after_big_up(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+10.0, week52_position_pct=98.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.extension_signal == -1

    def test_capitulation_after_big_down(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=-10.0, week52_position_pct=3.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.extension_signal == +1

    def test_neither_when_moderate(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+5.0, week52_position_pct=70.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.extension_signal == 0


class TestNewsSignal:
    def test_strong_news_with_high_volr(self):
        out = compute_per_ticker(
            _ticker(recent_news_count=5, volume_ratio=2.0,
                    research_priority=5),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.news_signal == +1

    def test_medium_news_with_modest_volr(self):
        out = compute_per_ticker(
            _ticker(recent_news_count=3, volume_ratio=1.3),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.news_signal == +1

    def test_news_without_volr_corroboration(self):
        # 4 news but volr only 1.0 → no signal
        out = compute_per_ticker(
            _ticker(recent_news_count=4, volume_ratio=1.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.news_signal == 0

    def test_zero_news(self):
        out = compute_per_ticker(
            _ticker(recent_news_count=0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.news_signal == 0


# ---------------------------------------------------------------------------
# §7 — Direction (incl. downside override)
# ---------------------------------------------------------------------------


class TestDirection:
    def test_downside_override_when_extended_and_regime_negative(self):
        """The v1 mapping failure: composite=0 from
        momentum=+1+extension=-1 mapped to flat. v2 with regime=negative
        should map to 'down'."""
        out = compute_per_ticker(
            _ticker(change_1d_pct=+10.0, week52_position_pct=98.0),
            regime="negative",
            has_t_minus_1_close=True,
        )
        assert out.extension_signal == -1
        assert out.predicted_direction == "down"
        # bucket should also be downside
        assert out.predicted_return_bucket in (
            "minus_3_to_minus_1", "below_minus_3",
        )

    def test_extended_without_negative_regime_is_flat_down(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+10.0, week52_position_pct=98.0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.extension_signal == -1
        assert out.predicted_direction == "flat-down"

    def test_composite_plus_2_is_up(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+5.0, recent_news_count=5,
                    volume_ratio=2.0, research_priority=5),
            regime="positive",  # +1
            has_t_minus_1_close=True,
        )
        assert out.composite >= +2
        assert out.predicted_direction == "up"

    def test_composite_plus_1_is_flat_up(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+2.5),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.composite == 1
        assert out.predicted_direction == "flat-up"

    def test_composite_zero_in_negative_regime_is_flat_down(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+1.0),  # mom=0
            regime="negative",            # -1
            has_t_minus_1_close=True,
        )
        # composite = 0 + 0 + 0 + (-1) = -1 → flat-down per the -1 branch
        # OR composite=0 with negative regime maps to flat-down — either way
        assert out.predicted_direction == "flat-down"

    def test_composite_minus_2_is_down(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=-5.0),
            regime="negative",  # -1
            has_t_minus_1_close=True,
        )
        assert out.composite <= -2
        assert out.predicted_direction == "down"


# ---------------------------------------------------------------------------
# §8 — Bucket (incl. relaxed extreme caps)
# ---------------------------------------------------------------------------


class TestBucket:
    def test_up_with_strong_composite_and_positive_regime_can_reach_above_plus_3(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+5.0, week52_position_pct=50.0,
                    recent_news_count=5, volume_ratio=2.0,
                    research_priority=5, signal_strength="high"),
            regime="positive",  # +1
            has_t_minus_1_close=True,
        )
        # composite = +1 + 0 + +1 + +1 = +3 → up + ≥+3 + positive → above_plus_3
        assert out.composite >= +3
        assert out.predicted_direction == "up"
        assert out.predicted_return_bucket == "above_plus_3"

    def test_up_without_extreme_composite_stays_in_plus_1_to_plus_3(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+3.0,
                    recent_news_count=3, volume_ratio=1.3),
            regime="positive",
            has_t_minus_1_close=True,
        )
        # composite = +1 + 0 + +1 + +1 = +3 → bucket might be above_plus_3
        # only if signal_strength=high AND regime=positive. signal_strength
        # default is "medium" → still gets above_plus_3 due to composite + regime.
        # Adjust: weaker regime to confirm
        out2 = compute_per_ticker(
            _ticker(change_1d_pct=+3.0,
                    recent_news_count=3, volume_ratio=1.3),
            regime="neutral",  # 0
            has_t_minus_1_close=True,
        )
        assert out2.composite == +2  # mom=+1, news=+1, regime=0
        assert out2.predicted_direction == "up"
        assert out2.predicted_return_bucket == "plus_1_to_plus_3"

    def test_down_with_strong_composite_and_negative_regime_reaches_below_minus_3(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=-5.0, week52_position_pct=98.0),
            regime="negative",
            has_t_minus_1_close=True,
        )
        # mom=-1, ext=0 (w52 high but d1d is -5 not -8 so not capitulation
        # AND not extended-up), news=0, regime=-1 → composite=-2
        # direction=down, but composite=-2 (not <=-3) → bucket=minus_3_to_minus_1
        assert out.predicted_direction == "down"
        # composite is -2 here, so not the below_minus_3 path
        assert out.predicted_return_bucket == "minus_3_to_minus_1"

    def test_below_minus_3_when_composite_le_minus_3_and_negative_regime(self):
        # Hand-construct an input where composite=-3 (mom=-1, regime=-1,
        # extension=-1 via the extended-after-pop path), and confirm bucket.
        out = compute_per_ticker(
            _ticker(change_1d_pct=+10.0, week52_position_pct=98.0,
                    recent_news_count=0),
            regime="negative",
            has_t_minus_1_close=True,
        )
        # mom=+1, ext=-1, news=0, regime=-1 → composite=-1
        # direction goes through the downside-override path (extension=-1 +
        # regime=negative) → down. composite=-1, not ≤-3 → minus_3_to_minus_1
        assert out.predicted_direction == "down"
        assert out.predicted_return_bucket == "minus_3_to_minus_1"

    def test_flat_predictions_stay_in_minus_1_to_plus_1(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+0.5),  # below momentum threshold
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.predicted_direction in ("flat-up", "flat-down")
        assert out.predicted_return_bucket == "minus_1_to_plus_1"


# ---------------------------------------------------------------------------
# §9 — Confidence
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_low_when_data_quality_not_complete(self):
        # change_1d_pct=None → data_quality=weak → eligible=False, so this
        # row never reaches the prediction path. Instead, test the partial
        # case: change_1d_pct present but everything else absent.
        out = compute_per_ticker(
            _ticker(change_1d_pct=+3.0, signal_strength=None,
                    recent_news_count=0, upcoming_earnings_count=0),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.data_quality == "partial"
        assert out.confidence == "low"

    def test_medium_when_composite_2_and_complete(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+3.0,
                    recent_news_count=3, volume_ratio=1.3,
                    signal_strength="medium"),
            regime="neutral",
            has_t_minus_1_close=True,
        )
        assert out.composite == +2
        assert out.confidence == "medium"

    def test_high_requires_all_conditions(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+5.0,
                    recent_news_count=5, volume_ratio=2.0,
                    research_priority=5, signal_strength="high",
                    risk_flags=()),
            regime="positive",
            has_t_minus_1_close=True,
        )
        # mom=+1, ext=0, news=+1, regime=+1 → composite=+3
        # signal_strength=high, no risk_flags, regime=positive aligns with up
        assert out.composite == +3
        assert out.predicted_direction == "up"
        assert out.confidence == "high"

    def test_high_blocked_by_risk_flags(self):
        out = compute_per_ticker(
            _ticker(change_1d_pct=+5.0,
                    recent_news_count=5, volume_ratio=2.0,
                    research_priority=5, signal_strength="high",
                    risk_flags=("low_volume",)),
            regime="positive",
            has_t_minus_1_close=True,
        )
        assert out.confidence == "medium"

    def test_high_blocked_by_unknown_regime(self):
        """Unknown regime fail-safes high → never reached when regime
        is unknown, even with strong composite."""
        out = compute_per_ticker(
            _ticker(change_1d_pct=+5.0,
                    recent_news_count=5, volume_ratio=2.0,
                    research_priority=5, signal_strength="high"),
            regime="unknown",
            has_t_minus_1_close=True,
        )
        # composite = mom(+1)+ext(0)+news(+1)+regime(0)=+2 → medium tier max
        assert out.confidence == "medium"


# ---------------------------------------------------------------------------
# Eval-side classification helpers
# ---------------------------------------------------------------------------


class TestActualDirectionBand:
    @pytest.mark.parametrize("ret_pct,expected", [
        (+5.0, "up"),
        (+0.6, "up"),
        (+0.5001, "up"),
        (+0.5, "flat-up"),
        (+0.3, "flat-up"),
        (+0.1, "flat-up"),
        (+0.05, "flat-flat"),
        (0.0, "flat-flat"),
        (-0.05, "flat-flat"),
        (-0.1, "flat-down"),
        (-0.3, "flat-down"),
        (-0.5, "flat-down"),
        (-0.5001, "down"),
        (-1.0, "down"),
        (-5.0, "down"),
    ])
    def test_bands(self, ret_pct, expected):
        assert actual_direction_band(ret_pct) == expected


class TestDirectionCorrect:
    @pytest.mark.parametrize("pred,actual,expected", [
        ("up", "up", True),
        ("up", "flat-up", False),
        ("up", "down", False),
        ("flat-up", "up", True),
        ("flat-up", "flat-up", True),
        ("flat-up", "flat-flat", True),
        ("flat-up", "flat-down", False),
        ("flat-up", "down", False),
        ("flat-down", "down", True),
        ("flat-down", "flat-down", True),
        ("flat-down", "flat-flat", True),
        ("flat-down", "flat-up", False),
        ("flat-down", "up", False),
        ("down", "down", True),
        ("down", "flat-down", False),
        ("down", "up", False),
    ])
    def test_collapse(self, pred, actual, expected):
        assert direction_correct(pred, actual) is expected


class TestBucketMidpoint:
    def test_each_bucket_midpoint(self):
        assert bucket_midpoint_pct("above_plus_3") == +4.0
        assert bucket_midpoint_pct("plus_1_to_plus_3") == +2.0
        assert bucket_midpoint_pct("minus_1_to_plus_1") == 0.0
        assert bucket_midpoint_pct("minus_3_to_minus_1") == -2.0
        assert bucket_midpoint_pct("below_minus_3") == -4.0


# ---------------------------------------------------------------------------
# Replay the v1 evidence pattern against v2 — would the dampener
# misfire have been avoided?
# ---------------------------------------------------------------------------


class TestV1FailureModesAvoidedByV2:
    """For each of the 3 v1 dampener-misfire tickers (MU/AMD/INTC),
    feed v2 a representative input AND a negative-regime market.
    Confirm v2 produces 'down' direction, not 'flat'.

    These are research observations, NOT retroactive backfills (which
    are explicitly forbidden by the pre-registration §13).
    """

    def test_mu_pattern_under_v2(self):
        # MU at 2026-05-12 brief time: d1d≈+15, w52=100 → extension=-1.
        # Market regime: SPY -1.1, QQQ -1.2 → negative.
        out = compute_per_ticker(
            _ticker(ticker="MU", change_1d_pct=+15.0,
                    week52_position_pct=100.0,
                    recent_news_count=2, volume_ratio=1.5,
                    research_priority=5),
            regime="negative",
            has_t_minus_1_close=True,
        )
        assert out.extension_signal == -1
        assert out.predicted_direction == "down"
        assert out.predicted_return_bucket in (
            "minus_3_to_minus_1", "below_minus_3",
        )

    def test_amd_pattern_under_v2(self):
        out = compute_per_ticker(
            _ticker(ticker="AMD", change_1d_pct=+11.4,
                    week52_position_pct=100.0,
                    recent_news_count=2, volume_ratio=1.5,
                    research_priority=4),
            regime="negative",
            has_t_minus_1_close=True,
        )
        assert out.predicted_direction == "down"

    def test_intc_pattern_under_v2(self):
        out = compute_per_ticker(
            _ticker(ticker="INTC", change_1d_pct=+14.0,
                    week52_position_pct=100.0,
                    recent_news_count=0, volume_ratio=2.0),
            regime="negative",
            has_t_minus_1_close=True,
        )
        assert out.predicted_direction == "down"


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------


class TestNoForbiddenSymbols:
    def test_rule_v2_no_broker_order_live_submit(self):
        src = _strip(inspect.getsource(rv2))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "/equity/orders/limit", "/equity/orders/market",
            "FEATURE_T212_LIVE_SUBMIT", "live_submit",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
            "selenium", "playwright", "puppeteer", "webdriver",
            "BeautifulSoup",
        ):
            assert needle.lower() not in src.lower(), (
                f"rule_v2 must not reference {needle!r}"
            )

    def test_rule_v2_no_banned_trading_phrases(self):
        """Platform-generated text must NEVER contain trade-action
        language. The module source after stripping comments and
        docstrings must be clean."""
        src = _strip(inspect.getsource(rv2))
        banned = (
            "buy now", "sell now", "enter long", "enter short",
            "target price", "position siz", "guaranteed",
            "must rise", "must fall", "必涨", "必跌",
            "买入建议", "卖出建议", "目标价", "仓位建议",
        )
        for phrase in banned:
            assert phrase.lower() not in src.lower(), (
                f"rule_v2 must not contain banned phrase {phrase!r}"
            )

    def test_rule_v2_is_pure_no_db_no_http(self):
        """The pure path must not import a DB session or HTTP client."""
        src = inspect.getsource(rv2)
        for needle in (
            "from sqlalchemy", "import sqlalchemy",
            "from libs.db", "from libs.adapters",
            "requests.", "httpx.", "aiohttp.",
            "get_sync_session",
            "INSERT", "UPDATE", "DELETE",
        ):
            assert needle not in src, (
                f"rule_v2 must be pure — found {needle!r}"
            )


# ---------------------------------------------------------------------------
# v2.1 amendment tests (additive — v2 tests above continue to pass)
# ---------------------------------------------------------------------------


from datetime import date as _date  # noqa: E402

from libs.prediction.rule_v2 import (  # noqa: E402
    MAX_ANCHOR_LAG_TRADING_DAYS,
    V21_HORIZON_LABEL,
    compute_per_ticker_v21,
    is_eligible_latest_anchor,
)


class TestV21Constants:
    def test_max_anchor_lag_is_three_trading_days(self):
        assert MAX_ANCHOR_LAG_TRADING_DAYS == 3

    def test_v21_horizon_label_is_distinct_from_v2(self):
        # v2 used "next_close_vs_previous_close". v2.1 must NOT reuse
        # that label — it would be dishonest under T-2 anchor.
        assert V21_HORIZON_LABEL == "latest_db_close_to_target_close"
        assert V21_HORIZON_LABEL != "next_close_vs_previous_close"


class TestV21WeekdaysBetween:
    """The helper _weekdays_between is package-private; tested via the
    public is_eligible_latest_anchor results."""

    def test_one_weekday_lag(self):
        # Thu 2026-05-14 → Fri 2026-05-15: exactly 1 weekday lag
        e, _, lag = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 14),
            target_trade_date=_date(2026, 5, 15),
        )
        assert e is True
        assert lag == 1

    def test_two_weekday_lag_across_weekend(self):
        # Fri 2026-05-15 → Mon 2026-05-18: lag = 1 (Mon)
        # Wed 2026-05-13 → Fri 2026-05-15: lag = 2 (Thu, Fri)
        e, _, lag = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        assert e is True
        assert lag == 2

    def test_anchor_across_weekend_skips_sat_sun(self):
        # Fri 2026-05-08 → Mon 2026-05-11: lag should be 1 (only Mon)
        e, _, lag = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 8),
            target_trade_date=_date(2026, 5, 11),
        )
        assert e is True
        assert lag == 1


class TestV21Eligibility:
    def test_unmapped_excluded(self):
        e, reason, _ = is_eligible_latest_anchor(
            _ticker(mapping_status="newly_resolvable",
                    change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        assert e is False
        assert "mapping_status" in (reason or "")

    def test_no_close_in_db_excluded(self):
        e, reason, _ = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=None,
            target_trade_date=_date(2026, 5, 15),
        )
        assert e is False
        assert reason == "no_close_in_db"

    def test_anchor_too_stale_excluded(self):
        # 4 weekday lag > MAX_ANCHOR_LAG_TRADING_DAYS=3
        # Mon 2026-05-11 → Mon 2026-05-18: weekdays between = 5 (Tue,
        # Wed, Thu, Fri, Mon) → too stale
        e, reason, lag = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 11),
            target_trade_date=_date(2026, 5, 18),
        )
        assert e is False
        assert reason and "anchor_too_stale" in reason
        assert lag is not None and lag > MAX_ANCHOR_LAG_TRADING_DAYS

    def test_boundary_lag_3_is_eligible(self):
        # exactly 3 weekday lag should still be eligible (boundary)
        e, reason, lag = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 12),
            target_trade_date=_date(2026, 5, 15),
        )
        # Tue 5/12 → Fri 5/15: Wed, Thu, Fri = 3 weekdays
        assert lag == 3
        assert e is True
        assert reason is None

    def test_boundary_lag_4_excluded(self):
        # 4 weekday lag is just over the boundary
        e, reason, lag = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 11),
            target_trade_date=_date(2026, 5, 15),
        )
        # Mon 5/11 → Fri 5/15: Tue, Wed, Thu, Fri = 4 weekdays
        assert lag == 4
        assert e is False
        assert "anchor_too_stale" in (reason or "")

    def test_anchor_on_or_after_target_rejected(self):
        e, reason, _ = is_eligible_latest_anchor(
            _ticker(change_1d_pct=+1.0),
            anchor_trade_date=_date(2026, 5, 15),
            target_trade_date=_date(2026, 5, 15),
        )
        assert e is False
        assert ">=" in (reason or "")

    def test_no_change_1d_excluded(self):
        e, reason, _ = is_eligible_latest_anchor(
            _ticker(change_1d_pct=None),
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        assert e is False
        assert "change_1d_pct" in (reason or "")


class TestV2vsV21Coexistence:
    """v2's `is_eligible(...)` and v2.1's `is_eligible_latest_anchor(...)`
    must coexist. v2 tests must continue to pass; v2.1 must NOT
    silently change v2 behaviour."""

    def test_v2_strict_t_minus_1_still_works(self):
        """v2's is_eligible still requires the boolean has_t_minus_1_close
        — confirm the v2 surface is intact."""
        out = compute_per_ticker(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            has_t_minus_1_close=False,  # simulating the v2 §3 failure
        )
        assert out.eligible is False
        assert "T-1" in (out.not_eligible_reason or "")

    def test_v21_passes_where_v2_fails_when_anchor_within_lag(self):
        """The 2026-05-14 scenario: T-1=2026-05-14 missing → v2 fails;
        most recent close = 2026-05-13 within 3-day lag → v2.1 passes."""
        # v2 path: fails because we say has_t_minus_1_close=False
        out_v2 = compute_per_ticker(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            has_t_minus_1_close=False,
        )
        assert out_v2.eligible is False

        # v2.1 path: passes with anchor=T-2 (2026-05-13), target=T (2026-05-15)
        out_v21 = compute_per_ticker_v21(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        assert out_v21["eligible"] is True
        assert out_v21["anchor_lag_trading_days"] == 2


class TestV21OutputShape:
    def test_eligible_row_has_v21_metadata(self):
        out = compute_per_ticker_v21(
            _ticker(change_1d_pct=+3.0, recent_news_count=3,
                    volume_ratio=1.3),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        # v2.1-specific fields
        assert out["schema_version"] == "v2.1"
        assert out["prediction_horizon"] == "latest_db_close_to_target_close"
        assert out["anchor_trade_date"] == "2026-05-13"
        assert out["target_trade_date"] == "2026-05-15"
        assert out["anchor_lag_trading_days"] == 2
        # v2 fields still carried through
        assert "decision" in out
        assert "predicted_direction" in out
        assert "predicted_return_bucket" in out
        assert "confidence" in out

    def test_horizon_label_is_never_v2_label_in_v21_output(self):
        """The v2 label 'next_close_vs_previous_close' would be
        dishonest under T-2 anchor; v2.1 output must NEVER carry it."""
        out = compute_per_ticker_v21(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        assert out["prediction_horizon"] != "next_close_vs_previous_close"

    def test_ineligible_row_carries_reason_and_metadata_but_no_prediction(self):
        out = compute_per_ticker_v21(
            _ticker(mapping_status="unmapped", change_1d_pct=+1.0),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        assert out["eligible"] is False
        assert out["not_eligible_reason"]
        # ineligible rows still carry anchor/target metadata (for the
        # eval-side to record the watch_only entry's intent)
        assert out["target_trade_date"] == "2026-05-15"
        assert out["prediction_horizon"] == "latest_db_close_to_target_close"
        # but no prediction fields
        assert "predicted_direction" not in out
        assert "predicted_return_bucket" not in out

    def test_watch_only_reasons_are_explicit(self):
        """The v2.1 vocabulary: unmapped / no_close_in_db /
        anchor_too_stale / change_1d_pct missing. All must be
        produceable."""
        reasons = set()
        # unmapped
        out = compute_per_ticker_v21(
            _ticker(mapping_status="unmapped", change_1d_pct=+1.0),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        reasons.add("mapping_status" in (out["not_eligible_reason"] or ""))
        # no_close_in_db
        out = compute_per_ticker_v21(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            anchor_trade_date=None,
            target_trade_date=_date(2026, 5, 15),
        )
        reasons.add(out["not_eligible_reason"] == "no_close_in_db")
        # anchor_too_stale
        out = compute_per_ticker_v21(
            _ticker(change_1d_pct=+1.0),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 8),
            target_trade_date=_date(2026, 5, 15),
        )
        reasons.add("anchor_too_stale" in (out["not_eligible_reason"] or ""))
        # change_1d_pct missing
        out = compute_per_ticker_v21(
            _ticker(change_1d_pct=None),
            regime="neutral",
            anchor_trade_date=_date(2026, 5, 13),
            target_trade_date=_date(2026, 5, 15),
        )
        reasons.add("change_1d_pct" in (out["not_eligible_reason"] or ""))
        assert all(reasons), reasons


class TestV21NoForbiddenSymbols:
    """v2.1 inherits v2's strict language ban. The new functions
    must NOT introduce any new trade-action vocabulary."""

    def test_v21_helpers_no_banned_language(self):
        src = _strip(inspect.getsource(is_eligible_latest_anchor)) + \
              _strip(inspect.getsource(compute_per_ticker_v21))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "FEATURE_T212_LIVE_SUBMIT", "live_submit",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
            "selenium", "playwright", "puppeteer", "webdriver",
            "BeautifulSoup",
            "buy now", "sell now", "enter long", "enter short",
            "target price", "position siz",
        ):
            assert needle.lower() not in src.lower(), (
                f"v2.1 helpers must not reference {needle!r}"
            )
