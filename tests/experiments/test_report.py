from copy import copy
from dataclasses import fields, replace
from decimal import Context, Decimal, localcontext
from uuid import UUID, uuid4

import pytest
from tests.experiments.test_comparison import _policy, _with_metrics
from tests.experiments.test_historical import _Factory, _request, _variant

from trading_bot.experiments import (
    HistoricalExperimentComparator,
    HistoricalExperimentGridAssignment,
    HistoricalExperimentGridAxis,
    HistoricalExperimentGridGenerator,
    HistoricalExperimentGridParameter,
    HistoricalExperimentGridSpecification,
    HistoricalExperimentMetrics,
    HistoricalExperimentRankingDirection,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentReportBuilder,
    HistoricalExperimentReportGridError,
    HistoricalExperimentReportMetricError,
    HistoricalExperimentReportRankingError,
    HistoricalExperimentReportVariantSource,
    HistoricalExperimentRunner,
    InconsistentHistoricalExperimentReportError,
    InvalidHistoricalExperimentReportInputError,
)
from trading_bot.experiments.report import _METRIC_FIELDS, _typed
from trading_bot.portfolio import MetadataEntry


def _explicit_result():
    return HistoricalExperimentRunner(_Factory()).run(_request())


def _grid_and_result():
    specification = HistoricalExperimentGridSpecification(
        UUID(int=901),
        _variant(900, name="base"),
        (
            HistoricalExperimentGridAxis(
                HistoricalExperimentGridParameter.RISK_AVERSION,
                (Decimal("1"), Decimal("2")),
            ),
        ),
        2,
    )
    grid = HistoricalExperimentGridGenerator().generate(specification)
    result = HistoricalExperimentRunner(_Factory()).run(
        _request(variants=tuple(item.variant for item in grid.generated_variants))
    )
    return grid, result


def _comparison(result):
    policy = _policy(
        (
            HistoricalExperimentRankingMetric.SIMULATION_RETURN,
            HistoricalExperimentRankingDirection.DESCENDING,
        )
    )
    return HistoricalExperimentComparator().compare(result, policy)


def _ranked_result():
    source = _explicit_result()
    ranked_source = _with_metrics(
        source,
        {"simulation_return": Decimal("0")},
        {"simulation_return": Decimal("1")},
    )
    return ranked_source, _comparison(ranked_source)


def test_explicit_projection_is_compact_caller_ordered_and_exact() -> None:
    source = _explicit_result()
    metadata = [MetadataEntry("owner", "research")]
    report = HistoricalExperimentReportBuilder().build(source, metadata=metadata)
    metadata.clear()

    assert report.variant_source is HistoricalExperimentReportVariantSource.EXPLICIT
    assert report.grid_specification_id is None
    assert report.grid_result_id is None
    assert report.ranking is None
    assert report.metadata == (MetadataEntry("owner", "research"),)
    assert tuple(row.caller_ordinal for row in report.variants) == (0, 1)
    for row, run in zip(report.variants, source.runs, strict=True):
        assert row.experiment_run_id == run.run_id
        assert row.rolling_result_id == run.rolling_result.result_id
        assert row.metrics is run.metrics
        assert row.grid_ordinal is None and row.grid_assignments == ()
        assert row.rank is None and row.comparison_values == ()
    assert not hasattr(report, "experiment_result")
    assert not hasattr(report.variants[0], "run")
    assert not hasattr(report.variants[0], "rolling_result")


def test_grid_provenance_is_positional_exact_and_defensively_copied() -> None:
    grid, result = _grid_and_result()
    report = HistoricalExperimentReportBuilder().build(result, grid_result=grid)

    assert report.variant_source is HistoricalExperimentReportVariantSource.GRID
    assert report.grid_specification_id == grid.specification.specification_id
    assert report.grid_result_id == grid.result_id
    for row, generated in zip(report.variants, grid.generated_variants, strict=True):
        assert row.grid_ordinal == generated.ordinal
        assert row.grid_assignments == generated.assignments
        assert row.grid_assignments is not generated.assignments


def test_ranking_is_projected_back_to_caller_order() -> None:
    result, comparison = _ranked_result()
    assert comparison.ranked_runs[0].caller_ordinal == 1

    report = HistoricalExperimentReportBuilder().build(
        result, comparison_result=comparison
    )

    assert tuple(row.caller_ordinal for row in report.variants) == (0, 1)
    assert tuple(row.rank for row in report.variants) == (2, 1)
    assert report.ranking is not None
    assert report.ranking.criteria == comparison.policy.criteria
    assert report.ranking.criteria is not comparison.policy.criteria
    by_ordinal = {item.caller_ordinal: item for item in comparison.ranked_runs}
    assert all(
        row.comparison_values == by_ordinal[row.caller_ordinal].comparison_values
        for row in report.variants
    )


@pytest.mark.parametrize(
    ("with_grid", "with_ranking"),
    ((False, False), (False, True), (True, False), (True, True)),
)
def test_all_provenance_combinations_are_supported(
    with_grid: bool, with_ranking: bool
) -> None:
    if with_grid:
        grid, result = _grid_and_result()
    else:
        grid, result = None, _explicit_result()
    comparison = _comparison(result) if with_ranking else None

    report = HistoricalExperimentReportBuilder().build(
        result,
        grid_result=grid,
        comparison_result=comparison,
    )

    assert (
        report.variant_source is HistoricalExperimentReportVariantSource.GRID
    ) is with_grid
    assert (report.ranking is not None) is with_ranking
    assert tuple(row.caller_ordinal for row in report.variants) == (0, 1)


def test_grid_type_count_order_and_foreign_identity_are_rejected() -> None:
    grid, result = _grid_and_result()
    builder = HistoricalExperimentReportBuilder()
    with pytest.raises(InvalidHistoricalExperimentReportInputError):
        builder.build(result, grid_result=object())  # type: ignore[arg-type]

    malformed = copy(grid)
    object.__setattr__(malformed, "generated_variants", grid.generated_variants[:1])
    with pytest.raises(HistoricalExperimentReportGridError, match="count"):
        builder.build(result, grid_result=malformed)

    malformed = copy(grid)
    object.__setattr__(
        malformed,
        "generated_variants",
        tuple(reversed(grid.generated_variants)),
    )
    with pytest.raises(HistoricalExperimentReportGridError):
        builder.build(result, grid_result=malformed)

    foreign_grid, _ = _grid_and_result()
    with pytest.raises(HistoricalExperimentReportGridError, match="exact"):
        builder.build(result, grid_result=foreign_grid)


def test_grid_uuid_name_and_assignment_tampering_are_rejected() -> None:
    grid, result = _grid_and_result()
    generated = copy(grid.generated_variants[0])
    variant = copy(generated.variant)
    object.__setattr__(variant, "variant_id", uuid4())
    object.__setattr__(generated, "variant", variant)
    malformed = copy(grid)
    object.__setattr__(
        malformed, "generated_variants", (generated, grid.generated_variants[1])
    )
    with pytest.raises(HistoricalExperimentReportGridError):
        HistoricalExperimentReportBuilder().build(result, grid_result=malformed)

    generated = copy(grid.generated_variants[0])
    object.__setattr__(generated, "assignments", ())
    malformed = copy(grid)
    object.__setattr__(
        malformed, "generated_variants", (generated, grid.generated_variants[1])
    )
    with pytest.raises(HistoricalExperimentReportGridError, match="assignments"):
        HistoricalExperimentReportBuilder().build(result, grid_result=malformed)


def test_ranking_wrong_type_unrelated_missing_duplicate_and_foreign_are_rejected() -> (
    None
):
    result, comparison = _ranked_result()
    builder = HistoricalExperimentReportBuilder()
    with pytest.raises(InvalidHistoricalExperimentReportInputError):
        builder.build(result, comparison_result=object())  # type: ignore[arg-type]

    unrelated = _comparison(_explicit_result())
    with pytest.raises(HistoricalExperimentReportRankingError, match="exact"):
        builder.build(result, comparison_result=unrelated)

    for ranked in (
        comparison.ranked_runs[:1],
        (comparison.ranked_runs[0], comparison.ranked_runs[0]),
    ):
        malformed = copy(comparison)
        object.__setattr__(malformed, "ranked_runs", ranked)
        with pytest.raises(HistoricalExperimentReportRankingError):
            builder.build(result, comparison_result=malformed)

    malformed = copy(comparison)
    foreign = copy(comparison.ranked_runs[0])
    object.__setattr__(foreign, "run", _explicit_result().runs[0])
    object.__setattr__(
        malformed,
        "ranked_runs",
        (foreign, comparison.ranked_runs[1]),
    )
    with pytest.raises(HistoricalExperimentReportRankingError, match="foreign"):
        builder.build(result, comparison_result=malformed)


def test_ranking_ordinal_rank_and_value_count_are_rejected() -> None:
    result, comparison = _ranked_result()
    builder = HistoricalExperimentReportBuilder()
    field_changes = (
        {"caller_ordinal": 99},
        {"rank": 99},
        {"comparison_values": ()},
    )
    for changes in field_changes:
        item = copy(comparison.ranked_runs[0])
        for name, value in changes.items():
            object.__setattr__(item, name, value)
        malformed = copy(comparison)
        object.__setattr__(
            malformed,
            "ranked_runs",
            (item, comparison.ranked_runs[1]),
        )
        with pytest.raises(
            (
                HistoricalExperimentReportRankingError,
                HistoricalExperimentReportMetricError,
            )
        ):
            builder.build(result, comparison_result=malformed)


def test_metric_identity_tuple_is_complete_unique_and_exact() -> None:
    model_fields = tuple(item.name for item in fields(HistoricalExperimentMetrics))
    assert len(_METRIC_FIELDS) == 26
    assert len(set(_METRIC_FIELDS)) == 26
    assert set(_METRIC_FIELDS) == set(model_fields)


def test_malformed_metrics_and_comparison_scalars_are_rejected() -> None:
    result = _explicit_result()
    malformed_metrics = copy(result.runs[0].metrics)
    object.__setattr__(malformed_metrics, "total_orders", Decimal("1"))
    malformed_run = copy(result.runs[0])
    object.__setattr__(malformed_run, "metrics", malformed_metrics)
    malformed_result = copy(result)
    object.__setattr__(malformed_result, "runs", (malformed_run, result.runs[1]))
    with pytest.raises(HistoricalExperimentReportMetricError):
        HistoricalExperimentReportBuilder().build(malformed_result)

    ranked_result, comparison = _ranked_result()
    malformed_item = copy(comparison.ranked_runs[0])
    object.__setattr__(malformed_item, "comparison_values", (True,))
    malformed_comparison = copy(comparison)
    object.__setattr__(
        malformed_comparison,
        "ranked_runs",
        (malformed_item, comparison.ranked_runs[1]),
    )
    with pytest.raises(HistoricalExperimentReportMetricError):
        HistoricalExperimentReportBuilder().build(
            ranked_result, comparison_result=malformed_comparison
        )


def test_metadata_policy_and_copying_are_strict() -> None:
    result = _explicit_result()
    builder = HistoricalExperimentReportBuilder()
    with pytest.raises(InvalidHistoricalExperimentReportInputError):
        builder.build(result, metadata=(object(),))  # type: ignore[arg-type]
    with pytest.raises(InvalidHistoricalExperimentReportInputError, match="unique"):
        builder.build(
            result,
            metadata=(MetadataEntry("same", "1"), MetadataEntry("same", "2")),
        )
    with pytest.raises(InvalidHistoricalExperimentReportInputError, match="reserved"):
        builder.build(
            result,
            metadata=(MetadataEntry("historical_experiment_report_owner", "x"),),
        )


def test_identity_is_deterministic_context_independent_and_metadata_sensitive() -> None:
    result = _explicit_result()
    builder = HistoricalExperimentReportBuilder()
    first = builder.build(result)
    with localcontext(Context(prec=4)):
        second = builder.build(result)
    assert first == second
    assert first.report_id == second.report_id
    assert (
        builder.build(
            result, metadata=(MetadataEntry("a", "1"), MetadataEntry("b", "2"))
        ).report_id
        != builder.build(
            result, metadata=(MetadataEntry("b", "2"), MetadataEntry("a", "1"))
        ).report_id
    )


def test_identity_changes_with_source_grid_ranking_and_row_material() -> None:
    builder = HistoricalExperimentReportBuilder()
    source = _explicit_result()
    baseline = builder.build(source)
    changed_source = copy(source)
    object.__setattr__(changed_source, "result_id", uuid4())
    assert builder.build(changed_source).report_id != baseline.report_id

    grid, grid_source = _grid_and_result()
    grid_report = builder.build(grid_source, grid_result=grid)
    changed_grid = copy(grid)
    object.__setattr__(changed_grid, "result_id", uuid4())
    assert (
        builder.build(grid_source, grid_result=changed_grid).report_id
        != grid_report.report_id
    )
    changed_row = copy(grid.generated_variants[0])
    assignment = changed_row.assignments[0]
    object.__setattr__(
        changed_row,
        "assignments",
        (HistoricalExperimentGridAssignment(assignment.parameter, Decimal("9")),),
    )
    changed_grid = copy(grid)
    object.__setattr__(
        changed_grid,
        "generated_variants",
        (changed_row, grid.generated_variants[1]),
    )
    assert (
        builder.build(grid_source, grid_result=changed_grid).report_id
        != grid_report.report_id
    )

    ranked_source, comparison = _ranked_result()
    ranked_report = builder.build(ranked_source, comparison_result=comparison)
    changed_comparison = copy(comparison)
    object.__setattr__(changed_comparison, "result_id", uuid4())
    assert (
        builder.build(ranked_source, comparison_result=changed_comparison).report_id
        != ranked_report.report_id
    )
    changed_item = copy(comparison.ranked_runs[0])
    object.__setattr__(changed_item, "comparison_values", (Decimal("123"),))
    changed_comparison = copy(comparison)
    object.__setattr__(
        changed_comparison,
        "ranked_runs",
        (changed_item, comparison.ranked_runs[1]),
    )
    assert (
        builder.build(ranked_source, comparison_result=changed_comparison).report_id
        != ranked_report.report_id
    )


def test_negative_zero_has_equivalent_report_identity() -> None:
    source = _explicit_result()
    negative = copy(source)
    runs = []
    for run in source.runs:
        cloned = copy(run)
        object.__setattr__(
            cloned,
            "metrics",
            replace(run.metrics, rejected_notional=Decimal("-0")),
        )
        runs.append(cloned)
    object.__setattr__(negative, "runs", tuple(runs))
    positive = copy(negative)
    positive_runs = []
    for run in negative.runs:
        cloned = copy(run)
        object.__setattr__(
            cloned,
            "metrics",
            replace(run.metrics, rejected_notional=Decimal("0")),
        )
        positive_runs.append(cloned)
    object.__setattr__(positive, "runs", tuple(positive_runs))

    builder = HistoricalExperimentReportBuilder()
    assert builder.build(negative).report_id == builder.build(positive).report_id


def test_type_markers_separate_supported_scalar_types() -> None:
    assert len({_typed(1), _typed(Decimal("1")), _typed("1"), _typed(True)}) == 4
    assert _typed(None) == "NULL|"


def test_retained_report_rejects_wrong_identity_and_relationships() -> None:
    report = HistoricalExperimentReportBuilder().build(_explicit_result())
    with pytest.raises(InconsistentHistoricalExperimentReportError, match="report_id"):
        replace(report, report_id=uuid4())
    with pytest.raises(InconsistentHistoricalExperimentReportError, match="ordinals"):
        replace(
            report,
            variants=(
                replace(report.variants[0], caller_ordinal=1),
                report.variants[1],
            ),
        )
    with pytest.raises(InconsistentHistoricalExperimentReportError, match="grid"):
        replace(report, grid_result_id=uuid4())
    with pytest.raises(InconsistentHistoricalExperimentReportError, match="ranking"):
        replace(
            report,
            variants=(
                replace(report.variants[0], rank=1),
                report.variants[1],
            ),
        )


def test_retained_rows_and_report_defensively_copy_tuples() -> None:
    report = HistoricalExperimentReportBuilder().build(_explicit_result())
    rows = list(report.variants)
    copied = replace(report, variants=rows)
    rows.clear()
    assert copied.variants == report.variants

    values = [Decimal("1")]
    row = replace(report.variants[0], rank=1, comparison_values=values)
    values.clear()
    assert row.comparison_values == (Decimal("1"),)


def test_builder_rejects_wrong_or_locally_malformed_experiment() -> None:
    builder = HistoricalExperimentReportBuilder()
    with pytest.raises(InvalidHistoricalExperimentReportInputError):
        builder.build(object())  # type: ignore[arg-type]
    result = _explicit_result()
    malformed = copy(result)
    object.__setattr__(malformed, "runs", tuple(reversed(result.runs)))
    with pytest.raises(InvalidHistoricalExperimentReportInputError, match="ordinals"):
        builder.build(malformed)
