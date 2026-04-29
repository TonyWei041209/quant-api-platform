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
   ║    - Optionally makes read-only provider calls                        ║
   ║    - Prints a readiness report to stdout                              ║
   ╚══════════════════════════════════════════════════════════════════════╝
================================================================================

Usage:
    # Default — small smoke (1 ticker each provider)
    python scripts/check_scanner_universe_provider_readiness.py

    # No external calls
    python scripts/check_scanner_universe_provider_readiness.py --skip-api

    # Full 36-ticker coverage probe — paces against Polygon free tier (5/min)
    # Default delays: --polygon-delay-seconds=13, --fmp-delay-seconds=1.0
    # Estimated runtime: ~8-9 minutes for full --check-all
    python scripts/check_scanner_universe_provider_readiness.py --check-all

    # Speed up if you've confirmed a paid Polygon tier is in use:
    python scripts/check_scanner_universe_provider_readiness.py --check-all \
      --polygon-delay-seconds=0.3

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

# Acceptance criterion #4 — minimum bars required to count a ticker as
# coverage-OK (one trading year ≈ 252 bars).
MIN_BARS_REQUIRED = 252

# Default Polygon date window for full coverage check: 18 months ≈ 540 days.
# Wide enough that 252+ bars is comfortably available even after weekends/
# holidays. 420 calendar days would be the bare minimum.
COVERAGE_WINDOW_DAYS = 540


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


def universe_summary(check_all: bool, polygon_delay: float, fmp_delay: float):
    """Print universe size summary."""
    print()
    print(f"[2/4] Scanner Research Universe — {len(UNIVERSE)} tickers")
    if check_all:
        sample_to_use = UNIVERSE
        eta_min = (len(UNIVERSE) * polygon_delay + len(UNIVERSE) * fmp_delay) / 60
        print(f"    Mode: --check-all (probes all {len(UNIVERSE)} tickers)")
        print(f"    Polygon pacing: {polygon_delay:.1f}s between calls (Polygon free tier = 5 req/min)")
        print(f"    FMP pacing    : {fmp_delay:.1f}s between calls")
        print(f"    Estimated runtime: ~{eta_min:.1f} minutes")
    else:
        sample_to_use = SAMPLE_TICKERS
        print(f"    Mode: default ({len(SAMPLE_TICKERS)} sample tickers, use --check-all for full)")
    print(f"    Universe (first 10): {', '.join(UNIVERSE[:10])}, ...")
    return sample_to_use


# ---------------------------------------------------------------------------
# Small smoke probes (default mode — 1 ticker each)
# ---------------------------------------------------------------------------

async def probe_polygon(sample: list[str]) -> tuple[bool, str]:
    """Tiny Polygon smoke: one ticker, ~5-day window. Read-only."""
    from libs.core.config import get_settings
    if not get_settings().massive_api_key:
        return False, "MASSIVE_API_KEY not set — skipping Polygon probe"
    try:
        from libs.adapters.massive_adapter import MassiveAdapter
        from datetime import date, timedelta
        adapter = MassiveAdapter()
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


# ---------------------------------------------------------------------------
# Full coverage probes (--check-all mode — all 36 tickers each, paced)
# ---------------------------------------------------------------------------

async def probe_all_polygon_with_pacing(tickers: list[str], delay_seconds: float) -> dict:
    """Probe ALL tickers via Polygon with pacing for free-tier rate limit.

    For each ticker, fetches a wide-enough window to verify coverage criterion
    #4 (>= 252 trading days available). Records bar count, first/last trade
    dates, and any error. Sleeps `delay_seconds` between calls.

    Returns a dict per ticker with: ok / bars_count / first_trade_date /
    last_trade_date / error. Plus aggregate `succeeded` / `coverage_failed` /
    `errored` lists.
    """
    from libs.core.config import get_settings
    if not get_settings().massive_api_key:
        return {"skipped": True, "reason": "MASSIVE_API_KEY not set"}

    from libs.adapters.massive_adapter import MassiveAdapter
    from datetime import date, timedelta

    adapter = MassiveAdapter()
    end_d = date.today()
    start_d = end_d - timedelta(days=COVERAGE_WINDOW_DAYS)

    per_ticker: dict[str, dict] = {}
    succeeded, coverage_failed, errored = [], [], []

    for i, tkr in enumerate(tickers):
        if i > 0 and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        try:
            bars = await adapter.get_eod_bars(tkr, start_d.isoformat(), end_d.isoformat())
            n = len(bars) if bars else 0
            first_d = last_d = None
            if bars:
                # Polygon raw bar fields use 't' (epoch ms) — convert at most
                # for display. Defensive: try several typical fields.
                def _bar_date(b):
                    if not isinstance(b, dict):
                        return None
                    if "t" in b:
                        try:
                            from datetime import datetime, timezone
                            return datetime.fromtimestamp(b["t"]/1000, tz=timezone.utc).date().isoformat()
                        except Exception:
                            return None
                    return b.get("date") or b.get("trade_date")
                first_d = _bar_date(bars[0])
                last_d = _bar_date(bars[-1])
            entry = {
                "ok": n >= MIN_BARS_REQUIRED,
                "bars_count": n,
                "first_trade_date": first_d,
                "last_trade_date": last_d,
                "error": None,
            }
            per_ticker[tkr] = entry
            if entry["ok"]:
                succeeded.append(tkr)
                print(f"    {tkr:6s} OK    bars={n:5d}  {first_d} -> {last_d}")
            else:
                coverage_failed.append((tkr, n))
                print(f"    {tkr:6s} SHORT bars={n:5d}  (need >= {MIN_BARS_REQUIRED})")
        except Exception as e:
            entry = {
                "ok": False,
                "bars_count": 0,
                "first_trade_date": None,
                "last_trade_date": None,
                "error": f"{type(e).__name__}: {str(e)[:120]}",
            }
            per_ticker[tkr] = entry
            errored.append((tkr, type(e).__name__))
            print(f"    {tkr:6s} ERROR {type(e).__name__}: {str(e)[:80]}")

    return {
        "per_ticker": per_ticker,
        "succeeded": succeeded,
        "coverage_failed": coverage_failed,
        "errored": errored,
    }


async def probe_all_fmp_with_pacing(tickers: list[str], delay_seconds: float) -> dict:
    """Probe ALL tickers via FMP get_profile with pacing.

    Verifies criterion #3 (FMP profile resolves for all 36 tickers). Captures
    company name and exchange when available. Sleeps `delay_seconds` between
    calls.
    """
    from libs.core.config import get_settings
    if not get_settings().fmp_api_key:
        return {"skipped": True, "reason": "FMP_API_KEY not set"}

    from libs.adapters.fmp_adapter import FMPAdapter
    adapter = FMPAdapter()

    per_ticker: dict[str, dict] = {}
    succeeded, errored = [], []

    for i, tkr in enumerate(tickers):
        if i > 0 and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        try:
            profile = await adapter.get_profile(tkr)
            if profile and isinstance(profile, dict):
                company = profile.get("companyName") or profile.get("name")
                exch = profile.get("exchange") or profile.get("exchangeShortName")
                entry = {
                    "ok": True,
                    "company_name": company,
                    "exchange": exch,
                    "error": None,
                }
                per_ticker[tkr] = entry
                succeeded.append(tkr)
                disp = (company[:30] if company else "?")
                print(f"    {tkr:6s} OK    {disp:30s}  exch={exch}")
            else:
                entry = {
                    "ok": False,
                    "company_name": None,
                    "exchange": None,
                    "error": "empty_or_invalid_profile",
                }
                per_ticker[tkr] = entry
                errored.append((tkr, "empty_or_invalid_profile"))
                print(f"    {tkr:6s} EMPTY (no profile resolved)")
        except Exception as e:
            entry = {
                "ok": False,
                "company_name": None,
                "exchange": None,
                "error": f"{type(e).__name__}: {str(e)[:120]}",
            }
            per_ticker[tkr] = entry
            errored.append((tkr, type(e).__name__))
            print(f"    {tkr:6s} ERROR {type(e).__name__}: {str(e)[:80]}")

    return {"per_ticker": per_ticker, "succeeded": succeeded, "errored": errored}


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

async def main_async(args):
    print_banner()
    keys = check_keys()
    sample = universe_summary(args.check_all, args.polygon_delay_seconds, args.fmp_delay_seconds)

    polygon_full = None
    fmp_full = None

    print()
    print("[3/4] Provider connectivity probe")
    if args.skip_api:
        print("    SKIPPED (--skip-api). No external API calls made.")
        polygon_ok = keys["MASSIVE_API_KEY"]
        fmp_ok = keys["FMP_API_KEY"]
    elif args.check_all:
        print(f"    Polygon: probing all {len(sample)} tickers with {args.polygon_delay_seconds:.1f}s pacing...")
        polygon_full = await probe_all_polygon_with_pacing(sample, args.polygon_delay_seconds)
        if polygon_full.get("skipped"):
            print(f"    SKIPPED: {polygon_full.get('reason')}")
            polygon_ok = False
        else:
            polygon_ok = (
                len(polygon_full["errored"]) == 0
                and len(polygon_full["coverage_failed"]) == 0
            )
        print()
        print(f"    FMP: probing all {len(sample)} tickers with {args.fmp_delay_seconds:.1f}s pacing...")
        fmp_full = await probe_all_fmp_with_pacing(sample, args.fmp_delay_seconds)
        if fmp_full.get("skipped"):
            print(f"    SKIPPED: {fmp_full.get('reason')}")
            fmp_ok = False
        else:
            fmp_ok = len(fmp_full["errored"]) == 0
    else:
        polygon_ok, p_msg = await probe_polygon(sample)
        print(f"    {p_msg}")
        fmp_ok, f_msg = await probe_fmp(sample)
        print(f"    {f_msg}")

    # Summary
    print()
    print("[4/4] Readiness summary")
    print(f"    Universe size              : {len(UNIVERSE)} tickers")
    print(f"    Polygon key (MASSIVE_API_KEY): {'SET' if keys['MASSIVE_API_KEY'] else 'NOT SET'}")
    print(f"    FMP key                    : {'SET' if keys['FMP_API_KEY'] else 'NOT SET'}")
    print(f"    Polygon reachable          : {'YES' if polygon_ok else 'NO/SKIPPED'}")
    print(f"    FMP reachable              : {'YES' if fmp_ok else 'NO/SKIPPED'}")
    if polygon_full and not polygon_full.get("skipped"):
        s = len(polygon_full["succeeded"])
        c = len(polygon_full["coverage_failed"])
        e = len(polygon_full["errored"])
        print(f"    Polygon coverage           : succeeded={s}/{len(UNIVERSE)}  short={c}  errored={e}")
        if polygon_full["coverage_failed"]:
            print(f"    Coverage-short tickers     : {polygon_full['coverage_failed'][:10]}")
        if polygon_full["errored"]:
            print(f"    Errored tickers            : {polygon_full['errored'][:10]}")
    if fmp_full and not fmp_full.get("skipped"):
        s = len(fmp_full["succeeded"])
        e = len(fmp_full["errored"])
        print(f"    FMP profile coverage       : succeeded={s}/{len(UNIVERSE)}  errored={e}")
        if fmp_full["errored"]:
            print(f"    FMP errored tickers        : {fmp_full['errored'][:10]}")
    print(f"    DB writes performed        : NONE")
    print(f"    Cloud Run jobs created     : NONE")
    print(f"    Scheduler changes          : NONE")
    print(f"    Production deploy          : NONE")

    # Acceptance criteria PASS/FAIL block
    print()
    print("[Acceptance criteria readiness — see plan Section 8]")
    print(f"    #1 Polygon key reachable             : {'PASS' if (keys['MASSIVE_API_KEY'] and (polygon_ok or args.skip_api)) else 'FAIL'}")
    print(f"    #2 FMP key reachable                 : {'PASS' if (keys['FMP_API_KEY'] and (fmp_ok or args.skip_api)) else 'FAIL'}")
    if args.check_all:
        c3 = "PASS" if (fmp_full and not fmp_full.get("skipped") and len(fmp_full["errored"]) == 0) else "FAIL"
        c4 = "PASS" if (polygon_full and not polygon_full.get("skipped")
                       and len(polygon_full["errored"]) == 0
                       and len(polygon_full["coverage_failed"]) == 0) else "FAIL"
        print(f"    #3 FMP profile for all 36 tickers    : {c3}")
        print(f"    #4 Polygon >=252 bars for all 36     : {c4}")
    else:
        print(f"    #3 FMP profile for all 36 tickers    : NOT VERIFIED (run --check-all)")
        print(f"    #4 Polygon >=252 bars for all 36     : NOT VERIFIED (run --check-all)")

    print()
    print("=" * 78)
    critical_ok = keys["MASSIVE_API_KEY"] and keys["FMP_API_KEY"]
    if critical_ok and (polygon_ok and fmp_ok or args.skip_api):
        print("  RESULT: keys present, providers reachable (or skipped). Production")
        print("  seed remains DEFERRED — see")
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
                        help="Probe all 36 universe tickers via Polygon + FMP (read-only). "
                             "Use only when explicitly preparing for production seed.")
    parser.add_argument("--polygon-delay-seconds", type=float, default=13.0,
                        help="Seconds to sleep between Polygon calls. Default 13.0 "
                             "(safe under Polygon free-tier 5 req/min). Lower this if "
                             "you've confirmed a paid Polygon tier.")
    parser.add_argument("--fmp-delay-seconds", type=float, default=1.0,
                        help="Seconds to sleep between FMP calls. Default 1.0.")
    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
