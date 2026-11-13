from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from trading_bot.robinhood_mcp.agent_initiated_partition_schema_qualifier import (
    AgentInitiatedPartitionSchemaClassification as Classification,
)
from trading_bot.robinhood_mcp.agent_initiated_partition_schema_qualifier import (
    AgentInitiatedPartitionSchemaMatcher,
)

_CONTRACT = (
    "true returns every agent-initiated order from any agent; "
    "false returns every order with no agent involved; "
    "omit the parameter to return all orders."
)


def _input_schema(
    *,
    field_type: object = None,
    required: bool = False,
    default: object = ...,
    description: str = _CONTRACT,
) -> dict[str, object]:
    if field_type is None:
        field_type = ["null", "boolean"]
    field: dict[str, object] = {"type": field_type, "description": description}
    if default is not ...:
        field["default"] = default
    return {
        "type": "object",
        "properties": {"account_number": {"type": "string"}, "agent_initiated": field},
        "required": ["account_number", "agent_initiated"]
        if required
        else ["account_number"],
        "additionalProperties": False,
    }


def _output_schema(
    *, field_type: object = "boolean", field_required: bool = True
) -> dict[str, object]:
    row_required = ["id", "symbol"]
    if field_required:
        row_required.append("agent_initiated")
    return {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "properties": {
                    "orders": {
                        "type": ["null", "array"],
                        "items": {
                            "type": ["null", "object"],
                            "properties": {
                                "id": {"type": "string"},
                                "symbol": {"type": "string"},
                                "agent_initiated": {"type": field_type},
                            },
                            "required": row_required,
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["orders"],
            },
            "guide": {"type": "string"},
        },
        "required": ["data", "guide"],
    }


def _tool(
    *,
    description: str = "List equity orders.",
    input_schema: dict[str, object] | None = None,
    output_schema: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": "get_equity_orders",
        "description": description,
        "inputSchema": _input_schema() if input_schema is None else input_schema,
        "outputSchema": _output_schema() if output_schema is None else output_schema,
    }


def _page(
    tools: list[object],
    *,
    next_cursor: object = None,
    result_type: str = "complete",
) -> dict[str, object]:
    return {
        "tools": tools,
        "next_cursor": next_cursor,
        "result_type": result_type,
    }


def _observe(pages: dict[str | None, object]):
    calls: list[str | None] = []

    def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        return pages[cursor]

    matcher = AgentInitiatedPartitionSchemaMatcher(repo_root=Path(__file__).parents[2])
    result = asyncio.run(matcher.match(tools_list=list_tools))
    return result, calls


def test_exact_three_clause_schema_is_only_an_unauthenticated_match() -> None:
    result, calls = _observe({None: _page([_tool()])})

    assert result.classification is Classification.UNAUTHENTICATED_SEMANTIC_MATCH
    assert result.semantic_match
    assert result.authenticated is False
    assert result.contract_version == "EXHAUSTIVE_AGENT_INITIATED_PARTITION/v1"
    assert result.output_schema_sha256 is not None
    assert result.agent_initiated_schema_sha256 is not None
    assert result.pagination_exhaustive
    assert calls == [None]


def test_complete_sdk_list_result_defaults_are_accepted() -> None:
    mcp_types = pytest.importorskip("mcp.types")
    tool = mcp_types.Tool(
        name="get_equity_orders",
        description="List equity orders.",
        input_schema=_input_schema(),
        output_schema=_output_schema(),
    )
    page = mcp_types.ListToolsResult(tools=[tool])
    assert page.result_type == "complete"
    assert page.next_cursor is None

    result, calls = _observe({None: page})
    assert result.semantic_match
    assert result.authenticated is False
    assert calls == [None]


def test_exhaustive_tools_list_pagination_collects_target_once() -> None:
    unrelated = {
        "name": "get_accounts",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "outputSchema": None,
    }
    result, calls = _observe(
        {
            None: _page([unrelated], next_cursor="page-2"),
            "page-2": _page([_tool()]),
        }
    )
    assert result.semantic_match
    assert result.tools_list_pages == 2
    assert result.pagination_exhaustive
    assert calls == [None, "page-2"]


@pytest.mark.parametrize(
    "schema",
    [
        _input_schema(field_type="string"),
        _input_schema(field_type=["boolean", "string"]),
        _input_schema(required=True),
        _input_schema(default=False),
        _input_schema(default=True),
        _input_schema(field_type="boolean", default=None),
    ],
)
def test_input_property_must_be_optional_noncontradictory_boolean(schema):
    result, _ = _observe({None: _page([_tool(input_schema=schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_missing_agent_initiated_input_property_is_unproven() -> None:
    schema = _input_schema()
    schema["properties"].pop("agent_initiated")  # type: ignore[union-attr]
    result, _ = _observe({None: _page([_tool(input_schema=schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_null_default_is_compatible_only_with_nullable_boolean() -> None:
    schema = _input_schema(default=None)
    result, _ = _observe({None: _page([_tool(input_schema=schema)])})
    assert result.semantic_match


@pytest.mark.parametrize(
    "description",
    [
        "true returns every agent-initiated order from any agent; "
        "false returns only orders the customer created with no agent involved; "
        "omit the parameter to return all orders.",
        "true returns every agent-initiated order from any agent; "
        "false returns every order with no agent involved.",
        "true returns every agent-initiated order from any agent; "
        "false returns every order with no agent involved; "
        "omit returns every agent-initiated order.",
        "true returns only this agent's orders; "
        "false returns every order with no agent involved; "
        "omit returns all agent-initiated orders.",
        "true returns only this agent's orders; "
        "false returns every order with no agent involved; "
        "omit the parameter to return all orders.",
    ],
)
def test_partial_or_crossed_semantics_never_match(description: str) -> None:
    schema = _input_schema(description=description)
    result, _ = _observe({None: _page([_tool(input_schema=schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


@pytest.mark.parametrize(
    "output_schema",
    [
        _output_schema(field_type="string"),
        _output_schema(field_required=False),
    ],
)
def test_output_agent_initiated_must_be_required_boolean(output_schema):
    result, _ = _observe({None: _page([_tool(output_schema=output_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_output_schema_requires_data_orders_and_rows_before_matching() -> None:
    for required_path in ("data", "orders"):
        schema = _output_schema()
        if required_path == "data":
            schema["required"] = ["guide"]
        else:
            schema["properties"]["data"]["required"] = []  # type: ignore[index]
        result, _ = _observe({None: _page([_tool(output_schema=schema)])})
        assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_output_order_without_agent_initiated_is_unproven() -> None:
    schema = _output_schema()
    row = schema["properties"]["data"]["properties"]["orders"]["items"]  # type: ignore[index]
    row["properties"].pop("agent_initiated")  # type: ignore[index]
    row["required"].remove("agent_initiated")  # type: ignore[index]
    result, _ = _observe({None: _page([_tool(output_schema=schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_schema_composition_and_narrowing_at_ancestors_blocks_match() -> None:
    input_schema = _input_schema()
    input_schema["allOf"] = [{"properties": {"agent_initiated": {"enum": [True]}}}]
    result, _ = _observe({None: _page([_tool(input_schema=input_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS

    output_schema = _output_schema()
    item = output_schema["properties"]["data"]["properties"]["orders"]["items"]  # type: ignore[index]
    item["if"] = {"properties": {"symbol": {"const": "SPY"}}}  # type: ignore[index]
    result, _ = _observe({None: _page([_tool(output_schema=output_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS

    input_schema = _input_schema()
    input_schema["minProperties"] = 3
    result, _ = _observe({None: _page([_tool(input_schema=input_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS

    input_schema = _input_schema()
    input_schema["properties"]["placed_agent"] = {  # type: ignore[index]
        "type": "string",
        "default": "agentic",
    }
    result, _ = _observe({None: _page([_tool(input_schema=input_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS

    input_schema = _input_schema()
    input_schema["properties"]["state"] = {  # type: ignore[index]
        "type": "string",
        "default": "filled",
    }
    result, _ = _observe({None: _page([_tool(input_schema=input_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS

    input_schema = _input_schema()
    input_schema["required"] = ["account_number", "placed_agent"]
    input_schema["properties"]["placed_agent"] = {"type": "string"}  # type: ignore[index]
    result, _ = _observe({None: _page([_tool(input_schema=input_schema)])})
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_duplicate_schema_aliases_and_duplicate_target_are_malformed() -> None:
    duplicate_alias = _tool()
    duplicate_alias["input_schema"] = duplicate_alias["inputSchema"]
    result, _ = _observe({None: _page([duplicate_alias])})
    assert result.classification is Classification.SCHEMA_MALFORMED

    result, _ = _observe({None: _page([_tool(), _tool()])})
    assert result.classification is Classification.SCHEMA_MALFORMED

    page = _page([_tool()])
    page["resultType"] = "incomplete"
    result, _ = _observe({None: page})
    assert result.classification is Classification.SCHEMA_MALFORMED

    result, _ = _observe(
        {
            None: {
                "tools": [_tool()],
                "next_cursor": None,
                "resultType": "incomplete",
            }
        }
    )
    assert result.classification is Classification.SCHEMA_MALFORMED


@pytest.mark.parametrize(
    "page",
    [
        _page([_tool()], result_type="incomplete"),
        {"tools": [_tool()], "next_cursor": None},
        _page([{"name": 4, "inputSchema": {"type": "object"}}]),
        _page(
            [
                {
                    "name": "unrelated",
                    "inputSchema": "malformed",
                    "outputSchema": None,
                },
                _tool(),
            ]
        ),
    ],
)
def test_malformed_or_noncomplete_unrelated_metadata_cannot_match(page: object) -> None:
    result, _ = _observe({None: page})
    assert result.classification is Classification.SCHEMA_MALFORMED


def test_repeated_cursor_and_page_fetch_failure_are_malformed() -> None:
    result, _ = _observe(
        {
            None: _page([_tool()], next_cursor="repeat"),
            "repeat": _page([], next_cursor="repeat"),
        }
    )
    assert result.classification is Classification.SCHEMA_MALFORMED

    calls: list[str | None] = []

    def fail(*, cursor: str | None) -> object:
        calls.append(cursor)
        raise RuntimeError("private provider response")

    matcher = AgentInitiatedPartitionSchemaMatcher(repo_root=Path(__file__).parents[2])
    result = asyncio.run(matcher.match(tools_list=fail))
    assert result.classification is Classification.SCHEMA_MALFORMED
    assert "private provider response" not in repr(result)
    assert calls == [None]


def test_source_identity_failure_precedes_metadata_seam(tmp_path: Path) -> None:
    calls: list[str | None] = []

    def forbidden(*, cursor: str | None) -> object:
        calls.append(cursor)
        raise AssertionError("metadata seam must not run")

    matcher = AgentInitiatedPartitionSchemaMatcher(repo_root=tmp_path)
    result = asyncio.run(matcher.match(tools_list=forbidden))
    assert result.classification is Classification.SOURCE_AUTHORITY_FAILED
    assert calls == []
