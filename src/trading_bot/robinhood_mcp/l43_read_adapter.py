"""Robinhood payload adapter for the neutral L43 read contract."""

from __future__ import annotations

from collections.abc import Mapping

from trading_bot.desktop_paper.robinhood_read import parse_position, resolve_account
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
    L43DollarAmountFact,
    L43ExecutionFact,
    L43OrderFact,
    L43PositionFact,
    L43ReadPage,
)
from trading_bot.robinhood_mcp.models import RobinhoodEquityOrder
from trading_bot.robinhood_mcp.parsing import parse_equity_orders_response


class RobinhoodL43PreEffectReadAdapter:
    """Convert raw Robinhood read envelopes into provider-independent facts."""

    __slots__ = ("_read",)

    def __init__(self, read: object) -> None:
        if not all(
            callable(getattr(read, name, None))
            for name in ("get_accounts", "get_equity_positions", "get_equity_orders")
        ):
            raise TypeError("Robinhood read adapter requires explicit read methods")
        self._read = read

    def get_accounts(self) -> L43AccountIdentity:
        account = resolve_account(self._read.get_accounts())
        return L43AccountIdentity(account.account_number, account.fingerprint)

    def get_equity_positions(self, arguments: Mapping[str, object]) -> L43ReadPage:
        payload = self._read.get_equity_positions(dict(arguments))
        data = _data(payload, "positions")
        return L43ReadPage(
            rows=tuple(
                _position_fact(parse_position(row)) for row in data["positions"]
            ),
            next_cursor=_cursor(data),
        )

    def get_equity_orders(self, arguments: Mapping[str, object]) -> L43ReadPage:
        return _order_page(self._read, arguments)


class RobinhoodL43B2PreEffectReadAdapter:
    """Narrow B2 sibling of the accepted L43 normalization adapter.

    B2 needs only account and equity-order reads.  It intentionally has no
    position, quote, portfolio, review, or mutation surface while reusing the
    same strict order normalization and pagination checks as the accepted
    ``RobinhoodL43PreEffectReadAdapter``.
    """

    __slots__ = ("_read",)

    def __init__(self, read: object) -> None:
        if not all(
            callable(getattr(read, name, None))
            for name in ("get_accounts", "get_equity_orders")
        ):
            raise TypeError("B2 read adapter requires account/order read methods")
        self._read = read

    def get_accounts(self) -> L43AccountIdentity:
        account = resolve_account(self._read.get_accounts())
        return L43AccountIdentity(account.account_number, account.fingerprint)

    def get_equity_orders(self, arguments: Mapping[str, object]) -> L43ReadPage:
        return _order_page(self._read, arguments)


def _order_page(read: object, arguments: Mapping[str, object]) -> L43ReadPage:
    payload = read.get_equity_orders(dict(arguments))
    data = _data(payload, "orders")
    agent_initiated = tuple(_strict_agent_initiated(row) for row in data["orders"])
    parsed = parse_equity_orders_response(payload)
    if len(parsed.orders) != len(data["orders"]) or any(
        order is None for order in parsed.orders
    ):
        raise ValueError("order page contains an invalid row")
    return L43ReadPage(
        rows=tuple(
            _order_fact(order, agent_initiated=agent_initiated[index])
            for index, order in enumerate(parsed.orders)
        ),
        next_cursor=_cursor(data),
    )


def _data(payload: object, collection: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("Robinhood response is not a mapping")
    data = payload.get("data")
    if not isinstance(data, Mapping) or not isinstance(data.get(collection), list):
        raise ValueError("Robinhood response collection is invalid")
    return data


def _cursor(data: Mapping[str, object]) -> str | None:
    if "next" not in data:
        raise ValueError("Robinhood pagination field is missing")
    cursor = data["next"]
    if cursor is not None and (
        type(cursor) is not str or not cursor or len(cursor) > 4096
    ):
        raise ValueError("Robinhood cursor is invalid")
    return cursor


def _strict_agent_initiated(row: object) -> bool:
    if not isinstance(row, Mapping) or "agent_initiated" not in row:
        raise ValueError("order row agent_initiated is missing")
    value = row["agent_initiated"]
    if type(value) is not bool:
        raise ValueError("order row agent_initiated must be a bool")
    return value


def _position_fact(position: object) -> L43PositionFact:
    return L43PositionFact(
        symbol=position.symbol,
        quantity=position.quantity,
        shares_available_for_sells=position.shares_available_for_sells,
        position_type=position.position_type,
    )


def _order_fact(order: RobinhoodEquityOrder, *, agent_initiated: bool) -> L43OrderFact:
    return L43OrderFact(
        order_id=order.order_id,
        symbol=order.symbol.value,
        side=order.side,
        state=order.state,
        placed_agent=order.placed_agent,
        agent_initiated=agent_initiated,
        created_at=order.created_at,
        market_hours=order.market_hours,
        time_in_force=order.time_in_force,
        order_type=order.order_type,
        cumulative_quantity=order.cumulative_quantity,
        average_price=order.average_price,
        dollar_based_amount=(
            None
            if order.dollar_based_amount is None
            else L43DollarAmountFact(
                amount=order.dollar_based_amount.amount,
                currency_code=order.dollar_based_amount.currency_code,
            )
        ),
        executions=tuple(
            L43ExecutionFact(
                execution_id=execution.execution_id,
                quantity=execution.quantity,
                price=execution.price,
                timestamp=execution.timestamp,
            )
            for execution in order.executions
        ),
    )


__all__ = [
    "RobinhoodL43B2PreEffectReadAdapter",
    "RobinhoodL43PreEffectReadAdapter",
]
