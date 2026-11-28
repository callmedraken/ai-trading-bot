"""Focused synthetic contracts for the PM2C typed research catalog."""

from decimal import Decimal, localcontext
from uuid import UUID

import pytest

from trading_bot.portfolio_manager.research_catalog import (
    AdjustmentBasis,
    CatalogEntry,
    EntryKind,
    EvidenceBasis,
    FormulaRef,
    InputSpec,
    ResearchCatalog,
    ValueKind,
    ValueSpec,
    WindowSpec,
    momentum_12m_minus_1m,
    ratio,
    research_identity,
    simple_return,
)


def _raw(
    key: str = "raw.price.close.unadjusted",
    *,
    value_spec: ValueSpec | None = None,
    basis: EvidenceBasis | None = None,
) -> CatalogEntry:
    return CatalogEntry(
        "v1",
        key,
        "1",
        "valuation",
        EntryKind.RAW,
        value_spec=value_spec or ValueSpec(ValueKind.DECIMAL, "currency/share", "USD"),
        basis=basis
        or EvidenceBasis("XNYS", AdjustmentBasis.UNADJUSTED, reporting_basis="PIT"),
    )


def _derived(raw: CatalogEntry, *, allow_repeat: bool = False) -> CatalogEntry:
    value_spec = ValueSpec(ValueKind.DECIMAL, "fraction")
    return CatalogEntry(
        "v1",
        "valuation.synthetic_ratio",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("ratio", "v1"),
        (
            InputSpec(
                raw.key,
                raw.version,
                "numerator",
                allow_repeat=allow_repeat,
                entry_id=raw.entry_id,
                value_spec=raw.value_spec,
                basis=raw.basis,
            ),
        ),
        value_spec=value_spec,
        window=WindowSpec("single", complete=True),
        basis=EvidenceBasis("XNYS", AdjustmentBasis.UNADJUSTED),
        availability_rules=("all_inputs_available",),
        domain_rules=("positive_denominator",),
    )


def test_catalog_binds_exact_registered_input_entry_and_is_immutable() -> None:
    raw = _raw()
    derived = _derived(raw)
    catalog = ResearchCatalog("v1", (raw, derived))

    assert isinstance(catalog.catalog_id, UUID)
    assert catalog.lookup(raw.key, raw.version) is raw
    assert catalog.lookup("valuation.synthetic_ratio") is derived
    assert catalog.lookup(derived.key).entry_id == derived.entry_id
    with pytest.raises(KeyError):
        catalog.lookup("unknown")

    with pytest.raises((AttributeError, TypeError)):
        catalog.version = "v2"  # type: ignore[misc]


def test_input_subject_id_is_typed_and_changes_catalog_entry_identity() -> None:
    raw = _raw()
    plain = _derived(raw)
    benchmark_input = InputSpec(
        raw.key,
        raw.version,
        "benchmark",
        entry_id=raw.entry_id,
        subject_id=UUID(int=2),
        value_spec=raw.value_spec,
        basis=raw.basis,
    )
    benchmark = CatalogEntry(
        "v1",
        "valuation.benchmark_ratio",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("ratio", "v1"),
        (benchmark_input,),
    )
    assert benchmark.entry_id != plain.entry_id
    assert ResearchCatalog("v1", (raw, benchmark)).lookup(benchmark.key) is benchmark
    with pytest.raises(TypeError):
        InputSpec(raw.key, raw.version, "benchmark", subject_id="benchmark")  # type: ignore[arg-type]


def test_catalog_rejects_id_version_value_or_basis_substitution() -> None:
    raw = _raw()
    wrong_id = InputSpec(raw.key, raw.version, "numerator", entry_id=UUID(int=1))
    entry = CatalogEntry(
        "v1",
        "valuation.bad_ratio",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("ratio", "v1"),
        (wrong_id,),
    )
    with pytest.raises(ValueError, match="entry ID"):
        ResearchCatalog("v1", (raw, entry))

    wrong_version = InputSpec(raw.key, "2", "numerator")
    entry = CatalogEntry(
        "v1",
        "valuation.bad_version",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("ratio", "v1"),
        (wrong_version,),
    )
    with pytest.raises(ValueError, match="does not resolve"):
        ResearchCatalog("v1", (raw, entry))

    wrong_spec = InputSpec(
        raw.key,
        raw.version,
        "numerator",
        value_spec=ValueSpec(ValueKind.DECIMAL, "shares"),
    )
    entry = CatalogEntry(
        "v1",
        "valuation.bad_spec",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("ratio", "v1"),
        (wrong_spec,),
    )
    with pytest.raises(ValueError, match="value specification"):
        ResearchCatalog("v1", (raw, entry))


def test_catalog_allows_same_key_for_distinct_ordered_roles() -> None:
    raw = _raw()
    entry = CatalogEntry(
        "v1",
        "valuation.duplicate",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("difference", "v1"),
        (
            InputSpec(raw.key, raw.version, "left", entry_id=raw.entry_id),
            InputSpec(raw.key, raw.version, "right", entry_id=raw.entry_id),
        ),
    )
    assert ResearchCatalog("v1", (raw, entry)).lookup(entry.key) is entry

    with pytest.raises(ValueError, match="input roles"):
        CatalogEntry(
            "v1",
            "valuation.duplicate_role",
            "1",
            "valuation",
            EntryKind.DERIVED,
            FormulaRef("difference", "v1"),
            (
                InputSpec(raw.key, raw.version, "same", entry_id=raw.entry_id),
                InputSpec(
                    raw.key,
                    raw.version,
                    "same",
                    allow_repeat=True,
                    entry_id=raw.entry_id,
                ),
            ),
        )

    repeated_role = CatalogEntry(
        "v1",
        "valuation.duplicate_allowed",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("difference", "v1"),
        (
            InputSpec(
                raw.key, raw.version, "same", allow_repeat=True, entry_id=raw.entry_id
            ),
        ),
    )
    assert (
        ResearchCatalog("v1", (raw, repeated_role)).lookup(repeated_role.key)
        is repeated_role
    )


def test_catalog_rejects_cycles_and_raw_formula_text() -> None:
    with pytest.raises(ValueError, match="RAW entries"):
        CatalogEntry(
            "v1", "raw.bad", "1", "valuation", EntryKind.RAW, FormulaRef("x", "1")
        )

    # The two edges are intentionally supplied without entry IDs first; the
    # registry check reaches exact key/version resolution before cycle walking.
    left = CatalogEntry(
        "v1",
        "derived.left",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("identity", "1"),
        (InputSpec("derived.right", "1", "right"),),
    )
    right = CatalogEntry(
        "v1",
        "derived.right",
        "1",
        "valuation",
        EntryKind.DERIVED,
        FormulaRef("identity", "1"),
        (InputSpec("derived.left", "1", "left"),),
    )
    with pytest.raises(ValueError, match="cycle"):
        ResearchCatalog("v1", (left, right))


@pytest.mark.parametrize(
    ("spec", "value", "expected"),
    [
        (ValueSpec(ValueKind.DECIMAL, "USD"), Decimal("0"), Decimal("0")),
        (ValueSpec(ValueKind.INTEGER), 4, 4),
        (ValueSpec(ValueKind.COUNT), 0, 0),
        (
            ValueSpec(ValueKind.IDENTIFIER_VECTOR),
            ("subject", "peer-1"),
            ("subject", "peer-1"),
        ),
        (
            ValueSpec(ValueKind.DECIMAL_VECTOR),
            (Decimal("1"), Decimal("-2")),
            (Decimal("1"), Decimal("-2")),
        ),
        (ValueSpec(ValueKind.BOOLEAN), True, True),
    ],
)
def test_value_specs_preserve_zero_order_and_typed_vectors(
    spec, value, expected
) -> None:
    assert spec.validate(value) == expected


def test_value_specs_reject_bool_as_count_and_nonfinite_decimal() -> None:
    with pytest.raises(TypeError):
        ValueSpec(ValueKind.COUNT).validate(True)
    with pytest.raises(ValueError):
        ValueSpec(ValueKind.DECIMAL).validate(Decimal("NaN"))
    with pytest.raises(TypeError):
        ValueSpec(ValueKind.IDENTIFIER_VECTOR).validate("not-a-vector")


def test_semantic_tokens_reject_prose_paths_and_noncanonical_currency_labels() -> None:
    with pytest.raises(TypeError):
        ValueSpec(ValueKind.DECIMAL, validation_rules=("provider prose",))
    with pytest.raises(TypeError):
        ValueSpec(ValueKind.IDENTIFIER).validate("provider prose")
    with pytest.raises(TypeError):
        ValueSpec(ValueKind.DECIMAL, unit="C:/tmp")
    with pytest.raises(TypeError):
        ValueSpec(ValueKind.DECIMAL, unit="currency/../share")
    with pytest.raises(ValueError):
        ValueSpec(ValueKind.DECIMAL, currency="Usd")
    assert ValueSpec(ValueKind.DECIMAL, unit="currency/share").unit == "currency/share"

    raw = _raw()
    with pytest.raises(TypeError):
        CatalogEntry(
            "v1",
            "valuation.bad_rules",
            "1",
            "valuation",
            EntryKind.DERIVED,
            FormulaRef("ratio", "v1"),
            (InputSpec(raw.key, raw.version, "numerator", entry_id=raw.entry_id),),
            availability_rules=("provider prose",),
        )


def test_semantic_identity_is_framed_and_does_not_accept_incidental_bytes() -> None:
    first = research_identity("fact", "provider", "v1", Decimal("1.00"))
    equivalent = research_identity("fact", "provider", "v1", Decimal("1.0"))
    changed = research_identity("fact", "provider", "v2", Decimal("1.00"))
    assert first == equivalent
    assert first != changed
    with pytest.raises(TypeError):
        research_identity("fact", b"serialized bytes")


def test_ratio_and_returns_are_context_independent_and_round_once_half_even() -> None:
    with localcontext() as context:
        context.prec = 3
        low_precision = ratio(Decimal("1"), Decimal("3"))
    with localcontext() as context:
        context.prec = 50
        high_precision = ratio(Decimal("1"), Decimal("3"))
    assert low_precision == high_precision == Decimal("0.333333333333")
    assert ratio(Decimal("1"), Decimal("0")) is None
    assert ratio(Decimal("-2"), Decimal("4")) == Decimal("-0.5")
    assert simple_return(Decimal("100"), Decimal("110")) == Decimal("0.1")
    assert simple_return(Decimal("0"), Decimal("110")) is None


def test_momentum_uses_only_two_named_anchors_not_current_close_or_return_difference():
    result = momentum_12m_minus_1m(Decimal("100"), Decimal("120"))
    assert result == Decimal("0.2")
    # A current close of 200 is deliberately unavailable to the helper and
    # cannot change the golden two-anchor result.
    assert result != simple_return(Decimal("100"), Decimal("200"))
    assert result != (
        simple_return(Decimal("100"), Decimal("120"))
        - simple_return(Decimal("120"), Decimal("200"))
    )
