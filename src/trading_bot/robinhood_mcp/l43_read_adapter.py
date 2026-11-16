"""Robinhood payload adapter for the neutral L43 read contract."""

from __future__ import annotations

import hashlib
import json
import math
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
from trading_bot.robinhood_mcp.agent_initiated_runtime_partition_proof import (
    B2CompatibilityFailure,
    B2FailureReason,
    B2OrderFact,
    B2OrderReadPage,
    validate_b2_order_fields,
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
    position, quote, portfolio, review, or mutation surface. Its order model is
    intentionally limited to the B2 partition facts and complete-row digest.
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

    def get_equity_orders(self, arguments: Mapping[str, object]) -> B2OrderReadPage:
        return _b2_order_page(self._read, arguments)


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


def _b2_order_page(read: object, arguments: Mapping[str, object]) -> B2OrderReadPage:
    try:
        payload = read.get_equity_orders(dict(arguments))
    except B2CompatibilityFailure:
        raise
    except Exception:
        raise B2CompatibilityFailure(
            B2FailureReason.TRANSPORT_TOOL_DISPATCH_FAILURE
        ) from None

    data = _b2_data(payload)
    rows: list[B2OrderFact] = []
    for row in data["orders"]:
        if not isinstance(row, Mapping):
            raise B2CompatibilityFailure(B2FailureReason.ORDER_ROW_SHAPE_FAILURE)
        try:
            order_id = row.get("id")
            symbol = row.get("symbol")
            agent_initiated = row.get("agent_initiated")
        except Exception:
            raise B2CompatibilityFailure(
                B2FailureReason.ORDER_ROW_SHAPE_FAILURE
            ) from None
        order_id, symbol, agent_initiated = validate_b2_order_fields(
            order_id, symbol, agent_initiated
        )
        try:
            row_digest = _b2_raw_row_sha256(row)
        except Exception:
            raise B2CompatibilityFailure(
                B2FailureReason.CANONICAL_ROW_SERIALIZATION_FAILURE
            ) from None
        rows.append(
            B2OrderFact(
                order_id=order_id,
                symbol=symbol,
                agent_initiated=agent_initiated,
                row_material_sha256=row_digest,
            )
        )
    return B2OrderReadPage(rows=tuple(rows), next_cursor=_b2_cursor(data))


def _b2_data(payload: object) -> Mapping[str, object]:
    try:
        if not isinstance(payload, Mapping):
            raise B2CompatibilityFailure(
                B2FailureReason.PROVIDER_RESULT_ENVELOPE_FAILURE
            )
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise B2CompatibilityFailure(
                B2FailureReason.PROVIDER_RESULT_ENVELOPE_FAILURE
            )
        orders = data.get("orders")
        if type(orders) is not list:
            raise B2CompatibilityFailure(B2FailureReason.ORDER_COLLECTION_SHAPE_FAILURE)
        return data
    except B2CompatibilityFailure:
        raise
    except Exception:
        raise B2CompatibilityFailure(
            B2FailureReason.PROVIDER_RESULT_ENVELOPE_FAILURE
        ) from None


def _b2_cursor(data: Mapping[str, object]) -> str | None:
    try:
        if "next" not in data:
            return None
        cursor = data["next"]
    except Exception:
        raise B2CompatibilityFailure(
            B2FailureReason.PAGINATION_ENVELOPE_CURSOR_FAILURE
        ) from None
    if cursor is None:
        return None
    if type(cursor) is not str:
        raise B2CompatibilityFailure(B2FailureReason.PAGINATION_ENVELOPE_CURSOR_FAILURE)
    if cursor == "":
        return None
    if len(cursor) > 4096:
        raise B2CompatibilityFailure(B2FailureReason.PAGINATION_ENVELOPE_CURSOR_FAILURE)
    return cursor


def _b2_raw_row_sha256(row: Mapping[str, object]) -> str:
    canonical = _canonical_json_value(row)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8", errors="strict")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json_value(value: object) -> object:
    if value is None or type(value) is bool or type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return value
    if type(value) is str:
        value.encode("utf-8", errors="strict")
        return value
    if type(value) is list:
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key in value:
            if type(key) is not str:
                raise ValueError("JSON object key is not a string")
            key.encode("utf-8", errors="strict")
            if key in normalized:
                raise ValueError("JSON object repeats a key")
            normalized[key] = _canonical_json_value(value[key])
        return normalized
    raise ValueError("value is outside the JSON domain")


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
