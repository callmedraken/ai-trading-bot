from __future__ import annotations

import ast
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from tests.runtime.test_manual_paper_strategy_plan import (
    _NEXT_SESSION,
    _decision_request,
    _request,
    calendar,
)

from scripts import checkpoint_runner
from scripts import run_test_certification as certification
from trading_bot.domain import OrderType, TimeInForce
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper import production_strategy_cycle as subject
from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedExecutionResult,
    ReviewPaperSupervisedPreparation,
    ReviewPaperSupervisedPreparationStatus,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.strategies.production import ProductionStrategyContract
from trading_bot.strategies.production_decision import (
    ProductionStrategyDecisionStatus,
    build_production_strategy_decision,
)

NAME = "arch134-production-strategy-live-paper"
BUFFER = timedelta(minutes=5)
AGE = timedelta(minutes=1)


def _decision(*, no_signal: bool = False):
    request = (
        _decision_request(_request(closes=("10", "11", "12"), selected_close="13"))
        if no_signal
        else _decision_request(_request())
    )
    contract = ProductionStrategyContract(
        _NEXT_SESSION.session_date,
        "a" * 40,
        "b" * 40,
        request.history_seed.seed.symbol,
        request.strategy_config,
    )
    return build_production_strategy_decision(contract, request, calendar())


def _schedule(session_date=None) -> ReviewPaperSessionSchedule:
    target = session_date or _NEXT_SESSION.session_date
    opens = datetime.combine(target, time(14, 30), tzinfo=UTC)
    closes = datetime.combine(target, time(21), tzinfo=UTC)
    return ReviewPaperSessionSchedule(target, opens, closes)


def _supervised(decision, status):
    value = object.__new__(ReviewPaperSupervisedPreparation)
    object.__setattr__(value, "status", status)
    object.__setattr__(value, "proposal", decision.proposal)
    object.__setattr__(value, "schedule", _schedule())
    return value


def _execution(supervised):
    value = object.__new__(ReviewPaperSupervisedExecutionResult)
    object.__setattr__(value, "preparation", supervised)
    return value


def _prepare_kwargs(decision):
    return {
        "decision": decision,
        "store": object.__new__(ReviewPaperStore),
        "schedule": _schedule(),
        "opening_buffer": BUFFER,
        "closing_buffer": BUFFER,
        "adapter": object.__new__(RobinhoodReviewReadAdapter),
        "max_quote_age": AGE,
        "risk_limits": RiskLimits(),
        "new_trading_enabled": True,
    }


def test_no_signal_is_zero_delegate_and_does_not_touch_other_inputs(monkeypatch):
    decision = _decision(no_signal=True)
    assert decision.status is ProductionStrategyDecisionStatus.NO_SIGNAL
    calls = 0

    def forbidden(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("PREPARE must not run for NO_SIGNAL")

    monkeypatch.setattr(subject, "prepare_review_paper_supervised_cycle", forbidden)
    result = subject.prepare_production_strategy_paper_cycle(
        decision=decision,
        store=object(),
        schedule=object(),
        opening_buffer=object(),
        closing_buffer=object(),
        adapter=object(),
        max_quote_age=object(),
        risk_limits=object(),
        new_trading_enabled=object(),
    )
    assert result.decision is decision
    assert result.status is subject.ProductionStrategyPaperPreparationStatus.NO_SIGNAL
    assert result.supervised is None
    assert calls == 0


def test_target_session_mismatch_blocks_before_prepare(monkeypatch):
    decision = _decision()
    calls = 0

    def forbidden(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("PREPARE must not run")

    monkeypatch.setattr(subject, "prepare_review_paper_supervised_cycle", forbidden)
    kwargs = _prepare_kwargs(decision)
    kwargs["schedule"] = _schedule(_NEXT_SESSION.session_date + timedelta(days=1))
    with pytest.raises(ValueError, match="target session"):
        subject.prepare_production_strategy_paper_cycle(**kwargs)
    assert calls == 0


@pytest.mark.parametrize(
    ("supervised_status", "expected"),
    [
        (
            ReviewPaperSupervisedPreparationStatus.SESSION_NOT_ADMITTED,
            subject.ProductionStrategyPaperPreparationStatus.SESSION_NOT_ADMITTED,
        ),
        (
            ReviewPaperSupervisedPreparationStatus.SESSION_EXPIRED_DURING_ACQUISITION,
            subject.ProductionStrategyPaperPreparationStatus.SESSION_EXPIRED_DURING_ACQUISITION,
        ),
        (
            ReviewPaperSupervisedPreparationStatus.RISK_REJECTED,
            subject.ProductionStrategyPaperPreparationStatus.RISK_REJECTED,
        ),
        (
            ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED,
            subject.ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED,
        ),
    ],
)
def test_trade_prepare_delegates_once_and_maps_exact_status(
    monkeypatch, supervised_status, expected
):
    decision = _decision()
    supervised = _supervised(decision, supervised_status)
    calls = []

    def prepare_once(**kwargs):
        calls.append(kwargs)
        return supervised

    monkeypatch.setattr(subject, "prepare_review_paper_supervised_cycle", prepare_once)
    kwargs = _prepare_kwargs(decision)
    result = subject.prepare_production_strategy_paper_cycle(**kwargs)

    assert len(calls) == 1
    assert calls[0]["proposal"] is decision.proposal
    for name in (
        "store",
        "schedule",
        "opening_buffer",
        "closing_buffer",
        "adapter",
        "max_quote_age",
        "risk_limits",
        "new_trading_enabled",
    ):
        assert calls[0][name] is kwargs[name]
    assert result.decision is decision
    assert result.status is expected
    assert result.supervised is supervised


def test_prepare_rejects_invalid_delegate_material(monkeypatch):
    decision = _decision()
    monkeypatch.setattr(
        subject,
        "prepare_review_paper_supervised_cycle",
        lambda **kwargs: object(),
    )
    with pytest.raises(ValueError, match="invalid material"):
        subject.prepare_production_strategy_paper_cycle(**_prepare_kwargs(decision))


def test_execute_requires_ready_and_exact_contract_source_before_delegate(
    monkeypatch, tmp_path
):
    decision = _decision()
    blocked = subject.ProductionStrategyPaperPreparation(
        decision,
        subject.ProductionStrategyPaperPreparationStatus.RISK_REJECTED,
        _supervised(decision, ReviewPaperSupervisedPreparationStatus.RISK_REJECTED),
    )
    calls = 0

    def forbidden(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("EXECUTE must not run")

    monkeypatch.setattr(subject, "execute_review_paper_supervised_cycle", forbidden)
    execute_kwargs = {
        "instruction": ExecutionInstruction(
            OrderType.MARKET, TimeInForce.DAY, datetime.now(UTC)
        ),
        "order_id": UUID(int=7),
        "expected_branch": "feature/example",
        "expected_head": "a" * 40,
        "expected_tree": "b" * 40,
        "evidence_path": tmp_path / "evidence.json",
        "redirect_uri": "http://127.0.0.1:8765/callback",
        "slippage_basis_points": Decimal("0"),
        "commission": Decimal("0"),
    }
    with pytest.raises(ValueError, match="READY_TO_PROCEED"):
        subject.execute_production_strategy_paper_cycle(
            preparation=blocked, **execute_kwargs
        )

    ready = subject.ProductionStrategyPaperPreparation(
        decision,
        subject.ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED,
        _supervised(decision, ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED),
    )
    for field, wrong in (("expected_head", "c" * 40), ("expected_tree", "d" * 40)):
        bad = dict(execute_kwargs)
        bad[field] = wrong
        with pytest.raises(ValueError, match="source"):
            subject.execute_production_strategy_paper_cycle(preparation=ready, **bad)
    assert calls == 0


def test_ready_execute_delegates_once_and_retains_exact_result(monkeypatch, tmp_path):
    decision = _decision()
    supervised = _supervised(
        decision, ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
    )
    ready = subject.ProductionStrategyPaperPreparation(
        decision,
        subject.ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED,
        supervised,
    )
    execution = _execution(supervised)
    calls = []

    def execute_once(**kwargs):
        calls.append(kwargs)
        return execution

    monkeypatch.setattr(subject, "execute_review_paper_supervised_cycle", execute_once)
    instruction = ExecutionInstruction(
        OrderType.MARKET,
        TimeInForce.DAY,
        datetime.now(UTC),
    )
    kwargs = {
        "preparation": ready,
        "instruction": instruction,
        "order_id": UUID(int=8),
        "expected_branch": "feature/example",
        "expected_head": decision.contract.source_head,
        "expected_tree": decision.contract.source_tree,
        "evidence_path": tmp_path / "evidence.json",
        "redirect_uri": "http://127.0.0.1:8765/callback",
        "slippage_basis_points": Decimal("1.25"),
        "commission": Decimal("0.1"),
    }
    result = subject.execute_production_strategy_paper_cycle(**kwargs)

    assert len(calls) == 1
    assert calls[0]["preparation"] is supervised
    for name, value in kwargs.items():
        if name != "preparation":
            assert calls[0][name] is value
    assert result.preparation is ready
    assert result.execution is execution


def test_result_models_fail_closed_on_mismatched_material() -> None:
    decision = _decision()
    supervised = _supervised(
        decision, ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
    )
    with pytest.raises(ValueError):
        subject.ProductionStrategyPaperPreparation(
            decision,
            subject.ProductionStrategyPaperPreparationStatus.RISK_REJECTED,
            supervised,
        )
    ready = subject.ProductionStrategyPaperPreparation(
        decision,
        subject.ProductionStrategyPaperPreparationStatus.READY_TO_PROCEED,
        supervised,
    )
    other = _supervised(
        decision, ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
    )
    with pytest.raises(ValueError):
        subject.ProductionStrategyPaperExecutionResult(ready, _execution(other))


def test_source_has_only_reviewed_composition_capabilities() -> None:
    path = Path(subject.__file__)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {
        "__future__",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "pathlib",
        "uuid",
        "trading_bot.execution.models",
        "trading_bot.review_paper.session_admission",
        "trading_bot.review_paper.store",
        "trading_bot.review_paper.supervised_forward_paper",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.strategies.production_decision",
    }
    assert "place_equity_order" not in source
    assert "cancel" not in source
    assert "options" not in source
    assert "crypto" not in source
    assert "while " not in source
    assert "sleep(" not in source
    assert "candidate" not in source.lower()
    assert "promotion" not in source.lower()
    assert "run_robinhood_forward_paper_cycle" not in source
    assert "record_market_review" not in source
    assert "acquire_review_paper_risk_price_snapshot" not in source


def test_checkpoint_and_certification_inventory_are_exact() -> None:
    spec = checkpoint_runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == "feature/robinhood-production-strategy-live-paper"
    assert (
        spec.authority_check
        is checkpoint_runner._arch134_production_strategy_live_paper_authority_check
    )
    assert checkpoint_runner.ACTIVE_CI_CHECKPOINTS[-5:-2] == (
        "arch134-production-strategy-contract",
        "arch134-production-strategy-decision",
        NAME,
    )
    assert len(checkpoint_runner.ACTIVE_CI_CHECKPOINTS) == 70
    assert (
        checkpoint_runner.ACTIVE_CI_CHECKPOINTS[-7]
        == checkpoint_runner.ARCH134_AUTH_NAME
    )

    root = Path(certification.__file__).resolve().parents[1]
    inventory = certification.discover_inventory(root)
    profiles = {
        name: certification.select_inventory(inventory, name)
        for name in ("full", "robinhood", "legacy", "exhaustive")
    }
    assert {name: len(value) for name, value in profiles.items()} == {
        "full": 192,
        "robinhood": 103,
        "legacy": 222,
        "exhaustive": 414,
    }
    assert "tests/review_paper/test_production_strategy_cycle.py" in profiles["full"]
    assert (
        "tests/review_paper/test_production_strategy_cycle.py" in profiles["robinhood"]
    )
