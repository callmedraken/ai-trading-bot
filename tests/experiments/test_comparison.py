from copy import copy
from dataclasses import replace
from decimal import Context, Decimal, localcontext
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest
from tests.experiments.test_historical import _Factory, _request

from trading_bot.experiments import (
    HistoricalExperimentComparator,
    HistoricalExperimentComparisonResult,
    HistoricalExperimentMetricError,
    HistoricalExperimentRankedRun,
    HistoricalExperimentRankingCriterion,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentRankingPolicy,
    HistoricalExperimentResult,
    HistoricalExperimentRunner,
    HistoricalExperimentTieBreaker,
    InconsistentHistoricalExperimentComparisonResultError,
    InvalidHistoricalExperimentRankingPolicyError,
)
from trading_bot.experiments.comparison import _METRIC_FIELDS, _identity_value
from trading_bot.portfolio import MetadataEntry

M = HistoricalExperimentRankingMetric
D = HistoricalExperimentRankingDirection
T = HistoricalExperimentTieBreaker
POLICY_ID = UUID("00000000-0000-0000-0000-000000000501")

EXPECTED_FIELDS = {
    M.INITIAL_EQUITY: "initial_equity",
    M.FINAL_EQUITY: "final_equity",
    M.ABSOLUTE_SIMULATION_PROFIT_LOSS: "absolute_simulation_profit_loss",
    M.SIMULATION_RETURN: "simulation_return",
    M.MAXIMUM_DRAWDOWN_AMOUNT: "maximum_drawdown_amount",
    M.MAXIMUM_DRAWDOWN_PERCENTAGE: "maximum_drawdown_percentage",
    M.SIMULATION_REALIZED_PROFIT_LOSS: "simulation_realized_profit_loss",
    M.TOTAL_COMMISSIONS: "total_commissions",
    M.ADVERSE_SLIPPAGE_COST: "adverse_slippage_cost",
    M.TOTAL_EXECUTION_COST: "total_execution_cost",
    M.AGGREGATE_ONE_WAY_TURNOVER: "aggregate_one_way_turnover",
    M.AGGREGATE_TWO_WAY_TURNOVER: "aggregate_two_way_turnover",
    M.MAXIMUM_ALLOCATION_DRIFT: "maximum_allocation_drift",
    M.TOTAL_ORDERS: "total_orders",
    M.TOTAL_FILLS: "total_fills",
    M.APPROVED_DECISIONS: "approved_decisions",
    M.RESIZED_DECISIONS: "resized_decisions",
    M.REJECTED_DECISIONS: "rejected_decisions",
    M.REJECTED_NOTIONAL: "rejected_notional",
    M.REDUCED_NOTIONAL: "reduced_notional",
    M.MEAN_EXPECTED_PORTFOLIO_RETURN: "mean_expected_portfolio_return",
    M.WORST_CVAR: "worst_cvar",
    M.MINIMUM_TARGET_CASH_WEIGHT: "minimum_target_cash_weight",
    M.MAXIMUM_TARGET_CASH_WEIGHT: "maximum_target_cash_weight",
    M.APPLIED_CYCLE_COUNT: "applied_cycle_count",
    M.NO_ACTION_CYCLE_COUNT: "no_action_cycle_count",
}


@pytest.fixture(scope="module")
def source_result() -> HistoricalExperimentResult:
    return HistoricalExperimentRunner(_Factory()).run(_request())


def _policy(
    *criteria: tuple[
        HistoricalExperimentRankingMetric,
        HistoricalExperimentRankingDirection,
    ],
    tie_breaker: HistoricalExperimentTieBreaker = T.CALLER_ORDER,
    policy_id: UUID = POLICY_ID,
    metadata: tuple[MetadataEntry, ...] = (),
) -> HistoricalExperimentRankingPolicy:
    return HistoricalExperimentRankingPolicy(
        policy_id,
        tuple(HistoricalExperimentRankingCriterion(*item) for item in criteria),
        tie_breaker,
        metadata,
    )


def _with_metrics(
    source: HistoricalExperimentResult, *changes: dict[str, Decimal | int]
) -> HistoricalExperimentResult:
    result = copy(source)
    runs = []
    for run, values in zip(source.runs, changes, strict=True):
        cloned = copy(run)
        object.__setattr__(cloned, "metrics", replace(run.metrics, **values))
        runs.append(cloned)
    object.__setattr__(result, "runs", tuple(runs))
    return result


def _reordered(source: HistoricalExperimentResult) -> HistoricalExperimentResult:
    request = copy(source.request)
    variants = tuple(reversed(source.request.variants))
    object.__setattr__(request, "variants", variants)
    runs = []
    for ordinal, original in enumerate(reversed(source.runs)):
        run = copy(original)
        object.__setattr__(run, "ordinal", ordinal)
        runs.append(run)
    result = copy(source)
    object.__setattr__(result, "request", request)
    object.__setattr__(result, "runs", tuple(runs))
    return result


def test_metric_mapping_is_immutable_complete_unique_and_exact() -> None:
    assert isinstance(_METRIC_FIELDS, MappingProxyType)
    assert dict(_METRIC_FIELDS) == EXPECTED_FIELDS
    assert set(_METRIC_FIELDS) == set(M)
    assert len(set(_METRIC_FIELDS.values())) == len(M)
    with pytest.raises(TypeError):
        _METRIC_FIELDS[M.FINAL_EQUITY] = "changed"  # type: ignore[index]


def test_valid_one_and_multiple_criterion_policies_copy_inputs() -> None:
    criteria = [HistoricalExperimentRankingCriterion(M.SIMULATION_RETURN, D.DESCENDING)]
    metadata = [MetadataEntry("owner", "research")]
    policy = HistoricalExperimentRankingPolicy(
        uuid4(), criteria, T.CALLER_ORDER, metadata
    )
    criteria.clear()
    metadata.clear()
    assert len(policy.criteria) == 1
    assert policy.metadata == (MetadataEntry("owner", "research"),)

    multiple = _policy(
        (M.SIMULATION_RETURN, D.DESCENDING),
        (M.MAXIMUM_DRAWDOWN_PERCENTAGE, D.ASCENDING),
    )
    assert len(multiple.criteria) == 2


@pytest.mark.parametrize(
    "arguments",
    (
        (uuid4(), (), T.CALLER_ORDER, ()),
        ("bad", ((M.SIMULATION_RETURN, D.DESCENDING),), T.CALLER_ORDER, ()),
        (
            uuid4(),
            (
                HistoricalExperimentRankingCriterion(M.SIMULATION_RETURN, D.DESCENDING),
                HistoricalExperimentRankingCriterion(M.SIMULATION_RETURN, D.ASCENDING),
            ),
            T.CALLER_ORDER,
            (),
        ),
        (
            uuid4(),
            (HistoricalExperimentRankingCriterion(M.SIMULATION_RETURN, D.DESCENDING),),
            "CALLER_ORDER",
            (),
        ),
    ),
)
def test_invalid_policy_shapes_are_rejected(arguments: tuple) -> None:
    with pytest.raises(InvalidHistoricalExperimentRankingPolicyError):
        HistoricalExperimentRankingPolicy(*arguments)


def test_invalid_criterion_types_and_metadata_are_rejected() -> None:
    with pytest.raises(InvalidHistoricalExperimentRankingPolicyError):
        HistoricalExperimentRankingCriterion("SIMULATION_RETURN", D.DESCENDING)
    with pytest.raises(InvalidHistoricalExperimentRankingPolicyError):
        HistoricalExperimentRankingCriterion(M.SIMULATION_RETURN, "DESCENDING")
    criterion = HistoricalExperimentRankingCriterion(M.SIMULATION_RETURN, D.DESCENDING)
    with pytest.raises(InvalidHistoricalExperimentRankingPolicyError):
        HistoricalExperimentRankingPolicy(
            uuid4(),
            (criterion,),
            T.CALLER_ORDER,
            (MetadataEntry("same", "1"), MetadataEntry("same", "2")),
        )
    with pytest.raises(InvalidHistoricalExperimentRankingPolicyError):
        HistoricalExperimentRankingPolicy(
            uuid4(),
            (criterion,),
            T.CALLER_ORDER,
            (MetadataEntry("historical_experiment_comparison_bad", "x"),),
        )


@pytest.mark.parametrize(
    ("metric", "direction", "values", "expected"),
    (
        (M.SIMULATION_RETURN, D.DESCENDING, ("0.1", "0.2"), (1, 0)),
        (M.MAXIMUM_DRAWDOWN_PERCENTAGE, D.ASCENDING, ("0.2", "0.1"), (1, 0)),
        (M.TOTAL_EXECUTION_COST, D.ASCENDING, ("2", "1"), (1, 0)),
        (M.ABSOLUTE_SIMULATION_PROFIT_LOSS, D.DESCENDING, ("-2", "0"), (1, 0)),
    ),
)
def test_exact_decimal_ordering(
    source_result: HistoricalExperimentResult,
    metric: HistoricalExperimentRankingMetric,
    direction: HistoricalExperimentRankingDirection,
    values: tuple[str, str],
    expected: tuple[int, int],
) -> None:
    field = EXPECTED_FIELDS[metric]
    source = _with_metrics(
        source_result,
        {field: Decimal(values[0])},
        {field: Decimal(values[1])},
    )
    result = HistoricalExperimentComparator().compare(
        source, _policy((metric, direction))
    )
    assert tuple(item.caller_ordinal for item in result.ranked_runs) == expected
    assert result.ranked_runs[0].comparison_values == (Decimal(values[expected[0]]),)


def test_integer_and_mixed_direction_criteria(
    source_result: HistoricalExperimentResult,
) -> None:
    source = _with_metrics(
        source_result,
        {"total_orders": 2, "simulation_return": Decimal("0.1")},
        {"total_orders": 1, "simulation_return": Decimal("0.1")},
    )
    policy = _policy(
        (M.SIMULATION_RETURN, D.DESCENDING),
        (M.TOTAL_ORDERS, D.ASCENDING),
    )
    result = HistoricalExperimentComparator().compare(source, policy)
    assert tuple(item.caller_ordinal for item in result.ranked_runs) == (1, 0)
    assert result.ranked_runs[0].comparison_values == (Decimal("0.1"), 1)


def test_third_criterion_resolves_first_two_ties(
    source_result: HistoricalExperimentResult,
) -> None:
    source = _with_metrics(
        source_result,
        {
            "simulation_return": Decimal("1"),
            "total_orders": 1,
            "total_execution_cost": Decimal("2"),
        },
        {
            "simulation_return": Decimal("1"),
            "total_orders": 1,
            "total_execution_cost": Decimal("1"),
        },
    )
    result = HistoricalExperimentComparator().compare(
        source,
        _policy(
            (M.SIMULATION_RETURN, D.DESCENDING),
            (M.TOTAL_ORDERS, D.ASCENDING),
            (M.TOTAL_EXECUTION_COST, D.ASCENDING),
        ),
    )
    assert tuple(item.caller_ordinal for item in result.ranked_runs) == (1, 0)


def test_high_precision_decimal_order_is_exact(
    source_result: HistoricalExperimentResult,
) -> None:
    source = _with_metrics(
        source_result,
        {"simulation_return": Decimal("0.1000000000000000000000000001")},
        {"simulation_return": Decimal("0.1000000000000000000000000002")},
    )
    result = HistoricalExperimentComparator().compare(
        source, _policy((M.SIMULATION_RETURN, D.DESCENDING))
    )
    assert result.ranked_runs[0].caller_ordinal == 1


def test_complete_tie_uses_explicit_caller_order(
    source_result: HistoricalExperimentResult,
) -> None:
    result = HistoricalExperimentComparator().compare(
        source_result, _policy((M.INITIAL_EQUITY, D.ASCENDING))
    )
    assert tuple(item.caller_ordinal for item in result.ranked_runs) == (0, 1)
    assert tuple(item.rank for item in result.ranked_runs) == (1, 2)


def test_complete_tie_uses_variant_uuid_integer(
    source_result: HistoricalExperimentResult,
) -> None:
    result = HistoricalExperimentComparator().compare(
        source_result,
        _policy(
            (M.INITIAL_EQUITY, D.ASCENDING),
            tie_breaker=T.VARIANT_ID,
        ),
    )
    expected = tuple(
        item.ordinal
        for item in sorted(
            source_result.runs, key=lambda item: item.variant.variant_id.int
        )
    )
    assert tuple(item.caller_ordinal for item in result.ranked_runs) == expected


def test_caller_order_is_preserved_and_exact_runs_are_retained(
    source_result: HistoricalExperimentResult,
) -> None:
    before = source_result.runs
    result = HistoricalExperimentComparator().compare(
        source_result, _policy((M.FINAL_EQUITY, D.DESCENDING))
    )
    assert source_result.runs is before
    assert result.experiment_result is source_result
    for ranked in result.ranked_runs:
        assert ranked.run is source_result.runs[ranked.caller_ordinal]


def test_reordered_source_only_changes_caller_order_ties(
    source_result: HistoricalExperimentResult,
) -> None:
    reordered = _reordered(source_result)
    tie_policy = _policy((M.INITIAL_EQUITY, D.ASCENDING))
    tied = HistoricalExperimentComparator().compare(reordered, tie_policy)
    assert tuple(item.run.variant for item in tied.ranked_runs) == tuple(
        reversed(source_result.request.variants)
    )

    distinct = _with_metrics(
        reordered,
        {"simulation_return": Decimal("2")},
        {"simulation_return": Decimal("1")},
    )
    ranked = HistoricalExperimentComparator().compare(
        distinct, _policy((M.SIMULATION_RETURN, D.DESCENDING))
    )
    assert ranked.ranked_runs[0].comparison_values == (Decimal("2"),)


def test_variant_id_tie_order_is_independent_of_source_order(
    source_result: HistoricalExperimentResult,
) -> None:
    policy = _policy((M.INITIAL_EQUITY, D.ASCENDING), tie_breaker=T.VARIANT_ID)
    first = HistoricalExperimentComparator().compare(source_result, policy)
    second = HistoricalExperimentComparator().compare(_reordered(source_result), policy)
    assert tuple(item.run.variant.variant_id for item in first.ranked_runs) == tuple(
        item.run.variant.variant_id for item in second.ranked_runs
    )


def test_equal_inputs_produce_equal_comparison_and_identity(
    source_result: HistoricalExperimentResult,
) -> None:
    policy = _policy((M.SIMULATION_RETURN, D.DESCENDING))
    first = HistoricalExperimentComparator().compare(source_result, policy)
    second = HistoricalExperimentComparator().compare(source_result, policy)
    assert first == second
    assert first.result_id == second.result_id
    assert first.policy_fingerprint == second.policy_fingerprint


@pytest.mark.parametrize(
    "changed",
    (
        _policy((M.FINAL_EQUITY, D.DESCENDING)),
        _policy((M.SIMULATION_RETURN, D.ASCENDING)),
        _policy(
            (M.TOTAL_ORDERS, D.ASCENDING),
            (M.SIMULATION_RETURN, D.DESCENDING),
        ),
        _policy((M.SIMULATION_RETURN, D.DESCENDING), tie_breaker=T.VARIANT_ID),
        _policy(
            (M.SIMULATION_RETURN, D.DESCENDING),
            metadata=(MetadataEntry("changed", "yes"),),
        ),
        _policy(
            (M.SIMULATION_RETURN, D.DESCENDING),
            policy_id=UUID("00000000-0000-0000-0000-000000000502"),
        ),
    ),
)
def test_policy_changes_change_comparison_identity(
    source_result: HistoricalExperimentResult,
    changed: HistoricalExperimentRankingPolicy,
) -> None:
    baseline = HistoricalExperimentComparator().compare(
        source_result, _policy((M.SIMULATION_RETURN, D.DESCENDING))
    )
    result = HistoricalExperimentComparator().compare(source_result, changed)
    assert (
        result.policy_fingerprint != baseline.policy_fingerprint
        or result.result_id != baseline.result_id
    )


def test_source_result_and_metric_changes_change_result_identity(
    source_result: HistoricalExperimentResult,
) -> None:
    policy = _policy((M.SIMULATION_RETURN, D.DESCENDING))
    baseline = HistoricalExperimentComparator().compare(source_result, policy)
    changed_metric = _with_metrics(
        source_result,
        {"simulation_return": Decimal("100")},
        {"simulation_return": Decimal("0")},
    )
    metric_result = HistoricalExperimentComparator().compare(changed_metric, policy)
    assert metric_result.result_id != baseline.result_id

    changed_source = copy(source_result)
    object.__setattr__(changed_source, "result_id", uuid4())
    source_result_changed = HistoricalExperimentComparator().compare(
        changed_source, policy
    )
    assert source_result_changed.result_id != baseline.result_id


def test_decimal_context_and_negative_zero_do_not_affect_identity(
    source_result: HistoricalExperimentResult,
) -> None:
    source = _with_metrics(
        source_result,
        {"simulation_return": Decimal("-0")},
        {"simulation_return": Decimal("0")},
    )
    policy = _policy((M.SIMULATION_RETURN, D.ASCENDING))
    with localcontext(Context(prec=3)):
        first = HistoricalExperimentComparator().compare(source, policy)
    with localcontext(Context(prec=50)):
        second = HistoricalExperimentComparator().compare(source, policy)
    assert first == second
    assert _identity_value(Decimal("-0")) == "DECIMAL|0"
    assert tuple(item.caller_ordinal for item in first.ranked_runs) == (0, 1)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("simulation_return", Decimal("NaN")),
        ("simulation_return", Decimal("Infinity")),
        ("total_orders", True),
        ("total_orders", -1),
    ),
)
def test_corrupted_metric_scalars_are_rejected(
    source_result: HistoricalExperimentResult, field: str, value: Decimal | int
) -> None:
    source = copy(source_result)
    run = copy(source.runs[0])
    metrics = copy(run.metrics)
    object.__setattr__(metrics, field, value)
    object.__setattr__(run, "metrics", metrics)
    object.__setattr__(source, "runs", (run, source.runs[1]))
    metric = next(key for key, name in EXPECTED_FIELDS.items() if name == field)
    with pytest.raises(HistoricalExperimentMetricError):
        HistoricalExperimentComparator().compare(source, _policy((metric, D.ASCENDING)))


def test_result_model_rejects_corrupted_relationships(
    source_result: HistoricalExperimentResult,
) -> None:
    policy = _policy((M.INITIAL_EQUITY, D.ASCENDING))
    valid = HistoricalExperimentComparator().compare(source_result, policy)
    first, second = valid.ranked_runs
    foreign_run = copy(first.run)
    corruptions = (
        (first,),
        (first, first),
        (
            HistoricalExperimentRankedRun(
                1,
                foreign_run.ordinal,
                foreign_run,
                first.comparison_values,
            ),
            second,
        ),
        (
            HistoricalExperimentRankedRun(
                2, first.caller_ordinal, first.run, first.comparison_values
            ),
            second,
        ),
        (
            second,
            first,
        ),
        (
            HistoricalExperimentRankedRun(
                1,
                first.caller_ordinal,
                first.run,
                (Decimal("999"),),
            ),
            second,
        ),
    )
    for ranked in corruptions:
        with pytest.raises(InconsistentHistoricalExperimentComparisonResultError):
            HistoricalExperimentComparisonResult(
                valid.result_id,
                source_result,
                policy,
                valid.policy_fingerprint,
                ranked,
            )
    with pytest.raises(InconsistentHistoricalExperimentComparisonResultError):
        HistoricalExperimentComparisonResult(
            valid.result_id,
            source_result,
            policy,
            uuid4(),
            valid.ranked_runs,
        )
    with pytest.raises(InconsistentHistoricalExperimentComparisonResultError):
        HistoricalExperimentComparisonResult(
            uuid4(),
            source_result,
            policy,
            valid.policy_fingerprint,
            valid.ranked_runs,
        )


def test_ranked_run_rejects_wrong_ordinal_and_scalar_shape(
    source_result: HistoricalExperimentResult,
) -> None:
    run = source_result.runs[0]
    with pytest.raises(InconsistentHistoricalExperimentComparisonResultError):
        HistoricalExperimentRankedRun(1, 1, run, (Decimal("0"),))
    with pytest.raises(InconsistentHistoricalExperimentComparisonResultError):
        HistoricalExperimentRankedRun(1, 0, run, (True,))


def test_comparator_does_not_invoke_experiment_runner(
    source_result: HistoricalExperimentResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("experiment execution must not run")

    monkeypatch.setattr(HistoricalExperimentRunner, "run", forbidden)
    result = HistoricalExperimentComparator().compare(
        source_result, _policy((M.FINAL_EQUITY, D.DESCENDING))
    )
    assert len(result.ranked_runs) == len(source_result.runs)
