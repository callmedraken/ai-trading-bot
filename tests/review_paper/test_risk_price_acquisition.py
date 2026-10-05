"""Architecture 131-P bounded acquisition through a real adapter and fake transport."""

import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

import trading_bot.review_paper.risk_price_acquisition as module
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.review_paper.models import (
    ReviewPaperIntent,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
)
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk import RiskManager, RiskOutcome
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.models import RobinhoodMcpSchemaError

AT = datetime(2026, 10, 3, 16, tzinfo=UTC)
AGE = timedelta(minutes=1)
SPY = Symbol("SPY")


def _proposal(symbol=SPY):
    return TradeProposal(UUID(int=1), symbol, OrderSide.BUY, Decimal("1"), AT, "test")


def _quote(symbol_value, **changes):
    return {
        "symbol": symbol_value,
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
        **changes,
    }


class FakeTransport:
    def __init__(self, *, changes=None, error=None, payload=None):
        self.calls = []
        self.changes = changes or {}
        self.error = error
        self.payload = payload

    def get_equity_quotes(self, arguments):
        self.calls.append(("get_equity_quotes", arguments))
        if self.error is not None:
            raise self.error
        if self.payload is not None:
            return self.payload
        return {
            "data": {
                "results": [
                    {"quote": _quote(symbol, **self.changes), "close": None}
                    for symbol in reversed(arguments["symbols"])
                ]
            }
        }

    def __getattr__(self, name):
        raise AssertionError(f"forbidden transport access: {name}")


@pytest.fixture
def store(tmp_path):
    return ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    clock = Mock()
    clock.now.return_value = AT
    monkeypatch.setattr(module, "datetime", clock)
    return clock


def _acquire(store, transport=None, **changes):
    transport = FakeTransport() if transport is None else transport
    return module.acquire_review_paper_risk_price_snapshot(
        **{
            "store": store,
            "proposal": _proposal(),
            "adapter": RobinhoodReviewReadAdapter(transport),
            "max_quote_age": AGE,
            **changes,
        }
    )


def _seed(store, symbol, identity):
    intent = ReviewPaperIntent(
        proposal_id=UUID(int=identity),
        order_id=UUID(int=identity + 100),
        symbol=symbol,
        side=OrderSide.BUY,
        desired_quantity=Decimal("1"),
        approved_quantity=Decimal("1"),
        risk_outcome=RiskOutcome.APPROVED,
        risk_reason_codes=(),
        proposal_reason="fixture",
        proposal_confidence=None,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        proposed_at=AT,
    )
    quote = RobinhoodReviewQuote(
        **{
            **_quote(symbol),
            **{
                name: Decimal(value)
                for name, value in _quote(symbol).items()
                if name.endswith("price")
                or name in ("adjusted_previous_close", "previous_close")
                if value is not None
            },
            "venue_ask_time": AT,
            "venue_bid_time": AT,
            "venue_last_trade_time": AT,
        }
    )
    review = RobinhoodEquityOrderReview(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        quote=quote,
        order_checks_json="{}",
        reviewed_at=AT,
        market_data_disclosure=None,
    )
    store.record_market_review(intent, review)


@pytest.mark.parametrize(
    "positions,proposal,expected",
    [
        ((), "SPY", ("SPY",)),
        (("SPY",), "SPY", ("SPY",)),
        (("SPY", "QQQ"), "AAPL", ("AAPL", "QQQ", "SPY")),
        (("Z", "AA", "A"), "AA", ("A", "AA", "Z")),
    ],
)
def test_durable_symbols_canonical_and_unique(
    store, monkeypatch, frozen_clock, positions, proposal, expected
):
    for identity, symbol in enumerate(positions, 2):
        _seed(store, Symbol(symbol), identity)
    before = store.path.read_bytes()
    reconstruct = Mock(wraps=store.reconstruct_ledger)
    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    transport = FakeTransport()
    result = _acquire(store, transport, proposal=_proposal(Symbol(proposal)))
    assert tuple(str(mark.symbol) for mark in result.marks) == expected
    assert transport.calls == [("get_equity_quotes", {"symbols": list(expected)})]
    reconstruct.assert_called_once_with()
    frozen_clock.now.assert_called_once_with(UTC)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("count", [20, 21])
@pytest.mark.parametrize("new_proposal", [False, True])
def test_symbol_bound_before_adapter_access(
    store, monkeypatch, frozen_clock, count, new_proposal
):
    symbols = tuple(Symbol(f"S{i:02d}") for i in range(count))
    proposal = _proposal(symbols[-1] if new_proposal else symbols[0])
    positions = symbols[:-1] if new_proposal else symbols
    # Only the positions keys are available: account/risk fields would fail.
    reconstruct = Mock(return_value=SimpleNamespace(positions=dict.fromkeys(positions)))
    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    original = RobinhoodReviewReadAdapter.equity_quotes
    quotes = Mock()

    def counted_quotes(self, symbols):
        quotes(symbols)
        return original(self, symbols)

    monkeypatch.setattr(RobinhoodReviewReadAdapter, "equity_quotes", counted_quotes)
    transport = FakeTransport()
    adapter = RobinhoodReviewReadAdapter(transport)
    if count == 21:
        with pytest.raises(ValueError, match="20 symbols"):
            _acquire(store, transport, adapter=adapter, proposal=proposal)
        quotes.assert_not_called()
        frozen_clock.now.assert_not_called()
        assert transport.calls == []
    else:
        result = _acquire(store, transport, adapter=adapter, proposal=proposal)
        assert len(result.marks) == 20
        quotes.assert_called_once_with(symbols)
        assert len(transport.calls) == 1
    reconstruct.assert_called_once_with()


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("store", object(), TypeError),
        ("proposal", object(), TypeError),
        ("adapter", object(), TypeError),
        ("max_quote_age", 60, TypeError),
        ("max_quote_age", None, TypeError),
        ("max_quote_age", timedelta(0), ValueError),
        ("max_quote_age", timedelta(seconds=-1), ValueError),
    ],
)
def test_invalid_admission_has_zero_effects(
    store, monkeypatch, frozen_clock, field, value, error
):
    reconstruct = Mock(side_effect=AssertionError("premature reconstruction"))
    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    transport = FakeTransport()
    with pytest.raises(error):
        _acquire(store, transport, **{field: value})
    reconstruct.assert_not_called()
    frozen_clock.now.assert_not_called()
    assert transport.calls == []


@pytest.mark.parametrize("field", ["store", "proposal", "adapter", "max_quote_age"])
def test_subclasses_fail_exact_admission(store, monkeypatch, frozen_clock, field):
    transport = FakeTransport()
    values = {
        "store": store,
        "proposal": _proposal(),
        "adapter": RobinhoodReviewReadAdapter(transport),
        "max_quote_age": AGE,
    }
    original = values[field]
    subclass = type("Subclass", (type(original),), {})
    if field == "max_quote_age":
        values[field] = subclass(seconds=60)
    elif field == "proposal":
        values[field] = subclass(
            UUID(int=1), SPY, OrderSide.BUY, Decimal("1"), AT, "test"
        )
    elif field == "adapter":
        values[field] = subclass(transport)
    else:
        values[field] = object.__new__(subclass)
    reconstruct = Mock()
    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    with pytest.raises(TypeError):
        module.acquire_review_paper_risk_price_snapshot(**values)
    assert transport.calls == []
    reconstruct.assert_not_called()
    frozen_clock.now.assert_not_called()


def test_exact_order_and_delegation_identity(store, monkeypatch, frozen_clock):
    events = []
    original_reconstruct = store.reconstruct_ledger

    def reconstruct():
        events.append("store reconstruction")
        return original_reconstruct()

    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    original_quotes = RobinhoodReviewReadAdapter.equity_quotes
    captured = {}

    def quotes(self, symbols):
        response = original_quotes(self, symbols)
        captured.update(response=response, symbols=symbols)
        events.append("equity_quotes returns")
        return response

    monkeypatch.setattr(RobinhoodReviewReadAdapter, "equity_quotes", quotes)

    def now(zone):
        assert zone is UTC
        events.append("clock read")
        return AT

    frozen_clock.now.side_effect = now
    snapshot = ReviewPaperRiskPriceSnapshot(
        AT, (ReviewPaperRiskPriceMark(SPY, Decimal("100"), AT),)
    )

    def builder(**arguments):
        events.append("131-N builder")
        assert arguments["response"] is captured["response"]
        assert arguments["required_symbols"] is captured["symbols"]
        assert type(captured["symbols"]) is tuple and captured["symbols"] == (SPY,)
        assert arguments["observed_at"] is AT
        assert arguments["max_quote_age"] is AGE
        return snapshot

    build = Mock(side_effect=builder)
    monkeypatch.setattr(module, "build_review_paper_risk_price_snapshot", build)
    transport = FakeTransport()
    assert _acquire(store, transport) is snapshot
    assert events == [
        "store reconstruction",
        "equity_quotes returns",
        "clock read",
        "131-N builder",
    ]
    build.assert_called_once()
    frozen_clock.now.assert_called_once_with(UTC)
    assert len(transport.calls) == 1


def test_reconstruction_exception_propagates_without_provider(
    store, monkeypatch, frozen_clock
):
    error = RuntimeError("durable history failure")
    reconstruct = Mock(side_effect=error)
    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    transport = FakeTransport()
    with pytest.raises(RuntimeError) as caught:
        _acquire(store, transport)
    assert caught.value is error
    reconstruct.assert_called_once_with()
    assert transport.calls == []
    frozen_clock.now.assert_not_called()


@pytest.mark.parametrize("failure", ["provider", "parser"])
def test_adapter_failure_propagates_once_without_clock_or_builder(
    store, monkeypatch, frozen_clock, failure
):
    error = RuntimeError("provider failure")
    transport = (
        FakeTransport(error=error)
        if failure == "provider"
        else FakeTransport(payload={"data": {"results": "invalid"}})
    )
    build = Mock(side_effect=AssertionError("builder after adapter failure"))
    monkeypatch.setattr(module, "build_review_paper_risk_price_snapshot", build)
    expected = RuntimeError if failure == "provider" else RobinhoodMcpSchemaError
    with pytest.raises(expected) as caught:
        _acquire(store, transport)
    if failure == "provider":
        assert caught.value is error
    assert len(transport.calls) == 1
    frozen_clock.now.assert_not_called()
    build.assert_not_called()


@pytest.mark.parametrize(
    "changes,message",
    [
        (
            {"venue_last_trade_time": (AT - AGE - timedelta(seconds=1)).isoformat()},
            "stale",
        ),
        ({"venue_last_trade_time": (AT + timedelta(seconds=1)).isoformat()}, "future"),
        ({"state": "inactive"}, "not active"),
        ({"has_traded": False}, "never traded"),
        ({"last_trade_price": "0"}, "positive"),
        ({"symbol": "QQQ"}, "exactly match"),
    ],
)
def test_131n_rejection_propagates_without_reacquisition(
    store, monkeypatch, frozen_clock, changes, message
):
    build = Mock(wraps=module.build_review_paper_risk_price_snapshot)
    monkeypatch.setattr(module, "build_review_paper_risk_price_snapshot", build)
    transport = FakeTransport(changes=changes)
    with pytest.raises(ValueError, match=message):
        _acquire(store, transport)
    assert len(transport.calls) == 1
    build.assert_called_once()
    frozen_clock.now.assert_called_once_with(UTC)


def test_builder_exception_identity_propagates(store, monkeypatch):
    error = ValueError("131-N rejection")
    build = Mock(side_effect=error)
    monkeypatch.setattr(module, "build_review_paper_risk_price_snapshot", build)
    transport = FakeTransport()
    with pytest.raises(ValueError) as caught:
        _acquire(store, transport)
    assert caught.value is error
    build.assert_called_once()
    assert len(transport.calls) == 1


def test_no_risk_account_order_or_durable_effects(store, monkeypatch):
    before = store.path.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden capability")

    for name in ("record_market_review", "create_account_snapshot", "_initialize"):
        monkeypatch.setattr(store, name, forbidden)
    for name in ("review_market_order", "agentic_equity_orders"):
        monkeypatch.setattr(RobinhoodReviewReadAdapter, name, forbidden)
    monkeypatch.setattr(RiskManager, "evaluate", forbidden)
    import trading_bot.review_paper.risk_context as risk_context

    monkeypatch.setattr(risk_context, "build_review_paper_risk_context", forbidden)
    _acquire(store)
    assert store.path.read_bytes() == before


def test_frozen_module_capability_surface():
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    assert all(
        isinstance(node, (ast.Expr, ast.ImportFrom, ast.FunctionDef))
        for node in tree.body
    )
    imports = {
        node.module: tuple(alias.name for alias in node.names)
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__": ("annotations",),
        "datetime": ("UTC", "datetime", "timedelta"),
        "trading_bot.domain": ("TradeProposal",),
        "trading_bot.review_paper.risk_prices": (
            "ReviewPaperRiskPriceSnapshot",
            "build_review_paper_risk_price_snapshot",
        ),
        "trading_bot.review_paper.store": ("ReviewPaperStore",),
        "trading_bot.robinhood_mcp.adapter": ("RobinhoodReviewReadAdapter",),
    }
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert len(functions) == 1
    function = functions[0]
    assert function.name == "acquire_review_paper_risk_price_snapshot"
    assert function.args.args == [] and function.args.posonlyargs == []
    assert [arg.arg for arg in function.args.kwonlyargs] == [
        "store",
        "proposal",
        "adapter",
        "max_quote_age",
    ]
    assert function.args.kw_defaults == [None] * 4
    assert function.args.vararg is None and function.args.kwarg is None
    assert ast.unparse(function.returns) == "ReviewPaperRiskPriceSnapshot"
    assert not any(
        isinstance(
            node,
            (ast.For, ast.While, ast.Try, ast.With, ast.ListComp, ast.GeneratorExp),
        )
        for node in ast.walk(tree)
    )
    calls = [
        ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)
    ]
    assert sorted(calls) == sorted(
        [
            "type",
            "type",
            "type",
            "type",
            "TypeError",
            "TypeError",
            "TypeError",
            "TypeError",
            "timedelta",
            "ValueError",
            "store.reconstruct_ledger",
            "tuple",
            "sorted",
            "set",
            "len",
            "ValueError",
            "adapter.equity_quotes",
            "datetime.now",
            "build_review_paper_risk_price_snapshot",
        ]
    )
    attributes = {
        ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert attributes == {
        "store.reconstruct_ledger",
        "ledger.positions",
        "proposal.symbol",
        "adapter.equity_quotes",
        "datetime.now",
    }
    ordered = [
        ast.unparse(node.value)
        for node in function.body
        if isinstance(node, ast.Assign)
    ]
    assert ordered == [
        "store.reconstruct_ledger()",
        "tuple(sorted(set(ledger.positions) | {proposal.symbol}, key=str))",
        "adapter.equity_quotes(required_symbols)",
        "datetime.now(UTC)",
    ]
    returned = function.body[-1]
    assert isinstance(returned, ast.Return)
    assert ast.unparse(returned.value) == (
        "build_review_paper_risk_price_snapshot(response=response, "
        "required_symbols=required_symbols, observed_at=observed_at, "
        "max_quote_age=max_quote_age)"
    )


def test_parser_exception_identity_propagates_once(store, monkeypatch, frozen_clock):
    import trading_bot.robinhood_mcp.adapter as adapter_module

    error = RobinhoodMcpSchemaError("parser failure")
    parse = Mock(side_effect=error)
    monkeypatch.setattr(adapter_module, "parse_equity_quotes_response", parse)
    build = Mock(side_effect=AssertionError("builder after parsing failure"))
    monkeypatch.setattr(module, "build_review_paper_risk_price_snapshot", build)
    transport = FakeTransport()
    with pytest.raises(RobinhoodMcpSchemaError) as caught:
        _acquire(store, transport)
    assert caught.value is error
    assert len(transport.calls) == 1
    parse.assert_called_once()
    build.assert_not_called()
    frozen_clock.now.assert_not_called()
