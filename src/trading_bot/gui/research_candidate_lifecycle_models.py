"""Bounded Qt-free local lifecycle evidence; no external-chain authority."""

from dataclasses import dataclass, field, fields
from datetime import UTC, date, datetime
from enum import Enum
from re import fullmatch
from uuid import UUID

LOCAL_VERIFICATION_SCOPE = (
    "Canonical local artifacts and SHADOW successor linkage verified. "
    "Full historical external-chain qualification was not re-run by this GUI."
)
RANK_NOTICE = "Original rank is retained as evidence only; rank grants no authority."


class ResearchCandidateLifecyclePageStatus(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    ATTENTION = "ATTENTION"


class ResearchCandidateLifecycleDiagnostic(Enum):
    NOT_CONFIGURED = "No research lifecycle artifact set is connected."
    LOCAL_LINKAGE = LOCAL_VERIFICATION_SCOPE
    INVALID = (
        "Selected research lifecycle evidence could not be inspected within the "
        "local bounds or failed canonical parsing or SHADOW successor linkage."
    )


class ResearchCandidateLifecycleStage(Enum):
    SHADOW = "SHADOW"


class LifecycleQualificationStatus(Enum):
    PASSED = "PASSED"


def _integer(value: int, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Exact bounded integer required")


@dataclass(frozen=True, slots=True)
class LifecycleSourceView:
    head: str
    tree: str

    def __post_init__(self) -> None:
        for value in (self.head, self.tree):
            if type(value) is not str or fullmatch(r"[0-9a-f]{40}", value) is None:
                raise ValueError("Exact lowercase source digest required")


@dataclass(frozen=True, slots=True)
class LifecycleZeroEffectsView:
    credential_reads: int
    provider_calls: int
    robinhood_reads: int
    broker_calls: int
    paper_mutations: int
    scheduler_calls: int
    acl_mutations: int
    production_sqlite_reads: int
    production_sqlite_writes: int

    def __post_init__(self) -> None:
        for item in fields(self):
            _integer(getattr(self, item.name), 0, 0)


@dataclass(frozen=True, slots=True)
class LifecycleObservationView:
    observation_count: int
    distinct_session_count: int
    first_session_date: date
    last_session_date: date
    first_observed_at_utc: datetime
    last_observed_at_utc: datetime
    zero_effects: LifecycleZeroEffectsView

    def __post_init__(self) -> None:
        _integer(self.observation_count, 1, 100_000)
        _integer(self.distinct_session_count, 1, self.observation_count)
        for value in (self.first_session_date, self.last_session_date):
            if type(value) is not date:
                raise TypeError("Exact session date required")
        for value in (self.first_observed_at_utc, self.last_observed_at_utc):
            if type(value) is not datetime or value.tzinfo is not UTC or value.fold:
                raise ValueError("Exact UTC timestamp required")
        if (
            self.first_session_date > self.last_session_date
            or self.first_observed_at_utc > self.last_observed_at_utc
        ):
            raise ValueError("Ordered observation range required")
        if type(self.zero_effects) is not LifecycleZeroEffectsView:
            raise TypeError("Exact zero effect presentation required")


@dataclass(frozen=True, slots=True)
class LifecycleQualificationView:
    minimum_session_count: int
    minimum_total_observation_count: int
    minimum_observations_per_session: int
    observation_count: int
    distinct_session_count: int
    minimum_observations_in_any_session: int
    status: LifecycleQualificationStatus
    failure_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for item in fields(self):
            if item.name not in ("status", "failure_reasons"):
                _integer(getattr(self, item.name), 1, 100_000)
        if type(self.status) is not LifecycleQualificationStatus:
            raise TypeError("Exact PASSED qualification status required")
        if type(self.failure_reasons) is not tuple or self.failure_reasons:
            raise ValueError("SHADOW requires empty ordered failure reasons")
        if (
            self.minimum_total_observation_count
            < self.minimum_session_count * self.minimum_observations_per_session
            or self.distinct_session_count < self.minimum_session_count
            or self.observation_count < self.minimum_total_observation_count
            or self.minimum_observations_in_any_session
            < self.minimum_observations_per_session
            or self.observation_count
            < self.distinct_session_count * self.minimum_observations_in_any_session
        ):
            raise ValueError("Inconsistent PASSED coverage presentation")


@dataclass(frozen=True, slots=True)
class ResearchCandidateLifecycleView:
    shadow_candidate_id: UUID
    walk_forward_passed_candidate_id: UUID
    backtested_candidate_id: UUID
    walk_forward_qualification_id: UUID
    binding_id: UUID
    observation_batch_id: UUID
    qualification_id: UUID
    report_id: UUID
    experiment_result_id: UUID
    variant_id: UUID
    caller_ordinal: int
    variant_name: str
    rank: int | None
    candidate_source: LifecycleSourceView
    walk_forward_qualification_source: LifecycleSourceView
    binding_source: LifecycleSourceView
    observation_source: LifecycleSourceView
    qualification_source: LifecycleSourceView
    observations: LifecycleObservationView
    qualification: LifecycleQualificationView
    stage: ResearchCandidateLifecycleStage = field(
        default=ResearchCandidateLifecycleStage.SHADOW, init=False
    )

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name.endswith("_id") and type(value) is not UUID:
                raise TypeError("Exact lifecycle UUID required")
            if item.name.endswith("_source") and type(value) is not LifecycleSourceView:
                raise TypeError("Exact lifecycle source presentation required")
        _integer(self.caller_ordinal, 0, 1_000_000)
        if self.rank is not None:
            _integer(self.rank, 1, 1_000_000)
        name = self.variant_name
        if (
            type(name) is not str
            or not name
            or name != name.strip()
            or len(name) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
        ):
            raise ValueError("Bounded canonical variant text required")
        name.encode("utf-8", errors="strict")
        if (
            type(self.observations) is not LifecycleObservationView
            or type(self.qualification) is not LifecycleQualificationView
        ):
            raise TypeError("Complete lifecycle evidence presentation required")
        if (
            self.observations.observation_count != self.qualification.observation_count
            or self.observations.distinct_session_count
            != self.qualification.distinct_session_count
        ):
            raise ValueError("Observation and qualification counts conflict")

    @property
    def artifact_identifiers(self) -> tuple[tuple[str, UUID], ...]:
        """Five canonical artifact identities for pure audit/navigation adapters."""
        return (
            ("WALK_FORWARD_PASSED candidate", self.walk_forward_passed_candidate_id),
            ("139-A binding", self.binding_id),
            ("B1 observation batch", self.observation_batch_id),
            ("B2 qualification", self.qualification_id),
            ("SHADOW candidate", self.shadow_candidate_id),
        )


@dataclass(frozen=True, slots=True)
class ResearchCandidateLifecyclePageState:
    status: ResearchCandidateLifecyclePageStatus
    diagnostic: ResearchCandidateLifecycleDiagnostic
    evidence: ResearchCandidateLifecycleView | None = None
    automatic_promotion_enabled: bool = field(default=False, init=False)
    human_promotion_required: bool = field(default=True, init=False)
    promotion_authority_connected: bool = field(default=False, init=False)
    can_research_replace_production: bool = field(default=False, init=False)
    full_external_research_chain_verified_by_gui: bool = field(
        default=False, init=False
    )

    def __post_init__(self) -> None:
        if (
            type(self.status) is not ResearchCandidateLifecyclePageStatus
            or type(self.diagnostic) is not ResearchCandidateLifecycleDiagnostic
        ):
            raise TypeError("Exact lifecycle classifications required")
        expected = {
            ResearchCandidateLifecycleDiagnostic.NOT_CONFIGURED: (
                ResearchCandidateLifecyclePageStatus.UNAVAILABLE
            ),
            ResearchCandidateLifecycleDiagnostic.LOCAL_LINKAGE: (
                ResearchCandidateLifecyclePageStatus.AVAILABLE
            ),
            ResearchCandidateLifecycleDiagnostic.INVALID: (
                ResearchCandidateLifecyclePageStatus.ATTENTION
            ),
        }[self.diagnostic]
        if self.status is not expected:
            raise ValueError("Lifecycle classifications conflict")
        if self.status is ResearchCandidateLifecyclePageStatus.AVAILABLE:
            if type(self.evidence) is not ResearchCandidateLifecycleView:
                raise TypeError("AVAILABLE requires complete lifecycle evidence")
        elif self.evidence is not None:
            raise ValueError("Unavailable or invalid state cannot retain evidence")

    @property
    def message(self) -> str:
        return self.diagnostic.value


def unavailable_research_candidate_lifecycle_state() -> (
    ResearchCandidateLifecyclePageState
):
    return ResearchCandidateLifecyclePageState(
        ResearchCandidateLifecyclePageStatus.UNAVAILABLE,
        ResearchCandidateLifecycleDiagnostic.NOT_CONFIGURED,
    )
