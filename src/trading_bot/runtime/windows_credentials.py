"""Narrow, read-only Windows Credential Manager access for the capture child."""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass, field
from typing import Protocol

from trading_bot.runtime.capture_attempt_authority import (
    CredentialPersistence,
    CredentialStoreType,
    WindowsMarketDataCredentialReference,
)

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168
MAX_WINDOWS_CREDENTIAL_BLOB_BYTES = 1024


class WindowsCredentialReadError(RuntimeError):
    """Credential access failed without carrying credential material."""


class WindowsCredentialNotFoundError(WindowsCredentialReadError):
    """One of the two exact referenced credentials was absent."""


class WindowsCredentialInvalidError(WindowsCredentialReadError):
    """A referenced credential violated the approved fixed contract."""


class WindowsCredentialSidMismatchError(WindowsCredentialReadError):
    """The current process SID is not the reference owner."""


class WindowsCredentialUnsupportedError(WindowsCredentialReadError):
    """The Credential Manager boundary is unavailable."""


@dataclass(slots=True, repr=False)
class NativeCredentialEntry:
    """One native generic credential; blob and handle are always redacted."""

    target_name: str
    credential_type: int
    persistence: int
    blob: bytearray = field(repr=False)
    native_pointer: object | None = field(default=None, repr=False)
    native_blob_address: int | None = field(default=None, repr=False)
    released: bool = field(default=False, repr=False)

    def __repr__(self) -> str:
        return "NativeCredentialEntry(<redacted>)"

    __str__ = __repr__


class WindowsCredentialNativeApi(Protocol):
    """Injectable surface: exact SID lookup, two named reads, and cleanup only."""

    def current_process_sid(self) -> str: ...

    def read_generic(self, target_name: str) -> NativeCredentialEntry: ...

    def release(self, entry: NativeCredentialEntry) -> None: ...


class ScopedAlpacaSecrets:
    """Short-lived secret pair with redacted representations."""

    __slots__ = ("_api_key_id", "_api_secret_key", "_closed")

    def __init__(self, api_key_id: str, api_secret_key: str) -> None:
        self._api_key_id = api_key_id
        self._api_secret_key = api_secret_key
        self._closed = False

    def __repr__(self) -> str:
        return "ScopedAlpacaSecrets(<redacted>)"

    __str__ = __repr__

    def __enter__(self) -> ScopedAlpacaSecrets:
        if self._closed:
            raise WindowsCredentialInvalidError("credential scope is closed")
        return self

    def __exit__(self, *args: object) -> bool:
        self.close()
        return False

    def as_provider_mapping(self) -> dict[str, str]:
        if self._closed:
            raise WindowsCredentialInvalidError("credential scope is closed")
        return {
            "APCA_API_KEY_ID": self._api_key_id,
            "APCA_API_SECRET_KEY": self._api_secret_key,
        }

    def close(self) -> None:
        # Python immutable-string storage cannot be guaranteed to be zeroized.
        self._api_key_id = ""
        self._api_secret_key = ""
        self._closed = True


class WindowsCredentialManagerReader:
    """Read exactly two generic credentials after exact SID verification."""

    def __init__(self, native_api: WindowsCredentialNativeApi | None = None) -> None:
        if native_api is None:
            native_api = CtypesWindowsCredentialNativeApi()
        self._native_api = native_api

    def verify_current_sid(
        self, reference: WindowsMarketDataCredentialReference
    ) -> str:
        _verified_reference(reference)
        try:
            sid = self._native_api.current_process_sid()
        except WindowsCredentialReadError:
            raise
        except Exception:
            raise WindowsCredentialInvalidError(
                "current process SID inspection failed"
            ) from None
        if sid != reference.owner_account_sid:
            raise WindowsCredentialSidMismatchError(
                "current process SID does not match credential owner"
            )
        return sid

    def read(
        self, reference: WindowsMarketDataCredentialReference
    ) -> ScopedAlpacaSecrets:
        _verified_reference(reference)
        verified_sid = self.verify_current_sid(reference)
        return self.read_after_sid_verification(reference, verified_sid)

    def read_after_sid_verification(
        self,
        reference: WindowsMarketDataCredentialReference,
        verified_sid: str,
    ) -> ScopedAlpacaSecrets:
        """Read only after a SID value from ``verify_current_sid`` reconciles."""
        _verified_reference(reference)
        if verified_sid != reference.owner_account_sid:
            raise WindowsCredentialSidMismatchError(
                "current process SID does not match credential owner"
            )
        key_entry: NativeCredentialEntry | None = None
        secret_entry: NativeCredentialEntry | None = None
        scoped: ScopedAlpacaSecrets | None = None
        cleanup_failed = False
        try:
            key_entry = self._read_one(reference.api_key_id_target_name)
            secret_entry = self._read_one(reference.api_secret_key_target_name)
            key = _decode_credential(key_entry)
            secret = _decode_credential(secret_entry)
            scoped = ScopedAlpacaSecrets(key, secret)
        finally:
            for entry in (secret_entry, key_entry):
                if entry is not None:
                    try:
                        self._native_api.release(entry)
                    except Exception:
                        cleanup_failed = True
        if cleanup_failed:
            if scoped is not None:
                scoped.close()
            raise WindowsCredentialInvalidError("native credential cleanup failed")
        if scoped is None:
            raise WindowsCredentialInvalidError("credential value is invalid")
        return scoped

    def _read_one(self, target_name: str) -> NativeCredentialEntry:
        try:
            entry = self._native_api.read_generic(target_name)
        except WindowsCredentialNotFoundError:
            raise
        except WindowsCredentialReadError:
            raise
        except Exception:
            raise WindowsCredentialInvalidError("credential read failed") from None
        if type(entry) is not NativeCredentialEntry:
            raise WindowsCredentialInvalidError("credential entry is invalid")
        try:
            if entry.target_name != target_name:
                raise WindowsCredentialInvalidError("credential target is inconsistent")
            if entry.credential_type != CRED_TYPE_GENERIC:
                raise WindowsCredentialInvalidError("credential type is unsupported")
            if entry.persistence != CRED_PERSIST_LOCAL_MACHINE:
                raise WindowsCredentialInvalidError(
                    "credential persistence is unsupported"
                )
            if (
                type(entry.blob) is not bytearray
                or not entry.blob
                or len(entry.blob) > MAX_WINDOWS_CREDENTIAL_BLOB_BYTES
            ):
                raise WindowsCredentialInvalidError("credential value is invalid")
        except WindowsCredentialInvalidError:
            try:
                self._native_api.release(entry)
            except Exception:
                pass
            raise
        return entry


def _verified_reference(
    reference: WindowsMarketDataCredentialReference,
) -> None:
    if type(reference) is not WindowsMarketDataCredentialReference:
        raise WindowsCredentialInvalidError("credential reference is invalid")
    if (
        reference.store_type
        is not CredentialStoreType.WINDOWS_CREDENTIAL_MANAGER_GENERIC
        or reference.persistence is not CredentialPersistence.LOCAL_MACHINE
        or reference.api_key_id_target_name == reference.api_secret_key_target_name
    ):
        raise WindowsCredentialInvalidError("credential reference is unsupported")


def _decode_credential(entry: NativeCredentialEntry) -> str:
    try:
        value = bytes(entry.blob).decode("utf-8")
    except UnicodeDecodeError:
        raise WindowsCredentialInvalidError("credential value is malformed") from None
    if (
        not value
        or value != value.strip()
        or any(character in value for character in ("\r", "\n", "\0"))
    ):
        raise WindowsCredentialInvalidError("credential value is malformed")
    return value


class CtypesWindowsCredentialNativeApi:
    """CredReadW/CredFree plus exact current-process SID inspection."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsCredentialUnsupportedError(
                "Windows Credential Manager is unsupported"
            )
        from ctypes import wintypes

        class CREDENTIALW(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWrittenLow", wintypes.DWORD),
                ("LastWrittenHigh", wintypes.DWORD),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        self._credential_type = CREDENTIALW
        self._wintypes = wintypes
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._secur32 = ctypes.WinDLL("secur32", use_last_error=True)
        self._ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        credential_pointer = ctypes.POINTER(CREDENTIALW)
        self._advapi32.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(credential_pointer),
        ]
        self._advapi32.CredReadW.restype = wintypes.BOOL
        self._advapi32.CredFree.argtypes = [ctypes.c_void_p]
        self._advapi32.CredFree.restype = None
        self._kernel32.GetCurrentProcess.argtypes = []
        self._kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        self._advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self._advapi32.OpenProcessToken.restype = wintypes.BOOL
        self._advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._advapi32.GetTokenInformation.restype = wintypes.BOOL
        self._advapi32.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self._advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        # ``RtlSecureZeroMemory`` is a Windows SDK intrinsic and is not
        # exported by every supported ntdll build.  Use the exported
        # ``RtlZeroMemory`` entry point when the intrinsic is unavailable so
        # native credential buffers are still cleared before ``CredFree``.
        self._zero_memory = getattr(
            self._ntdll,
            "RtlSecureZeroMemory",
            self._ntdll.RtlZeroMemory,
        )
        self._zero_memory.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._zero_memory.restype = ctypes.c_void_p

    def current_process_sid(self) -> str:
        token = self._wintypes.HANDLE()
        if not self._advapi32.OpenProcessToken(
            self._kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)
        ):
            raise WindowsCredentialInvalidError("current process SID inspection failed")
        try:
            required = self._wintypes.DWORD()
            self._advapi32.GetTokenInformation(
                token, 1, None, 0, ctypes.byref(required)
            )
            if required.value == 0 or required.value > 64 * 1024:
                raise WindowsCredentialInvalidError(
                    "current process SID inspection failed"
                )
            buffer = ctypes.create_string_buffer(required.value)
            if not self._advapi32.GetTokenInformation(
                token,
                1,
                buffer,
                required,
                ctypes.byref(required),
            ):
                raise WindowsCredentialInvalidError(
                    "current process SID inspection failed"
                )
            sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
            sid_text = self._wintypes.LPWSTR()
            if not self._advapi32.ConvertSidToStringSidW(
                sid_pointer, ctypes.byref(sid_text)
            ):
                raise WindowsCredentialInvalidError(
                    "current process SID inspection failed"
                )
            try:
                value = sid_text.value
                if not value:
                    raise WindowsCredentialInvalidError(
                        "current process SID inspection failed"
                    )
                return value
            finally:
                self._kernel32.LocalFree(sid_text)
        finally:
            self._kernel32.CloseHandle(token)

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        pointer = ctypes.POINTER(self._credential_type)()
        if not self._advapi32.CredReadW(
            target_name,
            CRED_TYPE_GENERIC,
            0,
            ctypes.byref(pointer),
        ):
            error = ctypes.get_last_error()
            if error == ERROR_NOT_FOUND:
                raise WindowsCredentialNotFoundError("credential was not found")
            raise WindowsCredentialInvalidError("credential read failed")
        credential = pointer.contents
        blob_size = int(credential.CredentialBlobSize)
        copied_size = min(blob_size, MAX_WINDOWS_CREDENTIAL_BLOB_BYTES + 1)
        blob_address = (
            ctypes.addressof(credential.CredentialBlob.contents)
            if copied_size and credential.CredentialBlob
            else None
        )
        blob = (
            bytearray(ctypes.string_at(blob_address, copied_size))
            if blob_address is not None
            else bytearray()
        )
        return NativeCredentialEntry(
            target_name=credential.TargetName or "",
            credential_type=int(credential.Type),
            persistence=int(credential.Persist),
            blob=blob,
            native_pointer=pointer,
            native_blob_address=blob_address,
        )

    def release(self, entry: NativeCredentialEntry) -> None:
        if entry.released:
            return
        if entry.native_blob_address is not None and entry.blob:
            self._zero_memory(
                entry.native_blob_address,
                len(entry.blob),
            )
        for index in range(len(entry.blob)):
            entry.blob[index] = 0
        if entry.native_pointer is not None:
            self._advapi32.CredFree(entry.native_pointer)
        entry.native_pointer = None
        entry.native_blob_address = None
        entry.released = True
