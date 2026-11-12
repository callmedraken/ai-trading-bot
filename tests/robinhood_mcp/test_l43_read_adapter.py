from __future__ import annotations

import pytest

from trading_bot.robinhood_mcp.l43_read_adapter import (
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
@pytest.mark.parametrize("cursor", (False, 1, [], {}))
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
