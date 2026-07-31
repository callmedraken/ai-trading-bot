"""Provider-free authority for scheduled capture-attempt evidence.

This module deliberately stops before credential retrieval, process creation,
network access, snapshot capture, and retry execution.  It records the
authority boundary that a later provider runner must consume.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    AdjustmentType,
    ProviderDescriptor,
    Timeframe,
)
from trading_bot.market_data.daily_snapshot_identity import canonical_timestamp
from trading_bot.runtime.guarded_capture_readiness import (
    NextEligibleAction,
    ScheduledCaptureReadinessDecision,
)
from trading_bot.runtime.scheduled_readiness import (
    ArtifactEvidence,
    HeadRecordEvidence,
    ScheduledReadinessClassification,
    TerminalCheckpointEvidence,
    derive_scheduled_capture_attempt_id,
)

MAX_CAPTURE_ATTEMPT_ARTIFACT_BYTES = 512 * 1024
MAX_CAPTURE_ATTEMPT_ITEMS = 100
MAX_CAPTURE_ATTEMPT_TEXT = 256
MAX_CAPTURE_ATTEMPT_INTEGER = (1 << 63) - 1


def validate_output_parent(path: Path):  # type: ignore[no-untyped-def]
    """Load the shared output-parent validator only when authority writes."""
    from trading_bot.cli.checkpoint_transition_output import (
        validate_output_parent as shared_validate_output_parent,
    )

    return shared_validate_output_parent(path)


WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_SCHEMA_VERSION = 1
WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_MATERIAL_VERSION = (
    "windows-market-data-credential-reference-v1"
)
WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_NAMESPACE = UUID(
    "d4f985b0-7c04-58cc-a5f3-2db32d301b77"
)

CAPTURE_ATTEMPT_ALLOCATION_SCHEMA_VERSION = 1
CAPTURE_ATTEMPT_ALLOCATION_MATERIAL_VERSION = "capture-attempt-allocation-v1"
CAPTURE_ATTEMPT_ALLOCATION_NAMESPACE = UUID("f759d6d6-b147-5b82-883a-4a0f1e3b3a1c")

ATTEMPT_HISTORY_HEAD_SCHEMA_VERSION = 1
ATTEMPT_HISTORY_HEAD_MATERIAL_VERSION = "capture-attempt-history-head-v1"
ATTEMPT_HISTORY_HEAD_NAMESPACE = UUID("e55f1b39-6f42-58c5-95cb-34f0b3aa9f0c")
CURRENT_ATTEMPT_HISTORY_REFERENCE_SCHEMA_VERSION = 1

CAPTURE_ATTEMPT_TERMINAL_SCHEMA_VERSION = 2
CAPTURE_ATTEMPT_TERMINAL_MATERIAL_VERSION = "capture-attempt-terminal-v2"
CAPTURE_ATTEMPT_TERMINAL_NAMESPACE = UUID("37f3e0e7-12d5-53c0-bc64-fad7443e7ed5")

ZERO_PROVIDER_CALL_PROOF_SCHEMA_VERSION = 1
ZERO_PROVIDER_CALL_PROOF_MATERIAL_VERSION = "zero-provider-call-proof-v1"
ZERO_PROVIDER_CALL_PROOF_NAMESPACE = UUID("a10d1b65-72b9-5b0b-a4af-5a2fd9c0ed4a")

MANUAL_CAPTURE_RECOVERY_SCHEMA_VERSION = 1
MANUAL_CAPTURE_RECOVERY_MATERIAL_VERSION = "manual-capture-attempt-recovery-v1"
MANUAL_CAPTURE_RECOVERY_NAMESPACE = UUID("b97ef1a8-6de8-5dc6-a1aa-f369ba5a0f9a")

CAPTURE_TERMINAL_SELECTION_SCHEMA_VERSION = 1
CAPTURE_TERMINAL_SELECTION_MATERIAL_VERSION = "capture-terminal-selection-v1"
CAPTURE_TERMINAL_SELECTION_NAMESPACE = UUID("c27d17bc-c8b5-50e7-9d8f-5ef4c9ef0a67")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]*$")
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_SID = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$")
_TARGET = re.compile(
    r"^AITradingBot/AlpacaMarketData/v1/[a-z0-9][a-z0-9._-]{0,31}/"
    r"(?:KeyId|SecretKey)/[1-9][0-9]{0,17}$"
)


class CaptureAttemptAuthorityError(ValueError):
    """Base error for strict capture-attempt authority artifacts."""


class CaptureAttemptArtifactSyntaxError(CaptureAttemptAuthorityError):
    """Raised when canonical artifact bytes cannot be parsed."""


class CaptureAttemptHistoryClassification(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    CONFLICTING = "CONFLICTING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class CredentialStoreType(StrEnum):
    WINDOWS_CREDENTIAL_MANAGER_GENERIC = "WINDOWS_CREDENTIAL_MANAGER_GENERIC"


class CredentialPersistence(StrEnum):
    LOCAL_MACHINE = "LOCAL_MACHINE"


class CredentialPurpose(StrEnum):
    MARKET_DATA_CAPTURE_ONLY = "MARKET_DATA_CAPTURE_ONLY"


class CaptureAllocationClassification(StrEnum):
    CAPTURE_ONLY_AUTHORIZED = "CAPTURE_ONLY_AUTHORIZED"


class AttemptHistoryState(StrEnum):
    EMPTY = "EMPTY"
    ALLOCATED_NOT_LAUNCHED = "ALLOCATED_NOT_LAUNCHED"
    LAUNCH_MAY_HAVE_OCCURRED = "LAUNCH_MAY_HAVE_OCCURRED"
    TERMINAL_SELECTED = "TERMINAL_SELECTED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    SUCCESS_SELECTED = "SUCCESS_SELECTED"
    SESSION_CLOSED = "SESSION_CLOSED"


class AttemptHistoryCause(StrEnum):
    GENESIS = "GENESIS"
    ALLOCATION = "ALLOCATION"
    LAUNCH_AUTHORIZATION = "LAUNCH_AUTHORIZATION"
    TERMINAL = "TERMINAL"
    ZERO_CALL_RECOVERY = "ZERO_CALL_RECOVERY"
    MANUAL_RECOVERY = "MANUAL_RECOVERY"
    TERMINAL_SELECTION = "TERMINAL_SELECTION"
    SESSION_CLOSE = "SESSION_CLOSE"


class ProviderCallDisposition(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    MAY_HAVE_STARTED = "MAY_HAVE_STARTED"
    RESPONSE_CONFIRMED = "RESPONSE_CONFIRMED"
    UNKNOWN = "UNKNOWN"


class CaptureAttemptTerminalClassification(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    NETWORK_FAILED = "NETWORK_FAILED"
    TIMEOUT = "TIMEOUT"
    INCOMPLETE_RESPONSE = "INCOMPLETE_RESPONSE"
    OUTPUT_FAILED = "OUTPUT_FAILED"
    CHILD_CRASHED = "CHILD_CRASHED"
    UNKNOWN_AFTER_LAUNCH = "UNKNOWN_AFTER_LAUNCH"


class SnapshotTerminalVerification(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SecretCleanupResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ZeroProviderCallProofClassification(StrEnum):
    CHILD_NOT_CREATED = "CHILD_NOT_CREATED"
    CHILD_CREATED_NEVER_RESUMED = "CHILD_CREATED_NEVER_RESUMED"
    CHILD_EXITED_BEFORE_PROVIDER_ADAPTER = "CHILD_EXITED_BEFORE_PROVIDER_ADAPTER"
    PROVIDER_ADAPTER_NOT_ENTERED = "PROVIDER_ADAPTER_NOT_ENTERED"
    TRANSPORT_NOT_ENTERED = "TRANSPORT_NOT_ENTERED"


class ManualCaptureAttemptRecoveryAction(StrEnum):
    CONTINUE_ALLOCATED_ATTEMPT_WITH_ZERO_CALL_PROOF = (
        "CONTINUE_ALLOCATED_ATTEMPT_WITH_ZERO_CALL_PROOF"
    )
    SELECT_EXISTING_TERMINAL = "SELECT_EXISTING_TERMINAL"
    RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS = "RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS"
    MARK_ATTEMPT_AMBIGUOUS_AND_REQUIRE_NEW_REVIEW = (
        "MARK_ATTEMPT_AMBIGUOUS_AND_REQUIRE_NEW_REVIEW"
    )
    CLOSE_SESSION_WITHOUT_CAPTURE = "CLOSE_SESSION_WITHOUT_CAPTURE"


class CaptureRetryClassification(StrEnum):
    SAME_ATTEMPT_CONTINUATION_ALLOWED = "SAME_ATTEMPT_CONTINUATION_ALLOWED"
    NEW_ATTEMPT_AFTER_BACKOFF = "NEW_ATTEMPT_AFTER_BACKOFF"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_CLOSED = "SESSION_CLOSED"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    CONFLICTING = "CONFLICTING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class WindowsMarketDataCredentialReference:
    schema_version: int
    credential_reference_id: UUID
    store_type: CredentialStoreType
    owner_account_sid: str
    api_key_id_target_name: str
    api_secret_key_target_name: str
    credential_version: str
    persistence: CredentialPersistence
    provider_id: str
    purpose: CredentialPurpose
    permission_profile: str
    permission_attestation_evidence: ArtifactEvidence
    rotation_generation: int
    reference_policy_version: str

    def __post_init__(self) -> None:
        if (
            self.schema_version
            != WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_SCHEMA_VERSION
        ):
            raise CaptureAttemptAuthorityError(
                "credential reference schema_version must be 1"
            )
        _uuid(self.credential_reference_id, "credential_reference_id")
        if (
            self.store_type
            is not CredentialStoreType.WINDOWS_CREDENTIAL_MANAGER_GENERIC
        ):
            raise CaptureAttemptAuthorityError("credential store type is unsupported")
        if (
            type(self.owner_account_sid) is not str
            or _SID.fullmatch(self.owner_account_sid) is None
        ):
            raise CaptureAttemptAuthorityError("owner_account_sid is not canonical")
        for value, label in (
            (self.api_key_id_target_name, "api_key_id_target_name"),
            (self.api_secret_key_target_name, "api_secret_key_target_name"),
        ):
            if (
                type(value) is not str
                or len(value) > MAX_CAPTURE_ATTEMPT_TEXT
                or _TARGET.fullmatch(value) is None
            ):
                raise CaptureAttemptAuthorityError(
                    f"{label} is not a versioned target name"
                )
        if self.api_key_id_target_name == self.api_secret_key_target_name:
            raise CaptureAttemptAuthorityError("credential target names must differ")
        _text(self.credential_version, "credential_version")
        if self.persistence is not CredentialPersistence.LOCAL_MACHINE:
            raise CaptureAttemptAuthorityError("credential persistence is unsupported")
        if self.provider_id != "ALPACA_MARKET_DATA":
            raise CaptureAttemptAuthorityError("provider_id must be ALPACA_MARKET_DATA")
        if self.purpose is not CredentialPurpose.MARKET_DATA_CAPTURE_ONLY:
            raise CaptureAttemptAuthorityError("credential purpose is unsupported")
        _text(self.permission_profile, "permission_profile")
        if type(self.permission_attestation_evidence) is not ArtifactEvidence:
            raise CaptureAttemptAuthorityError(
                "permission attestation evidence is invalid"
            )
        _nonnegative(self.rotation_generation, "rotation_generation")
        _policy(self.reference_policy_version, "reference_policy_version")
        expected = derive_windows_market_data_credential_reference_id(
            store_type=self.store_type,
            owner_account_sid=self.owner_account_sid,
            api_key_id_target_name=self.api_key_id_target_name,
            api_secret_key_target_name=self.api_secret_key_target_name,
            credential_version=self.credential_version,
            persistence=self.persistence,
            provider_id=self.provider_id,
            purpose=self.purpose,
            permission_profile=self.permission_profile,
            permission_attestation_evidence=self.permission_attestation_evidence,
            rotation_generation=self.rotation_generation,
            reference_policy_version=self.reference_policy_version,
        )
        if self.credential_reference_id != expected:
            raise CaptureAttemptAuthorityError(
                "credential_reference_id does not match canonical material"
            )


def derive_windows_market_data_credential_reference_id(
    *,
    store_type: CredentialStoreType,
    owner_account_sid: str,
    api_key_id_target_name: str,
    api_secret_key_target_name: str,
    credential_version: str,
    persistence: CredentialPersistence,
    provider_id: str,
    purpose: CredentialPurpose,
    permission_profile: str,
    permission_attestation_evidence: ArtifactEvidence,
    rotation_generation: int,
    reference_policy_version: str,
) -> UUID:
    if type(permission_attestation_evidence) is not ArtifactEvidence:
        raise CaptureAttemptAuthorityError("permission attestation evidence is invalid")
    return _id(
        WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_NAMESPACE,
        (
            WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_MATERIAL_VERSION,
            store_type.value,
            owner_account_sid,
            api_key_id_target_name,
            api_secret_key_target_name,
            credential_version,
            persistence.value,
            provider_id,
            purpose.value,
            permission_profile,
            *_evidence_parts(permission_attestation_evidence),
            str(rotation_generation),
            reference_policy_version,
        ),
    )


def create_windows_market_data_credential_reference(
    *,
    owner_account_sid: str,
    api_key_id_target_name: str,
    api_secret_key_target_name: str,
    credential_version: str,
    permission_profile: str,
    permission_attestation_evidence: ArtifactEvidence,
    rotation_generation: int,
    reference_policy_version: str,
) -> WindowsMarketDataCredentialReference:
    store = CredentialStoreType.WINDOWS_CREDENTIAL_MANAGER_GENERIC
    persistence = CredentialPersistence.LOCAL_MACHINE
    provider_id = "ALPACA_MARKET_DATA"
    purpose = CredentialPurpose.MARKET_DATA_CAPTURE_ONLY
    reference_id = derive_windows_market_data_credential_reference_id(
        store_type=store,
        owner_account_sid=owner_account_sid,
        api_key_id_target_name=api_key_id_target_name,
        api_secret_key_target_name=api_secret_key_target_name,
        credential_version=credential_version,
        persistence=persistence,
        provider_id=provider_id,
        purpose=purpose,
        permission_profile=permission_profile,
        permission_attestation_evidence=permission_attestation_evidence,
        rotation_generation=rotation_generation,
        reference_policy_version=reference_policy_version,
    )
    return WindowsMarketDataCredentialReference(
        WINDOWS_MARKET_DATA_CREDENTIAL_REFERENCE_SCHEMA_VERSION,
        reference_id,
        store,
        owner_account_sid,
        api_key_id_target_name,
        api_secret_key_target_name,
        credential_version,
        persistence,
        provider_id,
        purpose,
        permission_profile,
        permission_attestation_evidence,
        rotation_generation,
        reference_policy_version,
    )


@dataclass(frozen=True, slots=True)
class CaptureAttemptAllocationRecord:
    schema_version: int
    allocation_record_id: UUID
    attempt_id: UUID
    attempt_ordinal: int
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    authority_epoch_id: UUID
    head_record: HeadRecordEvidence
    verified_lineage_evidence_id: UUID
    terminal_checkpoint: TerminalCheckpointEvidence
    terminal_as_of: datetime
    readiness_decision: ArtifactEvidence
    market_hours_schedule: ArtifactEvidence
    capture_policy: ArtifactEvidence
    capture_policy_version: str
    capture_configuration: ArtifactEvidence
    snapshot_capture_request_id: UUID
    target_session: TradingSession
    request_timestamp_utc: datetime
    symbols: tuple[Symbol, ...]
    timeframe: Timeframe
    adjustment: AdjustmentType
    provider: ProviderDescriptor
    feed: str
    currency: str
    credential_reference: ArtifactEvidence
    credential_reference_version: str
    destination_reference: ArtifactEvidence
    software_release: ArtifactEvidence
    observed_allocation_at: datetime
    previous_attempt_history_head: ArtifactEvidence
    allocation_classification: CaptureAllocationClassification
    provider_call_budget: int
    allocation_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != CAPTURE_ATTEMPT_ALLOCATION_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError("allocation schema_version must be 1")
        for value, label in (
            (self.allocation_record_id, "allocation_record_id"),
            (self.attempt_id, "attempt_id"),
            (self.scheduled_session_id, "scheduled_session_id"),
            (self.scheduled_launch_id, "scheduled_launch_id"),
            (self.authority_epoch_id, "authority_epoch_id"),
            (self.verified_lineage_evidence_id, "verified_lineage_evidence_id"),
            (self.snapshot_capture_request_id, "snapshot_capture_request_id"),
        ):
            _uuid(value, label)
        _nonnegative(self.attempt_ordinal, "attempt_ordinal")
        if (
            type(self.head_record) is not HeadRecordEvidence
            or self.head_record.authority_epoch_id != self.authority_epoch_id
        ):
            raise CaptureAttemptAuthorityError(
                "head record evidence does not reconcile"
            )
        if type(self.terminal_checkpoint) is not TerminalCheckpointEvidence:
            raise CaptureAttemptAuthorityError(
                "terminal checkpoint evidence is invalid"
            )
        if (
            self.terminal_as_of != _utc(self.terminal_as_of, "terminal_as_of")
            or self.terminal_as_of != self.terminal_checkpoint.as_of
        ):
            raise CaptureAttemptAuthorityError("terminal_as_of does not reconcile")
        for value, label in (
            (self.readiness_decision, "readiness_decision"),
            (self.market_hours_schedule, "market_hours_schedule"),
            (self.capture_policy, "capture_policy"),
            (self.capture_configuration, "capture_configuration"),
            (self.credential_reference, "credential_reference"),
            (self.destination_reference, "destination_reference"),
            (self.software_release, "software_release"),
            (self.previous_attempt_history_head, "previous_attempt_history_head"),
        ):
            if type(value) is not ArtifactEvidence:
                raise CaptureAttemptAuthorityError(f"{label} evidence is invalid")
        _policy(self.capture_policy_version, "capture_policy_version")
        _policy(self.credential_reference_version, "credential_reference_version")
        _policy(self.allocation_policy_version, "allocation_policy_version")
        if type(self.target_session) is not TradingSession:
            raise CaptureAttemptAuthorityError("target_session is invalid")
        request_at = _utc(self.request_timestamp_utc, "request_timestamp_utc")
        observed_at = _utc(self.observed_allocation_at, "observed_allocation_at")
        if observed_at < request_at:
            raise CaptureAttemptAuthorityError(
                "allocation timestamp precedes request timestamp"
            )
        object.__setattr__(self, "request_timestamp_utc", request_at)
        object.__setattr__(self, "observed_allocation_at", observed_at)
        symbols = _symbols(self.symbols)
        if (
            self.timeframe is not Timeframe.DAY_1
            or self.adjustment is not AdjustmentType.RAW
        ):
            raise CaptureAttemptAuthorityError(
                "allocation timeframe or adjustment is unsupported"
            )
        if (
            type(self.provider) is not ProviderDescriptor
            or self.provider.feed != self.feed
        ):
            raise CaptureAttemptAuthorityError(
                "allocation provider/feed is inconsistent"
            )
        _text(self.feed, "feed")
        if type(self.currency) is not str or not re.fullmatch(
            r"[A-Z]{3}", self.currency
        ):
            raise CaptureAttemptAuthorityError("currency is invalid")
        if (
            self.allocation_classification
            is not CaptureAllocationClassification.CAPTURE_ONLY_AUTHORIZED
        ):
            raise CaptureAttemptAuthorityError(
                "allocation classification is unsupported"
            )
        if self.provider_call_budget != 1:
            raise CaptureAttemptAuthorityError("provider_call_budget must be 1")
        expected_attempt = derive_scheduled_capture_attempt_id(
            self.scheduled_session_id,
            self.attempt_ordinal,
            symbols,
            self.timeframe,
            self.adjustment,
            self.provider,
            self.feed,
            self.currency,
            self.capture_policy_version,
            self.capture_configuration,
        )
        if self.attempt_id != expected_attempt:
            raise CaptureAttemptAuthorityError(
                "attempt_id does not match scheduled identity"
            )
        expected = derive_capture_attempt_allocation_id(self)
        if self.allocation_record_id != expected:
            raise CaptureAttemptAuthorityError(
                "allocation_record_id does not match canonical material"
            )
        object.__setattr__(self, "symbols", symbols)


def derive_capture_attempt_allocation_id(
    record: CaptureAttemptAllocationRecord,
) -> UUID:
    if type(record) is not CaptureAttemptAllocationRecord:
        raise TypeError("record must be CaptureAttemptAllocationRecord")
    return _id(
        CAPTURE_ATTEMPT_ALLOCATION_NAMESPACE,
        (
            CAPTURE_ATTEMPT_ALLOCATION_MATERIAL_VERSION,
            str(record.attempt_id),
            str(record.attempt_ordinal),
            str(record.scheduled_session_id),
            str(record.scheduled_launch_id),
            str(record.authority_epoch_id),
            str(record.head_record.authority_epoch_id),
            *_evidence_parts(record.head_record.record),
            str(record.head_record.generation),
            str(record.verified_lineage_evidence_id),
            *_evidence_parts(record.terminal_checkpoint.checkpoint),
            str(record.terminal_checkpoint.sequence),
            canonical_timestamp(record.terminal_checkpoint.as_of),
            *_evidence_parts(record.readiness_decision),
            *_evidence_parts(record.market_hours_schedule),
            *_evidence_parts(record.capture_policy),
            record.capture_policy_version,
            *_evidence_parts(record.capture_configuration),
            str(record.snapshot_capture_request_id),
            record.target_session.session_date.isoformat(),
            canonical_timestamp(record.request_timestamp_utc),
            str(len(record.symbols)),
            *(str(symbol) for symbol in record.symbols),
            record.timeframe.value,
            record.adjustment.value,
            record.provider.provider_id,
            str(record.provider.adapter_version),
            record.provider.operation,
            record.provider.feed,
            record.feed,
            record.currency,
            *_evidence_parts(record.credential_reference),
            record.credential_reference_version,
            *_evidence_parts(record.destination_reference),
            *_evidence_parts(record.software_release),
            canonical_timestamp(record.observed_allocation_at),
            *_evidence_parts(record.previous_attempt_history_head),
            record.allocation_classification.value,
            str(record.provider_call_budget),
            record.allocation_policy_version,
        ),
    )


def create_capture_attempt_allocation(
    **values: object,
) -> CaptureAttemptAllocationRecord:
    """Create an allocation and derive its deterministic record identity."""
    names = tuple(field.name for field in fields(CaptureAttemptAllocationRecord))
    supplied = dict(values)
    supplied.setdefault("schema_version", CAPTURE_ATTEMPT_ALLOCATION_SCHEMA_VERSION)
    supplied.setdefault("allocation_record_id", UUID(int=0))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing allocation fields: {', '.join(missing)}")
    return _build_with_derived_id(
        CaptureAttemptAllocationRecord,
        tuple(supplied[name] for name in names),
        "allocation_record_id",
        derive_capture_attempt_allocation_id,
    )  # type: ignore[return-value]


def reconcile_allocation_with_readiness(
    allocation: CaptureAttemptAllocationRecord,
    decision: ScheduledCaptureReadinessDecision,
) -> None:
    """Require one allocation to be authorized by the exact existing decision."""
    if (
        type(allocation) is not CaptureAttemptAllocationRecord
        or type(decision) is not ScheduledCaptureReadinessDecision
    ):
        raise CaptureAttemptAuthorityError(
            "allocation and readiness decision types are invalid"
        )
    if (
        not decision.provider_invocation_permitted
        or decision.readiness_classification
        is not ScheduledReadinessClassification.READY
        or decision.next_eligible_action
        is not NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED
        or decision.capture_attempt_ordinal != allocation.attempt_ordinal
        or decision.capture_attempt_id != allocation.attempt_id
        or decision.scheduled_session_id != allocation.scheduled_session_id
        or decision.scheduled_launch_id != allocation.scheduled_launch_id
        or decision.authority_epoch_id != allocation.authority_epoch_id
        or decision.head_record != allocation.head_record
        or decision.terminal_checkpoint != allocation.terminal_checkpoint
        or decision.market_hours_schedule != allocation.market_hours_schedule
        or decision.capture_policy != allocation.capture_policy
        or allocation.readiness_decision.artifact_id != decision.decision_id
    ):
        raise CaptureAttemptAuthorityError(
            "allocation is not authorized by exact READY decision"
        )


@dataclass(frozen=True, slots=True)
class AttemptHistoryHeadRecord:
    schema_version: int
    history_head_record_id: UUID
    scheduled_session_id: UUID
    authority_epoch_id: UUID
    generation: int
    predecessor: ArtifactEvidence | None
    latest_allocation: ArtifactEvidence | None
    latest_terminal: ArtifactEvidence | None
    latest_zero_call_proof: ArtifactEvidence | None
    latest_recovery: ArtifactEvidence | None
    state: AttemptHistoryState
    next_attempt_ordinal: int
    advancement_cause: AttemptHistoryCause
    policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != ATTEMPT_HISTORY_HEAD_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError("history-head schema_version must be 1")
        _uuid(self.history_head_record_id, "history_head_record_id")
        _uuid(self.scheduled_session_id, "scheduled_session_id")
        _uuid(self.authority_epoch_id, "authority_epoch_id")
        _nonnegative(self.generation, "generation")
        for value, label in (
            (self.predecessor, "predecessor"),
            (self.latest_allocation, "latest_allocation"),
            (self.latest_terminal, "latest_terminal"),
            (self.latest_zero_call_proof, "latest_zero_call_proof"),
            (self.latest_recovery, "latest_recovery"),
        ):
            if value is not None and type(value) is not ArtifactEvidence:
                raise CaptureAttemptAuthorityError(f"{label} evidence is invalid")
        if (
            type(self.state) is not AttemptHistoryState
            or type(self.advancement_cause) is not AttemptHistoryCause
        ):
            raise CaptureAttemptAuthorityError("history state or cause is invalid")
        _nonnegative(self.next_attempt_ordinal, "next_attempt_ordinal")
        _policy(self.policy_version, "policy_version")
        if self.generation == 0:
            if (
                self.predecessor is not None
                or any(
                    value is not None
                    for value in (
                        self.latest_allocation,
                        self.latest_terminal,
                        self.latest_zero_call_proof,
                        self.latest_recovery,
                    )
                )
                or self.state is not AttemptHistoryState.EMPTY
                or self.next_attempt_ordinal != 0
                or self.advancement_cause is not AttemptHistoryCause.GENESIS
            ):
                raise CaptureAttemptAuthorityError("invalid genesis history head")
        elif (
            self.predecessor is None
            or self.state is AttemptHistoryState.EMPTY
            or self.advancement_cause is AttemptHistoryCause.GENESIS
        ):
            raise CaptureAttemptAuthorityError("invalid non-genesis history head")
        if (
            self.state is AttemptHistoryState.ALLOCATED_NOT_LAUNCHED
            and self.latest_allocation is None
        ):
            raise CaptureAttemptAuthorityError(
                "allocated state requires allocation evidence"
            )
        if (
            self.state
            in {
                AttemptHistoryState.LAUNCH_MAY_HAVE_OCCURRED,
                AttemptHistoryState.TERMINAL_SELECTED,
                AttemptHistoryState.RECOVERY_REQUIRED,
                AttemptHistoryState.SUCCESS_SELECTED,
            }
            and self.latest_allocation is None
        ):
            raise CaptureAttemptAuthorityError(
                "nonempty state requires allocation evidence"
            )
        if (
            self.state
            in {
                AttemptHistoryState.TERMINAL_SELECTED,
                AttemptHistoryState.SUCCESS_SELECTED,
            }
            and self.latest_terminal is None
        ):
            raise CaptureAttemptAuthorityError(
                "terminal-selected state requires terminal evidence"
            )
        if (
            self.state is AttemptHistoryState.RECOVERY_REQUIRED
            and self.latest_recovery is None
        ):
            raise CaptureAttemptAuthorityError(
                "recovery-required state requires recovery evidence"
            )
        expected = derive_attempt_history_head_id(self)
        if self.history_head_record_id != expected:
            raise CaptureAttemptAuthorityError(
                "history-head ID does not match canonical material"
            )


def derive_attempt_history_head_id(record: AttemptHistoryHeadRecord) -> UUID:
    if type(record) is not AttemptHistoryHeadRecord:
        raise TypeError("record must be AttemptHistoryHeadRecord")
    parts = [
        ATTEMPT_HISTORY_HEAD_MATERIAL_VERSION,
        str(record.scheduled_session_id),
        str(record.authority_epoch_id),
        str(record.generation),
        "NONE" if record.predecessor is None else "PRESENT",
    ]
    if record.predecessor is not None:
        parts.extend(_evidence_parts(record.predecessor))
    for value in (
        record.latest_allocation,
        record.latest_terminal,
        record.latest_zero_call_proof,
        record.latest_recovery,
    ):
        parts.append("NONE" if value is None else "PRESENT")
        if value is not None:
            parts.extend(_evidence_parts(value))
    parts.extend(
        (
            record.state.value,
            str(record.next_attempt_ordinal),
            record.advancement_cause.value,
            record.policy_version,
        )
    )
    return _id(ATTEMPT_HISTORY_HEAD_NAMESPACE, tuple(parts))


@dataclass(frozen=True, slots=True)
class CurrentAttemptHistoryReference:
    schema_version: int
    scheduled_session_id: UUID
    authority_epoch_id: UUID
    generation: int
    head_record: ArtifactEvidence

    def __post_init__(self) -> None:
        if self.schema_version != CURRENT_ATTEMPT_HISTORY_REFERENCE_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError(
                "history pointer schema_version must be 1"
            )
        _uuid(self.scheduled_session_id, "scheduled_session_id")
        _uuid(self.authority_epoch_id, "authority_epoch_id")
        _nonnegative(self.generation, "generation")
        if type(self.head_record) is not ArtifactEvidence:
            raise CaptureAttemptAuthorityError(
                "history pointer head evidence is invalid"
            )


@dataclass(frozen=True, slots=True)
class CaptureAttemptTerminalRecordV2:
    schema_version: int
    terminal_record_id: UUID
    allocation: ArtifactEvidence
    attempt_id: UUID
    attempt_ordinal: int
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    child_request: ArtifactEvidence | None
    child_launch: ArtifactEvidence | None
    resume_authorization: ArtifactEvidence | None
    credential_access: ArtifactEvidence | None
    child_result: ArtifactEvidence | None
    provider_call_disposition: ProviderCallDisposition
    completed_at: datetime
    classification: CaptureAttemptTerminalClassification
    diagnostics: tuple[str, ...]
    native_child_exit_code: int | None
    timeout_termination: ArtifactEvidence | None
    snapshot: ArtifactEvidence | None
    recovery_candidate: ArtifactEvidence | None
    snapshot_verification: SnapshotTerminalVerification
    secret_cleanup: SecretCleanupResult
    terminal_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != CAPTURE_ATTEMPT_TERMINAL_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError("terminal schema_version must be 2")
        for value, label in (
            (self.terminal_record_id, "terminal_record_id"),
            (self.attempt_id, "attempt_id"),
            (self.scheduled_session_id, "scheduled_session_id"),
            (self.scheduled_launch_id, "scheduled_launch_id"),
        ):
            _uuid(value, label)
        if type(self.allocation) is not ArtifactEvidence:
            raise CaptureAttemptAuthorityError(
                "terminal allocation evidence is invalid"
            )
        _nonnegative(self.attempt_ordinal, "attempt_ordinal")
        for value, label in (
            (self.child_request, "child_request"),
            (self.child_launch, "child_launch"),
            (self.resume_authorization, "resume_authorization"),
            (self.credential_access, "credential_access"),
            (self.child_result, "child_result"),
            (self.timeout_termination, "timeout_termination"),
            (self.snapshot, "snapshot"),
            (self.recovery_candidate, "recovery_candidate"),
        ):
            if value is not None and type(value) is not ArtifactEvidence:
                raise CaptureAttemptAuthorityError(f"{label} evidence is invalid")
        if type(self.provider_call_disposition) is not ProviderCallDisposition:
            raise CaptureAttemptAuthorityError("provider call disposition is invalid")
        completed = _utc(self.completed_at, "completed_at")
        _policy(self.terminal_policy_version, "terminal_policy_version")
        diagnostics = tuple(self.diagnostics)
        if (
            len(diagnostics) > MAX_CAPTURE_ATTEMPT_ITEMS
            or any(
                type(item) is not str or _TEXT.fullmatch(item) is None
                for item in diagnostics
            )
            or len(set(diagnostics)) != len(diagnostics)
        ):
            raise CaptureAttemptAuthorityError("terminal diagnostics are invalid")
        if self.native_child_exit_code is not None:
            if (
                type(self.native_child_exit_code) is not int
                or not -(1 << 31) <= self.native_child_exit_code <= (1 << 31) - 1
            ):
                raise CaptureAttemptAuthorityError("native child exit code is invalid")
        if type(self.classification) is not CaptureAttemptTerminalClassification:
            raise CaptureAttemptAuthorityError("terminal classification is invalid")
        if (
            any(
                value is not None
                for value in (
                    self.child_launch,
                    self.resume_authorization,
                    self.credential_access,
                    self.child_result,
                )
            )
            and self.child_request is None
        ):
            raise CaptureAttemptAuthorityError(
                "child evidence requires child request evidence"
            )
        if self.resume_authorization is not None and self.child_launch is None:
            raise CaptureAttemptAuthorityError(
                "resume evidence requires child launch evidence"
            )
        if self.child_result is not None and self.child_launch is None:
            raise CaptureAttemptAuthorityError(
                "child result requires child launch evidence"
            )
        if (
            type(self.snapshot_verification) is not SnapshotTerminalVerification
            or type(self.secret_cleanup) is not SecretCleanupResult
        ):
            raise CaptureAttemptAuthorityError("terminal result fields are invalid")
        if self.classification is CaptureAttemptTerminalClassification.SUCCEEDED:
            if (
                self.snapshot is None
                or self.snapshot_verification is not SnapshotTerminalVerification.PASS
                or self.provider_call_disposition
                is not ProviderCallDisposition.RESPONSE_CONFIRMED
            ):
                raise CaptureAttemptAuthorityError(
                    "SUCCEEDED requires verified response and snapshot"
                )
        else:
            if (
                self.snapshot is not None
                or self.snapshot_verification is SnapshotTerminalVerification.PASS
            ):
                raise CaptureAttemptAuthorityError(
                    "failed terminal cannot claim accepted snapshot"
                )
        if (
            self.classification
            in {
                CaptureAttemptTerminalClassification.TIMEOUT,
                CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH,
            }
            and self.provider_call_disposition is ProviderCallDisposition.NOT_STARTED
        ):
            raise CaptureAttemptAuthorityError(
                "ambiguous terminal cannot claim NOT_STARTED"
            )
        if (
            self.classification is CaptureAttemptTerminalClassification.OUTPUT_FAILED
            and self.snapshot is not None
        ):
            raise CaptureAttemptAuthorityError(
                "OUTPUT_FAILED cannot claim accepted snapshot"
            )
        if (
            self.classification is CaptureAttemptTerminalClassification.OUTPUT_FAILED
            and self.recovery_candidate is None
        ):
            raise CaptureAttemptAuthorityError(
                "OUTPUT_FAILED requires recovery candidate evidence"
            )
        expected = derive_capture_attempt_terminal_id(self)
        if self.terminal_record_id != expected:
            raise CaptureAttemptAuthorityError(
                "terminal_record_id does not match canonical material"
            )
        object.__setattr__(self, "completed_at", completed)
        object.__setattr__(self, "diagnostics", diagnostics)


def derive_capture_attempt_terminal_id(record: CaptureAttemptTerminalRecordV2) -> UUID:
    if type(record) is not CaptureAttemptTerminalRecordV2:
        raise TypeError("record must be CaptureAttemptTerminalRecordV2")
    parts = [
        CAPTURE_ATTEMPT_TERMINAL_MATERIAL_VERSION,
        *_evidence_parts(record.allocation),
        str(record.attempt_id),
        str(record.attempt_ordinal),
        str(record.scheduled_session_id),
        str(record.scheduled_launch_id),
    ]
    for value in (
        record.child_request,
        record.child_launch,
        record.resume_authorization,
        record.credential_access,
        record.child_result,
        record.timeout_termination,
        record.snapshot,
        record.recovery_candidate,
    ):
        parts.append("NONE" if value is None else "PRESENT")
        if value is not None:
            parts.extend(_evidence_parts(value))
    parts.extend(
        (
            record.provider_call_disposition.value,
            canonical_timestamp(record.completed_at),
            record.classification.value,
            str(len(record.diagnostics)),
            *record.diagnostics,
            "NONE"
            if record.native_child_exit_code is None
            else str(record.native_child_exit_code),
            record.snapshot_verification.value,
            record.secret_cleanup.value,
            record.terminal_policy_version,
        )
    )
    return _id(CAPTURE_ATTEMPT_TERMINAL_NAMESPACE, tuple(parts))


def create_capture_attempt_terminal_v2(
    **values: object,
) -> CaptureAttemptTerminalRecordV2:
    """Create schema-2 terminal evidence with a derived terminal ID."""
    names = tuple(field.name for field in fields(CaptureAttemptTerminalRecordV2))
    supplied = dict(values)
    supplied.setdefault("schema_version", CAPTURE_ATTEMPT_TERMINAL_SCHEMA_VERSION)
    supplied.setdefault("terminal_record_id", UUID(int=0))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing terminal fields: {', '.join(missing)}")
    return _build_with_derived_id(
        CaptureAttemptTerminalRecordV2,
        tuple(supplied[name] for name in names),
        "terminal_record_id",
        derive_capture_attempt_terminal_id,
    )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ZeroProviderCallProof:
    schema_version: int
    proof_id: UUID
    allocation: ArtifactEvidence
    attempt_id: UUID
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    child_request: ArtifactEvidence | None
    process_creation: ArtifactEvidence | None
    child_resume: ArtifactEvidence | None
    provider_adapter_stage: ArtifactEvidence | None
    transport_entry: ArtifactEvidence | None
    process_exit_or_termination: ArtifactEvidence | None
    classification: ZeroProviderCallProofClassification
    diagnostics: tuple[str, ...]
    proof_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != ZERO_PROVIDER_CALL_PROOF_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError(
                "zero-call proof schema_version must be 1"
            )
        for value, label in (
            (self.proof_id, "proof_id"),
            (self.attempt_id, "attempt_id"),
            (self.scheduled_session_id, "scheduled_session_id"),
            (self.scheduled_launch_id, "scheduled_launch_id"),
        ):
            _uuid(value, label)
        if type(self.allocation) is not ArtifactEvidence:
            raise CaptureAttemptAuthorityError(
                "zero-call allocation evidence is invalid"
            )
        evidence = (
            self.child_request,
            self.process_creation,
            self.child_resume,
            self.provider_adapter_stage,
            self.transport_entry,
            self.process_exit_or_termination,
        )
        if any(
            value is not None and type(value) is not ArtifactEvidence
            for value in evidence
        ):
            raise CaptureAttemptAuthorityError("zero-call evidence is invalid")
        if type(self.classification) is not ZeroProviderCallProofClassification:
            raise CaptureAttemptAuthorityError(
                "zero-call proof classification is invalid"
            )
        _diagnostics(self.diagnostics, "zero-call diagnostics")
        _policy(self.proof_policy_version, "proof_policy_version")
        if self.classification is ZeroProviderCallProofClassification.CHILD_NOT_CREATED:
            if any(value is not None for value in evidence):
                raise CaptureAttemptAuthorityError(
                    "CHILD_NOT_CREATED cannot include child evidence"
                )
        elif (
            self.classification
            is ZeroProviderCallProofClassification.CHILD_CREATED_NEVER_RESUMED
        ):
            if (
                self.child_request is None
                or self.process_creation is None
                or self.child_resume is not None
                or self.provider_adapter_stage is not None
                or self.transport_entry is not None
                or self.process_exit_or_termination is None
            ):
                raise CaptureAttemptAuthorityError(
                    "CHILD_CREATED_NEVER_RESUMED evidence is incomplete"
                )
        elif (
            self.classification
            is ZeroProviderCallProofClassification.CHILD_EXITED_BEFORE_PROVIDER_ADAPTER
        ):
            if (
                self.child_request is None
                or self.process_creation is None
                or self.child_resume is None
                or self.provider_adapter_stage is not None
                or self.transport_entry is not None
                or self.process_exit_or_termination is None
            ):
                raise CaptureAttemptAuthorityError(
                    "CHILD_EXITED_BEFORE_PROVIDER_ADAPTER evidence is incomplete"
                )
        elif (
            self.classification
            is ZeroProviderCallProofClassification.PROVIDER_ADAPTER_NOT_ENTERED
        ):
            if (
                self.child_request is None
                or self.process_creation is None
                or self.child_resume is None
                or self.provider_adapter_stage is None
                or self.transport_entry is not None
                or self.process_exit_or_termination is None
            ):
                raise CaptureAttemptAuthorityError(
                    "PROVIDER_ADAPTER_NOT_ENTERED evidence is incomplete"
                )
        elif (
            self.classification
            is ZeroProviderCallProofClassification.TRANSPORT_NOT_ENTERED
        ):
            if (
                self.child_request is None
                or self.process_creation is None
                or self.child_resume is None
                or self.provider_adapter_stage is None
                or self.transport_entry is None
                or self.process_exit_or_termination is None
            ):
                raise CaptureAttemptAuthorityError(
                    "TRANSPORT_NOT_ENTERED evidence is incomplete"
                )
        expected = derive_zero_provider_call_proof_id(self)
        if self.proof_id != expected:
            raise CaptureAttemptAuthorityError(
                "zero-call proof ID does not match canonical material"
            )


def derive_zero_provider_call_proof_id(proof: ZeroProviderCallProof) -> UUID:
    if type(proof) is not ZeroProviderCallProof:
        raise TypeError("proof must be ZeroProviderCallProof")
    parts = [
        ZERO_PROVIDER_CALL_PROOF_MATERIAL_VERSION,
        *_evidence_parts(proof.allocation),
        str(proof.attempt_id),
        str(proof.scheduled_session_id),
        str(proof.scheduled_launch_id),
    ]
    for value in (
        proof.child_request,
        proof.process_creation,
        proof.child_resume,
        proof.provider_adapter_stage,
        proof.transport_entry,
        proof.process_exit_or_termination,
    ):
        parts.append("NONE" if value is None else "PRESENT")
        if value is not None:
            parts.extend(_evidence_parts(value))
    parts.extend(
        (
            proof.classification.value,
            str(len(proof.diagnostics)),
            *proof.diagnostics,
            proof.proof_policy_version,
        )
    )
    return _id(ZERO_PROVIDER_CALL_PROOF_NAMESPACE, tuple(parts))


def create_zero_provider_call_proof(**values: object) -> ZeroProviderCallProof:
    """Create zero-call evidence with a derived proof identity."""
    names = tuple(field.name for field in fields(ZeroProviderCallProof))
    supplied = dict(values)
    supplied.setdefault("schema_version", ZERO_PROVIDER_CALL_PROOF_SCHEMA_VERSION)
    supplied.setdefault("proof_id", UUID(int=0))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing zero-call proof fields: {', '.join(missing)}")
    return _build_with_derived_id(
        ZeroProviderCallProof,
        tuple(supplied[name] for name in names),
        "proof_id",
        derive_zero_provider_call_proof_id,
    )  # type: ignore[return-value]


def verify_zero_provider_call_proof(proof: ZeroProviderCallProof) -> None:
    """Validate structural evidence; no absence claim is inferred."""
    if type(proof) is not ZeroProviderCallProof:
        raise CaptureAttemptAuthorityError("proof must be ZeroProviderCallProof")
    if (
        proof.classification is ZeroProviderCallProofClassification.CHILD_NOT_CREATED
        and proof.child_request is not None
    ):
        raise CaptureAttemptAuthorityError(
            "child request evidence contradicts CHILD_NOT_CREATED"
        )


@dataclass(frozen=True, slots=True)
class ManualCaptureAttemptRecoveryRecord:
    schema_version: int
    recovery_record_id: UUID
    history_head: ArtifactEvidence
    allocation: ArtifactEvidence
    zero_call_proof: ArtifactEvidence | None
    terminal: ArtifactEvidence | None
    snapshot_candidate: ArtifactEvidence | None
    operator_approval: ArtifactEvidence
    action: ManualCaptureAttemptRecoveryAction
    resulting_state: AttemptHistoryState
    recovery_policy_version: str

    def __post_init__(self) -> None:
        if self.schema_version != MANUAL_CAPTURE_RECOVERY_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError("recovery schema_version must be 1")
        for value, label in (
            (self.history_head, "history_head"),
            (self.allocation, "allocation"),
            (self.operator_approval, "operator_approval"),
        ):
            if type(value) is not ArtifactEvidence:
                raise CaptureAttemptAuthorityError(f"{label} evidence is invalid")
        for value, label in (
            (self.zero_call_proof, "zero_call_proof"),
            (self.terminal, "terminal"),
            (self.snapshot_candidate, "snapshot_candidate"),
        ):
            if value is not None and type(value) is not ArtifactEvidence:
                raise CaptureAttemptAuthorityError(f"{label} evidence is invalid")
        _uuid(self.recovery_record_id, "recovery_record_id")
        if (
            type(self.action) is not ManualCaptureAttemptRecoveryAction
            or type(self.resulting_state) is not AttemptHistoryState
        ):
            raise CaptureAttemptAuthorityError("recovery action or state is invalid")
        continuation_action = _recovery_action(
            "CONTINUE_ALLOCATED_ATTEMPT_WITH_ZERO_CALL_PROOF"
        )
        if self.action is continuation_action:
            if (
                self.zero_call_proof is None
                or self.resulting_state
                is not AttemptHistoryState.ALLOCATED_NOT_LAUNCHED
            ):
                raise CaptureAttemptAuthorityError(
                    "continuation requires zero-call proof"
                )
        if (
            self.action is ManualCaptureAttemptRecoveryAction.SELECT_EXISTING_TERMINAL
            and (
                self.terminal is None
                or self.resulting_state is not AttemptHistoryState.TERMINAL_SELECTED
            )
        ):
            raise CaptureAttemptAuthorityError(
                "terminal selection requires terminal evidence"
            )
        if (
            self.action
            is ManualCaptureAttemptRecoveryAction.RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS
            and (
                self.snapshot_candidate is None
                or self.resulting_state is not AttemptHistoryState.SUCCESS_SELECTED
            )
        ):
            raise CaptureAttemptAuthorityError(
                "snapshot recovery requires candidate evidence"
            )
        ambiguous_action = _recovery_action(
            "MARK_ATTEMPT_AMBIGUOUS_AND_REQUIRE_NEW_REVIEW"
        )
        if (
            self.action is ambiguous_action
            and self.resulting_state is not AttemptHistoryState.RECOVERY_REQUIRED
        ):
            raise CaptureAttemptAuthorityError("ambiguous recovery must require review")
        if (
            self.action
            is ManualCaptureAttemptRecoveryAction.CLOSE_SESSION_WITHOUT_CAPTURE
            and self.resulting_state is not AttemptHistoryState.SESSION_CLOSED
        ):
            raise CaptureAttemptAuthorityError(
                "close-session recovery must close the session"
            )
        _policy(self.recovery_policy_version, "recovery_policy_version")
        expected = derive_manual_capture_attempt_recovery_id(self)
        if self.recovery_record_id != expected:
            raise CaptureAttemptAuthorityError(
                "recovery_record_id does not match canonical material"
            )


def derive_manual_capture_attempt_recovery_id(
    record: ManualCaptureAttemptRecoveryRecord,
) -> UUID:
    if type(record) is not ManualCaptureAttemptRecoveryRecord:
        raise TypeError("record must be ManualCaptureAttemptRecoveryRecord")
    parts = [
        MANUAL_CAPTURE_RECOVERY_MATERIAL_VERSION,
        *_evidence_parts(record.history_head),
        *_evidence_parts(record.allocation),
    ]
    for value in (record.zero_call_proof, record.terminal, record.snapshot_candidate):
        parts.append("NONE" if value is None else "PRESENT")
        if value is not None:
            parts.extend(_evidence_parts(value))
    parts.extend(
        (
            *_evidence_parts(record.operator_approval),
            record.action.value,
            record.resulting_state.value,
            record.recovery_policy_version,
        )
    )
    return _id(MANUAL_CAPTURE_RECOVERY_NAMESPACE, tuple(parts))


def create_manual_capture_attempt_recovery(
    **values: object,
) -> ManualCaptureAttemptRecoveryRecord:
    """Create operator recovery evidence with a derived record identity."""
    names = tuple(field.name for field in fields(ManualCaptureAttemptRecoveryRecord))
    supplied = dict(values)
    supplied.setdefault("schema_version", MANUAL_CAPTURE_RECOVERY_SCHEMA_VERSION)
    supplied.setdefault("recovery_record_id", UUID(int=0))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing recovery fields: {', '.join(missing)}")
    if type(supplied["operator_approval"]) is not ArtifactEvidence:
        raise CaptureAttemptAuthorityError("operator approval evidence is invalid")
    return _build_with_derived_id(
        ManualCaptureAttemptRecoveryRecord,
        tuple(supplied[name] for name in names),
        "recovery_record_id",
        derive_manual_capture_attempt_recovery_id,
    )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class CaptureTerminalSelectionRecord:
    schema_version: int
    selection_record_id: UUID
    scheduled_session_id: UUID
    allocation: ArtifactEvidence
    terminal: ArtifactEvidence
    snapshot: ArtifactEvidence
    selection_policy_version: str
    result: str

    def __post_init__(self) -> None:
        if self.schema_version != CAPTURE_TERMINAL_SELECTION_SCHEMA_VERSION:
            raise CaptureAttemptAuthorityError("selection schema_version must be 1")
        _uuid(self.selection_record_id, "selection_record_id")
        _uuid(self.scheduled_session_id, "scheduled_session_id")
        for value, label in (
            (self.allocation, "allocation"),
            (self.terminal, "terminal"),
            (self.snapshot, "snapshot"),
        ):
            if type(value) is not ArtifactEvidence:
                raise CaptureAttemptAuthorityError(
                    f"selection {label} evidence is invalid"
                )
        _policy(self.selection_policy_version, "selection_policy_version")
        if self.result != "SUCCESS_SELECTED":
            raise CaptureAttemptAuthorityError("selection result is unsupported")
        expected = derive_capture_terminal_selection_id(self)
        if self.selection_record_id != expected:
            raise CaptureAttemptAuthorityError(
                "selection_record_id does not match canonical material"
            )


def derive_capture_terminal_selection_id(
    record: CaptureTerminalSelectionRecord,
) -> UUID:
    if type(record) is not CaptureTerminalSelectionRecord:
        raise TypeError("record must be CaptureTerminalSelectionRecord")
    return _id(
        CAPTURE_TERMINAL_SELECTION_NAMESPACE,
        (
            CAPTURE_TERMINAL_SELECTION_MATERIAL_VERSION,
            str(record.scheduled_session_id),
            *_evidence_parts(record.allocation),
            *_evidence_parts(record.terminal),
            *_evidence_parts(record.snapshot),
            record.selection_policy_version,
            record.result,
        ),
    )


def create_capture_terminal_selection(
    **values: object,
) -> CaptureTerminalSelectionRecord:
    names = tuple(field.name for field in fields(CaptureTerminalSelectionRecord))
    supplied = dict(values)
    supplied.setdefault("schema_version", CAPTURE_TERMINAL_SELECTION_SCHEMA_VERSION)
    supplied.setdefault("selection_record_id", UUID(int=0))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing selection fields: {', '.join(missing)}")
    return _build_with_derived_id(
        CaptureTerminalSelectionRecord,
        tuple(supplied[name] for name in names),
        "selection_record_id",
        derive_capture_terminal_selection_id,
    )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class CaptureRetryPolicyInputs:
    history_state: AttemptHistoryState
    terminal_classification: CaptureAttemptTerminalClassification | None
    provider_call_disposition: ProviderCallDisposition | None
    zero_call_proof_verified: bool
    observed_at: datetime
    deadline: datetime
    attempts_remaining: int
    backoff_until: datetime | None
    credential_reference_changed: bool
    manual_approval: ArtifactEvidence | None


@dataclass(frozen=True, slots=True)
class CaptureRetryPolicyDecision:
    classification: CaptureRetryClassification
    diagnostic: str


def classify_capture_retry_policy(
    inputs: CaptureRetryPolicyInputs,
) -> CaptureRetryPolicyDecision:
    """Classify policy only; never changes terminal facts or performs work."""
    if type(inputs) is not CaptureRetryPolicyInputs:
        raise TypeError("inputs must be CaptureRetryPolicyInputs")
    observed = _utc(inputs.observed_at, "observed_at")
    deadline = _utc(inputs.deadline, "deadline")
    if type(inputs.history_state) is not AttemptHistoryState:
        raise CaptureAttemptAuthorityError("history_state is invalid")
    if (
        inputs.terminal_classification is not None
        and type(inputs.terminal_classification)
        is not CaptureAttemptTerminalClassification
    ):
        raise CaptureAttemptAuthorityError("terminal_classification is invalid")
    if (
        inputs.provider_call_disposition is not None
        and type(inputs.provider_call_disposition) is not ProviderCallDisposition
    ):
        raise CaptureAttemptAuthorityError("provider_call_disposition is invalid")
    if type(inputs.zero_call_proof_verified) is not bool:
        raise CaptureAttemptAuthorityError("zero_call_proof_verified is invalid")
    if type(inputs.credential_reference_changed) is not bool:
        raise CaptureAttemptAuthorityError("credential_reference_changed is invalid")
    if (
        inputs.manual_approval is not None
        and type(inputs.manual_approval) is not ArtifactEvidence
    ):
        raise CaptureAttemptAuthorityError("manual_approval is invalid")
    if inputs.attempts_remaining < 0:
        raise CaptureAttemptAuthorityError("attempts_remaining must be nonnegative")
    if observed > deadline:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.BLOCKED, "CAPTURE_WINDOW_EXPIRED"
        )
    if inputs.history_state is AttemptHistoryState.SESSION_CLOSED:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.SESSION_CLOSED, "SESSION_CLOSED"
        )
    if inputs.history_state is AttemptHistoryState.SUCCESS_SELECTED:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.SESSION_COMPLETED, "SUCCESS_SELECTED"
        )
    if inputs.attempts_remaining == 0:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.BLOCKED, "CAPTURE_ATTEMPTS_EXHAUSTED"
        )
    if inputs.history_state in {
        AttemptHistoryState.LAUNCH_MAY_HAVE_OCCURRED,
        AttemptHistoryState.RECOVERY_REQUIRED,
    }:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.MANUAL_REVIEW_REQUIRED, "AMBIGUOUS_ATTEMPT"
        )
    if inputs.history_state is AttemptHistoryState.ALLOCATED_NOT_LAUNCHED:
        if inputs.zero_call_proof_verified:
            return CaptureRetryPolicyDecision(
                CaptureRetryClassification.SAME_ATTEMPT_CONTINUATION_ALLOWED,
                "VERIFIED_ZERO_PROVIDER_CALL",
            )
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.MANUAL_REVIEW_REQUIRED,
            "ALLOCATED_ATTEMPT_REQUIRES_PROOF",
        )
    if inputs.terminal_classification is CaptureAttemptTerminalClassification.SUCCEEDED:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.SESSION_COMPLETED, "SUCCEEDED"
        )
    if (
        inputs.terminal_classification
        is CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED
    ):
        if inputs.credential_reference_changed and inputs.manual_approval is not None:
            return CaptureRetryPolicyDecision(
                CaptureRetryClassification.NEW_ATTEMPT_AFTER_BACKOFF,
                "CREDENTIAL_REFERENCE_CHANGED",
            )
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.MANUAL_REVIEW_REQUIRED,
            "AUTHENTICATION_REQUIRES_CREDENTIAL_ROTATION",
        )
    if inputs.terminal_classification in {
        CaptureAttemptTerminalClassification.TIMEOUT,
        CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH,
        CaptureAttemptTerminalClassification.CHILD_CRASHED,
    } or inputs.provider_call_disposition in {
        ProviderCallDisposition.MAY_HAVE_STARTED,
        ProviderCallDisposition.UNKNOWN,
    }:
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.MANUAL_REVIEW_REQUIRED, "AMBIGUOUS_PROVIDER_CALL"
        )
    if inputs.backoff_until is not None and observed < _utc(
        inputs.backoff_until, "backoff_until"
    ):
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.NOT_READY, "CAPTURE_BACKOFF_ACTIVE"
        )
    if (
        inputs.terminal_classification
        is CaptureAttemptTerminalClassification.PROVIDER_REJECTED
    ):
        return CaptureRetryPolicyDecision(
            CaptureRetryClassification.MANUAL_REVIEW_REQUIRED, "PROVIDER_REJECTED"
        )
    return CaptureRetryPolicyDecision(
        CaptureRetryClassification.NEW_ATTEMPT_AFTER_BACKOFF, "RETRY_ALLOWED_BY_POLICY"
    )


@dataclass(frozen=True, slots=True)
class AttemptHistoryVerificationResult:
    classification: CaptureAttemptHistoryClassification
    pointer: CurrentAttemptHistoryReference | None
    head: AttemptHistoryHeadRecord | None
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaptureAttemptHistoryFacts:
    """Pointer-selected allocation and terminal facts in chronological order."""

    verification: AttemptHistoryVerificationResult
    allocations: tuple[CaptureAttemptAllocationRecord, ...]
    terminals: tuple[CaptureAttemptTerminalRecordV2, ...]


def capture_attempt_session_root(root: Path, scheduled_session_id: UUID) -> Path:
    """Return the fixed session root without discovering any artifacts."""
    return _history_session_root(root, scheduled_session_id)


def capture_attempt_allocation_path(
    root: Path,
    scheduled_session_id: UUID,
    allocation_record_id: UUID,
) -> Path:
    """Resolve one allocation by its explicit immutable identity."""
    _uuid(allocation_record_id, "allocation_record_id")
    return (
        _history_session_root(root, scheduled_session_id)
        / "allocations"
        / _allocation_filename(allocation_record_id)
    )


def load_capture_attempt_history_facts(
    root: Path,
    scheduled_session_id: UUID,
) -> CaptureAttemptHistoryFacts:
    """Read only the pointer-selected history chain and named evidence."""
    verification = verify_capture_attempt_history(root, scheduled_session_id)
    if (
        verification.classification is not CaptureAttemptHistoryClassification.PASS
        or verification.pointer is None
        or verification.head is None
    ):
        raise CaptureAttemptAuthorityError("capture-attempt history is not verified")
    session_root = _history_session_root(root, scheduled_session_id)
    allocations_newest: list[CaptureAttemptAllocationRecord] = []
    terminals_newest: list[CaptureAttemptTerminalRecordV2] = []
    allocation_ids: set[UUID] = set()
    terminal_ids: set[UUID] = set()
    current = verification.head
    for _ in range(MAX_CAPTURE_ATTEMPT_ITEMS + 1):
        if current.latest_allocation is not None:
            evidence = current.latest_allocation
            if evidence.artifact_id not in allocation_ids:
                payload = _safe_read(
                    session_root
                    / "allocations"
                    / _allocation_filename(evidence.artifact_id)
                )
                if _artifact_evidence(evidence.artifact_id, payload) != evidence:
                    raise CaptureAttemptAuthorityError(
                        "allocation evidence changed during history read"
                    )
                allocation = parse_capture_attempt_allocation(payload)
                if allocation.scheduled_session_id != scheduled_session_id:
                    raise CaptureAttemptAuthorityError("allocation session mismatch")
                allocations_newest.append(allocation)
                allocation_ids.add(evidence.artifact_id)
        if current.latest_terminal is not None:
            evidence = current.latest_terminal
            if evidence.artifact_id not in terminal_ids:
                terminal = _read_named_terminal(session_root, evidence)
                if terminal.scheduled_session_id != scheduled_session_id:
                    raise CaptureAttemptAuthorityError("terminal session mismatch")
                terminals_newest.append(terminal)
                terminal_ids.add(evidence.artifact_id)
        if current.predecessor is None:
            break
        current = _read_named_head(session_root, current.predecessor)
    else:
        raise CaptureAttemptAuthorityError("history chain exceeds bound")
    allocations = tuple(reversed(allocations_newest))
    terminals = tuple(reversed(terminals_newest))
    if tuple(item.attempt_ordinal for item in allocations) != tuple(
        range(len(allocations))
    ):
        raise CaptureAttemptAuthorityError("attempt ordinals are not contiguous")
    if len(terminals) > len(allocations):
        raise CaptureAttemptAuthorityError("terminal history exceeds allocations")
    return CaptureAttemptHistoryFacts(verification, allocations, terminals)


def initialize_capture_attempt_history(
    root: Path,
    scheduled_session_id: UUID,
    authority_epoch_id: UUID,
    policy_version: str,
) -> AttemptHistoryHeadRecord:
    """Create or idempotently verify a generation-zero history authority."""
    _ensure_history_directories(root, scheduled_session_id)
    pointer_path = (
        _history_session_root(root, scheduled_session_id)
        / "current-attempt-history.json"
    )
    if pointer_path.exists():
        result = verify_capture_attempt_history(root, scheduled_session_id)
        if (
            result.classification is not CaptureAttemptHistoryClassification.PASS
            or result.head is None
            or result.head.generation != 0
            or result.head.authority_epoch_id != authority_epoch_id
            or result.head.policy_version != policy_version
        ):
            raise CaptureAttemptAuthorityError(
                "existing capture-attempt history is not a valid genesis"
            )
        return result.head
    genesis = _build_history_head(
        ATTEMPT_HISTORY_HEAD_SCHEMA_VERSION,
        UUID(int=0),
        scheduled_session_id,
        authority_epoch_id,
        0,
        None,
        None,
        None,
        None,
        None,
        AttemptHistoryState.EMPTY,
        0,
        AttemptHistoryCause.GENESIS,
        policy_version,
    )
    payload = serialize_attempt_history_head_record(genesis)
    evidence = _artifact_evidence(genesis.history_head_record_id, payload)
    _publish_immutable(
        _history_session_root(root, scheduled_session_id) / "history-head-records",
        _head_filename(genesis.history_head_record_id),
        payload,
        parse_attempt_history_head_record,
    )
    pointer = CurrentAttemptHistoryReference(
        CURRENT_ATTEMPT_HISTORY_REFERENCE_SCHEMA_VERSION,
        scheduled_session_id,
        authority_epoch_id,
        0,
        evidence,
    )
    _publish_exclusive(
        _history_session_root(root, scheduled_session_id)
        / "current-attempt-history.json",
        serialize_current_attempt_history_reference(pointer),
        parse_current_attempt_history_reference,
    )
    return genesis


def verify_capture_attempt_history(
    root: Path, scheduled_session_id: UUID
) -> AttemptHistoryVerificationResult:
    """Verify only the pointer-selected predecessor chain and named evidence."""
    try:
        session_root = _history_session_root(root, scheduled_session_id)
        pointer_payload = _safe_read(session_root / "current-attempt-history.json")
        pointer = parse_current_attempt_history_reference(pointer_payload)
        if pointer.scheduled_session_id != scheduled_session_id:
            raise CaptureAttemptAuthorityError("history pointer session mismatch")
        head = _read_named_head(session_root, pointer.head_record)
        if (
            head.authority_epoch_id != pointer.authority_epoch_id
            or head.generation != pointer.generation
        ):
            raise CaptureAttemptAuthorityError("history pointer/head mismatch")
        seen: set[UUID] = set()
        current = head
        for _ in range(MAX_CAPTURE_ATTEMPT_ITEMS + 1):
            if current.history_head_record_id in seen:
                raise CaptureAttemptAuthorityError("history predecessor cycle")
            seen.add(current.history_head_record_id)
            _verify_selected_state_artifacts(session_root, current)
            if current.predecessor is None:
                if current.generation != 0:
                    raise CaptureAttemptAuthorityError(
                        "history generation does not reach genesis"
                    )
                break
            predecessor = _read_named_head(session_root, current.predecessor)
            if (
                predecessor.generation + 1 != current.generation
                or predecessor.scheduled_session_id != current.scheduled_session_id
                or predecessor.authority_epoch_id != current.authority_epoch_id
            ):
                raise CaptureAttemptAuthorityError(
                    "history predecessor generation or authority mismatch"
                )
            if current.next_attempt_ordinal < predecessor.next_attempt_ordinal:
                raise CaptureAttemptAuthorityError("history ordinal regressed")
            current = predecessor
        else:
            raise CaptureAttemptAuthorityError("history chain exceeds bound")
        return AttemptHistoryVerificationResult(
            CaptureAttemptHistoryClassification.PASS, pointer, head, ()
        )
    except FileNotFoundError:
        return AttemptHistoryVerificationResult(
            CaptureAttemptHistoryClassification.BLOCKED,
            None,
            None,
            ("HISTORY_POINTER_MISSING",),
        )
    except (OSError, CaptureAttemptAuthorityError):
        return AttemptHistoryVerificationResult(
            CaptureAttemptHistoryClassification.CONFLICTING,
            None,
            None,
            ("HISTORY_VERIFICATION_FAILED",),
        )


def allocate_capture_attempt(
    root: Path,
    allocation: CaptureAttemptAllocationRecord,
    readiness_decision: ScheduledCaptureReadinessDecision,
    *,
    pointer_replacer: AtomicAttemptHistoryPointerReplacer | None = None,
) -> AttemptHistoryHeadRecord:
    """Publish one allocation and advance the explicit history pointer."""
    reconcile_allocation_with_readiness(allocation, readiness_decision)
    result = verify_capture_attempt_history(root, allocation.scheduled_session_id)
    if (
        result.classification is not CaptureAttemptHistoryClassification.PASS
        or result.pointer is None
        or result.head is None
    ):
        raise CaptureAttemptAuthorityError("current attempt history is not verified")
    if (
        allocation.authority_epoch_id != result.pointer.authority_epoch_id
        or allocation.previous_attempt_history_head != result.pointer.head_record
        or allocation.attempt_ordinal != result.head.next_attempt_ordinal
    ):
        raise CaptureAttemptAuthorityError(
            "allocation does not extend current attempt history"
        )
    if result.head.state not in {
        AttemptHistoryState.EMPTY,
        AttemptHistoryState.TERMINAL_SELECTED,
    }:
        raise CaptureAttemptAuthorityError(
            "allocation is not permitted from current history state"
        )
    allocation_payload = serialize_capture_attempt_allocation(allocation)
    allocation_evidence = _artifact_evidence(
        allocation.allocation_record_id, allocation_payload
    )
    session_root = _history_session_root(root, allocation.scheduled_session_id)
    _publish_immutable(
        session_root / "allocations",
        _allocation_filename(allocation.allocation_record_id),
        allocation_payload,
        parse_capture_attempt_allocation,
    )
    new_head = _build_history_head(
        ATTEMPT_HISTORY_HEAD_SCHEMA_VERSION,
        UUID(int=0),
        allocation.scheduled_session_id,
        allocation.authority_epoch_id,
        result.head.generation + 1,
        result.pointer.head_record,
        allocation_evidence,
        None,
        None,
        None,
        AttemptHistoryState.ALLOCATED_NOT_LAUNCHED,
        result.head.next_attempt_ordinal + 1,
        AttemptHistoryCause.ALLOCATION,
        allocation.allocation_policy_version,
    )
    head_payload = serialize_attempt_history_head_record(new_head)
    head_evidence = _artifact_evidence(new_head.history_head_record_id, head_payload)
    _publish_immutable(
        session_root / "history-head-records",
        _head_filename(new_head.history_head_record_id),
        head_payload,
        parse_attempt_history_head_record,
    )
    expected_pointer = serialize_current_attempt_history_reference(result.pointer)
    replacement = CurrentAttemptHistoryReference(
        1,
        allocation.scheduled_session_id,
        allocation.authority_epoch_id,
        new_head.generation,
        head_evidence,
    )
    _replace_history_pointer(
        session_root / "current-attempt-history.json",
        expected_pointer,
        serialize_current_attempt_history_reference(replacement),
        pointer_replacer,
    )
    return new_head


def publish_capture_attempt_terminal(
    root: Path,
    terminal: CaptureAttemptTerminalRecordV2,
    *,
    pointer_replacer: AtomicAttemptHistoryPointerReplacer | None = None,
) -> AttemptHistoryHeadRecord:
    result = verify_capture_attempt_history(root, terminal.scheduled_session_id)
    if (
        result.classification is not CaptureAttemptHistoryClassification.PASS
        or result.pointer is None
        or result.head is None
        or result.head.latest_allocation is None
    ):
        raise CaptureAttemptAuthorityError(
            "terminal requires verified allocated history"
        )
    if result.head.state is not AttemptHistoryState.ALLOCATED_NOT_LAUNCHED:
        raise CaptureAttemptAuthorityError(
            "terminal cannot replace an existing terminal"
        )
    if (
        terminal.allocation != result.head.latest_allocation
        or terminal.attempt_id is None
    ):
        raise CaptureAttemptAuthorityError("terminal does not bind current allocation")
    session_root = _history_session_root(root, terminal.scheduled_session_id)
    allocation_payload = _safe_read(
        session_root
        / "allocations"
        / _allocation_filename(terminal.allocation.artifact_id)
    )
    if (
        _artifact_evidence(terminal.allocation.artifact_id, allocation_payload)
        != terminal.allocation
    ):
        raise CaptureAttemptAuthorityError("terminal allocation evidence is not exact")
    allocation = parse_capture_attempt_allocation(allocation_payload)
    if (
        terminal.attempt_id != allocation.attempt_id
        or terminal.attempt_ordinal != allocation.attempt_ordinal
        or terminal.scheduled_session_id != allocation.scheduled_session_id
        or terminal.scheduled_launch_id != allocation.scheduled_launch_id
    ):
        raise CaptureAttemptAuthorityError(
            "terminal fields do not reconcile with allocation"
        )
    payload = serialize_capture_attempt_terminal_v2(terminal)
    evidence = _artifact_evidence(terminal.terminal_record_id, payload)
    _publish_immutable(
        session_root / "terminals",
        _terminal_filename(terminal.terminal_record_id),
        payload,
        parse_capture_attempt_terminal_v2,
    )
    # An ambiguous terminal is a fact that requires review, but it is not
    # itself a manual recovery record.  Keep the history in the explicit
    # launch-may-have-occurred state until an operator publishes recovery
    # evidence; RECOVERY_REQUIRED requires that immutable recovery artifact.
    new_state = (
        AttemptHistoryState.LAUNCH_MAY_HAVE_OCCURRED
        if terminal.classification
        in {
            CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH,
            CaptureAttemptTerminalClassification.TIMEOUT,
        }
        else AttemptHistoryState.TERMINAL_SELECTED
    )
    new_head = _build_history_head(
        1,
        UUID(int=0),
        terminal.scheduled_session_id,
        result.pointer.authority_epoch_id,
        result.head.generation + 1,
        result.pointer.head_record,
        result.head.latest_allocation,
        evidence,
        None,
        None,
        new_state,
        result.head.next_attempt_ordinal,
        AttemptHistoryCause.TERMINAL,
        terminal.terminal_policy_version,
    )
    head_payload = serialize_attempt_history_head_record(new_head)
    head_evidence = _artifact_evidence(new_head.history_head_record_id, head_payload)
    _publish_immutable(
        session_root / "history-head-records",
        _head_filename(new_head.history_head_record_id),
        head_payload,
        parse_attempt_history_head_record,
    )
    replacement = CurrentAttemptHistoryReference(
        1,
        terminal.scheduled_session_id,
        result.pointer.authority_epoch_id,
        new_head.generation,
        head_evidence,
    )
    _replace_history_pointer(
        session_root / "current-attempt-history.json",
        serialize_current_attempt_history_reference(result.pointer),
        serialize_current_attempt_history_reference(replacement),
        pointer_replacer,
    )
    return new_head


def publish_zero_provider_call_proof(
    root: Path, proof: ZeroProviderCallProof
) -> ArtifactEvidence:
    """Publish immutable zero-call evidence without advancing the pointer."""
    verify_zero_provider_call_proof(proof)
    result = verify_capture_attempt_history(root, proof.scheduled_session_id)
    if (
        result.classification is not CaptureAttemptHistoryClassification.PASS
        or result.head is None
        or result.head.latest_allocation != proof.allocation
    ):
        raise CaptureAttemptAuthorityError(
            "zero-call proof must bind the pointer-selected allocation"
        )
    session_root = _history_session_root(root, proof.scheduled_session_id)
    payload = serialize_zero_provider_call_proof(proof)
    _publish_immutable(
        session_root / "zero-call-proofs",
        _proof_filename(proof.proof_id),
        payload,
        parse_zero_provider_call_proof,
    )
    return _artifact_evidence(proof.proof_id, payload)


def select_capture_attempt_terminal(
    root: Path,
    scheduled_session_id: UUID,
    selection_policy_version: str,
    *,
    pointer_replacer: AtomicAttemptHistoryPointerReplacer | None = None,
) -> CaptureTerminalSelectionRecord:
    result = verify_capture_attempt_history(root, scheduled_session_id)
    if (
        result.classification is not CaptureAttemptHistoryClassification.PASS
        or result.pointer is None
        or result.head is None
        or result.head.latest_terminal is None
        or result.head.latest_allocation is None
    ):
        raise CaptureAttemptAuthorityError(
            "terminal selection requires verified terminal history"
        )
    session_root = _history_session_root(root, scheduled_session_id)
    terminal = _read_named_terminal(session_root, result.head.latest_terminal)
    if (
        terminal.classification is not CaptureAttemptTerminalClassification.SUCCEEDED
        or terminal.snapshot is None
    ):
        raise CaptureAttemptAuthorityError(
            "only a verified successful terminal can be selected"
        )
    selection = _build_selection(
        1,
        UUID(int=0),
        scheduled_session_id,
        result.head.latest_allocation,
        result.head.latest_terminal,
        terminal.snapshot,
        selection_policy_version,
        "SUCCESS_SELECTED",
    )
    selection_payload = serialize_capture_terminal_selection(selection)
    _publish_immutable(
        session_root / "terminals",
        _selection_filename(selection.selection_record_id),
        selection_payload,
        parse_capture_terminal_selection,
    )
    new_head = _build_history_head(
        1,
        UUID(int=0),
        scheduled_session_id,
        result.pointer.authority_epoch_id,
        result.head.generation + 1,
        result.pointer.head_record,
        result.head.latest_allocation,
        result.head.latest_terminal,
        None,
        None,
        AttemptHistoryState.SUCCESS_SELECTED,
        result.head.next_attempt_ordinal,
        AttemptHistoryCause.TERMINAL_SELECTION,
        selection_policy_version,
    )
    head_payload = serialize_attempt_history_head_record(new_head)
    head_evidence = _artifact_evidence(new_head.history_head_record_id, head_payload)
    _publish_immutable(
        session_root / "history-head-records",
        _head_filename(new_head.history_head_record_id),
        head_payload,
        parse_attempt_history_head_record,
    )
    replacement = CurrentAttemptHistoryReference(
        1,
        scheduled_session_id,
        result.pointer.authority_epoch_id,
        new_head.generation,
        head_evidence,
    )
    _replace_history_pointer(
        session_root / "current-attempt-history.json",
        serialize_current_attempt_history_reference(result.pointer),
        serialize_current_attempt_history_reference(replacement),
        pointer_replacer,
    )
    return selection


def apply_capture_attempt_recovery(
    root: Path,
    recovery: ManualCaptureAttemptRecoveryRecord,
    scheduled_session_id: UUID,
    *,
    pointer_replacer: AtomicAttemptHistoryPointerReplacer | None = None,
) -> AttemptHistoryHeadRecord:
    """Publish explicit provider-free recovery evidence and advance the head.

    This function never repairs a pointer or discovers artifacts.  The
    recovery record must name the exact current head and allocation selected by
    the pointer; a stale pointer therefore fails closed.
    """
    _uuid(scheduled_session_id, "scheduled_session_id")
    allocation_session = scheduled_session_id
    result = verify_capture_attempt_history(root, allocation_session)
    if (
        result.classification is not CaptureAttemptHistoryClassification.PASS
        or result.pointer is None
        or result.head is None
    ):
        raise CaptureAttemptAuthorityError("recovery requires verified history")
    if (
        recovery.history_head != result.pointer.head_record
        or recovery.allocation != result.head.latest_allocation
    ):
        raise CaptureAttemptAuthorityError(
            "recovery is not bound to current head and allocation"
        )
    if (
        recovery.resulting_state is AttemptHistoryState.SUCCESS_SELECTED
        and result.head.latest_terminal is None
    ):
        raise CaptureAttemptAuthorityError(
            "successful recovery requires an existing terminal"
        )
    if (
        recovery.action is ManualCaptureAttemptRecoveryAction.SELECT_EXISTING_TERMINAL
        and recovery.terminal != result.head.latest_terminal
    ):
        raise CaptureAttemptAuthorityError(
            "terminal recovery evidence is not the current terminal"
        )
    session_root = _history_session_root(root, allocation_session)
    if recovery.action in {
        ManualCaptureAttemptRecoveryAction.SELECT_EXISTING_TERMINAL,
        ManualCaptureAttemptRecoveryAction.RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS,
    }:
        if result.head.latest_terminal is None:
            raise CaptureAttemptAuthorityError(
                "terminal recovery requires the current terminal"
            )
        terminal = _read_named_terminal(session_root, result.head.latest_terminal)
        if (
            terminal.classification
            is not CaptureAttemptTerminalClassification.SUCCEEDED
            or terminal.snapshot is None
            or terminal.snapshot_verification is not SnapshotTerminalVerification.PASS
        ):
            raise CaptureAttemptAuthorityError(
                "terminal recovery requires a verified successful terminal"
            )
        if (
            recovery.action
            is ManualCaptureAttemptRecoveryAction.RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS
            and recovery.snapshot_candidate != terminal.snapshot
        ):
            raise CaptureAttemptAuthorityError(
                "snapshot candidate is not the committed terminal snapshot"
            )
    if recovery.zero_call_proof is not None:
        proof_payload = _safe_read(
            session_root
            / "zero-call-proofs"
            / _proof_filename(recovery.zero_call_proof.artifact_id)
        )
        if (
            _artifact_evidence(recovery.zero_call_proof.artifact_id, proof_payload)
            != recovery.zero_call_proof
        ):
            raise CaptureAttemptAuthorityError("recovery zero-call evidence mismatch")
        proof = parse_zero_provider_call_proof(proof_payload)
        if proof.allocation != recovery.allocation:
            raise CaptureAttemptAuthorityError(
                "recovery zero-call proof does not bind allocation"
            )
    payload = serialize_manual_capture_attempt_recovery(recovery)
    evidence = _artifact_evidence(recovery.recovery_record_id, payload)
    _publish_immutable(
        session_root / "recovery-records",
        _recovery_filename(recovery.recovery_record_id),
        payload,
        parse_manual_capture_attempt_recovery,
    )
    new_head = _build_history_head(
        ATTEMPT_HISTORY_HEAD_SCHEMA_VERSION,
        UUID(int=0),
        allocation_session,
        result.pointer.authority_epoch_id,
        result.head.generation + 1,
        result.pointer.head_record,
        result.head.latest_allocation,
        result.head.latest_terminal,
        recovery.zero_call_proof,
        evidence,
        recovery.resulting_state,
        result.head.next_attempt_ordinal,
        AttemptHistoryCause.MANUAL_RECOVERY,
        recovery.recovery_policy_version,
    )
    head_payload = serialize_attempt_history_head_record(new_head)
    head_evidence = _artifact_evidence(new_head.history_head_record_id, head_payload)
    _publish_immutable(
        session_root / "history-head-records",
        _head_filename(new_head.history_head_record_id),
        head_payload,
        parse_attempt_history_head_record,
    )
    replacement = CurrentAttemptHistoryReference(
        1,
        allocation_session,
        result.pointer.authority_epoch_id,
        new_head.generation,
        head_evidence,
    )
    _replace_history_pointer(
        session_root / "current-attempt-history.json",
        serialize_current_attempt_history_reference(result.pointer),
        serialize_current_attempt_history_reference(replacement),
        pointer_replacer,
    )
    return new_head


class AtomicAttemptHistoryPointerReplacer(Protocol):
    def replace(
        self,
        pointer_path: Path,
        *,
        expected_payload: bytes,
        replacement_payload: bytes,
        parent_identity: tuple[int, int],
    ) -> None: ...


class AtomicAttemptHistoryPointerReplacementError(CaptureAttemptAuthorityError):
    pass


class AtomicAttemptHistoryPointerReplacementUnavailable(
    AtomicAttemptHistoryPointerReplacementError
):
    pass


class WindowsAtomicAttemptHistoryPointerReplacer:
    """Same-directory MoveFileExW compare-and-swap for the history pointer."""

    def replace(
        self,
        pointer_path: Path,
        *,
        expected_payload: bytes,
        replacement_payload: bytes,
        parent_identity: tuple[int, int],
    ) -> None:
        if os.name != "nt":
            raise AtomicAttemptHistoryPointerReplacementUnavailable(
                "Windows pointer replacement is unavailable"
            )
        parent = pointer_path.parent
        _require_directory_identity(parent, parent_identity)
        if _safe_read(pointer_path) != expected_payload:
            raise AtomicAttemptHistoryPointerReplacementError(
                "history pointer changed before compare-and-swap"
            )
        staging = parent / ".current-attempt-history.json.staging"
        _publish_exclusive(
            staging, replacement_payload, parse_current_attempt_history_reference
        )
        try:
            if _safe_read(pointer_path) != expected_payload:
                raise AtomicAttemptHistoryPointerReplacementError(
                    "history pointer changed before replacement"
                )
            _require_directory_identity(parent, parent_identity)
            move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
            move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            move.restype = ctypes.c_int
            if not move(str(staging), str(pointer_path), 0x1 | 0x8):
                raise AtomicAttemptHistoryPointerReplacementError("MoveFileExW failed")
            if _safe_read(pointer_path) != replacement_payload:
                raise AtomicAttemptHistoryPointerReplacementError(
                    "installed pointer does not reconcile"
                )
            _require_directory_identity(parent, parent_identity)
        except Exception:
            raise


def serialize_windows_market_data_credential_reference(
    reference: WindowsMarketDataCredentialReference,
) -> bytes:
    if type(reference) is not WindowsMarketDataCredentialReference:
        raise TypeError("reference must be WindowsMarketDataCredentialReference")
    return _json_bytes(_credential_tree(reference))


def parse_windows_market_data_credential_reference(
    payload: bytes,
) -> WindowsMarketDataCredentialReference:
    root = _object(_load_json(payload), _CREDENTIAL_FIELDS, "credential reference")
    reference = WindowsMarketDataCredentialReference(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["credential_reference_id"], "credential_reference_id"),
        _enum(CredentialStoreType, root["store_type"], "store_type"),
        _string(root["owner_account_sid"], "owner_account_sid"),
        _string(root["api_key_id_target_name"], "api_key_id_target_name"),
        _string(root["api_secret_key_target_name"], "api_secret_key_target_name"),
        _string(root["credential_version"], "credential_version"),
        _enum(CredentialPersistence, root["persistence"], "persistence"),
        _string(root["provider_id"], "provider_id"),
        _enum(CredentialPurpose, root["purpose"], "purpose"),
        _string(root["permission_profile"], "permission_profile"),
        _artifact(
            root["permission_attestation_evidence"], "permission_attestation_evidence"
        ),
        _nonnegative_value(root["rotation_generation"], "rotation_generation"),
        _string(root["reference_policy_version"], "reference_policy_version"),
    )
    if serialize_windows_market_data_credential_reference(reference) != payload:
        raise CaptureAttemptArtifactSyntaxError(
            "credential reference bytes are not canonical"
        )
    return reference


def serialize_capture_attempt_allocation(
    record: CaptureAttemptAllocationRecord,
) -> bytes:
    if type(record) is not CaptureAttemptAllocationRecord:
        raise TypeError("record must be CaptureAttemptAllocationRecord")
    return _json_bytes(_allocation_tree(record))


def parse_capture_attempt_allocation(payload: bytes) -> CaptureAttemptAllocationRecord:
    root = _object(_load_json(payload), _ALLOCATION_FIELDS, "allocation")
    record = CaptureAttemptAllocationRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["allocation_record_id"], "allocation_record_id"),
        _uuid_value(root["attempt_id"], "attempt_id"),
        _nonnegative_value(root["attempt_ordinal"], "attempt_ordinal"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _uuid_value(root["authority_epoch_id"], "authority_epoch_id"),
        _head_record(root["head_record"]),
        _uuid_value(
            root["verified_lineage_evidence_id"], "verified_lineage_evidence_id"
        ),
        _terminal_checkpoint(root["terminal_checkpoint"]),
        _timestamp(root["terminal_as_of"], "terminal_as_of"),
        _artifact(root["readiness_decision"], "readiness_decision"),
        _artifact(root["market_hours_schedule"], "market_hours_schedule"),
        _artifact(root["capture_policy"], "capture_policy"),
        _string(root["capture_policy_version"], "capture_policy_version"),
        _artifact(root["capture_configuration"], "capture_configuration"),
        _uuid_value(root["snapshot_capture_request_id"], "snapshot_capture_request_id"),
        TradingSession(_date(root["target_session"], "target_session")),
        _timestamp(root["request_timestamp_utc"], "request_timestamp_utc"),
        _symbols_value(root["symbols"], "symbols"),
        _enum(Timeframe, root["timeframe"], "timeframe"),
        _enum(AdjustmentType, root["adjustment"], "adjustment"),
        _provider(root["provider"]),
        _string(root["feed"], "feed"),
        _string(root["currency"], "currency"),
        _artifact(root["credential_reference"], "credential_reference"),
        _string(root["credential_reference_version"], "credential_reference_version"),
        _artifact(root["destination_reference"], "destination_reference"),
        _artifact(root["software_release"], "software_release"),
        _timestamp(root["observed_allocation_at"], "observed_allocation_at"),
        _artifact(
            root["previous_attempt_history_head"], "previous_attempt_history_head"
        ),
        _enum(
            CaptureAllocationClassification,
            root["allocation_classification"],
            "allocation_classification",
        ),
        _integer(root["provider_call_budget"], "provider_call_budget"),
        _string(root["allocation_policy_version"], "allocation_policy_version"),
    )
    if serialize_capture_attempt_allocation(record) != payload:
        raise CaptureAttemptArtifactSyntaxError("allocation bytes are not canonical")
    return record


def serialize_attempt_history_head_record(record: AttemptHistoryHeadRecord) -> bytes:
    if type(record) is not AttemptHistoryHeadRecord:
        raise TypeError("record must be AttemptHistoryHeadRecord")
    return _json_bytes(_history_head_tree(record))


def parse_attempt_history_head_record(payload: bytes) -> AttemptHistoryHeadRecord:
    root = _object(_load_json(payload), _HEAD_FIELDS, "history head")
    record = AttemptHistoryHeadRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["history_head_record_id"], "history_head_record_id"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid_value(root["authority_epoch_id"], "authority_epoch_id"),
        _nonnegative_value(root["generation"], "generation"),
        _nullable_artifact(root["predecessor"], "predecessor"),
        _nullable_artifact(root["latest_allocation"], "latest_allocation"),
        _nullable_artifact(root["latest_terminal"], "latest_terminal"),
        _nullable_artifact(root["latest_zero_call_proof"], "latest_zero_call_proof"),
        _nullable_artifact(root["latest_recovery"], "latest_recovery"),
        _enum(AttemptHistoryState, root["state"], "state"),
        _nonnegative_value(root["next_attempt_ordinal"], "next_attempt_ordinal"),
        _enum(AttemptHistoryCause, root["advancement_cause"], "advancement_cause"),
        _string(root["policy_version"], "policy_version"),
    )
    if serialize_attempt_history_head_record(record) != payload:
        raise CaptureAttemptArtifactSyntaxError("history head bytes are not canonical")
    return record


def serialize_current_attempt_history_reference(
    reference: CurrentAttemptHistoryReference,
) -> bytes:
    if type(reference) is not CurrentAttemptHistoryReference:
        raise TypeError("reference must be CurrentAttemptHistoryReference")
    return _json_bytes(_pointer_tree(reference))


def parse_current_attempt_history_reference(
    payload: bytes,
) -> CurrentAttemptHistoryReference:
    root = _object(_load_json(payload), _POINTER_FIELDS, "history pointer")
    reference = CurrentAttemptHistoryReference(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid_value(root["authority_epoch_id"], "authority_epoch_id"),
        _nonnegative_value(root["generation"], "generation"),
        _artifact(root["head_record"], "head_record"),
    )
    if serialize_current_attempt_history_reference(reference) != payload:
        raise CaptureAttemptArtifactSyntaxError(
            "history pointer bytes are not canonical"
        )
    return reference


def serialize_capture_attempt_terminal_v2(
    record: CaptureAttemptTerminalRecordV2,
) -> bytes:
    if type(record) is not CaptureAttemptTerminalRecordV2:
        raise TypeError("record must be CaptureAttemptTerminalRecordV2")
    return _json_bytes(_terminal_tree(record))


def parse_capture_attempt_terminal_v2(payload: bytes) -> CaptureAttemptTerminalRecordV2:
    root = _object(_load_json(payload), _TERMINAL_FIELDS, "terminal")
    record = CaptureAttemptTerminalRecordV2(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["terminal_record_id"], "terminal_record_id"),
        _artifact(root["allocation"], "allocation"),
        _uuid_value(root["attempt_id"], "attempt_id"),
        _nonnegative_value(root["attempt_ordinal"], "attempt_ordinal"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _nullable_artifact(root["child_request"], "child_request"),
        _nullable_artifact(root["child_launch"], "child_launch"),
        _nullable_artifact(root["resume_authorization"], "resume_authorization"),
        _nullable_artifact(root["credential_access"], "credential_access"),
        _nullable_artifact(root["child_result"], "child_result"),
        _enum(
            ProviderCallDisposition,
            root["provider_call_disposition"],
            "provider_call_disposition",
        ),
        _timestamp(root["completed_at"], "completed_at"),
        _enum(
            CaptureAttemptTerminalClassification,
            root["classification"],
            "classification",
        ),
        tuple(
            _string(item, "diagnostics")
            for item in _array(root["diagnostics"], "diagnostics")
        ),
        None
        if root["native_child_exit_code"] is None
        else _integer(root["native_child_exit_code"], "native_child_exit_code"),
        _nullable_artifact(root["timeout_termination"], "timeout_termination"),
        _nullable_artifact(root["snapshot"], "snapshot"),
        _nullable_artifact(root["recovery_candidate"], "recovery_candidate"),
        _enum(
            SnapshotTerminalVerification,
            root["snapshot_verification"],
            "snapshot_verification",
        ),
        _enum(SecretCleanupResult, root["secret_cleanup"], "secret_cleanup"),
        _string(root["terminal_policy_version"], "terminal_policy_version"),
    )
    if serialize_capture_attempt_terminal_v2(record) != payload:
        raise CaptureAttemptArtifactSyntaxError("terminal bytes are not canonical")
    return record


# Short aliases keep the schema-2 API discoverable while the explicit v2 names
# make the compatibility boundary unambiguous.
create_capture_attempt_terminal = create_capture_attempt_terminal_v2
serialize_capture_attempt_terminal = serialize_capture_attempt_terminal_v2
parse_capture_attempt_terminal = parse_capture_attempt_terminal_v2


def serialize_zero_provider_call_proof(proof: ZeroProviderCallProof) -> bytes:
    if type(proof) is not ZeroProviderCallProof:
        raise TypeError("proof must be ZeroProviderCallProof")
    return _json_bytes(_zero_proof_tree(proof))


def parse_zero_provider_call_proof(payload: bytes) -> ZeroProviderCallProof:
    root = _object(_load_json(payload), _ZERO_FIELDS, "zero-call proof")
    proof = ZeroProviderCallProof(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["proof_id"], "proof_id"),
        _artifact(root["allocation"], "allocation"),
        _uuid_value(root["attempt_id"], "attempt_id"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _uuid_value(root["scheduled_launch_id"], "scheduled_launch_id"),
        _nullable_artifact(root["child_request"], "child_request"),
        _nullable_artifact(root["process_creation"], "process_creation"),
        _nullable_artifact(root["child_resume"], "child_resume"),
        _nullable_artifact(root["provider_adapter_stage"], "provider_adapter_stage"),
        _nullable_artifact(root["transport_entry"], "transport_entry"),
        _nullable_artifact(
            root["process_exit_or_termination"], "process_exit_or_termination"
        ),
        _enum(
            ZeroProviderCallProofClassification,
            root["classification"],
            "classification",
        ),
        tuple(
            _string(item, "diagnostics")
            for item in _array(root["diagnostics"], "diagnostics")
        ),
        _string(root["proof_policy_version"], "proof_policy_version"),
    )
    if serialize_zero_provider_call_proof(proof) != payload:
        raise CaptureAttemptArtifactSyntaxError(
            "zero-call proof bytes are not canonical"
        )
    return proof


def serialize_manual_capture_attempt_recovery(
    record: ManualCaptureAttemptRecoveryRecord,
) -> bytes:
    if type(record) is not ManualCaptureAttemptRecoveryRecord:
        raise TypeError("record must be ManualCaptureAttemptRecoveryRecord")
    return _json_bytes(_recovery_tree(record))


def parse_manual_capture_attempt_recovery(
    payload: bytes,
) -> ManualCaptureAttemptRecoveryRecord:
    root = _object(_load_json(payload), _RECOVERY_FIELDS, "recovery")
    record = ManualCaptureAttemptRecoveryRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["recovery_record_id"], "recovery_record_id"),
        _artifact(root["history_head"], "history_head"),
        _artifact(root["allocation"], "allocation"),
        _nullable_artifact(root["zero_call_proof"], "zero_call_proof"),
        _nullable_artifact(root["terminal"], "terminal"),
        _nullable_artifact(root["snapshot_candidate"], "snapshot_candidate"),
        _artifact(root["operator_approval"], "operator_approval"),
        _enum(ManualCaptureAttemptRecoveryAction, root["action"], "action"),
        _enum(AttemptHistoryState, root["resulting_state"], "resulting_state"),
        _string(root["recovery_policy_version"], "recovery_policy_version"),
    )
    if serialize_manual_capture_attempt_recovery(record) != payload:
        raise CaptureAttemptArtifactSyntaxError("recovery bytes are not canonical")
    return record


def serialize_capture_terminal_selection(
    record: CaptureTerminalSelectionRecord,
) -> bytes:
    if type(record) is not CaptureTerminalSelectionRecord:
        raise TypeError("record must be CaptureTerminalSelectionRecord")
    return _json_bytes(_selection_tree(record))


def parse_capture_terminal_selection(payload: bytes) -> CaptureTerminalSelectionRecord:
    root = _object(_load_json(payload), _SELECTION_FIELDS, "terminal selection")
    record = CaptureTerminalSelectionRecord(
        _integer(root["schema_version"], "schema_version"),
        _uuid_value(root["selection_record_id"], "selection_record_id"),
        _uuid_value(root["scheduled_session_id"], "scheduled_session_id"),
        _artifact(root["allocation"], "allocation"),
        _artifact(root["terminal"], "terminal"),
        _artifact(root["snapshot"], "snapshot"),
        _string(root["selection_policy_version"], "selection_policy_version"),
        _string(root["result"], "result"),
    )
    if serialize_capture_terminal_selection(record) != payload:
        raise CaptureAttemptArtifactSyntaxError("selection bytes are not canonical")
    return record


# Strict schema field sets are deliberately declared after the models so that
# all parsers reject additions and omissions.
_CREDENTIAL_FIELDS = {
    "schema_version",
    "credential_reference_id",
    "store_type",
    "owner_account_sid",
    "api_key_id_target_name",
    "api_secret_key_target_name",
    "credential_version",
    "persistence",
    "provider_id",
    "purpose",
    "permission_profile",
    "permission_attestation_evidence",
    "rotation_generation",
    "reference_policy_version",
}
_ALLOCATION_FIELDS = {
    "schema_version",
    "allocation_record_id",
    "attempt_id",
    "attempt_ordinal",
    "scheduled_session_id",
    "scheduled_launch_id",
    "authority_epoch_id",
    "head_record",
    "verified_lineage_evidence_id",
    "terminal_checkpoint",
    "terminal_as_of",
    "readiness_decision",
    "market_hours_schedule",
    "capture_policy",
    "capture_policy_version",
    "capture_configuration",
    "snapshot_capture_request_id",
    "target_session",
    "request_timestamp_utc",
    "symbols",
    "timeframe",
    "adjustment",
    "provider",
    "feed",
    "currency",
    "credential_reference",
    "credential_reference_version",
    "destination_reference",
    "software_release",
    "observed_allocation_at",
    "previous_attempt_history_head",
    "allocation_classification",
    "provider_call_budget",
    "allocation_policy_version",
}
_HEAD_FIELDS = {
    "schema_version",
    "history_head_record_id",
    "scheduled_session_id",
    "authority_epoch_id",
    "generation",
    "predecessor",
    "latest_allocation",
    "latest_terminal",
    "latest_zero_call_proof",
    "latest_recovery",
    "state",
    "next_attempt_ordinal",
    "advancement_cause",
    "policy_version",
}
_POINTER_FIELDS = {
    "schema_version",
    "scheduled_session_id",
    "authority_epoch_id",
    "generation",
    "head_record",
}
_TERMINAL_FIELDS = {
    "schema_version",
    "terminal_record_id",
    "allocation",
    "attempt_id",
    "attempt_ordinal",
    "scheduled_session_id",
    "scheduled_launch_id",
    "child_request",
    "child_launch",
    "resume_authorization",
    "credential_access",
    "child_result",
    "provider_call_disposition",
    "completed_at",
    "classification",
    "diagnostics",
    "native_child_exit_code",
    "timeout_termination",
    "snapshot",
    "recovery_candidate",
    "snapshot_verification",
    "secret_cleanup",
    "terminal_policy_version",
}
_ZERO_FIELDS = {
    "schema_version",
    "proof_id",
    "allocation",
    "attempt_id",
    "scheduled_session_id",
    "scheduled_launch_id",
    "child_request",
    "process_creation",
    "child_resume",
    "provider_adapter_stage",
    "transport_entry",
    "process_exit_or_termination",
    "classification",
    "diagnostics",
    "proof_policy_version",
}
_RECOVERY_FIELDS = {
    "schema_version",
    "recovery_record_id",
    "history_head",
    "allocation",
    "zero_call_proof",
    "terminal",
    "snapshot_candidate",
    "operator_approval",
    "action",
    "resulting_state",
    "recovery_policy_version",
}
_SELECTION_FIELDS = {
    "schema_version",
    "selection_record_id",
    "scheduled_session_id",
    "allocation",
    "terminal",
    "snapshot",
    "selection_policy_version",
    "result",
}


def _credential_tree(
    reference: WindowsMarketDataCredentialReference,
) -> dict[str, object]:
    return {
        "schema_version": reference.schema_version,
        "credential_reference_id": str(reference.credential_reference_id),
        "store_type": reference.store_type.value,
        "owner_account_sid": reference.owner_account_sid,
        "api_key_id_target_name": reference.api_key_id_target_name,
        "api_secret_key_target_name": reference.api_secret_key_target_name,
        "credential_version": reference.credential_version,
        "persistence": reference.persistence.value,
        "provider_id": reference.provider_id,
        "purpose": reference.purpose.value,
        "permission_profile": reference.permission_profile,
        "permission_attestation_evidence": _artifact_tree(
            reference.permission_attestation_evidence
        ),
        "rotation_generation": reference.rotation_generation,
        "reference_policy_version": reference.reference_policy_version,
    }


def _allocation_tree(record: CaptureAttemptAllocationRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "allocation_record_id": str(record.allocation_record_id),
        "attempt_id": str(record.attempt_id),
        "attempt_ordinal": record.attempt_ordinal,
        "scheduled_session_id": str(record.scheduled_session_id),
        "scheduled_launch_id": str(record.scheduled_launch_id),
        "authority_epoch_id": str(record.authority_epoch_id),
        "head_record": _head_tree(record.head_record),
        "verified_lineage_evidence_id": str(record.verified_lineage_evidence_id),
        "terminal_checkpoint": _terminal_checkpoint_tree(record.terminal_checkpoint),
        "terminal_as_of": canonical_timestamp(record.terminal_as_of),
        "readiness_decision": _artifact_tree(record.readiness_decision),
        "market_hours_schedule": _artifact_tree(record.market_hours_schedule),
        "capture_policy": _artifact_tree(record.capture_policy),
        "capture_policy_version": record.capture_policy_version,
        "capture_configuration": _artifact_tree(record.capture_configuration),
        "snapshot_capture_request_id": str(record.snapshot_capture_request_id),
        "target_session": record.target_session.session_date.isoformat(),
        "request_timestamp_utc": canonical_timestamp(record.request_timestamp_utc),
        "symbols": [str(symbol) for symbol in record.symbols],
        "timeframe": record.timeframe.value,
        "adjustment": record.adjustment.value,
        "provider": _provider_tree(record.provider),
        "feed": record.feed,
        "currency": record.currency,
        "credential_reference": _artifact_tree(record.credential_reference),
        "credential_reference_version": record.credential_reference_version,
        "destination_reference": _artifact_tree(record.destination_reference),
        "software_release": _artifact_tree(record.software_release),
        "observed_allocation_at": canonical_timestamp(record.observed_allocation_at),
        "previous_attempt_history_head": _artifact_tree(
            record.previous_attempt_history_head
        ),
        "allocation_classification": record.allocation_classification.value,
        "provider_call_budget": record.provider_call_budget,
        "allocation_policy_version": record.allocation_policy_version,
    }


def _history_head_tree(record: AttemptHistoryHeadRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "history_head_record_id": str(record.history_head_record_id),
        "scheduled_session_id": str(record.scheduled_session_id),
        "authority_epoch_id": str(record.authority_epoch_id),
        "generation": record.generation,
        "predecessor": _nullable_artifact_tree(record.predecessor),
        "latest_allocation": _nullable_artifact_tree(record.latest_allocation),
        "latest_terminal": _nullable_artifact_tree(record.latest_terminal),
        "latest_zero_call_proof": _nullable_artifact_tree(
            record.latest_zero_call_proof
        ),
        "latest_recovery": _nullable_artifact_tree(record.latest_recovery),
        "state": record.state.value,
        "next_attempt_ordinal": record.next_attempt_ordinal,
        "advancement_cause": record.advancement_cause.value,
        "policy_version": record.policy_version,
    }


def _pointer_tree(reference: CurrentAttemptHistoryReference) -> dict[str, object]:
    return {
        "schema_version": reference.schema_version,
        "scheduled_session_id": str(reference.scheduled_session_id),
        "authority_epoch_id": str(reference.authority_epoch_id),
        "generation": reference.generation,
        "head_record": _artifact_tree(reference.head_record),
    }


def _terminal_tree(record: CaptureAttemptTerminalRecordV2) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "terminal_record_id": str(record.terminal_record_id),
        "allocation": _artifact_tree(record.allocation),
        "attempt_id": str(record.attempt_id),
        "attempt_ordinal": record.attempt_ordinal,
        "scheduled_session_id": str(record.scheduled_session_id),
        "scheduled_launch_id": str(record.scheduled_launch_id),
        "child_request": _nullable_artifact_tree(record.child_request),
        "child_launch": _nullable_artifact_tree(record.child_launch),
        "resume_authorization": _nullable_artifact_tree(record.resume_authorization),
        "credential_access": _nullable_artifact_tree(record.credential_access),
        "child_result": _nullable_artifact_tree(record.child_result),
        "provider_call_disposition": record.provider_call_disposition.value,
        "completed_at": canonical_timestamp(record.completed_at),
        "classification": record.classification.value,
        "diagnostics": list(record.diagnostics),
        "native_child_exit_code": record.native_child_exit_code,
        "timeout_termination": _nullable_artifact_tree(record.timeout_termination),
        "snapshot": _nullable_artifact_tree(record.snapshot),
        "recovery_candidate": _nullable_artifact_tree(record.recovery_candidate),
        "snapshot_verification": record.snapshot_verification.value,
        "secret_cleanup": record.secret_cleanup.value,
        "terminal_policy_version": record.terminal_policy_version,
    }


def _zero_proof_tree(proof: ZeroProviderCallProof) -> dict[str, object]:
    return {
        "schema_version": proof.schema_version,
        "proof_id": str(proof.proof_id),
        "allocation": _artifact_tree(proof.allocation),
        "attempt_id": str(proof.attempt_id),
        "scheduled_session_id": str(proof.scheduled_session_id),
        "scheduled_launch_id": str(proof.scheduled_launch_id),
        "child_request": _nullable_artifact_tree(proof.child_request),
        "process_creation": _nullable_artifact_tree(proof.process_creation),
        "child_resume": _nullable_artifact_tree(proof.child_resume),
        "provider_adapter_stage": _nullable_artifact_tree(proof.provider_adapter_stage),
        "transport_entry": _nullable_artifact_tree(proof.transport_entry),
        "process_exit_or_termination": _nullable_artifact_tree(
            proof.process_exit_or_termination
        ),
        "classification": proof.classification.value,
        "diagnostics": list(proof.diagnostics),
        "proof_policy_version": proof.proof_policy_version,
    }


def _recovery_tree(record: ManualCaptureAttemptRecoveryRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "recovery_record_id": str(record.recovery_record_id),
        "history_head": _artifact_tree(record.history_head),
        "allocation": _artifact_tree(record.allocation),
        "zero_call_proof": _nullable_artifact_tree(record.zero_call_proof),
        "terminal": _nullable_artifact_tree(record.terminal),
        "snapshot_candidate": _nullable_artifact_tree(record.snapshot_candidate),
        "operator_approval": _artifact_tree(record.operator_approval),
        "action": record.action.value,
        "resulting_state": record.resulting_state.value,
        "recovery_policy_version": record.recovery_policy_version,
    }


def _selection_tree(record: CaptureTerminalSelectionRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "selection_record_id": str(record.selection_record_id),
        "scheduled_session_id": str(record.scheduled_session_id),
        "allocation": _artifact_tree(record.allocation),
        "terminal": _artifact_tree(record.terminal),
        "snapshot": _artifact_tree(record.snapshot),
        "selection_policy_version": record.selection_policy_version,
        "result": record.result,
    }


def _head_tree(value: HeadRecordEvidence) -> dict[str, object]:
    return {
        "authority_epoch_id": str(value.authority_epoch_id),
        "record": _artifact_tree(value.record),
        "generation": value.generation,
    }


def _terminal_checkpoint_tree(value: TerminalCheckpointEvidence) -> dict[str, object]:
    return {
        "checkpoint": _artifact_tree(value.checkpoint),
        "sequence": value.sequence,
        "as_of": canonical_timestamp(value.as_of),
    }


def _artifact_tree(value: ArtifactEvidence) -> dict[str, object]:
    return {
        "artifact_id": str(value.artifact_id),
        "sha256": value.sha256,
        "byte_length": value.byte_length,
    }


def _nullable_artifact_tree(value: ArtifactEvidence | None) -> dict[str, object] | None:
    return None if value is None else _artifact_tree(value)


def _artifact(value: object, label: str) -> ArtifactEvidence:
    root = _object(value, {"artifact_id", "sha256", "byte_length"}, label)
    artifact = ArtifactEvidence(
        _uuid_value(root["artifact_id"], f"{label}.artifact_id"),
        _sha_value(root["sha256"], f"{label}.sha256"),
        _nonnegative_value(root["byte_length"], f"{label}.byte_length"),
    )
    if artifact.artifact_id == UUID(int=0):
        raise CaptureAttemptAuthorityError(f"{label}.artifact_id must be nonzero")
    return artifact


def _nullable_artifact(value: object, label: str) -> ArtifactEvidence | None:
    return None if value is None else _artifact(value, label)


def _head_record(value: object) -> HeadRecordEvidence:
    root = _object(value, {"authority_epoch_id", "record", "generation"}, "head_record")
    return HeadRecordEvidence(
        _uuid_value(root["authority_epoch_id"], "head_record.authority_epoch_id"),
        _artifact(root["record"], "head_record.record"),
        _nonnegative_value(root["generation"], "head_record.generation"),
    )


def _terminal_checkpoint(value: object) -> TerminalCheckpointEvidence:
    root = _object(value, {"checkpoint", "sequence", "as_of"}, "terminal_checkpoint")
    return TerminalCheckpointEvidence(
        _artifact(root["checkpoint"], "terminal_checkpoint.checkpoint"),
        _nonnegative_value(root["sequence"], "terminal_checkpoint.sequence"),
        _timestamp(root["as_of"], "terminal_checkpoint.as_of"),
    )


def _provider(value: object) -> ProviderDescriptor:
    root = _object(
        value, {"provider_id", "adapter_version", "operation", "feed"}, "provider"
    )
    return ProviderDescriptor(
        _string(root["provider_id"], "provider.provider_id"),
        _integer(root["adapter_version"], "provider.adapter_version"),
        _string(root["operation"], "provider.operation"),
        _string(root["feed"], "provider.feed"),
    )


def _provider_tree(value: ProviderDescriptor) -> dict[str, object]:
    return {
        "provider_id": value.provider_id,
        "adapter_version": value.adapter_version,
        "operation": value.operation,
        "feed": value.feed,
    }


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
    if len(payload) > MAX_CAPTURE_ATTEMPT_ARTIFACT_BYTES:
        raise CaptureAttemptAuthorityError("capture-attempt artifact exceeds bound")
    return payload


def _load_json(payload: bytes) -> object:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > MAX_CAPTURE_ATTEMPT_ARTIFACT_BYTES
        or payload.startswith(b"\xef\xbb\xbf")
    ):
        raise CaptureAttemptArtifactSyntaxError("artifact bytes are invalid")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        CaptureAttemptAuthorityError,
    ) as error:
        raise CaptureAttemptArtifactSyntaxError(
            "artifact is not strict JSON"
        ) from error


def _duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CaptureAttemptArtifactSyntaxError("duplicate JSON field")
        result[key] = value
    return result


def _reject_float(_: str) -> None:
    raise CaptureAttemptArtifactSyntaxError("JSON floats are not permitted")


def _reject_constant(_: str) -> None:
    raise CaptureAttemptArtifactSyntaxError("JSON constants are not permitted")


def _object(value: object, fields: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise CaptureAttemptAuthorityError(f"{label} fields are invalid")
    return value


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list or len(value) > MAX_CAPTURE_ATTEMPT_ITEMS:
        raise CaptureAttemptAuthorityError(f"{label} must be a bounded array")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= MAX_CAPTURE_ATTEMPT_TEXT:
        raise CaptureAttemptAuthorityError(f"{label} must be bounded text")
    return value


def _text(value: str, label: str) -> None:
    if (
        type(value) is not str
        or _TEXT.fullmatch(value) is None
        or len(value) > MAX_CAPTURE_ATTEMPT_TEXT
    ):
        raise CaptureAttemptAuthorityError(f"{label} must be canonical text")


def _policy(value: str, label: str) -> None:
    if type(value) is not str or _POLICY.fullmatch(value) is None:
        raise CaptureAttemptAuthorityError(
            f"{label} must be a canonical policy version"
        )


def _integer(value: object, label: str) -> int:
    if type(value) is not int or abs(value) > MAX_CAPTURE_ATTEMPT_INTEGER:
        raise CaptureAttemptAuthorityError(f"{label} must be a bounded integer")
    return value


def _nonnegative(value: object, label: str) -> None:
    if type(value) is not int or not 0 <= value <= MAX_CAPTURE_ATTEMPT_INTEGER:
        raise CaptureAttemptAuthorityError(f"{label} must be nonnegative")


def _nonnegative_value(value: object, label: str) -> int:
    _nonnegative(value, label)
    return value  # type: ignore[return-value]


def _uuid(value: object, label: str) -> None:
    if type(value) is not UUID or value == UUID(int=0):
        raise CaptureAttemptAuthorityError(f"{label} must be a UUID")


def _uuid_value(value: object, label: str) -> UUID:
    text = _string(value, label)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise CaptureAttemptAuthorityError(
            f"{label} must be canonical UUID text"
        ) from error
    if str(parsed) != text:
        raise CaptureAttemptAuthorityError(f"{label} must be canonical UUID text")
    return parsed


def _sha_value(value: object, label: str) -> str:
    text = _string(value, label)
    if _SHA256.fullmatch(text) is None:
        raise CaptureAttemptAuthorityError(f"{label} must be lowercase SHA-256")
    return text


def _timestamp(value: object, label: str) -> datetime:
    text = _string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise CaptureAttemptAuthorityError(f"{label} is not a timestamp") from error
    normalized = _utc(parsed, label)
    if canonical_timestamp(normalized) != text:
        raise CaptureAttemptAuthorityError(f"{label} is not canonical")
    return normalized


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise CaptureAttemptAuthorityError(f"{label} is not a date") from error
    if parsed.isoformat() != text:
        raise CaptureAttemptAuthorityError(f"{label} is not canonical")
    return parsed


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise CaptureAttemptAuthorityError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _symbols(value: object) -> tuple[Symbol, ...]:
    items = tuple(value) if not isinstance(value, (str, bytes)) else ()
    if (
        not 1 <= len(items) <= MAX_CAPTURE_ATTEMPT_ITEMS
        or any(type(item) is not Symbol for item in items)
        or len(set(items)) != len(items)
    ):
        raise CaptureAttemptAuthorityError(
            "symbols must be ordered unique Symbol values"
        )
    return items


def _symbols_value(value: object, label: str) -> tuple[Symbol, ...]:
    values = _array(value, label)
    symbols: list[Symbol] = []
    for item in values:
        raw = _string(item, label)
        try:
            symbol = Symbol(raw)
        except (TypeError, ValueError) as error:
            raise CaptureAttemptAuthorityError(
                f"{label} contains invalid symbol"
            ) from error
        if str(symbol) != raw:
            raise CaptureAttemptAuthorityError(f"{label} contains noncanonical symbol")
        symbols.append(symbol)
    return _symbols(tuple(symbols))


def _enum(enum_type, value: object, label: str):  # type: ignore[no-untyped-def]
    text = _string(value, label)
    try:
        return enum_type(text)
    except ValueError as error:
        raise CaptureAttemptAuthorityError(f"{label} is unsupported") from error


def _recovery_action(name: str) -> ManualCaptureAttemptRecoveryAction:
    return ManualCaptureAttemptRecoveryAction[name]


def _diagnostics(value: object, label: str) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or len(value) > MAX_CAPTURE_ATTEMPT_ITEMS:
        raise CaptureAttemptAuthorityError(f"{label} must be a bounded array")
    diagnostics = tuple(_string(item, label) for item in value)
    if len(set(diagnostics)) != len(diagnostics):
        raise CaptureAttemptAuthorityError(f"{label} are invalid")
    return diagnostics


def _evidence_parts(value: ArtifactEvidence) -> tuple[str, ...]:
    return str(value.artifact_id), value.sha256, str(value.byte_length)


def _id(namespace: UUID, parts: tuple[str, ...]) -> UUID:
    return uuid5(namespace, _framed(parts))


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)


def _artifact_evidence(artifact_id: UUID, payload: bytes) -> ArtifactEvidence:
    return ArtifactEvidence(
        artifact_id, hashlib.sha256(payload).hexdigest(), len(payload)
    )


def _build_with_derived_id(
    cls, values: tuple[object, ...], id_field: str, derive
) -> object:  # type: ignore[no-untyped-def]
    """Construct a frozen model after deriving its identity.

    Identity derivation necessarily consumes the other fields, so factories
    build an unchecked instance, derive the ID, and then run the model's full
    validator.  Parsers never use this path: they validate the supplied ID.
    """
    record = object.__new__(cls)
    expected_fields = fields(cls)
    if len(values) != len(expected_fields):
        raise TypeError("model field count mismatch")
    for field, value in zip(expected_fields, values, strict=True):
        object.__setattr__(record, field.name, value)
    object.__setattr__(record, id_field, derive(record))
    cls.__post_init__(record)
    return record


def _build_history_head(*values: object) -> AttemptHistoryHeadRecord:
    return _build_with_derived_id(
        AttemptHistoryHeadRecord,
        tuple(values),
        "history_head_record_id",
        derive_attempt_history_head_id,
    )  # type: ignore[return-value]


def create_attempt_history_head(**values: object) -> AttemptHistoryHeadRecord:
    """Create an immutable history head with a derived record identity."""
    names = tuple(field.name for field in fields(AttemptHistoryHeadRecord))
    supplied = dict(values)
    supplied.setdefault("schema_version", ATTEMPT_HISTORY_HEAD_SCHEMA_VERSION)
    supplied.setdefault("history_head_record_id", UUID(int=0))
    missing = [name for name in names if name not in supplied]
    if missing:
        raise TypeError(f"missing history-head fields: {', '.join(missing)}")
    return _build_with_derived_id(
        AttemptHistoryHeadRecord,
        tuple(supplied[name] for name in names),
        "history_head_record_id",
        derive_attempt_history_head_id,
    )  # type: ignore[return-value]


def _build_selection(*values: object) -> CaptureTerminalSelectionRecord:
    return _build_with_derived_id(
        CaptureTerminalSelectionRecord,
        tuple(values),
        "selection_record_id",
        derive_capture_terminal_selection_id,
    )  # type: ignore[return-value]


def _history_session_root(root: Path, session_id: UUID) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise CaptureAttemptAuthorityError(
            "capture-attempt authority root must be absolute"
        )
    _uuid(session_id, "scheduled_session_id")
    return root / str(session_id)


def _ensure_history_directories(root: Path, session_id: UUID) -> Path:
    session_root = _history_session_root(root, session_id)
    if not root.exists():
        raise CaptureAttemptAuthorityError(
            "capture-attempt authority root must already exist"
        )
    try:
        validate_output_parent(root)
    except Exception as error:
        raise CaptureAttemptAuthorityError(
            "capture-attempt authority root is unsafe"
        ) from error
    try:
        if not session_root.exists():
            os.mkdir(session_root)
        validate_output_parent(session_root)
        for name in (
            "history-head-records",
            "allocations",
            "terminals",
            "zero-call-proofs",
            "recovery-records",
        ):
            directory = session_root / name
            if not directory.exists():
                os.mkdir(directory)
            validate_output_parent(directory)
    except OSError as error:
        raise CaptureAttemptAuthorityError(
            "cannot create capture-attempt authority directories"
        ) from error
    return session_root


def _publish_exclusive(path: Path, payload: bytes, parser) -> None:  # type: ignore[no-untyped-def]
    try:
        validate_output_parent(path.parent)
    except Exception as error:
        raise CaptureAttemptAuthorityError(
            "artifact parent is not a safe existing directory"
        ) from error
    if path.exists():
        existing = _safe_read(path)
        if existing != payload or parser(existing) != parser(payload):
            raise CaptureAttemptAuthorityError(
                "existing artifact conflicts with requested bytes"
            )
        return
    staging = path.parent / f".{path.name}.staging"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(staging, flags, 0o600)
    except FileExistsError as error:
        raise CaptureAttemptAuthorityError(
            "crash-left staging requires manual review"
        ) from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if _safe_read(staging) != payload or parser(_safe_read(staging)) != parser(
            payload
        ):
            raise CaptureAttemptAuthorityError("staging bytes do not reconcile")
        try:
            os.link(staging, path, follow_symlinks=False)
        except FileExistsError as error:
            if _safe_read(path) != payload:
                raise CaptureAttemptAuthorityError(
                    "no-clobber finalization conflict"
                ) from error
        if parser(_safe_read(path)) != parser(payload):
            raise CaptureAttemptAuthorityError("final artifact does not reconcile")
        staging_stat = staging.lstat()
        final_stat = path.lstat()
        if (staging_stat.st_dev, staging_stat.st_ino) != (
            final_stat.st_dev,
            final_stat.st_ino,
        ):
            raise CaptureAttemptAuthorityError("staging and final identities differ")
        staging.unlink()
    except Exception:
        raise


def _publish_immutable(directory: Path, filename: str, payload: bytes, parser) -> Path:  # type: ignore[no-untyped-def]
    path = directory / filename
    _publish_exclusive(path, payload, parser)
    return path


def _replace_history_pointer(
    pointer_path: Path,
    expected_payload: bytes,
    replacement_payload: bytes,
    replacer: AtomicAttemptHistoryPointerReplacer | None,
) -> None:
    parent = validate_output_parent(pointer_path.parent)
    retained = (
        WindowsAtomicAttemptHistoryPointerReplacer() if replacer is None else replacer
    )
    retained.replace(
        pointer_path,
        expected_payload=expected_payload,
        replacement_payload=replacement_payload,
        parent_identity=(parent.device, parent.inode),
    )


def _safe_read(path: Path) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise CaptureAttemptAuthorityError("artifact is not a safe regular file")
    with path.open("rb") as stream:
        payload = stream.read(MAX_CAPTURE_ATTEMPT_ARTIFACT_BYTES + 1)
    after = path.lstat()
    if (info.st_dev, info.st_ino) != (
        after.st_dev,
        after.st_ino,
    ) or info.st_size != after.st_size:
        raise CaptureAttemptAuthorityError("artifact changed during reread")
    if len(payload) > MAX_CAPTURE_ATTEMPT_ARTIFACT_BYTES:
        raise CaptureAttemptAuthorityError("artifact exceeds bounded reread")
    return payload


def _require_directory_identity(path: Path, expected: tuple[int, int]) -> None:
    state = validate_output_parent(path)
    if (state.device, state.inode) != expected:
        raise AtomicAttemptHistoryPointerReplacementError(
            "pointer parent identity changed"
        )


def _read_named_head(
    session_root: Path, evidence: ArtifactEvidence
) -> AttemptHistoryHeadRecord:
    payload = _safe_read(
        session_root / "history-head-records" / _head_filename(evidence.artifact_id)
    )
    if _artifact_evidence(evidence.artifact_id, payload) != evidence:
        raise CaptureAttemptAuthorityError("history-head evidence mismatch")
    record = parse_attempt_history_head_record(payload)
    if record.history_head_record_id != evidence.artifact_id:
        raise CaptureAttemptAuthorityError("history-head identity mismatch")
    return record


def _read_named_terminal(
    session_root: Path, evidence: ArtifactEvidence
) -> CaptureAttemptTerminalRecordV2:
    payload = _safe_read(
        session_root / "terminals" / _terminal_filename(evidence.artifact_id)
    )
    if _artifact_evidence(evidence.artifact_id, payload) != evidence:
        raise CaptureAttemptAuthorityError("terminal evidence mismatch")
    record = parse_capture_attempt_terminal_v2(payload)
    if record.terminal_record_id != evidence.artifact_id:
        raise CaptureAttemptAuthorityError("terminal identity mismatch")
    return record


def _verify_selected_state_artifacts(
    session_root: Path, head: AttemptHistoryHeadRecord
) -> None:
    if head.latest_allocation is not None:
        payload = _safe_read(
            session_root
            / "allocations"
            / _allocation_filename(head.latest_allocation.artifact_id)
        )
        if (
            _artifact_evidence(head.latest_allocation.artifact_id, payload)
            != head.latest_allocation
        ):
            raise CaptureAttemptAuthorityError("allocation evidence mismatch")
        allocation = parse_capture_attempt_allocation(payload)
        if allocation.allocation_record_id != head.latest_allocation.artifact_id:
            raise CaptureAttemptAuthorityError("allocation identity mismatch")
        if allocation.scheduled_session_id != head.scheduled_session_id:
            raise CaptureAttemptAuthorityError("allocation session mismatch")
    if head.latest_terminal is not None:
        terminal = _read_named_terminal(session_root, head.latest_terminal)
        if (
            head.latest_allocation is None
            or terminal.allocation != head.latest_allocation
        ):
            raise CaptureAttemptAuthorityError("terminal/allocation history mismatch")
    if head.latest_recovery is not None:
        payload = _safe_read(
            session_root
            / "recovery-records"
            / _recovery_filename(head.latest_recovery.artifact_id)
        )
        if (
            _artifact_evidence(head.latest_recovery.artifact_id, payload)
            != head.latest_recovery
        ):
            raise CaptureAttemptAuthorityError("recovery evidence mismatch")
        recovery = parse_manual_capture_attempt_recovery(payload)
        if recovery.recovery_record_id != head.latest_recovery.artifact_id:
            raise CaptureAttemptAuthorityError("recovery identity mismatch")
    if head.latest_zero_call_proof is not None:
        payload = _safe_read(
            session_root
            / "zero-call-proofs"
            / _proof_filename(head.latest_zero_call_proof.artifact_id)
        )
        if (
            _artifact_evidence(head.latest_zero_call_proof.artifact_id, payload)
            != head.latest_zero_call_proof
        ):
            raise CaptureAttemptAuthorityError("zero-call proof evidence mismatch")
        proof = parse_zero_provider_call_proof(payload)
        if proof.proof_id != head.latest_zero_call_proof.artifact_id:
            raise CaptureAttemptAuthorityError("zero-call proof identity mismatch")
        verify_zero_provider_call_proof(proof)


def _head_filename(value: UUID) -> str:
    return f"capture-attempt-history-head-{value}.json"


def _allocation_filename(value: UUID) -> str:
    return f"capture-attempt-allocation-{value}.json"


def _terminal_filename(value: UUID) -> str:
    return f"capture-attempt-terminal-{value}.json"


def _proof_filename(value: UUID) -> str:
    return f"zero-provider-call-proof-{value}.json"


def _recovery_filename(value: UUID) -> str:
    return f"capture-attempt-recovery-{value}.json"


def _selection_filename(value: UUID) -> str:
    return f"capture-terminal-selection-{value}.json"
