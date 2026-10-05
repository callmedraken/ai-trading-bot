from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from trading_bot.robinhood_mcp import (
    RobinhoodAgenticAccountResolutionError,
    RobinhoodAgenticAccountResolver,
    RobinhoodMcpStreamableHttpTransport,
    create_robinhood_agentic_account_resolver,
)


def _account(number="canonical-agent", allowed=True):
    return {"account_number": number, "agentic_allowed": allowed}


def _resolver(accounts):
    return RobinhoodAgenticAccountResolver(lambda: {"data": {"accounts": accounts}})


def test_unique_eligible_account_resolves_exactly_without_cache():
    calls = []

    async def caller(name, arguments):
        calls.append((name, arguments))
        return {"data": {"accounts": [_account("ordinary", False), _account()]}}

    transport = RobinhoodMcpStreamableHttpTransport.for_test(caller)
    resolver = create_robinhood_agentic_account_resolver(transport)
    assert resolver.resolve() == "canonical-agent"
    assert resolver.resolve() == "canonical-agent"
    assert calls == [("get_accounts", {}), ("get_accounts", {})]
    assert "canonical-agent" not in repr(resolver)


@pytest.mark.parametrize(
    "accounts",
    [
        [],
        [_account(allowed=False)],
        [_account(), _account("second")],
        [_account(), _account()],
    ],
)
def test_zero_or_multiple_eligible_accounts_fail(accounts):
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        _resolver(accounts).resolve()


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        "text",
        {},
        {"data": None},
        {"data": []},
        {"data": {}},
        {"data": {"accounts": None}},
        {"data": {"accounts": {}}},
        {"data": {"accounts": "text"}},
        {"data": {"accounts": (_account(),)}},
    ],
)
def test_malformed_root_data_accounts_fail(response):
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        RobinhoodAgenticAccountResolver(lambda: response).resolve()


@pytest.mark.parametrize(
    "record",
    [
        None,
        [],
        "text",
        {},
        {"account_number": "ordinary"},
        _account(allowed=None),
        _account(allowed="true"),
        _account(allowed=1),
        _account(allowed=0),
        _account(allowed=[]),
        _account(allowed={}),
    ],
)
def test_malformed_records_or_eligibility_fail_even_beside_valid_account(record):
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        _resolver([_account(), record]).resolve()


@pytest.mark.parametrize(
    "number",
    [
        None,
        123,
        True,
        "",
        " ",
        " canonical-agent",
        "canonical-agent ",
        "a b",
        "a\nb",
        "a\x00b",
        "a\x7fb",
        "x" * 129,
    ],
)
@pytest.mark.parametrize("allowed", [True, False])
def test_invalid_account_numbers_fail(number, allowed):
    with pytest.raises(RobinhoodAgenticAccountResolutionError) as exc:
        _resolver([_account(), _account(number, allowed)]).resolve()
    assert "canonical-agent" not in str(exc.value)


@pytest.mark.parametrize("number", [None, "", " "])
def test_rhs_account_number_is_never_a_fallback(number):
    record = _account(number)
    record["rhs_account_number"] = "rhs-fallback"
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        _resolver([record]).resolve()


def test_missing_account_number_is_never_replaced_by_rhs():
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        _resolver([{"agentic_allowed": True, "rhs_account_number": "rhs"}]).resolve()


def test_unexpected_caller_error_is_sanitized():
    def read_accounts():
        raise RuntimeError("sensitive-account")

    with pytest.raises(RobinhoodAgenticAccountResolutionError) as exc:
        RobinhoodAgenticAccountResolver(read_accounts).resolve()
    assert "sensitive-account" not in str(exc.value)
    assert exc.value.__suppress_context__


def _fake_sdk(monkeypatch, result, *, names=None, failure=None):
    calls = []

    class Context:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class Client(Context):
        async def list_tools(self, *, cursor=None):
            calls.append(("inventory", cursor))
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(name=name)
                    for name in (
                        names
                        if names is not None
                        else [
                            "get_equity_orders",
                            "get_equity_quotes",
                            "review_equity_order",
                            "get_accounts",
                        ]
                    )
                ],
                next_cursor=None,
            )

        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            if failure:
                raise failure
            return result

    monkeypatch.setitem(sys.modules, "httpx2", SimpleNamespace(AsyncClient=Context))
    monkeypatch.setitem(sys.modules, "mcp", SimpleNamespace(Client=Client))
    monkeypatch.setitem(
        sys.modules,
        "mcp.client.streamable_http",
        SimpleNamespace(streamable_http_client=lambda *args, **kwargs: object()),
    )
    transport = RobinhoodMcpStreamableHttpTransport(lambda: object())
    return create_robinhood_agentic_account_resolver(transport), calls


def test_production_path_calls_only_internal_accounts_with_empty_args(monkeypatch):
    result = SimpleNamespace(
        is_error=False, structured_content={"data": {"accounts": [_account()]}}
    )
    resolver, calls = _fake_sdk(monkeypatch, result)
    assert resolver.resolve() == "canonical-agent"
    assert calls == [("inventory", None), ("get_accounts", {})]


@pytest.mark.parametrize(
    "result",
    [
        SimpleNamespace(
            is_error=True, structured_content={"data": {"accounts": [_account()]}}
        ),
        SimpleNamespace(
            isError=True, structuredContent={"data": {"accounts": [_account()]}}
        ),
        SimpleNamespace(is_error=None, structured_content={}),
        SimpleNamespace(is_error=0, structured_content={}),
        SimpleNamespace(is_error=False),
        SimpleNamespace(is_error=False, structured_content=None),
        SimpleNamespace(is_error=False, structured_content=[]),
        SimpleNamespace(is_error=False, structured_content="text"),
        object(),
    ],
)
def test_tool_error_or_missing_structured_content_fail(monkeypatch, result):
    resolver, _ = _fake_sdk(monkeypatch, result)
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        resolver.resolve()


def test_missing_account_tool_prevents_call(monkeypatch):
    resolver, calls = _fake_sdk(
        monkeypatch,
        object(),
        names=["get_equity_orders", "get_equity_quotes", "review_equity_order"],
    )
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        resolver.resolve()
    assert calls == [("inventory", None)]


def test_unexpected_session_failure_fails_closed(monkeypatch):
    resolver, _ = _fake_sdk(monkeypatch, object(), failure=RuntimeError("sensitive"))
    with pytest.raises(RobinhoodAgenticAccountResolutionError, match="request failed"):
        resolver.resolve()


def test_resolver_rejects_active_event_loop_before_call():
    calls = []

    async def caller(name, arguments):
        calls.append(name)
        return {}

    resolver = create_robinhood_agentic_account_resolver(
        RobinhoodMcpStreamableHttpTransport.for_test(caller)
    )

    async def inside_loop():
        with pytest.raises(RobinhoodAgenticAccountResolutionError):
            resolver.resolve()

    asyncio.run(inside_loop())
    assert calls == []
