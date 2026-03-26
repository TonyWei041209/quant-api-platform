"""FMP Production Path Validation — Real data ingestion and verification."""
import asyncio
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER','quant')}:"
    f"{os.getenv('POSTGRES_PASSWORD','quant')}@"
    f"{os.getenv('POSTGRES_HOST','localhost')}:"
    f"{os.getenv('POSTGRES_PORT','5432')}/"
    f"{os.getenv('POSTGRES_DB','quant_platform')}"
)
engine = create_engine(DB_URL)

from libs.adapters.fmp_adapter import FMPAdapter

UNIVERSE = ["AAPL", "MSFT", "NVDA", "SPY"]


async def run():
    adapter = FMPAdapter()

    print("=" * 60)
    print("FMP PRODUCTION PATH VALIDATION")
    print("=" * 60)

    # Step 1: Get instrument_id mapping
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT instrument_id, id_value FROM instrument_identifier "
            "WHERE id_type='ticker' AND id_value IN :tickers"
        ), {"tickers": tuple(UNIVERSE)}).fetchall()
        ticker_to_id = {r[1]: r[0] for r in rows}

    print(f"\n[1] Instrument mapping: {len(ticker_to_id)} found")
    for t, iid in ticker_to_id.items():
        print(f"    {t} -> {str(iid)[:8]}...")

    if not ticker_to_id:
        print("ERROR: No instruments found in DB.")
        return

    # Step 2: Fetch and ingest EOD prices
    print(f"\n[2] Fetching EOD prices from FMP stable API...")
    total_bars = 0
    for ticker, inst_id in ticker_to_id.items():
        try:
            bars = await adapter.get_eod_prices(
                ticker, from_date="2025-01-01", to_date="2025-03-25"
            )
            if not bars:
                print(f"    {ticker}: 0 bars returned")
                continue

            with engine.begin() as conn:
                inserted = 0
                for bar in bars:
                    norm = adapter.normalize_price(bar)
                    td = norm["trade_date"]
                    if not td:
                        continue
                    exists = conn.execute(text(
                        "SELECT 1 FROM price_bar_raw "
                        "WHERE instrument_id=:iid AND trade_date=:td AND source='fmp'"
                    ), {"iid": inst_id, "td": td}).fetchone()
                    if exists:
                        continue
                    raw_json = json.dumps(bar, default=str)
                    conn.execute(text(
                        "INSERT INTO price_bar_raw "
                        "(instrument_id, trade_date, open, high, low, close, volume, vwap, source, ingested_at, raw_payload) "
                        "VALUES (:iid, :td, :o, :h, :l, :c, :v, :vwap, 'fmp', :now, CAST(:raw AS jsonb))"
                    ), {
                        "iid": inst_id, "td": td,
                        "o": norm["open"], "h": norm["high"],
                        "l": norm["low"], "c": norm["close"],
                        "v": norm["volume"], "vwap": norm.get("vwap"),
                        "now": datetime.now(timezone.utc),
                        "raw": raw_json,
                    })
                    inserted += 1
                total_bars += inserted
                print(f"    {ticker}: {len(bars)} fetched, {inserted} new bars inserted")
        except Exception as e:
            print(f"    {ticker}: ERROR - {e}")

    print(f"    Total new FMP bars: {total_bars}")

    # Step 3: Fetch and ingest fundamentals
    print(f"\n[3] Fetching financial statements...")
    for ticker, inst_id in ticker_to_id.items():
        try:
            income = await adapter.get_income_statement(ticker, limit=2)
            bs = await adapter.get_balance_sheet(ticker, limit=2)
            cf = await adapter.get_cash_flow(ticker, limit=2)

            with engine.begin() as conn:
                for stmt_list, stmt_type in [
                    (income, "income"), (bs, "balance"), (cf, "cashflow")
                ]:
                    for stmt in stmt_list:
                        period_end = stmt.get("date")
                        if not period_end:
                            continue
                        fy = stmt.get("calendarYear", period_end[:4])
                        fq_raw = stmt.get("period", "FY")
                        scope = "annual" if fq_raw == "FY" else "quarterly"
                        # Map period string to integer quarter
                        fq_map = {"FY": 0, "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
                        fq = fq_map.get(fq_raw, 0)
                        reported_at = (
                            stmt.get("fillingDate")
                            or stmt.get("acceptedDate")
                            or period_end
                        )

                        existing = conn.execute(text(
                            "SELECT financial_period_id FROM financial_period "
                            "WHERE instrument_id=:iid AND period_end=:pe "
                            "AND source='fmp' AND statement_scope=:scope"
                        ), {"iid": inst_id, "pe": period_end, "scope": scope}).fetchone()

                        if existing:
                            fp_id = existing[0]
                        else:
                            fp_id = uuid.uuid4()
                            conn.execute(text(
                                "INSERT INTO financial_period "
                                "(financial_period_id, instrument_id, statement_scope, "
                                "fiscal_year, fiscal_quarter, period_end, reported_at, "
                                "source, ingested_at) "
                                "VALUES (:fpid, :iid, :scope, :fy, :fq, :pe, :ra, 'fmp', :now)"
                            ), {
                                "fpid": fp_id, "iid": inst_id, "scope": scope,
                                "fy": int(fy) if fy else 2024, "fq": fq,
                                "pe": period_end, "ra": reported_at,
                                "now": datetime.now(timezone.utc),
                            })

                        facts = adapter.normalize_financial(stmt, stmt_type)
                        for fact in facts:
                            conn.execute(text(
                                "INSERT INTO financial_fact_std "
                                "(financial_period_id, statement_type, metric_code, "
                                "metric_value, unit, source, ingested_at) "
                                "VALUES (:fpid, :st, :mc, :mv, :u, 'fmp', :now) "
                                "ON CONFLICT DO NOTHING"
                            ), {
                                "fpid": fp_id, "st": fact["statement_type"],
                                "mc": fact["metric_code"],
                                "mv": fact["metric_value"],
                                "u": fact["unit"],
                                "now": datetime.now(timezone.utc),
                            })

            print(f"    {ticker}: income={len(income)}, balance={len(bs)}, cashflow={len(cf)}")
        except Exception as e:
            print(f"    {ticker}: ERROR - {e}")

    # Step 4: Profiles
    print(f"\n[4] Company profiles:")
    for ticker in UNIVERSE:
        try:
            profile = await adapter.get_profile(ticker)
            name = profile.get("companyName", "?")
            price = profile.get("price", "?")
            mcap = profile.get("marketCap", 0)
            print(f"    {ticker}: {name}, ${price}, MCap=${mcap/1e9:.0f}B")
        except Exception as e:
            print(f"    {ticker}: ERROR - {e}")

    # Step 5: Post-ingestion counts
    print(f"\n[5] Post-ingestion data counts:")
    with engine.connect() as conn:
        for table in ["price_bar_raw", "financial_period", "financial_fact_std"]:
            total = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            fmp = conn.execute(text(
                f"SELECT count(*) FROM {table} WHERE source='fmp'"
            )).scalar()
            print(f"    {table}: {total} total, {fmp} from FMP")

        sources = conn.execute(text(
            "SELECT source, count(*) FROM price_bar_raw GROUP BY source ORDER BY count(*) DESC"
        )).fetchall()
        print(f"\n    Price bar sources:")
        for src, cnt in sources:
            print(f"      {src}: {cnt} bars")

    # Step 6: Verify DQ
    print(f"\n[6] Running DQ on FMP data...")
    with engine.connect() as conn:
        # Check OHLC logic on FMP bars
        bad_ohlc = conn.execute(text(
            "SELECT count(*) FROM price_bar_raw "
            "WHERE source='fmp' AND (high < low OR high < open OR high < close "
            "OR low > open OR low > close)"
        )).scalar()
        print(f"    OHLC violations: {bad_ohlc}")

        # Check negative prices
        neg = conn.execute(text(
            "SELECT count(*) FROM price_bar_raw "
            "WHERE source='fmp' AND (close < 0 OR volume < 0)"
        )).scalar()
        print(f"    Negative price/volume: {neg}")

        # Check duplicates
        dupes = conn.execute(text(
            "SELECT instrument_id, trade_date, source, count(*) "
            "FROM price_bar_raw WHERE source='fmp' "
            "GROUP BY instrument_id, trade_date, source HAVING count(*) > 1"
        )).fetchall()
        print(f"    Duplicate bars: {len(dupes)}")

    print(f"\n{'=' * 60}")
    print("FMP VALIDATION COMPLETE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(run())
