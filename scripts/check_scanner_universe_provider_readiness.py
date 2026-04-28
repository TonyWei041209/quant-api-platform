"""DRY-RUN ONLY: Provider readiness check for Scanner Research Universe seed.

================================================================================
   ╔══════════════════════════════════════════════════════════════════════╗
   ║  DRY RUN ONLY — NO DB WRITES — NO PRODUCTION CHANGES                 ║
   ║                                                                      ║
   ║  This script does NOT:                                                ║
   ║    - Write to any database (local or production)                      ║
   ║    - Create any Cloud Run Job or Scheduler                            ║
   ║    - Deploy any service                                               ║
   ║    - Touch execution / broker write / live submit                     ║
   ║    - Use yfinance_dev as a production source                          ║
   ║                                                                      ║
   ║  This script ONLY:                                                    ║
   ║    - Inspects local environment for provider key presence             ║
   ║    - Optionally makes a tiny number of read-only provider calls       ║
   ║      (default: 3 sample tickers; can be skipped with --skip-api)      ║
   ║    - Prints a readiness report to stdout                              ║
   ╚══════════════════════════════════════════════════════════════════════╝
================================================================================

Usage:
    # Default — does up to 3 small API calls per provider
    python scripts/check_scanner_universe_provider_readiness.py

    # Truly read-only — no API calls at all
    python scripts/check_scanner_universe_provider_readiness.py --skip-api

    # Check all 36 tickers (only use when explicitly preparing for seed)
    python scripts/check_scanner_universe_provider_readiness.py --check-all

Exit codes:
    0 — readiness OK (or --skip-api with all keys present)
    1 — at least one critical readiness check failed
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# The 36-ticker universe — must match scripts/bootstrap_research_universe_dev.py
UNIVERSE = [
    "NVDA","AMD","AVGO","TSM","INTC","MU",
    "AAPL","MSFT","GOOGL","META","AMZN",
    "TSLA","RIVN","LCID","NIO","XPEV",
    "SOFI","PLTR","COIN",
    "JPM","BAC","GS",
    "XOM","CVX","OXY",
    "DIS","NFLX","UBER",
    "F","GM","BA",
    "SIRI","AMC",
    "SPY","QQQ","IWM",
]

SAMPLE_TICKERS = ["NVDA", "AMD", "QQQ"]  # used for default 3-ticker smoke


def print_banner():
    print()
    print("=" * 78)
    print("  DRY RUN ONLY — NO DB WRITES — NO PRODUCTION CHANGES")
    print("=" * 78)
    print()


def check_keys() -> dict[str, bool]:
    """Read-only check of key presence via the platform's settings loader.

    Uses libs.core.config.get_settings() so .env files are honored exactly the
    same way the rest of the platform reads them. NEVER prints key values.
    """
    print("[1/4] Provider key presence check (settings — values masked)")
    try:
        from libs.core.config import get_settings
        s = get_settings()
        keys = {
            "MASSIVE_API_KEY":  bool(s.massive_api_key),
            "FMP_API_KEY":      bool(s.fmp_api_key),
            "OPENFIGI_API_KEY": bool(s.openfigi_api_key),
            "SEC_USER_AGENT":   bool(os.environ.get("SEC_USER_AGENT")),
        }
    except Exception as e:
        print(f"    WARNING: get_settings() failed ({e}); falling back to env-only check")
        keys = {
            "MASSIVE_API_KEY":  bool(os.environ.get("MASSIVE_API_KEY")),
            "FMP_API_KEY":      bool(os.environ.get("FMP_API_KEY")),
            "OPENFIGI_API_KEY": bool(os.environ.get("OPENFIGI_API_KEY")),
            "SEC_USER_AGENT":   bool(os.environ.get("SEC_USER_AGENT")),
        }
    for k, present in keys.items():
        status = "SET" if present else "NOT SET"
        critical = " (REQUIRED for seed)" if k in ("MASSIVE_API_KEY", "FMP_API_KEY") else ""
        print(f"    {k:20s}: {status}{critical}")
    return keys


def universe_summary(check_all: bool):
    """Print universe size summary."""
    print()
    print(f"[2/4] Scanner Research Universe — {len(UNIVERSE)} tickers")
    if check_all:
        sample_to_use = UNIVERSE
        print(f"    Mode: --check-all (will probe all {len(UNIVERSE)} tickers)")
    else:
        sample_to_use = SAMPLE_TICKERS
        print(f"    Mode: default ({len(SAMPLE_TICKERS)} sample tickers, use --check-all for full)")
    print(f"    Universe (first 10): {', '.join(UNIVERSE[:10])}, ...")
    print(f"    Sample to probe: {', '.join(sample_to_use)}")
    return sample_to_use


async def probe_polygon(sample: list[str]) -> tuple[bool, str]:
    """Tiny Polygon smoke: one ticker, one day's bar. Read-only."""
    from libs.core.config import get_settings
    if not get_settings().massive_api_key:
        return False, "MASSIVE_API_KEY not set — skipping Polygon probe"
    try:
        from libs.adapters.massive_adapter import MassiveAdapter
        from datetime import date, timedelta
        adapter = MassiveAdapter()
        # Tiny window — last 5 calendar days, only first sample ticker
        ticker = sample[0]
        end_d = date.today()
        start_d = end_d - timedelta(days=5)
        bars = await adapter.get_eod_bars(ticker, start_d.isoformat(), end_d.isoformat())
        n = len(bars) if bars else 0
        return True, f"Polygon OK — {ticker} returned {n} bar(s) for last 5 days"
    except Exception as e:
        return False, f"Polygon ERROR: {type(e).__name__}: {str(e)[:100]}"


async def probe_fmp(sample: list[str]) -> tuple[bool, str]:
    """Tiny FMP smoke: one ticker's profile. Read-only."""
    from libs.core.config import get_settings
    if not get_settings().fmp_api_key:
        return False, "FMP_API_KEY not set — skipping FMP probe"
    try:
        from libs.adapters.fmp_adapter import FMPAdapter
        adapter = FMPAdapter()
        ticker = sample[0]
        profile = await adapter.get_profile(ticker)
        if profile and isinstance(profile, dict):
            company = profile.get("companyName") or profile.get("name") or "(unknown)"
            return True, f"FMP OK — {ticker} profile resolved (company: {company[:40]})"
        return False, f"FMP returned empty/invalid profile for {ticker}"
    except Exception as e:
        return False, f"FMP ERROR: {type(e).__name__}: {str(e)[:100]}"


async def probe_each_universe_ticker_polygon(tickers: list[str]) -> dict:
    """Probe each ticker — only used with --check-all. Still read-only."""
    from libs.core.config import get_settings
    if not get_settings().massive_api_key:
        return {"skipped": True, "reason": "MASSIVE_API_KEY not set"}
    from libs.adapters.massive_adapter import MassiveAdapter
    from datetime import date, timedelta
    adapter = MassiveAdapter()
    end_d = date.today()
    start_d = end_d - timedelta(days=15)
    succeeded, failed = [], []
    for tkr in tickers:
        try:
            bars = await adapter.get_eod_bars(tkr, start_d.isoformat(), end_d.isoformat())
            if bars and len(bars) > 0:
                succeeded.append(tkr)
            else:
                failed.append((tkr, "0 bars"))
        except Exception as e:
            failed.append((tkr, type(e).__name__))
    return {"succeeded": succeeded, "failed": failed}


async def main_async(args):
    print_banner()
    keys = check_keys()
    sample = universe_summary(args.check_all)

    print()
    print("[3/4] Provider connectivity probe")
    if args.skip_api:
        print("    SKIPPED (--skip-api). No external API calls made.")
        polygon_ok = keys["MASSIVE_API_KEY"]
        fmp_ok = keys["FMP_API_KEY"]
    else:
        if args.check_all:
            print(f"    Probing all {len(sample)} tickers via Polygon (read-only)...")
            res = await probe_each_universe_ticker_polygon(sample)
            if res.get("skipped"):
                print(f"    SKIPPED: {res.get('reason')}")
                polygon_ok = False
            else:
                print(f"    Polygon all-tickers: succeeded={len(res['succeeded'])}, failed={len(res['failed'])}")
                if res["failed"]:
                    print(f"    Failed tickers: {res['failed'][:10]}")
                polygon_ok = len(res["failed"]) == 0
            # Tiny FMP probe still
            fmp_ok, fmp_msg = await probe_fmp(sample)
            print(f"    {fmp_msg}")
        else:
            polygon_ok, p_msg = await probe_polygon(sample)
            print(f"    {p_msg}")
            fmp_ok, f_msg = await probe_fmp(sample)
            print(f"    {f_msg}")

    print()
    print("[4/4] Readiness summary")
    print(f"    Universe size              : {len(UNIVERSE)} tickers")
    print(f"    Polygon key (MASSIVE_API_KEY): {'SET' if keys['MASSIVE_API_KEY'] else 'NOT SET'}")
    print(f"    FMP key                    : {'SET' if keys['FMP_API_KEY'] else 'NOT SET'}")
    print(f"    Polygon reachable          : {'YES' if polygon_ok else 'NO/SKIPPED'}")
    print(f"    FMP reachable              : {'YES' if fmp_ok else 'NO/SKIPPED'}")
    print(f"    DB writes performed        : NONE")
    print(f"    Cloud Run jobs created     : NONE")
    print(f"    Scheduler changes          : NONE")
    print(f"    Production deploy          : NONE")

    print()
    print("=" * 78)
    critical_ok = keys["MASSIVE_API_KEY"] and keys["FMP_API_KEY"]
    if critical_ok and (polygon_ok and fmp_ok or args.skip_api):
        print("  RESULT: keys present, providers reachable (or skipped). Acceptance")
        print("  criteria items 1-2 (key presence) and partial 3-4 (sample probe)")
        print("  satisfied. Production seed remains DEFERRED — see")
        print("  docs/scanner-research-universe-production-plan.md Section 8 for")
        print("  the full checklist and required user sign-off.")
        exit_code = 0
    else:
        print("  RESULT: at least one critical check failed. See output above.")
        exit_code = 1
    print("=" * 78)
    print()
    return exit_code


def main():
    parser = argparse.ArgumentParser(description="Scanner universe provider readiness dry-run")
    parser.add_argument("--skip-api", action="store_true",
                        help="Skip all external API calls. Only check env vars.")
    parser.add_argument("--check-all", action="store_true",
                        help="Probe all 36 universe tickers via Polygon (read-only). "
                             "Use only when explicitly preparing for production seed.")
    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
