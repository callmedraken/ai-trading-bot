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


@pytest.mark.parametrize("name", LIVE_TOOL_SURFACE)
@pytest.mark.parametrize("outcome", ("success", "raises", "error", "malformed"))
def test_tool_counts_actual_invocations_including_failures(name, outcome):
    calls = []

    class Session(_Session):
        async def _call_tool(self, tool, arguments):
            calls.append((tool, arguments))
            # Accounting must already be visible at the invocation boundary.
            assert dict(transport.call_counts)[tool] == len(calls)
            if outcome == "raises":
                raise RuntimeError("SECRET_OAUTH_ACCOUNT_PROVIDER_PAYLOAD")
            return SimpleNamespace(
                is_error=outcome == "error",
                structured_content=[] if outcome == "malformed" else {"data": {}},
            )

    transport = RobinhoodCurrentLiveTransport.for_test(lambda: Session(_schemas()))
    method = getattr(transport, name)
    if outcome == "success":
        result = method() if name == "get_accounts" else method({})
        assert result == {"data": {}}
    else:
        code = "LIVE_REQUEST_FAILED" if outcome == "raises" else "LIVE_RESULT_INVALID"
        with pytest.raises(CurrentLiveTransportError, match=f"^{code}$"):
            method() if name == "get_accounts" else method({})
    assert calls == [(name, {})]
    assert dict(transport.call_counts) == {
        tool: int(tool == name) for tool in LIVE_TOOL_SURFACE
    }


@pytest.mark.parametrize("name", LIVE_TOOL_SURFACE)
@pytest.mark.parametrize("failure", ("discovery", "schema"))
def test_failure_before_tool_invocation_keeps_all_counts_zero(name, failure):
    calls = []

    class Session(_Session):
        async def _list_tools(self, cursor=None):
            if failure == "discovery":
                raise RuntimeError("SECRET_PROVIDER_PAYLOAD")
            return await super()._list_tools(cursor)

        async def _call_tool(self, tool, arguments):
            calls.append(tool)
            raise AssertionError("local failure must prevent tool invocation")

    transport = RobinhoodCurrentLiveTransport.for_test(
        lambda: Session(_schemas(include_dollar=False))
    )
    code = (
        "LIVE_REQUEST_FAILED"
        if failure == "discovery"
        else "LIVE_DOLLAR_ORDER_SCHEMA_MISSING"
    )
    with pytest.raises(CurrentLiveTransportError, match=f"^{code}$"):
        method = getattr(transport, name)
        method() if name == "get_accounts" else method({})
    assert calls == []
    assert dict(transport.call_counts) == dict.fromkeys(LIVE_TOOL_SURFACE, 0)
