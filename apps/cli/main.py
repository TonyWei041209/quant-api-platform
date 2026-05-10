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


@app.command()
def sync_eod_fmp(
    tickers: str = typer.Option("AAPL,MSFT,NVDA,SPY", help="Comma-separated tickers"),
    from_date: str = typer.Option("2025-01-01", help="Start date YYYY-MM-DD"),
    to_date: str = typer.Option("2025-12-31", help="End date YYYY-MM-DD"),
) -> None:
    """Sync EOD prices from FMP (production primary path)."""
    setup_logging()
    from libs.ingestion.sync_eod_prices_fmp import sync_eod_prices_fmp
    from sqlalchemy import text

    session = get_sync_session()
    try:
        for ticker in [t.strip() for t in tickers.split(",")]:
            row = session.execute(text(
                "SELECT instrument_id FROM instrument_identifier "
                "WHERE id_type='ticker' AND id_value=:t"
            ), {"t": ticker}).fetchone()
            if not row:
                typer.echo(f"  {ticker}: not found in DB, skipping")
                continue
            iid = str(row[0])
            counters = asyncio.run(sync_eod_prices_fmp(session, ticker, iid, from_date, to_date))
            typer.echo(f"  {ticker}: {counters}")
    finally:
        session.close()


@app.command()
def sync_fundamentals_fmp(
    tickers: str = typer.Option("AAPL,MSFT,NVDA", help="Comma-separated tickers"),
    limit: int = typer.Option(2, help="Number of periods per statement"),
) -> None:
    """Sync financial statements from FMP (production primary path)."""
    setup_logging()
    from libs.ingestion.sync_eod_prices_fmp import sync_fundamentals_fmp as _sync
    from sqlalchemy import text

    session = get_sync_session()
    try:
        for ticker in [t.strip() for t in tickers.split(",")]:
            row = session.execute(text(
                "SELECT instrument_id FROM instrument_identifier "
                "WHERE id_type='ticker' AND id_value=:t"
            ), {"t": ticker}).fetchone()
            if not row:
                typer.echo(f"  {ticker}: not found in DB, skipping")
                continue
            iid = str(row[0])
            counters = asyncio.run(_sync(session, ticker, iid, limit=limit))
            typer.echo(f"  {ticker}: {counters}")
    finally:
        session.close()


@app.command("sync-eod-prices-universe")
def sync_eod_prices_universe_cmd(
    universe: str = typer.Option("scanner-research", "--universe",
        help="Named universe to sync (currently: scanner-research)"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run",
        help="Default: True. Set --no-dry-run only with explicit --write."),
    write: bool = typer.Option(False, "--write/--no-write",
        help="Enable actual writes. Requires non-dry-run mode and a target flag."),
    db_target: str = typer.Option("local", "--db-target",
        help="local | production. Production also requires --confirm-production-write."),
    confirm_production_write: bool = typer.Option(False, "--confirm-production-write/--no-confirm-production-write",
        help="Second flag required for production writes. Single-flag production writes are refused."),
    polygon_delay_seconds: float = typer.Option(13.0, "--polygon-delay-seconds",
        help="Pacing between Polygon calls. Default 13s for free-tier 5/min safety."),
    lookback_days: int = typer.Option(7, "--lookback-days",
        help="How many days back from latest known trade_date to re-pull (idempotent overlap)."),
) -> None:
    """Plan-or-execute Scanner Research Universe daily EOD sync.

    By default this command is a DRY RUN. It computes a sync plan from
    existing local DB state (if any), prints the plan, and exits without
    making any provider HTTP calls or writing to any database.

    Production writes are gated by TWO explicit flags:
        --no-dry-run --write --db-target=production --confirm-production-write
    Without all four, production writes are refused.
    """
    setup_logging()
    from libs.ingestion.sync_eod_prices_universe import (
        build_sync_plan, render_plan_report, execute_sync, render_sync_result,
    )
    from libs.scanner.scanner_universe import get_universe

    # Resolve universe
    try:
        tickers = get_universe(universe)
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(code=1)

    # Determine effective write mode
    if dry_run or not write:
        write_mode = "DRY_RUN"
    elif db_target == "production":
        if not confirm_production_write:
            typer.echo(
                "REFUSED: --db-target=production requires --confirm-production-write. "
                "Single-flag production writes are not allowed by policy.",
                err=True,
            )
            raise typer.Exit(code=1)
        write_mode = "WRITE_PRODUCTION"
    elif db_target == "local":
        write_mode = "WRITE_LOCAL"
    else:
        typer.echo(f"ERROR: unknown --db-target '{db_target}' (use 'local' or 'production')", err=True)
        raise typer.Exit(code=1)

    # Open session ONLY if we need DB introspection. For pure DRY_RUN we
    # still introspect read-only to enrich the plan with last_known dates.
    session = get_sync_session()
    try:
        plan = build_sync_plan(
            universe_name=universe,
            tickers=tickers,
            write_mode=write_mode,
            confirm_production_write=confirm_production_write,
            polygon_delay_seconds=polygon_delay_seconds,
            lookback_days=lookback_days,
            session=session,
        )
        typer.echo(render_plan_report(plan))

        if write_mode == "DRY_RUN":
            return  # Exit cleanly — no writes, no API calls

        # WRITE_LOCAL: ingestion against localhost DB only.
        # WRITE_PRODUCTION: ingestion against Cloud SQL — only entered when
        # all four flags pass AND DB URL classifies as production. The
        # planner + execute_sync defense-in-depth verify this before any
        # provider HTTP call.
        # Any ValueError (e.g. db_target mismatch with write_mode) is a
        # caller / configuration error → REFUSED + exit 1, no writes.
        try:
            result = asyncio.run(execute_sync(plan, session=session))
        except ValueError as e:
            typer.echo(f"REFUSED: {e}", err=True)
            raise typer.Exit(code=1)
        typer.echo(render_sync_result(result))
    finally:
        session.close()


@app.command("bootstrap-research-universe-prod")
def bootstrap_research_universe_prod_cmd(
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run",
        help="Default: True. Set --no-dry-run only with explicit --write."),
    write: bool = typer.Option(False, "--write/--no-write",
        help="Enable actual writes. Requires non-dry-run mode and a target flag."),
    db_target: str = typer.Option("local", "--db-target",
        help="local | production. Production also requires --confirm-production-write."),
    confirm_production_write: bool = typer.Option(False, "--confirm-production-write/--no-confirm-production-write",
        help="Second flag required for production writes. Single-flag production writes are refused."),
    fmp_delay_seconds: float = typer.Option(1.0, "--fmp-delay-seconds",
        help="Pacing between FMP profile calls. Default 1.0s (FMP is more permissive than Polygon)."),
) -> None:
    """Plan-or-execute Scanner Research Universe production bootstrap.

    Bootstrap = scaffolding rows only (instrument + instrument_identifier +
    ticker_history). DOES NOT write price_bar_raw, corporate_action,
    earnings_event, financial facts, watchlist, broker, or execution tables.

    Target list is computed deterministically as
    ``SCANNER_RESEARCH_UNIVERSE - PROTECTED_TICKERS`` = 32 tickers.
    Protected tickers (NVDA / AAPL / MSFT / SPY) are HARD-EXCLUDED from the
    plan even if explicitly requested.

    By default this command is a DRY RUN. It computes a bootstrap plan from
    existing local DB state (if any), prints the plan, and exits without
    making any provider HTTP calls or writing to any database.

    Production writes are gated by FOUR explicit flags:
        --no-dry-run --write --db-target=production --confirm-production-write
    Without all four, production writes are refused.
    """
    setup_logging()
    from libs.ingestion.bootstrap_research_universe_prod import (
        build_bootstrap_plan,
        render_bootstrap_plan_report,
        execute_bootstrap,
        render_bootstrap_result,
    )
    from libs.scanner.scanner_universe import BOOTSTRAP_TARGET_TICKERS

    # Determine effective write mode
    if dry_run or not write:
        write_mode = "DRY_RUN"
    elif db_target == "production":
        if not confirm_production_write:
            typer.echo(
                "REFUSED: --db-target=production requires --confirm-production-write. "
                "Single-flag production writes are not allowed by policy.",
                err=True,
            )
            raise typer.Exit(code=1)
        write_mode = "WRITE_PRODUCTION"
    elif db_target == "local":
        write_mode = "WRITE_LOCAL"
    else:
        typer.echo(
            f"ERROR: unknown --db-target '{db_target}' (use 'local' or 'production')",
            err=True,
        )
        raise typer.Exit(code=1)

    session = get_sync_session()
    try:
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode=write_mode,
            confirm_production_write=confirm_production_write,
            fmp_delay_seconds=fmp_delay_seconds,
            session=session,
        )
        typer.echo(render_bootstrap_plan_report(plan))

        if write_mode == "DRY_RUN":
            return  # Exit cleanly — no writes, no API calls

        try:
            result = asyncio.run(execute_bootstrap(plan, session=session))
        except ValueError as e:
            typer.echo(f"REFUSED: {e}", err=True)
            raise typer.Exit(code=1)
        typer.echo(render_bootstrap_result(result))
    finally:
        session.close()


@app.command("bootstrap-mirror-instruments")
def bootstrap_mirror_instruments_cmd(
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run",
        help="Default: True. Set --no-dry-run only with explicit --write."),
    write: bool = typer.Option(False, "--write/--no-write",
        help="Enable actual writes. Requires non-dry-run mode and a target flag."),
    db_target: str = typer.Option("local", "--db-target",
        help="local | production. Production also requires --confirm-production-write."),
    confirm_production_write: bool = typer.Option(False, "--confirm-production-write/--no-confirm-production-write",
        help="Second flag required for production writes. Single-flag production writes are refused."),
    fetch_profiles: bool = typer.Option(False, "--fetch-profiles/--no-fetch-profiles",
        help="Default: False. When True, the dry-run plan calls FMP profile for each unmapped ticker (read-only)."),
    include_recent_orders: bool = typer.Option(True, "--include-recent-orders/--no-include-recent-orders",
        help="Include tickers traded within the lookback window."),
    lookback_days: int = typer.Option(7, "--lookback-days",
        help="Recent-orders lookback window."),
    manual: str = typer.Option("", "--manual",
        help="Comma-separated manually-watched tickers to merge into the plan."),
    fmp_delay_seconds: float = typer.Option(1.0, "--fmp-delay-seconds",
        help="Pacing between FMP profile calls."),
) -> None:
    """Plan-or-execute Trading 212 Mirror Universe instrument bootstrap.

    DRY RUN by default. Discovers tickers from broker_position_snapshot
    (held), broker_order_snapshot (recently traded), and the optional
    --manual list, then classifies each one against the platform
    instrument master:

        mapped              → already in the master, nothing to do
        unmapped            → not in the master, no provider lookup yet
                              (use --fetch-profiles to query FMP)
        newly_resolvable    → not in the master, FMP profile returned
                              enough fields to bootstrap on next write
        unresolved          → not in the master, FMP returned nothing
        ambiguous           → reserved (treated as unresolved this phase)

    The actual write path delegates to
    ``libs.ingestion.bootstrap_research_universe_prod`` which has the
    same four-flag handshake. Protected tickers (NVDA/AAPL/MSFT/SPY) are
    hard-excluded.

    Side-effect attestations:
        DB writes              : NONE in DRY_RUN; instrument /
                                 instrument_identifier / ticker_history
                                 in WRITE_*.
        price_bar_raw          : NEVER written by this command.
        corporate_action       : NEVER written by this command.
        earnings_event         : NEVER written by this command.
        watchlist_*            : NEVER written by this command.
        broker_*               : NEVER written by this command.
        order_intent / draft   : NEVER created.
        Live submit            : LOCKED (FEATURE_T212_LIVE_SUBMIT untouched).
    """
    setup_logging()
    from libs.instruments.mirror_instrument_mapper import (
        build_mirror_mapping_plan,
        filter_for_bootstrap,
        render_mapping_plan_report,
    )
    from libs.ingestion.bootstrap_research_universe_prod import (
        build_bootstrap_plan,
        render_bootstrap_plan_report,
        execute_bootstrap,
        render_bootstrap_result,
    )

    # Determine effective write mode (mirrors the existing pattern)
    if dry_run or not write:
        write_mode = "DRY_RUN"
    elif db_target == "production":
        if not confirm_production_write:
            typer.echo(
                "REFUSED: --db-target=production requires --confirm-production-write. "
                "Single-flag production writes are not allowed by policy.",
                err=True,
            )
            raise typer.Exit(code=1)
        write_mode = "WRITE_PRODUCTION"
    elif db_target == "local":
        write_mode = "WRITE_LOCAL"
    else:
        typer.echo(
            f"ERROR: unknown --db-target '{db_target}' (use 'local' or 'production')",
            err=True,
        )
        raise typer.Exit(code=1)

    manual_list = [t.strip() for t in manual.split(",") if t.strip()] if manual else None

    session = get_sync_session()
    try:
        # Build a profile fetcher only if requested (FMP is HTTP — no calls
        # are made when --no-fetch-profiles is in effect).
        fmp_fetcher = None
        if fetch_profiles:
            from libs.adapters.fmp_adapter import FMPAdapter
            adapter = FMPAdapter()

            async def _fetch(symbol: str) -> dict | None:
                return await adapter.get_profile(symbol)
            fmp_fetcher = _fetch

        plan = asyncio.run(build_mirror_mapping_plan(
            session,
            fetch_profiles=fetch_profiles,
            include_recent_orders=include_recent_orders,
            recent_lookback_days=lookback_days,
            manual_tickers=manual_list,
            fmp_profile_fetcher=fmp_fetcher,
        ))
        typer.echo(render_mapping_plan_report(plan))

        if write_mode == "DRY_RUN":
            return

        # Eligible-for-write tickers come from the mapping plan: only
        # newly_resolvable + non-protected entries. The downstream
        # bootstrap module re-checks protected and re-fetches its own
        # profile, so we are NOT trusting any plan output for
        # security-relevant decisions — defense in depth.
        eligible = filter_for_bootstrap(plan)
        if not eligible:
            typer.echo("Nothing eligible to bootstrap (no newly_resolvable items).")
            return

        boot_plan = build_bootstrap_plan(
            universe_name="trading212-mirror",
            tickers=eligible,
            write_mode=write_mode,
            confirm_production_write=confirm_production_write,
            fmp_delay_seconds=fmp_delay_seconds,
            session=session,
        )
        typer.echo(render_bootstrap_plan_report(boot_plan))

        try:
            result = asyncio.run(execute_bootstrap(boot_plan, session=session))
        except ValueError as e:
            typer.echo(f"REFUSED: {e}", err=True)
            raise typer.Exit(code=1)
        typer.echo(render_bootstrap_result(result))
    finally:
        session.close()


@app.command("generate-market-brief")
def generate_market_brief_cmd(
    mode: str = typer.Option(
        "overnight", "--mode",
        help="Run mode tag stored in market_brief_run.source. "
             "Use 'overnight' for the scheduled job; 'manual' for "
             "ad-hoc CLI runs.",
    ),
    days: int = typer.Option(
        7, "--days", min=1, max=30,
        help="News + earnings window in days (matches API default).",
    ),
    scanner_limit: int = typer.Option(
        50, "--scanner-limit", min=10, max=100,
        help="Max scanner candidates considered.",
    ),
    news_top_n: int = typer.Option(
        5, "--news-top-n", min=1, max=25,
        help="News fan-out cap.",
    ),
    news_limit_per_ticker: int = typer.Option(
        3, "--news-limit-per-ticker", min=1, max=10,
        help="Per-ticker news cap.",
    ),
    write_snapshot: bool = typer.Option(
        False, "--write-snapshot/--no-write-snapshot",
        help="If True, persist the brief to market_brief_run + "
             "market_brief_candidate_snapshot. Off by default.",
    ),
    db_target: str = typer.Option(
        "local", "--db-target",
        help="local | production. Snapshot writes still require "
             "FEATURE_RESEARCH_SNAPSHOT_WRITE to be enabled.",
    ),
) -> None:
    """Generate an overnight Market Brief from the CLI.

    READ-ONLY composition path: the command runs the same
    ``build_overnight_brief`` service that the API endpoint uses, then
    optionally persists the result via the research-only snapshot
    service (``libs.research_snapshot``).

    The CLI never:
      * calls a Trading 212 write endpoint
      * creates an order_intent / order_draft
      * mutates FEATURE_T212_LIVE_SUBMIT
      * writes broker_*, instrument_*, order_*, watchlist_*, etc.

    The only DB write — when --write-snapshot is set — goes to the
    four research snapshot tables introduced in migration
    `c1d4e7f8a902`. Snapshot persistence failure is isolated and never
    raises; the brief JSON is always printed to stdout.
    """
    setup_logging()
    from libs.market_brief.overnight_brief_service import build_overnight_brief
    from libs.research_snapshot import (
        is_snapshot_write_enabled,
        persist_market_brief_snapshot,
    )
    import json

    if db_target not in ("local", "production"):
        typer.echo(
            f"ERROR: unknown --db-target '{db_target}' "
            "(use 'local' or 'production')",
            err=True,
        )
        raise typer.Exit(code=1)

    session = get_sync_session()
    try:
        brief = asyncio.run(build_overnight_brief(
            session,
            days=days,
            scanner_limit=scanner_limit,
            news_top_n=news_top_n,
            news_limit_per_ticker=news_limit_per_ticker,
        ))
        # Print a single JSON line so log scrapers can ingest it.
        typer.echo(json.dumps({
            "status": "ok",
            "ticker_count": brief.get("ticker_count"),
            "universe_scope": brief.get("universe_scope"),
            "news_section_state": (
                brief.get("provider_diagnostics", {})
                .get("news", {})
                .get("section_state")
            ),
            "side_effects": brief.get("side_effects"),
        }))

        if write_snapshot:
            if not is_snapshot_write_enabled():
                typer.echo(json.dumps({
                    "status": "snapshot_skipped",
                    "reason": "FEATURE_RESEARCH_SNAPSHOT_WRITE is off",
                }))
            else:
                # Mode tag is stored as the persistence "source" so the
                # API history endpoints can filter by source.
                persist_result = persist_market_brief_snapshot(
                    session, brief, source=str(mode)[:32],
                )
                typer.echo(json.dumps({
                    "status": "snapshot_done",
                    **persist_result.to_dict(),
                }))
    finally:
        session.close()


if __name__ == "__main__":
    app()
