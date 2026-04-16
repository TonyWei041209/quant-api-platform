"""Pilot ingestion script: add 6 T212-tradable scalping candidates.

Creates Instrument + InstrumentIdentifier + TickerHistory rows, then loads
EOD price bars via the existing dev_load_prices adapter (source='yfinance_dev').

Guardrails:
- Dev data source only (tagged 'yfinance_dev'), never claimed as production
- Idempotent: safe to re-run, existing instruments are skipped
- Research-open scope: no execution, no broker write
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.instrument import Instrument
from libs.db.models.identifier import InstrumentIdentifier
from libs.db.models.ticker_history import TickerHistory
from libs.db.session import get_sync_session
from libs.ingestion.dev_load_prices import load_eod_prices

logger = get_logger(__name__)


# Pilot universe — known T212-tradable US-listed scalping candidates
# Picked for mix of price tiers, volatility profiles, sectors.
PILOT_CANDIDATES = [
    {"ticker": "SOFI", "issuer": "SoFi Technologies, Inc.", "exchange": "NASDAQ"},
    {"ticker": "F",    "issuer": "Ford Motor Company",       "exchange": "NYSE"},
    {"ticker": "SIRI", "issuer": "Sirius XM Holdings Inc.",  "exchange": "NASDAQ"},
    {"ticker": "NIO",  "issuer": "NIO Inc.",                 "exchange": "NYSE"},
    {"ticker": "LCID", "issuer": "Lucid Group, Inc.",        "exchange": "NASDAQ"},
    {"ticker": "AMC",  "issuer": "AMC Entertainment Holdings","exchange": "NYSE"},
]


def ensure_instrument(session, ticker: str, issuer: str, exchange: str) -> str:
    """Create instrument/identifier/ticker_history if missing. Returns instrument_id."""
    existing = session.execute(
        text("""
            SELECT instrument_id::text FROM instrument_identifier
            WHERE id_type = 'ticker' AND id_value = :t
        """),
        {"t": ticker.upper()},
    ).first()
    if existing:
        return existing[0]

    # Create instrument
    iid = new_id()
    session.add(Instrument(
        instrument_id=iid,
        asset_type="EQUITY",
        issuer_name_current=issuer,
        exchange_primary=exchange,
        currency="USD",
        country_code="US",
        is_active=True,
    ))

    # Create ticker identifier (source='pilot' so it's clearly tagged as manual seed)
    session.add(InstrumentIdentifier(
        instrument_id=iid,
        id_type="ticker",
        id_value=ticker.upper(),
        source="pilot",
        valid_from=date(2020, 1, 1),
        is_primary=True,
    ))

    # Ticker history (required by watchlist + instruments router)
    session.add(TickerHistory(
        instrument_id=iid,
        ticker=ticker.upper(),
        effective_from=date(2020, 1, 1),
        issuer_name=issuer,
        exchange=exchange,
        source="pilot",
    ))

    session.flush()
    logger.info("pilot.instrument_created", ticker=ticker, instrument_id=str(iid))
    return str(iid)


def main():
    session = get_sync_session()
    summary = []

    try:
        for cand in PILOT_CANDIDATES:
            ticker = cand["ticker"]
            iid = ensure_instrument(
                session, ticker, cand["issuer"], cand["exchange"]
            )
            session.commit()

            # Load price history via existing adapter (source='yfinance_dev')
            try:
                counters = load_eod_prices(
                    session, ticker,
                    start="2023-01-01",
                    end="2025-01-01",
                )
                summary.append({
                    "ticker": ticker,
                    "instrument_id": iid[:8] + "...",
                    "inserted": counters["inserted"],
                    "skipped": counters["skipped"],
                    "errors": counters["errors"],
                })
            except Exception as e:
                logger.error("pilot.load_failed", ticker=ticker, error=str(e))
                summary.append({
                    "ticker": ticker, "instrument_id": iid[:8] + "...",
                    "error": str(e),
                })

    finally:
        session.close()

    # Print summary
    print()
    print("=" * 70)
    print("PILOT INGESTION SUMMARY")
    print("=" * 70)
    for row in summary:
        print(f"  {row}")


if __name__ == "__main__":
    main()
