"""Focused Architecture 142-B strategy-native walk-forward coverage."""

import ast
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest

from scripts import checkpoint_runner
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.research_strategy_backtest import (
    derive_backtest_run_id,
)
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.experiments.research_strategy_walk_forward import (
    TEST_FOLD_ROLE,
    TRAINING_FOLD_ROLE,
    CompletedResearchStrategyWalkForward,
    ResearchStrategyWalkForwardError,
    ResearchStrategyWalkForwardEvidence,
    ResearchStrategyWalkForwardFold,
    ResearchStrategyWalkForwardQualification,
    ResearchStrategyWalkForwardQualificationPolicy,
    WalkForwardPassedResearchStrategy,
    build_walk_forward_passed_research_strategy,
    qualify_research_strategy_walk_forward,
    run_research_strategy_walk_forward,
    verify_research_strategy_walk_forward,
    verify_research_strategy_walk_forward_evidence,
    verify_research_strategy_walk_forward_qualification,
)
from trading_bot.experiments.research_strategy_walk_forward import (
    ResearchStrategyWalkForwardFailureReason as Reason,
)
from trading_bot.experiments.research_strategy_walk_forward import (
    ResearchStrategyWalkForwardQualificationStatus as Status,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult
from trading_bot.strategies import MovingAverageCrossoverConfig

HEAD = "a" * 40
TREE = "b" * 40
EVALUATION_HEAD = "c" * 40
EVALUATION_TREE = "d" * 40


def test_arch142b_inventory_overlay_is_explicit_and_composes_142a() -> None:
    predecessor = checkpoint_runner.ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    successor = checkpoint_runner.ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    assert set(successor) == set(predecessor)
    assert (
        sha256(json.dumps(successor, sort_keys=True).encode()).hexdigest()
        == checkpoint_runner.ARCH142B_CURRENT_INVENTORY_TEST_PINS_SHA256
    )
    for relative, pin in predecessor.items():
        before = checkpoint_runner.ARCH134_D1R8_TEST_PIN_OVERRIDES.get(
            relative, checkpoint_runner.ARCH134_D1R8_SOURCE_PINS.get(relative)
        )
        assert before is not None
        assert (
            checkpoint_runner._arch142_current_inventory_test_pin(relative, before)
            == pin
        )
        assert (
            checkpoint_runner._arch142b_current_inventory_test_pin(relative, pin)
            == successor[relative]
        )
    assert (
        checkpoint_runner._arch142b_current_inventory_test_pin(
            "tests/experiments/test_research_strategy_walk_forward.py", "a" * 40
        )
        == "a" * 40
    )


@pytest.mark.parametrize("mutation", ["missing", "extra", "drift", "predecessor"])
def test_arch142b_inventory_overlay_fails_closed(monkeypatch, mutation: str) -> None:
    pins = dict(checkpoint_runner.ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    path = next(iter(pins))
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/unreviewed.py"] = "a" * 40
    elif mutation == "drift":
        pins[path] = "0" * 40
    else:
        with pytest.raises(ValueError, match="wrong before"):
            checkpoint_runner._arch142b_current_inventory_test_pin(path, "0" * 40)
        return
    monkeypatch.setattr(
        checkpoint_runner, "ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    with pytest.raises(ValueError):
        checkpoint_runner._arch142b_current_inventory_test_pin(
            path, checkpoint_runner.ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[path]
        )


@pytest.fixture
def data() -> HistoricalDataResult:
    symbol = Symbol("SPY")
    request = HistoricalDataRequest(
        symbol,
        datetime(2024, 1, 2, tzinfo=UTC),
        datetime(2024, 1, 19, tzinfo=UTC),
    )
    timestamps = (
        datetime(2024, 1, 2, 20, tzinfo=UTC),
        datetime(2024, 1, 3, 20, tzinfo=UTC),
        datetime(2024, 1, 4, 20, tzinfo=UTC),
        datetime(2024, 1, 5, 20, tzinfo=UTC),
        datetime(2024, 1, 8, 20, tzinfo=UTC),
        datetime(2024, 1, 9, 20, tzinfo=UTC),
        datetime(2024, 1, 10, 20, tzinfo=UTC),
        datetime(2024, 1, 11, 20, tzinfo=UTC),
        datetime(2024, 1, 12, 20, tzinfo=UTC),
        datetime(2024, 1, 16, 20, tzinfo=UTC),
        datetime(2024, 1, 17, 20, tzinfo=UTC),
    )
    closes = (
        "100",
        "101",
        "99",
        "102",
        "103",
        "101",
        "104",
        "105",
        "103",
        "106",
        "107",
    )
    bars = tuple(
        Bar(
            symbol,
            timestamp,
            Decimal(close) - Decimal("1"),
            Decimal(close),
            Decimal(close) - Decimal("1"),
            Decimal(close),
            1000 + index,
        )
        for index, (timestamp, close) in enumerate(zip(timestamps, closes, strict=True))
    )
    return HistoricalDataResult(request, bars, "test-memory")


@pytest.fixture
def definition() -> ResearchStrategyDefinition:
    return ResearchStrategyDefinition(
        HEAD,
        TREE,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
    )


@pytest.fixture
def evaluation_policy() -> ResearchStrategyEvaluationPolicy:
    return ResearchStrategyEvaluationPolicy(
        starting_cash=Decimal("10000"),
        fixed_commission=Decimal("0"),
        slippage_basis_points=Decimal("0"),
        trading_enabled=True,
        allow_missing_sessions=False,
        max_position_percent=Decimal("0.20"),
        max_total_exposure_percent=Decimal("0.80"),
        max_order_notional=None,
        max_new_position_percent=None,
        minimum_cash_reserve_percent=Decimal("0.10"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("0"),
    )


@pytest.fixture
def folds() -> tuple[ResearchStrategyWalkForwardFold, ...]:
    return (
        ResearchStrategyWalkForwardFold(
            datetime(2024, 1, 2, 5, tzinfo=UTC),
            datetime(2024, 1, 5, 5, tzinfo=UTC),
            datetime(2024, 1, 5, 5, tzinfo=UTC),
            datetime(2024, 1, 9, 5, tzinfo=UTC),
        ),
        ResearchStrategyWalkForwardFold(
            datetime(2024, 1, 9, 5, tzinfo=UTC),
            datetime(2024, 1, 12, 5, tzinfo=UTC),
            datetime(2024, 1, 12, 5, tzinfo=UTC),
            datetime(2024, 1, 17, 5, tzinfo=UTC),
        ),
    )


@pytest.fixture
def completed(
    definition, evaluation_policy, data, folds
) -> CompletedResearchStrategyWalkForward:
    return run_research_strategy_walk_forward(
        definition,
        evaluation_policy,
        data,
        folds,
        evaluation_source_head=EVALUATION_HEAD,
        evaluation_source_tree=EVALUATION_TREE,
    )


def _qualification_policy() -> ResearchStrategyWalkForwardQualificationPolicy:
    return ResearchStrategyWalkForwardQualificationPolicy(
        minimum_fold_count=2,
        minimum_fold_return=Decimal("-1"),
        minimum_median_return=Decimal("-1"),
        maximum_fold_drawdown_percentage=Decimal("100"),
        require_equal_test_window_bar_count=True,
    )


def test_fold_identity_and_canonical_roundtrip(folds) -> None:
    assert folds[0].fold_id != folds[1].fold_id
    assert ResearchStrategyWalkForwardFold.from_json(folds[0].to_json()) == folds[0]
    raw = json.loads(folds[0].to_json())
    raw["test_end"] = "2024-01-10T00:00:00.000000Z"
    with pytest.raises(ResearchStrategyWalkForwardError):
        ResearchStrategyWalkForwardFold.from_json(
            json.dumps(raw, separators=(",", ":"), sort_keys=True)
        )


def test_walk_forward_runs_independent_roles_without_lookahead(
    completed, folds
) -> None:
    assert isinstance(completed, CompletedResearchStrategyWalkForward)
    assert len(completed.folds) == 2
    for item, fold in zip(completed.folds, folds, strict=True):
        assert item.training.evidence.backtest_run_id == derive_backtest_run_id(
            completed.definition.definition_id,
            completed.evaluation_policy.policy_id,
            item.training.evidence.historical_data_fingerprint,
            fold_role=TRAINING_FOLD_ROLE,
            fold_id=fold.fold_id,
        )
        assert item.test.evidence.backtest_run_id == derive_backtest_run_id(
            completed.definition.definition_id,
            completed.evaluation_policy.policy_id,
            item.test.evidence.historical_data_fingerprint,
            fold_role=TEST_FOLD_ROLE,
            fold_id=fold.fold_id,
        )
        assert (
            item.training.evidence.backtest_run_id != item.test.evidence.backtest_run_id
        )
        assert item.training.historical_data.bars[-1].timestamp < fold.test_start
        assert item.test.historical_data.bars[0].timestamp >= fold.test_start
    verify_research_strategy_walk_forward(completed)


def test_walk_forward_evidence_and_external_replay_are_exact(
    completed, definition, evaluation_policy, data, folds
) -> None:
    evidence = ResearchStrategyWalkForwardEvidence.from_json(
        completed.evidence.to_json()
    )
    assert evidence == completed.evidence
    verify_research_strategy_walk_forward_evidence(
        evidence,
        definition,
        evaluation_policy,
        data,
        folds,
        evaluation_source_head=EVALUATION_HEAD,
        evaluation_source_tree=EVALUATION_TREE,
    )
    forged = replace(
        evidence,
        source_historical_fingerprint=UUID(int=99),
    )
    with pytest.raises(ResearchStrategyWalkForwardError):
        verify_research_strategy_walk_forward_evidence(
            forged,
            definition,
            evaluation_policy,
            data,
            folds,
            evaluation_source_head=EVALUATION_HEAD,
            evaluation_source_tree=EVALUATION_TREE,
        )


def test_qualification_derives_ordered_failures_and_passed_artifact(completed) -> None:
    policy = _qualification_policy()
    qualification = qualify_research_strategy_walk_forward(
        completed,
        policy,
        qualification_source_head=EVALUATION_HEAD,
        qualification_source_tree=EVALUATION_TREE,
    )
    assert qualification.status is Status.PASSED
    assert qualification.failure_reasons == ()
    assert (
        ResearchStrategyWalkForwardQualification.from_json(qualification.to_json())
        == qualification
    )
    passed = build_walk_forward_passed_research_strategy(qualification)
    assert isinstance(passed, WalkForwardPassedResearchStrategy)
    assert WalkForwardPassedResearchStrategy.from_json(passed.to_json()) == passed
    verify_research_strategy_walk_forward_qualification(
        qualification,
        completed,
        policy,
        qualification_source_head=EVALUATION_HEAD,
        qualification_source_tree=EVALUATION_TREE,
    )


def test_qualification_threshold_failures_are_valid_failed_evidence(completed) -> None:
    policy = ResearchStrategyWalkForwardQualificationPolicy(
        minimum_fold_count=3,
        minimum_fold_return=Decimal("100"),
        minimum_median_return=Decimal("100"),
        maximum_fold_drawdown_percentage=Decimal("0"),
        require_equal_test_window_bar_count=True,
    )
    qualification = qualify_research_strategy_walk_forward(
        completed,
        policy,
        qualification_source_head=EVALUATION_HEAD,
        qualification_source_tree=EVALUATION_TREE,
    )
    assert qualification.status is Status.FAILED
    expected_reasons = (
        Reason.INSUFFICIENT_FOLDS,
        Reason.MINIMUM_FOLD_RETURN_BELOW_THRESHOLD,
        Reason.MEDIAN_FOLD_RETURN_BELOW_THRESHOLD,
    )
    if qualification.maximum_observed_fold_drawdown_percentage > Decimal("0"):
        expected_reasons += (Reason.MAXIMUM_FOLD_DRAWDOWN_PERCENTAGE_ABOVE_THRESHOLD,)
    assert qualification.failure_reasons == expected_reasons
    with pytest.raises(ResearchStrategyWalkForwardError):
        build_walk_forward_passed_research_strategy(qualification)


@pytest.mark.parametrize(
    "bad_folds",
    [
        (
            ResearchStrategyWalkForwardFold(
                datetime(2024, 1, 2, tzinfo=UTC),
                datetime(2024, 1, 5, tzinfo=UTC),
                datetime(2024, 1, 5, tzinfo=UTC),
                datetime(2024, 1, 9, tzinfo=UTC),
            ),
            ResearchStrategyWalkForwardFold(
                datetime(2024, 1, 10, tzinfo=UTC),
                datetime(2024, 1, 12, tzinfo=UTC),
                datetime(2024, 1, 12, tzinfo=UTC),
                datetime(2024, 1, 18, tzinfo=UTC),
            ),
        ),
    ],
)
def test_gap_between_folds_is_rejected(
    definition, evaluation_policy, data, bad_folds
) -> None:
    with pytest.raises(ResearchStrategyWalkForwardError):
        run_research_strategy_walk_forward(
            definition,
            evaluation_policy,
            data,
            bad_folds,
            evaluation_source_head=EVALUATION_HEAD,
            evaluation_source_tree=EVALUATION_TREE,
        )


def test_inputs_are_unchanged_on_rejection(
    definition, evaluation_policy, data, folds
) -> None:
    before_data = repr(data)
    before_folds = repr(folds)
    with pytest.raises(ResearchStrategyWalkForwardError):
        run_research_strategy_walk_forward(
            definition,
            evaluation_policy,
            data,
            folds,
            evaluation_source_head="not-a-source",
            evaluation_source_tree=EVALUATION_TREE,
        )
    assert repr(data) == before_data
    assert repr(folds) == before_folds


def test_walk_forward_module_has_no_external_capability_paths() -> None:
    import inspect

    import trading_bot.experiments.research_strategy_walk_forward as module

    tree = ast.parse(inspect.getsource(module))
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports <= {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "uuid",
        "trading_bot.analytics.models",
        "trading_bot.backtesting.models",
        "trading_bot.experiments.research_strategy_backtest",
        "trading_bot.experiments.research_strategy_definition",
        "trading_bot.market_data.models",
    }
    forbidden = {
        "open",
        "exec",
        "eval",
        "__import__",
        "hash",
        "id",
        "float",
        "uuid4",
        "now",
        "utcnow",
        "today",
        "connect",
        "request",
        "send",
        "promote",
        "advance",
        "set_stage",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", "")
            )
            assert name not in forbidden
    source = inspect.getsource(module)
    assert "HistoricalExperimentWalkForwardFold" not in source
    assert "ProductionStrategyContract" not in source
