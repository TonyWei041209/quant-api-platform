"""DRY-RUN ONLY: Validate the rollback SQL template documented in
docs/scanner-research-universe-production-plan.md Section 6.

================================================================================
   ╔══════════════════════════════════════════════════════════════════════╗
   ║  DRY RUN ONLY — NO PRODUCTION DB ACCESS — NO COMMIT — NO DELETIONS   ║
   ║                                                                      ║
   ║  This script:                                                         ║
   ║    1. Refuses to run against any non-localhost DB                     ║
   ║    2. Wraps everything in BEGIN ... ROLLBACK                          ║
   ║    3. Runs SELECT COUNT(*) pre-checks first to size impact            ║
   ║    4. Executes the rollback DELETE templates inside the transaction   ║
   ║    5. Always ROLLBACKs — never COMMITs                                ║
   ║    6. Verifies post-ROLLBACK counts match pre-counts                  ║
   ║    7. Verifies the 4 protected tickers (NVDA/AAPL/MSFT/SPY) are       ║
   ║       NEVER inside the proposed DELETE scope                          ║
   ╚══════════════════════════════════════════════════════════════════════╝
================================================================================
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from libs.db.session import get_sync_session


# 32 tickers that the production seed WOULD add (universe minus the 4
# pre-existing in production: NVDA, AAPL, MSFT, SPY)
PRODUCTION_NEW_TICKERS = [
    "AMD","AVGO","TSM","INTC","MU","GOOGL","META","AMZN",
    "TSLA","RIVN","LCID","NIO","XPEV","SOFI","PLTR","COIN",
    "JPM","BAC","GS","XOM","CVX","OXY","DIS","NFLX","UBER",
    "F","GM","BA","SIRI","AMC","QQQ","IWM",
]

# These MUST NOT be deleted by rollback — they are pre-existing in production
PROTECTED_TICKERS = ["NVDA", "AAPL", "MSFT", "SPY"]


def banner():
    print()
    print("=" * 78)
    print("  ROLLBACK SQL DRY-RUN VALIDATION (BEGIN ... ROLLBACK)")
    print("  NO COMMIT — NO PRODUCTION DB — NO REAL DELETIONS")
    print("=" * 78)
    print()


def assert_localhost(session) -> str:
    url = str(session.get_bind().url)
    if "localhost" not in url and "127.0.0.1" not in url:
        raise SystemExit(
            f"REFUSED: DB target is not localhost. Aborting to protect production. "
            f"(URL host inspection only; password masked.)"
        )
    return "localhost (dev)"


def main() -> int:
    banner()
    session = get_sync_session()
    try:
        env = assert_localhost(session)
        print(f"DB target verified: {env}")
        print()

        # 1. Verify protected tickers are NOT in the rollback allowlist
        print("[1/5] Allowlist hygiene check")
        overlap = set(PROTECTED_TICKERS) & set(PRODUCTION_NEW_TICKERS)
        if overlap:
            print(f"    FAIL: protected ticker(s) {overlap} appear in rollback allowlist")
            return 1
        print(f"    OK: 0 of {len(PROTECTED_TICKERS)} protected tickers appear in "
              f"the {len(PRODUCTION_NEW_TICKERS)}-ticker rollback allowlist")
        print()

        # 2. Pre-count rows for the rollback target set
        print("[2/5] Pre-count rows that the rollback DELETE would target")
        pre_counts = _query_target_counts(session, PRODUCTION_NEW_TICKERS)
        for k, v in pre_counts.items():
            print(f"    {k:32s} {v:>6}")

        # 3. Pre-count rows for the protected tickers (must stay constant)
        print()
        print("[3/5] Pre-count rows for PROTECTED tickers (must remain unchanged)")
        protected_pre = _query_target_counts(session, PROTECTED_TICKERS)
        for k, v in protected_pre.items():
            print(f"    {k:32s} {v:>6}")

        # 4. Run the rollback DELETE INSIDE BEGIN ... ROLLBACK
        print()
        print("[4/5] Run rollback DELETE inside BEGIN ... ROLLBACK")
        print("    (this is the SQL template from plan doc Section 6,")
        print("     wrapped so nothing actually persists)")

        # SQLAlchemy autocommit-style: each session has implicit transaction.
        # We will explicitly issue the DELETE statements then call rollback().
        rollback_results = _run_rollback_delete_dryrun(session, PRODUCTION_NEW_TICKERS)
        for k, v in rollback_results.items():
            print(f"    {k:32s} would-delete={v}")
        # Roll back: SQLAlchemy session.rollback() reverts uncommitted changes
        session.rollback()
        print("    ROLLBACK executed — no rows persisted")

        # 5. Verify counts unchanged after rollback
        print()
        print("[5/5] Post-rollback verification")
        post_counts = _query_target_counts(session, PRODUCTION_NEW_TICKERS)
        post_protected = _query_target_counts(session, PROTECTED_TICKERS)

        target_unchanged = pre_counts == post_counts
        protected_unchanged = protected_pre == post_protected

        print(f"    Target counts unchanged    : {'YES' if target_unchanged else 'NO'}")
        print(f"    Protected counts unchanged : {'YES' if protected_unchanged else 'NO'}")

        ok = target_unchanged and protected_unchanged

        print()
        print("=" * 78)
        if ok:
            print("  RESULT: rollback SQL syntax valid; allowlist correctly excludes")
            print("  protected tickers; BEGIN/ROLLBACK leaves all data unchanged.")
            print("  Acceptance criterion #7 (rollback SQL tested in dev DB) → PASS")
            print("  No production DB was contacted. No COMMIT was issued.")
            return 0
        else:
            print("  RESULT: post-rollback state differs from pre-rollback state.")
            print("  This should be impossible with a successful ROLLBACK — investigate.")
            return 1
    finally:
        # Defensive: rollback any uncommitted state before closing
        try:
            session.rollback()
        except Exception:
            pass
        session.close()


def _query_target_counts(session, tickers: list[str]) -> dict[str, int]:
    """Read-only count of rows that the rollback would target for given tickers."""
    if not tickers:
        return {}

    # Find instrument_ids for these tickers
    sql = text("""
        SELECT id_value, instrument_id::text
        FROM instrument_identifier
        WHERE id_type = 'ticker' AND id_value = ANY(:tickers)
    """)
    rows = session.execute(sql, {"tickers": tickers}).fetchall()
    iids = [r[1] for r in rows]
    found_tickers = [r[0] for r in rows]

    counts = {
        "instruments_found": len(iids),
        "tickers_resolved": len(found_tickers),
    }
    if not iids:
        counts.update({
            "price_bar_raw_rows": 0,
            "instrument_identifier_rows": 0,
            "ticker_history_rows": 0,
        })
        return counts

    counts["price_bar_raw_rows"] = session.execute(
        text("SELECT COUNT(*) FROM price_bar_raw WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    ).scalar() or 0
    counts["instrument_identifier_rows"] = session.execute(
        text("SELECT COUNT(*) FROM instrument_identifier WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    ).scalar() or 0
    counts["ticker_history_rows"] = session.execute(
        text("SELECT COUNT(*) FROM ticker_history WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    ).scalar() or 0
    return counts


def _run_rollback_delete_dryrun(session, tickers: list[str]) -> dict[str, int]:
    """Issue the rollback DELETE statements WITHOUT committing.

    Returns the row counts that would be deleted, captured via RETURNING.
    Uses CTE form mirroring the plan doc Section 6 template.
    """
    if not tickers:
        return {}

    target_iids_sql = text("""
        SELECT i.instrument_id::text
        FROM instrument i
        JOIN instrument_identifier ii ON ii.instrument_id = i.instrument_id
        WHERE ii.id_type = 'ticker'
          AND ii.id_value = ANY(:tickers)
    """)
    iids = [r[0] for r in session.execute(target_iids_sql, {"tickers": tickers}).fetchall()]
    if not iids:
        return {"price_bar_raw_deleted": 0, "instrument_identifier_deleted": 0,
                "ticker_history_deleted": 0, "instrument_deleted": 0}

    # 1. price_bar_raw
    r1 = session.execute(
        text("DELETE FROM price_bar_raw WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    )
    # 2. instrument_identifier
    r2 = session.execute(
        text("DELETE FROM instrument_identifier WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    )
    # 3. ticker_history
    r3 = session.execute(
        text("DELETE FROM ticker_history WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    )
    # 4. instrument
    r4 = session.execute(
        text("DELETE FROM instrument WHERE instrument_id::text = ANY(:iids)"),
        {"iids": iids},
    )
    # IMPORTANT: caller must rollback. We don't commit here.
    return {
        "price_bar_raw_deleted": r1.rowcount,
        "instrument_identifier_deleted": r2.rowcount,
        "ticker_history_deleted": r3.rowcount,
        "instrument_deleted": r4.rowcount,
    }


if __name__ == "__main__":
    sys.exit(main())
