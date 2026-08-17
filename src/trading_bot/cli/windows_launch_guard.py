"""Windows named-mutex launch guard with immutable local lease evidence."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Protocol
from uuid import UUID

from trading_bot.cli.checkpoint_transition_output import (
    OutputParent,
    validate_output_parent,
)
from trading_bot.runtime.launch_guard import (
    MAX_LEASE_ARTIFACT_BYTES,
    LaunchGuardAcquisitionClassification,
    LaunchGuardDiagnostic,
    LaunchLeaseArtifactReference,
    LaunchLeaseRelease,
    LaunchLeaseReleaseClassification,
    LaunchLeaseStart,
    LaunchResultClassification,
    create_launch_lease_release,
    create_launch_lease_start,
    derive_launch_lease_release_id,
    derive_launch_lease_start_id,
    parse_launch_lease_release,
    parse_launch_lease_start,
    serialize_launch_lease_release,
    serialize_launch_lease_start,
    windows_mutex_name,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence, ScheduledPhase

_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_ERROR_ACCESS_DENIED = 5
_INFINITE = 0xFFFFFFFF
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_MAX_LOCK_EVENT_ENTRIES = 10_000
_FINAL_NAME_RE = re.compile(
    r"launch-lease-(?:start|release)-[0-9a-f]{8}-"
    r"[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-"
    r"[0-9a-f]{12}\.json"
)


class LaunchGuardAclPolicy(StrEnum):
    """Explicit ACL posture for the mutex."""

    ALLOW_DEFAULT_DACL = "ALLOW_DEFAULT_DACL"
    REQUIRE_VERIFIED_DACL = "REQUIRE_VERIFIED_DACL"


class LaunchGuardAclEnforcement(StrEnum):
    """Honest status for the deliberately unimplemented ACL hardening."""

    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class EvidencePublicationClassification(StrEnum):
    PUBLISHED = "PUBLISHED"
    IDEMPOTENT = "IDEMPOTENT"


class ReleaseOperationalClassification(StrEnum):
    RELEASED = "RELEASED"
    EVIDENCE_PUBLICATION_FAILED = "EVIDENCE_PUBLICATION_FAILED"
    NATIVE_RELEASE_FAILED = "NATIVE_RELEASE_FAILED"
    EVIDENCE_AND_NATIVE_RELEASE_FAILED = "EVIDENCE_AND_NATIVE_RELEASE_FAILED"


class LaunchGuardEvidenceError(RuntimeError):
    """Safe publication or immutable evidence validation failed."""


class LaunchGuardLifecycleError(RuntimeError):
    """The ownership object was used outside its valid lifecycle."""


class LaunchGuardOperationalError(RuntimeError):
    """A context-managed release could not complete safely."""


@dataclass(frozen=True, slots=True)
class NativeMutexAcquire:
    classification: LaunchGuardAcquisitionClassification
    handle: object | None
    native_error_code: int | None = None

    def __post_init__(self) -> None:
        acquired = self.classification in {
            LaunchGuardAcquisitionClassification.ACQUIRED,
            LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED,
        }
        if acquired != (self.handle is not None):
            raise ValueError(
                "native handle presence must match acquired classification"
            )


class WindowsMutexApi(Protocol):
    """Narrow injectable Win32 mutex surface."""

    def acquire(
        self, mutex_name: str, timeout_milliseconds: int
    ) -> NativeMutexAcquire: ...

    def release(self, handle: object) -> None: ...

    def close(self, handle: object) -> None: ...


class CtypesWindowsMutexApi:
    """CreateMutexW/WaitForSingleObject/ReleaseMutex/CloseHandle adapter."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows named mutexes are unsupported on this platform")
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._ctypes = ctypes
        self._kernel32 = kernel32

    def acquire(self, mutex_name: str, timeout_milliseconds: int) -> NativeMutexAcquire:
        handle = self._kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            error = self._ctypes.get_last_error()
            classification = (
                LaunchGuardAcquisitionClassification.ACCESS_DENIED
                if error == _ERROR_ACCESS_DENIED
                else LaunchGuardAcquisitionClassification.ERROR
            )
            return NativeMutexAcquire(classification, None, error)
        wait_result = int(
            self._kernel32.WaitForSingleObject(handle, timeout_milliseconds)
        )
        if wait_result == _WAIT_OBJECT_0:
            return NativeMutexAcquire(
                LaunchGuardAcquisitionClassification.ACQUIRED,
                handle,
            )
        if wait_result == _WAIT_ABANDONED:
            return NativeMutexAcquire(
                LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED,
                handle,
            )
        error: int | None = None
        if wait_result == _WAIT_FAILED:
            error = self._ctypes.get_last_error()
        if not self._kernel32.CloseHandle(handle):
            close_error = self._ctypes.get_last_error()
            return NativeMutexAcquire(
                LaunchGuardAcquisitionClassification.ERROR,
                None,
                close_error,
            )
        if wait_result == _WAIT_TIMEOUT:
            return NativeMutexAcquire(
                LaunchGuardAcquisitionClassification.ALREADY_HELD,
                None,
            )
        classification = (
            LaunchGuardAcquisitionClassification.ACCESS_DENIED
            if error == _ERROR_ACCESS_DENIED
            else LaunchGuardAcquisitionClassification.ERROR
        )
        return NativeMutexAcquire(classification, None, error)

    def release(self, handle: object) -> None:
        if not self._kernel32.ReleaseMutex(handle):
            error = self._ctypes.get_last_error()
            raise OSError(error, "ReleaseMutex failed")

    def close(self, handle: object) -> None:
        if not self._kernel32.CloseHandle(handle):
            error = self._ctypes.get_last_error()
            raise OSError(error, "CloseHandle failed")


@dataclass(frozen=True, slots=True)
class LaunchLeaseReleaseInput:
    release_classification: LaunchLeaseReleaseClassification
    release_timestamp_utc: str
    monotonic_duration_nanoseconds: int
    result_classification: LaunchResultClassification
    result_diagnostic: str
    process_exit_code: int | None
    release_policy: str


@dataclass(frozen=True, slots=True)
class LaunchGuardAcquireRequest:
    audit_root: Path
    scheduled_launch_id: UUID
    authority_epoch_id: UUID
    scheduled_phase: ScheduledPhase
    machine_authority_id: UUID
    boot_evidence: str
    process_id: int
    process_creation_timestamp_utc: str
    user_sid: str
    executable_release: ArtifactEvidence
    acquisition_timestamp_utc: str
    max_runtime_seconds: int
    launch_policy: str
    timeout_seconds: int
    acl_policy: LaunchGuardAclPolicy
    validate_audit_root_before_acquire: bool = True
    context_release_input: LaunchLeaseReleaseInput | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.audit_root, Path):
            raise ValueError("audit_root must be a Path")
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, int
        ):
            raise ValueError("timeout_seconds must be an integer")
        if not 0 <= self.timeout_seconds <= (_INFINITE - 1) // 1000:
            raise ValueError("timeout_seconds is outside the bounded Win32 range")
        if not isinstance(self.acl_policy, LaunchGuardAclPolicy):
            raise ValueError("acl_policy must be LaunchGuardAclPolicy")
        if type(self.validate_audit_root_before_acquire) is not bool:
            raise ValueError("validate_audit_root_before_acquire must be a bool")
        if self.context_release_input is not None and not isinstance(
            self.context_release_input,
            LaunchLeaseReleaseInput,
        ):
            raise ValueError(
                "context_release_input must be LaunchLeaseReleaseInput or None"
            )
        derive_launch_lease_start_id(
            scheduled_launch_id=self.scheduled_launch_id,
            authority_epoch_id=self.authority_epoch_id,
            scheduled_phase=self.scheduled_phase,
            mutex_name=windows_mutex_name(self.authority_epoch_id),
            acquisition_classification=LaunchGuardAcquisitionClassification.ACQUIRED,
            machine_authority_id=self.machine_authority_id,
            boot_evidence=self.boot_evidence,
            process_id=self.process_id,
            process_creation_timestamp_utc=self.process_creation_timestamp_utc,
            user_sid=self.user_sid,
            executable_release=self.executable_release,
            acquisition_timestamp_utc=self.acquisition_timestamp_utc,
            max_runtime_seconds=self.max_runtime_seconds,
            launch_policy=self.launch_policy,
        )
        if self.context_release_input is not None:
            release_input = self.context_release_input
            derive_launch_lease_release_id(
                lease_start=LaunchLeaseArtifactReference(
                    record_id=UUID("aac32d21-c577-57f5-9f64-37e9985d348c"),
                    sha256="0" * 64,
                    byte_length=1,
                ),
                scheduled_launch_id=self.scheduled_launch_id,
                authority_epoch_id=self.authority_epoch_id,
                release_classification=release_input.release_classification,
                release_timestamp_utc=release_input.release_timestamp_utc,
                monotonic_duration_nanoseconds=(
                    release_input.monotonic_duration_nanoseconds
                ),
                result_classification=release_input.result_classification,
                result_diagnostic=release_input.result_diagnostic,
                process_exit_code=release_input.process_exit_code,
                release_policy=release_input.release_policy,
            )


@dataclass(frozen=True, slots=True)
class EvidencePublicationResult:
    classification: EvidencePublicationClassification
    path: Path
    artifact_reference: LaunchLeaseArtifactReference


@dataclass(frozen=True, slots=True)
class LaunchGuardAcquireResult:
    classification: LaunchGuardAcquisitionClassification
    mutex_name: str
    acl_enforcement: LaunchGuardAclEnforcement
    ownership: LaunchGuardOwnership | None
    native_error_code: int | None
    diagnostic: str


@dataclass(frozen=True, slots=True)
class LaunchGuardReleaseResult:
    classification: ReleaseOperationalClassification
    release_record: LaunchLeaseRelease
    publication: EvidencePublicationResult | None
    evidence_error: str | None
    native_error: str | None
    manual_review_required: bool


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(
        getattr(stat_result, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _assert_regular_file(path: Path) -> os.stat_result:
    info = path.lstat()
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        raise LaunchGuardEvidenceError(f"unsafe non-regular artifact entry: {path}")
    return info


def _bounded_read(path: Path) -> bytes:
    before = _assert_regular_file(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        held = os.fstat(stream.fileno())
        if _is_reparse(held) or not stat.S_ISREG(held.st_mode):
            raise LaunchGuardEvidenceError("opened artifact is not a regular file")
        if (before.st_dev, before.st_ino) != (held.st_dev, held.st_ino):
            raise LaunchGuardEvidenceError(
                "artifact identity changed before bounded reread"
            )
        payload = stream.read(MAX_LEASE_ARTIFACT_BYTES + 1)
    after = _assert_regular_file(path)
    if (held.st_dev, held.st_ino, held.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise LaunchGuardEvidenceError("artifact identity changed during reread")
    if len(payload) > MAX_LEASE_ARTIFACT_BYTES:
        raise LaunchGuardEvidenceError("artifact exceeds the bounded reread limit")
    return payload


def _validate_event_directory(root: Path) -> tuple[Path, OutputParent]:
    if not root.is_absolute():
        raise LaunchGuardEvidenceError("audit_root must be absolute")
    root_state = validate_output_parent(root)
    entries = list(root.iterdir())
    if len(entries) > _MAX_LOCK_EVENT_ENTRIES:
        raise LaunchGuardEvidenceError("audit root contains too many entries")
    folded = [entry.name.casefold() for entry in entries]
    if len(folded) != len(set(folded)):
        raise LaunchGuardEvidenceError("audit root contains case-fold collisions")
    collisions = [
        entry.name
        for entry in entries
        if entry.name.casefold() == "lock-events" and entry.name != "lock-events"
    ]
    if collisions:
        raise LaunchGuardEvidenceError(
            f"audit root contains lock-events case collision: {sorted(collisions)}"
        )
    event_dir = root / "lock-events"
    if event_dir.exists():
        event_state = validate_output_parent(event_dir)
    else:
        try:
            os.mkdir(event_dir)
        except FileExistsError:
            pass
        event_state = validate_output_parent(event_dir)
    if validate_output_parent(root) != root_state:
        raise LaunchGuardEvidenceError("audit root identity changed")
    return event_dir, event_state


def _validate_existing_event_entries(event_dir: Path) -> None:
    entries = list(event_dir.iterdir())
    if len(entries) > _MAX_LOCK_EVENT_ENTRIES:
        raise LaunchGuardEvidenceError("lock-events contains too many entries")
    folded = [entry.name.casefold() for entry in entries]
    if len(folded) != len(set(folded)):
        raise LaunchGuardEvidenceError("lock-events contains case-fold collisions")
    for entry in entries:
        if not _FINAL_NAME_RE.fullmatch(entry.name):
            raise LaunchGuardEvidenceError(
                f"lock-events contains unexpected entry: {entry.name}"
            )
        payload = _bounded_read(entry)
        try:
            if entry.name.startswith("launch-lease-start-"):
                record = parse_launch_lease_start(payload)
                expected_name = f"launch-lease-start-{record.record_id}.json"
            else:
                record = parse_launch_lease_release(payload)
                expected_name = f"launch-lease-release-{record.release_id}.json"
        except ValueError as exc:
            raise LaunchGuardEvidenceError(
                f"existing lease artifact is not canonical: {entry.name}"
            ) from exc
        if entry.name != expected_name:
            raise LaunchGuardEvidenceError(
                f"lease artifact filename does not match canonical ID: {entry.name}"
            )


def _publish_payload(
    *,
    audit_root: Path,
    final_name: str,
    payload: bytes,
    artifact_id: UUID,
    parser: Callable[[bytes], object],
) -> EvidencePublicationResult:
    event_dir, parent_state = _validate_event_directory(audit_root)
    _validate_existing_event_entries(event_dir)
    final_path = event_dir / final_name
    if final_path.exists():
        existing = _bounded_read(final_path)
        if existing != payload:
            raise LaunchGuardEvidenceError(
                "existing final artifact conflicts with requested bytes"
            )
        parser(existing)
        return EvidencePublicationResult(
            EvidencePublicationClassification.IDEMPOTENT,
            final_path,
            LaunchLeaseArtifactReference(
                record_id=artifact_id,
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_length=len(payload),
            ),
        )
    staging_path = event_dir / f".{final_name}.staging"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(staging_path, flags, 0o600)
    except FileExistsError as exc:
        raise LaunchGuardEvidenceError(
            f"crash-left staging entry requires manual review: {staging_path.name}"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Deliberately preserve invocation-owned staging evidence on failure.
        raise
    reread = _bounded_read(staging_path)
    if reread != payload:
        raise LaunchGuardEvidenceError("staging reread differs from intended bytes")
    parser(reread)
    if validate_output_parent(event_dir) != parent_state:
        raise LaunchGuardEvidenceError("lock-events parent identity changed")
    try:
        os.link(staging_path, final_path)
    except FileExistsError as exc:
        existing = _bounded_read(final_path)
        if existing != payload:
            raise LaunchGuardEvidenceError(
                "no-clobber finalization found conflict"
            ) from exc
    final_bytes = _bounded_read(final_path)
    if final_bytes != payload:
        raise LaunchGuardEvidenceError("finalized artifact differs from intended bytes")
    parser(final_bytes)
    if validate_output_parent(event_dir) != parent_state:
        raise LaunchGuardEvidenceError("lock-events parent changed after finalization")
    try:
        staging_info = _assert_regular_file(staging_path)
        final_info = _assert_regular_file(final_path)
        if (staging_info.st_dev, staging_info.st_ino) != (
            final_info.st_dev,
            final_info.st_ino,
        ):
            raise LaunchGuardEvidenceError(
                "staging identity differs from finalized artifact"
            )
        staging_path.unlink()
    except FileNotFoundError as exc:
        raise LaunchGuardEvidenceError(
            "staging entry disappeared before successful finalization"
        ) from exc
    return EvidencePublicationResult(
        EvidencePublicationClassification.PUBLISHED,
        final_path,
        LaunchLeaseArtifactReference(
            record_id=artifact_id,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_length=len(payload),
        ),
    )


def publish_launch_lease_start(
    audit_root: Path,
    lease_start: LaunchLeaseStart,
) -> EvidencePublicationResult:
    payload = serialize_launch_lease_start(lease_start)
    return _publish_payload(
        audit_root=audit_root,
        final_name=f"launch-lease-start-{lease_start.record_id}.json",
        payload=payload,
        artifact_id=lease_start.record_id,
        parser=parse_launch_lease_start,
    )


def publish_launch_lease_release(
    audit_root: Path,
    lease_release: LaunchLeaseRelease,
) -> EvidencePublicationResult:
    payload = serialize_launch_lease_release(lease_release)
    return _publish_payload(
        audit_root=audit_root,
        final_name=f"launch-lease-release-{lease_release.release_id}.json",
        payload=payload,
        artifact_id=lease_release.release_id,
        parser=parse_launch_lease_release,
    )


@dataclass(slots=True)
class _LaunchGuardOwnershipState:
    api: WindowsMutexApi
    handle: object
    audit_root: Path
    start_record: LaunchLeaseStart
    start_publication: EvidencePublicationResult
    context_release_input: LaunchLeaseReleaseInput | None
    released: bool = False
    release_publication: EvidencePublicationResult | None = None


@dataclass(frozen=True, slots=True)
class LaunchGuardOwnership:
    """Scoped ownership; the native handle is private and never serialized."""

    _state: _LaunchGuardOwnershipState

    @property
    def start_record(self) -> LaunchLeaseStart:
        return self._state.start_record

    @property
    def start_reference(self) -> LaunchLeaseArtifactReference:
        return self._state.start_publication.artifact_reference

    @property
    def released(self) -> bool:
        return self._state.released

    def __enter__(self) -> LaunchGuardOwnership:
        if self._state.released:
            raise LaunchGuardLifecycleError("ownership has already been released")
        if self._state.context_release_input is None:
            raise LaunchGuardLifecycleError(
                "context-manager use requires explicit context_release_input"
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exc_type, exc_value, traceback
        if self._state.context_release_input is None:
            raise LaunchGuardLifecycleError(
                "context-manager use requires explicit context_release_input"
            )
        result = self.release(self._state.context_release_input)
        if result.classification is not ReleaseOperationalClassification.RELEASED:
            raise LaunchGuardOperationalError(
                f"launch guard release requires manual review: {result.classification}"
            )
        return False

    def release(
        self,
        release_input: LaunchLeaseReleaseInput,
    ) -> LaunchGuardReleaseResult:
        if self._state.released:
            raise LaunchGuardLifecycleError("ownership has already been released")
        release_record = create_launch_lease_release(
            lease_start=self._state.start_record,
            lease_start_reference=self._state.start_publication.artifact_reference,
            release_classification=release_input.release_classification,
            release_timestamp_utc=release_input.release_timestamp_utc,
            monotonic_duration_nanoseconds=(
                release_input.monotonic_duration_nanoseconds
            ),
            result_classification=release_input.result_classification,
            result_diagnostic=release_input.result_diagnostic,
            process_exit_code=release_input.process_exit_code,
            release_policy=release_input.release_policy,
        )
        self._state.released = True
        publication: EvidencePublicationResult | None = None
        evidence_error: str | None = None
        fatal_error: BaseException | None = None
        try:
            publication = publish_launch_lease_release(
                self._state.audit_root,
                release_record,
            )
            self._state.release_publication = publication
        except BaseException as exc:
            if isinstance(exc, Exception):
                evidence_error = f"{type(exc).__name__}: {exc}"
            else:
                fatal_error = exc
                evidence_error = type(exc).__name__
        native_errors: list[str] = []
        try:
            self._state.api.release(self._state.handle)
        except BaseException as exc:
            native_errors.append(f"{type(exc).__name__}: {exc}")
            if not isinstance(exc, Exception) and fatal_error is None:
                fatal_error = exc
        try:
            self._state.api.close(self._state.handle)
        except BaseException as exc:
            native_errors.append(f"{type(exc).__name__}: {exc}")
            if not isinstance(exc, Exception) and fatal_error is None:
                fatal_error = exc
        native_error = "; ".join(native_errors) or None
        if fatal_error is not None:
            if evidence_error is not None:
                fatal_error.add_note(f"lease evidence error: {evidence_error}")
            if native_error is not None:
                fatal_error.add_note(f"native release error: {native_error}")
            raise fatal_error
        if evidence_error and native_error:
            classification = (
                ReleaseOperationalClassification.EVIDENCE_AND_NATIVE_RELEASE_FAILED
            )
        elif evidence_error:
            classification = (
                ReleaseOperationalClassification.EVIDENCE_PUBLICATION_FAILED
            )
        elif native_error:
            classification = ReleaseOperationalClassification.NATIVE_RELEASE_FAILED
        else:
            classification = ReleaseOperationalClassification.RELEASED
        return LaunchGuardReleaseResult(
            classification=classification,
            release_record=release_record,
            publication=publication,
            evidence_error=evidence_error,
            native_error=native_error,
            manual_review_required=classification
            is not ReleaseOperationalClassification.RELEASED,
        )


def acquire_windows_launch_guard(
    request: LaunchGuardAcquireRequest,
    *,
    native_api: WindowsMutexApi | None = None,
) -> LaunchGuardAcquireResult:
    """Validate, acquire, publish start evidence, then return scoped ownership."""

    mutex_name = windows_mutex_name(request.authority_epoch_id)
    acl_enforcement = LaunchGuardAclEnforcement.NOT_IMPLEMENTED
    if request.acl_policy is LaunchGuardAclPolicy.REQUIRE_VERIFIED_DACL:
        return LaunchGuardAcquireResult(
            classification=LaunchGuardAcquisitionClassification.UNSUPPORTED,
            mutex_name=mutex_name,
            acl_enforcement=acl_enforcement,
            ownership=None,
            native_error_code=None,
            diagnostic="VERIFIED_DACL_NOT_IMPLEMENTED",
        )
    if request.validate_audit_root_before_acquire:
        try:
            validate_output_parent(request.audit_root)
        except Exception as exc:
            return LaunchGuardAcquireResult(
                classification=LaunchGuardAcquisitionClassification.ERROR,
                mutex_name=mutex_name,
                acl_enforcement=acl_enforcement,
                ownership=None,
                native_error_code=None,
                diagnostic=f"AUDIT_ROOT_INVALID:{type(exc).__name__}",
            )
    if native_api is None and os.name != "nt":
        return LaunchGuardAcquireResult(
            classification=LaunchGuardAcquisitionClassification.UNSUPPORTED,
            mutex_name=mutex_name,
            acl_enforcement=acl_enforcement,
            ownership=None,
            native_error_code=None,
            diagnostic="WINDOWS_NAMED_MUTEX_UNSUPPORTED",
        )
    try:
        if native_api is None:
            native_api = CtypesWindowsMutexApi()
        native = native_api.acquire(mutex_name, request.timeout_seconds * 1000)
    except Exception as exc:
        error_code = getattr(exc, "winerror", None)
        return LaunchGuardAcquireResult(
            classification=(
                LaunchGuardAcquisitionClassification.ACCESS_DENIED
                if error_code == _ERROR_ACCESS_DENIED
                else LaunchGuardAcquisitionClassification.ERROR
            ),
            mutex_name=mutex_name,
            acl_enforcement=acl_enforcement,
            ownership=None,
            native_error_code=error_code,
            diagnostic=f"NATIVE_ACQUIRE_FAILED:{type(exc).__name__}",
        )
    if native.handle is None:
        return LaunchGuardAcquireResult(
            classification=native.classification,
            mutex_name=mutex_name,
            acl_enforcement=acl_enforcement,
            ownership=None,
            native_error_code=native.native_error_code,
            diagnostic=native.classification.value,
        )
    failure_stage = "START_CONSTRUCTION_FAILED"
    try:
        if not request.validate_audit_root_before_acquire:
            failure_stage = "AUDIT_ROOT_INVALID"
            validate_output_parent(request.audit_root)
        start_record = create_launch_lease_start(
            scheduled_launch_id=request.scheduled_launch_id,
            authority_epoch_id=request.authority_epoch_id,
            scheduled_phase=request.scheduled_phase,
            acquisition_classification=native.classification,
            machine_authority_id=request.machine_authority_id,
            boot_evidence=request.boot_evidence,
            process_id=request.process_id,
            process_creation_timestamp_utc=request.process_creation_timestamp_utc,
            user_sid=request.user_sid,
            executable_release=request.executable_release,
            acquisition_timestamp_utc=request.acquisition_timestamp_utc,
            max_runtime_seconds=request.max_runtime_seconds,
            launch_policy=request.launch_policy,
        )
        failure_stage = "START_PUBLICATION_FAILED"
        publication = publish_launch_lease_start(request.audit_root, start_record)
        failure_stage = "OWNERSHIP_CONSTRUCTION_FAILED"
        ownership = LaunchGuardOwnership(
            _LaunchGuardOwnershipState(
                api=native_api,
                handle=native.handle,
                audit_root=request.audit_root,
                start_record=start_record,
                start_publication=publication,
                context_release_input=request.context_release_input,
            )
        )
    except BaseException as exc:
        cleanup_errors: list[str] = []
        try:
            native_api.release(native.handle)
        except BaseException as cleanup_exc:
            cleanup_errors.append(type(cleanup_exc).__name__)
        try:
            native_api.close(native.handle)
        except BaseException as cleanup_exc:
            cleanup_errors.append(type(cleanup_exc).__name__)
        if not isinstance(exc, Exception):
            if cleanup_errors:
                exc.add_note(
                    f"launch-guard cleanup failures: {','.join(cleanup_errors)}"
                )
            raise
        suffix = f":CLEANUP_FAILED:{','.join(cleanup_errors)}" if cleanup_errors else ""
        return LaunchGuardAcquireResult(
            classification=LaunchGuardAcquisitionClassification.ERROR,
            mutex_name=mutex_name,
            acl_enforcement=acl_enforcement,
            ownership=None,
            native_error_code=None,
            diagnostic=f"{failure_stage}:{type(exc).__name__}{suffix}",
        )
    return LaunchGuardAcquireResult(
        classification=native.classification,
        mutex_name=mutex_name,
        acl_enforcement=acl_enforcement,
        ownership=ownership,
        native_error_code=native.native_error_code,
        diagnostic=(
            "ABANDONED_OWNER_MANUAL_REVIEW_REQUIRED"
            if native.classification
            is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
            else "ACQUIRED"
        ),
    )


def diagnostic_from_ownership(
    ownership: LaunchGuardOwnership,
) -> LaunchGuardDiagnostic:
    """Return sanitized read-only data; it grants no authority."""

    start = ownership.start_record
    release_publication = ownership._state.release_publication
    return LaunchGuardDiagnostic(
        mutex_name=start.mutex_name,
        process_id=start.process_id,
        process_creation_timestamp_utc=start.process_creation_timestamp_utc,
        boot_evidence=start.boot_evidence,
        user_sid=start.user_sid,
        lease_start=ownership.start_reference,
        lease_release=(
            None
            if release_publication is None
            else release_publication.artifact_reference
        ),
        released=ownership.released,
    )
