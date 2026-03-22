"""CLI entry point for quant-api-platform ingestion and management commands."""
from __future__ import annotations

import asyncio

import typer

from libs.core.config import get_settings
from libs.core.logging import setup_logging, get_logger
from libs.db.session import get_sync_session

app = typer.Typer(name="quant-cli", help="Quant API Platform CLI")
logger = get_logger(__name__)


@app.command()
def bootstrap_security_master(
    limit: int = typer.Option(None, help="Max number of companies to process"),
) -> None:
    """Bootstrap security master from SEC + OpenFIGI."""
    setup_logging()
    from libs.ingestion.bootstrap_security_master import bootstrap_security_master as _bootstrap

    session = get_sync_session()
    try:
        counters = asyncio.run(_bootstrap(session, limit=limit))
        typer.echo(f"Bootstrap complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_eod_prices(
    ticker: str = typer.Option(..., help="Ticker symbol"),
    instrument_id: str = typer.Option(..., help="Instrument UUID"),
    from_date: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., help="End date (YYYY-MM-DD)"),
) -> None:
    """Sync raw EOD prices from Massive."""
    setup_logging()
    from libs.ingestion.sync_eod_prices import sync_eod_prices as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session, ticker, instrument_id, from_date, to_date))
        typer.echo(f"EOD sync complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_corporate_actions(
    ticker: str = typer.Option(..., help="Ticker symbol"),
    instrument_id: str = typer.Option(..., help="Instrument UUID"),
) -> None:
    """Sync corporate actions (splits, dividends)."""
    setup_logging()
    from libs.ingestion.sync_corporate_actions import sync_corporate_actions as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session, ticker, instrument_id))
        typer.echo(f"Corporate actions sync complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_filings(
    cik: str = typer.Option(..., help="CIK number"),
    instrument_id: str = typer.Option(..., help="Instrument UUID"),
) -> None:
    """Sync SEC filings."""
    setup_logging()
    from libs.ingestion.sync_filings import sync_filings as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session, cik, instrument_id))
        typer.echo(f"Filings sync complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_earnings(
    symbol: str = typer.Option(..., help="Ticker symbol"),
    instrument_id: str = typer.Option(..., help="Instrument UUID"),
) -> None:
    """Sync earnings events from FMP."""
    setup_logging()
    from libs.ingestion.sync_earnings import sync_earnings as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session, symbol, instrument_id))
        typer.echo(f"Earnings sync complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_fundamentals(
    symbol: str = typer.Option(..., help="Ticker symbol"),
    instrument_id: str = typer.Option(..., help="Instrument UUID"),
    period: str = typer.Option("annual", help="annual or quarter"),
) -> None:
    """Sync financial statements from FMP."""
    setup_logging()
    from libs.ingestion.sync_fundamentals import sync_fundamentals as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session, symbol, instrument_id, period))
        typer.echo(f"Fundamentals sync complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_macro() -> None:
    """Sync macroeconomic data (Phase 1 skeleton)."""
    setup_logging()
    from libs.ingestion.sync_macro import sync_macro as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session))
        typer.echo(f"Macro sync complete: {counters}")
    finally:
        session.close()


@app.command()
def sync_trading212(
    demo: bool = typer.Option(True, help="Use demo account"),
) -> None:
    """Sync Trading 212 read-only data."""
    setup_logging()
    from libs.ingestion.sync_trading212_readonly import sync_trading212_readonly as _sync

    session = get_sync_session()
    try:
        counters = asyncio.run(_sync(session, use_demo=demo))
        typer.echo(f"Trading 212 sync complete: {counters}")
    finally:
        session.close()


@app.command()
def run_dq() -> None:
    """Run all data quality checks."""
    setup_logging()
    from libs.dq.rules import run_all_rules

    session = get_sync_session()
    try:
        counters = run_all_rules(session)
        typer.echo(f"DQ complete: {counters}")
    finally:
        session.close()


if __name__ == "__main__":
    app()
