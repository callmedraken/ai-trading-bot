"""131-U source tests use inert constructors and fake provider calls only."""

import ast
import asyncio
import inspect
import json
import subprocess
import webbrowser
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import get_type_hints
from unittest.mock import Mock
from uuid import UUID

import pytest

from trading_bot import robinhood_prepare_operator as module
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper import risk_price_acquisition, supervised_forward_paper
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparation,
    ReviewPaperSupervisedPreparationStatus,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp import sdk_transport, windows_oauth

RUN = module.run_robinhood_published_session_prepare_qualification
DELEGATE = "run_review_paper_published_session_prepare_qualification"
AT = datetime(2026, 10, 2, 16, tzinfo=UTC)


def _inputs(tmp_path):
    return dict(
        session_date=AT.date(),
        store=object(),
        proposal=object(),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=7),
        max_quote_age=timedelta(seconds=60),
        risk_limits=object(),
        new_trading_enabled=True,
        expected_source_head="a" * 40,
        expected_source_tree="b" * 40,
        evidence_path=tmp_path / "evidence.json",
        redirect_uri="http://127.0.0.1:8765/callback",
    )


def test_exact_public_signature():
    types = dict(
        session_date=date,
        store=ReviewPaperStore,
        proposal=TradeProposal,
        opening_buffer=timedelta,
        closing_buffer=timedelta,
        max_quote_age=timedelta,
        risk_limits=RiskLimits,
        new_trading_enabled=bool,
        expected_source_head=str,
        expected_source_tree=str,
        evidence_path=Path,
        redirect_uri=str,
    )
    signature = inspect.signature(RUN)
    assert tuple(signature.parameters) == tuple(types)
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY
        and p.default is inspect.Parameter.empty
        for p in signature.parameters.values()
    )
    assert get_type_hints(RUN) == {
        **types,
        "return": ReviewPaperSupervisedPreparation,
    }
    assert [
        name
        for name, value in vars(module).items()
        if inspect.isfunction(value)
        and value.__module__ == module.__name__
        and not name.startswith("_")
    ] == [RUN.__name__]


@pytest.mark.parametrize("failure", [None, "oauth", "transport", "adapter", "delegate"])
def test_exact_once_sequence_forwarding_and_failure(tmp_path, monkeypatch, failure):
    inputs = _inputs(tmp_path)
    oauth_factory, transport, adapter, result = (object() for _ in range(4))
    error = RuntimeError("boundary failed")
    calls = []
    mocks = {}
    for key, name, value in (
        ("oauth", "create_windows_robinhood_oauth_factory", oauth_factory),
        ("transport", "RobinhoodMcpStreamableHttpTransport", transport),
        ("adapter", "RobinhoodReviewReadAdapter", adapter),
        ("delegate", DELEGATE, result),
    ):

        def invoke(*args, _key=key, _value=value, **kwargs):
            calls.append(_key)
            if failure == _key:
                raise error
            return _value

        mocks[key] = Mock(side_effect=invoke)
        monkeypatch.setattr(module, name, mocks[key])
    if failure:
        with pytest.raises(RuntimeError) as caught:
            RUN(**inputs)
        assert caught.value is error
    else:
        assert RUN(**inputs) is result
    keys = ["oauth", "transport", "adapter", "delegate"]
    expected = keys if failure is None else keys[: keys.index(failure) + 1]
    assert calls == expected
    assert all(mocks[key].call_count == (key in expected) for key in keys)
    mocks["oauth"].assert_called_once_with(
        redirect_uri=inputs["redirect_uri"],
        browser_opener=module._block_interactive_authorization,
    )
    assert mocks["oauth"].call_args.kwargs["redirect_uri"] is inputs["redirect_uri"]
    assert (
        mocks["oauth"].call_args.kwargs["browser_opener"]
        is module._block_interactive_authorization
    )
    if "transport" in expected:
        mocks["transport"].assert_called_once_with(oauth_factory)
        assert mocks["transport"].call_args.args[0] is oauth_factory
    if "adapter" in expected:
        mocks["adapter"].assert_called_once_with(transport)
        assert mocks["adapter"].call_args.args[0] is transport
    if "delegate" in expected:
        forwarded = {
            key: value for key, value in inputs.items() if key != "redirect_uri"
        }
        mocks["delegate"].assert_called_once_with(**forwarded, adapter=adapter)
        for key, value in forwarded.items():
            assert mocks["delegate"].call_args.kwargs[key] is value
        assert mocks["delegate"].call_args.kwargs["adapter"] is adapter
    assert not inputs["evidence_path"].exists()


@pytest.fixture
def effect_guards(monkeypatch):
    guard = Mock(side_effect=AssertionError("unauthorized effect"))
    for owner, name in (
        (windows_oauth.WindowsCredentialApi, "read_generic"),
        (windows_oauth.WindowsOAuthStorage, "get_tokens"),
        (windows_oauth.WindowsOAuthStorage, "get_client_info"),
        (windows_oauth.LoopbackOAuthCallback, "redirect_handler"),
        (windows_oauth.LoopbackOAuthCallback, "callback_handler"),
        (sdk_transport.RobinhoodMcpStreamableHttpTransport, "_request_once"),
        (webbrowser, "open"),
        (subprocess, "Popen"),
        (asyncio, "start_server"),
    ):
        monkeypatch.setattr(owner, name, guard)
    return guard


def test_browser_blocker_is_sanitized_and_has_no_effect(effect_guards):
    material = "https://authorization.invalid/?code=private-material"
    with pytest.raises(windows_oauth.LoopbackOAuthError) as caught:
        module._block_interactive_authorization(material)
    assert str(caught.value) == "Interactive OAuth authorization is forbidden"
    assert material not in str(caught.value) + repr(caught.value)
    effect_guards.assert_not_called()


def test_accepted_constructors_are_inert(tmp_path, monkeypatch, effect_guards):
    # Keep real storage/factory/transport/adapter construction, replacing only
    # the native credential API so no real credential boundary is accessed.
    native = Mock(side_effect=AssertionError("credential access"))
    api = Mock(spec=["read_generic", "write_generic"])
    api.read_generic = native
    api.write_generic = native
    monkeypatch.setattr(windows_oauth, "WindowsCredentialApi", Mock(return_value=api))
    result = object()
    delegate = Mock(return_value=result)
    monkeypatch.setattr(module, DELEGATE, delegate)
    assert RUN(**_inputs(tmp_path)) is result
    delegate.assert_called_once()
    assert (
        type(delegate.call_args.kwargs["adapter"]) is module.RobinhoodReviewReadAdapter
    )
    native.assert_not_called()
    effect_guards.assert_not_called()


def _quote():
    return {
        "symbol": "SPY",
        "adjusted_previous_close": "100",
        "ask_price": "101",
        "bid_price": "99",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "100",
        "previous_close": "100",
        "previous_close_date": None,
        "state": "active",
        "venue_ask_time": AT.isoformat(),
        "venue_bid_time": AT.isoformat(),
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": AT.isoformat(),
    }


@pytest.mark.parametrize("failure", [None, "quote", "reauthorization", "evidence"])
def test_fake_end_to_end_prepare_is_quote_only(
    tmp_path, monkeypatch, effect_guards, failure
):
    inputs = _inputs(tmp_path)
    inputs.update(
        store=ReviewPaperStore(
            tmp_path / "paper.sqlite", starting_cash=Decimal("10000")
        ),
        proposal=TradeProposal(
            UUID(int=1), Symbol("SPY"), OrderSide.BUY, Decimal("1"), AT, "test"
        ),
        risk_limits=RiskLimits(),
    )
    calls = []
    error = RuntimeError("fake quote failure")
    oauth_factory = Mock(side_effect=AssertionError("authentication"))

    def oauth(*, redirect_uri, browser_opener):
        assert redirect_uri is inputs["redirect_uri"]
        authorization["browser_opener"] = browser_opener
        return oauth_factory

    authorization = {}

    async def caller(name, arguments):
        calls.append((name, arguments))
        assert name == "get_equity_quotes"
        if failure == "quote":
            raise error
        if failure == "reauthorization":
            authorization["browser_opener"](
                "https://authorization.invalid/?code=private"
            )
        return {"data": {"results": [{"quote": _quote(), "close": None}]}}

    transport = sdk_transport.RobinhoodMcpStreamableHttpTransport.for_test(caller)
    constructor = Mock(return_value=transport)
    factory = Mock(side_effect=oauth)
    monkeypatch.setattr(module, "create_windows_robinhood_oauth_factory", factory)
    monkeypatch.setattr(module, "RobinhoodMcpStreamableHttpTransport", constructor)
    clock = Mock()
    clock.now.return_value = AT
    monkeypatch.setattr(supervised_forward_paper, "datetime", clock)
    monkeypatch.setattr(risk_price_acquisition, "datetime", clock)
    execute = Mock(side_effect=AssertionError("EXECUTE"))
    monkeypatch.setattr(
        supervised_forward_paper, "execute_review_paper_supervised_cycle", execute
    )
    monkeypatch.setattr(
        supervised_forward_paper, "run_robinhood_forward_paper_cycle", execute
    )
    lookup = Mock(wraps=NYSEPublishedRegularSessionAuthority.schedule_for)
    monkeypatch.setattr(
        NYSEPublishedRegularSessionAuthority,
        "schedule_for",
        lambda self, value: lookup(self, value),
    )
    delegate = Mock(wraps=getattr(module, DELEGATE))
    monkeypatch.setattr(module, DELEGATE, delegate)
    before = inputs["store"].path.read_bytes()
    publication_calls = []
    original_open = Path.open

    def open_path(path, *args, **kwargs):
        if path == inputs["evidence_path"] and args == ("x",):
            publication_calls.append(path)
            if failure == "evidence":
                raise error
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)
    if failure:
        exception = (
            RuntimeError
            if failure in {"quote", "evidence"}
            else windows_oauth.LoopbackOAuthError
        )
        with pytest.raises(exception) as caught:
            RUN(**inputs)
        if failure in {"quote", "evidence"}:
            assert caught.value is error
        assert not inputs["evidence_path"].exists()
    else:
        result = RUN(**inputs)
        assert result.status is ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
        assert result.store is inputs["store"] and result.proposal is inputs["proposal"]
        evidence = json.loads(inputs["evidence_path"].read_text())
        assert evidence["execute_invoked"] is False
        assert evidence["pipeline_result_present"] is False
        assert evidence["durable_before"] == evidence["durable_after"]
    assert calls == [("get_equity_quotes", {"symbols": ["SPY"]})]
    factory.assert_called_once_with(
        redirect_uri=inputs["redirect_uri"],
        browser_opener=module._block_interactive_authorization,
    )
    constructor.assert_called_once_with(oauth_factory)
    assert publication_calls == (
        [inputs["evidence_path"]] if failure in {None, "evidence"} else []
    )
    delegate.assert_called_once()
    lookup.assert_called_once()
    assert lookup.call_args.args[1] is inputs["session_date"]
    assert inputs["store"].path.read_bytes() == before
    execute.assert_not_called()
    oauth_factory.assert_not_called()
    effect_guards.assert_not_called()


def _assert_prepare_only_source(source):
    tree = ast.parse(source)
    imports = {
        "__future__": {"annotations"},
        "datetime": {"date", "timedelta"},
        "pathlib": {"Path"},
        "trading_bot.domain": {"TradeProposal"},
        "trading_bot.review_paper.published_session_prepare": {DELEGATE},
        "trading_bot.review_paper.store": {"ReviewPaperStore"},
        "trading_bot.review_paper.supervised_forward_paper": {
            "ReviewPaperSupervisedPreparation"
        },
        "trading_bot.risk.models": {"RiskLimits"},
        "trading_bot.robinhood_mcp.adapter": {"RobinhoodReviewReadAdapter"},
        "trading_bot.robinhood_mcp.sdk_transport": {
            "RobinhoodMcpStreamableHttpTransport"
        },
        "trading_bot.robinhood_mcp.windows_oauth": {
            "LoopbackOAuthError",
            "create_windows_robinhood_oauth_factory",
        },
    }
    assert all(
        isinstance(n, (ast.Expr, ast.ImportFrom, ast.FunctionDef)) for n in tree.body
    )
    names = {alias for values in imports.values() for alias in values} | {
        "url",
        "str",
        "object",
        "bool",
        "session_date",
        "store",
        "proposal",
        "opening_buffer",
        "closing_buffer",
        "max_quote_age",
        "risk_limits",
        "new_trading_enabled",
        "expected_source_head",
        "expected_source_tree",
        "evidence_path",
        "redirect_uri",
        "oauth_factory",
        "transport",
        "adapter",
        "_block_interactive_authorization",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id in names
        assert not isinstance(node, ast.Attribute)
        assert not isinstance(
            node,
            (
                ast.Import,
                ast.For,
                ast.While,
                ast.Try,
                ast.If,
                ast.With,
                ast.AsyncFunctionDef,
                ast.Lambda,
            ),
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module in imports
            assert {alias.name for alias in node.names} <= imports[node.module]
            assert all(alias.asname is None for alias in node.names)
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name)
            assert node.func.id in {
                "LoopbackOAuthError",
                "create_windows_robinhood_oauth_factory",
                "RobinhoodMcpStreamableHttpTransport",
                "RobinhoodReviewReadAdapter",
                DELEGATE,
            }
    assert {n.name for n in tree.body if isinstance(n, ast.FunctionDef)} == {
        RUN.__name__,
        "_block_interactive_authorization",
    }


def test_source_imports_and_calls_have_no_other_capability():
    _assert_prepare_only_source(Path(module.__file__).read_text(encoding="utf-8"))


_FORBIDDEN = [
    "import os",
    "import webbrowser",
    "import subprocess",
    "import time",
    "from trading_bot.execution.models import ExecutionInstruction",
    "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
    (
        "from trading_bot.robinhood_paper_pipeline import "
        "run_robinhood_deterministic_paper_pipeline"
    ),
    (
        "from trading_bot.review_paper.supervised_forward_paper import "
        "execute_review_paper_supervised_cycle"
    ),
    "run_robinhood_forward_paper_cycle()",
    "build_review_paper_intent()",
    "uuid4()",
    "execute_review_paper_supervised_cycle",
    "adapter.review_equity_order",
    "transport.get_accounts()",
    "adapter.equity_orders()",
    "transport.get_equity_orders()",
    "transport.review_equity_order()",
    "adapter.equity_quotes()",
    "resolve_account()",
    "place_order()",
    "cancel_order()",
    "options_mutation()",
    "crypto_mutation()",
    "storage.get_tokens()",
    "storage.get_client_info()",
    "api.read_generic()",
    "retry()",
    "poll()",
    "sleep(1)",
    "scheduler.run()",
    "config.read()",
    "environ.get('SESSION_DATE')",
    "date.today()",
    "while True: pass",
]


@pytest.mark.parametrize("addition", _FORBIDDEN)
def test_source_guard_rejects_forbidden_capabilities(addition):
    source = Path(module.__file__).read_text(encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_prepare_only_source(source + "\n" + addition + "\n")
