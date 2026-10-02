"""Parsers for the reviewed Robinhood MCP read/review response schemas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation

from trading_bot.domain import OrderSide, OrderType, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.review_paper import (
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    canonical_order_checks,
)
from trading_bot.robinhood_mcp.models import (
    RobinhoodDollarBasedAmount,
    RobinhoodEquityExecution,
    RobinhoodEquityOrder,
    RobinhoodEquityOrdersPage,
    RobinhoodEquityQuoteResult,
    RobinhoodEquityQuotesResponse,
    RobinhoodMcpSchemaError,
    RobinhoodOfficialClose,
    RobinhoodQuoteData,
)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RobinhoodMcpSchemaError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise RobinhoodMcpSchemaError(f"{field_name} must be an array")
    return value


def _required_str(
    mapping: Mapping[str, object],
    key: str,
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise RobinhoodMcpSchemaError(f"{key} must be a nonblank string")
    return value


def _optional_str(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RobinhoodMcpSchemaError(f"{key} must be a string or null")
    return value


def _decimal_text(value: object, field_name: str) -> Decimal:
    if not isinstance(value, str) or not value:
        raise RobinhoodMcpSchemaError(f"{field_name} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise RobinhoodMcpSchemaError(
            f"{field_name} must be a decimal string"
        ) from error
    if not parsed.is_finite():
        raise RobinhoodMcpSchemaError(f"{field_name} must be finite")
    return parsed


def _optional_decimal_text(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal_text(value, field_name)


def _timestamp_text(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RobinhoodMcpSchemaError(f"{field_name} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise RobinhoodMcpSchemaError(
            f"{field_name} must be an ISO timestamp"
        ) from error
    try:
        return normalize_utc(parsed, field_name)
    except (TypeError, ValueError) as error:
        raise RobinhoodMcpSchemaError(str(error)) from error


def _optional_timestamp_text(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    return _timestamp_text(value, field_name)


def _bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise RobinhoodMcpSchemaError(f"{field_name} must be a bool")
    return value


def _side(value: object) -> OrderSide:
    if value == "buy":
        return OrderSide.BUY
    if value == "sell":
        return OrderSide.SELL
    raise RobinhoodMcpSchemaError("side must be buy or sell")


def _review_order_type(value: object) -> OrderType:
    if value == "market":
        return OrderType.MARKET
    if value == "limit":
        return OrderType.LIMIT
    raise RobinhoodMcpSchemaError("review order type is unsupported")


def parse_quote_data(value: object) -> RobinhoodQuoteData:
    data = _mapping(value, "quote_data")
    symbol = Symbol(_required_str(data, "symbol"))
    has_traded = _bool(data.get("has_traded"), "has_traded")
    return RobinhoodQuoteData(
        symbol=symbol,
        adjusted_previous_close=_decimal_text(
            data.get("adjusted_previous_close"),
            "adjusted_previous_close",
        ),
        ask_price=_decimal_text(data.get("ask_price"), "ask_price"),
        bid_price=_decimal_text(data.get("bid_price"), "bid_price"),
        has_traded=has_traded,
        last_non_reg_trade_price=_optional_decimal_text(
            data.get("last_non_reg_trade_price"),
            "last_non_reg_trade_price",
        ),
        last_trade_price=_decimal_text(
            data.get("last_trade_price"),
            "last_trade_price",
        ),
        previous_close=_decimal_text(data.get("previous_close"), "previous_close"),
        previous_close_date=_optional_str(data, "previous_close_date"),
        state=_required_str(data, "state"),
        venue_ask_time=_timestamp_text(data.get("venue_ask_time"), "venue_ask_time"),
        venue_bid_time=_timestamp_text(data.get("venue_bid_time"), "venue_bid_time"),
        venue_last_non_reg_trade_time=_optional_timestamp_text(
            data.get("venue_last_non_reg_trade_time"),
            "venue_last_non_reg_trade_time",
        ),
        venue_last_trade_time=_timestamp_text(
            data.get("venue_last_trade_time"),
            "venue_last_trade_time",
        ),
    )


def parse_review_equity_order_response(
    payload: Mapping[str, object],
    *,
    received_at: datetime,
) -> RobinhoodEquityOrderReview:
    """Parse one review response into the paper ledger's reviewed model."""

    root = _mapping(payload, "review response")
    data = _mapping(root.get("data"), "data")
    quote = parse_quote_data(data.get("quote_data"))
    quantity = _decimal_text(data.get("quantity"), "quantity")
    order_checks = _mapping(data.get("order_checks"), "order_checks")
    generic_quote = quote.require_paper_fill_reference(_side(data.get("side")))
    del generic_quote
    review_quote = RobinhoodReviewQuote(
        symbol=quote.symbol,
        adjusted_previous_close=quote.adjusted_previous_close,
        ask_price=quote.ask_price,
        bid_price=quote.bid_price,
        has_traded=quote.has_traded,
        last_non_reg_trade_price=quote.last_non_reg_trade_price,
        last_trade_price=quote.last_trade_price,
        previous_close=quote.previous_close,
        previous_close_date=quote.previous_close_date,
        state=quote.state,
        venue_ask_time=quote.venue_ask_time,
        venue_bid_time=quote.venue_bid_time,
        venue_last_non_reg_trade_time=quote.venue_last_non_reg_trade_time,
        venue_last_trade_time=quote.venue_last_trade_time,
    )
    symbol = Symbol(_required_str(data, "symbol"))
    if symbol != quote.symbol:
        raise RobinhoodMcpSchemaError("review symbol disagrees with quote symbol")
    return RobinhoodEquityOrderReview(
        symbol=symbol,
        side=_side(data.get("side")),
        order_type=_review_order_type(data.get("type")),
        quantity=quantity,
        quote=review_quote,
        order_checks_json=canonical_order_checks(order_checks),
        reviewed_at=received_at,
        market_data_disclosure=_optional_str(data, "market_data_disclosure"),
    )


def _parse_close(value: object) -> RobinhoodOfficialClose:
    data = _mapping(value, "close")
    interpolated = data.get("interpolated")
    if interpolated is not None and not isinstance(interpolated, bool):
        raise RobinhoodMcpSchemaError("interpolated must be bool or null")
    return RobinhoodOfficialClose(
        symbol=Symbol(_required_str(data, "symbol")),
        date=_optional_str(data, "date"),
        interpolated=interpolated,
        price=_optional_decimal_text(data.get("price"), "price"),
        source=_optional_str(data, "source"),
    )


def parse_equity_quotes_response(
    payload: Mapping[str, object],
) -> RobinhoodEquityQuotesResponse:
    root = _mapping(payload, "equity quotes response")
    data = _mapping(root.get("data"), "data")
    raw_results = data.get("results")
    results: list[RobinhoodEquityQuoteResult | None] = []
    if raw_results is not None:
        for raw in _sequence(raw_results, "results"):
            if raw is None:
                results.append(None)
                continue
            result = _mapping(raw, "quote result")
            raw_quote = result.get("quote")
            raw_close = result.get("close")
            quote = None if raw_quote is None else parse_quote_data(raw_quote)
            close = None if raw_close is None else _parse_close(raw_close)
            try:
                results.append(RobinhoodEquityQuoteResult(quote=quote, close=close))
            except (TypeError, ValueError) as error:
                raise RobinhoodMcpSchemaError(str(error)) from error
    return RobinhoodEquityQuotesResponse(
        results=tuple(results),
        closes_error=_optional_str(data, "closes_error"),
    )


def _parse_execution(value: object) -> RobinhoodEquityExecution:
    data = _mapping(value, "execution")
    return RobinhoodEquityExecution(
        fees=_decimal_text(data.get("fees"), "execution.fees"),
        execution_id=_required_str(data, "id"),
        price=_decimal_text(data.get("price"), "execution.price"),
        quantity=_decimal_text(data.get("quantity"), "execution.quantity"),
        timestamp=_timestamp_text(data.get("timestamp"), "execution.timestamp"),
    )


def _parse_dollar_amount(value: object) -> RobinhoodDollarBasedAmount:
    data = _mapping(value, "dollar_based_amount")
    return RobinhoodDollarBasedAmount(
        amount=_decimal_text(data.get("amount"), "dollar_based_amount.amount"),
        currency_code=_required_str(data, "currency_code"),
    )


def _parse_order(value: object) -> RobinhoodEquityOrder:
    data = _mapping(value, "order")
    raw_executions = data.get("executions")
    executions = (
        ()
        if raw_executions is None
        else tuple(
            _parse_execution(item)
            for item in _sequence(raw_executions, "executions")
        )
    )
    dollar_amount = data.get("dollar_based_amount")
    return RobinhoodEquityOrder(
        order_id=_required_str(data, "id"),
        symbol=Symbol(_required_str(data, "symbol")),
        side=_side(data.get("side")),
        state=_required_str(data, "state"),
        placed_agent=_required_str(data, "placed_agent"),
        created_at=_timestamp_text(data.get("created_at"), "created_at"),
        last_transaction_at=_optional_timestamp_text(
            data.get("last_transaction_at"),
            "last_transaction_at",
        ),
        market_hours=_required_str(data, "market_hours"),
        time_in_force=_required_str(data, "time_in_force"),
        order_type=_required_str(data, "type"),
        trigger=_required_str(data, "trigger"),
        quantity=_optional_decimal_text(data.get("quantity"), "quantity"),
        cumulative_quantity=_decimal_text(
            data.get("cumulative_quantity"),
            "cumulative_quantity",
        ),
        average_price=_optional_decimal_text(data.get("average_price"), "average_price"),
        price=_optional_decimal_text(data.get("price"), "price"),
        stop_price=_optional_decimal_text(data.get("stop_price"), "stop_price"),
        fees=_decimal_text(data.get("fees"), "fees"),
        ref_id=_optional_str(data, "ref_id"),
        reject_reason=_optional_str(data, "reject_reason"),
        instrument_id=_required_str(data, "instrument_id"),
        dollar_based_amount=(
            None if dollar_amount is None else _parse_dollar_amount(dollar_amount)
        ),
        executions=executions,
    )


def parse_equity_orders_response(
    payload: Mapping[str, object],
) -> RobinhoodEquityOrdersPage:
    root = _mapping(payload, "equity orders response")
    data = _mapping(root.get("data"), "data")
    raw_orders = data.get("orders")
    orders: list[RobinhoodEquityOrder | None] = []
    if raw_orders is not None:
        for raw in _sequence(raw_orders, "orders"):
            orders.append(None if raw is None else _parse_order(raw))
    return RobinhoodEquityOrdersPage(
        orders=tuple(orders),
        next_cursor=_optional_str(data, "next"),
    )
