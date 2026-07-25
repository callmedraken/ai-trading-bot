from dataclasses import fields, replace
from decimal import Context, Decimal, localcontext
from uuid import UUID

import pytest
from tests.experiments.test_walk_forward import _request

from trading_bot.experiments import (
    METRIC_OPERATION_ELIGIBILITY,
    HistoricalExperimentMetrics,
    HistoricalExperimentWalkForwardAggregateAnalyzer,
    HistoricalExperimentWalkForwardAggregateMetric,
    HistoricalExperimentWalkForwardAggregateOperation,
    HistoricalExperimentWalkForwardAggregateOperationError,
    HistoricalExperimentWalkForwardAggregatePolicy,
    HistoricalExperimentWalkForwardAggregateResult,
    HistoricalExperimentWalkForwardExactRational,
    HistoricalExperimentWalkForwardMetricPolicy,
    HistoricalExperimentWalkForwardRunner,
    InconsistentHistoricalExperimentWalkForwardAggregateResultError,
    InvalidHistoricalExperimentWalkForwardAggregatePolicyError,
)
from trading_bot.portfolio import MetadataEntry


def _source():
    from tests.experiments.test_historical import _Factory

    return HistoricalExperimentWalkForwardRunner(_Factory()).run(_request())


def _metric(
    metric: HistoricalExperimentWalkForwardAggregateMetric,
    *operations: HistoricalExperimentWalkForwardAggregateOperation,
) -> HistoricalExperimentWalkForwardMetricPolicy:
    return HistoricalExperimentWalkForwardMetricPolicy(metric, operations)


def _policy(*metrics: HistoricalExperimentWalkForwardMetricPolicy):
    return HistoricalExperimentWalkForwardAggregatePolicy(
        UUID(int=201),
        metrics,
        (MetadataEntry("purpose", "aggregate-test"),),
    )


def test_metric_mapping_exactly_covers_all_historical_metrics() -> None:
    aggregate_fields = tuple(
        item.value.lower() for item in HistoricalExperimentWalkForwardAggregateMetric
    )
    assert aggregate_fields == tuple(
        item.name for item in fields(HistoricalExperimentMetrics)
    )
    assert set(METRIC_OPERATION_ELIGIBILITY) == set(
        HistoricalExperimentWalkForwardAggregateMetric
    )


def test_analyzer_retains_ordered_test_evidence_and_safe_statistics() -> None:
    operations = HistoricalExperimentWalkForwardAggregateOperation
    policy = _policy(
        _metric(
            HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
            operations.SIGN_COUNTS,
            operations.EQUAL_FOLD_ARITHMETIC_MEAN,
            operations.MAXIMUM,
            operations.MINIMUM,
            operations.MEDIAN,
        ),
        _metric(
            HistoricalExperimentWalkForwardAggregateMetric.TOTAL_ORDERS,
            operations.MEDIAN,
            operations.EQUAL_FOLD_ARITHMETIC_MEAN,
            operations.MINIMUM,
            operations.MAXIMUM,
        ),
        _metric(
            HistoricalExperimentWalkForwardAggregateMetric.TOTAL_COMMISSIONS,
        ),
    )
    source = _source()

    result = HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(source, policy)

    assert result.fold_count == result.successful_test_fold_count == 2
    assert tuple(item.fold_ordinal for item in result.fold_summaries) == (0, 1)
    assert result.policy.metrics[0].operations == tuple(operations)
    for metric_index, metric_policy in enumerate(policy.metrics):
        expected = tuple(
            getattr(
                fold.test_report.variants[0].metrics,
                metric_policy.metric.value.lower(),
            )
            for fold in source.folds
        )
        summary = result.metric_summaries[metric_index]
        assert tuple(item.value for item in summary.observations) == expected
        assert (
            tuple(fold.metrics[metric_index] for fold in result.fold_summaries)
            == summary.observations
        )
    commission = result.metric_summaries[2]
    assert (
        commission.minimum,
        commission.maximum,
        commission.median,
        commission.arithmetic_mean,
        commission.sign_counts,
    ) == (None, None, None, None, None)
    assert sum(item.selected_fold_count for item in result.variant_frequencies) == 2
    assert all(
        item.selected_fold_count == item.rank_one_selected_fold_count
        for item in result.variant_frequencies
    )


def test_policy_rejects_duplicates_and_ineligible_operations() -> None:
    operation = HistoricalExperimentWalkForwardAggregateOperation.MINIMUM
    with pytest.raises(InvalidHistoricalExperimentWalkForwardAggregatePolicyError):
        _metric(
            HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
            operation,
            operation,
        )
    with pytest.raises(HistoricalExperimentWalkForwardAggregateOperationError):
        _metric(
            HistoricalExperimentWalkForwardAggregateMetric.TOTAL_COMMISSIONS,
            operation,
        )
    metric = _metric(
        HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
        operation,
    )
    with pytest.raises(InvalidHistoricalExperimentWalkForwardAggregatePolicyError):
        _policy(metric, metric)


def test_exact_rational_mean_and_median_ignore_decimal_context() -> None:
    from trading_bot.experiments.walk_forward_analytics import _mean, _median

    values = (Decimal("0"), Decimal("0"), Decimal("1"))
    with localcontext(Context(prec=1)):
        mean = _mean(values)
        median = _median((Decimal("1.2"), Decimal("1.3")))
    assert mean == HistoricalExperimentWalkForwardExactRational(1, 3)
    assert median == Decimal("1.25")
    assert _median((1, 2)) == Decimal("1.5")


def test_one_fold_behavior_and_variant_frequency() -> None:
    request = replace(_request(), folds=(_request().folds[0],))
    from tests.experiments.test_historical import _Factory

    source = HistoricalExperimentWalkForwardRunner(_Factory()).run(request)
    operation = HistoricalExperimentWalkForwardAggregateOperation
    result = HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(
        source,
        _policy(
            _metric(
                HistoricalExperimentWalkForwardAggregateMetric.TOTAL_ORDERS,
                operation.MINIMUM,
                operation.MAXIMUM,
                operation.MEDIAN,
                operation.EQUAL_FOLD_ARITHMETIC_MEAN,
            )
        ),
    )
    value = source.folds[0].test_report.variants[0].metrics.total_orders
    summary = result.metric_summaries[0]
    assert summary.minimum == summary.maximum == value
    assert summary.median == Decimal(value)
    assert summary.arithmetic_mean == HistoricalExperimentWalkForwardExactRational(
        value, 1
    )
    assert result.variant_frequencies[0].selected_fold_count == 1


def test_identity_is_repeatable_and_context_independent() -> None:
    operation = HistoricalExperimentWalkForwardAggregateOperation
    policy = _policy(
        _metric(
            HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
            operation.MINIMUM,
            operation.EQUAL_FOLD_ARITHMETIC_MEAN,
        )
    )
    source = _source()
    analyzer = HistoricalExperimentWalkForwardAggregateAnalyzer()
    first = analyzer.analyze(source, policy)
    with localcontext(Context(prec=1)):
        second = analyzer.analyze(source, policy)
    assert first == second
    assert first.result_id == second.result_id


def test_result_rejects_tampered_statistics_and_success_count() -> None:
    operation = HistoricalExperimentWalkForwardAggregateOperation
    aggregate = HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(
        _source(),
        _policy(
            _metric(
                HistoricalExperimentWalkForwardAggregateMetric.TOTAL_ORDERS,
                operation.MINIMUM,
            )
        ),
    )
    with pytest.raises(InconsistentHistoricalExperimentWalkForwardAggregateResultError):
        replace(aggregate, successful_test_fold_count=1)
    changed_summary = replace(aggregate.metric_summaries[0], minimum=999)
    with pytest.raises(InconsistentHistoricalExperimentWalkForwardAggregateResultError):
        replace(aggregate, metric_summaries=(changed_summary,))


def test_public_result_is_exact_immutable_model() -> None:
    result = HistoricalExperimentWalkForwardAggregateAnalyzer().analyze(
        _source(),
        _policy(
            _metric(
                HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
                HistoricalExperimentWalkForwardAggregateOperation.SIGN_COUNTS,
            )
        ),
    )
    assert type(result) is HistoricalExperimentWalkForwardAggregateResult
    with pytest.raises((AttributeError, TypeError)):
        result.fold_count = 3  # type: ignore[misc]
