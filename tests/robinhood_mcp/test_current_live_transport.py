from types import SimpleNamespace

import pytest

from trading_bot.robinhood_mcp.current_live_transport import (
    LIVE_TOOL_SURFACE,
    CurrentLiveTransportError,
    RobinhoodCurrentLiveTransport,
)


class _Session:
    def __init__(self, schemas):
        self.client = SimpleNamespace(
            list_tools=self._list_tools,
            call_tool=self._call_tool,
        )
        self.schemas = schemas

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *args):
        return None

    async def _list_tools(self, cursor=None):
        del cursor
        return SimpleNamespace(tools=self.schemas, next_cursor=None)

    async def _call_tool(self, name, arguments):
        return SimpleNamespace(
            is_error=False,
            structured_content={"data": {}, "name": name, "arguments": arguments},
        )


def _schemas(include_dollar=True):
    entries = []
    for name in LIVE_TOOL_SURFACE:
        properties = {"account_number": {}}
        required = []
        if name in {"review_equity_order", "place_equity_order"}:
            properties.update(
                {
                    "symbol": {},
                    "side": {},
                    "type": {},
                    "market_hours": {},
                    "time_in_force": {},
                }
            )
            if include_dollar:
                properties["dollar_amount"] = {}
                required.append("dollar_amount")
        if name == "cancel_equity_order":
            properties["order_id"] = {}
        entries.append(
            SimpleNamespace(
                name=name,
                inputSchema={"properties": properties, "required": required},
            )
        )
    return entries


def test_live_transport_discovers_exact_surface_without_generic_dispatch():
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: _Session(_schemas()))
    assert {item.name for item in transport.discover_required_capabilities()} == set(
        LIVE_TOOL_SURFACE
    )
    assert not hasattr(transport, "call_tool")
    assert transport.place_equity_order({"dollar_amount": "0.50"})["data"] == {}
    assert dict(transport.call_counts)["place_equity_order"] == 1


def test_live_transport_fails_closed_without_dollar_schema():
    transport = RobinhoodCurrentLiveTransport.for_test(
        lambda: _Session(_schemas(include_dollar=False))
    )
    with pytest.raises(CurrentLiveTransportError, match="DOLLAR_ORDER"):
        transport.discover_required_capabilities()
