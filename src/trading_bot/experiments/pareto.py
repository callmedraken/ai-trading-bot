"""Deterministic Pareto analysis of compact historical experiment reports."""

from dataclasses import dataclass, fields
from decimal import MAX_EMAX, MIN_EMIN, Context, Decimal, DecimalException, localcontext
from enum import Enum
from itertools import combinations
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments.comparison import (
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
)
from trading_bot.experiments.exceptions import (
    HistoricalExperimentParetoMetricError,
    HistoricalExperimentParetoReconciliationError,
    HistoricalExperimentParetoReportError,
    InconsistentHistoricalExperimentParetoResultError,
    InvalidHistoricalExperimentParetoPolicyError,
)
from trading_bot.experiments.historical import HistoricalExperimentMetrics
from trading_bot.experiments.report import (
    HistoricalExperimentReport,
    HistoricalExperimentReportVariant,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-pareto-v1"
_NAMESPACE = UUID("a28762c1-2fbf-5458-b3d8-1ab16e6ac8e5")
_RESERVED_PREFIX = "historical_experiment_pareto_"

_METRIC_FIELDS = MappingProxyType(
    {
        metric: field.name
        for metric, field in zip(
            HistoricalExperimentRankingMetric,
            fields(HistoricalExperimentMetrics),
            strict=True,
        )
    }
)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentParetoObjective:
    metric: HistoricalExperimentRankingMetric
    direction: HistoricalExperimentRankingDirection

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentParetoPolicyError
        if type(self.metric) is not HistoricalExperimentRankingMetric:
            raise error("objective metric has an invalid type")
        if type(self.direction) is not HistoricalExperimentRankingDirection:
            raise error("objective direction has an invalid type")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentParetoPolicy:
    policy_id: UUID
    objectives: tuple[HistoricalExperimentParetoObjective, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentParetoPolicyError
        if type(self.policy_id) is not UUID:
            raise error("policy_id must be an exact UUID")
        objectives = _tuple(self.objectives, "objectives", error)
        if not objectives or not all(
            type(item) is HistoricalExperimentParetoObjective for item in objectives
        ):
            raise error("objectives must contain exact Pareto objectives")
        for objective in objectives:
            objective.__post_init__()
        if len({item.metric for item in objectives}) != len(objectives):
            raise error("objective metrics must be unique")
        metadata = _tuple(self.metadata, "metadata", error)
        if not all(type(item) is MetadataEntry for item in metadata):
            raise error("metadata must contain exact MetadataEntry values")
        for item in metadata:
            try:
                item.__post_init__()
            except (TypeError, ValueError) as caught:
                raise error("metadata contains an invalid entry") from caught
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
        object.__setattr__(self, "objectives", objectives)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentParetoObjectiveComparison:
    objective: HistoricalExperimentParetoObjective
    dominator_value: Decimal | int
    dominated_value: Decimal | int
    strictly_better: bool

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentParetoResultError
        if type(self.objective) is not HistoricalExperimentParetoObjective:
            raise error("comparison objective has an invalid type")
        self.objective.__post_init__()
        _validate_pair(self.dominator_value, self.dominated_value, error)
        if type(self.strictly_better) is not bool:
            raise error("strictly_better must be an exact bool")
        no_worse, strict = _compare(
            self.dominator_value, self.dominated_value, self.objective.direction
        )
        if not no_worse or strict != self.strictly_better:
            raise error("objective comparison is directionally inconsistent")


@dataclass(frozen=True, slots=True)
class HistoricalExperimentParetoDominance:
    dominator_caller_ordinal: int
    dominated_caller_ordinal: int
    dominator_variant_id: UUID
    dominated_variant_id: UUID
    objective_values: tuple[HistoricalExperimentParetoObjectiveComparison, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentParetoResultError
        _ordinal(self.dominator_caller_ordinal, "dominator_caller_ordinal", error)
        _ordinal(self.dominated_caller_ordinal, "dominated_caller_ordinal", error)
        if self.dominator_caller_ordinal == self.dominated_caller_ordinal:
            raise error("dominance caller ordinals must be distinct")
        if (
            type(self.dominator_variant_id) is not UUID
            or type(self.dominated_variant_id) is not UUID
        ):
            raise error("dominance variant IDs must be exact UUIDs")
        if self.dominator_variant_id == self.dominated_variant_id:
            raise error("dominance variant IDs must be distinct")
        values = _tuple(self.objective_values, "objective_values", error)
        if not values or not all(
            type(item) is HistoricalExperimentParetoObjectiveComparison
            for item in values
        ):
            raise error("objective_values must contain exact comparisons")
        for item in values:
            item.__post_init__()
        if not any(item.strictly_better for item in values):
            raise error("dominance requires at least one strictly better objective")
        object.__setattr__(self, "objective_values", values)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentParetoVariant:
    caller_ordinal: int
    variant_id: UUID
    is_nondominated: bool
    dominated_by_variant_ids: tuple[UUID, ...]
    dominates_variant_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentParetoResultError
        _ordinal(self.caller_ordinal, "caller_ordinal", error)
        if type(self.variant_id) is not UUID:
            raise error("variant_id must be an exact UUID")
        if type(self.is_nondominated) is not bool:
            raise error("is_nondominated must be an exact bool")
        dominated_by = _uuid_tuple(
            self.dominated_by_variant_ids, "dominated_by_variant_ids", self.variant_id
        )
        dominates = _uuid_tuple(
            self.dominates_variant_ids, "dominates_variant_ids", self.variant_id
        )
        if self.is_nondominated != (not dominated_by):
            raise error("nondominated flag disagrees with dominated-by relationships")
        object.__setattr__(self, "dominated_by_variant_ids", dominated_by)
        object.__setattr__(self, "dominates_variant_ids", dominates)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentParetoResult:
    result_id: UUID
    source_report_id: UUID
    policy: HistoricalExperimentParetoPolicy
    frontier_variant_ids: tuple[UUID, ...]
    variants: tuple[HistoricalExperimentParetoVariant, ...]
    dominance_records: tuple[HistoricalExperimentParetoDominance, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentParetoResultError
        if type(self.result_id) is not UUID or type(self.source_report_id) is not UUID:
            raise error("result and source report IDs must be exact UUIDs")
        if type(self.policy) is not HistoricalExperimentParetoPolicy:
            raise error("policy must be exactly HistoricalExperimentParetoPolicy")
        try:
            self.policy.__post_init__()
        except InvalidHistoricalExperimentParetoPolicyError as caught:
            raise error(f"retained policy is invalid: {caught}") from caught
        frontier = _uuid_tuple(self.frontier_variant_ids, "frontier_variant_ids", None)
        variants = _tuple(self.variants, "variants", error)
        records = _tuple(self.dominance_records, "dominance_records", error)
        if not variants or not all(
            type(item) is HistoricalExperimentParetoVariant for item in variants
        ):
            raise error("variants must contain exact Pareto variants")
        if not all(
            type(item) is HistoricalExperimentParetoDominance for item in records
        ):
            raise error("dominance_records contain an invalid value")
        for item in (*variants, *records):
            item.__post_init__()
        _reconcile_result(self.policy, frontier, variants, records, error)
        object.__setattr__(self, "frontier_variant_ids", frontier)
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "dominance_records", records)
        if self.result_id != _result_id(
            self.source_report_id, self.policy, frontier, variants, records
        ):
            raise error("result_id is inconsistent")


class HistoricalExperimentParetoAnalyzer:
    """Analyze exact Pareto dominance over one completed compact report."""

    def analyze(
        self,
        report: HistoricalExperimentReport,
        policy: HistoricalExperimentParetoPolicy,
    ) -> HistoricalExperimentParetoResult:
        rows = _validate_report(report)
        if type(policy) is not HistoricalExperimentParetoPolicy:
            raise InvalidHistoricalExperimentParetoPolicyError(
                "policy must be exactly HistoricalExperimentParetoPolicy"
            )
        policy.__post_init__()
        report_before = _report_invariant(report, policy)
        policy_before = (policy.policy_id, policy.objectives, policy.metadata)
        vectors = tuple(_vector(row, policy) for row in rows)
        evaluated = []
        records = []
        dominated_by = [[] for _ in rows]
        dominates = [[] for _ in rows]
        for left, right in combinations(range(len(rows)), 2):
            evaluated.append((left, right))
            relation = _dominance(vectors[left], vectors[right], policy)
            if relation == 0:
                continue
            dominator, dominated = (left, right) if relation == 1 else (right, left)
            evidence = _evidence(vectors[dominator], vectors[dominated], policy)
            records.append(
                HistoricalExperimentParetoDominance(
                    dominator,
                    dominated,
                    rows[dominator].variant_id,
                    rows[dominated].variant_id,
                    evidence,
                )
            )
            dominates[dominator].append(dominated)
            dominated_by[dominated].append(dominator)
        expected = list(combinations(range(len(rows)), 2))
        if evaluated != expected:
            raise HistoricalExperimentParetoReconciliationError(
                "unordered pair coverage is inconsistent"
            )
        summaries = tuple(
            HistoricalExperimentParetoVariant(
                index,
                row.variant_id,
                not dominated_by[index],
                tuple(rows[item].variant_id for item in dominated_by[index]),
                tuple(rows[item].variant_id for item in dominates[index]),
            )
            for index, row in enumerate(rows)
        )
        frontier = tuple(item.variant_id for item in summaries if item.is_nondominated)
        records_tuple = tuple(records)
        _reconcile_result(
            policy,
            frontier,
            summaries,
            records_tuple,
            HistoricalExperimentParetoReconciliationError,
        )
        if report_before != _report_invariant(report, policy) or policy_before != (
            policy.policy_id,
            policy.objectives,
            policy.metadata,
        ):
            raise HistoricalExperimentParetoReconciliationError(
                "source report or policy changed during analysis"
            )
        result_id = _result_id(
            report.report_id, policy, frontier, summaries, records_tuple
        )
        return HistoricalExperimentParetoResult(
            result_id,
            report.report_id,
            policy,
            frontier,
            summaries,
            records_tuple,
        )


def _validate_report(
    report: HistoricalExperimentReport,
) -> tuple[HistoricalExperimentReportVariant, ...]:
    if type(report) is not HistoricalExperimentReport:
        raise HistoricalExperimentParetoReportError(
            "report must be exactly HistoricalExperimentReport"
        )
    try:
        rows = tuple(report.variants)
    except TypeError as caught:
        raise HistoricalExperimentParetoReportError(
            "report variants are not iterable"
        ) from caught
    if not rows or not all(
        type(row) is HistoricalExperimentReportVariant for row in rows
    ):
        raise HistoricalExperimentParetoReportError("report variants are malformed")
    if tuple(row.caller_ordinal for row in rows) != tuple(range(len(rows))):
        raise HistoricalExperimentParetoReportError(
            "caller ordinals must be sequential"
        )
    if len({row.variant_id for row in rows}) != len(rows):
        raise HistoricalExperimentParetoReportError("variant IDs must be unique")
    if not all(type(row.variant_id) is UUID for row in rows):
        raise HistoricalExperimentParetoReportError("variant IDs must be exact UUIDs")
    if not all(type(row.metrics) is HistoricalExperimentMetrics for row in rows):
        raise HistoricalExperimentParetoReportError("metrics must be exact models")
    return rows


def _vector(row, policy):  # type: ignore[no-untyped-def]
    values = []
    for objective in policy.objectives:
        field = _METRIC_FIELDS.get(objective.metric)
        if field is None:
            raise HistoricalExperimentParetoMetricError("unsupported objective metric")
        value = getattr(row.metrics, field, None)
        _validate_scalar(value, HistoricalExperimentParetoMetricError)
        values.append(value)
    return tuple(values)


def _dominance(left, right, policy):  # type: ignore[no-untyped-def]
    left_flags = tuple(
        _compare(a, b, objective.direction)
        for a, b, objective in zip(left, right, policy.objectives, strict=True)
    )
    right_flags = tuple(
        _compare(b, a, objective.direction)
        for a, b, objective in zip(left, right, policy.objectives, strict=True)
    )
    left_dominates = all(flag[0] for flag in left_flags) and any(
        flag[1] for flag in left_flags
    )
    right_dominates = all(flag[0] for flag in right_flags) and any(
        flag[1] for flag in right_flags
    )
    if left_dominates and right_dominates:
        raise HistoricalExperimentParetoReconciliationError(
            "both variants cannot dominate each other"
        )
    return 1 if left_dominates else -1 if right_dominates else 0


def _evidence(dominator, dominated, policy):  # type: ignore[no-untyped-def]
    return tuple(
        HistoricalExperimentParetoObjectiveComparison(
            objective,
            left,
            right,
            _compare(left, right, objective.direction)[1],
        )
        for left, right, objective in zip(
            dominator, dominated, policy.objectives, strict=True
        )
    )


def _compare(left, right, direction):  # type: ignore[no-untyped-def]
    _validate_pair(left, right, HistoricalExperimentParetoMetricError)
    if direction is HistoricalExperimentRankingDirection.ASCENDING:
        return left <= right, left < right
    return left >= right, left > right


def _validate_pair(left, right, error):  # type: ignore[no-untyped-def]
    _validate_scalar(left, error)
    _validate_scalar(right, error)
    if type(left) is not type(right):
        raise error("objective values must have the same exact scalar type")


def _validate_scalar(value, error):  # type: ignore[no-untyped-def]
    if type(value) is Decimal:
        if not value.is_finite():
            raise error("objective Decimal values must be finite")
    elif type(value) is not int:
        raise error("objective values must be exact Decimal or int")


def _reconcile_result(policy, frontier, variants, records, error):  # type: ignore[no-untyped-def]
    ids = tuple(item.variant_id for item in variants)
    if tuple(item.caller_ordinal for item in variants) != tuple(range(len(variants))):
        raise error("variant summaries must be in caller order")
    if len(set(ids)) != len(ids):
        raise error("variant summary IDs must be unique")
    expected_frontier = tuple(
        item.variant_id for item in variants if not item.dominated_by_variant_ids
    )
    if frontier != expected_frontier:
        raise error("frontier does not match nondominated variants")
    index = {value: ordinal for ordinal, value in enumerate(ids)}
    derived_by = [[] for _ in variants]
    derived_dominates = [[] for _ in variants]
    seen_pairs = set()
    last_pair = None
    for record in records:
        if (
            record.dominator_variant_id not in index
            or record.dominated_variant_id not in index
        ):
            raise error("dominance record references an unknown variant")
        dominator = index[record.dominator_variant_id]
        dominated = index[record.dominated_variant_id]
        if (dominator, dominated) != (
            record.dominator_caller_ordinal,
            record.dominated_caller_ordinal,
        ):
            raise error("dominance record ordinals disagree with variant IDs")
        pair = tuple(sorted((dominator, dominated)))
        if pair in seen_pairs or (last_pair is not None and pair <= last_pair):
            raise error("dominance records are not in unique source-pair order")
        seen_pairs.add(pair)
        last_pair = pair
        if (
            tuple(item.objective for item in record.objective_values)
            != policy.objectives
        ):
            raise error("objective evidence order disagrees with policy")
        derived_by[dominated].append(dominator)
        derived_dominates[dominator].append(dominated)
    for ordinal, item in enumerate(variants):
        if item.dominated_by_variant_ids != tuple(ids[i] for i in derived_by[ordinal]):
            raise error("dominated-by relationships disagree with records")
        if item.dominates_variant_ids != tuple(
            ids[i] for i in derived_dominates[ordinal]
        ):
            raise error("dominates relationships disagree with records")


def _result_id(source, policy, frontier, variants, records):  # type: ignore[no-untyped-def]
    material = [_typed(source), _typed(policy.policy_id)]
    for objective in policy.objectives:
        material.extend((_typed(objective.metric), _typed(objective.direction)))
    for item in policy.metadata:
        material.extend((_typed(item.key), _typed(item.value)))
    material.extend(_typed(item) for item in frontier)
    for item in variants:
        material.extend(
            (
                _typed(item.caller_ordinal),
                _typed(item.variant_id),
                _typed(item.is_nondominated),
                *(_typed(value) for value in item.dominated_by_variant_ids),
                *(_typed(value) for value in item.dominates_variant_ids),
            )
        )
    for record in records:
        material.extend(
            (
                _typed(record.dominator_caller_ordinal),
                _typed(record.dominated_caller_ordinal),
                _typed(record.dominator_variant_id),
                _typed(record.dominated_variant_id),
            )
        )
        for item in record.objective_values:
            material.extend(
                (
                    _typed(item.objective.metric),
                    _typed(item.objective.direction),
                    _typed(item.dominator_value),
                    _typed(item.dominated_value),
                    _typed(item.strictly_better),
                )
            )
    return uuid5(_NAMESPACE, "|".join((_VERSION, "pareto-result", *material)))


def _typed(value) -> str:  # type: ignore[no-untyped-def]
    if type(value) is Decimal:
        return f"DECIMAL|{_canonical_decimal(value)}"
    if type(value) is bool:
        return f"BOOLEAN|{str(value).lower()}"
    if type(value) is int:
        return f"INTEGER|{value}"
    if type(value) is UUID:
        return f"UUID|{value}"
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    if type(value) is str:
        return f"STRING|{value}"
    raise InconsistentHistoricalExperimentParetoResultError(
        "identity value has an unsupported type"
    )


def _canonical_decimal(value: Decimal) -> str:
    try:
        with localcontext(
            Context(
                prec=max(len(value.as_tuple().digits), 1),
                Emax=MAX_EMAX,
                Emin=MIN_EMIN,
            )
        ):
            return canonical_decimal(value)
    except (DecimalException, MemoryError, OverflowError, ValueError) as caught:
        raise InconsistentHistoricalExperimentParetoResultError(
            f"cannot canonicalize Decimal identity value: {caught}"
        ) from caught


def _tuple(values, name, error):  # type: ignore[no-untyped-def]
    try:
        return tuple(values)
    except TypeError as caught:
        raise error(f"{name} must be iterable") from caught


def _ordinal(value, name, error):  # type: ignore[no-untyped-def]
    if type(value) is not int or value < 0:
        raise error(f"{name} must be an exact nonnegative integer")


def _uuid_tuple(values, name, self_id):  # type: ignore[no-untyped-def]
    error = InconsistentHistoricalExperimentParetoResultError
    result = _tuple(values, name, error)
    if not all(type(item) is UUID for item in result):
        raise error(f"{name} must contain exact UUIDs")
    if len(set(result)) != len(result):
        raise error(f"{name} must contain unique UUIDs")
    if self_id is not None and self_id in result:
        raise error(f"{name} cannot contain the variant itself")
    return result


def _report_invariant(report, policy):  # type: ignore[no-untyped-def]
    return (
        report.report_id,
        tuple(
            (
                row.caller_ordinal,
                row.variant_id,
                tuple(
                    getattr(row.metrics, _METRIC_FIELDS[obj.metric])
                    for obj in policy.objectives
                ),
            )
            for row in report.variants
        ),
    )
