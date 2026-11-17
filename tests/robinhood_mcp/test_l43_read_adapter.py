from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from trading_bot.robinhood_mcp.agent_initiated_runtime_partition_proof import (
    B2CompatibilityFailure,
    B2FailureReason,
    B2OrderFact,
)
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
def test_paginated_response_normalizes_missing_next_key_as_terminal(
    collection: str,
    read_method: str,
) -> None:
    adapter = RobinhoodL43PreEffectReadAdapter(_Read(collection, {collection: []}))

    page = getattr(adapter, read_method)({})

    assert page.next_cursor is None


@pytest.mark.parametrize(
    ("collection", "read_method"),
    (
        ("positions", "get_equity_positions"),
        ("orders", "get_equity_orders"),
    ),
)
@pytest.mark.parametrize("cursor", (None, "", "cursor-2", "c" * 4096))
def test_paginated_response_accepts_exhaustion_or_cursor(
    collection: str,
    read_method: str,
    cursor: str | None,
) -> None:
    adapter = RobinhoodL43PreEffectReadAdapter(
        _Read(collection, {collection: [], "next": cursor})
    )

    page = getattr(adapter, read_method)({})

    assert page.next_cursor == (cursor or None)


@pytest.mark.parametrize(
    ("collection", "read_method"),
    (
        ("positions", "get_equity_positions"),
        ("orders", "get_equity_orders"),
    ),
)
@pytest.mark.parametrize(
    "cursor",
    (False, True, 0, 1, [], {}, object(), "c" * 4097),
)
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


def test_paginated_response_rejects_non_string_equal_to_empty_cursor() -> None:
    class _EmptyEqual:
        def __eq__(self, other: object) -> bool:
            return other == ""

    adapter = RobinhoodL43PreEffectReadAdapter(
        _Read("positions", {"positions": [], "next": _EmptyEqual()})
    )

    with pytest.raises(ValueError, match="cursor is invalid"):
        adapter.get_equity_positions({})


@pytest.mark.parametrize(
    "cursor",
    (
        "cursor/π/雪",
        " \t\n ",
        "https://example.invalid/orders?cursor=a%2Fb&next=https://other.invalid/",
    ),
)
def test_paginated_response_preserves_opaque_nonempty_cursor_verbatim(
    cursor: str,
) -> None:
    for collection, read_method in (
        ("positions", "get_equity_positions"),
        ("orders", "get_equity_orders"),
    ):
        adapter = RobinhoodL43PreEffectReadAdapter(
            _Read(collection, {collection: [], "next": cursor})
        )

        page = getattr(adapter, read_method)({})

        assert page.next_cursor == cursor


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


def _b2_order(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "b2-order-147",
        "symbol": "SPY",
        "agent_initiated": True,
    }
    row.update(overrides)
    return row


def _b2_page(row: object, *, next_cursor: object = None):
    return RobinhoodL43B2PreEffectReadAdapter(
        _Read("orders", {"orders": [row], "next": next_cursor})
    ).get_equity_orders({})


@pytest.mark.parametrize(
    "row",
    (
        _b2_order(),
        _b2_order(placed_agent=None, review_status="customer_approved"),
        _b2_order(
            placed_agent="user",
            extra={"nullable": None, "numbers": [1, 2.5], "flags": [True, False]},
        ),
    ),
)
def test_b2_accepts_minimal_and_customer_shaped_rows_without_generic_fields(
    row: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "trading_bot.robinhood_mcp.l43_read_adapter.parse_equity_orders_response",
        lambda _payload: pytest.fail("B2 must not call the generic order parser"),
    )

    page = RobinhoodL43B2PreEffectReadAdapter(
        _Read("orders", {"orders": [row]})
    ).get_equity_orders({})

    assert len(page.rows) == 1
    fact = page.rows[0]
    assert type(fact) is B2OrderFact
    assert fact.order_id == row["id"]
    assert fact.symbol == "SPY"
    assert fact.agent_initiated is True
    assert len(fact.row_material_sha256) == 64


def test_b2_raw_row_digest_uses_sorted_json_object_keys() -> None:
    first = _b2_order(extra={"z": 1, "a": {"second": 2, "first": 1}})
    second = {
        "extra": {"a": {"first": 1, "second": 2}, "z": 1},
        "agent_initiated": True,
        "symbol": "SPY",
        "id": "b2-order-147",
    }

    assert (
        _b2_page(first).rows[0].row_material_sha256
        == _b2_page(second).rows[0].row_material_sha256
    )


def test_b2_raw_row_digest_preserves_array_order_and_json_type() -> None:
    first = _b2_order(extra=[1, True, None])
    reordered = _b2_order(extra=[True, 1, None])
    numeric = _b2_order(extra=1)
    boolean = _b2_order(extra=True)

    assert (
        _b2_page(first).rows[0].row_material_sha256
        != _b2_page(reordered).rows[0].row_material_sha256
    )
    assert (
        _b2_page(numeric).rows[0].row_material_sha256
        != _b2_page(boolean).rows[0].row_material_sha256
    )


def test_b2_raw_row_digest_canonicalizes_null_values() -> None:
    row = _b2_order(nullable=None)
    expected = hashlib.sha256(
        b'{"agent_initiated":true,"id":"b2-order-147","nullable":null,"symbol":"SPY"}'
    ).hexdigest()

    assert _b2_page(row).rows[0].row_material_sha256 == expected


@pytest.mark.parametrize(
    "bad_value",
    (
        float("nan"),
        float("inf"),
        float("-inf"),
        "\ud800",
        {1: "non-string-key"},
        object(),
    ),
)
def test_b2_rejects_values_outside_the_closed_json_domain(bad_value: object) -> None:
    with pytest.raises(B2CompatibilityFailure) as error:
        _b2_page(_b2_order(extra=bad_value))

    assert error.value.reason is B2FailureReason.CANONICAL_ROW_SERIALIZATION_FAILURE


def test_b2_rejects_recursive_json_values() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    with pytest.raises(B2CompatibilityFailure) as error:
        _b2_page(_b2_order(extra=cyclic))

    assert error.value.reason is B2FailureReason.CANONICAL_ROW_SERIALIZATION_FAILURE


@pytest.mark.parametrize(
    "row",
    (
        {"symbol": "SPY", "agent_initiated": True},
        _b2_order(id=None),
        _b2_order(id=1),
        _b2_order(id="bad/id"),
        _b2_order(id="o" * 129),
        {"id": "valid-id", "agent_initiated": True},
        _b2_order(symbol=None),
        _b2_order(symbol="QQQ"),
    ),
)
def test_b2_rejects_missing_or_malformed_required_fields(row: object) -> None:
    with pytest.raises(B2CompatibilityFailure) as error:
        _b2_page(row)

    assert error.value.reason is B2FailureReason.REQUIRED_B2_FIELD_FAILURE


@pytest.mark.parametrize(
    "row",
    (
        {"id": "valid-id", "symbol": "SPY"},
        _b2_order(agent_initiated=None),
        _b2_order(agent_initiated="true"),
        _b2_order(agent_initiated="false"),
        _b2_order(agent_initiated=0),
        _b2_order(agent_initiated=1),
    ),
)
def test_b2_requires_strict_agent_initiated_boolean(row: object) -> None:
    with pytest.raises(B2CompatibilityFailure) as error:
        _b2_page(row)

    assert error.value.reason is B2FailureReason.AGENT_INITIATED_STRICT_BOOL_FAILURE


def test_b2_accepts_true_and_false_strict_values() -> None:
    for value in (True, False):
        fact = _b2_page(_b2_order(agent_initiated=value)).rows[0]
        assert fact.agent_initiated is value


@pytest.mark.parametrize(
    "payload_data",
    ({}, {"orders": None}, {"orders": "not-a-list"}, {"orders": {}}),
)
def test_b2_rejects_missing_or_malformed_order_collection(
    payload_data: dict[str, object],
) -> None:
    adapter = RobinhoodL43B2PreEffectReadAdapter(_Read("orders", payload_data))

    with pytest.raises(B2CompatibilityFailure) as error:
        adapter.get_equity_orders({})

    assert error.value.reason is B2FailureReason.ORDER_COLLECTION_SHAPE_FAILURE


@pytest.mark.parametrize("row", (None, "not-a-mapping", 17, []))
def test_b2_rejects_null_or_non_mapping_order_row(row: object) -> None:
    with pytest.raises(B2CompatibilityFailure) as error:
        _b2_page(row)

    assert error.value.reason is B2FailureReason.ORDER_ROW_SHAPE_FAILURE


@pytest.mark.parametrize("next_value", (None, ""))
def test_b2_normalizes_null_and_empty_terminal_cursors(next_value: object) -> None:
    page = RobinhoodL43B2PreEffectReadAdapter(
        _Read("orders", {"orders": [], "next": next_value})
    ).get_equity_orders({})

    assert page.next_cursor is None


def test_b2_normalizes_missing_terminal_cursor_and_preserves_opaque_cursor() -> None:
    missing = RobinhoodL43B2PreEffectReadAdapter(
        _Read("orders", {"orders": []})
    ).get_equity_orders({})
    cursor = "opaque cursor/%2F?next=https://example.invalid"
    nonempty = RobinhoodL43B2PreEffectReadAdapter(
        _Read("orders", {"orders": [], "next": cursor})
    ).get_equity_orders({})

    assert missing.next_cursor is None
    assert nonempty.next_cursor == cursor


@pytest.mark.parametrize("next_value", (True, 4, [], {}, "c" * 4097))
def test_b2_rejects_malformed_or_oversized_cursors(next_value: object) -> None:
    with pytest.raises(B2CompatibilityFailure) as error:
        RobinhoodL43B2PreEffectReadAdapter(
            _Read("orders", {"orders": [], "next": next_value})
        ).get_equity_orders({})

    assert error.value.reason is B2FailureReason.PAGINATION_ENVELOPE_CURSOR_FAILURE
