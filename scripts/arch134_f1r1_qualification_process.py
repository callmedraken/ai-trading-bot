"""C1 qualification-only process observation. No process-control access rights."""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QualificationProcessEvidence:
    pid: int
    birth: str
    executable: str


def observe_process(pid: int) -> QualificationProcessEvidence | None:
    """Return creation identity plus executable, never infer life from a PID."""
    if type(pid) is not int or pid <= 0:
        raise ValueError("positive process identifier required")
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        # PROCESS_QUERY_LIMITED_INFORMATION only: no terminate/suspend/write rights.
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return None
            raise OSError("process observation unavailable")
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            code = wintypes.DWORD()
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not (
                kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times))
                and kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            ):
                raise OSError("process observation unavailable")
            if code.value != 259:
                return None
            if not kernel.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            ):
                raise OSError("process image observation unavailable")
            birth = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return QualificationProcessEvidence(
                pid, "windows-filetime:" + str(birth), str(Path(buffer.value).resolve())
            )
        finally:
            kernel.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        # Disposable CI portability; start ticks + boot identity detect PID reuse.
        base = Path("/proc") / str(pid)
        try:
            first = (base / "stat").read_text().rsplit(")", 1)[1].split()
            if first[0] == "Z":
                return None
            executable = str((base / "exe").resolve(strict=True))
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            second = (base / "stat").read_text().rsplit(")", 1)[1].split()
            if first[19] != second[19] or second[0] == "Z":
                raise OSError("process observation changed")
            return QualificationProcessEvidence(
                pid, "linux-start:" + boot + ":" + first[19], executable
            )
        except FileNotFoundError:
            return None
    raise OSError("process identity unsupported")


def current_process() -> QualificationProcessEvidence:
    evidence = observe_process(os.getpid())
    if evidence is None:
        raise OSError("own process identity unavailable")
    return evidence
