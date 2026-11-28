"""Immutable synthetic evidence contracts for Architecture 152-PM2C.

The module owns only typed in-memory evidence.  A :class:`ResearchCatalog` is
required by :class:`EvidenceGraph`; providers, storage, policy, AI,
recommendations, allocation, and execution are intentionally absent.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.research_catalog import (
    CatalogEntry,
    EntryKind,
    ResearchCatalog,
    momentum_12m_minus_1m,
    ratio,
    research_identity,
    simple_return,
)

EvidenceScalar = Decimal | str | int | bool
EvidenceValue = EvidenceScalar | tuple[EvidenceScalar, ...]
EvidenceValueT = TypeVar("EvidenceValueT")


class EvidenceContractError(ValueError):
    """Raised when immutable evidence cannot satisfy its contract."""


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_YET_AVAILABLE = "NOT_YET_AVAILABLE"
    CONFLICTED = "CONFLICTED"
    INVALID = "INVALID"


class AvailabilityReason(StrEnum):
    MISSING_REQUIRED_INPUT = "MISSING_REQUIRED_INPUT"
    MISSING_EXPECTED_PERIOD = "MISSING_EXPECTED_PERIOD"
    MISSING_EXPECTED_SESSION = "MISSING_EXPECTED_SESSION"
    MISSING_EXPECTED_QUARTER = "MISSING_EXPECTED_QUARTER"
    MISSING_EXPECTED_ANCHOR = "MISSING_EXPECTED_ANCHOR"
    MISSING_COVERAGE = "MISSING_COVERAGE"
    STALE_NAMED_RULE = "STALE_NAMED_RULE"
    UNSUPPORTED_DENOMINATOR = "UNSUPPORTED_DENOMINATOR"
    UNSUPPORTED_NONAPPLICABLE = "UNSUPPORTED_NONAPPLICABLE"
    UNSUPPORTED_BASIS = "UNSUPPORTED_BASIS"
    UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"
    NOT_YET_AVAILABLE_PUBLICATION = "NOT_YET_AVAILABLE_PUBLICATION"
    NOT_YET_AVAILABLE_RECEIPT = "NOT_YET_AVAILABLE_RECEIPT"
    NOT_YET_AVAILABLE_MATERIALIZATION = "NOT_YET_AVAILABLE_MATERIALIZATION"
    CONFLICT_COMPARABLE_WITNESSES = "CONFLICT_COMPARABLE_WITNESSES"
    CONFLICT_CANDIDATE_IDENTITIES = "CONFLICT_CANDIDATE_IDENTITIES"
    INVALID_NONFINITE = "INVALID_NONFINITE"
    INVALID_MALFORMED = "INVALID_MALFORMED"
    INVALID_IDENTITY = "INVALID_IDENTITY"
    INVALID_TIMING = "INVALID_TIMING"
    INVALID_REVISION = "INVALID_REVISION"
    INVALID_BASIS = "INVALID_BASIS"
    INVALID_TYPE = "INVALID_TYPE"


class SnapshotMode(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    HISTORICAL_RECONSTRUCTION = "HISTORICAL_RECONSTRUCTION"


class EvidenceTimeframeKind(StrEnum):
    INSTANT = "INSTANT"
    PERIOD = "PERIOD"
    SESSION = "SESSION"
    WINDOW = "WINDOW"


def _ordered_tuple(value: object, name: str) -> tuple[object, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be an ordered tuple or list")
    return tuple(value)


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{name} must be nonblank")
    return value.strip()


def _opaque_id(value: str, name: str) -> str:
    value = _text(value, name)
    if any(character.isspace() for character in value) or "/" in value or "\\" in value:
        raise ValueError(f"{name} must be a canonical opaque ID")
    return value


def _uuid(value: UUID, name: str) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError(f"{name} must be a UUID")
    return value


def _value_is_immutable(value: object) -> None:
    """Keep evidence values within catalog-supported deeply immutable types."""

    from decimal import Decimal

    if isinstance(value, Decimal):
        if not value.is_finite():
            raise EvidenceContractError("evidence value must be finite")
        return
    if isinstance(value, (str, int, bool)):
        return
    if isinstance(value, tuple):
        for item in value:
            _value_is_immutable(item)
        return
    raise EvidenceContractError("evidence value must be a supported immutable value")


@dataclass(frozen=True, slots=True)
class EvidenceSubject:
    """Stable security identity or typed portfolio/account scope."""

    symbol: Symbol | None = None
    issuer_id: str | None = None
    security_id: str | None = None
    share_class: str | None = None
    portfolio_account_id: str | None = None
    portfolio_snapshot_id: UUID | None = None
    scope: str | None = None

    def __post_init__(self) -> None:
        if self.symbol is not None and not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol or None")
        for name in (
            "issuer_id",
            "security_id",
            "share_class",
            "portfolio_account_id",
            "scope",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(value, name))
        if self.portfolio_snapshot_id is not None:
            _uuid(self.portfolio_snapshot_id, "portfolio_snapshot_id")
        if all(
            value is None
            for value in (
                self.symbol,
                self.issuer_id,
                self.security_id,
                self.portfolio_account_id,
                self.portfolio_snapshot_id,
                self.scope,
            )
        ):
            raise ValueError("subject must identify a security or typed scope")

    @property
    def identity_material(self) -> tuple[str, ...]:
        return (
            self.symbol.value if self.symbol else "",
            self.issuer_id or "",
            self.security_id or "",
            self.share_class or "",
            self.portfolio_account_id or "",
            str(self.portfolio_snapshot_id) if self.portfolio_snapshot_id else "",
            self.scope or "",
        )

    @property
    def subject_id(self) -> UUID:
        return research_identity("evidence-subject", self.identity_material)


@dataclass(frozen=True, slots=True)
class EvidenceTimeframe:
    """Economic period/session/window, distinct from publication availability."""

    kind: EvidenceTimeframeKind
    start: datetime
    end: datetime | None = None
    anchor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceTimeframeKind):
            raise TypeError("kind must be an EvidenceTimeframeKind")
        start = normalize_utc(self.start, "timeframe.start")
        end = None if self.end is None else normalize_utc(self.end, "timeframe.end")
        if end is not None and end < start:
            raise ValueError("timeframe.end must not precede start")
        if self.kind is EvidenceTimeframeKind.INSTANT and end is not None:
            raise ValueError("instant timeframe cannot have an end")
        if self.kind is not EvidenceTimeframeKind.INSTANT and end is None:
            raise ValueError("non-instant timeframe requires an end")
        if self.anchor is not None:
            _text(self.anchor, "timeframe.anchor")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    @property
    def period_start(self) -> datetime:
        return self.start

    @property
    def period_end(self) -> datetime | None:
        return self.end


@dataclass(frozen=True, slots=True)
class EvidenceOutcome[EvidenceValueT]:
    """Status/value pair; unavailable states have no numeric substitute."""

    status: AvailabilityStatus
    value: EvidenceValueT | None = None
    reasons: tuple[AvailabilityReason, ...] = ()
    conflict_candidate_ids: tuple[UUID, ...] = ()
    freshness_rule: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AvailabilityStatus):
            raise TypeError("status must be AvailabilityStatus")
        reasons = _ordered_tuple(self.reasons, "reasons")
        if not all(isinstance(reason, AvailabilityReason) for reason in reasons):
            raise TypeError("reasons must contain AvailabilityReason values")
        candidates = _ordered_tuple(
            self.conflict_candidate_ids, "conflict_candidate_ids"
        )
        if any(not isinstance(item, UUID) for item in candidates):
            raise TypeError("conflict candidates must be UUIDs")
        if len(set(candidates)) != len(candidates):
            raise ValueError("conflict candidate IDs must be unique")
        if self.status is AvailabilityStatus.AVAILABLE:
            if self.value is None or reasons or candidates:
                raise ValueError(
                    "AVAILABLE requires a value and no unavailable metadata"
                )
        elif self.value is not None:
            raise ValueError("unavailable states cannot carry a value")
        if self.status is AvailabilityStatus.STALE:
            if self.freshness_rule is None:
                raise ValueError("STALE requires a named freshness rule")
            _text(self.freshness_rule, "freshness_rule")
        elif self.freshness_rule is not None:
            raise ValueError("freshness_rule is only valid for STALE")
        if self.status is AvailabilityStatus.CONFLICTED:
            if not candidates:
                raise ValueError("CONFLICTED requires multiple candidate IDs")
            if len(candidates) < 2:
                raise ValueError("CONFLICTED requires multiple candidate IDs")
        elif candidates:
            raise ValueError("candidate IDs are only valid for CONFLICTED")
        _value_is_immutable(self.value) if self.value is not None else None
        _validate_reason_compatibility(self.status, reasons)
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(self, "conflict_candidate_ids", candidates)

    @property
    def available(self) -> bool:
        return self.status is AvailabilityStatus.AVAILABLE


def _validate_reason_compatibility(
    status: AvailabilityStatus, reasons: tuple[AvailabilityReason, ...]
) -> None:
    if status is AvailabilityStatus.AVAILABLE:
        return
    if not reasons:
        raise ValueError(f"{status.value} requires a typed reason")
    prefix = {
        AvailabilityStatus.MISSING: "MISSING_",
        AvailabilityStatus.STALE: "STALE_",
        AvailabilityStatus.UNSUPPORTED: "UNSUPPORTED_",
        AvailabilityStatus.NOT_YET_AVAILABLE: "NOT_YET_AVAILABLE_",
        AvailabilityStatus.CONFLICTED: "CONFLICT_",
        AvailabilityStatus.INVALID: "INVALID_",
    }[status]
    if any(not reason.value.startswith(prefix) for reason in reasons):
        raise ValueError(f"reason is incompatible with {status.value}")


@dataclass(frozen=True, slots=True)
class VersionAsOfWitness:
    """Exact source-version/publication witness for historical reconstruction."""

    source_fact_id: UUID
    source_version: str
    publication_at: datetime
    source_record_id: str
    source_content_digest: str
    source_identity: str
    revision_id: str | None = None
    effective_at: datetime | None = None
    visibility_ends_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.source_fact_id, "source_fact_id")
        for name in (
            "source_version",
            "source_record_id",
            "source_content_digest",
            "source_identity",
        ):
            _opaque_id(getattr(self, name), name)
        if self.revision_id is not None:
            _opaque_id(self.revision_id, "revision_id")
        object.__setattr__(
            self, "publication_at", normalize_utc(self.publication_at, "publication_at")
        )
        if self.effective_at is not None:
            object.__setattr__(
                self, "effective_at", normalize_utc(self.effective_at, "effective_at")
            )
        if self.visibility_ends_at is not None:
            end = normalize_utc(self.visibility_ends_at, "visibility_ends_at")
            if end < self.publication_at:
                raise ValueError("visibility_ends_at cannot precede publication_at")
            object.__setattr__(self, "visibility_ends_at", end)

    def proves(self, fact: SourceFact, cutoff: datetime) -> bool:
        if not isinstance(fact, SourceFact):
            raise TypeError("fact must be a SourceFact")
        cutoff = normalize_utc(cutoff, "cutoff")
        return (
            self.publication_at <= cutoff
            and (self.visibility_ends_at is None or cutoff <= self.visibility_ends_at)
            and self.source_fact_id == fact.evidence_id
            and self.source_version == fact.source_version
            and self.source_record_id == fact.source_record_id
            and self.source_content_digest == fact.source_content_digest
            and self.source_identity == fact.source_identity
            and self.revision_id == fact.revision_id
            and self.effective_at == fact.effective_at
            and fact.available_at == self.publication_at
        )

    @property
    def witness_id(self) -> UUID:
        return research_identity(
            "version-as-of-witness",
            self.source_fact_id,
            self.source_version,
            self.publication_at,
            self.source_record_id,
            self.source_content_digest,
            self.source_identity,
            self.revision_id,
            self.effective_at,
            self.visibility_ends_at,
        )


@dataclass(frozen=True, slots=True)
class SourceFact:
    """One immutable, catalog-bound point-in-time source fact."""

    entry: CatalogEntry
    subject: EvidenceSubject
    source_identity: str
    source_version: str
    outcome: EvidenceOutcome[EvidenceValue]
    timeframe: EvidenceTimeframe | None = None
    available_at: datetime | None = None
    observed_at: datetime | None = None
    effective_at: datetime | None = None
    revision_id: str | None = None
    revision_predecessor: UUID | None = None
    revision_predecessor_available_at: datetime | None = None
    source_record_id: str | None = None
    source_content_digest: str | None = None
    as_of_witness: VersionAsOfWitness | None = None
    source_path: str | None = None
    receipt_annotation: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.entry, CatalogEntry)
            or self.entry.kind is not EntryKind.RAW
        ):
            raise TypeError("SourceFact entry must be a registered RAW CatalogEntry")
        if not isinstance(self.subject, EvidenceSubject):
            raise TypeError("subject must be EvidenceSubject")
        if not isinstance(self.outcome, EvidenceOutcome):
            raise TypeError("outcome must be EvidenceOutcome")
        _opaque_id(self.source_identity, "source_identity")
        _opaque_id(self.source_version, "source_version")
        if self.timeframe is not None and not isinstance(
            self.timeframe, EvidenceTimeframe
        ):
            raise TypeError("timeframe must be EvidenceTimeframe")
        _normalize_times(self)
        if self.revision_predecessor is not None:
            _uuid(self.revision_predecessor, "revision_predecessor")
        if self.revision_predecessor is not None and self.revision_id is None:
            raise ValueError("revision_predecessor requires revision_id")
        if self.revision_predecessor_available_at is not None:
            predecessor_available_at = normalize_utc(
                self.revision_predecessor_available_at,
                "revision_predecessor_available_at",
            )
            object.__setattr__(
                self,
                "revision_predecessor_available_at",
                predecessor_available_at,
            )
            if (
                self.available_at is not None
                and predecessor_available_at > self.available_at
            ):
                raise ValueError("revision predecessor cannot be newer than this fact")
        for name in ("revision_id", "source_record_id", "source_content_digest"):
            value = getattr(self, name)
            if value is not None:
                _opaque_id(value, name)
        if self.outcome.available:
            if self.available_at is None or self.observed_at is None:
                raise ValueError(
                    "AVAILABLE source facts require available_at and observed_at"
                )
            self.entry.value_spec.validate(self.outcome.value)
        elif self.outcome.value is not None:
            raise ValueError("unavailable source fact cannot carry a value")
        if self.as_of_witness is not None and not isinstance(
            self.as_of_witness, VersionAsOfWitness
        ):
            raise TypeError("as_of_witness must be VersionAsOfWitness")
        if self.as_of_witness is not None and self.available_at is not None:
            if not self.as_of_witness.proves(self, self.available_at):
                raise ValueError("as_of_witness does not match exact source fact")

    @property
    def status(self) -> AvailabilityStatus:
        return self.outcome.status

    @property
    def value(self) -> EvidenceValue | None:
        return self.outcome.value

    @property
    def unit(self) -> str | None:
        return self.entry.value_spec.unit

    @property
    def currency(self) -> str | None:
        return self.entry.value_spec.currency

    @property
    def evidence_id(self) -> UUID:
        return research_identity(
            "source-fact",
            self.entry,
            self.subject.identity_material,
            self.source_identity,
            self.source_version,
            self.entry.value_spec.canonical_value(self.value)
            if self.value is not None
            else None,
            self.timeframe_material,
            self.available_at,
            self.effective_at,
            self.revision_id,
            self.revision_predecessor,
            self.source_record_id,
            self.source_content_digest,
            self.outcome.status,
            self.outcome.reasons,
            self.outcome.conflict_candidate_ids,
            self.outcome.freshness_rule,
            self.revision_predecessor_available_at,
        )

    @property
    def fact_id(self) -> UUID:
        return self.evidence_id

    @property
    def identity(self) -> UUID:
        return self.evidence_id

    @property
    def timeframe_material(self) -> tuple[object, ...] | None:
        if self.timeframe is None:
            return None
        return (
            self.timeframe.kind,
            self.timeframe.start,
            self.timeframe.end,
            self.timeframe.anchor,
        )

    def validate_cutoff(
        self,
        cutoff: datetime,
        mode: SnapshotMode,
        *,
        witness: VersionAsOfWitness | None = None,
    ) -> None:
        cutoff = normalize_utc(cutoff, "cutoff")
        if not self.outcome.available:
            raise EvidenceContractError(
                "unavailable fact cannot be admitted as available"
            )
        if self.available_at is None or self.available_at > cutoff:
            raise EvidenceContractError("fact publication is after cutoff")
        if mode is SnapshotMode.OPERATIONAL:
            if self.observed_at is None or self.observed_at > cutoff:
                raise EvidenceContractError("operational receipt is after cutoff")
        elif mode is SnapshotMode.HISTORICAL_RECONSTRUCTION:
            selected = witness or self.as_of_witness
            if selected is None or not selected.proves(self, cutoff):
                raise EvidenceContractError(
                    "historical fact lacks exact version witness"
                )
        else:
            raise TypeError("mode must be SnapshotMode")


def _normalize_times(value: SourceFact | DerivedFeature) -> None:
    for name in ("available_at", "observed_at", "effective_at", "calculated_at"):
        if not hasattr(value, name):
            continue
        timestamp = getattr(value, name)
        if timestamp is not None:
            object.__setattr__(value, name, normalize_utc(timestamp, name))
    observed_at = getattr(value, "observed_at", None)
    available_at = getattr(value, "available_at", None)
    if observed_at is not None and available_at is not None:
        if observed_at < available_at:
            raise ValueError("observed_at cannot precede available_at")
    if isinstance(value, DerivedFeature):
        if value.calculated_at is not None and value.available_at is not None:
            if value.calculated_at < value.available_at:
                raise ValueError("calculated_at cannot precede available_at")


@dataclass(frozen=True, slots=True)
class EvidenceDependency:
    evidence_id: UUID
    role: str

    def __post_init__(self) -> None:
        _uuid(self.evidence_id, "evidence_id")
        _text(self.role, "dependency role")


@dataclass(frozen=True, slots=True)
class DerivedFeature:
    """Catalog-bound deterministic output with ordered immediate inputs."""

    entry: CatalogEntry
    subject: EvidenceSubject
    dependencies: tuple[EvidenceDependency, ...]
    outcome: EvidenceOutcome[EvidenceValue]
    available_at: datetime | None = None
    calculated_at: datetime | None = None
    timeframe: EvidenceTimeframe | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.entry, CatalogEntry)
            or self.entry.kind is not EntryKind.DERIVED
        ):
            raise TypeError("DerivedFeature entry must be a DERIVED CatalogEntry")
        if not isinstance(self.subject, EvidenceSubject):
            raise TypeError("subject must be EvidenceSubject")
        if not isinstance(self.outcome, EvidenceOutcome):
            raise TypeError("outcome must be EvidenceOutcome")
        dependencies = _ordered_tuple(self.dependencies, "dependencies")
        if not all(isinstance(item, EvidenceDependency) for item in dependencies):
            raise TypeError("dependencies must contain EvidenceDependency")
        object.__setattr__(self, "dependencies", dependencies)
        if self.timeframe is not None and not isinstance(
            self.timeframe, EvidenceTimeframe
        ):
            raise TypeError("timeframe must be EvidenceTimeframe")
        _normalize_times(self)
        if self.outcome.available:
            if self.available_at is None or self.calculated_at is None:
                raise ValueError(
                    "AVAILABLE features require availability and calculation times"
                )
            self.entry.value_spec.validate(self.outcome.value)

    @property
    def status(self) -> AvailabilityStatus:
        return self.outcome.status

    @property
    def value(self) -> EvidenceValue | None:
        return self.outcome.value

    @property
    def unit(self) -> str | None:
        return self.entry.value_spec.unit

    @property
    def currency(self) -> str | None:
        return self.entry.value_spec.currency

    @property
    def evidence_id(self) -> UUID:
        return research_identity(
            "derived-feature",
            self.entry,
            self.subject.identity_material,
            tuple((item.evidence_id, item.role) for item in self.dependencies),
            self.entry.value_spec.canonical_value(self.value)
            if self.value is not None
            else None,
            self.outcome.status,
            self.outcome.reasons,
            self.outcome.conflict_candidate_ids,
            self.outcome.freshness_rule,
            self.available_at,
            self.timeframe_material,
        )

    @property
    def feature_id(self) -> UUID:
        return self.evidence_id

    @property
    def identity(self) -> UUID:
        return self.evidence_id

    @property
    def timeframe_material(self) -> tuple[object, ...] | None:
        if self.timeframe is None:
            return None
        return (
            self.timeframe.kind,
            self.timeframe.start,
            self.timeframe.end,
            self.timeframe.anchor,
        )


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    parent_id: UUID
    child_id: UUID
    role: str


@dataclass(frozen=True, slots=True)
class EvidenceGraph:
    """A frozen DAG whose catalog references and roles are all checked."""

    catalog: ResearchCatalog
    nodes: tuple[SourceFact | DerivedFeature, ...]
    _index: Mapping[UUID, SourceFact | DerivedFeature] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, ResearchCatalog):
            raise TypeError("EvidenceGraph requires a ResearchCatalog")
        nodes = _ordered_tuple(self.nodes, "nodes")
        if not nodes or not all(
            isinstance(node, (SourceFact, DerivedFeature)) for node in nodes
        ):
            raise TypeError("nodes must contain SourceFact or DerivedFeature values")
        ids = tuple(node.evidence_id for node in nodes)
        if len(set(ids)) != len(ids):
            raise EvidenceContractError("duplicate evidence identity in graph")
        object.__setattr__(self, "nodes", nodes)
        by_id = MappingProxyType(dict(zip(ids, nodes, strict=True)))
        object.__setattr__(self, "_index", by_id)
        for node in nodes:
            registered = self.catalog.lookup(node.entry.key, node.entry.version)
            if registered.entry_id != node.entry.entry_id or registered != node.entry:
                raise EvidenceContractError(
                    "node entry is not the exact registered catalog entry"
                )
            if isinstance(node, DerivedFeature):
                self._validate_feature(node, by_id)
        self._validate_acyclic(by_id)

    def _validate_feature(
        self,
        feature: DerivedFeature,
        by_id: Mapping[UUID, SourceFact | DerivedFeature],
    ) -> None:
        specs = feature.entry.inputs
        if len(feature.dependencies) != len(specs):
            raise EvidenceContractError(
                "dependency count does not match catalog inputs"
            )
        seen: set[UUID] = set()
        currencies: set[str] = set()
        repeat_roles: dict[UUID, list[bool]] = {}
        for dependency, spec in zip(feature.dependencies, specs, strict=True):
            if dependency.role != spec.role:
                raise EvidenceContractError(
                    "dependency role/order does not match catalog"
                )
            target = by_id.get(dependency.evidence_id)
            if target is None:
                raise EvidenceContractError("unknown dependency evidence ID")
            registered = self.catalog.lookup(spec.key, spec.version)
            if (
                target.entry.entry_id != registered.entry_id
                or target.entry != registered
            ):
                raise EvidenceContractError(
                    "dependency key/version/entry ID substitution"
                )
            if (
                spec.value_spec is not None
                and target.entry.value_spec != spec.value_spec
            ):
                raise EvidenceContractError("dependency value specification mismatch")
            if spec.basis is not None and target.entry.basis != spec.basis:
                raise EvidenceContractError("dependency basis mismatch")
            if (
                target.entry.value_spec.currency is not None
                and feature.entry.value_spec.currency is not None
                and target.entry.value_spec.currency
                != feature.entry.value_spec.currency
            ):
                raise EvidenceContractError("cross-currency dependency is unsupported")
            if target.entry.value_spec.currency is not None:
                currencies.add(target.entry.value_spec.currency)
            if len(currencies) > 1:
                raise EvidenceContractError("cross-currency dependency is unsupported")
            if spec.anchor is not None:
                target_timeframe = getattr(target, "timeframe", None)
                if target_timeframe is None or target_timeframe.anchor != spec.anchor:
                    raise EvidenceContractError(
                        "dependency timeframe anchor does not match catalog"
                    )
            expected_subject_id = spec.subject_id or feature.subject.subject_id
            if target.subject.subject_id != expected_subject_id:
                raise EvidenceContractError(
                    "dependency subject does not match catalog declaration"
                )
            if dependency.evidence_id in seen and not spec.allow_repeat:
                raise EvidenceContractError(
                    "repeated dependency is not permitted by InputSpec"
                )
            seen.add(dependency.evidence_id)
            repeat_roles.setdefault(dependency.evidence_id, []).append(
                spec.allow_repeat
            )
        if any(
            len(allow_repeat) > 1 and not all(allow_repeat)
            for allow_repeat in repeat_roles.values()
        ):
            raise EvidenceContractError(
                "repeated dependency requires every reuse role to allow repeat"
            )
        if feature.outcome.available:
            unavailable = [
                by_id[item.evidence_id]
                for item in feature.dependencies
                if not by_id[item.evidence_id].outcome.available
            ]
            if unavailable:
                raise EvidenceContractError(
                    "AVAILABLE feature depends on unavailable input"
                )
            available_times = [
                by_id[item.evidence_id].available_at for item in feature.dependencies
            ]
            if any(timestamp is None for timestamp in available_times):
                raise EvidenceContractError(
                    "required input lacks availability timestamp"
                )
            assert feature.available_at is not None
            if feature.available_at < max(available_times):
                raise EvidenceContractError(
                    "derived availability precedes required input"
                )
        elif feature.available_at is not None:
            available_times = [
                by_id[item.evidence_id].available_at
                for item in feature.dependencies
                if by_id[item.evidence_id].available_at is not None
            ]
            if available_times and feature.available_at < max(available_times):
                raise EvidenceContractError(
                    "unavailable output claims an early availability"
                )

    @staticmethod
    def _validate_acyclic(by_id: Mapping[UUID, SourceFact | DerivedFeature]) -> None:
        visiting: set[UUID] = set()
        visited: set[UUID] = set()

        def visit(node_id: UUID) -> None:
            if node_id in visiting:
                raise EvidenceContractError("evidence dependency cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            node = by_id[node_id]
            if isinstance(node, DerivedFeature):
                for dependency in node.dependencies:
                    visit(dependency.evidence_id)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in by_id:
            visit(node_id)

    @property
    def _by_id(self) -> Mapping[UUID, SourceFact | DerivedFeature]:
        return self._index

    def node_for(self, evidence_id: UUID) -> SourceFact | DerivedFeature:
        _uuid(evidence_id, "evidence_id")
        try:
            return self._by_id[evidence_id]
        except KeyError as error:
            raise KeyError(f"unknown evidence ID: {evidence_id}") from error

    def closure(self, evidence_id: UUID) -> tuple[UUID, ...]:
        self.node_for(evidence_id)
        ordered: list[UUID] = []
        seen: set[UUID] = set()

        def walk(node_id: UUID) -> None:
            if node_id in seen:
                return
            seen.add(node_id)
            ordered.append(node_id)
            node = self.node_for(node_id)
            if isinstance(node, DerivedFeature):
                for dependency in node.dependencies:
                    walk(dependency.evidence_id)

        walk(evidence_id)
        return tuple(ordered)

    def source_closure(self, evidence_id: UUID) -> tuple[UUID, ...]:
        return tuple(
            item
            for item in self.closure(evidence_id)
            if isinstance(self.node_for(item), SourceFact)
        )

    @property
    def source_ids(self) -> tuple[UUID, ...]:
        return tuple(
            node.evidence_id for node in self.nodes if isinstance(node, SourceFact)
        )

    @property
    def edges(self) -> tuple[EvidenceEdge, ...]:
        return tuple(
            EvidenceEdge(dependency.evidence_id, feature.evidence_id, dependency.role)
            for feature in self.nodes
            if isinstance(feature, DerivedFeature)
            for dependency in feature.dependencies
        )


__all__ = [
    "AvailabilityReason",
    "AvailabilityStatus",
    "DerivedFeature",
    "EvidenceContractError",
    "EvidenceDependency",
    "EvidenceEdge",
    "EvidenceGraph",
    "EvidenceOutcome",
    "EvidenceSubject",
    "EvidenceTimeframe",
    "EvidenceTimeframeKind",
    "SnapshotMode",
    "SourceFact",
    "VersionAsOfWitness",
    "momentum_12m_minus_1m",
    "ratio",
    "research_identity",
    "simple_return",
]
