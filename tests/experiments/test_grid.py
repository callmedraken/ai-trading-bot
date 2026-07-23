from dataclasses import fields, replace
from decimal import Decimal, localcontext
from types import MappingProxyType
from uuid import UUID

import pytest
from tests.experiments.test_historical import _variant

from trading_bot.experiments import (
    HistoricalExperimentGeneratedVariant,
    HistoricalExperimentGridAssignment,
    HistoricalExperimentGridAxis,
    HistoricalExperimentGridAxisError,
    HistoricalExperimentGridGenerator,
    HistoricalExperimentGridParameter,
    HistoricalExperimentGridResult,
    HistoricalExperimentGridSizeError,
    HistoricalExperimentGridSpecification,
    HistoricalExperimentGridValueError,
    HistoricalExperimentGridVariantError,
    InconsistentHistoricalExperimentGridResultError,
    InvalidHistoricalExperimentGridSpecificationError,
)
from trading_bot.portfolio import MetadataEntry

P = HistoricalExperimentGridParameter


def _axis(
    parameter: HistoricalExperimentGridParameter,
    *values: int | Decimal | bool | None,
) -> HistoricalExperimentGridAxis:
    return HistoricalExperimentGridAxis(parameter, values)


def _specification(
    *axes: HistoricalExperimentGridAxis,
    base=None,  # type: ignore[no-untyped-def]
    maximum: int = 100,
    metadata: tuple[MetadataEntry, ...] = (),
) -> HistoricalExperimentGridSpecification:
    return HistoricalExperimentGridSpecification(
        UUID("00000000-0000-0000-0000-000000000701"),
        base or _variant(700, name="Base"),
        axes or (_axis(P.RISK_AVERSION, Decimal("1"), Decimal("2")),),
        maximum,
        metadata,
    )


def test_public_models_defensively_copy_ordered_inputs() -> None:
    values = [Decimal("2"), Decimal("1")]
    axis = HistoricalExperimentGridAxis(P.RISK_AVERSION, values)
    values.reverse()
    axes = [axis]
    metadata = [MetadataEntry("caller", "ordered")]
    specification = HistoricalExperimentGridSpecification(
        UUID(int=701), _variant(700), axes, 2, metadata
    )
    axes.clear()
    metadata.clear()
    assert axis.values == (Decimal("2"), Decimal("1"))
    assert specification.axes == (axis,)
    assert specification.metadata == (MetadataEntry("caller", "ordered"),)

    result = HistoricalExperimentGridGenerator().generate(specification)
    rows = list(result.generated_variants)
    copied = replace(result, generated_variants=rows)
    rows.clear()
    assert copied.generated_variants == result.generated_variants


@pytest.mark.parametrize(
    ("parameter", "valid"),
    (
        (P.WINDOW_OBSERVATION_COUNT, (2, 10)),
        (P.SCENARIO_CASH_RETURN, (Decimal("-1"), Decimal("0.01"))),
        (P.RISK_AVERSION, (Decimal("0"), Decimal("2"))),
        (P.PROPOSAL_CONFIDENCE, (None, Decimal("0"), Decimal("1"))),
        (P.TRADING_ENABLED, (False, True)),
    ),
)
def test_exact_supported_values_are_accepted(
    parameter: HistoricalExperimentGridParameter,
    valid: tuple[int | Decimal | bool | None, ...],
) -> None:
    assert HistoricalExperimentGridAxis(parameter, valid).values == valid
    for value in valid:
        assert HistoricalExperimentGridAssignment(parameter, value).value is value


@pytest.mark.parametrize(
    ("parameter", "invalid"),
    (
        (P.WINDOW_OBSERVATION_COUNT, (1, True, Decimal("2"), "2")),
        (
            P.SCENARIO_CASH_RETURN,
            (Decimal("-1.01"), Decimal("NaN"), Decimal("Infinity"), 0, 0.0, "0"),
        ),
        (
            P.RISK_AVERSION,
            (Decimal("-0.01"), Decimal("-Infinity"), 1, 1.0, "1"),
        ),
        (
            P.PROPOSAL_CONFIDENCE,
            (Decimal("-0.01"), Decimal("1.01"), Decimal("NaN"), 1, 1.0, "1"),
        ),
        (P.TRADING_ENABLED, (0, 1, Decimal("1"), "true")),
    ),
)
def test_invalid_values_are_rejected_without_coercion(
    parameter: HistoricalExperimentGridParameter,
    invalid: tuple[object, ...],
) -> None:
    for value in invalid:
        with pytest.raises(HistoricalExperimentGridValueError):
            HistoricalExperimentGridAxis(parameter, (value,))  # type: ignore[arg-type]


def test_axis_structure_and_canonical_duplicates_are_rejected() -> None:
    with pytest.raises(HistoricalExperimentGridAxisError, match="empty"):
        HistoricalExperimentGridAxis(P.RISK_AVERSION, ())
    with pytest.raises(HistoricalExperimentGridAxisError, match="parameter"):
        HistoricalExperimentGridAxis("RISK_AVERSION", (Decimal("1"),))  # type: ignore[arg-type]
    for values in (
        (Decimal("1"), Decimal("1.0")),
        (Decimal("0"), Decimal("-0")),
    ):
        with pytest.raises(HistoricalExperimentGridValueError, match="duplicate"):
            HistoricalExperimentGridAxis(P.RISK_AVERSION, values)


def test_specification_validation_is_strict() -> None:
    axis = _axis(P.RISK_AVERSION, Decimal("1"))
    with pytest.raises(InvalidHistoricalExperimentGridSpecificationError):
        HistoricalExperimentGridSpecification("bad", _variant(1), (axis,), 1)  # type: ignore[arg-type]
    with pytest.raises(InvalidHistoricalExperimentGridSpecificationError):
        HistoricalExperimentGridSpecification(UUID(int=1), object(), (axis,), 1)  # type: ignore[arg-type]
    with pytest.raises(
        InvalidHistoricalExperimentGridSpecificationError, match="empty"
    ):
        HistoricalExperimentGridSpecification(UUID(int=1), _variant(1), (), 1)
    for maximum in (0, -1, True, Decimal("1")):
        with pytest.raises(InvalidHistoricalExperimentGridSpecificationError):
            HistoricalExperimentGridSpecification(
                UUID(int=1),
                _variant(1),
                (axis,),
                maximum,  # type: ignore[arg-type]
            )
    with pytest.raises(HistoricalExperimentGridAxisError, match="unique"):
        _specification(axis, axis)
    with pytest.raises(
        InvalidHistoricalExperimentGridSpecificationError, match="unique"
    ):
        _specification(
            axis,
            metadata=(MetadataEntry("x", "1"), MetadataEntry("x", "2")),
        )
    with pytest.raises(
        InvalidHistoricalExperimentGridSpecificationError, match="reserved"
    ):
        _specification(
            axis, metadata=(MetadataEntry("historical_experiment_grid_x", "1"),)
        )


def test_cartesian_order_preserves_axes_and_final_axis_varies_fastest() -> None:
    specification = _specification(
        _axis(P.WINDOW_OBSERVATION_COUNT, 2, 3),
        _axis(P.RISK_AVERSION, Decimal("2"), Decimal("1")),
        _axis(P.TRADING_ENABLED, True, False),
    )
    result = HistoricalExperimentGridGenerator().generate(specification)
    actual = tuple(
        tuple(item.value for item in row.assignments)
        for row in result.generated_variants
    )
    assert actual == (
        (2, Decimal("2"), True),
        (2, Decimal("2"), False),
        (2, Decimal("1"), True),
        (2, Decimal("1"), False),
        (3, Decimal("2"), True),
        (3, Decimal("2"), False),
        (3, Decimal("1"), True),
        (3, Decimal("1"), False),
    )
    assert tuple(row.ordinal for row in result.generated_variants) == tuple(range(8))


def test_size_is_checked_before_any_row_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specification = _specification(
        _axis(P.RISK_AVERSION, Decimal("1"), Decimal("2")),
        _axis(P.TRADING_ENABLED, True, False),
        maximum=3,
    )

    def forbidden(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("row construction must not occur")

    from trading_bot.experiments import grid

    monkeypatch.setattr(grid, "_build_row", forbidden)
    with pytest.raises(HistoricalExperimentGridSizeError, match="4"):
        HistoricalExperimentGridGenerator().generate(specification)

    at_limit = replace(specification, maximum_variant_count=4)
    monkeypatch.undo()
    assert (
        len(HistoricalExperimentGridGenerator().generate(at_limit).generated_variants)
        == 4
    )


@pytest.mark.parametrize(
    ("parameter", "value", "field_name"),
    (
        (P.WINDOW_OBSERVATION_COUNT, 5, "window_policy"),
        (P.SCENARIO_CASH_RETURN, Decimal("0.1"), "scenario_cash_return"),
        (P.RISK_AVERSION, Decimal("3"), "risk_aversion"),
        (P.PROPOSAL_CONFIDENCE, Decimal("0.5"), "proposal_confidence"),
        (P.TRADING_ENABLED, False, "trading_enabled"),
    ),
)
def test_each_parameter_replaces_only_its_intended_field(
    parameter: HistoricalExperimentGridParameter,
    value: int | Decimal | bool | None,
    field_name: str,
) -> None:
    base = _variant(700, name="Base")
    result = HistoricalExperimentGridGenerator().generate(
        _specification(_axis(parameter, value), base=base)
    )
    generated = result.generated_variants[0].variant
    excluded = {"variant_id", "name", field_name}
    for field in fields(base):
        if field.name not in excluded:
            assert getattr(generated, field.name) == getattr(base, field.name)
            if field.name.endswith(
                ("policy", "parameters", "constraints", "assumptions", "limits")
            ):
                assert getattr(generated, field.name) is getattr(base, field.name)
    if parameter is P.WINDOW_OBSERVATION_COUNT:
        assert generated.window_policy.observation_count == value
        assert generated.window_policy is not base.window_policy
    else:
        assert getattr(generated, field_name) == value
    assert base == _variant(700, name="Base")
    assert generated.metadata is base.metadata


def test_names_typed_assignments_and_base_valued_combination() -> None:
    base = _variant(700, name="Base", risk_aversion="1", trading_enabled=True)
    result = HistoricalExperimentGridGenerator().generate(
        _specification(
            _axis(P.RISK_AVERSION, Decimal("1")),
            _axis(P.PROPOSAL_CONFIDENCE, None),
            _axis(P.TRADING_ENABLED, True),
            base=base,
        )
    )
    generated = result.generated_variants[0].variant
    assert generated.name == (
        "Base | RISK_AVERSION=1, PROPOSAL_CONFIDENCE=NULL, TRADING_ENABLED=true"
    )
    assert generated.variant_id != base.variant_id
    assert generated.risk_aversion == base.risk_aversion
    assert generated.trading_enabled == base.trading_enabled


def test_equal_grids_are_deterministic_and_inputs_affect_identity() -> None:
    axis = _axis(P.RISK_AVERSION, Decimal("1"), Decimal("2"))
    first = HistoricalExperimentGridGenerator().generate(_specification(axis))
    second = HistoricalExperimentGridGenerator().generate(_specification(axis))
    assert first == second

    changed_maximum = HistoricalExperimentGridGenerator().generate(
        _specification(axis, maximum=101)
    )
    changed_metadata = HistoricalExperimentGridGenerator().generate(
        _specification(axis, metadata=(MetadataEntry("purpose", "other"),))
    )
    changed_base = HistoricalExperimentGridGenerator().generate(
        _specification(axis, base=_variant(701, name="Base"))
    )
    reversed_values = HistoricalExperimentGridGenerator().generate(
        _specification(_axis(P.RISK_AVERSION, Decimal("2"), Decimal("1")))
    )
    assert (
        len(
            {
                first.result_id,
                changed_maximum.result_id,
                changed_metadata.result_id,
                changed_base.result_id,
                reversed_values.result_id,
            }
        )
        == 5
    )
    assert tuple(row.variant.variant_id for row in first.generated_variants) != tuple(
        row.variant.variant_id for row in reversed_values.generated_variants
    )


def test_axis_order_changes_generated_order_and_ids() -> None:
    first = HistoricalExperimentGridGenerator().generate(
        _specification(
            _axis(P.RISK_AVERSION, Decimal("1"), Decimal("2")),
            _axis(P.TRADING_ENABLED, True, False),
        )
    )
    second = HistoricalExperimentGridGenerator().generate(
        _specification(
            _axis(P.TRADING_ENABLED, True, False),
            _axis(P.RISK_AVERSION, Decimal("1"), Decimal("2")),
        )
    )
    assert first.result_id != second.result_id
    assert tuple(row.variant.variant_id for row in first.generated_variants) != tuple(
        row.variant.variant_id for row in second.generated_variants
    )


def test_decimal_context_does_not_affect_names_or_identities() -> None:
    specification = _specification(
        _axis(P.RISK_AVERSION, Decimal("1.2300"), Decimal("2.3400"))
    )
    with localcontext() as context:
        context.prec = 3
        first = HistoricalExperimentGridGenerator().generate(specification)
    with localcontext() as context:
        context.prec = 50
        second = HistoricalExperimentGridGenerator().generate(specification)
    assert first == second
    assert "RISK_AVERSION=1.23" in first.generated_variants[0].variant.name


def test_expected_combination_failure_retains_context_and_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.experiments import grid

    def fail(variant, value):  # type: ignore[no-untyped-def]
        raise ValueError("deliberate constructor failure")

    replacements = dict(grid._REPLACEMENTS)
    replacements[P.RISK_AVERSION] = fail
    monkeypatch.setattr(grid, "_REPLACEMENTS", MappingProxyType(replacements))
    with pytest.raises(HistoricalExperimentGridVariantError) as caught:
        HistoricalExperimentGridGenerator().generate(
            _specification(_axis(P.RISK_AVERSION, Decimal("2")))
        )
    assert caught.value.ordinal == 0
    assert caught.value.parameter is P.RISK_AVERSION
    assert caught.value.assignments[0].value == Decimal("2")
    assert isinstance(caught.value.cause, ValueError)


def test_equivalent_effective_variants_are_rejected_without_deduplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.experiments import grid

    replacements = dict(grid._REPLACEMENTS)
    replacements[P.RISK_AVERSION] = lambda variant, value: variant
    monkeypatch.setattr(grid, "_REPLACEMENTS", MappingProxyType(replacements))
    with pytest.raises(HistoricalExperimentGridVariantError, match="equivalent"):
        HistoricalExperimentGridGenerator().generate(
            _specification(_axis(P.RISK_AVERSION, Decimal("1"), Decimal("2")))
        )


def test_retained_result_reconciliation_rejects_tampering() -> None:
    result = HistoricalExperimentGridGenerator().generate(_specification())
    with pytest.raises(
        InconsistentHistoricalExperimentGridResultError, match="result_id"
    ):
        replace(result, result_id=UUID(int=999))

    row = result.generated_variants[0]
    wrong_row = HistoricalExperimentGeneratedVariant(
        row.ordinal,
        replace(row.variant, name="wrong"),
        row.assignments,
    )
    with pytest.raises(
        InconsistentHistoricalExperimentGridResultError, match="inconsistent"
    ):
        HistoricalExperimentGridResult(
            result.result_id,
            result.specification,
            (wrong_row, *result.generated_variants[1:]),
        )

    with pytest.raises(InconsistentHistoricalExperimentGridResultError, match="count"):
        HistoricalExperimentGridResult(
            result.result_id, result.specification, result.generated_variants[:-1]
        )


def test_generator_rejects_nonexact_specification() -> None:
    with pytest.raises(InvalidHistoricalExperimentGridSpecificationError):
        HistoricalExperimentGridGenerator().generate(object())  # type: ignore[arg-type]
