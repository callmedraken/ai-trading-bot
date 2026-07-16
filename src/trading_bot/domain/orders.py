"""Order request, fill, and state models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID, uuid4

from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)
from trading_bot.domain.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from trading_bot.domain.market import Symbol


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """An immutable proposal to place a paper order."""

    order_id: UUID
    symbol: Symbol
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    time_in_force: TimeInForce
    submitted_at: datetime
    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, UUID):
            raise TypeError("order_id must be a UUID")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type must be an OrderType")
        if not isinstance(self.time_in_force, TimeInForce):
            raise TypeError("time_in_force must be a TimeInForce")
        require_positive_decimal(self.quantity, "quantity")
        object.__setattr__(
            self, "submitted_at", normalize_utc(self.submitted_at, "submitted_at")
        )
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit orders require a limit_price")
            require_positive_decimal(self.limit_price, "limit_price")
        elif self.limit_price is not None:
            raise ValueError("market orders must not have a limit_price")

    @classmethod
    def create(
        cls,
        *,
        symbol: Symbol,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        time_in_force: TimeInForce,
        submitted_at: datetime,
        limit_price: Decimal | None = None,
        order_id: UUID | None = None,
    ) -> Self:
        """Create a request, generating its identifier when omitted."""
        return cls(
            order_id=order_id or uuid4(),
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            time_in_force=time_in_force,
            submitted_at=submitted_at,
            limit_price=limit_price,
        )


@dataclass(frozen=True, slots=True)
class OrderFill:
    """An immutable record of a simulated order fill."""

    fill_id: UUID
    order_id: UUID
    symbol: Symbol
    side: OrderSide
    quantity: Decimal
    price: Decimal
    commission: Decimal
    filled_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.fill_id, UUID) or not isinstance(self.order_id, UUID):
            raise TypeError("fill_id and order_id must be UUIDs")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        require_positive_decimal(self.quantity, "quantity")
        require_positive_decimal(self.price, "price")
        require_decimal(self.commission, "commission")
        if self.commission < Decimal("0"):
            raise ValueError("commission must be zero or greater")
        object.__setattr__(
            self, "filled_at", normalize_utc(self.filled_at, "filled_at")
        )

    @property
    def gross_amount(self) -> Decimal:
        return self.quantity * self.price

    @property
    def net_cash_effect(self) -> Decimal:
        if self.side is OrderSide.BUY:
            return -(self.gross_amount + self.commission)
        return self.gross_amount - self.commission


@dataclass(frozen=True, slots=True)
class Order:
    """The immutable current state of an order."""

    request: OrderRequest
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, OrderRequest):
            raise TypeError("request must be an OrderRequest")
        if not isinstance(self.status, OrderStatus):
            raise TypeError("status must be an OrderStatus")
        require_decimal(self.filled_quantity, "filled_quantity")
        if self.filled_quantity < Decimal("0"):
            raise ValueError("filled_quantity cannot be negative")
        if self.filled_quantity > self.request.quantity:
            raise ValueError("filled_quantity cannot exceed requested quantity")
        if self.average_fill_price is not None:
            require_positive_decimal(self.average_fill_price, "average_fill_price")

        full = self.filled_quantity == self.request.quantity
        if self.status is OrderStatus.FILLED and not full:
            raise ValueError("filled orders must have their full quantity filled")
        if self.status is OrderStatus.PARTIALLY_FILLED and not (
            Decimal("0") < self.filled_quantity < self.request.quantity
        ):
            raise ValueError("partially filled orders require a partial quantity")
        if (
            self.status
            in {
                OrderStatus.PENDING,
                OrderStatus.SUBMITTED,
                OrderStatus.CANCELED,
                OrderStatus.REJECTED,
            }
            and full
        ):
            raise ValueError(
                f"{self.status.value} orders cannot claim the full quantity"
            )
        if self.status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}:
            if self.average_fill_price is None:
                raise ValueError("filled orders require an average_fill_price")

        if self.status is OrderStatus.REJECTED:
            if (
                not isinstance(self.rejection_reason, str)
                or not self.rejection_reason.strip()
            ):
                raise ValueError("rejected orders require a nonblank rejection_reason")
        elif self.rejection_reason is not None:
            raise ValueError("non-rejected orders must not have a rejection_reason")

    @property
    def remaining_quantity(self) -> Decimal:
        return self.request.quantity - self.filled_quantity
