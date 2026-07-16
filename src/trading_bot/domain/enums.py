"""Enumerations used by the trading domain."""

from enum import StrEnum


class AssetType(StrEnum):
    STOCK = "STOCK"
    ETF = "ETF"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class TimeInForce(StrEnum):
    DAY = "DAY"
    GOOD_TIL_CANCELED = "GOOD_TIL_CANCELED"
