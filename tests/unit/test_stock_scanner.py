"""Unit tests for the Stock Scanner service.

Three test families:
1. Rule classification — scan_types match expected behaviour
2. Signal strength — boundary conditions
3. GUARDRAIL — banned words, whitelisted recommended_next_step, no
   buy/sell/target/position fields, schema strictness
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from apps.api.routers.scanner import ScanItem, ScanResponse
from libs.scanner.stock_scanner_service import (
    BANNED_WORDS,
    RECOMMENDED_NEXT_STEPS,
    SCAN_TYPES,
    _eval_rules,
    _explanation,
    _recommended_next_step,
    _signal_strength,
)


NOW = datetime(2026, 4, 16, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Rule classification
# ---------------------------------------------------------------------------

class TestStrongMomentum:
    def test_1d_above_5_triggers(self):
        snap = {"change_1d_pct": 6.0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "strong_momentum" in scan_types

    def test_5d_above_10_triggers(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 11.0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "strong_momentum" in scan_types

    def test_1m_above_20_triggers(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 21.0, "week52_pct": 50}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "strong_momentum" in scan_types

    def test_below_thresholds_does_not_trigger(self):
        snap = {"change_1d_pct": 4.9, "change_5d_pct": 9.9, "change_1m_pct": 19.9, "week52_pct": 50}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "strong_momentum" not in scan_types


class TestExtremeMover:
    def test_1d_abs_above_10(self):
        snap = {"change_1d_pct": -11.0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "extreme_mover" in scan_types
        assert "high_volatility" in scan_types  # both should trigger

    def test_just_below_does_not_trigger(self):
        snap = {"change_1d_pct": 9.9, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "extreme_mover" not in scan_types


class TestBreakoutCandidate:
    def test_w52_85_triggers(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 85}
        scan_types, _, _ = _eval_rules(snap, {}, None, NOW)
        assert "breakout_candidate" in scan_types

    def test_w52_90_adds_near_high_risk(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 92}
        _, risk_flags, _ = _eval_rules(snap, {}, None, NOW)
        assert "near_52w_high" in risk_flags


class TestNeedsResearch:
    def test_no_note_triggers(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, risk_flags, days = _eval_rules(snap, {}, None, NOW)
        assert "needs_research" in scan_types
        assert "no_recent_research" in risk_flags
        assert days is None

    def test_recent_note_does_not_trigger(self):
        recent = (NOW.replace(hour=0)).isoformat()
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, _, days = _eval_rules(snap, {"last_note_at": recent}, None, NOW)
        assert "needs_research" not in scan_types
        assert days is not None and days < 14

    def test_14_days_old_triggers(self):
        old = NOW.replace(year=NOW.year, month=NOW.month, day=1)
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        scan_types, _, days = _eval_rules(snap, {"last_note_at": old.isoformat()}, None, NOW)
        if days is not None and days >= 14:
            assert "needs_research" in scan_types


class TestInsufficientData:
    def test_missing_field_marks_insufficient(self):
        snap = {"change_1d_pct": None, "change_5d_pct": 5, "change_1m_pct": 10, "week52_pct": 60}
        _, risk_flags, _ = _eval_rules(snap, {}, None, NOW)
        assert "insufficient_data" in risk_flags


class TestVolumeFlags:
    def test_volume_3x_triggers_high_relative_volume(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        _, risk_flags, _ = _eval_rules(snap, {}, 3.5, NOW)
        assert "high_relative_volume" in risk_flags

    def test_volume_2x_does_not_set_risk_flag(self):
        snap = {"change_1d_pct": 0, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": 50}
        _, risk_flags, _ = _eval_rules(snap, {}, 2.0, NOW)
        assert "high_relative_volume" not in risk_flags


# ---------------------------------------------------------------------------
# Signal strength
# ---------------------------------------------------------------------------

class TestSignalStrength:
    def test_extreme_mover_alone_is_high(self):
        assert _signal_strength(["extreme_mover"]) == "high"

    def test_three_types_is_high(self):
        assert _signal_strength(["strong_momentum", "breakout_candidate", "needs_research"]) == "high"

    def test_two_types_is_medium(self):
        assert _signal_strength(["strong_momentum", "breakout_candidate"]) == "medium"

    def test_one_type_is_low(self):
        assert _signal_strength(["strong_momentum"]) == "low"


# ---------------------------------------------------------------------------
# recommended_next_step whitelist
# ---------------------------------------------------------------------------

class TestRecommendedNextStep:
    def test_always_in_whitelist(self):
        scenarios = [
            (["needs_research"], []),
            (["high_volatility"], []),
            (["breakout_candidate"], []),
            (["strong_momentum"], []),
            (["extreme_mover", "breakout_candidate"], ["extended_move"]),
            ([], []),
        ]
        for scan_types, risk_flags in scenarios:
            step = _recommended_next_step(scan_types, risk_flags)
            assert step in RECOMMENDED_NEXT_STEPS, f"{step} not in whitelist for {scan_types}"


# ---------------------------------------------------------------------------
# GUARDRAIL — banned words
# ---------------------------------------------------------------------------

class TestExplanationGuardrail:
    """The single most important test category. If this fails, fix the
    scanner before shipping — explanation must NEVER contain trading language."""

    def _build_examples(self):
        return [
            # (scan_types, risk_flags, snap, vol_ratio, freshness)
            (["strong_momentum"], [],
             {"change_1d_pct": 6, "change_5d_pct": 12, "change_1m_pct": 25, "week52_pct": 80},
             None, 5),
            (["extreme_mover", "high_volatility"], ["extended_move"],
             {"change_1d_pct": -15, "change_5d_pct": -5, "change_1m_pct": 35, "week52_pct": 50},
             3.5, None),
            (["breakout_candidate"], ["near_52w_high"],
             {"change_1d_pct": 1, "change_5d_pct": 4, "change_1m_pct": 8, "week52_pct": 95},
             2.1, 7),
            (["needs_research"], ["no_recent_research", "insufficient_data"],
             {"change_1d_pct": None, "change_5d_pct": 0, "change_1m_pct": 0, "week52_pct": None},
             None, None),
        ]

    def test_no_banned_words_in_any_explanation(self):
        for scan_types, risk_flags, snap, vr, days in self._build_examples():
            text = _explanation(scan_types, risk_flags, snap, vr, days).lower()
            for banned in BANNED_WORDS:
                assert banned.lower() not in text, (
                    f"BANNED WORD '{banned}' found in explanation: {text}"
                )

    def test_explanation_contains_research_language(self):
        text = _explanation(
            ["strong_momentum"], [],
            {"change_1d_pct": 6, "change_5d_pct": 12, "change_1m_pct": 25, "week52_pct": 80},
            None, 5,
        ).lower()
        assert "research" in text or "validate" in text


# ---------------------------------------------------------------------------
# GUARDRAIL — Pydantic schema strictness (extra="forbid")
# ---------------------------------------------------------------------------

class TestSchemaStrictness:
    """Pydantic must reject any unknown field — guards against accidental
    leakage of buy_signal, target_price, position_size etc."""

    def _valid_item_dict(self):
        return {
            "instrument_id": "00000000-0000-0000-0000-000000000001",
            "ticker": "TEST",
            "issuer_name": "Test Corp",
            "universe_source": "all",
            "scan_types": ["strong_momentum"],
            "signal_strength": "low",
            "change_1d_pct": 5.5,
            "change_5d_pct": 10.0,
            "change_1m_pct": 15.0,
            "week52_position_pct": 70.0,
            "volume_ratio": 1.2,
            "risk_flags": [],
            "explanation": "Research candidate, validate against fundamentals.",
            "recommended_next_step": "research",
            "data_mode": "daily_eod",
            "as_of": "2026-04-16",
        }

    def test_valid_item_passes(self):
        ScanItem(**self._valid_item_dict())  # should not raise

    def test_buy_signal_field_rejected(self):
        d = self._valid_item_dict()
        d["buy_signal"] = True
        with pytest.raises(ValidationError):
            ScanItem(**d)

    def test_target_price_field_rejected(self):
        d = self._valid_item_dict()
        d["target_price"] = 100.0
        with pytest.raises(ValidationError):
            ScanItem(**d)

    def test_position_size_field_rejected(self):
        d = self._valid_item_dict()
        d["position_size"] = 100
        with pytest.raises(ValidationError):
            ScanItem(**d)

    def test_invalid_recommended_next_step_rejected(self):
        d = self._valid_item_dict()
        d["recommended_next_step"] = "buy"
        with pytest.raises(ValidationError):
            ScanItem(**d)

    def test_invalid_signal_strength_rejected(self):
        d = self._valid_item_dict()
        d["signal_strength"] = "extreme"
        with pytest.raises(ValidationError):
            ScanItem(**d)

    def test_data_mode_must_be_daily_eod(self):
        d = self._valid_item_dict()
        d["data_mode"] = "intraday"
        with pytest.raises(ValidationError):
            ScanItem(**d)


class TestResponseSchemaStrictness:
    def test_response_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ScanResponse(
                items=[],
                as_of=None,
                data_mode="daily_eod",
                universe="all",
                limit=50,
                scanned=0,
                matched=0,
                rogue_field="should_not_exist",
            )


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------

class TestConstants:
    def test_recommended_steps_whitelist_has_no_trading_words(self):
        bad = {"buy", "sell", "enter", "exit", "long", "short", "close_position"}
        assert RECOMMENDED_NEXT_STEPS.isdisjoint(bad)

    def test_scan_types_set_immutable(self):
        # Sanity check no trading-action types
        bad = {"buy_signal", "sell_signal", "enter_long", "go_short"}
        assert SCAN_TYPES.isdisjoint(bad)
