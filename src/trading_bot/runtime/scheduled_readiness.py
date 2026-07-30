"""Pure deterministic identities and readiness decisions for scheduled paper runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.market_data.daily_snapshot_models import (
    XNYS_CALENDAR_DESCRIPTOR,
    CalendarDescriptor,
    ProviderDescriptor,
)
from trading_bot.market_data.models import AdjustmentType, Timeframe

SCHEDULED_CAPTURE_ATTEMPT_RECORD_SCHEMA_VERSION = 1
SCHEDULED_SNAPSHOT_SELECTION_SCHEMA_VERSION = 1
SCHEDULED_PAPER_SESSION_MATERIAL_VERSION = "scheduled-paper-session-v1"
SCHEDULED_LAUNCH_MATERIAL_VERSION = "scheduled-launch-v1"
SCHEDULED_CAPTURE_ATTEMPT_MATERIAL_VERSION = "scheduled-capture-attempt-v1"
SCHEDULED_SNAPSHOT_SELECTION_MATERIAL_VERSION = "scheduled-snapshot-selection-v1"
SCHEDULER_CALLER_IDEMPOTENCY_MATERIAL_VERSION = "scheduler-caller-idempotency-key-v1"

SCHEDULED_PAPER_SESSION_NAMESPACE = UUID("1a3373dc-b18e-583b-b983-b60336bfa7ea")
SCHEDULED_LAUNCH_NAMESPACE = UUID("4f62bcb9-1e06-55fa-82b8-d1293447390b")
SCHEDULED_CAPTURE_ATTEMPT_NAMESPACE = UUID("b9ebad76-c89b-5df0-9256-203f0cee267a")
SCHEDULED_SNAPSHOT_SELECTION_NAMESPACE = UUID("261aef12-6159-5def-9508-56b406b649d8")
SCHEDULER_CALLER_IDEMPOTENCY_NAMESPACE = UUID("fac48241-5672-5ce3-9014-9ed29b47d07a")

MAX_SCHEDULED_ARTIFACT_BYTES = 256 * 1024
MAX_SCHEDULED_COLLECTION_ITEMS = 100
MAX_SCHEDULED_TEXT_CHARACTERS = 256
MAX_SCHEDULED_INTEGER = (1 << 63) - 1

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]*$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_NEW_YORK = ZoneInfo("America/New_York")


class ScheduledReadinessModelError(ValueError):
    """Raised when explicit scheduled-readiness material is invalid."""


class ScheduledArtifactSyntaxError(ScheduledReadinessModelError):
    """Raised when scheduled artifact bytes are not strict JSON."""


class ScheduledPhase(StrEnum):
    CAPTURE = "CAPTURE"
    OPERATION = "OPERATION"


class MarketSessionHoursKind(StrEnum):
    REGULAR = "REGULAR"
    EARLY_CLOSE = "EARLY_CLOSE"


class CaptureAttemptStatus(StrEnum):
    PASS = "PASS"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SnapshotChronologyResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class SnapshotReadinessClassification(StrEnum):
    CAPTURE_TOO_EARLY = "CAPTURE_TOO_EARLY"
    CAPTURE_WINDOW_OPEN = "CAPTURE_WINDOW_OPEN"
    CAPTURE_DEADLINE_PASSED = "CAPTURE_DEADLINE_PASSED"
    NO_ATTEMPTS = "NO_ATTEMPTS"
    CAPTURE_BACKOFF_ACTIVE = "CAPTURE_BACKOFF_ACTIVE"
    CAPTURE_ATTEMPTS_EXHAUSTED = "CAPTURE_ATTEMPTS_EXHAUSTED"
    VALID_SELECTED_SNAPSHOT = "VALID_SELECTED_SNAPSHOT"
    SNAPSHOT_NOT_SELECTED = "SNAPSHOT_NOT_SELECTED"
    SNAPSHOT_TARGET_MISMATCH = "SNAPSHOT_TARGET_MISMATCH"
    SYMBOL_UNIVERSE_MISMATCH = "SYMBOL_UNIVERSE_MISMATCH"
    PROVIDER_POLICY_MISMATCH = "PROVIDER_POLICY_MISMATCH"
    INCOMPLETE_OR_REJECTED_SNAPSHOT = "INCOMPLETE_OR_REJECTED_SNAPSHOT"
    SNAPSHOT_CAPTURED_BEFORE_TERMINAL = "SNAPSHOT_CAPTURED_BEFORE_TERMINAL"
    SNAPSHOT_FUTURE_SKEW = "SNAPSHOT_FUTURE_SKEW"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    DUPLICATE_ELIGIBLE_CAPTURES = "DUPLICATE_ELIGIBLE_CAPTURES"
    SELECTION_RECORD_MISMATCH = "SELECTION_RECORD_MISMATCH"
    CONFLICTING_CAPTURE_RECORDS = "CONFLICTING_CAPTURE_RECORDS"


class ScheduledReadinessClassification(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    BLOCKED = "BLOCKED"
    CONFLICTING = "CONFLICTING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class ScheduledReadinessCode(StrEnum):
    HEAD_UNVERIFIED = "HEAD_UNVERIFIED"
    HEAD_ADVANCEMENT_PENDING = "HEAD_ADVANCEMENT_PENDING"
    MANUAL_DISABLE_ACTIVE = "MANUAL_DISABLE_ACTIVE"
    MARKET_HOURS_UNAVAILABLE = "MARKET_HOURS_UNAVAILABLE"
    CAPTURE_TOO_EARLY = "CAPTURE_TOO_EARLY"
    CAPTURE_WINDOW_EXPIRED = "CAPTURE_WINDOW_EXPIRED"
    CAPTURE_BACKOFF_ACTIVE = "CAPTURE_BACKOFF_ACTIVE"
    CAPTURE_ATTEMPTS_EXHAUSTED = "CAPTURE_ATTEMPTS_EXHAUSTED"
    SNAPSHOT_NOT_SELECTED = "SNAPSHOT_NOT_SELECTED"
    SNAPSHOT_INELIGIBLE = "SNAPSHOT_INELIGIBLE"
    SNAPSHOT_TERMINAL_CHRONOLOGY_FAILURE = "SNAPSHOT_TERMINAL_CHRONOLOGY_FAILURE"
    SNAPSHOT_FUTURE_SKEW = "SNAPSHOT_FUTURE_SKEW"
    SESSION_MISMATCH = "SESSION_MISMATCH"
    EXECUTION_CHRONOLOGY_FAILURE = "EXECUTION_CHRONOLOGY_FAILURE"
    TARGET_AUTHORITY_MISSING = "TARGET_AUTHORITY_MISSING"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    RELEASE_NOT_APPROVED = "RELEASE_NOT_APPROVED"
    OPERATION_CREDENTIALS_PRESENT = "OPERATION_CREDENTIALS_PRESENT"
    AUDIT_UNHEALTHY = "AUDIT_UNHEALTHY"
    NOTIFICATION_UNAVAILABLE = "NOTIFICATION_UNAVAILABLE"
    BACKUP_REQUIREMENT_UNMET = "BACKUP_REQUIREMENT_UNMET"
    DISK_WATERMARK_BLOCKED = "DISK_WATERMARK_BLOCKED"
    COORDINATOR_PENDING = "COORDINATOR_PENDING"
    OPERATION_ALREADY_COMPLETED = "OPERATION_ALREADY_COMPLETED"
    OPERATION_BLOCKED = "OPERATION_BLOCKED"
    OPERATION_CONFLICTING = "OPERATION_CONFLICTING"
    FAILED_RECEIPT_REQUIRES_REVIEW = "FAILED_RECEIPT_REQUIRES_REVIEW"
    STAGING_REQUIRES_REVIEW = "STAGING_REQUIRES_REVIEW"
    SCHEDULED_IDENTITY_MISMATCH = "SCHEDULED_IDENTITY_MISMATCH"
    SNAPSHOT_SELECTION_CONFLICT = "SNAPSHOT_SELECTION_CONFLICT"


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    artifact_id: UUID
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_uuid(self.artifact_id, "artifact_id")
        _require_evidence(self.sha256, self.byte_length, "artifact")


@dataclass(frozen=True, slots=True)
class HeadRecordEvidence:
    authority_epoch_id: UUID
    record: ArtifactEvidence
    generation: int

    def __post_init__(self) -> None:
        _require_uuid(self.authority_epoch_id, "authority_epoch_id")
        if type(self.record) is not ArtifactEvidence:
            raise ScheduledReadinessModelError("record must be ArtifactEvidence")
        _require_nonnegative(self.generation, "generation")


@dataclass(frozen=True, slots=True)
class TerminalCheckpointEvidence:
    checkpoint: ArtifactEvidence
    sequence: int
    as_of: datetime

    def __post_init__(self) -> None:
        if type(self.checkpoint) is not ArtifactEvidence:
            raise ScheduledReadinessModelError("checkpoint must be ArtifactEvidence")
        _require_nonnegative(self.sequence, "sequence")
        object.__setattr__(self, "as_of", _utc(self.as_of, "as_of"))


@dataclass(frozen=True, slots=True)
class VerifiedAuthoritativeHeadInput:
    head_record: HeadRecordEvidence
    verified_lineage_evidence_id: UUID
    terminal_checkpoint: TerminalCheckpointEvidence
    verification_passed: bool

    def __post_init__(self) -> None:
        if (
            type(self.head_record) is not HeadRecordEvidence
            or type(self.terminal_checkpoint) is not TerminalCheckpointEvidence
            or type(self.verification_passed) is not bool
        ):
            raise ScheduledReadinessModelError("authoritative-head input is invalid")
        _require_uuid(self.verified_lineage_evidence_id, "verified_lineage_evidence_id")
        if (
            self.head_record.generation != self.terminal_checkpoint.sequence
            or self.head_record.record.artifact_id == UUID(int=0)
        ):
            raise ScheduledReadinessModelError(
                "authoritative head and terminal do not reconcile"
            )


@dataclass(frozen=True, slots=True)
class SnapshotEvidence:
    artifact: ArtifactEvidence
    target_session: TradingSession
    captured_at: datetime
    symbols: tuple[Symbol, ...]
    provider: ProviderDescriptor
    timeframe: Timeframe
    adjustment: AdjustmentType
    feed: str
    currency: str
    verification_passed: bool
    complete: bool

    def __post_init__(self) -> None:
        if type(self.artifact) is not ArtifactEvidence:
            raise ScheduledReadinessModelError("snapshot artifact is invalid")
        _require_session(self.target_session, "target_session")
        object.__setattr__(self, "captured_at", _utc(self.captured_at, "captured_at"))
        object.__setattr__(self, "symbols", _symbols(self.symbols))
        if type(self.provider) is not ProviderDescriptor:
            raise ScheduledReadinessModelError("provider is invalid")
        if type(self.timeframe) is not Timeframe:
            raise ScheduledReadinessModelError("timeframe is invalid")
        if type(self.adjustment) is not AdjustmentType:
            raise ScheduledReadinessModelError("adjustment is invalid")
        _require_text(self.feed, "feed")
        if type(self.currency) is not str or _CURRENCY.fullmatch(self.currency) is None:
            raise ScheduledReadinessModelError("currency must be uppercase ISO text")
        if (
            type(self.verification_passed) is not bool
            or type(self.complete) is not bool
        ):
            raise ScheduledReadinessModelError(
                "snapshot verification flags must be bools"
            )


@dataclass(frozen=True, slots=True)
class MarketSessionHours:
    session: TradingSession
    opens_at: datetime
    closes_at: datetime
    kind: MarketSessionHoursKind

    def __post_init__(self) -> None:
        _require_session(self.session, "session")
        opens_at = _utc(self.opens_at, "opens_at")
        closes_at = _utc(self.closes_at, "closes_at")
        if type(self.kind) is not MarketSessionHoursKind:
            raise ScheduledReadinessModelError("hours kind is invalid")
        local_open = opens_at.astimezone(_NEW_YORK)
        local_close = closes_at.astimezone(_NEW_YORK)
        expected_close = (
            time(16, 0) if self.kind is MarketSessionHoursKind.REGULAR else time(13, 0)
        )
        if (
            local_open.date() != self.session.session_date
            or local_close.date() != self.session.session_date
            or local_open.time().replace(tzinfo=None) != time(9, 30)
            or local_close.time().replace(tzinfo=None) != expected_close
            or closes_at <= opens_at
        ):
            raise ScheduledReadinessModelError(
                "session hours do not match explicit XNYS regular/early-close policy"
            )
        object.__setattr__(self, "opens_at", opens_at)
        object.__setattr__(self, "closes_at", closes_at)


@dataclass(frozen=True, slots=True)
class MarketSessionHoursSchedule:
    calendar: CalendarDescriptor
    schedule_version: str
    coverage_start: date
    coverage_end: date
    entries: tuple[MarketSessionHours, ...]
    exceptional_closures: tuple[date, ...]
    authority_evidence: ArtifactEvidence

    def __post_init__(self) -> None:
        if self.calendar != XNYS_CALENDAR_DESCRIPTOR:
            raise ScheduledReadinessModelError(
                "schedule must bind the exact supported XNYS descriptor"
            )
        _require_text(self.schedule_version, "schedule_version")
        if (
            type(self.coverage_start) is not date
            or type(self.coverage_end) is not date
            or self.coverage_start > self.coverage_end
        ):
            raise ScheduledReadinessModelError("schedule coverage is invalid")
        entries = _bounded_tuple(self.entries, "entries")
        closures = _bounded_tuple(self.exceptional_closures, "exceptional_closures")
        if any(type(item) is not MarketSessionHours for item in entries):
            raise ScheduledReadinessModelError("schedule entries are invalid")
        if any(type(item) is not date for item in closures):
            raise ScheduledReadinessModelError("exceptional closures are invalid")
        entry_dates = tuple(item.session.session_date for item in entries)
        if tuple(sorted(entry_dates)) != entry_dates or len(set(entry_dates)) != len(
            entry_dates
        ):
            raise ScheduledReadinessModelError(
                "schedule entries must be unique and ordered"
            )
        if tuple(sorted(closures)) != closures or len(set(closures)) != len(closures):
            raise ScheduledReadinessModelError(
                "exceptional closures must be unique and ordered"
            )
        if set(entry_dates) & set(closures):
            raise ScheduledReadinessModelError(
                "a session cannot be both open and exceptionally closed"
            )
        modeled = _modeled_sessions(self.coverage_start, self.coverage_end)
        if tuple(sorted((*entry_dates, *closures))) != modeled:
            raise ScheduledReadinessModelError(
                "schedule has missing, non-session, or ambiguous closure entries"
            )
        if type(self.authority_evidence) is not ArtifactEvidence:
            raise ScheduledReadinessModelError("schedule authority evidence is invalid")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "exceptional_closures", closures)

    def hours_for(self, session: TradingSession) -> MarketSessionHours | None:
        _require_session(session, "session")
        return next((item for item in self.entries if item.session == session), None)


@dataclass(frozen=True, slots=True)
class CapturePolicy:
    policy_version: str
    publication_delay_seconds: int
    capture_cutoff_guard_seconds: int
    maximum_attempts: int
    fixed_backoffs_seconds: tuple[int, ...]
    maximum_clock_skew_seconds: int
    maximum_acceptable_lateness_seconds: int
    symbols: tuple[Symbol, ...]
    timeframe: Timeframe
    adjustment: AdjustmentType
    provider: ProviderDescriptor
    feed: str
    currency: str
    configuration_evidence: ArtifactEvidence

    def __post_init__(self) -> None:
        _require_text(self.policy_version, "policy_version")
        for name in (
            "publication_delay_seconds",
            "capture_cutoff_guard_seconds",
            "maximum_clock_skew_seconds",
            "maximum_acceptable_lateness_seconds",
        ):
            _require_nonnegative(getattr(self, name), name)
        if (
            type(self.maximum_attempts) is not int
            or not 1 <= self.maximum_attempts <= MAX_SCHEDULED_COLLECTION_ITEMS
        ):
            raise ScheduledReadinessModelError("maximum_attempts is invalid")
        backoffs = _bounded_tuple(self.fixed_backoffs_seconds, "fixed_backoffs_seconds")
        if len(backoffs) != self.maximum_attempts - 1 or any(
            type(value) is not int or value < 0 for value in backoffs
        ):
            raise ScheduledReadinessModelError(
                "fixed backoffs must define every retry interval"
            )
        object.__setattr__(self, "fixed_backoffs_seconds", backoffs)
        object.__setattr__(self, "symbols", _symbols(self.symbols))
        if (
            self.timeframe is not Timeframe.DAY_1
            or self.adjustment is not AdjustmentType.RAW
            or type(self.provider) is not ProviderDescriptor
        ):
            raise ScheduledReadinessModelError(
                "capture market-data policy is unsupported"
            )
        _require_text(self.feed, "feed")
        if self.provider.feed != self.feed:
            raise ScheduledReadinessModelError("provider and policy feed must match")
        if type(self.currency) is not str or _CURRENCY.fullmatch(self.currency) is None:
            raise ScheduledReadinessModelError("currency must be uppercase ISO text")
        if type(self.configuration_evidence) is not ArtifactEvidence:
            raise ScheduledReadinessModelError(
                "capture configuration evidence is invalid"
            )


@dataclass(frozen=True, slots=True)
class ScheduledCaptureAttemptRecord:
    schema_version: int
    attempt_id: UUID
    scheduled_session_id: UUID
    attempt_ordinal: int
    symbols: tuple[Symbol, ...]
    timeframe: Timeframe
    adjustment: AdjustmentType
    provider: ProviderDescriptor
    feed: str
    currency: str
    capture_policy_version: str
    configuration_evidence: ArtifactEvidence
    started_at: datetime
    completed_at: datetime
    status: CaptureAttemptStatus
    snapshot: SnapshotEvidence | None
    terminal_code: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEDULED_CAPTURE_ATTEMPT_RECORD_SCHEMA_VERSION:
            raise ScheduledReadinessModelError("attempt schema_version must be 1")
        _require_uuid(self.attempt_id, "attempt_id")
        _require_uuid(self.scheduled_session_id, "scheduled_session_id")
        _require_nonnegative(self.attempt_ordinal, "attempt_ordinal")
        symbols = _symbols(self.symbols)
        if (
            type(self.provider) is not ProviderDescriptor
            or type(self.timeframe) is not Timeframe
            or type(self.adjustment) is not AdjustmentType
        ):
            raise ScheduledReadinessModelError("attempt market-data policy is invalid")
        _require_text(self.feed, "feed")
        if self.provider.feed != self.feed:
            raise ScheduledReadinessModelError("attempt provider feed is inconsistent")
        if type(self.currency) is not str or _CURRENCY.fullmatch(self.currency) is None:
            raise ScheduledReadinessModelError("attempt currency is invalid")
        _require_text(self.capture_policy_version, "capture_policy_version")
        if type(self.configuration_evidence) is not ArtifactEvidence:
            raise ScheduledReadinessModelError(
                "attempt configuration evidence is invalid"
            )
        started = _utc(self.started_at, "started_at")
        completed = _utc(self.completed_at, "completed_at")
        if completed < started or type(self.status) is not CaptureAttemptStatus:
            raise ScheduledReadinessModelError("attempt terminal state is invalid")
        if self.status is CaptureAttemptStatus.PASS:
            if (
                type(self.snapshot) is not SnapshotEvidence
                or not self.snapshot.verification_passed
                or not self.snapshot.complete
                or self.terminal_code != "PASS"
            ):
                raise ScheduledReadinessModelError(
                    "PASS attempt requires complete verified snapshot evidence"
                )
        elif self.snapshot is not None or not self.terminal_code:
            raise ScheduledReadinessModelError(
                "non-PASS attempt must retain only a terminal code"
            )
        expected = derive_scheduled_capture_attempt_id(
            self.scheduled_session_id,
            self.attempt_ordinal,
            symbols,
            self.timeframe,
            self.adjustment,
            self.provider,
            self.feed,
            self.currency,
            self.capture_policy_version,
            self.configuration_evidence,
        )
        if self.attempt_id != expected:
            raise ScheduledReadinessModelError(
                "attempt_id does not match canonical material"
            )
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)


@dataclass(frozen=True, slots=True)
class ScheduledSnapshotSelectionRecord:
    schema_version: int
    selection_id: UUID
    scheduled_session_id: UUID
    head_record: HeadRecordEvidence
    terminal_checkpoint: TerminalCheckpointEvidence
    capture_attempts: tuple[ArtifactEvidence, ...]
    selected_attempt_id: UUID
    selected_snapshot: ArtifactEvidence
    selection_policy_version: str
    chronology_result: SnapshotChronologyResult

    def __post_init__(self) -> None:
        if self.schema_version != SCHEDULED_SNAPSHOT_SELECTION_SCHEMA_VERSION:
            raise ScheduledReadinessModelError("selection schema_version must be 1")
        _require_uuid(self.selection_id, "selection_id")
        _require_uuid(self.scheduled_session_id, "scheduled_session_id")
        if (
            type(self.head_record) is not HeadRecordEvidence
            or type(self.terminal_checkpoint) is not TerminalCheckpointEvidence
        ):
            raise ScheduledReadinessModelError(
                "selection authority evidence is invalid"
            )
        attempts = _bounded_tuple(self.capture_attempts, "capture_attempts")
        if not attempts or any(type(item) is not ArtifactEvidence for item in attempts):
            raise ScheduledReadinessModelError("selection attempt evidence is invalid")
        if len({item.artifact_id for item in attempts}) != len(attempts):
            raise ScheduledReadinessModelError(
                "selection attempt evidence must be unique"
            )
        _require_uuid(self.selected_attempt_id, "selected_attempt_id")
        if self.selected_attempt_id not in {item.artifact_id for item in attempts}:
            raise ScheduledReadinessModelError(
                "selected attempt must be present in ordered evidence"
            )
        if type(self.selected_snapshot) is not ArtifactEvidence:
            raise ScheduledReadinessModelError("selected snapshot evidence is invalid")
        _require_text(self.selection_policy_version, "selection_policy_version")
        if type(self.chronology_result) is not SnapshotChronologyResult:
            raise ScheduledReadinessModelError("chronology result is invalid")
        expected = derive_scheduled_snapshot_selection_id(
            self.scheduled_session_id,
            self.head_record,
            self.terminal_checkpoint,
            attempts,
            self.selected_attempt_id,
            self.selected_snapshot,
            self.selection_policy_version,
            self.chronology_result,
        )
        if self.selection_id != expected:
            raise ScheduledReadinessModelError(
                "selection_id does not match canonical material"
            )
        object.__setattr__(self, "capture_attempts", attempts)


@dataclass(frozen=True, slots=True)
class ScheduledHealthInputs:
    disk_watermark_ok: bool
    audit_ok: bool
    notification_ok: bool
    backup_ok: bool
    credential_isolation_ok: bool
    operation_credentials_present: bool

    def __post_init__(self) -> None:
        if any(
            type(getattr(self, name)) is not bool
            for name in (
                "disk_watermark_ok",
                "audit_ok",
                "notification_ok",
                "backup_ok",
                "credential_isolation_ok",
                "operation_credentials_present",
            )
        ):
            raise ScheduledReadinessModelError("health inputs must be explicit bools")


@dataclass(frozen=True, slots=True)
class ScheduledCycleInputs:
    cycle_request: ArtifactEvidence
    cycle_configuration: ArtifactEvidence
    selected_snapshot: ArtifactEvidence
    planning_at: datetime
    submitted_at: datetime
    filled_at: datetime
    expected_caller_idempotency_key: UUID
    target_authority_version: str
    target_authority: ArtifactEvidence
    approved_release: ArtifactEvidence
    release_approved: bool
    approval_required: bool
    approval: ArtifactEvidence | None

    def __post_init__(self) -> None:
        if any(
            type(value) is not ArtifactEvidence
            for value in (
                self.cycle_request,
                self.cycle_configuration,
                self.selected_snapshot,
                self.target_authority,
                self.approved_release,
            )
        ):
            raise ScheduledReadinessModelError("cycle artifact evidence is invalid")
        planning = _utc(self.planning_at, "planning_at")
        submitted = _utc(self.submitted_at, "submitted_at")
        filled = _utc(self.filled_at, "filled_at")
        _require_uuid(
            self.expected_caller_idempotency_key,
            "expected_caller_idempotency_key",
        )
        _require_text(self.target_authority_version, "target_authority_version")
        if (
            type(self.release_approved) is not bool
            or type(self.approval_required) is not bool
        ):
            raise ScheduledReadinessModelError("cycle approval flags are invalid")
        if self.approval is not None and type(self.approval) is not ArtifactEvidence:
            raise ScheduledReadinessModelError("approval evidence is invalid")
        object.__setattr__(self, "planning_at", planning)
        object.__setattr__(self, "submitted_at", submitted)
        object.__setattr__(self, "filled_at", filled)


@dataclass(frozen=True, slots=True)
class CoordinatorInspectionInput:
    classification: str
    terminal_checkpoint_id: UUID
    diagnostic: str
    successor_checkpoint_id: UUID | None = None
    completed_receipt_verified: bool = False
    transition_verified: bool = False
    head_advanced_to_successor: bool = False

    def __post_init__(self) -> None:
        if self.classification not in {
            "PENDING",
            "ALREADY_APPLIED",
            "BLOCKED",
            "CONFLICTING",
        }:
            raise ScheduledReadinessModelError("coordinator classification is invalid")
        _require_uuid(self.terminal_checkpoint_id, "terminal_checkpoint_id")
        _require_text(self.diagnostic, "diagnostic")
        if (
            self.successor_checkpoint_id is not None
            and type(self.successor_checkpoint_id) is not UUID
        ):
            raise ScheduledReadinessModelError(
                "successor_checkpoint_id must be a UUID or None"
            )
        if any(
            type(getattr(self, name)) is not bool
            for name in (
                "completed_receipt_verified",
                "transition_verified",
                "head_advanced_to_successor",
            )
        ):
            raise ScheduledReadinessModelError(
                "coordinator verification flags are invalid"
            )


@dataclass(frozen=True, slots=True)
class ScheduledReadinessInputs:
    authoritative_head: VerifiedAuthoritativeHeadInput | None
    target_session: TradingSession
    execution_session: TradingSession
    observed_at: datetime
    market_hours: MarketSessionHoursSchedule | None
    capture_policy: CapturePolicy
    capture_attempts: tuple[ScheduledCaptureAttemptRecord, ...]
    selected_snapshot: SnapshotEvidence | None
    snapshot_selection: ScheduledSnapshotSelectionRecord | None
    cycle: ScheduledCycleInputs | None
    scheduled_session_id: UUID
    universe_policy_version: str
    readiness_policy_version: str
    selection_policy_version: str
    manual_disable_active: bool
    head_advancement_pending: bool
    health: ScheduledHealthInputs
    coordinator: CoordinatorInspectionInput | None
    staging_present: bool = False
    failed_receipt_verified: bool = False
    transition_without_receipt: bool = False

    def __post_init__(self) -> None:
        if (
            self.authoritative_head is not None
            and type(self.authoritative_head) is not VerifiedAuthoritativeHeadInput
        ):
            raise ScheduledReadinessModelError("authoritative_head is invalid")
        _require_session(self.target_session, "target_session")
        _require_session(self.execution_session, "execution_session")
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))
        if (
            self.market_hours is not None
            and type(self.market_hours) is not MarketSessionHoursSchedule
        ):
            raise ScheduledReadinessModelError("market_hours is invalid")
        if type(self.capture_policy) is not CapturePolicy:
            raise ScheduledReadinessModelError("capture_policy is invalid")
        attempts = _bounded_tuple(self.capture_attempts, "capture_attempts")
        if any(type(item) is not ScheduledCaptureAttemptRecord for item in attempts):
            raise ScheduledReadinessModelError("capture_attempts are invalid")
        if (
            self.selected_snapshot is not None
            and type(self.selected_snapshot) is not SnapshotEvidence
        ):
            raise ScheduledReadinessModelError("selected_snapshot is invalid")
        if (
            self.snapshot_selection is not None
            and type(self.snapshot_selection) is not ScheduledSnapshotSelectionRecord
        ):
            raise ScheduledReadinessModelError("snapshot_selection is invalid")
        if self.cycle is not None and type(self.cycle) is not ScheduledCycleInputs:
            raise ScheduledReadinessModelError("cycle is invalid")
        _require_uuid(self.scheduled_session_id, "scheduled_session_id")
        for name in (
            "universe_policy_version",
            "readiness_policy_version",
            "selection_policy_version",
        ):
            _require_text(getattr(self, name), name)
        if type(self.health) is not ScheduledHealthInputs:
            raise ScheduledReadinessModelError("health is invalid")
        if (
            self.coordinator is not None
            and type(self.coordinator) is not CoordinatorInspectionInput
        ):
            raise ScheduledReadinessModelError("coordinator is invalid")
        for name in (
            "manual_disable_active",
            "head_advancement_pending",
            "staging_present",
            "failed_receipt_verified",
            "transition_without_receipt",
        ):
            if type(getattr(self, name)) is not bool:
                raise ScheduledReadinessModelError(f"{name} must be a bool")
        object.__setattr__(self, "capture_attempts", attempts)


@dataclass(frozen=True, slots=True)
class SnapshotReadinessResult:
    classification: SnapshotReadinessClassification
    diagnostics: tuple[ScheduledReadinessCode, ...]
    selected_attempt_id: UUID | None

    def __post_init__(self) -> None:
        if type(self.classification) is not SnapshotReadinessClassification:
            raise ScheduledReadinessModelError(
                "snapshot readiness classification is invalid"
            )
        diagnostics = tuple(self.diagnostics)
        if (
            any(type(item) is not ScheduledReadinessCode for item in diagnostics)
            or len(set(diagnostics)) != len(diagnostics)
            or diagnostics
            != tuple(item for item in ScheduledReadinessCode if item in diagnostics)
            or (
                self.selected_attempt_id is not None
                and type(self.selected_attempt_id) is not UUID
            )
        ):
            raise ScheduledReadinessModelError("snapshot readiness result is invalid")
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class ScheduledReadinessResult:
    classification: ScheduledReadinessClassification
    diagnostics: tuple[ScheduledReadinessCode, ...]
    scheduled_session_id: UUID
    caller_idempotency_key: UUID | None
    snapshot_result: SnapshotReadinessResult

    def __post_init__(self) -> None:
        if type(self.classification) is not ScheduledReadinessClassification:
            raise ScheduledReadinessModelError("readiness classification is invalid")
        diagnostics = tuple(self.diagnostics)
        if (
            any(type(item) is not ScheduledReadinessCode for item in diagnostics)
            or len(set(diagnostics)) != len(diagnostics)
            or diagnostics
            != tuple(item for item in ScheduledReadinessCode if item in diagnostics)
            or type(self.scheduled_session_id) is not UUID
            or (
                self.caller_idempotency_key is not None
                and type(self.caller_idempotency_key) is not UUID
            )
            or type(self.snapshot_result) is not SnapshotReadinessResult
        ):
            raise ScheduledReadinessModelError("readiness result is invalid")
        object.__setattr__(self, "diagnostics", diagnostics)


def derive_scheduled_paper_session_id(
    authority_epoch_id: UUID,
    calendar: CalendarDescriptor,
    target_session: TradingSession,
    execution_session: TradingSession,
    symbols: tuple[Symbol, ...],
    universe_policy_version: str,
    readiness_policy_version: str,
) -> UUID:
    _require_uuid(authority_epoch_id, "authority_epoch_id")
    if calendar != XNYS_CALENDAR_DESCRIPTOR:
        raise ScheduledReadinessModelError("calendar descriptor is unsupported")
    _require_session(target_session, "target_session")
    _require_session(execution_session, "execution_session")
    ordered_symbols = _symbols(symbols)
    _require_text(universe_policy_version, "universe_policy_version")
    _require_text(readiness_policy_version, "readiness_policy_version")
    return _id(
        SCHEDULED_PAPER_SESSION_NAMESPACE,
        (
            SCHEDULED_PAPER_SESSION_MATERIAL_VERSION,
            str(authority_epoch_id),
            calendar.calendar_id,
            calendar.version,
            calendar.exchange_timezone,
            target_session.session_date.isoformat(),
            execution_session.session_date.isoformat(),
            str(len(ordered_symbols)),
            *(str(symbol) for symbol in ordered_symbols),
            universe_policy_version,
            readiness_policy_version,
        ),
    )


def derive_scheduled_launch_id(
    authority_epoch_id: UUID,
    phase: ScheduledPhase,
    scheduled_session_id: UUID,
    nominal_scheduled_slot: datetime,
    launch_retry_ordinal: int,
    runner_policy_version: str,
) -> UUID:
    _require_uuid(authority_epoch_id, "authority_epoch_id")
    if type(phase) is not ScheduledPhase:
        raise ScheduledReadinessModelError("phase is invalid")
    _require_uuid(scheduled_session_id, "scheduled_session_id")
    slot = _utc(nominal_scheduled_slot, "nominal_scheduled_slot")
    _require_nonnegative(launch_retry_ordinal, "launch_retry_ordinal")
    _require_text(runner_policy_version, "runner_policy_version")
    return _id(
        SCHEDULED_LAUNCH_NAMESPACE,
        (
            SCHEDULED_LAUNCH_MATERIAL_VERSION,
            str(authority_epoch_id),
            phase.value,
            str(scheduled_session_id),
            canonical_timestamp(slot),
            str(launch_retry_ordinal),
            runner_policy_version,
        ),
    )


def derive_scheduled_capture_attempt_id(
    scheduled_session_id: UUID,
    capture_attempt_ordinal: int,
    symbols: tuple[Symbol, ...],
    timeframe: Timeframe,
    adjustment: AdjustmentType,
    provider: ProviderDescriptor,
    feed: str,
    currency: str,
    capture_policy_version: str,
    configuration_evidence: ArtifactEvidence,
) -> UUID:
    _require_uuid(scheduled_session_id, "scheduled_session_id")
    _require_nonnegative(capture_attempt_ordinal, "capture_attempt_ordinal")
    ordered_symbols = _symbols(symbols)
    if (
        type(timeframe) is not Timeframe
        or type(adjustment) is not AdjustmentType
        or type(provider) is not ProviderDescriptor
        or type(configuration_evidence) is not ArtifactEvidence
    ):
        raise ScheduledReadinessModelError(
            "capture attempt identity inputs are invalid"
        )
    _require_text(feed, "feed")
    if provider.feed != feed:
        raise ScheduledReadinessModelError("provider and feed must match")
    if type(currency) is not str or _CURRENCY.fullmatch(currency) is None:
        raise ScheduledReadinessModelError("currency is invalid")
    _require_text(capture_policy_version, "capture_policy_version")
    return _id(
        SCHEDULED_CAPTURE_ATTEMPT_NAMESPACE,
        (
            SCHEDULED_CAPTURE_ATTEMPT_MATERIAL_VERSION,
            str(scheduled_session_id),
            str(capture_attempt_ordinal),
            str(len(ordered_symbols)),
            *(str(symbol) for symbol in ordered_symbols),
            timeframe.value,
            adjustment.value,
            provider.provider_id,
            str(provider.adapter_version),
            provider.operation,
            provider.feed,
            feed,
            currency,
            capture_policy_version,
            *_artifact_parts(configuration_evidence),
        ),
    )


def derive_scheduled_snapshot_selection_id(
    scheduled_session_id: UUID,
    head_record: HeadRecordEvidence,
    terminal_checkpoint: TerminalCheckpointEvidence,
    capture_attempts: tuple[ArtifactEvidence, ...],
    selected_attempt_id: UUID,
    selected_snapshot: ArtifactEvidence,
    selection_policy_version: str,
    chronology_result: SnapshotChronologyResult,
) -> UUID:
    _require_uuid(scheduled_session_id, "scheduled_session_id")
    if (
        type(head_record) is not HeadRecordEvidence
        or type(terminal_checkpoint) is not TerminalCheckpointEvidence
        or type(selected_snapshot) is not ArtifactEvidence
        or type(chronology_result) is not SnapshotChronologyResult
    ):
        raise ScheduledReadinessModelError("selection identity inputs are invalid")
    attempts = _bounded_tuple(capture_attempts, "capture_attempts")
    if not attempts or any(type(item) is not ArtifactEvidence for item in attempts):
        raise ScheduledReadinessModelError("capture attempt evidence is invalid")
    _require_uuid(selected_attempt_id, "selected_attempt_id")
    if selected_attempt_id not in {item.artifact_id for item in attempts}:
        raise ScheduledReadinessModelError(
            "selected attempt must be present in capture evidence"
        )
    _require_text(selection_policy_version, "selection_policy_version")
    parts = [
        SCHEDULED_SNAPSHOT_SELECTION_MATERIAL_VERSION,
        str(scheduled_session_id),
        str(head_record.authority_epoch_id),
        *_artifact_parts(head_record.record),
        str(head_record.generation),
        *_artifact_parts(terminal_checkpoint.checkpoint),
        str(terminal_checkpoint.sequence),
        canonical_timestamp(terminal_checkpoint.as_of),
        str(len(attempts)),
    ]
    for ordinal, attempt in enumerate(attempts):
        parts.extend((str(ordinal), *_artifact_parts(attempt)))
    parts.extend(
        (
            str(selected_attempt_id),
            *_artifact_parts(selected_snapshot),
            selection_policy_version,
            chronology_result.value,
        )
    )
    return _id(SCHEDULED_SNAPSHOT_SELECTION_NAMESPACE, tuple(parts))


def derive_scheduler_caller_idempotency_key(
    scheduled_session_id: UUID,
    head_record: HeadRecordEvidence,
    verified_lineage_evidence_id: UUID,
    terminal_checkpoint: TerminalCheckpointEvidence,
    snapshot_selection: ArtifactEvidence,
    selected_snapshot: ArtifactEvidence,
    cycle_request: ArtifactEvidence,
    cycle_configuration: ArtifactEvidence,
    target_authority_version: str,
    target_authority: ArtifactEvidence,
    approved_release: ArtifactEvidence,
    approval: ArtifactEvidence | None,
) -> UUID:
    _require_uuid(scheduled_session_id, "scheduled_session_id")
    _require_uuid(verified_lineage_evidence_id, "verified_lineage_evidence_id")
    if any(
        type(value) is not ArtifactEvidence
        for value in (
            snapshot_selection,
            selected_snapshot,
            cycle_request,
            cycle_configuration,
            target_authority,
            approved_release,
        )
    ) or (approval is not None and type(approval) is not ArtifactEvidence):
        raise ScheduledReadinessModelError("caller-key artifact evidence is invalid")
    if (
        type(head_record) is not HeadRecordEvidence
        or type(terminal_checkpoint) is not TerminalCheckpointEvidence
    ):
        raise ScheduledReadinessModelError("caller-key authority evidence is invalid")
    _require_text(target_authority_version, "target_authority_version")
    return _id(
        SCHEDULER_CALLER_IDEMPOTENCY_NAMESPACE,
        (
            SCHEDULER_CALLER_IDEMPOTENCY_MATERIAL_VERSION,
            str(scheduled_session_id),
            str(head_record.authority_epoch_id),
            *_artifact_parts(head_record.record),
            str(head_record.generation),
            str(verified_lineage_evidence_id),
            *_artifact_parts(terminal_checkpoint.checkpoint),
            str(terminal_checkpoint.sequence),
            canonical_timestamp(terminal_checkpoint.as_of),
            *_artifact_parts(snapshot_selection),
            *_artifact_parts(selected_snapshot),
            *_artifact_parts(cycle_request),
            *_artifact_parts(cycle_configuration),
            target_authority_version,
            *_artifact_parts(target_authority),
            *_artifact_parts(approved_release),
            "NONE" if approval is None else "PRESENT",
            *(() if approval is None else _artifact_parts(approval)),
        ),
    )


def create_scheduled_capture_attempt_record(
    scheduled_session_id: UUID,
    attempt_ordinal: int,
    policy: CapturePolicy,
    started_at: datetime,
    completed_at: datetime,
    status: CaptureAttemptStatus,
    snapshot: SnapshotEvidence | None,
    terminal_code: str,
) -> ScheduledCaptureAttemptRecord:
    attempt_id = derive_scheduled_capture_attempt_id(
        scheduled_session_id,
        attempt_ordinal,
        policy.symbols,
        policy.timeframe,
        policy.adjustment,
        policy.provider,
        policy.feed,
        policy.currency,
        policy.policy_version,
        policy.configuration_evidence,
    )
    return ScheduledCaptureAttemptRecord(
        SCHEDULED_CAPTURE_ATTEMPT_RECORD_SCHEMA_VERSION,
        attempt_id,
        scheduled_session_id,
        attempt_ordinal,
        policy.symbols,
        policy.timeframe,
        policy.adjustment,
        policy.provider,
        policy.feed,
        policy.currency,
        policy.policy_version,
        policy.configuration_evidence,
        started_at,
        completed_at,
        status,
        snapshot,
        terminal_code,
    )


def capture_attempt_record_evidence(
    record: ScheduledCaptureAttemptRecord,
) -> ArtifactEvidence:
    payload = serialize_scheduled_capture_attempt_record(record)
    return ArtifactEvidence(
        record.attempt_id, sha256(payload).hexdigest(), len(payload)
    )


def create_scheduled_snapshot_selection_record(
    scheduled_session_id: UUID,
    head_record: HeadRecordEvidence,
    terminal_checkpoint: TerminalCheckpointEvidence,
    capture_attempts: tuple[ArtifactEvidence, ...],
    selected_attempt_id: UUID,
    selected_snapshot: ArtifactEvidence,
    selection_policy_version: str,
    chronology_result: SnapshotChronologyResult,
) -> ScheduledSnapshotSelectionRecord:
    selection_id = derive_scheduled_snapshot_selection_id(
        scheduled_session_id,
        head_record,
        terminal_checkpoint,
        capture_attempts,
        selected_attempt_id,
        selected_snapshot,
        selection_policy_version,
        chronology_result,
    )
    return ScheduledSnapshotSelectionRecord(
        SCHEDULED_SNAPSHOT_SELECTION_SCHEMA_VERSION,
        selection_id,
        scheduled_session_id,
        head_record,
        terminal_checkpoint,
        capture_attempts,
        selected_attempt_id,
        selected_snapshot,
        selection_policy_version,
        chronology_result,
    )


def snapshot_selection_record_evidence(
    record: ScheduledSnapshotSelectionRecord,
) -> ArtifactEvidence:
    payload = serialize_scheduled_snapshot_selection_record(record)
    return ArtifactEvidence(
        record.selection_id, sha256(payload).hexdigest(), len(payload)
    )


def evaluate_snapshot_readiness(
    inputs: ScheduledReadinessInputs,
) -> SnapshotReadinessResult:
    """Classify explicit capture history without discovery, I/O, or clock reads."""
    if type(inputs) is not ScheduledReadinessInputs:
        raise TypeError("inputs must be ScheduledReadinessInputs")
    target_hours = (
        None
        if inputs.market_hours is None
        else inputs.market_hours.hours_for(inputs.target_session)
    )
    execution_hours = (
        None
        if inputs.market_hours is None
        else inputs.market_hours.hours_for(inputs.execution_session)
    )
    if target_hours is None or execution_hours is None:
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.CAPTURE_TOO_EARLY,
            (ScheduledReadinessCode.MARKET_HOURS_UNAVAILABLE,),
            None,
        )
    window_open = target_hours.closes_at + timedelta(
        seconds=inputs.capture_policy.publication_delay_seconds
    )
    deadline = execution_hours.opens_at - timedelta(
        seconds=inputs.capture_policy.capture_cutoff_guard_seconds
    )
    if inputs.observed_at < window_open:
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.CAPTURE_TOO_EARLY,
            (ScheduledReadinessCode.CAPTURE_TOO_EARLY,),
            None,
        )
    if inputs.observed_at > deadline:
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.CAPTURE_DEADLINE_PASSED,
            (ScheduledReadinessCode.CAPTURE_WINDOW_EXPIRED,),
            None,
        )
    attempts = inputs.capture_attempts
    if not attempts:
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.NO_ATTEMPTS,
            (ScheduledReadinessCode.SNAPSHOT_NOT_SELECTED,),
            None,
        )
    history_conflict = _capture_history_conflict(attempts)
    if history_conflict is not None:
        return SnapshotReadinessResult(
            history_conflict,
            (ScheduledReadinessCode.SNAPSHOT_SELECTION_CONFLICT,),
            None,
        )
    eligible: list[ScheduledCaptureAttemptRecord] = []
    ineligible: SnapshotReadinessClassification | None = None
    verified_snapshot_ineligible = False
    for attempt in attempts:
        if not _attempt_matches_policy(attempt, inputs):
            ineligible = SnapshotReadinessClassification.PROVIDER_POLICY_MISMATCH
            continue
        snapshot = attempt.snapshot
        if attempt.status is not CaptureAttemptStatus.PASS or snapshot is None:
            ineligible = SnapshotReadinessClassification.INCOMPLETE_OR_REJECTED_SNAPSHOT
            continue
        if snapshot.target_session != inputs.target_session:
            ineligible = SnapshotReadinessClassification.SNAPSHOT_TARGET_MISMATCH
            verified_snapshot_ineligible = True
            continue
        if snapshot.symbols != inputs.capture_policy.symbols:
            ineligible = SnapshotReadinessClassification.SYMBOL_UNIVERSE_MISMATCH
            verified_snapshot_ineligible = True
            continue
        if (
            snapshot.provider != inputs.capture_policy.provider
            or snapshot.timeframe is not inputs.capture_policy.timeframe
            or snapshot.adjustment is not inputs.capture_policy.adjustment
            or snapshot.feed != inputs.capture_policy.feed
            or snapshot.currency != inputs.capture_policy.currency
        ):
            ineligible = SnapshotReadinessClassification.PROVIDER_POLICY_MISMATCH
            verified_snapshot_ineligible = True
            continue
        terminal = inputs.authoritative_head
        if (
            terminal is None
            or snapshot.captured_at < terminal.terminal_checkpoint.as_of
        ):
            ineligible = (
                SnapshotReadinessClassification.SNAPSHOT_CAPTURED_BEFORE_TERMINAL
            )
            verified_snapshot_ineligible = True
            continue
        if snapshot.captured_at > inputs.observed_at + timedelta(
            seconds=inputs.capture_policy.maximum_clock_skew_seconds
        ):
            ineligible = SnapshotReadinessClassification.SNAPSHOT_FUTURE_SKEW
            verified_snapshot_ineligible = True
            continue
        if snapshot.captured_at > target_hours.closes_at + timedelta(
            seconds=inputs.capture_policy.maximum_acceptable_lateness_seconds
        ):
            ineligible = SnapshotReadinessClassification.STALE_SNAPSHOT
            verified_snapshot_ineligible = True
            continue
        eligible.append(attempt)
    if eligible:
        selected = min(eligible, key=lambda item: item.attempt_ordinal)
        if inputs.selected_snapshot is None or inputs.snapshot_selection is None:
            return SnapshotReadinessResult(
                SnapshotReadinessClassification.SNAPSHOT_NOT_SELECTED,
                (ScheduledReadinessCode.SNAPSHOT_NOT_SELECTED,),
                selected.attempt_id,
            )
        if not _selection_matches(inputs, selected):
            return SnapshotReadinessResult(
                SnapshotReadinessClassification.SELECTION_RECORD_MISMATCH,
                (ScheduledReadinessCode.SNAPSHOT_INELIGIBLE,),
                selected.attempt_id,
            )
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.VALID_SELECTED_SNAPSHOT,
            (),
            selected.attempt_id,
        )
    if verified_snapshot_ineligible and ineligible is not None:
        return SnapshotReadinessResult(
            ineligible,
            (_snapshot_code(ineligible),),
            None,
        )
    if len(attempts) >= inputs.capture_policy.maximum_attempts:
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.CAPTURE_ATTEMPTS_EXHAUSTED,
            (ScheduledReadinessCode.CAPTURE_ATTEMPTS_EXHAUSTED,),
            None,
        )
    backoff = inputs.capture_policy.fixed_backoffs_seconds[len(attempts) - 1]
    if inputs.observed_at < attempts[-1].completed_at + timedelta(seconds=backoff):
        return SnapshotReadinessResult(
            SnapshotReadinessClassification.CAPTURE_BACKOFF_ACTIVE,
            (ScheduledReadinessCode.CAPTURE_BACKOFF_ACTIVE,),
            None,
        )
    return SnapshotReadinessResult(
        SnapshotReadinessClassification.CAPTURE_WINDOW_OPEN,
        (_snapshot_code(ineligible),) if ineligible is not None else (),
        None,
    )


def evaluate_scheduled_readiness(
    inputs: ScheduledReadinessInputs,
) -> ScheduledReadinessResult:
    """Return a deterministic immutable readiness decision from explicit inputs."""
    if type(inputs) is not ScheduledReadinessInputs:
        raise TypeError("inputs must be ScheduledReadinessInputs")
    snapshot = evaluate_snapshot_readiness(inputs)
    codes: set[ScheduledReadinessCode] = set(snapshot.diagnostics)
    categories: set[ScheduledReadinessClassification] = set()
    head = inputs.authoritative_head
    if head is None or not head.verification_passed:
        codes.add(ScheduledReadinessCode.HEAD_UNVERIFIED)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if inputs.head_advancement_pending or inputs.transition_without_receipt:
        codes.add(ScheduledReadinessCode.HEAD_ADVANCEMENT_PENDING)
        categories.add(ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED)
    if inputs.manual_disable_active:
        codes.add(ScheduledReadinessCode.MANUAL_DISABLE_ACTIVE)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if inputs.market_hours is None:
        codes.add(ScheduledReadinessCode.MARKET_HOURS_UNAVAILABLE)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    else:
        later_sessions = tuple(
            item.session
            for item in inputs.market_hours.entries
            if item.session.session_date > inputs.target_session.session_date
        )
        if (
            inputs.market_hours.hours_for(inputs.target_session) is None
            or not later_sessions
            or later_sessions[0] != inputs.execution_session
        ):
            codes.add(ScheduledReadinessCode.SESSION_MISMATCH)
            categories.add(ScheduledReadinessClassification.BLOCKED)
    if inputs.staging_present:
        codes.add(ScheduledReadinessCode.STAGING_REQUIRES_REVIEW)
        categories.add(ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED)
    if inputs.failed_receipt_verified:
        codes.add(ScheduledReadinessCode.FAILED_RECEIPT_REQUIRES_REVIEW)
        categories.add(ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED)
    if not inputs.health.disk_watermark_ok:
        codes.add(ScheduledReadinessCode.DISK_WATERMARK_BLOCKED)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if not inputs.health.audit_ok:
        codes.add(ScheduledReadinessCode.AUDIT_UNHEALTHY)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if not inputs.health.notification_ok:
        codes.add(ScheduledReadinessCode.NOTIFICATION_UNAVAILABLE)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if not inputs.health.backup_ok:
        codes.add(ScheduledReadinessCode.BACKUP_REQUIREMENT_UNMET)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if (
        not inputs.health.credential_isolation_ok
        or inputs.health.operation_credentials_present
    ):
        codes.add(ScheduledReadinessCode.OPERATION_CREDENTIALS_PRESENT)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    if snapshot.classification in {
        SnapshotReadinessClassification.CONFLICTING_CAPTURE_RECORDS,
        SnapshotReadinessClassification.DUPLICATE_ELIGIBLE_CAPTURES,
        SnapshotReadinessClassification.SELECTION_RECORD_MISMATCH,
    }:
        categories.add(ScheduledReadinessClassification.CONFLICTING)
    elif snapshot.classification in {
        SnapshotReadinessClassification.CAPTURE_DEADLINE_PASSED,
        SnapshotReadinessClassification.CAPTURE_ATTEMPTS_EXHAUSTED,
    }:
        categories.add(ScheduledReadinessClassification.BLOCKED)
    elif (
        snapshot.classification
        is SnapshotReadinessClassification.SNAPSHOT_CAPTURED_BEFORE_TERMINAL
        and len(inputs.capture_attempts) >= inputs.capture_policy.maximum_attempts
    ):
        categories.add(ScheduledReadinessClassification.BLOCKED)
    elif snapshot.classification is not (
        SnapshotReadinessClassification.VALID_SELECTED_SNAPSHOT
    ):
        categories.add(ScheduledReadinessClassification.NOT_READY)
    caller_key: UUID | None = None
    cycle = inputs.cycle
    if cycle is None:
        codes.add(ScheduledReadinessCode.TARGET_AUTHORITY_MISSING)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    elif head is not None and inputs.snapshot_selection is not None:
        selection_evidence = snapshot_selection_record_evidence(
            inputs.snapshot_selection
        )
        caller_key = derive_scheduler_caller_idempotency_key(
            inputs.scheduled_session_id,
            head.head_record,
            head.verified_lineage_evidence_id,
            head.terminal_checkpoint,
            selection_evidence,
            cycle.selected_snapshot,
            cycle.cycle_request,
            cycle.cycle_configuration,
            cycle.target_authority_version,
            cycle.target_authority,
            cycle.approved_release,
            cycle.approval,
        )
        if caller_key != cycle.expected_caller_idempotency_key:
            codes.add(ScheduledReadinessCode.SCHEDULED_IDENTITY_MISMATCH)
            categories.add(ScheduledReadinessClassification.CONFLICTING)
        if not cycle.release_approved:
            codes.add(ScheduledReadinessCode.RELEASE_NOT_APPROVED)
            categories.add(ScheduledReadinessClassification.BLOCKED)
        if cycle.approval_required and cycle.approval is None:
            codes.add(ScheduledReadinessCode.APPROVAL_MISSING)
            categories.add(ScheduledReadinessClassification.BLOCKED)
        execution_hours = (
            None
            if inputs.market_hours is None
            else inputs.market_hours.hours_for(inputs.execution_session)
        )
        captured = (
            None
            if inputs.selected_snapshot is None
            else inputs.selected_snapshot.captured_at
        )
        terminal_as_of = head.terminal_checkpoint.as_of
        if (
            captured is None
            or not (
                terminal_as_of
                <= captured
                <= cycle.planning_at
                <= cycle.submitted_at
                <= cycle.filled_at
            )
            or execution_hours is None
            or not (
                execution_hours.opens_at <= cycle.filled_at <= execution_hours.closes_at
            )
        ):
            codes.add(ScheduledReadinessCode.EXECUTION_CHRONOLOGY_FAILURE)
            categories.add(ScheduledReadinessClassification.BLOCKED)
        if cycle.selected_snapshot != (
            None
            if inputs.selected_snapshot is None
            else inputs.selected_snapshot.artifact
        ):
            codes.add(ScheduledReadinessCode.SESSION_MISMATCH)
            categories.add(ScheduledReadinessClassification.CONFLICTING)
    coordinator = inputs.coordinator
    if coordinator is None:
        codes.add(ScheduledReadinessCode.OPERATION_BLOCKED)
        categories.add(ScheduledReadinessClassification.BLOCKED)
    elif (
        head is not None
        and coordinator.classification != "ALREADY_APPLIED"
        and (
            coordinator.terminal_checkpoint_id
            != head.terminal_checkpoint.checkpoint.artifact_id
        )
    ):
        codes.add(ScheduledReadinessCode.SESSION_MISMATCH)
        categories.add(ScheduledReadinessClassification.CONFLICTING)
    elif coordinator.classification == "CONFLICTING":
        codes.add(ScheduledReadinessCode.OPERATION_CONFLICTING)
        categories.add(ScheduledReadinessClassification.CONFLICTING)
    elif coordinator.classification == "BLOCKED":
        if coordinator.diagnostic in {
            "VALID_FAILED_RECEIPT",
            "FINALIZED_TRANSITION_WITHOUT_RECEIPT",
            "OPERATION_STAGING_EXISTS",
            "TRANSITION_STAGING_EXISTS",
        }:
            categories.add(ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED)
        else:
            categories.add(ScheduledReadinessClassification.BLOCKED)
        codes.add(ScheduledReadinessCode.OPERATION_BLOCKED)
    elif coordinator.classification == "ALREADY_APPLIED":
        codes.add(ScheduledReadinessCode.OPERATION_ALREADY_COMPLETED)
        if (
            coordinator.completed_receipt_verified
            and coordinator.transition_verified
            and coordinator.head_advanced_to_successor
            and coordinator.successor_checkpoint_id
            == (
                None
                if head is None
                else head.terminal_checkpoint.checkpoint.artifact_id
            )
        ):
            categories.add(ScheduledReadinessClassification.ALREADY_COMPLETED)
        else:
            categories.add(ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED)
    else:
        codes.add(ScheduledReadinessCode.COORDINATOR_PENDING)
    if head is not None:
        expected_session_id = derive_scheduled_paper_session_id(
            head.head_record.authority_epoch_id,
            XNYS_CALENDAR_DESCRIPTOR,
            inputs.target_session,
            inputs.execution_session,
            inputs.capture_policy.symbols,
            inputs.universe_policy_version,
            inputs.readiness_policy_version,
        )
        if expected_session_id != inputs.scheduled_session_id:
            codes.add(ScheduledReadinessCode.SCHEDULED_IDENTITY_MISMATCH)
            categories.add(ScheduledReadinessClassification.CONFLICTING)
    classification = _precedence(categories)
    return ScheduledReadinessResult(
        classification,
        tuple(code for code in ScheduledReadinessCode if code in codes),
        inputs.scheduled_session_id,
        caller_key,
        snapshot,
    )


def serialize_scheduled_capture_attempt_record(
    record: ScheduledCaptureAttemptRecord,
) -> bytes:
    if type(record) is not ScheduledCaptureAttemptRecord:
        raise TypeError("record must be ScheduledCaptureAttemptRecord")
    return _json_bytes(_attempt_tree(record))


def parse_scheduled_capture_attempt_record(
    payload: bytes,
) -> ScheduledCaptureAttemptRecord:
    root = _object(
        _load_json(payload),
        {
            "schema_version",
            "attempt_id",
            "scheduled_session_id",
            "attempt_ordinal",
            "symbols",
            "timeframe",
            "adjustment",
            "provider",
            "feed",
            "currency",
            "capture_policy_version",
            "configuration_evidence",
            "started_at",
            "completed_at",
            "status",
            "snapshot",
            "terminal_code",
        },
        "attempt",
    )
    snapshot_value = root["snapshot"]
    snapshot = None if snapshot_value is None else _snapshot(snapshot_value)
    record = ScheduledCaptureAttemptRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid(root["attempt_id"], "attempt_id"),
        _uuid(root["scheduled_session_id"], "scheduled_session_id"),
        _nonnegative(root["attempt_ordinal"], "attempt_ordinal"),
        _symbol_array(root["symbols"], "symbols"),
        _enum(Timeframe, root["timeframe"], "timeframe"),
        _enum(AdjustmentType, root["adjustment"], "adjustment"),
        _provider(root["provider"]),
        _string(root["feed"], "feed"),
        _string(root["currency"], "currency"),
        _string(root["capture_policy_version"], "capture_policy_version"),
        _artifact(root["configuration_evidence"], "configuration_evidence"),
        _timestamp(root["started_at"], "started_at"),
        _timestamp(root["completed_at"], "completed_at"),
        _enum(CaptureAttemptStatus, root["status"], "status"),
        snapshot,
        _string(root["terminal_code"], "terminal_code"),
    )
    if serialize_scheduled_capture_attempt_record(record) != payload:
        raise ScheduledReadinessModelError("attempt bytes are not canonical")
    return record


def serialize_scheduled_snapshot_selection_record(
    record: ScheduledSnapshotSelectionRecord,
) -> bytes:
    if type(record) is not ScheduledSnapshotSelectionRecord:
        raise TypeError("record must be ScheduledSnapshotSelectionRecord")
    return _json_bytes(_selection_tree(record))


def parse_scheduled_snapshot_selection_record(
    payload: bytes,
) -> ScheduledSnapshotSelectionRecord:
    root = _object(
        _load_json(payload),
        {
            "schema_version",
            "selection_id",
            "scheduled_session_id",
            "head_record",
            "terminal_checkpoint",
            "capture_attempts",
            "selected_attempt_id",
            "selected_snapshot",
            "selection_policy_version",
            "chronology_result",
        },
        "selection",
    )
    head = _object(
        root["head_record"],
        {"authority_epoch_id", "record", "generation"},
        "head_record",
    )
    terminal = _object(
        root["terminal_checkpoint"],
        {"checkpoint", "sequence", "as_of"},
        "terminal_checkpoint",
    )
    attempts = _array(root["capture_attempts"], "capture_attempts")
    record = ScheduledSnapshotSelectionRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid(root["selection_id"], "selection_id"),
        _uuid(root["scheduled_session_id"], "scheduled_session_id"),
        HeadRecordEvidence(
            _uuid(head["authority_epoch_id"], "head_record.authority_epoch_id"),
            _artifact(head["record"], "head_record.record"),
            _nonnegative(head["generation"], "head_record.generation"),
        ),
        TerminalCheckpointEvidence(
            _artifact(terminal["checkpoint"], "terminal_checkpoint.checkpoint"),
            _nonnegative(terminal["sequence"], "terminal_checkpoint.sequence"),
            _timestamp(terminal["as_of"], "terminal_checkpoint.as_of"),
        ),
        tuple(_artifact(item, "capture_attempt") for item in attempts),
        _uuid(root["selected_attempt_id"], "selected_attempt_id"),
        _artifact(root["selected_snapshot"], "selected_snapshot"),
        _string(root["selection_policy_version"], "selection_policy_version"),
        _enum(
            SnapshotChronologyResult,
            root["chronology_result"],
            "chronology_result",
        ),
    )
    if serialize_scheduled_snapshot_selection_record(record) != payload:
        raise ScheduledReadinessModelError("selection bytes are not canonical")
    return record


def _attempt_matches_policy(
    attempt: ScheduledCaptureAttemptRecord, inputs: ScheduledReadinessInputs
) -> bool:
    policy = inputs.capture_policy
    return (
        attempt.scheduled_session_id == inputs.scheduled_session_id
        and attempt.attempt_ordinal < policy.maximum_attempts
        and attempt.symbols == policy.symbols
        and attempt.timeframe is policy.timeframe
        and attempt.adjustment is policy.adjustment
        and attempt.provider == policy.provider
        and attempt.feed == policy.feed
        and attempt.currency == policy.currency
        and attempt.capture_policy_version == policy.policy_version
        and attempt.configuration_evidence == policy.configuration_evidence
    )


def _capture_history_conflict(
    attempts: tuple[ScheduledCaptureAttemptRecord, ...],
) -> SnapshotReadinessClassification | None:
    ordinals = tuple(item.attempt_ordinal for item in attempts)
    if len(set(ordinals)) != len(ordinals):
        groups = {
            ordinal: tuple(item for item in attempts if item.attempt_ordinal == ordinal)
            for ordinal in set(ordinals)
        }
        if all(
            len(set(items)) == 1 and items[0].status is CaptureAttemptStatus.PASS
            for items in groups.values()
        ):
            return SnapshotReadinessClassification.DUPLICATE_ELIGIBLE_CAPTURES
        return SnapshotReadinessClassification.CONFLICTING_CAPTURE_RECORDS
    if ordinals != tuple(range(len(attempts))) or len(
        {item.attempt_id for item in attempts}
    ) != len(attempts):
        return SnapshotReadinessClassification.CONFLICTING_CAPTURE_RECORDS
    return None


def _selection_matches(
    inputs: ScheduledReadinessInputs,
    selected: ScheduledCaptureAttemptRecord,
) -> bool:
    head = inputs.authoritative_head
    selection = inputs.snapshot_selection
    snapshot = inputs.selected_snapshot
    if head is None or selection is None or snapshot is None:
        return False
    attempts = tuple(
        capture_attempt_record_evidence(item) for item in inputs.capture_attempts
    )
    expected = create_scheduled_snapshot_selection_record(
        inputs.scheduled_session_id,
        head.head_record,
        head.terminal_checkpoint,
        attempts,
        selected.attempt_id,
        snapshot.artifact,
        inputs.selection_policy_version,
        SnapshotChronologyResult.PASS,
    )
    return (
        selection == expected
        and selected.snapshot is not None
        and selected.snapshot == snapshot
        and selection.selected_snapshot == snapshot.artifact
    )


def _snapshot_code(
    classification: SnapshotReadinessClassification | None,
) -> ScheduledReadinessCode:
    if classification is SnapshotReadinessClassification.SNAPSHOT_FUTURE_SKEW:
        return ScheduledReadinessCode.SNAPSHOT_FUTURE_SKEW
    if (
        classification
        is SnapshotReadinessClassification.SNAPSHOT_CAPTURED_BEFORE_TERMINAL
    ):
        return ScheduledReadinessCode.SNAPSHOT_TERMINAL_CHRONOLOGY_FAILURE
    return ScheduledReadinessCode.SNAPSHOT_INELIGIBLE


def _precedence(
    categories: set[ScheduledReadinessClassification],
) -> ScheduledReadinessClassification:
    for value in (
        ScheduledReadinessClassification.CONFLICTING,
        ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED,
        ScheduledReadinessClassification.BLOCKED,
        ScheduledReadinessClassification.ALREADY_COMPLETED,
        ScheduledReadinessClassification.NOT_READY,
    ):
        if value in categories:
            return value
    return ScheduledReadinessClassification.READY


def _attempt_tree(record: ScheduledCaptureAttemptRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "attempt_id": str(record.attempt_id),
        "scheduled_session_id": str(record.scheduled_session_id),
        "attempt_ordinal": record.attempt_ordinal,
        "symbols": [str(item) for item in record.symbols],
        "timeframe": record.timeframe.value,
        "adjustment": record.adjustment.value,
        "provider": _provider_tree(record.provider),
        "feed": record.feed,
        "currency": record.currency,
        "capture_policy_version": record.capture_policy_version,
        "configuration_evidence": _artifact_tree(record.configuration_evidence),
        "started_at": canonical_timestamp(record.started_at),
        "completed_at": canonical_timestamp(record.completed_at),
        "status": record.status.value,
        "snapshot": None
        if record.snapshot is None
        else _snapshot_tree(record.snapshot),
        "terminal_code": record.terminal_code,
    }


def _selection_tree(record: ScheduledSnapshotSelectionRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "selection_id": str(record.selection_id),
        "scheduled_session_id": str(record.scheduled_session_id),
        "head_record": {
            "authority_epoch_id": str(record.head_record.authority_epoch_id),
            "record": _artifact_tree(record.head_record.record),
            "generation": record.head_record.generation,
        },
        "terminal_checkpoint": {
            "checkpoint": _artifact_tree(record.terminal_checkpoint.checkpoint),
            "sequence": record.terminal_checkpoint.sequence,
            "as_of": canonical_timestamp(record.terminal_checkpoint.as_of),
        },
        "capture_attempts": [_artifact_tree(item) for item in record.capture_attempts],
        "selected_attempt_id": str(record.selected_attempt_id),
        "selected_snapshot": _artifact_tree(record.selected_snapshot),
        "selection_policy_version": record.selection_policy_version,
        "chronology_result": record.chronology_result.value,
    }


def _snapshot_tree(snapshot: SnapshotEvidence) -> dict[str, object]:
    return {
        "artifact": _artifact_tree(snapshot.artifact),
        "target_session": snapshot.target_session.session_date.isoformat(),
        "captured_at": canonical_timestamp(snapshot.captured_at),
        "symbols": [str(item) for item in snapshot.symbols],
        "provider": _provider_tree(snapshot.provider),
        "timeframe": snapshot.timeframe.value,
        "adjustment": snapshot.adjustment.value,
        "feed": snapshot.feed,
        "currency": snapshot.currency,
        "verification_passed": snapshot.verification_passed,
        "complete": snapshot.complete,
    }


def _snapshot(value: object) -> SnapshotEvidence:
    item = _object(
        value,
        {
            "artifact",
            "target_session",
            "captured_at",
            "symbols",
            "provider",
            "timeframe",
            "adjustment",
            "feed",
            "currency",
            "verification_passed",
            "complete",
        },
        "snapshot",
    )
    return SnapshotEvidence(
        _artifact(item["artifact"], "snapshot.artifact"),
        TradingSession(_date(item["target_session"], "snapshot.target_session")),
        _timestamp(item["captured_at"], "snapshot.captured_at"),
        _symbol_array(item["symbols"], "snapshot.symbols"),
        _provider(item["provider"]),
        _enum(Timeframe, item["timeframe"], "snapshot.timeframe"),
        _enum(AdjustmentType, item["adjustment"], "snapshot.adjustment"),
        _string(item["feed"], "snapshot.feed"),
        _string(item["currency"], "snapshot.currency"),
        _boolean(item["verification_passed"], "snapshot.verification_passed"),
        _boolean(item["complete"], "snapshot.complete"),
    )


def _artifact_tree(value: ArtifactEvidence) -> dict[str, object]:
    return {
        "artifact_id": str(value.artifact_id),
        "sha256": value.sha256,
        "byte_length": value.byte_length,
    }


def _provider_tree(value: ProviderDescriptor) -> dict[str, object]:
    return {
        "provider_id": value.provider_id,
        "adapter_version": value.adapter_version,
        "operation": value.operation,
        "feed": value.feed,
    }


def _artifact(value: object, label: str) -> ArtifactEvidence:
    item = _object(value, {"artifact_id", "sha256", "byte_length"}, label)
    return ArtifactEvidence(
        _uuid(item["artifact_id"], f"{label}.artifact_id"),
        _sha(item["sha256"], f"{label}.sha256"),
        _nonnegative(item["byte_length"], f"{label}.byte_length"),
    )


def _provider(value: object) -> ProviderDescriptor:
    item = _object(
        value,
        {"provider_id", "adapter_version", "operation", "feed"},
        "provider",
    )
    return ProviderDescriptor(
        _string(item["provider_id"], "provider.provider_id"),
        _integer(item["adapter_version"], "provider.adapter_version"),
        _string(item["operation"], "provider.operation"),
        _string(item["feed"], "provider.feed"),
    )


def _modeled_sessions(start: date, end: date) -> tuple[date, ...]:
    calendar = NYSEMarketCalendar()
    current = start
    result: list[date] = []
    while current <= end:
        local_noon = datetime.combine(current, time(12), _NEW_YORK).astimezone(UTC)
        if calendar.is_trading_session(local_noon):
            result.append(current)
        current += timedelta(days=1)
    return tuple(result)


def _id(namespace: UUID, parts: tuple[str, ...]) -> UUID:
    return uuid5(namespace, _framed(parts))


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _artifact_parts(value: ArtifactEvidence) -> tuple[str, ...]:
    return str(value.artifact_id), value.sha256, str(value.byte_length)


def _utc(value: object, label: str) -> datetime:
    try:
        if type(value) is not datetime:
            raise TypeError(f"{label} must be an exact datetime")
        return normalize_utc(value, label)
    except (TypeError, ValueError) as error:
        raise ScheduledReadinessModelError(str(error)) from error


def _symbols(value: object) -> tuple[Symbol, ...]:
    items = _bounded_tuple(value, "symbols")
    if (
        not items
        or any(type(item) is not Symbol for item in items)
        or len(set(items)) != len(items)
    ):
        raise ScheduledReadinessModelError(
            "symbols must be ordered unique Symbol values"
        )
    return items


def _bounded_tuple(value: object, label: str) -> tuple:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise ScheduledReadinessModelError(f"{label} must be iterable") from error
    if len(items) > MAX_SCHEDULED_COLLECTION_ITEMS:
        raise ScheduledReadinessModelError(f"{label} exceeds its bound")
    return items


def _require_uuid(value: object, label: str) -> None:
    if type(value) is not UUID:
        raise ScheduledReadinessModelError(f"{label} must be an exact UUID")


def _require_session(value: object, label: str) -> None:
    if type(value) is not TradingSession:
        raise ScheduledReadinessModelError(f"{label} must be TradingSession")


def _require_text(value: object, label: str) -> None:
    if (
        type(value) is not str
        or not 1 <= len(value) <= MAX_SCHEDULED_TEXT_CHARACTERS
        or _TEXT.fullmatch(value) is None
    ):
        raise ScheduledReadinessModelError(f"{label} must be canonical ASCII text")


def _require_nonnegative(value: object, label: str) -> None:
    if type(value) is not int or not 0 <= value <= MAX_SCHEDULED_INTEGER:
        raise ScheduledReadinessModelError(f"{label} must be a bounded integer")


def _require_evidence(digest: object, length: object, label: str) -> None:
    if (
        type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        or type(length) is not int
        or not 0 <= length <= MAX_SCHEDULED_INTEGER
    ):
        raise ScheduledReadinessModelError(f"{label} evidence is invalid")


def _json_bytes(value: object) -> bytes:
    payload = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")
    if len(payload) > MAX_SCHEDULED_ARTIFACT_BYTES:
        raise ScheduledReadinessModelError("scheduled artifact exceeds byte bound")
    return payload


def _load_json(payload: bytes) -> object:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_SCHEDULED_ARTIFACT_BYTES
        or payload.startswith(b"\xef\xbb\xbf")
    ):
        raise ScheduledArtifactSyntaxError("scheduled artifact bytes are invalid")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except ScheduledReadinessModelError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScheduledArtifactSyntaxError(
            "scheduled artifact is not strict UTF-8 JSON"
        ) from error


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ScheduledReadinessModelError(f"duplicate field: {key}")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise ScheduledReadinessModelError("JSON floats are not permitted")


def _reject_constant(_: str) -> None:
    raise ScheduledReadinessModelError("JSON constants are not permitted")


def _object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise ScheduledReadinessModelError(f"{label} fields are invalid")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list or len(value) > MAX_SCHEDULED_COLLECTION_ITEMS:
        raise ScheduledReadinessModelError(f"{label} must be a bounded array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or len(value) > MAX_SCHEDULED_TEXT_CHARACTERS:
        raise ScheduledReadinessModelError(f"{label} must be a bounded string")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ScheduledReadinessModelError(f"{label} must be a bool")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or abs(value) > MAX_SCHEDULED_INTEGER:
        raise ScheduledReadinessModelError(f"{label} must be a bounded integer")
    return value


def _nonnegative(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise ScheduledReadinessModelError(f"{label} must be nonnegative")
    return parsed


def _uuid(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise ScheduledReadinessModelError(f"{label} must be a UUID") from error
    if str(parsed) != text:
        raise ScheduledReadinessModelError(f"{label} must be canonical UUID text")
    return parsed


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ScheduledReadinessModelError(f"{label} must be lowercase SHA-256")
    return text


def _timestamp(value: object, label: str) -> datetime:
    text = _string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ScheduledReadinessModelError(f"{label} is not a timestamp") from error
    normalized = _utc(parsed, label)
    if canonical_timestamp(normalized) != text:
        raise ScheduledReadinessModelError(f"{label} is not canonical")
    return normalized


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise ScheduledReadinessModelError(f"{label} is not a date") from error
    if parsed.isoformat() != text:
        raise ScheduledReadinessModelError(f"{label} is not canonical")
    return parsed


def _symbol_array(value: object, label: str) -> tuple[Symbol, ...]:
    values = _array(value, label)
    try:
        return _symbols(tuple(Symbol(_string(item, label)) for item in values))
    except (TypeError, ValueError) as error:
        raise ScheduledReadinessModelError(f"{label} is invalid") from error


def _enum(enum_type, value: object, label: str):  # type: ignore[no-untyped-def]
    text = _string(value, label)
    try:
        return enum_type(text)
    except ValueError as error:
        raise ScheduledReadinessModelError(f"{label} is unsupported") from error
