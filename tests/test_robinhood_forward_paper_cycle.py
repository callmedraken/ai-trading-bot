from __future__ import annotations

import ast
import inspect
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from trading_bot import robinhood_forward_paper_cycle as cycle
from trading_bot import robinhood_paper_pipeline as pipeline
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper import ReviewPaperStore, build_review_paper_risk_context
from trading_bot.risk import RiskLimits, RiskManager, RiskOutcome
from trading_bot.robinhood_paper_operator import RobinhoodPaperOperatorEvidence

NOW = datetime(2026, 10, 3, 15, tzinfo=UTC)
SPY = Symbol("SPY")


def _inputs(tmp_path: Path, cash: Decimal = Decimal("10000.00")) -> dict:
    return dict(
        store=ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=cash),
        proposal=TradeProposal(
            proposal_id=UUID(int=1),
            symbol=SPY,
            side=OrderSide.BUY,
            desired_quantity=Decimal("10.250"),
            created_at=NOW,
            reason="explicit human-started proposal",
            confidence=Decimal("0.7200"),
        ),
        prices=MappingProxyType({SPY: Decimal("100.0000")}),
        as_of=NOW + timedelta(seconds=1),
        new_trading_enabled=True,
        risk_limits=RiskLimits(),
        instruction=ExecutionInstruction(
            OrderType.MARKET, TimeInForce.DAY, NOW + timedelta(seconds=2)
        ),
        order_id=UUID(int=2),
        review_received_at=NOW + timedelta(seconds=3),
        expected_branch="feature/robinhood-review-paper-mode",
        expected_head="a" * 40,
        expected_tree="b" * 40,
        evidence_path=tmp_path / "evidence.json",
        redirect_uri="http://127.0.0.1:8765/callback",
        slippage_basis_points=Decimal("1.2500"),
        commission=Decimal("0.1000"),
    )


@pytest.mark.parametrize("cash", [Decimal("10000.00"), Decimal("4321.5600")])
@pytest.mark.parametrize("enabled", [True, False])
def test_exact_builder_then_pipeline_forwarding_and_result_identity(
    tmp_path, monkeypatch, cash, enabled
):
    inputs = _inputs(tmp_path, cash)
    inputs["new_trading_enabled"] = enabled
    context = build_review_paper_risk_context(
        inputs["store"],
        inputs["proposal"],
        inputs["prices"],
        as_of=inputs["as_of"],
        new_trading_enabled=enabled,
    )
    decision = RiskManager(inputs["risk_limits"]).evaluate(
        inputs["proposal"], replace(context, new_trading_enabled=False)
    )
    expected_result = pipeline.RobinhoodDeterministicPaperPipelineResult(
        decision, None, None
    )
    builder = Mock(return_value=context)
    run_pipeline = Mock(return_value=expected_result)
    calls = Mock()
    calls.attach_mock(builder, "builder")
    calls.attach_mock(run_pipeline, "pipeline")
    monkeypatch.setattr(cycle, "build_review_paper_risk_context", builder)
    monkeypatch.setattr(
        cycle, "run_robinhood_deterministic_paper_pipeline", run_pipeline
    )
    store_bytes = inputs["store"].path.read_bytes()

    result = cycle.run_robinhood_forward_paper_cycle(**inputs)

    assert [call[0] for call in calls.mock_calls] == ["builder", "pipeline"]
    builder.assert_called_once_with(
        inputs["store"],
        inputs["proposal"],
        inputs["prices"],
        as_of=inputs["as_of"],
        new_trading_enabled=enabled,
    )
    for actual, key in zip(
        builder.call_args.args, ("store", "proposal", "prices"), strict=True
    ):
        assert actual is inputs[key]
    assert builder.call_args.kwargs["as_of"] is inputs["as_of"]
    assert builder.call_args.kwargs["new_trading_enabled"] is enabled
    expected = {
        key: value
        for key, value in inputs.items()
        if key not in {"store", "prices", "as_of", "new_trading_enabled"}
    }
    expected.update(
        risk_context=context,
        paper_store_path=inputs["store"].path,
        starting_cash=inputs["store"].starting_cash,
    )
    run_pipeline.assert_called_once_with(**expected)
    for key, value in expected.items():
        assert run_pipeline.call_args.kwargs[key] is value
    assert result is expected_result
    assert type(result) is pipeline.RobinhoodDeterministicPaperPipelineResult
    assert inputs["store"].path.read_bytes() == store_bytes
    assert not inputs["evidence_path"].exists()


@pytest.mark.parametrize("boundary", ["builder", "pipeline"])
def test_boundary_exception_propagates_once_without_retry(
    tmp_path, monkeypatch, boundary
):
    inputs = _inputs(tmp_path)
    error = RuntimeError("explicit boundary failure")
    builder = Mock(wraps=build_review_paper_risk_context)
    run_pipeline = Mock(side_effect=error)
    if boundary == "builder":
        builder.side_effect = error
    monkeypatch.setattr(cycle, "build_review_paper_risk_context", builder)
    monkeypatch.setattr(
        cycle, "run_robinhood_deterministic_paper_pipeline", run_pipeline
    )
    with pytest.raises(RuntimeError) as caught:
        cycle.run_robinhood_forward_paper_cycle(**inputs)
    assert caught.value is error
    builder.assert_called_once()
    if boundary == "builder":
        run_pipeline.assert_not_called()
    else:
        run_pipeline.assert_called_once()


@pytest.mark.parametrize(
    "key,bad,exception",
    [
        ("store", object(), TypeError),
        (
            "store",
            SimpleNamespace(path=Path("other"), starting_cash=Decimal("1")),
            TypeError,
        ),
        ("proposal", object(), TypeError),
        ("prices", None, TypeError),
        ("prices", {}, ValueError),
        ("prices", {"SPY": Decimal("100")}, TypeError),
        ("prices", {SPY: 100}, TypeError),
        ("prices", {SPY: Decimal("0")}, ValueError),
        ("prices", {SPY: Decimal("-1")}, ValueError),
        ("prices", {SPY: Decimal("NaN")}, ValueError),
        ("prices", {SPY: Decimal("Infinity")}, ValueError),
        ("prices", {SPY: Decimal("100"), Symbol("QQQ"): Decimal("200")}, ValueError),
        ("as_of", "now", TypeError),
        ("as_of", NOW.replace(tzinfo=None), ValueError),
        ("as_of", NOW - timedelta(seconds=1), ValueError),
        ("new_trading_enabled", 1, TypeError),
        ("new_trading_enabled", None, TypeError),
    ],
)
def test_malformed_builder_inputs_cannot_reach_pipeline(
    tmp_path, monkeypatch, key, bad, exception
):
    inputs = _inputs(tmp_path)
    inputs[key] = bad
    builder = Mock(wraps=build_review_paper_risk_context)
    run_pipeline = Mock(side_effect=AssertionError("pipeline reached"))
    monkeypatch.setattr(cycle, "build_review_paper_risk_context", builder)
    monkeypatch.setattr(
        cycle, "run_robinhood_deterministic_paper_pipeline", run_pipeline
    )
    with pytest.raises(exception):
        cycle.run_robinhood_forward_paper_cycle(**inputs)
    builder.assert_called_once()
    run_pipeline.assert_not_called()


def test_corrupt_durable_history_cannot_reach_pipeline(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    inputs["store"].path.write_bytes(b"invalid sqlite database")
    run_pipeline = Mock(side_effect=AssertionError("pipeline reached"))
    monkeypatch.setattr(
        cycle, "run_robinhood_deterministic_paper_pipeline", run_pipeline
    )
    with pytest.raises(sqlite3.DatabaseError):
        cycle.run_robinhood_forward_paper_cycle(**inputs)
    run_pipeline.assert_not_called()


def test_store_subclass_cannot_supply_an_alternate_account(tmp_path, monkeypatch):
    class AlternateStore(ReviewPaperStore):
        pass

    inputs = _inputs(tmp_path)
    inputs["store"] = AlternateStore(
        tmp_path / "other.sqlite", starting_cash=Decimal("1")
    )
    run_pipeline = Mock(side_effect=AssertionError("pipeline reached"))
    monkeypatch.setattr(
        cycle, "run_robinhood_deterministic_paper_pipeline", run_pipeline
    )
    with pytest.raises(TypeError, match="exactly a ReviewPaperStore"):
        cycle.run_robinhood_forward_paper_cycle(**inputs)
    run_pipeline.assert_not_called()


def _evidence() -> RobinhoodPaperOperatorEvidence:
    return RobinhoodPaperOperatorEvidence(
        source_head="a" * 40,
        source_tree="b" * 40,
        status="PASS",
        phase="complete",
        symbol="SPY",
        side="buy",
        quantity="10.25",
        order_type="market",
        get_accounts_calls=1,
        get_equity_orders_calls=2,
        review_equity_order_calls=1,
        get_equity_quotes_calls=0,
        baseline_order_pages=1,
        post_review_order_pages=1,
        paper_record_count=1,
        replay=False,
        review_echo_validated=True,
        quote_fill_validated=True,
        disclosure_present=True,
        interactive_reauth_count=0,
    )


@pytest.mark.parametrize("outcome", list(RiskOutcome))
def test_accepted_boundaries_own_reconstruction_and_risk_once(
    tmp_path, monkeypatch, outcome
):
    inputs = _inputs(tmp_path)
    if outcome is RiskOutcome.REJECTED:
        inputs["new_trading_enabled"] = False
    elif outcome is RiskOutcome.RESIZED:
        inputs["risk_limits"] = replace(
            inputs["risk_limits"], max_order_notional=Decimal("200")
        )
    store = inputs["store"]
    reconstruct = Mock(wraps=store.reconstruct_ledger)
    monkeypatch.setattr(store, "reconstruct_ledger", reconstruct)
    builder = Mock(wraps=build_review_paper_risk_context)
    monkeypatch.setattr(cycle, "build_review_paper_risk_context", builder)
    evaluate = Mock(wraps=RiskManager(inputs["risk_limits"]).evaluate)
    monkeypatch.setattr(
        pipeline, "RiskManager", Mock(return_value=Mock(evaluate=evaluate))
    )
    evidence = _evidence()
    run_operator = Mock(return_value=evidence)
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)
    results = []

    def delegate(**kwargs):
        result = pipeline.run_robinhood_deterministic_paper_pipeline(**kwargs)
        results.append(result)
        return result

    run_pipeline = Mock(side_effect=delegate)
    monkeypatch.setattr(
        cycle, "run_robinhood_deterministic_paper_pipeline", run_pipeline
    )
    store_bytes = store.path.read_bytes()
    result = cycle.run_robinhood_forward_paper_cycle(**inputs)
    builder.assert_called_once()
    reconstruct.assert_called_once()
    run_pipeline.assert_called_once()
    evaluate.assert_called_once()
    assert evaluate.call_args.args[1] is run_pipeline.call_args.kwargs["risk_context"]
    assert result is results[0]
    assert result.risk_decision.outcome is outcome
    if outcome is RiskOutcome.REJECTED:
        run_operator.assert_not_called()
        assert result.intent is None and result.operator_evidence is None
    else:
        run_operator.assert_called_once()
        assert result.operator_evidence is evidence
        assert run_operator.call_args.kwargs["paper_store_path"] is store.path
        assert run_operator.call_args.kwargs["starting_cash"] is store.starting_cash
    assert store.path.read_bytes() == store_bytes
    assert not inputs["evidence_path"].exists()


@pytest.mark.parametrize("key", ["paper_store_path", "starting_cash", "risk_context"])
def test_public_signature_rejects_alternate_account_and_context_inputs(tmp_path, key):
    signature = inspect.signature(cycle.run_robinhood_forward_paper_cycle)
    assert key not in signature.parameters
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY for p in signature.parameters.values()
    )
    assert all(
        p.default is inspect.Parameter.empty for p in signature.parameters.values()
    )
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        cycle.run_robinhood_forward_paper_cycle(**_inputs(tmp_path), **{key: object()})


def test_source_has_only_the_two_accepted_boundaries():
    tree = ast.parse(Path(cycle.__file__).read_text(encoding="utf-8"))
    imports = {
        "__future__": {"annotations"},
        "collections.abc": {"Mapping"},
        "datetime": {"datetime"},
        "decimal": {"Decimal"},
        "pathlib": {"Path"},
        "uuid": {"UUID"},
        "trading_bot.domain": {"Symbol", "TradeProposal"},
        "trading_bot.execution.models": {"ExecutionInstruction"},
        "trading_bot.review_paper.risk_context": {"build_review_paper_risk_context"},
        "trading_bot.review_paper.store": {"ReviewPaperStore"},
        "trading_bot.risk": {"RiskLimits"},
        "trading_bot.robinhood_paper_pipeline": {
            "RobinhoodDeterministicPaperPipelineResult",
            "run_robinhood_deterministic_paper_pipeline",
        },
    }
    nodes = tree.body[1:]
    assert all(isinstance(node, (ast.ImportFrom, ast.FunctionDef)) for node in nodes)
    imported = [node for node in nodes if isinstance(node, ast.ImportFrom)]
    assert {
        node.module: {alias.name for alias in node.names} for node in imported
    } == imports
    assert all(
        node.level == 0 and all(a.asname is None for a in node.names)
        for node in imported
    )
    functions = [node for node in nodes if isinstance(node, ast.FunctionDef)]
    assert len(functions) == 1
    function = functions[0]
    assert function.name == "run_robinhood_forward_paper_cycle"
    assert not function.decorator_list
    assert [type(node) for node in function.body] == [ast.Expr, ast.Assign, ast.Return]
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert all(isinstance(node.func, ast.Name) for node in calls)
    assert [node.func.id for node in calls] == [
        "build_review_paper_risk_context",
        "run_robinhood_deterministic_paper_pipeline",
    ]
    assert {
        ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } == {"store.path", "store.starting_cash"}
