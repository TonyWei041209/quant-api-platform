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
    tickers: str = typer.Option(None, help="Comma-separated list of tickers to bootstrap"),
) -> None:
    """Bootstrap security master from SEC + OpenFIGI."""
    setup_logging()
    from libs.ingestion.bootstrap_security_master import bootstrap_security_master as _bootstrap

    tickers_filter = [t.strip() for t in tickers.split(",")] if tickers else None
    session = get_sync_session()
    try:
        counters = asyncio.run(_bootstrap(session, limit=limit, tickers_filter=tickers_filter))
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


@app.command()
def populate_calendar(
    start_year: int = typer.Option(2020, help="Start year"),
    end_year: int = typer.Option(2026, help="End year"),
) -> None:
    """Populate exchange calendar for NYSE/NASDAQ."""
    setup_logging()
    from libs.ingestion.populate_exchange_calendar import populate_exchange_calendar

    session = get_sync_session()
    try:
        counters = populate_exchange_calendar(session, start_year=start_year, end_year=end_year)
        typer.echo(f"Calendar populated: {counters}")
    finally:
        session.close()


@app.command()
def status() -> None:
    """Show database status and record counts."""
    setup_logging()
    from sqlalchemy import text
    session = get_sync_session()
    try:
        tables = [
            "instrument", "instrument_identifier", "ticker_history",
            "exchange_calendar", "price_bar_raw", "corporate_action",
            "filing", "earnings_event", "financial_period", "financial_fact_std",
            "macro_series", "macro_observation", "source_run", "data_issue",
            "order_intent", "order_draft",
            "broker_account_snapshot", "broker_position_snapshot", "broker_order_snapshot",
        ]
        typer.echo("=== Database Status ===")
        for table in tables:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            typer.echo(f"  {table:.<40} {count:>8}")

        # Latest source runs
        typer.echo("\n=== Recent Source Runs ===")
        runs = session.execute(text(
            "SELECT job_name, status, started_at, counters "
            "FROM source_run ORDER BY started_at DESC LIMIT 10"
        )).fetchall()
        for r in runs:
            typer.echo(f"  {r[0]:.<30} {r[1]:<10} {str(r[2])[:19]}  {r[3]}")

        # DQ issues
        issue_count = session.execute(text("SELECT COUNT(*) FROM data_issue WHERE resolved_flag = false")).scalar()
        typer.echo(f"\n=== DQ Issues (unresolved): {issue_count} ===")
        if issue_count > 0:
            issues = session.execute(text(
                "SELECT rule_code, severity, table_name, record_key "
                "FROM data_issue WHERE resolved_flag = false "
                "ORDER BY issue_time DESC LIMIT 10"
            )).fetchall()
            for i in issues:
                typer.echo(f"  [{i[1]}] {i[0]} on {i[2]}: {i[3]}")
    finally:
        session.close()


@app.command()
def dq_report() -> None:
    """Run DQ and show detailed report."""
    setup_logging()
    from libs.dq.rules import run_all_rules
    from sqlalchemy import text
    session = get_sync_session()
    try:
        counters = run_all_rules(session)
        typer.echo(f"\n=== DQ Report ===")
        typer.echo(f"Rules run: {counters['rules_run']}")
        typer.echo(f"Issues found: {counters['issues_found']}")
        typer.echo(f"Rules skipped: {counters['rules_skipped']}")

        if counters['issues_found'] > 0:
            typer.echo(f"\n=== Issues Detail ===")
            issues = session.execute(text(
                "SELECT rule_code, severity, COUNT(*) "
                "FROM data_issue WHERE resolved_flag = false "
                "GROUP BY rule_code, severity ORDER BY rule_code"
            )).fetchall()
            for i in issues:
                typer.echo(f"  {i[0]} [{i[1]}]: {i[2]} issues")
    finally:
        session.close()


@app.command("run-backtest")
def run_backtest_cmd(
    strategy: str = typer.Option("momentum", help="Strategy name"),
    tickers: str = typer.Option("AAPL,MSFT,NVDA,SPY", help="Comma-separated tickers"),
    start: str = typer.Option("2023-01-01", help="Start date YYYY-MM-DD"),
    end: str = typer.Option("2024-12-31", help="End date YYYY-MM-DD"),
    commission_bps: float = typer.Option(5.0, help="Commission in basis points"),
    slippage_bps: float = typer.Option(5.0, help="Slippage in basis points"),
    max_positions: int = typer.Option(20, help="Max positions"),
    rebalance: str = typer.Option("monthly", help="Rebalance frequency"),
) -> None:
    """Run a backtest with the given strategy and parameters."""
    setup_logging()
    from datetime import date as dt_date
    from sqlalchemy import text

    session = get_sync_session()
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        typer.echo(f"Resolving tickers: {ticker_list}")

        rows = session.execute(
            text(
                "SELECT ii.id_value, i.instrument_id::text "
                "FROM instrument_identifier ii "
                "JOIN instrument i ON i.instrument_id = ii.instrument_id "
                "WHERE ii.id_type = 'ticker' AND ii.id_value = ANY(:tickers)"
            ),
            {"tickers": ticker_list},
        ).fetchall()

        if not rows:
            typer.echo("No instruments found for the given tickers.", err=True)
            raise typer.Exit(1)

        instrument_map = {r[0]: r[1] for r in rows}
        typer.echo(f"Resolved {len(instrument_map)} instruments: {list(instrument_map.keys())}")

        from libs.backtest.engine import run_and_persist_backtest, CostModel, PortfolioConfig

        cost = CostModel(slippage_bps=slippage_bps)
        config = PortfolioConfig(
            max_positions=max_positions,
            rebalance_frequency=rebalance,
        )

        result, run_id = run_and_persist_backtest(
            session=session,
            instrument_ids=list(instrument_map.values()),
            start_date=dt_date.fromisoformat(start),
            end_date=dt_date.fromisoformat(end),
            strategy_name=strategy,
            config=config,
            cost_model=cost,
        )
        session.commit()

        m = result.metrics
        typer.echo(f"\n=== Backtest Complete ===")
        typer.echo(f"  Run ID:           {run_id}")
        typer.echo(f"  Strategy:         {strategy}")
        typer.echo(f"  Period:           {start} to {end}")
        typer.echo(f"  Tickers:          {', '.join(ticker_list)}")
        typer.echo(f"  Total Return:     {m.get('total_return', 0):.2%}")
        typer.echo(f"  Ann. Return:      {m.get('annualized_return', 0):.2%}")
        typer.echo(f"  Sharpe Ratio:     {m.get('sharpe_ratio', 0):.2f}")
        typer.echo(f"  Max Drawdown:     {m.get('max_drawdown', 0):.2%}")
        typer.echo(f"  Total Trades:     {m.get('total_trades', 0)}")
        typer.echo(f"  Total Costs:      ${m.get('total_costs', 0):,.2f}")
        typer.echo(f"  Final NAV:        ${m.get('final_nav', 0):,.2f}")
    finally:
        session.close()


@app.command("list-instruments")
def list_instruments() -> None:
    """List all instruments with tickers and basic stats."""
    setup_logging()
    from sqlalchemy import text

    session = get_sync_session()
    try:
        sql = text("""
            SELECT
                i.instrument_id::text,
                i.issuer_name_current,
                COALESCE(ii.id_value, '—') AS ticker,
                COALESCE(pc.price_count, 0) AS price_count,
                COALESCE(ac.action_count, 0) AS action_count,
                COALESCE(fc.filing_count, 0) AS filing_count
            FROM instrument i
            LEFT JOIN LATERAL (
                SELECT id_value FROM instrument_identifier
                WHERE instrument_id = i.instrument_id AND id_type = 'ticker'
                LIMIT 1
            ) ii ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS price_count FROM price_bar_raw
                WHERE instrument_id = i.instrument_id
            ) pc ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS action_count FROM corporate_action
                WHERE instrument_id = i.instrument_id
            ) ac ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS filing_count FROM filing
                WHERE instrument_id = i.instrument_id
            ) fc ON true
            ORDER BY ii.id_value NULLS LAST
        """)
        rows = session.execute(sql).fetchall()

        typer.echo(f"{'Ticker':<10} {'Name':<35} {'Prices':>8} {'Actions':>8} {'Filings':>8}  {'Instrument ID'}")
        typer.echo("-" * 110)
        for row in rows:
            iid, name, ticker, prices, actions, filings = row
            display_name = (name or "—")[:34]
            typer.echo(
                f"{ticker:<10} {display_name:<35} {prices:>8} {actions:>8} {filings:>8}  {iid}"
            )
        typer.echo(f"\nTotal instruments: {len(rows)}")
    finally:
        session.close()


if __name__ == "__main__":
    app()
