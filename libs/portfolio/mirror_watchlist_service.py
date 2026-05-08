"""Trading 212 Mirror Watchlist — composed read-only view.

Trading 212's public API does NOT expose the user's in-app watchlist. This
service composes a "mirror" view from data we already have access to:

  1. HELD              — currently held positions from the latest
                         `sync_session_id` snapshot in `broker_position_snapshot`
                         (live read-through is not used here so the mirror
                         endpoint can serve dozens of dashboard polls without
                         hitting T212 every few seconds)
  2. RECENTLY_TRADED   — distinct broker_tickers from `broker_order_snapshot`
                         within a configurable lookback (default 7 days),
                         status=FILLED only
  3. WATCHED           — manually-supplied tickers (passed via query string by
                         the Dashboard, persisted in browser localStorage —
                         see plan doc; no schema migration in this phase)

Each ticker resolves to an internal `instrument_id` when possible (via
`ticker_history` and `instrument_identifier` lookups). Unresolved entries
are kept with `mapping_status="unresolved"` and an `Unmapped` source tag.

This module:
  - never writes to the database
  - never calls a Trading 212 write endpoint
  - never touches order_intent / order_draft / submit objects
  - never reads or mutates FEATURE_T212_LIVE_SUBMIT
  - never scrapes or automates a browser
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from libs.core.time import utc_now


SOURCE_LIVE_HOLDINGS = "live_holdings"
SOURCE_DB_HOLDINGS = "db_latest_session"
DEFAULT_RECENT_LOOKBACK_DAYS = 7

# Display ticker normalization: T212 broker_ticker is `{TICKER}_{EXCHANGE}_{TYPE}`
# (e.g. `MU_US_EQ`, `NOK_US_EQ`, `SMSNl_EQ`). Pull the first segment as the
# display ticker. Same logic as `sync_trading212_readonly._resolve_instrument_id`.
_BROKER_TICKER_DISPLAY_RE = re.compile(r"^([A-Za-z0-9.\-]+)")


def normalize_display_ticker(broker_ticker: str | None) -> str | None:
    """`MU_US_EQ` -> `MU`. Returns None for empty input."""
    if not broker_ticker:
        return None
    match = _BROKER_TICKER_DISPLAY_RE.match(broker_ticker.strip())
    return match.group(1).upper() if match else None


def normalize_user_ticker(raw: str) -> str | None:
    """Sanitize user-supplied ticker input.

    Strips whitespace, uppercases, drops anything that isn't a plausible
    ticker character. Empty / non-conforming input returns None.
    """
    if raw is None:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9.\-_]", "", raw.strip()).upper()
    if not cleaned:
        return None
    if len(cleaned) > 20:
        cleaned = cleaned[:20]
    return cleaned


@dataclass
class _ResolvedTicker:
    instrument_id: str | None
    company_name: str | None


def _build_ticker_resolver(db: Session) -> dict[str, _ResolvedTicker]:
    """Map UPPER(display_ticker) -> {instrument_id, company_name}.

    Read-only. Joins ticker_history (canonical) and instrument_identifier
    (type=ticker) to the instrument table for the issuer name.
    """
    resolver: dict[str, _ResolvedTicker] = {}

    # ticker_history is the canonical mapping
    rows = db.execute(sql_text(
        """
        SELECT th.ticker, th.instrument_id, i.issuer_name_current
        FROM ticker_history th
        JOIN instrument i ON i.instrument_id = th.instrument_id
        WHERE th.ticker IS NOT NULL
        """
    )).fetchall()
    for tk, iid, name in rows:
        if tk:
            resolver[tk.upper()] = _ResolvedTicker(
                instrument_id=str(iid),
                company_name=name,
            )

    # instrument_identifier (id_type='ticker') is the secondary source
    rows = db.execute(sql_text(
        """
        SELECT ii.id_value, ii.instrument_id, i.issuer_name_current
        FROM instrument_identifier ii
        JOIN instrument i ON i.instrument_id = ii.instrument_id
        WHERE ii.id_type = 'ticker' AND ii.id_value IS NOT NULL
        """
    )).fetchall()
    for tk, iid, name in rows:
        if tk and tk.upper() not in resolver:
            resolver[tk.upper()] = _ResolvedTicker(
                instrument_id=str(iid),
                company_name=name,
            )
    return resolver


def _resolve(broker_ticker: str | None, resolver: dict[str, _ResolvedTicker]) -> _ResolvedTicker:
    display = normalize_display_ticker(broker_ticker)
    if display and display in resolver:
        return resolver[display]
    return _ResolvedTicker(instrument_id=None, company_name=None)


def _fetch_held(db: Session, broker: str = "trading212") -> list[dict]:
    """Latest sync_session_id holdings (matches portfolio_service semantics).

    Read-only. Falls back to the legacy DISTINCT-on-broker_ticker query when
    no row has a sync_session_id yet, so the mirror keeps working during a
    rollout window.
    """
    sid_row = db.execute(sql_text(
        """
        SELECT sync_session_id
        FROM broker_position_snapshot
        WHERE broker = :broker AND sync_session_id IS NOT NULL
        ORDER BY snapshot_at DESC
        LIMIT 1
        """
    ), {"broker": broker}).fetchone()

    if sid_row and sid_row[0] is not None:
        rows = db.execute(sql_text(
            """
            SELECT broker_ticker, instrument_id, quantity, current_price,
                   market_value, pnl, snapshot_at
            FROM broker_position_snapshot
            WHERE broker = :broker
              AND sync_session_id = :sid
              AND quantity > 0
            ORDER BY snapshot_at DESC, broker_ticker
            """
        ), {"broker": broker, "sid": sid_row[0]}).fetchall()
    else:
        rows = db.execute(sql_text(
            """
            SELECT DISTINCT ON (broker_ticker)
                   broker_ticker, instrument_id, quantity, current_price,
                   market_value, pnl, snapshot_at
            FROM broker_position_snapshot
            WHERE broker = :broker AND quantity > 0
            ORDER BY broker_ticker, snapshot_at DESC
            """
        ), {"broker": broker}).fetchall()

    out = []
    for r in rows:
        out.append({
            "broker_ticker": r[0],
            "db_instrument_id": str(r[1]) if r[1] else None,
            "quantity": float(r[2]) if r[2] is not None else 0.0,
            "current_price": float(r[3]) if r[3] is not None else None,
            "market_value": float(r[4]) if r[4] is not None else None,
            "pnl": float(r[5]) if r[5] is not None else None,
            "snapshot_at": r[6].isoformat() if r[6] else None,
        })
    return out


def _fetch_recently_traded(
    db: Session,
    broker: str = "trading212",
    lookback_days: int = DEFAULT_RECENT_LOOKBACK_DAYS,
) -> list[dict]:
    """Distinct broker_tickers traded (FILLED) within the lookback window."""
    cutoff = utc_now() - timedelta(days=lookback_days)
    rows = db.execute(sql_text(
        """
        SELECT broker_ticker,
               MAX(filled_at)    AS last_filled,
               MAX(snapshot_at)  AS last_seen
        FROM broker_order_snapshot
        WHERE broker = :broker
          AND broker_ticker IS NOT NULL
          AND status = 'FILLED'
          AND COALESCE(filled_at, snapshot_at) >= :cutoff
        GROUP BY broker_ticker
        ORDER BY last_seen DESC
        """
    ), {"broker": broker, "cutoff": cutoff}).fetchall()
    return [
        {
            "broker_ticker": r[0],
            "last_filled_at": r[1].isoformat() if r[1] else None,
            "last_seen_at": r[2].isoformat() if r[2] else None,
        }
        for r in rows
    ]


def build_mirror_watchlist(
    db: Session,
    *,
    manual_tickers: Iterable[str] | None = None,
    include_recent_orders: bool = True,
    recent_lookback_days: int = DEFAULT_RECENT_LOOKBACK_DAYS,
    broker: str = "trading212",
) -> dict:
    """Compose the Trading 212 Mirror watchlist payload.

    Pure read-only. Never writes the database, never calls upstream T212.
    """
    resolver = _build_ticker_resolver(db)

    held_rows = _fetch_held(db, broker=broker)
    recent_rows = (
        _fetch_recently_traded(db, broker=broker, lookback_days=recent_lookback_days)
        if include_recent_orders else []
    )

    cleaned_manual = []
    seen_manual = set()
    for raw in (manual_tickers or []):
        norm = normalize_user_ticker(raw)
        if norm and norm not in seen_manual:
            seen_manual.add(norm)
            cleaned_manual.append(norm)

    # Deduplicate by display_ticker, merging source tags. broker_ticker is
    # carried through when the same display_ticker came from a held/recent
    # row (so the UI can show the broker-side string too).
    by_display: dict[str, dict] = {}

    def _ensure(display: str, broker_ticker: str | None, last_seen_at: str | None) -> dict:
        item = by_display.get(display)
        if item is None:
            res = resolver.get(display, _ResolvedTicker(None, None))
            item = {
                "display_ticker": display,
                "broker_ticker": broker_ticker,
                "instrument_id": res.instrument_id,
                "company_name": res.company_name,
                "source_tags": [],
                "is_currently_held": False,
                "is_recently_traded": False,
                "is_user_watched": False,
                "mapping_status": "mapped" if res.instrument_id else "unresolved",
                "last_seen_at": last_seen_at,
                "live_quantity": None,
                "live_pnl": None,
                "current_price": None,
                "market_value": None,
            }
            by_display[display] = item
        else:
            if broker_ticker and not item["broker_ticker"]:
                item["broker_ticker"] = broker_ticker
            if last_seen_at and (item["last_seen_at"] is None or last_seen_at > item["last_seen_at"]):
                item["last_seen_at"] = last_seen_at
        return item

    for h in held_rows:
        display = normalize_display_ticker(h["broker_ticker"])
        if not display:
            continue
        item = _ensure(display, h["broker_ticker"], h["snapshot_at"])
        item["is_currently_held"] = True
        item["live_quantity"] = h["quantity"]
        item["live_pnl"] = h["pnl"]
        item["current_price"] = h["current_price"]
        item["market_value"] = h["market_value"]
        if "HELD" not in item["source_tags"]:
            item["source_tags"].append("HELD")

    for r in recent_rows:
        display = normalize_display_ticker(r["broker_ticker"])
        if not display:
            continue
        item = _ensure(display, r["broker_ticker"], r["last_seen_at"])
        item["is_recently_traded"] = True
        if "RECENTLY_TRADED" not in item["source_tags"]:
            item["source_tags"].append("RECENTLY_TRADED")

    for m in cleaned_manual:
        item = _ensure(m, None, None)
        item["is_user_watched"] = True
        if "WATCHED" not in item["source_tags"]:
            item["source_tags"].append("WATCHED")

    # Append UNMAPPED as a secondary tag so the UI badge stays simple
    for item in by_display.values():
        if item["mapping_status"] == "unresolved" and "UNMAPPED" not in item["source_tags"]:
            item["source_tags"].append("UNMAPPED")

    # Stable display order: HELD first (largest market_value first), then
    # RECENTLY_TRADED (most recent first), then WATCHED (alphabetical).
    held_items = sorted(
        (it for it in by_display.values() if it["is_currently_held"]),
        key=lambda it: (-(it.get("market_value") or 0), it["display_ticker"]),
    )
    recent_only = sorted(
        (it for it in by_display.values() if not it["is_currently_held"] and it["is_recently_traded"]),
        key=lambda it: it["last_seen_at"] or "",
        reverse=True,
    )
    watched_only = sorted(
        (it for it in by_display.values() if not it["is_currently_held"] and not it["is_recently_traded"]),
        key=lambda it: it["display_ticker"],
    )
    items = [*held_items, *recent_only, *watched_only]

    return {
        "name": "Trading 212 Mirror",
        "source": "trading212_mirror",
        "generated_at": utc_now().isoformat(),
        "official_watchlist_api_available": False,
        "explanation": (
            "Trading 212 does not expose app watchlists through the public API. "
            "This mirror combines live holdings, recent trades, and your "
            "manually added watched tickers."
        ),
        "lookback_days": recent_lookback_days,
        "counts": {
            "held": sum(1 for x in items if x["is_currently_held"]),
            "recently_traded": sum(1 for x in items if x["is_recently_traded"]),
            "user_watched": sum(1 for x in items if x["is_user_watched"]),
            "total": len(items),
            "unmapped": sum(1 for x in items if x["mapping_status"] == "unresolved"),
        },
        "items": items,
    }
