"""Allowlisted read/review adapter for Robinhood MCP paper mode."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.domain._validation import normalize_utc
from trading_bot.review_paper import ReviewPaperIntent, RobinhoodEquityOrderReview
from trading_bot.robinhood_mcp.models import (
    RobinhoodEquityOrdersPage,
    RobinhoodEquityQuotesResponse,
)
from trading_bot.robinhood_mcp.parsing import (
    parse_equity_orders_response,
    parse_equity_quotes_response,
    parse_review_equity_order_response,
)


class RobinhoodReviewReadTransport(Protocol):
    """Minimal transport surface intentionally excluding order mutation tools."""

    def review_equity_order(
        self,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def get_equity_quotes(
        self,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def get_equity_orders(
        self,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class RobinhoodReviewReadAdapter:
    """Typed facade over the three reviewed Robinhood MCP operations."""

    def __init__(self, transport: RobinhoodReviewReadTransport) -> None:
        self._transport = transport

    def review_market_order(
        self,
        *,
        account_number: str,
        intent: ReviewPaperIntent,
        received_at: datetime,
    ) -> RobinhoodEquityOrderReview:
        account = _account_number(account_number)
        if not isinstance(intent, ReviewPaperIntent):
            raise TypeError("intent must be ReviewPaperIntent")
        if intent.order_type is not OrderType.MARKET:
            raise ValueError("paper review adapter currently supports MARKET only")
        time_in_force = {
            TimeInForce.DAY: "gfd",
            TimeInForce.GOOD_TIL_CANCELED: "gtc",
        }[intent.time_in_force]
        arguments: dict[str, object] = {
            "account_number": account,
            "market_hours": "regular_hours",
            "quantity": _decimal_text(intent.approved_quantity),
            "side": "buy" if intent.side is OrderSide.BUY else "sell",
            "symbol": str(intent.symbol),
            "time_in_force": time_in_force,
            "type": "market",
        }
        response = self._transport.review_equity_order(arguments)
        review = parse_review_equity_order_response(
            response,
            received_at=normalize_utc(received_at, "received_at"),
        )
        if (
            review.symbol != intent.symbol
            or review.side is not intent.side
            or review.order_type is not intent.order_type
            or review.quantity != intent.approved_quantity
        ):
            raise ValueError("Robinhood review does not echo risk-approved order")
        return review

    def equity_quotes(
        self,
        symbols: Sequence[Symbol],
    ) -> RobinhoodEquityQuotesResponse:
        if not isinstance(symbols, Sequence) or isinstance(
            symbols, (str, bytes, bytearray)
        ):
            raise TypeError("symbols must be a sequence")
        if not symbols:
            raise ValueError("at least one symbol is required")
        if len(symbols) > 20:
            raise ValueError("at most 20 symbols are allowed per valuation request")
        normalized: list[str] = []
        for symbol in symbols:
            if not isinstance(symbol, Symbol):
                raise TypeError("symbols must contain Symbol values")
            normalized.append(str(symbol))
        response = self._transport.get_equity_quotes({"symbols": normalized})
        return parse_equity_quotes_response(response)

    def agentic_equity_orders(
        self,
        *,
        account_number: str,
        created_at_gte: datetime | None = None,
        cursor: str | None = None,
        symbol: Symbol | None = None,
        state: str | None = None,
    ) -> RobinhoodEquityOrdersPage:
        arguments: dict[str, object] = {
            "account_number": _account_number(account_number),
            "placed_agent": "agentic",
        }
        if created_at_gte is not None:
            arguments["created_at_gte"] = normalize_utc(
                created_at_gte,
                "created_at_gte",
            ).isoformat()
        if cursor is not None:
            if not isinstance(cursor, str) or not cursor:
                raise ValueError("cursor must be nonblank when supplied")
            arguments["cursor"] = cursor
        if symbol is not None:
            if not isinstance(symbol, Symbol):
                raise TypeError("symbol must be a Symbol")
            arguments["symbol"] = str(symbol)
        if state is not None:
            if not isinstance(state, str) or not state:
                raise ValueError("state must be nonblank when supplied")
            arguments["state"] = state
        response = self._transport.get_equity_orders(arguments)
        return parse_equity_orders_response(response)


def _account_number(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
    ):
        raise ValueError("account_number must be exact nonblank text")
    return value


def _decimal_text(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("quantity must be a finite Decimal")
    return format(value, "f")
