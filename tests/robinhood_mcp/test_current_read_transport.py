"""Fake SDK sessions prove the current boundary without OAuth or networking."""

from contextlib import asynccontextmanager
from types import SimpleNamespace as NS

import pytest

from trading_bot.robinhood_mcp.current_read_transport import (
    READ_TOOLS,
    CurrentReadError,
    RobinhoodCurrentReadTransport,
)
from trading_bot.robinhood_mcp.sdk_transport import _ALLOWED_TOOL_NAMES


class FakeSession:
    def __init__(self, *, tools=READ_TOOLS, cursor=None, failure=None):
        self.tools = tools
        self.cursor = cursor
        self.failure = failure
        self.calls = []
        self.listings = 0

    async def list_tools(self, *, cursor):
        self.listings += 1
        return NS(tools=[NS(name=n) for n in self.tools], next_cursor=self.cursor)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.failure:
            raise RuntimeError(self.failure)
        return NS(is_error=False, structured_content={"data": {}})

    @asynccontextmanager
    async def connect(self):
        yield self


def test_exact_public_read_surface_and_frozen_131_contract():
    public = {n for n in dir(RobinhoodCurrentReadTransport) if not n.startswith("_")}
    assert public == {*READ_TOOLS, "for_test", "call_counts", "observed_read_tools"}
    assert _ALLOWED_TOOL_NAMES == (
        "get_equity_historicals",
        "get_equity_orders",
        "get_equity_quotes",
        "review_equity_order",
    )
    for name in (
        "review_equity_order",
        "place_equity_order",
        "cancel_equity_order",
        "place_option_order",
        "cancel_option_order",
        "exercise_option",
        "place_crypto_order",
        "cancel_crypto_order",
        "call_tool",
        "get_equity_historicals",
    ):
        assert not hasattr(RobinhoodCurrentReadTransport, name)


@pytest.mark.parametrize("name", READ_TOOLS)
def test_each_read_discovers_all_required_tools_before_one_dispatch(name):
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    result = getattr(transport, name)(*(() if name == "get_accounts" else ({},)))
    assert result == {"data": {}}
    assert client.calls == [(name, {})]
    assert client.listings == 1
    assert dict(transport.call_counts)[name] == 1
    assert sum(dict(transport.call_counts).values()) == 1
    assert transport.observed_read_tools == READ_TOOLS


@pytest.mark.parametrize("missing", READ_TOOLS)
def test_missing_capability_blocks_even_accounts_before_dispatch(missing):
    client = FakeSession(tools=tuple(t for t in READ_TOOLS if t != missing))
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError):
        transport.get_accounts()
    assert client.calls == []
    assert sum(dict(transport.call_counts).values()) == 0


def test_mutation_inventory_is_unneeded_and_not_surfaced():
    client = FakeSession(tools=(*READ_TOOLS, "place_equity_order"))
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    transport.get_accounts()
    assert transport.observed_read_tools == READ_TOOLS


def test_repeated_discovery_cursor_is_bounded_before_dispatch():
    client = FakeSession(cursor="repeated")
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError):
        transport.get_accounts()
    assert client.listings == 2
    assert not client.calls


def test_private_dispatch_still_rejects_arbitrary_methods():
    client = FakeSession()
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError):
        transport._invoke("place_equity_order", {})
    assert not client.calls and client.listings == 0


def test_composition_is_inert_and_provider_failures_sanitized():
    def forbidden():
        raise AssertionError("OAuth called at construction")

    RobinhoodCurrentReadTransport(forbidden)
    client = FakeSession(failure="secret-token raw-account-123")
    transport = RobinhoodCurrentReadTransport.for_test(client.connect)
    with pytest.raises(CurrentReadError) as caught:
        transport.get_accounts()
    assert str(caught.value) == "READ_REQUEST_FAILED"
    assert caught.value.__suppress_context__
    assert len(client.calls) == 1
