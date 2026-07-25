from dataclasses import replace
from decimal import Context, Decimal, localcontext
from uuid import UUID

import pytest
from tests.experiments.test_historical import _Factory
from tests.experiments.test_walk_forward import START, _request
from tests.experiments.test_walk_forward_analytics import _source

from trading_bot.experiments import (
    HistoricalExperimentWalkForwardAggregateAnalyzer,
    HistoricalExperimentWalkForwardAggregateMetric,
    HistoricalExperimentWalkForwardAggregatePolicy,
    HistoricalExperimentWalkForwardComparabilityRule,
    HistoricalExperimentWalkForwardMetricPolicy,
    HistoricalExperimentWalkForwardRunner,
    HistoricalExperimentWalkForwardStabilityAnalyzer,
    HistoricalExperimentWalkForwardStabilityComparabilityError,
    HistoricalExperimentWalkForwardStabilityMetric,
    HistoricalExperimentWalkForwardStabilityMetricPolicy,
    HistoricalExperimentWalkForwardStabilityOperation,
    HistoricalExperimentWalkForwardStabilityOperationError,
    HistoricalExperimentWalkForwardStabilityPolicy,
    InconsistentHistoricalExperimentWalkForwardStabilityResultError,
    InvalidHistoricalExperimentWalkForwardStabilityPolicyError,
)

OPERATION = HistoricalExperimentWalkForwardStabilityOperation
M = HistoricalExperimentWalkForwardStabilityMetric
C = HistoricalExperimentWalkForwardComparabilityRule


def _metric(
    metric: HistoricalExperimentWalkForwardStabilityMetric,
    operations: tuple[HistoricalExperimentWalkForwardStabilityOperation, ...] = (),
    comparability: HistoricalExperimentWalkForwardComparabilityRule = C.NONE,
) -> HistoricalExperimentWalkForwardStabilityMetricPolicy:
    return HistoricalExperimentWalkForwardStabilityMetricPolicy(
        metric, operations, comparability
    )


def _policy(
    *metrics: HistoricalExperimentWalkForwardStabilityMetricPolicy,
) -> HistoricalExperimentWalkForwardStabilityPolicy:
    return HistoricalExperimentWalkForwardStabilityPolicy(UUID(int=301), metrics)


def test_selection_stability_retains_order_self_transitions_and_runs() -> None:
    source = _source()
    result = HistoricalExperimentWalkForwardStabilityAnalyzer().analyze(
        source, _policy(_metric(M.TOTAL_COMMISSIONS))
    )

    stability = result.selection_stability
    selected = tuple(fold.selection.selected_variant_id for fold in source.folds)
    assert (
        tuple(item.selected_variant_id for item in stability.observations) == selected
    )
    assert stability.unique_selected_variant_count == 1
    assert stability.persistence_adjacency_count == 1
    assert stability.changed_adjacency_count == 0
    assert (
        stability.persistence_ratio.numerator,
        stability.persistence_ratio.denominator,
    ) == (1, 1)
    assert stability.longest_consecutive_selection_run == 2
    assert stability.runs[0].consecutive_fold_count == 2
    transition = stability.transitions[0]
    assert transition.from_variant_id == transition.to_variant_id == selected[0]
    assert transition.changed is False
    assert stability.transition_frequencies[0].occurrence_count == 1
    assert stability.variant_frequencies[0].first_selected_fold_ordinal == 0


def test_metric_stability_is_exact_and_decimal_context_independent() -> None:
    policy = _policy(
        _metric(
            M.SIMULATION_RETURN,
            (
                _CHANGE := OPERATION.ADJACENT_ABSOLUTE_CHANGE,
                OPERATION.RANGE,
                OPERATION.MEDIAN_ABSOLUTE_DEVIATION,
            ),
            C.EQUAL_TEST_DURATION,
        ),
        _metric(
            M.TOTAL_ORDERS,
            (OPERATION.RANGE, OPERATION.MEDIAN_ABSOLUTE_DEVIATION),
            C.EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT,
        ),
    )
    source = _source()
    analyzer = HistoricalExperimentWalkForwardStabilityAnalyzer()
    first = analyzer.analyze(source, policy)
    with localcontext(Context(prec=1)):
        second = analyzer.analyze(source, policy)

    assert _CHANGE is OPERATION.ADJACENT_ABSOLUTE_CHANGE
    assert first == second
    assert first.result_id == second.result_id
    decimal_summary, integer_summary = first.metric_stability
    assert type(decimal_summary.value_range) is Decimal
    assert type(decimal_summary.adjacent_changes[0].absolute_change) is Decimal
    assert type(integer_summary.value_range) is int
    assert decimal_summary.median is not None
    assert decimal_summary.median_absolute_deviation is not None


def test_observations_only_and_sign_only_do_not_populate_magnitude_fields() -> None:
    result = HistoricalExperimentWalkForwardStabilityAnalyzer().analyze(
        _source(),
        _policy(
            _metric(M.TOTAL_COMMISSIONS),
            _metric(
                M.ABSOLUTE_SIMULATION_PROFIT_LOSS,
                (OPERATION.SIGN_CHANGE_COUNT,),
            ),
        ),
    )
    observations_only, sign_only = result.metric_stability
    assert observations_only.observations
    assert (
        observations_only.adjacent_changes,
        observations_only.value_range,
        observations_only.median,
        observations_only.median_absolute_deviation,
        observations_only.sign_change_count,
    ) == ((), None, None, None, None)
    assert sign_only.median is None
    assert sign_only.sign_change_count == 0


def test_policy_enforces_operation_eligibility_and_comparability() -> None:
    with pytest.raises(HistoricalExperimentWalkForwardStabilityOperationError):
        _metric(M.TOTAL_COMMISSIONS, (OPERATION.RANGE,), C.EQUAL_TEST_DURATION)
    with pytest.raises(InvalidHistoricalExperimentWalkForwardStabilityPolicyError):
        _metric(M.TOTAL_ORDERS, (OPERATION.RANGE,), C.EQUAL_TEST_DURATION)
    with pytest.raises(InvalidHistoricalExperimentWalkForwardStabilityPolicyError):
        _metric(M.SIMULATION_RETURN, (), C.EQUAL_TEST_DURATION)
    with pytest.raises(InvalidHistoricalExperimentWalkForwardStabilityPolicyError):
        _policy(_metric(M.SIMULATION_RETURN), _metric(M.SIMULATION_RETURN))


def test_adjacent_and_collection_comparability_reject_unequal_durations() -> None:
    request = _request()
    shorter = replace(
        request.folds[0],
        test_end=START
        + (request.folds[0].test_end - START)
        - (request.folds[0].test_end - request.folds[0].test_start) / 4,
    )
    source = HistoricalExperimentWalkForwardRunner(_Factory()).run(
        replace(request, folds=(shorter, request.folds[1]))
    )
    analyzer = HistoricalExperimentWalkForwardStabilityAnalyzer()
    with pytest.raises(HistoricalExperimentWalkForwardStabilityComparabilityError):
        analyzer.analyze(
            source,
            _policy(
                _metric(
                    M.SIMULATION_RETURN,
                    (OPERATION.ADJACENT_ABSOLUTE_CHANGE,),
                    C.EQUAL_TEST_DURATION,
                )
            ),
        )
    with pytest.raises(HistoricalExperimentWalkForwardStabilityComparabilityError):
        analyzer.analyze(
            source,
            _policy(
                _metric(
                    M.SIMULATION_RETURN,
                    (OPERATION.MEDIAN_ABSOLUTE_DEVIATION,),
                    C.EQUAL_TEST_DURATION,
                )
            ),
        )


def test_optional_aggregate_is_reconciled_and_bound_into_identity() -> None:
    source = _source()
    aggregate = HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(
        source,
        HistoricalExperimentWalkForwardAggregatePolicy(
            UUID(int=302),
            (
                HistoricalExperimentWalkForwardMetricPolicy(
                    HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
                    (),
                ),
            ),
        ),
    )
    policy = _policy(_metric(M.SIMULATION_RETURN))
    analyzer = HistoricalExperimentWalkForwardStabilityAnalyzer()
    without = analyzer.analyze(source, policy)
    with_aggregate = analyzer.analyze(source, policy, aggregate)

    assert without.metric_stability == with_aggregate.metric_stability
    assert without.selection_stability == with_aggregate.selection_stability
    assert without.result_id != with_aggregate.result_id
    assert with_aggregate.source_aggregate_result_id == aggregate.result_id


def test_zero_mediated_reversals_are_not_sign_changes() -> None:
    from trading_bot.experiments.walk_forward_stability import _sign_change_count

    assert _sign_change_count((Decimal("1"), Decimal("0"), Decimal("-1"))) == 0
    assert _sign_change_count((Decimal("1"), Decimal("-1"), Decimal("1"))) == 2
    assert _sign_change_count((Decimal("-0"), Decimal("1"))) == 0


def test_one_fold_behavior_and_tamper_reconciliation() -> None:
    request = replace(_request(), folds=(_request().folds[0],))
    source = HistoricalExperimentWalkForwardRunner(_Factory()).run(request)
    result = HistoricalExperimentWalkForwardStabilityAnalyzer().analyze(
        source,
        _policy(
            _metric(
                M.SIMULATION_RETURN,
                (
                    OPERATION.RANGE,
                    OPERATION.MEDIAN_ABSOLUTE_DEVIATION,
                    OPERATION.SIGN_CHANGE_COUNT,
                ),
                C.EQUAL_TEST_DURATION,
            )
        ),
    )
    selection = result.selection_stability
    assert selection.transitions == ()
    assert selection.transition_frequencies == ()
    assert selection.persistence_ratio is None
    assert selection.longest_consecutive_selection_run == 1
    summary = result.metric_stability[0]
    assert summary.value_range == Decimal("0")
    assert summary.median_absolute_deviation == Decimal("0")
    assert summary.sign_change_count == 0
    with pytest.raises(InconsistentHistoricalExperimentWalkForwardStabilityResultError):
        replace(result, fold_count=2)
