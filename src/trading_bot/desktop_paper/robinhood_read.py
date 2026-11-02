"""Strict observation models, separate from simulated-paper financial authority."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from trading_bot.robinhood_mcp.account_resolution import RobinhoodAgenticAccountResolver
from trading_bot.robinhood_mcp.models import RobinhoodQuoteData
from trading_bot.robinhood_mcp.parsing import parse_equity_quotes_response


class ObservationError(ValueError):
    """Sanitized current-product observation rejection."""


def utc(value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ObservationError("OBSERVATION_UTC_REQUIRED")
    return value.astimezone(UTC)


def decimal_value(value: object) -> Decimal:
    if (
        not isinstance(value, (str, Decimal))
        or (isinstance(value, str) and not value)
        or len(str(value)) > 128
    ):
        raise ObservationError("OBSERVATION_DECIMAL_INVALID")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ObservationError("OBSERVATION_DECIMAL_INVALID") from None
    if not result.is_finite() or abs(result.as_tuple().exponent) > 100:
        raise ObservationError("OBSERVATION_DECIMAL_INVALID")
    return result


def text(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or value != value.strip()
        or any(ord(c) < 33 or ord(c) > 126 for c in value)
    ):
        raise ObservationError("OBSERVATION_TEXT_INVALID")
    return value


def symbol(value: object) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,15}", value) is None
    ):
        raise ObservationError("OBSERVATION_SYMBOL_INVALID")
    return value


def data(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), Mapping):
        raise ObservationError("OBSERVATION_DATA_INVALID")
    return payload["data"]


def commitment(material: object) -> str:
    """Versioned semantic decimal/UTC projection; no raw provider bytes."""

    def scalar(value: object) -> str:
        if isinstance(value, Decimal):
            # No normalize()/ambient Decimal context dependency.
            if value == 0:
                return "0"
            rendered = format(value, "f")
            return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
        if isinstance(value, datetime):
            return utc(value).isoformat()
        raise TypeError("unsupported commitment value")

    return hashlib.sha256(
        json.dumps(
            ["p5b-observation/v1", material],
            default=scalar,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class AgenticAccountIdentity:
    account_number: str = field(repr=False)
    observed_account_count: int
    eligible_account_count: int = 1

    def __post_init__(self) -> None:
        text(self.account_number)
        if (
            type(self.observed_account_count) is not int
            or not 1 <= self.observed_account_count <= 100
            or type(self.eligible_account_count) is not int
            or self.eligible_account_count != 1
        ):
            raise ObservationError("ACCOUNT_COUNTS_INVALID")

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.account_number.encode("utf-8")).hexdigest()


def resolve_account(payload: Mapping[str, object]) -> AgenticAccountIdentity:
    accounts = data(payload).get("accounts")
    if not isinstance(accounts, list) or not 1 <= len(accounts) <= 100:
        raise ObservationError("ACCOUNT_COLLECTION_INVALID")
    numbers = []
    for account in accounts:
        if not isinstance(account, Mapping):
            raise ObservationError("ACCOUNT_RECORD_INVALID")
        numbers.append(text(account.get("account_number")))
    if len(numbers) != len(set(numbers)):
        raise ObservationError("ACCOUNT_DUPLICATE")
    try:
        number = RobinhoodAgenticAccountResolver(lambda: payload).resolve()
    except Exception:
        raise ObservationError("ACCOUNT_SELECTION_FAILED") from None
    return AgenticAccountIdentity(number, len(accounts))


@dataclass(frozen=True, slots=True)
class PortfolioObservation:
    total_value: Decimal
    cash: Decimal
    equity_value: Decimal
    buying_power: Decimal
    unleveraged_buying_power: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.currency != "USD":
            raise ObservationError("PORTFOLIO_CURRENCY_INVALID")
        for value in (
            self.total_value,
            self.cash,
            self.equity_value,
            self.buying_power,
            self.unleveraged_buying_power,
        ):
            if type(value) is not Decimal:
                raise ObservationError("PORTFOLIO_DECIMAL_REQUIRED")
            decimal_value(value)

    @property
    def digest(self) -> str:
        return commitment(
            [
                self.currency,
                self.total_value,
                self.cash,
                self.equity_value,
                self.buying_power,
                self.unleveraged_buying_power,
            ]
        )


def parse_portfolio(payload: object) -> PortfolioObservation:
    root = data(payload)
    power = root.get("buying_power")
    if (
        not isinstance(power, Mapping)
        or root.get("currency") != "USD"
        or power.get("display_currency") != "USD"
    ):
        raise ObservationError("PORTFOLIO_REQUIRED_FIELDS_INVALID")
    return PortfolioObservation(
        *(
            decimal_value(value)
            for value in (
                root.get("total_value"),
                root.get("cash"),
                root.get("equity_value"),
                power.get("buying_power"),
                power.get("unleveraged_buying_power"),
            )
        )
    )


@dataclass(frozen=True, slots=True)
class EquityPositionObservation:
    symbol: str
    quantity: Decimal
    shares_available_for_sells: Decimal
    average_buy_price: Decimal | None
    position_type: str

    def __post_init__(self) -> None:
        symbol(self.symbol)
        for value in (self.quantity, self.shares_available_for_sells):
            if type(value) is not Decimal:
                raise ObservationError("POSITION_DECIMAL_REQUIRED")
            decimal_value(value)
        if (
            self.position_type not in {"long", "short", "empty"}
            or self.shares_available_for_sells < 0
            or (self.position_type == "long" and self.quantity <= 0)
            or (self.position_type == "short" and self.quantity >= 0)
            or (self.position_type == "empty" and self.quantity != 0)
        ):
            raise ObservationError("POSITION_QUANTITY_INVALID")
        if self.quantity >= 0 and self.shares_available_for_sells > self.quantity:
            raise ObservationError("POSITION_SELLABLE_INVALID")
        if self.average_buy_price is not None and (
            type(self.average_buy_price) is not Decimal
            or decimal_value(self.average_buy_price) < 0
        ):
            raise ObservationError("POSITION_COST_INVALID")


def parse_position(value: object) -> EquityPositionObservation:
    if not isinstance(value, Mapping):
        raise ObservationError("POSITION_INVALID")
    cost = value.get("average_buy_price")
    return EquityPositionObservation(
        symbol(value.get("symbol")),
        decimal_value(value.get("quantity")),
        decimal_value(value.get("shares_available_for_sells")),
        None if cost is None else decimal_value(cost),
        text(value.get("type")),
    )


def parse_spy_quote(payload: Mapping[str, object]) -> RobinhoodQuoteData:
    # The public historical parser and current-trade selector remain unchanged.
    parsed = parse_equity_quotes_response(payload)
    if (
        len(parsed.results) != 1
        or parsed.results[0] is None
        or parsed.results[0].quote is None
    ):
        raise ObservationError("SPY_QUOTE_MISSING")
    quote = parsed.results[0].quote
    validate_spy_quote(quote)
    return quote


def validate_spy_quote(quote: RobinhoodQuoteData) -> None:
    """Validate public typed quotes too, so direct snapshot construction is strict."""
    if (
        str(quote.symbol) != "SPY"
        or quote.state != "active"
        or quote.has_traded is not True
    ):
        raise ObservationError("SPY_QUOTE_INVALID")
    for price in (
        quote.adjusted_previous_close,
        quote.ask_price,
        quote.bid_price,
        quote.last_trade_price,
        quote.previous_close,
    ):
        if price <= 0:
            raise ObservationError("SPY_PRICE_INVALID")
    if (
        quote.last_non_reg_trade_price is not None
        and quote.last_non_reg_trade_price <= 0
    ):
        raise ObservationError("SPY_PRICE_INVALID")
    # Public parser rejects naive timestamps and normalizes aware ones to UTC.
    for stamp in (
        quote.venue_ask_time,
        quote.venue_bid_time,
        quote.venue_last_trade_time,
    ):
        utc(stamp)
    if quote.venue_last_non_reg_trade_time is not None:
        utc(quote.venue_last_non_reg_trade_time)


@dataclass(frozen=True, slots=True)
class EquityOrderObservation:
    order_id: str = field(repr=False)
    symbol: str
    side: str
    state: str
    quantity: Decimal | None
    cumulative_quantity: Decimal
    created_at: datetime
    placed_agent: str = "agentic"
    bot_attributable: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        text(self.order_id)
        symbol(self.symbol)
        text(self.state)
        utc(self.created_at)
        if self.side not in {"buy", "sell"} or self.placed_agent != "agentic":
            raise ObservationError("ORDER_FILTER_INVALID")
        if type(self.cumulative_quantity) is not Decimal:
            raise ObservationError("ORDER_CUMULATIVE_QUANTITY_REQUIRED")
        for value in (self.quantity, self.cumulative_quantity):
            if value is not None and (
                type(value) is not Decimal or decimal_value(value) < 0
            ):
                raise ObservationError("ORDER_QUANTITY_INVALID")
        if self.quantity is not None and self.cumulative_quantity > self.quantity:
            raise ObservationError("ORDER_FILL_INVALID")


def parse_order(value: object) -> EquityOrderObservation:
    if not isinstance(value, Mapping) or "quantity" not in value:
        raise ObservationError("ORDER_INVALID")
    try:
        stamp = datetime.fromisoformat(text(value.get("created_at")))
    except ValueError:
        raise ObservationError("ORDER_TIMESTAMP_INVALID") from None
    quantity = value.get("quantity")
    return EquityOrderObservation(
        text(value.get("id")),
        symbol(value.get("symbol")),
        text(value.get("side")),
        text(value.get("state")),
        None if quantity is None else decimal_value(quantity),
        decimal_value(value.get("cumulative_quantity")),
        utc(stamp),
        text(value.get("placed_agent")),
    )
