"""Compact deterministic projections of completed historical experiments."""

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from enum import Enum, StrEnum
from uuid import UUID, uuid5

from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments.comparison import (
    HistoricalExperimentComparisonResult,
    HistoricalExperimentRankingCriterion,
    HistoricalExperimentRankingPolicy,
    HistoricalExperimentTieBreaker,
)
from trading_bot.experiments.exceptions import (
    HistoricalExperimentReportGridError,
    HistoricalExperimentReportMetricError,
    HistoricalExperimentReportRankingError,
    HistoricalExperimentReportReconciliationError,
    InconsistentHistoricalExperimentReportError,
    InvalidHistoricalExperimentReportInputError,
)
from trading_bot.experiments.grid import (
    HistoricalExperimentGridAssignment,
    HistoricalExperimentGridResult,
    HistoricalExperimentGridSpecification,
)
from trading_bot.experiments.historical import (
    HistoricalExperimentMetrics,
    HistoricalExperimentRequest,
    HistoricalExperimentResult,
    HistoricalExperimentRun,
    HistoricalExperimentVariant,
)
from trading_bot.portfolio import MetadataEntry

_VERSION = "historical-experiment-report-v1"
_NAMESPACE = UUID("684b5f35-f9af-553b-8063-46de18e7f60a")
_RESERVED_PREFIX = "historical_experiment_report_"

_METRIC_FIELDS = (
    "initial_equity",
    "final_equity",
    "absolute_simulation_profit_loss",
    "simulation_return",
    "maximum_drawdown_amount",
    "maximum_drawdown_percentage",
    "simulation_realized_profit_loss",
    "total_commissions",
    "adverse_slippage_cost",
    "total_execution_cost",
    "aggregate_one_way_turnover",
    "aggregate_two_way_turnover",
    "maximum_allocation_drift",
    "total_orders",
    "total_fills",
    "approved_decisions",
    "resized_decisions",
    "rejected_decisions",
    "rejected_notional",
    "reduced_notional",
    "mean_expected_portfolio_return",
    "worst_cvar",
    "minimum_target_cash_weight",
    "maximum_target_cash_weight",
    "applied_cycle_count",
    "no_action_cycle_count",
)
_INTEGER_METRIC_FIELDS = frozenset(
    {
        "total_orders",
        "total_fills",
        "approved_decisions",
        "resized_decisions",
        "rejected_decisions",
        "applied_cycle_count",
        "no_action_cycle_count",
    }
)


class HistoricalExperimentReportVariantSource(StrEnum):
    EXPLICIT = "EXPLICIT"
    GRID = "GRID"


@dataclass(frozen=True, slots=True)
class HistoricalExperimentReportVariant:
    caller_ordinal: int
    experiment_run_id: UUID
    rolling_result_id: UUID
    variant_id: UUID
    variant_name: str
    grid_ordinal: int | None
    grid_assignments: tuple[HistoricalExperimentGridAssignment, ...]
    rank: int | None
    comparison_values: tuple[Decimal | int, ...]
    metrics: HistoricalExperimentMetrics

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentReportError
        if type(self.caller_ordinal) is not int or self.caller_ordinal < 0:
            raise error("caller_ordinal must be a nonnegative integer")
        for name in ("experiment_run_id", "rolling_result_id", "variant_id"):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be a UUID")
        if not isinstance(self.variant_name, str) or not self.variant_name.strip():
            raise error("variant_name must be nonblank")
        if self.grid_ordinal is not None and (
            type(self.grid_ordinal) is not int or self.grid_ordinal < 0
        ):
            raise error("grid_ordinal must be a nonnegative integer or None")
        if self.rank is not None and (type(self.rank) is not int or self.rank <= 0):
            raise error("rank must be a positive integer or None")
        try:
            assignments = tuple(item for item in self.grid_assignments)
            values = tuple(item for item in self.comparison_values)
        except TypeError as caught:
            raise error(
                "assignments and comparison values must be iterable"
            ) from caught
        if not all(
            type(item) is HistoricalExperimentGridAssignment for item in assignments
        ):
            raise error("grid_assignments contain an invalid value")
        for item in assignments:
            try:
                item.__post_init__()
            except (TypeError, ValueError) as caught:
                raise error("grid_assignments contain an invalid value") from caught
        _validate_comparison_values(values, error)
        _validate_metrics(self.metrics, error)
        object.__setattr__(self, "variant_name", self.variant_name.strip())
        object.__setattr__(self, "grid_assignments", assignments)
        object.__setattr__(self, "comparison_values", values)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentReportRanking:
    policy_id: UUID
    policy_fingerprint: UUID
    comparison_result_id: UUID
    criteria: tuple[HistoricalExperimentRankingCriterion, ...]
    tie_breaker: HistoricalExperimentTieBreaker

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentReportError
        for name in ("policy_id", "policy_fingerprint", "comparison_result_id"):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be a UUID")
        try:
            criteria = tuple(item for item in self.criteria)
        except TypeError as caught:
            raise error("ranking criteria must be iterable") from caught
        if not criteria or not all(
            type(item) is HistoricalExperimentRankingCriterion for item in criteria
        ):
            raise error("ranking criteria contain an invalid value")
        for criterion in criteria:
            try:
                criterion.__post_init__()
            except (TypeError, ValueError) as caught:
                raise error("ranking criteria contain an invalid value") from caught
        if len({item.metric for item in criteria}) != len(criteria):
            raise error("ranking criterion metrics must be unique")
        if type(self.tie_breaker) is not HistoricalExperimentTieBreaker:
            raise error("ranking tie_breaker has an invalid type")
        object.__setattr__(self, "criteria", criteria)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentReport:
    report_id: UUID
    experiment_request_id: UUID
    experiment_result_id: UUID
    historical_fingerprint: UUID
    schedule_fingerprint: UUID
    initial_state_fingerprint: UUID
    variant_source: HistoricalExperimentReportVariantSource
    grid_specification_id: UUID | None
    grid_result_id: UUID | None
    ranking: HistoricalExperimentReportRanking | None
    variants: tuple[HistoricalExperimentReportVariant, ...]
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentReportError
        for name in (
            "report_id",
            "experiment_request_id",
            "experiment_result_id",
            "historical_fingerprint",
            "schedule_fingerprint",
            "initial_state_fingerprint",
        ):
            if type(getattr(self, name)) is not UUID:
                raise error(f"{name} must be a UUID")
        if type(self.variant_source) is not HistoricalExperimentReportVariantSource:
            raise error("variant_source has an invalid type")
        for name in ("grid_specification_id", "grid_result_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not UUID:
                raise error(f"{name} must be a UUID or None")
        if (
            self.ranking is not None
            and type(self.ranking) is not HistoricalExperimentReportRanking
        ):
            raise error("ranking has an invalid type")
        if self.ranking is not None:
            self.ranking.__post_init__()
        try:
            variants = tuple(item for item in self.variants)
        except TypeError as caught:
            raise error("variants must be iterable") from caught
        if not variants or not all(
            type(item) is HistoricalExperimentReportVariant for item in variants
        ):
            raise error("variants must contain compact report rows")
        for variant in variants:
            variant.__post_init__()
        metadata = _validated_metadata(self.metadata, error)
        _validate_retained_relationships(
            self.variant_source,
            self.grid_specification_id,
            self.grid_result_id,
            self.ranking,
            variants,
            error,
        )
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "metadata", metadata)
        expected = _report_id_from_fields(
            self.experiment_request_id,
            self.experiment_result_id,
            self.historical_fingerprint,
            self.schedule_fingerprint,
            self.initial_state_fingerprint,
            self.variant_source,
            self.grid_specification_id,
            self.grid_result_id,
            self.ranking,
            variants,
            metadata,
        )
        if self.report_id != expected:
            raise error("report_id is inconsistent")


class HistoricalExperimentReportBuilder:
    """Project one completed immutable experiment into a compact report."""

    def build(
        self,
        experiment_result: HistoricalExperimentResult,
        *,
        grid_result: HistoricalExperimentGridResult | None = None,
        comparison_result: HistoricalExperimentComparisonResult | None = None,
        metadata: tuple[MetadataEntry, ...] = (),
    ) -> HistoricalExperimentReport:
        _validate_experiment(experiment_result)
        if (
            grid_result is not None
            and type(grid_result) is not HistoricalExperimentGridResult
        ):
            raise InvalidHistoricalExperimentReportInputError(
                "grid_result must be exactly HistoricalExperimentGridResult or None"
            )
        if (
            comparison_result is not None
            and type(comparison_result) is not HistoricalExperimentComparisonResult
        ):
            raise InvalidHistoricalExperimentReportInputError(
                "comparison_result must be exactly "
                "HistoricalExperimentComparisonResult or None"
            )
        report_metadata = _validated_metadata(
            metadata, InvalidHistoricalExperimentReportInputError
        )
        before = _source_invariant(experiment_result, grid_result, comparison_result)
        grid_rows = _grid_rows(experiment_result, grid_result)
        ranking, ranked = _ranking_rows(experiment_result, comparison_result)
        rows = tuple(
            HistoricalExperimentReportVariant(
                run.ordinal,
                run.run_id,
                run.rolling_result.result_id,
                run.variant.variant_id,
                run.variant.name,
                None if grid_rows is None else grid_rows[index].ordinal,
                () if grid_rows is None else grid_rows[index].assignments,
                None if ranked is None else ranked[id(run)].rank,
                () if ranked is None else ranked[id(run)].comparison_values,
                run.metrics,
            )
            for index, run in enumerate(experiment_result.runs)
        )
        if before != _source_invariant(
            experiment_result, grid_result, comparison_result
        ):
            raise HistoricalExperimentReportReconciliationError(
                "report source inputs changed during projection"
            )
        _reconcile_projection(experiment_result, grid_result, comparison_result, rows)
        source = (
            HistoricalExperimentReportVariantSource.EXPLICIT
            if grid_result is None
            else HistoricalExperimentReportVariantSource.GRID
        )
        report_id = _report_id_from_fields(
            experiment_result.request.request_id,
            experiment_result.result_id,
            experiment_result.historical_fingerprint,
            experiment_result.schedule_fingerprint,
            experiment_result.initial_state_fingerprint,
            source,
            None if grid_result is None else grid_result.specification.specification_id,
            None if grid_result is None else grid_result.result_id,
            ranking,
            rows,
            report_metadata,
        )
        return HistoricalExperimentReport(
            report_id,
            experiment_result.request.request_id,
            experiment_result.result_id,
            experiment_result.historical_fingerprint,
            experiment_result.schedule_fingerprint,
            experiment_result.initial_state_fingerprint,
            source,
            None if grid_result is None else grid_result.specification.specification_id,
            None if grid_result is None else grid_result.result_id,
            ranking,
            rows,
            report_metadata,
        )


def _validate_experiment(result) -> None:  # type: ignore[no-untyped-def]
    error = InvalidHistoricalExperimentReportInputError
    if type(result) is not HistoricalExperimentResult:
        raise error("experiment_result must be exactly HistoricalExperimentResult")
    for name in (
        "result_id",
        "historical_fingerprint",
        "schedule_fingerprint",
        "initial_state_fingerprint",
    ):
        if type(getattr(result, name, None)) is not UUID:
            raise error(f"experiment {name} must be a UUID")
    if type(result.request) is not HistoricalExperimentRequest:
        raise error("experiment request must be exactly HistoricalExperimentRequest")
    if type(result.request.request_id) is not UUID:
        raise error("experiment request_id must be a UUID")
    runs = result.runs
    if not runs or not all(type(item) is HistoricalExperimentRun for item in runs):
        raise error(
            "experiment runs must be nonempty exact HistoricalExperimentRun values"
        )
    if any(type(item.ordinal) is not int for item in runs) or tuple(
        item.ordinal for item in runs
    ) != tuple(range(len(runs))):
        raise error("experiment run ordinals must be sequential from zero")
    if len({item.run_id for item in runs}) != len(runs):
        raise error("experiment run IDs must be unique")
    if len({item.variant.variant_id for item in runs}) != len(runs):
        raise error("experiment variant IDs must be unique")
    if len(result.request.variants) != len(runs):
        raise error("experiment request variants and runs must have equal counts")
    for run, variant in zip(runs, result.request.variants, strict=True):
        if (
            type(run.variant) is not HistoricalExperimentVariant
            or run.variant is not variant
        ):
            raise error("run variants must retain exact request relationships")
        if type(run.variant.variant_id) is not UUID:
            raise error("run variant_id must be a UUID")
        if not isinstance(run.variant.name, str) or not run.variant.name.strip():
            raise error("run variant name must be nonblank")
        if type(run.run_id) is not UUID:
            raise error("experiment run_id must be a UUID")
        if type(getattr(run.rolling_result, "result_id", None)) is not UUID:
            raise error("rolling result_id must be a UUID")
        _validate_metrics(run.metrics, HistoricalExperimentReportMetricError)


def _grid_rows(
    experiment_result: HistoricalExperimentResult,
    grid_result: HistoricalExperimentGridResult | None,
):  # type: ignore[no-untyped-def]
    if grid_result is None:
        return None
    if type(grid_result.result_id) is not UUID:
        raise HistoricalExperimentReportGridError("grid result_id must be a UUID")
    if type(grid_result.specification) is not HistoricalExperimentGridSpecification:
        raise HistoricalExperimentReportGridError(
            "grid specification has an invalid type"
        )
    if type(grid_result.specification.specification_id) is not UUID:
        raise HistoricalExperimentReportGridError(
            "grid specification_id must be a UUID"
        )
    rows = grid_result.generated_variants
    runs = experiment_result.runs
    if len(rows) != len(runs):
        raise HistoricalExperimentReportGridError(
            "grid generated count differs from experiment run count"
        )
    for index, (generated, run) in enumerate(zip(rows, runs, strict=True)):
        if type(generated.ordinal) is not int:
            raise HistoricalExperimentReportGridError(
                "grid ordinal must be an exact integer"
            )
        if generated.ordinal != index:
            raise HistoricalExperimentReportGridError(
                "grid ordinals must be sequential from zero"
            )
        if generated.variant is not run.variant:
            raise HistoricalExperimentReportGridError(
                f"grid variant {index} is not the exact experiment variant"
            )
        if (
            generated.variant.variant_id != run.variant.variant_id
            or generated.variant.name != run.variant.name
        ):
            raise HistoricalExperimentReportGridError(
                f"grid variant {index} identity or name differs from experiment"
            )
        try:
            assignments = tuple(generated.assignments)
        except TypeError as caught:
            raise HistoricalExperimentReportGridError(
                f"grid variant {index} assignments must be iterable"
            ) from caught
        if not assignments or not all(
            type(item) is HistoricalExperimentGridAssignment for item in assignments
        ):
            raise HistoricalExperimentReportGridError(
                f"grid variant {index} assignments are invalid"
            )
        for assignment in assignments:
            try:
                assignment.__post_init__()
            except (TypeError, ValueError) as caught:
                raise HistoricalExperimentReportGridError(
                    f"grid variant {index} assignment is invalid"
                ) from caught
    return rows


def _ranking_rows(
    experiment_result: HistoricalExperimentResult,
    comparison_result: HistoricalExperimentComparisonResult | None,
):  # type: ignore[no-untyped-def]
    if comparison_result is None:
        return None, None
    if comparison_result.experiment_result is not experiment_result:
        raise HistoricalExperimentReportRankingError(
            "comparison does not retain the exact experiment result"
        )
    policy = comparison_result.policy
    if type(policy) is not HistoricalExperimentRankingPolicy:
        raise HistoricalExperimentReportRankingError(
            "ranking policy has an invalid type"
        )
    if type(policy.policy_id) is not UUID:
        raise HistoricalExperimentReportRankingError("ranking policy_id must be a UUID")
    if (
        type(comparison_result.policy_fingerprint) is not UUID
        or type(comparison_result.result_id) is not UUID
    ):
        raise HistoricalExperimentReportRankingError(
            "ranking fingerprints and result IDs must be UUIDs"
        )
    criteria = tuple(policy.criteria)
    ranking = HistoricalExperimentReportRanking(
        policy.policy_id,
        comparison_result.policy_fingerprint,
        comparison_result.result_id,
        criteria,
        policy.tie_breaker,
    )
    lookup = {}
    source_ids = {id(run) for run in experiment_result.runs}
    for item in comparison_result.ranked_runs:
        if type(item.rank) is not int or item.rank <= 0:
            raise HistoricalExperimentReportRankingError(
                "comparison rank must be a positive integer"
            )
        key = id(item.run)
        if key in lookup:
            raise HistoricalExperimentReportRankingError(
                "comparison contains a duplicate source run"
            )
        if key not in source_ids:
            raise HistoricalExperimentReportRankingError(
                "comparison contains a foreign source run"
            )
        if item.caller_ordinal != item.run.ordinal:
            raise HistoricalExperimentReportRankingError(
                "ranked caller ordinal differs from source run"
            )
        if len(item.comparison_values) != len(criteria):
            raise HistoricalExperimentReportMetricError(
                "comparison value count differs from ranking criteria"
            )
        _validate_comparison_values(
            item.comparison_values, HistoricalExperimentReportMetricError
        )
        lookup[key] = item
    if set(lookup) != source_ids:
        raise HistoricalExperimentReportRankingError(
            "comparison does not exactly cover experiment runs"
        )
    ranks = tuple(item.rank for item in comparison_result.ranked_runs)
    if set(ranks) != set(range(1, len(ranks) + 1)):
        raise HistoricalExperimentReportRankingError(
            "comparison ranks must be unique and sequential"
        )
    return ranking, lookup


def _reconcile_projection(
    experiment_result,
    grid_result,
    comparison_result,
    rows,
) -> None:  # type: ignore[no-untyped-def]
    if len(rows) != len(experiment_result.runs):
        raise HistoricalExperimentReportReconciliationError(
            "report row count differs from experiment runs"
        )
    generated = None if grid_result is None else grid_result.generated_variants
    ranked = (
        None
        if comparison_result is None
        else {id(item.run): item for item in comparison_result.ranked_runs}
    )
    for index, (row, run) in enumerate(zip(rows, experiment_result.runs, strict=True)):
        if (
            row.caller_ordinal != index
            or row.experiment_run_id != run.run_id
            or row.rolling_result_id != run.rolling_result.result_id
            or row.variant_id != run.variant.variant_id
            or row.variant_name != run.variant.name
            or row.metrics is not run.metrics
        ):
            raise HistoricalExperimentReportReconciliationError(
                f"report row {index} differs from its experiment source"
            )
        if generated is None:
            if row.grid_ordinal is not None or row.grid_assignments:
                raise HistoricalExperimentReportReconciliationError(
                    "explicit report row contains grid provenance"
                )
        elif (
            row.grid_ordinal != generated[index].ordinal
            or row.grid_assignments != generated[index].assignments
        ):
            raise HistoricalExperimentReportReconciliationError(
                f"report row {index} differs from grid provenance"
            )
        if ranked is None:
            if row.rank is not None or row.comparison_values:
                raise HistoricalExperimentReportReconciliationError(
                    "unranked report row contains ranking provenance"
                )
        else:
            source = ranked[id(run)]
            if (
                row.rank != source.rank
                or row.comparison_values != source.comparison_values
            ):
                raise HistoricalExperimentReportReconciliationError(
                    f"report row {index} differs from ranking provenance"
                )


def _validate_retained_relationships(
    source,
    grid_specification_id,
    grid_result_id,
    ranking,
    variants,
    error_type,
) -> None:  # type: ignore[no-untyped-def]
    if tuple(item.caller_ordinal for item in variants) != tuple(range(len(variants))):
        raise error_type("report row ordinals must be sequential from zero")
    if len({item.experiment_run_id for item in variants}) != len(variants):
        raise error_type("report run IDs must be unique")
    if len({item.variant_id for item in variants}) != len(variants):
        raise error_type("report variant IDs must be unique")
    if source is HistoricalExperimentReportVariantSource.EXPLICIT:
        if grid_specification_id is not None or grid_result_id is not None:
            raise error_type("explicit reports cannot contain grid IDs")
        if any(
            item.grid_ordinal is not None or item.grid_assignments for item in variants
        ):
            raise error_type("explicit report rows cannot contain grid provenance")
    else:
        if type(grid_specification_id) is not UUID or type(grid_result_id) is not UUID:
            raise error_type("grid reports require specification and result UUIDs")
        if tuple(item.grid_ordinal for item in variants) != tuple(range(len(variants))):
            raise error_type("grid ordinals must be sequential from zero")
        if any(not item.grid_assignments for item in variants):
            raise error_type("grid report rows require assignments")
    if ranking is None:
        if any(item.rank is not None or item.comparison_values for item in variants):
            raise error_type("unranked report rows cannot contain ranking provenance")
    else:
        ranks = tuple(item.rank for item in variants)
        if set(ranks) != set(range(1, len(variants) + 1)):
            raise error_type("report ranks must be unique and sequential")
        if any(
            len(item.comparison_values) != len(ranking.criteria) for item in variants
        ):
            raise error_type("comparison values must match ranking criteria")


def _validate_metrics(metrics, error_type) -> None:  # type: ignore[no-untyped-def]
    if type(metrics) is not HistoricalExperimentMetrics:
        raise error_type("metrics must be exactly HistoricalExperimentMetrics")
    for name in _METRIC_FIELDS:
        value = getattr(metrics, name)
        if name in _INTEGER_METRIC_FIELDS:
            if type(value) is not int:
                raise error_type(f"metric {name} must be an exact integer")
            if value < 0:
                raise error_type(f"metric {name} must be nonnegative")
        else:
            if type(value) is not Decimal or not value.is_finite():
                raise error_type(f"metric {name} must be a finite exact Decimal")


def _validate_comparison_values(values, error_type) -> None:  # type: ignore[no-untyped-def]
    for value in values:
        if type(value) is Decimal:
            if not value.is_finite():
                raise error_type("comparison Decimal values must be finite")
        elif type(value) is int:
            if value < 0:
                raise error_type("comparison integer values must be nonnegative")
        else:
            raise error_type("comparison values must be exact Decimal or integer")


def _validated_metadata(values, error_type):  # type: ignore[no-untyped-def]
    try:
        metadata = tuple(item for item in values)
    except TypeError as caught:
        raise error_type("metadata must be iterable") from caught
    if not all(type(item) is MetadataEntry for item in metadata):
        raise error_type("metadata must contain exact MetadataEntry values")
    if len({item.key for item in metadata}) != len(metadata):
        raise error_type("metadata keys must be unique")
    if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
        raise error_type(f"{_RESERVED_PREFIX} metadata keys are reserved")
    return metadata


def _source_invariant(experiment, grid, comparison):  # type: ignore[no-untyped-def]
    return (
        experiment.result_id,
        experiment.request.request_id,
        experiment.historical_fingerprint,
        experiment.schedule_fingerprint,
        experiment.initial_state_fingerprint,
        tuple(
            (
                id(run),
                run.ordinal,
                run.run_id,
                run.rolling_result.result_id,
                id(run.variant),
                run.variant.variant_id,
                run.variant.name,
                id(run.metrics),
                _metric_material(run.metrics),
            )
            for run in experiment.runs
        ),
        None
        if grid is None
        else (
            grid.result_id,
            grid.specification.specification_id,
            tuple(
                (
                    item.ordinal,
                    id(item.variant),
                    item.variant.variant_id,
                    item.variant.name,
                    item.assignments,
                )
                for item in grid.generated_variants
            ),
        ),
        None
        if comparison is None
        else (
            comparison.result_id,
            comparison.policy.policy_id,
            comparison.policy_fingerprint,
            comparison.policy.criteria,
            comparison.policy.tie_breaker,
            tuple(
                (
                    item.rank,
                    item.caller_ordinal,
                    id(item.run),
                    item.comparison_values,
                )
                for item in comparison.ranked_runs
            ),
        ),
    )


def _report_id_from_fields(
    experiment_request_id: UUID,
    experiment_result_id: UUID,
    historical_fingerprint: UUID,
    schedule_fingerprint: UUID,
    initial_state_fingerprint: UUID,
    variant_source: HistoricalExperimentReportVariantSource,
    grid_specification_id: UUID | None,
    grid_result_id: UUID | None,
    ranking: HistoricalExperimentReportRanking | None,
    variants: tuple[HistoricalExperimentReportVariant, ...],
    metadata: tuple[MetadataEntry, ...],
) -> UUID:
    material = [
        _typed(experiment_request_id),
        _typed(experiment_result_id),
        _typed(historical_fingerprint),
        _typed(schedule_fingerprint),
        _typed(initial_state_fingerprint),
        _typed(variant_source),
        _typed(grid_specification_id),
        _typed(grid_result_id),
    ]
    if ranking is None:
        material.extend((_typed(None), _typed(None), _typed(None), _typed(None)))
    else:
        material.extend(
            (
                _typed(ranking.policy_id),
                _typed(ranking.policy_fingerprint),
                _typed(ranking.comparison_result_id),
            )
        )
        for criterion in ranking.criteria:
            material.extend((_typed(criterion.metric), _typed(criterion.direction)))
        material.append(_typed(ranking.tie_breaker))
    for row in variants:
        material.extend(
            (
                _typed(row.caller_ordinal),
                _typed(row.experiment_run_id),
                _typed(row.rolling_result_id),
                _typed(row.variant_id),
                _typed(row.variant_name),
                _typed(row.grid_ordinal),
            )
        )
        for assignment in row.grid_assignments:
            material.extend((_typed(assignment.parameter), _typed(assignment.value)))
        material.append(_typed(row.rank))
        material.extend(_typed(value) for value in row.comparison_values)
        material.extend(_metric_material(row.metrics))
    material.extend(
        value for item in metadata for value in (_typed(item.key), _typed(item.value))
    )
    return uuid5(_NAMESPACE, "|".join((_VERSION, "report", *material)))


def _metric_material(metrics: HistoricalExperimentMetrics) -> tuple[str, ...]:
    return tuple(
        material
        for name in _METRIC_FIELDS
        for material in (_typed(name), _typed(getattr(metrics, name)))
    )


def _typed(value) -> str:  # type: ignore[no-untyped-def]
    if value is None:
        return "NULL|"
    if type(value) is bool:
        return f"BOOLEAN|{'true' if value else 'false'}"
    if type(value) is int:
        return f"INTEGER|{value}"
    if type(value) is Decimal:
        if not value.is_finite():
            raise HistoricalExperimentReportMetricError(
                "identity Decimal values must be finite"
            )
        return f"DECIMAL|{_canonical_decimal(value)}"
    if type(value) is UUID:
        return f"UUID|{value}"
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    if type(value) is str:
        return f"STRING|{value}"
    raise HistoricalExperimentReportMetricError(
        "identity value has an unsupported type"
    )


def _canonical_decimal(value: Decimal) -> str:
    digits = len(value.as_tuple().digits)
    with localcontext(
        Context(prec=max(digits, 1), Emax=999_999_999, Emin=-999_999_999)
    ):
        return canonical_decimal(value)
