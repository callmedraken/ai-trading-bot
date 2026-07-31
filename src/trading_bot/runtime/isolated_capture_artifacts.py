"""Canonical evidence for one manually launched isolated Alpaca capture child."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    MAX_ALPACA_RESPONSE_BYTES,
    MAX_DAILY_SNAPSHOT_SYMBOLS,
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    CalendarDescriptor,
    Timeframe,
)
from trading_bot.market_data.alpaca_daily_snapshot import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
)
from trading_bot.market_data.alpaca_http import ALPACA_SOCKET_TIMEOUT_SECONDS
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime.capture_attempt_authority import (
    CaptureAttemptAllocationRecord,
    ProviderCallDisposition,
    SecretCleanupResult,
    SnapshotTerminalVerification,
    WindowsMarketDataCredentialReference,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence

ISOLATED_CAPTURE_CHILD_REQUEST_SCHEMA_VERSION = 1
ISOLATED_CAPTURE_CHILD_REQUEST_MATERIAL_VERSION = "isolated-capture-child-request-v1"
ISOLATED_CAPTURE_CHILD_REQUEST_NAMESPACE = UUID("4f31015f-5b34-5b37-98cc-4a64fe1d3490")
ISOLATED_CAPTURE_CHILD_RESULT_SCHEMA_VERSION = 1
ISOLATED_CAPTURE_CHILD_RESULT_MATERIAL_VERSION = "isolated-capture-child-result-v1"
ISOLATED_CAPTURE_CHILD_RESULT_NAMESPACE = UUID("b560a813-c0aa-50e7-ab5e-f6d21ef35f66")
CHILD_PROCESS_CREATION_RECORD_SCHEMA_VERSION = 1
CHILD_PROCESS_CREATION_RECORD_MATERIAL_VERSION = "child-process-creation-record-v1"
CHILD_PROCESS_CREATION_RECORD_NAMESPACE = UUID("f6720dce-e063-5e41-8bbd-e7c99b7f52e6")
CHILD_RESUME_AUTHORIZATION_RECORD_SCHEMA_VERSION = 1
CHILD_RESUME_AUTHORIZATION_RECORD_MATERIAL_VERSION = (
    "child-resume-authorization-record-v1"
)
CHILD_RESUME_AUTHORIZATION_RECORD_NAMESPACE = UUID(
    "45c8a044-a8cf-5b23-81cd-3ce0d7bda4a6"
)
CHILD_TERMINATION_RECORD_SCHEMA_VERSION = 1
CHILD_TERMINATION_RECORD_MATERIAL_VERSION = "child-termination-record-v1"
CHILD_TERMINATION_RECORD_NAMESPACE = UUID("00d4e570-2864-580d-8f73-f0f3a77158c2")

ISOLATED_CAPTURE_CHILD_OPERATION_VERSION = "isolated-alpaca-capture-child-v1"
ISOLATED_CAPTURE_ENVIRONMENT_POLICY_VERSION = "isolated-python-environment-v1"
ISOLATED_CAPTURE_PROVIDER_ID = "ALPACA_MARKET_DATA"
ISOLATED_CAPTURE_FEED = "SIP"
ISOLATED_CAPTURE_CURRENCY = "USD"
ISOLATED_CAPTURE_DEFAULT_WALL_TIMEOUT_SECONDS = 30
ISOLATED_CAPTURE_MAX_STREAM_BYTES = 64 * 1024
MAX_ISOLATED_CAPTURE_ARTIFACT_BYTES = 512 * 1024
MAX_ISOLATED_CAPTURE_TEXT = 256

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_DIAGNOSTIC = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_REQUEST_ID = re.compile(r"^[!-~]{1,256}$")


class IsolatedCaptureArtifactError(ValueError):
    """Base error for strict isolated-capture evidence."""


class IsolatedCaptureArtifactSyntaxError(IsolatedCaptureArtifactError):
    """Canonical artifact syntax or bytes are invalid."""


class IsolatedCaptureReconciliationError(IsolatedCaptureArtifactError):
    """A child request does not reconcile with its authoritative inputs."""


class IsolatedCapturePublicationError(IsolatedCaptureArtifactError):
    """Immutable artifact publication failed closed."""


class IsolatedCaptureChildClassification(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    CREDENTIAL_REFERENCE_INVALID = "CREDENTIAL_REFERENCE_INVALID"
    SID_MISMATCH = "SID_MISMATCH"
    CREDENTIAL_NOT_FOUND = "CREDENTIAL_NOT_FOUND"
    CREDENTIAL_INVALID = "CREDENTIAL_INVALID"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    NETWORK_FAILED = "NETWORK_FAILED"
    TIMEOUT = "TIMEOUT"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"
    SNAPSHOT_OUTPUT_FAILED = "SNAPSHOT_OUTPUT_FAILED"
    INTERNAL_FAILED = "INTERNAL_FAILED"


class ProcessCreationResult(StrEnum):
    CREATED_SUSPENDED = "CREATED_SUSPENDED"
    FAILED = "FAILED"


class JobObjectAssignmentResult(StrEnum):
    ASSIGNED = "ASSIGNED"
    NOT_ASSIGNED = "NOT_ASSIGNED"
    FAILED = "FAILED"


class HandleInheritancePosture(StrEnum):
    DISABLED = "DISABLED"


class ResumeAuthorizationResult(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    RESUME_FAILED = "RESUME_FAILED"


class ProcessTreeTerminationResult(StrEnum):
    EXITED = "EXITED"
    TERMINATED_AND_CONFIRMED = "TERMINATED_AND_CONFIRMED"
    TERMINATION_UNCONFIRMED = "TERMINATION_UNCONFIRMED"
    NOT_CREATED = "NOT_CREATED"


@dataclass(frozen=True, slots=True)
class IsolatedCaptureChildRequest:
    schema_version: int
    child_request_id: UUID
    allocation: ArtifactEvidence
    allocation_path: Path
    attempt_id: UUID
    attempt_ordinal: int
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    credential_reference: ArtifactEvidence
    credential_reference_path: Path
    snapshot_capture_request_id: UUID
    capture_configuration: ArtifactEvidence
    capture_configuration_path: Path
    symbols: tuple[Symbol, ...]
    calendar: CalendarDescriptor
    timeframe: Timeframe
    adjustment: AdjustmentType
    provider_id: str
    adapter_version: int
    provider_operation: str
    feed: str
    currency: str
    target_session: TradingSession
    request_timestamp_utc: datetime
    request_new_york_date: date
    socket_timeout_seconds: int
    wall_timeout_seconds: int
    maximum_response_bytes: int
    maximum_candidate_count: int
    snapshot_destination_reference: ArtifactEvidence
    snapshot_destination_path: Path
    child_result_path: Path
    software_release: ArtifactEvidence
    child_operation_version: str

    def __post_init__(self) -> None:
        if self.schema_version != ISOLATED_CAPTURE_CHILD_REQUEST_SCHEMA_VERSION:
            raise IsolatedCaptureArtifactError("child request schema_version must be 1")
        _uuid(self.child_request_id, "child_request_id")
        for value, label in (
            (self.allocation, "allocation"),
            (self.credential_reference, "credential_reference"),
            (self.capture_configuration, "capture_configuration"),
            (self.snapshot_destination_reference, "snapshot_destination_reference"),
            (self.software_release, "software_release"),
        ):
            _evidence(value, label)
        for value, label in (
            (self.allocation_path, "allocation_path"),
            (self.credential_reference_path, "credential_reference_path"),
            (self.capture_configuration_path, "capture_configuration_path"),
            (self.snapshot_destination_path, "snapshot_destination_path"),
            (self.child_result_path, "child_result_path"),
        ):
            _absolute_path(value, label)
        for value, label in (
            (self.attempt_id, "attempt_id"),
            (self.scheduled_session_id, "scheduled_session_id"),
            (self.scheduled_launch_id, "scheduled_launch_id"),
            (self.snapshot_capture_request_id, "snapshot_capture_request_id"),
        ):
            _uuid(value, label)
        _nonnegative(self.attempt_ordinal, "attempt_ordinal")
        symbols = tuple(self.symbols)
        if symbols != (Symbol("SPY"), Symbol("QQQ")):
            raise IsolatedCaptureArtifactError("symbols must be exactly SPY, QQQ")
        if self.calendar != XNYS_CALENDAR_DESCRIPTOR:
            raise IsolatedCaptureArtifactError("calendar must be exact XNYS")
        if self.timeframe is not Timeframe.DAY_1:
            raise IsolatedCaptureArtifactError("timeframe must be 1D")
        if self.adjustment is not AdjustmentType.RAW:
            raise IsolatedCaptureArtifactError("adjustment must be RAW")
        if self.provider_id != ISOLATED_CAPTURE_PROVIDER_ID:
            raise IsolatedCaptureArtifactError("provider_id must be ALPACA_MARKET_DATA")
        if self.adapter_version != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.adapter_version:
            raise IsolatedCaptureArtifactError("adapter_version is unsupported")
        if self.provider_operation != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation:
            raise IsolatedCaptureArtifactError("provider_operation is unsupported")
        if self.feed != ISOLATED_CAPTURE_FEED:
            raise IsolatedCaptureArtifactError("feed must be SIP")
        if self.currency != ISOLATED_CAPTURE_CURRENCY:
            raise IsolatedCaptureArtifactError("currency must be USD")
        if type(self.target_session) is not TradingSession:
            raise IsolatedCaptureArtifactError("target_session is invalid")
        requested_at = _utc(self.request_timestamp_utc, "request_timestamp_utc")
        if (
            type(self.request_new_york_date) is not date
            or self.request_new_york_date
            != requested_at.astimezone(ZoneInfo("America/New_York")).date()
        ):
            raise IsolatedCaptureArtifactError(
                "request New York date does not reconcile"
            )
        if self.socket_timeout_seconds != int(ALPACA_SOCKET_TIMEOUT_SECONDS):
            raise IsolatedCaptureArtifactError("socket timeout must be 15 seconds")
        _positive_bounded(
            self.wall_timeout_seconds, "wall_timeout_seconds", maximum=300
        )
        if self.maximum_response_bytes != MAX_ALPACA_RESPONSE_BYTES:
            raise IsolatedCaptureArtifactError(
                "maximum_response_bytes must be the approved value"
            )
        if self.maximum_candidate_count != MAX_DAILY_SNAPSHOT_SYMBOLS:
            raise IsolatedCaptureArtifactError(
                "maximum_candidate_count must be the approved value"
            )
        _policy(self.child_operation_version, "child_operation_version")
        if self.child_operation_version != ISOLATED_CAPTURE_CHILD_OPERATION_VERSION:
            raise IsolatedCaptureArtifactError("child_operation_version is unsupported")
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "request_timestamp_utc", requested_at)
        expected = derive_isolated_capture_child_request_id(self)
        if self.child_request_id != expected:
            raise IsolatedCaptureArtifactError(
                "child_request_id does not match canonical material"
            )


@dataclass(frozen=True, slots=True)
class IsolatedCaptureChildResult:
    schema_version: int
    child_result_id: UUID
    child_request: ArtifactEvidence
    allocation: ArtifactEvidence
    attempt_id: UUID
    provider_call_disposition: ProviderCallDisposition
    classification: IsolatedCaptureChildClassification
    diagnostics: tuple[str, ...]
    http_status: int | None
    provider_code: int | None
    provider_request_id: str | None
    native_exit_code: int
    snapshot: ArtifactEvidence | None
    snapshot_verification: SnapshotTerminalVerification
    secret_cleanup: SecretCleanupResult
    child_operation_version: str

    def __post_init__(self) -> None:
        if self.schema_version != ISOLATED_CAPTURE_CHILD_RESULT_SCHEMA_VERSION:
            raise IsolatedCaptureArtifactError("child result schema_version must be 1")
        _uuid(self.child_result_id, "child_result_id")
        _evidence(self.child_request, "child_request")
        _evidence(self.allocation, "allocation")
        _uuid(self.attempt_id, "attempt_id")
        if type(self.provider_call_disposition) is not ProviderCallDisposition:
            raise IsolatedCaptureArtifactError("provider_call_disposition is invalid")
        if type(self.classification) is not IsolatedCaptureChildClassification:
            raise IsolatedCaptureArtifactError("classification is invalid")
        diagnostics = _diagnostics(self.diagnostics)
        if self.http_status is not None and (
            type(self.http_status) is not int or not 100 <= self.http_status <= 599
        ):
            raise IsolatedCaptureArtifactError("http_status is invalid")
        if self.provider_code is not None and (
            type(self.provider_code) is not int
            or not -(1 << 31) <= self.provider_code < (1 << 31)
        ):
            raise IsolatedCaptureArtifactError("provider_code is invalid")
        if self.provider_request_id is not None and (
            type(self.provider_request_id) is not str
            or _REQUEST_ID.fullmatch(self.provider_request_id) is None
        ):
            raise IsolatedCaptureArtifactError("provider_request_id is invalid")
        if (
            type(self.native_exit_code) is not int
            or not 0 <= self.native_exit_code < 256
        ):
            raise IsolatedCaptureArtifactError("native_exit_code is invalid")
        if self.snapshot is not None:
            _evidence(self.snapshot, "snapshot")
        if type(self.snapshot_verification) is not SnapshotTerminalVerification:
            raise IsolatedCaptureArtifactError("snapshot_verification is invalid")
        if type(self.secret_cleanup) is not SecretCleanupResult:
            raise IsolatedCaptureArtifactError("secret_cleanup is invalid")
        _policy(self.child_operation_version, "child_operation_version")
        succeeded = self.classification is IsolatedCaptureChildClassification.SUCCEEDED
        if succeeded != (
            self.provider_call_disposition is ProviderCallDisposition.RESPONSE_CONFIRMED
            and self.snapshot is not None
            and self.snapshot_verification is SnapshotTerminalVerification.PASS
            and self.native_exit_code == 0
            and self.secret_cleanup is SecretCleanupResult.PASS
        ):
            raise IsolatedCaptureArtifactError(
                "successful child result requires an independently verified snapshot"
            )
        if (
            not succeeded
            and self.snapshot_verification is SnapshotTerminalVerification.PASS
        ):
            raise IsolatedCaptureArtifactError(
                "failed child result cannot claim snapshot verification PASS"
            )
        object.__setattr__(self, "diagnostics", diagnostics)
        expected = derive_isolated_capture_child_result_id(self)
        if self.child_result_id != expected:
            raise IsolatedCaptureArtifactError(
                "child_result_id does not match canonical material"
            )


@dataclass(frozen=True, slots=True)
class ChildProcessCreationRecord:
    schema_version: int
    process_creation_record_id: UUID
    allocation: ArtifactEvidence
    child_request: ArtifactEvidence
    scheduled_launch_id: UUID
    approved_executable: ArtifactEvidence
    software_release: ArtifactEvidence
    process_id: int | None
    creation_result: ProcessCreationResult
    job_object_assignment: JobObjectAssignmentResult
    handle_inheritance: HandleInheritancePosture
    environment_policy_version: str
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        _process_record_common(
            self.schema_version,
            CHILD_PROCESS_CREATION_RECORD_SCHEMA_VERSION,
            self.process_creation_record_id,
            self.allocation,
            self.child_request,
            self.scheduled_launch_id,
            self.diagnostics,
        )
        _evidence(self.approved_executable, "approved_executable")
        _evidence(self.software_release, "software_release")
        if self.process_id is not None:
            _positive_bounded(self.process_id, "process_id", maximum=(1 << 32) - 1)
        if type(self.creation_result) is not ProcessCreationResult:
            raise IsolatedCaptureArtifactError("creation_result is invalid")
        if type(self.job_object_assignment) is not JobObjectAssignmentResult:
            raise IsolatedCaptureArtifactError("job_object_assignment is invalid")
        if self.handle_inheritance is not HandleInheritancePosture.DISABLED:
            raise IsolatedCaptureArtifactError("handle inheritance must be disabled")
        _policy(self.environment_policy_version, "environment_policy_version")
        created = self.creation_result is ProcessCreationResult.CREATED_SUSPENDED
        if created != (
            self.process_id is not None
            and self.job_object_assignment is JobObjectAssignmentResult.ASSIGNED
        ):
            raise IsolatedCaptureArtifactError(
                "created process must be suspended and assigned to the Job Object"
            )
        if self.process_creation_record_id != derive_child_process_creation_record_id(
            self
        ):
            raise IsolatedCaptureArtifactError(
                "process_creation_record_id does not match canonical material"
            )


@dataclass(frozen=True, slots=True)
class ChildResumeAuthorizationRecord:
    schema_version: int
    resume_authorization_record_id: UUID
    allocation: ArtifactEvidence
    child_request: ArtifactEvidence
    process_creation: ArtifactEvidence
    scheduled_launch_id: UUID
    process_id: int
    evidence_verified: bool
    result: ResumeAuthorizationResult
    diagnostics: tuple[str, ...]
    resume_policy_version: str

    def __post_init__(self) -> None:
        _process_record_common(
            self.schema_version,
            CHILD_RESUME_AUTHORIZATION_RECORD_SCHEMA_VERSION,
            self.resume_authorization_record_id,
            self.allocation,
            self.child_request,
            self.scheduled_launch_id,
            self.diagnostics,
        )
        _evidence(self.process_creation, "process_creation")
        _positive_bounded(self.process_id, "process_id", maximum=(1 << 32) - 1)
        if type(self.evidence_verified) is not bool:
            raise IsolatedCaptureArtifactError("evidence_verified must be a bool")
        if type(self.result) is not ResumeAuthorizationResult:
            raise IsolatedCaptureArtifactError("resume result is invalid")
        _policy(self.resume_policy_version, "resume_policy_version")
        if self.result is ResumeAuthorizationResult.AUTHORIZED and not (
            self.evidence_verified
        ):
            raise IsolatedCaptureArtifactError(
                "resume authorization requires verified evidence"
            )
        if self.resume_authorization_record_id != (
            derive_child_resume_authorization_record_id(self)
        ):
            raise IsolatedCaptureArtifactError(
                "resume_authorization_record_id does not match canonical material"
            )


@dataclass(frozen=True, slots=True)
class ChildTerminationRecord:
    schema_version: int
    termination_record_id: UUID
    allocation: ArtifactEvidence
    child_request: ArtifactEvidence
    process_creation: ArtifactEvidence
    resume_authorization: ArtifactEvidence | None
    scheduled_launch_id: UUID
    process_id: int | None
    timed_out: bool
    job_termination_requested: bool
    process_tree_result: ProcessTreeTerminationResult
    native_exit_code: int | None
    diagnostics: tuple[str, ...]
    termination_policy_version: str

    def __post_init__(self) -> None:
        _process_record_common(
            self.schema_version,
            CHILD_TERMINATION_RECORD_SCHEMA_VERSION,
            self.termination_record_id,
            self.allocation,
            self.child_request,
            self.scheduled_launch_id,
            self.diagnostics,
        )
        _evidence(self.process_creation, "process_creation")
        if self.resume_authorization is not None:
            _evidence(self.resume_authorization, "resume_authorization")
        if self.process_id is not None:
            _positive_bounded(self.process_id, "process_id", maximum=(1 << 32) - 1)
        if (
            type(self.timed_out) is not bool
            or type(self.job_termination_requested) is not bool
        ):
            raise IsolatedCaptureArtifactError("termination booleans are invalid")
        if type(self.process_tree_result) is not ProcessTreeTerminationResult:
            raise IsolatedCaptureArtifactError("process_tree_result is invalid")
        if self.native_exit_code is not None and (
            type(self.native_exit_code) is not int
            or not 0 <= self.native_exit_code <= (1 << 32) - 1
        ):
            raise IsolatedCaptureArtifactError("native_exit_code is invalid")
        _policy(self.termination_policy_version, "termination_policy_version")
        if self.timed_out and not self.job_termination_requested:
            raise IsolatedCaptureArtifactError(
                "timeout requires Job Object termination request"
            )
        if self.termination_record_id != derive_child_termination_record_id(self):
            raise IsolatedCaptureArtifactError(
                "termination_record_id does not match canonical material"
            )


def derive_isolated_capture_child_request_id(
    request: IsolatedCaptureChildRequest,
) -> UUID:
    return _id(
        ISOLATED_CAPTURE_CHILD_REQUEST_NAMESPACE,
        (
            ISOLATED_CAPTURE_CHILD_REQUEST_MATERIAL_VERSION,
            *_evidence_parts(request.allocation),
            str(request.attempt_id),
            str(request.attempt_ordinal),
            str(request.scheduled_session_id),
            str(request.scheduled_launch_id),
            *_evidence_parts(request.credential_reference),
            str(request.snapshot_capture_request_id),
            *_evidence_parts(request.capture_configuration),
            str(len(request.symbols)),
            *(str(symbol) for symbol in request.symbols),
            request.calendar.calendar_id,
            request.calendar.version,
            request.calendar.exchange_timezone,
            request.timeframe.value,
            request.adjustment.value,
            request.provider_id,
            str(request.adapter_version),
            request.provider_operation,
            request.feed,
            request.currency,
            request.target_session.session_date.isoformat(),
            canonical_timestamp(request.request_timestamp_utc),
            request.request_new_york_date.isoformat(),
            str(request.socket_timeout_seconds),
            str(request.wall_timeout_seconds),
            str(request.maximum_response_bytes),
            str(request.maximum_candidate_count),
            *_evidence_parts(request.snapshot_destination_reference),
            *_evidence_parts(request.software_release),
            request.child_operation_version,
        ),
    )


def create_isolated_capture_child_request(
    **values: object,
) -> IsolatedCaptureChildRequest:
    return _create_with_id(
        IsolatedCaptureChildRequest,
        "child_request_id",
        derive_isolated_capture_child_request_id,
        values,
        schema_version=ISOLATED_CAPTURE_CHILD_REQUEST_SCHEMA_VERSION,
    )


def derive_isolated_capture_child_result_id(
    result: IsolatedCaptureChildResult,
) -> UUID:
    return _id(
        ISOLATED_CAPTURE_CHILD_RESULT_NAMESPACE,
        (
            ISOLATED_CAPTURE_CHILD_RESULT_MATERIAL_VERSION,
            *_evidence_parts(result.child_request),
            *_evidence_parts(result.allocation),
            str(result.attempt_id),
            result.provider_call_disposition.value,
            result.classification.value,
            str(len(result.diagnostics)),
            *result.diagnostics,
            _nullable(result.http_status),
            _nullable(result.provider_code),
            "" if result.provider_request_id is None else result.provider_request_id,
            str(result.native_exit_code),
            *_nullable_evidence_parts(result.snapshot),
            result.snapshot_verification.value,
            result.secret_cleanup.value,
            result.child_operation_version,
        ),
    )


def create_isolated_capture_child_result(
    **values: object,
) -> IsolatedCaptureChildResult:
    return _create_with_id(
        IsolatedCaptureChildResult,
        "child_result_id",
        derive_isolated_capture_child_result_id,
        values,
        schema_version=ISOLATED_CAPTURE_CHILD_RESULT_SCHEMA_VERSION,
    )


def derive_child_process_creation_record_id(
    record: ChildProcessCreationRecord,
) -> UUID:
    return _id(
        CHILD_PROCESS_CREATION_RECORD_NAMESPACE,
        (
            CHILD_PROCESS_CREATION_RECORD_MATERIAL_VERSION,
            *_evidence_parts(record.allocation),
            *_evidence_parts(record.child_request),
            str(record.scheduled_launch_id),
            *_evidence_parts(record.approved_executable),
            *_evidence_parts(record.software_release),
            _nullable(record.process_id),
            record.creation_result.value,
            record.job_object_assignment.value,
            record.handle_inheritance.value,
            record.environment_policy_version,
            str(len(record.diagnostics)),
            *record.diagnostics,
        ),
    )


def create_child_process_creation_record(
    **values: object,
) -> ChildProcessCreationRecord:
    return _create_with_id(
        ChildProcessCreationRecord,
        "process_creation_record_id",
        derive_child_process_creation_record_id,
        values,
        schema_version=CHILD_PROCESS_CREATION_RECORD_SCHEMA_VERSION,
    )


def derive_child_resume_authorization_record_id(
    record: ChildResumeAuthorizationRecord,
) -> UUID:
    return _id(
        CHILD_RESUME_AUTHORIZATION_RECORD_NAMESPACE,
        (
            CHILD_RESUME_AUTHORIZATION_RECORD_MATERIAL_VERSION,
            *_evidence_parts(record.allocation),
            *_evidence_parts(record.child_request),
            *_evidence_parts(record.process_creation),
            str(record.scheduled_launch_id),
            str(record.process_id),
            str(record.evidence_verified).lower(),
            record.result.value,
            str(len(record.diagnostics)),
            *record.diagnostics,
            record.resume_policy_version,
        ),
    )


def create_child_resume_authorization_record(
    **values: object,
) -> ChildResumeAuthorizationRecord:
    return _create_with_id(
        ChildResumeAuthorizationRecord,
        "resume_authorization_record_id",
        derive_child_resume_authorization_record_id,
        values,
        schema_version=CHILD_RESUME_AUTHORIZATION_RECORD_SCHEMA_VERSION,
    )


def derive_child_termination_record_id(record: ChildTerminationRecord) -> UUID:
    return _id(
        CHILD_TERMINATION_RECORD_NAMESPACE,
        (
            CHILD_TERMINATION_RECORD_MATERIAL_VERSION,
            *_evidence_parts(record.allocation),
            *_evidence_parts(record.child_request),
            *_evidence_parts(record.process_creation),
            *_nullable_evidence_parts(record.resume_authorization),
            str(record.scheduled_launch_id),
            _nullable(record.process_id),
            str(record.timed_out).lower(),
            str(record.job_termination_requested).lower(),
            record.process_tree_result.value,
            _nullable(record.native_exit_code),
            str(len(record.diagnostics)),
            *record.diagnostics,
            record.termination_policy_version,
        ),
    )


def create_child_termination_record(**values: object) -> ChildTerminationRecord:
    return _create_with_id(
        ChildTerminationRecord,
        "termination_record_id",
        derive_child_termination_record_id,
        values,
        schema_version=CHILD_TERMINATION_RECORD_SCHEMA_VERSION,
    )


def serialize_isolated_capture_child_request(
    request: IsolatedCaptureChildRequest,
) -> bytes:
    return _serialize(request, _request_tree)


def parse_isolated_capture_child_request(
    payload: bytes,
) -> IsolatedCaptureChildRequest:
    root = _object(
        _load(payload),
        {field.name for field in fields(IsolatedCaptureChildRequest)},
        "child request",
    )
    request = IsolatedCaptureChildRequest(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["child_request_id"], "child_request_id"),
        _artifact(root["allocation"], "allocation"),
        _path(root["allocation_path"], "allocation_path"),
        _uuid_value(root["attempt_id"], "attempt_id"),
        _integer(root["attempt_ordinal"], "attempt_ordinal"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _artifact(root["credential_reference"], "credential_reference"),
        _path(root["credential_reference_path"], "credential_reference_path"),
        _uuid_value(root["snapshot_capture_request_id"], "snapshot_capture_request_id"),
        _artifact(root["capture_configuration"], "capture_configuration"),
        _path(root["capture_configuration_path"], "capture_configuration_path"),
        _symbols(root["symbols"]),
        _calendar(root["calendar"]),
        _enum(Timeframe, root["timeframe"], "timeframe"),
        _enum(AdjustmentType, root["adjustment"], "adjustment"),
        _string(root["provider_id"], "provider_id"),
        _integer(root["adapter_version"], "adapter_version"),
        _string(root["provider_operation"], "provider_operation"),
        _string(root["feed"], "feed"),
        _string(root["currency"], "currency"),
        TradingSession(_date(root["target_session"], "target_session")),
        _timestamp(root["request_timestamp_utc"], "request_timestamp_utc"),
        _date(root["request_new_york_date"], "request_new_york_date"),
        _integer(root["socket_timeout_seconds"], "socket_timeout_seconds"),
        _integer(root["wall_timeout_seconds"], "wall_timeout_seconds"),
        _integer(root["maximum_response_bytes"], "maximum_response_bytes"),
        _integer(root["maximum_candidate_count"], "maximum_candidate_count"),
        _artifact(
            root["snapshot_destination_reference"], "snapshot_destination_reference"
        ),
        _path(root["snapshot_destination_path"], "snapshot_destination_path"),
        _path(root["child_result_path"], "child_result_path"),
        _artifact(root["software_release"], "software_release"),
        _string(root["child_operation_version"], "child_operation_version"),
    )
    _canonical(
        payload, serialize_isolated_capture_child_request(request), "child request"
    )
    return request


def serialize_isolated_capture_child_result(
    result: IsolatedCaptureChildResult,
) -> bytes:
    return _serialize(result, _result_tree)


def parse_isolated_capture_child_result(payload: bytes) -> IsolatedCaptureChildResult:
    root = _object(
        _load(payload),
        {field.name for field in fields(IsolatedCaptureChildResult)},
        "child result",
    )
    result = IsolatedCaptureChildResult(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["child_result_id"], "child_result_id"),
        _artifact(root["child_request"], "child_request"),
        _artifact(root["allocation"], "allocation"),
        _uuid_value(root["attempt_id"], "attempt_id"),
        _enum(
            ProviderCallDisposition,
            root["provider_call_disposition"],
            "provider_call_disposition",
        ),
        _enum(
            IsolatedCaptureChildClassification,
            root["classification"],
            "classification",
        ),
        _strings(root["diagnostics"], "diagnostics"),
        _nullable_integer(root["http_status"], "http_status"),
        _nullable_integer(root["provider_code"], "provider_code"),
        _nullable_string(root["provider_request_id"], "provider_request_id"),
        _integer(root["native_exit_code"], "native_exit_code"),
        _nullable_artifact(root["snapshot"], "snapshot"),
        _enum(
            SnapshotTerminalVerification,
            root["snapshot_verification"],
            "snapshot_verification",
        ),
        _enum(SecretCleanupResult, root["secret_cleanup"], "secret_cleanup"),
        _string(root["child_operation_version"], "child_operation_version"),
    )
    _canonical(payload, serialize_isolated_capture_child_result(result), "child result")
    return result


def serialize_child_process_creation_record(
    record: ChildProcessCreationRecord,
) -> bytes:
    return _serialize(record, _creation_tree)


def parse_child_process_creation_record(payload: bytes) -> ChildProcessCreationRecord:
    root = _object(
        _load(payload),
        {field.name for field in fields(ChildProcessCreationRecord)},
        "process creation",
    )
    record = ChildProcessCreationRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["process_creation_record_id"], "process_creation_record_id"),
        _artifact(root["allocation"], "allocation"),
        _artifact(root["child_request"], "child_request"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _artifact(root["approved_executable"], "approved_executable"),
        _artifact(root["software_release"], "software_release"),
        _nullable_integer(root["process_id"], "process_id"),
        _enum(ProcessCreationResult, root["creation_result"], "creation_result"),
        _enum(
            JobObjectAssignmentResult,
            root["job_object_assignment"],
            "job_object_assignment",
        ),
        _enum(
            HandleInheritancePosture,
            root["handle_inheritance"],
            "handle_inheritance",
        ),
        _string(root["environment_policy_version"], "environment_policy_version"),
        _strings(root["diagnostics"], "diagnostics"),
    )
    _canonical(
        payload, serialize_child_process_creation_record(record), "process creation"
    )
    return record


def serialize_child_resume_authorization_record(
    record: ChildResumeAuthorizationRecord,
) -> bytes:
    return _serialize(record, _resume_tree)


def parse_child_resume_authorization_record(
    payload: bytes,
) -> ChildResumeAuthorizationRecord:
    root = _object(
        _load(payload),
        {field.name for field in fields(ChildResumeAuthorizationRecord)},
        "resume authorization",
    )
    record = ChildResumeAuthorizationRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(
            root["resume_authorization_record_id"],
            "resume_authorization_record_id",
        ),
        _artifact(root["allocation"], "allocation"),
        _artifact(root["child_request"], "child_request"),
        _artifact(root["process_creation"], "process_creation"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _integer(root["process_id"], "process_id"),
        _boolean(root["evidence_verified"], "evidence_verified"),
        _enum(ResumeAuthorizationResult, root["result"], "result"),
        _strings(root["diagnostics"], "diagnostics"),
        _string(root["resume_policy_version"], "resume_policy_version"),
    )
    _canonical(
        payload,
        serialize_child_resume_authorization_record(record),
        "resume authorization",
    )
    return record


def serialize_child_termination_record(record: ChildTerminationRecord) -> bytes:
    return _serialize(record, _termination_tree)


def parse_child_termination_record(payload: bytes) -> ChildTerminationRecord:
    root = _object(
        _load(payload),
        {field.name for field in fields(ChildTerminationRecord)},
        "termination",
    )
    record = ChildTerminationRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["termination_record_id"], "termination_record_id"),
        _artifact(root["allocation"], "allocation"),
        _artifact(root["child_request"], "child_request"),
        _artifact(root["process_creation"], "process_creation"),
        _nullable_artifact(root["resume_authorization"], "resume_authorization"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _nullable_integer(root["process_id"], "process_id"),
        _boolean(root["timed_out"], "timed_out"),
        _boolean(root["job_termination_requested"], "job_termination_requested"),
        _enum(
            ProcessTreeTerminationResult,
            root["process_tree_result"],
            "process_tree_result",
        ),
        _nullable_integer(root["native_exit_code"], "native_exit_code"),
        _strings(root["diagnostics"], "diagnostics"),
        _string(root["termination_policy_version"], "termination_policy_version"),
    )
    _canonical(payload, serialize_child_termination_record(record), "termination")
    return record


def reconcile_child_request(
    request: IsolatedCaptureChildRequest,
    allocation: CaptureAttemptAllocationRecord,
    credential_reference: WindowsMarketDataCredentialReference,
    capture_configuration: object,
) -> None:
    """Require exact allocation, credential, configuration, and provider policy."""
    if type(request) is not IsolatedCaptureChildRequest:
        raise IsolatedCaptureReconciliationError("child request type is invalid")
    if type(allocation) is not CaptureAttemptAllocationRecord:
        raise IsolatedCaptureReconciliationError("allocation type is invalid")
    if type(credential_reference) is not WindowsMarketDataCredentialReference:
        raise IsolatedCaptureReconciliationError("credential reference type is invalid")
    config_request_id = getattr(capture_configuration, "request_id", None)
    config_symbols = getattr(capture_configuration, "symbols", None)
    config_calendar = getattr(capture_configuration, "calendar", None)
    config_timeframe = getattr(capture_configuration, "timeframe", None)
    config_adjustment = getattr(capture_configuration, "adjustment", None)
    config_provider = getattr(capture_configuration, "provider", None)
    if (
        request.allocation.artifact_id != allocation.allocation_record_id
        or request.attempt_id != allocation.attempt_id
        or request.attempt_ordinal != allocation.attempt_ordinal
        or request.scheduled_session_id != allocation.scheduled_session_id
        or request.scheduled_launch_id != allocation.scheduled_launch_id
        or request.credential_reference != allocation.credential_reference
        or request.credential_reference.artifact_id
        != credential_reference.credential_reference_id
        or request.snapshot_capture_request_id != allocation.snapshot_capture_request_id
        or request.capture_configuration != allocation.capture_configuration
        or request.symbols != allocation.symbols
        or request.timeframe is not allocation.timeframe
        or request.adjustment is not allocation.adjustment
        or request.target_session != allocation.target_session
        or request.request_timestamp_utc != allocation.request_timestamp_utc
        or request.snapshot_destination_reference != allocation.destination_reference
        or request.software_release != allocation.software_release
        or credential_reference.provider_id != request.provider_id
        or credential_reference.credential_version
        != allocation.credential_reference_version
        or config_request_id != request.snapshot_capture_request_id
        or config_symbols != request.symbols
        or config_calendar != request.calendar
        or config_timeframe is not request.timeframe
        or config_adjustment is not request.adjustment
        or config_provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
        or allocation.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
        or allocation.feed.casefold() != ISOLATED_CAPTURE_FEED.casefold()
        or allocation.currency != request.currency
        or allocation.provider_call_budget != 1
    ):
        raise IsolatedCaptureReconciliationError(
            "child request does not reconcile with exact authoritative inputs"
        )


def evidence_for_payload(artifact_id: UUID, payload: bytes) -> ArtifactEvidence:
    return ArtifactEvidence(
        artifact_id, hashlib.sha256(payload).hexdigest(), len(payload)
    )


def verify_payload_evidence(payload: bytes, evidence: ArtifactEvidence) -> None:
    _evidence(evidence, "evidence")
    if (
        len(payload) != evidence.byte_length
        or hashlib.sha256(payload).hexdigest() != evidence.sha256
    ):
        raise IsolatedCaptureReconciliationError(
            "artifact bytes do not match exact evidence"
        )


def publish_canonical_artifact(
    path: Path,
    payload: bytes,
    parser: object,
) -> Path:
    """Publish exact canonical bytes with exclusive staging and no clobber."""
    if not isinstance(path, Path) or not path.is_absolute():
        raise IsolatedCapturePublicationError("artifact path must be absolute")
    parent = path.parent
    try:
        parent_state = os.lstat(parent)
    except OSError as error:
        raise IsolatedCapturePublicationError(
            "artifact parent must be an existing real directory"
        ) from error
    if (
        not stat.S_ISDIR(parent_state.st_mode)
        or stat.S_ISLNK(parent_state.st_mode)
        or _is_reparse(parent_state)
    ):
        raise IsolatedCapturePublicationError(
            "artifact parent must be an existing real directory"
        )
    if path.exists():
        existing = _bounded_read(path)
        if existing != payload:
            raise IsolatedCapturePublicationError(
                "existing artifact conflicts with canonical bytes"
            )
        parser(existing)  # type: ignore[operator]
        return path
    staging = parent / f".{path.name}.staging"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(staging, flags, 0o600)
    except FileExistsError as error:
        raise IsolatedCapturePublicationError(
            "crash-left staging requires manual review"
        ) from error
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    if _bounded_read(staging) != payload:
        raise IsolatedCapturePublicationError("staging reread differs")
    parser(payload)  # type: ignore[operator]
    current_parent = os.lstat(parent)
    if (current_parent.st_dev, current_parent.st_ino) != (
        parent_state.st_dev,
        parent_state.st_ino,
    ):
        raise IsolatedCapturePublicationError("artifact parent identity changed")
    try:
        os.link(staging, path)
    except FileExistsError as error:
        if _bounded_read(path) != payload:
            raise IsolatedCapturePublicationError("no-clobber conflict") from error
    if _bounded_read(path) != payload:
        raise IsolatedCapturePublicationError("final artifact differs")
    parser(payload)  # type: ignore[operator]
    try:
        staging.unlink()
    except OSError as error:
        raise IsolatedCapturePublicationError(
            "final artifact installed but staging cleanup failed"
        ) from error
    return path


def _request_tree(value: IsolatedCaptureChildRequest) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "child_request_id": str(value.child_request_id),
        "allocation": _artifact_tree(value.allocation),
        "allocation_path": str(value.allocation_path),
        "attempt_id": str(value.attempt_id),
        "attempt_ordinal": value.attempt_ordinal,
        "scheduled_session_id": str(value.scheduled_session_id),
        "scheduled_launch_id": str(value.scheduled_launch_id),
        "credential_reference": _artifact_tree(value.credential_reference),
        "credential_reference_path": str(value.credential_reference_path),
        "snapshot_capture_request_id": str(value.snapshot_capture_request_id),
        "capture_configuration": _artifact_tree(value.capture_configuration),
        "capture_configuration_path": str(value.capture_configuration_path),
        "symbols": [str(symbol) for symbol in value.symbols],
        "calendar": {
            "calendar_id": value.calendar.calendar_id,
            "version": value.calendar.version,
            "exchange_timezone": value.calendar.exchange_timezone,
        },
        "timeframe": value.timeframe.value,
        "adjustment": value.adjustment.value,
        "provider_id": value.provider_id,
        "adapter_version": value.adapter_version,
        "provider_operation": value.provider_operation,
        "feed": value.feed,
        "currency": value.currency,
        "target_session": value.target_session.session_date.isoformat(),
        "request_timestamp_utc": canonical_timestamp(value.request_timestamp_utc),
        "request_new_york_date": value.request_new_york_date.isoformat(),
        "socket_timeout_seconds": value.socket_timeout_seconds,
        "wall_timeout_seconds": value.wall_timeout_seconds,
        "maximum_response_bytes": value.maximum_response_bytes,
        "maximum_candidate_count": value.maximum_candidate_count,
        "snapshot_destination_reference": _artifact_tree(
            value.snapshot_destination_reference
        ),
        "snapshot_destination_path": str(value.snapshot_destination_path),
        "child_result_path": str(value.child_result_path),
        "software_release": _artifact_tree(value.software_release),
        "child_operation_version": value.child_operation_version,
    }


def _result_tree(value: IsolatedCaptureChildResult) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "child_result_id": str(value.child_result_id),
        "child_request": _artifact_tree(value.child_request),
        "allocation": _artifact_tree(value.allocation),
        "attempt_id": str(value.attempt_id),
        "provider_call_disposition": value.provider_call_disposition.value,
        "classification": value.classification.value,
        "diagnostics": list(value.diagnostics),
        "http_status": value.http_status,
        "provider_code": value.provider_code,
        "provider_request_id": value.provider_request_id,
        "native_exit_code": value.native_exit_code,
        "snapshot": _nullable_artifact_tree(value.snapshot),
        "snapshot_verification": value.snapshot_verification.value,
        "secret_cleanup": value.secret_cleanup.value,
        "child_operation_version": value.child_operation_version,
    }


def _creation_tree(value: ChildProcessCreationRecord) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "process_creation_record_id": str(value.process_creation_record_id),
        "allocation": _artifact_tree(value.allocation),
        "child_request": _artifact_tree(value.child_request),
        "scheduled_launch_id": str(value.scheduled_launch_id),
        "approved_executable": _artifact_tree(value.approved_executable),
        "software_release": _artifact_tree(value.software_release),
        "process_id": value.process_id,
        "creation_result": value.creation_result.value,
        "job_object_assignment": value.job_object_assignment.value,
        "handle_inheritance": value.handle_inheritance.value,
        "environment_policy_version": value.environment_policy_version,
        "diagnostics": list(value.diagnostics),
    }


def _resume_tree(value: ChildResumeAuthorizationRecord) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "resume_authorization_record_id": str(value.resume_authorization_record_id),
        "allocation": _artifact_tree(value.allocation),
        "child_request": _artifact_tree(value.child_request),
        "process_creation": _artifact_tree(value.process_creation),
        "scheduled_launch_id": str(value.scheduled_launch_id),
        "process_id": value.process_id,
        "evidence_verified": value.evidence_verified,
        "result": value.result.value,
        "diagnostics": list(value.diagnostics),
        "resume_policy_version": value.resume_policy_version,
    }


def _termination_tree(value: ChildTerminationRecord) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "termination_record_id": str(value.termination_record_id),
        "allocation": _artifact_tree(value.allocation),
        "child_request": _artifact_tree(value.child_request),
        "process_creation": _artifact_tree(value.process_creation),
        "resume_authorization": _nullable_artifact_tree(value.resume_authorization),
        "scheduled_launch_id": str(value.scheduled_launch_id),
        "process_id": value.process_id,
        "timed_out": value.timed_out,
        "job_termination_requested": value.job_termination_requested,
        "process_tree_result": value.process_tree_result.value,
        "native_exit_code": value.native_exit_code,
        "diagnostics": list(value.diagnostics),
        "termination_policy_version": value.termination_policy_version,
    }


def _serialize(value: object, tree: object) -> bytes:
    return (
        json.dumps(
            tree(value),  # type: ignore[operator]
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _load(payload: bytes) -> object:
    if type(payload) is not bytes or len(payload) > MAX_ISOLATED_CAPTURE_ARTIFACT_BYTES:
        raise IsolatedCaptureArtifactSyntaxError(
            "artifact bytes are invalid or oversized"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise IsolatedCaptureArtifactSyntaxError("UTF-8 BOM is unsupported")
    try:
        text = payload.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IsolatedCaptureArtifactSyntaxError(
            "artifact is not valid strict UTF-8 JSON"
        ) from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IsolatedCaptureArtifactSyntaxError("duplicate JSON member")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise IsolatedCaptureArtifactSyntaxError("floats are unsupported")


def _reject_constant(value: str) -> None:
    raise IsolatedCaptureArtifactSyntaxError(
        f"nonstandard JSON constant is unsupported: {value}"
    )


def _object(value: object, expected: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} fields do not match schema")
    return value


def _artifact(value: object, label: str) -> ArtifactEvidence:
    root = _object(value, {"artifact_id", "sha256", "byte_length"}, label)
    return ArtifactEvidence(
        _uuid_value(root["artifact_id"], f"{label}.artifact_id"),
        _string(root["sha256"], f"{label}.sha256"),
        _integer(root["byte_length"], f"{label}.byte_length"),
    )


def _nullable_artifact(value: object, label: str) -> ArtifactEvidence | None:
    return None if value is None else _artifact(value, label)


def _artifact_tree(value: ArtifactEvidence) -> dict[str, object]:
    return {
        "artifact_id": str(value.artifact_id),
        "sha256": value.sha256,
        "byte_length": value.byte_length,
    }


def _nullable_artifact_tree(
    value: ArtifactEvidence | None,
) -> dict[str, object] | None:
    return None if value is None else _artifact_tree(value)


def _calendar(value: object) -> CalendarDescriptor:
    root = _object(value, {"calendar_id", "version", "exchange_timezone"}, "calendar")
    return CalendarDescriptor(
        _string(root["calendar_id"], "calendar.calendar_id"),
        _string(root["version"], "calendar.version"),
        _string(root["exchange_timezone"], "calendar.exchange_timezone"),
    )


def _symbols(value: object) -> tuple[Symbol, ...]:
    if type(value) is not list:
        raise IsolatedCaptureArtifactSyntaxError("symbols must be an array")
    try:
        symbols = tuple(Symbol(_string(item, "symbol")) for item in value)
    except ValueError as error:
        raise IsolatedCaptureArtifactSyntaxError("symbol is invalid") from error
    if any(str(symbol) != raw for symbol, raw in zip(symbols, value, strict=True)):
        raise IsolatedCaptureArtifactSyntaxError("symbol text is noncanonical")
    return symbols


def _strings(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} must be an array")
    return tuple(_string(item, label) for item in value)


def _uuid_value(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is invalid") from error
    if str(parsed) != text:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is noncanonical")
    return parsed


def _path(value: object, label: str) -> Path:
    return Path(_string(value, label))


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is invalid") from error
    if parsed.isoformat() != text:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is noncanonical")
    return parsed


def _timestamp(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise IsolatedCaptureArtifactSyntaxError(f"{label} must use canonical UTC")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is invalid") from error
    if canonical_timestamp(parsed) != text:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is noncanonical")
    return parsed


def _enum(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    try:
        return enum_type(_string(value, label))
    except ValueError as error:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} is invalid") from error


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} must be a string")
    return value


def _nullable_string(value: object, label: str) -> str | None:
    return None if value is None else _string(value, label)


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} must be an integer")
    return value


def _nullable_integer(value: object, label: str) -> int | None:
    return None if value is None else _integer(value, label)


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} must be a bool")
    return value


def _canonical(payload: bytes, canonical: bytes, label: str) -> None:
    if payload != canonical:
        raise IsolatedCaptureArtifactSyntaxError(f"{label} bytes are noncanonical")


def _uuid(value: object, label: str) -> None:
    if type(value) is not UUID or value.int == 0:
        raise IsolatedCaptureArtifactError(f"{label} must be a nonzero UUID")


def _evidence(value: object, label: str) -> None:
    if type(value) is not ArtifactEvidence:
        raise IsolatedCaptureArtifactError(f"{label} must be ArtifactEvidence")


def _absolute_path(value: object, label: str) -> None:
    if not isinstance(value, Path) or not value.is_absolute():
        raise IsolatedCaptureArtifactError(f"{label} must be absolute")


def _nonnegative(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise IsolatedCaptureArtifactError(f"{label} must be nonnegative")


def _positive_bounded(value: object, label: str, *, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise IsolatedCaptureArtifactError(f"{label} is outside its approved bound")


def _policy(value: object, label: str) -> None:
    if type(value) is not str or _POLICY.fullmatch(value) is None:
        raise IsolatedCaptureArtifactError(f"{label} is invalid")


def _diagnostics(value: object) -> tuple[str, ...]:
    try:
        diagnostics = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise IsolatedCaptureArtifactError("diagnostics must be iterable") from error
    if (
        len(diagnostics) > 32
        or any(
            type(item) is not str or _DIAGNOSTIC.fullmatch(item) is None
            for item in diagnostics
        )
        or len(set(diagnostics)) != len(diagnostics)
    ):
        raise IsolatedCaptureArtifactError("diagnostics are invalid")
    return diagnostics


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise IsolatedCaptureArtifactError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _evidence_parts(value: ArtifactEvidence) -> tuple[str, str, str]:
    return str(value.artifact_id), value.sha256, str(value.byte_length)


def _nullable_evidence_parts(
    value: ArtifactEvidence | None,
) -> tuple[str, ...]:
    return ("0",) if value is None else ("1", *_evidence_parts(value))


def _nullable(value: int | None) -> str:
    return "" if value is None else str(value)


def _id(namespace: UUID, parts: tuple[str, ...]) -> UUID:
    material = "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
    return uuid5(namespace, material)


def _create_with_id(
    model: type,
    id_field: str,
    derive: object,
    values: dict[str, object],
    *,
    schema_version: int,
) -> object:
    supplied = dict(values)
    supplied.setdefault("schema_version", schema_version)
    supplied.setdefault(id_field, UUID(int=0))
    names = tuple(field.name for field in fields(model))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing fields: {', '.join(missing)}")
    provisional_values = dict(supplied)
    provisional_values[id_field] = UUID(int=1)
    provisional = object.__new__(model)
    for name in names:
        object.__setattr__(provisional, name, provisional_values[name])
    supplied[id_field] = derive(provisional)  # type: ignore[operator]
    return model(**{name: supplied[name] for name in names})


def _process_record_common(
    schema_version: int,
    expected_schema: int,
    record_id: UUID,
    allocation: ArtifactEvidence,
    child_request: ArtifactEvidence,
    scheduled_launch_id: UUID,
    diagnostics: tuple[str, ...],
) -> None:
    if schema_version != expected_schema:
        raise IsolatedCaptureArtifactError("process record schema_version must be 1")
    _uuid(record_id, "record_id")
    _evidence(allocation, "allocation")
    _evidence(child_request, "child_request")
    _uuid(scheduled_launch_id, "scheduled_launch_id")
    _diagnostics(diagnostics)


def _bounded_read(path: Path) -> bytes:
    try:
        state = os.lstat(path)
    except OSError as error:
        raise IsolatedCapturePublicationError("artifact cannot be read") from error
    if (
        not stat.S_ISREG(state.st_mode)
        or stat.S_ISLNK(state.st_mode)
        or _is_reparse(state)
        or state.st_size > MAX_ISOLATED_CAPTURE_ARTIFACT_BYTES
    ):
        raise IsolatedCapturePublicationError("artifact is not a bounded regular file")
    payload = path.read_bytes()
    if len(payload) > MAX_ISOLATED_CAPTURE_ARTIFACT_BYTES:
        raise IsolatedCapturePublicationError("artifact exceeds read bound")
    return payload


def _is_reparse(value: os.stat_result) -> bool:
    return bool(getattr(value, "st_file_attributes", 0) & 0x400)
