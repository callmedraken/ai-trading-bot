"""Immutable public ledger models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.domain._validation import normalize_utc, require_decimal


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """A point-in-time valuation of a paper-trading account."""

    timestamp: datetime
    cash: Decimal
    positions_market_value: Decimal
    equity: Decimal
    buying_power: Decimal
    realized_profit_loss: Decimal
    unrealized_profit_loss: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", normalize_utc(self.timestamp, "timestamp")
        )
        for field_name in (
            "cash",
            "positions_market_value",
            "equity",
            "buying_power",
            "realized_profit_loss",
            "unrealized_profit_loss",
        ):
            require_decimal(getattr(self, field_name), field_name)
        if self.cash < Decimal("0"):
            raise ValueError("cash cannot be negative")
        if self.positions_market_value < Decimal("0"):
            raise ValueError("positions_market_value cannot be negative")
        if self.equity != self.cash + self.positions_market_value:
            raise ValueError("equity must equal cash plus positions_market_value")
        if self.buying_power != self.cash:
            raise ValueError("buying_power must equal cash while margin is prohibited")
