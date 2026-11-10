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


def _schemas(include_dollar=True, *, style="v2_object"):
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
                    "quantity": {},
                    "limit_price": {},
                    "stop_price": {},
                    "tax_lots": {},
                }
            )
            if include_dollar:
                properties["dollar_amount"] = {}
            required = ["account_number", "symbol", "side", "type"]
        if name == "place_equity_order":
            properties["ref_id"] = {}
        if name == "cancel_equity_order":
            properties["order_id"] = {}
            required = ["account_number", "order_id"]
        schema = {"properties": properties, "required": required}
        if style == "legacy_object":
            entries.append(SimpleNamespace(name=name, inputSchema=schema))
        else:
            entries.append(SimpleNamespace(name=name, input_schema=schema))
    return entries


def _schema_for(entry):
    return getattr(entry, "input_schema", getattr(entry, "inputSchema", None))


def test_live_transport_discovers_exact_surface_without_generic_dispatch():
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: _Session(_schemas()))
    assert {item.name for item in transport.discover_required_capabilities()} == set(
        LIVE_TOOL_SURFACE
    )
    assert not hasattr(transport, "call_tool")
    assert transport.place_equity_order({"dollar_amount": "0.50"})["data"] == {}
    assert dict(transport.call_counts)["place_equity_order"] == 1


def test_live_transport_accepts_mcp_v2_snake_case_tool_objects():
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: _Session(_schemas()))
    schemas = transport.discover_required_capabilities()

    assert {item.name for item in schemas} == set(LIVE_TOOL_SURFACE)
    assert dict(transport.call_counts) == dict.fromkeys(LIVE_TOOL_SURFACE, 0)


def test_live_transport_retains_legacy_camel_case_object_compatibility():
    transport = RobinhoodCurrentLiveTransport.for_test(
        lambda: _Session(_schemas(style="legacy_object"))
    )

    assert {item.name for item in transport.discover_required_capabilities()} == set(
        LIVE_TOOL_SURFACE
    )
    assert dict(transport.call_counts) == dict.fromkeys(LIVE_TOOL_SURFACE, 0)


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


def test_current_alternative_sizing_schema_does_not_require_dollar_globally():
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: _Session(_schemas()))
    schemas = {item.name: item for item in transport.discover_required_capabilities()}
    for name in ("review_equity_order", "place_equity_order"):
        assert {"dollar_amount", "quantity"} <= schemas[name].properties
        assert schemas[name].required == {"account_number", "symbol", "side", "type"}
    assert dict(transport.call_counts) == dict.fromkeys(LIVE_TOOL_SURFACE, 0)


@pytest.mark.parametrize(
    "name,field",
    [
        (name, field)
        for name in ("review_equity_order", "place_equity_order")
        for field in (
            "account_number",
            "symbol",
            "side",
            "type",
            "market_hours",
            "time_in_force",
            "dollar_amount",
        )
    ]
    + [
        ("place_equity_order", "ref_id"),
        ("cancel_equity_order", "account_number"),
        ("cancel_equity_order", "order_id"),
    ],
)
def test_missing_p6_sent_property_blocks_before_any_invocation(name, field):
    schemas = _schemas()
    schema = _schema_for(next(item for item in schemas if item.name == name))
    del schema["properties"][field]
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: _Session(schemas))
    with pytest.raises(
        CurrentLiveTransportError, match="LIVE_DOLLAR_ORDER_SCHEMA_MISSING"
    ):
        transport.get_accounts()
    assert dict(transport.call_counts) == dict.fromkeys(LIVE_TOOL_SURFACE, 0)


@pytest.mark.parametrize(
    "name,field",
    [
        (name, field)
        for name in ("review_equity_order", "place_equity_order")
        for field in ("account_number", "symbol", "side", "type")
    ]
    + [("cancel_equity_order", "account_number"), ("cancel_equity_order", "order_id")],
)
def test_stable_unconditional_required_fields_fail_closed(name, field):
    schemas = _schemas()
    schema = _schema_for(next(item for item in schemas if item.name == name))
    schema["required"].remove(field)
    transport = RobinhoodCurrentLiveTransport.for_test(lambda: _Session(schemas))
    with pytest.raises(
        CurrentLiveTransportError, match="LIVE_DOLLAR_ORDER_SCHEMA_MISSING"
    ):
        transport.discover_required_capabilities()
    assert dict(transport.call_counts) == dict.fromkeys(LIVE_TOOL_SURFACE, 0)
