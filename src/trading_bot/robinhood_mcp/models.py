"""Immutable typed values for the observed Robinhood MCP schemas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_bot.domain import OrderSide, Symbol
from trading_bot.domain._validation import normalize_utc, require_decimal


class RobinhoodMcpSchemaError(ValueError):
    """A Robinhood MCP payload does not match the reviewed schema contract."""


def _nonnegative(value: Decimal, field_name: str) -> Decimal:
    require_decimal(value, field_name)
    if not value.is_finite() or value < Decimal("0"):
        raise ValueError(f"{field_name} must be a finite nonnegative Decimal")
    return value


def _positive(value: Decimal, field_name: str) -> Decimal:
    _nonnegative(value, field_name)
    if value == Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class RobinhoodQuoteData:
    """Complete quote_data shape shared by review and equity quote tools."""

    symbol: Symbol
    adjusted_previous_close: Decimal
    ask_price: Decimal
    bid_price: Decimal
    has_traded: bool
    last_non_reg_trade_price: Decimal | None
    last_trade_price: Decimal
    previous_close: Decimal
    previous_close_date: str | None
    state: str
    venue_ask_time: datetime
    venue_bid_time: datetime
    venue_last_non_reg_trade_time: datetime | None
    venue_last_trade_time: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        _nonnegative(self.adjusted_previous_close, "adjusted_previous_close")
        _nonnegative(self.ask_price, "ask_price")
        _nonnegative(self.bid_price, "bid_price")
        if not isinstance(self.has_traded, bool):
            raise TypeError("has_traded must be a bool")
        if self.last_non_reg_trade_price is not None:
            _nonnegative(
                self.last_non_reg_trade_price,
                "last_non_reg_trade_price",
            )
        _nonnegative(self.last_trade_price, "last_trade_price")
        _nonnegative(self.previous_close, "previous_close")
        if self.previous_close_date is not None and (
            not isinstance(self.previous_close_date, str)
            or not self.previous_close_date.strip()
        ):
            raise ValueError("previous_close_date must be nonblank when supplied")
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("state must be nonblank")
        for field_name in (
            "venue_ask_time",
            "venue_bid_time",
            "venue_last_trade_time",
        ):
            object.__setattr__(
                self,
                field_name,
                normalize_utc(getattr(self, field_name), field_name),
            )
        if self.venue_last_non_reg_trade_time is not None:
            object.__setattr__(
                self,
                "venue_last_non_reg_trade_time",
                normalize_utc(
                    self.venue_last_non_reg_trade_time,
                    "venue_last_non_reg_trade_time",
                ),
            )

    def current_trade_candidate(self) -> tuple[Decimal, datetime]:
        """Return the newer regular/non-regular trade without claiming freshness."""

        regular = (self.last_trade_price, self.venue_last_trade_time)
        if (
            self.last_non_reg_trade_price is None
            or self.venue_last_non_reg_trade_time is None
            or self.venue_last_non_reg_trade_time <= self.venue_last_trade_time
        ):
            return regular
        return self.last_non_reg_trade_price, self.venue_last_non_reg_trade_time

    def require_paper_fill_reference(
        self,
        side: OrderSide,
    ) -> tuple[Decimal, datetime]:
        """Return the side-specific live book value required by paper fills."""

        if not isinstance(side, OrderSide):
            raise TypeError("side must be an OrderSide")
        if not self.has_traded:
            raise ValueError("instrument has never traded")
        if self.state != "active":
            raise ValueError("instrument is not active")
        if side is OrderSide.BUY:
            return _positive(self.ask_price, "ask_price"), self.venue_ask_time
        return _positive(self.bid_price, "bid_price"), self.venue_bid_time


@dataclass(frozen=True, slots=True)
class RobinhoodOfficialClose:
    symbol: Symbol
    date: str | None
    interpolated: bool | None
    price: Decimal | None
    source: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if self.price is not None:
            _nonnegative(self.price, "price")
        if self.interpolated is not None and not isinstance(self.interpolated, bool):
            raise TypeError("interpolated must be bool or None")


@dataclass(frozen=True, slots=True)
class RobinhoodEquityQuoteResult:
    quote: RobinhoodQuoteData | None
    close: RobinhoodOfficialClose | None

    def __post_init__(self) -> None:
        if self.quote is not None and not isinstance(self.quote, RobinhoodQuoteData):
            raise TypeError("quote must be RobinhoodQuoteData or None")
        if self.close is not None and not isinstance(
            self.close, RobinhoodOfficialClose
        ):
            raise TypeError("close must be RobinhoodOfficialClose or None")
        if (
            self.quote is not None
            and self.close is not None
            and self.quote.symbol != self.close.symbol
        ):
            raise ValueError("quote and close symbols must match")


@dataclass(frozen=True, slots=True)
class RobinhoodEquityQuotesResponse:
    results: tuple[RobinhoodEquityQuoteResult | None, ...]
    closes_error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.results, tuple):
            raise TypeError("results must be a tuple")
        if self.closes_error is not None and not isinstance(self.closes_error, str):
            raise TypeError("closes_error must be a string or None")


@dataclass(frozen=True, slots=True)
class RobinhoodDollarBasedAmount:
    amount: Decimal
    currency_code: str

    def __post_init__(self) -> None:
        _nonnegative(self.amount, "amount")
        if not isinstance(self.currency_code, str) or not self.currency_code:
            raise ValueError("currency_code must be nonblank")


@dataclass(frozen=True, slots=True)
class RobinhoodEquityExecution:
    fees: Decimal
    execution_id: str
    price: Decimal
    quantity: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        _nonnegative(self.fees, "fees")
        _positive(self.price, "price")
        _positive(self.quantity, "quantity")
        if not isinstance(self.execution_id, str) or not self.execution_id:
            raise ValueError("execution_id must be nonblank")
        object.__setattr__(
            self, "timestamp", normalize_utc(self.timestamp, "timestamp")
        )


@dataclass(frozen=True, slots=True)
class RobinhoodEquityOrder:
    order_id: str
    symbol: Symbol
    side: OrderSide
    state: str
    placed_agent: str
    created_at: datetime
    last_transaction_at: datetime | None
    market_hours: str
    time_in_force: str
    order_type: str
    trigger: str
    quantity: Decimal | None
    cumulative_quantity: Decimal
    average_price: Decimal | None
    price: Decimal | None
    stop_price: Decimal | None
    fees: Decimal
    ref_id: str | None
    reject_reason: str | None
    instrument_id: str
    dollar_based_amount: RobinhoodDollarBasedAmount | None
    executions: tuple[RobinhoodEquityExecution, ...]

    def __post_init__(self) -> None:
        for value, name in (
            (self.order_id, "order_id"),
            (self.state, "state"),
            (self.placed_agent, "placed_agent"),
            (self.market_hours, "market_hours"),
            (self.time_in_force, "time_in_force"),
            (self.order_type, "order_type"),
            (self.trigger, "trigger"),
            (self.instrument_id, "instrument_id"),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        object.__setattr__(
            self, "created_at", normalize_utc(self.created_at, "created_at")
        )
        if self.last_transaction_at is not None:
            object.__setattr__(
                self,
                "last_transaction_at",
                normalize_utc(self.last_transaction_at, "last_transaction_at"),
            )
        if self.quantity is not None:
            _nonnegative(self.quantity, "quantity")
        _nonnegative(self.cumulative_quantity, "cumulative_quantity")
        if self.average_price is not None:
            _positive(self.average_price, "average_price")
        if self.price is not None:
            _positive(self.price, "price")
        if self.stop_price is not None:
            _positive(self.stop_price, "stop_price")
        _nonnegative(self.fees, "fees")
        if self.ref_id is not None and not isinstance(self.ref_id, str):
            raise TypeError("ref_id must be a string or None")
        if self.reject_reason is not None and not isinstance(self.reject_reason, str):
            raise TypeError("reject_reason must be a string or None")
        if self.dollar_based_amount is not None and not isinstance(
            self.dollar_based_amount, RobinhoodDollarBasedAmount
        ):
            raise TypeError("dollar_based_amount has invalid type")
        if not isinstance(self.executions, tuple) or not all(
            isinstance(item, RobinhoodEquityExecution) for item in self.executions
        ):
            raise TypeError("executions must contain RobinhoodEquityExecution values")


@dataclass(frozen=True, slots=True)
class RobinhoodEquityOrdersPage:
    orders: tuple[RobinhoodEquityOrder | None, ...]
    next_cursor: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.orders, tuple):
            raise TypeError("orders must be a tuple")
        if self.next_cursor is not None and not isinstance(self.next_cursor, str):
            raise TypeError("next_cursor must be a string or None")
