"""Immutable execution instructions and lifecycle audit events."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import OrderType, TimeInForce
from trading_bot.domain._validation import normalize_utc, require_positive_decimal


@dataclass(frozen=True, slots=True)
class ExecutionInstruction:
    """Broker-independent details needed to construct an order request."""

    order_type: OrderType
    time_in_force: TimeInForce
    created_at: datetime
    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type must be an OrderType")
        if not isinstance(self.time_in_force, TimeInForce):
            raise TypeError("time_in_force must be a TimeInForce")
        object.__setattr__(
            self, "created_at", normalize_utc(self.created_at, "created_at")
        )
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit orders require a limit_price")
            require_positive_decimal(self.limit_price, "limit_price")
        elif self.limit_price is not None:
            raise ValueError("market orders must not have a limit_price")


class OrderEventType(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


_FILL_EVENTS = {OrderEventType.PARTIALLY_FILLED, OrderEventType.FILLED}


@dataclass(frozen=True, slots=True)
class OrderEvent:
    """A lightweight immutable record of a successful lifecycle transition."""

    event_id: UUID
    order_id: UUID
    event_type: OrderEventType
    occurred_at: datetime
    fill_id: UUID | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, UUID) or not isinstance(self.order_id, UUID):
            raise TypeError("event_id and order_id must be UUIDs")
        if not isinstance(self.event_type, OrderEventType):
            raise TypeError("event_type must be an OrderEventType")
        object.__setattr__(
            self, "occurred_at", normalize_utc(self.occurred_at, "occurred_at")
        )
        if self.event_type in _FILL_EVENTS:
            if not isinstance(self.fill_id, UUID):
                raise ValueError("fill events require a fill_id")
        elif self.fill_id is not None:
            raise ValueError("non-fill events must not contain a fill_id")
        if self.event_type is OrderEventType.REJECTED:
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("rejection events require a nonblank reason")
        elif self.event_type is OrderEventType.CANCELED:
            if self.reason is not None and (
                not isinstance(self.reason, str) or not self.reason.strip()
            ):
                raise ValueError("cancellation reason must be nonblank when supplied")
        elif self.reason is not None:
            raise ValueError("this event type must not contain a reason")
