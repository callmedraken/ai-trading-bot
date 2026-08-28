"""C3 Windows containment, IPC, and exact parent-owned artifact handles."""

from __future__ import annotations

import ctypes
import os
import secrets
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol
from uuid import UUID

from trading_bot.market_data import MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES
from trading_bot.runtime.windows_authority import PRODUCTION_CAPTURE_OUTPUT_ROOT
from trading_bot.runtime.windows_effectful_capture_protocol import (
    MAX_C3_CHILD_REQUEST_BYTES,
    MAX_C3_CHILD_RESULT_BYTES,
)

JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_NO_WINDOW = 0x08000000
C3_REQUEST_HANDLE_ARGUMENT = "--c3-request-handle"
C3_RESULT_HANDLE_ARGUMENT = "--c3-result-handle"
C3_STAGING_HANDLE_ARGUMENT = "--c3-staging-handle"
C3_CREATE_PROCESS_FLAGS = (
    CREATE_SUSPENDED
    | EXTENDED_STARTUPINFO_PRESENT
    | CREATE_UNICODE_ENVIRONMENT
    | CREATE_NO_WINDOW
)
HANDLE_FLAG_INHERIT = 0x00000001
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
DELETE = 0x00010000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
CREATE_NEW = 1
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_OVERLAPPED = 0x40000000
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_ACCESS_INBOUND = 0x00000001
PIPE_ACCESS_OUTBOUND = 0x00000002
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
SECURITY_DESCRIPTOR_REVISION = 1
_C3_PIPE_SECURITY_SDDL = "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;OW)"
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_BROKEN_PIPE = 109
ERROR_PIPE_CONNECTED = 535
ERROR_IO_PENDING = 997
ERROR_IO_INCOMPLETE = 996
ERROR_OPERATION_ABORTED = 995
ERROR_NOT_FOUND = 1168
INVALID_SUSPEND_COUNT = 0xFFFFFFFF
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF
DUPLICATE_SAME_ACCESS = 0x00000002
FILE_ID_INFO_CLASS = 18
FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
FILE_DISPOSITION_INFO_CLASS = 4

C3_CHILD_REQUEST_DELIVERY_TIMEOUT_MS = 10_000
C3_CHILD_COMPLETION_TIMEOUT_MS = 120_000
C3_CHILD_OBSERVATION_SLICE_MS = 100
C3_CHILD_TERMINATION_TIMEOUT_MS = 10_000
C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS = 1_000

PRODUCTION_C3_RUNTIME_ROOT = r"F:\AITradingBot\runtime"
PRODUCTION_C3_PYTHON_EXECUTABLE = r"F:\AITradingBot\runtime\python.exe"
PRODUCTION_C3_CONTROLLED_TEMP_ROOT = r"F:\AITradingBot\temp"
PRODUCTION_C3_CHILD_MODULE = "trading_bot.runtime.windows_effectful_capture_child"
PRODUCTION_C3_CHILD_BASE_ARGUMENTS = ("-m", PRODUCTION_C3_CHILD_MODULE)


class WindowsEffectfulCaptureNativeError(RuntimeError):
    """C3 native containment failed without exposing native error text."""


class WindowsEffectfulCaptureNativeUnsupportedError(WindowsEffectfulCaptureNativeError):
    """The C3 native boundary is unavailable on this platform."""


class WindowsEffectfulCaptureProcessNotCreatedError(WindowsEffectfulCaptureNativeError):
    """Native state proves that no child process was created."""


class WindowsEffectfulCaptureProcessOutcomeUnknownError(
    WindowsEffectfulCaptureNativeError
):
    """Native state cannot support a definitive NOT_CREATED result."""


class C3NativeWaitStatus(StrEnum):
    IO_COMPLETED = "IO_COMPLETED"
    PROCESS_EXITED = "PROCESS_EXITED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


class C3ResultTransportStatus(StrEnum):
    COMPLETE = "COMPLETE"
    EMPTY = "EMPTY"
    OVERSIZED = "OVERSIZED"
    READ_FAILED = "READ_FAILED"


class C3ProcessOutcomeStatus(StrEnum):
    EXITED_ZERO = "EXITED_ZERO"
    EXITED_NONZERO = "EXITED_NONZERO"
    TIMED_OUT_TERMINATED = "TIMED_OUT_TERMINATED"
    WAIT_FAILED_TERMINATED = "WAIT_FAILED_TERMINATED"
    OBSERVATION_FAILED_TERMINATED = "OBSERVATION_FAILED_TERMINATED"
    TERMINATION_UNCONFIRMED = "TERMINATION_UNCONFIRMED"


class C3ParentCleanupStatus(StrEnum):
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class NativeFileIdentity:
    """Stable sanitized Windows file identity; never a raw HANDLE."""

    volume_serial_number: int
    file_id: bytes

    def __post_init__(self) -> None:
        if type(self.volume_serial_number) is not int or not (
            0 <= self.volume_serial_number < 1 << 64
        ):
            raise WindowsEffectfulCaptureNativeError("file volume identity is invalid")
        if type(self.file_id) is not bytes or len(self.file_id) != 16:
            raise WindowsEffectfulCaptureNativeError("native file identity is invalid")

    def canonical_evidence(self) -> dict[str, str]:
        return {
            "file_id": self.file_id.hex(),
            "volume_serial_number": f"{self.volume_serial_number:016x}",
        }


@dataclass(frozen=True, slots=True)
class NativeStagingObject:
    """Private master/child handle set for one exclusively created staging file."""

    parent_handle: int
    child_write_handle: int
    identity: NativeFileIdentity
    path: str
    child_access_mask: int = GENERIC_WRITE
    parent_inheritable: bool = False

    def __post_init__(self) -> None:
        _handle(self.parent_handle, "parent staging handle")
        _handle(self.child_write_handle, "child staging handle")
        if self.parent_handle == self.child_write_handle:
            raise WindowsEffectfulCaptureNativeError(
                "parent and child staging handles must be distinct"
            )
        if type(self.identity) is not NativeFileIdentity:
            raise WindowsEffectfulCaptureNativeError("staging identity is invalid")
        _windows_path(self.path, "staging path")
        if self.child_access_mask != GENERIC_WRITE:
            raise WindowsEffectfulCaptureNativeError(
                "child staging authority must be write-only"
            )
        if self.parent_inheritable is not False:
            raise WindowsEffectfulCaptureNativeError(
                "parent staging authority must be noninheritable"
            )


@dataclass(frozen=True, slots=True)
class NativeOpenedArtifact:
    handle: int
    identity: NativeFileIdentity

    def __post_init__(self) -> None:
        _handle(self.handle, "opened artifact handle")
        if type(self.identity) is not NativeFileIdentity:
            raise WindowsEffectfulCaptureNativeError("opened identity is invalid")


@dataclass(frozen=True, slots=True)
class NativeOverlappedCompletion:
    transferred: int
    payload: bytes
    eof: bool


@dataclass(frozen=True, slots=True)
class NativeC3ChildObservation:
    result_transport: C3ResultTransportStatus
    process_outcome: C3ProcessOutcomeStatus
    parent_cleanup: C3ParentCleanupStatus
    result_payload: bytes | None

    def __post_init__(self) -> None:
        if type(self.result_transport) is not C3ResultTransportStatus:
            raise TypeError("result transport status is invalid")
        if type(self.process_outcome) is not C3ProcessOutcomeStatus:
            raise TypeError("process outcome status is invalid")
        if type(self.parent_cleanup) is not C3ParentCleanupStatus:
            raise TypeError("parent cleanup status is invalid")
        if self.result_transport is C3ResultTransportStatus.COMPLETE:
            if type(self.result_payload) is not bytes or not self.result_payload:
                raise TypeError("complete result payload is invalid")
        elif self.result_payload is not None:
            raise TypeError("untrusted result transport cannot retain payload")


@dataclass(frozen=True, slots=True)
class NativePipePair:
    read_handle: int
    write_handle: int

    def __post_init__(self) -> None:
        _handle(self.read_handle, "pipe read handle")
        _handle(self.write_handle, "pipe write handle")
        if self.read_handle == self.write_handle:
            raise WindowsEffectfulCaptureNativeError("pipe handles must be distinct")


@dataclass(frozen=True, slots=True)
class NativeCreatedProcess:
    process_id: int
    thread_id: int
    process_handle: int
    primary_thread_handle: int

    def __post_init__(self) -> None:
        if type(self.process_id) is not int or self.process_id <= 0:
            raise WindowsEffectfulCaptureNativeError("process ID is invalid")
        if type(self.thread_id) is not int or self.thread_id <= 0:
            raise WindowsEffectfulCaptureNativeError("thread ID is invalid")
        _handle(self.process_handle, "process handle")
        _handle(self.primary_thread_handle, "primary thread handle")
        if self.process_handle == self.primary_thread_handle:
            raise WindowsEffectfulCaptureNativeError("process handles must be distinct")


class WindowsEffectfulCaptureNativeApi(Protocol):
    def create_job_object(self) -> int: ...
    def set_job_limits(self, job_handle: int) -> None: ...
    def create_request_pipe(self, buffer_size: int) -> NativePipePair: ...
    def create_result_pipe(self, buffer_size: int) -> NativePipePair: ...
    def set_handle_inheritable(self, handle: int, inheritable: bool) -> None: ...
    def create_staging_file(self, path: str) -> NativeStagingObject: ...
    def get_file_identity(self, handle: int) -> NativeFileIdentity: ...
    def read_artifact_file(self, handle: int, max_bytes: int) -> bytes: ...
    def reject_casefold_collisions(
        self, directory: str, names: tuple[str, ...]
    ) -> None: ...
    def publish_staging_link(
        self, staging_handle: int, staging_path: str, final_path: str
    ) -> None: ...
    def open_final_artifact(self, path: str) -> NativeOpenedArtifact: ...
    def delete_staging_link(self, staging_handle: int) -> None: ...

    def create_suspended_process(
        self,
        *,
        application_name: str,
        arguments: tuple[str, ...],
        environment: Mapping[str, str],
        current_directory: str,
        inherited_handles: tuple[int, int, int],
        job_handle: int,
        creation_flags: int,
        inherit_handles: bool,
    ) -> NativeCreatedProcess: ...

    def begin_overlapped_write(self, handle: int, payload: bytes) -> object: ...
    def begin_overlapped_read(self, handle: int, max_bytes: int) -> object: ...

    def wait_overlapped_or_process(
        self, operation: object, process_handle: int | None, timeout_ms: int
    ) -> C3NativeWaitStatus: ...

    def complete_overlapped(self, operation: object) -> NativeOverlappedCompletion: ...

    def cancel_and_settle_overlapped(
        self, operation: object, timeout_ms: int
    ) -> bool: ...

    def quarantine_overlapped(self, operation: object) -> None: ...
    def wait_process(
        self, process_handle: int, timeout_ms: int
    ) -> C3NativeWaitStatus: ...
    def get_exit_code_process(self, process_handle: int) -> int: ...
    def terminate_job_object(self, job_handle: int) -> None: ...
    def resume_thread(self, thread_handle: int) -> int: ...
    def close_handle(self, handle: int) -> None: ...


class WindowsEffectfulCaptureChildIoApi(Protocol):
    """Exact synchronous Win32 I/O used by the contained C3 child."""

    def read_file(self, handle: int, max_bytes: int) -> bytes: ...
    def write_file(self, handle: int, payload: bytes) -> int: ...
    def flush_file_buffers(self, handle: int) -> None: ...
    def close_handle(self, handle: int) -> None: ...


class SuspendedCaptureChild:
    """Private live handles for one contained process still suspended at entry."""

    __slots__ = (
        "_api",
        "_closed",
        "_job_handle",
        "_primary_thread_handle",
        "_process_handle",
        "_request_attempted",
        "_request_delivered",
        "_request_writer",
        "_result_reader",
        "_resume_attempted",
        "_staging_handle",
        "_staging_identity",
        "_staging_path",
        "process_id",
        "thread_id",
    )

    def __init__(
        self,
        api: WindowsEffectfulCaptureNativeApi,
        process: NativeCreatedProcess,
        handles: tuple[int, int, int, int],
        *,
        staging_identity: NativeFileIdentity,
        staging_path: str,
        _issuer: object,
    ) -> None:
        if _issuer is not _SUSPENDED_CHILD_ISSUER:
            raise TypeError("suspended child must be issued by C3 native containment")
        if type(process) is not NativeCreatedProcess:
            raise TypeError("native process result is invalid")
        request_writer, result_reader, staging_handle, job_handle = handles
        retained = (
            request_writer,
            result_reader,
            staging_handle,
            process.primary_thread_handle,
            process.process_handle,
            job_handle,
        )
        for value in retained:
            _handle(value, "retained native handle")
        if len(set(retained)) != len(retained):
            raise WindowsEffectfulCaptureNativeError(
                "retained handles must be distinct"
            )
        self._api = api
        self._request_writer = request_writer
        self._result_reader = result_reader
        self._staging_handle = staging_handle
        self._staging_identity = staging_identity
        self._staging_path = _windows_path(staging_path, "staging path")
        self._primary_thread_handle = process.primary_thread_handle
        self._process_handle = process.process_handle
        self._job_handle = job_handle
        self.process_id = process.process_id
        self.thread_id = process.thread_id
        self._closed = False
        self._request_attempted = False
        self._request_delivered = False
        self._resume_attempted = False

    def __repr__(self) -> str:
        return (
            "SuspendedCaptureChild("
            f"process_id={self.process_id}, closed={self._closed})"
        )

    def __copy__(self) -> object:
        raise TypeError("SuspendedCaptureChild cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("SuspendedCaptureChild cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("SuspendedCaptureChild cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("SuspendedCaptureChild cannot be pickled")

    @property
    def closed(self) -> bool:
        return self._closed

    def _retained_staging(self) -> tuple[int, NativeFileIdentity, str]:
        handle = self._staging_handle
        if handle is None or self._closed:
            raise WindowsEffectfulCaptureNativeError(
                "parent staging authority is unavailable"
            )
        return handle, self._staging_identity, self._staging_path

    def _release_staging_handle(self) -> int:
        handle = self._staging_handle
        if handle is None:
            raise WindowsEffectfulCaptureNativeError(
                "parent staging authority is unavailable"
            )
        self._staging_handle = None
        return handle

    def _write_request_and_close(self, payload: bytes) -> None:
        if self._closed:
            raise WindowsEffectfulCaptureNativeError("suspended child is closed")
        if self._request_attempted:
            raise WindowsEffectfulCaptureNativeError(
                "child request delivery was already attempted"
            )
        if type(payload) is not bytes or not payload:
            raise WindowsEffectfulCaptureNativeError("child request payload is invalid")
        if len(payload) > MAX_C3_CHILD_REQUEST_BYTES:
            raise WindowsEffectfulCaptureNativeError(
                "child request exceeds its byte bound"
            )
        self._request_attempted = True
        request_writer = self._request_writer
        if request_writer is None:
            raise WindowsEffectfulCaptureNativeError(
                "child request writer is unavailable"
            )
        offset = 0
        deadline_ns = time.monotonic_ns() + (
            C3_CHILD_REQUEST_DELIVERY_TIMEOUT_MS * 1_000_000
        )
        operation: object | None = None
        quarantined = False
        try:
            while offset < len(payload):
                operation = self._api.begin_overlapped_write(
                    request_writer, payload[offset:]
                )
                remaining_ms = _remaining_timeout_ms(deadline_ns)
                if remaining_ms <= 0:
                    raise WindowsEffectfulCaptureNativeError(
                        "child request delivery timed out"
                    )
                status = self._api.wait_overlapped_or_process(
                    operation, None, remaining_ms
                )
                if status is not C3NativeWaitStatus.IO_COMPLETED:
                    raise WindowsEffectfulCaptureNativeError(
                        "child request delivery timed out"
                        if status is C3NativeWaitStatus.TIMEOUT
                        else "child request delivery failed"
                    )
                completion = self._api.complete_overlapped(operation)
                operation = None
                written = completion.transferred
                if (
                    type(written) is not int
                    or written <= 0
                    or written > len(payload) - offset
                    or completion.payload
                    or completion.eof
                ):
                    raise WindowsEffectfulCaptureNativeError(
                        "child request write result is invalid"
                    )
                offset += written
        except Exception:
            if operation is not None:
                try:
                    settled = self._api.cancel_and_settle_overlapped(
                        operation, C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS
                    )
                except Exception:
                    settled = False
                if not settled:
                    try:
                        self._api.quarantine_overlapped(operation)
                    except Exception:
                        pass
                    finally:
                        quarantined = True
                        self._request_writer = None
            if not quarantined:
                self._request_writer = None
                try:
                    self._api.close_handle(request_writer)
                except Exception:
                    pass
            try:
                self._close_all_retained()
            except Exception:
                pass
            raise WindowsEffectfulCaptureNativeError(
                "child request delivery failed"
            ) from None

        self._request_writer = None
        try:
            self._api.close_handle(request_writer)
        except Exception:
            try:
                self._close_all_retained()
            except Exception:
                pass
            raise WindowsEffectfulCaptureNativeError(
                "child request delivery failed"
            ) from None
        self._request_delivered = True

    def _resume_once(self) -> None:
        if self._closed:
            raise WindowsEffectfulCaptureNativeError("suspended child is closed")
        if self._resume_attempted:
            raise WindowsEffectfulCaptureNativeError(
                "child resume was already attempted"
            )
        if not self._request_delivered:
            raise WindowsEffectfulCaptureNativeError(
                "child request was not completely delivered"
            )
        self._resume_attempted = True
        thread_handle = self._primary_thread_handle
        if thread_handle is None:
            raise WindowsEffectfulCaptureNativeError(
                "primary thread handle is unavailable"
            )
        try:
            previous_suspend_count = self._api.resume_thread(thread_handle)
        except Exception:
            raise WindowsEffectfulCaptureNativeError("ResumeThread failed") from None
        if type(previous_suspend_count) is not int:
            raise WindowsEffectfulCaptureNativeError(
                "ResumeThread returned an invalid suspend count"
            )
        if previous_suspend_count == INVALID_SUSPEND_COUNT:
            raise WindowsEffectfulCaptureNativeError("ResumeThread failed")
        if previous_suspend_count != 1:
            raise WindowsEffectfulCaptureNativeError(
                "ResumeThread previous suspend count was not one"
            )

    def _observe_after_resume(self) -> NativeC3ChildObservation:
        if self._closed:
            raise WindowsEffectfulCaptureNativeError("suspended child is closed")
        if not self._resume_attempted:
            raise WindowsEffectfulCaptureNativeError("child was not resumed")
        result_handle = self._result_reader
        process_handle = self._process_handle
        job_handle = self._job_handle
        if result_handle is None or process_handle is None or job_handle is None:
            raise WindowsEffectfulCaptureNativeError(
                "child observation handles are unavailable"
            )

        payload = bytearray()
        transport: C3ResultTransportStatus | None = None
        process_outcome: C3ProcessOutcomeStatus | None = None
        process_exited = False
        operation: object | None = None
        quarantined = False
        observation_failed = False
        wait_failed = False
        deadline_ns = time.monotonic_ns() + C3_CHILD_COMPLETION_TIMEOUT_MS * 1_000_000

        try:
            while transport is None or not process_exited:
                if transport is None and operation is None:
                    operation = self._api.begin_overlapped_read(
                        result_handle,
                        MAX_C3_CHILD_RESULT_BYTES + 1 - len(payload),
                    )
                remaining_ms = _remaining_timeout_ms(deadline_ns)
                if remaining_ms <= 0:
                    break
                wait_ms = min(C3_CHILD_OBSERVATION_SLICE_MS, remaining_ms)
                if operation is not None:
                    status = self._api.wait_overlapped_or_process(
                        operation,
                        None if process_exited else process_handle,
                        wait_ms,
                    )
                else:
                    status = self._api.wait_process(process_handle, wait_ms)

                if status is C3NativeWaitStatus.IO_COMPLETED:
                    if operation is None:
                        observation_failed = True
                        break
                    completion = self._api.complete_overlapped(operation)
                    operation = None
                    if completion.payload:
                        payload.extend(completion.payload)
                    if len(payload) > MAX_C3_CHILD_RESULT_BYTES:
                        transport = C3ResultTransportStatus.OVERSIZED
                        break
                    if completion.eof:
                        transport = (
                            C3ResultTransportStatus.COMPLETE
                            if payload
                            else C3ResultTransportStatus.EMPTY
                        )
                elif status is C3NativeWaitStatus.PROCESS_EXITED:
                    exit_code = self._api.get_exit_code_process(process_handle)
                    process_exited = True
                    process_outcome = (
                        C3ProcessOutcomeStatus.EXITED_ZERO
                        if exit_code == 0
                        else C3ProcessOutcomeStatus.EXITED_NONZERO
                    )
                elif status is C3NativeWaitStatus.FAILED:
                    observation_failed = True
                    wait_failed = True
                    break
                elif status is not C3NativeWaitStatus.TIMEOUT:
                    observation_failed = True
                    wait_failed = True
                    break
        except Exception:
            observation_failed = True

        timed_out = (
            not observation_failed
            and (transport is None or not process_exited)
            and _remaining_timeout_ms(deadline_ns) <= 0
        )
        if operation is not None:
            try:
                settled = self._api.cancel_and_settle_overlapped(
                    operation, C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS
                )
            except Exception:
                settled = False
            if not settled:
                try:
                    self._api.quarantine_overlapped(operation)
                except Exception:
                    pass
                quarantined = True
                self._result_reader = None

        if transport is None:
            transport = C3ResultTransportStatus.READ_FAILED
        if transport in (
            C3ResultTransportStatus.OVERSIZED,
            C3ResultTransportStatus.READ_FAILED,
        ):
            observation_failed = True

        if not process_exited:
            terminated = False
            try:
                self._api.terminate_job_object(job_handle)
                terminated = True
            except Exception:
                terminated = False
            if terminated:
                try:
                    termination_wait = self._api.wait_process(
                        process_handle, C3_CHILD_TERMINATION_TIMEOUT_MS
                    )
                except Exception:
                    termination_wait = C3NativeWaitStatus.FAILED
                if termination_wait is C3NativeWaitStatus.PROCESS_EXITED:
                    process_exited = True
                    if timed_out:
                        process_outcome = C3ProcessOutcomeStatus.TIMED_OUT_TERMINATED
                    elif observation_failed:
                        process_outcome = (
                            C3ProcessOutcomeStatus.WAIT_FAILED_TERMINATED
                            if wait_failed
                            else C3ProcessOutcomeStatus.OBSERVATION_FAILED_TERMINATED
                        )
            if not process_exited:
                process_outcome = C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED

        if process_outcome is None:
            process_outcome = C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED

        cleanup_failed = False
        for attribute in (
            "_result_reader",
            "_primary_thread_handle",
            "_process_handle",
            "_job_handle",
        ):
            handle = getattr(self, attribute)
            if handle is None:
                continue
            setattr(self, attribute, None)
            try:
                self._api.close_handle(handle)
            except Exception:
                cleanup_failed = True
        parent_cleanup = (
            C3ParentCleanupStatus.UNRESOLVED
            if quarantined
            or process_outcome is C3ProcessOutcomeStatus.TERMINATION_UNCONFIRMED
            else C3ParentCleanupStatus.FAILED
            if cleanup_failed
            else C3ParentCleanupStatus.COMPLETE
        )
        trusted_payload = (
            bytes(payload) if transport is C3ResultTransportStatus.COMPLETE else None
        )
        return NativeC3ChildObservation(
            result_transport=transport,
            process_outcome=process_outcome,
            parent_cleanup=parent_cleanup,
            result_payload=trusted_payload,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._close_all_retained()

    def _close_all_retained(self) -> None:
        if self._closed:
            return
        self._closed = True
        failed = False
        for attribute in (
            "_request_writer",
            "_result_reader",
            "_staging_handle",
            "_primary_thread_handle",
            "_process_handle",
            "_job_handle",
        ):
            handle = getattr(self, attribute)
            if handle is None:
                continue
            setattr(self, attribute, None)
            try:
                self._api.close_handle(handle)
            except Exception:
                failed = True
        if failed:
            raise WindowsEffectfulCaptureNativeError(
                "native suspended-child cleanup failed"
            ) from None


_SUSPENDED_CHILD_ISSUER = object()


def deliver_canonical_child_request(
    child: SuspendedCaptureChild, payload: bytes
) -> None:
    """Completely write one bounded request and close the parent writer."""

    if type(child) is not SuspendedCaptureChild:
        raise TypeError("child request delivery requires SuspendedCaptureChild")
    child._write_request_and_close(payload)


def resume_suspended_capture_child(child: SuspendedCaptureChild) -> None:
    """Attempt exactly one resume and require previous suspend count one."""

    if type(child) is not SuspendedCaptureChild:
        raise TypeError("resume requires SuspendedCaptureChild")
    child._resume_once()


def observe_resumed_capture_child(
    child: SuspendedCaptureChild,
) -> NativeC3ChildObservation:
    """Perform the fixed bounded C3-C3B parent observation and cleanup."""

    if type(child) is not SuspendedCaptureChild:
        raise TypeError("observation requires SuspendedCaptureChild")
    return child._observe_after_resume()


def build_c3_child_environment(
    parent_environment: Mapping[str, str],
    controlled_temp_directory: str,
) -> dict[str, str]:
    """Build exactly the frozen five-entry C3 v1 child environment."""

    if not isinstance(parent_environment, Mapping):
        raise WindowsEffectfulCaptureNativeError("parent environment must be a mapping")
    temp = _windows_path(controlled_temp_directory, "controlled TEMP directory")
    folded: dict[str, str] = {}
    for key, value in parent_environment.items():
        if type(key) is not str or type(value) is not str:
            raise WindowsEffectfulCaptureNativeError("parent environment must be text")
        upper = key.upper()
        if upper in folded:
            raise WindowsEffectfulCaptureNativeError(
                "parent environment has case-insensitive duplicate names"
            )
        folded[upper] = value
    try:
        system_root = _windows_path(folded["SYSTEMROOT"], "SystemRoot")
        windir = _windows_path(folded["WINDIR"], "WINDIR")
    except KeyError:
        raise WindowsEffectfulCaptureNativeError(
            "required Windows runtime environment is absent"
        ) from None
    return {
        "SystemRoot": system_root,
        "WINDIR": windir,
        "TEMP": temp,
        "TMP": temp,
        "PYTHONUTF8": "1",
    }


def create_suspended_capture_child_for_test(
    *,
    application_name: str,
    arguments: tuple[str, ...],
    current_directory: str,
    controlled_temp_directory: str,
    staging_path: str,
    parent_environment: Mapping[str, str],
    native_api: WindowsEffectfulCaptureNativeApi,
) -> SuspendedCaptureChild:
    """Injected C3-C1 seam; production path selection is deliberately absent."""

    required = (
        "create_job_object",
        "set_job_limits",
        "create_request_pipe",
        "create_result_pipe",
        "set_handle_inheritable",
        "create_staging_file",
        "get_file_identity",
        "read_artifact_file",
        "reject_casefold_collisions",
        "publish_staging_link",
        "open_final_artifact",
        "delete_staging_link",
        "create_suspended_process",
        "begin_overlapped_write",
        "begin_overlapped_read",
        "wait_overlapped_or_process",
        "complete_overlapped",
        "cancel_and_settle_overlapped",
        "quarantine_overlapped",
        "wait_process",
        "get_exit_code_process",
        "terminate_job_object",
        "resume_thread",
        "close_handle",
    )
    if not all(callable(getattr(native_api, name, None)) for name in required):
        raise TypeError("test native API is invalid")
    return _create_suspended_capture_child(
        application_name=application_name,
        arguments=arguments,
        current_directory=current_directory,
        controlled_temp_directory=controlled_temp_directory,
        staging_path=staging_path,
        parent_environment=parent_environment,
        native_api=native_api,
    )


def create_production_suspended_capture_child(
    reservation_id: str,
    native_api: CtypesWindowsEffectfulCaptureNativeApi,
) -> SuspendedCaptureChild:
    """Create the fixed deployed C3 child through the exact ctypes adapter."""

    if type(native_api) is not CtypesWindowsEffectfulCaptureNativeApi:
        raise TypeError("production C3 containment requires the exact ctypes adapter")
    try:
        reservation_id = str(UUID(str(reservation_id)))
    except (AttributeError, TypeError, ValueError):
        raise WindowsEffectfulCaptureNativeError(
            "production C3 reservation identity is invalid"
        ) from None
    staging_path = str(
        PureWindowsPath(str(PRODUCTION_CAPTURE_OUTPUT_ROOT))
        / f".c3-capture-{reservation_id}.staging"
    )
    return _create_suspended_capture_child(
        application_name=PRODUCTION_C3_PYTHON_EXECUTABLE,
        arguments=PRODUCTION_C3_CHILD_BASE_ARGUMENTS,
        current_directory=PRODUCTION_C3_RUNTIME_ROOT,
        controlled_temp_directory=PRODUCTION_C3_CONTROLLED_TEMP_ROOT,
        staging_path=staging_path,
        parent_environment=os.environ,
        native_api=native_api,
    )


def _create_suspended_capture_child(
    *,
    application_name: str,
    arguments: tuple[str, ...],
    current_directory: str,
    controlled_temp_directory: str,
    staging_path: str,
    parent_environment: Mapping[str, str],
    native_api: WindowsEffectfulCaptureNativeApi,
) -> SuspendedCaptureChild:
    application = _windows_path(application_name, "application name")
    current = _windows_path(current_directory, "current directory")
    staging = _windows_path(staging_path, "staging path")
    args = _arguments(arguments)
    environment = build_c3_child_environment(
        parent_environment, controlled_temp_directory
    )

    acquired: list[int] = []
    job: int | None = None
    process_creation_entered = False
    process_created = False
    try:
        job = _handle(native_api.create_job_object(), "job handle")
        acquired.append(job)
        native_api.set_job_limits(job)

        request = native_api.create_request_pipe(MAX_C3_CHILD_REQUEST_BYTES)
        if type(request) is not NativePipePair:
            raise WindowsEffectfulCaptureNativeError("request pipe result is invalid")
        acquired.extend((request.read_handle, request.write_handle))

        result = native_api.create_result_pipe(MAX_C3_CHILD_RESULT_BYTES)
        if type(result) is not NativePipePair:
            raise WindowsEffectfulCaptureNativeError("result pipe result is invalid")
        acquired.extend((result.read_handle, result.write_handle))

        staging_object = native_api.create_staging_file(staging)
        if type(staging_object) is not NativeStagingObject:
            raise WindowsEffectfulCaptureNativeError("staging object result is invalid")
        staging_handle = staging_object.parent_handle
        child_staging_handle = staging_object.child_write_handle
        acquired.extend((staging_handle, child_staging_handle))
        child_handles = (
            request.read_handle,
            result.write_handle,
            child_staging_handle,
        )
        if len(set(child_handles)) != 3:
            raise WindowsEffectfulCaptureNativeError("child handles must be distinct")

        bootstrap_args = (*args, *_handle_bootstrap_arguments(child_handles))
        process_creation_entered = True
        process = native_api.create_suspended_process(
            application_name=application,
            arguments=bootstrap_args,
            environment=environment,
            current_directory=current,
            inherited_handles=child_handles,
            job_handle=job,
            creation_flags=C3_CREATE_PROCESS_FLAGS,
            inherit_handles=True,
        )
        if type(process) is not NativeCreatedProcess:
            raise WindowsEffectfulCaptureNativeError(
                "process creation result is invalid"
            )
        process_created = True
        acquired.extend((process.process_handle, process.primary_thread_handle))

        for child_pipe_handle in (request.read_handle, result.write_handle):
            native_api.close_handle(child_pipe_handle)
            acquired.remove(child_pipe_handle)
        native_api.close_handle(child_staging_handle)
        acquired.remove(child_staging_handle)

        child = SuspendedCaptureChild(
            native_api,
            process,
            (request.write_handle, result.read_handle, staging_handle, job),
            staging_identity=staging_object.identity,
            staging_path=staging_object.path,
            _issuer=_SUSPENDED_CHILD_ISSUER,
        )
        for transferred in (
            request.write_handle,
            result.read_handle,
            staging_handle,
            process.primary_thread_handle,
            process.process_handle,
            job,
        ):
            acquired.remove(transferred)
        return child
    except Exception as error:
        cleanup_failed = False
        ordered = [value for value in reversed(acquired) if value != job]
        if job is not None and job in acquired:
            ordered.append(job)
        for handle in ordered:
            try:
                native_api.close_handle(handle)
            except Exception:
                cleanup_failed = True
        if process_created or (
            process_creation_entered
            and not isinstance(error, WindowsEffectfulCaptureProcessNotCreatedError)
        ):
            raise WindowsEffectfulCaptureProcessOutcomeUnknownError(
                "native process creation outcome is not safely persistable"
            ) from None
        if cleanup_failed:
            raise WindowsEffectfulCaptureProcessNotCreatedError(
                "native containment failed before child creation; "
                "cleanup was incomplete"
            ) from None
        if isinstance(error, WindowsEffectfulCaptureProcessNotCreatedError):
            raise
        if isinstance(error, WindowsEffectfulCaptureNativeError):
            raise WindowsEffectfulCaptureProcessNotCreatedError(
                "native containment failed before child creation"
            ) from None
        raise WindowsEffectfulCaptureProcessNotCreatedError(
            "native containment failed before child creation"
        ) from None


@dataclass(slots=True, repr=False)
class _C3OverlappedOperation:
    owner: CtypesWindowsEffectfulCaptureNativeApi
    handle: int
    event_handle: int
    overlapped: object
    buffer: object
    operation_type: str
    requested: int
    immediate_eof: bool = False
    settled: bool = False
    quarantined: bool = False

    def __repr__(self) -> str:
        return "C3OverlappedOperation(<private>)"

    def __reduce__(self) -> object:
        raise TypeError("C3 overlapped operation cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3 overlapped operation cannot be pickled")


_C3_OVERLAPPED_QUARANTINE: list[_C3OverlappedOperation] = []
_C3_OVERLAPPED_QUARANTINE_LOCK = threading.Lock()


class CtypesWindowsEffectfulCaptureNativeApi:
    """ctypes implementation of the exact C3-specific process topology."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsEffectfulCaptureNativeUnsupportedError(
                "C3 native containment is supported only on Windows"
            )
        from ctypes import wintypes

        class SECURITY_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("nLength", wintypes.DWORD),
                ("lpSecurityDescriptor", ctypes.c_void_p),
                ("bInheritHandle", wintypes.BOOL),
            ]

        class STARTUPINFOW(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD),
                ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD),
                ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD),
                ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE),
            ]

        class STARTUPINFOEXW(ctypes.Structure):
            _fields_ = [
                ("StartupInfo", STARTUPINFOW),
                ("lpAttributeList", ctypes.c_void_p),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess", wintypes.HANDLE),
                ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD),
            ]

        class OVERLAPPED_OFFSET(ctypes.Structure):
            _fields_ = [
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
            ]

        class OVERLAPPED_UNION(ctypes.Union):
            _fields_ = [
                ("offset", OVERLAPPED_OFFSET),
                ("Pointer", ctypes.c_void_p),
            ]

        class OVERLAPPED(ctypes.Structure):
            _anonymous_ = ("union",)
            _fields_ = [
                ("Internal", ctypes.c_size_t),
                ("InternalHigh", ctypes.c_size_t),
                ("union", OVERLAPPED_UNION),
                ("hEvent", wintypes.HANDLE),
            ]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class FILE_ID_128(ctypes.Structure):
            _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

        class FILE_ID_INFO(ctypes.Structure):
            _fields_ = [
                ("VolumeSerialNumber", ctypes.c_ulonglong),
                ("FileId", FILE_ID_128),
            ]

        class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
            _fields_ = [
                ("FileAttributes", wintypes.DWORD),
                ("ReparseTag", wintypes.DWORD),
            ]

        class FILE_DISPOSITION_INFO(ctypes.Structure):
            _fields_ = [("DeleteFile", wintypes.BOOL)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.CreateNamedPipeW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(SECURITY_ATTRIBUTES),
        ]
        k32.CreateNamedPipeW.restype = wintypes.HANDLE
        k32.ConnectNamedPipe.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(OVERLAPPED),
        ]
        k32.ConnectNamedPipe.restype = wintypes.BOOL
        k32.SetHandleInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        k32.SetHandleInformation.restype = wintypes.BOOL
        k32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateHardLinkW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(SECURITY_ATTRIBUTES),
        ]
        k32.CreateHardLinkW.restype = wintypes.BOOL
        k32.GetCurrentProcess.argtypes = []
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.DuplicateHandle.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        k32.DuplicateHandle.restype = wintypes.BOOL
        k32.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        k32.SetFilePointerEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        k32.SetFilePointerEx.restype = wintypes.BOOL
        k32.SetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k32.SetFileInformationByHandle.restype = wintypes.BOOL
        k32.InitializeProcThreadAttributeList.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        k32.UpdateProcThreadAttribute.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        k32.UpdateProcThreadAttribute.restype = wintypes.BOOL
        k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        k32.DeleteProcThreadAttributeList.restype = None
        k32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(STARTUPINFOEXW),
            ctypes.POINTER(PROCESS_INFORMATION),
        ]
        k32.CreateProcessW.restype = wintypes.BOOL
        k32.WriteFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(OVERLAPPED),
        ]
        k32.WriteFile.restype = wintypes.BOOL
        k32.ReadFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(OVERLAPPED),
        ]
        k32.ReadFile.restype = wintypes.BOOL
        k32.CreateEventW.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        k32.CreateEventW.restype = wintypes.HANDLE
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD
        k32.WaitForMultipleObjects.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        k32.WaitForMultipleObjects.restype = wintypes.DWORD
        k32.GetOverlappedResult.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(OVERLAPPED),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.BOOL,
        ]
        k32.GetOverlappedResult.restype = wintypes.BOOL
        k32.CancelIoEx.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(OVERLAPPED),
        ]
        k32.CancelIoEx.restype = wintypes.BOOL
        k32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        k32.GetExitCodeProcess.restype = wintypes.BOOL
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.ResumeThread.argtypes = [wintypes.HANDLE]
        k32.ResumeThread.restype = wintypes.DWORD
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        k32.LocalFree.argtypes = [ctypes.c_void_p]
        k32.LocalFree.restype = ctypes.c_void_p
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
            wintypes.BOOL
        )
        self._k32 = k32
        self._advapi32 = advapi32
        self._w = wintypes
        self._sa = SECURITY_ATTRIBUTES
        self._startup = STARTUPINFOEXW
        self._pi = PROCESS_INFORMATION
        self._limits = EXTENDED_LIMIT
        self._overlapped = OVERLAPPED
        self._file_id_info = FILE_ID_INFO
        self._file_attribute_tag_info = FILE_ATTRIBUTE_TAG_INFO
        self._file_disposition_info = FILE_DISPOSITION_INFO

    def create_job_object(self) -> int:
        value = self._k32.CreateJobObjectW(None, None)
        if not value:
            raise _native_error("CreateJobObjectW")
        return _native_handle(value, "job handle")

    def set_job_limits(self, job_handle: int) -> None:
        limits = self._limits()
        limits.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        )
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        if not self._k32.SetInformationJobObject(
            self._w.HANDLE(_handle(job_handle, "job handle")),
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            raise _native_error("SetInformationJobObject")

    def create_request_pipe(self, buffer_size: int) -> NativePipePair:
        return self._create_named_pipe_pair(
            buffer_size=buffer_size,
            server_access=PIPE_ACCESS_OUTBOUND,
            client_access=GENERIC_READ,
        )

    def create_result_pipe(self, buffer_size: int) -> NativePipePair:
        return self._create_named_pipe_pair(
            buffer_size=buffer_size,
            server_access=PIPE_ACCESS_INBOUND,
            client_access=GENERIC_WRITE,
        )

    def _create_named_pipe_pair(
        self, *, buffer_size: int, server_access: int, client_access: int
    ) -> NativePipePair:
        if type(buffer_size) is not int or buffer_size <= 0:
            raise WindowsEffectfulCaptureNativeError("pipe bound is invalid")
        if server_access not in (PIPE_ACCESS_INBOUND, PIPE_ACCESS_OUTBOUND):
            raise WindowsEffectfulCaptureNativeError("pipe direction is invalid")
        name = rf"\\.\pipe\ai-trading-bot-c3-{secrets.token_hex(32)}"
        descriptor = ctypes.c_void_p()
        if not self._advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            _C3_PIPE_SECURITY_SDDL,
            SECURITY_DESCRIPTOR_REVISION,
            ctypes.byref(descriptor),
            None,
        ):
            raise _native_error("ConvertStringSecurityDescriptorToSecurityDescriptorW")
        try:
            server_sa = self._sa(ctypes.sizeof(self._sa), descriptor.value, False)
            server_value = self._k32.CreateNamedPipeW(
                name,
                server_access | FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE,
                PIPE_TYPE_BYTE
                | PIPE_READMODE_BYTE
                | PIPE_WAIT
                | PIPE_REJECT_REMOTE_CLIENTS,
                1,
                buffer_size if server_access == PIPE_ACCESS_OUTBOUND else 0,
                buffer_size if server_access == PIPE_ACCESS_INBOUND else 0,
                0,
                ctypes.byref(server_sa),
            )
            create_error = ctypes.get_last_error()
        finally:
            self._k32.LocalFree(descriptor)
        server = _native_handle(server_value, "named pipe server", allow_invalid=True)
        if server == ctypes.c_void_p(-1).value:
            raise _native_error("CreateNamedPipeW", create_error)
        client_sa = self._sa(ctypes.sizeof(self._sa), None, True)
        client_value = self._k32.CreateFileW(
            name,
            client_access,
            0,
            ctypes.byref(client_sa),
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        client = _native_handle(client_value, "named pipe client", allow_invalid=True)
        if client == ctypes.c_void_p(-1).value:
            client_error = ctypes.get_last_error()
            try:
                self.close_handle(server)
            finally:
                raise _native_error("CreateFileW(named pipe)", client_error)
        event_value = self._k32.CreateEventW(None, True, False, None)
        event_handle = _native_handle(event_value, "pipe connection event")
        connect_overlapped = self._overlapped()
        connect_overlapped.hEvent = self._w.HANDLE(event_handle)
        ctypes.set_last_error(0)
        connected = self._k32.ConnectNamedPipe(
            self._w.HANDLE(server), ctypes.byref(connect_overlapped)
        )
        connect_error = ctypes.get_last_error()
        if connected or connect_error == ERROR_PIPE_CONNECTED:
            self.close_handle(event_handle)
        elif connect_error == ERROR_IO_PENDING:
            operation = _C3OverlappedOperation(
                owner=self,
                handle=server,
                event_handle=event_handle,
                overlapped=connect_overlapped,
                buffer=ctypes.create_string_buffer(1),
                operation_type="CONNECT",
                requested=0,
            )
            try:
                settled = self.cancel_and_settle_overlapped(
                    operation, C3_OVERLAPPED_CANCEL_SETTLEMENT_TIMEOUT_MS
                )
            except Exception:
                settled = False
            if not settled:
                try:
                    self.quarantine_overlapped(operation)
                except Exception:
                    pass
            try:
                self.close_handle(client)
            finally:
                if settled:
                    self.close_handle(server)
            raise WindowsEffectfulCaptureNativeError(
                "named pipe connection did not complete synchronously"
            ) from None
        else:
            self.close_handle(event_handle)
            failed = False
            for handle in (client, server):
                try:
                    self.close_handle(handle)
                except Exception:
                    failed = True
            if failed:
                raise WindowsEffectfulCaptureNativeError(
                    "named pipe connection and cleanup failed"
                ) from None
            raise _native_error("ConnectNamedPipe", connect_error)
        if server_access == PIPE_ACCESS_OUTBOUND:
            read_handle, write_handle = client, server
        else:
            read_handle, write_handle = server, client
        return NativePipePair(read_handle, write_handle)

    def set_handle_inheritable(self, handle: int, inheritable: bool) -> None:
        if type(inheritable) is not bool:
            raise WindowsEffectfulCaptureNativeError("inheritance state is invalid")
        flags = HANDLE_FLAG_INHERIT if inheritable else 0
        if not self._k32.SetHandleInformation(
            self._w.HANDLE(_handle(handle, "inheritance handle")),
            HANDLE_FLAG_INHERIT,
            flags,
        ):
            raise _native_error("SetHandleInformation")

    def create_staging_file(self, path: str) -> NativeStagingObject:
        path = _windows_path(path, "staging path")
        parsed = PureWindowsPath(path)
        self.reject_casefold_collisions(str(parsed.parent), (parsed.name,))
        sa = self._sa(ctypes.sizeof(self._sa), None, False)
        value = self._k32.CreateFileW(
            path,
            GENERIC_READ | GENERIC_WRITE | DELETE,
            FILE_SHARE_READ | FILE_SHARE_DELETE,
            ctypes.byref(sa),
            CREATE_NEW,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        raw = _native_handle(value, "staging handle", allow_invalid=True)
        if raw == ctypes.c_void_p(-1).value:
            raise _native_error("CreateFileW")
        master = _handle(raw, "staging handle")
        duplicate = self._w.HANDLE()
        process = self._k32.GetCurrentProcess()
        if not self._k32.DuplicateHandle(
            process,
            self._w.HANDLE(master),
            process,
            ctypes.byref(duplicate),
            GENERIC_WRITE,
            True,
            0,
        ):
            try:
                self.close_handle(master)
            finally:
                raise _native_error("DuplicateHandle") from None
        child = _handle(
            _native_handle(duplicate, "child staging handle"),
            "child staging handle",
        )
        try:
            identity = self.get_file_identity(master)
            return NativeStagingObject(master, child, identity, path)
        except BaseException:
            self.close_handle(child)
            self.close_handle(master)
            raise

    def get_file_identity(self, handle: int) -> NativeFileIdentity:
        info = self._file_id_info()
        if not self._k32.GetFileInformationByHandleEx(
            self._w.HANDLE(_handle(handle, "identity handle")),
            FILE_ID_INFO_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise _native_error("GetFileInformationByHandleEx")
        return NativeFileIdentity(
            int(info.VolumeSerialNumber), bytes(info.FileId.Identifier)
        )

    def read_artifact_file(self, handle: int, max_bytes: int) -> bytes:
        if type(max_bytes) is not int or max_bytes <= 0:
            raise WindowsEffectfulCaptureNativeError("artifact byte bound is invalid")
        handle = _handle(handle, "artifact read handle")
        if not self._k32.SetFilePointerEx(self._w.HANDLE(handle), 0, None, 0):
            raise _native_error("SetFilePointerEx")
        payload = bytearray()
        while len(payload) <= max_bytes:
            requested = min(65536, max_bytes + 1 - len(payload))
            buffer = ctypes.create_string_buffer(requested)
            transferred = self._w.DWORD()
            if not self._k32.ReadFile(
                self._w.HANDLE(handle),
                buffer,
                requested,
                ctypes.byref(transferred),
                None,
            ):
                raise _native_error("ReadFile")
            count = int(transferred.value)
            if count == 0:
                break
            payload.extend(buffer.raw[:count])
        return bytes(payload)

    def reject_casefold_collisions(
        self, directory: str, names: tuple[str, ...]
    ) -> None:
        directory = _windows_path(directory, "artifact directory")
        if (
            type(names) is not tuple
            or not names
            or any(type(name) is not str or not name for name in names)
        ):
            raise WindowsEffectfulCaptureNativeError("artifact names are invalid")
        wanted = {name.casefold() for name in names}
        try:
            entries = os.listdir(directory)
        except OSError:
            raise WindowsEffectfulCaptureNativeError(
                "artifact directory enumeration failed"
            ) from None
        if any(entry.casefold() in wanted for entry in entries):
            raise WindowsEffectfulCaptureNativeError(
                "artifact name collision prevents no-clobber publication"
            )

    def publish_staging_link(
        self, staging_handle: int, staging_path: str, final_path: str
    ) -> None:
        staging_path = _windows_path(staging_path, "staging path")
        final_path = _windows_path(final_path, "final artifact path")
        staging = PureWindowsPath(staging_path)
        final = PureWindowsPath(final_path)
        if staging.parent != final.parent:
            raise WindowsEffectfulCaptureNativeError(
                "publication paths must share the same parent directory"
            )
        _handle(staging_handle, "publication staging handle")
        if not self._k32.CreateHardLinkW(final_path, staging_path, None):
            raise _native_error("CreateHardLinkW")

    def open_final_artifact(self, path: str) -> NativeOpenedArtifact:
        path = _windows_path(path, "final artifact path")
        value = self._k32.CreateFileW(
            path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        raw = _native_handle(value, "final artifact handle", allow_invalid=True)
        if raw == ctypes.c_void_p(-1).value:
            raise _native_error("CreateFileW")
        handle = _handle(raw, "final artifact handle")
        try:
            attributes = self._file_attribute_tag_info()
            if not self._k32.GetFileInformationByHandleEx(
                self._w.HANDLE(handle),
                FILE_ATTRIBUTE_TAG_INFO_CLASS,
                ctypes.byref(attributes),
                ctypes.sizeof(attributes),
            ):
                raise _native_error("GetFileInformationByHandleEx")
            if int(attributes.FileAttributes) & FILE_ATTRIBUTE_REPARSE_POINT:
                raise WindowsEffectfulCaptureNativeError(
                    "final artifact is a reparse point"
                )
            return NativeOpenedArtifact(handle, self.get_file_identity(handle))
        except BaseException:
            self.close_handle(handle)
            raise

    def delete_staging_link(self, staging_handle: int) -> None:
        info = self._file_disposition_info(True)
        if not self._k32.SetFileInformationByHandle(
            self._w.HANDLE(_handle(staging_handle, "staging cleanup handle")),
            FILE_DISPOSITION_INFO_CLASS,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise _native_error("SetFileInformationByHandle")

    def create_suspended_process(
        self,
        *,
        application_name: str,
        arguments: tuple[str, ...],
        environment: Mapping[str, str],
        current_directory: str,
        inherited_handles: tuple[int, int, int],
        job_handle: int,
        creation_flags: int,
        inherit_handles: bool,
    ) -> NativeCreatedProcess:
        application = _windows_path(application_name, "application name")
        current = _windows_path(current_directory, "current directory")
        args = _arguments(arguments)
        if creation_flags != C3_CREATE_PROCESS_FLAGS or inherit_handles is not True:
            raise WindowsEffectfulCaptureNativeError(
                "CreateProcess policy is not exact"
            )
        if (
            type(inherited_handles) is not tuple
            or len(inherited_handles) != 3
            or len(set(inherited_handles)) != 3
        ):
            raise WindowsEffectfulCaptureNativeError(
                "HANDLE_LIST must contain exactly three handles"
            )
        inherited_handles = tuple(
            _handle(value, "inherited handle") for value in inherited_handles
        )
        job_handle = _handle(job_handle, "job handle")

        size = ctypes.c_size_t()
        ctypes.set_last_error(0)
        first = self._k32.InitializeProcThreadAttributeList(
            None, 2, 0, ctypes.byref(size)
        )
        error = ctypes.get_last_error()
        if first or size.value <= 0 or error not in (0, ERROR_INSUFFICIENT_BUFFER):
            raise _native_error("InitializeProcThreadAttributeList", error)
        buffer = ctypes.create_string_buffer(size.value)
        attrs = ctypes.cast(buffer, ctypes.c_void_p)
        initialized = False
        try:
            if not self._k32.InitializeProcThreadAttributeList(
                attrs, 2, 0, ctypes.byref(size)
            ):
                raise _native_error("InitializeProcThreadAttributeList")
            initialized = True
            handles = (self._w.HANDLE * 3)(
                *(self._w.HANDLE(value) for value in inherited_handles)
            )
            jobs = (self._w.HANDLE * 1)(self._w.HANDLE(job_handle))
            if not self._k32.UpdateProcThreadAttribute(
                attrs,
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                ctypes.cast(handles, ctypes.c_void_p),
                ctypes.sizeof(handles),
                None,
                None,
            ):
                raise _native_error("UpdateProcThreadAttribute(HANDLE_LIST)")
            if not self._k32.UpdateProcThreadAttribute(
                attrs,
                0,
                PROC_THREAD_ATTRIBUTE_JOB_LIST,
                ctypes.cast(jobs, ctypes.c_void_p),
                ctypes.sizeof(jobs),
                None,
                None,
            ):
                raise _native_error("UpdateProcThreadAttribute(JOB_LIST)")
            startup = self._startup()
            pi = self._pi()
            startup.StartupInfo.cb = ctypes.sizeof(startup)
            startup.lpAttributeList = attrs
            command = " ".join(_quote_arg(value) for value in (application, *args))
            command_buffer = ctypes.create_unicode_buffer(command)
            environment_buffer = ctypes.create_unicode_buffer(
                _environment_block(environment)
            )
            if not self._k32.CreateProcessW(
                application,
                command_buffer,
                None,
                None,
                True,
                creation_flags,
                environment_buffer,
                current,
                ctypes.byref(startup),
                ctypes.byref(pi),
            ):
                error = ctypes.get_last_error()
                raise WindowsEffectfulCaptureProcessNotCreatedError(
                    f"CreateProcessW failed with Win32 error {error}"
                ) from None
            try:
                return NativeCreatedProcess(
                    int(pi.dwProcessId),
                    int(pi.dwThreadId),
                    _native_handle(pi.hProcess, "process handle"),
                    _native_handle(pi.hThread, "primary thread handle"),
                )
            except BaseException:
                cleanup_failed = False
                for raw_handle in (pi.hThread, pi.hProcess):
                    try:
                        self.close_handle(_native_handle(raw_handle, "created handle"))
                    except BaseException:
                        cleanup_failed = True
                message = "created process result could not be retained"
                if cleanup_failed:
                    message = "created process result cleanup was incomplete"
                raise WindowsEffectfulCaptureProcessOutcomeUnknownError(
                    message
                ) from None
        finally:
            if initialized:
                self._k32.DeleteProcThreadAttributeList(attrs)

    def close_handle(self, handle: int) -> None:
        if not self._k32.CloseHandle(self._w.HANDLE(_handle(handle, "close handle"))):
            raise _native_error("CloseHandle")

    def begin_overlapped_write(self, handle: int, payload: bytes) -> object:
        if type(payload) is not bytes or not payload:
            raise WindowsEffectfulCaptureNativeError("WriteFile payload is invalid")
        if len(payload) > MAX_C3_CHILD_REQUEST_BYTES:
            raise WindowsEffectfulCaptureNativeError("WriteFile payload exceeds bound")
        return self._begin_overlapped("WRITE", handle, payload, len(payload))

    def begin_overlapped_read(self, handle: int, max_bytes: int) -> object:
        if (
            type(max_bytes) is not int
            or max_bytes <= 0
            or max_bytes > MAX_C3_CHILD_RESULT_BYTES + 1
        ):
            raise WindowsEffectfulCaptureNativeError("ReadFile bound is invalid")
        return self._begin_overlapped("READ", handle, None, max_bytes)

    def _begin_overlapped(
        self, operation_type: str, handle: int, payload: bytes | None, size: int
    ) -> _C3OverlappedOperation:
        self._reap_quarantine()
        handle = _handle(handle, "overlapped pipe handle")
        event_value = self._k32.CreateEventW(None, True, False, None)
        event_handle = _native_handle(event_value, "overlapped event handle")
        overlapped = self._overlapped()
        overlapped.hEvent = self._w.HANDLE(event_handle)
        buffer = (
            ctypes.create_string_buffer(size)
            if payload is None
            else ctypes.create_string_buffer(payload, size)
        )
        operation = _C3OverlappedOperation(
            owner=self,
            handle=handle,
            event_handle=event_handle,
            overlapped=overlapped,
            buffer=buffer,
            operation_type=operation_type,
            requested=size,
        )
        ctypes.set_last_error(0)
        if operation_type == "WRITE":
            succeeded = self._k32.WriteFile(
                self._w.HANDLE(handle),
                ctypes.cast(buffer, ctypes.c_void_p),
                size,
                None,
                ctypes.byref(overlapped),
            )
        else:
            succeeded = self._k32.ReadFile(
                self._w.HANDLE(handle),
                ctypes.cast(buffer, ctypes.c_void_p),
                size,
                None,
                ctypes.byref(overlapped),
            )
        error = ctypes.get_last_error()
        if succeeded:
            operation.settled = True
        elif operation_type == "READ" and error == ERROR_BROKEN_PIPE:
            operation.immediate_eof = True
            operation.settled = True
        elif error != ERROR_IO_PENDING:
            try:
                self.close_handle(event_handle)
            finally:
                raise _native_error(f"{operation_type.title()}File", error)
        return operation

    def wait_overlapped_or_process(
        self, operation: object, process_handle: int | None, timeout_ms: int
    ) -> C3NativeWaitStatus:
        item = self._operation(operation)
        if type(timeout_ms) is not int or timeout_ms < 0 or timeout_ms >= INFINITE:
            raise WindowsEffectfulCaptureNativeError("wait timeout is invalid")
        if item.settled:
            return C3NativeWaitStatus.IO_COMPLETED
        if process_handle is None:
            result = int(
                self._k32.WaitForSingleObject(
                    self._w.HANDLE(item.event_handle), timeout_ms
                )
            )
            if result == WAIT_OBJECT_0:
                return C3NativeWaitStatus.IO_COMPLETED
        else:
            handles = (self._w.HANDLE * 2)(
                self._w.HANDLE(item.event_handle),
                self._w.HANDLE(_handle(process_handle, "process wait handle")),
            )
            result = int(
                self._k32.WaitForMultipleObjects(2, handles, False, timeout_ms)
            )
            if result == WAIT_OBJECT_0:
                return C3NativeWaitStatus.IO_COMPLETED
            if result == WAIT_OBJECT_0 + 1:
                return C3NativeWaitStatus.PROCESS_EXITED
        if result == WAIT_TIMEOUT:
            return C3NativeWaitStatus.TIMEOUT
        return C3NativeWaitStatus.FAILED

    def complete_overlapped(self, operation: object) -> NativeOverlappedCompletion:
        item = self._operation(operation)
        if item.quarantined:
            raise WindowsEffectfulCaptureNativeError(
                "quarantined operation cannot be completed by its former owner"
            )
        if item.immediate_eof:
            item.settled = True
            self._close_operation_event(item)
            return NativeOverlappedCompletion(0, b"", True)
        transferred = self._w.DWORD()
        ctypes.set_last_error(0)
        if not self._k32.GetOverlappedResult(
            self._w.HANDLE(item.handle),
            ctypes.byref(item.overlapped),
            ctypes.byref(transferred),
            False,
        ):
            error = ctypes.get_last_error()
            if item.operation_type == "READ" and error == ERROR_BROKEN_PIPE:
                item.settled = True
                self._close_operation_event(item)
                return NativeOverlappedCompletion(0, b"", True)
            raise _native_error("GetOverlappedResult", error)
        item.settled = True
        count = int(transferred.value)
        if count < 0 or count > item.requested:
            raise WindowsEffectfulCaptureNativeError(
                "overlapped transfer count is invalid"
            )
        data = bytes(item.buffer.raw[:count]) if item.operation_type == "READ" else b""
        self._close_operation_event(item)
        return NativeOverlappedCompletion(
            transferred=count,
            payload=data,
            eof=item.operation_type == "READ" and count == 0,
        )

    def cancel_and_settle_overlapped(self, operation: object, timeout_ms: int) -> bool:
        item = self._operation(operation)
        if item.settled:
            self._close_operation_event(item)
            return True
        if type(timeout_ms) is not int or timeout_ms < 0 or timeout_ms >= INFINITE:
            raise WindowsEffectfulCaptureNativeError(
                "cancellation settlement timeout is invalid"
            )
        ctypes.set_last_error(0)
        cancelled = self._k32.CancelIoEx(
            self._w.HANDLE(item.handle), ctypes.byref(item.overlapped)
        )
        cancel_error = ctypes.get_last_error()
        if not cancelled and cancel_error != ERROR_NOT_FOUND:
            return False
        wait = int(
            self._k32.WaitForSingleObject(self._w.HANDLE(item.event_handle), timeout_ms)
        )
        if wait != WAIT_OBJECT_0:
            return False
        if not self._definitively_settled(item):
            return False
        self._close_operation_event(item)
        return True

    def quarantine_overlapped(self, operation: object) -> None:
        item = self._operation(operation)
        if item.quarantined:
            raise WindowsEffectfulCaptureNativeError(
                "overlapped operation is already quarantined"
            )
        item.quarantined = True
        with _C3_OVERLAPPED_QUARANTINE_LOCK:
            _C3_OVERLAPPED_QUARANTINE.append(item)
        self._reap_quarantine()

    def _reap_quarantine(self) -> None:
        with _C3_OVERLAPPED_QUARANTINE_LOCK:
            retained: list[_C3OverlappedOperation] = []
            for item in _C3_OVERLAPPED_QUARANTINE:
                owner = item.owner
                wait = int(
                    owner._k32.WaitForSingleObject(
                        owner._w.HANDLE(item.event_handle), 0
                    )
                )
                if wait != WAIT_OBJECT_0 or not owner._definitively_settled(item):
                    retained.append(item)
                    continue
                owner._close_operation_event(item)
                try:
                    owner.close_handle(item.handle)
                except Exception:
                    pass
            _C3_OVERLAPPED_QUARANTINE[:] = retained

    def _definitively_settled(self, item: _C3OverlappedOperation) -> bool:
        transferred = self._w.DWORD()
        ctypes.set_last_error(0)
        if self._k32.GetOverlappedResult(
            self._w.HANDLE(item.handle),
            ctypes.byref(item.overlapped),
            ctypes.byref(transferred),
            False,
        ):
            item.settled = True
            return True
        error = ctypes.get_last_error()
        if error in (ERROR_OPERATION_ABORTED, ERROR_BROKEN_PIPE):
            item.settled = True
            return True
        return False

    def _close_operation_event(self, item: _C3OverlappedOperation) -> None:
        event_handle = item.event_handle
        if event_handle == 0:
            return
        item.event_handle = 0
        self.close_handle(event_handle)

    def _operation(self, operation: object) -> _C3OverlappedOperation:
        if type(operation) is not _C3OverlappedOperation or operation.owner is not self:
            raise WindowsEffectfulCaptureNativeError(
                "overlapped operation provenance is invalid"
            )
        return operation

    def wait_process(self, process_handle: int, timeout_ms: int) -> C3NativeWaitStatus:
        if type(timeout_ms) is not int or timeout_ms < 0 or timeout_ms >= INFINITE:
            raise WindowsEffectfulCaptureNativeError("process wait timeout is invalid")
        result = int(
            self._k32.WaitForSingleObject(
                self._w.HANDLE(_handle(process_handle, "process wait handle")),
                timeout_ms,
            )
        )
        if result == WAIT_OBJECT_0:
            return C3NativeWaitStatus.PROCESS_EXITED
        if result == WAIT_TIMEOUT:
            return C3NativeWaitStatus.TIMEOUT
        return C3NativeWaitStatus.FAILED

    def get_exit_code_process(self, process_handle: int) -> int:
        exit_code = self._w.DWORD()
        if not self._k32.GetExitCodeProcess(
            self._w.HANDLE(_handle(process_handle, "process exit handle")),
            ctypes.byref(exit_code),
        ):
            raise _native_error("GetExitCodeProcess")
        return int(exit_code.value)

    def terminate_job_object(self, job_handle: int) -> None:
        if not self._k32.TerminateJobObject(
            self._w.HANDLE(_handle(job_handle, "termination job handle")), 1
        ):
            raise _native_error("TerminateJobObject")

    def resume_thread(self, thread_handle: int) -> int:
        return int(
            self._k32.ResumeThread(
                self._w.HANDLE(_handle(thread_handle, "primary thread handle"))
            )
        )


class CtypesWindowsEffectfulCaptureChildIoApi:
    """ctypes binding for the three inherited handles owned by the C3 child."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsEffectfulCaptureNativeUnsupportedError(
                "C3 child I/O is supported only on Windows"
            )
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.ReadFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        k32.ReadFile.restype = wintypes.BOOL
        k32.WriteFile.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        k32.WriteFile.restype = wintypes.BOOL
        k32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        k32.FlushFileBuffers.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        self._k32 = k32
        self._w = wintypes

    def read_file(self, handle: int, max_bytes: int) -> bytes:
        if (
            type(max_bytes) is not int
            or max_bytes <= 0
            or max_bytes > MAX_C3_CHILD_REQUEST_BYTES
        ):
            raise WindowsEffectfulCaptureNativeError("ReadFile bound is invalid")
        buffer = ctypes.create_string_buffer(max_bytes)
        read = self._w.DWORD()
        ctypes.set_last_error(0)
        if not self._k32.ReadFile(
            self._w.HANDLE(_handle(handle, "request reader handle")),
            ctypes.cast(buffer, ctypes.c_void_p),
            max_bytes,
            ctypes.byref(read),
            None,
        ):
            error = ctypes.get_last_error()
            if error == ERROR_BROKEN_PIPE:
                return b""
            raise _native_error("ReadFile", error)
        count = int(read.value)
        if count > max_bytes:
            raise WindowsEffectfulCaptureNativeError(
                "ReadFile returned an invalid byte count"
            )
        return bytes(buffer.raw[:count])

    def write_file(self, handle: int, payload: bytes) -> int:
        if type(payload) is not bytes or not payload:
            raise WindowsEffectfulCaptureNativeError("WriteFile payload is invalid")
        if len(payload) > MAX_DAILY_SNAPSHOT_ARTIFACT_BYTES:
            raise WindowsEffectfulCaptureNativeError("WriteFile payload exceeds bound")
        buffer = ctypes.create_string_buffer(payload, len(payload))
        written = self._w.DWORD()
        if not self._k32.WriteFile(
            self._w.HANDLE(_handle(handle, "child writer handle")),
            ctypes.cast(buffer, ctypes.c_void_p),
            len(payload),
            ctypes.byref(written),
            None,
        ):
            raise _native_error("WriteFile")
        return int(written.value)

    def flush_file_buffers(self, handle: int) -> None:
        if not self._k32.FlushFileBuffers(
            self._w.HANDLE(_handle(handle, "staging writer handle"))
        ):
            raise _native_error("FlushFileBuffers")

    def close_handle(self, handle: int) -> None:
        if not self._k32.CloseHandle(
            self._w.HANDLE(_handle(handle, "child-owned handle"))
        ):
            raise _native_error("CloseHandle")


def _handle_bootstrap_arguments(handles: tuple[int, int, int]) -> tuple[str, ...]:
    request_read, result_write, staging_write = handles
    return (
        C3_REQUEST_HANDLE_ARGUMENT,
        str(_handle(request_read, "request read handle")),
        C3_RESULT_HANDLE_ARGUMENT,
        str(_handle(result_write, "result write handle")),
        C3_STAGING_HANDLE_ARGUMENT,
        str(_handle(staging_write, "staging write handle")),
    )


def _remaining_timeout_ms(deadline_ns: int) -> int:
    remaining_ns = deadline_ns - time.monotonic_ns()
    if remaining_ns <= 0:
        return 0
    return min((remaining_ns + 999_999) // 1_000_000, INFINITE - 1)


def _handle(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise WindowsEffectfulCaptureNativeError(f"{label} is invalid")
    return value


def _native_handle(value: object, label: str, *, allow_invalid: bool = False) -> int:
    raw = getattr(value, "value", value)
    raw = 0 if raw is None else raw
    try:
        result = int(raw)
    except (TypeError, ValueError, OverflowError):
        raise WindowsEffectfulCaptureNativeError(f"{label} is invalid") from None
    return result if allow_invalid else _handle(result, label)


def _windows_path(value: object, label: str) -> str:
    if (
        type(value) is not str
        or not value
        or "\0" in value
        or not PureWindowsPath(value).is_absolute()
    ):
        raise WindowsEffectfulCaptureNativeError(
            f"{label} must be absolute Windows text"
        )
    return str(PureWindowsPath(value))


def _arguments(value: object) -> tuple[str, ...]:
    if type(value) is not tuple or any(
        type(argument) is not str or "\0" in argument for argument in value
    ):
        raise WindowsEffectfulCaptureNativeError("child arguments are invalid")
    return value


def _environment_block(environment: Mapping[str, str]) -> str:
    expected = {"SystemRoot", "WINDIR", "TEMP", "TMP", "PYTHONUTF8"}
    if not isinstance(environment, Mapping) or set(environment) != expected:
        raise WindowsEffectfulCaptureNativeError(
            "child environment fields are not exact"
        )
    invalid = environment["PYTHONUTF8"] != "1" or any(
        type(key) is not str
        or type(value) is not str
        or not key
        or "=" in key
        or "\0" in key
        or "\0" in value
        for key, value in environment.items()
    )
    if invalid:
        raise WindowsEffectfulCaptureNativeError("child environment is invalid")
    ordered = sorted(environment.items(), key=lambda item: item[0].upper())
    return "".join(f"{key}={value}\0" for key, value in ordered) + "\0"


def _quote_arg(value: str) -> str:
    if value and not any(character in value for character in ' \t"'):
        return value
    result = '"'
    slashes = 0
    for character in value:
        if character == "\\":
            slashes += 1
        elif character == '"':
            result += "\\" * (slashes * 2 + 1) + '"'
            slashes = 0
        else:
            result += "\\" * slashes + character
            slashes = 0
    return result + "\\" * (slashes * 2) + '"'


def _native_error(
    operation: str, code: int | None = None
) -> WindowsEffectfulCaptureNativeError:
    value = ctypes.get_last_error() if code is None else code
    suffix = "" if not value else f" (win32={value})"
    return WindowsEffectfulCaptureNativeError(
        f"Windows operation failed: {operation}{suffix}"
    )
