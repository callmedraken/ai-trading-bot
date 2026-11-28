"""Typed, deterministic research catalog contracts.

This module deliberately describes research evidence.  It does not acquire
data, evaluate arbitrary formula text, score securities, or create a PM1
recommendation.  A catalog entry is a versioned declaration whose inputs must
resolve to the exact registered catalog entries before it can be used by a
future evidence layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid5

from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.models import (
    canonical_decimal,
    decimal_subtract,
)

_IDENTITY_NAMESPACE = UUID("f1b8fb6a-0e3d-5e24-8b11-524b2ce93386")
_ZERO = Decimal("0")
_ROUNDING_PLACES = 12


class EntryKind(StrEnum):
    """Whether a catalog entry names source evidence or a derivation."""

    RAW = "RAW"
    DERIVED = "DERIVED"


class ValueKind(StrEnum):
    """Closed set of values admitted by a catalog entry."""

    DECIMAL = "DECIMAL"
    INTEGER = "INTEGER"
    COUNT = "COUNT"
    IDENTIFIER = "IDENTIFIER"
    IDENTIFIER_VECTOR = "IDENTIFIER_VECTOR"
    DECIMAL_VECTOR = "DECIMAL_VECTOR"
    BOOLEAN = "BOOLEAN"


class AdjustmentBasis(StrEnum):
    """Price/action adjustment basis, intentionally not an inferred policy."""

    UNADJUSTED = "UNADJUSTED"
    SPLIT_ONLY = "SPLIT_ONLY"
    TOTAL_RETURN = "TOTAL_RETURN"


@dataclass(frozen=True, slots=True)
class FormulaRef:
    """A fixed, versioned formula identity; it is not executable source text."""

    formula_id: str
    version: str

    def __post_init__(self) -> None:
        _require_token(self.formula_id, "formula_id")
        _require_token(self.version, "formula version")

    @property
    def key(self) -> str:
        """Alias used by evidence records when they call the formula a key."""

        return self.formula_id


@dataclass(frozen=True, slots=True)
class EvidenceBasis:
    """Named calendar and adjustment/data basis of an evidence value."""

    calendar: str
    adjustment: AdjustmentBasis = AdjustmentBasis.UNADJUSTED
    data_basis: str | None = None
    reporting_basis: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.calendar, "calendar")
        if not isinstance(self.adjustment, AdjustmentBasis):
            raise TypeError("adjustment must be AdjustmentBasis")
        for name in ("data_basis", "reporting_basis"):
            value = getattr(self, name)
            if value is not None:
                _require_token(value, name)

    @property
    def basis(self) -> str:
        """Stable compact label for diagnostics and identity material."""

        labels = [self.adjustment.value]
        if self.data_basis is not None:
            labels.append(self.data_basis)
        if self.reporting_basis is not None:
            labels.append(self.reporting_basis)
        return "/".join(labels)


@dataclass(frozen=True, slots=True)
class ScopeSpec:
    """Typed scope anchor (security, universe, account, peer panel, and so on)."""

    name: str
    anchor: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.name, "scope name")
        if self.anchor is not None:
            _require_token(self.anchor, "scope anchor")


@dataclass(frozen=True, slots=True)
class PeriodSpec:
    """Relative economic-period declaration; it does not turn period end into PIT."""

    name: str
    relation: str | None = None
    anchor: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.name, "period name")
        for label in ("relation", "anchor"):
            value = getattr(self, label)
            if value is not None:
                _require_token(value, label)


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Window/anchor declaration, including complete-window requirements."""

    name: str
    length: int | None = None
    anchor: str | None = None
    complete: bool = True
    calendar: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.name, "window name")
        if self.length is not None and (
            isinstance(self.length, bool)
            or not isinstance(self.length, int)
            or self.length <= 0
        ):
            raise ValueError("window length must be a positive integer")
        if self.anchor is not None:
            _require_token(self.anchor, "window anchor")
        if not isinstance(self.complete, bool):
            raise TypeError("window complete must be a bool")
        if self.calendar is not None:
            _require_token(self.calendar, "window calendar")


@dataclass(frozen=True, slots=True)
class ValueSpec:
    """Exact value kind/unit/currency and its canonical validation contract."""

    kind: ValueKind
    unit: str | None = None
    currency: str | None = None
    element_kind: ValueKind | None = None
    validation_rules: tuple[str, ...] = ()
    canonical_form: str = "typed-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ValueKind):
            raise TypeError("value kind must be ValueKind")
        kind = self.kind
        if self.unit is not None:
            _require_label(self.unit, "unit")
        if self.currency is not None:
            _require_currency(self.currency)
        element_kind = self.element_kind
        if element_kind is not None:
            if not isinstance(element_kind, ValueKind):
                raise TypeError("element kind must be ValueKind")
        if kind is ValueKind.IDENTIFIER_VECTOR:
            if element_kind not in (None, ValueKind.IDENTIFIER):
                raise ValueError("identifier vectors require identifier elements")
        elif kind is ValueKind.DECIMAL_VECTOR:
            if element_kind not in (None, ValueKind.DECIMAL):
                raise ValueError("decimal vectors require Decimal elements")
        elif element_kind is not None:
            raise ValueError("element_kind is only valid for vector values")
        rules = _ordered_tuple(self.validation_rules, "validation_rules")
        for rule in rules:
            _require_token(rule, "validation rule")
        object.__setattr__(self, "validation_rules", rules)
        _require_token(self.canonical_form, "canonical_form")

    def validate(self, value: object) -> object:
        """Validate and return a canonical immutable value for this specification."""

        kind = self.kind
        if kind is ValueKind.DECIMAL:
            return _finite_decimal(value, "value")
        if kind in (ValueKind.INTEGER, ValueKind.COUNT):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{kind.value} values must be integers, not bool")
            if kind is ValueKind.COUNT and value < 0:
                raise ValueError("count values cannot be negative")
            return value
        if kind is ValueKind.BOOLEAN:
            if not isinstance(value, bool):
                raise TypeError("BOOLEAN values must be bool")
            return value
        if kind is ValueKind.IDENTIFIER:
            return _identifier(value)
        if kind is ValueKind.IDENTIFIER_VECTOR:
            values = _ordered_tuple(value, "identifier vector")
            normalized = tuple(_identifier(item) for item in values)
            if len(set(normalized)) != len(normalized):
                raise ValueError("identifier vectors must preserve unique IDs")
            return normalized
        if kind is ValueKind.DECIMAL_VECTOR:
            return tuple(
                _finite_decimal(item, f"decimal vector[{index}]")
                for index, item in enumerate(_ordered_tuple(value, "decimal vector"))
            )
        raise AssertionError(f"unhandled value kind: {kind!r}")

    def canonical_value(self, value: object) -> str:
        """Render a validated value without floats, repr, or ambient context."""

        value = self.validate(value)
        if isinstance(value, Decimal):
            return canonical_decimal(value)
        if isinstance(value, tuple):
            return _frame(tuple(_canonical_scalar(item) for item in value))
        return _canonical_scalar(value)


@dataclass(frozen=True, slots=True)
class InputSpec:
    """One ordered, role-labelled dependency of a catalog entry."""

    key: str
    version: str
    role: str
    allow_repeat: bool = False
    entry_id: UUID | None = None
    value_spec: ValueSpec | None = None
    basis: EvidenceBasis | None = None
    session_anchor: str | None = None
    fiscal_anchor: str | None = None
    target_anchor: str | None = None
    window_policy: str | None = None
    subject_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_token(self.key, "input key")
        _require_token(self.version, "input version")
        _require_token(self.role, "input role")
        if not isinstance(self.allow_repeat, bool):
            raise TypeError("allow_repeat must be a bool")
        if self.entry_id is not None and not isinstance(self.entry_id, UUID):
            raise TypeError("entry_id must be a UUID or None")
        if self.subject_id is not None and not isinstance(self.subject_id, UUID):
            raise TypeError("subject_id must be a UUID or None")
        if self.value_spec is not None and not isinstance(self.value_spec, ValueSpec):
            raise TypeError("input value_spec must be ValueSpec or None")
        if self.basis is not None and not isinstance(self.basis, EvidenceBasis):
            raise TypeError("input basis must be EvidenceBasis or None")
        for name in (
            "session_anchor",
            "fiscal_anchor",
            "target_anchor",
            "window_policy",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_token(value, name)
        anchor_count = sum(
            value is not None
            for value in (
                self.session_anchor,
                self.fiscal_anchor,
                self.target_anchor,
            )
        )
        if anchor_count > 1:
            raise ValueError("an input may declare only one anchor kind")

    @property
    def anchor(self) -> str | None:
        """Return the one explicitly declared temporal anchor, if any."""

        values = tuple(
            value
            for value in (
                self.session_anchor,
                self.fiscal_anchor,
                self.target_anchor,
            )
            if value is not None
        )
        return values[0] if values else None


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One immutable versioned catalog declaration."""

    catalog_version: str
    key: str
    version: str
    family: str
    kind: EntryKind
    formula: FormulaRef | None = None
    inputs: tuple[InputSpec, ...] = ()
    value_spec: ValueSpec = field(default_factory=lambda: ValueSpec(ValueKind.DECIMAL))
    scope: ScopeSpec = field(default_factory=lambda: ScopeSpec("security"))
    period_basis: PeriodSpec = field(
        default_factory=lambda: PeriodSpec("point_in_time")
    )
    window: WindowSpec = field(default_factory=lambda: WindowSpec("single"))
    basis: EvidenceBasis | None = None
    availability_rules: tuple[str, ...] = ()
    domain_rules: tuple[str, ...] = ()
    entry_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.catalog_version, "catalog_version")
        _require_token(self.key, "catalog key")
        _require_token(self.version, "catalog entry version")
        _require_token(self.family, "catalog family")
        if not isinstance(self.kind, EntryKind):
            raise TypeError("entry kind must be EntryKind")
        kind = self.kind
        formula = self.formula
        if formula is not None and not isinstance(formula, FormulaRef):
            raise TypeError("formula must be a FormulaRef or None")
        if kind is EntryKind.RAW and formula is not None:
            raise ValueError("RAW entries cannot carry a formula")
        if kind is EntryKind.DERIVED and formula is None:
            raise ValueError("DERIVED entries require a FormulaRef")
        inputs = _ordered_tuple(self.inputs, "inputs")
        if not all(isinstance(item, InputSpec) for item in inputs):
            raise TypeError("inputs must contain InputSpec values")
        if len({item.role for item in inputs}) != len(inputs):
            raise ValueError("input roles must be unique within an entry")
        if kind is EntryKind.RAW and inputs:
            raise ValueError("RAW entries cannot carry dependencies")
        if kind is EntryKind.DERIVED and not inputs:
            raise ValueError("DERIVED entries require at least one input")
        object.__setattr__(self, "inputs", inputs)
        if not isinstance(self.value_spec, ValueSpec):
            raise TypeError("value_spec must be ValueSpec")
        if not isinstance(self.scope, ScopeSpec):
            raise TypeError("scope must be ScopeSpec")
        if not isinstance(self.period_basis, PeriodSpec):
            raise TypeError("period_basis must be PeriodSpec")
        if not isinstance(self.window, WindowSpec):
            raise TypeError("window must be WindowSpec")
        if self.basis is not None and not isinstance(self.basis, EvidenceBasis):
            raise TypeError("basis must be EvidenceBasis or None")
        for name in ("availability_rules", "domain_rules"):
            rules = _ordered_tuple(getattr(self, name), name)
            for rule in rules:
                _require_token(rule, name[:-6] + " rule")
            object.__setattr__(self, name, rules)
        object.__setattr__(
            self,
            "entry_id",
            research_identity(
                "catalog-entry",
                self.catalog_version,
                self.key,
                self.version,
                self.family,
                self.kind.value,
                self.formula,
                self.inputs,
                self.value_spec,
                self.scope,
                self.period_basis,
                self.window,
                self.basis,
                self.availability_rules,
                self.domain_rules,
            ),
        )


@dataclass(frozen=True, slots=True)
class ResearchCatalog:
    """Immutable registry that proves every dependency is exact and registered."""

    version: str
    entries: tuple[CatalogEntry, ...]
    catalog_id: UUID = field(init=False)
    _by_key: Mapping[tuple[str, str], CatalogEntry] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        _require_token(self.version, "catalog version")
        entries = _ordered_tuple(self.entries, "entries")
        if not entries:
            raise ValueError("catalog must contain at least one entry")
        if not all(isinstance(item, CatalogEntry) for item in entries):
            raise TypeError("entries must contain CatalogEntry values")
        if any(item.catalog_version != self.version for item in entries):
            raise ValueError("every entry must use the catalog version")
        keys = tuple((item.key, item.version) for item in entries)
        if len(set(keys)) != len(keys):
            raise ValueError("catalog key/version pairs must be unique")
        by_key = dict(zip(keys, entries, strict=True))
        for entry in entries:
            for dependency in entry.inputs:
                lookup_key = (dependency.key, dependency.version)
                target = by_key.get(lookup_key)
                if target is None:
                    raise ValueError(
                        f"input {dependency.role!r} does not resolve to a registered "
                        f"entry: {dependency.key}@{dependency.version}"
                    )
                if (
                    dependency.entry_id is not None
                    and dependency.entry_id != target.entry_id
                ):
                    raise ValueError(
                        f"input {dependency.role!r} has an unregistered entry ID"
                    )
                if (
                    dependency.value_spec is not None
                    and dependency.value_spec != target.value_spec
                ):
                    raise ValueError(
                        f"input {dependency.role!r} value specification does not "
                        "match the registered entry"
                    )
                if dependency.basis is not None and dependency.basis != target.basis:
                    raise ValueError(
                        f"input {dependency.role!r} basis does not match the "
                        "registered entry"
                    )
        _validate_acyclic(entries, by_key)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "_by_key", MappingProxyType(by_key))
        object.__setattr__(
            self,
            "catalog_id",
            research_identity(
                "research-catalog",
                self.version,
                tuple(item.entry_id for item in entries),
            ),
        )

    def lookup(self, key: str, version: str | None = None) -> CatalogEntry:
        """Look up an exact key/version, rejecting ambiguous key-only lookup."""

        _require_token(key, "catalog key")
        if version is not None:
            _require_token(version, "catalog entry version")
            try:
                return self._by_key[(key, version)]
            except KeyError as error:
                raise KeyError(f"unknown catalog entry {key}@{version}") from error
        matches = tuple(
            item for (item_key, _), item in self._by_key.items() if item_key == key
        )
        if not matches:
            raise KeyError(f"unknown catalog key {key}")
        if len(matches) != 1:
            raise KeyError(f"catalog key {key} requires an exact version")
        return matches[0]

    def get(self, key: str, version: str | None = None) -> CatalogEntry | None:
        """Optional exact lookup convenience."""

        try:
            return self.lookup(key, version)
        except KeyError:
            return None


def research_identity(kind: str, *fields: object) -> UUID:
    """Return a stable UUID5 over framed, typed semantic fields.

    Only explicit scalar/container values and the typed contracts in this
    module are accepted.  In particular, floats, object ``repr`` values,
    filesystem paths, and serialized bytes cannot enter semantic identity.
    """

    _require_token(kind, "identity kind")
    material = ("research/v1", kind, *(_canonical_field(value) for value in fields))
    return uuid5(_IDENTITY_NAMESPACE, _frame(material))


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Calculate a supported positive-denominator ratio, rounded once.

    ``None`` represents known unsupported denominator math.  The caller's
    evidence layer maps that outcome to its typed ``UNSUPPORTED`` status.
    """

    numerator = _finite_decimal(numerator, "numerator")
    denominator = _finite_decimal(denominator, "denominator")
    if denominator <= _ZERO:
        return None
    return _rounded_fraction(numerator, denominator, _ROUNDING_PLACES)


def simple_return(old_value: Decimal, new_value: Decimal) -> Decimal | None:
    """Return ``new / old - 1`` with no float conversion or implicit carry."""

    old_value = _finite_decimal(old_value, "old_value")
    new_value = _finite_decimal(new_value, "new_value")
    if old_value <= _ZERO:
        return None
    return ratio(decimal_subtract(new_value, old_value), old_value)


def momentum_12m_minus_1m(old_12m: Decimal, new_1m: Decimal) -> Decimal | None:
    """Golden PM2B anchor: ``T[-1m] / T[-12m] - 1`` only.

    There is intentionally no current-close argument.  A caller must supply
    the two named anchors from the same admitted total-return series.
    """

    return simple_return(old_12m, new_1m)


def _rounded_fraction(numerator: Decimal, denominator: Decimal, places: int) -> Decimal:
    """Round an exact Decimal quotient half-even at ``places`` places."""

    numerator_int, numerator_den = numerator.as_integer_ratio()
    denominator_int, denominator_den = denominator.as_integer_ratio()
    # Decimal.as_integer_ratio() returns integer pairs whose quotient is the
    # exact Decimal value; retain the denominator signs in the fraction.
    rational_numerator = numerator_int * denominator_den
    rational_denominator = denominator_int * numerator_den
    if rational_denominator == 0:
        raise ZeroDivisionError("denominator must be nonzero")
    if rational_denominator < 0:
        rational_numerator = -rational_numerator
        rational_denominator = -rational_denominator
    scale = 10**places
    scaled = rational_numerator * scale
    sign = -1 if scaled < 0 else 1
    magnitude, remainder = divmod(abs(scaled), rational_denominator)
    doubled = remainder * 2
    if doubled > rational_denominator or (
        doubled == rational_denominator and magnitude % 2 == 1
    ):
        magnitude += 1
    coefficient = sign * magnitude
    if coefficient == 0:
        return _ZERO
    digits = Decimal(abs(coefficient)).as_tuple().digits
    return Decimal((1 if coefficient < 0 else 0, digits, -places))


def _validate_acyclic(
    entries: tuple[CatalogEntry, ...],
    by_key: Mapping[tuple[str, str], CatalogEntry],
) -> None:
    """Reject catalog dependency cycles while retaining ordered edge roles."""

    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(entry: CatalogEntry) -> None:
        key = (entry.key, entry.version)
        if key in visiting:
            raise ValueError(
                f"catalog dependency cycle includes {entry.key}@{entry.version}"
            )
        if key in visited:
            return
        visiting.add(key)
        for dependency in entry.inputs:
            visit(by_key[(dependency.key, dependency.version)])
        visiting.remove(key)
        visited.add(key)

    for entry in entries:
        visit(entry)


def _finite_decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


def _ordered_tuple(value: object, name: str) -> tuple[object, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be an ordered tuple or list")
    return tuple(value)


def _identifier(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str):
        raise TypeError("identifiers must be strings or UUIDs")
    _require_token(value, "identifier")
    return value


def _canonical_scalar(value: object) -> str:
    if isinstance(value, Decimal):
        return "decimal:" + canonical_decimal(value)
    if isinstance(value, bool):
        return "bool:true" if value else "bool:false"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, UUID):
        return "uuid:" + str(value)
    if isinstance(value, str):
        return "str:" + value
    raise TypeError(f"unsupported identity scalar {type(value).__name__}")


def _canonical_field(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, StrEnum):
        return f"enum:{type(value).__name__}:{value.value}"
    if isinstance(value, (str, int, bool, Decimal, UUID)):
        return _canonical_scalar(value)
    if isinstance(value, datetime):
        return "datetime:" + normalize_utc(value, "identity timestamp").isoformat()
    if isinstance(value, FormulaRef):
        return _frame(("FormulaRef", value.formula_id, value.version))
    if isinstance(value, EvidenceBasis):
        return _frame(
            (
                "EvidenceBasis",
                value.calendar,
                value.adjustment.value,
                value.data_basis or "",
                value.reporting_basis or "",
            )
        )
    if isinstance(value, ValueSpec):
        return _frame(
            (
                "ValueSpec",
                value.kind.value,
                value.unit or "",
                value.currency or "",
                value.element_kind.value if value.element_kind else "",
                value.canonical_form,
                *value.validation_rules,
            )
        )
    if isinstance(value, InputSpec):
        return _frame(
            (
                "InputSpec",
                value.key,
                value.version,
                value.role,
                "1" if value.allow_repeat else "0",
                str(value.entry_id) if value.entry_id else "",
                _canonical_field(value.value_spec),
                _canonical_field(value.basis),
                value.session_anchor or "",
                value.fiscal_anchor or "",
                value.target_anchor or "",
                value.window_policy or "",
                str(value.subject_id) if value.subject_id else "",
            )
        )
    if isinstance(value, ScopeSpec):
        return _frame(("ScopeSpec", value.name, value.anchor or ""))
    if isinstance(value, PeriodSpec):
        return _frame(
            ("PeriodSpec", value.name, value.relation or "", value.anchor or "")
        )
    if isinstance(value, WindowSpec):
        return _frame(
            (
                "WindowSpec",
                value.name,
                str(value.length) if value.length is not None else "",
                value.anchor or "",
                "1" if value.complete else "0",
                value.calendar or "",
            )
        )
    if isinstance(value, CatalogEntry):
        return "entry:" + str(value.entry_id)
    if isinstance(value, tuple):
        return _frame(tuple(_canonical_field(item) for item in value))
    if isinstance(value, list):
        return _frame(tuple(_canonical_field(item) for item in value))
    raise TypeError(f"unsupported identity field {type(value).__name__}")


def _frame(values: tuple[str, ...]) -> str:
    return "".join(f"{len(value)}:{value}" for value in values)


def _require_token(value: object, name: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character.isspace() for character in value)
        or "/" in value
        or "\\" in value
        or value in {".", ".."}
        or not (
            "A" <= value[0] <= "Z" or "a" <= value[0] <= "z" or "0" <= value[0] <= "9"
        )
        or any(
            not (
                "A" <= character <= "Z"
                or "a" <= character <= "z"
                or "0" <= character <= "9"
                or character in "._:-"
            )
            for character in value
        )
    ):
        raise TypeError(f"{name} must be a padded-free token")


def _require_currency(value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 3
        or any(not ("A" <= character <= "Z") for character in value)
    ):
        raise ValueError("currency must be a three-letter uppercase code")


def _require_label(value: object, name: str) -> None:
    """Validate a small semantic label such as ``currency/share``."""

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character.isspace() for character in value)
        or "\\" in value
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
    ):
        raise TypeError(f"{name} must be a semantic label")
    components = value.split("/")
    if any(":" in component for component in components):
        raise TypeError(f"{name} must not contain a drive-like component")
    for component in components:
        _require_token(component, name)


__all__ = [
    "AdjustmentBasis",
    "CatalogEntry",
    "EntryKind",
    "EvidenceBasis",
    "FormulaRef",
    "InputSpec",
    "PeriodSpec",
    "ResearchCatalog",
    "ScopeSpec",
    "ValueKind",
    "ValueSpec",
    "WindowSpec",
    "momentum_12m_minus_1m",
    "ratio",
    "research_identity",
    "simple_return",
]
