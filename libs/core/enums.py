"""Shared enumerations."""
from __future__ import annotations

from enum import StrEnum


class AssetType(StrEnum):
    COMMON_STOCK = "common_stock"
    ETF = "etf"
    ADR = "adr"
    PREFERRED = "preferred"
    REIT = "reit"
    UNKNOWN = "unknown"


class IdType(StrEnum):
    TICKER = "ticker"
    CIK = "cik"
    FIGI = "figi"
    COMPOSITE_FIGI = "composite_figi"
    SHARE_CLASS_FIGI = "share_class_figi"
    ISIN = "isin"


class ActionType(StrEnum):
    SPLIT = "split"
    CASH_DIVIDEND = "cash_dividend"
    TICKER_CHANGE = "ticker_change"
    NAME_CHANGE = "name_change"
    DELISTING = "delisting"


class StatementScope(StrEnum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    TTM = "ttm"


class StatementType(StrEnum):
    INCOME = "income"
    BALANCE = "balance"
    CASHFLOW = "cashflow"
    RATIOS = "ratios"


class EventTimeCode(StrEnum):
    BMO = "BMO"
    AMC = "AMC"
    DURING = "DURING"
    UNKNOWN = "UNKNOWN"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(StrEnum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class IntentStatus(StrEnum):
    PENDING = "pending"
    DRAFTED = "drafted"
    CANCELLED = "cancelled"


class DraftStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
