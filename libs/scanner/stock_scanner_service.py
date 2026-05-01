"""Stock Scanner Service — research candidate discovery.

Research-open Layer 1 component. Reads price + research data, applies
deterministic rules, emits research candidates.

HARD CONSTRAINTS:
- NEVER produce buy/sell/enter/target/position/leverage language
- NEVER create execution objects
- NEVER write to broker
- recommended_next_step is whitelisted: {research, validate, add_to_watchlist,
  run_backtest, monitor}
- Explanation copy is generated from templates, not free-form LLM
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


SCAN_TYPES = {
    "strong_momentum",
    "extreme_mover",
    "breakout_candidate",
    "high_volatility",
    "needs_research",
}

RISK_FLAGS = {
    "extended_move",
    "near_52w_high",
    "no_recent_research",
    "insufficient_data",
    "high_volatility",
    "high_relative_volume",
}

RECOMMENDED_NEXT_STEPS = {
    "research",
    "validate",
    "add_to_watchlist",
    "run_backtest",
    "monitor",
}

# Phrases that MUST NOT appear in scanner-GENERATED text (explanation,
# recommended_next_step). Use precise phrases — single short words like
# "enter" / "exit" produce false positives against legitimate company names
# (e.g. "AMC Entertainment", "Exit Realty Inc").
#
# Scope: applied to explanation strings only, NOT to passthrough data fields
# like issuer_name or ticker.
BANNED_WORDS = (
    "buy now", "sell now",
    "buy signal", "sell signal",
    "enter long", "enter short", "enter position", "enter the trade", "enter now",
    "exit long", "exit short", "exit position", "close position",
    "target price", "stop loss", "take profit",
    "position size", "position sizing", "leverage",
    "guaranteed", "certain to rise", "must rise", "definitely will rise",
    # Research-only tone polish (added 2026-05-01): explanation must not
    # frame anything as a trade entry/exit decision, even as a risk hint.
    "trading near", "entry-timing", "entry timing",
    "new position", "new positions",
    # Chinese research-only tone polish: explanation must not contain
    # action-oriented phrases. Disclaimer banner negation lives in the
    # frontend bundle, not in this generator, so these are safe to ban here.
    "暴涨确定", "必涨", "一定会涨", "保证盈利",
    "入场时机", "建仓", "仓位建议", "买入建议", "卖出建议", "目标价",
)


@dataclass
class ScanCandidate:
    """A single scanner result. Constructed only via _build_candidate to
    guarantee field whitelist."""
    instrument_id: str
    ticker: str | None
    issuer_name: str | None
    universe_source: str
    scan_types: list[str]
    signal_strength: Literal["low", "medium", "high"]
    change_1d_pct: float | None
    change_5d_pct: float | None
    change_1m_pct: float | None
    week52_position_pct: float | None
    volume_ratio: float | None
    risk_flags: list[str]
    explanation: str
    recommended_next_step: Literal["research", "validate", "add_to_watchlist",
                                    "run_backtest", "monitor"]
    data_mode: str
    as_of: str | None


# ---------------------------------------------------------------------------
# Universe resolution
# ---------------------------------------------------------------------------

def _resolve_universe_all(db: Session) -> list[str]:
    rows = db.execute(text(
        "SELECT instrument_id::text FROM instrument WHERE is_active = TRUE"
    )).fetchall()
    return [r[0] for r in rows]


def _resolve_universe_watchlist(db: Session, group_id: str) -> list[str]:
    try:
        gid = uuid.UUID(group_id)
    except (ValueError, AttributeError, TypeError):
        return []
    rows = db.execute(text("""
        SELECT instrument_id::text
        FROM watchlist_item
        WHERE group_id = :gid
    """), {"gid": gid}).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Volume ratio computation (current / 60-day mean)
# ---------------------------------------------------------------------------

def _compute_volume_ratios(db: Session, instrument_ids: list[str]) -> dict[str, float | None]:
    """Return {instrument_id_str: volume_ratio} where volume_ratio =
    most_recent_volume / mean(last_60_days_volume_excluding_today).
    None if insufficient data.
    """
    if not instrument_ids:
        return {}
    placeholders = ", ".join(f"'{i}'::uuid" for i in instrument_ids)
    rows = db.execute(text(f"""
        WITH ranked AS (
            SELECT instrument_id, trade_date, volume,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM price_bar_raw
            WHERE instrument_id IN ({placeholders})
        )
        SELECT instrument_id::text, rn, volume::float
        FROM ranked
        WHERE rn <= 61
        ORDER BY instrument_id, rn
    """)).fetchall()
    by_inst: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        by_inst[r[0]].append((int(r[1]), float(r[2])))

    result: dict[str, float | None] = {}
    for iid in instrument_ids:
        bars = by_inst.get(iid, [])
        if len(bars) < 21:  # need at least 20 historical bars + today
            result[iid] = None
            continue
        today_vol = bars[0][1]
        # Mean of bars rn 2..61 (i.e. previous 60 sessions, excluding today)
        prior = [v for rn, v in bars if 2 <= rn <= 61]
        if not prior:
            result[iid] = None
            continue
        mean_vol = sum(prior) / len(prior)
        if mean_vol <= 0:
            result[iid] = None
            continue
        result[iid] = round(today_vol / mean_vol, 2)
    return result


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------

def _eval_rules(
    snap: dict,
    research: dict,
    volume_ratio: float | None,
    today: datetime,
) -> tuple[list[str], list[str], int | None]:
    """Apply rules. Returns (scan_types, risk_flags, freshness_days)."""
    scan_types: list[str] = []
    risk_flags: list[str] = []

    c1d = snap.get("change_1d_pct")
    c5d = snap.get("change_5d_pct")
    c1m = snap.get("change_1m_pct")
    w52 = snap.get("week52_pct")

    # --- scan_types ---
    if (c1d is not None and c1d >= 5) \
            or (c5d is not None and c5d >= 10) \
            or (c1m is not None and c1m >= 20):
        scan_types.append("strong_momentum")

    if c1d is not None and abs(c1d) >= 10:
        scan_types.append("extreme_mover")

    if w52 is not None and w52 >= 85:
        scan_types.append("breakout_candidate")

    if (c1d is not None and abs(c1d) >= 10) \
            or (c5d is not None and abs(c5d) >= 15) \
            or (c1m is not None and abs(c1m) >= 30):
        scan_types.append("high_volatility")

    # --- research freshness ---
    last_note_at = research.get("last_note_at") if research else None
    freshness_days: int | None = None
    if last_note_at:
        try:
            last_dt = datetime.fromisoformat(last_note_at)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            freshness_days = (today - last_dt).days
        except (ValueError, TypeError):
            freshness_days = None

    if freshness_days is None or freshness_days >= 14:
        scan_types.append("needs_research")

    # --- risk_flags ---
    if c1m is not None and c1m >= 30:
        risk_flags.append("extended_move")
    if w52 is not None and w52 >= 90:
        risk_flags.append("near_52w_high")
    if freshness_days is None or freshness_days >= 30:
        risk_flags.append("no_recent_research")
    if "high_volatility" in scan_types:
        risk_flags.append("high_volatility")

    # Insufficient data: ANY of the 4 key fields missing
    if c1d is None or c5d is None or c1m is None or w52 is None:
        risk_flags.append("insufficient_data")

    # Volume-related risk flags (separate from scan_types for the first version)
    if volume_ratio is not None and volume_ratio >= 3:
        if "high_relative_volume" not in risk_flags:
            risk_flags.append("high_relative_volume")

    # Deduplicate while preserving order
    seen = set()
    risk_flags = [x for x in risk_flags if not (x in seen or seen.add(x))]
    seen = set()
    scan_types = [x for x in scan_types if not (x in seen or seen.add(x))]

    return scan_types, risk_flags, freshness_days


def _signal_strength(scan_types: list[str]) -> str:
    if "extreme_mover" in scan_types or len(scan_types) >= 3:
        return "high"
    if len(scan_types) >= 2:
        return "medium"
    if len(scan_types) >= 1:
        return "low"
    return "low"


def _explanation(
    scan_types: list[str],
    risk_flags: list[str],
    snap: dict,
    volume_ratio: float | None,
    freshness_days: int | None,
) -> str:
    """Generate research-toned explanation from templates. NEVER uses
    buy/sell/target/position language."""
    parts: list[str] = []

    # Price-action summary
    pieces = []
    if snap.get("change_1d_pct") is not None:
        pieces.append(f"1D {snap['change_1d_pct']:+.1f}%")
    if snap.get("change_5d_pct") is not None:
        pieces.append(f"5D {snap['change_5d_pct']:+.1f}%")
    if snap.get("change_1m_pct") is not None:
        pieces.append(f"1M {snap['change_1m_pct']:+.1f}%")
    if pieces:
        parts.append("Recent price action: " + ", ".join(pieces) + ".")

    if snap.get("week52_pct") is not None:
        parts.append(f"Currently at {snap['week52_pct']:.0f}% of the 52-week range.")

    if volume_ratio is not None:
        if volume_ratio >= 3:
            parts.append(
                f"Volume is {volume_ratio:.1f}x the 60-day mean — "
                f"volume expansion requires validation, not confirmation of any move."
            )
        elif volume_ratio >= 2:
            parts.append(f"Volume is {volume_ratio:.1f}x the 60-day mean.")

    # Scan-type summary (descriptive, not prescriptive)
    if "extreme_mover" in scan_types:
        parts.append("Magnitude of recent move is unusually large.")
    if "breakout_candidate" in scan_types:
        parts.append("Price is in the upper band of the 52-week range.")
    if "strong_momentum" in scan_types and "extreme_mover" not in scan_types:
        parts.append("Price action shows momentum across multiple timeframes.")
    if "needs_research" in scan_types:
        if freshness_days is None:
            parts.append("No prior research notes on file.")
        else:
            parts.append(f"Last research note was {freshness_days} days ago.")

    # Risk reminders
    if "extended_move" in risk_flags:
        parts.append("Move is extended — mean-reversion risk should be considered.")
    if "near_52w_high" in risk_flags:
        parts.append(
            "Near the 52-week high — review valuation, news, and "
            "volatility context before further research prioritization."
        )

    # Closing — research-toned only
    parts.append(
        "This is a research candidate. Validate against fundamentals and "
        "recent news before any further action."
    )

    return " ".join(parts)


def _recommended_next_step(scan_types: list[str], risk_flags: list[str]) -> str:
    """Map scan_types → research action. Whitelisted return values only."""
    if "needs_research" in scan_types or "no_recent_research" in risk_flags:
        return "research"
    if "high_volatility" in scan_types or "extended_move" in risk_flags:
        return "validate"
    if "breakout_candidate" in scan_types:
        return "monitor"
    if "strong_momentum" in scan_types:
        return "run_backtest"
    return "research"


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan_stocks(
    db: Session,
    universe: str,
    *,
    watchlist_group_id: str | None = None,
    limit: int = 50,
    sort_by: str = "signal_strength",
    min_change_1d: float | None = None,
    min_change_5d: float | None = None,
    include_needs_research: bool = False,
) -> dict:
    """Run the stock scanner and return a structured response dict.

    Args mirror the API contract; returns a dict shaped for the response model.
    """
    # Resolve universe
    if universe == "all":
        instrument_ids = _resolve_universe_all(db)
    elif universe == "watchlist":
        if not watchlist_group_id:
            return {
                "items": [], "as_of": None, "data_mode": "daily_eod",
                "universe": "watchlist", "limit": limit,
                "scanned": 0, "matched": 0,
                "error": "watchlist_group_id is required when universe=watchlist",
            }
        instrument_ids = _resolve_universe_watchlist(db, watchlist_group_id)
    else:
        # holdings or other — caller already validated; safety fallback
        return {
            "items": [], "as_of": None, "data_mode": "daily_eod",
            "universe": universe, "limit": limit,
            "scanned": 0, "matched": 0,
            "error": f"universe '{universe}' is not supported in this version",
        }

    if not instrument_ids:
        return {
            "items": [], "as_of": None, "data_mode": "daily_eod",
            "universe": universe, "limit": limit,
            "scanned": 0, "matched": 0,
        }

    # Reuse existing helpers
    from apps.api.routers.watchlist import _compute_price_snapshots
    from libs.portfolio.portfolio_service import get_research_status_batch

    price_snaps = _compute_price_snapshots(db, instrument_ids)
    research_status = get_research_status_batch(db, instrument_ids)
    volume_ratios = _compute_volume_ratios(db, instrument_ids)

    # Ticker + issuer lookup
    placeholders = ", ".join(f"'{i}'::uuid" for i in instrument_ids)
    meta_rows = db.execute(text(f"""
        SELECT i.instrument_id::text, i.issuer_name_current,
               (SELECT id_value FROM instrument_identifier ii
                WHERE ii.instrument_id = i.instrument_id
                  AND ii.id_type = 'ticker'
                ORDER BY ii.is_primary DESC NULLS LAST
                LIMIT 1) AS ticker
        FROM instrument i
        WHERE i.instrument_id IN ({placeholders})
    """)).fetchall()
    meta = {r[0]: {"issuer_name": r[1], "ticker": r[2]} for r in meta_rows}

    today = datetime.now(timezone.utc)
    candidates: list[ScanCandidate] = []
    latest_overall: str | None = None

    for iid in instrument_ids:
        snap = price_snaps.get(iid, {})
        research = research_status.get(iid, {})
        vr = volume_ratios.get(iid)

        scan_types, risk_flags, freshness_days = _eval_rules(snap, research, vr, today)

        # Optional filtering on min change values (must satisfy if provided)
        if min_change_1d is not None:
            c1d = snap.get("change_1d_pct")
            if c1d is None or c1d < min_change_1d:
                continue
        if min_change_5d is not None:
            c5d = snap.get("change_5d_pct")
            if c5d is None or c5d < min_change_5d:
                continue

        # If the only matching scan_type is needs_research and the caller
        # did not opt-in, drop it.
        if not include_needs_research and scan_types == ["needs_research"]:
            continue
        if not scan_types:
            continue

        m = meta.get(iid, {})
        cand = ScanCandidate(
            instrument_id=iid,
            ticker=m.get("ticker"),
            issuer_name=m.get("issuer_name"),
            universe_source=universe,
            scan_types=scan_types,
            signal_strength=_signal_strength(scan_types),  # type: ignore[arg-type]
            change_1d_pct=snap.get("change_1d_pct"),
            change_5d_pct=snap.get("change_5d_pct"),
            change_1m_pct=snap.get("change_1m_pct"),
            week52_position_pct=snap.get("week52_pct"),
            volume_ratio=vr,
            risk_flags=risk_flags,
            explanation=_explanation(scan_types, risk_flags, snap, vr, freshness_days),
            recommended_next_step=_recommended_next_step(scan_types, risk_flags),  # type: ignore[arg-type]
            data_mode="daily_eod",
            as_of=snap.get("latest_trade_date"),
        )
        candidates.append(cand)
        if cand.as_of and (latest_overall is None or cand.as_of > latest_overall):
            latest_overall = cand.as_of

    # Sort
    rank = {"high": 0, "medium": 1, "low": 2}
    if sort_by == "signal_strength":
        candidates.sort(key=lambda c: (
            rank.get(c.signal_strength, 9),
            -(c.change_1d_pct or -1e9),
        ))
    elif sort_by == "change_1d":
        candidates.sort(key=lambda c: -(c.change_1d_pct or -1e9))
    elif sort_by == "change_5d":
        candidates.sort(key=lambda c: -(c.change_5d_pct or -1e9))
    elif sort_by == "change_1m":
        candidates.sort(key=lambda c: -(c.change_1m_pct or -1e9))
    elif sort_by == "week52":
        candidates.sort(key=lambda c: -(c.week52_position_pct or -1e9))

    matched = len(candidates)
    candidates = candidates[:limit]

    return {
        "items": [c.__dict__ for c in candidates],
        "as_of": latest_overall,
        "data_mode": "daily_eod",
        "universe": universe,
        "limit": limit,
        "scanned": len(instrument_ids),
        "matched": matched,
    }
