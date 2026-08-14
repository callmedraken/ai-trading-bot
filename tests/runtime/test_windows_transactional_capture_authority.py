"""Executable evidence for the normalized transactional authority design."""

from __future__ import annotations

import ast
import contextvars
import hashlib
import inspect
import json
import multiprocessing
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from trading_bot.market_data import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    MAX_DAILY_SNAPSHOT_SYMBOLS,
)
from trading_bot.runtime.windows_authority import PRODUCTION_AUTHORITY_PATHS
from trading_bot.runtime.windows_authority_schema import (
    INITIALIZATION_POLICY_VERSION,
    METADATA_ENCODING_VERSION,
    PRODUCTION_SCHEMA_ARTIFACT_BYTES,
    PRODUCTION_SCHEMA_ARTIFACT_SHA256,
    PRODUCTION_SCHEMA_ID,
    PRODUCTION_SCHEMA_VERSION,
    SchemaValidationError,
    configure_trusted_schema_off,
    execute_schema_artifact,
    require_evidence_digest,
)
from trading_bot.runtime.windows_transactional_authority import (
    ConstructedProvider as FakeConstructedProvider,
)
from trading_bot.runtime.windows_transactional_authority import (
    DisposableAuthorityDatabaseForTest,
    ExternalAuthorityBoundaryUnavailable,
    TransactionalAuthorityCore,
    TransactionalAuthorityCoreBinding,
    ValidatedCaptureRequest,
)
from trading_bot.runtime.windows_transactional_authority import (
    ProcessCreationFailure as FakeProcessCreationFailure,
)
from trading_bot.runtime.windows_transactional_authority import (
    ProcessCreationReceipt as FakeProcessCreationReceipt,
)
from trading_bot.runtime.windows_transactional_authority import (
    ProcessIntent as FakeProcessIntent,
)
from trading_bot.runtime.windows_transactional_authority import (
    ProviderConstructionPermit as FakeProviderConstructionPermit,
)
from trading_bot.runtime.windows_transactional_authority import (
    ResumeIntent as FakeResumeIntent,
)
from trading_bot.runtime.windows_transactional_authority import (
    ResumeReceipt as FakeResumeReceipt,
)
from trading_bot.runtime.windows_transactional_authority import (
    consume_constructed_provider_for_test as _consume_constructed_provider,
)
from trading_bot.runtime.windows_transactional_authority import (
    consume_process_intent_for_test as _consume_process_intent,
)
from trading_bot.runtime.windows_transactional_authority import (
    consume_process_result_for_test as _consume_process_result,
)
from trading_bot.runtime.windows_transactional_authority import (
    consume_provider_construction_permit_for_test as _consume_provider_construction_permit,  # noqa: E501
)
from trading_bot.runtime.windows_transactional_authority import (
    consume_resume_intent_for_test as _consume_resume_intent,
)
from trading_bot.runtime.windows_transactional_authority import (
    consume_resume_result_for_test as _consume_resume_result,
)
from trading_bot.runtime.windows_transactional_authority import (
    issue_constructed_provider_for_test as _issue_constructed_provider,
)
from trading_bot.runtime.windows_transactional_authority import (
    issue_process_creation_failure_for_test as _issue_process_creation_failure,
)
from trading_bot.runtime.windows_transactional_authority import (
    issue_process_creation_receipt_for_test as _issue_process_creation_receipt,
)
from trading_bot.runtime.windows_transactional_authority import (
    issue_resume_receipt_for_test as _issue_resume_receipt,
)
from trading_bot.runtime.windows_transactional_authority import (
    process_failure_json_for_test as _process_failure_json,
)
from trading_bot.runtime.windows_transactional_authority import (
    process_intent_json_for_test as _process_intent_json,
)
from trading_bot.runtime.windows_transactional_authority import (
    process_success_evidence_for_test as _process_success_evidence,
)
from trading_bot.runtime.windows_transactional_authority import (
    registered_constructed_provider_reservation_id_for_test as _registered_constructed_provider_reservation_id,  # noqa: E501
)
from trading_bot.runtime.windows_transactional_authority import (
    registered_process_intent_reservation_id_for_test as _registered_process_intent_reservation_id,  # noqa: E501
)
from trading_bot.runtime.windows_transactional_authority import (
    registered_process_result_reservation_id_for_test as _registered_process_result_reservation_id,  # noqa: E501
)
from trading_bot.runtime.windows_transactional_authority import (
    registered_provider_reservation_id_for_test as _registered_provider_reservation_id,
)
from trading_bot.runtime.windows_transactional_authority import (
    registered_resume_intent_binding_for_test as _registered_resume_intent_binding,
)
from trading_bot.runtime.windows_transactional_authority import (
    registered_resume_result_binding_for_test as _registered_resume_result_binding,
)
from trading_bot.runtime.windows_transactional_authority import (
    snapshot_capture_request_for_test as _snapshot_capture_request,
)


def _capability_is_registered(capability: object) -> bool:
    try:
        if type(capability) is FakeProviderConstructionPermit:
            _registered_provider_reservation_id(capability)
        elif type(capability) is FakeConstructedProvider:
            _registered_constructed_provider_reservation_id(capability)
        elif type(capability) is FakeProcessIntent:
            _registered_process_intent_reservation_id(capability)
        elif type(capability) in {
            FakeProcessCreationReceipt,
            FakeProcessCreationFailure,
        }:
            _registered_process_result_reservation_id(capability)
        elif type(capability) is FakeResumeIntent:
            _registered_resume_intent_binding(capability)
        elif type(capability) is FakeResumeReceipt:
            _registered_resume_result_binding(capability)
        else:
            return False
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _consume_capability_for_test(capability: object) -> None:
    if not _capability_is_registered(capability):
        return
    harness = _CURRENT_HARNESS.get()
    if harness is None:
        raise HarnessLifecycleError(
            "capability consumer requires an active Architecture-77 harness"
        )
    core = harness._core
    if type(capability) is FakeProviderConstructionPermit:
        _consume_provider_construction_permit(
            capability,
            _registered_provider_reservation_id(capability),
            core=core,
        )
    elif type(capability) is FakeConstructedProvider:
        _consume_constructed_provider(
            capability,
            _registered_constructed_provider_reservation_id(capability),
            core=core,
        )
    elif type(capability) is FakeProcessIntent:
        _consume_process_intent(
            capability,
            _registered_process_intent_reservation_id(capability),
            core=core,
        )
    elif type(capability) in {FakeProcessCreationReceipt, FakeProcessCreationFailure}:
        _consume_process_result(
            capability,
            _registered_process_result_reservation_id(capability),
            core=core,
        )
    elif type(capability) is FakeResumeIntent:
        execution_id, reservation_id = _registered_resume_intent_binding(capability)
        _consume_resume_intent(capability, execution_id, reservation_id, core=core)
    elif type(capability) is FakeResumeReceipt:
        execution_id, reservation_id = _registered_resume_result_binding(capability)
        _consume_resume_result(capability, execution_id, reservation_id, core=core)


def _assert_capability_available(capability: object) -> None:
    assert _capability_is_registered(capability)


def _assert_capability_consumed(capability: object) -> None:
    assert not _capability_is_registered(capability)


def _forged_capability(capability_type: type[object], **fields: object) -> object:
    forged = object.__new__(capability_type)
    for field_name, value in fields.items():
        object.__setattr__(forged, field_name, value)
    return forged


_HARNESS_MODULE_PATH = Path(__file__).resolve(strict=True)
_HARNESS_REPOSITORY_ROOT = _HARNESS_MODULE_PATH.parents[2]
_EXPECTED_HARNESS_PATH = (
    _HARNESS_REPOSITORY_ROOT
    / "tests"
    / "runtime"
    / "test_windows_transactional_capture_authority.py"
)
if (
    _HARNESS_MODULE_PATH != _EXPECTED_HARNESS_PATH
    or not (_HARNESS_REPOSITORY_ROOT / "AGENTS.md").is_file()
):
    raise RuntimeError("transactional-authority repository root is ambiguous")
_LIFECYCLE_ARBITER_ROOT = (
    _HARNESS_REPOSITORY_ROOT / ".pytest_cache" / "ai-trading-bot-lifecycle-arbiters-v1"
).resolve()
if not _LIFECYCLE_ARBITER_ROOT.is_absolute():
    raise RuntimeError("lifecycle-arbiter adapter root must be absolute")
SCHEMA_BYTES = PRODUCTION_SCHEMA_ARTIFACT_BYTES
SCHEMA_SHA256 = PRODUCTION_SCHEMA_ARTIFACT_SHA256
NAMESPACE = uuid.UUID("7c2d5a44-3b2e-5f8f-9a1c-6d4e7b8f9012")
EPOCH = "12345678-1234-5678-9abc-def012345678"
MACHINE = "87654321-4321-8765-cba9-876543210987"
PROVIDER = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
OPERATION = ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
POLICY = "authority-policy/v1"
CLAIM_POLICY = "claim-policy/v1"
RELEASE = "release/v1"
TERMINAL_POLICY = "terminal-policy/v1"
SELECTION_POLICY = "selection-policy/v1"
RECOVERY_POLICY = "recovery-policy/v1"
TIMESTAMP = "2026-01-01T00:00:00Z"
PROCESS_INTENT_TIMESTAMP = "2026-01-01T00:00:30Z"
PROCESS_CREATED_TIMESTAMP = "2026-01-01T00:01:00Z"
RESUME_INTENT_TIMESTAMP = "2026-01-01T00:01:30Z"
PROCESS_FAILURE_TIMESTAMP = "2026-01-01T00:02:00Z"
MANUAL_REVIEW_TIMESTAMP = "2026-01-01T00:03:00Z"
TERMINAL_TIMESTAMP = "2026-01-01T00:04:00Z"
SELECTION_TIMESTAMP = "2026-01-01T00:05:00Z"
CLOSE_TIMESTAMP = "2026-01-01T00:06:00Z"
CAPTURE_REQUEST_FIELDS = frozenset(
    {
        "bar_interval",
        "child_operation_version",
        "ordered_universe",
        "output_policy_version",
        "permitted_provider_operation",
        "provider_id",
        "request_limit",
        "request_window_end_date",
        "request_window_start_date",
        "target_session_date",
    }
)
EVIDENCE_PAIR_INVENTORY = {
    ("authority_metadata", "metadata_json", "metadata_digest"): (
        "owned-insert",
        "authority_metadata_before_insert",
    ),
    ("schema_migrations", "migration_json", "migration_digest"): (
        "owned-insert",
        "schema_migrations_before_insert",
    ),
    ("sessions", "request_json", "request_digest"): (
        "owned-insert",
        "sessions_before_insert",
    ),
    ("attempts", "request_json", "request_digest"): (
        "copied-parent",
        "attempts_before_insert",
    ),
    (
        "attempts",
        "allocation_evidence_json",
        "allocation_evidence_digest",
    ): ("owned-insert", "attempts_before_insert"),
    ("attempts", "attempt_evidence_json", "attempt_evidence_digest"): (
        "owned-insert",
        "attempts_before_insert",
    ),
    ("provider_call_claims", "request_json", "request_digest"): (
        "copied-parent",
        "provider_call_claims_before_insert",
    ),
    (
        "provider_call_claims",
        "claim_evidence_json",
        "claim_evidence_digest",
    ): ("owned-insert", "provider_call_claims_before_insert"),
    (
        "launch_reservations",
        "reservation_evidence_json",
        "reservation_evidence_digest",
    ): ("owned-insert", "launch_reservations_before_insert"),
    ("launch_reservations", "process_intent_json", "process_intent_digest"): (
        "appended-update",
        "launch_reservations_process_intent_append_only",
    ),
    (
        "launch_reservations",
        "process_creation_failure_json",
        "process_creation_failure_digest",
    ): ("appended-update", "launch_reservations_failure_evidence_guard"),
    (
        "launch_executions",
        "process_creation_json",
        "process_creation_digest",
    ): ("owned-insert", "launch_executions_before_insert"),
    ("launch_executions", "job_object_json", "job_object_digest"): (
        "owned-insert",
        "launch_executions_before_insert",
    ),
    (
        "launch_executions",
        "resume_authorization_json",
        "resume_authorization_digest",
    ): ("owned-insert", "launch_executions_before_insert"),
    ("launch_executions", "resume_intent_json", "resume_intent_digest"): (
        "appended-update",
        "launch_executions_resume_intent_append_only",
    ),
    ("launch_executions", "post_resume_json", "post_resume_digest"): (
        "appended-update",
        "launch_executions_post_resume_append_only",
    ),
    ("launch_executions", "cleanup_json", "cleanup_digest"): (
        "appended-update",
        "launch_executions_cleanup_append_only",
    ),
    ("terminals", "evidence_json", "evidence_digest"): (
        "owned-insert",
        "terminals_before_insert",
    ),
    (
        "terminals",
        "sanitized_diagnostics_json",
        "sanitized_diagnostics_digest",
    ): ("owned-insert", "terminals_before_insert"),
    (
        "session_selections",
        "selection_evidence_json",
        "selection_evidence_digest",
    ): ("owned-insert", "session_selections_before_insert"),
    (
        "manual_recoveries",
        "operator_evidence_json",
        "operator_evidence_digest",
    ): ("owned-insert", "manual_recoveries_before_insert"),
}


@dataclass(frozen=True)
class _DependentDigestAudit:
    historical_trigger: str
    semantic_call_site: str
    historical_predicate: str
    evidence_pair: str
    service_owner: str
    checker: str


_DEPENDENT_DIGEST_AUDIT = (
    _DependentDigestAudit(
        "provider_call_claims_before_insert",
        "claim.retry_safe_prior.process_creation_failure",
        "sha256(safe_reservation.process_creation_failure_json) IS "
        "safe_reservation.process_creation_failure_digest",
        "launch_reservations.process_creation_failure",
        "commit_claim",
        "_validate_claim_admission_evidence",
    ),
    _DependentDigestAudit(
        "provider_call_claims_before_insert",
        "claim.retry_safe_prior.process_intent",
        "sha256(safe_reservation.process_intent_json) IS "
        "safe_reservation.process_intent_digest",
        "launch_reservations.process_intent",
        "commit_claim",
        "_validate_claim_admission_evidence",
    ),
    _DependentDigestAudit(
        "launch_reservations_failure_evidence_guard",
        "process_failure.failure_guard.parent_process_intent",
        "sha256(OLD.process_intent_json) IS OLD.process_intent_digest",
        "launch_reservations.process_intent",
        "record_process_creation_failure",
        "_record_process_creation_failure_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "process_intent_commit.new_process_intent",
        "sha256(NEW.process_intent_json) IS NEW.process_intent_digest",
        "launch_reservations.process_intent",
        "commit_process_intent",
        "_commit_process_intent_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "execution.transition.parent_process_intent",
        "sha256(OLD.process_intent_json) IS OLD.process_intent_digest",
        "launch_reservations.process_intent",
        "record_execution",
        "_record_execution_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "execution.transition.process_creation",
        "sha256(e.process_creation_json) IS e.process_creation_digest",
        "launch_executions.process_creation",
        "record_execution",
        "_record_execution_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "execution.transition.job_object",
        "sha256(e.job_object_json) IS e.job_object_digest",
        "launch_executions.job_object",
        "record_execution",
        "_record_execution_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "execution.transition.resume_authorization",
        "sha256(e.resume_authorization_json) IS e.resume_authorization_digest",
        "launch_executions.resume_authorization",
        "record_execution",
        "_record_execution_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "process_failure.state_guard.parent_process_intent",
        "sha256(OLD.process_intent_json) IS OLD.process_intent_digest",
        "launch_reservations.process_intent",
        "record_process_creation_failure",
        "_record_process_creation_failure_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "process_failure.new_failure_evidence",
        "sha256(NEW.process_creation_failure_json) IS "
        "NEW.process_creation_failure_digest",
        "launch_reservations.process_creation_failure",
        "record_process_creation_failure",
        "_record_process_creation_failure_locked",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "recovery.process_outcome_unknown.state_guard.process_intent",
        "sha256(OLD.process_intent_json) IS OLD.process_intent_digest",
        "launch_reservations.process_intent",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "launch_reservations_state_guard",
        "recovery.resume_outcome_unknown.state_guard.resume_intent",
        "sha256(e.resume_intent_json) IS e.resume_intent_digest",
        "launch_executions.resume_intent",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "launch_executions_parent_policy_before_insert",
        "execution.insert.parent_process_intent",
        "sha256(r.process_intent_json) IS r.process_intent_digest",
        "launch_reservations.process_intent",
        "record_execution",
        "_record_execution_locked",
    ),
    _DependentDigestAudit(
        "launch_executions_phase_guard",
        "resume_intent.commit.new_resume_intent",
        "sha256(NEW.resume_intent_json) IS NEW.resume_intent_digest",
        "launch_executions.resume_intent",
        "commit_resume_intent",
        "_commit_resume_intent_locked",
    ),
    _DependentDigestAudit(
        "launch_executions_phase_guard",
        "post_resume.record.post_resume",
        "sha256(NEW.post_resume_json) IS NEW.post_resume_digest",
        "launch_executions.post_resume",
        "record_post_resume_evidence",
        "_record_post_resume_evidence_locked",
    ),
    _DependentDigestAudit(
        "launch_executions_phase_guard",
        "post_resume.record.cleanup",
        "sha256(NEW.cleanup_json) IS NEW.cleanup_digest",
        "launch_executions.cleanup",
        "record_post_resume_evidence",
        "_record_post_resume_evidence_locked",
    ),
    _DependentDigestAudit(
        "terminals_before_insert",
        "terminal.failed_not_started.parent_process_intent",
        "sha256(r.process_intent_json) IS r.process_intent_digest",
        "launch_reservations.process_intent",
        "record_terminal",
        "_record_terminal_locked",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.attempt_ambiguity.post_resume",
        "sha256(e.post_resume_json) IS e.post_resume_digest",
        "launch_executions.post_resume",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.attempt_ambiguity.cleanup",
        "sha256(e.cleanup_json) IS e.cleanup_digest",
        "launch_executions.cleanup",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.claim_ambiguity.post_resume",
        "sha256(e.post_resume_json) IS e.post_resume_digest",
        "launch_executions.post_resume",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.claim_ambiguity.cleanup",
        "sha256(e.cleanup_json) IS e.cleanup_digest",
        "launch_executions.cleanup",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.process_outcome_unknown.manual_recovery.process_intent",
        "sha256(r.process_intent_json) IS r.process_intent_digest",
        "launch_reservations.process_intent",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.pre_resume_ready.process_creation",
        "sha256(e.process_creation_json) IS e.process_creation_digest",
        "launch_executions.process_creation",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.pre_resume_ready.job_object",
        "sha256(e.job_object_json) IS e.job_object_digest",
        "launch_executions.job_object",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.pre_resume_ready.resume_authorization",
        "sha256(e.resume_authorization_json) IS e.resume_authorization_digest",
        "launch_executions.resume_authorization",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.resume_outcome_unknown.process_creation",
        "sha256(e.process_creation_json) IS e.process_creation_digest",
        "launch_executions.process_creation",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.resume_outcome_unknown.job_object",
        "sha256(e.job_object_json) IS e.job_object_digest",
        "launch_executions.job_object",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.resume_outcome_unknown.resume_authorization",
        "sha256(e.resume_authorization_json) IS e.resume_authorization_digest",
        "launch_executions.resume_authorization",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
    _DependentDigestAudit(
        "manual_recoveries_before_insert",
        "recovery.resume_outcome_unknown.manual_recovery.resume_intent",
        "sha256(e.resume_intent_json) IS e.resume_intent_digest",
        "launch_executions.resume_intent",
        "record_recovery",
        "_validate_recovery_target_evidence",
    ),
)


class InterprocessLifecycleArbiter:
    """Test adapter for the deterministic OS-backed reservation arbiter."""

    LABEL = "lifecycle-arbiter/v1"

    def __init__(
        self,
        reservation_id: str,
        *,
        machine_authority_id: str = MACHINE,
        authority_epoch_id: str = EPOCH,
    ) -> None:
        reservation_id = str(reservation_id)
        material = json.dumps(
            {
                "authority_epoch_id": authority_epoch_id,
                "label": self.LABEL,
                "launch_reservation_id": reservation_id,
                "machine_authority_id": machine_authority_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.identity = hashlib.sha256(material).hexdigest()
        self.path = _LIFECYCLE_ARBITER_ROOT / f"{self.identity}.lock"
        self._stream: Any | None = None
        self._overlapped: Any | None = None

    def __enter__(self) -> InterprocessLifecycleArbiter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b", buffering=0)
        if os.name == "nt":
            self._lock_windows(stream)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        self._stream = stream
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            if os.name == "nt":
                self._unlock_windows(stream)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()
            self._stream = None
            self._overlapped = None

    def _lock_windows(self, stream: Any) -> None:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class Overlapped(ctypes.Structure):
            _fields_ = [
                ("Internal", ctypes.c_size_t),
                ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE),
            ]

        overlapped = Overlapped()
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
        lock_file_ex = ctypes.windll.kernel32.LockFileEx
        lock_file_ex.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(Overlapped),
        ]
        lock_file_ex.restype = wintypes.BOOL
        if not lock_file_ex(handle, 0x2, 0, 1, 0, ctypes.byref(overlapped)):
            stream.close()
            raise ctypes.WinError()
        self._overlapped = overlapped

    def _unlock_windows(self, stream: Any) -> None:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        overlapped = self._overlapped
        if overlapped is None:
            raise RuntimeError("Windows lifecycle arbiter was not acquired")
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno()))
        unlock_file_ex = ctypes.windll.kernel32.UnlockFileEx
        unlock_file_ex.restype = wintypes.BOOL
        if not unlock_file_ex(handle, 0, 1, 0, ctypes.byref(overlapped)):
            raise ctypes.WinError()


@contextmanager
def _mutated_frozen_object_for_test(
    value: object, **changes: object
) -> Iterator[object]:
    originals = {name: getattr(value, name) for name in changes}
    try:
        for name, replacement in changes.items():
            object.__setattr__(value, name, replacement)
        yield value
    finally:
        for name, original in originals.items():
            object.__setattr__(value, name, original)


def test_fixed_authority_timestamps_are_causally_ordered() -> None:
    assert (
        TIMESTAMP
        < PROCESS_INTENT_TIMESTAMP
        < PROCESS_CREATED_TIMESTAMP
        < RESUME_INTENT_TIMESTAMP
        < PROCESS_FAILURE_TIMESTAMP
        < MANUAL_REVIEW_TIMESTAMP
        < TERMINAL_TIMESTAMP
        < SELECTION_TIMESTAMP
        < CLOSE_TIMESTAMP
    )


def test_authority_values_are_sourced_from_public_alpaca_descriptor() -> None:
    assert ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id == "alpaca-market-data"
    assert (
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        == "historical-stock-bars-v2-raw-usd-no-asof"
    )
    assert (PROVIDER, OPERATION) == (
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
    )


def _frame(value: str) -> str:
    value = str(value)
    encoded = value.encode("utf-8")
    return f"{len(encoded)}:" + value


def _ordered_list(values: tuple[str, ...]) -> str:
    return _frame(str(len(values))) + "".join(_frame(value) for value in values)


def _identity(label: str, *values: str) -> str:
    material = _frame(label) + "".join(_frame(value) for value in values)
    return str(uuid.uuid5(NAMESPACE, material))


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _require_evidence_pair(
    evidence: bytes, digest: bytes, *, field: str = "evidence digest"
) -> None:
    require_evidence_digest(evidence, digest, field=field)


def _json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _evidence(label: str) -> tuple[bytes, bytes]:
    value = _json({"evidence": label, "schema": 1})
    return value, _digest(value)


TEST_SNAPSHOT_DIGEST = _digest(b"verified-snapshot")
TEST_OPERATOR_EVIDENCE_JSON, TEST_OPERATOR_EVIDENCE_DIGEST = _evidence(
    "explicit-test-operator-evidence"
)


def _insert_session_row_for_test(
    connection: sqlite3.Connection,
    session_id: str,
    request_bytes: bytes | str,
    *,
    target_session_date: str = "2026-01-01",
    request_digest: bytes | None = None,
) -> None:
    digest_material = (
        request_bytes.encode("utf-8") if type(request_bytes) is str else request_bytes
    )
    stored_digest = (
        _digest(digest_material) if request_digest is None else request_digest
    )
    _require_evidence_pair(
        digest_material, stored_digest, field="session request digest"
    )
    connection.execute(
        """
        INSERT INTO sessions (
            session_id, authority_epoch_id, session_schema,
            authority_policy_version, claim_policy_version,
            target_session_date, state, next_attempt_ordinal,
            next_recovery_ordinal, request_json, request_digest,
            created_at_utc, closed_at_utc, close_reason
        ) VALUES (?, ?, 1, ?, ?, ?, 'OPEN', 0, 0, ?, ?, ?, NULL, NULL)
        """,
        (
            session_id,
            EPOCH,
            POLICY,
            CLAIM_POLICY,
            target_session_date,
            request_bytes,
            stored_digest,
            TIMESTAMP,
        ),
    )


def _insert_attempt_row_for_test(
    connection: sqlite3.Connection,
    session_id: str,
    ordinal: int,
    request_bytes: bytes,
    request_digest: bytes,
    *,
    attempt_schema: int = 1,
    attempt_policy_version: str | None = None,
    provider_id: str | None = None,
    permitted_provider_operation: str | None = None,
    created_at_utc: str = TIMESTAMP,
) -> str:
    parent = connection.execute(
        """
        SELECT s.claim_policy_version, m.provider_id,
               m.permitted_provider_operation
        FROM sessions s
        JOIN authority_metadata m
          ON m.authority_epoch_id = s.authority_epoch_id
        WHERE s.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw attempt session")
    parent_policy, parent_provider, parent_operation = parent
    policy = parent_policy if attempt_policy_version is None else attempt_policy_version
    provider = parent_provider if provider_id is None else provider_id
    operation = (
        parent_operation
        if permitted_provider_operation is None
        else permitted_provider_operation
    )
    attempt_id = _attempt_id(session_id, ordinal, provider, operation, policy)
    allocation, allocation_digest = _evidence(f"raw-allocation:{ordinal}")
    attempt, attempt_digest = _evidence(f"raw-attempt:{ordinal}")
    _require_evidence_pair(
        request_bytes, request_digest, field="attempt request digest"
    )
    _require_evidence_pair(
        allocation, allocation_digest, field="attempt allocation digest"
    )
    _require_evidence_pair(attempt, attempt_digest, field="attempt evidence digest")
    connection.execute(
        """
        INSERT INTO attempts (
            attempt_id, session_id, ordinal, provider_id,
            permitted_provider_operation, provider_call_budget,
            request_json, request_digest, attempt_schema,
            attempt_policy_version, allocation_evidence_json,
            allocation_evidence_digest, attempt_evidence_json,
            attempt_evidence_digest, state, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'ALLOCATED', ?)
        """,
        (
            attempt_id,
            session_id,
            ordinal,
            provider,
            operation,
            request_bytes,
            request_digest,
            attempt_schema,
            policy,
            allocation,
            allocation_digest,
            attempt,
            attempt_digest,
            created_at_utc,
        ),
    )
    return attempt_id


def _insert_claim_row_for_test(
    connection: sqlite3.Connection,
    attempt_id: str,
    request_bytes: bytes,
    request_digest: bytes,
    *,
    claim_schema: int = 1,
    claim_policy_version: str | None = None,
    committed_at_utc: str = TIMESTAMP,
) -> str:
    parent = connection.execute(
        """
        SELECT attempt_policy_version, provider_id,
               permitted_provider_operation, provider_call_budget
        FROM attempts WHERE attempt_id = ?
        """,
        (attempt_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw claim attempt")
    parent_policy, provider_id, operation, budget = parent
    policy = parent_policy if claim_policy_version is None else claim_policy_version
    claim_id = _claim_id(attempt_id, policy, provider_id, operation, budget)
    evidence, evidence_digest = _evidence(f"raw-claim:{attempt_id}")
    _require_evidence_pair(request_bytes, request_digest, field="claim request digest")
    _require_evidence_pair(evidence, evidence_digest, field="claim evidence digest")
    connection.execute(
        """
        INSERT INTO provider_call_claims (
            claim_id, attempt_id, claim_schema, claim_policy_version,
            provider_id, permitted_provider_operation, provider_call_budget,
            request_json, request_digest, claim_evidence_json,
            claim_evidence_digest, state, committed_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED', ?)
        """,
        (
            claim_id,
            attempt_id,
            claim_schema,
            policy,
            provider_id,
            operation,
            budget,
            request_bytes,
            request_digest,
            evidence,
            evidence_digest,
            committed_at_utc,
        ),
    )
    return claim_id


def _insert_reservation_row_for_test(
    connection: sqlite3.Connection,
    claim_id: str,
    request_digest: bytes,
    reservation_state: str = "COMMITTED",
    failure_mode: bool = False,
    outcome_timestamp: str | None = None,
    *,
    launch_reservation_schema: int = 1,
    authority_policy_version: str | None = None,
    claim_policy_version: str | None = None,
    committed_at_utc: str = TIMESTAMP,
) -> str:
    parent = connection.execute(
        """
        SELECT c.claim_policy_version, s.authority_policy_version
             , a.request_json
        FROM provider_call_claims c
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE c.claim_id = ?
        """,
        (claim_id,),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw reservation claim")
    parent_claim_policy, parent_authority_policy, parent_request = parent
    claim_policy = (
        parent_claim_policy if claim_policy_version is None else claim_policy_version
    )
    authority_policy = (
        parent_authority_policy
        if authority_policy_version is None
        else authority_policy_version
    )
    reservation_id = _reservation_id(claim_id, RELEASE, authority_policy, claim_policy)
    evidence, evidence_digest = _evidence(f"raw-reservation:{claim_id}")
    failure = failure_digest = None
    if failure_mode:
        failure, failure_digest = _evidence(f"raw-failure:{claim_id}")
    _require_evidence_pair(
        parent_request, request_digest, field="reservation request digest"
    )
    _require_evidence_pair(
        evidence, evidence_digest, field="reservation evidence digest"
    )
    if failure is not None and failure_digest is not None:
        _require_evidence_pair(failure, failure_digest, field="process failure digest")
    connection.execute(
        """
        INSERT INTO launch_reservations (
            launch_reservation_id, claim_id, launch_reservation_schema,
            application_release_version, authority_policy_version,
            claim_policy_version, request_digest, reservation_evidence_json,
            reservation_evidence_digest, reservation_state,
            process_creation_failure_json, process_creation_failure_digest,
            committed_at_utc, outcome_recorded_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            reservation_id,
            claim_id,
            launch_reservation_schema,
            RELEASE,
            authority_policy,
            claim_policy,
            request_digest,
            evidence,
            evidence_digest,
            reservation_state,
            failure,
            failure_digest,
            committed_at_utc,
            outcome_timestamp,
        ),
    )
    return reservation_id


def _insert_terminal_row_for_test(
    connection: sqlite3.Connection,
    reservation_id: str,
    request_digest: bytes,
    state: str,
    disposition: str,
    snapshot_mode: str = "auto",
    *,
    terminal_schema: int = 1,
    evidence_json: bytes | None = None,
    evidence_digest: bytes | None = None,
    diagnostics_json: bytes | None = None,
    diagnostics_digest: bytes | None = None,
    recorded_at_utc: str = TERMINAL_TIMESTAMP,
) -> str:
    reservation_id = str(reservation_id)
    terminal_id = _terminal_id(reservation_id, TERMINAL_POLICY)
    generated_evidence, generated_evidence_digest = _evidence(
        f"raw-terminal:{reservation_id}"
    )
    generated_diagnostics, generated_diagnostics_digest = _evidence("raw-diagnostics")
    evidence = generated_evidence if evidence_json is None else evidence_json
    evidence_hash = (
        generated_evidence_digest if evidence_digest is None else evidence_digest
    )
    diagnostics = (
        generated_diagnostics if diagnostics_json is None else diagnostics_json
    )
    diagnostics_hash = (
        generated_diagnostics_digest
        if diagnostics_digest is None
        else diagnostics_digest
    )
    request_row = connection.execute(
        """
        SELECT a.request_json
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        WHERE r.launch_reservation_id = ?
        """,
        (reservation_id,),
    ).fetchone()
    if request_row is None:
        raise ValueError("unknown raw terminal reservation")
    _require_evidence_pair(
        request_row[0], request_digest, field="terminal request digest"
    )
    _require_evidence_pair(evidence, evidence_hash, field="terminal evidence digest")
    _require_evidence_pair(
        diagnostics, diagnostics_hash, field="terminal diagnostics digest"
    )
    snapshot = (
        TEST_SNAPSHOT_DIGEST
        if snapshot_mode == "present"
        or (snapshot_mode == "auto" and state == "SUCCEEDED")
        else None
    )
    connection.execute(
        """
        INSERT INTO terminals (
            terminal_id, launch_reservation_id, terminal_schema,
            terminal_policy_version, terminal_state,
            provider_call_disposition, request_digest, evidence_json,
            evidence_digest, snapshot_digest, sanitized_diagnostics_json,
            sanitized_diagnostics_digest, recorded_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            terminal_id,
            reservation_id,
            terminal_schema,
            TERMINAL_POLICY,
            state,
            disposition,
            request_digest,
            evidence,
            evidence_hash,
            snapshot,
            diagnostics,
            diagnostics_hash,
            recorded_at_utc,
        ),
    )
    return terminal_id


def _insert_execution_row_for_test(
    connection: sqlite3.Connection,
    reservation_id: str,
    *,
    launch_schema: int = 1,
    authority_policy_version: str | None = None,
    created_at_utc: str = PROCESS_CREATED_TIMESTAMP,
) -> str:
    reservation_id = str(reservation_id)
    parent = connection.execute(
        """
        SELECT application_release_version, authority_policy_version
        FROM launch_reservations WHERE launch_reservation_id = ?
        """,
        (str(reservation_id),),
    ).fetchone()
    if parent is None:
        raise ValueError("unknown raw execution reservation")
    application_release_version, parent_authority_policy = parent
    authority_policy = (
        parent_authority_policy
        if authority_policy_version is None
        else authority_policy_version
    )
    execution_id = _execution_id(
        reservation_id, application_release_version, authority_policy
    )
    process, process_digest = _evidence(f"raw-process:{reservation_id}")
    job, job_digest = _evidence(f"raw-job:{reservation_id}")
    resume, resume_digest = _evidence(f"raw-resume:{reservation_id}")
    _require_evidence_pair(process, process_digest, field="process creation digest")
    _require_evidence_pair(job, job_digest, field="job object digest")
    _require_evidence_pair(resume, resume_digest, field="resume authorization digest")
    connection.execute(
        """
        INSERT INTO launch_executions (
            launch_execution_id, launch_reservation_id, launch_schema,
            application_release_version, authority_policy_version, phase,
            process_creation_json, process_creation_digest, job_object_json,
            job_object_digest, resume_authorization_json,
            resume_authorization_digest, resume_intent_json,
            resume_intent_digest, resume_intent_committed_at_utc,
            post_resume_json, post_resume_digest, cleanup_json,
            cleanup_digest, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, 'PRE_RESUME_READY', ?, ?, ?, ?, ?, ?,
                  NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (
            execution_id,
            reservation_id,
            launch_schema,
            application_release_version,
            authority_policy,
            process,
            process_digest,
            job,
            job_digest,
            resume,
            resume_digest,
            created_at_utc,
        ),
    )
    return execution_id


def _request(target_date: str = "2026-01-01") -> dict[str, Any]:
    return {
        "bar_interval": "1d",
        "child_operation_version": "child/v1",
        "ordered_universe": ["QQQ", "SPY"],
        "output_policy_version": "output/v1",
        "permitted_provider_operation": OPERATION,
        "provider_id": PROVIDER,
        "request_limit": 2,
        "request_window_end_date": "2025-12-31",
        "request_window_start_date": "2025-12-01",
        "target_session_date": target_date,
    }


def _session_id(
    request: ValidatedCaptureRequest,
    *,
    machine_authority_id: str,
    authority_epoch_id: str,
    authority_policy_version: str,
    claim_policy_version: str,
) -> str:
    return _identity(
        "session_id/v2",
        machine_authority_id,
        authority_epoch_id,
        "1",
        authority_policy_version,
        claim_policy_version,
        "capture_request/v2",
        request.target_session_date,
        request.provider_id,
        request.permitted_provider_operation,
        _ordered_list(request.ordered_universe),
        request.bar_interval,
        request.request_window_start_date,
        request.request_window_end_date,
        str(request.request_limit),
        request.child_operation_version,
        request.output_policy_version,
    )


def _canonical_ordinal(value: object, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be an exact non-negative int")
    return value


def _attempt_id(
    session_id: str,
    ordinal: int,
    provider_id: str,
    permitted_provider_operation: str,
    attempt_policy_version: str,
) -> str:
    ordinal = _canonical_ordinal(ordinal, "attempt ordinal")
    return _identity(
        "attempt_id/v2",
        session_id,
        str(ordinal),
        provider_id,
        permitted_provider_operation,
        "1",
        attempt_policy_version,
    )


def _claim_id(
    attempt_id: str,
    claim_policy_version: str,
    provider_id: str,
    permitted_provider_operation: str,
    provider_call_budget: int,
) -> str:
    return _identity(
        "claim_id/v2",
        attempt_id,
        "1",
        claim_policy_version,
        provider_id,
        permitted_provider_operation,
        str(provider_call_budget),
    )


def _reservation_id(
    claim_id: str,
    application_release_version: str,
    authority_policy_version: str,
    claim_policy_version: str,
) -> str:
    return _identity(
        "launch_reservation_id/v2",
        claim_id,
        "1",
        application_release_version,
        authority_policy_version,
        claim_policy_version,
    )


def _execution_id(
    reservation_id: str,
    application_release_version: str,
    authority_policy_version: str,
) -> str:
    return _identity(
        "launch_execution_id/v2",
        reservation_id,
        "1",
        application_release_version,
        authority_policy_version,
    )


def _terminal_id(reservation_id: str, terminal_policy_version: str) -> str:
    return _identity("terminal_id/v2", reservation_id, "1", terminal_policy_version)


def _selection_id(
    session_id: str, terminal_id: str, selection_policy_version: str
) -> str:
    return _identity(
        "selection_id/v2",
        session_id,
        terminal_id,
        "1",
        selection_policy_version,
    )


def _recovery_id(
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    predecessor_state: str,
    resulting_state: str,
    ordinal: int,
    recovery_policy_version: str,
) -> str:
    ordinal = _canonical_ordinal(ordinal, "recovery ordinal")
    return _identity(
        "recovery_id/v2",
        session_id,
        target_kind,
        target_id,
        action,
        predecessor_state,
        resulting_state,
        "1",
        recovery_policy_version,
        str(ordinal),
    )


def _raw_connection_for_test(
    connection: sqlite3.Connection | DisposableAuthorityDatabaseForTest,
) -> sqlite3.Connection:
    if type(connection) is DisposableAuthorityDatabaseForTest:
        return connection._connection
    return connection


def _connect(path: Path) -> sqlite3.Connection:
    """Open a harness-owned file database for cross-process Architecture-77 tests."""

    connection = sqlite3.connect(
        path,
        timeout=5.0,
        isolation_level=None,
        check_same_thread=False,
    )
    try:
        configure_trusted_schema_off(connection)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        harness = _CURRENT_HARNESS.get()
        if harness is not None and path.resolve(strict=False) == harness.database_path:
            harness._register_connection(connection)
        return connection
    except BaseException:
        connection.close()
        raise


def _install_schema(
    connection: sqlite3.Connection | DisposableAuthorityDatabaseForTest,
) -> None:
    raw_connection = _raw_connection_for_test(connection)
    execute_schema_artifact(raw_connection)
    raw_connection.execute("PRAGMA foreign_keys = ON")


def test_transactional_harness_uses_pinned_packaged_production_artifact() -> None:
    assert SCHEMA_BYTES is PRODUCTION_SCHEMA_ARTIFACT_BYTES
    assert len(SCHEMA_BYTES) == 118_896
    assert hashlib.sha256(SCHEMA_BYTES).hexdigest() == SCHEMA_SHA256
    assert SCHEMA_SHA256 == (
        "aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58"
    )
    assert b"\r" not in SCHEMA_BYTES
    assert b"sha256(" not in SCHEMA_BYTES.lower()
    assert not (
        _HARNESS_REPOSITORY_ROOT
        / "tests"
        / "fixtures"
        / "transactional_authority_schema.sql"
    ).exists()
    connection = sqlite3.connect(":memory:")
    try:
        _install_schema(connection)
        assert connection.execute("PRAGMA trusted_schema").fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone() == (10,)
        with pytest.raises(sqlite3.OperationalError, match="no such function"):
            connection.execute("SELECT sha256(?)", (b"test-only-udf",)).fetchone()
    finally:
        connection.close()


def _insert_metadata(
    connection: sqlite3.Connection,
    *,
    provider_id: str = PROVIDER,
    permitted_provider_operation: str = OPERATION,
    authority_policy_version: str = POLICY,
    claim_policy_version: str = CLAIM_POLICY,
    created_at_utc: str = TIMESTAMP,
) -> None:
    metadata_values = {
        "approved_account_sid": "S-1-5-21-111-222-333-444",
        "authority_epoch_id": EPOCH,
        "authority_policy_version": authority_policy_version,
        "bootstrap_digest": _digest(b"bootstrap").hex(),
        "bootstrap_generation": 1,
        "bootstrap_schema": 1,
        "claim_policy_version": claim_policy_version,
        "created_at_utc": created_at_utc,
        "database_identity_digest": _digest(b"database").hex(),
        "initialization_policy_version": INITIALIZATION_POLICY_VERSION,
        "machine_authority_id": MACHINE,
        "metadata_encoding_version": METADATA_ENCODING_VERSION,
        "production_schema_digest": SCHEMA_SHA256,
        "production_schema_id": PRODUCTION_SCHEMA_ID,
        "production_schema_version": PRODUCTION_SCHEMA_VERSION,
        "provider_id": provider_id,
        "permitted_provider_operation": permitted_provider_operation,
        "signing_key_id": "test-signing-key/v1",
        "singleton_key": 1,
    }
    metadata = _json(metadata_values)
    _require_evidence_pair(metadata, _digest(metadata), field="metadata digest")
    connection.execute(
        """
        INSERT INTO authority_metadata (
            authority_epoch_id, machine_authority_id, bootstrap_schema,
            bootstrap_generation, signing_key_id, approved_account_sid,
            provider_id, permitted_provider_operation, authority_policy_version,
            claim_policy_version, created_at_utc, bootstrap_digest,
            database_identity_digest, metadata_json, metadata_digest,
            production_schema_id, production_schema_version,
            production_schema_digest, metadata_encoding_version,
            initialization_policy_version, singleton_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            EPOCH,
            MACHINE,
            1,
            1,
            "test-signing-key/v1",
            "S-1-5-21-111-222-333-444",
            provider_id,
            permitted_provider_operation,
            authority_policy_version,
            claim_policy_version,
            created_at_utc,
            _digest(b"bootstrap"),
            _digest(b"database"),
            metadata,
            _digest(metadata),
            PRODUCTION_SCHEMA_ID,
            PRODUCTION_SCHEMA_VERSION,
            bytes.fromhex(SCHEMA_SHA256),
            METADATA_ENCODING_VERSION,
            INITIALIZATION_POLICY_VERSION,
            1,
        ),
    )


def _insert_migration(
    connection: sqlite3.Connection, *, applied_at_utc: str = TIMESTAMP
) -> str:
    migration_id = _identity(
        "migration_id/v1", EPOCH, str(PRODUCTION_SCHEMA_VERSION), "migration-policy/v1"
    )
    evidence = _json(
        {
            "application_release_digest": _digest(b"release").hex(),
            "applied_at_utc": applied_at_utc,
            "authority_epoch_id": EPOCH,
            "initialization_policy_version": INITIALIZATION_POLICY_VERSION,
            "migration_id": migration_id,
            "migration_policy_version": "migration-policy/v1",
            "production_schema_digest": SCHEMA_SHA256,
            "production_schema_id": PRODUCTION_SCHEMA_ID,
            "schema_version": PRODUCTION_SCHEMA_VERSION,
        }
    )
    evidence_digest = _digest(evidence)
    _require_evidence_pair(evidence, evidence_digest, field="migration digest")
    connection.execute(
        """
        INSERT INTO schema_migrations (
            migration_id, authority_epoch_id, schema_version,
            migration_policy_version, migration_digest,
            application_release_digest, migration_json, applied_at_utc
        ) VALUES (?, ?, ?, 'migration-policy/v1', ?, ?, ?, ?)
        """,
        (
            migration_id,
            EPOCH,
            PRODUCTION_SCHEMA_VERSION,
            evidence_digest,
            _digest(b"release"),
            evidence,
            applied_at_utc,
        ),
    )
    return migration_id


def _require_no_active_transaction(
    connection: sqlite3.Connection | DisposableAuthorityDatabaseForTest,
) -> None:
    raw_connection = _raw_connection_for_test(connection)
    if type(raw_connection) is not sqlite3.Connection:
        raise TypeError("lifecycle boundary requires an exact sqlite3.Connection")
    if raw_connection.in_transaction:
        raise ValueError("lifecycle boundary requires no active SQLite transaction")


def _begin(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")


def _finish(connection: sqlite3.Connection, commit: bool) -> None:
    (connection.commit if commit else connection.rollback)()


def _current_lifecycle_arbiter(reservation_id: str):
    return InterprocessLifecycleArbiter(reservation_id)


@dataclass(frozen=True, slots=True)
class Architecture77HarnessDescriptor:
    root: str
    database_path: str


class HarnessLifecycleError(RuntimeError):
    """A reviewed Architecture-77 harness lifecycle has been closed or invalid."""


_HARNESS_CONSTRUCTOR_TOKEN = object()
_CURRENT_HARNESS: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "architecture77_harness", default=None
)


class Architecture77HarnessAuthority:
    """Own one explicit file-backed Architecture-77 test lifecycle."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        capture_request_factory: Callable[[object], ValidatedCaptureRequest]
        | None = None,
        *,
        root: Path,
        _construction_token: object,
        _service_token: object | None = None,
        _owner: Architecture77HarnessAuthority | None = None,
        _cleanup_root: bool = True,
    ) -> None:
        if _construction_token is not _HARNESS_CONSTRUCTOR_TOKEN:
            raise TypeError(
                "Architecture-77 harness instances require an explicit factory"
            )
        if type(connection) is not sqlite3.Connection:
            raise TypeError(
                "Architecture-77 harness requires an exact sqlite3.Connection"
            )
        resolved_root = root.resolve(strict=True)
        if not resolved_root.is_dir():
            raise HarnessLifecycleError("harness root is not a directory")
        self._connection = connection
        self._root = resolved_root
        self._database_path = (resolved_root / "authority.sqlite3").resolve(
            strict=False
        )
        self._owner = self if _owner is None else _owner
        self._service_token = object() if _service_token is None else _service_token
        self._cleanup_root = _cleanup_root if _owner is None else False
        self._capture_request_factory = capture_request_factory
        self._closed = False
        if _owner is None:
            self._connections: dict[int, sqlite3.Connection] = {}
            self._bindings: list[TransactionalAuthorityCoreBinding] = []
        self._register_connection(connection)
        self._core_binding_issuer = (
            TransactionalAuthorityCoreBinding.create_harness_issuer(self)
        )
        self._core_binding = TransactionalAuthorityCoreBinding.issue_for_harness(
            self._core_binding_issuer
        )
        self._owner._bindings.append(self._core_binding)
        self._core = TransactionalAuthorityCore.from_harness_binding(self._core_binding)

    @classmethod
    def create(cls) -> Architecture77HarnessAuthority:
        root = Path(tempfile.mkdtemp(prefix="ai-trading-bot-arch77-"))
        path = root / "authority.sqlite3"
        connection: sqlite3.Connection | None = None
        try:
            connection = _connect(path)
            _install_schema(connection)
            _insert_metadata(connection)
            _insert_migration(connection)
            instance = cls(
                connection,
                root=root,
                _construction_token=_HARNESS_CONSTRUCTOR_TOKEN,
            )
            instance._validate_storage()
            return instance
        except BaseException:
            if connection is not None:
                connection.close()
            shutil.rmtree(root, ignore_errors=True)
            raise

    @classmethod
    def open_from_descriptor(
        cls, descriptor: Architecture77HarnessDescriptor
    ) -> Architecture77HarnessAuthority:
        """Open a fresh child-process lifecycle from the factory descriptor."""

        if type(descriptor) is not Architecture77HarnessDescriptor:
            raise HarnessLifecycleError("spawn requires an Architecture-77 descriptor")
        database_path = Path(descriptor.database_path).resolve(strict=False)
        if database_path == Path(PRODUCTION_AUTHORITY_PATHS.database).resolve():
            raise HarnessLifecycleError(
                "descriptor selected the production authority path"
            )
        try:
            root = Path(descriptor.root).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise HarnessLifecycleError("descriptor root is unavailable") from exc
        expected_path = (root / "authority.sqlite3").resolve(strict=False)
        if database_path != expected_path:
            raise HarnessLifecycleError("descriptor database escaped its harness root")
        if not database_path.is_file():
            raise HarnessLifecycleError("descriptor database is unavailable")
        connection: sqlite3.Connection | None = None
        try:
            connection = _connect(database_path)
            instance = cls(
                connection,
                root=root,
                _construction_token=_HARNESS_CONSTRUCTOR_TOKEN,
                _cleanup_root=False,
            )
            instance._validate_storage()
            return instance
        except BaseException:
            if connection is not None:
                connection.close()
            raise

    @property
    def database_path(self) -> Path:
        self._require_open()
        return self._database_path

    @property
    def descriptor(self) -> Architecture77HarnessDescriptor:
        self._require_open()
        return Architecture77HarnessDescriptor(
            root=str(self._root), database_path=str(self.database_path)
        )

    def _require_open(self) -> None:
        if self._owner._closed:
            raise HarnessLifecycleError("Architecture-77 harness lifecycle is closed")

    def _register_connection(self, connection: sqlite3.Connection) -> None:
        self._require_open()
        if type(connection) is not sqlite3.Connection:
            raise TypeError("harness binding requires an exact sqlite3.Connection")
        try:
            connection.execute("SELECT 1")
        except sqlite3.ProgrammingError as exc:
            raise HarnessLifecycleError("harness connection is closed") from exc
        self._validate_connection(connection)
        self._owner._connections[id(connection)] = connection

    def _issue_transactional_core_binding(
        self,
        issuer: object,
    ) -> tuple[
        sqlite3.Connection,
        Callable[[str], AbstractContextManager[object]],
        Callable[[object], ValidatedCaptureRequest] | None,
        None,
        object,
    ]:
        """Return reviewed components to the supported core binding issuer."""

        self._require_open()
        if issuer is not self._core_binding_issuer:
            raise TypeError(
                "harness core binding issuer is not owned by this lifecycle"
            )
        self._validate_connection(self._connection)
        return (
            self._connection,
            _current_lifecycle_arbiter,
            self._capture_request_factory,
            None,
            self._owner._service_token,
        )

    def _validate_connection(self, connection: sqlite3.Connection) -> None:
        try:
            rows = connection.execute("PRAGMA database_list").fetchall()
            if len(rows) != 1 or rows[0][1] != "main":
                raise HarnessLifecycleError(
                    "harness database must have exactly one main database"
                )
            opened_path = str(rows[0][2])
            if not opened_path or Path(opened_path).resolve() != self._database_path:
                raise HarnessLifecycleError(
                    "harness connection identity mismatches descriptor"
                )
            schema = connection.execute(
                "SELECT production_schema_id, production_schema_version, "
                "production_schema_digest FROM authority_metadata "
                "WHERE singleton_key = 1"
            ).fetchone()
        except sqlite3.Error as exc:
            raise HarnessLifecycleError(
                "harness database schema is unavailable"
            ) from exc
        if schema != (
            PRODUCTION_SCHEMA_ID,
            PRODUCTION_SCHEMA_VERSION,
            bytes.fromhex(SCHEMA_SHA256),
        ):
            raise HarnessLifecycleError(
                "harness database schema identity is not reviewed"
            )

    def bind_connection(
        self,
        connection: sqlite3.Connection,
        capture_request_factory: Callable[[object], ValidatedCaptureRequest]
        | None = None,
    ) -> Architecture77HarnessAuthority:
        self._register_connection(connection)
        return type(self)(
            connection,
            capture_request_factory,
            root=self._root,
            _construction_token=_HARNESS_CONSTRUCTOR_TOKEN,
            _service_token=self._service_token,
            _owner=self._owner,
            _cleanup_root=False,
        )

    def open_connection(self) -> sqlite3.Connection:
        self._require_open()
        return _connect(self.database_path)

    def _validate_storage(self) -> None:
        root = self._root
        if self.database_path.parent != root:
            raise AssertionError("harness database escaped its private temporary root")
        if self.database_path == Path(PRODUCTION_AUTHORITY_PATHS.database).resolve():
            raise AssertionError(
                "harness database selected the production authority path"
            )
        self._validate_connection(self._connection)

    def close(self) -> None:
        owner = self._owner
        if owner._closed:
            return
        owner._closed = True
        close_error = HarnessLifecycleError(
            "Architecture-77 harness lifecycle is closed"
        )
        for binding in tuple(owner._bindings):
            binding.invalidate_for_harness_close(close_error)
        owner._bindings.clear()
        for connection in tuple(owner._connections.values()):
            try:
                connection.execute("SELECT 1")
            except sqlite3.ProgrammingError:
                pass
            else:
                connection.close()
        owner._connections.clear()
        if owner._cleanup_root:
            shutil.rmtree(owner._root, ignore_errors=True)

    @contextmanager
    def bind_external_effects(self) -> Iterator[None]:
        self._require_open()
        with self._core.bind_external_effects():
            yield

    def _acquire_lifecycle_lease(self, reservation_id: str) -> object:
        self._require_open()
        return self._core_binding.acquire_lifecycle_lease(self._core, reservation_id)

    def _release_lifecycle_lease(self, lease: object, *args: object) -> None:
        self._core_binding.release_lifecycle_lease(lease, *args)

    def _core_for_use(self) -> TransactionalAuthorityCore:
        self._require_open()
        return self._core

    def require_test_capability(self, capability: object) -> None:
        self._require_open()
        self._core.require_test_capability(capability)

    def lifecycle_lease(self, reservation_id: str) -> TestLifecycleLease:
        self._require_open()
        return TestLifecycleLease(self, reservation_id)

    def create_session(
        self, request: dict[str, Any], *, created_at_utc: str = TIMESTAMP
    ) -> str:
        self._require_open()
        return self._core.create_session(request, created_at_utc=created_at_utc)

    def allocate_attempt(
        self,
        session_id: str,
        ordinal: int | None = None,
        *,
        created_at_utc: str = TIMESTAMP,
    ) -> str:
        self._require_open()
        return self._core.allocate_attempt(
            session_id, ordinal=ordinal, created_at_utc=created_at_utc
        )

    def commit_claim(
        self, attempt_id: str, *, committed_at_utc: str = TIMESTAMP
    ) -> str:
        self._require_open()
        return self._core.commit_claim(attempt_id, committed_at_utc=committed_at_utc)

    def reserve_launch(
        self, claim_id: str, *, committed_at_utc: str = TIMESTAMP
    ) -> FakeProviderConstructionPermit:
        self._require_open()
        return self._core.reserve_launch(claim_id, committed_at_utc=committed_at_utc)

    def commit_process_intent(
        self, reservation_id: str, provider: FakeConstructedProvider | None = None
    ) -> FakeProcessIntent:
        self._require_open()
        return self._core.commit_process_intent(  # type: ignore[arg-type]
            reservation_id, provider
        )

    def record_execution(
        self, reservation_id: str, receipt: FakeProcessCreationReceipt
    ) -> str:
        self._require_open()
        return self._core.record_execution(reservation_id, receipt)

    def commit_resume_intent(
        self, execution_id: str, reservation_id: str
    ) -> FakeResumeIntent:
        self._require_open()
        return self._core.commit_resume_intent(execution_id, reservation_id)

    def record_process_creation_failure(
        self, reservation_id: str, failure: FakeProcessCreationFailure
    ) -> None:
        self._require_open()
        return self._core.record_process_creation_failure(reservation_id, failure)

    def record_post_resume_evidence(
        self, execution_id: str, resume_receipt: FakeResumeReceipt
    ) -> None:
        self._require_open()
        return self._core.record_post_resume_evidence(execution_id, resume_receipt)

    def record_terminal(
        self,
        reservation_id: str,
        state: str = "SUCCEEDED",
        disposition: str = "CONFIRMED",
        *,
        snapshot_digest: bytes | None,
    ) -> str:
        self._require_open()
        return self._core.record_terminal(
            reservation_id,
            state,
            disposition,
            snapshot_digest=snapshot_digest,
        )

    def record_recovery(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        action: str,
        ordinal: int | None = None,
        *,
        operator_evidence_json: bytes,
        operator_evidence_digest: bytes,
    ) -> str:
        self._require_open()
        if ordinal is not None:
            _canonical_ordinal(ordinal, "recovery ordinal")
        _require_no_active_transaction(self._connection)
        return self._core.record_recovery(
            session_id,
            target_kind,
            target_id,
            action,
            ordinal,
            operator_evidence_json=operator_evidence_json,
            operator_evidence_digest=operator_evidence_digest,
        )


class TestLifecycleLease:
    """Explicit named-operation lease for already-held arbiter tests."""

    __test__ = False

    def __init__(
        self, authority: Architecture77HarnessAuthority, reservation_id: str
    ) -> None:
        authority._require_open()
        self._authority = authority
        self._reservation_id = str(reservation_id)
        self._core_lease: object | None = None
        self._entered = False
        self._exited = False
        self._execution_ids: set[str] = set()

    def _require_active(self) -> object:
        self._authority._require_open()
        if not self._entered or self._exited or self._core_lease is None:
            raise HarnessLifecycleError("lifecycle lease is not active")
        return self._core_lease

    def _require_reservation(self, reservation_id: str) -> object:
        witness = self._require_active()
        if str(reservation_id) != self._reservation_id:
            raise ValueError(
                "operation reservation does not match held lifecycle lease"
            )
        return witness

    def __enter__(self) -> TestLifecycleLease:
        if self._entered or self._exited:
            raise HarnessLifecycleError("lifecycle lease cannot be re-entered")
        self._authority._require_open()
        try:
            self._core_lease = self._authority._acquire_lifecycle_lease(
                self._reservation_id
            )
            self._entered = True
            return self
        except BaseException:
            self._core_lease = None
            raise

    def __exit__(self, *args: object) -> None:
        if self._core_lease is None:
            if self._exited:
                raise HarnessLifecycleError("lifecycle lease was already exited")
            return None
        lease = self._core_lease
        self._core_lease = None
        self._exited = True
        self._authority._release_lifecycle_lease(lease, *args)

    def bind_execution(self, execution_id: str) -> None:
        witness = self._require_active()
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("lifecycle lease requires a canonical execution id")
        self._authority._core_for_use().require_execution_binding_while_held(
            execution_id,
            self._reservation_id,
            lease_witness=witness,
        )
        self._execution_ids.add(execution_id)

    def record_execution(
        self, reservation_id: str, receipt: FakeProcessCreationReceipt
    ) -> str:
        witness = self._require_reservation(reservation_id)
        return self._authority._core_for_use().record_execution_while_held(
            reservation_id, receipt, lease_witness=witness
        )

    def commit_process_intent(
        self, reservation_id: str, provider: FakeConstructedProvider
    ) -> FakeProcessIntent:
        witness = self._require_reservation(reservation_id)
        return self._authority._core_for_use().commit_process_intent_while_held(
            reservation_id, provider, lease_witness=witness
        )

    def commit_resume_intent(
        self, execution_id: str, reservation_id: str
    ) -> FakeResumeIntent:
        witness = self._require_reservation(reservation_id)
        result = self._authority._core_for_use().commit_resume_intent_while_held(
            execution_id, reservation_id, lease_witness=witness
        )
        self._execution_ids.add(execution_id)
        return result

    def record_process_creation_failure(
        self, reservation_id: str, failure: FakeProcessCreationFailure
    ) -> None:
        witness = self._require_reservation(reservation_id)
        return (
            self._authority._core_for_use().record_process_creation_failure_while_held(
                reservation_id, failure, lease_witness=witness
            )
        )

    def record_post_resume_evidence(
        self, execution_id: str, receipt: FakeResumeReceipt
    ) -> None:
        witness = self._require_active()
        if execution_id not in self._execution_ids:
            raise ValueError("execution is not bound to the held lifecycle lease")
        return self._authority._core_for_use().record_post_resume_evidence_while_held(
            execution_id, receipt, lease_witness=witness
        )

    def record_terminal(
        self,
        reservation_id: str,
        state: str = "SUCCEEDED",
        disposition: str = "CONFIRMED",
        *,
        snapshot_digest: bytes | None,
    ) -> str:
        witness = self._require_reservation(reservation_id)
        return self._authority._core_for_use().record_terminal_while_held(
            reservation_id,
            state,
            disposition,
            snapshot_digest=snapshot_digest,
            lease_witness=witness,
        )

    def record_recovery(
        self,
        session_id: str,
        target_kind: str,
        target_id: str,
        action: str,
        ordinal: int | None = None,
        *,
        operator_evidence_json: bytes,
        operator_evidence_digest: bytes,
    ) -> str:
        witness = self._require_active()
        return self._authority._core_for_use().record_recovery_while_held(
            session_id,
            target_kind,
            target_id,
            action,
            ordinal,
            operator_evidence_json=operator_evidence_json,
            operator_evidence_digest=operator_evidence_digest,
            lease_witness=witness,
        )


def _test_service(
    connection: sqlite3.Connection,
    *,
    capture_request_factory: Callable[[object], ValidatedCaptureRequest] | None = None,
) -> Architecture77HarnessAuthority:
    harness = _CURRENT_HARNESS.get()
    if harness is None:
        raise HarnessLifecycleError(
            "test service requires an explicitly bound Architecture-77 harness"
        )
    return harness.bind_connection(connection, capture_request_factory)


def create_session(
    connection: sqlite3.Connection,
    request: dict[str, Any] | None = None,
    *,
    created_at_utc: str = TIMESTAMP,
) -> str:
    return _test_service(connection).create_session(
        _request() if request is None else request, created_at_utc=created_at_utc
    )


def allocate_attempt(
    connection: sqlite3.Connection,
    session_id: str,
    ordinal: int | None = None,
    *,
    created_at_utc: str = TIMESTAMP,
) -> str:
    return _test_service(connection).allocate_attempt(
        session_id, ordinal, created_at_utc=created_at_utc
    )


def commit_claim(
    connection: sqlite3.Connection,
    attempt_id: str,
    *,
    committed_at_utc: str = TIMESTAMP,
) -> str:
    return _test_service(connection).commit_claim(
        attempt_id, committed_at_utc=committed_at_utc
    )


def reserve_launch(
    connection: sqlite3.Connection,
    claim_id: str,
    *,
    committed_at_utc: str = TIMESTAMP,
) -> FakeProviderConstructionPermit:
    return _test_service(connection).reserve_launch(
        claim_id, committed_at_utc=committed_at_utc
    )


def commit_process_intent(
    connection: sqlite3.Connection,
    reservation_id: str,
    provider: FakeConstructedProvider | None = None,
) -> FakeProcessIntent:
    return _test_service(connection).commit_process_intent(reservation_id, provider)


def record_execution(
    connection: sqlite3.Connection,
    reservation_id: str,
    receipt: FakeProcessCreationReceipt,
) -> str:
    return _test_service(connection).record_execution(reservation_id, receipt)


def commit_resume_intent(
    connection: sqlite3.Connection,
    execution_id: str,
    reservation_id: str,
) -> FakeResumeIntent:
    return _test_service(connection).commit_resume_intent(execution_id, reservation_id)


def record_process_creation_failure(
    connection: sqlite3.Connection,
    reservation_id: str,
    failure: FakeProcessCreationFailure,
) -> None:
    return _test_service(connection).record_process_creation_failure(
        reservation_id, failure
    )


def record_post_resume_evidence(
    connection: sqlite3.Connection,
    execution_id: str,
    resume_receipt: FakeResumeReceipt,
) -> None:
    return _test_service(connection).record_post_resume_evidence(
        execution_id, resume_receipt
    )


def record_terminal(
    connection: sqlite3.Connection,
    reservation_id: str,
    state: str = "SUCCEEDED",
    disposition: str = "CONFIRMED",
    *,
    snapshot_digest: bytes | None,
) -> str:
    return _test_service(connection).record_terminal(
        reservation_id,
        state,
        disposition,
        snapshot_digest=snapshot_digest,
    )


def select_terminal(
    connection: sqlite3.Connection, session_id: str, terminal_id: str
) -> str:
    return _test_service(connection)._core.select_terminal(session_id, terminal_id)


def record_recovery(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    ordinal: int | None = None,
    *,
    operator_evidence_json: bytes,
    operator_evidence_digest: bytes,
) -> str:
    return _test_service(connection).record_recovery(
        session_id,
        target_kind,
        target_id,
        action,
        ordinal,
        operator_evidence_json=operator_evidence_json,
        operator_evidence_digest=operator_evidence_digest,
    )


def _insert_selection_row_for_test(
    connection: sqlite3.Connection,
    session_id: str,
    terminal_id: str,
    *,
    selection_schema: int = 1,
    selected_at_utc: str = SELECTION_TIMESTAMP,
) -> str:
    snapshot = connection.execute(
        "SELECT snapshot_digest FROM terminals WHERE terminal_id = ?", (terminal_id,)
    ).fetchone()
    if snapshot is None or snapshot[0] is None:
        raise ValueError("terminal has no snapshot")
    selection_id = _selection_id(session_id, terminal_id, SELECTION_POLICY)
    evidence, evidence_digest = _evidence(f"raw-selection:{terminal_id}")
    _require_evidence_pair(evidence, evidence_digest, field="selection evidence digest")
    connection.execute(
        """
        INSERT INTO session_selections (
            selection_id, session_id, terminal_id, selection_schema,
            selection_policy_version, snapshot_digest,
            selection_evidence_json, selection_evidence_digest,
            selected_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            selection_id,
            session_id,
            terminal_id,
            selection_schema,
            SELECTION_POLICY,
            snapshot[0],
            evidence,
            evidence_digest,
            selected_at_utc,
        ),
    )
    return selection_id


def _target_state(
    connection: sqlite3.Connection, target_kind: str, target_id: str
) -> str:
    table, identity_column = {
        "SESSION": ("sessions", "session_id"),
        "ATTEMPT": ("attempts", "attempt_id"),
        "CLAIM": ("provider_call_claims", "claim_id"),
        "LAUNCH_RESERVATION": ("launch_reservations", "launch_reservation_id"),
        "TERMINAL": ("terminals", "terminal_id"),
    }[target_kind]
    state_column = {
        "SESSION": "state",
        "ATTEMPT": "state",
        "CLAIM": "state",
        "LAUNCH_RESERVATION": "reservation_state",
        "TERMINAL": "terminal_state",
    }[target_kind]
    row = connection.execute(
        f"SELECT {state_column} FROM {table} WHERE {identity_column} = ?", (target_id,)
    ).fetchone()
    if row is None:
        raise ValueError("unknown recovery target")
    return row[0]


def test_dependent_digest_audit_accounts_for_all_29_call_sites() -> None:
    assert len(_DEPENDENT_DIGEST_AUDIT) == 29
    assert len({entry.semantic_call_site for entry in _DEPENDENT_DIGEST_AUDIT}) == 29
    counts: dict[str, int] = {}
    for entry in _DEPENDENT_DIGEST_AUDIT:
        counts[entry.historical_trigger] = counts.get(entry.historical_trigger, 0) + 1
        assert entry.historical_predicate.startswith("sha256(")
        assert entry.evidence_pair
        assert entry.service_owner
        assert entry.checker
    assert counts == {
        "provider_call_claims_before_insert": 2,
        "launch_reservations_failure_evidence_guard": 1,
        "launch_reservations_state_guard": 9,
        "launch_executions_parent_policy_before_insert": 1,
        "launch_executions_phase_guard": 3,
        "terminals_before_insert": 1,
        "manual_recoveries_before_insert": 12,
    }
    assert (
        sum(
            entry.historical_trigger == "manual_recoveries_before_insert"
            for entry in _DEPENDENT_DIGEST_AUDIT
        )
        == 12
    )
    assert (
        sum(
            entry.historical_trigger == "terminals_before_insert"
            for entry in _DEPENDENT_DIGEST_AUDIT
        )
        == 1
    )


_RECOVERY_ACTIONS: dict[str, tuple[str, str, str]] = {
    "RECORD_ATTEMPT_AMBIGUITY": (
        "ATTEMPT",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
    ),
    "RECORD_CLAIM_AMBIGUITY": (
        "CLAIM",
        "COMMITTED",
        "AMBIGUITY_RECORDED",
    ),
    "CLASSIFY_LAUNCH_RESERVATION": (
        "LAUNCH_RESERVATION",
        "COMMITTED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN": (
        "LAUNCH_RESERVATION",
        "PROCESS_INTENT_COMMITTED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_PRE_RESUME_READY": (
        "LAUNCH_RESERVATION",
        "PROCESS_CREATED",
        "MANUAL_REVIEW",
    ),
    "CLASSIFY_RESUME_OUTCOME_UNKNOWN": (
        "LAUNCH_RESERVATION",
        "PROCESS_CREATED",
        "MANUAL_REVIEW",
    ),
    "SELECT_COMMITTED_SUCCESS": (
        "TERMINAL",
        "SUCCEEDED",
        "SUCCESS_SELECTED",
    ),
    "CLOSE_SESSION": ("SESSION", "OPEN", "CLOSED"),
    "ACKNOWLEDGE_RESTORE": (
        "SESSION",
        "OPEN",
        "RESTORE_ACKNOWLEDGED",
    ),
}


_RECOVERY_TARGET_EVIDENCE_PAIRS: dict[str, tuple[str, ...]] = {
    "RECORD_ATTEMPT_AMBIGUITY": (
        "launch_executions.post_resume",
        "launch_executions.cleanup",
    ),
    "RECORD_CLAIM_AMBIGUITY": (
        "launch_executions.post_resume",
        "launch_executions.cleanup",
    ),
    "CLASSIFY_LAUNCH_RESERVATION": (),
    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN": ("launch_reservations.process_intent",),
    "CLASSIFY_PRE_RESUME_READY": (
        "launch_executions.process_creation",
        "launch_executions.job_object",
        "launch_executions.resume_authorization",
    ),
    "CLASSIFY_RESUME_OUTCOME_UNKNOWN": (
        "launch_executions.process_creation",
        "launch_executions.job_object",
        "launch_executions.resume_authorization",
        "launch_executions.resume_intent",
    ),
    "SELECT_COMMITTED_SUCCESS": (),
    "CLOSE_SESSION": (),
    "ACKNOWLEDGE_RESTORE": (),
}


def _insert_recovery_fact_for_test(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    *,
    operator_evidence_json: bytes,
    operator_evidence_digest: bytes,
    recovery_schema: int = 1,
    created_at_utc: str = MANUAL_REVIEW_TIMESTAMP,
) -> str:
    expected_kind, _, resulting = _RECOVERY_ACTIONS[action]
    if target_kind != expected_kind:
        raise ValueError("recovery action target kind is invalid")
    ordinal_row = connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if ordinal_row is None:
        raise ValueError("unknown recovery session")
    recovery_ordinal = ordinal_row[0]
    predecessor = _target_state(connection, target_kind, target_id)
    recovery_id = _recovery_id(
        session_id,
        target_kind,
        target_id,
        action,
        predecessor,
        resulting,
        recovery_ordinal,
        RECOVERY_POLICY,
    )
    _require_evidence_pair(
        operator_evidence_json,
        operator_evidence_digest,
        field="operator evidence digest",
    )
    connection.execute(
        """
        INSERT INTO manual_recoveries (
            recovery_id, session_id, recovery_ordinal, target_kind,
            target_id, action, predecessor_state, resulting_state,
            recovery_schema, recovery_policy_version,
            operator_evidence_json, operator_evidence_digest,
            created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            recovery_id,
            session_id,
            recovery_ordinal,
            target_kind,
            target_id,
            action,
            predecessor,
            resulting,
            recovery_schema,
            RECOVERY_POLICY,
            operator_evidence_json,
            operator_evidence_digest,
            created_at_utc,
        ),
    )
    return recovery_id


class FakeSideEffects:
    """Test-only hooks that can observe committed authority facts."""

    def __init__(
        self,
        observer: sqlite3.Connection,
        events: list[str] | None = None,
        event_lock: threading.Lock | None = None,
        *,
        service: Architecture77HarnessAuthority | None = None,
    ) -> None:
        self.observer = observer
        self.events = [] if events is None else events
        self._event_lock = threading.Lock() if event_lock is None else event_lock
        self._service = (
            _test_service(observer)
            if service is None and _CURRENT_HARNESS.get() is not None
            else service
        )

    @property
    def _bound_service(self) -> Architecture77HarnessAuthority:
        if self._service is None:
            raise HarnessLifecycleError(
                "external-effect test adapter requires an explicit harness service"
            )
        return self._service

    def _emit(self, event: str) -> None:
        with self._event_lock:
            self.events.append(event)

    def construct_provider(
        self,
        capability: FakeProviderConstructionPermit,
        *,
        fail: bool = False,
    ) -> FakeConstructedProvider:
        if type(capability) is not FakeProviderConstructionPermit:
            raise TypeError(
                "provider construction requires the reservation-issued permit"
            )
        self._bound_service.require_test_capability(capability)
        _require_no_active_transaction(self.observer)
        reservation_id = _registered_provider_reservation_id(capability)
        with InterprocessLifecycleArbiter(reservation_id):
            return self._construct_provider_locked(capability, fail=fail)

    def _construct_provider_locked(
        self,
        capability: FakeProviderConstructionPermit,
        *,
        fail: bool,
    ) -> FakeConstructedProvider:
        reservation_id = _registered_provider_reservation_id(capability)
        row = self.observer.execute(
            """
            SELECT r.reservation_state, r.request_digest,
                   r.authority_policy_version, r.claim_policy_version,
                   r.reservation_evidence_json,
                   r.reservation_evidence_digest, r.process_intent_json,
                   r.process_intent_digest, r.process_intent_committed_at_utc,
                   c.state, c.request_json, c.request_digest,
                   c.claim_policy_version, c.provider_id,
                   c.permitted_provider_operation, c.provider_call_budget,
                   c.claim_evidence_json, c.claim_evidence_digest,
                   a.state, a.request_json, a.request_digest,
                   a.attempt_policy_version, a.provider_id,
                   a.permitted_provider_operation, a.provider_call_budget,
                   s.state, s.request_json, s.request_digest,
                   s.authority_policy_version, s.claim_policy_version,
                   m.provider_id, m.permitted_provider_operation,
                   m.authority_policy_version, m.claim_policy_version
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            JOIN authority_metadata m ON m.singleton_key = 1
            WHERE r.launch_reservation_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM launch_executions e
                  WHERE e.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (str(reservation_id),),
        ).fetchone()
        if row is None:
            raise ValueError("provider construction active lineage is unavailable")
        if (
            row[0] != "COMMITTED"
            or row[6] is not None
            or row[7] is not None
            or row[8] is not None
            or row[9] != "COMMITTED"
            or row[18] != "LAUNCH_RESERVED"
            or row[25] != "OPEN"
        ):
            raise ValueError("provider construction active lineage is revoked")
        if (
            _digest(row[4]) != row[5]
            or _digest(row[16]) != row[17]
            or _digest(row[10]) != row[11]
            or row[10] != row[19]
            or row[10] != row[26]
            or row[1] != row[11]
            or row[1] != row[20]
            or row[1] != row[27]
            or row[3] != row[12]
            or row[3] != row[21]
            or row[3] != row[29]
            or row[3] != row[33]
            or row[2] != row[28]
            or row[2] != row[32]
            or row[13] != row[22]
            or row[13] != row[30]
            or row[13] != PROVIDER
            or row[14] != row[23]
            or row[14] != row[31]
            or row[14] != OPERATION
            or row[15] != 1
            or row[24] != 1
        ):
            raise ValueError("provider construction lineage evidence is invalid")
        _consume_provider_construction_permit(
            capability, reservation_id, core=self._bound_service._core
        )

        assert not self.observer.in_transaction
        self._emit("provider-constructed")
        if fail:
            self._emit("provider-construction-failed")
            raise RuntimeError("modeled provider construction failure")
        with self._bound_service.bind_external_effects():
            return _issue_constructed_provider(reservation_id)

    def create_process(
        self, process_intent: FakeProcessIntent, *, fail: bool = False
    ) -> FakeProcessCreationReceipt | FakeProcessCreationFailure:
        if type(process_intent) is not FakeProcessIntent:
            raise TypeError("create process requires an opaque fake process intent")
        self._bound_service.require_test_capability(process_intent)
        _require_no_active_transaction(self.observer)
        reservation_id = _registered_process_intent_reservation_id(process_intent)
        with InterprocessLifecycleArbiter(reservation_id):
            return self._create_process_locked(process_intent, fail=fail)

    def _create_process_locked(
        self,
        process_intent: FakeProcessIntent,
        *,
        fail: bool,
    ) -> FakeProcessCreationReceipt | FakeProcessCreationFailure:
        reservation_id = _registered_process_intent_reservation_id(process_intent)
        row = self.observer.execute(
            """
            SELECT r.reservation_state, r.request_digest,
                   r.authority_policy_version, r.claim_policy_version,
                   r.process_intent_json, r.process_intent_digest,
                   c.state, a.state, s.state
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE r.launch_reservation_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (str(reservation_id),),
        ).fetchone()
        if row is None:
            raise ValueError("CreateProcessW intent names an unknown reservation")
        expected_intent = _process_intent_json(reservation_id, row[1], row[2], row[3])
        if row[0] != "PROCESS_INTENT_COMMITTED":
            raise ValueError("CreateProcessW requires PROCESS_INTENT_COMMITTED")
        if row[6] != "COMMITTED" or row[7] != "LAUNCH_RESERVED" or row[8] != "OPEN":
            raise ValueError("CreateProcessW active parent lineage is revoked")
        if (
            row[4] != process_intent.intent_json
            or row[5] != process_intent.intent_digest
            or process_intent.intent_json != expected_intent
            or process_intent.intent_digest != _digest(expected_intent)
        ):
            raise ValueError("CreateProcessW intent does not match durable authority")
        _consume_process_intent(
            process_intent, reservation_id, core=self._bound_service._core
        )

        self._emit("process-intent-committed")
        assert not self.observer.in_transaction
        self._emit("create-process")
        if fail:
            self._emit("process-creation-failed")
            result_json = _process_failure_json(
                reservation_id, process_intent.intent_digest
            )
            with self._bound_service.bind_external_effects():
                return _issue_process_creation_failure(
                    reservation_id,
                    process_intent.intent_digest,
                    result_json,
                    _digest(result_json),
                )
        self._emit("process-created")
        process_json, job_json, resume_json = _process_success_evidence(
            reservation_id, process_intent.intent_digest
        )
        with self._bound_service.bind_external_effects():
            return _issue_process_creation_receipt(
                reservation_id,
                process_intent.intent_digest,
                process_json,
                _digest(process_json),
                job_json,
                _digest(job_json),
                resume_json,
                _digest(resume_json),
            )

    def resume_thread(
        self, resume_intent: FakeResumeIntent, *, fail: bool = False
    ) -> FakeResumeReceipt:
        if type(resume_intent) is not FakeResumeIntent:
            raise TypeError("resume thread requires an opaque fake resume intent")
        self._bound_service.require_test_capability(resume_intent)
        _require_no_active_transaction(self.observer)
        execution_id, reservation_id = _registered_resume_intent_binding(resume_intent)
        with InterprocessLifecycleArbiter(reservation_id):
            return self._resume_thread_locked(resume_intent, fail=fail)

    def _resume_thread_locked(
        self,
        resume_intent: FakeResumeIntent,
        *,
        fail: bool,
    ) -> FakeResumeReceipt:
        execution_id, reservation_id = _registered_resume_intent_binding(resume_intent)
        row = self.observer.execute(
            """
            SELECT e.phase, e.process_creation_json, e.process_creation_digest,
                   e.job_object_json, e.job_object_digest,
                   e.resume_authorization_json, e.resume_authorization_digest,
                   e.resume_intent_json, e.resume_intent_digest,
                   r.reservation_state, s.state, e.launch_reservation_id
            FROM launch_executions e
            JOIN launch_reservations r
              ON r.launch_reservation_id = e.launch_reservation_id
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            JOIN sessions s ON s.session_id = a.session_id
            WHERE e.launch_execution_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM terminals t
                  WHERE t.launch_reservation_id = r.launch_reservation_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM session_selections ss
                  WHERE ss.session_id = s.session_id
              )
            """,
            (execution_id,),
        ).fetchone()
        if row is None:
            raise ValueError("ResumeThread active lineage is unavailable")
        if row[0] != "RESUME_INTENT_COMMITTED":
            raise ValueError("ResumeThread requires RESUME_INTENT_COMMITTED")
        if row[9] != "PROCESS_CREATED" or row[10] != "OPEN":
            raise ValueError("ResumeThread active parent lineage is revoked")
        if row[11] != reservation_id:
            raise ValueError("ResumeThread intent belongs to another reservation")
        for evidence_json, evidence_digest in (
            (row[1], row[2]),
            (row[3], row[4]),
            (row[5], row[6]),
        ):
            if evidence_json is None or evidence_digest != _digest(evidence_json):
                raise AssertionError("pre-resume evidence is not committed")
        if row[7] != resume_intent.intent_json or row[8] != resume_intent.intent_digest:
            raise ValueError("ResumeThread intent does not match committed authority")
        expected_intent = _json(
            {
                "execution_id": execution_id,
                "resume_operation": "ResumeThread",
                "schema": 1,
            }
        )
        if (
            resume_intent.intent_json != expected_intent
            or resume_intent.intent_digest != _digest(expected_intent)
        ):
            raise ValueError("ResumeThread intent is not canonical")
        _consume_resume_intent(
            resume_intent,
            execution_id,
            reservation_id,
            core=self._bound_service._core,
        )

        self._emit("resume-intent-committed")
        assert not self.observer.in_transaction
        self._emit("resume-thread")
        if fail:
            self._emit("resume-thread-failed")
            raise RuntimeError("modeled ResumeThread failure")
        result_json = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": resume_intent.intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        with self._bound_service.bind_external_effects():
            return _issue_resume_receipt(
                execution_id,
                reservation_id,
                resume_intent.intent_digest,
                result_json,
                _digest(result_json),
            )

    def observe_post_resume_evidence(self, execution_id: str) -> None:
        assert (
            self.observer.execute(
                "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
                "cleanup_digest FROM launch_executions "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()[0]
            == "RESUME_RECORDED"
        )
        self._emit("post-resume-evidence")

    def observe_terminal(self, reservation_id: str) -> None:
        assert (
            self.observer.execute(
                "SELECT terminal_id FROM terminals WHERE launch_reservation_id = ?",
                (str(reservation_id),),
            ).fetchone()
            is not None
        )
        self._emit("terminal")


def _create_process_receipt(
    connection: sqlite3.Connection, reservation_id: str
) -> FakeProcessCreationReceipt:
    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    result = FakeSideEffects(connection).create_process(intent)
    assert type(result) is FakeProcessCreationReceipt
    return result


def _record_successful_process(
    connection: sqlite3.Connection, reservation_id: str
) -> str:
    receipt = _create_process_receipt(connection, reservation_id)
    return record_execution(connection, reservation_id, receipt)


def _prepare_lease_resume_case(
    harness: Architecture77HarnessAuthority, target_date: str
) -> tuple[str, str, str, FakeResumeReceipt]:
    with _bind_harness(harness):
        connection = harness._connection
        session_id = create_session(connection, _request(target_date))
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        intent = commit_resume_intent(connection, execution_id, reservation_id)
        receipt = FakeSideEffects(connection).resume_thread(intent)
    return session_id, str(reservation_id), execution_id, receipt


def _prepare_lease_recovery_lineage_case(
    harness: Architecture77HarnessAuthority, target_kind: str
) -> tuple[str, str, str, str, str]:
    action = {
        "SESSION": "CLOSE_SESSION",
        "ATTEMPT": "RECORD_ATTEMPT_AMBIGUITY",
        "CLAIM": "RECORD_CLAIM_AMBIGUITY",
        "LAUNCH_RESERVATION": "CLASSIFY_LAUNCH_RESERVATION",
        "TERMINAL": "SELECT_COMMITTED_SUCCESS",
    }[target_kind]

    def build_lineage(target_date: str) -> tuple[str, str, str]:
        session_id = create_session(harness._connection, _request(target_date))
        attempt_id = allocate_attempt(harness._connection, session_id)
        claim_id = commit_claim(harness._connection, attempt_id)
        reservation_permit = reserve_launch(harness._connection, claim_id)
        reservation_id = str(reservation_permit)
        target_id = {
            "SESSION": session_id,
            "ATTEMPT": attempt_id,
            "CLAIM": claim_id,
            "LAUNCH_RESERVATION": reservation_id,
        }.get(target_kind)
        if target_kind in {"ATTEMPT", "CLAIM", "TERMINAL"}:
            execution_id = _record_successful_process(
                harness._connection, reservation_permit
            )
            _resume_and_persist(harness._connection, execution_id, reservation_id)
            if target_kind == "TERMINAL":
                target_id = record_terminal(
                    harness._connection,
                    reservation_id,
                    snapshot_digest=TEST_SNAPSHOT_DIGEST,
                )
        return session_id, reservation_id, target_id

    with _bind_harness(harness):
        session_a, reservation_a, target_a = build_lineage("2026-01-01")
        _, _, target_b = build_lineage("2026-01-02")
    return session_a, reservation_a, target_a, target_b, action


def _prepare_test_consumer_capability(
    harness: Architecture77HarnessAuthority, family: str
) -> tuple[object, str, str | None]:
    with _bind_harness(harness):
        connection = harness._connection
        if family in {"provider", "process_intent", "resume_intent"}:
            session_id = create_session(connection, _request())
            attempt_id = allocate_attempt(connection, session_id)
            claim_id = commit_claim(connection, attempt_id)
            permit = reserve_launch(connection, claim_id)
            reservation_id = str(permit)
        else:
            permit = None
            reservation_id = "consumer-reservation"

        if family == "provider":
            return permit, reservation_id, None
        if family == "constructed":
            with harness.bind_external_effects():
                return _issue_constructed_provider(reservation_id), reservation_id, None
        if family == "process_intent":
            assert type(permit) is FakeProviderConstructionPermit
            return (
                _construct_provider_and_commit_process_intent(connection, permit),
                reservation_id,
                None,
            )
        if family == "process_result":
            with harness.bind_external_effects():
                return (
                    _issue_process_creation_receipt(
                        reservation_id,
                        b"intent-digest",
                        b"process",
                        _digest(b"process"),
                        b"job",
                        _digest(b"job"),
                        b"resume",
                        _digest(b"resume"),
                    ),
                    reservation_id,
                    None,
                )
        if family == "resume_intent":
            assert type(permit) is FakeProviderConstructionPermit
            execution_id = _record_successful_process(connection, permit)
            return (
                commit_resume_intent(connection, execution_id, reservation_id),
                reservation_id,
                execution_id,
            )
        if family == "resume_result":
            with harness.bind_external_effects():
                return (
                    _issue_resume_receipt(
                        "consumer-execution",
                        reservation_id,
                        b"resume-intent-digest",
                        b"resumed",
                        _digest(b"resumed"),
                    ),
                    reservation_id,
                    "consumer-execution",
                )
    raise AssertionError(f"unsupported capability family: {family}")


def _consume_test_consumer_capability(
    family: str,
    capability: object,
    reservation_id: str,
    execution_id: str | None,
    *,
    core: TransactionalAuthorityCore,
) -> None:
    if family == "provider":
        _consume_provider_construction_permit(
            capability,
            reservation_id,
            core=core,  # type: ignore[arg-type]
        )
    elif family == "constructed":
        _consume_constructed_provider(
            capability,
            reservation_id,
            core=core,  # type: ignore[arg-type]
        )
    elif family == "process_intent":
        _consume_process_intent(
            capability,
            reservation_id,
            core=core,  # type: ignore[arg-type]
        )
    elif family == "process_result":
        _consume_process_result(
            capability,
            reservation_id,
            core=core,  # type: ignore[arg-type]
        )
    elif family == "resume_intent":
        assert execution_id is not None
        _consume_resume_intent(
            capability,
            execution_id,
            reservation_id,
            core=core,  # type: ignore[arg-type]
        )
    elif family == "resume_result":
        assert execution_id is not None
        _consume_resume_result(
            capability,
            execution_id,
            reservation_id,
            core=core,  # type: ignore[arg-type]
        )
    else:
        raise AssertionError(f"unsupported capability family: {family}")


def _record_definitive_process_failure(
    connection: sqlite3.Connection, reservation_id: str
) -> None:
    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    result = FakeSideEffects(connection).create_process(intent, fail=True)
    assert type(result) is FakeProcessCreationFailure
    record_process_creation_failure(connection, reservation_id, result)


def _corrupt_retry_safe_prior_evidence(
    connection: sqlite3.Connection, reservation_id: str, pair: str
) -> bytes:
    trigger, column = {
        "process_creation_failure": (
            "launch_reservations_failure_evidence_guard",
            "process_creation_failure_digest",
        ),
        "process_intent": (
            "launch_reservations_process_intent_append_only",
            "process_intent_digest",
        ),
    }[pair]
    wrong_digest = _digest(f"corrupt-{pair}".encode("ascii"))
    connection.execute(f"DROP TRIGGER {trigger}")
    connection.execute(
        f"UPDATE launch_reservations SET {column} = ? WHERE launch_reservation_id = ?",
        (wrong_digest, str(reservation_id)),
    )
    connection.commit()
    return wrong_digest


def _construct_provider_and_commit_process_intent(
    connection: sqlite3.Connection,
    reservation_id: str,
    hooks: FakeSideEffects | None = None,
) -> FakeProcessIntent:
    if type(reservation_id) is not FakeProviderConstructionPermit:
        raise TypeError("provider handoff requires the reservation-issued permit")
    provider = (
        FakeSideEffects(connection) if hooks is None else hooks
    ).construct_provider(reservation_id)
    return commit_process_intent(connection, reservation_id, provider)


def _resume_and_persist(
    connection: sqlite3.Connection, execution_id: str, reservation_id: str
) -> FakeResumeReceipt:
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    receipt = FakeSideEffects(connection).resume_thread(intent)
    record_post_resume_evidence(connection, execution_id, receipt)
    return receipt


def _spawn_boundary_worker(
    descriptor: Architecture77HarnessDescriptor,
    scenario: str,
    first: bool,
    setup_queue: Any,
    result_queue: Any,
    go: Any,
    acquired: Any,
    release: Any,
    started: Any,
) -> None:
    harness = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    harness_context = _CURRENT_HARNESS.set(harness)
    connection = harness._connection
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    try:
        session_id = create_session(connection)
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        permit = reserve_launch(connection, claim_id)
        reservation_id = str(permit)
        capability: object = permit
        execution_id: str | None = None

        if scenario != "provider-dispatch":
            provider = hooks.construct_provider(permit)
            capability = commit_process_intent(connection, reservation_id, provider)
        if scenario in {
            "process-persistence",
            "resume-dispatch",
            "resume-persistence",
        }:
            assert type(capability) is FakeProcessIntent
            capability = hooks.create_process(capability)
        if scenario in {"resume-dispatch", "resume-persistence"}:
            assert type(capability) is FakeProcessCreationReceipt
            execution_id = record_execution(connection, reservation_id, capability)
            capability = commit_resume_intent(connection, execution_id, reservation_id)
        if scenario == "resume-persistence":
            assert type(capability) is FakeResumeIntent
            capability = hooks.resume_thread(capability)

        setup_queue.put((session_id, reservation_id, execution_id))
        connection.close()
        connection = None
        if not go.wait(20):
            raise TimeoutError("boundary worker was not released to race")

        try:
            if not first:
                started.set()
            connection = _connect(Path(descriptor.database_path))
            hooks.observer = connection
            harness = _test_service(connection)
            with harness.lifecycle_lease(reservation_id) as lease:
                if first:
                    acquired.set()
                    if not release.wait(20):
                        raise TimeoutError("boundary winner was not released")
                if scenario == "provider-dispatch":
                    assert type(capability) is FakeProviderConstructionPermit
                    hooks._construct_provider_locked(capability, fail=False)
                elif scenario == "process-dispatch":
                    assert type(capability) is FakeProcessIntent
                    hooks._create_process_locked(capability, fail=False)
                elif scenario == "process-persistence":
                    assert type(capability) is FakeProcessCreationReceipt
                    lease.record_execution(reservation_id, capability)
                elif scenario == "resume-dispatch":
                    assert type(capability) is FakeResumeIntent
                    hooks._resume_thread_locked(capability, fail=False)
                else:
                    assert scenario == "resume-persistence"
                    assert execution_id is not None
                    assert type(capability) is FakeResumeReceipt
                    lease.bind_execution(execution_id)
                    lease.record_post_resume_evidence(execution_id, capability)
            outcome = "ok"
        except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
            outcome = f"rejected:{type(exc).__name__}"
        result_queue.put(("boundary", outcome, events))
    except BaseException as exc:
        result_queue.put(("boundary-error", repr(exc), events))
    finally:
        if connection is not None:
            connection.close()
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()


def _spawn_recovery_worker(
    descriptor: Architecture77HarnessDescriptor,
    session_id: str,
    reservation_id: str,
    action: str,
    first: bool,
    result_queue: Any,
    go: Any,
    acquired: Any,
    release: Any,
    started: Any,
) -> None:
    harness = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    harness_context = _CURRENT_HARNESS.set(harness)
    connection: sqlite3.Connection | None = None
    try:
        if not go.wait(20):
            raise TimeoutError("recovery worker was not released to race")
        try:
            if not first:
                started.set()
            connection = _connect(Path(descriptor.database_path))
            harness = _test_service(connection)
            with harness.lifecycle_lease(reservation_id) as lease:
                if first:
                    acquired.set()
                    if not release.wait(20):
                        raise TimeoutError("recovery winner was not released")
                lease.record_recovery(
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    action,
                    None,
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
            outcome = "ok"
        except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
            outcome = f"rejected:{type(exc).__name__}"
        result_queue.put(("recovery", outcome, []))
    except BaseException as exc:
        result_queue.put(("recovery-error", repr(exc), []))
    finally:
        if connection is not None:
            connection.close()
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()


@contextmanager
def _spawn_temp_environment(temp_root: Path) -> Iterator[None]:
    names = ("TEMP", "TMP", "TMPDIR")
    previous = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ[name] = str(temp_root)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _spawn_cross_environment_arbiter_worker(
    reservation_id: str,
    temp_root: str,
    working_directory: str,
    label: str,
    attempting: Any,
    acquired: Any,
    release: Any,
    hold_until_released: bool,
    effect_count: Any,
    result_queue: Any,
) -> None:
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = temp_root
    os.chdir(working_directory)
    arbiter = InterprocessLifecycleArbiter(reservation_id)
    result_queue.put(
        (
            "path",
            label,
            str(arbiter.path.parent),
            str(arbiter.path),
            arbiter.identity,
        )
    )
    attempting.set()
    with arbiter:
        eligible_for_effect = effect_count.value == 0
        acquired.set()
        if hold_until_released and not release.wait(20):
            raise TimeoutError("cross-environment arbiter owner was not released")
        emitted = False
        if eligible_for_effect:
            effect_count.value += 1
            emitted = True
    result_queue.put(("result", label, emitted, effect_count.value))


def _spawn_crash_while_holding_arbiter(reservation_id: str, acquired: Any) -> None:
    with InterprocessLifecycleArbiter(reservation_id):
        acquired.set()
        os._exit(23)


def _spawn_reconstructed_capability_worker(
    descriptor: Architecture77HarnessDescriptor, reservation_id: str, result_queue: Any
) -> None:
    harness = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    harness_context = _CURRENT_HARNESS.set(harness)
    connection = harness._connection
    hooks = FakeSideEffects(connection)
    outcomes: list[str] = []
    try:
        reconstructed_permit = _forged_capability(
            FakeProviderConstructionPermit,
            reservation_id=reservation_id,
        )
        try:
            hooks.construct_provider(reconstructed_permit)
        except (AttributeError, TypeError, ValueError) as exc:
            outcomes.append(f"rejected:{type(exc).__name__}")
        reconstructed_provider = _forged_capability(
            FakeConstructedProvider,
            reservation_id=reservation_id,
        )
        try:
            commit_process_intent(connection, reservation_id, reconstructed_provider)
        except (AttributeError, TypeError, ValueError) as exc:
            outcomes.append(f"rejected:{type(exc).__name__}")
        result_queue.put(outcomes)
    finally:
        connection.close()
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()


def _spawn_outer_transaction_boundary_worker(
    descriptor: Architecture77HarnessDescriptor,
    setup_queue: Any,
    result_queue: Any,
    recovery_acquired: Any,
    transaction_started: Any,
    transaction_released: Any,
) -> None:
    harness = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    harness_context = _CURRENT_HARNESS.set(harness)
    connection = harness._connection
    hooks = FakeSideEffects(connection)
    try:
        session_id = create_session(connection)
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation = reserve_launch(connection, claim_id)
        provider = hooks.construct_provider(reservation)
        setup_queue.put((session_id, str(reservation)))
        if not recovery_acquired.wait(20):
            raise TimeoutError("recovery worker did not acquire the arbiter")
        before = _database_rows(connection)
        events_before = list(hooks.events)
        connection.execute("BEGIN IMMEDIATE")
        transaction_started.set()
        try:
            commit_process_intent(connection, str(reservation), provider)
        except ValueError as exc:
            rejection = str(exc)
        else:
            raise AssertionError("active transaction reached lifecycle arbiter")
        assert connection.in_transaction
        _assert_capability_available(provider)
        assert hooks.events == events_before
        assert _database_rows(connection) == before
        connection.rollback()
        transaction_released.set()
        result_queue.put(("boundary", rejection))
    except BaseException as exc:
        if connection.in_transaction:
            connection.rollback()
        result_queue.put(("boundary-error", repr(exc)))
    finally:
        connection.close()
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()


def _spawn_stored_observer_transaction_boundary_worker(
    descriptor: Architecture77HarnessDescriptor,
    setup_queue: Any,
    result_queue: Any,
    recovery_acquired: Any,
    transaction_started: Any,
    transaction_released: Any,
) -> None:
    harness = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    harness_context = _CURRENT_HARNESS.set(harness)
    observer = harness._connection
    events: list[str] = []
    hooks = FakeSideEffects(observer, events)
    try:
        session_id = create_session(observer)
        attempt_id = allocate_attempt(observer, session_id)
        claim_id = commit_claim(observer, attempt_id)
        permit = reserve_launch(observer, claim_id)
        setup_queue.put((session_id, str(permit)))
        if not recovery_acquired.wait(20):
            raise TimeoutError("recovery worker did not acquire the arbiter")
        before = _database_rows(observer)
        observer.execute("BEGIN IMMEDIATE")
        transaction_started.set()
        try:
            hooks.construct_provider(permit)
        except ValueError as exc:
            rejection = str(exc)
        else:
            raise AssertionError(
                "active observer transaction reached lifecycle arbiter"
            )
        assert observer.in_transaction
        _assert_capability_available(permit)
        assert events == []
        assert _database_rows(observer) == before
        observer.rollback()
        transaction_released.set()
        result_queue.put(
            (
                "boundary",
                (
                    rejection,
                    _capability_is_registered(permit),
                    observer.in_transaction,
                    events,
                ),
            )
        )
    except BaseException as exc:
        if observer.in_transaction:
            observer.rollback()
        result_queue.put(("boundary-error", repr(exc)))
    finally:
        observer.close()
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()


def _spawn_recovery_after_outer_transaction_worker(
    descriptor: Architecture77HarnessDescriptor,
    session_id: str,
    reservation_id: str,
    result_queue: Any,
    recovery_acquired: Any,
    transaction_started: Any,
    transaction_released: Any,
) -> None:
    harness = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    harness_context = _CURRENT_HARNESS.set(harness)
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect(Path(descriptor.database_path))
        harness = _test_service(connection)
        with harness.lifecycle_lease(reservation_id) as lease:
            recovery_acquired.set()
            if not transaction_started.wait(20):
                raise TimeoutError("boundary worker did not begin its transaction")
            if not transaction_released.wait(20):
                raise TimeoutError("boundary worker did not release its transaction")
            recovery_id = lease.record_recovery(
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_LAUNCH_RESERVATION",
                None,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
        result_queue.put(("recovery", recovery_id))
    except BaseException as exc:
        result_queue.put(("recovery-error", repr(exc)))
    finally:
        if connection is not None:
            connection.close()
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()


@pytest.fixture
def db_path(request: pytest.FixtureRequest) -> Path:
    harness = Architecture77HarnessAuthority.create()
    harness_context = _CURRENT_HARNESS.set(harness)

    def finalize() -> None:
        _CURRENT_HARNESS.reset(harness_context)
        harness.close()

    request.addfinalizer(finalize)
    return harness.database_path


def _descriptor_for(db_path: Path) -> Architecture77HarnessDescriptor:
    harness = _CURRENT_HARNESS.get()
    if harness is None or harness.database_path != db_path.resolve(strict=False):
        raise HarnessLifecycleError("database path is not bound to the active harness")
    return harness.descriptor


def _inherit_harness_thread(
    target: Callable[..., Any], *args: Any
) -> Callable[[], Any]:
    harness = _CURRENT_HARNESS.get()
    if harness is None:
        raise HarnessLifecycleError("thread requires an active Architecture-77 harness")

    def run() -> Any:
        context_token = _CURRENT_HARNESS.set(harness)
        try:
            return target(*args)
        finally:
            _CURRENT_HARNESS.reset(context_token)

    return run


@contextmanager
def _bind_harness(harness: Architecture77HarnessAuthority) -> Iterator[None]:
    context_token = _CURRENT_HARNESS.set(harness)
    try:
        yield
    finally:
        _CURRENT_HARNESS.reset(context_token)


def _seed_harness_metadata(
    harness: Architecture77HarnessAuthority, **metadata: Any
) -> None:
    seed = sqlite3.connect(":memory:", isolation_level=None)
    try:
        _install_schema(seed)
        _insert_metadata(seed, **metadata)
        seed.backup(harness._connection)
    finally:
        seed.close()


def test_harness_provenance_does_not_survive_same_path_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "reused-harness-root"

    def fresh_root(*, prefix: str) -> str:
        del prefix
        root.mkdir()
        return str(root)

    monkeypatch.setattr(tempfile, "mkdtemp", fresh_root)
    first = Architecture77HarnessAuthority.create()
    session_id = first.create_session(_request())
    attempt_id = first.allocate_attempt(session_id)
    claim_id = first.commit_claim(attempt_id)
    permit = first.reserve_launch(claim_id)
    first.close()
    assert not root.exists()

    second = Architecture77HarnessAuthority.create()
    try:
        assert second.database_path == root / "authority.sqlite3"
        before = _database_rows(second._connection)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            second.require_test_capability(permit)
        assert _database_rows(second._connection) == before
    finally:
        second.close()


def test_simultaneous_harness_lifetimes_have_distinct_provenance() -> None:
    first = Architecture77HarnessAuthority.create()
    second = Architecture77HarnessAuthority.create()
    try:
        assert first._service_token is not second._service_token
        session_a = first.create_session(_request())
        attempt_a = first.allocate_attempt(session_a)
        claim_a = first.commit_claim(attempt_a)
        permit_a = first.reserve_launch(claim_a)
        session_b = second.create_session(_request())
        attempt_b = second.allocate_attempt(session_b)
        claim_b = second.commit_claim(attempt_b)
        second.reserve_launch(claim_b)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            second.require_test_capability(permit_a)
    finally:
        first.close()
        second.close()


def test_closed_harness_rejects_bindings_and_operations_without_stale_cache() -> None:
    harness = Architecture77HarnessAuthority.create()
    connection = harness._connection
    service = harness.bind_connection(connection)
    harness.close()
    harness.close()
    with pytest.raises(HarnessLifecycleError, match="lifecycle is closed"):
        service.create_session(_request())
    with pytest.raises(HarnessLifecycleError, match="lifecycle is closed"):
        harness.bind_connection(connection)
    with pytest.raises(HarnessLifecycleError, match="lifecycle is closed"):
        harness._core.create_session(_request())
    with pytest.raises(HarnessLifecycleError, match="lifecycle is closed"):
        TransactionalAuthorityCore.from_harness_binding(harness._core_binding)


def test_raw_connection_cannot_create_a_transactional_core() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        before = _database_rows(harness._connection)
        with pytest.raises(TypeError, match="reviewed harness binding"):
            TransactionalAuthorityCore.from_harness_binding(harness._connection)
        with pytest.raises(TypeError, match="reviewed storage binding"):
            TransactionalAuthorityCore(harness._connection)
        assert _database_rows(harness._connection) == before
    finally:
        harness.close()


def test_harness_core_binding_cannot_be_subclassed_or_faked() -> None:
    with pytest.raises(TypeError, match="cannot be subclassed"):

        class ForgedBinding(TransactionalAuthorityCoreBinding):
            pass

    class FakeBinding:
        pass

    with pytest.raises(TypeError, match="reviewed harness binding"):
        TransactionalAuthorityCore.from_harness_binding(FakeBinding())  # type: ignore[arg-type]


def test_fake_writable_binding_is_rejected_before_arbiter_or_mutation() -> None:
    connection = sqlite3.connect(":memory:", isolation_level=None)

    class FakeBinding:
        def __init__(self, writable_connection: sqlite3.Connection) -> None:
            self.writable_connection = writable_connection

        def _components(self) -> tuple[object, ...]:
            raise AssertionError("fake binding components must not be inspected")

    try:
        with pytest.raises(TypeError, match="reviewed harness binding"):
            TransactionalAuthorityCore.from_harness_binding(  # type: ignore[arg-type]
                FakeBinding(connection)
            )
        with pytest.raises(TypeError, match="requires its issuer"):
            TransactionalAuthorityCoreBinding(
                object(),
                connection,
                lambda _reservation: None,
                None,
                None,
                object(),
            )
        assert connection.execute("SELECT 1").fetchone() == (1,)
    finally:
        connection.close()


def test_valid_harness_core_binding_runs_the_shared_state_machine() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        session_id = harness._core.create_session(_request())
        assert isinstance(session_id, str)
    finally:
        harness.close()


@pytest.mark.parametrize(
    "family",
    [
        "provider",
        "constructed",
        "process_intent",
        "process_result",
        "resume_intent",
        "resume_result",
    ],
)
def test_public_test_consumers_require_matching_test_service_provenance(
    family: str,
) -> None:
    owner = Architecture77HarnessAuthority.create()
    other = Architecture77HarnessAuthority.create()
    try:
        capability, reservation_id, execution_id = _prepare_test_consumer_capability(
            owner, family
        )
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            _consume_test_consumer_capability(
                family,
                capability,
                reservation_id,
                execution_id,
                core=other._core,
            )
        assert _capability_is_registered(capability)
        with pytest.raises(TypeError, match="unsupported transactional capability"):
            _consume_test_consumer_capability(
                family,
                object(),
                reservation_id,
                execution_id,
                core=owner._core,
            )
        assert _capability_is_registered(capability)
        _consume_test_consumer_capability(
            family,
            capability,
            reservation_id,
            execution_id,
            core=owner._core,
        )
        assert not _capability_is_registered(capability)
    finally:
        owner.close()
        other.close()


def test_closed_connection_does_not_close_harness_lifecycle() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        harness._connection.close()
        replacement = harness.open_connection()
        service = harness.bind_connection(replacement)
        assert service.create_session(_request())
    finally:
        harness.close()


def test_harness_descriptor_reopen_requires_factory_database_identity(
    tmp_path: Path,
) -> None:
    harness = Architecture77HarnessAuthority.create()
    descriptor = harness.descriptor
    child = Architecture77HarnessAuthority.open_from_descriptor(descriptor)
    child.close()
    assert harness._root.exists()
    try:
        wrong_root = tmp_path / "wrong-root"
        wrong_root.mkdir()
        with pytest.raises(HarnessLifecycleError, match="escaped"):
            Architecture77HarnessAuthority.open_from_descriptor(
                replace(descriptor, root=str(wrong_root))
            )
        with pytest.raises(HarnessLifecycleError, match="escaped"):
            Architecture77HarnessAuthority.open_from_descriptor(
                replace(
                    descriptor,
                    database_path=str(harness._root / "other.sqlite3"),
                )
            )
        production_path = Path(PRODUCTION_AUTHORITY_PATHS.database).resolve()
        with pytest.raises(HarnessLifecycleError, match="production authority"):
            Architecture77HarnessAuthority.open_from_descriptor(
                replace(
                    descriptor,
                    root=str(production_path.parent),
                    database_path=str(production_path),
                )
            )
        wrong_schema_root = tmp_path / "wrong-schema-root"
        wrong_schema_root.mkdir()
        wrong_schema_path = wrong_schema_root / "authority.sqlite3"
        wrong_schema_connection = _connect(wrong_schema_path)
        _install_schema(wrong_schema_connection)
        wrong_schema_connection.close()
        with pytest.raises(HarnessLifecycleError, match="schema"):
            Architecture77HarnessAuthority.open_from_descriptor(
                Architecture77HarnessDescriptor(
                    root=str(wrong_schema_root),
                    database_path=str(wrong_schema_path),
                )
            )
        harness._connection.execute("ATTACH DATABASE ':memory:' AS attached_test")
        with pytest.raises(HarnessLifecycleError, match="exactly one main"):
            harness._validate_connection(harness._connection)
        harness._connection.execute("DETACH DATABASE attached_test")
    finally:
        harness.close()


def test_lifecycle_lease_binds_one_reservation_and_invalidates_on_exit() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        session_a = harness.create_session(_request())
        attempt_a = harness.allocate_attempt(session_a)
        claim_a = harness.commit_claim(attempt_a)
        reservation_a = str(harness.reserve_launch(claim_a))
        session_b = harness.create_session(_request("2026-01-02"))
        attempt_b = harness.allocate_attempt(session_b)
        claim_b = harness.commit_claim(attempt_b)
        reservation_b = str(harness.reserve_launch(claim_b))
        lease = harness.lifecycle_lease(reservation_a)
        before = _database_rows(harness._connection)
        with pytest.raises(HarnessLifecycleError, match="not active"):
            lease.record_execution(reservation_a, object())  # type: ignore[arg-type]
        with lease:
            with pytest.raises(ValueError, match="does not match"):
                lease.record_execution(reservation_b, object())  # type: ignore[arg-type]
            with pytest.raises(HarnessLifecycleError, match="re-entered"):
                lease.__enter__()
        with pytest.raises(HarnessLifecycleError, match="not active"):
            lease.record_execution(reservation_a, object())  # type: ignore[arg-type]
        with pytest.raises(HarnessLifecycleError, match="already exited"):
            lease.__exit__(None, None, None)
        assert _database_rows(harness._connection) == before
    finally:
        harness.close()


def test_core_cannot_mint_lifecycle_witness_without_entered_lease() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        session_id = harness.create_session(_request())
        attempt_id = harness.allocate_attempt(session_id)
        claim_id = harness.commit_claim(attempt_id)
        reservation_id = str(harness.reserve_launch(claim_id))
        before = _database_rows(harness._connection)

        witness_factory_name = "create_lifecycle_lease_witness"
        with pytest.raises(AttributeError, match=witness_factory_name):
            getattr(harness._core, witness_factory_name)(reservation_id)

        assert _database_rows(harness._connection) == before
    finally:
        harness.close()


def test_lifecycle_lease_binds_execution_to_its_reservation() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        _, reservation_a, execution_a, receipt_a = _prepare_lease_resume_case(
            harness, "2026-01-01"
        )
        _, reservation_b, execution_b, receipt_b = _prepare_lease_resume_case(
            harness, "2026-01-02"
        )
        before = harness._connection.execute(
            "SELECT launch_execution_id, launch_reservation_id, phase "
            "FROM launch_executions ORDER BY launch_execution_id"
        ).fetchall()

        with harness.lifecycle_lease(reservation_a) as lease:
            with pytest.raises(ValueError, match="does not belong"):
                lease.bind_execution(execution_b)
            assert lease._core_lease is not None
            with pytest.raises(ValueError, match="held reservation"):
                harness._core.record_post_resume_evidence_while_held(
                    execution_b,
                    receipt_b,
                    lease_witness=lease._core_lease,
                )
            lease.bind_execution(execution_a)

        assert (
            harness._connection.execute(
                "SELECT launch_execution_id, launch_reservation_id, phase "
                "FROM launch_executions ORDER BY launch_execution_id"
            ).fetchall()
            == before
        )
        _assert_capability_available(receipt_b)
        assert receipt_a is not receipt_b
    finally:
        harness.close()


def test_lifecycle_lease_accepts_same_reservation_post_resume_receipt() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        _, reservation_id, execution_id, receipt = _prepare_lease_resume_case(
            harness, "2026-01-01"
        )
        with harness.lifecycle_lease(reservation_id) as lease:
            lease.bind_execution(execution_id)
            lease.record_post_resume_evidence(execution_id, receipt)
        assert harness._connection.execute(
            "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("RESUME_RECORDED",)
        _assert_capability_consumed(receipt)
    finally:
        harness.close()


def test_lifecycle_lease_invalidates_before_release_and_reacquisition() -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        session_id = harness.create_session(_request())
        attempt_id = harness.allocate_attempt(session_id)
        claim_id = harness.commit_claim(attempt_id)
        reservation_id = str(harness.reserve_launch(claim_id))
        lease = harness.lifecycle_lease(reservation_id)
        with lease:
            core_lease = lease._core_lease
            assert core_lease is not None
            arbiter = core_lease._arbiter
            observed: list[bool] = []

            class ArbiterExitProbe:
                def __exit__(self, *args: object) -> None:
                    observed.append(core_lease._witness.active)
                    arbiter.__exit__(*args)

            core_lease._arbiter = ArbiterExitProbe()
        assert observed == [False]
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="closed"):
            harness._core.record_post_resume_evidence_while_held(
                "missing-execution", object(), lease_witness=core_lease
            )
        with harness.lifecycle_lease(reservation_id):
            with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="closed"):
                harness._core.record_post_resume_evidence_while_held(
                    "missing-execution", object(), lease_witness=core_lease
                )
    finally:
        harness.close()


def test_harness_close_invalidates_outstanding_lifecycle_lease() -> None:
    harness = Architecture77HarnessAuthority.create()
    session_id = harness.create_session(_request())
    attempt_id = harness.allocate_attempt(session_id)
    claim_id = harness.commit_claim(attempt_id)
    reservation_id = str(harness.reserve_launch(claim_id))
    lease = harness.lifecycle_lease(reservation_id)
    lease.__enter__()
    core_lease = lease._core_lease
    assert core_lease is not None
    harness.close()
    with pytest.raises(HarnessLifecycleError, match="closed"):
        harness._core.record_post_resume_evidence_while_held(
            "missing-execution", object(), lease_witness=core_lease
        )


def test_lifecycle_witness_lifetime_and_cross_harness_binding() -> None:
    first = Architecture77HarnessAuthority.create()
    second = Architecture77HarnessAuthority.create()
    try:
        _, reservation_a, execution_a, receipt_a = _prepare_lease_resume_case(
            first, "2026-01-01"
        )
        _, reservation_b, execution_b, receipt_b = _prepare_lease_resume_case(
            second, "2026-01-02"
        )
        lease = first.lifecycle_lease(reservation_a)
        with pytest.raises(TypeError, match="already-held operation"):
            first._core.record_post_resume_evidence_while_held(
                execution_a, receipt_a, lease_witness=None
            )
        with lease:
            core_lease = lease._core_lease
            assert core_lease is not None
            with pytest.raises(ValueError, match="invalid or mismatched"):
                second._core.record_post_resume_evidence_while_held(
                    execution_b, receipt_b, lease_witness=core_lease
                )
        with pytest.raises(ExternalAuthorityBoundaryUnavailable, match="closed"):
            first._core.record_post_resume_evidence_while_held(
                execution_a, receipt_a, lease_witness=core_lease
            )
        _assert_capability_available(receipt_a)
        _assert_capability_available(receipt_b)
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "target_kind",
    [
        "SESSION",
        "ATTEMPT",
        "CLAIM",
        "LAUNCH_RESERVATION",
        "TERMINAL",
    ],
)
def test_lifecycle_recovery_rejects_target_outside_held_reservation(
    target_kind: str,
) -> None:
    harness = Architecture77HarnessAuthority.create()
    try:
        session_id, reservation_id, target_a, target_b, action = (
            _prepare_lease_recovery_lineage_case(harness, target_kind)
        )
        before = _database_rows(harness._connection)
        with harness.lifecycle_lease(reservation_id) as lease:
            with pytest.raises(ValueError, match="outside the held reservation"):
                lease.record_recovery(
                    session_id,
                    target_kind,
                    target_b,
                    action,
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
            assert _database_rows(harness._connection) == before
            retry_kind, retry_id, retry_action = (
                ("LAUNCH_RESERVATION", reservation_id, "CLASSIFY_LAUNCH_RESERVATION")
                if target_kind == "SESSION"
                else (target_kind, target_a, action)
            )
            recovery_id = lease.record_recovery(
                session_id,
                retry_kind,
                retry_id,
                retry_action,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
        assert harness._connection.execute(
            "SELECT recovery_id FROM manual_recoveries WHERE recovery_id = ?",
            (recovery_id,),
        ).fetchone() == (recovery_id,)
    finally:
        harness.close()


def _run_spawn_race(
    db_path: Path, scenario: str, winner: str
) -> tuple[dict[str, tuple[str, list[str]]], str, str | None]:
    descriptor = _descriptor_for(db_path)
    context = multiprocessing.get_context("spawn")
    setup_queue = context.Queue()
    result_queue = context.Queue()
    boundary_go = context.Event()
    boundary_acquired = context.Event()
    boundary_release = context.Event()
    boundary_started = context.Event()
    recovery_go = context.Event()
    recovery_acquired = context.Event()
    recovery_release = context.Event()
    recovery_started = context.Event()
    boundary = context.Process(
        target=_spawn_boundary_worker,
        args=(
            descriptor,
            scenario,
            winner == "boundary",
            setup_queue,
            result_queue,
            boundary_go,
            boundary_acquired,
            boundary_release,
            boundary_started,
        ),
    )
    boundary.start()
    session_id, reservation_id, execution_id = setup_queue.get(timeout=30)
    action = {
        "provider-dispatch": "CLASSIFY_LAUNCH_RESERVATION",
        "process-dispatch": "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        "process-persistence": "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        "resume-dispatch": "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        "resume-persistence": "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
    }[scenario]
    recovery = context.Process(
        target=_spawn_recovery_worker,
        args=(
            descriptor,
            session_id,
            reservation_id,
            action,
            winner == "recovery",
            result_queue,
            recovery_go,
            recovery_acquired,
            recovery_release,
            recovery_started,
        ),
    )
    recovery.start()
    if winner == "boundary":
        boundary_go.set()
        assert boundary_acquired.wait(20)
        recovery_go.set()
        assert recovery_started.wait(20)
        boundary_release.set()
    else:
        recovery_go.set()
        assert recovery_acquired.wait(20)
        boundary_go.set()
        assert boundary_started.wait(20)
        recovery_release.set()
    boundary.join(30)
    recovery.join(30)
    assert boundary.exitcode == 0
    assert recovery.exitcode == 0
    raw = [result_queue.get(timeout=10), result_queue.get(timeout=10)]
    outcomes = {source: (result, events) for source, result, events in raw}
    assert set(outcomes) == {"boundary", "recovery"}
    return outcomes, reservation_id, execution_id


@pytest.mark.parametrize(
    "scenario",
    [
        "provider-dispatch",
        "process-dispatch",
        "resume-dispatch",
        "process-persistence",
        "resume-persistence",
    ],
)
@pytest.mark.parametrize("winner", ["boundary", "recovery"])
def test_spawned_processes_serialize_dispatch_persistence_and_recovery(
    db_path: Path, scenario: str, winner: str
) -> None:
    outcomes, reservation_id, execution_id = _run_spawn_race(db_path, scenario, winner)
    boundary_outcome, boundary_events = outcomes["boundary"]
    recovery_outcome, _ = outcomes["recovery"]
    persistence = scenario.endswith("persistence")
    if winner == "boundary":
        assert boundary_outcome == "ok"
        if persistence:
            assert recovery_outcome.startswith("rejected:")
        else:
            assert recovery_outcome == "ok"
    else:
        assert recovery_outcome == "ok"
        assert boundary_outcome.startswith("rejected:")

    effect = {
        "provider-dispatch": "provider-constructed",
        "process-dispatch": "create-process",
        "resume-dispatch": "resume-thread",
        "process-persistence": "create-process",
        "resume-persistence": "resume-thread",
    }[scenario]
    expected_effects = 0 if winner == "recovery" and not persistence else 1
    assert boundary_events.count(effect) == expected_effects

    verify = _connect(db_path)
    state = verify.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone()[0]
    if winner == "recovery" or not persistence:
        assert state == "MANUAL_REVIEW"
        assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
            1,
        )
    else:
        assert state == "PROCESS_CREATED"
        assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
            0,
        )
    if scenario == "process-persistence":
        assert verify.execute("SELECT count(*) FROM launch_executions").fetchone() == (
            1 if winner == "boundary" else 0,
        )
    if scenario == "resume-persistence":
        assert execution_id is not None
        expected = (
            ("RESUME_RECORDED", 1)
            if winner == "boundary"
            else ("RESUME_INTENT_COMMITTED", 0)
        )
        assert (
            verify.execute(
                "SELECT phase, post_resume_json IS NOT NULL FROM launch_executions "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()
            == expected
        )
    assert verify.execute("PRAGMA foreign_key_check").fetchall() == []
    verify.close()


def test_spawned_arbiter_namespace_is_temp_and_cwd_independent(
    tmp_path: Path,
) -> None:
    reservation_id = "cross-environment/reservation"
    first_temp = tmp_path / "first-temp"
    second_temp = tmp_path / "second-temp"
    first_cwd = tmp_path / "first-cwd"
    second_cwd = tmp_path / "second-cwd"
    for directory in (first_temp, second_temp, first_cwd, second_cwd):
        directory.mkdir()

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    release = context.Event()
    first_attempting = context.Event()
    first_acquired = context.Event()
    second_attempting = context.Event()
    second_acquired = context.Event()
    effect_count = context.Value("i", 0, lock=False)
    first = context.Process(
        target=_spawn_cross_environment_arbiter_worker,
        args=(
            reservation_id,
            str(first_temp),
            str(first_cwd),
            "first",
            first_attempting,
            first_acquired,
            release,
            True,
            effect_count,
            result_queue,
        ),
    )
    second = context.Process(
        target=_spawn_cross_environment_arbiter_worker,
        args=(
            reservation_id,
            str(second_temp),
            str(second_cwd),
            "second",
            second_attempting,
            second_acquired,
            release,
            False,
            effect_count,
            result_queue,
        ),
    )
    with _spawn_temp_environment(first_temp):
        first.start()
    assert first_attempting.wait(20)
    assert first_acquired.wait(20)
    with _spawn_temp_environment(second_temp):
        second.start()
    assert second_attempting.wait(20)
    second_blocked_until_release = not second_acquired.wait(1)
    release.set()
    first.join(20)
    second.join(20)
    assert first.exitcode == 0
    assert second.exitcode == 0
    assert second_blocked_until_release
    assert second_acquired.is_set()

    messages = [result_queue.get(timeout=10) for _ in range(4)]
    path_messages = [message for message in messages if message[0] == "path"]
    result_messages = [message for message in messages if message[0] == "result"]
    paths = {
        message[1]: (message[2], message[3], message[4]) for message in path_messages
    }
    results = {message[1]: (message[2], message[3]) for message in result_messages}
    assert set(paths) == {"first", "second"}
    assert set(results) == {"first", "second"}
    assert paths["first"] == paths["second"]
    root, path, identity = paths["first"]
    assert Path(root) == _LIFECYCLE_ARBITER_ROOT
    assert Path(path) == _LIFECYCLE_ARBITER_ROOT / f"{identity}.lock"
    expected_material = json.dumps(
        {
            "authority_epoch_id": EPOCH,
            "label": "lifecycle-arbiter/v1",
            "launch_reservation_id": reservation_id,
            "machine_authority_id": MACHINE,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert identity == hashlib.sha256(expected_material).hexdigest()
    assert sum(emitted for emitted, _ in results.values()) == 1
    assert effect_count.value == 1


def test_spawned_process_crash_releases_lifecycle_arbiter_without_retry(
    db_path: Path, tmp_path: Path
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    permit = reserve_launch(setup, claim_id)
    reservation_id = str(permit)
    setup.close()
    crashed_temp = tmp_path / "crashed-owner-temp"
    recovery_temp = tmp_path / "recovery-temp"
    crashed_temp.mkdir()
    recovery_temp.mkdir()

    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    crashed = context.Process(
        target=_spawn_crash_while_holding_arbiter,
        args=(reservation_id, acquired),
    )
    with _spawn_temp_environment(crashed_temp):
        crashed.start()
    assert acquired.wait(20)
    crashed.join(20)
    assert crashed.exitcode == 23

    result_queue = context.Queue()
    go = context.Event()
    started = context.Event()
    recovery_acquired = context.Event()
    recovery_release = context.Event()
    recovery = context.Process(
        target=_spawn_recovery_worker,
        args=(
            _descriptor_for(db_path),
            session_id,
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
            False,
            result_queue,
            go,
            recovery_acquired,
            recovery_release,
            started,
        ),
    )
    with _spawn_temp_environment(recovery_temp):
        recovery.start()
    go.set()
    assert started.wait(20)
    recovery.join(20)
    assert recovery.exitcode == 0
    assert result_queue.get(timeout=10)[:2] == ("recovery", "ok")
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (1,)
    verify.close()


def test_spawned_process_rejects_reconstructed_process_local_capabilities(
    db_path: Path,
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    permit = reserve_launch(setup, claim_id)
    reservation_id = str(permit)
    setup.close()
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    child = context.Process(
        target=_spawn_reconstructed_capability_worker,
        args=(_descriptor_for(db_path), reservation_id, result_queue),
    )
    child.start()
    child.join(20)
    assert child.exitcode == 0
    outcomes = result_queue.get(timeout=10)
    assert len(outcomes) == 2
    assert all(outcome.startswith("rejected:") for outcome in outcomes)
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state, process_intent_json "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("COMMITTED", None)
    verify.close()


def test_spawned_outer_transaction_rejects_before_arbiter_and_releases_writer(
    db_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    setup_queue = context.Queue()
    result_queue = context.Queue()
    recovery_acquired = context.Event()
    transaction_started = context.Event()
    transaction_released = context.Event()
    boundary = context.Process(
        target=_spawn_outer_transaction_boundary_worker,
        args=(
            _descriptor_for(db_path),
            setup_queue,
            result_queue,
            recovery_acquired,
            transaction_started,
            transaction_released,
        ),
    )
    boundary.start()
    session_id, reservation_id = setup_queue.get(timeout=30)
    recovery = context.Process(
        target=_spawn_recovery_after_outer_transaction_worker,
        args=(
            _descriptor_for(db_path),
            session_id,
            reservation_id,
            result_queue,
            recovery_acquired,
            transaction_started,
            transaction_released,
        ),
    )
    recovery.start()
    boundary.join(20)
    recovery.join(20)
    assert boundary.exitcode == 0
    assert recovery.exitcode == 0
    outcomes = dict([result_queue.get(timeout=10), result_queue.get(timeout=10)])
    assert set(outcomes) == {"boundary", "recovery"}
    assert outcomes["boundary"] == (
        "lifecycle boundary requires no active SQLite transaction"
    )
    assert uuid.UUID(outcomes["recovery"]).version == 5
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state, process_intent_json "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW", None)
    assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (1,)
    assert verify.execute("PRAGMA foreign_key_check").fetchall() == []
    assert verify.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    verify.close()


def test_spawned_stored_observer_transaction_rejects_before_arbiter(
    db_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    setup_queue = context.Queue()
    result_queue = context.Queue()
    recovery_acquired = context.Event()
    transaction_started = context.Event()
    transaction_released = context.Event()
    boundary = context.Process(
        target=_spawn_stored_observer_transaction_boundary_worker,
        args=(
            _descriptor_for(db_path),
            setup_queue,
            result_queue,
            recovery_acquired,
            transaction_started,
            transaction_released,
        ),
    )
    boundary.start()
    session_id, reservation_id = setup_queue.get(timeout=30)
    recovery = context.Process(
        target=_spawn_recovery_after_outer_transaction_worker,
        args=(
            _descriptor_for(db_path),
            session_id,
            reservation_id,
            result_queue,
            recovery_acquired,
            transaction_started,
            transaction_released,
        ),
    )
    recovery.start()
    boundary.join(20)
    recovery.join(20)
    assert boundary.exitcode == 0
    assert recovery.exitcode == 0
    outcomes = dict([result_queue.get(timeout=10), result_queue.get(timeout=10)])
    assert set(outcomes) == {"boundary", "recovery"}
    assert outcomes["boundary"] == (
        "lifecycle boundary requires no active SQLite transaction",
        True,
        False,
        [],
    )
    assert uuid.UUID(outcomes["recovery"]).version == 5
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state, process_intent_json "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone() == ("MANUAL_REVIEW", None)
    assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (1,)
    assert verify.execute("PRAGMA foreign_key_check").fetchall() == []
    assert verify.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    verify.close()


def _prepare_active_transaction_boundary(
    connection: sqlite3.Connection,
    boundary: str,
) -> tuple[Callable[[], object], object | None, list[str]]:
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    service = _test_service(connection)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation = reserve_launch(connection, claim_id)
    reservation_id = str(reservation)

    if boundary == "recover-launch-reservation":
        return (
            lambda: service.record_recovery(
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_LAUNCH_RESERVATION",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            ),
            None,
            events,
        )

    provider = hooks.construct_provider(reservation)
    if boundary == "commit-process-intent":
        return (
            lambda: service.commit_process_intent(reservation_id, provider),
            provider,
            events,
        )

    process_intent = commit_process_intent(connection, reservation_id, provider)
    if boundary == "recover-process-outcome":
        return (
            lambda: service.record_recovery(
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            ),
            None,
            events,
        )

    process_result = hooks.create_process(
        process_intent, fail=boundary == "record-process-creation-failure"
    )
    if boundary == "record-process-creation-failure":
        assert type(process_result) is FakeProcessCreationFailure
        return (
            lambda: service.record_process_creation_failure(
                reservation_id, process_result
            ),
            process_result,
            events,
        )
    assert type(process_result) is FakeProcessCreationReceipt
    if boundary == "record-execution":
        return (
            lambda: service.record_execution(reservation_id, process_result),
            process_result,
            events,
        )

    execution_id = record_execution(connection, reservation_id, process_result)
    if boundary == "recover-pre-resume":
        return (
            lambda: service.record_recovery(
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_PRE_RESUME_READY",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            ),
            None,
            events,
        )
    if boundary == "commit-resume-intent":
        return (
            lambda: service.commit_resume_intent(execution_id, reservation_id),
            None,
            events,
        )

    resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
    if boundary == "recover-resume-outcome":
        return (
            lambda: service.record_recovery(
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            ),
            None,
            events,
        )

    resume_receipt = hooks.resume_thread(resume_intent)
    if boundary == "record-post-resume-evidence":
        return (
            lambda: service.record_post_resume_evidence(execution_id, resume_receipt),
            resume_receipt,
            events,
        )

    assert boundary == "record-terminal"
    record_post_resume_evidence(connection, execution_id, resume_receipt)
    return (
        lambda: service.record_terminal(
            reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        ),
        None,
        events,
    )


def _prepare_stored_observer_boundary(
    connection: sqlite3.Connection,
    hooks: FakeSideEffects,
    boundary: str,
) -> tuple[Callable[[], object], object, str]:
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    permit = reserve_launch(connection, claim_id)
    reservation_id = str(permit)
    if boundary == "construct-provider":
        return (
            lambda: hooks.construct_provider(permit),
            permit,
            "provider-constructed",
        )

    provider = hooks.construct_provider(permit)
    process_intent = commit_process_intent(connection, reservation_id, provider)
    if boundary == "create-process":
        return (
            lambda: hooks.create_process(process_intent),
            process_intent,
            "create-process",
        )

    assert boundary == "resume-thread"
    process_result = hooks.create_process(process_intent)
    assert type(process_result) is FakeProcessCreationReceipt
    execution_id = record_execution(connection, reservation_id, process_result)
    resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
    return (
        lambda: hooks.resume_thread(resume_intent),
        resume_intent,
        "resume-thread",
    )


@pytest.mark.parametrize(
    "boundary",
    [
        "commit-process-intent",
        "record-execution",
        "record-process-creation-failure",
        "commit-resume-intent",
        "record-post-resume-evidence",
        "record-terminal",
        "recover-launch-reservation",
        "recover-process-outcome",
        "recover-pre-resume",
        "recover-resume-outcome",
    ],
)
def test_arbiter_sqlite_boundaries_reject_active_caller_transaction_before_lock(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    connection = _connect(db_path)
    invoke, capability, events = _prepare_active_transaction_boundary(
        connection, boundary
    )
    before = _database_rows(connection)
    events_before = list(events)
    arbiter_attempts: list[str] = []

    class ArbiterProbe:
        def __init__(self, reservation_id: str) -> None:
            arbiter_attempts.append(str(reservation_id))

        def __enter__(self) -> ArbiterProbe:
            raise AssertionError("active transaction reached arbiter acquisition")

        def __exit__(self, *args: object) -> None:
            return None

    connection.execute("BEGIN IMMEDIATE")
    traces: list[str] = []
    connection.set_trace_callback(traces.append)
    with monkeypatch.context() as context:
        context.setattr(
            sys.modules[__name__], "InterprocessLifecycleArbiter", ArbiterProbe
        )
        with pytest.raises(
            ValueError,
            match="lifecycle boundary requires no active SQLite transaction",
        ):
            invoke()
    connection.set_trace_callback(None)
    assert traces == []
    assert arbiter_attempts == []
    assert connection.in_transaction
    assert events == events_before
    assert _database_rows(connection) == before
    if capability is not None:
        _assert_capability_available(capability)
    connection.rollback()
    assert not connection.in_transaction

    result = invoke()
    assert result is not None or boundary in {
        "record-process-creation-failure",
        "record-post-resume-evidence",
    }
    if capability is not None:
        _assert_capability_consumed(capability)
    assert _database_rows(connection) != before
    connection.close()


@pytest.mark.parametrize(
    "transaction_entry",
    ["BEGIN IMMEDIATE", "SAVEPOINT caller_work"],
    ids=["begin-immediate", "savepoint"],
)
@pytest.mark.parametrize("action", list(_RECOVERY_ACTIONS))
def test_every_recovery_action_rejects_active_transaction_before_dispatch(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    transaction_entry: str,
) -> None:
    connection = _connect(db_path)
    session_id, target_kind, target_id, _, _ = _prepare_recovery_chronology_case(
        connection, action
    )
    service = _test_service(connection)
    before = _database_rows(connection)
    arbiter_attempts: list[str] = []

    class ArbiterProbe:
        def __init__(self, reservation_id: str) -> None:
            arbiter_attempts.append(str(reservation_id))

        def __enter__(self) -> ArbiterProbe:
            raise AssertionError("active recovery reached arbiter acquisition")

        def __exit__(self, *args: object) -> None:
            return None

    connection.execute(transaction_entry)
    traces: list[str] = []
    connection.set_trace_callback(traces.append)
    with monkeypatch.context() as context:
        context.setattr(
            sys.modules[__name__], "InterprocessLifecycleArbiter", ArbiterProbe
        )
        with pytest.raises(
            ValueError,
            match="lifecycle boundary requires no active SQLite transaction",
        ):
            service.record_recovery(
                session_id,
                target_kind,
                target_id,
                action,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
    connection.set_trace_callback(None)

    assert traces == []
    assert arbiter_attempts == []
    assert connection.in_transaction
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (0,)

    if transaction_entry.startswith("SAVEPOINT"):
        connection.execute("ROLLBACK TO caller_work")
        connection.execute("RELEASE caller_work")
    else:
        connection.rollback()
    assert not connection.in_transaction

    recovery_id = service.record_recovery(
        session_id,
        target_kind,
        target_id,
        action,
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert type(recovery_id) is str
    assert _database_rows(connection) != before
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (1,)
    connection.close()


@pytest.mark.parametrize(
    "transaction_entry",
    ["BEGIN IMMEDIATE", "SAVEPOINT caller_work"],
    ids=["begin-immediate", "savepoint"],
)
@pytest.mark.parametrize(
    "boundary",
    ["construct-provider", "create-process", "resume-thread"],
)
def test_stored_observer_boundaries_reject_active_transaction_before_lock(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    transaction_entry: str,
) -> None:
    connection = _connect(db_path)
    observer = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(observer, events, service=_test_service(connection))
    invoke, capability, effect = _prepare_stored_observer_boundary(
        connection, hooks, boundary
    )
    before = _database_rows(observer)
    events_before = list(events)
    arbiter_attempts: list[str] = []

    class ArbiterProbe:
        def __init__(self, reservation_id: str) -> None:
            arbiter_attempts.append(str(reservation_id))

        def __enter__(self) -> ArbiterProbe:
            raise AssertionError("active observer transaction reached arbiter")

        def __exit__(self, *args: object) -> None:
            return None

    observer.execute(transaction_entry)
    traces: list[str] = []
    observer.set_trace_callback(traces.append)
    with monkeypatch.context() as context:
        context.setattr(
            sys.modules[__name__], "InterprocessLifecycleArbiter", ArbiterProbe
        )
        with pytest.raises(
            ValueError,
            match="lifecycle boundary requires no active SQLite transaction",
        ):
            invoke()
    observer.set_trace_callback(None)
    assert traces == []
    assert arbiter_attempts == []
    assert observer.in_transaction
    assert events == events_before
    assert _database_rows(observer) == before
    _assert_capability_available(capability)
    if transaction_entry.startswith("SAVEPOINT"):
        observer.execute("ROLLBACK TO caller_work")
        observer.execute("RELEASE caller_work")
    else:
        observer.rollback()
    assert not observer.in_transaction

    result = invoke()
    assert result is not None
    _assert_capability_consumed(capability)
    assert events.count(effect) == events_before.count(effect) + 1
    events_after_success = list(events)
    with pytest.raises(ValueError):
        invoke()
    assert events == events_after_success
    observer.close()
    connection.close()


def test_reservation_recovery_validates_ordinal_before_transaction_guard(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = str(reserve_launch(connection, claim_id))
    service = _test_service(connection)
    before = _database_rows(connection)
    arbiter_attempts: list[str] = []

    class ArbiterProbe:
        def __init__(self, selected_reservation_id: str) -> None:
            arbiter_attempts.append(selected_reservation_id)

    connection.execute("BEGIN IMMEDIATE")
    with monkeypatch.context() as context:
        context.setattr(
            sys.modules[__name__], "InterprocessLifecycleArbiter", ArbiterProbe
        )
        with pytest.raises(ValueError, match="exact non-negative int"):
            service.record_recovery(
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_LAUNCH_RESERVATION",
                ordinal=False,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
    assert arbiter_attempts == []
    assert connection.in_transaction
    assert _database_rows(connection) == before
    connection.rollback()
    connection.close()


def test_lifecycle_arbiter_identity_and_global_lock_order_are_explicit() -> None:
    import trading_bot.runtime.windows_transactional_authority as production

    production_source = Path(production.__file__).read_text(encoding="utf-8")
    assert "GlobalLifecycleMutex" in production_source
    assert "Local\\AITradingBot" not in production_source
    assert "threading.RLock" not in production_source
    for operation in (
        production._core_commit_process_intent,
        production._core_record_execution,
        production._core_record_process_creation_failure,
        production._core_commit_resume_intent,
        production._core_record_post_resume_evidence,
        production._core_record_terminal,
        production._core_record_recovery,
    ):
        source = inspect.getsource(operation)
        assert source.index("_require_no_active_transaction") < source.index(
            "_lifecycle_arbiter"
        )
        assert source.index("_lifecycle_arbiter") < source.index("_locked")

    from trading_bot.runtime.windows_authority_mutex import (
        canonical_lifecycle_mutex_material,
        lifecycle_mutex_digest,
        lifecycle_mutex_name,
    )

    material = canonical_lifecycle_mutex_material(
        MACHINE, EPOCH, "reservation/raw/value"
    )
    assert material == (
        b'{"authority_epoch_id":"12345678-1234-5678-9abc-def012345678",'
        b'"label":"lifecycle-arbiter/v1",'
        b'"launch_reservation_id":"reservation/raw/value",'
        b'"machine_authority_id":"87654321-4321-8765-cba9-876543210987"}'
    )
    digest = lifecycle_mutex_digest(MACHINE, EPOCH, "reservation/raw/value")
    assert digest == hashlib.sha256(material).hexdigest()
    assert lifecycle_mutex_name(MACHINE, EPOCH, "reservation/raw/value") == (
        "Global\\AITradingBot-Lifecycle-v1-" + digest
    )

    adapter = InterprocessLifecycleArbiter("reservation/raw/value")
    assert adapter.identity == digest
    assert adapter.path.parent == _LIFECYCLE_ARBITER_ROOT


def test_lifecycle_transaction_guard_requires_exact_sqlite_connection() -> None:
    class ConnectionSubclass(sqlite3.Connection):
        pass

    exact_connection = sqlite3.connect(":memory:", isolation_level=None)
    exact_connection.execute("SAVEPOINT caller_work")
    try:
        with pytest.raises(ValueError, match="no active SQLite transaction"):
            _require_no_active_transaction(exact_connection)
        assert exact_connection.in_transaction
        exact_connection.execute("ROLLBACK TO caller_work")
        exact_connection.execute("RELEASE caller_work")
        assert not exact_connection.in_transaction
    finally:
        exact_connection.close()

    connection = sqlite3.connect(":memory:", factory=ConnectionSubclass)
    try:
        with pytest.raises(TypeError, match="exact sqlite3.Connection"):
            _require_no_active_transaction(connection)
    finally:
        connection.close()


@pytest.mark.parametrize(
    (
        "request_field",
        "request_value",
        "remove_field",
        "metadata_provider_id",
        "metadata_operation",
    ),
    [
        ("provider_id", "different-provider", False, PROVIDER, OPERATION),
        (
            "permitted_provider_operation",
            "different-operation",
            False,
            PROVIDER,
            OPERATION,
        ),
        (None, None, False, "different-provider", OPERATION),
        (None, None, False, PROVIDER, "different-operation"),
        ("provider_id", "", False, PROVIDER, OPERATION),
        ("permitted_provider_operation", "", False, PROVIDER, OPERATION),
        ("provider_id", "ALPACA_MARKET_DATA", False, PROVIDER, OPERATION),
        (
            "permitted_provider_operation",
            "HISTORICAL_DAILY_BARS",
            False,
            PROVIDER,
            OPERATION,
        ),
        ("provider_id", None, True, PROVIDER, OPERATION),
        ("permitted_provider_operation", None, True, PROVIDER, OPERATION),
        ("provider_id", 1, False, PROVIDER, OPERATION),
        ("permitted_provider_operation", [OPERATION], False, PROVIDER, OPERATION),
    ],
    ids=[
        "request-provider-mismatch",
        "request-operation-mismatch",
        "metadata-provider-mismatch",
        "metadata-operation-mismatch",
        "blank-provider",
        "blank-operation",
        "legacy-provider",
        "legacy-operation",
        "missing-provider",
        "missing-operation",
        "provider-wrong-type",
        "operation-wrong-type",
    ],
)
def test_session_creation_rejects_descriptor_drift_before_persistence(
    request_field: str | None,
    request_value: object,
    remove_field: bool,
    metadata_provider_id: str,
    metadata_operation: str,
) -> None:
    harness = Architecture77HarnessAuthority.create()
    connection = harness._connection
    try:
        _seed_harness_metadata(
            harness,
            provider_id=metadata_provider_id,
            permitted_provider_operation=metadata_operation,
        )
        core = harness._core
        side_effects = FakeSideEffects(connection)
        request = _request()
        if request_field is not None:
            if remove_field:
                del request[request_field]
            else:
                request[request_field] = request_value

        with pytest.raises(ValueError):
            core.create_session(request)

        assert connection.execute(
            "SELECT count(*), coalesce(sum(next_attempt_ordinal), 0), "
            "coalesce(sum(next_recovery_ordinal), 0) FROM sessions"
        ).fetchone() == (0, 0, 0)
        assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM provider_call_claims"
        ).fetchone() == (0,)
        assert side_effects.events == []
    finally:
        harness.close()


def _assert_no_capture_authority_side_effects(
    connection: sqlite3.Connection,
) -> None:
    for table in (
        "sessions",
        "attempts",
        "provider_call_claims",
        "launch_reservations",
        "launch_executions",
        "terminals",
        "session_selections",
        "manual_recoveries",
    ):
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_validated_capture_request_is_frozen_and_detached_from_caller() -> None:
    caller_request = _request()
    caller_universe = caller_request["ordered_universe"]
    assert type(caller_universe) is list
    snapshot = _snapshot_capture_request(caller_request)

    caller_universe.append("IWM")
    caller_request["ordered_universe"] = ["DIA"]
    caller_request["request_limit"] = 1
    caller_request["target_session_date"] = "2099-12-31"

    assert snapshot.ordered_universe == ("QQQ", "SPY")
    assert snapshot.request_limit == 2
    assert snapshot.target_session_date == "2026-01-01"
    assert snapshot.ordered_universe is not caller_universe
    assert not hasattr(snapshot, "__dict__")
    assert all(
        type(getattr(snapshot, field_name)) not in (dict, list)
        for field_name in snapshot.__dataclass_fields__
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.target_session_date = "2099-12-31"  # type: ignore[misc]


def test_capture_snapshot_recreates_existing_exact_canonical_json() -> None:
    snapshot = _snapshot_capture_request(_request())
    expected = (
        b'{"bar_interval":"1d","child_operation_version":"child/v1",'
        b'"ordered_universe":["QQQ","SPY"],"output_policy_version":"output/v1",'
        b'"permitted_provider_operation":"historical-stock-bars-v2-raw-usd-no-asof",'
        b'"provider_id":"alpaca-market-data","request_limit":2,'
        b'"request_window_end_date":"2025-12-31",'
        b'"request_window_start_date":"2025-12-01",'
        b'"target_session_date":"2026-01-01"}'
    )
    assert snapshot.canonical_json() == expected == _json(_request())


def test_caller_mutation_after_snapshot_cannot_desynchronize_session(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connect(db_path)
    caller_request = _request()
    caller_universe = caller_request["ordered_universe"]
    assert type(caller_universe) is list
    snapshots: list[ValidatedCaptureRequest] = []
    snapshot_function = _snapshot_capture_request

    def snapshot_then_mutate(request: object) -> ValidatedCaptureRequest:
        snapshot = snapshot_function(request)
        snapshots.append(snapshot)
        assert type(request) is dict
        caller_universe.append("IWM")
        request["ordered_universe"] = ["DIA"]
        request["request_limit"] = 1
        request["target_session_date"] = "2099-12-31"
        return snapshot

    service = _test_service(connection, capture_request_factory=snapshot_then_mutate)
    session_id = service.create_session(caller_request)
    snapshot = snapshots[0]
    expected_bytes = snapshot.canonical_json()
    expected_id = _session_id(
        snapshot,
        machine_authority_id=MACHINE,
        authority_epoch_id=EPOCH,
        authority_policy_version=POLICY,
        claim_policy_version=CLAIM_POLICY,
    )
    assert session_id == expected_id
    assert connection.execute(
        "SELECT target_session_date, request_json, request_digest "
        "FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (
        snapshot.target_session_date,
        expected_bytes,
        _digest(expected_bytes),
    )
    assert caller_request != json.loads(expected_bytes)
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (0,)
    connection.close()


def test_capture_snapshot_accepts_canonical_period_and_hyphen_symbols() -> None:
    request = _request()
    request["ordered_universe"] = ["BRK.B", "ABC-1"]
    snapshot = _snapshot_capture_request(request)
    assert snapshot.ordered_universe == ("BRK.B", "ABC-1")
    assert json.loads(snapshot.canonical_json())["ordered_universe"] == [
        "BRK.B",
        "ABC-1",
    ]


def test_symbol_normalization_equivalence_is_detected_as_duplicate() -> None:
    request = _request()
    request["ordered_universe"] = ["SPY", "spy"]
    with pytest.raises(ValueError, match="duplicate-free"):
        _snapshot_capture_request(request)


@pytest.mark.parametrize(
    ("authority_policy_version", "claim_policy_version"),
    [
        ("authority-policy/v2", CLAIM_POLICY),
        (POLICY, "claim-policy/v2"),
    ],
    ids=["unsupported-authority-policy", "unsupported-claim-policy"],
)
def test_session_creation_rejects_unsupported_signed_policy_before_persistence(
    authority_policy_version: str,
    claim_policy_version: str,
) -> None:
    harness = Architecture77HarnessAuthority.create()
    connection = harness._connection
    try:
        _seed_harness_metadata(
            harness,
            authority_policy_version=authority_policy_version,
            claim_policy_version=claim_policy_version,
        )
        core = harness._core
        side_effects = FakeSideEffects(connection)

        with pytest.raises(ValueError, match="policy is unsupported"):
            core.create_session(_request())

        _assert_no_capture_authority_side_effects(connection)
        assert side_effects.events == []
    finally:
        harness.close()


@pytest.mark.parametrize("missing_field", sorted(CAPTURE_REQUEST_FIELDS))
def test_capture_request_requires_every_exact_field(
    db_path: Path, missing_field: str
) -> None:
    connection = _connect(db_path)
    request = _request()
    del request[missing_field]
    with pytest.raises(ValueError):
        create_session(connection, request)
    _assert_no_capture_authority_side_effects(connection)
    connection.close()


def _invalid_capture_request(case: str) -> object:
    request: object = _request()
    assert isinstance(request, dict)
    if case == "not-exact-dict":
        return list(request.items())
    if case == "unknown-field":
        request["unknown"] = "value"
    elif case == "request-limit-string":
        request["request_limit"] = "2"
    elif case == "request-limit-bool":
        request["request_limit"] = True
    elif case == "request-limit-zero":
        request["request_limit"] = 0
    elif case == "request-limit-mismatch":
        request["request_limit"] = 1
    elif case == "tuple-universe":
        request["ordered_universe"] = ("QQQ", "SPY")
    elif case == "nonstring-universe-member":
        request["ordered_universe"] = ["QQQ", 1]
    elif case == "duplicate-universe":
        request["ordered_universe"] = ["QQQ", "QQQ"]
    elif case == "empty-universe":
        request["ordered_universe"] = []
        request["request_limit"] = 0
    elif case == "oversized-universe":
        request["ordered_universe"] = [
            f"SYM{index}" for index in range(MAX_DAILY_SNAPSHOT_SYMBOLS + 1)
        ]
        request["request_limit"] = MAX_DAILY_SNAPSHOT_SYMBOLS + 1
    elif case == "blank-universe-member":
        request["ordered_universe"] = ["QQQ", ""]
    elif case == "whitespace-universe-member":
        request["ordered_universe"] = ["QQQ", "   "]
    elif case == "lowercase-symbol":
        request["ordered_universe"] = ["QQQ", "spy"]
    elif case == "padded-symbol":
        request["ordered_universe"] = ["QQQ", " SPY "]
    elif case == "overlong-symbol":
        request["ordered_universe"] = ["QQQ", "ABCDEFGHIJK"]
    elif case == "unsupported-symbol-punctuation":
        request["ordered_universe"] = ["QQQ", "BRK_B"]
    elif case == "normalization-equivalent-symbols":
        request["ordered_universe"] = ["SPY", "spy"]
    elif case == "malformed-date":
        request["request_window_start_date"] = "2025-13-01"
    elif case == "noncanonical-date":
        request["target_session_date"] = "20260101"
    elif case == "window-reversed":
        request["request_window_start_date"] = "2026-01-01"
    elif case == "window-not-before-target":
        request["request_window_end_date"] = "2026-01-01"
    elif case.startswith("invalid-fixed-"):
        field_name = case.removeprefix("invalid-fixed-")
        request[field_name] = "invalid"
    elif case == "string-field-bool":
        request["bar_interval"] = True
    else:
        raise AssertionError(f"unhandled invalid capture request: {case}")
    return request


@pytest.mark.parametrize(
    "case",
    [
        "not-exact-dict",
        "unknown-field",
        "request-limit-string",
        "request-limit-bool",
        "request-limit-zero",
        "request-limit-mismatch",
        "tuple-universe",
        "nonstring-universe-member",
        "duplicate-universe",
        "empty-universe",
        "oversized-universe",
        "blank-universe-member",
        "whitespace-universe-member",
        "lowercase-symbol",
        "padded-symbol",
        "overlong-symbol",
        "unsupported-symbol-punctuation",
        "normalization-equivalent-symbols",
        "malformed-date",
        "noncanonical-date",
        "window-reversed",
        "window-not-before-target",
        "invalid-fixed-bar_interval",
        "invalid-fixed-child_operation_version",
        "invalid-fixed-output_policy_version",
        "invalid-fixed-provider_id",
        "invalid-fixed-permitted_provider_operation",
        "string-field-bool",
    ],
)
def test_capture_request_rejects_noncanonical_shapes_without_side_effects(
    db_path: Path, case: str
) -> None:
    connection = _connect(db_path)
    side_effects = FakeSideEffects(connection)
    with pytest.raises(ValueError):
        create_session(connection, _invalid_capture_request(case))  # type: ignore[arg-type]
    _assert_no_capture_authority_side_effects(connection)
    assert side_effects.events == []
    connection.close()


def test_invalid_alternate_request_cannot_collide_with_persisted_session(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    valid_request = _request()
    session_id = create_session(connection, valid_request)
    alternate = {**valid_request, "ordered_universe": ("QQQ", "SPY")}
    with pytest.raises(ValueError, match="exact list"):
        create_session(connection, alternate)  # type: ignore[arg-type]
    assert connection.execute(
        "SELECT session_id, request_json, next_attempt_ordinal, "
        "next_recovery_ordinal FROM sessions"
    ).fetchall() == [
        (
            session_id,
            _snapshot_capture_request(valid_request).canonical_json(),
            0,
            0,
        )
    ]
    connection.close()


def _seed_lifecycle(path: Path) -> dict[str, str]:
    connection = _connect(path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id, reservation_id)
    terminal_id = record_terminal(
        connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    connection.close()
    return {
        "session_id": session_id,
        "attempt_id": attempt_id,
        "claim_id": claim_id,
        "reservation_id": reservation_id,
        "execution_id": execution_id,
        "terminal_id": terminal_id,
    }


def test_complete_ddl_and_immediate_parent_chain(db_path: Path) -> None:
    connection = _connect(db_path)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert tables == {
        "authority_metadata",
        "schema_migrations",
        "sessions",
        "attempts",
        "provider_call_claims",
        "launch_reservations",
        "launch_executions",
        "terminals",
        "session_selections",
        "manual_recoveries",
    }
    parents = {
        "schema_migrations": "authority_metadata",
        "sessions": "authority_metadata",
        "attempts": "sessions",
        "provider_call_claims": "attempts",
        "launch_reservations": "provider_call_claims",
        "launch_executions": "launch_reservations",
        "terminals": "launch_reservations",
        "session_selections": "sessions,terminals",
        "manual_recoveries": "sessions",
    }
    for table, expected in parents.items():
        actual = {
            row[2] for row in connection.execute(f"PRAGMA foreign_key_list({table})")
        }
        assert actual == set(expected.split(","))
    execution_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(launch_executions)")
    }
    assert {
        "resume_intent_json",
        "resume_intent_digest",
        "resume_intent_committed_at_utc",
    } <= execution_columns
    assert connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'launch_executions_resume_intent_append_only'"
    ).fetchone() == (1,)
    reservation_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(launch_reservations)")
    }
    assert {
        "process_intent_json",
        "process_intent_digest",
        "process_intent_committed_at_utc",
    } <= reservation_columns
    assert connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'launch_reservations_process_intent_append_only'"
    ).fetchone() == (1,)
    policy_triggers = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' "
            "AND name IN ('sessions_before_insert', 'attempts_before_insert', "
            "'provider_call_claims_before_insert', "
            "'launch_reservations_before_insert', "
            "'launch_executions_parent_policy_before_insert')"
        )
    }
    assert policy_triggers == {
        "sessions_before_insert",
        "attempts_before_insert",
        "provider_call_claims_before_insert",
        "launch_reservations_before_insert",
        "launch_executions_parent_policy_before_insert",
    }
    connection.close()


@pytest.mark.parametrize(
    "table",
    [
        "sessions",
        "attempts",
        "provider_call_claims",
        "launch_reservations",
        "launch_executions",
        "terminals",
        "session_selections",
        "manual_recoveries",
    ],
)
@pytest.mark.parametrize("unsupported_schema", [0, 2, 99])
def test_identity_bearing_rows_reject_unsupported_schema_at_insert(
    db_path: Path, table: str, unsupported_schema: int
) -> None:
    connection = _connect(db_path)
    session_id: str | None = None
    process_intent: FakeProcessIntent | None = None

    if table == "sessions":
        request = _snapshot_capture_request(_request()).canonical_json()

        def insert_invalid() -> None:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, authority_epoch_id, session_schema,
                    authority_policy_version, claim_policy_version,
                    target_session_date, state, next_attempt_ordinal,
                    next_recovery_ordinal, request_json, request_digest,
                    created_at_utc, closed_at_utc, close_reason
                ) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', 0, 0, ?, ?, ?, NULL, NULL)
                """,
                (
                    f"unsupported-session-schema-{unsupported_schema}",
                    EPOCH,
                    unsupported_schema,
                    POLICY,
                    CLAIM_POLICY,
                    "2026-01-01",
                    request,
                    _digest(request),
                    TIMESTAMP,
                ),
            )

    else:
        session_id = create_session(connection)
        if table == "attempts":
            request, request_digest = connection.execute(
                "SELECT request_json, request_digest FROM sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            def insert_invalid() -> None:
                _insert_attempt_row_for_test(
                    connection,
                    session_id,
                    0,
                    request,
                    request_digest,
                    attempt_schema=unsupported_schema,
                )

        else:
            attempt_id = allocate_attempt(connection, session_id)
            request, request_digest = connection.execute(
                "SELECT request_json, request_digest FROM attempts "
                "WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if table == "provider_call_claims":

                def insert_invalid() -> None:
                    _insert_claim_row_for_test(
                        connection,
                        attempt_id,
                        request,
                        request_digest,
                        claim_schema=unsupported_schema,
                    )

            else:
                claim_id = commit_claim(connection, attempt_id)
                if table == "launch_reservations":

                    def insert_invalid() -> None:
                        _insert_reservation_row_for_test(
                            connection,
                            claim_id,
                            request_digest,
                            launch_reservation_schema=unsupported_schema,
                        )

                else:
                    reservation_id = reserve_launch(connection, claim_id)
                    if table == "launch_executions":
                        process_intent = _construct_provider_and_commit_process_intent(
                            connection, reservation_id
                        )

                        def insert_invalid() -> None:
                            _insert_execution_row_for_test(
                                connection,
                                reservation_id,
                                launch_schema=unsupported_schema,
                            )

                    elif table == "manual_recoveries":

                        def insert_invalid() -> None:
                            _insert_recovery_fact_for_test(
                                connection,
                                session_id,
                                "SESSION",
                                session_id,
                                "ACKNOWLEDGE_RESTORE",
                                recovery_schema=unsupported_schema,
                                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                            )

                    else:
                        execution_id = _record_successful_process(
                            connection, reservation_id
                        )
                        _resume_and_persist(connection, execution_id, reservation_id)
                        if table == "terminals":

                            def insert_invalid() -> None:
                                _insert_terminal_row_for_test(
                                    connection,
                                    reservation_id,
                                    request_digest,
                                    "SUCCEEDED",
                                    "CONFIRMED",
                                    terminal_schema=unsupported_schema,
                                )

                        else:
                            terminal_id = record_terminal(
                                connection,
                                reservation_id,
                                snapshot_digest=TEST_SNAPSHOT_DIGEST,
                            )

                            def insert_invalid() -> None:
                                _insert_selection_row_for_test(
                                    connection,
                                    session_id,
                                    terminal_id,
                                    selection_schema=unsupported_schema,
                                )

    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError):
        insert_invalid()
    assert _database_rows(connection) == before
    if process_intent is not None:
        _consume_capability_for_test(process_intent)
    connection.close()


@pytest.mark.parametrize(
    (
        "case_id",
        "state",
        "next_attempt_ordinal",
        "next_recovery_ordinal",
        "closed_at_utc",
        "close_reason",
    ),
    [
        ("selected", "SUCCESS_SELECTED", 0, 0, None, None),
        ("closed", "CLOSED", 0, 0, CLOSE_TIMESTAMP, "preclosed"),
        ("unknown", "NOT_A_STATE", 0, 0, None, None),
        ("attempt-counter", "OPEN", 1, 0, None, None),
        ("recovery-counter", "OPEN", 0, 1, None, None),
        ("closed-at", "OPEN", 0, 0, CLOSE_TIMESTAMP, "preclosed"),
        ("close-reason", "OPEN", 0, 0, None, "preclosed"),
    ],
)
def test_direct_session_insert_requires_canonical_initial_projection(
    db_path: Path,
    case_id: str,
    state: str,
    next_attempt_ordinal: int,
    next_recovery_ordinal: int,
    closed_at_utc: str | None,
    close_reason: str | None,
) -> None:
    connection = _connect(db_path)
    request = _snapshot_capture_request(_request()).canonical_json()
    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO sessions (
                session_id, authority_epoch_id, session_schema,
                authority_policy_version, claim_policy_version,
                target_session_date, state, next_attempt_ordinal,
                next_recovery_ordinal, request_json, request_digest,
                created_at_utc, closed_at_utc, close_reason
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"noncanonical-session-{case_id}",
                EPOCH,
                POLICY,
                CLAIM_POLICY,
                "2026-01-01",
                state,
                next_attempt_ordinal,
                next_recovery_ordinal,
                request,
                _digest(request),
                TIMESTAMP,
                closed_at_utc,
                close_reason,
            ),
        )
    assert _database_rows(connection) == before
    connection.close()


DIRECT_SQL_SESSION_REQUEST_CASES = (
    "target-column-request-mismatch",
    "missing-field",
    "unknown-field",
    "duplicate-json-key",
    "reordered-keys",
    "added-whitespace",
    "text-storage",
    "malformed-json",
    "wrong-root-type",
    "wrong-scalar-type",
    "request-limit-true",
    "request-limit-false",
    "request-limit-string",
    "request-limit-real",
    "request-limit-zero",
    "request-limit-over-bound",
    "request-limit-size-mismatch",
    "empty-universe",
    "oversized-universe",
    "non-string-universe-member",
    "duplicate-symbol",
    "lowercase-symbol",
    "padded-symbol",
    "blank-symbol",
    "overlong-symbol",
    "unsupported-symbol-punctuation",
    "malformed-date",
    "noncanonical-date",
    "start-after-end",
    "end-equals-target",
    "end-after-target",
    "wrong-bar-interval",
    "wrong-child-operation-version",
    "wrong-output-policy-version",
    "wrong-provider",
    "wrong-operation",
    "request-digest-mismatch",
)


def _direct_sql_session_request_candidate(
    case_id: str,
) -> tuple[bytes | str, str, bytes | None]:
    request = _request()
    target_session_date = request["target_session_date"]
    request_digest: bytes | None = None

    if case_id == "target-column-request-mismatch":
        target_session_date = "2026-01-02"
    elif case_id == "missing-field":
        del request["bar_interval"]
    elif case_id == "unknown-field":
        request["unknown"] = "value"
    elif case_id == "wrong-root-type":
        return _json([]), target_session_date, request_digest
    elif case_id == "wrong-scalar-type":
        request["bar_interval"] = ["1d"]
    elif case_id == "request-limit-true":
        request["request_limit"] = True
    elif case_id == "request-limit-false":
        request["request_limit"] = False
    elif case_id == "request-limit-string":
        request["request_limit"] = "2"
    elif case_id == "request-limit-real":
        request["request_limit"] = 2.0
    elif case_id == "request-limit-zero":
        request["request_limit"] = 0
    elif case_id == "request-limit-over-bound":
        request["request_limit"] = MAX_DAILY_SNAPSHOT_SYMBOLS + 1
    elif case_id == "request-limit-size-mismatch":
        request["request_limit"] = 1
    elif case_id == "empty-universe":
        request["ordered_universe"] = []
        request["request_limit"] = 0
    elif case_id == "oversized-universe":
        request["ordered_universe"] = [
            f"S{index}" for index in range(MAX_DAILY_SNAPSHOT_SYMBOLS + 1)
        ]
        request["request_limit"] = MAX_DAILY_SNAPSHOT_SYMBOLS + 1
    elif case_id == "non-string-universe-member":
        request["ordered_universe"] = ["QQQ", 7]
    elif case_id == "duplicate-symbol":
        request["ordered_universe"] = ["QQQ", "QQQ"]
    elif case_id == "lowercase-symbol":
        request["ordered_universe"] = ["QQQ", "spy"]
    elif case_id == "padded-symbol":
        request["ordered_universe"] = ["QQQ", " SPY"]
    elif case_id == "blank-symbol":
        request["ordered_universe"] = ["QQQ", ""]
    elif case_id == "overlong-symbol":
        request["ordered_universe"] = ["QQQ", "ABCDEFGHIJK"]
    elif case_id == "unsupported-symbol-punctuation":
        request["ordered_universe"] = ["QQQ", "BRK/B"]
    elif case_id == "malformed-date":
        request["request_window_start_date"] = "2025-13-01"
    elif case_id == "noncanonical-date":
        request["request_window_start_date"] = "2025-12-1"
    elif case_id == "start-after-end":
        request["request_window_start_date"] = "2025-12-31"
        request["request_window_end_date"] = "2025-12-01"
    elif case_id == "end-equals-target":
        request["request_window_end_date"] = target_session_date
    elif case_id == "end-after-target":
        request["request_window_end_date"] = "2026-01-02"
    elif case_id == "wrong-bar-interval":
        request["bar_interval"] = "1h"
    elif case_id == "wrong-child-operation-version":
        request["child_operation_version"] = "child/v2"
    elif case_id == "wrong-output-policy-version":
        request["output_policy_version"] = "output/v2"
    elif case_id == "wrong-provider":
        request["provider_id"] = "other-provider"
    elif case_id == "wrong-operation":
        request["permitted_provider_operation"] = "other-operation"

    request_bytes = _json(request)
    if case_id == "duplicate-json-key":
        request_bytes = request_bytes.replace(
            b'{"bar_interval":"1d"',
            b'{"bar_interval":"1d","bar_interval":"1d"',
            1,
        )
    elif case_id == "reordered-keys":
        request_bytes = json.dumps(
            dict(reversed(tuple(request.items()))),
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
        ).encode("utf-8")
    elif case_id == "added-whitespace":
        request_bytes += b" "
    elif case_id == "text-storage":
        return request_bytes.decode("utf-8"), target_session_date, request_digest
    elif case_id == "malformed-json":
        request_bytes = b'{"bar_interval":'
    elif case_id == "request-digest-mismatch":
        request_digest = _digest(b"wrong-session-request")
    return request_bytes, target_session_date, request_digest


@pytest.mark.parametrize("case_id", DIRECT_SQL_SESSION_REQUEST_CASES)
def test_direct_sql_session_request_admission_is_canonical_and_atomic(
    db_path: Path,
    case_id: str,
) -> None:
    connection = _connect(db_path)
    request_bytes, target_session_date, request_digest = (
        _direct_sql_session_request_candidate(case_id)
    )
    before = _database_rows(connection)

    expected_error = (
        SchemaValidationError
        if case_id == "request-digest-mismatch"
        else sqlite3.IntegrityError
    )
    with pytest.raises(expected_error):
        _insert_session_row_for_test(
            connection,
            f"invalid-request-{case_id}",
            request_bytes,
            target_session_date=target_session_date,
            request_digest=request_digest,
        )

    assert _database_rows(connection) == before
    _assert_no_capture_authority_side_effects(connection)

    valid_request = _snapshot_capture_request(_request()).canonical_json()
    _insert_session_row_for_test(
        connection,
        f"valid-request-after-{case_id}",
        valid_request,
    )
    assert connection.execute(
        """
        SELECT target_session_date, next_attempt_ordinal, next_recovery_ordinal,
               request_json, request_digest
        FROM sessions
        """
    ).fetchone() == (
        "2026-01-01",
        0,
        0,
        valid_request,
        _digest(valid_request),
    )
    connection.close()


@pytest.mark.parametrize(
    ("metadata_provider_id", "metadata_operation"),
    [
        ("other-provider", OPERATION),
        (PROVIDER, "other-operation"),
    ],
    ids=("metadata-provider", "metadata-operation"),
)
def test_direct_sql_session_request_requires_exact_public_metadata_descriptor(
    tmp_path: Path,
    metadata_provider_id: str,
    metadata_operation: str,
) -> None:
    path = tmp_path / "direct-metadata-binding.sqlite3"
    connection = _connect(path)
    _install_schema(connection)
    _insert_metadata(
        connection,
        provider_id=metadata_provider_id,
        permitted_provider_operation=metadata_operation,
    )
    _insert_migration(connection)
    request_bytes = _snapshot_capture_request(_request()).canonical_json()
    before = _database_rows(connection)

    with pytest.raises(sqlite3.IntegrityError, match="binding differs from metadata"):
        _insert_session_row_for_test(
            connection,
            f"invalid-metadata-{metadata_provider_id}-{metadata_operation}",
            request_bytes,
        )

    assert _database_rows(connection) == before
    _assert_no_capture_authority_side_effects(connection)
    connection.close()


def test_session_request_admission_uses_native_json1_and_repository_bound(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        ("sessions_before_insert",),
    ).fetchone()
    assert trigger_sql is not None
    compact_sql = " ".join(trigger_sql[0].split())
    for json1_function in (
        "json_valid(",
        "json_type(",
        "json_each(",
        "json_array_length(",
        "json_group_array(",
        "json_extract(",
        "json_quote(",
    ):
        assert json1_function in compact_sql
    assert MAX_DAILY_SNAPSHOT_SYMBOLS == 100
    connection.close()


def test_complete_evidence_pair_inventory_has_authoritative_digest_guards(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    discovered: set[tuple[str, str, str]] = set()
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    ]
    for table in tables:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for blob_column in (column for column in columns if column.endswith("_json")):
            digest_column = (
                "migration_digest"
                if (table, blob_column) == ("schema_migrations", "migration_json")
                else f"{blob_column.removesuffix('json')}digest"
            )
            assert digest_column in columns
            discovered.add((table, blob_column, digest_column))
    assert discovered == set(EVIDENCE_PAIR_INVENTORY)

    for (_table, _blob_column, _digest_column), (
        classification,
        boundary,
    ) in EVIDENCE_PAIR_INVENTORY.items():
        assert classification in {"owned-insert", "copied-parent", "appended-update"}
        assert boundary.endswith(("before_insert", "append_only", "evidence_guard"))

    # The production artifact intentionally contains no application-defined
    # hash calls.  The same 21 pairs remain covered by reviewed Python
    # mutation/validation boundaries, whose negative cases below exercise the
    # exact byte/digest comparison before any dependent mutation.
    assert b"sha256(" not in SCHEMA_BYTES.lower()
    assert "_require_evidence_pair" in inspect.getsource(_insert_session_row_for_test)
    assert "_require_evidence_pair" in inspect.getsource(_insert_attempt_row_for_test)
    assert "_require_evidence_pair" in inspect.getsource(_insert_claim_row_for_test)
    assert "_require_evidence_pair" in inspect.getsource(
        _insert_reservation_row_for_test
    )
    assert "_require_evidence_pair" in inspect.getsource(_insert_terminal_row_for_test)
    assert "_require_evidence_pair" in inspect.getsource(_insert_execution_row_for_test)
    assert "_require_evidence_pair" in inspect.getsource(_insert_selection_row_for_test)
    assert "_require_evidence_pair" in inspect.getsource(_insert_recovery_fact_for_test)

    distinct_digest_semantics = {
        ("authority_metadata", "bootstrap_digest"),
        ("authority_metadata", "database_identity_digest"),
        ("schema_migrations", "application_release_digest"),
        ("launch_reservations", "request_digest"),
        ("terminals", "request_digest"),
        ("terminals", "snapshot_digest"),
        ("session_selections", "snapshot_digest"),
    }
    for table, digest_column in distinct_digest_semantics:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        assert digest_column in columns
        assert all(
            not (inventory_table == table and inventory_digest == digest_column)
            for inventory_table, _, inventory_digest in EVIDENCE_PAIR_INVENTORY
        )
    connection.close()


def _prepare_owned_insert_parent(
    connection: sqlite3.Connection, table: str
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if table == "authority_metadata":
        return context
    _insert_metadata(connection)
    if table == "schema_migrations":
        return context
    _insert_migration(connection)
    if table == "sessions":
        return context
    context["session_id"] = create_session(connection)
    if table == "attempts":
        return context
    context["attempt_id"] = allocate_attempt(connection, context["session_id"])
    if table == "provider_call_claims":
        return context
    context["claim_id"] = commit_claim(connection, context["attempt_id"])
    if table == "launch_reservations":
        return context
    if table == "launch_executions":
        return context
    context["reservation_id"] = reserve_launch(connection, context["claim_id"])
    if table == "manual_recoveries":
        return context
    context["execution_id"] = _record_successful_process(
        connection, context["reservation_id"]
    )
    _resume_and_persist(connection, context["execution_id"], context["reservation_id"])
    if table == "terminals":
        return context
    assert table == "session_selections"
    context["terminal_id"] = record_terminal(
        connection, context["reservation_id"], snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    return context


def _create_owned_insert_candidate(
    connection: sqlite3.Connection, table: str, context: dict[str, Any]
) -> None:
    if table == "authority_metadata":
        _insert_metadata(connection)
    elif table == "schema_migrations":
        _insert_migration(connection)
    elif table == "sessions":
        create_session(connection)
    elif table == "attempts":
        allocate_attempt(connection, context["session_id"])
    elif table == "provider_call_claims":
        commit_claim(connection, context["attempt_id"])
    elif table == "launch_reservations":
        reserve_launch(connection, context["claim_id"])
    elif table == "launch_executions":
        reservation_id = reserve_launch(connection, context["claim_id"])
        process_intent = _construct_provider_and_commit_process_intent(
            connection, reservation_id
        )
        receipt = FakeSideEffects(connection).create_process(process_intent)
        assert type(receipt) is FakeProcessCreationReceipt
        record_execution(connection, reservation_id, receipt)
    elif table == "terminals":
        record_terminal(
            connection, context["reservation_id"], snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
    elif table == "session_selections":
        select_terminal(connection, context["session_id"], context["terminal_id"])
    else:
        assert table == "manual_recoveries"
        record_recovery(
            connection,
            context["session_id"],
            "LAUNCH_RESERVATION",
            context["reservation_id"],
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )


def _database_rows(connection: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        for table in tables
    }


@pytest.mark.parametrize(
    "owned_pair",
    [
        pair
        for pair, (classification, _) in EVIDENCE_PAIR_INVENTORY.items()
        if classification == "owned-insert"
    ],
    ids=lambda pair: f"{pair[0]}-{pair[1]}",
)
@pytest.mark.parametrize("invalid_part", ["bytes", "digest"])
def test_every_owned_insert_pair_rejects_python_mismatch_before_mutation(
    owned_pair: tuple[str, str, str],
    invalid_part: str,
) -> None:
    table, blob_column, digest_column = owned_pair
    base_harness = Architecture77HarnessAuthority.create()
    candidate_harness = Architecture77HarnessAuthority.create()
    try:
        base = base_harness._connection
        candidate = candidate_harness._connection
        schema_seed = sqlite3.connect(":memory:", isolation_level=None)
        try:
            _install_schema(schema_seed)
            schema_seed.backup(base)
        finally:
            schema_seed.close()
        with _bind_harness(base_harness):
            context = _prepare_owned_insert_parent(base, table)
        base.backup(candidate)
        if table != "authority_metadata":
            candidate_harness._validate_connection(candidate)
        with _bind_harness(candidate_harness):
            _create_owned_insert_candidate(candidate, table, context)
        columns = [row[1] for row in candidate.execute(f"PRAGMA table_info({table})")]
        values = list(candidate.execute(f"SELECT * FROM {table}").fetchone())

        if invalid_part == "bytes":
            values[columns.index(blob_column)] += b" "
        else:
            values[columns.index(digest_column)] = _digest(b"wrong-owned-pair-digest")
        before = _database_rows(base)
        with pytest.raises(
            SchemaValidationError, match="does not match evidence bytes"
        ):
            _require_evidence_pair(
                values[columns.index(blob_column)],
                values[columns.index(digest_column)],
                field=f"{table}.{blob_column}",
            )
        assert _database_rows(base) == before
    finally:
        candidate_harness.close()
        base_harness.close()


@pytest.mark.parametrize("copied_pair", ["attempt-request", "claim-request"])
def test_copied_request_pairs_reject_child_mismatch_and_parent_drift(
    db_path: Path, copied_pair: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    request_json, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    drifted_json = request_json + b" "
    drifted_digest = _digest(drifted_json)
    if copied_pair == "attempt-request":
        with pytest.raises(sqlite3.IntegrityError, match="attempt parent binding"):
            _insert_attempt_row_for_test(
                connection,
                session_id,
                0,
                drifted_json,
                drifted_digest,
            )
        assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
        assert connection.execute(
            "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone() == (0,)
        parent_table = "sessions"
        parent_key = "session_id"
        parent_id = session_id
    else:
        attempt_id = allocate_attempt(connection, session_id)
        with pytest.raises(sqlite3.IntegrityError, match="claim admission"):
            _insert_claim_row_for_test(
                connection,
                attempt_id,
                drifted_json,
                drifted_digest,
            )
        assert connection.execute(
            "SELECT count(*) FROM provider_call_claims"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone() == ("ALLOCATED",)
        parent_table = "attempts"
        parent_key = "attempt_id"
        parent_id = attempt_id

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            f"UPDATE {parent_table} SET request_json = ?, request_digest = ? "
            f"WHERE {parent_key} = ?",
            (drifted_json, drifted_digest, parent_id),
        )
    assert connection.execute(
        f"SELECT request_json, request_digest FROM {parent_table} "
        f"WHERE {parent_key} = ?",
        (parent_id,),
    ).fetchone() == (request_json, request_digest)
    connection.close()


@pytest.mark.parametrize(
    "appended_pair",
    [
        "process-intent",
        "process-failure",
        "resume-intent",
        "post-resume",
        "cleanup",
    ],
)
def test_append_on_update_pairs_reject_wrong_digest_at_python_boundary(
    db_path: Path, appended_pair: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    wrong_digest = _digest(b"wrong-appended-evidence")

    if appended_pair == "process-intent":
        request_digest, authority_policy, claim_policy = connection.execute(
            "SELECT request_digest, authority_policy_version, claim_policy_version "
            "FROM launch_reservations WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone()
        intent_json = _process_intent_json(
            reservation_id, request_digest, authority_policy, claim_policy
        )
        before = connection.execute(
            "SELECT reservation_state, process_intent_json, process_intent_digest, "
            "process_intent_committed_at_utc FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone()
        with pytest.raises(
            SchemaValidationError, match="does not match evidence bytes"
        ):
            _require_evidence_pair(
                intent_json, wrong_digest, field="process intent digest"
            )
        after = connection.execute(
            "SELECT reservation_state, process_intent_json, process_intent_digest, "
            "process_intent_committed_at_utc FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone()
    elif appended_pair == "process-failure":
        intent = _construct_provider_and_commit_process_intent(
            connection, reservation_id
        )
        failure_json = _process_failure_json(reservation_id, intent.intent_digest)
        before = connection.execute(
            "SELECT reservation_state, process_creation_failure_json, "
            "process_creation_failure_digest, outcome_recorded_at_utc "
            "FROM launch_reservations WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone()
        with pytest.raises(
            SchemaValidationError, match="does not match evidence bytes"
        ):
            _require_evidence_pair(
                failure_json, wrong_digest, field="process failure digest"
            )
        after = connection.execute(
            "SELECT reservation_state, process_creation_failure_json, "
            "process_creation_failure_digest, outcome_recorded_at_utc "
            "FROM launch_reservations WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone()
        _consume_capability_for_test(intent)
    else:
        execution_id = _record_successful_process(connection, reservation_id)
        if appended_pair == "resume-intent":
            intent_json = _json(
                {
                    "execution_id": execution_id,
                    "resume_operation": "ResumeThread",
                    "schema": 1,
                }
            )
            before = connection.execute(
                "SELECT phase, resume_intent_json, resume_intent_digest, "
                "resume_intent_committed_at_utc FROM launch_executions "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()
            with pytest.raises(
                SchemaValidationError, match="does not match evidence bytes"
            ):
                _require_evidence_pair(
                    intent_json, wrong_digest, field="resume intent digest"
                )
            after = connection.execute(
                "SELECT phase, resume_intent_json, resume_intent_digest, "
                "resume_intent_committed_at_utc FROM launch_executions "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()
        else:
            intent = commit_resume_intent(connection, execution_id, reservation_id)
            post_resume = _json(
                {
                    "execution_id": execution_id,
                    "resume_intent_digest": intent.intent_digest.hex(),
                    "resume_result": "RESUMED",
                    "schema": 1,
                }
            )
            cleanup, cleanup_digest = _evidence(f"cleanup:{execution_id}")
            post_digest = _digest(post_resume)
            if appended_pair == "post-resume":
                post_digest = wrong_digest
            else:
                cleanup_digest = wrong_digest
            before = connection.execute(
                "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
                "cleanup_digest FROM launch_executions WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()
            with pytest.raises(
                SchemaValidationError, match="does not match evidence bytes"
            ):
                if appended_pair == "post-resume":
                    _require_evidence_pair(
                        post_resume, post_digest, field="post-resume digest"
                    )
                else:
                    _require_evidence_pair(
                        cleanup, cleanup_digest, field="cleanup digest"
                    )
            after = connection.execute(
                "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
                "cleanup_digest FROM launch_executions WHERE launch_execution_id = ?",
                (execution_id,),
            ).fetchone()
            _consume_capability_for_test(intent)
    assert after == before
    assert connection.execute(
        "SELECT next_attempt_ordinal, next_recovery_ordinal FROM sessions "
        "WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (1, 0)
    connection.close()


def test_descendants_do_not_copy_ancestor_identity_columns(db_path: Path) -> None:
    connection = _connect(db_path)
    columns = {
        table: {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for table in (
            "provider_call_claims",
            "launch_reservations",
            "launch_executions",
            "terminals",
            "session_selections",
            "manual_recoveries",
        )
    }
    assert {"session_id", "authority_epoch_id", "ordinal"}.isdisjoint(
        columns["provider_call_claims"]
    )
    assert {
        "attempt_id",
        "session_id",
        "authority_epoch_id",
        "allocation_id",
    }.isdisjoint(columns["launch_reservations"])
    assert {
        "claim_id",
        "attempt_id",
        "session_id",
        "authority_epoch_id",
    }.isdisjoint(columns["launch_executions"])
    assert {
        "claim_id",
        "attempt_id",
        "session_id",
        "authority_epoch_id",
        "launch_execution_id",
    }.isdisjoint(columns["terminals"])
    assert {
        "claim_id",
        "attempt_id",
        "authority_epoch_id",
    }.isdisjoint(columns["session_selections"])
    assert {
        "target_allocation_id",
        "target_claim_id",
        "target_attempt_id",
        "target_epoch_id",
    }.isdisjoint(columns["manual_recoveries"])
    connection.close()


def test_identity_vectors_use_normalized_immediate_parent_material() -> None:
    request = _request()
    snapshot = _snapshot_capture_request(request)
    migration_id = _identity(
        "migration_id/v1", EPOCH, str(PRODUCTION_SCHEMA_VERSION), "migration-policy/v1"
    )
    session_id = _session_id(
        snapshot,
        machine_authority_id=MACHINE,
        authority_epoch_id=EPOCH,
        authority_policy_version=POLICY,
        claim_policy_version=CLAIM_POLICY,
    )
    attempt_id = _attempt_id(session_id, 0, PROVIDER, OPERATION, CLAIM_POLICY)
    claim_id = _claim_id(attempt_id, CLAIM_POLICY, PROVIDER, OPERATION, 1)
    reservation_id = _reservation_id(claim_id, RELEASE, POLICY, CLAIM_POLICY)
    execution_id = _execution_id(reservation_id, RELEASE, POLICY)
    terminal_id = _terminal_id(reservation_id, TERMINAL_POLICY)
    selection_id = _selection_id(session_id, terminal_id, SELECTION_POLICY)
    recovery_id = _recovery_id(
        session_id,
        "ATTEMPT",
        attempt_id,
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        0,
        RECOVERY_POLICY,
    )
    assert migration_id == "57197f2c-4879-59ba-a646-5ae4a015fc66"
    assert session_id == "80e64e2b-689f-5c0f-9076-bd251b55a9ee"
    assert attempt_id == "550d4a64-0306-5f15-a0ab-f65722c790a2"
    assert claim_id == "8a3ba04b-6548-577f-9773-2b30744b929f"
    assert reservation_id == "51e87e09-cea2-5828-8598-14dd053be048"
    assert execution_id == "f5727d7d-dd0b-50d8-8bf3-6ff2e44414e7"
    assert terminal_id == "bfee46cc-85a7-5fa7-88cd-0d5468dc51ef"
    assert selection_id == "f10c3fc1-49b0-554a-8fa7-d36fa4d1bee8"
    assert recovery_id == "9aaadbb2-62af-58db-af21-b5208551ec01"
    assert (
        _session_id(
            _snapshot_capture_request(_request()),
            machine_authority_id=MACHINE,
            authority_epoch_id=EPOCH,
            authority_policy_version=POLICY,
            claim_policy_version=CLAIM_POLICY,
        )
        == session_id
    )
    for field_name, value in (
        ("provider_id", "provider-drift"),
        ("permitted_provider_operation", "operation-drift"),
    ):
        drifted_request = {**request, field_name: value}
        with pytest.raises(ValueError):
            _snapshot_capture_request(drifted_request)
    assert (
        _session_id(
            snapshot,
            machine_authority_id=MACHINE,
            authority_epoch_id=EPOCH,
            authority_policy_version="authority-policy/drift",
            claim_policy_version=CLAIM_POLICY,
        )
        != session_id
    )
    assert (
        _session_id(
            snapshot,
            machine_authority_id=MACHINE,
            authority_epoch_id=EPOCH,
            authority_policy_version=POLICY,
            claim_policy_version="claim-policy/drift",
        )
        != session_id
    )
    assert (
        _attempt_id(session_id, 0, PROVIDER, OPERATION, "claim-policy/drift")
        != attempt_id
    )
    assert (
        _claim_id(attempt_id, "claim-policy/drift", PROVIDER, OPERATION, 1) != claim_id
    )
    assert (
        _reservation_id(claim_id, RELEASE, "authority-policy/drift", CLAIM_POLICY)
        != reservation_id
    )
    assert (
        _reservation_id(claim_id, RELEASE, POLICY, "claim-policy/drift")
        != reservation_id
    )
    assert (
        _execution_id(reservation_id, RELEASE, "authority-policy/drift") != execution_id
    )


def test_identity_helpers_require_explicit_persisted_policy_inputs() -> None:
    request = _snapshot_capture_request(_request())
    with pytest.raises(TypeError):
        _session_id(request)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _attempt_id("session", 0)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _claim_id("attempt")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _reservation_id("claim")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _execution_id("reservation")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _terminal_id("reservation")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _selection_id("session", "terminal")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _recovery_id(
            "session",
            "SESSION",
            "session",
            "ACKNOWLEDGE_RESTORE",
            "OPEN",
            "RESTORE_ACKNOWLEDGED",
            0,
        )  # type: ignore[call-arg]


def test_valid_lifecycle_from_metadata_to_selection(db_path: Path) -> None:
    connection = _connect(db_path)
    request = _request("2026-07-14")
    request.update(
        {
            "ordered_universe": ["DIA", "SPY", "QQQ"],
            "request_limit": 3,
        }
    )
    session_id = create_session(connection, request)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id, reservation_id)
    terminal_id = record_terminal(
        connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    selection_id = select_terminal(connection, session_id, terminal_id)
    expected_request = _snapshot_capture_request(request).canonical_json()
    expected_digest = _digest(expected_request)
    assert b"ALPACA_MARKET_DATA" not in expected_request
    assert b"HISTORICAL_DAILY_BARS" not in expected_request
    assert connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (expected_request, expected_digest)
    assert connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone() == (expected_request, expected_digest)
    assert connection.execute(
        "SELECT request_json, request_digest FROM provider_call_claims "
        "WHERE claim_id = ?",
        (claim_id,),
    ).fetchone() == (expected_request, expected_digest)
    assert connection.execute(
        "SELECT request_digest FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (reservation_id.reservation_id,),
    ).fetchone() == (expected_digest,)
    assert connection.execute(
        "SELECT request_digest FROM terminals WHERE terminal_id = ?", (terminal_id,)
    ).fetchone() == (expected_digest,)
    assert connection.execute(
        "SELECT provider_id, permitted_provider_operation FROM authority_metadata"
    ).fetchone() == (PROVIDER, OPERATION)
    assert connection.execute(
        "SELECT provider_id, permitted_provider_operation FROM attempts "
        "WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone() == (PROVIDER, OPERATION)
    assert connection.execute(
        "SELECT provider_id, permitted_provider_operation FROM provider_call_claims "
        "WHERE claim_id = ?",
        (claim_id,),
    ).fetchone() == (PROVIDER, OPERATION)
    assert connection.execute(
        """
        SELECT m.authority_policy_version, m.claim_policy_version,
               s.authority_policy_version, s.claim_policy_version,
               a.attempt_policy_version, c.claim_policy_version,
               r.authority_policy_version, r.claim_policy_version,
               e.authority_policy_version
        FROM authority_metadata m
        JOIN sessions s ON s.authority_epoch_id = m.authority_epoch_id
        JOIN attempts a ON a.session_id = s.session_id
        JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
        JOIN launch_reservations r ON r.claim_id = c.claim_id
        JOIN launch_executions e
          ON e.launch_reservation_id = r.launch_reservation_id
        WHERE s.session_id = ?
        """,
        (session_id,),
    ).fetchone() == (
        POLICY,
        CLAIM_POLICY,
        POLICY,
        CLAIM_POLICY,
        CLAIM_POLICY,
        CLAIM_POLICY,
        POLICY,
        CLAIM_POLICY,
        POLICY,
    )
    assert connection.execute("SELECT state FROM sessions").fetchone() == (
        "SUCCESS_SELECTED",
    )
    assert connection.execute("SELECT state FROM attempts").fetchone() == (
        "SUCCESS_SELECTED",
    )
    assert connection.execute(
        "SELECT selection_id FROM session_selections"
    ).fetchone() == (selection_id,)
    terminal_recorded_at, selection_selected_at = connection.execute(
        """
        SELECT t.recorded_at_utc, ss.selected_at_utc
        FROM terminals t
        JOIN session_selections ss ON ss.terminal_id = t.terminal_id
        WHERE t.terminal_id = ?
        """,
        (terminal_id,),
    ).fetchone()
    assert (terminal_recorded_at, selection_selected_at) == (
        TERMINAL_TIMESTAMP,
        SELECTION_TIMESTAMP,
    )
    assert terminal_recorded_at <= selection_selected_at
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_immediate_parent_request_mismatches_are_rejected(db_path: Path) -> None:
    connection = _connect(db_path)
    request = _request("2026-07-15")
    session_id = create_session(connection, request)
    request_bytes = _snapshot_capture_request(request).canonical_json()
    request_digest = _digest(request_bytes)
    wrong_request = _json({**request, "request_limit": 99})
    wrong_digest = _digest(wrong_request)

    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_attempt_row_for_test(
            connection, session_id, 0, wrong_request, wrong_digest
        )
    connection.rollback()

    attempt_id = allocate_attempt(connection, session_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim_row_for_test(connection, attempt_id, wrong_request, wrong_digest)
    connection.rollback()

    claim_id = commit_claim(connection, attempt_id)
    _begin(connection)
    with pytest.raises(SchemaValidationError, match="does not match evidence bytes"):
        _insert_reservation_row_for_test(connection, claim_id, wrong_digest)
    connection.rollback()

    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_reservation_row_for_test(
            connection, claim_id, request_digest, "PROCESS_CREATION_FAILED"
        )
    connection.rollback()

    reservation_id = reserve_launch(connection, claim_id)
    _record_definitive_process_failure(connection, reservation_id)
    _begin(connection)
    with pytest.raises(SchemaValidationError, match="does not match evidence bytes"):
        _insert_terminal_row_for_test(
            connection,
            reservation_id,
            wrong_digest,
            "FAILED",
            "NOT_STARTED",
        )
    connection.rollback()
    assert connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (request_bytes, request_digest)
    connection.close()


def test_direct_sql_rejects_every_copied_parent_policy_drift(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_attempt_row_for_test(
            connection,
            session_id,
            0,
            request_bytes,
            request_digest,
            attempt_policy_version="claim-policy/drift",
        )
    connection.rollback()
    assert connection.execute(
        "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (0,)

    attempt_id = allocate_attempt(connection, session_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim_row_for_test(
            connection,
            attempt_id,
            request_bytes,
            request_digest,
            claim_policy_version="claim-policy/drift",
        )
    connection.rollback()

    claim_id = commit_claim(connection, attempt_id)
    for authority_policy, claim_policy in (
        ("authority-policy/drift", CLAIM_POLICY),
        (POLICY, "claim-policy/drift"),
    ):
        _begin(connection)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_reservation_row_for_test(
                connection,
                claim_id,
                request_digest,
                authority_policy_version=authority_policy,
                claim_policy_version=claim_policy,
            )
        connection.rollback()

    reservation_id = reserve_launch(connection, claim_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_execution_row_for_test(
            connection,
            reservation_id,
            authority_policy_version="authority-policy/drift",
        )
    connection.rollback()
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (1,)
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    assert connection.execute(
        "SELECT count(*) FROM launch_reservations"
    ).fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    connection.close()


def test_descendant_helpers_ignore_reset_release_constants_after_session_commit(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    monkeypatch.setitem(globals(), "POLICY", "authority-policy/reset")
    monkeypatch.setitem(globals(), "CLAIM_POLICY", "claim-policy/reset")

    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)

    assert connection.execute(
        """
        SELECT a.attempt_policy_version, c.claim_policy_version,
               r.authority_policy_version, r.claim_policy_version,
               e.authority_policy_version
        FROM attempts a
        JOIN provider_call_claims c ON c.attempt_id = a.attempt_id
        JOIN launch_reservations r ON r.claim_id = c.claim_id
        JOIN launch_executions e
          ON e.launch_reservation_id = r.launch_reservation_id
        WHERE a.attempt_id = ?
        """,
        (attempt_id,),
    ).fetchone() == (
        "claim-policy/v1",
        "claim-policy/v1",
        "authority-policy/v1",
        "claim-policy/v1",
        "authority-policy/v1",
    )
    assert claim_id and reservation_id and execution_id
    connection.close()


def test_process_creation_failure_can_record_terminal_without_execution(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    _record_definitive_process_failure(connection, reservation_id)
    terminal_id = record_terminal(
        connection, reservation_id, "FAILED", "NOT_STARTED", snapshot_digest=None
    )
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (1,)
    assert connection.execute(
        "SELECT terminal_id FROM terminals WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == (terminal_id,)
    connection.close()


def test_failed_not_started_terminal_revalidates_parent_process_intent(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    _record_definitive_process_failure(connection, reservation_id)
    wrong_digest = _corrupt_retry_safe_prior_evidence(
        connection, reservation_id, "process_intent"
    )
    before = _database_rows(connection)

    with pytest.raises(
        SchemaValidationError, match="terminal parent process intent digest"
    ):
        record_terminal(
            connection, reservation_id, "FAILED", "NOT_STARTED", snapshot_digest=None
        )

    assert not connection.in_transaction
    assert _database_rows(connection) == before
    assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("PROCESS_CREATION_FAILED",)
    assert connection.execute(
        "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
    ).fetchone() == ("LAUNCH_RESERVED",)
    assert connection.execute(
        "SELECT process_intent_digest FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == (wrong_digest,)
    connection.close()


def _prepare_terminal_insert_path(
    connection: sqlite3.Connection, state: str
) -> tuple[str, str, str, str]:
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if state in {"SUCCEEDED", "AMBIGUOUS"}:
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
        disposition = "CONFIRMED" if state == "SUCCEEDED" else "MAY_HAVE_OCCURRED"
    elif state == "FAILED":
        _record_definitive_process_failure(connection, reservation_id)
        disposition = "NOT_STARTED"
    else:
        assert state == "CLOSED"
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        disposition = "MAY_HAVE_OCCURRED"
    return session_id, attempt_id, reservation_id, disposition


@pytest.mark.parametrize(
    ("state", "disposition", "preparation", "valid", "snapshot_mode"),
    [
        ("SUCCEEDED", "CONFIRMED", "resumed", True, "auto"),
        ("FAILED", "NOT_STARTED", "process_failure", True, "auto"),
        ("FAILED", "CONFIRMED", "resumed", True, "auto"),
        ("AMBIGUOUS", "MAY_HAVE_OCCURRED", "resumed", True, "auto"),
        ("CLOSED", "MAY_HAVE_OCCURRED", "manual_review", True, "auto"),
        ("AMBIGUOUS", "NOT_STARTED", "resumed", False, "auto"),
        ("AMBIGUOUS", "CONFIRMED", "resumed", False, "auto"),
        ("SUCCEEDED", "CONFIRMED", "resumed", False, "none"),
        ("FAILED", "NOT_STARTED", "process_failure", False, "present"),
        ("FAILED", "MAY_HAVE_OCCURRED", "process_failure", False, "none"),
        ("CLOSED", "CONFIRMED", "manual_review", False, "none"),
    ],
)
def test_terminal_state_disposition_matrix(
    db_path: Path,
    state: str,
    disposition: str,
    preparation: str,
    valid: bool,
    snapshot_mode: str,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if preparation == "resumed":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
    elif preparation == "process_failure":
        _record_definitive_process_failure(connection, reservation_id)
    else:
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )

    if valid:
        terminal_id = record_terminal(
            connection,
            reservation_id,
            state,
            disposition,
            snapshot_digest=TEST_SNAPSHOT_DIGEST if state == "SUCCEEDED" else None,
        )
        assert connection.execute(
            "SELECT terminal_state, provider_call_disposition, snapshot_digest "
            "FROM terminals WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone()[:2] == (state, disposition)
    else:
        request_digest = connection.execute(
            "SELECT request_digest FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone()[0]
        _begin(connection)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_terminal_row_for_test(
                connection,
                reservation_id,
                request_digest,
                state,
                disposition,
                snapshot_mode,
            )
        connection.rollback()
    connection.close()


def test_terminal_persists_supplied_snapshot_and_selection_copies_it(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    snapshot_digests = (_digest(b"snapshot-one"), _digest(b"snapshot-two"))
    terminal_ids: list[str] = []
    for index, snapshot_digest in enumerate(snapshot_digests, start=1):
        session_id = create_session(connection, _request(f"2026-01-0{index}"))
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
        terminal_id = record_terminal(
            connection,
            reservation_id,
            snapshot_digest=snapshot_digest,
        )
        terminal_ids.append(terminal_id)
        assert connection.execute(
            "SELECT snapshot_digest FROM terminals WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone() == (snapshot_digest,)
        select_terminal(connection, session_id, terminal_id)
        assert connection.execute(
            "SELECT snapshot_digest FROM session_selections WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone() == (snapshot_digest,)

    assert terminal_ids[0] != terminal_ids[1]
    assert snapshot_digests[0] != snapshot_digests[1]
    connection.close()


@pytest.mark.parametrize("snapshot_digest", [None, b"invalid-snapshot-digest"])
def test_successful_terminal_requires_supplied_snapshot_digest(
    db_path: Path, snapshot_digest: bytes | None
) -> None:
    connection = _connect(db_path)
    session_id, _, reservation_id, _ = _prepare_terminal_insert_path(
        connection, "SUCCEEDED"
    )
    before = _database_rows(connection)
    with pytest.raises(SchemaValidationError, match="snapshot digest"):
        record_terminal(
            connection,
            reservation_id,
            snapshot_digest=snapshot_digest,
        )
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (0,)
    connection.close()


def test_failed_terminal_persists_no_snapshot_digest(db_path: Path) -> None:
    connection = _connect(db_path)
    _, _, reservation_id, _ = _prepare_terminal_insert_path(connection, "FAILED")
    terminal_id = record_terminal(
        connection,
        reservation_id,
        "FAILED",
        "NOT_STARTED",
        snapshot_digest=None,
    )
    assert connection.execute(
        "SELECT snapshot_digest FROM terminals WHERE terminal_id = ?",
        (terminal_id,),
    ).fetchone() == (None,)
    connection.close()


@pytest.mark.parametrize("state", ["SUCCEEDED", "FAILED", "AMBIGUOUS", "CLOSED"])
@pytest.mark.parametrize(
    ("invalid_field", "invalid_value", "error"),
    [
        ("evidence_json", b'{"malformed":true}', "terminal evidence digest"),
        ("evidence_digest", b"x" * 32, "terminal evidence digest"),
        (
            "diagnostics_json",
            b'{"malformed":true}',
            "terminal diagnostics digest",
        ),
        ("diagnostics_digest", b"y" * 32, "terminal diagnostics digest"),
    ],
)
def test_terminal_owned_evidence_pairs_fail_at_python_service_boundary(
    db_path: Path,
    state: str,
    invalid_field: str,
    invalid_value: bytes,
    error: str,
) -> None:
    connection = _connect(db_path)
    session_id, attempt_id, reservation_id, disposition = _prepare_terminal_insert_path(
        connection, state
    )
    request_digest = connection.execute(
        "SELECT request_digest FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone()[0]
    before = (
        connection.execute(
            "SELECT state, next_attempt_ordinal, next_recovery_ordinal "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone(),
        connection.execute(
            "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone(),
        connection.execute(
            "SELECT reservation_state, outcome_recorded_at_utc "
            "FROM launch_reservations WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone(),
    )
    with pytest.raises(SchemaValidationError, match="does not match evidence bytes"):
        _insert_terminal_row_for_test(
            connection,
            reservation_id,
            request_digest,
            state,
            disposition,
            **{invalid_field: invalid_value},
        )
    assert connection.execute("SELECT count(*) FROM terminals").fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM session_selections").fetchone() == (
        0,
    )
    after = (
        connection.execute(
            "SELECT state, next_attempt_ordinal, next_recovery_ordinal "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone(),
        connection.execute(
            "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone(),
        connection.execute(
            "SELECT reservation_state, outcome_recorded_at_utc "
            "FROM launch_reservations WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone(),
    )
    assert after == before

    if state == "SUCCEEDED":
        terminal_id = _terminal_id(reservation_id, TERMINAL_POLICY)
        selection_evidence, selection_digest = _evidence("missing-terminal-selection")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO session_selections (
                    selection_id, session_id, terminal_id, selection_schema,
                    selection_policy_version, snapshot_digest,
                    selection_evidence_json, selection_evidence_digest,
                    selected_at_utc
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    _selection_id(session_id, terminal_id, SELECTION_POLICY),
                    session_id,
                    terminal_id,
                    SELECTION_POLICY,
                    _digest(b"raw-snapshot"),
                    selection_evidence,
                    selection_digest,
                    SELECTION_TIMESTAMP,
                ),
            )
        assert connection.execute(
            "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone() == ("OPEN",)

    valid_terminal_id = _insert_terminal_row_for_test(
        connection, reservation_id, request_digest, state, disposition
    )
    assert connection.execute(
        "SELECT terminal_id FROM terminals WHERE terminal_id = ?",
        (valid_terminal_id,),
    ).fetchone() == (valid_terminal_id,)
    connection.close()


@pytest.mark.parametrize("invalid_part", ["bytes", "digest"])
def test_selection_evidence_pair_fails_at_python_service_boundary(
    db_path: Path, invalid_part: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id, reservation_id)
    terminal_id = record_terminal(
        connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    evidence, evidence_digest = _evidence(f"selection:{terminal_id}")
    if invalid_part == "bytes":
        evidence = b'{"malformed":true}'
    else:
        evidence_digest = b"z" * 32
    before = connection.execute(
        "SELECT state, next_attempt_ordinal, next_recovery_ordinal "
        "FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    with pytest.raises(SchemaValidationError, match="does not match evidence bytes"):
        _require_evidence_pair(
            evidence, evidence_digest, field="selection evidence digest"
        )
    assert connection.execute("SELECT count(*) FROM session_selections").fetchone() == (
        0,
    )
    assert (
        connection.execute(
            "SELECT state, next_attempt_ordinal, next_recovery_ordinal "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        == before
    )
    assert connection.execute(
        "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
    ).fetchone() == ("TERMINAL_RECORDED",)
    selection_id = select_terminal(connection, session_id, terminal_id)
    assert selection_id
    connection.close()


def test_recovery_action_matrix_allows_documented_actions(db_path: Path) -> None:
    connection = _connect(db_path)

    claim_session = create_session(connection)
    claim_attempt = allocate_attempt(connection, claim_session)
    claim_id = commit_claim(connection, claim_attempt)
    claim_reservation = reserve_launch(connection, claim_id)
    claim_execution = _record_successful_process(connection, claim_reservation)
    _resume_and_persist(connection, claim_execution, claim_reservation)
    claim_recovery = record_recovery(
        connection,
        claim_session,
        "CLAIM",
        claim_id,
        "RECORD_CLAIM_AMBIGUITY",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT state FROM provider_call_claims WHERE claim_id = ?", (claim_id,)
    ).fetchone() == ("COMMITTED",)
    assert connection.execute(
        "SELECT resulting_state FROM manual_recoveries WHERE recovery_id = ?",
        (claim_recovery,),
    ).fetchone() == ("AMBIGUITY_RECORDED",)

    review_session = create_session(connection, _request("2026-01-02"))
    review_attempt = allocate_attempt(connection, review_session)
    review_claim = commit_claim(connection, review_attempt)
    review_reservation = reserve_launch(connection, review_claim)
    review_recovery = record_recovery(
        connection,
        review_session,
        "LAUNCH_RESERVATION",
        review_reservation,
        "CLASSIFY_LAUNCH_RESERVATION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (review_reservation,),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert review_recovery

    select_session = create_session(connection, _request("2026-01-03"))
    select_attempt = allocate_attempt(connection, select_session)
    select_claim = commit_claim(connection, select_attempt)
    select_reservation = reserve_launch(connection, select_claim)
    select_execution = _record_successful_process(connection, select_reservation)
    _resume_and_persist(connection, select_execution, select_reservation)
    select_terminal = record_terminal(
        connection, select_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    select_recovery = record_recovery(
        connection,
        select_session,
        "TERMINAL",
        select_terminal,
        "SELECT_COMMITTED_SUCCESS",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (select_session,)
    ).fetchone() == ("SUCCESS_SELECTED",)
    assert connection.execute(
        "SELECT terminal_id FROM session_selections WHERE session_id = ?",
        (select_session,),
    ).fetchone() == (select_terminal,)
    terminal_recorded_at, recovery_created_at, selection_selected_at = (
        connection.execute(
            """
            SELECT t.recorded_at_utc, mr.created_at_utc, ss.selected_at_utc
            FROM terminals t
            JOIN manual_recoveries mr ON mr.target_id = t.terminal_id
            JOIN session_selections ss ON ss.terminal_id = t.terminal_id
            WHERE t.terminal_id = ?
              AND mr.action = 'SELECT_COMMITTED_SUCCESS'
            """,
            (select_terminal,),
        ).fetchone()
    )
    assert (terminal_recorded_at, recovery_created_at, selection_selected_at) == (
        TERMINAL_TIMESTAMP,
        SELECTION_TIMESTAMP,
        SELECTION_TIMESTAMP,
    )
    assert terminal_recorded_at <= selection_selected_at
    assert select_recovery

    close_session = create_session(connection, _request("2026-01-04"))
    close_recovery = record_recovery(
        connection,
        close_session,
        "SESSION",
        close_session,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (close_session,)
    ).fetchone() == ("CLOSED",)
    assert close_recovery

    restore_session = create_session(connection, _request("2026-01-05"))
    restore_recovery = record_recovery(
        connection,
        restore_session,
        "SESSION",
        restore_session,
        "ACKNOWLEDGE_RESTORE",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (restore_session,)
    ).fetchone() == ("OPEN",)
    assert restore_recovery
    connection.close()


def test_recovery_persists_explicit_operator_evidence_without_identity_binding(
    tmp_path: Path,
) -> None:
    del tmp_path
    first_harness = Architecture77HarnessAuthority.create()
    second_harness = Architecture77HarnessAuthority.create()
    first_path = first_harness.database_path
    second_path = second_harness.database_path
    for harness in (first_harness, second_harness):
        context_token = _CURRENT_HARNESS.set(harness)
        try:
            _seed_lifecycle(harness.database_path)
        finally:
            _CURRENT_HARNESS.reset(context_token)
    first_evidence, first_digest = _evidence("operator-evidence-first")
    second_evidence, second_digest = _evidence("operator-evidence-second")

    recovery_ids: list[str] = []
    try:
        for harness, path, evidence, digest in (
            (first_harness, first_path, first_evidence, first_digest),
            (second_harness, second_path, second_evidence, second_digest),
        ):
            context_token = _CURRENT_HARNESS.set(harness)
            try:
                connection = _connect(path)
                session_id = connection.execute(
                    "SELECT session_id FROM sessions"
                ).fetchone()[0]
                recovery_id = record_recovery(
                    connection,
                    session_id,
                    "SESSION",
                    session_id,
                    "CLOSE_SESSION",
                    operator_evidence_json=evidence,
                    operator_evidence_digest=digest,
                )
                recovery_ids.append(recovery_id)
                assert connection.execute(
                    "SELECT operator_evidence_json, operator_evidence_digest "
                    "FROM manual_recoveries WHERE recovery_id = ?",
                    (recovery_id,),
                ).fetchone() == (evidence, digest)
                connection.close()
            finally:
                _CURRENT_HARNESS.reset(context_token)
    finally:
        first_harness.close()
        second_harness.close()

    assert recovery_ids[0] == recovery_ids[1]
    assert first_evidence != second_evidence


def test_bad_recovery_evidence_fails_before_ordinal_or_mutation(
    db_path: Path,
) -> None:
    values = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    before = _database_rows(connection)
    bad_evidence = b'{"operator":"bad"}'
    with pytest.raises(SchemaValidationError, match="does not match evidence bytes"):
        record_recovery(
            connection,
            values["session_id"],
            "SESSION",
            values["session_id"],
            "CLOSE_SESSION",
            operator_evidence_json=bad_evidence,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (values["session_id"],),
    ).fetchone() == (0,)
    connection.close()


def test_one_to_one_parent_fences(db_path: Path) -> None:
    values = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        commit_claim(connection, values["attempt_id"])
    with pytest.raises(sqlite3.IntegrityError):
        reserve_launch(connection, values["claim_id"])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        _record_successful_process(connection, values["reservation_id"])
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(
            connection, values["reservation_id"], snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
    select_terminal(connection, values["session_id"], values["terminal_id"])
    with pytest.raises(sqlite3.IntegrityError):
        select_terminal(connection, values["session_id"], values["terminal_id"])
    second_session = create_session(connection, _request("2026-01-02"))
    with pytest.raises(sqlite3.IntegrityError):
        select_terminal(connection, second_session, values["terminal_id"])
    connection.close()


def test_selection_and_recovery_lineage_is_session_scoped(db_path: Path) -> None:
    connection = _connect(db_path)
    first_session = create_session(connection)
    first_attempt = allocate_attempt(connection, first_session)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    first_execution = _record_successful_process(connection, first_reservation)
    _resume_and_persist(connection, first_execution, first_reservation)
    first_terminal = record_terminal(
        connection, first_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    second_execution = _record_successful_process(connection, second_reservation)
    _resume_and_persist(connection, second_execution, second_reservation)
    second_terminal = record_terminal(
        connection, second_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    with pytest.raises(sqlite3.IntegrityError):
        select_terminal(connection, second_session, first_terminal)
    for target_kind, target_id, action in (
        ("SESSION", second_session, "CLOSE_SESSION"),
        ("ATTEMPT", second_attempt, "RECORD_ATTEMPT_AMBIGUITY"),
        ("CLAIM", second_claim, "RECORD_CLAIM_AMBIGUITY"),
        ("LAUNCH_RESERVATION", second_reservation, "CLASSIFY_LAUNCH_RESERVATION"),
        ("TERMINAL", second_terminal, "SELECT_COMMITTED_SUCCESS"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            record_recovery(
                connection,
                first_session,
                target_kind,
                target_id,
                action,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
    assert first_execution != second_execution
    connection.close()


def test_attempt_ordinal_trigger_is_single_insert_and_atomic(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    with pytest.raises(sqlite3.IntegrityError):
        allocate_attempt(connection, session_id, ordinal=1)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET next_attempt_ordinal = 1 WHERE session_id = ?",
            (session_id,),
        )
    _begin(connection)
    request_bytes, request_digest, provider_id, operation, attempt_policy = (
        connection.execute(
            """
            SELECT s.request_json, s.request_digest, m.provider_id,
                   m.permitted_provider_operation, s.claim_policy_version
            FROM sessions s
            JOIN authority_metadata m
              ON m.authority_epoch_id = s.authority_epoch_id
            WHERE s.session_id = ?
            """,
            (session_id,),
        ).fetchone()
    )
    attempt_id = _attempt_id(session_id, 0, provider_id, operation, attempt_policy)
    allocation, allocation_digest = _evidence("rollback-allocation")
    attempt, attempt_digest = _evidence("rollback-attempt")
    connection.execute(
        """
        INSERT INTO attempts (
            attempt_id, session_id, ordinal, provider_id,
            permitted_provider_operation, provider_call_budget,
            request_json, request_digest, attempt_schema,
            attempt_policy_version, allocation_evidence_json,
            allocation_evidence_digest, attempt_evidence_json,
            attempt_evidence_digest, state, created_at_utc
        ) VALUES (?, ?, 0, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?, ?, 'ALLOCATED', ?)
        """,
        (
            attempt_id,
            session_id,
            provider_id,
            operation,
            request_bytes,
            request_digest,
            attempt_policy,
            allocation,
            allocation_digest,
            attempt,
            attempt_digest,
            TIMESTAMP,
        ),
    )
    connection.rollback()
    assert connection.execute(
        "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    committed_attempt = allocate_attempt(connection, session_id)
    assert committed_attempt == attempt_id
    assert connection.execute(
        "SELECT next_attempt_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (1,)
    with pytest.raises(sqlite3.IntegrityError):
        allocate_attempt(connection, session_id, ordinal=0)
    with pytest.raises(sqlite3.IntegrityError):
        allocate_attempt(connection, session_id, ordinal=2)
    connection.close()


def test_attempt_ordinals_serialize_across_connections_and_sessions(
    db_path: Path,
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    second_session = create_session(setup, _request("2026-01-02"))
    setup.close()
    barrier = threading.Barrier(2)
    results: list[tuple[str, int]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        try:
            barrier.wait()
            attempt_id = allocate_attempt(connection, session_id)
            ordinal = connection.execute(
                "SELECT ordinal FROM attempts WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()[0]
            with lock:
                results.append((attempt_id, ordinal))
        except BaseException as error:
            with lock:
                errors.append(error)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=_inherit_harness_thread(worker)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert sorted(ordinal for _, ordinal in results) == [0, 1]
    second_connection = _connect(db_path)
    assert allocate_attempt(second_connection, second_session) == _attempt_id(
        second_session, 0, PROVIDER, OPERATION, CLAIM_POLICY
    )
    second_connection.close()


def test_recovery_ordinal_trigger_is_atomic_and_session_local(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    target_attempt = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, target_attempt)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id, reservation_id)
    first_recovery = record_recovery(
        connection,
        session_id,
        "ATTEMPT",
        target_attempt,
        "RECORD_ATTEMPT_AMBIGUITY",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert first_recovery == _recovery_id(
        session_id,
        "ATTEMPT",
        target_attempt,
        "RECORD_ATTEMPT_AMBIGUITY",
        "LAUNCH_RESERVED",
        "AMBIGUITY_RECORDED",
        0,
        RECOVERY_POLICY,
    )
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "ACKNOWLEDGE_RESTORE",
            ordinal=0,
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "ACKNOWLEDGE_RESTORE",
            ordinal=2,
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET next_recovery_ordinal = 3 WHERE session_id = ?",
            (session_id,),
        )
    _begin(connection)
    recovery_id = _recovery_id(
        session_id,
        "SESSION",
        session_id,
        "ACKNOWLEDGE_RESTORE",
        "OPEN",
        "RESTORE_ACKNOWLEDGED",
        1,
        RECOVERY_POLICY,
    )
    evidence, evidence_digest = _evidence("rollback-recovery")
    connection.execute(
        """
        INSERT INTO manual_recoveries (
            recovery_id, session_id, recovery_ordinal, target_kind, target_id,
            action, predecessor_state, resulting_state, recovery_schema,
            recovery_policy_version, operator_evidence_json,
            operator_evidence_digest, created_at_utc
        ) VALUES (?, ?, 1, 'SESSION', ?, 'ACKNOWLEDGE_RESTORE',
                  'OPEN', 'RESTORE_ACKNOWLEDGED', 1, ?, ?, ?, ?)
        """,
        (
            recovery_id,
            session_id,
            session_id,
            RECOVERY_POLICY,
            evidence,
            evidence_digest,
            TIMESTAMP,
        ),
    )
    connection.rollback()
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        1,
    )
    second_recovery = record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "ACKNOWLEDGE_RESTORE",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert second_recovery != first_recovery
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == (2,)
    second_session = create_session(connection, _request("2026-01-02"))
    second_recovery = record_recovery(
        connection,
        second_session,
        "SESSION",
        second_session,
        "ACKNOWLEDGE_RESTORE",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert second_recovery != first_recovery
    assert connection.execute(
        "SELECT recovery_ordinal FROM manual_recoveries WHERE session_id = ?",
        (second_session,),
    ).fetchone() == (0,)
    connection.close()


def test_recovery_after_absorbing_session_state_fails(db_path: Path) -> None:
    values = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    select_terminal(connection, values["session_id"], values["terminal_id"])
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        record_recovery(
            connection,
            values["session_id"],
            "SESSION",
            values["session_id"],
            "CLOSE_SESSION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    connection.close()


def test_claim_and_launch_boundaries_commit_before_fake_side_effects(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    observer = _connect(db_path)
    hooks = FakeSideEffects(observer, service=_test_service(connection))
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = _construct_provider_and_commit_process_intent(
        connection, reservation_id, hooks
    )
    process_receipt = hooks.create_process(process_intent)
    assert type(process_receipt) is FakeProcessCreationReceipt
    execution_id = record_execution(connection, reservation_id, process_receipt)
    resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
    resume_receipt = hooks.resume_thread(resume_intent)
    record_post_resume_evidence(connection, execution_id, resume_receipt)
    hooks.observe_post_resume_evidence(execution_id)
    terminal_id = record_terminal(
        connection,
        reservation_id,
        "AMBIGUOUS",
        "MAY_HAVE_OCCURRED",
        snapshot_digest=None,
    )
    assert terminal_id
    hooks.observe_terminal(reservation_id)
    with pytest.raises(sqlite3.IntegrityError):
        commit_claim(connection, attempt_id)
    assert hooks.events == [
        "provider-constructed",
        "process-intent-committed",
        "create-process",
        "process-created",
        "resume-intent-committed",
        "resume-thread",
        "post-resume-evidence",
        "terminal",
    ]
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    observer.close()
    connection.close()


def test_valid_capability_matrix_lifecycle_has_exactly_one_of_each(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = _construct_provider_and_commit_process_intent(
        connection, reservation_id, hooks
    )
    process_result = hooks.create_process(process_intent)
    assert type(process_result) is FakeProcessCreationReceipt
    execution_id = record_execution(connection, reservation_id, process_result)
    resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
    resume_result = hooks.resume_thread(resume_intent)
    record_post_resume_evidence(connection, execution_id, resume_result)
    terminal_id = record_terminal(
        connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    select_terminal(connection, session_id, terminal_id)

    assert events == [
        "provider-constructed",
        "process-intent-committed",
        "create-process",
        "process-created",
        "resume-intent-committed",
        "resume-thread",
    ]
    _assert_capability_consumed(process_intent)
    _assert_capability_consumed(process_result)
    _assert_capability_consumed(resume_intent)
    _assert_capability_consumed(resume_result)
    assert connection.execute(
        """
        SELECT
            (SELECT count(*) FROM provider_call_claims),
            (SELECT count(*) FROM launch_reservations),
            (SELECT count(*) FROM launch_executions),
            (SELECT count(*) FROM terminals),
            (SELECT count(*) FROM session_selections),
            (SELECT count(*) FROM manual_recoveries)
        """
    ).fetchone() == (1, 1, 1, 1, 1, 0)
    connection.close()


@pytest.mark.parametrize(
    "blocked_case",
    [
        "claim_without_reservation",
        "committed_without_execution",
        "process_creation_failed_without_terminal",
        "process_created_without_execution",
        "manual_review_without_terminal",
        "pre_resume_ready",
        "resume_crash",
        "resume_recorded",
        "post_resume_ambiguous",
        "ambiguous_terminal",
        "closed_terminal",
        "failed_confirmed",
        "successful_terminal",
        "successful_selection",
    ],
)
def test_claim_admission_blocks_non_retry_safe_prior_outcomes(
    db_path: Path, blocked_case: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = (
        None
        if blocked_case == "claim_without_reservation"
        else reserve_launch(connection, first_claim)
    )
    second_attempt = allocate_attempt(connection, session_id)

    if blocked_case == "claim_without_reservation":
        pass
    elif blocked_case == "committed_without_execution":
        pass
    elif blocked_case == "process_creation_failed_without_terminal":
        assert first_reservation is not None
        _record_definitive_process_failure(connection, first_reservation)
    elif blocked_case == "process_created_without_execution":
        assert first_reservation is not None
        _construct_provider_and_commit_process_intent(connection, first_reservation)
        with pytest.raises(sqlite3.IntegrityError, match="projection fact"):
            connection.execute(
                "UPDATE launch_reservations SET reservation_state = ?, "
                "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
                ("PROCESS_CREATED", PROCESS_CREATED_TIMESTAMP, first_reservation),
            )
    elif blocked_case == "manual_review_without_terminal":
        assert first_reservation is not None
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            first_reservation,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    elif blocked_case == "pre_resume_ready":
        assert first_reservation is not None
        _record_successful_process(connection, first_reservation)
    elif blocked_case == "resume_crash":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        intent = commit_resume_intent(connection, execution_id, first_reservation)
        FakeSideEffects(connection).resume_thread(intent)
    elif blocked_case in ("resume_recorded", "post_resume_ambiguous"):
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id, first_reservation)
        if blocked_case == "post_resume_ambiguous":
            record_recovery(
                connection,
                session_id,
                "ATTEMPT",
                first_attempt,
                "RECORD_ATTEMPT_AMBIGUITY",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
            connection.execute(
                "UPDATE launch_executions SET phase = 'POST_RESUME_AMBIGUOUS' "
                "WHERE launch_execution_id = ?",
                (execution_id,),
            )
            connection.commit()
    elif blocked_case == "ambiguous_terminal":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id, first_reservation)
        record_terminal(
            connection,
            first_reservation,
            "AMBIGUOUS",
            "MAY_HAVE_OCCURRED",
            snapshot_digest=None,
        )
    elif blocked_case == "closed_terminal":
        assert first_reservation is not None
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            first_reservation,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        record_terminal(
            connection,
            first_reservation,
            "CLOSED",
            "MAY_HAVE_OCCURRED",
            snapshot_digest=None,
        )
    elif blocked_case == "failed_confirmed":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id, first_reservation)
        record_terminal(
            connection, first_reservation, "FAILED", "CONFIRMED", snapshot_digest=None
        )
    elif blocked_case == "successful_terminal":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id, first_reservation)
        record_terminal(
            connection, first_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
    elif blocked_case == "successful_selection":
        assert first_reservation is not None
        execution_id = _record_successful_process(connection, first_reservation)
        _resume_and_persist(connection, execution_id, first_reservation)
        terminal_id = record_terminal(
            connection, first_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
        select_terminal(connection, session_id, terminal_id)
    else:
        raise AssertionError(f"unhandled blocked case: {blocked_case}")

    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(connection, second_attempt)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (second_attempt,),
    ).fetchone()
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        _insert_claim_row_for_test(
            connection, second_attempt, request_bytes, request_digest
        )
    connection.rollback()
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    connection.close()


def test_closed_session_rejects_new_attempt_admission(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    request_json, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="session is not open"):
        _insert_attempt_row_for_test(
            connection,
            session_id,
            0,
            request_json,
            request_digest,
        )
    assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize("insertion_path", ["helper", "direct"])
def test_claim_admission_allows_only_retry_safe_failed_not_started(
    db_path: Path, insertion_path: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    _record_definitive_process_failure(connection, first_reservation)
    record_terminal(
        connection, first_reservation, "FAILED", "NOT_STARTED", snapshot_digest=None
    )
    assert connection.execute(
        "SELECT reservation_state, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (first_reservation,),
    ).fetchone() == ("TERMINAL_RECORDED", PROCESS_FAILURE_TIMESTAMP)

    second_attempt = allocate_attempt(connection, session_id)
    if insertion_path == "helper":
        second_claim = commit_claim(connection, second_attempt)
    else:
        request_bytes, request_digest = connection.execute(
            "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
            (second_attempt,),
        ).fetchone()
        _begin(connection)
        second_claim = _insert_claim_row_for_test(
            connection, second_attempt, request_bytes, request_digest
        )
        connection.commit()
    assert second_claim == _claim_id(
        second_attempt, CLAIM_POLICY, PROVIDER, OPERATION, 1
    )
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (2,)
    connection.close()


@pytest.mark.parametrize("pair", ["process_creation_failure", "process_intent"])
def test_claim_admission_revalidates_retry_safe_parent_digest(
    db_path: Path, pair: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    _record_definitive_process_failure(connection, first_reservation)
    record_terminal(
        connection, first_reservation, "FAILED", "NOT_STARTED", snapshot_digest=None
    )
    wrong_digest = _corrupt_retry_safe_prior_evidence(
        connection, first_reservation, pair
    )

    second_attempt = allocate_attempt(connection, session_id)
    expected_field = {
        "process_creation_failure": "retry-safe process failure digest",
        "process_intent": "retry-safe process intent digest",
    }[pair]
    with pytest.raises(
        SchemaValidationError,
        match=expected_field,
    ):
        commit_claim(connection, second_attempt)

    assert not connection.in_transaction
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    assert connection.execute(
        "SELECT state FROM attempts WHERE attempt_id = ?", (second_attempt,)
    ).fetchone() == ("ALLOCATED",)
    assert connection.execute(
        f"SELECT {pair}_digest FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(first_reservation),),
    ).fetchone() == (wrong_digest,)
    connection.close()


@pytest.mark.parametrize(
    ("reservation_state", "failure_mode", "outcome_timestamp"),
    [
        ("PROCESS_INTENT_COMMITTED", False, None),
        ("PROCESS_CREATED", False, None),
        ("PROCESS_CREATION_FAILED", True, None),
        ("MANUAL_REVIEW", False, None),
        ("TERMINAL_RECORDED", False, None),
        ("COMMITTED", True, None),
        ("COMMITTED", False, PROCESS_CREATED_TIMESTAMP),
    ],
)
def test_reservations_require_a_committed_initial_fence(
    db_path: Path,
    reservation_state: str,
    failure_mode: bool,
    outcome_timestamp: str | None,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    request_digest = connection.execute(
        "SELECT request_digest FROM provider_call_claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()[0]
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError, match="committed fences"):
        _insert_reservation_row_for_test(
            connection,
            claim_id,
            request_digest,
            reservation_state,
            failure_mode,
            outcome_timestamp,
        )
    connection.rollback()
    assert connection.execute(
        "SELECT count(*) FROM launch_reservations"
    ).fetchone() == (0,)
    connection.close()


@pytest.mark.parametrize("outcome_kind", ["process", "failure", "manual"])
def test_reservation_outcome_timestamp_is_preserved_and_write_once(
    db_path: Path, outcome_kind: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if outcome_kind == "process":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
        expected_timestamp = PROCESS_CREATED_TIMESTAMP
        record_terminal(
            connection,
            reservation_id,
            "AMBIGUOUS",
            "MAY_HAVE_OCCURRED",
            snapshot_digest=None,
        )
    elif outcome_kind == "failure":
        _record_definitive_process_failure(connection, reservation_id)
        expected_timestamp = PROCESS_FAILURE_TIMESTAMP
        record_terminal(
            connection, reservation_id, "FAILED", "NOT_STARTED", snapshot_digest=None
        )
    else:
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        expected_timestamp = MANUAL_REVIEW_TIMESTAMP
        record_terminal(
            connection,
            reservation_id,
            "CLOSED",
            "MAY_HAVE_OCCURRED",
            snapshot_digest=None,
        )

    assert connection.execute(
        "SELECT outcome_recorded_at_utc FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == (expected_timestamp,)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET outcome_recorded_at_utc = ? "
            "WHERE launch_reservation_id = ?",
            ("2026-01-09T00:00:00Z", reservation_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET outcome_recorded_at_utc = NULL "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        )
    assert connection.execute(
        "SELECT outcome_recorded_at_utc FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == (expected_timestamp,)
    connection.close()


def test_terminal_transition_requires_a_prior_outcome_timestamp(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET reservation_state = ? "
            "WHERE launch_reservation_id = ?",
            ("TERMINAL_RECORDED", reservation_id),
        )
    connection.rollback()
    assert connection.execute(
        "SELECT reservation_state, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("COMMITTED", None)
    connection.close()


def test_resume_outcome_unknown_recovery_is_conservative_and_closable(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    reservation_id = reserve_launch(connection, first_claim)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    FakeSideEffects(connection).resume_thread(intent)

    recovery_id = record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert recovery_id
    assert connection.execute(
        "SELECT reservation_state, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW", PROCESS_CREATED_TIMESTAMP)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(
            connection,
            reservation_id,
            "SUCCEEDED",
            "CONFIRMED",
            snapshot_digest=TEST_SNAPSHOT_DIGEST,
        )
    terminal_id = record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED", snapshot_digest=None
    )
    assert terminal_id
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT state, closed_at_utc, close_reason FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == ("CLOSED", CLOSE_TIMESTAMP, "recovery-approved-close")
    connection.close()


def test_pre_resume_ready_has_separate_conservative_recovery_path(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    recovery_id = record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PRE_RESUME_READY",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert recovery_id
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert connection.execute(
        "SELECT phase, resume_intent_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY", None)
    connection.close()


def test_resume_outcome_unknown_recovery_grants_no_new_claim(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    first_attempt = allocate_attempt(connection, session_id)
    first_claim = commit_claim(connection, first_attempt)
    reservation_id = reserve_launch(connection, first_claim)
    second_attempt = allocate_attempt(connection, session_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    FakeSideEffects(connection).resume_thread(intent)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )

    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(connection, second_attempt)
    request_bytes, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (second_attempt,),
    ).fetchone()
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        _insert_claim_row_for_test(
            connection, second_attempt, request_bytes, request_digest
        )
    connection.rollback()
    assert connection.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    connection.close()


@pytest.mark.parametrize("failure_point", ["without_execution", "after_resume"])
def test_resume_outcome_unknown_requires_exact_unresolved_pre_resume_execution(
    db_path: Path, failure_point: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if failure_point == "after_resume":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    assert connection.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        0,
    )
    connection.close()


def test_session_close_facts_are_write_once_and_only_close_with_state(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = ? WHERE session_id = ?",
            (CLOSE_TIMESTAMP, session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = ?, close_reason = ? "
            "WHERE session_id = ?",
            (CLOSE_TIMESTAMP, "invalid-preclose", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET state = 'CLOSED', closed_at_utc = NULL, "
            "close_reason = ? WHERE session_id = ?",
            ("partial-close", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError, match="session (close facts|state)"):
        connection.execute(
            "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, "
            "close_reason = ? WHERE session_id = ?",
            (CLOSE_TIMESTAMP, "direct-close", session_id),
        )
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = ? WHERE session_id = ?",
            ("2026-01-10T00:00:00Z", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET close_reason = ? WHERE session_id = ?",
            ("replacement-close-reason", session_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE sessions SET closed_at_utc = NULL, close_reason = NULL "
            "WHERE session_id = ?",
            (session_id,),
        )

    selected_session = create_session(connection, _request("2026-01-02"))
    selected_attempt = allocate_attempt(connection, selected_session)
    selected_claim = commit_claim(connection, selected_attempt)
    selected_reservation = reserve_launch(connection, selected_claim)
    selected_execution = _record_successful_process(connection, selected_reservation)
    _resume_and_persist(connection, selected_execution, selected_reservation)
    selected_terminal = record_terminal(
        connection, selected_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    select_terminal(connection, selected_session, selected_terminal)
    connection.execute(
        "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, close_reason = ? "
        "WHERE session_id = ?",
        (CLOSE_TIMESTAMP, "selected-close", selected_session),
    )
    connection.commit()
    assert connection.execute(
        "SELECT state, closed_at_utc, close_reason FROM sessions WHERE session_id = ?",
        (selected_session,),
    ).fetchone() == ("CLOSED", CLOSE_TIMESTAMP, "selected-close")
    selection_selected_at, session_closed_at = connection.execute(
        """
        SELECT ss.selected_at_utc, s.closed_at_utc
        FROM session_selections ss
        JOIN sessions s ON s.session_id = ss.session_id
        WHERE ss.session_id = ?
        """,
        (selected_session,),
    ).fetchone()
    assert (selection_selected_at, session_closed_at) == (
        SELECTION_TIMESTAMP,
        CLOSE_TIMESTAMP,
    )
    assert selection_selected_at <= session_closed_at
    connection.close()


def test_process_intent_race_grants_exactly_one_process_call(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    setup.close()

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    outcome_lock = threading.Lock()
    events: list[str] = []
    event_lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        barrier.wait()
        try:
            intent = _construct_provider_and_commit_process_intent(
                connection, reservation_id, hooks
            )
            result = hooks.create_process(intent)
            assert type(result) is FakeProcessCreationReceipt
            record_execution(connection, reservation_id, result)
            outcome = "winner"
        except ValueError:
            outcome = "loser"
        with outcome_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(target=_inherit_harness_thread(worker)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["loser", "winner"]
    assert events == [
        "provider-constructed",
        "process-intent-committed",
        "create-process",
        "process-created",
    ]
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state, process_intent_json IS NOT NULL, "
        "process_intent_digest IS NOT NULL, process_intent_committed_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("PROCESS_CREATED", 1, 1, PROCESS_INTENT_TIMESTAMP)
    assert verify.execute("SELECT count(*) FROM launch_executions").fetchone() == (1,)
    verify.close()


def test_test_capabilities_are_bound_to_issuing_harness_service(
    tmp_path: Path,
) -> None:
    del tmp_path
    harness_a = Architecture77HarnessAuthority.create()
    harness_b = Architecture77HarnessAuthority.create()
    connection_a = harness_a._connection
    connection_b = harness_b._connection
    service_a = harness_a.bind_connection(connection_a)
    service_b = harness_b.bind_connection(connection_b)
    hooks_a = FakeSideEffects(connection_a, service=service_a)
    hooks_b = FakeSideEffects(connection_b, service=service_b)

    try:
        session_id = service_a.create_session(_request())
        attempt_id = service_a.allocate_attempt(session_id)
        claim_id = service_a.commit_claim(attempt_id)
        permit = service_a.reserve_launch(claim_id)
        reservation_id = permit.reservation_id
        session_b = service_b.create_session(_request())
        attempt_b = service_b.allocate_attempt(session_b)
        claim_b = service_b.commit_claim(attempt_b)
        permit_b = service_b.reserve_launch(claim_b)
        assert (session_id, attempt_id, claim_id, permit.reservation_id) == (
            session_b,
            attempt_b,
            claim_b,
            permit_b.reservation_id,
        )
        before_b = _database_rows(connection_b)

        before = _database_rows(connection_a)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            hooks_b.construct_provider(permit)
        assert _database_rows(connection_a) == before
        assert _database_rows(connection_b) == before_b

        provider = hooks_a.construct_provider(permit)
        before = _database_rows(connection_a)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            service_b.commit_process_intent(reservation_id, provider)
        assert _database_rows(connection_a) == before
        assert _database_rows(connection_b) == before_b

        process_intent = service_a.commit_process_intent(reservation_id, provider)
        before = _database_rows(connection_a)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            hooks_b.create_process(process_intent)
        assert _database_rows(connection_a) == before
        assert _database_rows(connection_b) == before_b

        process_result = hooks_a.create_process(process_intent)
        assert type(process_result) is FakeProcessCreationReceipt
        before = _database_rows(connection_a)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            service_b.record_execution(reservation_id, process_result)
        assert _database_rows(connection_a) == before
        assert _database_rows(connection_b) == before_b

        execution_id = service_a.record_execution(reservation_id, process_result)
        resume_intent = service_a.commit_resume_intent(execution_id, reservation_id)
        before = _database_rows(connection_a)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            hooks_b.resume_thread(resume_intent)
        assert _database_rows(connection_a) == before
        assert _database_rows(connection_b) == before_b

        resume_result = hooks_a.resume_thread(resume_intent)
        before = _database_rows(connection_a)
        with pytest.raises(TypeError, match="invalid test service provenance service"):
            service_b.record_post_resume_evidence(execution_id, resume_result)
        assert _database_rows(connection_a) == before
        assert _database_rows(connection_b) == before_b

        service_a.record_post_resume_evidence(execution_id, resume_result)
    finally:
        harness_a.close()
        harness_b.close()


def test_reservation_race_issues_one_provider_permit_and_construction(
    db_path: Path,
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    setup.close()
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, FakeConstructedProvider | None]] = []
    outcomes_lock = threading.Lock()
    events: list[str] = []
    event_lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        barrier.wait()
        try:
            permit = reserve_launch(connection, claim_id)
            provider = hooks.construct_provider(permit)
            outcome = ("winner", provider)
        except (ValueError, sqlite3.IntegrityError):
            outcome = ("loser", None)
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(target=_inherit_harness_thread(worker)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(name for name, _ in outcomes) == ["loser", "winner"]
    assert events == ["provider-constructed"]
    verify = _connect(db_path)
    assert verify.execute("SELECT count(*) FROM launch_reservations").fetchone() == (1,)
    verify.close()
    provider = next(provider for name, provider in outcomes if name == "winner")
    assert provider is not None
    _consume_capability_for_test(provider)


def test_provider_permit_and_constructed_provider_are_exact_one_shot_objects(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    first_session = create_session(connection)
    first_attempt = allocate_attempt(connection, first_session)
    first_claim = commit_claim(connection, first_attempt)
    first_permit = reserve_launch(connection, first_claim)
    hooks = FakeSideEffects(connection)

    reconstructed = _forged_capability(
        type(first_permit),
        reservation_id=first_permit.reservation_id,
        _issuer=object(),
        _permit=object(),
    )
    copied = replace(first_permit)
    for invalid in (reconstructed, copied):
        with pytest.raises((TypeError, ValueError), match="invalid|not issued"):
            hooks.construct_provider(invalid)
    with pytest.raises(TypeError, match="reservation-issued"):
        hooks.construct_provider(first_claim)  # type: ignore[arg-type]

    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_permit = reserve_launch(connection, second_claim)
    cross_reservation = replace(
        first_permit, reservation_id=second_permit.reservation_id
    )
    with pytest.raises(ValueError, match="not issued"):
        hooks.construct_provider(cross_reservation)

    provider = hooks.construct_provider(first_permit)
    with pytest.raises(ValueError, match="consumed|not issued"):
        hooks.construct_provider(first_permit)
    with pytest.raises(TypeError, match="opaque constructed provider"):
        commit_process_intent(connection, first_permit)  # type: ignore[call-arg]
    forged_provider = _forged_capability(
        type(provider),
        reservation_id=provider.reservation_id,
        _issuer=object(),
        _permit=object(),
    )
    for invalid_provider in (replace(provider), forged_provider):
        with pytest.raises((TypeError, ValueError), match="invalid|not issued"):
            commit_process_intent(connection, first_permit, invalid_provider)
    with pytest.raises(ValueError, match="another reservation"):
        commit_process_intent(connection, second_permit, provider)

    commit_process_intent(connection, first_permit, provider)
    with pytest.raises(ValueError, match="consumed|not issued"):
        commit_process_intent(connection, first_permit, provider)
    _consume_capability_for_test(second_permit)
    connection.close()


def test_provider_permit_is_frozen_and_forced_mutation_cannot_redirect(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _connect(db_path)
    hooks = FakeSideEffects(connection)
    permits: list[FakeProviderConstructionPermit] = []
    for target_date in ("2026-01-01", "2026-01-02"):
        session_id = create_session(connection, _request(target_date))
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        permits.append(reserve_launch(connection, claim_id))
    original, substituted = permits

    for field_name, value in (("reservation_id", substituted.reservation_id),):
        with pytest.raises(FrozenInstanceError):
            setattr(original, field_name, value)

    selected_arbiters: list[str] = []

    class ArbiterProbe:
        def __init__(self, reservation_id: str) -> None:
            selected_arbiters.append(str(reservation_id))

        def __enter__(self) -> ArbiterProbe:
            raise AssertionError("mutated capability reached arbiter selection")

        def __exit__(self, *args: object) -> None:
            return None

    traces: list[str] = []
    connection.set_trace_callback(traces.append)
    before = connection.execute(
        "SELECT launch_reservation_id, reservation_state "
        "FROM launch_reservations ORDER BY launch_reservation_id"
    ).fetchall()
    traces.clear()
    with monkeypatch.context() as context:
        context.setattr(
            sys.modules[__name__], "InterprocessLifecycleArbiter", ArbiterProbe
        )
        with _mutated_frozen_object_for_test(
            original, reservation_id=substituted.reservation_id
        ):
            with pytest.raises(ValueError, match="registry binding mismatch"):
                hooks.construct_provider(original)
        copied = replace(original)
        with pytest.raises(ValueError, match="registry binding mismatch"):
            hooks.construct_provider(copied)
    connection.set_trace_callback(None)

    assert selected_arbiters == []
    assert traces == []
    assert hooks.events == []
    assert (
        connection.execute(
            "SELECT launch_reservation_id, reservation_state "
            "FROM launch_reservations ORDER BY launch_reservation_id"
        ).fetchall()
        == before
    )

    substituted_provider = hooks.construct_provider(substituted)
    with pytest.raises(ValueError, match="consumed|not issued"):
        hooks.construct_provider(substituted)
    original_provider = hooks.construct_provider(original)
    _consume_capability_for_test(substituted_provider)
    _consume_capability_for_test(original_provider)
    assert hooks.events == ["provider-constructed", "provider-constructed"]
    connection.close()


@pytest.mark.parametrize(
    "capability_name",
    [
        "provider-permit",
        "constructed-provider",
        "process-intent",
        "process-success-result",
        "process-failure-result",
        "resume-intent",
        "resume-result",
    ],
)
def test_all_process_local_registries_reject_visible_lineage_mutation(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capability_name: str,
) -> None:
    connection = _connect(db_path)
    hooks = FakeSideEffects(connection)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    provider_permit = reserve_launch(connection, claim_id)
    reservation_id = provider_permit.reservation_id
    execution_id: str | None = None

    if capability_name == "provider-permit":
        authority: object = provider_permit

        def invoke() -> None:
            hooks.construct_provider(provider_permit)

        mutation = {"reservation_id": str(uuid.UUID(int=0))}
    else:
        provider = hooks.construct_provider(provider_permit)
        if capability_name == "constructed-provider":
            authority = provider

            def invoke() -> None:
                commit_process_intent(connection, reservation_id, provider)

            mutation = {"reservation_id": str(uuid.UUID(int=0))}
        else:
            process_intent = commit_process_intent(connection, reservation_id, provider)
            if capability_name == "process-intent":
                authority = process_intent

                def invoke() -> None:
                    hooks.create_process(process_intent)

                mutation = {"reservation_id": str(uuid.UUID(int=0))}
            else:
                process_result = hooks.create_process(
                    process_intent,
                    fail=capability_name == "process-failure-result",
                )
                if capability_name == "process-success-result":
                    assert type(process_result) is FakeProcessCreationReceipt
                    authority = process_result

                    def invoke() -> None:
                        record_execution(connection, reservation_id, process_result)

                    mutation = {"reservation_id": str(uuid.UUID(int=0))}
                elif capability_name == "process-failure-result":
                    assert type(process_result) is FakeProcessCreationFailure
                    authority = process_result

                    def invoke() -> None:
                        record_process_creation_failure(
                            connection, reservation_id, process_result
                        )

                    mutation = {"reservation_id": str(uuid.UUID(int=0))}
                else:
                    assert type(process_result) is FakeProcessCreationReceipt
                    execution_id = record_execution(
                        connection, reservation_id, process_result
                    )
                    resume_intent = commit_resume_intent(
                        connection, execution_id, reservation_id
                    )
                    if capability_name == "resume-intent":
                        authority = resume_intent

                        def invoke() -> None:
                            hooks.resume_thread(resume_intent)

                        mutation = {"execution_id": str(uuid.UUID(int=0))}
                    else:
                        resume_result = hooks.resume_thread(resume_intent)
                        authority = resume_result

                        def invoke() -> None:
                            assert execution_id is not None
                            record_post_resume_evidence(
                                connection, execution_id, resume_result
                            )

                        mutation = {"execution_id": str(uuid.UUID(int=0))}

    selected_arbiters: list[str] = []

    class ArbiterProbe:
        def __init__(self, selected_reservation_id: str) -> None:
            selected_arbiters.append(str(selected_reservation_id))

        def __enter__(self) -> ArbiterProbe:
            raise AssertionError("mutated authority reached arbiter selection")

        def __exit__(self, *args: object) -> None:
            return None

    before_rows = _database_rows(connection)
    events_before = list(hooks.events)
    with monkeypatch.context() as context:
        context.setattr(
            sys.modules[__name__], "InterprocessLifecycleArbiter", ArbiterProbe
        )
        with _mutated_frozen_object_for_test(authority, **mutation):
            with pytest.raises(ValueError, match="registry binding mismatch"):
                invoke()
    assert selected_arbiters == []
    assert _database_rows(connection) == before_rows
    assert hooks.events == events_before
    _assert_capability_available(authority)

    if capability_name == "provider-permit":
        produced = hooks.construct_provider(provider_permit)
        _consume_capability_for_test(produced)
    elif capability_name == "constructed-provider":
        produced = commit_process_intent(connection, reservation_id, authority)
        _consume_capability_for_test(produced)
    elif capability_name == "process-intent":
        produced = hooks.create_process(authority)
        _consume_capability_for_test(produced)
    elif capability_name == "process-success-result":
        assert type(authority) is FakeProcessCreationReceipt
        record_execution(connection, reservation_id, authority)
    elif capability_name == "process-failure-result":
        assert type(authority) is FakeProcessCreationFailure
        record_process_creation_failure(connection, reservation_id, authority)
    elif capability_name == "resume-intent":
        assert type(authority) is FakeResumeIntent
        produced = hooks.resume_thread(authority)
        _consume_capability_for_test(produced)
    else:
        assert execution_id is not None
        assert type(authority) is FakeResumeReceipt
        record_post_resume_evidence(connection, execution_id, authority)
    _assert_capability_consumed(authority)
    connection.close()


@pytest.mark.parametrize("recover_after_rollback", [False, True])
def test_constructed_provider_retry_survives_rollback_until_recovery(
    db_path: Path, recover_after_rollback: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    permit = reserve_launch(connection, claim_id)
    provider = FakeSideEffects(connection).construct_provider(permit)
    connection.execute(
        """
        CREATE TRIGGER fail_provider_handoff_for_test
        BEFORE UPDATE OF reservation_state ON launch_reservations
        WHEN NEW.reservation_state = 'PROCESS_INTENT_COMMITTED'
        BEGIN
            SELECT RAISE(ABORT, 'transient provider handoff failure');
        END
        """
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="transient provider"):
        commit_process_intent(connection, permit, provider)
    _assert_capability_available(provider)
    _assert_capability_available(provider)
    connection.execute("DROP TRIGGER fail_provider_handoff_for_test")
    connection.commit()

    if recover_after_rollback:
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            permit,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        with pytest.raises(ValueError, match="COMMITTED|revoked|not issued"):
            commit_process_intent(connection, permit, provider)
        _assert_capability_available(provider)
        _consume_capability_for_test(provider)
    else:
        intent = commit_process_intent(connection, permit, provider)
        assert intent
        _assert_capability_consumed(provider)
        _consume_capability_for_test(intent)
    connection.close()


@pytest.mark.parametrize("failure_mode", ["lost-result", "modeled-failure"])
def test_provider_construction_loss_allows_only_reservation_recovery(
    db_path: Path, failure_mode: str
) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    permit = reserve_launch(connection, claim_id)
    provider: FakeConstructedProvider | None = None
    if failure_mode == "modeled-failure":
        with pytest.raises(RuntimeError, match="modeled provider"):
            hooks.construct_provider(permit, fail=True)
        assert events == ["provider-constructed", "provider-construction-failed"]
    else:
        provider = hooks.construct_provider(permit)
        _consume_capability_for_test(provider)
        assert events == ["provider-constructed"]

    with pytest.raises(ValueError, match="consumed|not issued"):
        hooks.construct_provider(permit)
    if provider is not None:
        with pytest.raises(ValueError, match="not issued"):
            commit_process_intent(connection, permit, provider)
    assert connection.execute(
        "SELECT reservation_state, process_intent_json FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (permit,),
    ).fetchone() == ("COMMITTED", None)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        permit,
        "CLASSIFY_LAUNCH_RESERVATION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    connection.close()


def test_process_hook_requires_matching_one_shot_opaque_permit(db_path: Path) -> None:
    connection = _connect(db_path)
    first_session = create_session(connection)
    first_attempt = allocate_attempt(connection, first_session)
    first_claim = commit_claim(connection, first_attempt)
    first_reservation = reserve_launch(connection, first_claim)
    hooks = FakeSideEffects(connection)
    with pytest.raises(TypeError, match="opaque fake process intent"):
        hooks.create_process(first_reservation)  # type: ignore[arg-type]

    intent = _construct_provider_and_commit_process_intent(
        connection, first_reservation, hooks
    )
    for fabricated in (
        replace(intent),
        replace(intent, reservation_id=str(uuid.UUID(int=0))),
    ):
        with pytest.raises(ValueError, match="not issued"):
            hooks.create_process(fabricated)
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    cross_reservation = replace(intent, reservation_id=second_reservation)
    with pytest.raises(ValueError, match="registry binding mismatch"):
        hooks.create_process(cross_reservation)

    result = hooks.create_process(intent)
    assert type(result) is FakeProcessCreationReceipt
    with pytest.raises(ValueError, match="already consumed"):
        hooks.create_process(intent)
    record_execution(connection, first_reservation, result)
    connection.close()


def test_process_success_receipt_is_exact_canonical_and_one_shot(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    with pytest.raises(TypeError, match="fake process creation receipt"):
        record_execution(connection, reservation_id, None)  # type: ignore[arg-type]

    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    receipt = FakeSideEffects(connection).create_process(intent)
    assert type(receipt) is FakeProcessCreationReceipt
    canonical_process = json.loads(receipt.process_json)
    malformed_receipts = [
        {"process_json": b"{}", "process_digest": _digest(b"{}")},
        {
            "process_json": _json({**canonical_process, "extra": True}),
            "process_digest": _digest(_json({**canonical_process, "extra": True})),
        },
        {
            "process_json": _json({**canonical_process, "creation_result": "UNKNOWN"}),
            "process_digest": _digest(
                _json({**canonical_process, "creation_result": "UNKNOWN"})
            ),
        },
        {
            "process_json": b"not-json",
            "process_digest": _digest(b"not-json"),
        },
        {"process_digest": b"x" * 32},
    ]
    for changes in malformed_receipts:
        with _mutated_frozen_object_for_test(receipt, **changes):
            with pytest.raises(ValueError, match="registry binding|canonical evidence"):
                record_execution(connection, reservation_id, receipt)
    with pytest.raises(ValueError, match="not issued"):
        record_execution(connection, reservation_id, replace(receipt))
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )

    other_session = create_session(connection, _request("2026-01-02"))
    other_attempt = allocate_attempt(connection, other_session)
    other_claim = commit_claim(connection, other_attempt)
    other_reservation = reserve_launch(connection, other_claim)
    with pytest.raises(ValueError, match="another reservation"):
        record_execution(connection, other_reservation, receipt)

    execution_id = record_execution(connection, reservation_id, receipt)
    assert execution_id
    with pytest.raises(ValueError, match="already consumed"):
        record_execution(connection, reservation_id, receipt)
    connection.close()


def test_process_failure_result_is_exact_and_only_not_started_path(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    failure = FakeSideEffects(connection).create_process(intent, fail=True)
    assert type(failure) is FakeProcessCreationFailure
    with pytest.raises(TypeError, match="fake process creation receipt"):
        record_execution(connection, reservation_id, failure)  # type: ignore[arg-type]
    for changes in (
        {"result_json": b"{}", "result_digest": _digest(b"{}")},
        {"result_digest": b"x" * 32},
    ):
        with _mutated_frozen_object_for_test(failure, **changes):
            with pytest.raises(ValueError, match="registry binding|canonical evidence"):
                record_process_creation_failure(connection, reservation_id, failure)
    with pytest.raises(ValueError, match="not issued"):
        record_process_creation_failure(connection, reservation_id, replace(failure))
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("PROCESS_INTENT_COMMITTED",)

    other_session = create_session(connection, _request("2026-01-02"))
    other_attempt = allocate_attempt(connection, other_session)
    other_claim = commit_claim(connection, other_attempt)
    other_reservation = reserve_launch(connection, other_claim)
    with pytest.raises(ValueError, match="another reservation"):
        record_process_creation_failure(connection, other_reservation, failure)

    record_process_creation_failure(connection, reservation_id, failure)
    terminal_id = record_terminal(
        connection, reservation_id, "FAILED", "NOT_STARTED", snapshot_digest=None
    )
    assert terminal_id
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    with pytest.raises(ValueError, match="already consumed"):
        record_process_creation_failure(connection, reservation_id, failure)
    connection.close()


@pytest.mark.parametrize("failure_result", [False, True])
def test_process_result_requires_adapter_provenance_and_survives_rollback(
    db_path: Path, failure_result: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    result = FakeSideEffects(connection).create_process(intent, fail=failure_result)

    for fabricated in (
        replace(result),
        replace(result, reservation_id=str(uuid.UUID(int=0))),
    ):
        with pytest.raises(ValueError, match="not issued"):
            if failure_result:
                assert type(fabricated) is FakeProcessCreationFailure
                record_process_creation_failure(connection, reservation_id, fabricated)
            else:
                assert type(fabricated) is FakeProcessCreationReceipt
                record_execution(connection, reservation_id, fabricated)

    if failure_result:
        assert type(result) is FakeProcessCreationFailure
        connection.execute(
            """
            CREATE TRIGGER fail_process_result_for_test
            BEFORE UPDATE OF reservation_state ON launch_reservations
            WHEN NEW.reservation_state = 'PROCESS_CREATION_FAILED'
            BEGIN
                SELECT RAISE(ABORT, 'transient process persistence failure');
            END
            """
        )
    else:
        assert type(result) is FakeProcessCreationReceipt
        connection.execute(
            """
            CREATE TRIGGER fail_process_result_for_test
            BEFORE INSERT ON launch_executions
            BEGIN
                SELECT RAISE(ABORT, 'transient process persistence failure');
            END
            """
        )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="transient process"):
        if failure_result:
            record_process_creation_failure(connection, reservation_id, result)
        else:
            record_execution(connection, reservation_id, result)
    _assert_capability_available(result)
    _assert_capability_available(result)
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("PROCESS_INTENT_COMMITTED",)

    connection.execute("DROP TRIGGER fail_process_result_for_test")
    connection.commit()
    if failure_result:
        record_process_creation_failure(connection, reservation_id, result)
    else:
        record_execution(connection, reservation_id, result)
    _assert_capability_consumed(result)
    connection.close()


@pytest.mark.parametrize("winner", ["recovery", "dispatch"])
def test_process_dispatch_and_recovery_share_lifecycle_arbiter(
    db_path: Path, winner: str
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    intent = _construct_provider_and_commit_process_intent(setup, reservation_id)
    setup.close()
    lifecycle_lock = InterprocessLifecycleArbiter(reservation_id)
    winner_has_lock = threading.Event()
    events: list[str] = []
    event_lock = threading.Lock()
    outcomes: list[tuple[str, object | None]] = []
    outcomes_lock = threading.Lock()

    def run_recovery(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                _require_no_active_transaction(connection)
                with _test_service(connection).lifecycle_lease(reservation_id) as lease:
                    winner_has_lock.set()
                    lease.record_recovery(
                        session_id,
                        "LAUNCH_RESERVATION",
                        reservation_id,
                        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
                        None,
                        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                    )
            else:
                winner_has_lock.wait()
                record_recovery(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
            outcome: tuple[str, object | None] = ("recovery", None)
        except (ValueError, sqlite3.IntegrityError):
            outcome = ("recovery-rejected", None)
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    def run_dispatch(first: bool) -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        try:
            if first:
                _require_no_active_transaction(connection)
                with lifecycle_lock:
                    winner_has_lock.set()
                    result = hooks._create_process_locked(intent, fail=False)
            else:
                winner_has_lock.wait()
                result = hooks.create_process(intent)
            outcome = ("dispatch", result)
        except ValueError:
            outcome = ("dispatch-rejected", None)
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(
            target=_inherit_harness_thread(run_recovery, winner == "recovery")
        ),
        threading.Thread(
            target=_inherit_harness_thread(run_dispatch, winner == "dispatch")
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if winner == "recovery":
        assert sorted(name for name, _ in outcomes) == [
            "dispatch-rejected",
            "recovery",
        ]
        assert events == []
        _assert_capability_available(intent)
    else:
        assert sorted(name for name, _ in outcomes) == ["dispatch", "recovery"]
        assert events == [
            "process-intent-committed",
            "create-process",
            "process-created",
        ]
        _assert_capability_consumed(intent)
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    verify.close()
    _consume_capability_for_test(intent)
    for outcome, result in outcomes:
        if outcome == "dispatch":
            assert isinstance(result, FakeProcessCreationReceipt)
            _consume_capability_for_test(result)


@pytest.mark.parametrize("failure_result", [False, True])
@pytest.mark.parametrize("winner", ["recovery", "persistence"])
def test_process_result_persistence_and_recovery_are_serialized(
    db_path: Path, failure_result: bool, winner: str
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    intent = _construct_provider_and_commit_process_intent(setup, reservation_id)
    result = FakeSideEffects(setup).create_process(intent, fail=failure_result)
    setup.close()
    winner_has_lock = threading.Event()
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def run_recovery(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                _require_no_active_transaction(connection)
                with _test_service(connection).lifecycle_lease(reservation_id) as lease:
                    winner_has_lock.set()
                    lease.record_recovery(
                        session_id,
                        "LAUNCH_RESERVATION",
                        reservation_id,
                        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
                        None,
                        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                    )
            else:
                winner_has_lock.wait()
                record_recovery(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
            outcome = "recovery"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "recovery-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    def run_persistence(first: bool) -> None:
        connection = _connect(db_path)

        def persist() -> None:
            if failure_result:
                assert type(result) is FakeProcessCreationFailure
                record_process_creation_failure(connection, reservation_id, result)
            else:
                assert type(result) is FakeProcessCreationReceipt
                record_execution(connection, reservation_id, result)

        try:
            if first:
                _require_no_active_transaction(connection)
                with _test_service(connection).lifecycle_lease(reservation_id) as lease:
                    winner_has_lock.set()
                    if failure_result:
                        assert type(result) is FakeProcessCreationFailure
                        lease.record_process_creation_failure(reservation_id, result)
                    else:
                        assert type(result) is FakeProcessCreationReceipt
                        lease.record_execution(reservation_id, result)
            else:
                winner_has_lock.wait()
                persist()
            outcome = "persistence"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "persistence-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(
            target=_inherit_harness_thread(run_recovery, winner == "recovery")
        ),
        threading.Thread(
            target=_inherit_harness_thread(run_persistence, winner == "persistence")
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    verify = _connect(db_path)
    if winner == "recovery":
        assert sorted(outcomes) == ["persistence-rejected", "recovery"]
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == ("MANUAL_REVIEW",)
        _assert_capability_available(result)
        _consume_capability_for_test(result)
    else:
        assert sorted(outcomes) == ["persistence", "recovery-rejected"]
        expected_state = (
            "PROCESS_CREATION_FAILED" if failure_result else "PROCESS_CREATED"
        )
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == (expected_state,)
        _assert_capability_consumed(result)
    verify.close()


@pytest.mark.parametrize(
    ("capability", "revoking_state"),
    [
        (capability, revoking_state)
        for capability in (
            "provider-construction-permit",
            "constructed-provider",
            "process-intent",
            "process-success-result",
            "process-failure-result",
            "resume-intent",
            "resume-success-result",
        )
        for revoking_state in ("MANUAL_REVIEW", "TERMINAL_RECORDED", "CLOSED")
    ]
    + [
        (capability, revoking_state)
        for capability in (
            "provider-construction-permit",
            "constructed-provider",
            "process-intent",
            "process-success-result",
            "resume-intent",
            "resume-success-result",
        )
        for revoking_state in ("SUCCESS_SELECTED", "CLOSED_AFTER_SELECTION")
    ]
    + [
        ("provider-construction-permit", "PROCESS_INTENT_COMMITTED"),
        ("constructed-provider", "PROCESS_INTENT_COMMITTED"),
    ],
)
def test_authority_capability_revocation_matrix(
    db_path: Path, capability: str, revoking_state: str
) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    authority: object
    execution_id: str | None = None

    if revoking_state in {"SUCCESS_SELECTED", "CLOSED_AFTER_SELECTION"}:
        provider_permit = reservation_id
        constructed_provider = hooks.construct_provider(provider_permit)
        process_intent = commit_process_intent(
            connection, reservation_id, constructed_provider
        )
        process_result = hooks.create_process(process_intent)
        assert type(process_result) is FakeProcessCreationReceipt
        execution_id = record_execution(connection, reservation_id, process_result)
        resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
        resume_result = hooks.resume_thread(resume_intent)
        record_post_resume_evidence(connection, execution_id, resume_result)
        terminal_id = record_terminal(
            connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
        select_terminal(connection, session_id, terminal_id)
        if revoking_state == "CLOSED_AFTER_SELECTION":
            connection.execute(
                "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, "
                "close_reason = ? WHERE session_id = ?",
                (CLOSE_TIMESTAMP, "selected-close", session_id),
            )
            connection.commit()
        authority = {
            "provider-construction-permit": provider_permit,
            "constructed-provider": constructed_provider,
            "process-intent": process_intent,
            "process-success-result": process_result,
            "resume-intent": resume_intent,
            "resume-success-result": resume_result,
        }[capability]
    elif capability in {
        "provider-construction-permit",
        "constructed-provider",
    }:
        provider_permit = reservation_id
        constructed_provider: FakeConstructedProvider | None = None
        if (
            capability == "constructed-provider"
            or revoking_state == "PROCESS_INTENT_COMMITTED"
        ):
            constructed_provider = hooks.construct_provider(provider_permit)
        authority = (
            provider_permit
            if capability == "provider-construction-permit"
            else constructed_provider
        )
        assert authority is not None
        if revoking_state == "PROCESS_INTENT_COMMITTED":
            assert constructed_provider is not None
            commit_process_intent(connection, reservation_id, constructed_provider)
        else:
            record_recovery(
                connection,
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_LAUNCH_RESERVATION",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
    elif capability.startswith("process"):
        process_intent = _construct_provider_and_commit_process_intent(
            connection, reservation_id, hooks
        )
        if capability == "process-intent":
            authority = process_intent
        else:
            process_result = hooks.create_process(
                process_intent, fail=capability == "process-failure-result"
            )
            authority = process_result
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    else:
        execution_id = _record_successful_process(connection, reservation_id)
        resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
        if capability == "resume-intent":
            authority = resume_intent
        else:
            authority = hooks.resume_thread(resume_intent)
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )

    if revoking_state in {"TERMINAL_RECORDED", "CLOSED"}:
        record_terminal(
            connection,
            reservation_id,
            "CLOSED",
            "MAY_HAVE_OCCURRED",
            snapshot_digest=None,
        )
    if revoking_state == "CLOSED":
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "CLOSE_SESSION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )

    before = connection.execute(
        """
        SELECT s.state, r.reservation_state,
               (SELECT phase FROM launch_executions
                WHERE launch_reservation_id = r.launch_reservation_id),
               (SELECT count(*) FROM terminals
                WHERE launch_reservation_id = r.launch_reservation_id),
               (SELECT count(*) FROM session_selections
                WHERE session_id = s.session_id),
               (SELECT count(*) FROM manual_recoveries
                WHERE session_id = s.session_id)
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE r.launch_reservation_id = ?
        """,
        (str(reservation_id),),
    ).fetchone()
    events_before = list(events)

    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        if capability == "provider-construction-permit":
            assert type(authority) is FakeProviderConstructionPermit
            hooks.construct_provider(authority)
        elif capability == "constructed-provider":
            assert type(authority) is FakeConstructedProvider
            commit_process_intent(connection, reservation_id, authority)
        elif capability == "process-intent":
            assert type(authority) is FakeProcessIntent
            hooks.create_process(authority)
        elif capability == "process-success-result":
            assert type(authority) is FakeProcessCreationReceipt
            record_execution(connection, reservation_id, authority)
        elif capability == "process-failure-result":
            assert type(authority) is FakeProcessCreationFailure
            record_process_creation_failure(connection, reservation_id, authority)
        elif capability == "resume-intent":
            assert type(authority) is FakeResumeIntent
            hooks.resume_thread(authority)
        else:
            assert execution_id is not None
            assert type(authority) is FakeResumeReceipt
            record_post_resume_evidence(connection, execution_id, authority)

    after = connection.execute(
        """
        SELECT s.state, r.reservation_state,
               (SELECT phase FROM launch_executions
                WHERE launch_reservation_id = r.launch_reservation_id),
               (SELECT count(*) FROM terminals
                WHERE launch_reservation_id = r.launch_reservation_id),
               (SELECT count(*) FROM session_selections
                WHERE session_id = s.session_id),
               (SELECT count(*) FROM manual_recoveries
                WHERE session_id = s.session_id)
        FROM launch_reservations r
        JOIN provider_call_claims c ON c.claim_id = r.claim_id
        JOIN attempts a ON a.attempt_id = c.attempt_id
        JOIN sessions s ON s.session_id = a.session_id
        WHERE r.launch_reservation_id = ?
        """,
        (str(reservation_id),),
    ).fetchone()
    assert after == before
    assert events == events_before

    _consume_capability_for_test(authority)
    connection.close()


@pytest.mark.parametrize("invoke_create_process", [False, True])
def test_crash_around_process_call_is_unretryable_and_conservative(
    db_path: Path, invoke_create_process: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    result: FakeProcessCreationReceipt | FakeProcessCreationFailure | None = None
    if invoke_create_process:
        result = FakeSideEffects(connection).create_process(intent)
    connection.close()
    _consume_capability_for_test(intent)
    if result is not None:
        _consume_capability_for_test(result)

    recovered = _connect(db_path)
    durable = recovered.execute(
        "SELECT reservation_state, process_intent_json, process_intent_digest, "
        "process_intent_committed_at_utc FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone()
    assert durable == (
        "PROCESS_INTENT_COMMITTED",
        intent.intent_json,
        intent.intent_digest,
        PROCESS_INTENT_TIMESTAMP,
    )
    with pytest.raises(ValueError, match="COMMITTED|revoked|not issued"):
        _construct_provider_and_commit_process_intent(recovered, reservation_id)
    with pytest.raises(ValueError, match="already consumed|not issued"):
        FakeSideEffects(recovered).create_process(intent)
    second_attempt = allocate_attempt(recovered, session_id)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(recovered, second_attempt)

    record_recovery(
        recovered,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert recovered.execute(
        "SELECT reservation_state, process_intent_json, process_intent_digest, "
        "outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == (
        "MANUAL_REVIEW",
        intent.intent_json,
        intent.intent_digest,
        MANUAL_REVIEW_TIMESTAMP,
    )
    assert recovered.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (1,)
    assert recovered.execute(
        "SELECT action, predecessor_state, resulting_state "
        "FROM manual_recoveries WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        "PROCESS_INTENT_COMMITTED",
        "MANUAL_REVIEW",
    )
    with pytest.raises(ValueError, match="PROCESS_INTENT_COMMITTED|not issued"):
        FakeSideEffects(recovered).create_process(intent)
    recovered.close()


def test_process_unknown_recovery_allows_only_conservative_close_path(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    _consume_capability_for_test(intent)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    terminal_id = record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED", snapshot_digest=None
    )
    assert terminal_id
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == ("CLOSED",)
    connection.close()


def test_process_intent_evidence_is_paired_digest_valid_and_append_only(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_reservations SET reservation_state = "
            "'PROCESS_INTENT_COMMITTED' WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        )
    connection.rollback()

    intent = _construct_provider_and_commit_process_intent(connection, reservation_id)
    assert connection.execute(
        "SELECT reservation_state, process_intent_json, process_intent_digest, "
        "process_intent_committed_at_utc, outcome_recorded_at_utc "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == (
        "PROCESS_INTENT_COMMITTED",
        intent.intent_json,
        _digest(intent.intent_json),
        PROCESS_INTENT_TIMESTAMP,
        None,
    )
    for assignment, values in (
        ("process_intent_json = NULL", ()),
        ("process_intent_digest = NULL", ()),
        ("process_intent_committed_at_utc = NULL", ()),
        (
            "process_intent_json = ?, process_intent_digest = ?",
            (b"replacement", _digest(b"replacement")),
        ),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"UPDATE launch_reservations SET {assignment} "
                "WHERE launch_reservation_id = ?",
                (*values, reservation_id),
            )
        connection.rollback()
    with pytest.raises(ValueError, match="COMMITTED|revoked|not issued"):
        _construct_provider_and_commit_process_intent(connection, reservation_id)
    connection.close()


def test_pre_resume_recovery_revokes_intent_before_terminal_and_close(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PRE_RESUME_READY",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        commit_resume_intent(connection, execution_id, reservation_id)
    assert events == []

    record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED", snapshot_digest=None
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        commit_resume_intent(connection, execution_id, reservation_id)
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        commit_resume_intent(connection, execution_id, reservation_id)
    assert connection.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY",)
    assert hooks.events == []
    connection.close()


def test_resume_permit_is_revoked_by_unknown_outcome_recovery(db_path: Path) -> None:
    connection = _connect(db_path)
    events: list[str] = []
    hooks = FakeSideEffects(connection, events)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )

    with pytest.raises(ValueError, match="revoked"):
        hooks.resume_thread(intent)
    _assert_capability_available(intent)
    assert events == []
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)

    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(
            connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
    record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED", snapshot_digest=None
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        hooks.resume_thread(intent)
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        hooks.resume_thread(intent)
    assert connection.execute("SELECT count(*) FROM session_selections").fetchone() == (
        0,
    )
    _consume_capability_for_test(intent)
    connection.close()


def test_delayed_resume_receipt_is_revoked_by_recovery(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    receipt = FakeSideEffects(connection).resume_thread(intent)
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )

    with pytest.raises(ValueError, match="revoked"):
        record_post_resume_evidence(connection, execution_id, receipt)
    assert json.loads(receipt.result_json)["resume_result"] == "RESUMED"
    assert connection.execute(
        "SELECT phase, post_resume_json, post_resume_digest, cleanup_json, "
        "cleanup_digest FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None, None, None)
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    record_terminal(
        connection, reservation_id, "CLOSED", "MAY_HAVE_OCCURRED", snapshot_digest=None
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        record_post_resume_evidence(connection, execution_id, receipt)
    record_recovery(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    with pytest.raises(ValueError, match="revoked|unavailable"):
        record_post_resume_evidence(connection, execution_id, receipt)
    connection.close()


@pytest.mark.parametrize("phase", ["PRE_RESUME_READY", "RESUME_INTENT_COMMITTED"])
def test_direct_sql_resume_phase_advance_fails_after_manual_review(
    db_path: Path, phase: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )
    if phase == "PRE_RESUME_READY":
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_PRE_RESUME_READY",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE launch_executions SET phase = 'RESUME_INTENT_COMMITTED', "
                "resume_intent_json = ?, resume_intent_digest = ?, "
                "resume_intent_committed_at_utc = ? WHERE launch_execution_id = ?",
                (
                    intent_json,
                    _digest(intent_json),
                    RESUME_INTENT_TIMESTAMP,
                    execution_id,
                ),
            )
    else:
        intent = commit_resume_intent(connection, execution_id, reservation_id)
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        post_json = _json(
            {
                "execution_id": execution_id,
                "resume_intent_digest": intent.intent_digest.hex(),
                "resume_result": "RESUMED",
                "schema": 1,
            }
        )
        cleanup, cleanup_digest = _evidence(f"cleanup:{execution_id}")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
                "post_resume_json = ?, post_resume_digest = ?, cleanup_json = ?, "
                "cleanup_digest = ? WHERE launch_execution_id = ?",
                (
                    post_json,
                    _digest(post_json),
                    cleanup,
                    cleanup_digest,
                    execution_id,
                ),
            )
        _consume_capability_for_test(intent)
    connection.rollback()
    assert connection.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    connection.close()


def test_recovery_race_with_resume_intent_has_one_valid_winner(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    setup.close()
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, bool, FakeResumeIntent | None]] = []
    outcome_lock = threading.Lock()

    def intent_worker() -> None:
        connection = _connect(db_path)
        barrier.wait()
        intent: FakeResumeIntent | None = None
        try:
            intent = commit_resume_intent(connection, execution_id, reservation_id)
            success = True
        except (ValueError, sqlite3.IntegrityError):
            success = False
        with outcome_lock:
            outcomes.append(("intent", success, intent))
        connection.close()

    def recovery_worker() -> None:
        connection = _connect(db_path)
        barrier.wait()
        try:
            record_recovery(
                connection,
                session_id,
                "LAUNCH_RESERVATION",
                reservation_id,
                "CLASSIFY_PRE_RESUME_READY",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
            success = True
        except (ValueError, sqlite3.IntegrityError):
            success = False
        with outcome_lock:
            outcomes.append(("recovery", success, None))
        connection.close()

    threads = [
        threading.Thread(target=_inherit_harness_thread(intent_worker)),
        threading.Thread(target=_inherit_harness_thread(recovery_worker)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(success for _, success, _ in outcomes) == 1
    verify = _connect(db_path)
    intent_outcome = next(item for item in outcomes if item[0] == "intent")
    if intent_outcome[1]:
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == ("PROCESS_CREATED",)
        assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
            0,
        )
        assert intent_outcome[2] is not None
        _consume_capability_for_test(intent_outcome[2])
    else:
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == ("MANUAL_REVIEW",)
        assert verify.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
            1,
        )
    verify.close()


@pytest.mark.parametrize("winner", ["recovery", "hook"])
def test_recovery_race_with_resume_dispatch_is_serialized(
    db_path: Path, winner: str
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    intent = commit_resume_intent(setup, execution_id, reservation_id)
    setup.close()
    lifecycle_lock = InterprocessLifecycleArbiter(reservation_id)
    winner_has_lock = threading.Event()
    events: list[str] = []
    event_lock = threading.Lock()
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def run_recovery(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                _require_no_active_transaction(connection)
                with _test_service(connection).lifecycle_lease(reservation_id) as lease:
                    winner_has_lock.set()
                    lease.record_recovery(
                        session_id,
                        "LAUNCH_RESERVATION",
                        reservation_id,
                        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                        None,
                        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                    )
            else:
                winner_has_lock.wait()
                record_recovery(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
            outcome = "recovery"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "recovery-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    def run_hook(first: bool) -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        try:
            if first:
                _require_no_active_transaction(connection)
                with lifecycle_lock:
                    winner_has_lock.set()
                    hooks._resume_thread_locked(intent, fail=False)
            else:
                winner_has_lock.wait()
                hooks.resume_thread(intent)
            outcome = "hook"
        except ValueError:
            outcome = "hook-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(
            target=_inherit_harness_thread(run_recovery, winner == "recovery")
        ),
        threading.Thread(target=_inherit_harness_thread(run_hook, winner == "hook")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if winner == "recovery":
        assert sorted(outcomes) == ["hook-rejected", "recovery"]
        assert events == []
        _consume_capability_for_test(intent)
    else:
        assert sorted(outcomes) == ["hook", "recovery"]
        assert events == ["resume-intent-committed", "resume-thread"]
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("MANUAL_REVIEW",)
    verify.close()


@pytest.mark.parametrize("winner", ["recovery", "receipt"])
def test_recovery_race_with_receipt_persistence_is_serialized(
    db_path: Path, winner: str
) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    intent = commit_resume_intent(setup, execution_id, reservation_id)
    receipt = FakeSideEffects(setup).resume_thread(intent)
    setup.close()
    winner_has_lock = threading.Event()
    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def run_recovery(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                _require_no_active_transaction(connection)
                with _test_service(connection).lifecycle_lease(reservation_id) as lease:
                    winner_has_lock.set()
                    lease.record_recovery(
                        session_id,
                        "LAUNCH_RESERVATION",
                        reservation_id,
                        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                        None,
                        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                    )
            else:
                winner_has_lock.wait()
                record_recovery(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    reservation_id,
                    "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
            outcome = "recovery"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "recovery-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    def run_receipt(first: bool) -> None:
        connection = _connect(db_path)
        try:
            if first:
                _require_no_active_transaction(connection)
                with _test_service(connection).lifecycle_lease(reservation_id) as lease:
                    winner_has_lock.set()
                    lease.bind_execution(execution_id)
                    lease.record_post_resume_evidence(execution_id, receipt)
            else:
                winner_has_lock.wait()
                record_post_resume_evidence(connection, execution_id, receipt)
            outcome = "receipt"
        except (ValueError, sqlite3.IntegrityError):
            outcome = "receipt-rejected"
        with outcomes_lock:
            outcomes.append(outcome)
        connection.close()

    threads = [
        threading.Thread(
            target=_inherit_harness_thread(run_recovery, winner == "recovery")
        ),
        threading.Thread(
            target=_inherit_harness_thread(run_receipt, winner == "receipt")
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    verify = _connect(db_path)
    if winner == "recovery":
        assert sorted(outcomes) == ["receipt-rejected", "recovery"]
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == ("MANUAL_REVIEW",)
        assert verify.execute(
            "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    else:
        assert sorted(outcomes) == ["receipt", "recovery-rejected"]
        assert verify.execute(
            "SELECT reservation_state FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == ("PROCESS_CREATED",)
        assert verify.execute(
            "SELECT phase, post_resume_json IS NOT NULL, cleanup_json IS NOT NULL "
            "FROM launch_executions WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == ("RESUME_RECORDED", 1, 1)
    verify.close()


def test_process_receipt_cannot_persist_after_process_recovery(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = _construct_provider_and_commit_process_intent(
        connection, reservation_id
    )
    process_receipt = FakeSideEffects(connection).create_process(process_intent)
    assert type(process_receipt) is FakeProcessCreationReceipt
    record_recovery(
        connection,
        session_id,
        "LAUNCH_RESERVATION",
        reservation_id,
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    with pytest.raises(ValueError, match="PROCESS_INTENT_COMMITTED"):
        record_execution(connection, reservation_id, process_receipt)
    assert connection.execute("SELECT count(*) FROM launch_executions").fetchone() == (
        0,
    )
    _consume_capability_for_test(process_receipt)
    connection.close()


def test_resume_boundary_requires_pre_resume_and_receipt(db_path: Path) -> None:
    connection = _connect(db_path)
    hooks = FakeSideEffects(connection)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    application_release, authority_policy = connection.execute(
        "SELECT application_release_version, authority_policy_version "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone()
    execution_id = _execution_id(reservation_id, application_release, authority_policy)

    with pytest.raises(ValueError, match="unknown execution"):
        hooks.resume_thread(
            commit_resume_intent(connection, execution_id, reservation_id)
        )

    execution_id = _record_successful_process(connection, reservation_id)
    with pytest.raises(TypeError, match="fake resume receipt"):
        record_post_resume_evidence(connection, execution_id, None)  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(
            connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
    assert connection.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("PRE_RESUME_READY",)
    connection.close()


def test_resume_intent_race_grants_exactly_one_hook_authority(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    attempt_id = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, attempt_id)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    setup.close()

    barrier = threading.Barrier(2)
    results: list[str] = []
    result_lock = threading.Lock()
    events: list[str] = []
    event_lock = threading.Lock()

    def worker() -> None:
        connection = _connect(db_path)
        hooks = FakeSideEffects(connection, events, event_lock)
        barrier.wait()
        try:
            intent = commit_resume_intent(connection, execution_id, reservation_id)
            hooks.resume_thread(intent)
            outcome = "winner"
        except ValueError:
            outcome = "loser"
        with result_lock:
            results.append(outcome)
        connection.close()

    threads = [
        threading.Thread(target=_inherit_harness_thread(worker)) for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["loser", "winner"]
    assert events == ["resume-intent-committed", "resume-thread"]
    verify = _connect(db_path)
    assert verify.execute(
        "SELECT phase, resume_intent_json IS NOT NULL, "
        "resume_intent_digest IS NOT NULL, resume_intent_committed_at_utc "
        "FROM launch_executions WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", 1, 1, RESUME_INTENT_TIMESTAMP)
    with pytest.raises(ValueError, match="PRE_RESUME_READY"):
        commit_resume_intent(verify, execution_id, reservation_id)
    verify.close()


@pytest.mark.parametrize("invoke_resume_thread", [False, True])
def test_crash_around_resume_leaves_same_unretryable_intent_state(
    db_path: Path, invoke_resume_thread: bool
) -> None:
    connection = _connect(db_path)
    hooks = FakeSideEffects(connection)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    if invoke_resume_thread:
        hooks.resume_thread(intent)
    connection.close()
    _consume_capability_for_test(intent)

    recovered = _connect(db_path)
    assert recovered.execute(
        "SELECT phase, resume_intent_json, resume_intent_digest, "
        "post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == (
        "RESUME_INTENT_COMMITTED",
        intent.intent_json,
        intent.intent_digest,
        None,
        None,
    )
    assert recovered.execute(
        "SELECT reservation_state FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone() == ("PROCESS_CREATED",)
    with pytest.raises(sqlite3.IntegrityError):
        record_terminal(recovered, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST)
    with pytest.raises(ValueError, match="PRE_RESUME_READY"):
        commit_resume_intent(recovered, execution_id, reservation_id)
    with pytest.raises(ValueError, match="already consumed|not issued"):
        FakeSideEffects(recovered).resume_thread(intent)
    with pytest.raises(TypeError, match="opaque fake resume intent"):
        FakeSideEffects(recovered).resume_thread(execution_id)  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            recovered,
            session_id,
            "ATTEMPT",
            attempt_id,
            "RECORD_ATTEMPT_AMBIGUITY",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )

    second_attempt = allocate_attempt(recovered, session_id)
    with pytest.raises(sqlite3.IntegrityError, match="claim admission policy rejected"):
        commit_claim(recovered, second_attempt)
    assert recovered.execute(
        "SELECT count(*) FROM provider_call_claims"
    ).fetchone() == (1,)
    assert recovered.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        0,
    )
    recovered.close()


def test_resume_hook_failure_returns_no_receipt_and_consumes_permit(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    hooks = FakeSideEffects(connection)
    with pytest.raises(RuntimeError, match="modeled ResumeThread failure"):
        hooks.resume_thread(intent, fail=True)
    with pytest.raises(ValueError, match="already consumed"):
        hooks.resume_thread(intent)
    assert connection.execute(
        "SELECT phase, post_resume_json, post_resume_digest FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    connection.close()


def test_resume_receipt_requires_adapter_provenance_and_one_shot_permit(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    receipt = FakeSideEffects(connection).resume_thread(intent)

    reconstructed = _forged_capability(
        type(receipt),
        execution_id=receipt.execution_id,
        reservation_id=receipt.reservation_id,
        resume_intent_digest=receipt.resume_intent_digest,
        result_json=receipt.result_json,
        result_digest=receipt.result_digest,
        _issuer=object(),
        _permit=object(),
    )
    for fabricated in (
        reconstructed,
        replace(receipt),
        replace(receipt, result_digest=_digest(b"replacement")),
    ):
        with pytest.raises((TypeError, ValueError)):
            record_post_resume_evidence(connection, execution_id, fabricated)
    with _mutated_frozen_object_for_test(receipt, _issuer=object()):
        with pytest.raises(TypeError, match="issuer"):
            record_post_resume_evidence(connection, execution_id, receipt)

    record_post_resume_evidence(connection, execution_id, receipt)
    _assert_capability_consumed(receipt)
    with pytest.raises(ValueError, match="already consumed|not issued"):
        record_post_resume_evidence(connection, execution_id, receipt)
    connection.close()


def test_resume_receipt_survives_transient_database_rollback(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    receipt = FakeSideEffects(connection).resume_thread(intent)
    connection.execute(
        """
        CREATE TRIGGER fail_resume_persistence_for_test
        BEFORE UPDATE OF phase ON launch_executions
        WHEN NEW.phase = 'RESUME_RECORDED'
        BEGIN
            SELECT RAISE(ABORT, 'transient resume persistence failure');
        END
        """
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="transient resume"):
        record_post_resume_evidence(connection, execution_id, receipt)
    _assert_capability_available(receipt)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)

    connection.execute("DROP TRIGGER fail_resume_persistence_for_test")
    connection.commit()
    record_post_resume_evidence(connection, execution_id, receipt)
    _assert_capability_consumed(receipt)
    connection.close()


@pytest.mark.parametrize(
    "invalid_receipt",
    [
        "failed-result",
        "error-result",
        "unknown-result",
        "wrong-schema",
        "string-schema",
        "wrong-execution",
        "wrong-intent",
        "extra-field",
        "missing-field",
        "noncanonical-bytes",
        "wrong-digest",
    ],
)
def test_post_resume_evidence_requires_exact_canonical_success_receipt(
    db_path: Path, invalid_receipt: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent = commit_resume_intent(connection, execution_id, reservation_id)
    valid = FakeSideEffects(connection).resume_thread(intent)
    envelope: dict[str, object] = json.loads(valid.result_json)
    receipt_execution = execution_id
    receipt_intent_digest = intent.intent_digest
    if invalid_receipt == "failed-result":
        envelope["resume_result"] = "FAILED"
    elif invalid_receipt == "error-result":
        envelope["resume_result"] = "ERROR"
    elif invalid_receipt == "unknown-result":
        envelope["resume_result"] = "UNKNOWN"
    elif invalid_receipt == "wrong-schema":
        envelope["schema"] = 2
    elif invalid_receipt == "string-schema":
        envelope["schema"] = "1"
    elif invalid_receipt == "wrong-execution":
        receipt_execution = str(uuid.UUID(int=0))
    elif invalid_receipt == "wrong-intent":
        receipt_intent_digest = _digest(b"wrong-intent")
    elif invalid_receipt == "extra-field":
        envelope["extra"] = True
    elif invalid_receipt == "missing-field":
        del envelope["resume_result"]
    result_json = _json(envelope)
    if invalid_receipt == "noncanonical-bytes":
        result_json = json.dumps(envelope, indent=2).encode("utf-8")
    result_digest = _digest(result_json)
    if invalid_receipt == "wrong-digest":
        result_digest = _digest(b"wrong-result")
    changes = {
        "execution_id": receipt_execution,
        "resume_intent_digest": receipt_intent_digest,
        "result_json": result_json,
        "result_digest": result_digest,
    }
    with _mutated_frozen_object_for_test(valid, **changes):
        with pytest.raises(ValueError):
            record_post_resume_evidence(connection, execution_id, valid)
    assert connection.execute(
        "SELECT phase, post_resume_json, cleanup_json FROM launch_executions "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    ).fetchone() == ("RESUME_INTENT_COMMITTED", None, None)
    _assert_capability_available(valid)
    _assert_capability_available(valid)
    record_post_resume_evidence(connection, execution_id, valid)
    _assert_capability_consumed(valid)
    connection.close()


def test_fake_resume_receipt_cannot_be_reused_for_another_execution(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_ids = [
        create_session(connection, _request("2026-01-01")),
        create_session(connection, _request("2026-01-02")),
    ]
    attempts: list[str] = []
    reservations: list[str] = []
    for session_id in session_ids:
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservations.append(reserve_launch(connection, claim_id))
        attempts.append(attempt_id)

    executions = [
        _record_successful_process(connection, reservation)
        for reservation in reservations
    ]
    hooks = FakeSideEffects(connection)
    intents = [
        commit_resume_intent(connection, execution, reservation)
        for execution, reservation in zip(executions, reservations, strict=True)
    ]
    reused_intent = replace(
        intents[0],
        execution_id=executions[1],
        reservation_id=str(reservations[1]),
    )
    with pytest.raises(ValueError, match="registry binding mismatch"):
        hooks.resume_thread(reused_intent)
    receipt = hooks.resume_thread(intents[0])
    with pytest.raises(ValueError, match="another execution"):
        record_post_resume_evidence(connection, executions[1], receipt)
    assert connection.execute(
        "SELECT phase FROM launch_executions WHERE launch_execution_id = ?",
        (executions[1],),
    ).fetchone() == ("RESUME_INTENT_COMMITTED",)
    record_post_resume_evidence(connection, executions[0], receipt)
    second_receipt = hooks.resume_thread(intents[1])
    record_post_resume_evidence(connection, executions[1], second_receipt)
    assert attempts
    connection.close()


def test_launch_execution_evidence_is_append_only(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    post_resume, post_digest = _evidence("post-resume-test")
    cleanup, cleanup_digest = _evidence("cleanup-test")
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_INTENT_COMMITTED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET resume_intent_json = ?, "
            "resume_intent_digest = ?, resume_intent_committed_at_utc = ? "
            "WHERE launch_execution_id = ?",
            (
                intent_json,
                _digest(intent_json),
                RESUME_INTENT_TIMESTAMP,
                execution_id,
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET post_resume_json = ?, "
            "post_resume_digest = ? WHERE launch_execution_id = ?",
            (post_resume, post_digest, execution_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
            "post_resume_json = ? WHERE launch_execution_id = ?",
            (post_resume, execution_id),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
            "post_resume_json = ?, post_resume_digest = ? "
            "WHERE launch_execution_id = ?",
            (post_resume, _digest(b"wrong-post-digest"), execution_id),
        )

    resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
    reconstructed_intent = _forged_capability(
        type(resume_intent),
        execution_id=execution_id,
        reservation_id=str(reservation_id),
        intent_json=resume_intent.intent_json,
        intent_digest=resume_intent.intent_digest,
        _issuer=object(),
        _permit=object(),
    )
    with pytest.raises((TypeError, ValueError), match="invalid|not issued"):
        FakeSideEffects(connection).resume_thread(reconstructed_intent)
    with pytest.raises(ValueError, match="not issued"):
        FakeSideEffects(connection).resume_thread(replace(resume_intent))
    for sql, params in (
        (
            "UPDATE launch_executions SET resume_intent_json = ? "
            "WHERE launch_execution_id = ?",
            (_json({"replacement": True}), execution_id),
        ),
        (
            "UPDATE launch_executions SET resume_intent_digest = ? "
            "WHERE launch_execution_id = ?",
            (_digest(b"replacement"), execution_id),
        ),
        (
            "UPDATE launch_executions SET resume_intent_committed_at_utc = ? "
            "WHERE launch_execution_id = ?",
            (MANUAL_REVIEW_TIMESTAMP, execution_id),
        ),
        (
            "UPDATE launch_executions SET resume_intent_json = NULL, "
            "resume_intent_digest = NULL, resume_intent_committed_at_utc = NULL "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, params)
    invalid_receipt_json = _json(
        {
            "execution_id": execution_id,
            "resume_intent_digest": resume_intent.intent_digest.hex(),
            "resume_result": "FAILED",
            "schema": 1,
        }
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET phase = 'RESUME_RECORDED', "
            "post_resume_json = ?, post_resume_digest = ?, cleanup_json = ?, "
            "cleanup_digest = ? WHERE launch_execution_id = ?",
            (
                invalid_receipt_json,
                _digest(invalid_receipt_json),
                cleanup,
                cleanup_digest,
                execution_id,
            ),
        )
    resume_receipt = FakeSideEffects(connection).resume_thread(resume_intent)
    record_post_resume_evidence(connection, execution_id, resume_receipt)
    for sql, params in (
        (
            "UPDATE launch_executions SET post_resume_json = ? "
            "WHERE launch_execution_id = ?",
            (post_resume, execution_id),
        ),
        (
            "UPDATE launch_executions SET post_resume_digest = ? "
            "WHERE launch_execution_id = ?",
            (post_digest, execution_id),
        ),
        (
            "UPDATE launch_executions SET post_resume_json = NULL "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ),
        (
            "UPDATE launch_executions SET cleanup_json = ? "
            "WHERE launch_execution_id = ?",
            (cleanup, execution_id),
        ),
        (
            "UPDATE launch_executions SET cleanup_digest = ? "
            "WHERE launch_execution_id = ?",
            (cleanup_digest, execution_id),
        ),
        (
            "UPDATE launch_executions SET cleanup_digest = NULL "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, params)

    record_terminal(connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE launch_executions SET post_resume_json = ? "
            "WHERE launch_execution_id = ?",
            (post_resume, execution_id),
        )
    connection.close()


def test_direct_sql_state_projection_requires_normalized_durable_facts(
    db_path: Path,
) -> None:
    connection = _connect(db_path)

    def assert_rejected(sql: str, params: tuple[object, ...]) -> None:
        before = _database_rows(connection)
        with pytest.raises(sqlite3.IntegrityError, match="projection fact"):
            connection.execute(sql, params)
        assert _database_rows(connection) == before

    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    assert_rejected(
        "UPDATE attempts SET state = 'CLAIM_COMMITTED' WHERE attempt_id = ?",
        (attempt_id,),
    )

    claim_id = commit_claim(connection, attempt_id)
    assert_rejected(
        "UPDATE attempts SET state = 'LAUNCH_RESERVED' WHERE attempt_id = ?",
        (attempt_id,),
    )

    reservation_id = reserve_launch(connection, claim_id)
    assert_rejected(
        "UPDATE launch_reservations SET reservation_state = 'MANUAL_REVIEW', "
        "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
        (MANUAL_REVIEW_TIMESTAMP, str(reservation_id)),
    )

    process_intent = _construct_provider_and_commit_process_intent(
        connection, reservation_id
    )
    assert_rejected(
        "UPDATE launch_reservations SET reservation_state = 'PROCESS_CREATED', "
        "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
        (PROCESS_CREATED_TIMESTAMP, str(reservation_id)),
    )
    assert_rejected(
        "UPDATE launch_reservations SET reservation_state = "
        "'PROCESS_CREATION_FAILED', outcome_recorded_at_utc = ? "
        "WHERE launch_reservation_id = ?",
        (PROCESS_FAILURE_TIMESTAMP, str(reservation_id)),
    )
    assert_rejected(
        "UPDATE launch_reservations SET reservation_state = 'MANUAL_REVIEW', "
        "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
        (MANUAL_REVIEW_TIMESTAMP, str(reservation_id)),
    )

    process_result = FakeSideEffects(connection).create_process(process_intent)
    assert type(process_result) is FakeProcessCreationReceipt
    execution_id = record_execution(connection, reservation_id, process_result)
    assert_rejected(
        "UPDATE launch_reservations SET reservation_state = 'MANUAL_REVIEW' "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    )
    _resume_and_persist(connection, execution_id, reservation_id)
    assert_rejected(
        "UPDATE launch_executions SET phase = 'TERMINAL_RECORDED' "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    )
    assert_rejected(
        "UPDATE launch_reservations SET reservation_state = 'TERMINAL_RECORDED' "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    )
    assert_rejected(
        "UPDATE attempts SET state = 'TERMINAL_RECORDED' WHERE attempt_id = ?",
        (attempt_id,),
    )
    assert_rejected(
        "UPDATE launch_executions SET phase = 'POST_RESUME_AMBIGUOUS' "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    )
    assert_rejected(
        "UPDATE attempts SET state = 'LAUNCH_MAY_HAVE_OCCURRED' WHERE attempt_id = ?",
        (attempt_id,),
    )

    record_recovery(
        connection,
        session_id,
        "ATTEMPT",
        attempt_id,
        "RECORD_ATTEMPT_AMBIGUITY",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    connection.execute(
        "UPDATE launch_executions SET phase = 'POST_RESUME_AMBIGUOUS' "
        "WHERE launch_execution_id = ?",
        (execution_id,),
    )
    connection.execute(
        "UPDATE attempts SET state = 'LAUNCH_MAY_HAVE_OCCURRED' WHERE attempt_id = ?",
        (attempt_id,),
    )
    record_terminal(
        connection,
        reservation_id,
        "AMBIGUOUS",
        "MAY_HAVE_OCCURRED",
        snapshot_digest=None,
    )

    selected_session = create_session(connection, _request("2026-01-02"))
    selected_attempt = allocate_attempt(connection, selected_session)
    selected_claim = commit_claim(connection, selected_attempt)
    selected_reservation = reserve_launch(connection, selected_claim)
    selected_execution = _record_successful_process(connection, selected_reservation)
    _resume_and_persist(connection, selected_execution, selected_reservation)
    selected_terminal = record_terminal(
        connection, selected_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    assert_rejected(
        "UPDATE attempts SET state = 'SUCCESS_SELECTED' WHERE attempt_id = ?",
        (selected_attempt,),
    )
    assert_rejected(
        "UPDATE sessions SET state = 'SUCCESS_SELECTED' WHERE session_id = ?",
        (selected_session,),
    )
    select_terminal(connection, selected_session, selected_terminal)
    assert_rejected(
        "UPDATE attempts SET state = 'CLOSED' WHERE attempt_id = ?",
        (selected_attempt,),
    )
    assert_rejected(
        "UPDATE launch_executions SET phase = 'CLOSED' WHERE launch_execution_id = ?",
        (selected_execution,),
    )
    connection.execute(
        "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, close_reason = ? "
        "WHERE session_id = ?",
        (CLOSE_TIMESTAMP, "selected-close", selected_session),
    )
    connection.execute(
        "UPDATE launch_executions SET phase = 'CLOSED' WHERE launch_execution_id = ?",
        (selected_execution,),
    )
    connection.execute(
        "UPDATE attempts SET state = 'CLOSED' WHERE attempt_id = ?",
        (selected_attempt,),
    )
    assert connection.execute(
        "SELECT s.state, a.state FROM sessions s "
        "JOIN attempts a ON a.session_id = s.session_id WHERE s.session_id = ?",
        (selected_session,),
    ).fetchone() == ("CLOSED", "CLOSED")
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    connection.close()


def test_direct_sql_child_admission_requires_documented_predecessor(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    request_json, request_digest = connection.execute(
        "SELECT request_json, request_digest FROM attempts WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()
    claim_id = _insert_claim_row_for_test(
        connection, attempt_id, request_json, request_digest
    )

    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_reservation_row_for_test(connection, claim_id, request_digest)
    assert _database_rows(connection) == before

    connection.execute(
        "UPDATE attempts SET state = 'CLAIM_COMMITTED' WHERE attempt_id = ?",
        (attempt_id,),
    )
    reservation_id = _insert_reservation_row_for_test(
        connection, claim_id, request_digest
    )
    connection.execute(
        "UPDATE attempts SET state = 'LAUNCH_RESERVED' WHERE attempt_id = ?",
        (attempt_id,),
    )

    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_execution_row_for_test(connection, reservation_id)
    assert _database_rows(connection) == before
    with pytest.raises(sqlite3.IntegrityError):
        _insert_terminal_row_for_test(
            connection,
            reservation_id,
            request_digest,
            "CLOSED",
            "MAY_HAVE_OCCURRED",
        )
    assert _database_rows(connection) == before
    selection_evidence, selection_digest = _evidence("impossible-selection")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO session_selections (
                selection_id, session_id, terminal_id, selection_schema,
                selection_policy_version, snapshot_digest,
                selection_evidence_json, selection_evidence_digest,
                selected_at_utc
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                "impossible-selection-id",
                session_id,
                "missing-terminal-id",
                SELECTION_POLICY,
                _digest(b"missing-snapshot"),
                selection_evidence,
                selection_digest,
                SELECTION_TIMESTAMP,
            ),
        )
    assert _database_rows(connection) == before
    with pytest.raises(sqlite3.IntegrityError):
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "CLOSE_SESSION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize("fabricated_state", ["TERMINAL_RECORDED", "SUCCESS_SELECTED"])
def test_close_session_rejects_fabricated_terminal_looking_attempt_lineage(
    db_path: Path, fabricated_state: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    connection.execute("DROP TRIGGER attempts_state_guard")
    connection.execute(
        "UPDATE attempts SET state = ? WHERE attempt_id = ?",
        (fabricated_state, attempt_id),
    )
    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="recovery action matrix"):
        record_recovery(
            connection,
            session_id,
            "SESSION",
            session_id,
            "CLOSE_SESSION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT state, next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == ("OPEN", 0)
    connection.close()


class _OrdinalInt(int):
    pass


@pytest.mark.parametrize("operation", ["attempt", "recovery"])
@pytest.mark.parametrize(
    "invalid_ordinal",
    [False, True, 0.0, 1.0, "0", _OrdinalInt(0), -1],
    ids=["false", "true", "float-zero", "float-one", "string", "subclass", "negative"],
)
def test_caller_ordinal_overrides_require_exact_non_negative_int(
    db_path: Path, operation: str, invalid_ordinal: object
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    before = _database_rows(connection)
    with pytest.raises(ValueError, match="exact non-negative int"):
        if operation == "attempt":
            allocate_attempt(connection, session_id, ordinal=invalid_ordinal)  # type: ignore[arg-type]
        else:
            record_recovery(
                connection,
                session_id,
                "SESSION",
                session_id,
                "ACKNOWLEDGE_RESTORE",
                ordinal=invalid_ordinal,  # type: ignore[arg-type]
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT next_attempt_ordinal, next_recovery_ordinal "
        "FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (0, 0)
    connection.close()


def test_exact_integer_ordinal_overrides_accept_zero_and_current_positive_value(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    attempt_zero = allocate_attempt(connection, create_session(connection), ordinal=0)
    attempt_session = connection.execute(
        "SELECT session_id FROM attempts WHERE attempt_id = ?", (attempt_zero,)
    ).fetchone()[0]
    attempt_one = allocate_attempt(connection, attempt_session, ordinal=1)
    assert connection.execute(
        "SELECT ordinal FROM attempts WHERE attempt_id IN (?, ?) ORDER BY ordinal",
        (attempt_zero, attempt_one),
    ).fetchall() == [(0,), (1,)]

    recovery_session = create_session(connection, _request("2026-01-02"))
    first_recovery = record_recovery(
        connection,
        recovery_session,
        "SESSION",
        recovery_session,
        "ACKNOWLEDGE_RESTORE",
        ordinal=0,
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    second_recovery = record_recovery(
        connection,
        recovery_session,
        "SESSION",
        recovery_session,
        "CLOSE_SESSION",
        ordinal=1,
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    assert connection.execute(
        "SELECT recovery_ordinal FROM manual_recoveries "
        "WHERE recovery_id IN (?, ?) ORDER BY recovery_ordinal",
        (first_recovery, second_recovery),
    ).fetchall() == [(0,), (1,)]
    connection.close()


@pytest.mark.parametrize(
    "stale_action",
    [
        "RECORD_ATTEMPT_AMBIGUITY",
        "RECORD_CLAIM_AMBIGUITY",
        "CLASSIFY_LAUNCH_RESERVATION",
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
        "CLASSIFY_PRE_RESUME_READY",
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
        "SELECT_COMMITTED_SUCCESS",
        "CLOSE_SESSION",
        "ACKNOWLEDGE_RESTORE",
    ],
)
def test_recovery_insert_requires_action_to_be_currently_actionable(
    db_path: Path, stale_action: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    process_intent: FakeProcessIntent | None = None

    if stale_action in {"CLOSE_SESSION", "ACKNOWLEDGE_RESTORE"}:
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
        terminal_id = record_terminal(
            connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
        _insert_selection_row_for_test(connection, session_id, terminal_id)
        target_kind, target_id = "SESSION", session_id
    else:
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        target_kind = "LAUNCH_RESERVATION"
        target_id = str(reservation_id)

        if stale_action == "CLASSIFY_LAUNCH_RESERVATION":
            process_intent = _construct_provider_and_commit_process_intent(
                connection, reservation_id
            )
        elif stale_action == "CLASSIFY_PROCESS_OUTCOME_UNKNOWN":
            process_intent = _construct_provider_and_commit_process_intent(
                connection, reservation_id
            )
            _insert_execution_row_for_test(connection, reservation_id)
        else:
            execution_id = _record_successful_process(connection, reservation_id)
            if stale_action == "CLASSIFY_PRE_RESUME_READY":
                resume_intent = commit_resume_intent(
                    connection, execution_id, reservation_id
                )
                _consume_capability_for_test(resume_intent)
            elif stale_action == "CLASSIFY_RESUME_OUTCOME_UNKNOWN":
                resume_intent = commit_resume_intent(
                    connection, execution_id, reservation_id
                )
                receipt = FakeSideEffects(connection).resume_thread(resume_intent)
                record_post_resume_evidence(connection, execution_id, receipt)
            else:
                assert stale_action in {
                    "RECORD_ATTEMPT_AMBIGUITY",
                    "RECORD_CLAIM_AMBIGUITY",
                    "SELECT_COMMITTED_SUCCESS",
                }
                _resume_and_persist(connection, execution_id, reservation_id)
                terminal_id = _insert_terminal_row_for_test(
                    connection,
                    reservation_id,
                    connection.execute(
                        "SELECT request_digest FROM attempts WHERE attempt_id = ?",
                        (attempt_id,),
                    ).fetchone()[0],
                    "AMBIGUOUS"
                    if stale_action != "SELECT_COMMITTED_SUCCESS"
                    else "SUCCEEDED",
                    "MAY_HAVE_OCCURRED"
                    if stale_action != "SELECT_COMMITTED_SUCCESS"
                    else "CONFIRMED",
                )
                if stale_action == "RECORD_ATTEMPT_AMBIGUITY":
                    target_kind, target_id = "ATTEMPT", attempt_id
                elif stale_action == "RECORD_CLAIM_AMBIGUITY":
                    target_kind, target_id = "CLAIM", claim_id
                else:
                    connection.execute(
                        "UPDATE launch_executions SET phase = 'TERMINAL_RECORDED' "
                        "WHERE launch_execution_id = ?",
                        (execution_id,),
                    )
                    connection.execute(
                        "UPDATE launch_reservations SET reservation_state = "
                        "'TERMINAL_RECORDED' WHERE launch_reservation_id = ?",
                        (str(reservation_id),),
                    )
                    connection.execute(
                        "UPDATE attempts SET state = 'TERMINAL_RECORDED' "
                        "WHERE attempt_id = ?",
                        (attempt_id,),
                    )
                    _insert_selection_row_for_test(connection, session_id, terminal_id)
                    target_kind, target_id = "TERMINAL", terminal_id

    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="recovery action matrix"):
        _insert_recovery_fact_for_test(
            connection,
            session_id,
            target_kind,
            target_id,
            stale_action,
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == (0,)
    if process_intent is not None:
        _consume_capability_for_test(process_intent)
    connection.close()


@pytest.mark.parametrize(
    "stale_case",
    [
        "close-new-attempt",
        "process-unknown-new-execution",
        "pre-resume-new-intent",
        "resume-unknown-new-receipt",
    ],
)
def test_recovery_projection_rechecks_mutable_current_eligibility(
    db_path: Path, stale_case: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)

    if stale_case == "close-new-attempt":
        target_id = session_id
        _insert_recovery_fact_for_test(
            connection,
            session_id,
            "SESSION",
            target_id,
            "CLOSE_SESSION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        attempt_id = allocate_attempt(connection, session_id)
        update_sql = (
            "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, "
            "close_reason = ? WHERE session_id = ?"
        )
        update_params: tuple[object, ...] = (
            CLOSE_TIMESTAMP,
            "stale-close-recovery",
            session_id,
        )
    else:
        attempt_id = allocate_attempt(connection, session_id)
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        target_id = str(reservation_id)
        if stale_case == "process-unknown-new-execution":
            process_intent = _construct_provider_and_commit_process_intent(
                connection, reservation_id
            )
            _insert_recovery_fact_for_test(
                connection,
                session_id,
                "LAUNCH_RESERVATION",
                target_id,
                "CLASSIFY_PROCESS_OUTCOME_UNKNOWN",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
            _insert_execution_row_for_test(connection, target_id)
            _consume_capability_for_test(process_intent)
            update_sql = (
                "UPDATE launch_reservations SET reservation_state = "
                "'MANUAL_REVIEW', outcome_recorded_at_utc = ? "
                "WHERE launch_reservation_id = ?"
            )
            update_params = (MANUAL_REVIEW_TIMESTAMP, target_id)
        else:
            execution_id = _record_successful_process(connection, reservation_id)
            if stale_case == "pre-resume-new-intent":
                _insert_recovery_fact_for_test(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    target_id,
                    "CLASSIFY_PRE_RESUME_READY",
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
                resume_intent = commit_resume_intent(
                    connection, execution_id, reservation_id
                )
                _consume_capability_for_test(resume_intent)
            else:
                assert stale_case == "resume-unknown-new-receipt"
                resume_intent = commit_resume_intent(
                    connection, execution_id, reservation_id
                )
                _insert_recovery_fact_for_test(
                    connection,
                    session_id,
                    "LAUNCH_RESERVATION",
                    target_id,
                    "CLASSIFY_RESUME_OUTCOME_UNKNOWN",
                    operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                    operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
                )
                resume_receipt = FakeSideEffects(connection).resume_thread(
                    resume_intent
                )
                record_post_resume_evidence(connection, execution_id, resume_receipt)
            update_sql = (
                "UPDATE launch_reservations SET reservation_state = "
                "'MANUAL_REVIEW' WHERE launch_reservation_id = ?"
            )
            update_params = (target_id,)

    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="projection fact"):
        connection.execute(update_sql, update_params)
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT state, next_recovery_ordinal FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone() == ("OPEN", 1)
    assert connection.execute(
        "SELECT state FROM attempts WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()[0] in {
        "ALLOCATED",
        "LAUNCH_RESERVED",
    }
    connection.close()


@pytest.mark.parametrize("projection", ["attempt", "execution"])
def test_ambiguity_recovery_projection_rechecks_current_terminal_absence(
    db_path: Path, projection: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    _resume_and_persist(connection, execution_id, reservation_id)
    _insert_recovery_fact_for_test(
        connection,
        session_id,
        "ATTEMPT",
        attempt_id,
        "RECORD_ATTEMPT_AMBIGUITY",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    request_digest = connection.execute(
        "SELECT request_digest FROM attempts WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()[0]
    _insert_terminal_row_for_test(
        connection,
        reservation_id,
        request_digest,
        "AMBIGUOUS",
        "MAY_HAVE_OCCURRED",
    )

    mutation = (
        (
            "UPDATE attempts SET state = 'LAUNCH_MAY_HAVE_OCCURRED' "
            "WHERE attempt_id = ?",
            (attempt_id,),
        )
        if projection == "attempt"
        else (
            "UPDATE launch_executions SET phase = 'POST_RESUME_AMBIGUOUS' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    )
    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="projection fact"):
        connection.execute(*mutation)
    assert _database_rows(connection) == before
    connection.close()


def test_process_intent_projection_requires_current_active_parent_lineage(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    request_digest = connection.execute(
        "SELECT request_digest FROM attempts WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()[0]
    reservation_id = _insert_reservation_row_for_test(
        connection, claim_id, request_digest
    )
    intent_json = _process_intent_json(
        reservation_id, request_digest, POLICY, CLAIM_POLICY
    )

    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="projection fact"):
        connection.execute(
            "UPDATE launch_reservations SET reservation_state = "
            "'PROCESS_INTENT_COMMITTED', process_intent_json = ?, "
            "process_intent_digest = ?, process_intent_committed_at_utc = ? "
            "WHERE launch_reservation_id = ?",
            (
                intent_json,
                _digest(intent_json),
                PROCESS_INTENT_TIMESTAMP,
                reservation_id,
            ),
        )
    assert _database_rows(connection) == before
    assert connection.execute(
        "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
    ).fetchone() == ("CLAIM_COMMITTED",)
    connection.close()


@pytest.mark.parametrize(
    "invalid_boundary",
    [
        "attempt",
        "claim",
        "reservation",
        "execution",
        "terminal",
        "selection",
        "recovery",
    ],
)
def test_invalid_lifecycle_transitions_are_rejected(
    db_path: Path, invalid_boundary: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)

    if invalid_boundary == "attempt":
        mutation = (
            "UPDATE attempts SET state = 'SUCCESS_SELECTED' WHERE attempt_id = ?",
            (attempt_id,),
        )
    elif invalid_boundary == "claim":
        claim_id = commit_claim(connection, attempt_id)
        mutation = (
            "UPDATE provider_call_claims SET state = 'INVALID' WHERE claim_id = ?",
            (claim_id,),
        )
    elif invalid_boundary == "reservation":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        mutation = (
            "UPDATE launch_reservations SET reservation_state = "
            "'TERMINAL_RECORDED' WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        )
    elif invalid_boundary == "execution":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        mutation = (
            "UPDATE launch_executions SET phase = 'TERMINAL_RECORDED' "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        )
    elif invalid_boundary == "terminal":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
        terminal_id = record_terminal(
            connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
        mutation = (
            "UPDATE terminals SET terminal_state = 'FAILED' WHERE terminal_id = ?",
            (terminal_id,),
        )
    elif invalid_boundary == "selection":
        claim_id = commit_claim(connection, attempt_id)
        reservation_id = reserve_launch(connection, claim_id)
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
        terminal_id = record_terminal(
            connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
        )
        selection_id = select_terminal(connection, session_id, terminal_id)
        mutation = (
            "UPDATE session_selections SET selection_policy_version = 'bad' "
            "WHERE selection_id = ?",
            (selection_id,),
        )
    else:
        mutation = None

    if mutation is not None:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(*mutation)
    else:
        with pytest.raises(sqlite3.IntegrityError):
            record_recovery(
                connection,
                session_id,
                "ATTEMPT",
                attempt_id,
                "RECORD_ATTEMPT_AMBIGUITY",
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
    connection.close()


def test_recovery_race_produces_consecutive_ordinals(db_path: Path) -> None:
    setup = _connect(db_path)
    session_id = create_session(setup)
    target_attempt = allocate_attempt(setup, session_id)
    claim_id = commit_claim(setup, target_attempt)
    reservation_id = reserve_launch(setup, claim_id)
    execution_id = _record_successful_process(setup, reservation_id)
    _resume_and_persist(setup, execution_id, reservation_id)
    setup.close()
    barrier = threading.Barrier(2)
    results: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(target_kind: str, target_id: str, action: str) -> None:
        connection = _connect(db_path)
        try:
            barrier.wait()
            recovery_id = record_recovery(
                connection,
                session_id,
                target_kind,
                target_id,
                action,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
            with lock:
                results.append(recovery_id)
        except BaseException as error:
            with lock:
                errors.append(error)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=_inherit_harness_thread(
                worker, "ATTEMPT", target_attempt, "RECORD_ATTEMPT_AMBIGUITY"
            )
        ),
        threading.Thread(
            target=_inherit_harness_thread(
                worker, "SESSION", session_id, "ACKNOWLEDGE_RESTORE"
            )
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(results) == 2
    connection = _connect(db_path)
    assert [
        row[0]
        for row in connection.execute(
            "SELECT recovery_ordinal FROM manual_recoveries ORDER BY recovery_ordinal"
        )
    ] == [0, 1]
    connection.close()


_AUTHORITY_TIMESTAMP_COLUMNS = {
    "authority_metadata": ("created_at_utc",),
    "schema_migrations": ("applied_at_utc",),
    "sessions": ("created_at_utc", "closed_at_utc"),
    "attempts": ("created_at_utc",),
    "provider_call_claims": ("committed_at_utc",),
    "launch_reservations": (
        "process_intent_committed_at_utc",
        "committed_at_utc",
        "outcome_recorded_at_utc",
    ),
    "launch_executions": ("resume_intent_committed_at_utc", "created_at_utc"),
    "terminals": ("recorded_at_utc",),
    "session_selections": ("selected_at_utc",),
    "manual_recoveries": ("created_at_utc",),
}

_INVALID_GREGORIAN_DATES = (
    "0000-01-01",
    "2026-00-01",
    "2026-13-01",
    "2026-01-00",
    "2026-02-29",
    "2026-02-30",
    "2024-02-30",
    "2026-04-31",
    "2026-06-31",
    "2026-09-31",
    "2026-11-31",
    "1900-02-29",
    "2100-02-29",
    "2200-02-29",
    "2300-02-29",
)
_VALID_GREGORIAN_REQUEST_WINDOWS = {
    "0001-01-01": ("0001-01-01", "0001-01-01", "0001-01-02"),
    "2024-02-29": ("2024-02-29", "2024-02-29", "2024-03-01"),
    "2000-02-29": ("2000-02-29", "2000-02-29", "2000-03-01"),
    "2400-02-29": ("2400-02-29", "2400-02-29", "2400-03-01"),
    "2026-01-31": ("2026-01-31", "2026-01-31", "2026-02-01"),
    "2026-04-30": ("2026-04-30", "2026-04-30", "2026-05-01"),
    "9999-12-31": ("9999-12-30", "9999-12-30", "9999-12-31"),
}
_SQLITE_DATE_TIME_PARSER_FUNCTIONS = (
    "strftime(",
    "date(",
    "datetime(",
    "julianday(",
    "unixepoch(",
)


def _gregorian_sql_predicate(value_sql: str) -> str:
    return " ".join(
        f"""
        CAST(substr({value_sql}, 6, 2) AS INTEGER) BETWEEN 1 AND 12
        AND CAST(substr({value_sql}, 9, 2) AS INTEGER) >= 1
        AND CAST(substr({value_sql}, 9, 2) AS INTEGER) <=
            CASE
                WHEN CAST(substr({value_sql}, 6, 2) AS INTEGER)
                    IN (1, 3, 5, 7, 8, 10, 12) THEN 31
                WHEN CAST(substr({value_sql}, 6, 2) AS INTEGER)
                    IN (4, 6, 9, 11) THEN 30
                WHEN CAST(substr({value_sql}, 6, 2) AS INTEGER) = 2 THEN
                    CASE
                        WHEN CAST(substr({value_sql}, 1, 4) AS INTEGER) % 400 = 0
                          OR (CAST(substr({value_sql}, 1, 4) AS INTEGER) % 4 = 0
                              AND CAST(substr({value_sql}, 1, 4) AS INTEGER) % 100 <> 0)
                        THEN 29
                        ELSE 28
                    END
                ELSE 0
            END
        """.split()
    )


@pytest.mark.parametrize(
    ("calendar_date", "accepted"),
    [
        *((calendar_date, False) for calendar_date in _INVALID_GREGORIAN_DATES),
        *((calendar_date, True) for calendar_date in _VALID_GREGORIAN_REQUEST_WINDOWS),
    ],
)
def test_gregorian_calendar_matrix_for_timestamp_v1_is_parser_independent(
    tmp_path: Path,
    calendar_date: str,
    accepted: bool,
) -> None:
    connection = _connect(tmp_path / "gregorian-timestamp.sqlite3")
    _install_schema(connection)
    timestamp = f"{calendar_date}T12:34:56Z"
    before = _database_rows(connection)
    if accepted:
        _insert_metadata(connection, created_at_utc=timestamp)
        assert connection.execute(
            "SELECT created_at_utc FROM authority_metadata"
        ).fetchone() == (timestamp,)
    else:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_metadata(connection, created_at_utc=timestamp)
        assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize(
    "field_name",
    (
        "request_window_start_date",
        "request_window_end_date",
        "target_session_date",
    ),
)
@pytest.mark.parametrize("calendar_date", _INVALID_GREGORIAN_DATES)
def test_gregorian_calendar_matrix_rejects_each_request_date_atomically(
    db_path: Path,
    field_name: str,
    calendar_date: str,
) -> None:
    connection = _connect(db_path)
    request = _request()
    request[field_name] = calendar_date
    request_bytes = _json(request)
    target_session_date = request["target_session_date"]
    before = _database_rows(connection)

    with pytest.raises(sqlite3.IntegrityError, match="date window is invalid"):
        _insert_session_row_for_test(
            connection,
            f"invalid-{field_name}-{calendar_date}",
            request_bytes,
            target_session_date=target_session_date,
        )

    assert _database_rows(connection) == before
    _assert_no_capture_authority_side_effects(connection)
    connection.close()


@pytest.mark.parametrize(
    ("calendar_date", "request_window"),
    _VALID_GREGORIAN_REQUEST_WINDOWS.items(),
)
def test_gregorian_calendar_matrix_accepts_canonical_request_dates(
    db_path: Path,
    calendar_date: str,
    request_window: tuple[str, str, str],
) -> None:
    connection = _connect(db_path)
    window_start, window_end, target_session_date = request_window
    assert calendar_date in request_window
    request = _request(target_session_date)
    request["request_window_start_date"] = window_start
    request["request_window_end_date"] = window_end
    request_bytes = _json(request)

    _insert_session_row_for_test(
        connection,
        f"valid-gregorian-request-{calendar_date}",
        request_bytes,
        target_session_date=target_session_date,
    )

    assert connection.execute(
        "SELECT target_session_date, request_json FROM sessions"
    ).fetchone() == (target_session_date, request_bytes)
    connection.close()


def test_invalid_gregorian_nullable_timestamp_update_is_atomic(db_path: Path) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    _insert_recovery_fact_for_test(
        connection,
        session_id,
        "SESSION",
        session_id,
        "CLOSE_SESSION",
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    before = _database_rows(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            UPDATE sessions
            SET state = 'CLOSED',
                closed_at_utc = '2026-02-30T00:06:00Z',
                close_reason = 'invalid-calendar-date'
            WHERE session_id = ?
            """,
            (session_id,),
        )

    assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize(
    "invalid_timestamp",
    [
        "2026-1-01T00:00:00Z",
        "2026-01-1T00:00:00Z",
        "2026-01-01 00:00:00Z",
        "2026-01-01t00:00:00Z",
        "2026-01-01T00:00:00z",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:00.0Z",
        "2026-01-01T00:00:00.000Z",
        "2026-01-01T24:00:00Z",
        "2026-01-01T23:60:00Z",
        "2026-01-01T23:59:60Z",
        "2026-02-29T00:00:00Z",
        "2026-02-30T00:00:00Z",
        "2026-00-01T00:00:00Z",
        "2026-13-01T00:00:00Z",
        "2026-01-00T00:00:00Z",
        "0000-01-01T00:00:00Z",
        "arbitrary text",
        " 2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z ",
    ],
)
def test_canonical_authority_timestamp_v1_rejects_malformed_direct_sql(
    tmp_path: Path, invalid_timestamp: str
) -> None:
    connection = _connect(tmp_path / "invalid-timestamp.sqlite3")
    _install_schema(connection)
    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_metadata(connection, created_at_utc=invalid_timestamp)
    assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize(
    "valid_timestamp",
    [
        "0001-01-01T00:00:00Z",
        "2024-02-29T23:59:59Z",
        TIMESTAMP,
        "9999-12-31T23:59:59Z",
    ],
)
def test_canonical_authority_timestamp_v1_accepts_supported_boundaries(
    tmp_path: Path, valid_timestamp: str
) -> None:
    connection = _connect(tmp_path / "valid-timestamp.sqlite3")
    _install_schema(connection)
    _insert_metadata(connection, created_at_utc=valid_timestamp)
    assert connection.execute(
        "SELECT created_at_utc FROM authority_metadata"
    ).fetchone() == (valid_timestamp,)
    connection.close()


def test_every_authority_timestamp_column_uses_timestamp_v1_sql_check(
    db_path: Path,
) -> None:
    connection = _connect(db_path)
    schema_source = SCHEMA_BYTES.decode("utf-8").lower()
    for parser_function in _SQLITE_DATE_TIME_PARSER_FUNCTIONS:
        assert parser_function not in schema_source

    checked_columns = 0
    for table, columns in _AUTHORITY_TIMESTAMP_COLUMNS.items():
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()[0]
        compact_table_sql = " ".join(table_sql.split())
        for column in columns:
            assert f"length({column}) = 20" in compact_table_sql
            assert f"typeof({column}) = 'text'" in compact_table_sql
            assert _gregorian_sql_predicate(column) in compact_table_sql
            checked_columns += 1
    assert checked_columns == 14

    session_trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        ("sessions_before_insert",),
    ).fetchone()[0]
    compact_session_trigger_sql = " ".join(session_trigger_sql.split())
    request_date_fields = (
        "request_window_start_date",
        "request_window_end_date",
        "target_session_date",
    )
    for field_name in request_date_fields:
        request_value_sql = f"json_extract(NEW.request_json, '$.{field_name}')"
        assert (
            _gregorian_sql_predicate(request_value_sql) in compact_session_trigger_sql
        )
    connection.close()


@pytest.mark.parametrize(
    ("relation", "child_timestamp", "accepted"),
    [
        ("earlier", "2025-12-31T23:59:59Z", False),
        ("equal", TIMESTAMP, True),
        ("later", "2026-01-01T00:00:01Z", True),
    ],
)
def test_migration_timestamp_is_non_decreasing_from_metadata(
    tmp_path: Path, relation: str, child_timestamp: str, accepted: bool
) -> None:
    connection = _connect(tmp_path / f"migration-{relation}.sqlite3")
    _install_schema(connection)
    _insert_metadata(connection)
    before = _database_rows(connection)
    if accepted:
        _insert_migration(connection, applied_at_utc=child_timestamp)
        assert connection.execute(
            "SELECT applied_at_utc FROM schema_migrations"
        ).fetchone() == (child_timestamp,)
    else:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_migration(connection, applied_at_utc=child_timestamp)
        assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize("edge", ["session", "attempt", "claim", "reservation"])
@pytest.mark.parametrize(
    ("child_timestamp", "accepted"),
    [
        ("2025-12-31T23:59:59Z", False),
        (TIMESTAMP, True),
        ("2026-01-01T00:00:01Z", True),
    ],
)
def test_creation_chain_timestamps_are_non_decreasing_at_direct_sql_boundaries(
    db_path: Path, edge: str, child_timestamp: str, accepted: bool
) -> None:
    connection = _connect(db_path)
    session_id: str | None = None
    attempt_id: str | None = None
    claim_id: str | None = None
    if edge != "session":
        session_id = create_session(connection)
    if edge in {"claim", "reservation"}:
        assert session_id is not None
        attempt_id = allocate_attempt(connection, session_id)
    if edge == "reservation":
        assert attempt_id is not None
        claim_id = commit_claim(connection, attempt_id)
    before = _database_rows(connection)

    def insert_child() -> object:
        if edge == "session":
            return create_session(connection, created_at_utc=child_timestamp)
        if edge == "attempt":
            assert session_id is not None
            return allocate_attempt(
                connection, session_id, created_at_utc=child_timestamp
            )
        if edge == "claim":
            assert attempt_id is not None
            return commit_claim(
                connection, attempt_id, committed_at_utc=child_timestamp
            )
        assert claim_id is not None
        return reserve_launch(connection, claim_id, committed_at_utc=child_timestamp)

    if accepted:
        inserted = insert_child()
        if type(inserted) is FakeProviderConstructionPermit:
            _consume_capability_for_test(inserted)
    else:
        with pytest.raises(sqlite3.IntegrityError):
            insert_child()
        assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize(
    ("selected_at_utc", "accepted"),
    [
        ("2026-01-01T00:03:59Z", False),
        (TERMINAL_TIMESTAMP, True),
        ("2026-01-01T00:04:01Z", True),
    ],
)
def test_selection_timestamp_is_non_decreasing_from_exact_terminal(
    db_path: Path, selected_at_utc: str, accepted: bool
) -> None:
    lifecycle = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    before = _database_rows(connection)
    if accepted:
        selection_id = _insert_selection_row_for_test(
            connection,
            lifecycle["session_id"],
            lifecycle["terminal_id"],
            selected_at_utc=selected_at_utc,
        )
        assert connection.execute(
            "SELECT selected_at_utc FROM session_selections WHERE selection_id = ?",
            (selection_id,),
        ).fetchone() == (selected_at_utc,)
    else:
        with pytest.raises(sqlite3.IntegrityError, match="selection terminal"):
            _insert_selection_row_for_test(
                connection,
                lifecycle["session_id"],
                lifecycle["terminal_id"],
                selected_at_utc=selected_at_utc,
            )
        assert _database_rows(connection) == before
    connection.close()


def test_selection_chronology_cannot_be_satisfied_by_wrong_session_terminal(
    db_path: Path,
) -> None:
    first = _seed_lifecycle(db_path)
    connection = _connect(db_path)
    second_session = create_session(connection, _request("2026-01-02"))
    second_attempt = allocate_attempt(connection, second_session)
    second_claim = commit_claim(connection, second_attempt)
    second_reservation = reserve_launch(connection, second_claim)
    second_execution = _record_successful_process(connection, second_reservation)
    _resume_and_persist(connection, second_execution, second_reservation)
    second_terminal = record_terminal(
        connection, second_reservation, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    before = _database_rows(connection)
    with pytest.raises(sqlite3.IntegrityError, match="selection terminal"):
        _insert_selection_row_for_test(
            connection,
            first["session_id"],
            second_terminal,
            selected_at_utc="9999-12-31T23:59:59Z",
        )
    assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize(
    ("state", "disposition", "preparation", "predecessor", "earlier"),
    [
        (
            "SUCCEEDED",
            "CONFIRMED",
            "resumed",
            RESUME_INTENT_TIMESTAMP,
            "2026-01-01T00:01:29Z",
        ),
        (
            "FAILED",
            "CONFIRMED",
            "resumed",
            RESUME_INTENT_TIMESTAMP,
            "2026-01-01T00:01:29Z",
        ),
        (
            "AMBIGUOUS",
            "MAY_HAVE_OCCURRED",
            "resumed",
            RESUME_INTENT_TIMESTAMP,
            "2026-01-01T00:01:29Z",
        ),
        (
            "FAILED",
            "NOT_STARTED",
            "process_failure",
            PROCESS_FAILURE_TIMESTAMP,
            "2026-01-01T00:01:59Z",
        ),
        (
            "CLOSED",
            "MAY_HAVE_OCCURRED",
            "manual_review",
            MANUAL_REVIEW_TIMESTAMP,
            "2026-01-01T00:02:59Z",
        ),
    ],
)
@pytest.mark.parametrize("relation", ["earlier", "equal", "later"])
def test_terminal_chronology_uses_state_specific_durable_predecessor(
    db_path: Path,
    state: str,
    disposition: str,
    preparation: str,
    predecessor: str,
    earlier: str,
    relation: str,
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if preparation == "resumed":
        execution_id = _record_successful_process(connection, reservation_id)
        _resume_and_persist(connection, execution_id, reservation_id)
    elif preparation == "process_failure":
        _record_definitive_process_failure(connection, reservation_id)
    else:
        assert preparation == "manual_review"
        record_recovery(
            connection,
            session_id,
            "LAUNCH_RESERVATION",
            reservation_id,
            "CLASSIFY_LAUNCH_RESERVATION",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    recorded_at_utc = {
        "earlier": earlier,
        "equal": predecessor,
        "later": TERMINAL_TIMESTAMP,
    }[relation]
    request_digest = connection.execute(
        "SELECT request_digest FROM launch_reservations "
        "WHERE launch_reservation_id = ?",
        (str(reservation_id),),
    ).fetchone()[0]
    before = _database_rows(connection)
    if relation == "earlier":
        with pytest.raises(sqlite3.IntegrityError, match="terminal timestamp"):
            _insert_terminal_row_for_test(
                connection,
                reservation_id,
                request_digest,
                state,
                disposition,
                recorded_at_utc=recorded_at_utc,
            )
        assert _database_rows(connection) == before
        assert connection.execute(
            "SELECT state FROM attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()[0] in {"LAUNCH_RESERVED", "TERMINAL_RECORDED"}
    else:
        terminal_id = _insert_terminal_row_for_test(
            connection,
            reservation_id,
            request_digest,
            state,
            disposition,
            recorded_at_utc=recorded_at_utc,
        )
        assert connection.execute(
            "SELECT recorded_at_utc FROM terminals WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone() == (recorded_at_utc,)
    assert connection.execute(
        "SELECT state FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone() == ("OPEN",)
    connection.close()


@pytest.mark.parametrize("close_path", ["recovery", "selection"])
@pytest.mark.parametrize("relation", ["earlier", "equal", "later"])
def test_session_close_timestamp_uses_exact_close_predecessor(
    db_path: Path, close_path: str, relation: str
) -> None:
    connection = _connect(db_path)
    if close_path == "recovery":
        session_id = create_session(connection)
        _insert_recovery_fact_for_test(
            connection,
            session_id,
            "SESSION",
            session_id,
            "CLOSE_SESSION",
            created_at_utc=MANUAL_REVIEW_TIMESTAMP,
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        predecessor = MANUAL_REVIEW_TIMESTAMP
        earlier = "2026-01-01T00:02:59Z"
        later = TERMINAL_TIMESTAMP
    else:
        lifecycle = _seed_lifecycle(db_path)
        session_id = lifecycle["session_id"]
        select_terminal(connection, session_id, lifecycle["terminal_id"])
        predecessor = SELECTION_TIMESTAMP
        earlier = "2026-01-01T00:04:59Z"
        later = CLOSE_TIMESTAMP
    closed_at_utc = {"earlier": earlier, "equal": predecessor, "later": later}[relation]
    before = _database_rows(connection)
    update = (
        "UPDATE sessions SET state = 'CLOSED', closed_at_utc = ?, close_reason = ? "
        "WHERE session_id = ?",
        (closed_at_utc, f"{close_path}-{relation}", session_id),
    )
    if relation == "earlier":
        with pytest.raises(sqlite3.IntegrityError, match="session close facts"):
            connection.execute(*update)
        assert _database_rows(connection) == before
    else:
        connection.execute(*update)
        assert connection.execute(
            "SELECT state, closed_at_utc FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone() == ("CLOSED", closed_at_utc)
    connection.close()


@pytest.mark.parametrize(
    ("process_intent_at_utc", "accepted"),
    [
        ("2025-12-31T23:59:59Z", False),
        (TIMESTAMP, True),
        ("2026-01-01T00:00:01Z", True),
    ],
)
def test_process_intent_timestamp_is_non_decreasing_from_reservation(
    db_path: Path, process_intent_at_utc: str, accepted: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    permit = reserve_launch(connection, claim_id)
    reservation_id = str(permit)
    request_digest, authority_policy, claim_policy = connection.execute(
        "SELECT request_digest, authority_policy_version, claim_policy_version "
        "FROM launch_reservations WHERE launch_reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    intent_json = _process_intent_json(
        reservation_id, request_digest, authority_policy, claim_policy
    )
    mutation = (
        "UPDATE launch_reservations SET reservation_state = "
        "'PROCESS_INTENT_COMMITTED', process_intent_json = ?, "
        "process_intent_digest = ?, process_intent_committed_at_utc = ? "
        "WHERE launch_reservation_id = ?",
        (intent_json, _digest(intent_json), process_intent_at_utc, reservation_id),
    )
    before = _database_rows(connection)
    if accepted:
        connection.execute(*mutation)
        assert connection.execute(
            "SELECT process_intent_committed_at_utc FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (reservation_id,),
        ).fetchone() == (process_intent_at_utc,)
    else:
        with pytest.raises(sqlite3.IntegrityError, match="process intent"):
            connection.execute(*mutation)
        assert _database_rows(connection) == before
    _consume_capability_for_test(permit)
    connection.close()


@pytest.mark.parametrize(
    ("execution_created_at_utc", "accepted"),
    [
        ("2026-01-01T00:00:29Z", False),
        (PROCESS_INTENT_TIMESTAMP, True),
        ("2026-01-01T00:00:31Z", True),
    ],
)
def test_execution_timestamp_is_non_decreasing_from_process_intent(
    db_path: Path, execution_created_at_utc: str, accepted: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = _construct_provider_and_commit_process_intent(
        connection, reservation_id
    )
    before = _database_rows(connection)
    _begin(connection)
    if accepted:
        execution_id = _insert_execution_row_for_test(
            connection,
            reservation_id,
            created_at_utc=execution_created_at_utc,
        )
        assert connection.execute(
            "SELECT created_at_utc FROM launch_executions "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == (execution_created_at_utc,)
    else:
        with pytest.raises(sqlite3.IntegrityError, match="execution policy"):
            _insert_execution_row_for_test(
                connection,
                reservation_id,
                created_at_utc=execution_created_at_utc,
            )
        assert _database_rows(connection) == before
    connection.rollback()
    _consume_capability_for_test(process_intent)
    connection.close()


@pytest.mark.parametrize(
    ("resume_intent_at_utc", "accepted"),
    [
        ("2026-01-01T00:00:59Z", False),
        (PROCESS_CREATED_TIMESTAMP, True),
        ("2026-01-01T00:01:01Z", True),
    ],
)
def test_resume_intent_timestamp_is_non_decreasing_from_execution(
    db_path: Path, resume_intent_at_utc: str, accepted: bool
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    execution_id = _record_successful_process(connection, reservation_id)
    intent_json = _json(
        {
            "execution_id": execution_id,
            "resume_operation": "ResumeThread",
            "schema": 1,
        }
    )
    mutation = (
        "UPDATE launch_executions SET phase = 'RESUME_INTENT_COMMITTED', "
        "resume_intent_json = ?, resume_intent_digest = ?, "
        "resume_intent_committed_at_utc = ? WHERE launch_execution_id = ?",
        (intent_json, _digest(intent_json), resume_intent_at_utc, execution_id),
    )
    before = _database_rows(connection)
    if accepted:
        connection.execute(*mutation)
        assert connection.execute(
            "SELECT resume_intent_committed_at_utc FROM launch_executions "
            "WHERE launch_execution_id = ?",
            (execution_id,),
        ).fetchone() == (resume_intent_at_utc,)
    else:
        with pytest.raises(sqlite3.IntegrityError, match="resume intent"):
            connection.execute(*mutation)
        assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize("outcome_kind", ["process-created", "creation-failed"])
@pytest.mark.parametrize("relation", ["earlier", "equal", "later"])
def test_process_outcome_timestamp_uses_exact_durable_predecessor(
    db_path: Path, outcome_kind: str, relation: str
) -> None:
    connection = _connect(db_path)
    session_id = create_session(connection)
    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    process_intent = _construct_provider_and_commit_process_intent(
        connection, reservation_id
    )
    before = _database_rows(connection)
    _begin(connection)
    if outcome_kind == "process-created":
        _insert_execution_row_for_test(
            connection,
            reservation_id,
            created_at_utc=PROCESS_CREATED_TIMESTAMP,
        )
        outcome_at_utc = {
            "earlier": "2026-01-01T00:00:59Z",
            "equal": PROCESS_CREATED_TIMESTAMP,
            "later": "2026-01-01T00:01:01Z",
        }[relation]
        mutation = (
            "UPDATE launch_reservations SET reservation_state = 'PROCESS_CREATED', "
            "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
            (outcome_at_utc, str(reservation_id)),
        )
    else:
        failure_json = _process_failure_json(
            str(reservation_id), process_intent.intent_digest
        )
        outcome_at_utc = {
            "earlier": "2026-01-01T00:00:29Z",
            "equal": PROCESS_INTENT_TIMESTAMP,
            "later": "2026-01-01T00:00:31Z",
        }[relation]
        mutation = (
            "UPDATE launch_reservations SET reservation_state = "
            "'PROCESS_CREATION_FAILED', process_creation_failure_json = ?, "
            "process_creation_failure_digest = ?, outcome_recorded_at_utc = ? "
            "WHERE launch_reservation_id = ?",
            (
                failure_json,
                _digest(failure_json),
                outcome_at_utc,
                str(reservation_id),
            ),
        )
    if relation == "earlier":
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(*mutation)
        connection.rollback()
        assert _database_rows(connection) == before
    else:
        connection.execute(*mutation)
        assert connection.execute(
            "SELECT outcome_recorded_at_utc FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (str(reservation_id),),
        ).fetchone() == (outcome_at_utc,)
        connection.rollback()
    _consume_capability_for_test(process_intent)
    connection.close()


def _prepare_recovery_chronology_case(
    connection: sqlite3.Connection, action: str
) -> tuple[str, str, str, str, str]:
    session_id = create_session(connection)
    if action in {"CLOSE_SESSION", "ACKNOWLEDGE_RESTORE"}:
        return session_id, "SESSION", session_id, TIMESTAMP, "2025-12-31T23:59:59Z"

    attempt_id = allocate_attempt(connection, session_id)
    claim_id = commit_claim(connection, attempt_id)
    reservation_id = reserve_launch(connection, claim_id)
    if action == "CLASSIFY_LAUNCH_RESERVATION":
        return (
            session_id,
            "LAUNCH_RESERVATION",
            str(reservation_id),
            TIMESTAMP,
            "2025-12-31T23:59:59Z",
        )
    if action == "CLASSIFY_PROCESS_OUTCOME_UNKNOWN":
        process_intent = _construct_provider_and_commit_process_intent(
            connection, reservation_id
        )
        _consume_capability_for_test(process_intent)
        return (
            session_id,
            "LAUNCH_RESERVATION",
            str(reservation_id),
            PROCESS_INTENT_TIMESTAMP,
            "2026-01-01T00:00:29Z",
        )

    execution_id = _record_successful_process(connection, reservation_id)
    if action == "CLASSIFY_PRE_RESUME_READY":
        return (
            session_id,
            "LAUNCH_RESERVATION",
            str(reservation_id),
            PROCESS_CREATED_TIMESTAMP,
            "2026-01-01T00:00:59Z",
        )
    if action == "CLASSIFY_RESUME_OUTCOME_UNKNOWN":
        resume_intent = commit_resume_intent(connection, execution_id, reservation_id)
        _consume_capability_for_test(resume_intent)
        return (
            session_id,
            "LAUNCH_RESERVATION",
            str(reservation_id),
            RESUME_INTENT_TIMESTAMP,
            "2026-01-01T00:01:29Z",
        )

    _resume_and_persist(connection, execution_id, reservation_id)
    if action == "RECORD_ATTEMPT_AMBIGUITY":
        return (
            session_id,
            "ATTEMPT",
            attempt_id,
            RESUME_INTENT_TIMESTAMP,
            "2026-01-01T00:01:29Z",
        )
    if action == "RECORD_CLAIM_AMBIGUITY":
        return (
            session_id,
            "CLAIM",
            claim_id,
            RESUME_INTENT_TIMESTAMP,
            "2026-01-01T00:01:29Z",
        )
    assert action == "SELECT_COMMITTED_SUCCESS"
    terminal_id = record_terminal(
        connection, reservation_id, snapshot_digest=TEST_SNAPSHOT_DIGEST
    )
    return (
        session_id,
        "TERMINAL",
        terminal_id,
        TERMINAL_TIMESTAMP,
        "2026-01-01T00:03:59Z",
    )


@pytest.mark.parametrize("action", list(_RECOVERY_ACTIONS))
@pytest.mark.parametrize("relation", ["earlier", "equal", "later"])
def test_recovery_timestamp_uses_action_specific_durable_predecessor(
    db_path: Path, action: str, relation: str
) -> None:
    connection = _connect(db_path)
    session_id, target_kind, target_id, predecessor, earlier = (
        _prepare_recovery_chronology_case(connection, action)
    )
    recovery_created_at_utc = {
        "earlier": earlier,
        "equal": predecessor,
        "later": SELECTION_TIMESTAMP
        if action == "SELECT_COMMITTED_SUCCESS"
        else MANUAL_REVIEW_TIMESTAMP,
    }[relation]
    before = _database_rows(connection)
    _begin(connection)
    if relation == "earlier":
        with pytest.raises(sqlite3.IntegrityError, match="recovery timestamp"):
            _insert_recovery_fact_for_test(
                connection,
                session_id,
                target_kind,
                target_id,
                action,
                created_at_utc=recovery_created_at_utc,
                operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
                operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
            )
        connection.rollback()
        assert _database_rows(connection) == before
    else:
        recovery_id = _insert_recovery_fact_for_test(
            connection,
            session_id,
            target_kind,
            target_id,
            action,
            created_at_utc=recovery_created_at_utc,
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
        assert connection.execute(
            "SELECT created_at_utc FROM manual_recoveries WHERE recovery_id = ?",
            (recovery_id,),
        ).fetchone() == (recovery_created_at_utc,)
        connection.rollback()
    connection.close()


@pytest.mark.parametrize("action", list(_RECOVERY_ACTIONS))
def test_recovery_chronology_cannot_use_wrong_session_lineage(
    db_path: Path, action: str
) -> None:
    connection = _connect(db_path)
    _, target_kind, target_id, _, _ = _prepare_recovery_chronology_case(
        connection, action
    )
    wrong_session = create_session(connection, _request("2026-01-10"))
    before = _database_rows(connection)
    _begin(connection)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_recovery_fact_for_test(
            connection,
            wrong_session,
            target_kind,
            target_id,
            action,
            created_at_utc="9999-12-31T23:59:59Z",
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )
    connection.rollback()
    assert _database_rows(connection) == before
    connection.close()


@pytest.mark.parametrize(
    "action", ["CLASSIFY_LAUNCH_RESERVATION", "CLASSIFY_PROCESS_OUTCOME_UNKNOWN"]
)
@pytest.mark.parametrize("relation", ["earlier", "equal", "later"])
def test_manual_review_outcome_timestamp_does_not_predate_classification_recovery(
    db_path: Path, action: str, relation: str
) -> None:
    connection = _connect(db_path)
    session_id, target_kind, target_id, _, _ = _prepare_recovery_chronology_case(
        connection, action
    )
    before = _database_rows(connection)
    _begin(connection)
    _insert_recovery_fact_for_test(
        connection,
        session_id,
        target_kind,
        target_id,
        action,
        created_at_utc=MANUAL_REVIEW_TIMESTAMP,
        operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
        operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
    )
    outcome_at_utc = {
        "earlier": "2026-01-01T00:02:59Z",
        "equal": MANUAL_REVIEW_TIMESTAMP,
        "later": TERMINAL_TIMESTAMP,
    }[relation]
    mutation = (
        "UPDATE launch_reservations SET reservation_state = 'MANUAL_REVIEW', "
        "outcome_recorded_at_utc = ? WHERE launch_reservation_id = ?",
        (outcome_at_utc, target_id),
    )
    if relation == "earlier":
        with pytest.raises(sqlite3.IntegrityError, match="outcome timestamp"):
            connection.execute(*mutation)
        connection.rollback()
        assert _database_rows(connection) == before
    else:
        connection.execute(*mutation)
        assert connection.execute(
            "SELECT outcome_recorded_at_utc FROM launch_reservations "
            "WHERE launch_reservation_id = ?",
            (target_id,),
        ).fetchone() == (outcome_at_utc,)
        connection.rollback()
    connection.close()


def _recovery_target_reservation_id(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
) -> str:
    if target_kind == "LAUNCH_RESERVATION":
        return target_id
    if target_kind == "ATTEMPT":
        row = connection.execute(
            """
            SELECT r.launch_reservation_id
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            WHERE a.attempt_id = ? AND a.session_id = ?
            """,
            (target_id, session_id),
        ).fetchone()
    else:
        assert target_kind == "CLAIM"
        row = connection.execute(
            """
            SELECT r.launch_reservation_id
            FROM launch_reservations r
            JOIN provider_call_claims c ON c.claim_id = r.claim_id
            JOIN attempts a ON a.attempt_id = c.attempt_id
            WHERE c.claim_id = ? AND a.session_id = ?
            """,
            (target_id, session_id),
        ).fetchone()
    assert row is not None
    return row[0]


def _corrupt_recovery_target_evidence(
    connection: sqlite3.Connection,
    session_id: str,
    target_kind: str,
    target_id: str,
    pair: str,
) -> None:
    reservation_id = _recovery_target_reservation_id(
        connection, session_id, target_kind, target_id
    )
    wrong_digest = _digest(b"corrupted recovery target evidence")
    if pair == "launch_reservations.process_intent":
        connection.execute(
            "DROP TRIGGER launch_reservations_process_intent_append_only"
        )
        connection.execute(
            "UPDATE launch_reservations SET process_intent_digest = ? "
            "WHERE launch_reservation_id = ?",
            (wrong_digest, reservation_id),
        )
    else:
        column = pair.rsplit(".", 1)[1]
        trigger = {
            "post_resume": "launch_executions_post_resume_append_only",
            "cleanup": "launch_executions_cleanup_append_only",
            "process_creation": "launch_executions_immutable_fields",
            "job_object": "launch_executions_immutable_fields",
            "resume_authorization": "launch_executions_immutable_fields",
            "resume_intent": "launch_executions_resume_intent_append_only",
        }[column]
        connection.execute(f"DROP TRIGGER {trigger}")
        connection.execute(
            f"UPDATE launch_executions SET {column}_digest = ? "
            "WHERE launch_reservation_id = ?",
            (wrong_digest, reservation_id),
        )
    connection.commit()


_RECOVERY_TARGET_EVIDENCE_CORRUPTION_CASES = tuple(
    (action, pair)
    for action, pairs in _RECOVERY_TARGET_EVIDENCE_PAIRS.items()
    for pair in pairs
)


def test_recovery_target_evidence_mapping_has_exact_twelve_dependencies() -> None:
    assert _RECOVERY_TARGET_EVIDENCE_PAIRS == {
        "RECORD_ATTEMPT_AMBIGUITY": (
            "launch_executions.post_resume",
            "launch_executions.cleanup",
        ),
        "RECORD_CLAIM_AMBIGUITY": (
            "launch_executions.post_resume",
            "launch_executions.cleanup",
        ),
        "CLASSIFY_LAUNCH_RESERVATION": (),
        "CLASSIFY_PROCESS_OUTCOME_UNKNOWN": ("launch_reservations.process_intent",),
        "CLASSIFY_PRE_RESUME_READY": (
            "launch_executions.process_creation",
            "launch_executions.job_object",
            "launch_executions.resume_authorization",
        ),
        "CLASSIFY_RESUME_OUTCOME_UNKNOWN": (
            "launch_executions.process_creation",
            "launch_executions.job_object",
            "launch_executions.resume_authorization",
            "launch_executions.resume_intent",
        ),
        "SELECT_COMMITTED_SUCCESS": (),
        "CLOSE_SESSION": (),
        "ACKNOWLEDGE_RESTORE": (),
    }
    assert len(_RECOVERY_TARGET_EVIDENCE_CORRUPTION_CASES) == 12


def test_harness_imports_only_the_supported_transactional_core() -> None:
    tree = ast.parse(_HARNESS_MODULE_PATH.read_text(encoding="utf-8"))
    private_imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "trading_bot.runtime.windows_transactional_authority"
        for alias in node.names
        if alias.name.startswith("_")
    ]
    supported_imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "trading_bot.runtime.windows_transactional_authority"
        for alias in node.names
        if alias.name
        in {
            "TransactionalAuthorityCore",
            "TransactionalAuthorityCoreBinding",
        }
    ]
    assert private_imports == []
    assert supported_imports == [
        "TransactionalAuthorityCore",
        "TransactionalAuthorityCoreBinding",
    ]


@pytest.mark.parametrize(
    ("action", "pair"),
    _RECOVERY_TARGET_EVIDENCE_CORRUPTION_CASES,
    ids=lambda value: str(value),
)
def test_corrupt_recovery_target_evidence_blocks_without_mutation(
    db_path: Path, action: str, pair: str
) -> None:
    connection = _connect(db_path)
    session_id, target_kind, target_id, _, _ = _prepare_recovery_chronology_case(
        connection, action
    )
    _corrupt_recovery_target_evidence(
        connection, session_id, target_kind, target_id, pair
    )
    before = _database_rows(connection)
    target_state = _target_state(connection, target_kind, target_id)

    with pytest.raises(SchemaValidationError, match="does not match evidence bytes"):
        record_recovery(
            connection,
            session_id,
            target_kind,
            target_id,
            action,
            operator_evidence_json=TEST_OPERATOR_EVIDENCE_JSON,
            operator_evidence_digest=TEST_OPERATOR_EVIDENCE_DIGEST,
        )

    assert not connection.in_transaction
    assert _database_rows(connection) == before
    assert _target_state(connection, target_kind, target_id) == target_state
    assert connection.execute("SELECT count(*) FROM manual_recoveries").fetchone() == (
        0,
    )
    connection.execute("BEGIN IMMEDIATE")
    connection.rollback()
    connection.close()
