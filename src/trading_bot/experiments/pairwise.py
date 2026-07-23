"""Deterministic pairwise analysis of compact historical experiment reports."""

from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    Context,
    Decimal,
    DecimalException,
    localcontext,
)
from enum import Enum, StrEnum
from itertools import combinations
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments.comparison import HistoricalExperimentRankingMetric
from trading_bot.experiments.exceptions import (
    HistoricalExperimentPairwiseArithmeticError,
    HistoricalExperimentPairwiseMetricError,
    HistoricalExperimentPairwiseReconciliationError,
    HistoricalExperimentPairwiseReportError,
    InconsistentHistoricalExperimentPairwiseResultError,
    InvalidHistoricalExperimentPairwisePolicyError,
)
from trading_bot.experiments.historical import HistoricalExperimentMetrics
from trading_bot.experiments.report import (
    HistoricalExperimentReport,
    HistoricalExperimentReportVariant,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-pairwise-v1"
_NAMESPACE = UUID("ec4fc08a-97de-54ad-a941-98e16bdc8914")
_RESERVED_PREFIX = "historical_experiment_pairwise_"

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
_INTEGER_METRICS = frozenset(
    {
        HistoricalExperimentRankingMetric.TOTAL_ORDERS,
        HistoricalExperimentRankingMetric.TOTAL_FILLS,
        HistoricalExperimentRankingMetric.APPROVED_DECISIONS,
        HistoricalExperimentRankingMetric.RESIZED_DECISIONS,
        HistoricalExperimentRankingMetric.REJECTED_DECISIONS,
        HistoricalExperimentRankingMetric.APPLIED_CYCLE_COUNT,
        HistoricalExperimentRankingMetric.NO_ACTION_CYCLE_COUNT,
    }
)


class HistoricalExperimentPairwiseOrientation(StrEnum):
    CALLER_ORDER = "CALLER_ORDER"
    VARIANT_ID = "VARIANT_ID"


class HistoricalExperimentPairwisePairing(StrEnum):
    ALL_UNORDERED_PAIRS = "ALL_UNORDERED_PAIRS"
    BASELINE_VERSUS_ALL = "BASELINE_VERSUS_ALL"


@dataclass(frozen=True, slots=True)
class HistoricalExperimentPairwisePolicy:
    policy_id: UUID
    metrics: tuple[HistoricalExperimentRankingMetric, ...]
    pairing: HistoricalExperimentPairwisePairing
    orientation: HistoricalExperimentPairwiseOrientation
    baseline_variant_id: UUID | None
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentPairwisePolicyError
        if type(self.policy_id) is not UUID:
            raise error("policy_id must be an exact UUID")
        try:
            metrics = tuple(item for item in self.metrics)
        except TypeError as caught:
            raise error("metrics must be iterable") from caught
        if not metrics:
            raise error("metrics must not be empty")
        if not all(type(item) is HistoricalExperimentRankingMetric for item in metrics):
            raise error("metrics contain an invalid value")
        if len(set(metrics)) != len(metrics):
            raise error("metrics must be unique")
        if type(self.pairing) is not HistoricalExperimentPairwisePairing:
            raise error("pairing has an invalid type")
        if type(self.orientation) is not HistoricalExperimentPairwiseOrientation:
            raise error("orientation has an invalid type")
        baseline = self.baseline_variant_id
        if baseline is not None and type(baseline) is not UUID:
            raise error("baseline_variant_id must be an exact UUID or None")
        if self.pairing is HistoricalExperimentPairwisePairing.ALL_UNORDERED_PAIRS:
            if baseline is not None:
                raise error("all-pairs policy cannot specify a baseline")
        else:
            if baseline is None:
                raise error("baseline pairing requires baseline_variant_id")
            if (
                self.orientation
                is not HistoricalExperimentPairwiseOrientation.CALLER_ORDER
            ):
                raise error("baseline pairing requires CALLER_ORDER orientation")
        metadata = _validated_metadata(self.metadata, error)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentPairwiseDifference:
    metric: HistoricalExperimentRankingMetric
    left_value: Decimal | int
    right_value: Decimal | int
    difference: Decimal | int

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentPairwiseResultError
        if type(self.metric) is not HistoricalExperimentRankingMetric:
            raise error("difference metric has an invalid type")
        _validate_metric_scalar(self.metric, self.left_value, error)
        _validate_metric_scalar(self.metric, self.right_value, error)
        _validate_difference_values(
            self.left_value,
            self.right_value,
            self.difference,
            error,
        )
        if type(self.difference) is Decimal and self.difference == Decimal("0"):
            object.__setattr__(self, "difference", Decimal("0"))


@dataclass(frozen=True, slots=True)
class HistoricalExperimentPairwiseRecord:
    ordinal: int
    left_caller_ordinal: int
    right_caller_ordinal: int
    left_variant_id: UUID
    right_variant_id: UUID
    differences: tuple[HistoricalExperimentPairwiseDifference, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentPairwiseResultError
        for name in ("ordinal", "left_caller_ordinal", "right_caller_ordinal"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise error(f"{name} must be an exact nonnegative integer")
        if self.left_caller_ordinal == self.right_caller_ordinal:
            raise error("pair caller ordinals must be distinct")
        for name in ("left_variant_id", "right_variant_id"):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be an exact UUID")
        if self.left_variant_id == self.right_variant_id:
            raise error("pair variant IDs must be distinct")
        try:
            differences = tuple(item for item in self.differences)
        except TypeError as caught:
            raise error("differences must be iterable") from caught
        if not differences or not all(
            type(item) is HistoricalExperimentPairwiseDifference for item in differences
        ):
            raise error("differences must contain pairwise differences")
        for difference in differences:
            difference.__post_init__()
        object.__setattr__(self, "differences", differences)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentPairwiseResult:
    result_id: UUID
    source_report_id: UUID
    policy: HistoricalExperimentPairwisePolicy
    records: tuple[HistoricalExperimentPairwiseRecord, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentPairwiseResultError
        if type(self.result_id) is not UUID or type(self.source_report_id) is not UUID:
            raise error("result and source report IDs must be exact UUIDs")
        if type(self.policy) is not HistoricalExperimentPairwisePolicy:
            raise error("policy must be exactly HistoricalExperimentPairwisePolicy")
        try:
            self.policy.__post_init__()
        except InvalidHistoricalExperimentPairwisePolicyError as caught:
            raise error(f"retained policy is invalid: {caught}") from caught
        try:
            records = tuple(item for item in self.records)
        except TypeError as caught:
            raise error("records must be iterable") from caught
        if not all(
            type(item) is HistoricalExperimentPairwiseRecord for item in records
        ):
            raise error("records contain an invalid value")
        for record in records:
            record.__post_init__()
        _validate_retained_records(self.policy, records, error)
        object.__setattr__(self, "records", records)
        if self.result_id != _result_id(self.source_report_id, self.policy, records):
            raise error("result_id is inconsistent")


class HistoricalExperimentPairwiseComparator:
    """Compare selected exact metrics across one completed compact report."""

    def compare(
        self,
        report: HistoricalExperimentReport,
        policy: HistoricalExperimentPairwisePolicy,
    ) -> HistoricalExperimentPairwiseResult:
        _validate_report(report)
        if type(policy) is not HistoricalExperimentPairwisePolicy:
            raise InvalidHistoricalExperimentPairwisePolicyError(
                "policy must be exactly HistoricalExperimentPairwisePolicy"
            )
        policy.__post_init__()
        before_report = _report_invariant(report)
        before_policy = _policy_invariant(policy)
        fields = tuple(_METRIC_FIELDS[metric] for metric in policy.metrics)
        for row in report.variants:
            for metric, field in zip(policy.metrics, fields, strict=True):
                _validate_metric_scalar(
                    metric,
                    getattr(row.metrics, field),
                    HistoricalExperimentPairwiseMetricError,
                )
        pairs = _pair_rows(report.variants, policy)
        records = []
        for ordinal, (left, right) in enumerate(pairs):
            differences = []
            for metric, field in zip(policy.metrics, fields, strict=True):
                left_value = getattr(left.metrics, field)
                right_value = getattr(right.metrics, field)
                _validate_source_values(metric, left_value, right_value)
                try:
                    difference = _subtract(right_value, left_value)
                except HistoricalExperimentPairwiseArithmeticError as caught:
                    raise HistoricalExperimentPairwiseArithmeticError(
                        f"pair {ordinal} metric {metric.value}: {caught}"
                    ) from caught
                differences.append(
                    HistoricalExperimentPairwiseDifference(
                        metric, left_value, right_value, difference
                    )
                )
            records.append(
                HistoricalExperimentPairwiseRecord(
                    ordinal,
                    left.caller_ordinal,
                    right.caller_ordinal,
                    left.variant_id,
                    right.variant_id,
                    tuple(differences),
                )
            )
        result_records = tuple(records)
        _reconcile(report, policy, result_records)
        if before_report != _report_invariant(
            report
        ) or before_policy != _policy_invariant(policy):
            raise HistoricalExperimentPairwiseReconciliationError(
                "pairwise source inputs changed during comparison"
            )
        result_id = _result_id(report.report_id, policy, result_records)
        return HistoricalExperimentPairwiseResult(
            result_id, report.report_id, policy, result_records
        )


def _validate_report(report) -> None:  # type: ignore[no-untyped-def]
    error = HistoricalExperimentPairwiseReportError
    if type(report) is not HistoricalExperimentReport:
        raise error("report must be exactly HistoricalExperimentReport")
    if type(report.report_id) is not UUID:
        raise error("source report_id must be an exact UUID")
    rows = report.variants
    if not rows or not all(
        type(item) is HistoricalExperimentReportVariant for item in rows
    ):
        raise error("report variants must contain one or more exact rows")
    if tuple(item.caller_ordinal for item in rows) != tuple(range(len(rows))):
        raise error("report caller ordinals must be sequential from zero")
    if len({item.variant_id for item in rows}) != len(rows):
        raise error("report variant IDs must be unique")
    if not all(type(item.metrics) is HistoricalExperimentMetrics for item in rows):
        raise error("report rows must retain exact HistoricalExperimentMetrics")


def _pair_rows(
    rows: tuple[HistoricalExperimentReportVariant, ...],
    policy: HistoricalExperimentPairwisePolicy,
) -> tuple[
    tuple[HistoricalExperimentReportVariant, HistoricalExperimentReportVariant], ...
]:
    if policy.pairing is HistoricalExperimentPairwisePairing.BASELINE_VERSUS_ALL:
        matches = tuple(
            item for item in rows if item.variant_id == policy.baseline_variant_id
        )
        if len(matches) != 1:
            raise HistoricalExperimentPairwiseReportError(
                "baseline variant must appear exactly once in the report"
            )
        baseline = matches[0]
        return tuple((baseline, item) for item in rows if item is not baseline)
    pairs = []
    for first, second in combinations(rows, 2):
        if (
            policy.orientation is HistoricalExperimentPairwiseOrientation.VARIANT_ID
            and second.variant_id.int < first.variant_id.int
        ):
            pairs.append((second, first))
        else:
            pairs.append((first, second))
    return tuple(pairs)


def _validate_source_values(metric, left, right) -> None:  # type: ignore[no-untyped-def]
    error = HistoricalExperimentPairwiseMetricError
    _validate_metric_scalar(metric, left, error)
    _validate_metric_scalar(metric, right, error)


def _validate_metric_scalar(metric, value, error_type) -> None:  # type: ignore[no-untyped-def]
    if metric in _INTEGER_METRICS:
        if type(value) is not int or value < 0:
            raise error_type(
                f"metric {metric.value} must be an exact nonnegative integer"
            )
    elif type(value) is not Decimal or not value.is_finite():
        raise error_type(f"metric {metric.value} must be a finite exact Decimal")


def _validate_difference_values(left, right, difference, error_type) -> None:  # type: ignore[no-untyped-def]
    if type(left) is not type(right) or type(left) is not type(difference):
        raise error_type("difference values must have the same exact scalar type")
    if type(left) is int:
        if left < 0 or right < 0:
            raise error_type("integer source values must be nonnegative")
        expected = right - left
    elif type(left) is Decimal:
        if not left.is_finite() or not right.is_finite() or not difference.is_finite():
            raise error_type("Decimal difference values must be finite")
        expected = _exact_decimal_subtract(right, left)
    else:
        raise error_type("difference values must be exact Decimal or integer")
    if difference != expected:
        raise error_type("difference must equal exact right minus left")


def _subtract(right, left):  # type: ignore[no-untyped-def]
    if type(right) is int and type(left) is int:
        return right - left
    if type(right) is Decimal and type(left) is Decimal:
        return _exact_decimal_subtract(right, left)
    raise HistoricalExperimentPairwiseMetricError(
        "pairwise source values must share one supported exact type"
    )


def _exact_decimal_subtract(right: Decimal, left: Decimal) -> Decimal:
    if (
        type(right) is not Decimal
        or type(left) is not Decimal
        or not right.is_finite()
        or not left.is_finite()
    ):
        raise HistoricalExperimentPairwiseArithmeticError(
            "exact subtraction requires finite exact Decimals"
        )
    try:
        right_tuple = right.as_tuple()
        left_tuple = left.as_tuple()
        right_coefficient = _coefficient(right_tuple.digits)
        left_coefficient = _coefficient(left_tuple.digits)
        if right_tuple.sign:
            right_coefficient = -right_coefficient
        if left_tuple.sign:
            left_coefficient = -left_coefficient
        common_exponent = min(right_tuple.exponent, left_tuple.exponent)
        right_aligned = right_coefficient * (
            10 ** (right_tuple.exponent - common_exponent)
        )
        left_aligned = left_coefficient * (
            10 ** (left_tuple.exponent - common_exponent)
        )
        result_coefficient = right_aligned - left_aligned
        if result_coefficient == 0:
            return Decimal("0")
        digits = _integer_digits(abs(result_coefficient))
        return Decimal((int(result_coefficient < 0), digits, common_exponent))
    except (MemoryError, OverflowError, ValueError, DecimalException) as caught:
        raise HistoricalExperimentPairwiseArithmeticError(
            f"cannot complete exact Decimal subtraction: {caught}"
        ) from caught


def _coefficient(digits: tuple[int, ...]) -> int:
    result = 0
    for digit in digits:
        result = result * 10 + digit
    return result


def _integer_digits(value: int) -> tuple[int, ...]:
    digits = []
    while value:
        value, digit = divmod(value, 10)
        digits.append(digit)
    digits.reverse()
    return tuple(digits)


def _reconcile(report, policy, records) -> None:  # type: ignore[no-untyped-def]
    error = HistoricalExperimentPairwiseReconciliationError
    expected_pairs = _pair_rows(report.variants, policy)
    if len(records) != len(expected_pairs):
        raise error("pairwise record count differs from expected coverage")
    if tuple(item.ordinal for item in records) != tuple(range(len(records))):
        raise error("pairwise record ordinals must be sequential from zero")
    seen = set()
    fields = tuple(_METRIC_FIELDS[metric] for metric in policy.metrics)
    for ordinal, (record, (left, right)) in enumerate(
        zip(records, expected_pairs, strict=True)
    ):
        pair_key = frozenset((record.left_variant_id, record.right_variant_id))
        if len(pair_key) != 2 or pair_key in seen:
            raise error("pairwise records contain a self-pair or duplicate pair")
        seen.add(pair_key)
        if (
            record.ordinal != ordinal
            or record.left_caller_ordinal != left.caller_ordinal
            or record.right_caller_ordinal != right.caller_ordinal
            or record.left_variant_id != left.variant_id
            or record.right_variant_id != right.variant_id
        ):
            raise error(f"pairwise record {ordinal} orientation or identity differs")
        if tuple(item.metric for item in record.differences) != policy.metrics:
            raise error(f"pairwise record {ordinal} metric order differs from policy")
        for difference, field in zip(record.differences, fields, strict=True):
            left_value = getattr(left.metrics, field)
            right_value = getattr(right.metrics, field)
            if (
                difference.left_value != left_value
                or difference.right_value != right_value
                or difference.difference != _subtract(right_value, left_value)
            ):
                raise error(f"pairwise record {ordinal} values do not reconcile")


def _validate_retained_records(policy, records, error_type) -> None:  # type: ignore[no-untyped-def]
    if tuple(item.ordinal for item in records) != tuple(range(len(records))):
        raise error_type("record ordinals must be sequential from zero")
    seen = set()
    caller_to_variant = {}
    variant_to_caller = {}
    for record in records:
        for caller, variant in (
            (record.left_caller_ordinal, record.left_variant_id),
            (record.right_caller_ordinal, record.right_variant_id),
        ):
            if caller in caller_to_variant and caller_to_variant[caller] != variant:
                raise error_type("one caller ordinal maps to multiple variant IDs")
            if variant in variant_to_caller and variant_to_caller[variant] != caller:
                raise error_type("one variant ID maps to multiple caller ordinals")
            caller_to_variant[caller] = variant
            variant_to_caller[variant] = caller
        key = frozenset((record.left_variant_id, record.right_variant_id))
        if key in seen:
            raise error_type("records contain a duplicate unordered pair")
        seen.add(key)
        if tuple(item.metric for item in record.differences) != policy.metrics:
            raise error_type("record difference order must match policy metrics")
        if policy.pairing is HistoricalExperimentPairwisePairing.BASELINE_VERSUS_ALL:
            if record.left_variant_id != policy.baseline_variant_id:
                raise error_type("baseline must remain on the left")
        elif (
            policy.orientation is HistoricalExperimentPairwiseOrientation.CALLER_ORDER
            and record.left_caller_ordinal > record.right_caller_ordinal
        ):
            raise error_type("record violates caller-order orientation")
        elif (
            policy.orientation is HistoricalExperimentPairwiseOrientation.VARIANT_ID
            and record.left_variant_id.int > record.right_variant_id.int
        ):
            raise error_type("record violates variant-ID orientation")
    if caller_to_variant and set(caller_to_variant) != set(
        range(max(caller_to_variant) + 1)
    ):
        raise error_type("record caller ordinals do not form a sequential universe")
    if (
        policy.pairing is HistoricalExperimentPairwisePairing.ALL_UNORDERED_PAIRS
        and records
    ):
        expected = []
        for first, second in combinations(range(len(caller_to_variant)), 2):
            left, right = first, second
            if (
                policy.orientation is HistoricalExperimentPairwiseOrientation.VARIANT_ID
                and caller_to_variant[right].int < caller_to_variant[left].int
            ):
                left, right = right, left
            expected.append(
                (
                    left,
                    right,
                    caller_to_variant[left],
                    caller_to_variant[right],
                )
            )
        actual = [
            (
                item.left_caller_ordinal,
                item.right_caller_ordinal,
                item.left_variant_id,
                item.right_variant_id,
            )
            for item in records
        ]
        if actual != expected:
            raise error_type(
                "all-pairs records do not have canonical complete coverage"
            )
    elif policy.pairing is HistoricalExperimentPairwisePairing.BASELINE_VERSUS_ALL:
        rights = tuple(item.right_caller_ordinal for item in records)
        if rights != tuple(sorted(rights)) or len(set(rights)) != len(rights):
            raise error_type("baseline comparison rights must be unique caller ordered")


def _validated_metadata(values, error_type):  # type: ignore[no-untyped-def]
    try:
        metadata = tuple(item for item in values)
    except TypeError as caught:
        raise error_type("metadata must be iterable") from caught
    if not all(type(item) is MetadataEntry for item in metadata):
        raise error_type("metadata must contain exact MetadataEntry values")
    for item in metadata:
        try:
            item.__post_init__()
        except (TypeError, ValueError) as caught:
            raise error_type("metadata contains an invalid entry") from caught
    if len({item.key for item in metadata}) != len(metadata):
        raise error_type("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
        raise error_type(f"{_RESERVED_PREFIX} metadata keys are reserved")
    return metadata


def _report_invariant(report):  # type: ignore[no-untyped-def]
    return (
        report.report_id,
        tuple(
            (
                item.caller_ordinal,
                item.variant_id,
                tuple(
                    getattr(item.metrics, field) for field in _METRIC_FIELDS.values()
                ),
            )
            for item in report.variants
        ),
    )


def _policy_invariant(policy):  # type: ignore[no-untyped-def]
    return (
        policy.policy_id,
        policy.metrics,
        policy.pairing,
        policy.orientation,
        policy.baseline_variant_id,
        policy.metadata,
    )


def _result_id(source_report_id, policy, records) -> UUID:  # type: ignore[no-untyped-def]
    material = [
        _typed(source_report_id),
        _typed(policy.policy_id),
        *(_typed(metric) for metric in policy.metrics),
        _typed(policy.pairing),
        _typed(policy.orientation),
        _typed(policy.baseline_variant_id),
        *(
            value
            for item in policy.metadata
            for value in (_typed(item.key), _typed(item.value))
        ),
    ]
    for record in records:
        material.extend(
            (
                _typed(record.ordinal),
                _typed(record.left_caller_ordinal),
                _typed(record.right_caller_ordinal),
                _typed(record.left_variant_id),
                _typed(record.right_variant_id),
            )
        )
        for difference in record.differences:
            material.extend(
                (
                    _typed(difference.metric),
                    _typed(difference.left_value),
                    _typed(difference.right_value),
                    _typed(difference.difference),
                )
            )
    return uuid5(
        _NAMESPACE,
        "|".join((_VERSION, "pairwise-result", *material)),
    )


def _typed(value) -> str:  # type: ignore[no-untyped-def]
    if value is None:
        return "NULL|"
    if type(value) is int:
        return f"INTEGER|{value}"
    if type(value) is Decimal:
        return f"DECIMAL|{_canonical_decimal(value)}"
    if type(value) is UUID:
        return f"UUID|{value}"
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    if type(value) is str:
        return f"STRING|{value}"
    raise HistoricalExperimentPairwiseArithmeticError(
        "identity value has an unsupported type"
    )


def _canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise HistoricalExperimentPairwiseArithmeticError(
            "identity Decimal values must be finite"
        )
    try:
        with localcontext(
            Context(
                prec=max(len(value.as_tuple().digits), 1),
                Emax=MAX_EMAX,
                Emin=MIN_EMIN,
            )
        ):
            return canonical_decimal(value)
    except (MemoryError, OverflowError, ValueError, DecimalException) as caught:
        raise HistoricalExperimentPairwiseArithmeticError(
            f"cannot canonicalize Decimal identity value: {caught}"
        ) from caught
