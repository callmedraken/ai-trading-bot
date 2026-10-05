from __future__ import annotations

import ast
import builtins
import logging
import os
import socket
import subprocess
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper import ReviewPaperIntent, build_review_paper_intent
from trading_bot.risk import RiskDecision, RiskOutcome, RiskReason, RiskReasonCode

NOW = datetime(2026, 10, 2, 15, tzinfo=UTC)
ORDER_ID = UUID("22222222-2222-2222-2222-222222222222")
REASONS = (
    RiskReason(RiskReasonCode.MAX_ORDER_NOTIONAL, "notional constraint"),
    RiskReason(RiskReasonCode.CASH_CAPACITY, "cash constraint"),
    RiskReason(RiskReasonCode.QUANTITY_INCREMENT, "quantity constraint"),
)


def _decision() -> RiskDecision:
    return RiskDecision(
        proposal=TradeProposal(
            proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
            symbol=Symbol("SPY"),
            side=OrderSide.BUY,
            desired_quantity=Decimal("10.250"),
            created_at=NOW,
            reason="  validated signal with original whitespace  ",
            confidence=Decimal("0.7200"),
        ),
        outcome=RiskOutcome.APPROVED,
        approved_quantity=Decimal("10.250"),
        reasons=(),
        evaluated_at=NOW + timedelta(seconds=1),
    )


def _instruction() -> ExecutionInstruction:
    return ExecutionInstruction(
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        created_at=NOW + timedelta(seconds=2),
    )


@pytest.mark.parametrize("outcome", [RiskOutcome.APPROVED, RiskOutcome.RESIZED])
@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
@pytest.mark.parametrize("confidence", [None, Decimal("0.7200")])
@pytest.mark.parametrize("order_type", [OrderType.MARKET, OrderType.LIMIT])
def test_exact_mapping(outcome, side, confidence, order_type) -> None:
    decision = _decision()
    proposal = replace(decision.proposal, side=side, confidence=confidence)
    approved = (
        proposal.desired_quantity
        if outcome is RiskOutcome.APPROVED
        else Decimal("3.1250")
    )
    decision = replace(
        decision,
        proposal=proposal,
        outcome=outcome,
        approved_quantity=approved,
        reasons=REASONS,
    )
    limit_price = Decimal("501.2300") if order_type is OrderType.LIMIT else None
    instruction = replace(
        _instruction(),
        order_type=order_type,
        limit_price=limit_price,
        time_in_force=TimeInForce.GOOD_TIL_CANCELED,
    )

    intent = build_review_paper_intent(decision, instruction, order_id=ORDER_ID)

    assert intent == ReviewPaperIntent(
        proposal_id=proposal.proposal_id,
        order_id=ORDER_ID,
        symbol=proposal.symbol,
        side=side,
        desired_quantity=proposal.desired_quantity,
        approved_quantity=approved,
        risk_outcome=outcome,
        risk_reason_codes=("MAX_ORDER_NOTIONAL", "CASH_CAPACITY", "QUANTITY_INCREMENT"),
        proposal_reason="  validated signal with original whitespace  ",
        proposal_confidence=confidence,
        order_type=order_type,
        time_in_force=TimeInForce.GOOD_TIL_CANCELED,
        proposed_at=NOW,
        limit_price=limit_price,
    )
    assert intent.order_id is ORDER_ID
    assert intent.proposal_id is proposal.proposal_id
    assert intent.desired_quantity is proposal.desired_quantity
    assert intent.approved_quantity is approved
    assert intent.proposal_confidence is confidence
    assert intent.limit_price is limit_price
    assert decision.proposal is proposal
    assert decision.reasons is REASONS


def test_repeated_conversion_is_deterministic_and_context_independent() -> None:
    decision, instruction = _decision(), _instruction()
    with localcontext() as context:
        context.prec = 2
        first = build_review_paper_intent(decision, instruction, order_id=ORDER_ID)
    with localcontext() as context:
        context.prec = 50
        second = build_review_paper_intent(decision, instruction, order_id=ORDER_ID)
    assert first == second
    other_id = UUID("33333333-3333-3333-3333-333333333333")
    assert build_review_paper_intent(
        decision, instruction, order_id=other_id
    ) == replace(first, order_id=other_id)


def test_rejected_decision_is_refused() -> None:
    decision = replace(
        _decision(),
        outcome=RiskOutcome.REJECTED,
        approved_quantity=Decimal("0"),
        reasons=REASONS,
    )
    with pytest.raises(ValueError, match="rejected risk decisions"):
        build_review_paper_intent(decision, _instruction(), order_id=ORDER_ID)


def test_decision_before_proposal_is_refused() -> None:
    decision = replace(_decision(), evaluated_at=NOW - timedelta(microseconds=1))
    with pytest.raises(ValueError, match="decision evaluated_at"):
        build_review_paper_intent(decision, _instruction(), order_id=ORDER_ID)


def test_instruction_before_decision_is_refused() -> None:
    decision = _decision()
    instruction = replace(
        _instruction(), created_at=decision.evaluated_at - timedelta(microseconds=1)
    )
    with pytest.raises(ValueError, match="instruction created_at"):
        build_review_paper_intent(decision, instruction, order_id=ORDER_ID)


def test_equal_timestamps_are_allowed() -> None:
    decision = replace(_decision(), evaluated_at=NOW)
    instruction = replace(_instruction(), created_at=NOW)
    assert (
        build_review_paper_intent(decision, instruction, order_id=ORDER_ID).proposed_at
        == NOW
    )


@pytest.mark.parametrize("field", ["decision", "instruction", "order_id"])
@pytest.mark.parametrize("invalid", [None, "not-a-model-or-UUID", 1, object()])
def test_invalid_input_types_are_refused(field, invalid) -> None:
    values = dict(decision=_decision(), instruction=_instruction(), order_id=ORDER_ID)
    values[field] = invalid
    with pytest.raises(TypeError, match=field):
        build_review_paper_intent(**values)


@pytest.mark.parametrize("field", ["decision", "instruction", "order_id"])
def test_subclasses_are_refused_by_exact_type_boundary(field) -> None:
    class DerivedDecision(RiskDecision):
        pass

    class DerivedInstruction(ExecutionInstruction):
        pass

    class DerivedUUID(UUID):
        pass

    decision, instruction = _decision(), _instruction()
    subclasses = {
        "decision": DerivedDecision(
            decision.proposal,
            decision.outcome,
            decision.approved_quantity,
            decision.reasons,
            decision.evaluated_at,
        ),
        "instruction": DerivedInstruction(
            instruction.order_type, instruction.time_in_force, instruction.created_at
        ),
        "order_id": DerivedUUID(str(ORDER_ID)),
    }
    values = dict(decision=decision, instruction=instruction, order_id=ORDER_ID)
    values[field] = subclasses[field]
    with pytest.raises(TypeError, match=field):
        build_review_paper_intent(**values)


def test_order_id_is_required_and_keyword_only() -> None:
    with pytest.raises(TypeError, match="order_id"):
        build_review_paper_intent(_decision(), _instruction())
    with pytest.raises(TypeError):
        build_review_paper_intent(_decision(), _instruction(), ORDER_ID)


def test_duplicate_reason_codes_are_left_to_intent_validation() -> None:
    decision = replace(_decision(), reasons=(REASONS[0], REASONS[0]))
    with pytest.raises(ValueError, match="risk_reason_codes must be unique"):
        build_review_paper_intent(decision, _instruction(), order_id=ORDER_ID)


def test_conversion_has_no_operator_mcp_oauth_risk_order_or_host_effects(
    monkeypatch,
) -> None:
    from trading_bot import robinhood_paper_operator as operator
    from trading_bot.execution import OrderEngine
    from trading_bot.risk import RiskManager
    from trading_bot.robinhood_mcp import sdk_transport, windows_oauth
    from trading_bot.robinhood_paper_cycle import RobinhoodReviewPaperCycle

    decision, instruction = _decision(), _instruction()
    expected = build_review_paper_intent(decision, instruction, order_id=ORDER_ID)

    def forbidden(*args, **kwargs):
        raise AssertionError("bridge attempted an effect or downstream operation")

    with monkeypatch.context() as patch:
        for owner, name in (
            (operator, "run_robinhood_paper_operator"),
            (RobinhoodReviewPaperCycle, "__init__"),
            (sdk_transport.RobinhoodMcpStreamableHttpTransport, "__init__"),
            (sdk_transport.RobinhoodMcpStreamableHttpTransport, "_invoke"),
            (sdk_transport, "create_robinhood_oauth_factory"),
            (windows_oauth, "create_windows_robinhood_oauth_factory"),
            (windows_oauth.WindowsOAuthStorage, "__init__"),
            (windows_oauth.WindowsCredentialApi, "__init__"),
            (windows_oauth.LoopbackOAuthCallback, "__init__"),
            (RiskManager, "evaluate"),
            (OrderEngine, "create_order"),
            (OrderEngine, "submit_order"),
            (builtins, "open"),
            (builtins, "print"),
            (Path, "open"),
            (socket, "socket"),
            (subprocess, "Popen"),
            (os, "getenv"),
            (logging.Logger, "_log"),
            (uuid, "uuid4"),
        ):
            patch.setattr(owner, name, forbidden)
        patch.setattr(os, "environ", None)
        actual = build_review_paper_intent(decision, instruction, order_id=ORDER_ID)
    assert actual == expected


def test_bridge_source_has_only_model_imports_and_pure_calls() -> None:
    from trading_bot.review_paper import intent_bridge

    tree = ast.parse(Path(intent_bridge.__file__).read_text(encoding="utf-8"))
    imports = {
        (node.module, name.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for name in node.names
    }
    assert imports == {
        ("__future__", "annotations"),
        ("uuid", "UUID"),
        ("trading_bot.execution.models", "ExecutionInstruction"),
        ("trading_bot.review_paper.models", "ReviewPaperIntent"),
        ("trading_bot.risk.models", "RiskDecision"),
        ("trading_bot.risk.models", "RiskOutcome"),
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name)
            assert node.func.id in {
                "type",
                "TypeError",
                "ValueError",
                "tuple",
                "ReviewPaperIntent",
            }
