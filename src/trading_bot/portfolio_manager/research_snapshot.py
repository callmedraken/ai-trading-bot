"""Immutable, synthetic-only point-in-time research snapshots.

The snapshot is the PM2C admission boundary between the typed catalog and
evidence contracts.  Its validation inputs are ``InitVar`` values and are not
stored, so a snapshot cannot expose an unadmitted evidence graph or source
record.  This module has no provider, AI, recommendation, optimizer, or
dispatch surface.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.models import (
    ObservationProvenance,
    PortfolioObservation,
)
from trading_bot.portfolio_manager.research_catalog import (
    CatalogEntry,
    EntryKind,
    ResearchCatalog,
    ValueKind,
    research_identity,
)
from trading_bot.portfolio_manager.research_evidence import (
    AvailabilityReason,
    AvailabilityStatus,
    DerivedFeature,
    EvidenceGraph,
    EvidenceOutcome,
    EvidenceSubject,
    SnapshotMode,
    SourceFact,
    VersionAsOfWitness,
)


class ResearchSnapshotError(ValueError):
    """Base error for an invalid PM2C research snapshot."""


class SnapshotAdmissionError(ResearchSnapshotError):
    """Raised when typed evidence cannot be admitted at the requested cutoff."""


_AVAILABLE: Final[AvailabilityStatus] = AvailabilityStatus.AVAILABLE


def _witness_id(witness: VersionAsOfWitness) -> UUID:
    """Use the evidence lane's exact witness identity."""

    return witness.witness_id


def _same_entry(left: CatalogEntry, right: CatalogEntry) -> bool:
    return left.entry_id == right.entry_id and left == right


@dataclass(frozen=True, slots=True)
class SnapshotSlotRequest:
    """A requested slot bound to an exact catalog entry and typed subject.

    Either an evidence ID or an explicitly unavailable ``EvidenceOutcome`` is
    required.  Callers cannot supply a numeric value for an unavailable slot.
    """

    entry: CatalogEntry
    subject: EvidenceSubject
    evidence_id: UUID | None = None
    missing_outcome: EvidenceOutcome[object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.entry, CatalogEntry):
            raise TypeError("entry must be CatalogEntry")
        if not isinstance(self.subject, EvidenceSubject):
            raise TypeError("subject must be EvidenceSubject")
        if self.evidence_id is None and self.missing_outcome is None:
            raise SnapshotAdmissionError(
                "a slot requires an evidence ID or typed unavailable outcome"
            )
        if self.evidence_id is not None and not isinstance(self.evidence_id, UUID):
            raise TypeError("evidence_id must be UUID or None")
        if self.evidence_id is not None and self.missing_outcome is not None:
            raise SnapshotAdmissionError(
                "a slot cannot provide both evidence ID and missing outcome"
            )
        if self.missing_outcome is not None:
            if not isinstance(self.missing_outcome, EvidenceOutcome):
                raise TypeError("missing_outcome must be EvidenceOutcome")
            if self.missing_outcome.status is _AVAILABLE:
                raise SnapshotAdmissionError(
                    "missing_outcome must be an unavailable typed outcome"
                )

    @property
    def slot_key(self) -> str:
        return self.entry.key


@dataclass(frozen=True, slots=True)
class MembershipBinding:
    """PIT membership evidence and the ordered requested universe it proves."""

    entry: CatalogEntry
    subject: EvidenceSubject
    evidence_id: UUID
    version: str
    effective_at: datetime
    members: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.entry, CatalogEntry):
            raise TypeError("membership entry must be CatalogEntry")
        if not isinstance(self.subject, EvidenceSubject):
            raise TypeError("membership subject must be EvidenceSubject")
        if not isinstance(self.evidence_id, UUID):
            raise TypeError("membership evidence_id must be UUID")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("membership version must be nonblank")
        object.__setattr__(
            self, "effective_at", normalize_utc(self.effective_at, "effective_at")
        )
        members = tuple(self.members)
        if not members or any(
            not isinstance(member, str) or not member.strip() for member in members
        ):
            raise ValueError("membership members must be nonblank strings")
        if len(set(members)) != len(members):
            raise ValueError("membership members must be unique and ordered")
        object.__setattr__(self, "members", members)

    @property
    def binding_id(self) -> UUID:
        return research_identity(
            "snapshot-membership",
            self.entry,
            self.subject.identity_material,
            self.evidence_id,
            self.version,
            self.effective_at,
            self.members,
        )


@dataclass(frozen=True, slots=True)
class _PortfolioObservationReference:
    """Internal, value-only reference derived from an exact observation."""

    observation_id: UUID
    account_fingerprint: str
    observed_at: datetime
    coverage: tuple[tuple[str, bool], ...]
    cash_known: bool
    positions: tuple[tuple[str, bool, bool, bool], ...]


@dataclass(frozen=True, slots=True)
class ResearchSnapshotSlot:
    """One ordered admitted or explicitly unavailable slot."""

    slot_key: str
    entry_id: UUID
    entry_version: str
    subject: EvidenceSubject
    evidence_id: UUID | None
    outcome: EvidenceOutcome[object]
    source_fact_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.slot_key, str) or not self.slot_key.strip():
            raise ValueError("slot_key must be nonblank")
        if not isinstance(self.entry_id, UUID):
            raise TypeError("entry_id must be UUID")
        if not isinstance(self.entry_version, str) or not self.entry_version.strip():
            raise ValueError("entry_version must be nonblank")
        if not isinstance(self.subject, EvidenceSubject):
            raise TypeError("subject must be EvidenceSubject")
        if self.evidence_id is not None and not isinstance(self.evidence_id, UUID):
            raise TypeError("evidence_id must be UUID or None")
        if not isinstance(self.outcome, EvidenceOutcome):
            raise TypeError("outcome must be EvidenceOutcome")
        source_ids = tuple(self.source_fact_ids)
        if any(not isinstance(item, UUID) for item in source_ids):
            raise TypeError("source_fact_ids must contain UUID values")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_fact_ids must be unique")
        object.__setattr__(self, "source_fact_ids", source_ids)

    @property
    def status(self) -> AvailabilityStatus:
        return self.outcome.status

    @property
    def value(self) -> object | None:
        return self.outcome.value

    @property
    def reasons(self) -> tuple[AvailabilityReason, ...]:
        return self.outcome.reasons

    @property
    def semantic_id(self) -> UUID:
        return research_identity(
            "research-snapshot-slot",
            self.slot_key,
            self.entry_id,
            self.entry_version,
            self.subject.identity_material,
            self.evidence_id,
            self.outcome.status,
            self.outcome.value,
            self.outcome.reasons,
            self.outcome.conflict_candidate_ids,
            self.outcome.freshness_rule,
            self.source_fact_ids,
        )


@dataclass(frozen=True, slots=True)
class ResearchSnapshot:
    """Immutable, deterministic research evidence view at one cutoff.

    ``graph`` and ``portfolio_observation`` are InitVars: they are required for
    admission, then discarded.  The public snapshot retains only exact typed
    IDs, outcomes, membership metadata, witness records, and the value-only
    portfolio reference.
    """

    graph: InitVar[EvidenceGraph]
    decision_cutoff: datetime
    mode: SnapshotMode
    universe: tuple[str | Symbol, ...]
    membership: MembershipBinding
    slot_requests: InitVar[tuple[SnapshotSlotRequest, ...]]
    portfolio_observation: InitVar[PortfolioObservation | None] = None
    version_witnesses: InitVar[tuple[VersionAsOfWitness, ...]] = ()
    calculation_audit_at: datetime | None = field(
        default=None, compare=False, repr=False
    )
    catalog_version: str = field(init=False)
    slots: tuple[ResearchSnapshotSlot, ...] = field(init=False)
    source_fact_ids: tuple[UUID, ...] = field(init=False)
    derived_feature_ids: tuple[UUID, ...] = field(init=False)
    version_witness_ids: tuple[UUID, ...] = field(init=False)
    operational_witness_ids: tuple[UUID, ...] = field(init=False)
    catalog_id: UUID = field(init=False)
    portfolio: _PortfolioObservationReference | None = field(init=False, default=None)
    snapshot_id: UUID = field(init=False)

    def __post_init__(
        self,
        graph: EvidenceGraph,
        slot_requests: tuple[SnapshotSlotRequest, ...],
        portfolio_observation: PortfolioObservation | None,
        version_witnesses: tuple[VersionAsOfWitness, ...],
    ) -> None:
        if not isinstance(graph, EvidenceGraph):
            raise TypeError("graph must be EvidenceGraph")
        if not isinstance(graph.catalog, ResearchCatalog):
            raise TypeError("graph.catalog must be ResearchCatalog")
        if not isinstance(self.mode, SnapshotMode):
            raise TypeError("mode must be research_evidence.SnapshotMode")
        cutoff = normalize_utc(self.decision_cutoff, "decision_cutoff")
        object.__setattr__(self, "decision_cutoff", cutoff)
        universe = tuple(
            item.value if isinstance(item, Symbol) else item for item in self.universe
        )
        if not universe or any(
            not isinstance(item, str) or not item.strip() for item in universe
        ):
            raise SnapshotAdmissionError(
                "universe must contain nonblank symbol identities"
            )
        if len(set(universe)) != len(universe):
            raise SnapshotAdmissionError(
                "universe order must not contain duplicate symbols"
            )
        object.__setattr__(self, "universe", universe)
        if not isinstance(self.membership, MembershipBinding):
            raise TypeError("membership must be MembershipBinding")
        self._validate_membership(
            graph, self.membership, cutoff, self.mode, version_witnesses
        )
        requests = tuple(slot_requests)
        if not requests or not all(
            isinstance(item, SnapshotSlotRequest) for item in requests
        ):
            raise SnapshotAdmissionError(
                "slot_requests must contain SnapshotSlotRequest values"
            )
        witness_values = tuple(version_witnesses)
        if not all(isinstance(item, VersionAsOfWitness) for item in witness_values):
            raise TypeError("version_witnesses must contain VersionAsOfWitness values")
        if len({_witness_id(item) for item in witness_values}) != len(witness_values):
            raise SnapshotAdmissionError("version witnesses must be unique")
        if self.calculation_audit_at is not None:
            object.__setattr__(
                self,
                "calculation_audit_at",
                normalize_utc(self.calculation_audit_at, "calculation_audit_at"),
            )
        if portfolio_observation is not None:
            object.__setattr__(
                self,
                "portfolio",
                self._reference_portfolio(portfolio_observation, cutoff),
            )
        slots, source_ids, derived_ids = self._admit_slots(
            graph, requests, cutoff, self.mode, witness_values, portfolio_observation
        )
        membership_closure = graph.closure(self.membership.evidence_id)
        membership_source_ids = tuple(
            evidence_id
            for evidence_id in membership_closure
            if isinstance(graph.node_for(evidence_id), SourceFact)
        )
        membership_derived_ids = tuple(
            evidence_id
            for evidence_id in membership_closure
            if isinstance(graph.node_for(evidence_id), DerivedFeature)
        )
        object.__setattr__(self, "slots", slots)
        object.__setattr__(
            self,
            "source_fact_ids",
            tuple(dict.fromkeys((*membership_source_ids, *source_ids))),
        )
        object.__setattr__(
            self,
            "derived_feature_ids",
            tuple(dict.fromkeys((*membership_derived_ids, *derived_ids))),
        )
        used_late_fact_ids = {
            fact_id
            for fact_id in self.source_fact_ids
            if (
                isinstance(graph.node_for(fact_id), SourceFact)
                and graph.node_for(fact_id).observed_at is not None
                and graph.node_for(fact_id).observed_at > cutoff
            )
        }
        used_witnesses = tuple(
            witness
            for witness in witness_values
            if witness.source_fact_id in used_late_fact_ids
        )
        if len(used_witnesses) != len(witness_values):
            raise SnapshotAdmissionError(
                "version witnesses must be supplied only for selected late source facts"
            )
        if len({witness.source_fact_id for witness in used_witnesses}) != len(
            used_witnesses
        ):
            raise SnapshotAdmissionError(
                "a selected late source fact must have exactly one version witness"
            )
        object.__setattr__(
            self,
            "version_witness_ids",
            tuple(_witness_id(item) for item in used_witnesses),
        )
        object.__setattr__(self, "catalog_version", graph.catalog.version)
        object.__setattr__(self, "catalog_id", graph.catalog.catalog_id)
        operational_ids: list[UUID] = []
        if self.mode is SnapshotMode.OPERATIONAL:
            for evidence_id in (*self.source_fact_ids, *self.derived_feature_ids):
                node = graph.node_for(evidence_id)
                if isinstance(node, SourceFact) and node.outcome.available:
                    if node.observed_at is None:
                        raise SnapshotAdmissionError(
                            "operational source fact lacks receipt identity"
                        )
                    operational_ids.append(
                        research_identity(
                            "operational-receipt",
                            node.evidence_id,
                            node.observed_at,
                        )
                    )
                elif isinstance(node, DerivedFeature) and node.outcome.available:
                    if node.calculated_at is None:
                        raise SnapshotAdmissionError(
                            "operational feature lacks materialization identity"
                        )
                    operational_ids.append(
                        research_identity(
                            "operational-materialization",
                            node.evidence_id,
                            node.calculated_at,
                        )
                    )
        object.__setattr__(self, "operational_witness_ids", tuple(operational_ids))
        object.__setattr__(self, "snapshot_id", self._derive_snapshot_id())

    @classmethod
    def admit(
        cls,
        *,
        graph: EvidenceGraph,
        decision_cutoff: datetime,
        mode: SnapshotMode,
        universe: tuple[str | Symbol, ...],
        membership: MembershipBinding,
        slots: tuple[SnapshotSlotRequest, ...],
        portfolio_observation: PortfolioObservation | None = None,
        version_witnesses: tuple[VersionAsOfWitness, ...] = (),
        calculation_audit_at: datetime | None = None,
    ) -> ResearchSnapshot:
        """Validate the graph closure and construct one immutable snapshot."""

        return cls(
            graph,
            decision_cutoff,
            mode,
            universe,
            membership,
            slots,
            portfolio_observation,
            version_witnesses,
            calculation_audit_at,
        )

    @property
    def available_slots(self) -> tuple[ResearchSnapshotSlot, ...]:
        return tuple(item for item in self.slots if item.status is _AVAILABLE)

    @property
    def unavailable_slots(self) -> tuple[ResearchSnapshotSlot, ...]:
        return tuple(item for item in self.slots if item.status is not _AVAILABLE)

    @property
    def portfolio_observation_id(self) -> UUID | None:
        return None if self.portfolio is None else self.portfolio.observation_id

    @property
    def portfolio_account_fingerprint(self) -> str | None:
        return None if self.portfolio is None else self.portfolio.account_fingerprint

    def slot(
        self, entry_key: str, subject: EvidenceSubject | Symbol | str
    ) -> ResearchSnapshotSlot | None:
        subject_key = (
            str(subject.symbol)
            if isinstance(subject, EvidenceSubject) and subject.symbol is not None
            else str(subject)
        )
        return next(
            (
                item
                for item in self.slots
                if item.slot_key == entry_key
                and (
                    str(item.subject.symbol)
                    if item.subject.symbol is not None
                    else str(item.subject)
                )
                == subject_key
            ),
            None,
        )

    def _validate_membership(
        self,
        graph: EvidenceGraph,
        membership: MembershipBinding,
        cutoff: datetime,
        mode: SnapshotMode,
        witnesses: tuple[VersionAsOfWitness, ...],
    ) -> None:
        if tuple(self.universe) != membership.members:
            raise SnapshotAdmissionError(
                "ordered universe must equal the selected PIT membership panel"
            )
        try:
            registered = graph.catalog.lookup(
                membership.entry.key, membership.entry.version
            )
        except KeyError as error:
            raise SnapshotAdmissionError(
                "membership entry is not registered"
            ) from error
        if not _same_entry(registered, membership.entry):
            raise SnapshotAdmissionError(
                "membership entry is not the exact catalog object"
            )
        if membership.entry.kind is not EntryKind.RAW:
            raise SnapshotAdmissionError("PIT membership must use a RAW catalog entry")
        if membership.entry.value_spec.kind is not ValueKind.IDENTIFIER_VECTOR:
            raise SnapshotAdmissionError(
                "PIT membership must use an identifier-vector catalog entry"
            )
        node = graph.node_for(membership.evidence_id)
        if (
            not _same_entry(node.entry, membership.entry)
            or node.subject != membership.subject
        ):
            raise SnapshotAdmissionError("membership evidence entry/subject mismatch")
        if (
            not node.outcome.available
            or tuple(node.outcome.value or ()) != membership.members
        ):
            raise SnapshotAdmissionError(
                "membership evidence must admit the exact ordered member panel"
            )
        if membership.effective_at > cutoff:
            raise SnapshotAdmissionError("membership is not effective at the cutoff")
        if isinstance(node, SourceFact):
            if node.source_version != membership.version:
                raise SnapshotAdmissionError("membership source version mismatch")
            if node.effective_at != membership.effective_at:
                raise SnapshotAdmissionError("membership effective time mismatch")
        else:
            raise SnapshotAdmissionError("PIT membership must be a source fact")
        if node.timeframe is not None and (
            cutoff < node.timeframe.start
            or (node.timeframe.end is not None and cutoff >= node.timeframe.end)
        ):
            raise SnapshotAdmissionError(
                "membership source fact is outside its effective time window"
            )
        self._validate_closure(graph, node.evidence_id, cutoff, mode, witnesses)

    def _admit_slots(
        self,
        graph: EvidenceGraph,
        requests: tuple[SnapshotSlotRequest, ...],
        cutoff: datetime,
        mode: SnapshotMode,
        witnesses: tuple[VersionAsOfWitness, ...],
        portfolio_observation: PortfolioObservation | None,
    ) -> tuple[
        tuple[ResearchSnapshotSlot, ...],
        tuple[UUID, ...],
        tuple[UUID, ...],
    ]:
        seen: set[tuple[UUID, tuple[str, ...]]] = set()
        slots: list[ResearchSnapshotSlot] = []
        source_ids: list[UUID] = []
        derived_ids: list[UUID] = []
        for request in requests:
            try:
                registered = graph.catalog.lookup(
                    request.entry.key, request.entry.version
                )
            except KeyError as error:
                raise SnapshotAdmissionError("slot entry is not registered") from error
            if not _same_entry(registered, request.entry):
                raise SnapshotAdmissionError(
                    "slot entry is not the exact catalog object"
                )
            identity = (request.entry.entry_id, request.subject.identity_material)
            if identity in seen:
                raise SnapshotAdmissionError("duplicate slot identity")
            seen.add(identity)
            member_key = (
                request.subject.symbol.value
                if request.subject.symbol is not None
                else request.subject.security_id
            )
            if member_key is not None and member_key not in self.universe:
                raise SnapshotAdmissionError(
                    "slot subject is outside the selected PIT membership panel"
                )
            self._validate_portfolio_subject(request.subject, portfolio_observation)
            if request.evidence_id is None:
                assert request.missing_outcome is not None
                slots.append(
                    ResearchSnapshotSlot(
                        slot_key=request.slot_key,
                        entry_id=request.entry.entry_id,
                        entry_version=request.entry.version,
                        subject=request.subject,
                        evidence_id=None,
                        outcome=request.missing_outcome,
                        source_fact_ids=(),
                    )
                )
                continue
            node = graph.node_for(request.evidence_id)
            if (
                not _same_entry(node.entry, request.entry)
                or node.subject != request.subject
            ):
                raise SnapshotAdmissionError("slot evidence entry/subject mismatch")
            closure = graph.closure(node.evidence_id)
            self._validate_closure(graph, node.evidence_id, cutoff, mode, witnesses)
            for closure_id in closure:
                closure_node = graph.node_for(closure_id)
                self._validate_portfolio_subject(
                    closure_node.subject, portfolio_observation
                )
                self._validate_portfolio_fact(
                    closure_node, portfolio_observation, cutoff
                )
            hide_future_identity = node.outcome.status is not _AVAILABLE and any(
                self._is_late_unavailable(graph.node_for(evidence_id), cutoff)
                for evidence_id in closure
            )
            if not hide_future_identity:
                for evidence_id in closure:
                    closure_node = graph.node_for(evidence_id)
                    if isinstance(closure_node, SourceFact):
                        source_ids.append(evidence_id)
                    elif isinstance(closure_node, DerivedFeature):
                        derived_ids.append(evidence_id)
            slots.append(
                ResearchSnapshotSlot(
                    slot_key=request.slot_key,
                    entry_id=request.entry.entry_id,
                    entry_version=request.entry.version,
                    subject=request.subject,
                    evidence_id=None if hide_future_identity else node.evidence_id,
                    outcome=node.outcome,
                    source_fact_ids=()
                    if hide_future_identity
                    else graph.source_closure(node.evidence_id),
                )
            )
        return (
            tuple(slots),
            tuple(dict.fromkeys(source_ids)),
            tuple(dict.fromkeys(derived_ids)),
        )

    @staticmethod
    def _is_late_unavailable(
        node: SourceFact | DerivedFeature, cutoff: datetime
    ) -> bool:
        if node.outcome.available:
            return False
        if isinstance(node, SourceFact):
            return (node.available_at is not None and node.available_at > cutoff) or (
                node.observed_at is not None and node.observed_at > cutoff
            )
        return node.calculated_at is not None and node.calculated_at > cutoff

    @staticmethod
    def _validate_portfolio_subject(
        subject: EvidenceSubject,
        observation: PortfolioObservation | None,
    ) -> None:
        if (
            subject.portfolio_snapshot_id is None
            and subject.portfolio_account_id is None
        ):
            return
        if observation is None:
            raise SnapshotAdmissionError(
                "portfolio evidence requires the exact synthetic observation"
            )
        if (
            subject.portfolio_snapshot_id is not None
            and subject.portfolio_snapshot_id != observation.snapshot_id
        ):
            raise SnapshotAdmissionError(
                "portfolio evidence subject is not bound to the exact observation"
            )
        if (
            subject.portfolio_account_id is not None
            and subject.portfolio_account_id != observation.account_fingerprint
        ):
            raise SnapshotAdmissionError(
                "portfolio evidence subject is not bound to the exact account"
            )

    @staticmethod
    def _validate_portfolio_fact(
        node: SourceFact | DerivedFeature,
        observation: PortfolioObservation | None,
        cutoff: datetime,
    ) -> None:
        if not isinstance(node, SourceFact):
            return
        key = node.entry.key
        exact_keys = {
            "portfolio.cash",
            "portfolio.broker_equity",
            "portfolio.quantity",
            "portfolio.mark",
            "portfolio.average_cost",
        }
        if key not in exact_keys:
            return
        if observation is None:
            raise SnapshotAdmissionError(
                "portfolio source fact requires the exact synthetic observation"
            )
        if (
            node.subject.portfolio_snapshot_id != observation.snapshot_id
            or node.subject.portfolio_account_id != observation.account_fingerprint
        ):
            raise SnapshotAdmissionError(
                "portfolio source fact must bind exact snapshot and account"
            )
        symbol = None if node.subject.symbol is None else str(node.subject.symbol)
        position = next(
            (item for item in observation.positions if str(item.symbol) == symbol),
            None,
        )
        expected = None
        known = True
        if key == "portfolio.cash":
            expected = observation.cash
            coverage_ok = (
                observation.coverage.account_bound
                and observation.coverage.portfolio_complete
            )
        elif key == "portfolio.broker_equity":
            expected = observation.broker_reported_equity
            coverage_ok = (
                observation.coverage.account_bound
                and observation.coverage.portfolio_complete
            )
        elif key == "portfolio.quantity":
            expected = None if position is None else position.quantity
            coverage_ok = (
                observation.coverage.account_bound
                and observation.coverage.positions_complete
            )
        elif key == "portfolio.mark":
            expected = None if position is None else position.current_price
            coverage_ok = (
                observation.coverage.account_bound
                and observation.coverage.positions_complete
                and observation.coverage.quotes_complete
            )
        elif key == "portfolio.average_cost":
            expected = None if position is None else position.average_cost
            coverage_ok = (
                observation.coverage.account_bound
                and observation.coverage.positions_complete
            )
        if expected is None:
            known = False
        if node.outcome.available:
            if not coverage_ok or not known or node.outcome.value != expected:
                raise SnapshotAdmissionError(
                    "portfolio source fact does not match synthetic observation "
                    "knownness/value"
                )
            if key == "portfolio.mark" and (
                expected <= 0
                or node.observed_at is None
                or node.observed_at > cutoff
                or position is None
                or position.price_observed_at is None
                or position.price_observed_at > cutoff
            ):
                raise SnapshotAdmissionError(
                    "portfolio mark must be positive when known"
                )
        elif known and coverage_ok:
            late = (node.available_at is not None and node.available_at > cutoff) or (
                node.observed_at is not None and node.observed_at > cutoff
            )
            if late:
                return
            raise SnapshotAdmissionError(
                "portfolio source fact marks a known observation value unavailable"
            )

    @staticmethod
    def _validate_closure(
        graph: EvidenceGraph,
        evidence_id: UUID,
        cutoff: datetime,
        mode: SnapshotMode,
        witnesses: tuple[VersionAsOfWitness, ...],
    ) -> None:
        witness_by_fact: dict[UUID, tuple[VersionAsOfWitness, ...]] = {}
        for witness in witnesses:
            witness_by_fact.setdefault(witness.source_fact_id, ())
            witness_by_fact[witness.source_fact_id] = (
                *witness_by_fact[witness.source_fact_id],
                witness,
            )
        for closure_id in graph.closure(evidence_id):
            node = graph.node_for(closure_id)
            if isinstance(node, SourceFact):
                ResearchSnapshot._validate_source_fact(
                    node, cutoff, mode, witness_by_fact.get(node.evidence_id, ())
                )
            elif isinstance(node, DerivedFeature):
                ResearchSnapshot._validate_derived_feature(node, cutoff, mode)
            else:
                raise SnapshotAdmissionError("unknown evidence node type")

    @staticmethod
    def _validate_source_fact(
        fact: SourceFact,
        cutoff: datetime,
        mode: SnapshotMode,
        witnesses: tuple[VersionAsOfWitness, ...],
    ) -> None:
        if fact.outcome.available:
            if (
                fact.entry.key == "raw.price.close.unadjusted"
                and isinstance(fact.outcome.value, Decimal)
                and fact.outcome.value <= 0
            ):
                raise SnapshotAdmissionError("unadjusted close must be positive")
            if fact.available_at is None or fact.available_at > cutoff:
                raise SnapshotAdmissionError(
                    "available source fact was published after the snapshot cutoff"
                )
            if fact.observed_at is None:
                raise SnapshotAdmissionError("available source fact lacks receipt time")
            if fact.observed_at > cutoff:
                if mode is SnapshotMode.OPERATIONAL:
                    raise SnapshotAdmissionError(
                        "operational source receipt is after cutoff"
                    )
                if not witnesses or not any(
                    witness.proves(fact, cutoff) for witness in witnesses
                ):
                    raise SnapshotAdmissionError(
                        "late historical source receipt lacks exact version witness"
                    )
                # Historical replay preserves fact.observed_at; it does not
                # rewrite it to the decision cutoff.
                return
            return
        if fact.outcome.value is not None:
            raise SnapshotAdmissionError("unavailable source fact carries a value")
        if fact.available_at is not None and fact.available_at > cutoff:
            if fact.status is not AvailabilityStatus.NOT_YET_AVAILABLE or (
                AvailabilityReason.NOT_YET_AVAILABLE_PUBLICATION
                not in fact.outcome.reasons
            ):
                raise SnapshotAdmissionError(
                    "late source publication must be typed NOT_YET_AVAILABLE"
                )
        if (
            mode is SnapshotMode.OPERATIONAL
            and fact.observed_at is not None
            and fact.observed_at > cutoff
        ):
            if (
                fact.status is not AvailabilityStatus.NOT_YET_AVAILABLE
                or AvailabilityReason.NOT_YET_AVAILABLE_RECEIPT
                not in fact.outcome.reasons
            ):
                raise SnapshotAdmissionError(
                    "late source receipt must be typed NOT_YET_AVAILABLE_RECEIPT"
                )

    @staticmethod
    def _validate_derived_feature(
        feature: DerivedFeature, cutoff: datetime, mode: SnapshotMode
    ) -> None:
        if feature.outcome.available:
            if feature.available_at is None or feature.available_at > cutoff:
                raise SnapshotAdmissionError(
                    "available derived feature is newer than the snapshot cutoff"
                )
            if feature.calculated_at is None:
                raise SnapshotAdmissionError("available feature lacks calculation time")
            if mode is SnapshotMode.OPERATIONAL and feature.calculated_at > cutoff:
                raise SnapshotAdmissionError(
                    "operational feature materialization is after cutoff"
                )
            return
        if feature.outcome.value is not None:
            raise SnapshotAdmissionError("unavailable derived feature carries a value")
        if feature.calculated_at is not None and feature.calculated_at > cutoff:
            if (
                feature.status is not AvailabilityStatus.NOT_YET_AVAILABLE
                or AvailabilityReason.NOT_YET_AVAILABLE_MATERIALIZATION
                not in feature.outcome.reasons
            ):
                raise SnapshotAdmissionError(
                    "late feature materialization must be typed "
                    "NOT_YET_AVAILABLE_MATERIALIZATION"
                )

    def _reference_portfolio(
        self,
        observation: PortfolioObservation,
        cutoff: datetime,
    ) -> _PortfolioObservationReference:
        if not isinstance(observation, PortfolioObservation):
            raise TypeError("portfolio_observation must be PortfolioObservation")
        if observation.provenance is not ObservationProvenance.SYNTHETIC:
            raise SnapshotAdmissionError(
                "PM2C portfolio context accepts synthetic observations only"
            )
        if (
            observation.account_fingerprint is None
            or not observation.coverage.account_bound
            or observation.observed_account_fingerprint
            != observation.account_fingerprint
        ):
            raise SnapshotAdmissionError("portfolio observation is not account-bound")
        if observation.observed_at > cutoff:
            raise SnapshotAdmissionError(
                "portfolio observation is after snapshot cutoff"
            )
        coverage = tuple(
            (name, bool(getattr(observation.coverage, name)))
            for name in (
                "account_bound",
                "portfolio_complete",
                "positions_complete",
                "quotes_complete",
                "pagination_complete",
            )
        )
        positions = tuple(
            (
                str(position.symbol),
                position.quantity is not None,
                position.current_price is not None,
                position.average_cost is not None,
            )
            for position in observation.positions
        )
        return _PortfolioObservationReference(
            observation_id=observation.snapshot_id,
            account_fingerprint=observation.account_fingerprint,
            observed_at=observation.observed_at,
            coverage=coverage,
            cash_known=observation.cash is not None,
            positions=positions,
        )

    def _derive_snapshot_id(self) -> UUID:
        portfolio_material = None
        if self.portfolio is not None:
            portfolio_material = (
                self.portfolio.observation_id,
                self.portfolio.account_fingerprint,
                self.portfolio.observed_at,
                self.portfolio.coverage,
                self.portfolio.cash_known,
                self.portfolio.positions,
            )
        return research_identity(
            "research-snapshot",
            "research-snapshot-identity/v1",
            self.catalog_id,
            self.catalog_version,
            self.decision_cutoff,
            self.mode,
            self.universe,
            self.membership.binding_id,
            self.membership.entry.basis.calendar
            if self.membership.entry.basis is not None
            else None,
            tuple(item.semantic_id for item in self.slots),
            self.source_fact_ids,
            self.derived_feature_ids,
            self.version_witness_ids,
            self.operational_witness_ids,
            portfolio_material,
        )


__all__ = [
    "MembershipBinding",
    "ResearchSnapshot",
    "ResearchSnapshotError",
    "ResearchSnapshotSlot",
    "SnapshotAdmissionError",
    "SnapshotSlotRequest",
]
