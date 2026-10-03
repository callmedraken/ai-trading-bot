from __future__ import annotations

import ast
import socket
import subprocess
import uuid
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest

from trading_bot import robinhood_paper_operator as operator
from trading_bot import robinhood_paper_pipeline as pipeline
from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.execution.engine import OrderEngine
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper import build_review_paper_intent
from trading_bot.risk import RiskContext, RiskLimits, RiskManager, RiskOutcome

NOW = datetime(2026, 10, 2, 15, tzinfo=UTC)
ORDER_ID = UUID("22222222-2222-2222-2222-222222222222")


def _inputs(tmp_path: Path) -> dict:
    return dict(
        proposal=TradeProposal(
            proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
            symbol=Symbol("SPY"),
            side=OrderSide.BUY,
            desired_quantity=Decimal("10.250"),
            created_at=NOW,
            reason="  explicit local proposal  ",
            confidence=Decimal("0.7200"),
        ),
        risk_context=RiskContext(
            cash=Decimal("10000"),
            equity=Decimal("10000"),
            positions={},
            current_price=Decimal("100"),
            total_market_exposure=Decimal("0"),
            new_trading_enabled=True,
            as_of=NOW + timedelta(seconds=1),
        ),
        risk_limits=RiskLimits(),
        instruction=ExecutionInstruction(
            OrderType.MARKET, TimeInForce.DAY, NOW + timedelta(seconds=2)
        ),
        order_id=ORDER_ID,
        review_received_at=NOW + timedelta(seconds=3),
        expected_branch="feature/robinhood-review-paper-mode",
        expected_head="a" * 40,
        expected_tree="b" * 40,
        paper_store_path=tmp_path / "paper.sqlite",
        evidence_path=tmp_path / "evidence.json",
        redirect_uri="http://127.0.0.1:8765/callback",
        starting_cash=Decimal("10000.00"),
        slippage_basis_points=Decimal("1.2500"),
        commission=Decimal("0.1000"),
    )


def _evidence(status: str = "PASS") -> operator.RobinhoodPaperOperatorEvidence:
    return operator.RobinhoodPaperOperatorEvidence(
        source_head="a" * 40,
        source_tree="b" * 40,
        status=status,
        phase="complete" if status == "PASS" else "review",
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
        paper_record_count=1 if status == "PASS" else None,
        replay=False,
        review_echo_validated=status == "PASS",
        quote_fill_validated=status == "PASS",
        disclosure_present=status == "PASS",
        interactive_reauth_count=0,
    )


@pytest.mark.parametrize("status", ["PASS", "FAIL"])
@pytest.mark.parametrize("outcome", [RiskOutcome.APPROVED, RiskOutcome.RESIZED])
def test_accepted_exact_composition_and_forwarding(
    tmp_path, monkeypatch, status, outcome
):
    inputs = _inputs(tmp_path)
    if outcome is RiskOutcome.RESIZED:
        inputs["risk_limits"] = replace(
            inputs["risk_limits"],
            max_position_percent=Decimal("0.02"),
            max_total_exposure_percent=Decimal("0.02"),
            max_order_notional=Decimal("200"),
        )
    manager = RiskManager(inputs["risk_limits"])
    decision = manager.evaluate(inputs["proposal"], inputs["risk_context"])
    direct_intent = build_review_paper_intent(
        decision, inputs["instruction"], order_id=ORDER_ID
    )
    evaluation = Mock(return_value=decision)
    monkeypatch.setattr(manager, "evaluate", evaluation)
    constructor = Mock(return_value=manager)
    monkeypatch.setattr(pipeline, "RiskManager", constructor)
    bridge = Mock(wraps=build_review_paper_intent)
    monkeypatch.setattr(pipeline, "build_review_paper_intent", bridge)
    evidence = _evidence(status)
    run_operator = Mock(return_value=evidence)
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)

    result = pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)

    constructor.assert_called_once_with(inputs["risk_limits"])
    assert constructor.call_args.args[0] is inputs["risk_limits"]
    evaluation.assert_called_once_with(inputs["proposal"], inputs["risk_context"])
    assert evaluation.call_args.args[0] is inputs["proposal"]
    assert evaluation.call_args.args[1] is inputs["risk_context"]
    bridge.assert_called_once_with(decision, inputs["instruction"], order_id=ORDER_ID)
    assert bridge.call_args.args[0] is decision
    assert bridge.call_args.args[1] is inputs["instruction"]
    assert result.risk_decision is decision
    assert decision.outcome is outcome
    assert result.intent == direct_intent
    assert result.intent.order_id is ORDER_ID
    assert result.intent.proposal_id is inputs["proposal"].proposal_id
    assert result.intent.approved_quantity is decision.approved_quantity
    if outcome is RiskOutcome.RESIZED:
        assert result.intent.risk_reason_codes == (
            "MAX_POSITION_PERCENT",
            "MAX_TOTAL_EXPOSURE_PERCENT",
            "MAX_ORDER_NOTIONAL",
        )
    expected = {
        key: value
        for key, value in inputs.items()
        if key
        not in {"proposal", "risk_context", "risk_limits", "instruction", "order_id"}
    }
    run_operator.assert_called_once_with(intent=result.intent, **expected)
    for key, value in expected.items():
        assert run_operator.call_args.kwargs[key] is value
    assert result.operator_evidence is evidence
    assert result.operator_evidence.status == status
    assert not inputs["paper_store_path"].exists()
    assert not inputs["evidence_path"].exists()


def test_rejected_returns_before_bridge_operator_or_outputs(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    inputs["risk_context"] = replace(inputs["risk_context"], new_trading_enabled=False)
    evaluate = Mock(wraps=RiskManager(inputs["risk_limits"]).evaluate)
    manager = Mock(evaluate=evaluate)
    constructor = Mock(return_value=manager)
    monkeypatch.setattr(pipeline, "RiskManager", constructor)
    bridge = Mock(side_effect=AssertionError("bridge called for rejection"))
    run_operator = Mock(side_effect=AssertionError("operator called for rejection"))
    monkeypatch.setattr(pipeline, "build_review_paper_intent", bridge)
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)
    result = pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    constructor.assert_called_once_with(inputs["risk_limits"])
    evaluate.assert_called_once_with(inputs["proposal"], inputs["risk_context"])
    assert result.risk_decision.outcome is RiskOutcome.REJECTED
    assert result.intent is None and result.operator_evidence is None
    bridge.assert_not_called()
    run_operator.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad_timestamp", ["instruction", "risk_context"])
def test_timestamp_inconsistency_fails_before_operator(
    tmp_path, monkeypatch, bad_timestamp
):
    inputs = _inputs(tmp_path)
    if bad_timestamp == "instruction":
        inputs["instruction"] = replace(inputs["instruction"], created_at=NOW)
    else:
        inputs["risk_context"] = replace(
            inputs["risk_context"], as_of=NOW - timedelta(seconds=1)
        )
    run_operator = Mock(side_effect=AssertionError("operator called"))
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)
    with pytest.raises(ValueError, match="must not precede"):
        pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    run_operator.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_operator_exception_propagates_without_retry(tmp_path, monkeypatch):
    error = operator.RobinhoodPaperOperatorError("source identity unavailable")
    run_operator = Mock(side_effect=error)
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)
    with pytest.raises(operator.RobinhoodPaperOperatorError) as caught:
        pipeline.run_robinhood_deterministic_paper_pipeline(**_inputs(tmp_path))
    assert caught.value is error
    run_operator.assert_called_once()


@pytest.mark.parametrize("rejected", [False, True])
def test_deterministic_repeated_pre_operator_inputs(tmp_path, monkeypatch, rejected):
    inputs = _inputs(tmp_path)
    inputs["risk_context"] = replace(
        inputs["risk_context"], new_trading_enabled=not rejected
    )
    run_operator = Mock(return_value=_evidence())
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)
    first = pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    second = pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    assert first.risk_decision == second.risk_decision
    assert first.intent == second.intent
    assert run_operator.call_count == (0 if rejected else 2)


@pytest.mark.parametrize("field", ["instruction", "order_id"])
def test_explicit_input_types_fail_before_operator(tmp_path, monkeypatch, field):
    inputs = _inputs(tmp_path)
    inputs[field] = None
    run_operator = Mock()
    monkeypatch.setattr(pipeline, "run_robinhood_paper_operator", run_operator)
    with pytest.raises(TypeError, match=field):
        pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    run_operator.assert_not_called()


def test_immutable_closed_result_and_invariants(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pipeline, "run_robinhood_paper_operator", Mock(return_value=_evidence())
    )
    inputs = _inputs(tmp_path)
    accepted = pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    assert tuple(field.name for field in fields(accepted)) == (
        "risk_decision",
        "intent",
        "operator_evidence",
    )
    assert not hasattr(accepted, "__dict__")
    with pytest.raises(FrozenInstanceError):
        accepted.intent = None
    for field in ("intent", "operator_evidence", "risk_decision"):
        with pytest.raises(TypeError):
            replace(accepted, **{field: None})
    inputs["risk_context"] = replace(inputs["risk_context"], new_trading_enabled=False)
    rejected = pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    for field, value in (
        ("intent", accepted.intent),
        ("operator_evidence", _evidence()),
    ):
        with pytest.raises(ValueError):
            replace(rejected, **{field: value})


@pytest.mark.parametrize("rejected", [False, True])
def test_no_direct_effects_or_order_lifecycle(tmp_path, monkeypatch, rejected):
    inputs = _inputs(tmp_path)
    inputs["risk_context"] = replace(
        inputs["risk_context"], new_trading_enabled=not rejected
    )
    forbidden = Mock(side_effect=AssertionError("unreviewed direct effect"))
    for owner, name in (
        (OrderEngine, "create_order"),
        (OrderEngine, "submit_order"),
        (uuid, "uuid1"),
        (uuid, "uuid4"),
        (uuid, "uuid5"),
        (socket, "socket"),
        (subprocess, "run"),
        (operator, "create_windows_robinhood_oauth_factory"),
        (operator, "create_robinhood_agentic_account_resolver"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr(
        pipeline, "run_robinhood_paper_operator", Mock(return_value=_evidence())
    )
    pipeline.run_robinhood_deterministic_paper_pipeline(**inputs)
    forbidden.assert_not_called()


def test_source_has_no_retry_loop_or_scheduler():
    tree = ast.parse(Path(pipeline.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(
            node,
            (
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
                ast.Await,
                ast.AsyncFunctionDef,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        )
        for node in ast.walk(tree)
    )
