"""DEV-ONLY: Bootstrap Scanner Research Universe (~35 instruments) into local DB.

Adds high-liquidity large/mid-cap US stocks + major ETFs to enable Scanner v1
to operate on a meaningful universe. Uses yfinance_dev as data source —
strictly dev-only by policy (source='yfinance_dev' tag, never production).

Refuses to run if DATABASE_URL points anywhere other than localhost.

Idempotent: existing tickers are skipped; existing price bars are skipped via
INSERT ... ON CONFLICT DO NOTHING.

Guardrails:
- Dev-only — refuses non-local DB targets
- Read-only against production (does not touch Cloud SQL)
- No execution objects, no broker writes, no scanner code changes
- All price bars tagged source='yfinance_dev'
"""
from __future__ import annotations

import sys
from datetime import date

from sqlalchemy import text

from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.db.models.instrument import Instrument
from libs.db.models.identifier import InstrumentIdentifier
from libs.db.models.ticker_history import TickerHistory
from libs.db.session import get_sync_session
from libs.ingestion.dev_load_prices import load_eod_prices

logger = get_logger(__name__)


# Research universe — ~35 high-liquidity large/mid-cap US stocks + major ETFs
# Categories chosen for scanner relevance, not for trading recommendation
RESEARCH_UNIVERSE = [
    # AI / Semiconductor
    {"ticker": "NVDA",  "issuer": "NVIDIA Corporation",                       "exchange": "NASDAQ", "category": "ai_semi"},
    {"ticker": "AMD",   "issuer": "Advanced Micro Devices, Inc.",             "exchange": "NASDAQ", "category": "ai_semi"},
    {"ticker": "AVGO",  "issuer": "Broadcom Inc.",                            "exchange": "NASDAQ", "category": "ai_semi"},
    {"ticker": "TSM",   "issuer": "Taiwan Semiconductor Manufacturing (ADR)", "exchange": "NYSE",   "category": "ai_semi"},
    {"ticker": "INTC",  "issuer": "Intel Corporation",                        "exchange": "NASDAQ", "category": "ai_semi"},
    {"ticker": "MU",    "issuer": "Micron Technology, Inc.",                  "exchange": "NASDAQ", "category": "ai_semi"},
    # Mega-cap tech
    {"ticker": "AAPL",  "issuer": "Apple Inc.",                               "exchange": "NASDAQ", "category": "mega_tech"},
    {"ticker": "MSFT",  "issuer": "Microsoft Corporation",                    "exchange": "NASDAQ", "category": "mega_tech"},
    {"ticker": "GOOGL", "issuer": "Alphabet Inc. Class A",                    "exchange": "NASDAQ", "category": "mega_tech"},
    {"ticker": "META",  "issuer": "Meta Platforms, Inc.",                     "exchange": "NASDAQ", "category": "mega_tech"},
    {"ticker": "AMZN",  "issuer": "Amazon.com, Inc.",                         "exchange": "NASDAQ", "category": "mega_tech"},
    # EV / growth
    {"ticker": "TSLA",  "issuer": "Tesla, Inc.",                              "exchange": "NASDAQ", "category": "ev_growth"},
    {"ticker": "RIVN",  "issuer": "Rivian Automotive, Inc.",                  "exchange": "NASDAQ", "category": "ev_growth"},
    {"ticker": "LCID",  "issuer": "Lucid Group, Inc.",                        "exchange": "NASDAQ", "category": "ev_growth"},
    {"ticker": "NIO",   "issuer": "NIO Inc.",                                 "exchange": "NYSE",   "category": "ev_growth"},
    {"ticker": "XPEV",  "issuer": "XPeng Inc.",                               "exchange": "NYSE",   "category": "ev_growth"},
    # Fintech
    {"ticker": "SOFI",  "issuer": "SoFi Technologies, Inc.",                  "exchange": "NASDAQ", "category": "fintech"},
    {"ticker": "PLTR",  "issuer": "Palantir Technologies Inc.",               "exchange": "NYSE",   "category": "fintech"},
    {"ticker": "COIN",  "issuer": "Coinbase Global, Inc.",                    "exchange": "NASDAQ", "category": "fintech"},
    # Financials
    {"ticker": "JPM",   "issuer": "JPMorgan Chase & Co.",                     "exchange": "NYSE",   "category": "financials"},
    {"ticker": "BAC",   "issuer": "Bank of America Corporation",              "exchange": "NYSE",   "category": "financials"},
    {"ticker": "GS",    "issuer": "The Goldman Sachs Group, Inc.",            "exchange": "NYSE",   "category": "financials"},
    # Energy
    {"ticker": "XOM",   "issuer": "Exxon Mobil Corporation",                  "exchange": "NYSE",   "category": "energy"},
    {"ticker": "CVX",   "issuer": "Chevron Corporation",                      "exchange": "NYSE",   "category": "energy"},
    {"ticker": "OXY",   "issuer": "Occidental Petroleum Corporation",         "exchange": "NYSE",   "category": "energy"},
    # Communications / consumer
    {"ticker": "DIS",   "issuer": "The Walt Disney Company",                  "exchange": "NYSE",   "category": "communications"},
    {"ticker": "NFLX",  "issuer": "Netflix, Inc.",                            "exchange": "NASDAQ", "category": "communications"},
    {"ticker": "UBER",  "issuer": "Uber Technologies, Inc.",                  "exchange": "NYSE",   "category": "consumer_tech"},
    # Auto (incumbent)
    {"ticker": "F",     "issuer": "Ford Motor Company",                       "exchange": "NYSE",   "category": "auto"},
    {"ticker": "GM",    "issuer": "General Motors Company",                   "exchange": "NYSE",   "category": "auto"},
    # Industrial high-beta
    {"ticker": "BA",    "issuer": "The Boeing Company",                       "exchange": "NYSE",   "category": "industrial"},
    # Existing pilot / scanner
    {"ticker": "SIRI",  "issuer": "Sirius XM Holdings Inc.",                  "exchange": "NASDAQ", "category": "communications"},
    {"ticker": "AMC",   "issuer": "AMC Entertainment Holdings, Inc.",         "exchange": "NYSE",   "category": "consumer_tech"},
    # ETFs
    {"ticker": "SPY",   "issuer": "SPDR S&P 500 ETF Trust",                   "exchange": "NYSE",   "category": "etf"},
    {"ticker": "QQQ",   "issuer": "Invesco QQQ Trust",                        "exchange": "NASDAQ", "category": "etf"},
    {"ticker": "IWM",   "issuer": "iShares Russell 2000 ETF",                 "exchange": "NYSE",   "category": "etf"},
]


def _verify_db_target_is_local(session) -> str:
    """Refuse to run against any non-localhost DB. Returns env label."""
    url = str(session.get_bind().url)
    if "localhost" in url or "127.0.0.1" in url:
        return "localhost (dev)"
    if "cloudsql" in url.lower() or "/cloudsql/" in url:
        raise SystemExit(
            "REFUSED: DATABASE_URL points to Cloud SQL. This script is dev-only. "
            "Aborting to protect production."
        )
    raise SystemExit(
        f"REFUSED: cannot determine DB target safely from URL. Aborting. "
        f"(URL must contain 'localhost' or '127.0.0.1' for this script to run.)"
    )


def ensure_instrument(session, ticker: str, issuer: str, exchange: str) -> tuple[str, bool]:
    """Create instrument/identifier/ticker_history if missing.
    Returns (instrument_id_str, was_created)."""
    existing = session.execute(
        text(
            "SELECT instrument_id::text FROM instrument_identifier "
            "WHERE id_type='ticker' AND id_value = :t"
        ),
        {"t": ticker.upper()},
    ).first()
    if existing:
        return existing[0], False

    iid = new_id()
    session.add(Instrument(
        instrument_id=iid,
        asset_type="EQUITY" if not ticker.upper() in ("SPY","QQQ","IWM") else "ETF",
        issuer_name_current=issuer,
        exchange_primary=exchange,
        currency="USD",
        country_code="US",
        is_active=True,
    ))
    session.add(InstrumentIdentifier(
        instrument_id=iid,
        id_type="ticker",
        id_value=ticker.upper(),
        source="bootstrap_dev",
        valid_from=date(2020, 1, 1),
        is_primary=True,
    ))
    session.add(TickerHistory(
        instrument_id=iid,
        ticker=ticker.upper(),
        effective_from=date(2020, 1, 1),
        issuer_name=issuer,
        exchange=exchange,
        source="bootstrap_dev",
    ))
    session.flush()
    logger.info("bootstrap.instrument_created", ticker=ticker, instrument_id=str(iid))
    return str(iid), True


def main():
    session = get_sync_session()
    env_label = _verify_db_target_is_local(session)
    print(f"DB target: {env_label}")

    summary = {
        "instruments_created": 0,
        "instruments_existing": 0,
        "price_load_success": [],
        "price_load_failed": [],
        "total_bars_inserted": 0,
        "total_bars_skipped": 0,
    }

    try:
        for cand in RESEARCH_UNIVERSE:
            ticker = cand["ticker"]
            try:
                iid, created = ensure_instrument(
                    session, ticker, cand["issuer"], cand["exchange"]
                )
                session.commit()
                if created:
                    summary["instruments_created"] += 1
                else:
                    summary["instruments_existing"] += 1

                # Load EOD bars via yfinance_dev (date range chosen for scanner needs:
                # need ~365 days for 52W + ~21 days for 1M signal — 2 years gives buffer)
                counters = load_eod_prices(
                    session, ticker,
                    start="2023-01-01",
                    end="2025-04-01",
                )
                summary["price_load_success"].append(ticker)
                summary["total_bars_inserted"] += counters["inserted"]
                summary["total_bars_skipped"] += counters["skipped"]
                if counters.get("errors", 0) > 0:
                    logger.warning("bootstrap.bar_errors_for_ticker",
                                   ticker=ticker, count=counters["errors"])

            except Exception as e:
                logger.error("bootstrap.failed", ticker=ticker, error=str(e))
                summary["price_load_failed"].append({"ticker": ticker, "error": str(e)[:120]})

    finally:
        session.close()

    print()
    print("=" * 70)
    print("BOOTSTRAP SUMMARY")
    print("=" * 70)
    print(f"  Instruments created      : {summary['instruments_created']}")
    print(f"  Instruments already-exist: {summary['instruments_existing']}")
    print(f"  Price loads successful   : {len(summary['price_load_success'])}")
    print(f"  Price loads failed       : {len(summary['price_load_failed'])}")
    print(f"  Bars inserted            : {summary['total_bars_inserted']}")
    print(f"  Bars skipped (existed)   : {summary['total_bars_skipped']}")
    if summary["price_load_failed"]:
        print()
        print("Failed tickers:")
        for f in summary["price_load_failed"]:
            print(f"  - {f['ticker']}: {f['error']}")


if __name__ == "__main__":
    main()
