from copy import copy
from dataclasses import fields, replace
from decimal import Context, Decimal, localcontext
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest
from tests.experiments.test_historical import _Factory, _request, _variant

from trading_bot.experiments import (
    HistoricalExperimentMetrics,
    HistoricalExperimentPairwiseComparator,
    HistoricalExperimentPairwiseDifference,
    HistoricalExperimentPairwiseMetricError,
    HistoricalExperimentPairwiseOrientation,
    HistoricalExperimentPairwisePairing,
    HistoricalExperimentPairwisePolicy,
    HistoricalExperimentPairwiseReconciliationError,
    HistoricalExperimentPairwiseRecord,
    HistoricalExperimentPairwiseReportError,
    HistoricalExperimentPairwiseResult,
    HistoricalExperimentRankingMetric,
    HistoricalExperimentReportBuilder,
    HistoricalExperimentRunner,
    InconsistentHistoricalExperimentPairwiseResultError,
    InvalidHistoricalExperimentPairwisePolicyError,
)
from trading_bot.experiments.pairwise import (
    _METRIC_FIELDS,
    _exact_decimal_subtract,
    _typed,
)
from trading_bot.portfolio import MetadataEntry

M = HistoricalExperimentRankingMetric
ORIENTATION = HistoricalExperimentPairwiseOrientation
P = HistoricalExperimentPairwisePairing
POLICY_ID = UUID(int=801)


def _policy(
    *metrics: HistoricalExperimentRankingMetric,
    pairing: HistoricalExperimentPairwisePairing = P.ALL_UNORDERED_PAIRS,
    orientation: HistoricalExperimentPairwiseOrientation = ORIENTATION.CALLER_ORDER,
    baseline: UUID | None = None,
    policy_id: UUID = POLICY_ID,
    metadata: tuple[MetadataEntry, ...] = (),
) -> HistoricalExperimentPairwisePolicy:
    return HistoricalExperimentPairwisePolicy(
        policy_id,
        metrics or (M.SIMULATION_RETURN,),
        pairing,
        orientation,
        baseline,
        metadata,
    )


def _report(
    identifiers: tuple[int, ...] = (10, 11, 12),
    changes: tuple[dict[str, Decimal | int], ...] | None = None,
):
    variants = tuple(
        _variant(identifier, name=f"variant-{ordinal}")
        for ordinal, identifier in enumerate(identifiers)
    )
    result = HistoricalExperimentRunner(_Factory()).run(_request(variants=variants))
    if changes is not None:
        runs = []
        for run, values in zip(result.runs, changes, strict=True):
            cloned = copy(run)
            object.__setattr__(cloned, "metrics", replace(run.metrics, **values))
            runs.append(cloned)
        result = copy(result)
        object.__setattr__(result, "runs", tuple(runs))
    return HistoricalExperimentReportBuilder().build(result)


def test_metric_mapping_is_complete_exact_and_immutable() -> None:
    model_fields = {item.name for item in fields(HistoricalExperimentMetrics)}
    assert isinstance(_METRIC_FIELDS, MappingProxyType)
    assert set(_METRIC_FIELDS) == set(M)
    assert len(_METRIC_FIELDS) == 26
    assert len(set(_METRIC_FIELDS.values())) == 26
    assert set(_METRIC_FIELDS.values()) == model_fields
    with pytest.raises(TypeError):
        _METRIC_FIELDS[M.TOTAL_ORDERS] = "changed"  # type: ignore[index]


def test_policy_copies_ordered_metrics_and_metadata() -> None:
    metrics = [M.FINAL_EQUITY, M.TOTAL_ORDERS]
    metadata = [MetadataEntry("owner", "research")]
    policy = HistoricalExperimentPairwisePolicy(
        UUID(int=1),
        metrics,
        P.ALL_UNORDERED_PAIRS,
        ORIENTATION.VARIANT_ID,
        None,
        metadata,
    )
    metrics.clear()
    metadata.clear()
    assert policy.metrics == (M.FINAL_EQUITY, M.TOTAL_ORDERS)
    assert policy.metadata == (MetadataEntry("owner", "research"),)


@pytest.mark.parametrize(
    "arguments",
    (
        (
            "bad",
            (M.FINAL_EQUITY,),
            P.ALL_UNORDERED_PAIRS,
            ORIENTATION.CALLER_ORDER,
            None,
        ),
        (uuid4(), (), P.ALL_UNORDERED_PAIRS, ORIENTATION.CALLER_ORDER, None),
        (
            uuid4(),
            (M.FINAL_EQUITY, M.FINAL_EQUITY),
            P.ALL_UNORDERED_PAIRS,
            ORIENTATION.CALLER_ORDER,
            None,
        ),
        (
            uuid4(),
            ("FINAL_EQUITY",),
            P.ALL_UNORDERED_PAIRS,
            ORIENTATION.CALLER_ORDER,
            None,
        ),
        (uuid4(), (M.FINAL_EQUITY,), "ALL", ORIENTATION.CALLER_ORDER, None),
        (uuid4(), (M.FINAL_EQUITY,), P.ALL_UNORDERED_PAIRS, "CALLER", None),
        (
            uuid4(),
            (M.FINAL_EQUITY,),
            P.ALL_UNORDERED_PAIRS,
            ORIENTATION.CALLER_ORDER,
            uuid4(),
        ),
        (
            uuid4(),
            (M.FINAL_EQUITY,),
            P.BASELINE_VERSUS_ALL,
            ORIENTATION.CALLER_ORDER,
            None,
        ),
        (
            uuid4(),
            (M.FINAL_EQUITY,),
            P.BASELINE_VERSUS_ALL,
            ORIENTATION.VARIANT_ID,
            uuid4(),
        ),
    ),
)
def test_invalid_policy_shapes_are_rejected(arguments: tuple) -> None:
    with pytest.raises(InvalidHistoricalExperimentPairwisePolicyError):
        HistoricalExperimentPairwisePolicy(*arguments)


def test_policy_metadata_restrictions() -> None:
    with pytest.raises(InvalidHistoricalExperimentPairwisePolicyError, match="unique"):
        _policy(metadata=(MetadataEntry("same", "1"), MetadataEntry("same", "2")))
    with pytest.raises(
        InvalidHistoricalExperimentPairwisePolicyError, match="reserved"
    ):
        _policy(metadata=(MetadataEntry("historical_experiment_pairwise_owner", "x"),))


@pytest.mark.parametrize(("count", "expected"), ((1, 0), (2, 1), (3, 3), (4, 6)))
def test_all_pairs_have_triangular_caller_order_coverage(
    count: int, expected: int
) -> None:
    report = _report(tuple(range(10, 10 + count)))
    result = HistoricalExperimentPairwiseComparator().compare(
        report, _policy(M.FINAL_EQUITY)
    )
    assert len(result.records) == expected
    assert tuple(
        (item.left_caller_ordinal, item.right_caller_ordinal) for item in result.records
    ) == tuple(
        (left, right) for left in range(count) for right in range(left + 1, count)
    )
    assert tuple(item.ordinal for item in result.records) == tuple(range(expected))
    assert (
        len(
            {
                frozenset((item.left_variant_id, item.right_variant_id))
                for item in result.records
            }
        )
        == expected
    )


def test_variant_id_orientation_swaps_sides_without_reordering_pairs() -> None:
    report = _report((30, 10, 20))
    result = HistoricalExperimentPairwiseComparator().compare(
        report,
        _policy(M.FINAL_EQUITY, orientation=ORIENTATION.VARIANT_ID),
    )
    assert tuple(
        frozenset((item.left_caller_ordinal, item.right_caller_ordinal))
        for item in result.records
    ) == (frozenset((0, 1)), frozenset((0, 2)), frozenset((1, 2)))
    assert tuple(
        (item.left_caller_ordinal, item.right_caller_ordinal) for item in result.records
    ) == ((1, 0), (2, 0), (1, 2))
    assert all(
        item.left_variant_id.int < item.right_variant_id.int for item in result.records
    )


@pytest.mark.parametrize("baseline_index", (0, 1, 2))
def test_baseline_is_always_left_and_others_remain_caller_ordered(
    baseline_index: int,
) -> None:
    report = _report()
    baseline = report.variants[baseline_index]
    result = HistoricalExperimentPairwiseComparator().compare(
        report,
        _policy(
            M.FINAL_EQUITY,
            pairing=P.BASELINE_VERSUS_ALL,
            baseline=baseline.variant_id,
        ),
    )
    expected_right = tuple(index for index in range(3) if index != baseline_index)
    assert (
        tuple(item.left_variant_id for item in result.records)
        == (baseline.variant_id,) * 2
    )
    assert tuple(item.right_caller_ordinal for item in result.records) == expected_right


def test_one_row_baseline_produces_zero_records_and_foreign_baseline_fails() -> None:
    report = _report((10,))
    result = HistoricalExperimentPairwiseComparator().compare(
        report,
        _policy(
            M.FINAL_EQUITY,
            pairing=P.BASELINE_VERSUS_ALL,
            baseline=report.variants[0].variant_id,
        ),
    )
    assert result.records == ()
    with pytest.raises(HistoricalExperimentPairwiseReportError, match="baseline"):
        HistoricalExperimentPairwiseComparator().compare(
            report,
            _policy(
                M.FINAL_EQUITY,
                pairing=P.BASELINE_VERSUS_ALL,
                baseline=uuid4(),
            ),
        )


def test_decimal_and_integer_differences_are_exact_right_minus_left() -> None:
    report = _report(
        changes=(
            {"simulation_return": Decimal("2.25"), "total_orders": 4},
            {"simulation_return": Decimal("-1.75"), "total_orders": 1},
            {"simulation_return": Decimal("2.25"), "total_orders": 4},
        )
    )
    result = HistoricalExperimentPairwiseComparator().compare(
        report, _policy(M.SIMULATION_RETURN, M.TOTAL_ORDERS)
    )
    first = result.records[0].differences
    assert first[0].left_value == Decimal("2.25")
    assert first[0].right_value == Decimal("-1.75")
    assert first[0].difference == Decimal("-4.00")
    assert first[1].left_value == 4
    assert first[1].right_value == 1
    assert first[1].difference == -3
    zero = result.records[1].differences
    assert zero[0].difference == Decimal("0")
    assert zero[0].difference.as_tuple().sign == 0
    assert zero[1].difference == 0


def test_exact_decimal_subtraction_ignores_hostile_ambient_contexts() -> None:
    left = Decimal("123456789012345678901234567890.123456789")
    right = Decimal("-987654321098765432109876543210.987654321")
    expected = Decimal("-1111111110111111111011111111101.111111110")
    values = []
    for context in (
        Context(prec=1, Emax=9, Emin=-9),
        Context(prec=3, Emax=20, Emin=-20),
        Context(prec=6, Emax=99, Emin=-99),
    ):
        with localcontext(context):
            values.append(_exact_decimal_subtract(right, left))
    assert values == [expected, expected, expected]
    assert _exact_decimal_subtract(Decimal("1E+100"), Decimal("1E-100")) == Decimal(
        (0, (9,) * 200, -100)
    )


def test_negative_zero_difference_is_canonical_positive_zero() -> None:
    difference = HistoricalExperimentPairwiseDifference(
        M.SIMULATION_RETURN,
        Decimal("-0"),
        Decimal("0"),
        Decimal("-0"),
    )
    assert difference.left_value.is_signed()
    assert difference.difference == Decimal("0")
    assert not difference.difference.is_signed()


@pytest.mark.parametrize(
    "values",
    (
        (M.TOTAL_ORDERS, 1, 0, -1),
        (M.TOTAL_ORDERS, 0, 1, 1),
        (M.TOTAL_ORDERS, 1, 1, 0),
        (M.SIMULATION_RETURN, Decimal("1"), Decimal("2"), Decimal("1")),
    ),
)
def test_difference_model_accepts_exact_signed_results(values: tuple) -> None:
    assert HistoricalExperimentPairwiseDifference(*values).difference == values[3]


@pytest.mark.parametrize(
    "values",
    (
        (M.TOTAL_ORDERS, True, 1, 0),
        (M.TOTAL_ORDERS, -1, 1, 2),
        (M.TOTAL_ORDERS, 1, 2, Decimal("1")),
        (M.SIMULATION_RETURN, Decimal("NaN"), Decimal("1"), Decimal("0")),
        (M.SIMULATION_RETURN, Decimal("1"), Decimal("2"), Decimal("-1")),
    ),
)
def test_difference_model_rejects_malformed_values(values: tuple) -> None:
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        HistoricalExperimentPairwiseDifference(*values)


def test_record_validation_and_defensive_copying() -> None:
    difference = HistoricalExperimentPairwiseDifference(M.TOTAL_ORDERS, 1, 2, 1)
    differences = [difference]
    record = HistoricalExperimentPairwiseRecord(
        0, 0, 1, UUID(int=1), UUID(int=2), differences
    )
    differences.clear()
    assert record.differences == (difference,)
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        replace(record, right_caller_ordinal=0)
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        replace(record, right_variant_id=record.left_variant_id)


def test_results_are_deterministic_context_independent_and_compact() -> None:
    report = _report(
        changes=(
            {"simulation_return": Decimal("123456789.123456789")},
            {"simulation_return": Decimal("-987654321.987654321")},
            {"simulation_return": Decimal("0")},
        )
    )
    policy = _policy(
        M.SIMULATION_RETURN,
        metadata=(MetadataEntry("purpose", "research"),),
    )
    comparator = HistoricalExperimentPairwiseComparator()
    first = comparator.compare(report, policy)
    with localcontext(Context(prec=2, Emax=5, Emin=-5)):
        second = comparator.compare(report, policy)
    assert first == second
    assert first.result_id == second.result_id
    assert first.source_report_id == report.report_id
    assert not hasattr(first, "report")
    assert not hasattr(first.records[0], "metrics")
    assert not hasattr(first.records[0], "variant_name")


def test_identity_changes_with_policy_and_metadata_order() -> None:
    report = _report()
    comparator = HistoricalExperimentPairwiseComparator()
    baseline = comparator.compare(report, _policy(M.FINAL_EQUITY))
    assert (
        comparator.compare(report, _policy(M.FINAL_EQUITY, policy_id=uuid4())).result_id
        != baseline.result_id
    )
    assert (
        comparator.compare(report, _policy(M.TOTAL_ORDERS)).result_id
        != baseline.result_id
    )
    first = comparator.compare(
        report,
        _policy(
            M.FINAL_EQUITY,
            metadata=(MetadataEntry("a", "1"), MetadataEntry("b", "2")),
        ),
    )
    second = comparator.compare(
        report,
        _policy(
            M.FINAL_EQUITY,
            metadata=(MetadataEntry("b", "2"), MetadataEntry("a", "1")),
        ),
    )
    assert first.result_id != second.result_id


def test_identity_changes_with_report_pairing_orientation_and_baseline() -> None:
    report = _report()
    comparator = HistoricalExperimentPairwiseComparator()
    baseline = comparator.compare(report, _policy(M.FINAL_EQUITY))
    changed_report = _report(
        changes=(
            {"final_equity": Decimal("9999")},
            {"final_equity": Decimal("10000")},
            {"final_equity": Decimal("10000")},
        )
    )
    assert (
        comparator.compare(changed_report, _policy(M.FINAL_EQUITY)).result_id
        != baseline.result_id
    )
    assert (
        comparator.compare(
            report,
            _policy(M.FINAL_EQUITY, orientation=ORIENTATION.VARIANT_ID),
        ).result_id
        != baseline.result_id
    )
    baseline_result = comparator.compare(
        report,
        _policy(
            M.FINAL_EQUITY,
            pairing=P.BASELINE_VERSUS_ALL,
            baseline=report.variants[0].variant_id,
        ),
    )
    assert baseline_result.result_id != baseline.result_id


def test_typed_identity_markers_do_not_collapse_scalars() -> None:
    assert len({_typed(1), _typed(Decimal("1")), _typed("1"), _typed(None)}) == 4


def test_retained_result_rejects_wrong_uuid_order_orientation_and_metrics() -> None:
    result = HistoricalExperimentPairwiseComparator().compare(
        _report(), _policy(M.FINAL_EQUITY)
    )
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        replace(result, result_id=uuid4())
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        replace(
            result,
            records=(replace(result.records[0], ordinal=1), *result.records[1:]),
        )
    reversed_record = replace(
        result.records[0],
        left_caller_ordinal=result.records[0].right_caller_ordinal,
        right_caller_ordinal=result.records[0].left_caller_ordinal,
        left_variant_id=result.records[0].right_variant_id,
        right_variant_id=result.records[0].left_variant_id,
        differences=tuple(
            HistoricalExperimentPairwiseDifference(
                item.metric,
                item.right_value,
                item.left_value,
                -item.difference,
            )
            for item in result.records[0].differences
        ),
    )
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        replace(result, records=(reversed_record, *result.records[1:]))
    wrong_metric = copy(result.records[0].differences[0])
    object.__setattr__(wrong_metric, "metric", M.TOTAL_ORDERS)
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        replace(
            result,
            records=(
                replace(result.records[0], differences=(wrong_metric,)),
                *result.records[1:],
            ),
        )


def test_result_defensively_copies_records() -> None:
    result = HistoricalExperimentPairwiseComparator().compare(
        _report(), _policy(M.FINAL_EQUITY)
    )
    records = list(result.records)
    copied = HistoricalExperimentPairwiseResult(
        result.result_id, result.source_report_id, result.policy, records
    )
    records.clear()
    assert copied.records == result.records


def test_retained_result_rejects_missing_and_duplicate_pairs() -> None:
    result = HistoricalExperimentPairwiseComparator().compare(
        _report(), _policy(M.FINAL_EQUITY)
    )
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        HistoricalExperimentPairwiseResult(
            result.result_id,
            result.source_report_id,
            result.policy,
            result.records[:-1],
        )
    duplicate = replace(result.records[1], ordinal=2)
    with pytest.raises(InconsistentHistoricalExperimentPairwiseResultError):
        HistoricalExperimentPairwiseResult(
            result.result_id,
            result.source_report_id,
            result.policy,
            (*result.records[:2], duplicate),
        )


def test_wrong_report_and_malformed_requested_metric_are_focused_errors() -> None:
    comparator = HistoricalExperimentPairwiseComparator()
    with pytest.raises(HistoricalExperimentPairwiseReportError):
        comparator.compare(object(), _policy(M.FINAL_EQUITY))  # type: ignore[arg-type]
    report = _report()
    metrics = copy(report.variants[0].metrics)
    object.__setattr__(metrics, "total_orders", Decimal("1"))
    row = copy(report.variants[0])
    object.__setattr__(row, "metrics", metrics)
    malformed = copy(report)
    object.__setattr__(malformed, "variants", (row, *report.variants[1:]))
    with pytest.raises(HistoricalExperimentPairwiseMetricError):
        comparator.compare(malformed, _policy(M.TOTAL_ORDERS))


def test_reconciliation_detects_changed_pair_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.experiments import pairwise

    original = pairwise._pair_rows
    calls = 0

    def changing(rows, policy):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        pairs = original(rows, policy)
        return pairs if calls == 1 else pairs[:-1]

    monkeypatch.setattr(pairwise, "_pair_rows", changing)
    with pytest.raises(HistoricalExperimentPairwiseReconciliationError, match="count"):
        HistoricalExperimentPairwiseComparator().compare(
            _report(), _policy(M.FINAL_EQUITY)
        )
