"""Focused Architecture 145-A robustness and canary-evidence coverage."""

import ast
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

import trading_bot.experiments.research_strategy_robustness as subject
from trading_bot.domain import Symbol
from trading_bot.domain.enums import OrderSide
from trading_bot.experiments.research_strategy_robustness import (
    ResearchExecutionStressDisposition,
    ResearchExecutionStressKind,
    ResearchExecutionStressOrder,
    ResearchExecutionStressScenario,
    ResearchRobustnessPartitionRole,
    ResearchStrategyLiveCanaryEligibility,
    ResearchStrategyRobustnessError,
    ResearchStrategyRobustnessEvidence,
    ResearchStrategyRobustnessPartition,
    ResearchStrategyRobustnessQualificationPolicy,
    admit_research_strategy_final_holdout,
    build_research_strategy_live_canary_eligibility,
    simulate_research_execution_stress,
    verify_research_execution_stress_result,
    verify_research_strategy_live_canary_eligibility,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

HEAD = "a" * 40
TREE = "b" * 40
POLICY_HEAD = "c" * 40
POLICY_TREE = "d" * 40
DATA = UUID(int=3)


def _partition(role: ResearchRobustnessPartitionRole, start_day: int, value: int):
    return ResearchStrategyRobustnessPartition(
        role,
        datetime(2020, 1, start_day, tzinfo=UTC),
        datetime(2020, 1, start_day + 10, tzinfo=UTC),
        DATA,
        UUID(int=value),
    )


@pytest.fixture
def scenarios() -> tuple[ResearchExecutionStressScenario, ...]:
    return (
        ResearchExecutionStressScenario(
            "higher-cost",
            ResearchExecutionStressKind.HIGHER_COST,
            Decimal("10"),
            Decimal("1"),
            0,
            None,
        ),
        ResearchExecutionStressScenario(
            "delayed-fill",
            ResearchExecutionStressKind.DELAYED_FILL,
            Decimal("0"),
            Decimal("0"),
            1,
            None,
        ),
        ResearchExecutionStressScenario(
            "missed-fill",
            ResearchExecutionStressKind.MISSED_FILL,
            Decimal("0"),
            Decimal("0"),
            0,
            None,
        ),
        ResearchExecutionStressScenario(
            "rejected-fill",
            ResearchExecutionStressKind.REJECTED_FILL,
            Decimal("0"),
            Decimal("0"),
            0,
            None,
        ),
        ResearchExecutionStressScenario(
            "partial-fill",
            ResearchExecutionStressKind.PARTIAL_FILL,
            Decimal("0"),
            Decimal("0"),
            0,
            Decimal("0.5"),
        ),
    )


@pytest.fixture
def orders() -> tuple[ResearchExecutionStressOrder, ...]:
    return (
        ResearchExecutionStressOrder(
            UUID(int=20),
            Symbol("AAPL"),
            OrderSide.BUY,
            Decimal("10"),
            Decimal("100"),
            Decimal("90"),
            Decimal("100"),
        ),
    )


@pytest.fixture
def stress_results(scenarios, orders):
    return tuple(
        simulate_research_execution_stress(
            scenario, orders, starting_cash=Decimal("10000")
        )
        for scenario in scenarios
    )


@pytest.fixture
def policy(scenarios) -> ResearchStrategyRobustnessQualificationPolicy:
    return ResearchStrategyRobustnessQualificationPolicy(
        UUID(int=1),
        UUID(int=2),
        HEAD,
        TREE,
        "moving_average_crossover",
        "v1",
        Symbol("AAPL"),
        MovingAverageCrossoverConfig(3, 5, Decimal("10")),
        DATA,
        _partition(ResearchRobustnessPartitionRole.DEVELOPMENT, 1, 101),
        _partition(ResearchRobustnessPartitionRole.WALK_FORWARD, 11, 102),
        _partition(ResearchRobustnessPartitionRole.FINAL_HOLDOUT, 21, 103),
        1,
        Decimal("100"),
        Decimal("-1"),
        2,
        Decimal("0"),
        Decimal("0"),
        Decimal("100"),
        Decimal("100"),
        1,
        0,
        Decimal("100"),
        scenarios,
        None,
        POLICY_HEAD,
        POLICY_TREE,
    )


@pytest.fixture
def admission(policy):
    return admit_research_strategy_final_holdout(
        policy,
        admission_source_head=POLICY_HEAD,
        admission_source_tree=POLICY_TREE,
    )


@pytest.fixture
def evidence(policy, admission, stress_results) -> ResearchStrategyRobustnessEvidence:
    return ResearchStrategyRobustnessEvidence(
        policy.policy_id,
        policy.candidate_id,
        policy.strategy_definition_id,
        POLICY_HEAD,
        POLICY_TREE,
        DATA,
        policy.development_partition.partition_id,
        10,
        Decimal("0.2"),
        Decimal("1"),
        policy.walk_forward_partition.partition_id,
        UUID(int=301),
        2,
        2,
        UUID(int=302),
        2,
        2,
        Decimal("1"),
        Decimal("1"),
        UUID(int=303),
        2,
        2,
        Decimal("1"),
        stress_results,
        policy.final_holdout_partition.partition_id,
        admission.admission_id,
        UUID(int=304),
        10,
        Decimal("0.1"),
        Decimal("1"),
        None,
    )


def test_execution_stress_covers_and_reconciles_every_required_dimension(
    scenarios, stress_results
) -> None:
    assert tuple(item.scenario.kind for item in stress_results) == (
        ResearchExecutionStressKind.HIGHER_COST,
        ResearchExecutionStressKind.DELAYED_FILL,
        ResearchExecutionStressKind.MISSED_FILL,
        ResearchExecutionStressKind.REJECTED_FILL,
        ResearchExecutionStressKind.PARTIAL_FILL,
    )
    assert stress_results[0].reconciliation.total_transaction_cost == Decimal("1")
    assert stress_results[1].order_results[0].execution_price == Decimal("90")
    assert (
        stress_results[2].order_results[0].disposition
        is ResearchExecutionStressDisposition.MISSED
    )
    assert (
        stress_results[3].order_results[0].disposition
        is ResearchExecutionStressDisposition.REJECTED
    )
    assert stress_results[4].reconciliation.total_filled_quantity == Decimal("5.0")
    for result in stress_results:
        verify_research_execution_stress_result(result)
        assert result.to_json() == result.to_json()
        assert type(result.from_json(result.to_json())) is type(result)
    assert scenarios == tuple(item.scenario for item in stress_results)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("minimum_completed_trade_count", 2),
        ("maximum_drawdown_percentage", Decimal("99")),
        ("minimum_net_return", Decimal("-0.5")),
        ("minimum_walk_forward_fold_count", 3),
        ("minimum_walk_forward_pass_rate", Decimal("0.1")),
        ("minimum_stability_pass_rate", Decimal("0.1")),
        ("maximum_stability_range", Decimal("99")),
        ("maximum_stability_adjacent_change", Decimal("99")),
        ("minimum_sensitivity_neighborhood_count", 2),
        ("minimum_sensitivity_pass_count", 1),
        ("maximum_sensitivity_return_spread", Decimal("99")),
    ],
)
def test_every_threshold_changes_policy_identity(policy, field_name, value) -> None:
    changed = replace(policy, **{field_name: value})
    assert changed.policy_id != policy.policy_id


def test_policy_round_trip_and_chronological_holdout_isolation(policy) -> None:
    assert (
        ResearchStrategyRobustnessQualificationPolicy.from_json(policy.to_json())
        == policy
    )
    overlapping_partition = replace(
        policy.final_holdout_partition,
        start=datetime(2020, 1, 15, tzinfo=UTC),
    )
    with pytest.raises(ResearchStrategyRobustnessError):
        replace(policy, final_holdout_partition=overlapping_partition)


def test_holdout_admission_prevents_threshold_relaxation(
    policy, admission, evidence
) -> None:
    relaxed = replace(policy, minimum_net_return=Decimal("-2"))
    with pytest.raises(ResearchStrategyRobustnessError):
        build_research_strategy_live_canary_eligibility(relaxed, admission, evidence)
    assert (
        admit_research_strategy_final_holdout(
            policy,
            admission_source_head=POLICY_HEAD,
            admission_source_tree=POLICY_TREE,
        )
        == admission
    )


def test_positive_eligibility_is_reconciled_and_round_trips(
    policy, admission, evidence
):
    eligibility = build_research_strategy_live_canary_eligibility(
        policy, admission, evidence
    )
    verify_research_strategy_live_canary_eligibility(
        eligibility, policy, admission, evidence
    )
    restored = eligibility.from_json(eligibility.to_json())
    assert restored == eligibility
    assert eligibility.status.value == "LIVE_CANARY_ELIGIBLE"


def test_failing_required_stress_cannot_create_eligibility(
    policy, admission, evidence
) -> None:
    strict_policy = replace(policy, minimum_net_return=Decimal("0"))
    strict_admission = admit_research_strategy_final_holdout(
        strict_policy,
        admission_source_head=POLICY_HEAD,
        admission_source_tree=POLICY_TREE,
    )
    strict_evidence = replace(
        evidence,
        policy_id=strict_policy.policy_id,
        holdout_admission_id=strict_admission.admission_id,
    )
    with pytest.raises(ResearchStrategyRobustnessError):
        build_research_strategy_live_canary_eligibility(
            strict_policy, strict_admission, strict_evidence
        )


def test_eligibility_model_is_positive_only(policy, admission, evidence) -> None:
    failing = replace(evidence, final_holdout_net_return=Decimal("-2"))
    with pytest.raises(ResearchStrategyRobustnessError):
        ResearchStrategyLiveCanaryEligibility(policy, admission, failing)


def test_reordered_missing_or_unknown_evidence_fails_closed(evidence):
    encoded = json.loads(evidence.to_json())
    encoded["execution_stress_results"] = list(
        reversed(encoded["execution_stress_results"])
    )
    with pytest.raises(ResearchStrategyRobustnessError):
        ResearchStrategyRobustnessEvidence.from_json(json.dumps(encoded))

    missing = json.loads(evidence.to_json())
    del missing["sensitivity_result_id"]
    with pytest.raises(ResearchStrategyRobustnessError):
        ResearchStrategyRobustnessEvidence.from_json(json.dumps(missing))

    unknown = json.loads(evidence.to_json())
    unknown["unexpected"] = True
    with pytest.raises(ResearchStrategyRobustnessError):
        ResearchStrategyRobustnessEvidence.from_json(json.dumps(unknown))


def test_noncanonical_and_float_thresholds_fail_closed(policy):
    raw = json.loads(policy.to_json())
    raw["minimum_net_return"] = 0.1
    with pytest.raises(ResearchStrategyRobustnessError):
        ResearchStrategyRobustnessQualificationPolicy.from_json(json.dumps(raw))

    duplicate = policy.to_json().replace(
        '"schema":"research-strategy-robustness-qualification-policy/v1",',
        '"schema":"research-strategy-robustness-qualification-policy/v1",'
        '"schema":"research-strategy-robustness-qualification-policy/v1",',
    )
    with pytest.raises(ResearchStrategyRobustnessError):
        ResearchStrategyRobustnessQualificationPolicy.from_json(duplicate)


def test_source_has_no_lookahead_or_operational_capability() -> None:
    path = Path(subject.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    source = path.read_text(encoding="utf-8")
    assert "datetime.now" not in source
    assert "uuid4" not in source
    assert not {
        "F1_NAMESPACE_READS",
        "F1_NAMESPACE_WRITES",
        "PRODUCTION_SQLITE_READS",
        "PRODUCTION_SQLITE_WRITES",
        "CREDENTIAL_READS",
        "CREDENTIAL_WRITES",
        "PROVIDER_CALLS",
        "BROKER_CALLS",
        "SCHEDULER_CALLS",
        "PAPER_MUTATIONS",
        "D1_OPERATIONS",
        "D2_OPERATIONS",
        "STRATEGY_PROMOTIONS",
        "REAL_MONEY_EFFECTS",
    } & set(source.split())
    assert "simulate_research_execution_stress" in names
    assert "build_research_strategy_live_canary_eligibility" in names
    assert all(
        node.module not in {"sqlite3", "subprocess", "socket", "pathlib"}
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
