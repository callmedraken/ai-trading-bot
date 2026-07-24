from dataclasses import fields, replace
from decimal import Context, Decimal, localcontext
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest
from tests.experiments.test_pairwise import _report

from trading_bot.experiments import (
    HistoricalExperimentParetoAnalyzer,
    HistoricalExperimentParetoObjective,
    HistoricalExperimentParetoObjectiveComparison,
    HistoricalExperimentParetoPolicy,
    HistoricalExperimentParetoVariant,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    InconsistentHistoricalExperimentParetoResultError,
    InvalidHistoricalExperimentParetoPolicyError,
)
from trading_bot.experiments.historical import HistoricalExperimentMetrics
from trading_bot.experiments.pareto import _METRIC_FIELDS
from trading_bot.portfolio import MetadataEntry

M = HistoricalExperimentRankingMetric
D = HistoricalExperimentRankingDirection
POLICY_ID = UUID(int=901)


def _objective(
    metric: HistoricalExperimentRankingMetric = M.SIMULATION_RETURN,
    direction: HistoricalExperimentRankingDirection = D.DESCENDING,
) -> HistoricalExperimentParetoObjective:
    return HistoricalExperimentParetoObjective(metric, direction)


def _policy(
    *objectives: HistoricalExperimentParetoObjective,
    policy_id: UUID = POLICY_ID,
    metadata: tuple[MetadataEntry, ...] = (),
) -> HistoricalExperimentParetoPolicy:
    return HistoricalExperimentParetoPolicy(
        policy_id, objectives or (_objective(),), metadata
    )


def _analyze(changes, policy=None):  # type: ignore[no-untyped-def]
    return HistoricalExperimentParetoAnalyzer().analyze(
        _report(
            identifiers=tuple(range(10, 10 + len(changes))),
            changes=tuple(changes),
        ),
        policy or _policy(),
    )


def test_metric_mapping_is_exact_complete_and_immutable() -> None:
    assert isinstance(_METRIC_FIELDS, MappingProxyType)
    assert set(_METRIC_FIELDS) == set(M)
    assert len(_METRIC_FIELDS) == len(set(_METRIC_FIELDS.values())) == 26
    assert set(_METRIC_FIELDS.values()) == {
        item.name for item in fields(HistoricalExperimentMetrics)
    }
    assert all("." not in value for value in _METRIC_FIELDS.values())
    with pytest.raises(TypeError):
        _METRIC_FIELDS[M.FINAL_EQUITY] = "x"  # type: ignore[index]


def test_policy_copies_ordered_objectives_and_metadata() -> None:
    objectives = [_objective(), _objective(M.TOTAL_ORDERS, D.ASCENDING)]
    metadata = [MetadataEntry("owner", "research")]
    policy = HistoricalExperimentParetoPolicy(UUID(int=1), objectives, metadata)
    objectives.clear()
    metadata.clear()
    assert tuple(item.metric for item in policy.objectives) == (
        M.SIMULATION_RETURN,
        M.TOTAL_ORDERS,
    )
    assert policy.metadata == (MetadataEntry("owner", "research"),)


@pytest.mark.parametrize(
    "arguments",
    (
        ("bad", (_objective(),), ()),
        (uuid4(), (), ()),
        (uuid4(), (_objective(), _objective()), ()),
        (uuid4(), ("bad",), ()),
        (uuid4(), (_objective(),), ("bad",)),
        (
            uuid4(),
            (_objective(),),
            (MetadataEntry("historical_experiment_pareto_x", "1"),),
        ),
    ),
)
def test_invalid_policy_shapes_are_rejected(arguments: tuple) -> None:
    with pytest.raises(InvalidHistoricalExperimentParetoPolicyError):
        HistoricalExperimentParetoPolicy(*arguments)


def test_ascending_descending_and_mixed_dominance() -> None:
    result = _analyze(
        [
            {"simulation_return": Decimal("3"), "total_orders": 2},
            {"simulation_return": Decimal("2"), "total_orders": 3},
            {"simulation_return": Decimal("1"), "total_orders": 1},
        ],
        _policy(
            _objective(M.SIMULATION_RETURN, D.DESCENDING),
            _objective(M.TOTAL_ORDERS, D.ASCENDING),
        ),
    )
    assert len(result.dominance_records) == 1
    assert result.dominance_records[0].dominator_caller_ordinal == 0
    assert result.dominance_records[0].dominated_caller_ordinal == 1
    assert tuple(
        item.caller_ordinal for item in result.variants if item.is_nondominated
    ) == (
        0,
        2,
    )


def test_right_side_dominance_retains_source_pair_order() -> None:
    result = _analyze(
        [
            {"simulation_return": Decimal("1")},
            {"simulation_return": Decimal("3")},
            {"simulation_return": Decimal("2")},
        ]
    )
    assert [
        (item.dominator_caller_ordinal, item.dominated_caller_ordinal)
        for item in result.dominance_records
    ] == [(1, 0), (2, 0), (1, 2)]
    assert result.variants[0].dominated_by_variant_ids == (
        result.variants[1].variant_id,
        result.variants[2].variant_id,
    )
    assert result.frontier_variant_ids == (result.variants[1].variant_id,)


def test_equal_and_incomparable_vectors_are_nondominating() -> None:
    result = _analyze(
        [
            {"simulation_return": Decimal("1"), "total_orders": 1},
            {"simulation_return": Decimal("1"), "total_orders": 1},
            {"simulation_return": Decimal("2"), "total_orders": 2},
        ],
        _policy(_objective(), _objective(M.TOTAL_ORDERS, D.ASCENDING)),
    )
    assert result.dominance_records == ()
    assert result.frontier_variant_ids == tuple(
        item.variant_id for item in result.variants
    )


def test_one_variant_and_one_objective_are_valid() -> None:
    report = _report(identifiers=(10,))
    result = HistoricalExperimentParetoAnalyzer().analyze(report, _policy())
    assert result.frontier_variant_ids == (report.variants[0].variant_id,)
    assert result.dominance_records == ()
    assert result.variants[0].is_nondominated


def test_evidence_retains_all_objectives_and_exact_types() -> None:
    result = _analyze(
        [
            {"simulation_return": Decimal("2"), "total_orders": 1},
            {"simulation_return": Decimal("1"), "total_orders": 1},
        ],
        _policy(_objective(), _objective(M.TOTAL_ORDERS, D.ASCENDING)),
    )
    evidence = result.dominance_records[0].objective_values
    assert [item.strictly_better for item in evidence] == [True, False]
    assert type(evidence[0].dominator_value) is Decimal
    assert type(evidence[1].dominator_value) is int


def test_hostile_decimal_context_and_signed_zero_are_stable() -> None:
    policy = _policy()
    report = _report(
        changes=(
            {"simulation_return": Decimal("-0")},
            {"simulation_return": Decimal("0")},
            {"simulation_return": Decimal("1E+999")},
        )
    )
    expected = HistoricalExperimentParetoAnalyzer().analyze(report, policy)
    with localcontext(Context(prec=1, Emax=1, Emin=-1)):
        actual = HistoricalExperimentParetoAnalyzer().analyze(report, policy)
    assert actual == expected
    assert len(actual.dominance_records) == 2


def test_result_identity_is_deterministic_and_policy_sensitive() -> None:
    report = _report()
    first = HistoricalExperimentParetoAnalyzer().analyze(report, _policy())
    second = HistoricalExperimentParetoAnalyzer().analyze(report, _policy())
    changed = HistoricalExperimentParetoAnalyzer().analyze(
        report, _policy(policy_id=UUID(int=902))
    )
    assert first == second
    assert first.result_id != changed.result_id


def test_retained_models_reject_inconsistent_relationships() -> None:
    result = _analyze(
        [
            {"simulation_return": Decimal("2")},
            {"simulation_return": Decimal("1")},
            {"simulation_return": Decimal("0")},
        ]
    )
    with pytest.raises(InconsistentHistoricalExperimentParetoResultError):
        replace(result, result_id=uuid4())
    with pytest.raises(InconsistentHistoricalExperimentParetoResultError):
        replace(result, frontier_variant_ids=())
    with pytest.raises(InconsistentHistoricalExperimentParetoResultError):
        replace(
            result.variants[0],
            dominated_by_variant_ids=(result.variants[0].variant_id,),
        )
    record = result.dominance_records[0]
    with pytest.raises(InconsistentHistoricalExperimentParetoResultError):
        replace(
            record,
            objective_values=(
                replace(record.objective_values[0], strictly_better=False),
            ),
        )


def test_public_models_require_exact_types() -> None:
    with pytest.raises(InvalidHistoricalExperimentParetoPolicyError):
        HistoricalExperimentParetoObjective("SIMULATION_RETURN", D.DESCENDING)  # type: ignore[arg-type]
    with pytest.raises(InconsistentHistoricalExperimentParetoResultError):
        HistoricalExperimentParetoVariant(0, uuid4(), 1, (), ())  # type: ignore[arg-type]
    with pytest.raises(InconsistentHistoricalExperimentParetoResultError):
        HistoricalExperimentParetoObjectiveComparison(
            _objective(M.TOTAL_ORDERS),
            True,
            1,
            False,  # type: ignore[arg-type]
        )
