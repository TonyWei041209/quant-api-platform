"""Strategy interface abstractions for backtest and live execution.

Provides a clean separation between:
- Universe selection (which instruments to consider)
- Signal generation (what to buy/sell and how strongly)
- Portfolio construction (how to size positions)
- Risk management (constraints and limits)

All abstract interfaces use explicit ``asof_date`` parameters to
prevent look-ahead bias, consistent with the rest of the research
and backtest libraries.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import uuid

import pandas as pd
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    """A trading signal for a single instrument."""

    instrument_id: uuid.UUID
    ticker: str
    weight: float  # target weight in portfolio (0.0 = no position, 1.0 = 100%)
    score: float = 0.0  # signal strength for ranking
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract interfaces
# ---------------------------------------------------------------------------


class UniverseProvider(ABC):
    """Defines which instruments are eligible for trading."""

    @abstractmethod
    def get_universe(self, session: Session, asof_date: date) -> list[uuid.UUID]:
        """Return instrument_ids eligible as of the given date."""
        ...


class SignalProvider(ABC):
    """Generates trading signals for a universe of instruments."""

    @abstractmethod
    def generate_signals(
        self,
        session: Session,
        instrument_ids: list[uuid.UUID],
        asof_date: date,
    ) -> list[Signal]:
        """Generate signals for the given instruments as of the date."""
        ...


class PortfolioConstructor(ABC):
    """Converts signals into target portfolio weights."""

    @abstractmethod
    def construct(
        self,
        signals: list[Signal],
        current_positions: dict[uuid.UUID, float],
    ) -> dict[uuid.UUID, float]:
        """Return target weights ``{instrument_id: weight}``."""
        ...


class RiskOverlay(ABC):
    """Applies risk constraints to target weights."""

    @abstractmethod
    def apply(
        self,
        target_weights: dict[uuid.UUID, float],
        context: dict,
    ) -> dict[uuid.UUID, float]:
        """Return adjusted weights after risk constraints."""
        ...


# ---------------------------------------------------------------------------
# Concrete implementations — Universe
# ---------------------------------------------------------------------------


class AllActiveUniverse(UniverseProvider):
    """All active instruments in the database."""

    def get_universe(self, session: Session, asof_date: date) -> list[uuid.UUID]:
        from sqlalchemy import text

        rows = session.execute(
            text("SELECT instrument_id FROM instrument WHERE is_active = true")
        ).fetchall()
        return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Concrete implementations — Portfolio construction
# ---------------------------------------------------------------------------


class EqualWeightConstructor(PortfolioConstructor):
    """Equal weight across all signals with positive weight.

    Signals are ranked by ``score`` descending, then the top
    ``max_positions`` are selected and equally weighted.
    """

    def __init__(self, max_positions: int = 20):
        self.max_positions = max_positions

    def construct(
        self,
        signals: list[Signal],
        current_positions: dict[uuid.UUID, float],
    ) -> dict[uuid.UUID, float]:
        ranked = sorted(
            [s for s in signals if s.weight > 0],
            key=lambda s: s.score,
            reverse=True,
        )
        selected = ranked[: self.max_positions]
        if not selected:
            return {}
        w = 1.0 / len(selected)
        return {s.instrument_id: w for s in selected}


# ---------------------------------------------------------------------------
# Concrete implementations — Risk
# ---------------------------------------------------------------------------


class MaxPositionRiskOverlay(RiskOverlay):
    """Cap individual position sizes.

    After capping, weights are renormalised so that they sum to 1.0.
    """

    def __init__(self, max_weight: float = 0.25):
        self.max_weight = max_weight

    def apply(
        self,
        target_weights: dict[uuid.UUID, float],
        context: dict,
    ) -> dict[uuid.UUID, float]:
        capped = {k: min(v, self.max_weight) for k, v in target_weights.items()}
        total = sum(capped.values())
        if total > 0:
            capped = {k: v / total for k, v in capped.items()}
        return capped


# ---------------------------------------------------------------------------
# Concrete implementations — Signal generation
# ---------------------------------------------------------------------------


class MomentumSignalProvider(SignalProvider):
    """Simple momentum-based signal using N-day returns.

    Instruments with positive ``lookback_days``-period returns receive a
    weight of 1.0 (eligible) and the raw return as their score.
    Instruments with non-positive returns are excluded.
    """

    def __init__(self, lookback_days: int = 63):
        self.lookback_days = lookback_days

    def generate_signals(
        self,
        session: Session,
        instrument_ids: list[uuid.UUID],
        asof_date: date,
    ) -> list[Signal]:
        from sqlalchemy import text

        signals: list[Signal] = []
        for iid in instrument_ids:
            rows = session.execute(
                text(
                    """
                    SELECT close FROM price_bar_raw
                    WHERE instrument_id = :iid AND trade_date <= :asof
                    ORDER BY trade_date DESC LIMIT :n
                    """
                ),
                {"iid": iid, "asof": asof_date, "n": self.lookback_days + 1},
            ).fetchall()

            if len(rows) < 2:
                continue

            latest = float(rows[0][0])
            oldest = float(rows[-1][0])
            if oldest > 0:
                ret = (latest / oldest) - 1.0

                # Resolve ticker for display purposes
                ticker_row = session.execute(
                    text(
                        "SELECT id_value FROM instrument_identifier "
                        "WHERE instrument_id = :iid "
                        "AND id_type = 'ticker' AND is_primary = true "
                        "LIMIT 1"
                    ),
                    {"iid": iid},
                ).fetchone()
                ticker = ticker_row[0] if ticker_row else str(iid)[:8]

                signals.append(
                    Signal(
                        instrument_id=iid,
                        ticker=ticker,
                        weight=1.0 if ret > 0 else 0.0,
                        score=ret,
                        metadata={"return": ret, "lookback": self.lookback_days},
                    )
                )

        return signals
