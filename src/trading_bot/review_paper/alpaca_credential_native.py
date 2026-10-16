"""Inert D1R4 Win32 adapters; current token, fixed global mutex and v3 targets."""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes

from trading_bot.review_paper.alpaca_credential_generation import (
    MUTEX_NAME,
    TARGETS,
    GenerationError,
    clear_credential,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    CRED_PERSIST_LOCAL_MACHINE,
    CRED_TYPE_GENERIC,
    read_fixed_current_product_credential,
    validate_alpaca_credential_bytes,
)
from trading_bot.runtime.windows_authority_security import (
    MUTEX_ALL_ACCESS,
    MUTEX_MODIFY_STATE,
    READ_CONTROL,
    SYNCHRONIZE,
    SecurityAce,
    SecurityObjectType,
    SecurityPolicy,
    build_security_attributes,
    inspect_handle_security,
    resolve_current_token_sid,
)

ADMINISTRATORS = "S-1-5-32-544"
SYSTEM = "S-1-5-18"
_PROCESS_LOCK = threading.Lock()
_POISONED = False


def _target(target: str) -> None:
    if type(target) is not str or target not in TARGETS:
        raise GenerationError("fixed v3 target required")


class WindowsV3CredentialStore:
    """Only exact current-product records; no API initialization on import."""

    def __repr__(self) -> str:
        return "WindowsV3CredentialStore(<redacted>)"

    def read(self, target: str) -> bytearray | None:
        _target(target)
        return read_fixed_current_product_credential(target)

    def write(self, target: str, value: bytearray) -> bool:
        _target(target)
        validate_alpaca_credential_bytes(value)
        if os.name != "nt":
            raise GenerationError("Windows credential storage unavailable")

        class Credential(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        copy = bytearray(value)
        failed = False
        result = False
        try:
            buffer = (ctypes.c_ubyte * len(copy)).from_buffer(copy)
            record = Credential()
            record.Type = CRED_TYPE_GENERIC
            record.TargetName = target
            record.Persist = CRED_PERSIST_LOCAL_MACHINE
            record.CredentialBlobSize = len(copy)
            record.CredentialBlob = buffer
            api = ctypes.WinDLL("advapi32", use_last_error=True)
            api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
            api.CredWriteW.restype = wintypes.BOOL
            result = bool(api.CredWriteW(ctypes.byref(record), 0))
        except Exception:
            failed = True
        finally:
            clear_credential(copy)
        if failed:
            raise GenerationError("credential write outcome unknown")
        return result

    def delete(self, target: str) -> bool:
        _target(target)
        if os.name != "nt":
            raise GenerationError("Windows credential storage unavailable")
        failed = False
        result = False
        try:
            api = ctypes.WinDLL("advapi32", use_last_error=True)
            api.CredDeleteW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            api.CredDeleteW.restype = wintypes.BOOL
            result = bool(api.CredDeleteW(target, CRED_TYPE_GENERIC, 0))
        except Exception:
            failed = True
        if failed:
            raise GenerationError("credential delete outcome unknown")
        return result


def provisioning_mutex_policy(sid: str, owner: str) -> SecurityPolicy:
    """Architecture-77 kernel-object discipline, bound to current runtime SID."""
    if owner not in {sid, ADMINISTRATORS, SYSTEM}:
        raise GenerationError("unexpected provisioning mutex owner")
    return SecurityPolicy(
        owner,
        (
            SecurityAce(ADMINISTRATORS, MUTEX_ALL_ACCESS),
            SecurityAce(SYSTEM, MUTEX_ALL_ACCESS),
            SecurityAce(sid, MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE),
        ),
    )


class WindowsV3Exclusion:
    """Zero-wait global exclusion; no fallback/takeover, no process reentrancy."""

    def __init__(self) -> None:
        self.owned = self.abandoned = False
        self._handle = None
        self._reserved = False

    def acquire(self) -> bool:
        if _POISONED or self._reserved or os.name != "nt":
            raise GenerationError("provisioning exclusion unavailable")
        if not _PROCESS_LOCK.acquire(blocking=False):
            return False
        self._reserved = True
        try:
            sid = resolve_current_token_sid()
            policy = provisioning_mutex_policy(sid, sid)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexExW.argtypes = [
                ctypes.c_void_p,
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            kernel.CreateMutexExW.restype = ctypes.c_void_p
            with build_security_attributes(policy) as attributes:
                self._handle = kernel.CreateMutexExW(
                    ctypes.byref(attributes.attributes),
                    MUTEX_NAME,
                    0,
                    MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE,
                )
            if not self._handle:
                raise GenerationError("provisioning mutex create/open failed")
            owner, protected, aces = inspect_handle_security(
                self._handle, SecurityObjectType.KERNEL
            )
            if not protected or aces != provisioning_mutex_policy(sid, owner).aces:
                raise GenerationError("provisioning mutex security rejected")
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            result = int(kernel.WaitForSingleObject(self._handle, 0))
            if result == 258:
                self.release()
                return False
            if result not in {0, 0x80}:
                raise GenerationError("provisioning mutex acquisition failed")
            self.owned = True
            self.abandoned = result == 0x80
            return True
        except BaseException:
            self.release()
            raise

    def release(self) -> None:
        global _POISONED
        failed = False
        try:
            if self._handle:
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
                kernel.ReleaseMutex.restype = wintypes.BOOL
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel.CloseHandle.restype = wintypes.BOOL
                try:
                    if self.owned and not kernel.ReleaseMutex(self._handle):
                        failed = True
                finally:
                    if not kernel.CloseHandle(self._handle):
                        failed = True
        except Exception:
            failed = True
        finally:
            self._handle = None
            self.owned = False
            if self._reserved:
                self._reserved = False
                _PROCESS_LOCK.release()
        if failed:
            _POISONED = True
            raise GenerationError("provisioning exclusion release uncertain")
