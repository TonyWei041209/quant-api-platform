"""Market taxonomy — broad categories + subcategories for peer-group scanning.

Two layers:

  * BROAD_CATEGORIES (Sector-level): GICS-aligned with a few extras the
    scanner-research workflow cares about (ETFs / ADRs / Small Caps /
    High Volatility / Crypto-related / China ADR / User Custom).

  * SUBCATEGORIES (Theme-level): concrete narrative buckets the user
    scans against (AI Infrastructure / Semiconductors / Memory Chips /
    Data Centers / Cloud Software / Cybersecurity / Robotics /
    Space-Rocket / Defense / Nuclear-Uranium / Crypto Miners /
    Quantum / EV / Battery / Biotech / GLP-1 Weight-loss / Digital
    Health / Fintech / Retail-Meme Attention / Streaming-Media /
    Travel-Airlines / Banks / Brokers-Exchanges / Energy Exploration /
    Solar-Renewables).

Resolution rules:

  1. STATIC theme map — high-confidence ticker-to-tag mapping for
     well-known tickers (NVDA → AI Infrastructure; RKLB → Space-Rocket;
     IREN → Crypto Miners; etc.). This is the canonical source for
     stable, well-known tickers and is used by tests.
  2. PROVIDER profile — when a ticker is missing from the static map,
     classify_by_provider_profile() reads FMP profile fields
     (sector / industry / isEtf / country / etc.) to derive a
     best-effort tag set.
  3. Merge strategy — merge_taxonomy_tags() combines both sources.
     Static wins for the broad-category slot; subcategory tags from
     both sources are deduplicated.

Deterministic. Read-only. Pure data — no DB, no network, no Trading 212
write endpoint, no order/execution objects, no scraping.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# ---- Broad categories ----

BROAD_CATEGORIES: tuple[str, ...] = (
    "Technology",
    "Healthcare",
    "Financials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Industrials",
    "Materials",
    "Utilities",
    "Real Estate",
    "Communication Services",
    "ETFs",
    "ADRs",
    "Small Caps",
    "High Volatility",
    "Crypto-related",
    "China ADR",
    "User Custom",
)


# ---- Subcategories ----

SUBCATEGORIES: tuple[str, ...] = (
    "AI Infrastructure",
    "Semiconductors",
    "Memory Chips",
    "Data Centers",
    "Cloud Software",
    "Cybersecurity",
    "Robotics",
    "Space-Rocket",
    "Defense",
    "Nuclear-Uranium",
    "Crypto Miners",
    "Quantum",
    "EV",
    "Battery",
    "Biotech",
    "GLP-1 Weight-loss",
    "Digital Health",
    "Fintech",
    "Retail-Meme Attention",
    "Streaming-Media",
    "Travel-Airlines",
    "Banks",
    "Brokers-Exchanges",
    "Energy Exploration",
    "Solar-Renewables",
)


# ---- Static theme map (ticker → broad + subcategory tags) ----
#
# Keep this conservative. Only well-known, stable tickers belong here.
# Anything else is resolved by the provider-profile path so we don't
# create false-confidence tags for unfamiliar names.

_STATIC_THEMES: dict[str, dict] = {
    # AI / semis / memory
    "NVDA": {"broad": "Technology", "subs": ("Semiconductors", "AI Infrastructure", "Data Centers")},
    "AMD":  {"broad": "Technology", "subs": ("Semiconductors", "AI Infrastructure")},
    "AVGO": {"broad": "Technology", "subs": ("Semiconductors", "AI Infrastructure")},
    "TSM":  {"broad": "Technology", "subs": ("Semiconductors",)},
    "INTC": {"broad": "Technology", "subs": ("Semiconductors",)},
    "MU":   {"broad": "Technology", "subs": ("Semiconductors", "Memory Chips")},
    "WDC":  {"broad": "Technology", "subs": ("Semiconductors", "Memory Chips")},
    "SNDK": {"broad": "Technology", "subs": ("Semiconductors", "Memory Chips")},
    "AAOI": {"broad": "Technology", "subs": ("Semiconductors", "Data Centers")},
    "MRVL": {"broad": "Technology", "subs": ("Semiconductors", "Data Centers")},
    "NBIS": {"broad": "Technology", "subs": ("Cloud Software", "AI Infrastructure")},
    "CRWV": {"broad": "Technology", "subs": ("Cloud Software", "AI Infrastructure", "Data Centers")},
    "ORCL": {"broad": "Technology", "subs": ("Cloud Software", "Data Centers")},
    "PLTR": {"broad": "Technology", "subs": ("Cloud Software", "AI Infrastructure")},
    "ADBE": {"broad": "Technology", "subs": ("Cloud Software",)},
    "DUOL": {"broad": "Technology", "subs": ("Cloud Software",)},
    # Mega-cap tech
    "AAPL": {"broad": "Technology", "subs": ()},
    "MSFT": {"broad": "Technology", "subs": ("Cloud Software", "AI Infrastructure")},
    "GOOGL": {"broad": "Communication Services", "subs": ("AI Infrastructure",)},
    "META": {"broad": "Communication Services", "subs": ("AI Infrastructure",)},
    "AMZN": {"broad": "Consumer Discretionary", "subs": ("Cloud Software", "Data Centers")},
    "NFLX": {"broad": "Communication Services", "subs": ("Streaming-Media",)},
    # EV / autos
    "TSLA": {"broad": "Consumer Discretionary", "subs": ("EV", "Battery", "AI Infrastructure")},
    "RIVN": {"broad": "Consumer Discretionary", "subs": ("EV", "Battery")},
    "LCID": {"broad": "Consumer Discretionary", "subs": ("EV", "Battery")},
    "NIO":  {"broad": "Consumer Discretionary", "subs": ("EV", "China ADR")},
    "XPEV": {"broad": "Consumer Discretionary", "subs": ("EV", "China ADR")},
    "F":    {"broad": "Consumer Discretionary", "subs": ()},
    "GM":   {"broad": "Consumer Discretionary", "subs": ()},
    # Space / industrials / defense
    "RKLB": {"broad": "Industrials", "subs": ("Space-Rocket",)},
    "BA":   {"broad": "Industrials", "subs": ("Defense",)},
    # Healthcare / digital health
    "HIMS": {"broad": "Healthcare", "subs": ("Digital Health",)},
    "TEM":  {"broad": "Healthcare", "subs": ("AI Infrastructure", "Digital Health")},
    # Financials / fintech / brokers
    "SOFI": {"broad": "Financials", "subs": ("Fintech",)},
    "COIN": {"broad": "Financials", "subs": ("Brokers-Exchanges", "Crypto-related")},
    "JPM":  {"broad": "Financials", "subs": ("Banks",)},
    "BAC":  {"broad": "Financials", "subs": ("Banks",)},
    "GS":   {"broad": "Financials", "subs": ("Banks", "Brokers-Exchanges")},
    # Energy
    "XOM":  {"broad": "Energy", "subs": ("Energy Exploration",)},
    "CVX":  {"broad": "Energy", "subs": ("Energy Exploration",)},
    "OXY":  {"broad": "Energy", "subs": ("Energy Exploration",)},
    # Communications / consumer
    "DIS":  {"broad": "Communication Services", "subs": ("Streaming-Media",)},
    "UBER": {"broad": "Industrials", "subs": ()},
    "SIRI": {"broad": "Communication Services", "subs": ("Streaming-Media",)},
    "AMC":  {"broad": "Communication Services", "subs": ("Retail-Meme Attention",)},
    "NOK":  {"broad": "Communication Services", "subs": ("ADRs",)},
    # Crypto-related miners / data centers
    "IREN": {"broad": "Industrials", "subs": ("Crypto Miners", "Data Centers")},
    # Misc external mirror tickers seen in the user's order history
    "VACQ": {"broad": "Industrials", "subs": ()},
    "CRCL": {"broad": "Financials", "subs": ("Crypto-related",)},
    "OAC":  {"broad": "Industrials", "subs": ()},
    "AXTI": {"broad": "Technology", "subs": ("Semiconductors",)},
    "IPOE": {"broad": "Financials", "subs": ()},
    "PRSO": {"broad": "Technology", "subs": ("Semiconductors",)},
    "SMSN": {"broad": "Technology", "subs": ("Semiconductors", "Memory Chips", "ADRs")},
    # ETFs
    "SPY":  {"broad": "ETFs", "subs": ()},
    "QQQ":  {"broad": "ETFs", "subs": ()},
    "IWM":  {"broad": "ETFs", "subs": ("Small Caps",)},
}


# ---- Provider-profile heuristics ----
#
# These are conservative substring matches over FMP profile fields.
# They populate broad categories from the GICS sector if static doesn't
# have an entry, and bolt on subcategory tags when the industry matches
# a clear theme.

_SECTOR_TO_BROAD: dict[str, str] = {
    "Technology": "Technology",
    "Healthcare": "Healthcare",
    "Financial Services": "Financials",
    "Financials": "Financials",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Consumer Staples": "Consumer Staples",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Basic Materials": "Materials",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication Services",
}

_INDUSTRY_SUBCATEGORY_RULES: list[tuple[str, str]] = [
    # (industry substring lowercased, subcategory)
    ("semiconductor",        "Semiconductors"),
    ("memory",               "Memory Chips"),
    ("software—infrastruct", "Cloud Software"),
    ("software—application", "Cloud Software"),
    ("information technology service", "Cloud Software"),
    ("internet retail",      "Retail-Meme Attention"),
    ("specialty retail",     "Retail-Meme Attention"),
    ("entertainment",        "Streaming-Media"),
    ("airline",              "Travel-Airlines"),
    ("banks—",               "Banks"),
    ("capital markets",      "Brokers-Exchanges"),
    ("biotechnology",        "Biotech"),
    ("drug manufacturers",   "Biotech"),
    ("health information",   "Digital Health"),
    ("medical devices",      "Digital Health"),
    ("solar",                "Solar-Renewables"),
    ("oil & gas e&p",        "Energy Exploration"),
    ("uranium",              "Nuclear-Uranium"),
    ("aerospace & defense",  "Defense"),
    ("auto manufacturers",   "EV"),
]


def normalize_symbol(symbol: str | None) -> str | None:
    """Return the upper-case symbol, stripping common suffix noise.

    Trading 212 broker tickers like ``MU_US_EQ`` reduce to ``MU``;
    GDR/ADR symbols like ``SMSN.IL`` keep the dot suffix because the
    provider needs it. Empty / None returns None.
    """
    if not symbol:
        return None
    cleaned = symbol.strip().upper()
    if not cleaned:
        return None
    # Strip T212 broker_ticker tail (X_US_EQ → X). Do not strip a single
    # dot suffix since FMP/Yahoo sometimes need .IL / .L / .HK to resolve.
    parts = re.match(r"^([A-Z0-9.\-]+?)(?:_[A-Z0-9]+)*$", cleaned)
    if parts:
        head = parts.group(1)
        # If we stripped underscores entirely, return only the first
        # token (e.g., MU_US_EQ → MU). Otherwise keep the head.
        return head.split("_")[0] if "_" in cleaned and "_" not in head else head
    return cleaned


def classify_by_static_theme(symbol: str) -> dict | None:
    """Return the static theme entry for ``symbol`` or None."""
    norm = normalize_symbol(symbol)
    if not norm:
        return None
    return _STATIC_THEMES.get(norm)


def classify_by_provider_profile(profile: dict | None) -> dict:
    """Derive {broad, subs} from an FMP profile dict.

    Returns ``{"broad": str | None, "subs": tuple[str, ...]}`` — never
    raises and never returns None so callers don't need null guards.
    """
    if not isinstance(profile, dict) or not profile:
        return {"broad": None, "subs": ()}

    sector = (profile.get("sector") or "").strip()
    industry = (profile.get("industry") or "").strip()
    is_etf = bool(profile.get("isEtf") or (profile.get("type", "").lower() == "etf"))
    country = (profile.get("country") or "").strip().upper()

    broad: str | None = None
    if is_etf:
        broad = "ETFs"
    elif sector in _SECTOR_TO_BROAD:
        broad = _SECTOR_TO_BROAD[sector]

    subs: list[str] = []
    industry_low = industry.lower()
    for needle, tag in _INDUSTRY_SUBCATEGORY_RULES:
        if needle in industry_low and tag not in subs:
            subs.append(tag)

    # ADR / China-ADR layering — country code is conservative;
    # 'CN' or 'HK' both qualify as China ADR.
    if country in ("CN", "HK", "TW") and broad and broad != "ETFs":
        subs.append("China ADR")
    elif country and country != "US" and not is_etf:
        subs.append("ADRs")

    return {"broad": broad, "subs": tuple(dict.fromkeys(subs))}


@dataclass(frozen=True)
class TaxonomyTags:
    broad: str | None
    subs: tuple[str, ...]
    source: str  # "static" | "provider" | "merged" | "unknown"


def merge_taxonomy_tags(
    static_entry: dict | None,
    provider_entry: dict | None,
) -> TaxonomyTags:
    """Combine static + provider tags. Static wins for broad slot.

    De-duplicates subcategory tags while preserving order
    (static subs first, then provider subs).
    """
    if static_entry and provider_entry:
        broad = static_entry.get("broad") or provider_entry.get("broad")
        subs = []
        for s in (*(static_entry.get("subs") or ()),
                  *(provider_entry.get("subs") or ())):
            if s and s not in subs:
                subs.append(s)
        return TaxonomyTags(broad=broad, subs=tuple(subs), source="merged")
    if static_entry:
        return TaxonomyTags(
            broad=static_entry.get("broad"),
            subs=tuple(static_entry.get("subs") or ()),
            source="static",
        )
    if provider_entry:
        return TaxonomyTags(
            broad=provider_entry.get("broad"),
            subs=tuple(provider_entry.get("subs") or ()),
            source="provider",
        )
    return TaxonomyTags(broad=None, subs=(), source="unknown")


def filter_universe_by_categories(
    items: Iterable[dict],
    broad_categories: Iterable[str] | None = None,
    subcategories: Iterable[str] | None = None,
) -> list[dict]:
    """Filter ``items`` (each must have ``taxonomy_tags`` dict) by
    broad and/or subcategory match. None means "no filter for this
    dimension". Returns a new list.
    """
    if broad_categories is None and subcategories is None:
        return list(items)

    bset = {b for b in (broad_categories or []) if b}
    sset = {s for s in (subcategories or []) if s}
    out: list[dict] = []
    for it in items:
        tags = it.get("taxonomy_tags") or {}
        broad = tags.get("broad")
        subs = set(tags.get("subs") or ())
        if bset and (broad not in bset):
            continue
        if sset and not (subs & sset):
            continue
        out.append(it)
    return out
