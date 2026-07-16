"""Long-only position model."""

from dataclasses import dataclass
from decimal import Decimal

from trading_bot.domain._validation import require_positive_decimal
from trading_bot.domain.market import Symbol


@dataclass(frozen=True, slots=True)
class Position:
    """An immutable long-only position."""

    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        require_positive_decimal(self.quantity, "quantity")
        require_positive_decimal(self.average_cost, "average_cost")

    def market_value(self, current_price: Decimal) -> Decimal:
        """Calculate the position's value at a positive current price."""
        require_positive_decimal(current_price, "current_price")
        return self.quantity * current_price

    def unrealized_profit_loss(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized profit or loss at a positive current price."""
        return self.market_value(current_price) - (self.quantity * self.average_cost)
