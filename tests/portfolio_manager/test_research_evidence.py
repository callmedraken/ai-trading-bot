"""Focused synthetic/adversarial checks for PM2C evidence contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.domain import Symbol
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
)
from trading_bot.portfolio_manager.research_evidence import (
    AvailabilityReason,
    AvailabilityStatus,
    DerivedFeature,
    EvidenceContractError,
    EvidenceDependency,
    EvidenceGraph,
    EvidenceOutcome,
    EvidenceSubject,
    EvidenceTimeframe,
    EvidenceTimeframeKind,
    SnapshotMode,
    SourceFact,
    VersionAsOfWitness,
    momentum_12m_minus_1m,
    ratio,
)

BASE = datetime(2025, 1, 2, 15, tzinfo=UTC)
SUBJECT = EvidenceSubject(
    symbol=Symbol("AAPL"),
    issuer_id="issuer-a",
    security_id="security-a",
    share_class="common",
)
PERIOD = EvidenceTimeframe(
    EvidenceTimeframeKind.PERIOD,
    datetime(2024, 1, 1, tzinfo=UTC),
    datetime(2024, 12, 31, tzinfo=UTC),
)


def _catalog() -> tuple[ResearchCatalog, CatalogEntry, CatalogEntry]:
    raw = CatalogEntry(
        "v1",
        "raw.price.close.unadjusted",
        "1",
        "valuation",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "currency/share", "USD"),
        basis=EvidenceBasis("XNYS"),
    )
    derived = CatalogEntry(
        "v1",
        "synthetic.return",
        "1",
        "momentum",
        EntryKind.DERIVED,
        FormulaRef("simple-return", "1"),
        (
            InputSpec(
                raw.key,
                raw.version,
                "prior",
                entry_id=raw.entry_id,
                value_spec=raw.value_spec,
                basis=raw.basis,
            ),
        ),
        value_spec=ValueSpec(ValueKind.DECIMAL, "fraction"),
        basis=EvidenceBasis("XNYS"),
    )
    return ResearchCatalog("v1", (raw, derived)), raw, derived


def _fact(
    entry: CatalogEntry,
    value: Decimal | None = Decimal("100"),
    *,
    source_version: str = "provider-v1",
    status: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
    reasons: tuple[AvailabilityReason, ...] = (),
    available_at: datetime | None = BASE,
    observed_at: datetime | None = BASE,
    source_record_id: str | None = "record-1",
    source_content_digest: str | None = "semantic-digest-1",
    freshness_rule: str | None = None,
    timeframe: EvidenceTimeframe | None = PERIOD,
    **kwargs: object,
) -> SourceFact:
    return SourceFact(
        entry,
        SUBJECT,
        "synthetic-provider",
        source_version,
        EvidenceOutcome(status, value, reasons, freshness_rule=freshness_rule),
        timeframe,
        available_at,
        observed_at,
        source_record_id=source_record_id,
        source_content_digest=source_content_digest,
        **kwargs,
    )


def _feature(
    entry: CatalogEntry,
    source: SourceFact,
    *,
    value: Decimal | None = Decimal("0.1"),
    available_at: datetime | None = BASE,
    status: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
    reasons: tuple[AvailabilityReason, ...] = (),
) -> DerivedFeature:
    return DerivedFeature(
        entry,
        SUBJECT,
        (EvidenceDependency(source.evidence_id, "prior"),),
        EvidenceOutcome(status, value, reasons),
        available_at,
        BASE,
        PERIOD,
    )


def test_all_availability_states_and_zero_remain_typed() -> None:
    _, raw, _ = _catalog()
    zero = _fact(raw, Decimal("0"))
    assert zero.value == Decimal("0")
    states = (
        (AvailabilityStatus.MISSING, AvailabilityReason.MISSING_EXPECTED_PERIOD),
        (AvailabilityStatus.STALE, AvailabilityReason.STALE_NAMED_RULE),
        (AvailabilityStatus.UNSUPPORTED, AvailabilityReason.UNSUPPORTED_DENOMINATOR),
        (
            AvailabilityStatus.NOT_YET_AVAILABLE,
            AvailabilityReason.NOT_YET_AVAILABLE_PUBLICATION,
        ),
        (AvailabilityStatus.INVALID, AvailabilityReason.INVALID_TIMING),
    )
    for status, reason in states:
        kwargs = (
            {"freshness_rule": "named-rule"}
            if status is AvailabilityStatus.STALE
            else {}
        )
        unavailable = _fact(
            raw,
            None,
            status=status,
            reasons=(reason,),
            available_at=None,
            observed_at=None,
            source_record_id=None,
            source_content_digest=None,
            **kwargs,
        )
        assert unavailable.value is None
    candidates = (
        uuid5(NAMESPACE_URL, "candidate-a"),
        uuid5(NAMESPACE_URL, "candidate-b"),
    )
    conflict = SourceFact(
        raw,
        SUBJECT,
        "synthetic-provider",
        "provider-v1",
        EvidenceOutcome(
            AvailabilityStatus.CONFLICTED,
            reasons=(AvailabilityReason.CONFLICT_CANDIDATE_IDENTITIES,),
            conflict_candidate_ids=candidates,
        ),
    )
    assert conflict.outcome.conflict_candidate_ids == candidates


def test_identity_excludes_receipt_path_but_binds_value_and_version() -> None:
    _, raw, _ = _catalog()
    original = _fact(raw)
    replay = replace(
        original, source_path=r"F:\cache\different", receipt_annotation="replayed"
    )
    assert replay.evidence_id == original.evidence_id
    assert (
        replace(original, source_version="provider-v2").evidence_id
        != original.evidence_id
    )
    assert (
        replace(
            original,
            outcome=EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("101")),
        ).evidence_id
        != original.evidence_id
    )


def test_source_fact_rejects_nonfinite_float_and_impossible_timing() -> None:
    _, raw, _ = _catalog()
    with pytest.raises(EvidenceContractError):
        _fact(raw, Decimal("NaN"))
    with pytest.raises(EvidenceContractError):
        _fact(raw, 1.25)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="observed_at"):
        _fact(raw, observed_at=BASE - timedelta(days=1))


def test_operational_late_receipt_and_historical_witness_are_distinct() -> None:
    _, raw, _ = _catalog()
    late = _fact(raw, observed_at=BASE + timedelta(days=1))
    with pytest.raises(EvidenceContractError, match="receipt"):
        late.validate_cutoff(BASE, SnapshotMode.OPERATIONAL)
    witness = VersionAsOfWitness(
        late.evidence_id,
        late.source_version,
        late.available_at or BASE,
        late.source_record_id or "",
        late.source_content_digest or "",
        late.source_identity,
        late.revision_id,
        late.effective_at,
    )
    late = replace(late, as_of_witness=witness)
    late.validate_cutoff(BASE, SnapshotMode.HISTORICAL_RECONSTRUCTION)
    with pytest.raises(EvidenceContractError):
        late.validate_cutoff(BASE, SnapshotMode.OPERATIONAL)


def test_historical_witness_rejects_version_or_publication_mismatch() -> None:
    _, raw, _ = _catalog()
    original = _fact(raw)
    witness = VersionAsOfWitness(
        original.evidence_id,
        "wrong-version",
        original.available_at or BASE,
        original.source_record_id or "",
        original.source_content_digest or "",
        original.source_identity,
    )
    assert not witness.proves(original, BASE)


def test_graph_requires_exact_catalog_inputs_and_orders_closure() -> None:
    catalog, raw, derived_entry = _catalog()
    first = _fact(raw)
    derived = _feature(derived_entry, first)
    graph = EvidenceGraph(catalog, (first, derived))
    assert graph.node_for(derived.evidence_id) is derived
    assert graph.source_closure(derived.evidence_id) == (first.evidence_id,)
    assert graph.edges[0].role == "prior"

    wrong_role = replace(
        derived,
        dependencies=(EvidenceDependency(first.evidence_id, "wrong-role"),),
    )
    with pytest.raises(EvidenceContractError, match="role"):
        EvidenceGraph(catalog, (first, wrong_role))


def test_graph_rejects_late_or_unavailable_dependencies() -> None:
    catalog, raw, derived_entry = _catalog()
    late = _fact(
        raw,
        available_at=BASE + timedelta(hours=1),
        observed_at=BASE + timedelta(hours=1),
    )
    with pytest.raises(EvidenceContractError, match="precedes"):
        EvidenceGraph(catalog, (late, _feature(derived_entry, late)))
    missing = _fact(
        raw,
        None,
        status=AvailabilityStatus.MISSING,
        reasons=(AvailabilityReason.MISSING_EXPECTED_ANCHOR,),
        available_at=None,
        observed_at=None,
        source_record_id=None,
        source_content_digest=None,
    )
    blocked = _feature(
        derived_entry,
        missing,
        value=None,
        status=AvailabilityStatus.MISSING,
        reasons=(AvailabilityReason.MISSING_REQUIRED_INPUT,),
        available_at=None,
    )
    assert (
        EvidenceGraph(catalog, (missing, blocked)).node_for(blocked.evidence_id)
        is blocked
    )
    with pytest.raises(EvidenceContractError):
        EvidenceGraph(catalog, (missing, _feature(derived_entry, missing)))


def test_momentum_anchor_and_denominator_domain_are_fail_closed() -> None:
    assert ratio(Decimal("10"), Decimal("2")) == Decimal("5.000000000000")
    assert ratio(Decimal("10"), Decimal("0")) is None
    assert ratio(Decimal("-10"), Decimal("2")) == Decimal("-5.000000000000")
    assert momentum_12m_minus_1m(Decimal("100"), Decimal("110")) == Decimal(
        "0.100000000000"
    )


def test_pm1_firewall_is_structural() -> None:
    catalog, raw, derived_entry = _catalog()
    source = _fact(raw)
    derived = _feature(derived_entry, source)
    graph = EvidenceGraph(catalog, (source, derived))
    assert not hasattr(graph, "market_signal")
    assert not hasattr(graph, "recommendation")
    assert not hasattr(derived, "expected_return")
    assert not hasattr(derived, "target_weight")


def test_graph_preserves_four_discrete_quarter_roles_and_rejects_cumulative_swap() -> (
    None
):
    raws = tuple(
        CatalogEntry(
            "v1",
            f"raw.fiscal.quarter.eps.discrete.q{index}",
            "1",
            "growth",
            EntryKind.RAW,
            value_spec=ValueSpec(ValueKind.DECIMAL, "USD/share"),
            basis=EvidenceBasis("FISCAL"),
        )
        for index in range(1, 5)
    )
    ttm = CatalogEntry(
        "v1",
        "growth.synthetic.ttm_eps",
        "1",
        "growth",
        EntryKind.DERIVED,
        FormulaRef("sum-four-discrete-eps", "1"),
        tuple(
            InputSpec(
                raw.key,
                raw.version,
                f"quarter-{index}",
                entry_id=raw.entry_id,
                value_spec=raw.value_spec,
                basis=raw.basis,
            )
            for index, raw in enumerate(raws, 1)
        ),
        value_spec=ValueSpec(ValueKind.DECIMAL, "USD/share"),
        basis=EvidenceBasis("FISCAL"),
    )
    catalog = ResearchCatalog("v1", (*raws, ttm))
    facts = tuple(_fact(raw, Decimal(str(index))) for index, raw in enumerate(raws, 1))
    derived = DerivedFeature(
        ttm,
        SUBJECT,
        tuple(
            EvidenceDependency(item.evidence_id, f"quarter-{index}")
            for index, item in enumerate(facts, 1)
        ),
        EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("10")),
        BASE,
        BASE,
        PERIOD,
    )
    assert len(EvidenceGraph(catalog, (*facts, derived)).edges) == 4

    cumulative = replace(
        derived,
        dependencies=(
            EvidenceDependency(facts[0].evidence_id, "quarter-1"),
            EvidenceDependency(facts[1].evidence_id, "quarter-2"),
            EvidenceDependency(facts[2].evidence_id, "quarter-3"),
            EvidenceDependency(facts[2].evidence_id, "quarter-4"),
        ),
    )
    with pytest.raises(EvidenceContractError, match="substitution|repeated"):
        EvidenceGraph(catalog, (*facts, cumulative))


def test_graph_rejects_anchor_basis_and_currency_splice() -> None:
    raw_usd = CatalogEntry(
        "v1",
        "raw.price.anchor.usd",
        "1",
        "momentum",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "USD/share", "USD"),
        basis=EvidenceBasis("XNYS", AdjustmentBasis.TOTAL_RETURN),
    )
    raw_eur = CatalogEntry(
        "v1",
        "raw.price.anchor.eur",
        "1",
        "momentum",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "EUR/share", "EUR"),
        basis=EvidenceBasis("XNYS", AdjustmentBasis.TOTAL_RETURN),
    )
    derived = CatalogEntry(
        "v1",
        "momentum.synthetic",
        "1",
        "momentum",
        EntryKind.DERIVED,
        FormulaRef("two-anchor", "1"),
        (
            InputSpec(
                raw_usd.key,
                raw_usd.version,
                "minus-1m",
                entry_id=raw_usd.entry_id,
                value_spec=raw_usd.value_spec,
                basis=raw_usd.basis,
                session_anchor="expected-close",
            ),
            InputSpec(
                raw_usd.key,
                raw_usd.version,
                "minus-12m",
                entry_id=raw_usd.entry_id,
                value_spec=raw_usd.value_spec,
                basis=raw_usd.basis,
                session_anchor="expected-close",
                allow_repeat=True,
            ),
        ),
        value_spec=ValueSpec(ValueKind.DECIMAL, "fraction"),
        basis=EvidenceBasis("XNYS", AdjustmentBasis.TOTAL_RETURN),
    )
    catalog = ResearchCatalog("v1", (raw_usd, raw_eur, derived))
    first = _fact(
        raw_usd,
        timeframe=EvidenceTimeframe(
            EvidenceTimeframeKind.SESSION,
            BASE - timedelta(days=1),
            BASE - timedelta(days=1),
            "wrong-close",
        ),
    )
    second = _fact(
        raw_usd,
        timeframe=EvidenceTimeframe(
            EvidenceTimeframeKind.SESSION,
            BASE - timedelta(days=12),
            BASE - timedelta(days=12),
            "expected-close",
        ),
    )
    feature_with_wrong_anchor = DerivedFeature(
        derived,
        SUBJECT,
        (
            EvidenceDependency(first.evidence_id, "minus-1m"),
            EvidenceDependency(second.evidence_id, "minus-12m"),
        ),
        EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("0.1")),
        BASE,
        BASE,
        PERIOD,
    )
    with pytest.raises(EvidenceContractError, match="anchor"):
        EvidenceGraph(catalog, (first, second, feature_with_wrong_anchor))

    mixed_entry = replace(
        derived,
        key="momentum.synthetic.mixed",
        inputs=(
            derived.inputs[0],
            InputSpec(
                raw_eur.key,
                raw_eur.version,
                "minus-12m",
                entry_id=raw_eur.entry_id,
                value_spec=raw_eur.value_spec,
                basis=raw_eur.basis,
                session_anchor="expected-close",
            ),
        ),
    )
    mixed_catalog = ResearchCatalog("v1", (raw_usd, raw_eur, mixed_entry))
    first_expected = replace(
        first,
        timeframe=EvidenceTimeframe(
            EvidenceTimeframeKind.SESSION,
            BASE - timedelta(days=1),
            BASE - timedelta(days=1),
            "expected-close",
        ),
    )
    eur = _fact(raw_eur, Decimal("100"))
    mixed = replace(
        feature_with_wrong_anchor,
        entry=mixed_entry,
        dependencies=(
            EvidenceDependency(first_expected.evidence_id, "minus-1m"),
            EvidenceDependency(eur.evidence_id, "minus-12m"),
        ),
    )
    with pytest.raises(EvidenceContractError, match="currency|basis"):
        EvidenceGraph(mixed_catalog, (first_expected, eur, mixed))


def test_graph_duplicate_edge_requires_every_reuse_role_to_allow_repeat() -> None:
    catalog, raw, _ = _catalog()
    duplicate_entry = CatalogEntry(
        "v1",
        "synthetic.duplicate",
        "1",
        "momentum",
        EntryKind.DERIVED,
        FormulaRef("difference", "1"),
        (
            InputSpec(raw.key, raw.version, "left", entry_id=raw.entry_id),
            InputSpec(
                raw.key,
                raw.version,
                "right",
                allow_repeat=True,
                entry_id=raw.entry_id,
            ),
        ),
        value_spec=ValueSpec(ValueKind.DECIMAL, "fraction"),
    )
    catalog = ResearchCatalog("v1", (*catalog.entries, duplicate_entry))
    source = _fact(raw)
    duplicate = DerivedFeature(
        duplicate_entry,
        SUBJECT,
        (
            EvidenceDependency(source.evidence_id, "left"),
            EvidenceDependency(source.evidence_id, "right"),
        ),
        EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("0")),
        BASE,
        BASE,
        PERIOD,
    )
    with pytest.raises(EvidenceContractError, match="repeated"):
        EvidenceGraph(catalog, (source, duplicate))

    allowed_entry = replace(
        duplicate_entry,
        key="synthetic.duplicate.allowed",
        inputs=tuple(
            replace(item, allow_repeat=True) for item in duplicate_entry.inputs
        ),
    )
    allowed_catalog = ResearchCatalog("v1", (*catalog.entries, allowed_entry))
    allowed = replace(duplicate, entry=allowed_entry)
    assert EvidenceGraph(allowed_catalog, (source, allowed)).edges


def test_graph_accepts_explicitly_declared_benchmark_subject_only() -> None:
    catalog, raw, derived = _catalog()
    benchmark = EvidenceSubject(scope="benchmark", security_id="SPY")
    declared_input = replace(derived.inputs[0], subject_id=benchmark.subject_id)
    declared_entry = replace(
        derived, key="synthetic.benchmark-return", inputs=(declared_input,)
    )
    catalog = ResearchCatalog("v1", (raw, declared_entry))
    benchmark_fact = SourceFact(
        raw,
        benchmark,
        "synthetic-provider",
        "provider-v1",
        EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("100")),
        PERIOD,
        BASE,
        BASE,
        source_record_id="record-benchmark",
        source_content_digest="digest-benchmark",
    )
    benchmark_feature = DerivedFeature(
        declared_entry,
        SUBJECT,
        (EvidenceDependency(benchmark_fact.evidence_id, "prior"),),
        EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("0.1")),
        BASE,
        BASE,
        PERIOD,
    )
    assert EvidenceGraph(catalog, (benchmark_fact, benchmark_feature)).edges

    wrong_subject = replace(
        benchmark_fact, subject=EvidenceSubject(scope="benchmark", security_id="QQQ")
    )
    wrong_feature = replace(
        benchmark_feature,
        dependencies=(EvidenceDependency(wrong_subject.evidence_id, "prior"),),
    )
    with pytest.raises(EvidenceContractError, match="subject"):
        EvidenceGraph(catalog, (wrong_subject, wrong_feature))
