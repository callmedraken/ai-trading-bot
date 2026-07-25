"""Pure deterministic stability analysis over retained walk-forward folds."""

from dataclasses import dataclass, fields
from datetime import timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from fractions import Fraction
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.experiments.exceptions import (
    HistoricalExperimentWalkForwardStabilityAggregateSourceError,
    HistoricalExperimentWalkForwardStabilityArithmeticError,
    HistoricalExperimentWalkForwardStabilityComparabilityError,
    HistoricalExperimentWalkForwardStabilityMetricError,
    HistoricalExperimentWalkForwardStabilityOperationError,
    HistoricalExperimentWalkForwardStabilityReconciliationError,
    HistoricalExperimentWalkForwardStabilitySourceError,
    InconsistentHistoricalExperimentWalkForwardAggregateResultError,
    InconsistentHistoricalExperimentWalkForwardResultError,
    InconsistentHistoricalExperimentWalkForwardStabilityResultError,
    InvalidHistoricalExperimentWalkForwardStabilityPolicyError,
)
from trading_bot.experiments.historical import HistoricalExperimentMetrics
from trading_bot.experiments.report import (
    HistoricalExperimentReportVariant,
    HistoricalExperimentReportVariantSource,
)
from trading_bot.experiments.walk_forward import HistoricalExperimentWalkForwardResult
from trading_bot.experiments.walk_forward_analytics import (
    HistoricalExperimentWalkForwardAggregateResult,
    HistoricalExperimentWalkForwardExactRational,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-walk-forward-stability-v1"
_NAMESPACE = UUID("43fc6c3a-5e98-52af-bcb5-72927bef87e0")
_RESERVED_PREFIX = "historical_experiment_walk_forward_stability_"


class HistoricalExperimentWalkForwardStabilityMetric(StrEnum):
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


class HistoricalExperimentWalkForwardStabilityOperation(StrEnum):
    ADJACENT_ABSOLUTE_CHANGE = "ADJACENT_ABSOLUTE_CHANGE"
    RANGE = "RANGE"
    MEDIAN_ABSOLUTE_DEVIATION = "MEDIAN_ABSOLUTE_DEVIATION"
    SIGN_CHANGE_COUNT = "SIGN_CHANGE_COUNT"


class HistoricalExperimentWalkForwardComparabilityRule(StrEnum):
    NONE = "NONE"
    EQUAL_TEST_DURATION = "EQUAL_TEST_DURATION"
    EQUAL_TEST_SCHEDULE_COUNT = "EQUAL_TEST_SCHEDULE_COUNT"
    EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT = "EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT"


_ORDER = tuple(HistoricalExperimentWalkForwardStabilityOperation)
_CHANGE = HistoricalExperimentWalkForwardStabilityOperation.ADJACENT_ABSOLUTE_CHANGE
_RANGE = HistoricalExperimentWalkForwardStabilityOperation.RANGE
_MAD = HistoricalExperimentWalkForwardStabilityOperation.MEDIAN_ABSOLUTE_DEVIATION
_SIGN = HistoricalExperimentWalkForwardStabilityOperation.SIGN_CHANGE_COUNT
_MAGNITUDE = frozenset({_CHANGE, _RANGE, _MAD})
_DIMENSIONLESS = frozenset(
    {
        HistoricalExperimentWalkForwardStabilityMetric.SIMULATION_RETURN,
        HistoricalExperimentWalkForwardStabilityMetric.MAXIMUM_DRAWDOWN_PERCENTAGE,
        HistoricalExperimentWalkForwardStabilityMetric.AGGREGATE_ONE_WAY_TURNOVER,
        HistoricalExperimentWalkForwardStabilityMetric.AGGREGATE_TWO_WAY_TURNOVER,
        HistoricalExperimentWalkForwardStabilityMetric.MAXIMUM_ALLOCATION_DRIFT,
        HistoricalExperimentWalkForwardStabilityMetric.MEAN_EXPECTED_PORTFOLIO_RETURN,
        HistoricalExperimentWalkForwardStabilityMetric.WORST_CVAR,
        HistoricalExperimentWalkForwardStabilityMetric.MINIMUM_TARGET_CASH_WEIGHT,
        HistoricalExperimentWalkForwardStabilityMetric.MAXIMUM_TARGET_CASH_WEIGHT,
    }
)
_POINT_IN_TIME = frozenset(
    {
        HistoricalExperimentWalkForwardStabilityMetric.MAXIMUM_ALLOCATION_DRIFT,
        HistoricalExperimentWalkForwardStabilityMetric.MINIMUM_TARGET_CASH_WEIGHT,
        HistoricalExperimentWalkForwardStabilityMetric.MAXIMUM_TARGET_CASH_WEIGHT,
    }
)
_COUNTS = frozenset(
    {
        HistoricalExperimentWalkForwardStabilityMetric.TOTAL_ORDERS,
        HistoricalExperimentWalkForwardStabilityMetric.TOTAL_FILLS,
        HistoricalExperimentWalkForwardStabilityMetric.APPROVED_DECISIONS,
        HistoricalExperimentWalkForwardStabilityMetric.RESIZED_DECISIONS,
        HistoricalExperimentWalkForwardStabilityMetric.REJECTED_DECISIONS,
        HistoricalExperimentWalkForwardStabilityMetric.APPLIED_CYCLE_COUNT,
        HistoricalExperimentWalkForwardStabilityMetric.NO_ACTION_CYCLE_COUNT,
    }
)
_SIGNED = frozenset(
    {
        HistoricalExperimentWalkForwardStabilityMetric.SIMULATION_RETURN,
        HistoricalExperimentWalkForwardStabilityMetric.MEAN_EXPECTED_PORTFOLIO_RETURN,
        HistoricalExperimentWalkForwardStabilityMetric.WORST_CVAR,
        HistoricalExperimentWalkForwardStabilityMetric.ABSOLUTE_SIMULATION_PROFIT_LOSS,
        HistoricalExperimentWalkForwardStabilityMetric.SIMULATION_REALIZED_PROFIT_LOSS,
    }
)
_ELIGIBILITY = {
    metric: frozenset() for metric in HistoricalExperimentWalkForwardStabilityMetric
}
for _metric in _DIMENSIONLESS | _COUNTS:
    _ELIGIBILITY[_metric] = _MAGNITUDE
for _metric in _SIGNED:
    _ELIGIBILITY[_metric] = _ELIGIBILITY[_metric] | {_SIGN}
STABILITY_METRIC_OPERATION_ELIGIBILITY = MappingProxyType(_ELIGIBILITY)
del _ELIGIBILITY, _metric
_METRIC_FIELDS = MappingProxyType(
    {
        metric: metric.value.lower()
        for metric in HistoricalExperimentWalkForwardStabilityMetric
    }
)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardStabilityMetricPolicy:
    metric: HistoricalExperimentWalkForwardStabilityMetric
    operations: tuple[HistoricalExperimentWalkForwardStabilityOperation, ...]
    comparability_rule: HistoricalExperimentWalkForwardComparabilityRule

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardStabilityPolicyError
        if type(self.metric) is not HistoricalExperimentWalkForwardStabilityMetric:
            raise error("metric has an invalid type")
        operations = _tuple(self.operations, "operations", error)
        if not all(
            type(item) is HistoricalExperimentWalkForwardStabilityOperation
            for item in operations
        ):
            raise error("operations must contain exact stability operations")
        if len(set(operations)) != len(operations):
            raise error("operations must not contain duplicates")
        unsupported = (
            set(operations) - STABILITY_METRIC_OPERATION_ELIGIBILITY[self.metric]
        )
        if unsupported:
            names = ", ".join(sorted(item.value for item in unsupported))
            raise HistoricalExperimentWalkForwardStabilityOperationError(
                f"{self.metric.value} does not allow: {names}"
            )
        if (
            type(self.comparability_rule)
            is not HistoricalExperimentWalkForwardComparabilityRule
        ):
            raise error("comparability_rule has an invalid type")
        _validate_policy_comparability(self.metric, operations, self.comparability_rule)
        object.__setattr__(
            self, "operations", tuple(item for item in _ORDER if item in operations)
        )


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardStabilityPolicy:
    policy_id: UUID
    metrics: tuple[HistoricalExperimentWalkForwardStabilityMetricPolicy, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardStabilityPolicyError
        if type(self.policy_id) is not UUID:
            raise error("policy_id must be an exact UUID")
        metrics = _models(
            self.metrics,
            HistoricalExperimentWalkForwardStabilityMetricPolicy,
            "metrics",
            error,
        )
        for item in metrics:
            item.__post_init__()
        if len({item.metric for item in metrics}) != len(metrics):
            raise error("policy metrics must be unique")
        metadata = _metadata(self.metadata, error)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionObservation:
    fold_ordinal: int
    fold_id: UUID
    test_duration: timedelta
    test_schedule_count: int
    selected_variant_id: UUID
    selected_rank: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        _ordinal(self.fold_ordinal, "fold_ordinal", error)
        if type(self.fold_id) is not UUID or type(self.selected_variant_id) is not UUID:
            raise error("selection observation identities must be exact UUIDs")
        if (
            type(self.test_duration) is not timedelta
            or self.test_duration <= timedelta()
        ):
            raise error("test_duration must be a positive exact timedelta")
        _ordinal(self.test_schedule_count, "test_schedule_count", error)
        if self.test_schedule_count <= 0:
            raise error("test_schedule_count must be positive")
        if self.selected_rank != 1:
            raise error("selected_rank must be exactly one")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionRun:
    start_fold_ordinal: int
    end_fold_ordinal: int
    variant_id: UUID
    consecutive_fold_count: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        _ordinal(self.start_fold_ordinal, "start_fold_ordinal", error)
        _ordinal(self.end_fold_ordinal, "end_fold_ordinal", error)
        if type(self.variant_id) is not UUID:
            raise error("run variant_id must be an exact UUID")
        if (
            type(self.consecutive_fold_count) is not int
            or self.consecutive_fold_count <= 0
            or self.end_fold_ordinal - self.start_fold_ordinal + 1
            != self.consecutive_fold_count
        ):
            raise error("run bounds and count are inconsistent")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionTransition:
    previous_fold_ordinal: int
    current_fold_ordinal: int
    previous_fold_id: UUID
    current_fold_id: UUID
    from_variant_id: UUID
    to_variant_id: UUID
    changed: bool

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        _ordinal(self.previous_fold_ordinal, "previous_fold_ordinal", error)
        if self.current_fold_ordinal != self.previous_fold_ordinal + 1:
            raise error("transition fold ordinals must be adjacent")
        for name in (
            "previous_fold_id",
            "current_fold_id",
            "from_variant_id",
            "to_variant_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        if type(self.changed) is not bool or self.changed != (
            self.from_variant_id != self.to_variant_id
        ):
            raise error("transition changed evidence is inconsistent")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionTransitionFrequency:
    from_variant_id: UUID
    to_variant_id: UUID
    occurrence_count: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        if (
            type(self.from_variant_id) is not UUID
            or type(self.to_variant_id) is not UUID
        ):
            raise error("transition frequency identities must be exact UUIDs")
        if type(self.occurrence_count) is not int or self.occurrence_count <= 0:
            raise error("occurrence_count must be a positive exact integer")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionFrequency:
    variant_id: UUID
    selected_fold_count: int
    first_selected_fold_ordinal: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        if type(self.variant_id) is not UUID:
            raise error("frequency variant_id must be an exact UUID")
        if type(self.selected_fold_count) is not int or self.selected_fold_count <= 0:
            raise error("selected_fold_count must be a positive exact integer")
        _ordinal(
            self.first_selected_fold_ordinal,
            "first_selected_fold_ordinal",
            error,
        )


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSelectionStability:
    observations: tuple[HistoricalExperimentWalkForwardSelectionObservation, ...]
    unique_selected_variant_count: int
    persistence_adjacency_count: int
    changed_adjacency_count: int
    persistence_ratio: HistoricalExperimentWalkForwardExactRational | None
    runs: tuple[HistoricalExperimentWalkForwardSelectionRun, ...]
    longest_consecutive_selection_run: int
    transitions: tuple[HistoricalExperimentWalkForwardSelectionTransition, ...]
    transition_frequencies: tuple[
        HistoricalExperimentWalkForwardSelectionTransitionFrequency, ...
    ]
    variant_frequencies: tuple[HistoricalExperimentWalkForwardSelectionFrequency, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        observations = _models(
            self.observations,
            HistoricalExperimentWalkForwardSelectionObservation,
            "selection observations",
            error,
        )
        runs = _models(
            self.runs, HistoricalExperimentWalkForwardSelectionRun, "runs", error
        )
        transitions = _tuple(self.transitions, "transitions", error)
        if not all(
            type(item) is HistoricalExperimentWalkForwardSelectionTransition
            for item in transitions
        ):
            raise error("transitions contain an invalid model")
        transition_frequencies = _tuple(
            self.transition_frequencies, "transition_frequencies", error
        )
        if not all(
            type(item) is HistoricalExperimentWalkForwardSelectionTransitionFrequency
            for item in transition_frequencies
        ):
            raise error("transition_frequencies contain an invalid model")
        frequencies = _models(
            self.variant_frequencies,
            HistoricalExperimentWalkForwardSelectionFrequency,
            "variant_frequencies",
            error,
        )
        for item in (
            *observations,
            *runs,
            *transitions,
            *transition_frequencies,
            *frequencies,
        ):
            item.__post_init__()
        for name in (
            "unique_selected_variant_count",
            "persistence_adjacency_count",
            "changed_adjacency_count",
            "longest_consecutive_selection_run",
        ):
            _ordinal(getattr(self, name), name, error)
        if self.persistence_ratio is not None:
            if (
                type(self.persistence_ratio)
                is not HistoricalExperimentWalkForwardExactRational
            ):
                raise error("persistence_ratio has an invalid type")
            self.persistence_ratio.__post_init__()
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "runs", runs)
        object.__setattr__(self, "transitions", transitions)
        object.__setattr__(self, "transition_frequencies", transition_frequencies)
        object.__setattr__(self, "variant_frequencies", frequencies)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardStabilityMetricObservation:
    fold_ordinal: int
    fold_id: UUID
    test_report_id: UUID
    test_run_id: UUID
    selected_variant_id: UUID
    test_duration: timedelta
    test_schedule_count: int
    value: Decimal | int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        _ordinal(self.fold_ordinal, "fold_ordinal", error)
        for name in (
            "fold_id",
            "test_report_id",
            "test_run_id",
            "selected_variant_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        if (
            type(self.test_duration) is not timedelta
            or self.test_duration <= timedelta()
        ):
            raise error("test_duration must be a positive exact timedelta")
        if type(self.test_schedule_count) is not int or self.test_schedule_count <= 0:
            raise error("test_schedule_count must be a positive exact integer")
        _scalar(self.value, error)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardAdjacentMetricChange:
    previous_fold_ordinal: int
    current_fold_ordinal: int
    previous_fold_id: UUID
    current_fold_id: UUID
    previous_variant_id: UUID
    current_variant_id: UUID
    previous_value: Decimal | int
    current_value: Decimal | int
    absolute_change: Decimal | int
    comparability_rule: HistoricalExperimentWalkForwardComparabilityRule

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        _ordinal(self.previous_fold_ordinal, "previous_fold_ordinal", error)
        if self.current_fold_ordinal != self.previous_fold_ordinal + 1:
            raise error("metric change fold ordinals must be adjacent")
        for name in (
            "previous_fold_id",
            "current_fold_id",
            "previous_variant_id",
            "current_variant_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        for value in (
            self.previous_value,
            self.current_value,
            self.absolute_change,
        ):
            _scalar(value, error)
        if type(self.previous_value) is not type(self.current_value) or type(
            self.absolute_change
        ) is not type(self.previous_value):
            raise error("metric change scalar types must agree")
        if (
            type(self.comparability_rule)
            is not HistoricalExperimentWalkForwardComparabilityRule
        ):
            raise error("metric change comparability_rule has an invalid type")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardMetricStability:
    metric: HistoricalExperimentWalkForwardStabilityMetric
    observations: tuple[HistoricalExperimentWalkForwardStabilityMetricObservation, ...]
    adjacent_changes: tuple[
        HistoricalExperimentWalkForwardAdjacentMetricChange, ...
    ] = ()
    value_range: Decimal | int | None = None
    median: Decimal | None = None
    median_absolute_deviation: Decimal | None = None
    sign_change_count: int | None = None

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        if type(self.metric) is not HistoricalExperimentWalkForwardStabilityMetric:
            raise error("metric has an invalid type")
        observations = _models(
            self.observations,
            HistoricalExperimentWalkForwardStabilityMetricObservation,
            "metric observations",
            error,
        )
        changes = _tuple(self.adjacent_changes, "adjacent_changes", error)
        if not all(
            type(item) is HistoricalExperimentWalkForwardAdjacentMetricChange
            for item in changes
        ):
            raise error("adjacent_changes contain an invalid model")
        for item in (*observations, *changes):
            item.__post_init__()
        if self.value_range is not None:
            _scalar(self.value_range, error)
            if type(self.value_range) is not type(observations[0].value):
                raise error("value_range must retain the source scalar type")
        for name in ("median", "median_absolute_deviation"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not Decimal or not value.is_finite()
            ):
                raise error(f"{name} must be an exact finite Decimal or None")
        if self.sign_change_count is not None:
            _ordinal(self.sign_change_count, "sign_change_count", error)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "adjacent_changes", changes)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardStabilityResult:
    result_id: UUID
    source_walk_forward_result_id: UUID
    source_request_id: UUID
    source_historical_fingerprint: UUID
    source_aggregate_result_id: UUID | None
    policy: HistoricalExperimentWalkForwardStabilityPolicy
    fold_count: int
    selection_stability: HistoricalExperimentWalkForwardSelectionStability
    metric_stability: tuple[HistoricalExperimentWalkForwardMetricStability, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
        for name in (
            "result_id",
            "source_walk_forward_result_id",
            "source_request_id",
            "source_historical_fingerprint",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        if (
            self.source_aggregate_result_id is not None
            and type(self.source_aggregate_result_id) is not UUID
        ):
            raise error("source_aggregate_result_id must be an exact UUID or None")
        if type(self.policy) is not HistoricalExperimentWalkForwardStabilityPolicy:
            raise error("policy has an invalid type")
        self.policy.__post_init__()
        metrics = _models(
            self.metric_stability,
            HistoricalExperimentWalkForwardMetricStability,
            "metric_stability",
            error,
        )
        self.selection_stability.__post_init__()
        for item in metrics:
            item.__post_init__()
        _reconcile_result(
            self.fold_count, self.policy, self.selection_stability, metrics
        )
        expected = _result_id(
            self.source_walk_forward_result_id,
            self.source_request_id,
            self.source_historical_fingerprint,
            self.source_aggregate_result_id,
            self.policy,
            self.fold_count,
            self.selection_stability,
            metrics,
        )
        if self.result_id != expected:
            raise error("result_id is inconsistent")
        object.__setattr__(self, "metric_stability", metrics)


class HistoricalExperimentWalkForwardStabilityAnalyzer:
    """Describe retained fold selections and metric variation."""

    def analyze(
        self,
        source: HistoricalExperimentWalkForwardResult,
        policy: HistoricalExperimentWalkForwardStabilityPolicy,
        aggregate: HistoricalExperimentWalkForwardAggregateResult | None = None,
    ) -> HistoricalExperimentWalkForwardStabilityResult:
        folds = _validate_source(source)
        if type(policy) is not HistoricalExperimentWalkForwardStabilityPolicy:
            raise InvalidHistoricalExperimentWalkForwardStabilityPolicyError(
                "policy must be exactly HistoricalExperimentWalkForwardStabilityPolicy"
            )
        policy.__post_init__()
        aggregate_id = _validate_aggregate(source, folds, aggregate)
        before = _source_invariant(source, aggregate, policy)
        selection = _selection_stability(folds)
        metrics = tuple(_metric_stability(folds, item) for item in policy.metrics)
        _reconcile_aggregate_overlap(aggregate, metrics)
        identifier = _result_id(
            source.result_id,
            source.request_id,
            source.source_historical_fingerprint,
            aggregate_id,
            policy,
            len(folds),
            selection,
            metrics,
        )
        result = HistoricalExperimentWalkForwardStabilityResult(
            identifier,
            source.result_id,
            source.request_id,
            source.source_historical_fingerprint,
            aggregate_id,
            policy,
            len(folds),
            selection,
            metrics,
        )
        if before != _source_invariant(source, aggregate, policy):
            raise HistoricalExperimentWalkForwardStabilityReconciliationError(
                "stability inputs changed during analysis"
            )
        return result


def _validate_policy_comparability(metric, operations, rule):  # type: ignore[no-untyped-def]
    magnitude = bool(set(operations) & _MAGNITUDE)
    if not magnitude:
        if rule is not HistoricalExperimentWalkForwardComparabilityRule.NONE:
            raise InvalidHistoricalExperimentWalkForwardStabilityPolicyError(
                "observations and sign changes require NONE comparability"
            )
        return
    if metric in _COUNTS:
        rules = HistoricalExperimentWalkForwardComparabilityRule
        required = rules.EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT
        if rule is not required:
            raise InvalidHistoricalExperimentWalkForwardStabilityPolicyError(
                "count magnitude operations require equal duration and schedule count"
            )
    elif metric in _POINT_IN_TIME:
        return
    elif rule not in (
        HistoricalExperimentWalkForwardComparabilityRule.EQUAL_TEST_DURATION,
        HistoricalExperimentWalkForwardComparabilityRule.EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT,
    ):
        raise InvalidHistoricalExperimentWalkForwardStabilityPolicyError(
            "duration-sensitive magnitude operations require equal test duration"
        )


def _validate_source(source):  # type: ignore[no-untyped-def]
    error = HistoricalExperimentWalkForwardStabilitySourceError
    if type(source) is not HistoricalExperimentWalkForwardResult:
        raise error("source must be exactly HistoricalExperimentWalkForwardResult")
    try:
        source.__post_init__()
    except InconsistentHistoricalExperimentWalkForwardResultError as caught:
        raise error(f"source walk-forward result is inconsistent: {caught}") from caught
    for ordinal, fold in enumerate(source.folds):
        report = fold.test_report
        if (
            fold.ordinal != ordinal
            or report.variant_source
            is not HistoricalExperimentReportVariantSource.EXPLICIT
            or report.ranking is not None
            or len(report.variants) != 1
        ):
            raise error("test fold provenance is inconsistent")
        row = report.variants[0]
        if (
            type(row) is not HistoricalExperimentReportVariant
            or row.variant_id != fold.selection.selected_variant_id
            or row.experiment_run_id != fold.test_run_id
            or row.rolling_result_id != fold.test_rolling_result_id
            or fold.selection.selected_rank != 1
            or type(row.metrics) is not HistoricalExperimentMetrics
        ):
            raise error("test row provenance is inconsistent")
    return tuple(source.folds)


def _validate_aggregate(source, folds, aggregate):  # type: ignore[no-untyped-def]
    if aggregate is None:
        return None
    error = HistoricalExperimentWalkForwardStabilityAggregateSourceError
    if type(aggregate) is not HistoricalExperimentWalkForwardAggregateResult:
        raise error("aggregate must be an exact aggregate result or None")
    try:
        aggregate.__post_init__()
    except InconsistentHistoricalExperimentWalkForwardAggregateResultError as caught:
        raise error(f"aggregate result is inconsistent: {caught}") from caught
    if (
        aggregate.source_walk_forward_result_id != source.result_id
        or aggregate.source_request_id != source.request_id
        or aggregate.source_historical_fingerprint
        != source.source_historical_fingerprint
        or aggregate.fold_count != len(folds)
    ):
        raise error("aggregate source identities do not match walk-forward source")
    expected = tuple(
        (
            fold.ordinal,
            fold.fold.fold_id,
            fold.test_report.report_id,
            fold.test_run_id,
            fold.selection.selected_variant_id,
            fold.selection.selected_rank,
        )
        for fold in folds
    )
    actual = tuple(
        (
            fold.fold_ordinal,
            fold.fold_id,
            fold.test_report_id,
            fold.test_run_id,
            fold.selected_variant_id,
            fold.selected_rank,
        )
        for fold in aggregate.fold_summaries
    )
    if actual != expected:
        raise error("aggregate fold provenance does not match walk-forward source")
    return aggregate.result_id


def _selection_stability(folds):  # type: ignore[no-untyped-def]
    observations = tuple(
        HistoricalExperimentWalkForwardSelectionObservation(
            fold.ordinal,
            fold.fold.fold_id,
            fold.fold.test_end - fold.fold.test_start,
            len(fold.fold.test_rebalance_timestamps),
            fold.selection.selected_variant_id,
            fold.selection.selected_rank,
        )
        for fold in folds
    )
    transitions = tuple(
        HistoricalExperimentWalkForwardSelectionTransition(
            previous.fold_ordinal,
            current.fold_ordinal,
            previous.fold_id,
            current.fold_id,
            previous.selected_variant_id,
            current.selected_variant_id,
            previous.selected_variant_id != current.selected_variant_id,
        )
        for previous, current in zip(observations, observations[1:], strict=False)
    )
    runs = []
    start = 0
    for index in range(1, len(observations) + 1):
        if (
            index == len(observations)
            or observations[index].selected_variant_id
            != observations[start].selected_variant_id
        ):
            runs.append(
                HistoricalExperimentWalkForwardSelectionRun(
                    start,
                    index - 1,
                    observations[start].selected_variant_id,
                    index - start,
                )
            )
            start = index
    persistent = sum(not item.changed for item in transitions)
    ratio = (
        None
        if not transitions
        else HistoricalExperimentWalkForwardExactRational(
            *(lambda value: (value.numerator, value.denominator))(
                Fraction(persistent, len(transitions))
            )
        )
    )
    return HistoricalExperimentWalkForwardSelectionStability(
        observations,
        len({item.selected_variant_id for item in observations}),
        persistent,
        len(transitions) - persistent,
        ratio,
        tuple(runs),
        max(item.consecutive_fold_count for item in runs),
        transitions,
        _transition_frequencies(transitions),
        _selection_frequencies(observations),
    )


def _transition_frequencies(transitions):  # type: ignore[no-untyped-def]
    order = []
    counts = {}
    for item in transitions:
        pair = (item.from_variant_id, item.to_variant_id)
        if pair not in counts:
            order.append(pair)
            counts[pair] = 0
        counts[pair] += 1
    return tuple(
        HistoricalExperimentWalkForwardSelectionTransitionFrequency(
            pair[0], pair[1], counts[pair]
        )
        for pair in order
    )


def _selection_frequencies(observations):  # type: ignore[no-untyped-def]
    order = []
    counts = {}
    first = {}
    for item in observations:
        identifier = item.selected_variant_id
        if identifier not in counts:
            order.append(identifier)
            counts[identifier] = 0
            first[identifier] = item.fold_ordinal
        counts[identifier] += 1
    return tuple(
        HistoricalExperimentWalkForwardSelectionFrequency(
            identifier, counts[identifier], first[identifier]
        )
        for identifier in order
    )


def _metric_stability(folds, policy):  # type: ignore[no-untyped-def]
    observations = tuple(
        HistoricalExperimentWalkForwardStabilityMetricObservation(
            fold.ordinal,
            fold.fold.fold_id,
            fold.test_report.report_id,
            fold.test_run_id,
            fold.selection.selected_variant_id,
            fold.fold.test_end - fold.fold.test_start,
            len(fold.fold.test_rebalance_timestamps),
            _metric_value(fold.test_report.variants[0].metrics, policy.metric),
        )
        for fold in folds
    )
    operations = set(policy.operations)
    if operations & {_RANGE, _MAD}:
        _validate_collection_comparability(observations, policy.comparability_rule)
    changes = ()
    if _CHANGE in operations:
        changes = tuple(
            _adjacent_change(previous, current, policy.comparability_rule)
            for previous, current in zip(observations, observations[1:], strict=False)
        )
    values = tuple(item.value for item in observations)
    median = _median(values) if _MAD in operations else None
    return HistoricalExperimentWalkForwardMetricStability(
        policy.metric,
        observations,
        changes,
        _subtract(max(values), min(values)) if _RANGE in operations else None,
        median,
        _median(tuple(_absolute_deviation(item, median) for item in values))
        if median is not None
        else None,
        _sign_change_count(values) if _SIGN in operations else None,
    )


def _adjacent_change(previous, current, rule):  # type: ignore[no-untyped-def]
    _validate_pair_comparability(previous, current, rule)
    return HistoricalExperimentWalkForwardAdjacentMetricChange(
        previous.fold_ordinal,
        current.fold_ordinal,
        previous.fold_id,
        current.fold_id,
        previous.selected_variant_id,
        current.selected_variant_id,
        previous.value,
        current.value,
        _absolute_difference(previous.value, current.value),
        rule,
    )


def _validate_collection_comparability(observations, rule):  # type: ignore[no-untyped-def]
    for previous, current in zip(observations, observations[1:], strict=False):
        _validate_pair_comparability(previous, current, rule)


def _validate_pair_comparability(previous, current, rule):  # type: ignore[no-untyped-def]
    duration = rule in (
        HistoricalExperimentWalkForwardComparabilityRule.EQUAL_TEST_DURATION,
        HistoricalExperimentWalkForwardComparabilityRule.EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT,
    )
    schedule = rule in (
        HistoricalExperimentWalkForwardComparabilityRule.EQUAL_TEST_SCHEDULE_COUNT,
        HistoricalExperimentWalkForwardComparabilityRule.EQUAL_TEST_DURATION_AND_SCHEDULE_COUNT,
    )
    if duration and previous.test_duration != current.test_duration:
        raise HistoricalExperimentWalkForwardStabilityComparabilityError(
            "test durations are not equal"
        )
    if schedule and previous.test_schedule_count != current.test_schedule_count:
        raise HistoricalExperimentWalkForwardStabilityComparabilityError(
            "test schedule counts are not equal"
        )


def _metric_value(metrics, metric):  # type: ignore[no-untyped-def]
    value = getattr(metrics, _METRIC_FIELDS[metric])
    _scalar(value, HistoricalExperimentWalkForwardStabilityMetricError)
    return value


def _fraction(value):  # type: ignore[no-untyped-def]
    if type(value) is int:
        return Fraction(value)
    sign, digits, exponent = value.as_tuple()
    coefficient = int("".join(str(item) for item in digits) or "0")
    if sign:
        coefficient = -coefficient
    return (
        Fraction(coefficient * (10**exponent))
        if exponent >= 0
        else Fraction(coefficient, 10 ** (-exponent))
    )


def _decimal(value):  # type: ignore[no-untyped-def]
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise HistoricalExperimentWalkForwardStabilityArithmeticError(
            "exact statistic does not have a finite Decimal representation"
        )
    scale = max(twos, fives)
    coefficient = value.numerator * (2 ** (scale - twos)) * (5 ** (scale - fives))
    return Decimal(
        (
            1 if coefficient < 0 else 0,
            tuple(int(item) for item in str(abs(coefficient))) or (0,),
            -scale,
        )
    )


def _subtract(left, right):  # type: ignore[no-untyped-def]
    difference = _fraction(left) - _fraction(right)
    return difference.numerator if type(left) is int else _decimal(difference)


def _absolute_difference(left, right):  # type: ignore[no-untyped-def]
    difference = abs(_fraction(left) - _fraction(right))
    return difference.numerator if type(left) is int else _decimal(difference)


def _absolute_deviation(value, median):  # type: ignore[no-untyped-def]
    return _decimal(abs(_fraction(value) - _fraction(median)))


def _median(values):  # type: ignore[no-untyped-def]
    ordered = sorted(_fraction(item) for item in values)
    midpoint = len(ordered) // 2
    value = (
        ordered[midpoint]
        if len(ordered) % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    )
    return _decimal(value)


def _sign_change_count(values):  # type: ignore[no-untyped-def]
    return sum(
        previous != 0
        and current != 0
        and ((previous < 0 < current) or (current < 0 < previous))
        for previous, current in zip(values, values[1:], strict=False)
    )


def _reconcile_aggregate_overlap(aggregate, metrics):  # type: ignore[no-untyped-def]
    if aggregate is None:
        return
    available = {item.metric.value: item for item in aggregate.metric_summaries}
    for metric in metrics:
        summary = available.get(metric.metric.value)
        if summary is None:
            continue
        expected = tuple(
            (
                item.fold_ordinal,
                item.fold_id,
                item.test_report_id,
                item.test_run_id,
                item.selected_variant_id,
                item.value,
            )
            for item in metric.observations
        )
        actual = tuple(
            (
                item.fold_ordinal,
                item.fold_id,
                item.test_report_id,
                item.test_run_id,
                item.variant_id,
                item.value,
            )
            for item in summary.observations
        )
        if actual != expected:
            raise HistoricalExperimentWalkForwardStabilityAggregateSourceError(
                f"aggregate observations disagree for {metric.metric.value}"
            )


def _reconcile_result(fold_count, policy, selection, metrics):  # type: ignore[no-untyped-def]
    error = InconsistentHistoricalExperimentWalkForwardStabilityResultError
    if type(fold_count) is not int or fold_count <= 0:
        raise error("fold_count must be a positive exact integer")
    if type(selection) is not HistoricalExperimentWalkForwardSelectionStability:
        raise error("selection_stability has an invalid type")
    if len(selection.observations) != fold_count:
        raise error("selection observations do not cover every fold")
    selected = tuple(item.selected_variant_id for item in selection.observations)
    expected_transitions = _selection_stability_from_observations(
        selection.observations
    )
    if selection != expected_transitions:
        raise error("selection stability does not reconcile")
    if tuple(item.metric for item in metrics) != tuple(
        item.metric for item in policy.metrics
    ):
        raise error("metric stability order disagrees with policy")
    for metric_policy, metric in zip(policy.metrics, metrics, strict=True):
        if len(metric.observations) != fold_count:
            raise error("metric observations do not cover every fold")
        if tuple(item.selected_variant_id for item in metric.observations) != selected:
            raise error("metric selection provenance does not reconcile")
        expected = _metric_from_observations(metric.observations, metric_policy)
        if metric != expected:
            raise error("derived metric stability does not reconcile")


def _selection_stability_from_observations(observations):  # type: ignore[no-untyped-def]
    class Fold:
        pass

    folds = []
    for item in observations:
        fold = Fold()
        fold.ordinal = item.fold_ordinal
        fold.fold = Fold()
        fold.fold.fold_id = item.fold_id
        fold.fold.test_start = item.test_duration * 0
        fold.fold.test_end = item.test_duration
        fold.fold.test_rebalance_timestamps = range(item.test_schedule_count)
        fold.selection = Fold()
        fold.selection.selected_variant_id = item.selected_variant_id
        fold.selection.selected_rank = item.selected_rank
        folds.append(fold)
    return _selection_stability(tuple(folds))


def _metric_from_observations(observations, policy):  # type: ignore[no-untyped-def]
    operations = set(policy.operations)
    if operations & {_RANGE, _MAD}:
        _validate_collection_comparability(observations, policy.comparability_rule)
    changes = ()
    if _CHANGE in operations:
        changes = tuple(
            _adjacent_change(previous, current, policy.comparability_rule)
            for previous, current in zip(observations, observations[1:], strict=False)
        )
    values = tuple(item.value for item in observations)
    median = _median(values) if _MAD in operations else None
    return HistoricalExperimentWalkForwardMetricStability(
        policy.metric,
        observations,
        changes,
        _subtract(max(values), min(values)) if _RANGE in operations else None,
        median,
        _median(tuple(_absolute_deviation(item, median) for item in values))
        if median is not None
        else None,
        _sign_change_count(values) if _SIGN in operations else None,
    )


def _source_invariant(source, aggregate, policy):  # type: ignore[no-untyped-def]
    return (
        source,
        aggregate,
        policy,
        tuple(
            (
                fold.ordinal,
                fold.fold,
                fold.selection,
                fold.test_report.report_id,
                fold.test_report.variants[0],
            )
            for fold in source.folds
        ),
    )


def _result_id(
    source_id,
    request_id,
    fingerprint,
    aggregate_id,
    policy,
    fold_count,
    selection,
    metrics,
):  # type: ignore[no-untyped-def]
    material = [
        _typed(source_id),
        _typed(request_id),
        _typed(fingerprint),
        _typed(aggregate_id),
        _typed(policy.policy_id),
        _typed(fold_count),
        _typed_model(policy),
        _typed_model(selection),
    ]
    material.extend(_typed_model(item) for item in metrics)
    return uuid5(_NAMESPACE, "|".join((_VERSION, "result", *material)))


def _typed_model(value):  # type: ignore[no-untyped-def]
    if hasattr(value, "__dataclass_fields__"):
        return f"MODEL|{type(value).__name__}|" + "|".join(
            f"{field.name}={_typed_model(getattr(value, field.name))}"
            for field in fields(value)
        )
    if type(value) is tuple:
        return "TUPLE|" + "|".join(_typed_model(item) for item in value)
    return _typed(value)


def _typed(value):  # type: ignore[no-untyped-def]
    if value is None:
        return "NULL|"
    if type(value) is Decimal:
        return f"DECIMAL|{_canonical_decimal(value)}"
    if type(value) is bool:
        return f"BOOLEAN|{'true' if value else 'false'}"
    if type(value) is int:
        return f"INTEGER|{value}"
    if type(value) is UUID:
        return f"UUID|{value}"
    if type(value) is timedelta:
        return f"TIMEDELTA_MICROSECONDS|{_timedelta_microseconds(value)}"
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    if type(value) is str:
        return f"STRING|{len(value)}:{value}"
    raise HistoricalExperimentWalkForwardStabilityReconciliationError(
        "identity value has an unsupported type"
    )


def _timedelta_microseconds(value):  # type: ignore[no-untyped-def]
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _canonical_decimal(value):  # type: ignore[no-untyped-def]
    _scalar(value, HistoricalExperimentWalkForwardStabilityReconciliationError)
    fraction = _fraction(value)
    return _decimal(fraction).to_eng_string()


def _scalar(value, error):  # type: ignore[no-untyped-def]
    if type(value) is Decimal:
        if not value.is_finite():
            raise error("metric Decimal values must be finite")
    elif type(value) is not int:
        raise error("metric values must be exact Decimal or int")


def _ordinal(value, name, error):  # type: ignore[no-untyped-def]
    if type(value) is not int or value < 0:
        raise error(f"{name} must be an exact nonnegative integer")


def _tuple(values, name, error):  # type: ignore[no-untyped-def]
    try:
        return tuple(values)
    except TypeError as caught:
        raise error(f"{name} must be iterable") from caught


def _models(values, expected, name, error):  # type: ignore[no-untyped-def]
    result = _tuple(values, name, error)
    if not result or not all(type(item) is expected for item in result):
        raise error(f"{name} must contain exact {expected.__name__} values")
    return result


def _metadata(values, error):  # type: ignore[no-untyped-def]
    metadata = _tuple(values, "metadata", error)
    if not all(type(item) is MetadataEntry for item in metadata):
        raise error("metadata must contain exact MetadataEntry values")
    if len({item.key for item in metadata}) != len(metadata):
        raise error("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
        raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
    return metadata


if tuple(_METRIC_FIELDS.values()) != tuple(
    item.name for item in fields(HistoricalExperimentMetrics)
):
    raise RuntimeError("walk-forward stability metric mapping is incomplete")
