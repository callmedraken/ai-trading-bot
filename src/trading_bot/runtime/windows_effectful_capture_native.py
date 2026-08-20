"""C3-C1 Windows containment for one not-yet-resumed capture child.

C3-C1 owns only native containment. It does not bind C2 execution IDs, write
A2 request bytes, resume/wait/terminate the child, parse results, or publish a
snapshot. Production executable/entrypoint/TEMP bindings are intentionally
left to the later C3 composition checkpoint.
"""

from __future__ import annotations

import ctypes
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Protocol

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
GENERIC_WRITE = 0x40000000
CREATE_NEW = 1
FILE_ATTRIBUTE_NORMAL = 0x00000080
ERROR_INSUFFICIENT_BUFFER = 122


class WindowsEffectfulCaptureNativeError(RuntimeError):
    """C3 native containment failed without exposing native error text."""


class WindowsEffectfulCaptureNativeUnsupportedError(WindowsEffectfulCaptureNativeError):
    """The C3 native boundary is unavailable on this platform."""


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
    def create_pipe(self, buffer_size: int) -> NativePipePair: ...
    def set_handle_inheritable(self, handle: int, inheritable: bool) -> None: ...
    def create_staging_file(self, path: str) -> int: ...

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

    def close_handle(self, handle: int) -> None: ...


class SuspendedCaptureChild:
    """Private live handles for one contained process still suspended at entry."""

    __slots__ = ("_api", "_closed", "_handles", "process_id", "thread_id")

    def __init__(
        self,
        api: WindowsEffectfulCaptureNativeApi,
        process: NativeCreatedProcess,
        handles: tuple[int, int, int, int],
        *,
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
        self._handles = retained
        self.process_id = process.process_id
        self.thread_id = process.thread_id
        self._closed = False

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

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        failed = False
        for handle in self._handles:
            try:
                self._api.close_handle(handle)
            except Exception:
                failed = True
        if failed:
            raise WindowsEffectfulCaptureNativeError(
                "native suspended-child cleanup failed"
            ) from None


_SUSPENDED_CHILD_ISSUER = object()


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
        "create_pipe",
        "set_handle_inheritable",
        "create_staging_file",
        "create_suspended_process",
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
    try:
        job = _handle(native_api.create_job_object(), "job handle")
        acquired.append(job)
        native_api.set_job_limits(job)

        request = native_api.create_pipe(MAX_C3_CHILD_REQUEST_BYTES)
        if type(request) is not NativePipePair:
            raise WindowsEffectfulCaptureNativeError("request pipe result is invalid")
        acquired.extend((request.read_handle, request.write_handle))
        native_api.set_handle_inheritable(request.write_handle, False)

        result = native_api.create_pipe(MAX_C3_CHILD_RESULT_BYTES)
        if type(result) is not NativePipePair:
            raise WindowsEffectfulCaptureNativeError("result pipe result is invalid")
        acquired.extend((result.read_handle, result.write_handle))
        native_api.set_handle_inheritable(result.read_handle, False)

        staging_handle = _handle(
            native_api.create_staging_file(staging), "staging handle"
        )
        acquired.append(staging_handle)
        child_handles = (request.read_handle, result.write_handle, staging_handle)
        if len(set(child_handles)) != 3:
            raise WindowsEffectfulCaptureNativeError("child handles must be distinct")

        bootstrap_args = (*args, *_handle_bootstrap_arguments(child_handles))
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
        acquired.extend((process.process_handle, process.primary_thread_handle))

        for child_pipe_handle in (request.read_handle, result.write_handle):
            native_api.close_handle(child_pipe_handle)
            acquired.remove(child_pipe_handle)
        native_api.set_handle_inheritable(staging_handle, False)

        child = SuspendedCaptureChild(
            native_api,
            process,
            (request.write_handle, result.read_handle, staging_handle, job),
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
        if cleanup_failed:
            raise WindowsEffectfulCaptureNativeError(
                "native containment failed and cleanup was incomplete"
            ) from None
        if isinstance(error, WindowsEffectfulCaptureNativeError):
            raise
        raise WindowsEffectfulCaptureNativeError("native containment failed") from None


class CtypesWindowsEffectfulCaptureNativeApi:
    """ctypes implementation of the exact C3-C1 process topology."""

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

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(SECURITY_ATTRIBUTES),
            wintypes.DWORD,
        ]
        k32.CreatePipe.restype = wintypes.BOOL
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
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        self._k32 = k32
        self._w = wintypes
        self._sa = SECURITY_ATTRIBUTES
        self._startup = STARTUPINFOEXW
        self._pi = PROCESS_INFORMATION
        self._limits = EXTENDED_LIMIT

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

    def create_pipe(self, buffer_size: int) -> NativePipePair:
        if type(buffer_size) is not int or buffer_size <= 0:
            raise WindowsEffectfulCaptureNativeError("pipe bound is invalid")
        sa = self._sa(ctypes.sizeof(self._sa), None, True)
        read = self._w.HANDLE()
        write = self._w.HANDLE()
        if not self._k32.CreatePipe(
            ctypes.byref(read),
            ctypes.byref(write),
            ctypes.byref(sa),
            buffer_size,
        ):
            raise _native_error("CreatePipe")
        return NativePipePair(
            _native_handle(read, "pipe read handle"),
            _native_handle(write, "pipe write handle"),
        )

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

    def create_staging_file(self, path: str) -> int:
        sa = self._sa(ctypes.sizeof(self._sa), None, True)
        value = self._k32.CreateFileW(
            _windows_path(path, "staging path"),
            GENERIC_WRITE,
            0,
            ctypes.byref(sa),
            CREATE_NEW,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        raw = _native_handle(value, "staging handle", allow_invalid=True)
        if raw == ctypes.c_void_p(-1).value:
            raise _native_error("CreateFileW")
        return _handle(raw, "staging handle")

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
                raise _native_error("CreateProcessW")
            return NativeCreatedProcess(
                int(pi.dwProcessId),
                int(pi.dwThreadId),
                _native_handle(pi.hProcess, "process handle"),
                _native_handle(pi.hThread, "primary thread handle"),
            )
        finally:
            if initialized:
                self._k32.DeleteProcThreadAttributeList(attrs)

    def close_handle(self, handle: int) -> None:
        if not self._k32.CloseHandle(self._w.HANDLE(_handle(handle, "close handle"))):
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
