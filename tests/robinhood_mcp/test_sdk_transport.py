from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from trading_bot.robinhood_mcp.sdk_transport import (
    _ALLOWED_TOOL_NAMES,
    ROBINHOOD_TRADING_MCP_URL,
    RobinhoodMcpEventLoopError,
    RobinhoodMcpStreamableHttpTransport,
    RobinhoodMcpStructuredResultError,
    RobinhoodMcpToolCallError,
    RobinhoodMcpToolUnavailableError,
    _require_loopback_redirect_uri,
    _require_review_read_tools,
    _structured_result,
    create_robinhood_oauth_factory,
)


def test_test_transport_calls_only_exact_public_tool_names() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def caller(
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        calls.append((tool_name, dict(arguments)))
        return {"data": {"ok": True}}

    transport = RobinhoodMcpStreamableHttpTransport.for_test(caller)

    assert transport.review_equity_order({"symbol": "SPY"})["data"] == {"ok": True}
    assert transport.get_equity_quotes({"symbols": ["SPY"]})["data"] == {"ok": True}
    assert transport.get_equity_orders({"account_number": "agent"})["data"] == {
        "ok": True
    }
    assert [name for name, _ in calls] == [
        "review_equity_order",
        "get_equity_quotes",
        "get_equity_orders",
    ]


def test_blocking_transport_rejects_active_event_loop() -> None:
    async def caller(
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        del tool_name, arguments
        return {"data": {}}

    transport = RobinhoodMcpStreamableHttpTransport.for_test(caller)

    async def inside_loop() -> None:
        with pytest.raises(RobinhoodMcpEventLoopError):
            transport.get_equity_quotes({"symbols": ["SPY"]})

    asyncio.run(inside_loop())


def test_structured_result_requires_success_and_mapping() -> None:
    ok = SimpleNamespace(is_error=False, structured_content={"data": {"x": 1}})
    assert _structured_result("get_equity_quotes", ok) == {"data": {"x": 1}}

    with pytest.raises(RobinhoodMcpToolCallError):
        _structured_result(
            "get_equity_quotes",
            SimpleNamespace(is_error=True, structured_content=None),
        )
    with pytest.raises(RobinhoodMcpStructuredResultError):
        _structured_result(
            "get_equity_quotes",
            SimpleNamespace(is_error=False, structured_content=None),
        )
    with pytest.raises(RobinhoodMcpToolUnavailableError):
        _structured_result(
            "not_allowed",
            SimpleNamespace(is_error=False, structured_content={}),
        )


def test_tool_inventory_requires_all_three_tools_and_bounded_pagination() -> None:
    class Client:
        def __init__(self) -> None:
            self.calls: list[str | None] = []

        async def list_tools(self, *, cursor: str | None = None):
            self.calls.append(cursor)
            if cursor is None:
                return SimpleNamespace(
                    tools=[
                        SimpleNamespace(name="review_equity_order"),
                        SimpleNamespace(name="get_equity_quotes"),
                    ],
                    next_cursor="page-2",
                )
            return SimpleNamespace(
                tools=[SimpleNamespace(name="get_equity_orders")],
                next_cursor=None,
            )

    client = Client()
    asyncio.run(_require_review_read_tools(client))
    assert client.calls == [None, "page-2"]


def test_tool_inventory_rejects_missing_or_repeated_cursor() -> None:
    class MissingClient:
        async def list_tools(self, *, cursor: str | None = None):
            del cursor
            return SimpleNamespace(
                tools=[SimpleNamespace(name="get_equity_quotes")],
                next_cursor=None,
            )

    with pytest.raises(RobinhoodMcpToolUnavailableError, match="unavailable"):
        asyncio.run(_require_review_read_tools(MissingClient()))

    class RepeatingClient:
        async def list_tools(self, *, cursor: str | None = None):
            del cursor
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(name="review_equity_order"),
                    SimpleNamespace(name="get_equity_quotes"),
                ],
                next_cursor="same",
            )

    with pytest.raises(RobinhoodMcpToolUnavailableError, match="cursor repeated"):
        asyncio.run(_require_review_read_tools(RepeatingClient()))


def test_loopback_redirect_uri_is_fail_closed() -> None:
    assert (
        _require_loopback_redirect_uri("http://127.0.0.1:8765/callback")
        == "http://127.0.0.1:8765/callback"
    )
    assert (
        _require_loopback_redirect_uri("http://localhost:8765/callback")
        == "http://localhost:8765/callback"
    )
    for value in (
        "https://localhost:8765/callback",
        "http://example.com:8765/callback",
        "http://localhost/callback",
        "http://localhost:8765/",
        "http://user@localhost:8765/callback",
        "http://localhost:8765/callback?token=x",
    ):
        with pytest.raises(ValueError):
            _require_loopback_redirect_uri(value)


def test_oauth_factory_validates_storage_without_importing_optional_sdk() -> None:
    class Storage:
        async def get_tokens(self):
            return None

        async def set_tokens(self, value) -> None:
            del value

        async def get_client_info(self):
            return None

        async def set_client_info(self, value) -> None:
            del value

    async def redirect_handler(url: str) -> None:
        del url

    async def callback_handler():
        return object()

    factory = create_robinhood_oauth_factory(
        storage=Storage(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        redirect_uri="http://127.0.0.1:8765/callback",
    )

    assert callable(factory)
    assert ROBINHOOD_TRADING_MCP_URL == "https://agent.robinhood.com/mcp/trading"


def test_oauth_factory_rejects_non_token_storage() -> None:
    async def redirect_handler(url: str) -> None:
        del url

    async def callback_handler():
        return object()

    with pytest.raises(TypeError, match="TokenStorage"):
        create_robinhood_oauth_factory(
            storage=object(),
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
            redirect_uri="http://127.0.0.1:8765/callback",
        )


def test_public_facade_and_allowlist_remain_exact() -> None:
    from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadTransport

    expected = {"review_equity_order", "get_equity_quotes", "get_equity_orders"}
    assert _ALLOWED_TOOL_NAMES == (
        "get_equity_orders",
        "get_equity_quotes",
        "review_equity_order",
    )
    assert {
        name
        for name in vars(RobinhoodMcpStreamableHttpTransport)
        if not name.startswith("_")
    } == expected | {"for_test"}
    assert {
        name for name in vars(RobinhoodReviewReadTransport) if not name.startswith("_")
    } == expected

    async def caller(name, arguments):
        raise AssertionError("nonpublic tool must not reach caller")

    transport = RobinhoodMcpStreamableHttpTransport.for_test(caller)
    with pytest.raises(RobinhoodMcpToolUnavailableError):
        transport._invoke("get_accounts", {})
    with pytest.raises(RobinhoodMcpToolUnavailableError):
        asyncio.run(transport._call_tool_once("get_accounts", {}))
    with pytest.raises(RobinhoodMcpToolUnavailableError):
        _structured_result("get_accounts", object())


@pytest.mark.parametrize("advertised", [False, True])
def test_internal_account_resolution_requires_account_inventory(advertised) -> None:
    class Client:
        async def list_tools(self, *, cursor=None):
            names = list(_ALLOWED_TOOL_NAMES)
            if advertised:
                names.append("get_accounts")
            return SimpleNamespace(
                tools=[SimpleNamespace(name=name) for name in names], next_cursor=None
            )

    if advertised:
        asyncio.run(_require_review_read_tools(Client(), require_accounts=True))
    else:
        with pytest.raises(RobinhoodMcpToolUnavailableError):
            asyncio.run(_require_review_read_tools(Client(), require_accounts=True))
