"""Secret-free Windows parent launcher for one isolated capture child."""

from __future__ import annotations

import ctypes
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.market_data.daily_snapshot_verification import verify_daily_snapshot
from trading_bot.runtime.isolated_capture_artifacts import (
    ISOLATED_CAPTURE_ENVIRONMENT_POLICY_VERSION,
    ISOLATED_CAPTURE_MAX_STREAM_BYTES,
    ChildProcessCreationRecord,
    ChildResumeAuthorizationRecord,
    ChildTerminationRecord,
    HandleInheritancePosture,
    IsolatedCaptureChildClassification,
    IsolatedCaptureChildRequest,
    JobObjectAssignmentResult,
    ProcessCreationResult,
    ProcessTreeTerminationResult,
    ResumeAuthorizationResult,
    create_child_process_creation_record,
    create_child_resume_authorization_record,
    create_child_termination_record,
    evidence_for_payload,
    parse_child_process_creation_record,
    parse_child_resume_authorization_record,
    parse_child_termination_record,
    parse_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    publish_canonical_artifact,
    serialize_child_process_creation_record,
    serialize_child_resume_authorization_record,
    serialize_child_termination_record,
    verify_payload_evidence,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence

ISOLATED_CAPTURE_LAUNCHER_CONFIG_SCHEMA_VERSION = 1
MAX_ISOLATED_CAPTURE_LAUNCHER_CONFIG_BYTES = 64 * 1024
ISOLATED_CAPTURE_RESUME_POLICY_VERSION = "isolated-child-resume-v1"
ISOLATED_CAPTURE_TERMINATION_POLICY_VERSION = "isolated-child-termination-v1"


class IsolatedCaptureLauncherError(RuntimeError):
    """The parent launcher failed closed without carrying child output."""


class IsolatedCaptureLauncherConfigError(IsolatedCaptureLauncherError):
    """The strict nonsecret launcher configuration is invalid."""


@dataclass(frozen=True, slots=True)
class IsolatedCaptureLauncherConfig:
    schema_version: int
    child_request: ArtifactEvidence
    child_request_path: Path
    approved_python_executable: Path
    approved_python_executable_evidence: ArtifactEvidence
    approved_child_script: Path
    approved_child_script_evidence: ArtifactEvidence
    process_evidence_directory: Path
    controlled_temp_directory: Path
    environment_policy_version: str
    termination_grace_seconds: int

    def __post_init__(self) -> None:
        if self.schema_version != ISOLATED_CAPTURE_LAUNCHER_CONFIG_SCHEMA_VERSION:
            raise IsolatedCaptureLauncherConfigError(
                "launcher schema_version must be 1"
            )
        for value, label in (
            (self.child_request, "child_request"),
            (
                self.approved_python_executable_evidence,
                "approved_python_executable_evidence",
            ),
            (self.approved_child_script_evidence, "approved_child_script_evidence"),
        ):
            if type(value) is not ArtifactEvidence:
                raise IsolatedCaptureLauncherConfigError(f"{label} is invalid")
        for value, label in (
            (self.child_request_path, "child_request_path"),
            (self.approved_python_executable, "approved_python_executable"),
            (self.approved_child_script, "approved_child_script"),
            (self.process_evidence_directory, "process_evidence_directory"),
            (self.controlled_temp_directory, "controlled_temp_directory"),
        ):
            if not isinstance(value, Path) or not value.is_absolute():
                raise IsolatedCaptureLauncherConfigError(f"{label} must be absolute")
        if (
            self.environment_policy_version
            != ISOLATED_CAPTURE_ENVIRONMENT_POLICY_VERSION
        ):
            raise IsolatedCaptureLauncherConfigError(
                "environment policy is unsupported"
            )
        if (
            type(self.termination_grace_seconds) is not int
            or not 1 <= self.termination_grace_seconds <= 30
        ):
            raise IsolatedCaptureLauncherConfigError(
                "termination_grace_seconds is outside the approved bound"
            )


@dataclass(slots=True, repr=False)
class NativeSuspendedProcess:
    process_id: int
    process_handle: object
    primary_thread_handle: object
    stdout: bytes = b""
    stderr: bytes = b""

    def __repr__(self) -> str:
        return "NativeSuspendedProcess(<private handles>)"


class WindowsIsolatedProcessApi(Protocol):
    def create_suspended(
        self,
        *,
        executable: Path,
        arguments: tuple[str, ...],
        environment: Mapping[str, str],
        current_directory: Path,
        inherit_handles: bool,
    ) -> NativeSuspendedProcess: ...

    def create_job_with_limits(self) -> object: ...

    def assign_to_job(
        self, job_handle: object, process: NativeSuspendedProcess
    ) -> None: ...

    def resume(self, process: NativeSuspendedProcess) -> None: ...

    def wait(
        self, process: NativeSuspendedProcess, timeout_milliseconds: int
    ) -> bool: ...

    def terminate_job(self, job_handle: object, exit_code: int) -> None: ...

    def terminate_process(
        self, process: NativeSuspendedProcess, exit_code: int
    ) -> None: ...

    def exit_code(self, process: NativeSuspendedProcess) -> int: ...

    def close_handle(self, handle: object) -> None: ...


@dataclass(frozen=True, slots=True)
class IsolatedCaptureLauncherExecution:
    child_request: IsolatedCaptureChildRequest
    creation_record: ChildProcessCreationRecord
    resume_record: ChildResumeAuthorizationRecord | None
    termination_record: ChildTerminationRecord
    child_classification: IsolatedCaptureChildClassification | None
    native_exit_code: int | None


def load_isolated_capture_launcher_config(
    path: Path,
) -> IsolatedCaptureLauncherConfig:
    if not isinstance(path, Path):
        raise IsolatedCaptureLauncherConfigError("config path must be a Path")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise IsolatedCaptureLauncherConfigError(
            "launcher config cannot be read"
        ) from error
    if len(payload) > MAX_ISOLATED_CAPTURE_LAUNCHER_CONFIG_BYTES or payload.startswith(
        b"\xef\xbb\xbf"
    ):
        raise IsolatedCaptureLauncherConfigError("launcher config bytes are invalid")
    try:
        root = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IsolatedCaptureLauncherConfigError(
            "launcher config is not strict UTF-8 JSON"
        ) from error
    expected = {
        "schema_version",
        "child_request",
        "child_request_path",
        "approved_python_executable",
        "approved_python_executable_evidence",
        "approved_child_script",
        "approved_child_script_evidence",
        "process_evidence_directory",
        "controlled_temp_directory",
        "environment_policy_version",
        "termination_grace_seconds",
    }
    if type(root) is not dict or set(root) != expected:
        raise IsolatedCaptureLauncherConfigError(
            "launcher config fields do not match schema"
        )
    return IsolatedCaptureLauncherConfig(
        schema_version=_integer(root["schema_version"], "schema_version"),
        child_request=_artifact(root["child_request"], "child_request"),
        child_request_path=_path(root["child_request_path"], "child_request_path"),
        approved_python_executable=_path(
            root["approved_python_executable"], "approved_python_executable"
        ),
        approved_python_executable_evidence=_artifact(
            root["approved_python_executable_evidence"],
            "approved_python_executable_evidence",
        ),
        approved_child_script=_path(
            root["approved_child_script"], "approved_child_script"
        ),
        approved_child_script_evidence=_artifact(
            root["approved_child_script_evidence"],
            "approved_child_script_evidence",
        ),
        process_evidence_directory=_path(
            root["process_evidence_directory"], "process_evidence_directory"
        ),
        controlled_temp_directory=_path(
            root["controlled_temp_directory"], "controlled_temp_directory"
        ),
        environment_policy_version=_string(
            root["environment_policy_version"], "environment_policy_version"
        ),
        termination_grace_seconds=_integer(
            root["termination_grace_seconds"], "termination_grace_seconds"
        ),
    )


def build_isolated_child_environment(
    parent_environment: Mapping[str, str],
    controlled_temp_directory: Path,
) -> dict[str, str]:
    """Build a fixed allowlist; no parent credential or networking state passes."""
    if not isinstance(parent_environment, Mapping):
        raise IsolatedCaptureLauncherConfigError("parent environment must be a mapping")
    names = {str(name).upper() for name in parent_environment}
    if {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"} & names:
        raise IsolatedCaptureLauncherError(
            "parent environment contains prohibited Alpaca variables"
        )
    if (
        not isinstance(controlled_temp_directory, Path)
        or not controlled_temp_directory.is_absolute()
        or not controlled_temp_directory.is_dir()
    ):
        raise IsolatedCaptureLauncherConfigError("controlled TEMP directory is invalid")
    casefolded = {
        str(key).upper(): str(value) for key, value in parent_environment.items()
    }
    system_root = casefolded.get("SYSTEMROOT")
    windir = casefolded.get("WINDIR", system_root)
    if not system_root or not windir:
        raise IsolatedCaptureLauncherConfigError(
            "approved Windows runtime roots are absent"
        )
    return {
        "SystemRoot": system_root,
        "WINDIR": windir,
        "TEMP": str(controlled_temp_directory),
        "TMP": str(controlled_temp_directory),
        "PYTHONUTF8": "1",
    }


def launch_isolated_capture_child(
    config: IsolatedCaptureLauncherConfig,
    *,
    parent_environment: Mapping[str, str] | None = None,
    native_api: WindowsIsolatedProcessApi | None = None,
) -> IsolatedCaptureLauncherExecution:
    """Create suspended, contain, evidence, resume, wait, and verify once."""
    if type(config) is not IsolatedCaptureLauncherConfig:
        raise IsolatedCaptureLauncherConfigError("launcher config is invalid")
    environment = build_isolated_child_environment(
        os.environ if parent_environment is None else parent_environment,
        config.controlled_temp_directory,
    )
    request_payload = _read_exact_file(config.child_request_path)
    verify_payload_evidence(request_payload, config.child_request)
    request = parse_isolated_capture_child_request(request_payload)
    if config.child_request.artifact_id != request.child_request_id:
        raise IsolatedCaptureLauncherConfigError(
            "child request evidence ID does not reconcile"
        )
    _verify_file_evidence(
        config.approved_python_executable,
        config.approved_python_executable_evidence,
    )
    _verify_file_evidence(
        config.approved_child_script,
        config.approved_child_script_evidence,
    )
    if not config.process_evidence_directory.is_dir():
        raise IsolatedCaptureLauncherConfigError(
            "process evidence directory must already exist"
        )
    api = CtypesWindowsIsolatedProcessApi() if native_api is None else native_api
    process: NativeSuspendedProcess | None = None
    job_handle: object | None = None
    job_assigned = False
    resume_record: ChildResumeAuthorizationRecord | None = None
    creation_record: ChildProcessCreationRecord | None = None
    termination_record: ChildTerminationRecord | None = None
    creation_evidence: ArtifactEvidence | None = None
    resume_evidence: ArtifactEvidence | None = None
    timed_out = False
    termination_requested = False
    tree_result = ProcessTreeTerminationResult.NOT_CREATED
    native_exit_code: int | None = None
    termination_diagnostics: tuple[str, ...] = ("CHILD_NOT_CREATED",)
    try:
        process = api.create_suspended(
            executable=config.approved_python_executable,
            arguments=(
                str(config.approved_child_script),
                "--request",
                str(config.child_request_path),
            ),
            environment=environment,
            current_directory=config.approved_child_script.parent,
            inherit_handles=False,
        )
        job_handle = api.create_job_with_limits()
        api.assign_to_job(job_handle, process)
        job_assigned = True
        creation_record = create_child_process_creation_record(
            allocation=request.allocation,
            child_request=config.child_request,
            scheduled_launch_id=request.scheduled_launch_id,
            approved_executable=config.approved_python_executable_evidence,
            software_release=request.software_release,
            process_id=process.process_id,
            creation_result=ProcessCreationResult.CREATED_SUSPENDED,
            job_object_assignment=JobObjectAssignmentResult.ASSIGNED,
            handle_inheritance=HandleInheritancePosture.DISABLED,
            environment_policy_version=config.environment_policy_version,
            diagnostics=("CHILD_CREATED_SUSPENDED", "JOB_LIMITS_ASSIGNED"),
        )
        creation_payload = serialize_child_process_creation_record(creation_record)
        creation_path = config.process_evidence_directory / _creation_filename(
            creation_record
        )
        publish_canonical_artifact(
            creation_path, creation_payload, parse_child_process_creation_record
        )
        creation_evidence = evidence_for_payload(
            creation_record.process_creation_record_id, creation_payload
        )
        resume_record = create_child_resume_authorization_record(
            allocation=request.allocation,
            child_request=config.child_request,
            process_creation=creation_evidence,
            scheduled_launch_id=request.scheduled_launch_id,
            process_id=process.process_id,
            evidence_verified=True,
            result=ResumeAuthorizationResult.AUTHORIZED,
            diagnostics=("RESUME_AUTHORIZED",),
            resume_policy_version=ISOLATED_CAPTURE_RESUME_POLICY_VERSION,
        )
        resume_payload = serialize_child_resume_authorization_record(resume_record)
        resume_path = config.process_evidence_directory / _resume_filename(
            resume_record
        )
        publish_canonical_artifact(
            resume_path, resume_payload, parse_child_resume_authorization_record
        )
        resume_evidence = evidence_for_payload(
            resume_record.resume_authorization_record_id, resume_payload
        )
        api.resume(process)
        exited = api.wait(process, request.wall_timeout_seconds * 1000)
        if not exited:
            timed_out = True
            termination_requested = True
            api.terminate_job(job_handle, 9)
            exited = api.wait(process, config.termination_grace_seconds * 1000)
            if exited:
                tree_result = ProcessTreeTerminationResult.TERMINATED_AND_CONFIRMED
                termination_diagnostics = ("WALL_TIMEOUT", "PROCESS_TREE_TERMINATED")
            else:
                tree_result = ProcessTreeTerminationResult.TERMINATION_UNCONFIRMED
                termination_diagnostics = (
                    "WALL_TIMEOUT",
                    "PROCESS_TREE_TERMINATION_UNCONFIRMED",
                )
        else:
            tree_result = ProcessTreeTerminationResult.EXITED
            termination_diagnostics = ("CHILD_EXITED",)
        if exited:
            native_exit_code = api.exit_code(process)
        stdout_overflow = len(process.stdout) > ISOLATED_CAPTURE_MAX_STREAM_BYTES
        stderr_overflow = len(process.stderr) > ISOLATED_CAPTURE_MAX_STREAM_BYTES
        process.stdout = process.stdout[:ISOLATED_CAPTURE_MAX_STREAM_BYTES]
        process.stderr = process.stderr[:ISOLATED_CAPTURE_MAX_STREAM_BYTES]
        if stdout_overflow:
            termination_diagnostics += ("STDOUT_LIMIT_EXCEEDED",)
        if stderr_overflow:
            termination_diagnostics += ("STDERR_LIMIT_EXCEEDED",)
        process.stdout = b""
        process.stderr = b""
    except Exception:
        if resume_evidence is None:
            resume_record = None
        if process is None:
            creation_record = create_child_process_creation_record(
                allocation=request.allocation,
                child_request=config.child_request,
                scheduled_launch_id=request.scheduled_launch_id,
                approved_executable=config.approved_python_executable_evidence,
                software_release=request.software_release,
                process_id=None,
                creation_result=ProcessCreationResult.FAILED,
                job_object_assignment=JobObjectAssignmentResult.NOT_ASSIGNED,
                handle_inheritance=HandleInheritancePosture.DISABLED,
                environment_policy_version=config.environment_policy_version,
                diagnostics=("PROCESS_CREATION_FAILED",),
            )
            creation_payload = serialize_child_process_creation_record(creation_record)
            creation_path = config.process_evidence_directory / _creation_filename(
                creation_record
            )
            publish_canonical_artifact(
                creation_path, creation_payload, parse_child_process_creation_record
            )
            creation_evidence = evidence_for_payload(
                creation_record.process_creation_record_id, creation_payload
            )
        else:
            if creation_record is None:
                creation_record = create_child_process_creation_record(
                    allocation=request.allocation,
                    child_request=config.child_request,
                    scheduled_launch_id=request.scheduled_launch_id,
                    approved_executable=config.approved_python_executable_evidence,
                    software_release=request.software_release,
                    process_id=process.process_id,
                    creation_result=ProcessCreationResult.FAILED,
                    job_object_assignment=JobObjectAssignmentResult.FAILED,
                    handle_inheritance=HandleInheritancePosture.DISABLED,
                    environment_policy_version=config.environment_policy_version,
                    diagnostics=("JOB_ASSIGNMENT_FAILED",),
                )
                creation_payload = serialize_child_process_creation_record(
                    creation_record
                )
                creation_path = config.process_evidence_directory / _creation_filename(
                    creation_record
                )
                publish_canonical_artifact(
                    creation_path,
                    creation_payload,
                    parse_child_process_creation_record,
                )
                creation_evidence = evidence_for_payload(
                    creation_record.process_creation_record_id, creation_payload
                )
            try:
                if job_handle is not None and job_assigned:
                    api.terminate_job(job_handle, 9)
                    termination_requested = True
                else:
                    api.terminate_process(process, 9)
                exited = api.wait(process, config.termination_grace_seconds * 1000)
                tree_result = (
                    ProcessTreeTerminationResult.TERMINATED_AND_CONFIRMED
                    if exited
                    else ProcessTreeTerminationResult.TERMINATION_UNCONFIRMED
                )
            except Exception:
                tree_result = ProcessTreeTerminationResult.TERMINATION_UNCONFIRMED
            termination_diagnostics = (
                "LAUNCH_OPERATION_FAILED",
                (
                    "PROCESS_TREE_TERMINATED"
                    if tree_result
                    is ProcessTreeTerminationResult.TERMINATED_AND_CONFIRMED
                    else "PROCESS_TREE_TERMINATION_UNCONFIRMED"
                ),
            )
    finally:
        if creation_evidence is not None:
            termination_record = create_child_termination_record(
                allocation=request.allocation,
                child_request=config.child_request,
                process_creation=creation_evidence,
                resume_authorization=resume_evidence,
                scheduled_launch_id=request.scheduled_launch_id,
                process_id=None if process is None else process.process_id,
                timed_out=timed_out,
                job_termination_requested=termination_requested,
                process_tree_result=tree_result,
                native_exit_code=native_exit_code,
                diagnostics=termination_diagnostics,
                termination_policy_version=ISOLATED_CAPTURE_TERMINATION_POLICY_VERSION,
            )
            termination_payload = serialize_child_termination_record(termination_record)
            termination_path = (
                config.process_evidence_directory
                / f"child-termination-{termination_record.termination_record_id}.json"
            )
            publish_canonical_artifact(
                termination_path,
                termination_payload,
                parse_child_termination_record,
            )
        if process is not None:
            process.stdout = b""
            process.stderr = b""
            for handle in (
                process.primary_thread_handle,
                process.process_handle,
            ):
                try:
                    api.close_handle(handle)
                except Exception:
                    pass
        if job_handle is not None:
            try:
                api.close_handle(job_handle)
            except Exception:
                pass

    if creation_record is None or termination_record is None:
        raise IsolatedCaptureLauncherError(
            "process evidence could not be completed safely"
        )
    child_classification = None
    if (
        process is not None
        and resume_record is not None
        and not timed_out
        and tree_result is ProcessTreeTerminationResult.EXITED
    ):
        result_payload = _read_exact_file(request.child_result_path)
        result = parse_isolated_capture_child_result(result_payload)
        if (
            result.child_request != config.child_request
            or result.allocation != request.allocation
            or result.attempt_id != request.attempt_id
            or native_exit_code != result.native_exit_code
        ):
            raise IsolatedCaptureLauncherError(
                "canonical child result does not reconcile"
            )
        child_classification = result.classification
        if result.classification is IsolatedCaptureChildClassification.SUCCEEDED:
            if result.snapshot is None:
                raise IsolatedCaptureLauncherError(
                    "successful result has no snapshot evidence"
                )
            snapshot_path = (
                request.snapshot_destination_path
                / f"daily-market-data-snapshot-{result.snapshot.artifact_id}.json"
            )
            snapshot_payload = _read_exact_file(snapshot_path)
            verify_payload_evidence(snapshot_payload, result.snapshot)
            calendar = BoundMarketCalendar(
                XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()
            )
            verified = verify_daily_snapshot(
                snapshot_payload,
                calendar,
                expected_sha256=result.snapshot.sha256,
                expected_byte_length=result.snapshot.byte_length,
            )
            if (
                not verified.passed
                or verified.snapshot is None
                or verified.snapshot.snapshot_id != result.snapshot.artifact_id
            ):
                raise IsolatedCaptureLauncherError(
                    "independent snapshot verification failed"
                )
    return IsolatedCaptureLauncherExecution(
        child_request=request,
        creation_record=creation_record,
        resume_record=resume_record,
        termination_record=termination_record,
        child_classification=child_classification,
        native_exit_code=native_exit_code,
    )


class CtypesWindowsIsolatedProcessApi:
    """CreateProcessW and Job Object adapter with no shell or PATH lookup."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise IsolatedCaptureLauncherError("Windows process launch is unsupported")
        from ctypes import wintypes

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

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("hProcess", wintypes.HANDLE),
                ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_ulonglong)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
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

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateProcessW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(STARTUPINFOW),
            ctypes.POINTER(PROCESS_INFORMATION),
        ]
        kernel32.CreateProcessW.restype = wintypes.BOOL
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
        kernel32.ResumeThread.restype = wintypes.DWORD
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32
        self._wintypes = wintypes
        self._startup_type = STARTUPINFOW
        self._process_type = PROCESS_INFORMATION
        self._limit_type = EXTENDED_LIMIT

    def create_suspended(
        self,
        *,
        executable: Path,
        arguments: tuple[str, ...],
        environment: Mapping[str, str],
        current_directory: Path,
        inherit_handles: bool,
    ) -> NativeSuspendedProcess:
        if inherit_handles:
            raise IsolatedCaptureLauncherError("handle inheritance is prohibited")
        startup = self._startup_type()
        startup.cb = ctypes.sizeof(startup)
        process = self._process_type()
        command = " ".join(
            _quote_windows_argument(value) for value in (str(executable), *arguments)
        )
        command_buffer = ctypes.create_unicode_buffer(command)
        environment_text = (
            "".join(
                f"{key}={value}\0"
                for key, value in sorted(
                    environment.items(), key=lambda item: item[0].upper()
                )
            )
            + "\0"
        )
        environment_buffer = ctypes.create_unicode_buffer(environment_text)
        flags = 0x00000004 | 0x00000400 | 0x08000000
        if not self._kernel32.CreateProcessW(
            str(executable),
            command_buffer,
            None,
            None,
            False,
            flags,
            environment_buffer,
            str(current_directory),
            ctypes.byref(startup),
            ctypes.byref(process),
        ):
            raise IsolatedCaptureLauncherError("CreateProcessW failed")
        return NativeSuspendedProcess(
            int(process.dwProcessId),
            process.hProcess,
            process.hThread,
        )

    def create_job_with_limits(self) -> object:
        handle = self._kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise IsolatedCaptureLauncherError("CreateJobObjectW failed")
        limits = self._limit_type()
        limits.BasicLimitInformation.LimitFlags = 0x00002000 | 0x00000008
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        if not self._kernel32.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self._kernel32.CloseHandle(handle)
            raise IsolatedCaptureLauncherError("SetInformationJobObject failed")
        return handle

    def assign_to_job(
        self, job_handle: object, process: NativeSuspendedProcess
    ) -> None:
        if not self._kernel32.AssignProcessToJobObject(
            job_handle, process.process_handle
        ):
            raise IsolatedCaptureLauncherError("AssignProcessToJobObject failed")

    def resume(self, process: NativeSuspendedProcess) -> None:
        if self._kernel32.ResumeThread(process.primary_thread_handle) == 0xFFFFFFFF:
            raise IsolatedCaptureLauncherError("ResumeThread failed")

    def wait(self, process: NativeSuspendedProcess, timeout_milliseconds: int) -> bool:
        result = int(
            self._kernel32.WaitForSingleObject(
                process.process_handle, timeout_milliseconds
            )
        )
        if result == 0:
            return True
        if result == 258:
            return False
        raise IsolatedCaptureLauncherError("process wait failed")

    def terminate_job(self, job_handle: object, exit_code: int) -> None:
        if not self._kernel32.TerminateJobObject(job_handle, exit_code):
            raise IsolatedCaptureLauncherError("TerminateJobObject failed")

    def terminate_process(
        self, process: NativeSuspendedProcess, exit_code: int
    ) -> None:
        if not self._kernel32.TerminateProcess(process.process_handle, exit_code):
            raise IsolatedCaptureLauncherError("TerminateProcess failed")

    def exit_code(self, process: NativeSuspendedProcess) -> int:
        value = self._wintypes.DWORD()
        if not self._kernel32.GetExitCodeProcess(
            process.process_handle, ctypes.byref(value)
        ):
            raise IsolatedCaptureLauncherError("GetExitCodeProcess failed")
        return int(value.value)

    def close_handle(self, handle: object) -> None:
        if handle and not self._kernel32.CloseHandle(handle):
            raise IsolatedCaptureLauncherError("CloseHandle failed")


def _verify_file_evidence(path: Path, evidence: ArtifactEvidence) -> None:
    payload = _read_exact_file(path, maximum=64 * 1024 * 1024)
    verify_payload_evidence(payload, evidence)


def _creation_filename(record: ChildProcessCreationRecord) -> str:
    return f"child-process-creation-{record.process_creation_record_id}.json"


def _resume_filename(record: ChildResumeAuthorizationRecord) -> str:
    return f"child-resume-authorization-{record.resume_authorization_record_id}.json"


def _read_exact_file(path: Path, *, maximum: int = 512 * 1024) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute():
        raise IsolatedCaptureLauncherConfigError("artifact path must be absolute")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise IsolatedCaptureLauncherConfigError("artifact cannot be read") from error
    if len(payload) > maximum:
        raise IsolatedCaptureLauncherConfigError("artifact exceeds bounded read")
    return payload


def _quote_windows_argument(value: str) -> str:
    if not value or any(character in value for character in ' \t"'):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IsolatedCaptureLauncherConfigError("duplicate config member")
        result[key] = value
    return result


def _reject_number(value: str) -> None:
    raise IsolatedCaptureLauncherConfigError(
        f"unsupported numeric value in launcher config: {value}"
    )


def _artifact(value: object, label: str) -> ArtifactEvidence:
    if type(value) is not dict or set(value) != {
        "artifact_id",
        "sha256",
        "byte_length",
    }:
        raise IsolatedCaptureLauncherConfigError(f"{label} is invalid")
    try:
        artifact_id = UUID(_string(value["artifact_id"], label))
    except ValueError as error:
        raise IsolatedCaptureLauncherConfigError(f"{label} is invalid") from error
    sha256 = _string(value["sha256"], label)
    byte_length = _integer(value["byte_length"], label)
    if (
        str(artifact_id) != value["artifact_id"]
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256)
    ):
        raise IsolatedCaptureLauncherConfigError(f"{label} is invalid")
    return ArtifactEvidence(artifact_id, sha256, byte_length)


def _path(value: object, label: str) -> Path:
    return Path(_string(value, label))


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise IsolatedCaptureLauncherConfigError(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise IsolatedCaptureLauncherConfigError(f"{label} must be an integer")
    return value
