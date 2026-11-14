from __future__ import annotations

from decimal import Decimal

import pytest

from trading_bot.robinhood_mcp.l43_read_adapter import (
    RobinhoodL43B2PreEffectReadAdapter,
    RobinhoodL43PreEffectReadAdapter,
)


class _Read:
    def __init__(self, collection: str, data: dict[str, object]) -> None:
        self.collection = collection
        self.data = data

    def get_accounts(self) -> object:
        raise AssertionError("account reads are outside this adapter test")

    def get_equity_positions(self, arguments: dict[str, object]) -> object:
        del arguments
        if self.collection != "positions":
            raise AssertionError("unexpected positions read")
        return {"data": self.data}

    def get_equity_orders(self, arguments: dict[str, object]) -> object:
        del arguments
        if self.collection != "orders":
            raise AssertionError("unexpected orders read")
        return {"data": self.data}


def _order(**overrides: object) -> dict[str, object]:
    order = {
        "id": "order-147",
        "symbol": "SPY",
        "side": "buy",
        "state": "filled",
        "placed_agent": "agentic",
        "agent_initiated": True,
        "created_at": "2026-11-10T15:00:00+00:00",
        "last_transaction_at": "2026-11-10T15:00:00+00:00",
        "market_hours": "regular_hours",
        "time_in_force": "day",
        "type": "market",
        "trigger": "immediate",
        "quantity": None,
        "cumulative_quantity": "0.5",
        "average_price": "20",
        "price": None,
        "stop_price": None,
        "fees": "0",
        "ref_id": None,
        "reject_reason": None,
        "instrument_id": "instrument-147",
        "dollar_based_amount": None,
        "executions": [],
    }
    order.update(overrides)
    return order


@pytest.mark.parametrize(
    ("collection", "read_method"),
    (
        ("positions", "get_equity_positions"),
        ("orders", "get_equity_orders"),
    ),
)
def test_paginated_response_requires_explicit_next_key(
    collection: str,
    read_method: str,
) -> None:
    adapter = RobinhoodL43PreEffectReadAdapter(_Read(collection, {collection: []}))

    with pytest.raises(ValueError, match="pagination field is missing"):
        getattr(adapter, read_method)({})


@pytest.mark.parametrize(
    ("collection", "read_method"),
    (
        ("positions", "get_equity_positions"),
        ("orders", "get_equity_orders"),
    ),
)
@pytest.mark.parametrize("cursor", (None, "cursor-2"))
def test_paginated_response_accepts_exhaustion_or_cursor(
    collection: str,
    read_method: str,
    cursor: str | None,
) -> None:
    adapter = RobinhoodL43PreEffectReadAdapter(
        _Read(collection, {collection: [], "next": cursor})
    )

    page = getattr(adapter, read_method)({})

    assert page.next_cursor == cursor


@pytest.mark.parametrize(
    ("collection", "read_method"),
    (
        ("positions", "get_equity_positions"),
        ("orders", "get_equity_orders"),
    ),
)
@pytest.mark.parametrize("cursor", (False, 1, [], {}, "", "c" * 4097))
def test_paginated_response_rejects_malformed_cursor(
    collection: str,
    read_method: str,
    cursor: object,
) -> None:
    adapter = RobinhoodL43PreEffectReadAdapter(
        _Read(collection, {collection: [], "next": cursor})
    )

    with pytest.raises(ValueError):
        getattr(adapter, read_method)({})


@pytest.mark.parametrize(
    ("placed_agent", "agent_initiated"),
    (("agentic", True), ("user", True), ("agentic", False)),
)
def test_order_fact_preserves_strict_agent_initiated_independently(
    placed_agent: str, agent_initiated: bool
) -> None:
    row = _order(placed_agent=placed_agent, agent_initiated=agent_initiated)
    adapter = RobinhoodL43PreEffectReadAdapter(
        _Read("orders", {"orders": [row], "next": None})
    )

    page = adapter.get_equity_orders({"account_number": "account-147", "symbol": "SPY"})

    fact = page.rows[0]
    assert fact.agent_initiated is agent_initiated
    assert type(fact.agent_initiated) is bool
    assert fact.placed_agent == placed_agent


@pytest.mark.parametrize(
    "agent_initiated",
    (
        None,
        "true",
        "false",
        0,
        1,
        Decimal("0"),
        Decimal("1"),
        [],
        {},
        object(),
    ),
)
def test_order_page_rejects_non_boolean_agent_initiated_without_coercion(
    agent_initiated: object,
) -> None:
    row = _order(agent_initiated=agent_initiated)

    with pytest.raises(ValueError, match="agent_initiated"):
        RobinhoodL43PreEffectReadAdapter(
            _Read("orders", {"orders": [row], "next": None})
        ).get_equity_orders({})


def test_order_page_rejects_missing_agent_initiated() -> None:
    row = _order()
    del row["agent_initiated"]

    with pytest.raises(ValueError, match="agent_initiated"):
        RobinhoodL43PreEffectReadAdapter(
            _Read("orders", {"orders": [row], "next": None})
        ).get_equity_orders({})


def test_invalid_agent_initiated_row_rejects_whole_page() -> None:
    rows = [_order(id="valid-147"), _order(id="invalid-147", agent_initiated=1)]

    with pytest.raises(ValueError, match="agent_initiated"):
        RobinhoodL43PreEffectReadAdapter(
            _Read("orders", {"orders": rows, "next": "page-2"})
        ).get_equity_orders({})


def test_valid_order_page_preserves_pagination() -> None:
    page = RobinhoodL43PreEffectReadAdapter(
        _Read("orders", {"orders": [_order()], "next": "page-2"})
    ).get_equity_orders({})

    assert page.next_cursor == "page-2"


def test_b2_adapter_exposes_only_account_and_order_reads() -> None:
    adapter = RobinhoodL43B2PreEffectReadAdapter(
        _Read("orders", {"orders": [], "next": None})
    )

    assert hasattr(adapter, "get_accounts")
    assert hasattr(adapter, "get_equity_orders")
    assert not hasattr(adapter, "get_equity_positions")
    assert adapter.get_equity_orders({}).rows == ()
