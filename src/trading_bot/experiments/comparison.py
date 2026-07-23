"""Explicit deterministic ranking of completed historical experiment runs."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import cmp_to_key
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments.exceptions import (
    HistoricalExperimentComparisonReconciliationError,
    HistoricalExperimentMetricError,
    HistoricalExperimentRankingError,
    InconsistentHistoricalExperimentComparisonResultError,
    InvalidHistoricalExperimentRankingPolicyError,
)
from trading_bot.experiments.historical import (
    HistoricalExperimentMetrics,
    HistoricalExperimentResult,
    HistoricalExperimentRun,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-comparison-v1"
_NAMESPACE = UUID("3c4304f4-85df-54c4-b107-bf4e78cfc60c")
_RESERVED_PREFIX = "historical_experiment_comparison_"


class HistoricalExperimentRankingMetric(StrEnum):
    INITIAL_EQUITY = "INITIAL_EQUITY"
    FINAL_EQUITY = "FINAL_EQUITY"
    ABSOLUTE_SIMULATION_PROFIT_LOSS = "ABSOLUTE_SIMULATION_PROFIT_LOSS"
    SIMULATION_RETURN = "SIMULATION_RETURN"
    MAXIMUM_DRAWDOWN_AMOUNT = "MAXIMUM_DRAWDOWN_AMOUNT"
    MAXIMUM_DRAWDOWN_PERCENTAGE = "MAXIMUM_DRAWDOWN_PERCENTAGE"
    SIMULATION_REALIZED_PROFIT_LOSS = "SIMULATION_REALIZED_PROFIT_LOSS"
    TOTAL_COMMISSIONS = "TOTAL_COMMISSIONS"
    ADVERSE_SLIPPAGE_COST = "ADVERSE_SLIPPAGE_COST"
    TOTAL_EXECUTION_COST = "TOTAL_EXECUTION_COST"
    AGGREGATE_ONE_WAY_TURNOVER = "AGGREGATE_ONE_WAY_TURNOVER"
    AGGREGATE_TWO_WAY_TURNOVER = "AGGREGATE_TWO_WAY_TURNOVER"
    MAXIMUM_ALLOCATION_DRIFT = "MAXIMUM_ALLOCATION_DRIFT"
    TOTAL_ORDERS = "TOTAL_ORDERS"
    TOTAL_FILLS = "TOTAL_FILLS"
    APPROVED_DECISIONS = "APPROVED_DECISIONS"
    RESIZED_DECISIONS = "RESIZED_DECISIONS"
    REJECTED_DECISIONS = "REJECTED_DECISIONS"
    REJECTED_NOTIONAL = "REJECTED_NOTIONAL"
    REDUCED_NOTIONAL = "REDUCED_NOTIONAL"
    MEAN_EXPECTED_PORTFOLIO_RETURN = "MEAN_EXPECTED_PORTFOLIO_RETURN"
    WORST_CVAR = "WORST_CVAR"
    MINIMUM_TARGET_CASH_WEIGHT = "MINIMUM_TARGET_CASH_WEIGHT"
    MAXIMUM_TARGET_CASH_WEIGHT = "MAXIMUM_TARGET_CASH_WEIGHT"
    APPLIED_CYCLE_COUNT = "APPLIED_CYCLE_COUNT"
    NO_ACTION_CYCLE_COUNT = "NO_ACTION_CYCLE_COUNT"


class HistoricalExperimentRankingDirection(StrEnum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class HistoricalExperimentTieBreaker(StrEnum):
    CALLER_ORDER = "CALLER_ORDER"
    VARIANT_ID = "VARIANT_ID"


_METRIC_FIELDS = MappingProxyType(
    {
        HistoricalExperimentRankingMetric.INITIAL_EQUITY: "initial_equity",
        HistoricalExperimentRankingMetric.FINAL_EQUITY: "final_equity",
        HistoricalExperimentRankingMetric.ABSOLUTE_SIMULATION_PROFIT_LOSS: (
            "absolute_simulation_profit_loss"
        ),
        HistoricalExperimentRankingMetric.SIMULATION_RETURN: "simulation_return",
        HistoricalExperimentRankingMetric.MAXIMUM_DRAWDOWN_AMOUNT: (
            "maximum_drawdown_amount"
        ),
        HistoricalExperimentRankingMetric.MAXIMUM_DRAWDOWN_PERCENTAGE: (
            "maximum_drawdown_percentage"
        ),
        HistoricalExperimentRankingMetric.SIMULATION_REALIZED_PROFIT_LOSS: (
            "simulation_realized_profit_loss"
        ),
        HistoricalExperimentRankingMetric.TOTAL_COMMISSIONS: "total_commissions",
        HistoricalExperimentRankingMetric.ADVERSE_SLIPPAGE_COST: (
            "adverse_slippage_cost"
        ),
        HistoricalExperimentRankingMetric.TOTAL_EXECUTION_COST: (
            "total_execution_cost"
        ),
        HistoricalExperimentRankingMetric.AGGREGATE_ONE_WAY_TURNOVER: (
            "aggregate_one_way_turnover"
        ),
        HistoricalExperimentRankingMetric.AGGREGATE_TWO_WAY_TURNOVER: (
            "aggregate_two_way_turnover"
        ),
        HistoricalExperimentRankingMetric.MAXIMUM_ALLOCATION_DRIFT: (
            "maximum_allocation_drift"
        ),
        HistoricalExperimentRankingMetric.TOTAL_ORDERS: "total_orders",
        HistoricalExperimentRankingMetric.TOTAL_FILLS: "total_fills",
        HistoricalExperimentRankingMetric.APPROVED_DECISIONS: "approved_decisions",
        HistoricalExperimentRankingMetric.RESIZED_DECISIONS: "resized_decisions",
        HistoricalExperimentRankingMetric.REJECTED_DECISIONS: "rejected_decisions",
        HistoricalExperimentRankingMetric.REJECTED_NOTIONAL: "rejected_notional",
        HistoricalExperimentRankingMetric.REDUCED_NOTIONAL: "reduced_notional",
        HistoricalExperimentRankingMetric.MEAN_EXPECTED_PORTFOLIO_RETURN: (
            "mean_expected_portfolio_return"
        ),
        HistoricalExperimentRankingMetric.WORST_CVAR: "worst_cvar",
        HistoricalExperimentRankingMetric.MINIMUM_TARGET_CASH_WEIGHT: (
            "minimum_target_cash_weight"
        ),
        HistoricalExperimentRankingMetric.MAXIMUM_TARGET_CASH_WEIGHT: (
            "maximum_target_cash_weight"
        ),
        HistoricalExperimentRankingMetric.APPLIED_CYCLE_COUNT: "applied_cycle_count",
        HistoricalExperimentRankingMetric.NO_ACTION_CYCLE_COUNT: (
            "no_action_cycle_count"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentRankingCriterion:
    metric: HistoricalExperimentRankingMetric
    direction: HistoricalExperimentRankingDirection

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentRankingPolicyError
        if type(self.metric) is not HistoricalExperimentRankingMetric:
            raise error("criterion metric has an invalid type")
        if type(self.direction) is not HistoricalExperimentRankingDirection:
            raise error("criterion direction has an invalid type")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentRankingPolicy:
    policy_id: UUID
    criteria: tuple[HistoricalExperimentRankingCriterion, ...]
    tie_breaker: HistoricalExperimentTieBreaker
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentRankingPolicyError
        if not isinstance(self.policy_id, UUID):
            raise error("policy_id must be a UUID")
        try:
            criteria = tuple(self.criteria)
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("criteria and metadata must be iterable") from caught
        if not criteria:
            raise error("criteria must not be empty")
        if not all(
            type(item) is HistoricalExperimentRankingCriterion for item in criteria
        ):
            raise error("criteria contain an invalid value")
        for item in criteria:
            item.__post_init__()
        if len({item.metric for item in criteria}) != len(criteria):
            raise error("criterion metrics must be unique")
        if type(self.tie_breaker) is not HistoricalExperimentTieBreaker:
            raise error("tie_breaker has an invalid type")
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
        object.__setattr__(self, "criteria", criteria)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentRankedRun:
    rank: int
    caller_ordinal: int
    run: HistoricalExperimentRun
    comparison_values: tuple[Decimal | int, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentComparisonResultError
        if (
            not isinstance(self.rank, int)
            or isinstance(self.rank, bool)
            or self.rank <= 0
        ):
            raise error("rank must be a positive integer")
        if (
            not isinstance(self.caller_ordinal, int)
            or isinstance(self.caller_ordinal, bool)
            or self.caller_ordinal < 0
        ):
            raise error("caller_ordinal must be a nonnegative integer")
        if type(self.run) is not HistoricalExperimentRun:
            raise error("run must be exactly HistoricalExperimentRun")
        if self.caller_ordinal != self.run.ordinal:
            raise error("caller_ordinal must match the source run")
        try:
            values = tuple(self.comparison_values)
        except TypeError as caught:
            raise error("comparison_values must be iterable") from caught
        if not values:
            raise error("comparison_values must not be empty")
        for value in values:
            _validate_scalar(value, error)
        object.__setattr__(self, "comparison_values", values)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentComparisonResult:
    result_id: UUID
    experiment_result: HistoricalExperimentResult
    policy: HistoricalExperimentRankingPolicy
    policy_fingerprint: UUID
    ranked_runs: tuple[HistoricalExperimentRankedRun, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentComparisonResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        _validate_source(self.experiment_result, error)
        if type(self.policy) is not HistoricalExperimentRankingPolicy:
            raise error("policy must be exactly HistoricalExperimentRankingPolicy")
        self.policy.__post_init__()
        if not isinstance(self.policy_fingerprint, UUID):
            raise error("policy_fingerprint must be a UUID")
        try:
            ranked = tuple(self.ranked_runs)
        except TypeError as caught:
            raise error("ranked_runs must be iterable") from caught
        if not all(type(item) is HistoricalExperimentRankedRun for item in ranked):
            raise error("ranked_runs contain an invalid value")
        expected_policy_id = _policy_fingerprint(self.policy)
        if self.policy_fingerprint != expected_policy_id:
            raise error("policy_fingerprint is inconsistent")
        _reconcile_ranked(
            self.experiment_result,
            self.policy,
            ranked,
            error,
        )
        expected_result_id = _result_id(
            self.experiment_result,
            self.policy,
            expected_policy_id,
            ranked,
        )
        if self.result_id != expected_result_id:
            raise error("result_id is inconsistent")
        object.__setattr__(self, "ranked_runs", ranked)


class HistoricalExperimentComparator:
    """Rank completed experiment runs using one explicit caller policy."""

    def compare(
        self,
        experiment_result: HistoricalExperimentResult,
        policy: HistoricalExperimentRankingPolicy,
    ) -> HistoricalExperimentComparisonResult:
        _validate_source(experiment_result, HistoricalExperimentRankingError)
        if type(policy) is not HistoricalExperimentRankingPolicy:
            raise InvalidHistoricalExperimentRankingPolicyError(
                "policy must be exactly HistoricalExperimentRankingPolicy"
            )
        policy.__post_init__()
        source_before = _source_invariant(experiment_result)
        policy_before = _policy_invariant(policy)
        local = tuple(
            (run, _comparison_values(run, policy.criteria))
            for run in experiment_result.runs
        )
        ordered = tuple(
            sorted(
                local,
                key=cmp_to_key(lambda left, right: _compare(left, right, policy)),
            )
        )
        ranked = tuple(
            HistoricalExperimentRankedRun(rank, run.ordinal, run, values)
            for rank, (run, values) in enumerate(ordered, start=1)
        )
        if source_before != _source_invariant(experiment_result):
            raise HistoricalExperimentComparisonReconciliationError(
                "source experiment changed during comparison"
            )
        if policy_before != _policy_invariant(policy):
            raise HistoricalExperimentComparisonReconciliationError(
                "ranking policy changed during comparison"
            )
        _reconcile_ranked(
            experiment_result,
            policy,
            ranked,
            HistoricalExperimentComparisonReconciliationError,
        )
        policy_id = _policy_fingerprint(policy)
        result_id = _result_id(experiment_result, policy, policy_id, ranked)
        return HistoricalExperimentComparisonResult(
            result_id,
            experiment_result,
            policy,
            policy_id,
            ranked,
        )


def _validate_source(experiment_result, error_type):  # type: ignore[no-untyped-def]
    if type(experiment_result) is not HistoricalExperimentResult:
        raise error_type("experiment_result must be exactly HistoricalExperimentResult")
    runs = experiment_result.runs
    if not runs:
        raise error_type("experiment_result runs must not be empty")
    if tuple(item.ordinal for item in runs) != tuple(range(len(runs))):
        raise error_type("source run ordinals must be sequential")
    if len({item.run_id for item in runs}) != len(runs):
        raise error_type("source run IDs must be unique")
    if len({item.variant.variant_id for item in runs}) != len(runs):
        raise error_type("source variant IDs must be unique")
    if len(experiment_result.request.variants) != len(runs):
        raise error_type("source variants and runs must have equal counts")
    for ordinal, (run, variant) in enumerate(
        zip(runs, experiment_result.request.variants, strict=True)
    ):
        if type(run) is not HistoricalExperimentRun or run.ordinal != ordinal:
            raise error_type("source run type or ordinal is invalid")
        if run.variant is not variant:
            raise error_type("source run does not retain its request variant")
        if type(run.metrics) is not HistoricalExperimentMetrics:
            raise error_type("source run metrics have an invalid type")


def _comparison_values(
    run: HistoricalExperimentRun,
    criteria: tuple[HistoricalExperimentRankingCriterion, ...],
    error_type=HistoricalExperimentMetricError,  # type: ignore[no-untyped-def]
) -> tuple[Decimal | int, ...]:
    values = []
    for criterion in criteria:
        field = _METRIC_FIELDS.get(criterion.metric)
        if field is None:
            raise error_type(
                f"ranking metric {criterion.metric!r} has no field mapping"
            )
        value = getattr(run.metrics, field)
        _validate_scalar(value, error_type)
        values.append(value)
    return tuple(values)


def _validate_scalar(value, error_type):  # type: ignore[no-untyped-def]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise error_type("Decimal comparison values must be finite")
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise error_type("integer comparison values must be nonnegative")
        return
    raise error_type("comparison values must be exact Decimal or integer values")


def _compare(left, right, policy):  # type: ignore[no-untyped-def]
    left_run, left_values = left
    right_run, right_values = right
    for index, criterion in enumerate(policy.criteria):
        comparison = _compare_value(left_values[index], right_values[index])
        if comparison:
            return (
                comparison
                if criterion.direction is HistoricalExperimentRankingDirection.ASCENDING
                else -comparison
            )
    left_tie = _tie_value(left_run, policy.tie_breaker)
    right_tie = _tie_value(right_run, policy.tie_breaker)
    comparison = _compare_value(left_tie, right_tie)
    if comparison == 0 and left_run is not right_run:
        raise HistoricalExperimentRankingError(
            "explicit tie-breaker did not establish a total order"
        )
    return comparison


def _compare_value(left, right) -> int:  # type: ignore[no-untyped-def]
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def _tie_value(
    run: HistoricalExperimentRun, tie_breaker: HistoricalExperimentTieBreaker
) -> int:
    if tie_breaker is HistoricalExperimentTieBreaker.CALLER_ORDER:
        return run.ordinal
    if tie_breaker is HistoricalExperimentTieBreaker.VARIANT_ID:
        return run.variant.variant_id.int
    raise HistoricalExperimentRankingError("unsupported tie-breaker")


def _reconcile_ranked(
    experiment_result: HistoricalExperimentResult,
    policy: HistoricalExperimentRankingPolicy,
    ranked: tuple[HistoricalExperimentRankedRun, ...],
    error_type,
) -> None:  # type: ignore[no-untyped-def]
    source = experiment_result.runs
    if len(ranked) != len(source):
        raise error_type("ranked run count must equal source run count")
    if tuple(item.rank for item in ranked) != tuple(range(1, len(ranked) + 1)):
        raise error_type("ranks must be sequential from one")
    if len({id(item.run) for item in ranked}) != len(ranked):
        raise error_type("ranked runs must not contain duplicate source objects")
    if {id(item.run) for item in ranked} != {id(item) for item in source}:
        raise error_type("ranked runs must exactly cover source run objects")
    for item in ranked:
        if item.caller_ordinal != item.run.ordinal:
            raise error_type("ranked caller ordinal is inconsistent")
        expected = _comparison_values(item.run, policy.criteria, error_type)
        if item.comparison_values != expected:
            raise error_type("ranked comparison values are inconsistent")
    for left, right in zip(ranked, ranked[1:], strict=False):
        if (
            _compare(
                (left.run, left.comparison_values),
                (right.run, right.comparison_values),
                policy,
            )
            >= 0
        ):
            raise error_type("ranked runs are not in canonical order")


def _policy_fingerprint(policy: HistoricalExperimentRankingPolicy) -> UUID:
    return _id(
        "policy",
        str(policy.policy_id),
        *(
            material
            for item in policy.criteria
            for material in (item.metric.value, item.direction.value)
        ),
        policy.tie_breaker.value,
        *(f"{item.key}={item.value}" for item in policy.metadata),
    )


def _result_id(
    experiment_result: HistoricalExperimentResult,
    policy: HistoricalExperimentRankingPolicy,
    policy_fingerprint: UUID,
    ranked: tuple[HistoricalExperimentRankedRun, ...],
) -> UUID:
    material = [
        str(experiment_result.result_id),
        str(policy.policy_id),
        str(policy_fingerprint),
    ]
    for item in ranked:
        material.extend(
            (
                str(item.rank),
                str(item.caller_ordinal),
                str(item.run.run_id),
                str(item.run.variant.variant_id),
            )
        )
        for criterion, value in zip(
            policy.criteria, item.comparison_values, strict=True
        ):
            material.extend(
                (
                    criterion.metric.value,
                    _identity_value(value),
                )
            )
        material.append(
            f"{policy.tie_breaker.value}|{_tie_value(item.run, policy.tie_breaker)}"
        )
    return _id("result", *material)


def _identity_value(value: Decimal | int) -> str:
    if isinstance(value, Decimal):
        return f"DECIMAL|{canonical_decimal(value)}"
    return f"INTEGER|{value}"


def _source_invariant(
    experiment_result: HistoricalExperimentResult,
) -> tuple[object, ...]:
    return (
        experiment_result.result_id,
        experiment_result.runs,
        tuple(
            (
                run.run_id,
                run.ordinal,
                run.variant.variant_id,
                tuple(getattr(run.metrics, field) for field in _METRIC_FIELDS.values()),
            )
            for run in experiment_result.runs
        ),
    )


def _policy_invariant(
    policy: HistoricalExperimentRankingPolicy,
) -> tuple[object, ...]:
    return (
        policy.policy_id,
        policy.criteria,
        policy.tie_breaker,
        policy.metadata,
    )


def _id(stage: str, *material: str) -> UUID:
    return uuid5(_NAMESPACE, "|".join((_VERSION, stage, *material)))
