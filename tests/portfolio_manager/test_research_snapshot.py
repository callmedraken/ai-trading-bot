"""Focused synthetic/adversarial tests for the PM2C research snapshot."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager.models import (
    ObservationCoverage,
    ObservationProvenance,
    OrderCoverage,
    PortfolioObservation,
    PositionObservation,
    PositionType,
)
from trading_bot.portfolio_manager.research_catalog import (
    CatalogEntry,
    EntryKind,
    EvidenceBasis,
    ResearchCatalog,
    ValueKind,
    ValueSpec,
)
from trading_bot.portfolio_manager.research_evidence import (
    AvailabilityReason,
    AvailabilityStatus,
    EvidenceGraph,
    EvidenceOutcome,
    EvidenceSubject,
    EvidenceTimeframe,
    EvidenceTimeframeKind,
    SnapshotMode,
    SourceFact,
    VersionAsOfWitness,
)
from trading_bot.portfolio_manager.research_snapshot import (
    MembershipBinding,
    ResearchSnapshot,
    SnapshotAdmissionError,
    SnapshotSlotRequest,
)

CUTOFF = datetime(2026, 11, 26, 20, tzinfo=UTC)
BEFORE = CUTOFF - timedelta(hours=2)
AFTER = CUTOFF + timedelta(hours=2)
ACCOUNT = sha256(b"pm2c synthetic account").hexdigest()


def _catalog() -> tuple[ResearchCatalog, CatalogEntry, CatalogEntry]:
    membership = CatalogEntry(
        "v1",
        "raw.classification.membership",
        "1",
        "relative",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.IDENTIFIER_VECTOR),
        basis=EvidenceBasis("PIT", data_basis="synthetic-membership"),
    )
    price = CatalogEntry(
        "v1",
        "raw.price.close.unadjusted",
        "1",
        "valuation",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "currency/share", "USD"),
        basis=EvidenceBasis("XNYS", data_basis="synthetic-price"),
    )
    return ResearchCatalog("v1", (membership, price)), membership, price


def _subject(symbol: str) -> EvidenceSubject:
    return EvidenceSubject(symbol=Symbol(symbol), share_class="COMMON")


def _membership_fact(entry: CatalogEntry, members: tuple[str, ...]) -> SourceFact:
    return SourceFact(
        entry=entry,
        subject=EvidenceSubject(scope="peer-panel", security_id="panel-v1"),
        source_identity="SYNTHETIC_MEMBERSHIP",
        source_version="membership-v1",
        outcome=EvidenceOutcome(AvailabilityStatus.AVAILABLE, members),
        timeframe=EvidenceTimeframe(EvidenceTimeframeKind.INSTANT, BEFORE),
        available_at=BEFORE,
        observed_at=BEFORE,
        effective_at=BEFORE,
        source_record_id="membership-record-v1",
        source_content_digest="membership-digest-v1",
    )


def _price_fact(
    entry: CatalogEntry,
    symbol: str = "AAPL",
    *,
    value: Decimal | None = Decimal("100"),
    available_at: datetime | None = BEFORE,
    observed_at: datetime | None = BEFORE,
    outcome: EvidenceOutcome[object] | None = None,
    source_version: str = "price-v1",
) -> SourceFact:
    if outcome is None:
        assert value is not None
        outcome = EvidenceOutcome(AvailabilityStatus.AVAILABLE, value)
    return SourceFact(
        entry=entry,
        subject=_subject(symbol),
        source_identity="SYNTHETIC_PRICE",
        source_version=source_version,
        outcome=outcome,
        timeframe=EvidenceTimeframe(EvidenceTimeframeKind.SESSION, BEFORE, BEFORE),
        available_at=available_at,
        observed_at=observed_at,
        effective_at=BEFORE,
        source_record_id="price-record-v1",
        source_content_digest="price-digest-v1",
    )


def _binding(membership_entry: CatalogEntry, fact: SourceFact) -> MembershipBinding:
    return MembershipBinding(
        entry=membership_entry,
        subject=fact.subject,
        evidence_id=fact.evidence_id,
        version=fact.source_version,
        effective_at=BEFORE,
        members=("AAPL", "MSFT"),
    )


def _snapshot(
    *,
    price_entry: CatalogEntry,
    membership_entry: CatalogEntry,
    membership_fact: SourceFact,
    price_fact: SourceFact | None = None,
    request_outcome: EvidenceOutcome[object] | None = None,
    mode: SnapshotMode = SnapshotMode.OPERATIONAL,
    cutoff: datetime = CUTOFF,
    witnesses: tuple[VersionAsOfWitness, ...] = (),
    portfolio_observation: PortfolioObservation | None = None,
) -> ResearchSnapshot:
    nodes = (membership_fact,) if price_fact is None else (membership_fact, price_fact)
    catalog = ResearchCatalog("v1", (membership_entry, price_entry))
    graph = EvidenceGraph(
        catalog,
        nodes,
    )
    request = (
        SnapshotSlotRequest(
            entry=price_entry,
            subject=_subject("AAPL"),
            evidence_id=price_fact.evidence_id,
        )
        if price_fact is not None
        else SnapshotSlotRequest(
            entry=price_entry,
            subject=_subject("AAPL"),
            missing_outcome=request_outcome
            or EvidenceOutcome(
                AvailabilityStatus.MISSING,
                reasons=(AvailabilityReason.MISSING_REQUIRED_INPUT,),
            ),
        )
    )
    return ResearchSnapshot.admit(
        graph=graph,
        decision_cutoff=cutoff,
        mode=mode,
        universe=("AAPL", "MSFT"),
        membership=_binding(membership_entry, membership_fact),
        slots=(request,),
        version_witnesses=witnesses,
        portfolio_observation=portfolio_observation,
    )


def test_snapshot_preserves_zero_and_unavailable_slots_without_numeric_substitute() -> (
    None
):
    catalog, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    zero_fact = _price_fact(price_entry, value=Decimal("0.01"))
    snapshot = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        price_fact=zero_fact,
    )
    assert snapshot.slot(price_entry.key, _subject("AAPL")).value == Decimal("0.01")
    assert (
        snapshot.slot(price_entry.key, _subject("AAPL")).status
        is AvailabilityStatus.AVAILABLE
    )
    missing = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        request_outcome=EvidenceOutcome(
            AvailabilityStatus.MISSING,
            reasons=(AvailabilityReason.MISSING_COVERAGE,),
        ),
    )
    slot = missing.slot(price_entry.key, _subject("AAPL"))
    assert slot is not None
    assert slot.value is None
    assert slot.status is AvailabilityStatus.MISSING
    assert slot.evidence_id is None


@pytest.mark.parametrize(
    "status,reason",
    [
        (AvailabilityStatus.MISSING, AvailabilityReason.MISSING_REQUIRED_INPUT),
        (AvailabilityStatus.STALE, AvailabilityReason.STALE_NAMED_RULE),
        (AvailabilityStatus.UNSUPPORTED, AvailabilityReason.UNSUPPORTED_DENOMINATOR),
        (
            AvailabilityStatus.NOT_YET_AVAILABLE,
            AvailabilityReason.NOT_YET_AVAILABLE_PUBLICATION,
        ),
        (
            AvailabilityStatus.CONFLICTED,
            AvailabilityReason.CONFLICT_CANDIDATE_IDENTITIES,
        ),
        (AvailabilityStatus.INVALID, AvailabilityReason.INVALID_TYPE),
    ],
)
def test_snapshot_retains_all_unavailable_statuses(status, reason) -> None:
    _, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    candidates = (
        (UUID(int=1), UUID(int=2)) if status is AvailabilityStatus.CONFLICTED else ()
    )
    outcome = EvidenceOutcome(
        status,
        reasons=(reason,),
        conflict_candidate_ids=candidates,
        freshness_rule="named-rule-v1" if status is AvailabilityStatus.STALE else None,
    )
    snapshot = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        request_outcome=outcome,
    )
    assert snapshot.unavailable_slots[0].status is status
    assert snapshot.unavailable_slots[0].value is None


def test_semantic_identity_excludes_calculation_audit_but_changes_with_value() -> None:
    _, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    first = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        price_fact=_price_fact(price_entry, value=Decimal("100")),
    )
    second = ResearchSnapshot.admit(
        graph=EvidenceGraph(
            ResearchCatalog("v1", (membership_entry, price_entry)),
            (membership_fact, _price_fact(price_entry)),
        ),
        decision_cutoff=CUTOFF,
        mode=SnapshotMode.OPERATIONAL,
        universe=("AAPL", "MSFT"),
        membership=_binding(membership_entry, membership_fact),
        slots=(
            SnapshotSlotRequest(
                price_entry,
                _subject("AAPL"),
                evidence_id=_price_fact(price_entry).evidence_id,
            ),
        ),
        calculation_audit_at=AFTER,
    )
    assert first.snapshot_id == second.snapshot_id
    assert (
        first.catalog_id
        == ResearchCatalog("v1", (membership_entry, price_entry)).catalog_id
    )
    assert len(first.operational_witness_ids) == 2
    changed = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        price_fact=_price_fact(price_entry, value=Decimal("101")),
    )
    assert changed.snapshot_id != first.snapshot_id


def test_publication_after_cutoff_is_typed_unavailable_and_future_id_is_hidden() -> (
    None
):
    _, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    late = _price_fact(
        price_entry,
        outcome=EvidenceOutcome(
            AvailabilityStatus.NOT_YET_AVAILABLE,
            reasons=(AvailabilityReason.NOT_YET_AVAILABLE_PUBLICATION,),
        ),
        available_at=AFTER,
        observed_at=None,
    )
    snapshot = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        price_fact=late,
    )
    slot = snapshot.unavailable_slots[0]
    assert slot.status is AvailabilityStatus.NOT_YET_AVAILABLE
    assert slot.value is None
    assert slot.evidence_id is None
    assert late.evidence_id not in snapshot.source_fact_ids


def test_membership_effective_window_is_end_exclusive() -> None:
    _, membership_entry, price_entry = _catalog()
    membership_fact = replace(
        _membership_fact(membership_entry, ("AAPL", "MSFT")),
        timeframe=EvidenceTimeframe(EvidenceTimeframeKind.SESSION, BEFORE, CUTOFF),
    )
    with pytest.raises(SnapshotAdmissionError, match="effective time window"):
        _snapshot(
            price_entry=price_entry,
            membership_entry=membership_entry,
            membership_fact=membership_fact,
            request_outcome=EvidenceOutcome(
                AvailabilityStatus.MISSING,
                reasons=(AvailabilityReason.MISSING_COVERAGE,),
            ),
        )


def test_operational_late_receipt_rejected_and_historical_requires_exact_witness() -> (
    None
):
    _, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    late = _price_fact(price_entry, observed_at=AFTER)
    with pytest.raises(SnapshotAdmissionError, match="operational source receipt"):
        _snapshot(
            price_entry=price_entry,
            membership_entry=membership_entry,
            membership_fact=membership_fact,
            price_fact=late,
        )
    with pytest.raises(SnapshotAdmissionError, match="late historical source receipt"):
        _snapshot(
            price_entry=price_entry,
            membership_entry=membership_entry,
            membership_fact=membership_fact,
            price_fact=late,
            mode=SnapshotMode.HISTORICAL_RECONSTRUCTION,
        )
    witness = VersionAsOfWitness(
        source_fact_id=late.evidence_id,
        source_version=late.source_version,
        publication_at=late.available_at,
        source_record_id=late.source_record_id,
        source_content_digest=late.source_content_digest,
        source_identity=late.source_identity,
        effective_at=late.effective_at,
    )
    historical = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        price_fact=late,
        mode=SnapshotMode.HISTORICAL_RECONSTRUCTION,
        witnesses=(witness,),
    )
    assert historical.version_witness_ids == (witness.witness_id,)
    membership_witness = VersionAsOfWitness(
        source_fact_id=membership_fact.evidence_id,
        source_version=membership_fact.source_version,
        publication_at=membership_fact.available_at,
        source_record_id=membership_fact.source_record_id,
        source_content_digest=membership_fact.source_content_digest,
        source_identity=membership_fact.source_identity,
        effective_at=membership_fact.effective_at,
    )
    with pytest.raises(
        SnapshotAdmissionError, match="only for selected late source facts"
    ):
        _snapshot(
            price_entry=price_entry,
            membership_entry=membership_entry,
            membership_fact=membership_fact,
            price_fact=late,
            mode=SnapshotMode.HISTORICAL_RECONSTRUCTION,
            witnesses=(witness, membership_witness),
        )


def test_membership_id_is_in_closure_and_graph_and_slot_requests_are_not_retained() -> (
    None
):
    _, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    snapshot = _snapshot(
        price_entry=price_entry,
        membership_entry=membership_entry,
        membership_fact=membership_fact,
        request_outcome=EvidenceOutcome(
            AvailabilityStatus.MISSING,
            reasons=(AvailabilityReason.MISSING_COVERAGE,),
        ),
    )
    assert membership_fact.evidence_id in snapshot.source_fact_ids
    assert not hasattr(snapshot, "graph")
    assert not hasattr(snapshot, "slot_requests")


def _portfolio_observation(
    *,
    cash: Decimal | None,
    quote_complete: bool = True,
    quote_at: datetime | None = None,
) -> PortfolioObservation:
    position = PositionObservation(
        symbol=Symbol("AAPL"),
        quantity=Decimal("0"),
        available_to_sell=Decimal("0"),
        average_cost=Decimal("0"),
        current_price=None if quote_at is None else Decimal("100"),
        price_observed_at=quote_at,
        supported=True,
        position_type=PositionType.FLAT,
    )
    return PortfolioObservation(
        observed_at=BEFORE,
        account_fingerprint=ACCOUNT,
        observed_account_fingerprint=ACCOUNT,
        broker_reported_equity=None if cash is None else cash,
        broker_reported_position_value=Decimal("0"),
        cash=cash,
        buying_power=cash,
        unleveraged_buying_power=cash,
        positions=(position,),
        orders=(),
        coverage=ObservationCoverage(
            account_bound=True,
            portfolio_complete=cash is not None,
            positions_complete=True,
            quotes_complete=quote_complete,
            pagination_complete=True,
            order_scope=OrderCoverage.SYNTHETIC_COMPLETE,
        ),
        provenance=ObservationProvenance.SYNTHETIC,
    )


def test_portfolio_zero_and_missing_cash_bind_exact_observation_and_account() -> None:
    membership = CatalogEntry(
        "v1",
        "raw.classification.membership",
        "1",
        "relative",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.IDENTIFIER_VECTOR),
        basis=EvidenceBasis("PIT"),
    )
    cash_entry = CatalogEntry(
        "v1",
        "portfolio.cash",
        "1",
        "portfolio",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "currency", "USD"),
        basis=EvidenceBasis("PORTFOLIO"),
    )
    observation = _portfolio_observation(cash=Decimal("0"))
    membership_fact = _membership_fact(membership, ("AAPL", "MSFT"))
    cash_subject = EvidenceSubject(
        symbol=Symbol("AAPL"),
        portfolio_snapshot_id=observation.snapshot_id,
        portfolio_account_id=ACCOUNT,
    )
    cash_fact = SourceFact(
        entry=cash_entry,
        subject=cash_subject,
        source_identity="SYNTHETIC_PORTFOLIO",
        source_version="portfolio-v1",
        outcome=EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("0")),
        available_at=BEFORE,
        observed_at=BEFORE,
        effective_at=BEFORE,
        source_record_id="cash-record-v1",
        source_content_digest="cash-digest-v1",
    )
    graph = EvidenceGraph(
        ResearchCatalog("v1", (membership, cash_entry)),
        (membership_fact, cash_fact),
    )
    snapshot = ResearchSnapshot.admit(
        graph=graph,
        decision_cutoff=CUTOFF,
        mode=SnapshotMode.OPERATIONAL,
        universe=("AAPL", "MSFT"),
        membership=MembershipBinding(
            membership,
            membership_fact.subject,
            membership_fact.evidence_id,
            membership_fact.source_version,
            BEFORE,
            ("AAPL", "MSFT"),
        ),
        slots=(
            SnapshotSlotRequest(
                cash_entry, cash_subject, evidence_id=cash_fact.evidence_id
            ),
        ),
        portfolio_observation=observation,
    )
    assert snapshot.portfolio_observation_id == observation.snapshot_id
    assert snapshot.portfolio_account_fingerprint == ACCOUNT
    assert snapshot.slot(cash_entry.key, cash_subject).value == Decimal("0")

    missing_observation = _portfolio_observation(cash=None, quote_complete=False)
    missing_subject = EvidenceSubject(
        symbol=Symbol("AAPL"),
        portfolio_snapshot_id=missing_observation.snapshot_id,
        portfolio_account_id=ACCOUNT,
    )
    missing_fact = SourceFact(
        entry=cash_entry,
        subject=missing_subject,
        source_identity="SYNTHETIC_PORTFOLIO",
        source_version="portfolio-v1",
        outcome=EvidenceOutcome(
            AvailabilityStatus.MISSING,
            reasons=(AvailabilityReason.MISSING_COVERAGE,),
        ),
        effective_at=BEFORE,
    )
    missing_graph = EvidenceGraph(
        ResearchCatalog("v1", (membership, cash_entry)),
        (membership_fact, missing_fact),
    )
    missing_snapshot = ResearchSnapshot.admit(
        graph=missing_graph,
        decision_cutoff=CUTOFF,
        mode=SnapshotMode.OPERATIONAL,
        universe=("AAPL", "MSFT"),
        membership=MembershipBinding(
            membership,
            membership_fact.subject,
            membership_fact.evidence_id,
            membership_fact.source_version,
            BEFORE,
            ("AAPL", "MSFT"),
        ),
        slots=(
            SnapshotSlotRequest(
                cash_entry, missing_subject, evidence_id=missing_fact.evidence_id
            ),
        ),
        portfolio_observation=missing_observation,
    )
    assert missing_snapshot.slot(cash_entry.key, missing_subject).value is None

    unbound_cash_fact = replace(cash_fact, subject=_subject("AAPL"))
    with pytest.raises(SnapshotAdmissionError, match="exact synthetic observation"):
        ResearchSnapshot.admit(
            graph=EvidenceGraph(
                ResearchCatalog("v1", (membership, cash_entry)),
                (membership_fact, unbound_cash_fact),
            ),
            decision_cutoff=CUTOFF,
            mode=SnapshotMode.OPERATIONAL,
            universe=("AAPL", "MSFT"),
            membership=MembershipBinding(
                membership,
                membership_fact.subject,
                membership_fact.evidence_id,
                membership_fact.source_version,
                BEFORE,
                ("AAPL", "MSFT"),
            ),
            slots=(
                SnapshotSlotRequest(
                    cash_entry,
                    _subject("AAPL"),
                    evidence_id=unbound_cash_fact.evidence_id,
                ),
            ),
        )


def test_portfolio_mark_requires_original_quote_timestamp_at_cutoff() -> None:
    membership = CatalogEntry(
        "v1",
        "raw.classification.membership",
        "1",
        "relative",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.IDENTIFIER_VECTOR),
        basis=EvidenceBasis("PIT"),
    )
    mark_entry = CatalogEntry(
        "v1",
        "portfolio.mark",
        "1",
        "portfolio",
        EntryKind.RAW,
        value_spec=ValueSpec(ValueKind.DECIMAL, "currency/share", "USD"),
        basis=EvidenceBasis("PORTFOLIO"),
    )
    observation = _portfolio_observation(cash=Decimal("0"), quote_at=AFTER)
    membership_fact = _membership_fact(membership, ("AAPL", "MSFT"))
    mark_subject = EvidenceSubject(
        symbol=Symbol("AAPL"),
        portfolio_snapshot_id=observation.snapshot_id,
        portfolio_account_id=ACCOUNT,
    )
    mark_fact = SourceFact(
        entry=mark_entry,
        subject=mark_subject,
        source_identity="SYNTHETIC_PORTFOLIO",
        source_version="portfolio-v1",
        outcome=EvidenceOutcome(AvailabilityStatus.AVAILABLE, Decimal("100")),
        available_at=BEFORE,
        observed_at=BEFORE,
        effective_at=BEFORE,
        source_record_id="mark-record-v1",
        source_content_digest="mark-digest-v1",
    )
    with pytest.raises(SnapshotAdmissionError, match="portfolio mark must be positive"):
        ResearchSnapshot.admit(
            graph=EvidenceGraph(
                ResearchCatalog("v1", (membership, mark_entry)),
                (membership_fact, mark_fact),
            ),
            decision_cutoff=CUTOFF,
            mode=SnapshotMode.OPERATIONAL,
            universe=("AAPL", "MSFT"),
            membership=MembershipBinding(
                membership,
                membership_fact.subject,
                membership_fact.evidence_id,
                membership_fact.source_version,
                BEFORE,
                ("AAPL", "MSFT"),
            ),
            slots=(
                SnapshotSlotRequest(
                    mark_entry, mark_subject, evidence_id=mark_fact.evidence_id
                ),
            ),
            portfolio_observation=observation,
        )


def test_invalid_zero_price_is_rejected_and_portfolio_reference_is_not_forged() -> None:
    _, membership_entry, price_entry = _catalog()
    membership_fact = _membership_fact(membership_entry, ("AAPL", "MSFT"))
    zero_price = _price_fact(price_entry, value=Decimal("0"))
    with pytest.raises(SnapshotAdmissionError, match="close must be positive"):
        _snapshot(
            price_entry=price_entry,
            membership_entry=membership_entry,
            membership_fact=membership_fact,
            price_fact=zero_price,
        )
    with pytest.raises(SnapshotAdmissionError, match="synthetic observations only"):
        _snapshot(
            price_entry=price_entry,
            membership_entry=membership_entry,
            membership_fact=membership_fact,
            request_outcome=EvidenceOutcome(
                AvailabilityStatus.MISSING,
                reasons=(AvailabilityReason.MISSING_COVERAGE,),
            ),
            portfolio_observation=PortfolioObservation(
                **{
                    "observed_at": BEFORE,
                    "account_fingerprint": ACCOUNT,
                    "observed_account_fingerprint": ACCOUNT,
                    "broker_reported_equity": Decimal("0"),
                    "cash": Decimal("0"),
                    "buying_power": Decimal("0"),
                    "unleveraged_buying_power": Decimal("0"),
                    "positions": (),
                    "orders": (),
                    "coverage": ObservationCoverage(
                        True, True, True, True, True, OrderCoverage.SYNTHETIC_COMPLETE
                    ),
                    "provenance": ObservationProvenance.ROBINHOOD_READ_ONLY,
                }
            ),
        )
