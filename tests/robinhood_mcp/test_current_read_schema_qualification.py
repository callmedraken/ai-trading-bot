from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from trading_bot.robinhood_mcp.current_read_schema_qualification import (
    MAX_DISCOVERY_PAGES,
    OrderScopeQualification,
    SchemaFieldStatus,
    SchemaQualificationStatus,
    qualify_current_read_provider,
    qualify_current_read_schemas,
)
from trading_bot.robinhood_mcp.current_read_transport import READ_TOOLS


def _tool(
    name: str,
    *,
    arguments: dict[str, object] | None = None,
    required: tuple[str, ...] = (),
    output: dict[str, object] | None = None,
    description: str = "synthetic provider description",
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": arguments or {},
            "required": list(required),
            "additionalProperties": False,
        },
        outputSchema=output
        or {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"account_number": {"type": "string"}},
                }
            },
            "additionalProperties": False,
        },
    )


def _pages(tools: list[object], next_cursor: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(tools=tools, next_cursor=next_cursor)


def test_schema_observation_is_allowlisted_paginated_and_never_dispatches() -> None:
    rows = [_tool(name) for name in READ_TOOLS if name != "get_equity_orders"]
    rows.append(
        _tool(
            "get_equity_orders",
            arguments={
                "account_number": {"type": "string"},
                "cursor": {"type": "string"},
                "placed_agent": {"type": "string"},
                "created_at_gte": {"type": "string"},
            },
            required=("account_number",),
            output={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "data": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "account_number": {"type": "string"},
                            "orders": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "account_number": {"type": "string"}
                                    },
                                },
                            },
                            "next": {"type": ["string", "null"]},
                        },
                    }
                },
            },
        )
    )
    unknown = _tool(
        "place_equity_order",
        description="secret-marker-in-description",
        arguments={"secret_field": {"type": "string"}},
    )
    calls: list[str | None] = []
    tool_invocations: list[object] = []

    async def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        if cursor is None:
            return _pages(rows[:3], "page-2")
        return _pages([*rows[3:], unknown])

    result = asyncio.run(qualify_current_read_schemas(list_tools))
    order_schema = next(
        item for item in result.read_tools if item.name == "get_equity_orders"
    )
    arguments = {item.name: item for item in order_schema.arguments}

    assert result.status is SchemaQualificationStatus.COMPLETE
    assert result.tools_list_pages == 2
    assert result.pagination_complete
    assert calls == [None, "page-2"]
    assert result.quarantined_tool_count == 1
    assert tuple(item.name for item in result.read_tools) == READ_TOOLS
    assert arguments["account_number"].required
    assert arguments["account_number"].types == ("string",)
    assert order_schema.account_argument_status is SchemaFieldStatus.PRESENT_REQUIRED
    assert order_schema.pagination_arguments == ("cursor",)
    assert set(order_schema.order_filter_arguments) == {
        "placed_agent",
        "created_at_gte",
    }
    assert order_schema.result_account_binding_paths == (
        "data.account_number",
        "data.orders[].account_number",
    )
    assert order_schema.result_pagination_paths == ("data.next",)
    assert order_schema.result_schema_shape_complete
    assert result.order_scope is OrderScopeQualification.SCHEMA_ONLY_UNPROVEN
    assert "secret-marker" not in repr(result)
    assert "place_equity_order" not in repr(result)
    assert tool_invocations == []


def test_later_page_failure_discards_partial_schema_observation() -> None:
    calls: list[str | None] = []

    async def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        if cursor is None:
            return _pages([_tool(READ_TOOLS[0])], "page-2")
        raise RuntimeError("provider token and raw payload must not escape")

    result = asyncio.run(qualify_current_read_schemas(list_tools))

    assert result.status is SchemaQualificationStatus.INCOMPLETE
    assert not result.pagination_complete
    assert result.tools_list_pages == 1
    assert calls == [None, "page-2"]
    assert all(not item.advertised for item in result.read_tools)
    assert "token" not in repr(result)
    assert "payload" not in repr(result)


def test_schema_discovery_page_limit_is_incomplete() -> None:
    calls: list[str | None] = []

    async def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        page_number = len(calls)
        return _pages([], f"cursor-{page_number}")

    result = asyncio.run(qualify_current_read_schemas(list_tools))

    assert result.status is SchemaQualificationStatus.INCOMPLETE
    assert result.tools_list_pages == MAX_DISCOVERY_PAGES
    assert not result.pagination_complete
    assert len(calls) == MAX_DISCOVERY_PAGES
    assert all(not item.advertised for item in result.read_tools)


def test_missing_allowlisted_tool_is_explicit_after_complete_listing() -> None:
    tools = [_tool(name) for name in READ_TOOLS[:-1]]
    result = asyncio.run(qualify_current_read_schemas(lambda *, cursor: _pages(tools)))
    missing = result.read_tools[-1]

    assert result.status is SchemaQualificationStatus.INCOMPLETE
    assert result.pagination_complete
    assert missing.name == READ_TOOLS[-1]
    assert not missing.advertised
    assert missing.input_schema_sha256 is None
    assert missing.account_argument_status is SchemaFieldStatus.SCHEMA_UNAVAILABLE
    assert result.order_scope is OrderScopeQualification.SCHEMA_ONLY_UNPROVEN


@pytest.mark.parametrize(
    ("pages", "expected_status"),
    [
        (
            {
                None: _pages([_tool(READ_TOOLS[0])], "repeat"),
                "repeat": _pages([_tool(READ_TOOLS[1])], "repeat"),
            },
            SchemaQualificationStatus.MALFORMED,
        ),
        (
            {None: _pages([_tool(READ_TOOLS[0])], "")},
            SchemaQualificationStatus.MALFORMED,
        ),
    ],
)
def test_invalid_or_repeated_list_cursor_fails_closed(pages, expected_status) -> None:
    def list_tools(*, cursor: str | None) -> object:
        return pages[cursor]

    result = asyncio.run(qualify_current_read_schemas(list_tools))

    assert result.status is expected_status
    assert not result.pagination_complete
    assert all(not item.advertised for item in result.read_tools)


def test_malformed_schema_and_ambiguous_schema_alias_fail_closed() -> None:
    malformed = _tool(READ_TOOLS[0])
    malformed.inputSchema = {"type": "object", "properties": {"bad field": {}}}
    result = asyncio.run(
        qualify_current_read_schemas(lambda *, cursor: _pages([malformed]))
    )
    assert result.status is SchemaQualificationStatus.MALFORMED
    assert all(not item.advertised for item in result.read_tools)

    ambiguous = _tool(READ_TOOLS[0])
    ambiguous.input_schema = ambiguous.inputSchema
    result = asyncio.run(
        qualify_current_read_schemas(lambda *, cursor: _pages([ambiguous]))
    )
    assert result.status is SchemaQualificationStatus.MALFORMED
    assert all(not item.advertised for item in result.read_tools)


def test_unavailable_output_schema_is_reported_without_semantic_inference() -> None:
    tool = _tool(READ_TOOLS[0])
    del tool.outputSchema
    result = asyncio.run(qualify_current_read_schemas(lambda *, cursor: _pages([tool])))

    assert result.status is SchemaQualificationStatus.INCOMPLETE
    fact = result.read_tools[0]
    assert fact.advertised
    assert fact.output_schema_sha256 is None
    assert fact.result_schema_shape_complete is False
    assert fact.result_account_binding_paths is None
    assert fact.result_pagination_paths is None
    assert result.order_scope is OrderScopeQualification.SCHEMA_ONLY_UNPROVEN


def test_open_input_schema_does_not_claim_account_argument_absent() -> None:
    tool = _tool(READ_TOOLS[0])
    del tool.inputSchema["additionalProperties"]

    result = asyncio.run(qualify_current_read_schemas(lambda *, cursor: _pages([tool])))

    assert result.status is SchemaQualificationStatus.INCOMPLETE
    fact = result.read_tools[0]
    assert fact.advertised
    assert not fact.input_arguments_complete
    assert fact.account_argument_status is SchemaFieldStatus.SCHEMA_UNAVAILABLE


def test_explicit_provider_operation_uses_only_tools_list_with_fake_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.robinhood_mcp import current_read_schema_qualification as module

    class FakeSession:
        def __init__(self) -> None:
            self.list_calls = 0
            self.tool_calls = 0

        async def list_tools(self, *, cursor: str | None = None) -> object:
            self.list_calls += 1
            assert cursor is None
            return _pages([_tool(name) for name in READ_TOOLS])

        async def call_tool(self, *args: object, **kwargs: object) -> object:
            self.tool_calls += 1
            raise AssertionError("schema qualification must not dispatch tools")

    session = FakeSession()
    opened: list[object] = []

    @asynccontextmanager
    async def open_fake(factory):
        opened.append(factory)
        yield session

    monkeypatch.setattr(module, "_open_robinhood_client", open_fake)

    def oauth_factory() -> object:
        pytest.fail("fake session must not read credentials")

    result = asyncio.run(qualify_current_read_provider(oauth_factory))

    assert result.status is SchemaQualificationStatus.COMPLETE
    assert opened == [oauth_factory]
    assert session.list_calls == 1
    assert session.tool_calls == 0


def test_injected_schema_adapter_does_not_open_provider_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.robinhood_mcp import current_read_schema_qualification as module

    monkeypatch.setattr(
        module,
        "_open_robinhood_client",
        lambda _: pytest.fail("pure schema adapter must not open a session"),
    )
    result = asyncio.run(
        qualify_current_read_schemas(lambda *, cursor: _pages([_tool(READ_TOOLS[0])]))
    )

    assert result.status is SchemaQualificationStatus.INCOMPLETE
    assert result.read_tools[0].advertised
