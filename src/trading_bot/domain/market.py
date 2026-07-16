"""Market identity and bar models."""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.domain._validation import normalize_utc, require_positive_decimal
from trading_bot.domain.enums import AssetType

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.-]+$")


@dataclass(frozen=True, slots=True)
class Symbol:
    """A normalized, immutable ticker symbol."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("symbol must be a string")
        normalized = self.value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        if len(normalized) > 10:
            raise ValueError("symbol must be 10 characters or fewer")
        if _SYMBOL_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "symbol may contain only letters, numbers, periods, and hyphens"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Asset:
    """A supported tradable asset."""

    symbol: Symbol
    asset_type: AssetType
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.asset_type, AssetType):
            raise ValueError("asset_type must be STOCK or ETF")
        if self.name is not None:
            if not isinstance(self.name, str):
                raise TypeError("name must be a string or None")
            if not self.name.strip():
                raise ValueError("name must not be blank")


@dataclass(frozen=True, slots=True)
class Bar:
    """An immutable OHLCV market bar with a UTC timestamp."""

    symbol: Symbol
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        object.__setattr__(
            self, "timestamp", normalize_utc(self.timestamp, "timestamp")
        )
        for field_name in ("open", "high", "low", "close"):
            require_positive_decimal(getattr(self, field_name), field_name)
        if not isinstance(self.volume, int) or isinstance(self.volume, bool):
            raise TypeError("volume must be an integer")
        if self.volume < 0:
            raise ValueError("volume must be zero or greater")
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("high must be at least open, low, and close")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be at most open, high, and close")
