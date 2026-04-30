"""Single source of truth for the Scanner Research Universe.

This list MUST stay in sync with:
- scripts/bootstrap_research_universe_dev.py (dev DB seed)
- scripts/check_scanner_universe_provider_readiness.py (dry-run readiness)
- docs/scanner-research-universe-production-plan.md (Section 2 table)

Changes to the universe must be made deliberately: production seed scripts
use this list, daily sync depends on it, and rollback SQL templates use the
same allowlist.

Categories are documented in docs/scanner-research-universe-production-plan.md
Section 2. Inclusion criteria: high liquidity, mid-or-large cap, US-listed,
T212-tradable. NO microcaps, NO OTC, NO penny stocks, NO derivatives.

This list is NOT a buy/sell recommendation. It is a research universe —
instruments worth scanning for further investigation.
"""
from __future__ import annotations

# 36 tickers — see docs/scanner-research-universe-production-plan.md Section 2
SCANNER_RESEARCH_UNIVERSE: tuple[str, ...] = (
    # AI / Semiconductor
    "NVDA", "AMD", "AVGO", "TSM", "INTC", "MU",
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "META", "AMZN",
    # EV / growth
    "TSLA", "RIVN", "LCID", "NIO", "XPEV",
    # Fintech
    "SOFI", "PLTR", "COIN",
    # Financials
    "JPM", "BAC", "GS",
    # Energy
    "XOM", "CVX", "OXY",
    # Communications / consumer
    "DIS", "NFLX", "UBER",
    # Auto (incumbent)
    "F", "GM",
    # Industrial
    "BA",
    # Communications / consumer (cont'd)
    "SIRI", "AMC",
    # ETFs
    "SPY", "QQQ", "IWM",
)


SCANNER_UNIVERSE_NAMES: dict[str, tuple[str, ...]] = {
    "scanner-research": SCANNER_RESEARCH_UNIVERSE,
}


# Tickers that already have full instrument + identifier + ticker_history rows
# in production. These succeeded in Phase B2 (4/36) and MUST NEVER be touched
# by the production bootstrap script — bootstrapping them would risk creating
# duplicate identifier rows or shadowing the existing primary identifier with
# bootstrap_prod-tagged rows. The bootstrap script computes its target list as
# SCANNER_RESEARCH_UNIVERSE - PROTECTED_TICKERS and verifies the count is 32.
PROTECTED_TICKERS: frozenset[str] = frozenset({"NVDA", "AAPL", "MSFT", "SPY"})


# ETF-classed tickers in the universe. Used by asset_type_for() to set the
# instrument.asset_type column correctly during bootstrap. Equity is the
# default for everything else.
ETF_TICKERS: frozenset[str] = frozenset({"SPY", "QQQ", "IWM"})


# Tickers that need production bootstrap (instrument + instrument_identifier +
# ticker_history scaffolding). Computed deterministically from the universe
# minus the protected set so the two stay in lock-step.
BOOTSTRAP_TARGET_TICKERS: tuple[str, ...] = tuple(
    t for t in SCANNER_RESEARCH_UNIVERSE if t not in PROTECTED_TICKERS
)


def asset_type_for(ticker: str) -> str:
    """Return the asset_type label ("ETF" or "EQUITY") for a ticker.

    Pure data lookup — no DB, no network. ETF set is intentionally tiny
    (SPY/QQQ/IWM) because the rest of the research universe is equity. Adding
    new ETFs requires updating ETF_TICKERS deliberately.
    """
    return "ETF" if ticker.upper() in ETF_TICKERS else "EQUITY"


def get_universe(name: str) -> tuple[str, ...]:
    """Resolve a named universe to its ticker list.

    Raises ValueError on unknown name. Names are intentionally kebab-case to
    match CLI flag conventions.
    """
    if name not in SCANNER_UNIVERSE_NAMES:
        raise ValueError(
            f"Unknown universe '{name}'. Known: {sorted(SCANNER_UNIVERSE_NAMES)}"
        )
    return SCANNER_UNIVERSE_NAMES[name]
