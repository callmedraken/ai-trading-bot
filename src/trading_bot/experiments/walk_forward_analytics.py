"""Pure deterministic analytics over independent walk-forward test folds."""

from dataclasses import dataclass, fields
from decimal import Decimal
from enum import Enum, StrEnum
from fractions import Fraction
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.experiments.exceptions import (
    HistoricalExperimentWalkForwardAggregateArithmeticError,
    HistoricalExperimentWalkForwardAggregateMetricError,
    HistoricalExperimentWalkForwardAggregateOperationError,
    HistoricalExperimentWalkForwardAggregateReconciliationError,
    HistoricalExperimentWalkForwardAggregateSourceError,
    InconsistentHistoricalExperimentWalkForwardAggregateResultError,
    InconsistentHistoricalExperimentWalkForwardResultError,
    InvalidHistoricalExperimentWalkForwardAggregatePolicyError,
)
from trading_bot.experiments.historical import HistoricalExperimentMetrics
from trading_bot.experiments.report import (
    HistoricalExperimentReportVariant,
    HistoricalExperimentReportVariantSource,
)
from trading_bot.experiments.walk_forward import (
    HistoricalExperimentWalkForwardFoldResult,
    HistoricalExperimentWalkForwardResult,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-walk-forward-aggregate-v1"
_NAMESPACE = UUID("d2238de1-30d0-55ed-b9a8-1179c0b58b5d")
_RESERVED_PREFIX = "historical_experiment_walk_forward_aggregate_"


class HistoricalExperimentWalkForwardAggregateMetric(StrEnum):
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


class HistoricalExperimentWalkForwardAggregateOperation(StrEnum):
    MINIMUM = "MINIMUM"
    MAXIMUM = "MAXIMUM"
    MEDIAN = "MEDIAN"
    EQUAL_FOLD_ARITHMETIC_MEAN = "EQUAL_FOLD_ARITHMETIC_MEAN"
    SIGN_COUNTS = "SIGN_COUNTS"


_METRIC_FIELDS = MappingProxyType(
    {
        metric: metric.value.lower()
        for metric in HistoricalExperimentWalkForwardAggregateMetric
    }
)
_ORDER = tuple(HistoricalExperimentWalkForwardAggregateOperation)
_DISTRIBUTION = frozenset(
    {
        HistoricalExperimentWalkForwardAggregateOperation.MINIMUM,
        HistoricalExperimentWalkForwardAggregateOperation.MAXIMUM,
        HistoricalExperimentWalkForwardAggregateOperation.MEDIAN,
    }
)
_MEAN = HistoricalExperimentWalkForwardAggregateOperation.EQUAL_FOLD_ARITHMETIC_MEAN
_SIGN = HistoricalExperimentWalkForwardAggregateOperation.SIGN_COUNTS
_ELIGIBILITY = MappingProxyType(
    {metric: frozenset() for metric in HistoricalExperimentWalkForwardAggregateMetric}
)
_eligibility = dict(_ELIGIBILITY)
for _metric in (
    HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_RETURN,
    HistoricalExperimentWalkForwardAggregateMetric.MEAN_EXPECTED_PORTFOLIO_RETURN,
):
    _eligibility[_metric] = _DISTRIBUTION | {_MEAN, _SIGN}
for _metric in (
    HistoricalExperimentWalkForwardAggregateMetric.MAXIMUM_DRAWDOWN_PERCENTAGE,
    HistoricalExperimentWalkForwardAggregateMetric.AGGREGATE_ONE_WAY_TURNOVER,
    HistoricalExperimentWalkForwardAggregateMetric.AGGREGATE_TWO_WAY_TURNOVER,
    HistoricalExperimentWalkForwardAggregateMetric.MAXIMUM_ALLOCATION_DRIFT,
):
    _eligibility[_metric] = _DISTRIBUTION
_eligibility[HistoricalExperimentWalkForwardAggregateMetric.WORST_CVAR] = (
    _DISTRIBUTION | {_SIGN}
)
for _metric in (
    HistoricalExperimentWalkForwardAggregateMetric.MINIMUM_TARGET_CASH_WEIGHT,
    HistoricalExperimentWalkForwardAggregateMetric.MAXIMUM_TARGET_CASH_WEIGHT,
):
    _eligibility[_metric] = _DISTRIBUTION | {_MEAN}
for _metric in (
    HistoricalExperimentWalkForwardAggregateMetric.ABSOLUTE_SIMULATION_PROFIT_LOSS,
    HistoricalExperimentWalkForwardAggregateMetric.SIMULATION_REALIZED_PROFIT_LOSS,
):
    _eligibility[_metric] = frozenset({_SIGN})
for _metric in (
    HistoricalExperimentWalkForwardAggregateMetric.TOTAL_ORDERS,
    HistoricalExperimentWalkForwardAggregateMetric.TOTAL_FILLS,
    HistoricalExperimentWalkForwardAggregateMetric.APPROVED_DECISIONS,
    HistoricalExperimentWalkForwardAggregateMetric.RESIZED_DECISIONS,
    HistoricalExperimentWalkForwardAggregateMetric.REJECTED_DECISIONS,
    HistoricalExperimentWalkForwardAggregateMetric.APPLIED_CYCLE_COUNT,
    HistoricalExperimentWalkForwardAggregateMetric.NO_ACTION_CYCLE_COUNT,
):
    _eligibility[_metric] = _DISTRIBUTION | {_MEAN}
METRIC_OPERATION_ELIGIBILITY = MappingProxyType(_eligibility)
del _eligibility, _metric


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardMetricPolicy:
    metric: HistoricalExperimentWalkForwardAggregateMetric
    operations: tuple[HistoricalExperimentWalkForwardAggregateOperation, ...]

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardAggregatePolicyError
        if type(self.metric) is not HistoricalExperimentWalkForwardAggregateMetric:
            raise error("metric has an invalid type")
        operations = _tuple(self.operations, "operations", error)
        if not all(
            type(item) is HistoricalExperimentWalkForwardAggregateOperation
            for item in operations
        ):
            raise error("operations must contain exact aggregate operations")
        if len(set(operations)) != len(operations):
            raise error("operations must not contain duplicates")
        unsupported = set(operations) - METRIC_OPERATION_ELIGIBILITY[self.metric]
        if unsupported:
            names = ", ".join(sorted(item.value for item in unsupported))
            raise HistoricalExperimentWalkForwardAggregateOperationError(
                f"{self.metric.value} does not allow: {names}"
            )
        canonical = tuple(item for item in _ORDER if item in operations)
        object.__setattr__(self, "operations", canonical)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardAggregatePolicy:
    policy_id: UUID
    metrics: tuple[HistoricalExperimentWalkForwardMetricPolicy, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentWalkForwardAggregatePolicyError
        if type(self.policy_id) is not UUID:
            raise error("policy_id must be an exact UUID")
        metrics = _tuple(self.metrics, "metrics", error)
        if not metrics or not all(
            type(item) is HistoricalExperimentWalkForwardMetricPolicy
            for item in metrics
        ):
            raise error("metrics must contain exact metric policies")
        for item in metrics:
            item.__post_init__()
        if len({item.metric for item in metrics}) != len(metrics):
            raise error("policy metrics must be unique")
        metadata = _metadata(self.metadata, error)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardMetricObservation:
    fold_ordinal: int
    fold_id: UUID
    test_report_id: UUID
    test_run_id: UUID
    variant_id: UUID
    value: Decimal | int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        _ordinal(self.fold_ordinal, "fold_ordinal", error)
        for name in ("fold_id", "test_report_id", "test_run_id", "variant_id"):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        _scalar(self.value, error)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardExactRational:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise error("rational terms must be exact integers")
        if self.denominator <= 0:
            raise error("rational denominator must be positive")
        reduced = Fraction(self.numerator, self.denominator)
        if (reduced.numerator, reduced.denominator) != (
            self.numerator,
            self.denominator,
        ):
            raise error("rational terms must be reduced")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardSignCounts:
    positive: int
    zero: int
    negative: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        for name in ("positive", "zero", "negative"):
            _ordinal(getattr(self, name), name, error)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardMetricSummary:
    metric: HistoricalExperimentWalkForwardAggregateMetric
    observations: tuple[HistoricalExperimentWalkForwardMetricObservation, ...]
    minimum: Decimal | int | None = None
    maximum: Decimal | int | None = None
    median: Decimal | None = None
    arithmetic_mean: HistoricalExperimentWalkForwardExactRational | None = None
    sign_counts: HistoricalExperimentWalkForwardSignCounts | None = None

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        if type(self.metric) is not HistoricalExperimentWalkForwardAggregateMetric:
            raise error("metric has an invalid type")
        observations = _tuple(self.observations, "observations", error)
        if not observations or not all(
            type(item) is HistoricalExperimentWalkForwardMetricObservation
            for item in observations
        ):
            raise error("observations must contain exact metric observations")
        for item in observations:
            item.__post_init__()
        values = tuple(item.value for item in observations)
        if len({type(value) for value in values}) != 1:
            raise error("metric observation scalar types must agree")
        for value in (self.minimum, self.maximum):
            if value is not None:
                _scalar(value, error)
                if type(value) is not type(values[0]):
                    raise error("extrema must retain the source scalar type")
        if self.median is not None:
            if type(self.median) is not Decimal or not self.median.is_finite():
                raise error("median must be an exact finite Decimal or None")
        if self.arithmetic_mean is not None:
            if (
                type(self.arithmetic_mean)
                is not HistoricalExperimentWalkForwardExactRational
            ):
                raise error("arithmetic_mean has an invalid type")
            self.arithmetic_mean.__post_init__()
        if self.sign_counts is not None:
            if type(self.sign_counts) is not HistoricalExperimentWalkForwardSignCounts:
                raise error("sign_counts has an invalid type")
            self.sign_counts.__post_init__()
        object.__setattr__(self, "observations", observations)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardFoldSummary:
    fold_ordinal: int
    fold_id: UUID
    test_report_id: UUID
    test_run_id: UUID
    test_rolling_result_id: UUID
    selected_variant_id: UUID
    selected_rank: int
    metrics: tuple[HistoricalExperimentWalkForwardMetricObservation, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        _ordinal(self.fold_ordinal, "fold_ordinal", error)
        for name in (
            "fold_id",
            "test_report_id",
            "test_run_id",
            "test_rolling_result_id",
            "selected_variant_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        if self.selected_rank != 1:
            raise error("selected_rank must be exactly one")
        metrics = _tuple(self.metrics, "metrics", error)
        if not metrics or not all(
            type(item) is HistoricalExperimentWalkForwardMetricObservation
            for item in metrics
        ):
            raise error("metrics must contain exact observations")
        for item in metrics:
            item.__post_init__()
            if (
                item.fold_ordinal != self.fold_ordinal
                or item.fold_id != self.fold_id
                or item.test_report_id != self.test_report_id
                or item.test_run_id != self.test_run_id
                or item.variant_id != self.selected_variant_id
            ):
                raise error("fold observation provenance is inconsistent")
        object.__setattr__(self, "metrics", metrics)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardVariantFrequency:
    variant_id: UUID
    selected_fold_count: int
    rank_one_selected_fold_count: int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        if type(self.variant_id) is not UUID:
            raise error("variant_id must be an exact UUID")
        for name in ("selected_fold_count", "rank_one_selected_fold_count"):
            _ordinal(getattr(self, name), name, error)
        if self.selected_fold_count <= 0:
            raise error("frequency rows must represent at least one selection")
        if self.rank_one_selected_fold_count != self.selected_fold_count:
            raise error("all selected folds must be rank-one selections")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentWalkForwardAggregateResult:
    result_id: UUID
    source_walk_forward_result_id: UUID
    source_request_id: UUID
    source_historical_fingerprint: UUID
    policy: HistoricalExperimentWalkForwardAggregatePolicy
    fold_count: int
    successful_test_fold_count: int
    fold_summaries: tuple[HistoricalExperimentWalkForwardFoldSummary, ...]
    metric_summaries: tuple[HistoricalExperimentWalkForwardMetricSummary, ...]
    variant_frequencies: tuple[HistoricalExperimentWalkForwardVariantFrequency, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentWalkForwardAggregateResultError
        for name in (
            "result_id",
            "source_walk_forward_result_id",
            "source_request_id",
            "source_historical_fingerprint",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        if type(self.policy) is not HistoricalExperimentWalkForwardAggregatePolicy:
            raise error("policy has an invalid type")
        try:
            self.policy.__post_init__()
        except (
            InvalidHistoricalExperimentWalkForwardAggregatePolicyError,
            HistoricalExperimentWalkForwardAggregateOperationError,
        ) as caught:
            raise error(f"retained policy is invalid: {caught}") from caught
        folds = _exact_models(
            self.fold_summaries,
            HistoricalExperimentWalkForwardFoldSummary,
            "fold_summaries",
            error,
        )
        metrics = _exact_models(
            self.metric_summaries,
            HistoricalExperimentWalkForwardMetricSummary,
            "metric_summaries",
            error,
        )
        frequencies = _exact_models(
            self.variant_frequencies,
            HistoricalExperimentWalkForwardVariantFrequency,
            "variant_frequencies",
            error,
        )
        for item in (*folds, *metrics, *frequencies):
            item.__post_init__()
        _reconcile_aggregate(
            self.policy,
            self.fold_count,
            self.successful_test_fold_count,
            folds,
            metrics,
            frequencies,
            error,
        )
        object.__setattr__(self, "fold_summaries", folds)
        object.__setattr__(self, "metric_summaries", metrics)
        object.__setattr__(self, "variant_frequencies", frequencies)
        expected = _result_id(
            self.source_walk_forward_result_id,
            self.source_request_id,
            self.source_historical_fingerprint,
            self.policy,
            self.fold_count,
            self.successful_test_fold_count,
            folds,
            metrics,
            frequencies,
        )
        if self.result_id != expected:
            raise error("result_id is inconsistent")


class HistoricalExperimentWalkForwardAggregateAnalyzer:
    """Summarize exact independent test-fold observations without composition."""

    def analyze(
        self,
        result: HistoricalExperimentWalkForwardResult,
        policy: HistoricalExperimentWalkForwardAggregatePolicy,
    ) -> HistoricalExperimentWalkForwardAggregateResult:
        folds = _validate_source(result)
        if type(policy) is not HistoricalExperimentWalkForwardAggregatePolicy:
            raise InvalidHistoricalExperimentWalkForwardAggregatePolicyError(
                "policy must be exactly HistoricalExperimentWalkForwardAggregatePolicy"
            )
        policy.__post_init__()
        before = _source_invariant(result, policy)
        fold_summaries = tuple(_fold_summary(item, policy) for item in folds)
        metric_summaries = tuple(
            _metric_summary(metric_policy, fold_summaries, index)
            for index, metric_policy in enumerate(policy.metrics)
        )
        frequencies = _frequencies(fold_summaries)
        fold_count = len(folds)
        _reconcile_aggregate(
            policy,
            fold_count,
            fold_count,
            fold_summaries,
            metric_summaries,
            frequencies,
            HistoricalExperimentWalkForwardAggregateReconciliationError,
        )
        if before != _source_invariant(result, policy):
            raise HistoricalExperimentWalkForwardAggregateReconciliationError(
                "source result or policy changed during analysis"
            )
        identifier = _result_id(
            result.result_id,
            result.request_id,
            result.source_historical_fingerprint,
            policy,
            fold_count,
            fold_count,
            fold_summaries,
            metric_summaries,
            frequencies,
        )
        return HistoricalExperimentWalkForwardAggregateResult(
            identifier,
            result.result_id,
            result.request_id,
            result.source_historical_fingerprint,
            policy,
            fold_count,
            fold_count,
            fold_summaries,
            metric_summaries,
            frequencies,
        )


def _validate_source(
    result: HistoricalExperimentWalkForwardResult,
) -> tuple[HistoricalExperimentWalkForwardFoldResult, ...]:
    error = HistoricalExperimentWalkForwardAggregateSourceError
    if type(result) is not HistoricalExperimentWalkForwardResult:
        raise error("result must be exactly HistoricalExperimentWalkForwardResult")
    try:
        result.__post_init__()
    except InconsistentHistoricalExperimentWalkForwardResultError as caught:
        raise error(f"source walk-forward result is inconsistent: {caught}") from caught
    folds = tuple(result.folds)
    for expected_ordinal, fold in enumerate(folds):
        if fold.ordinal != expected_ordinal:
            raise error("source fold ordinals must be sequential")
        report = fold.test_report
        if (
            report.variant_source
            is not HistoricalExperimentReportVariantSource.EXPLICIT
            or report.ranking is not None
            or len(report.variants) != 1
        ):
            raise error("each test report must be explicit, unranked, and one-row")
        row = report.variants[0]
        if type(row) is not HistoricalExperimentReportVariant:
            raise error("test report row has an invalid type")
        if (
            row.caller_ordinal != 0
            or row.rank is not None
            or row.comparison_values
            or row.experiment_run_id != fold.test_run_id
            or row.rolling_result_id != fold.test_rolling_result_id
            or row.variant_id != fold.selection.selected_variant_id
        ):
            raise error("test report row provenance is inconsistent")
        if type(row.metrics) is not HistoricalExperimentMetrics:
            raise error("test report row metrics have an invalid type")
    return folds


def _fold_summary(fold, policy):  # type: ignore[no-untyped-def]
    row = fold.test_report.variants[0]
    observations = tuple(
        HistoricalExperimentWalkForwardMetricObservation(
            fold.ordinal,
            fold.fold.fold_id,
            fold.test_report.report_id,
            fold.test_run_id,
            fold.selection.selected_variant_id,
            _metric_value(row.metrics, item.metric),
        )
        for item in policy.metrics
    )
    return HistoricalExperimentWalkForwardFoldSummary(
        fold.ordinal,
        fold.fold.fold_id,
        fold.test_report.report_id,
        fold.test_run_id,
        fold.test_rolling_result_id,
        fold.selection.selected_variant_id,
        fold.selection.selected_rank,
        observations,
    )


def _metric_summary(policy, folds, index):  # type: ignore[no-untyped-def]
    observations = tuple(fold.metrics[index] for fold in folds)
    values = tuple(item.value for item in observations)
    operations = set(policy.operations)
    return HistoricalExperimentWalkForwardMetricSummary(
        policy.metric,
        observations,
        min(values)
        if HistoricalExperimentWalkForwardAggregateOperation.MINIMUM in operations
        else None,
        max(values)
        if HistoricalExperimentWalkForwardAggregateOperation.MAXIMUM in operations
        else None,
        _median(values)
        if HistoricalExperimentWalkForwardAggregateOperation.MEDIAN in operations
        else None,
        _mean(values) if _MEAN in operations else None,
        _sign_counts(values) if _SIGN in operations else None,
    )


def _metric_value(metrics, metric):  # type: ignore[no-untyped-def]
    field = _METRIC_FIELDS.get(metric)
    if field is None:
        raise HistoricalExperimentWalkForwardAggregateMetricError(
            "aggregate metric is unsupported"
        )
    value = getattr(metrics, field, None)
    _scalar(value, HistoricalExperimentWalkForwardAggregateMetricError)
    return value


def _fraction(value: Decimal | int) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    sign, digits, exponent = value.as_tuple()
    coefficient = int("".join(str(item) for item in digits) or "0")
    if sign:
        coefficient = -coefficient
    if exponent >= 0:
        return Fraction(coefficient * (10**exponent))
    return Fraction(coefficient, 10 ** (-exponent))


def _mean(values) -> HistoricalExperimentWalkForwardExactRational:  # type: ignore[no-untyped-def]
    try:
        value = sum((_fraction(item) for item in values), start=Fraction()) / len(
            values
        )
    except (MemoryError, OverflowError, ValueError, ZeroDivisionError) as caught:
        raise HistoricalExperimentWalkForwardAggregateArithmeticError(
            f"cannot construct exact arithmetic mean: {caught}"
        ) from caught
    return HistoricalExperimentWalkForwardExactRational(
        value.numerator, value.denominator
    )


def _median(values) -> Decimal:  # type: ignore[no-untyped-def]
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return _decimal_from_fraction(_fraction(ordered[midpoint]))
    return _decimal_from_fraction(
        (_fraction(ordered[midpoint - 1]) + _fraction(ordered[midpoint])) / 2
    )


def _decimal_from_fraction(value: Fraction) -> Decimal:
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise HistoricalExperimentWalkForwardAggregateArithmeticError(
            "exact median does not have a finite Decimal representation"
        )
    scale = max(twos, fives)
    coefficient = value.numerator * (2 ** (scale - twos)) * (5 ** (scale - fives))
    sign = 1 if coefficient < 0 else 0
    digits = tuple(int(item) for item in str(abs(coefficient))) or (0,)
    return Decimal((sign, digits, -scale))


def _sign_counts(values):  # type: ignore[no-untyped-def]
    return HistoricalExperimentWalkForwardSignCounts(
        sum(value > 0 for value in values),
        sum(value == 0 for value in values),
        sum(value < 0 for value in values),
    )


def _frequencies(folds):  # type: ignore[no-untyped-def]
    ordered = []
    counts = {}
    for fold in folds:
        identifier = fold.selected_variant_id
        if identifier not in counts:
            ordered.append(identifier)
            counts[identifier] = 0
        counts[identifier] += 1
    return tuple(
        HistoricalExperimentWalkForwardVariantFrequency(
            identifier, counts[identifier], counts[identifier]
        )
        for identifier in ordered
    )


def _reconcile_aggregate(
    policy, fold_count, successful, folds, metrics, frequencies, error
):  # type: ignore[no-untyped-def]
    if type(fold_count) is not int or fold_count <= 0:
        raise error("fold_count must be a positive exact integer")
    if successful != fold_count:
        raise error("successful_test_fold_count must equal fold_count")
    if len(folds) != fold_count or tuple(item.fold_ordinal for item in folds) != tuple(
        range(fold_count)
    ):
        raise error("fold summaries do not provide ordered complete coverage")
    if tuple(item.metric for item in metrics) != tuple(
        item.metric for item in policy.metrics
    ):
        raise error("metric summary order disagrees with policy")
    if any(len(item.metrics) != len(policy.metrics) for item in folds):
        raise error("fold metric coverage disagrees with policy")
    for index, (metric_policy, summary) in enumerate(
        zip(policy.metrics, metrics, strict=True)
    ):
        expected_observations = tuple(fold.metrics[index] for fold in folds)
        if summary.observations != expected_observations:
            raise error("metric observations do not preserve fold order")
        expected = _metric_summary(metric_policy, folds, index)
        if summary != expected:
            raise error("derived metric statistics do not reconcile")
    selected = tuple(item.selected_variant_id for item in folds)
    expected_frequencies = _frequencies(folds)
    if frequencies != expected_frequencies:
        raise error("variant frequencies do not reconcile in first-appearance order")
    if sum(item.selected_fold_count for item in frequencies) != fold_count:
        raise error("variant frequencies do not cover every fold")
    if not selected:
        raise error("aggregate must retain selected variants")


def _source_invariant(result, policy):  # type: ignore[no-untyped-def]
    return (
        result.result_id,
        result.request_id,
        result.source_historical_fingerprint,
        policy.policy_id,
        policy.metrics,
        policy.metadata,
        tuple(
            (
                item.ordinal,
                item.fold.fold_id,
                item.test_report.report_id,
                item.test_run_id,
                item.test_rolling_result_id,
                item.selection.selected_rank,
                item.selection.selected_variant_id,
                item.test_report.variants[0].metrics,
            )
            for item in result.folds
        ),
    )


def _result_id(
    source_result_id,
    source_request_id,
    source_fingerprint,
    policy,
    fold_count,
    successful,
    folds,
    metrics,
    frequencies,
):  # type: ignore[no-untyped-def]
    material = [
        _typed(source_result_id),
        _typed(source_request_id),
        _typed(source_fingerprint),
        _typed(policy.policy_id),
    ]
    for item in policy.metrics:
        material.append(_typed(item.metric))
        material.extend(_typed(operation) for operation in item.operations)
    for item in policy.metadata:
        material.extend((_typed(item.key), _typed(item.value)))
    material.extend((_typed(fold_count), _typed(successful)))
    for fold in folds:
        material.extend(
            (
                _typed(fold.fold_ordinal),
                _typed(fold.fold_id),
                _typed(fold.test_report_id),
                _typed(fold.test_run_id),
                _typed(fold.test_rolling_result_id),
                _typed(fold.selected_variant_id),
                _typed(fold.selected_rank),
            )
        )
        material.extend(_observation_material(item) for item in fold.metrics)
    for summary in metrics:
        material.append(_typed(summary.metric))
        material.extend(_observation_material(item) for item in summary.observations)
        material.extend(
            (
                _typed(summary.minimum),
                _typed(summary.maximum),
                _typed(summary.median),
            )
        )
        if summary.arithmetic_mean is None:
            material.append(_typed(None))
        else:
            material.append(
                "RATIONAL|"
                f"{summary.arithmetic_mean.numerator}/"
                f"{summary.arithmetic_mean.denominator}"
            )
        if summary.sign_counts is None:
            material.append(_typed(None))
        else:
            material.extend(
                (
                    _typed(summary.sign_counts.positive),
                    _typed(summary.sign_counts.zero),
                    _typed(summary.sign_counts.negative),
                )
            )
    for item in frequencies:
        material.extend(
            (
                _typed(item.variant_id),
                _typed(item.selected_fold_count),
                _typed(item.rank_one_selected_fold_count),
            )
        )
    return uuid5(_NAMESPACE, "|".join((_VERSION, "result", *material)))


def _observation_material(item):  # type: ignore[no-untyped-def]
    return ",".join(
        (
            _typed(item.fold_ordinal),
            _typed(item.fold_id),
            _typed(item.test_report_id),
            _typed(item.test_run_id),
            _typed(item.variant_id),
            _typed(item.value),
        )
    )


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
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    if type(value) is str:
        return f"STRING|{value}"
    raise HistoricalExperimentWalkForwardAggregateReconciliationError(
        "identity value has an unsupported type"
    )


def _canonical_decimal(value: Decimal) -> str:
    _scalar(value, HistoricalExperimentWalkForwardAggregateReconciliationError)
    if value.is_zero():
        return "0"
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(item) for item in digits)
    coefficient = coefficient.rstrip("0")
    exponent += len(digits) - len(coefficient)
    if exponent >= 0:
        text = coefficient + ("0" * exponent)
    else:
        point = len(coefficient) + exponent
        text = (
            coefficient[:point] + "." + coefficient[point:]
            if point > 0
            else "0." + ("0" * (-point)) + coefficient
        )
    return f"-{text}" if sign else text


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


def _metadata(values, error):  # type: ignore[no-untyped-def]
    metadata = _tuple(values, "metadata", error)
    if not all(type(item) is MetadataEntry for item in metadata):
        raise error("metadata must contain exact MetadataEntry values")
    if len({item.key for item in metadata}) != len(metadata):
        raise error("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
        raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
    return metadata


def _exact_models(values, expected, name, error):  # type: ignore[no-untyped-def]
    result = _tuple(values, name, error)
    if not result or not all(type(item) is expected for item in result):
        raise error(f"{name} must contain exact {expected.__name__} values")
    return result


if tuple(_METRIC_FIELDS.values()) != tuple(
    item.name for item in fields(HistoricalExperimentMetrics)
):
    raise RuntimeError("walk-forward aggregate metric mapping is incomplete")
