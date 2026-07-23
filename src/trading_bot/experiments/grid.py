"""Pure deterministic expansion of explicit historical experiment grids."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum, StrEnum
from itertools import product
from math import prod
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.experiments._variant_identity import (
    canonical_variant_material,
    canonical_variant_semantic_material,
)
from trading_bot.experiments.exceptions import (
    HistoricalExperimentGridAxisError,
    HistoricalExperimentGridReconciliationError,
    HistoricalExperimentGridSizeError,
    HistoricalExperimentGridValueError,
    HistoricalExperimentGridVariantError,
    InconsistentHistoricalExperimentGridResultError,
    InvalidHistoricalExperimentGridSpecificationError,
)
from trading_bot.experiments.historical import HistoricalExperimentVariant
from trading_bot.portfolio import MetadataEntry
from trading_bot.simulation import RollingHistoricalWindowPolicy

_VERSION = "historical-experiment-grid-v1"
_NAMESPACE = UUID("18ea3f4f-b434-57d8-8297-313ade17ad65")
_RESERVED_PREFIX = "historical_experiment_grid_"
_ZERO = Decimal("0")
_ONE = Decimal("1")
GridValue = int | Decimal | bool | None


class HistoricalExperimentGridParameter(StrEnum):
    WINDOW_OBSERVATION_COUNT = "WINDOW_OBSERVATION_COUNT"
    SCENARIO_CASH_RETURN = "SCENARIO_CASH_RETURN"
    RISK_AVERSION = "RISK_AVERSION"
    PROPOSAL_CONFIDENCE = "PROPOSAL_CONFIDENCE"
    TRADING_ENABLED = "TRADING_ENABLED"


@dataclass(frozen=True, slots=True)
class HistoricalExperimentGridAssignment:
    parameter: HistoricalExperimentGridParameter
    value: GridValue

    def __post_init__(self) -> None:
        _validate_parameter(self.parameter, HistoricalExperimentGridValueError)
        _validate_value(self.parameter, self.value)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentGridAxis:
    parameter: HistoricalExperimentGridParameter
    values: tuple[GridValue, ...]

    def __post_init__(self) -> None:
        _validate_parameter(self.parameter, HistoricalExperimentGridAxisError)
        try:
            values = tuple(self.values)
        except TypeError as error:
            raise HistoricalExperimentGridAxisError(
                "axis values must be iterable"
            ) from error
        if not values:
            raise HistoricalExperimentGridAxisError("axis values must not be empty")
        canonical = []
        for value in values:
            _validate_value(self.parameter, value)
            canonical.append(_typed_value(value))
        if len(set(canonical)) != len(canonical):
            raise HistoricalExperimentGridValueError(
                "axis values contain a canonical duplicate"
            )
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentGridSpecification:
    specification_id: UUID
    base_variant: HistoricalExperimentVariant
    axes: tuple[HistoricalExperimentGridAxis, ...]
    maximum_variant_count: int
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidHistoricalExperimentGridSpecificationError
        if type(self.specification_id) is not UUID:
            raise error("specification_id must be a UUID")
        if type(self.base_variant) is not HistoricalExperimentVariant:
            raise error("base_variant must be exactly HistoricalExperimentVariant")
        self.base_variant.__post_init__()
        try:
            axes = tuple(self.axes)
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("axes and metadata must be iterable") from caught
        if not axes:
            raise error("axes must not be empty")
        if not all(type(item) is HistoricalExperimentGridAxis for item in axes):
            raise error("axes must contain exact HistoricalExperimentGridAxis values")
        if len({item.parameter for item in axes}) != len(axes):
            raise HistoricalExperimentGridAxisError("axis parameters must be unique")
        maximum = self.maximum_variant_count
        if type(maximum) is not int or maximum <= 0:
            raise error("maximum_variant_count must be a positive non-boolean integer")
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
        object.__setattr__(self, "axes", axes)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentGeneratedVariant:
    ordinal: int
    variant: HistoricalExperimentVariant
    assignments: tuple[HistoricalExperimentGridAssignment, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentGridResultError
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise error("generated ordinal must be a nonnegative integer")
        if type(self.variant) is not HistoricalExperimentVariant:
            raise error("generated variant has an invalid type")
        try:
            assignments = tuple(self.assignments)
        except TypeError as caught:
            raise error("generated assignments must be iterable") from caught
        if not assignments or not all(
            type(item) is HistoricalExperimentGridAssignment for item in assignments
        ):
            raise error("generated assignments contain an invalid value")
        object.__setattr__(self, "assignments", assignments)


@dataclass(frozen=True, slots=True)
class HistoricalExperimentGridResult:
    result_id: UUID
    specification: HistoricalExperimentGridSpecification
    generated_variants: tuple[HistoricalExperimentGeneratedVariant, ...]

    def __post_init__(self) -> None:
        error = InconsistentHistoricalExperimentGridResultError
        if type(self.result_id) is not UUID:
            raise error("result_id must be a UUID")
        if type(self.specification) is not HistoricalExperimentGridSpecification:
            raise error("specification has an invalid type")
        try:
            generated = tuple(self.generated_variants)
        except TypeError as caught:
            raise error("generated_variants must be iterable") from caught
        if not all(
            type(item) is HistoricalExperimentGeneratedVariant for item in generated
        ):
            raise error("generated_variants contain an invalid value")
        _reconcile(self.specification, generated, error)
        expected = _result_id(self.specification, generated)
        if self.result_id != expected:
            raise error("result_id is inconsistent")
        object.__setattr__(self, "generated_variants", generated)


class HistoricalExperimentGridGenerator:
    """Expand one explicit finite grid without executing an experiment."""

    def generate(
        self,
        specification: HistoricalExperimentGridSpecification,
    ) -> HistoricalExperimentGridResult:
        if type(specification) is not HistoricalExperimentGridSpecification:
            raise InvalidHistoricalExperimentGridSpecificationError(
                "specification must be exactly HistoricalExperimentGridSpecification"
            )
        specification.__post_init__()
        before = _specification_invariant(specification)
        count = prod(len(axis.values) for axis in specification.axes)
        if count > specification.maximum_variant_count:
            raise HistoricalExperimentGridSizeError(
                f"Cartesian size {count} exceeds maximum_variant_count "
                f"{specification.maximum_variant_count}"
            )
        generated = []
        ids: set[UUID] = set()
        names: set[str] = set()
        semantics: set[tuple[str, ...]] = set()
        combinations = product(*(axis.values for axis in specification.axes))
        for ordinal, values in enumerate(combinations):
            assignments = tuple(
                HistoricalExperimentGridAssignment(axis.parameter, value)
                for axis, value in zip(specification.axes, values, strict=True)
            )
            row = _build_row(specification, ordinal, assignments)
            semantic = canonical_variant_semantic_material(row.variant)
            normalized_name = row.variant.name.strip().casefold()
            if row.variant.variant_id in ids:
                raise HistoricalExperimentGridVariantError(
                    "generated variant ID is duplicated",
                    ordinal=ordinal,
                    assignments=assignments,
                )
            if normalized_name in names:
                raise HistoricalExperimentGridVariantError(
                    "generated variant name is duplicated after normalization",
                    ordinal=ordinal,
                    assignments=assignments,
                )
            if semantic in semantics:
                raise HistoricalExperimentGridVariantError(
                    "different combinations produced equivalent effective variants",
                    ordinal=ordinal,
                    assignments=assignments,
                )
            ids.add(row.variant.variant_id)
            names.add(normalized_name)
            semantics.add(semantic)
            generated.append(row)
        rows = tuple(generated)
        if before != _specification_invariant(specification):
            raise HistoricalExperimentGridReconciliationError(
                "specification or base variant changed during generation"
            )
        _reconcile(specification, rows, HistoricalExperimentGridReconciliationError)
        return HistoricalExperimentGridResult(
            _result_id(specification, rows), specification, rows
        )


def _replace_window(
    variant: HistoricalExperimentVariant, value: GridValue
) -> HistoricalExperimentVariant:
    return replace(
        variant,
        window_policy=RollingHistoricalWindowPolicy(value),  # type: ignore[arg-type]
    )


def _replace_cash_return(
    variant: HistoricalExperimentVariant, value: GridValue
) -> HistoricalExperimentVariant:
    return replace(variant, scenario_cash_return=value)  # type: ignore[arg-type]


def _replace_risk_aversion(
    variant: HistoricalExperimentVariant, value: GridValue
) -> HistoricalExperimentVariant:
    return replace(variant, risk_aversion=value)  # type: ignore[arg-type]


def _replace_confidence(
    variant: HistoricalExperimentVariant, value: GridValue
) -> HistoricalExperimentVariant:
    return replace(variant, proposal_confidence=value)  # type: ignore[arg-type]


def _replace_trading(
    variant: HistoricalExperimentVariant, value: GridValue
) -> HistoricalExperimentVariant:
    return replace(variant, trading_enabled=value)  # type: ignore[arg-type]


_Replacement = Callable[
    [HistoricalExperimentVariant, GridValue], HistoricalExperimentVariant
]
_REPLACEMENTS: MappingProxyType[HistoricalExperimentGridParameter, _Replacement] = (
    MappingProxyType(
        {
            HistoricalExperimentGridParameter.WINDOW_OBSERVATION_COUNT: _replace_window,
            HistoricalExperimentGridParameter.SCENARIO_CASH_RETURN: (
                _replace_cash_return
            ),
            HistoricalExperimentGridParameter.RISK_AVERSION: _replace_risk_aversion,
            HistoricalExperimentGridParameter.PROPOSAL_CONFIDENCE: _replace_confidence,
            HistoricalExperimentGridParameter.TRADING_ENABLED: _replace_trading,
        }
    )
)


def _build_row(
    specification: HistoricalExperimentGridSpecification,
    ordinal: int,
    assignments: tuple[HistoricalExperimentGridAssignment, ...],
) -> HistoricalExperimentGeneratedVariant:
    variant = specification.base_variant
    parameter = None
    try:
        for assignment in assignments:
            parameter = assignment.parameter
            variant = _REPLACEMENTS[parameter](variant, assignment.value)
        identifier = _generated_variant_id(specification, ordinal, assignments)
        name = _generated_name(specification.base_variant, assignments)
        variant = replace(variant, variant_id=identifier, name=name)
    except (TypeError, ValueError) as caught:
        raise HistoricalExperimentGridVariantError(
            f"cannot construct generated variant {ordinal}: {caught}",
            ordinal=ordinal,
            assignments=assignments,
            parameter=parameter,
            cause=caught,
        ) from caught
    return HistoricalExperimentGeneratedVariant(ordinal, variant, assignments)


def _reconcile(specification, generated, error_type) -> None:  # type: ignore[no-untyped-def]
    expected_count = prod(len(axis.values) for axis in specification.axes)
    if len(generated) != expected_count:
        raise error_type("generated count differs from the Cartesian product")
    if tuple(item.ordinal for item in generated) != tuple(range(expected_count)):
        raise error_type("generated ordinals must be sequential from zero")
    expected_combinations = product(*(axis.values for axis in specification.axes))
    ids = set()
    names = set()
    semantics = set()
    for row, values in zip(generated, expected_combinations, strict=True):
        expected_assignments = tuple(
            HistoricalExperimentGridAssignment(axis.parameter, value)
            for axis, value in zip(specification.axes, values, strict=True)
        )
        if row.assignments != expected_assignments:
            raise error_type("assignments do not match their Cartesian position")
        try:
            expected = _build_row(specification, row.ordinal, expected_assignments)
        except HistoricalExperimentGridVariantError as caught:
            raise error_type(str(caught)) from caught
        if row.variant != expected.variant:
            raise error_type("generated variant content, name, or ID is inconsistent")
        identifier = row.variant.variant_id
        name = row.variant.name.strip().casefold()
        semantic = canonical_variant_semantic_material(row.variant)
        if identifier in ids or name in names or semantic in semantics:
            raise error_type("generated variants contain a duplicate")
        ids.add(identifier)
        names.add(name)
        semantics.add(semantic)


def _validate_parameter(parameter, error_type) -> None:  # type: ignore[no-untyped-def]
    if type(parameter) is not HistoricalExperimentGridParameter:
        raise error_type("parameter must be an exact supported grid parameter")


def _validate_value(
    parameter: HistoricalExperimentGridParameter, value: GridValue
) -> None:
    error = HistoricalExperimentGridValueError
    if parameter is HistoricalExperimentGridParameter.WINDOW_OBSERVATION_COUNT:
        if type(value) is not int or value < 2:
            raise error("WINDOW_OBSERVATION_COUNT values must be integers >= 2")
        return
    if parameter is HistoricalExperimentGridParameter.TRADING_ENABLED:
        if type(value) is not bool:
            raise error("TRADING_ENABLED values must be exact bool values")
        return
    if parameter is HistoricalExperimentGridParameter.PROPOSAL_CONFIDENCE:
        if value is None:
            return
        decimal = _exact_decimal(value, parameter)
        if not _ZERO <= decimal <= _ONE:
            raise error("PROPOSAL_CONFIDENCE values must be between zero and one")
        return
    decimal = _exact_decimal(value, parameter)
    if (
        parameter is HistoricalExperimentGridParameter.SCENARIO_CASH_RETURN
        and decimal < Decimal("-1")
    ):
        raise error("SCENARIO_CASH_RETURN values must be at least negative one")
    if parameter is HistoricalExperimentGridParameter.RISK_AVERSION and decimal < _ZERO:
        raise error("RISK_AVERSION values must be nonnegative")


def _exact_decimal(
    value: GridValue, parameter: HistoricalExperimentGridParameter
) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise HistoricalExperimentGridValueError(
            f"{parameter.value} values must be exact finite Decimal values"
        )
    return value


def _typed_value(value: GridValue | Enum) -> str:
    if value is None:
        return "NULL|"
    if type(value) is bool:
        return f"BOOLEAN|{'true' if value else 'false'}"
    if type(value) is int:
        return f"INTEGER|{value}"
    if type(value) is Decimal and value.is_finite():
        return f"DECIMAL|{canonical_decimal(value)}"
    if isinstance(value, Enum):
        return f"ENUM|{value.value}"
    raise HistoricalExperimentGridValueError(
        "value has no supported canonical representation"
    )


def _display_value(value: GridValue) -> str:
    return _typed_value(value).split("|", maxsplit=1)[1] or "NULL"


def _generated_name(
    base: HistoricalExperimentVariant,
    assignments: tuple[HistoricalExperimentGridAssignment, ...],
) -> str:
    suffix = ", ".join(
        f"{item.parameter.value}={_display_value(item.value)}" for item in assignments
    )
    return f"{base.name} | {suffix}"


def _generated_variant_id(
    specification: HistoricalExperimentGridSpecification,
    ordinal: int,
    assignments: tuple[HistoricalExperimentGridAssignment, ...],
) -> UUID:
    return _id(
        "generated-variant",
        str(specification.specification_id),
        *canonical_variant_material(specification.base_variant),
        str(specification.base_variant.variant_id),
        str(ordinal),
        *_assignment_material(assignments),
    )


def _result_id(
    specification: HistoricalExperimentGridSpecification,
    generated: tuple[HistoricalExperimentGeneratedVariant, ...],
) -> UUID:
    material = [
        str(specification.specification_id),
        *canonical_variant_material(specification.base_variant),
    ]
    for axis in specification.axes:
        material.append(axis.parameter.value)
        material.extend(_typed_value(value) for value in axis.values)
    material.append(str(specification.maximum_variant_count))
    material.extend(f"{item.key}={item.value}" for item in specification.metadata)
    for row in generated:
        material.append(str(row.variant.variant_id))
        material.extend(_assignment_material(row.assignments))
    return _id("result", *material)


def _assignment_material(
    assignments: tuple[HistoricalExperimentGridAssignment, ...],
) -> tuple[str, ...]:
    return tuple(
        material
        for item in assignments
        for material in (item.parameter.value, _typed_value(item.value))
    )


def _specification_invariant(
    specification: HistoricalExperimentGridSpecification,
) -> tuple[object, ...]:
    return (
        specification.specification_id,
        id(specification.base_variant),
        canonical_variant_material(specification.base_variant),
        specification.axes,
        specification.maximum_variant_count,
        specification.metadata,
    )


def _id(stage: str, *material: str) -> UUID:
    return uuid5(_NAMESPACE, "|".join((_VERSION, stage, *material)))
