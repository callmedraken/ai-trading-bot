from __future__ import annotations

import asyncio
import dataclasses
import inspect
from pathlib import Path

import pytest

from trading_bot.robinhood_mcp.order_scope_schema_qualifier import (
    OrderScopeClassification as Classification,
)
from trading_bot.robinhood_mcp.order_scope_schema_qualifier import (
    RobinhoodOrderScopeSchemaQualifier,
)

_EXPLICIT_SCOPE = (
    "When placed_agent is omitted, the result includes all orders for the "
    "authenticated account across all agents."
)


def _tool(
    *, description: str = "List equity orders.", schema: object | None = None
) -> dict[str, object]:
    return {
        "name": "get_equity_orders",
        "description": description,
        "input_schema": (
            {
                "type": "object",
                "properties": {
                    "placed_agent": {
                        "type": "string",
                        "description": "Optional order agent filter.",
                    }
                },
                "required": [],
            }
            if schema is None
            else schema
        ),
    }


def _page(tools: list[object], next_cursor: object = None) -> dict[str, object]:
    return {"tools": tools, "next_cursor": next_cursor}


def _observe(pages: dict[str | None, object]):
    calls: list[str | None] = []

    def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        return pages[cursor]

    qualifier = RobinhoodOrderScopeSchemaQualifier(repo_root=Path(__file__).parents[2])
    result = asyncio.run(qualifier.observe(test_tools_list=list_tools))
    return result, calls


def test_only_explicit_provider_scope_statement_proves_all_agents() -> None:
    result, calls = _observe({None: _page([_tool(description=_EXPLICIT_SCOPE)])})

    assert result.classification is Classification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS
    assert result.tool_name == "get_equity_orders"
    assert result.description_sha256 is not None
    assert result.input_schema_sha256 is not None
    assert result.placed_agent is not None
    assert result.placed_agent.present
    assert not result.placed_agent.required
    assert result.placed_agent.schema_sha256 is not None
    assert result.pagination_exhaustive
    assert calls == [None]


@pytest.mark.parametrize(
    "schema",
    [
        {
            "type": "object",
            "properties": {"placed_agent": {"type": "string"}},
            "required": ["placed_agent"],
        },
        {
            "type": "object",
            "properties": {"placed_agent": {"type": "string", "default": "agentic"}},
            "required": [],
        },
        {
            "type": "object",
            "properties": {"placed_agent": {"type": "integer"}},
            "required": [],
        },
        {"type": "object", "properties": {}, "required": []},
    ],
)
def test_explicit_description_cannot_override_conflicting_scope_schema(
    schema: dict[str, object],
) -> None:
    result, _ = _observe(
        {None: _page([_tool(description=_EXPLICIT_SCOPE, schema=schema)])}
    )

    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_explicit_scope_in_relevant_schema_description_can_qualify() -> None:
    schema = {
        "type": "object",
        "properties": {
            "placed_agent": {"type": "string", "description": _EXPLICIT_SCOPE}
        },
        "required": [],
    }
    result, _ = _observe({None: _page([_tool(schema=schema)])})

    assert result.classification is Classification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS
    assert result.placed_agent is not None
    assert not result.placed_agent.default_present
    assert result.placed_agent.default_is_null is None


@pytest.mark.parametrize(
    "description,schema",
    [
        ("List equity orders.", None),
        ("Omitting placed_agent returns every result.", None),
        ("Historical evidence says all agents were queried.", None),
        (
            f"{_EXPLICIT_SCOPE} This behavior is not guaranteed.",
            None,
        ),
        (
            "List equity orders.",
            {
                "type": "object",
                "properties": {
                    "placed_agent": {"type": "string", "default": "agent-a"}
                },
                "required": [],
            },
        ),
    ],
)
def test_omission_rows_and_historical_evidence_do_not_prove_scope(
    description: str, schema: object | None
) -> None:
    result, _ = _observe({None: _page([_tool(description=description, schema=schema)])})

    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_exhaustive_pagination_and_tool_name_are_not_scope_authority() -> None:
    result, calls = _observe(
        {
            None: _page(
                [
                    {"name": "review_equity_order", "description": _EXPLICIT_SCOPE},
                    _tool(),
                ],
                "next-page",
            ),
            "next-page": _page([{"name": "other_tool"}]),
        }
    )

    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS
    assert result.pagination_exhaustive
    assert result.tools_list_pages == 2
    assert calls == [None, "next-page"]


@pytest.mark.parametrize(
    "pages",
    [
        {None: {"tools": [], "next_cursor": ""}},
        {None: _page([], "cursor"), "cursor": _page([], "cursor")},
        {None: _page([], "x" * 4097)},
        {None: {"tools": []}},
        {None: _page([_tool(schema={"type": "object", "required": "placed_agent"})])},
        {None: _page([_tool(schema={"type": "array", "properties": {}})])},
    ],
)
def test_malformed_schema_or_pagination_fails_closed(
    pages: dict[str | None, object],
) -> None:
    result, _ = _observe(pages)

    assert result.classification is Classification.SCHEMA_MALFORMED
    assert not result.pagination_exhaustive


def test_tool_unavailable_is_closed_after_exhaustive_listing() -> None:
    result, _ = _observe({None: _page([{"name": "get_equity_tradability"}])})

    assert result.classification is Classification.TOOL_UNAVAILABLE
    assert result.pagination_exhaustive


def test_incomplete_pagination_fails_closed_at_page_bound() -> None:
    calls: list[str | None] = []

    def list_tools(*, cursor: str | None) -> object:
        calls.append(cursor)
        return _page([], f"cursor-{len(calls)}")

    qualifier = RobinhoodOrderScopeSchemaQualifier(repo_root=Path(__file__).parents[2])
    result = asyncio.run(qualifier.observe(test_tools_list=list_tools))

    assert result.classification is Classification.SCHEMA_MALFORMED
    assert not result.pagination_exhaustive
    assert result.tools_list_pages == 25


def test_caller_cannot_supply_scope_classification() -> None:
    signature = inspect.signature(RobinhoodOrderScopeSchemaQualifier.observe)
    assert "classification" not in signature.parameters
    assert "scope" not in signature.parameters
    with pytest.raises(TypeError):
        RobinhoodOrderScopeSchemaQualifier(  # type: ignore[call-arg]
            repo_root=Path(__file__).parents[2],
            classification=Classification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS,
        )


def test_construction_is_inert_and_schema_observer_invokes_no_provider_tools() -> None:
    qualifier = RobinhoodOrderScopeSchemaQualifier(repo_root=Path(__file__).parents[2])
    tools_list_calls = 0
    provider_tool_calls = 0

    async def list_tools(*, cursor: str | None) -> object:
        nonlocal tools_list_calls
        tools_list_calls += 1
        return _page([_tool()], None)

    assert tools_list_calls == 0
    result = asyncio.run(qualifier.observe(test_tools_list=list_tools))

    assert tools_list_calls == 1
    assert provider_tool_calls == 0
    assert result.classification is Classification.UNPROVEN_PROVIDER_SEMANTICS


def test_evidence_contains_digests_not_raw_provider_material() -> None:
    secret_marker = "provider-raw-text-sentinel-7f3a"
    result, _ = _observe(
        {
            None: _page(
                [_tool(description=f"{secret_marker}. {_EXPLICIT_SCOPE}")],
                f"cursor-{secret_marker}",
            ),
            f"cursor-{secret_marker}": _page([]),
        }
    )
    serialized = repr(dataclasses.asdict(result))

    assert result.classification is Classification.PROVEN_ACCOUNT_WIDE_ALL_AGENTS
    assert secret_marker not in serialized
    assert len(result.evidence_sha256) == 64
    assert len(result.description_sha256 or "") == 64
    assert len(result.input_schema_sha256 or "") == 64


def test_module_has_no_live_effect_or_holdout_dependency() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "trading_bot"
        / "robinhood_mcp"
        / "order_scope_schema_qualifier.py"
    )
    text = source.read_text(encoding="utf-8")

    assert "live_prototype" not in text
    assert "not authenticated" in text
    assert "L43EffectOperator" not in text
    assert "FINAL_HOLDOUT" not in text
    assert "get_equity_orders(" not in text
    assert "get_accounts(" not in text
    assert "get_equity_positions(" not in text
    assert "place_equity_order(" not in text
    assert "review_equity_order(" not in text
    assert "cancel_equity_order(" not in text
