"""C3-B1 child-only Windows Credential Manager boundary for Alpaca market data."""

from __future__ import annotations

import ctypes
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from trading_bot.runtime.windows_authority_security import resolve_current_token_sid
from trading_bot.runtime.windows_effectful_capture import (
    ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
    ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
)

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168
MAX_WINDOWS_CREDENTIAL_BLOB_BYTES = 1024
CRED_MAX_CREDENTIAL_BLOB_SIZE = 5 * 512
MAX_WINDOWS_CREDENTIAL_NATIVE_BLOB_BYTES = CRED_MAX_CREDENTIAL_BLOB_SIZE
_MAX_NATIVE_ADDRESS = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1
_SID_PATTERN = re.compile(r"^S-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))+$")

_ResultT = TypeVar("_ResultT")


class WindowsCredentialReadError(RuntimeError):
    """Credential access failed without carrying secret material."""


class WindowsCredentialNotFoundError(WindowsCredentialReadError):
    """One of the two fixed Alpaca credentials was absent."""


class WindowsCredentialInvalidError(WindowsCredentialReadError):
    """A credential or native result violated the fixed C3 contract."""


class WindowsCredentialSidMismatchError(WindowsCredentialReadError):
    """The child process SID is not the C1-approved Trading SID."""


class WindowsCredentialUnsupportedError(WindowsCredentialReadError):
    """Windows Credential Manager is unavailable on this platform."""


def _validate_native_blob_range(
    address: int | None,
    size: int,
) -> tuple[int, int] | None:
    if type(size) is not int or not 0 <= size <= CRED_MAX_CREDENTIAL_BLOB_SIZE:
        raise WindowsCredentialInvalidError("native credential blob range is invalid")
    if size == 0:
        if address is not None and (
            type(address) is not int or not 0 <= address <= _MAX_NATIVE_ADDRESS
        ):
            raise WindowsCredentialInvalidError(
                "native credential blob range is invalid"
            )
        return None
    if (
        type(address) is not int
        or address <= 0
        or address > _MAX_NATIVE_ADDRESS
        or address + size > _MAX_NATIVE_ADDRESS + 1
    ):
        raise WindowsCredentialInvalidError("native credential blob range is invalid")
    return address, size


@dataclass(slots=True, repr=False)
class NativeCredentialEntry:
    """One native generic credential with all secret/native fields redacted."""

    target_name: str
    credential_type: int
    persistence: int
    blob: bytearray = field(repr=False)
    native_pointer: object | None = field(default=None, repr=False)
    native_blob_address: int | None = field(default=None, repr=False)
    native_blob_size: int | None = field(default=None, repr=False)
    released: bool = field(default=False, repr=False)

    def __repr__(self) -> str:
        return "NativeCredentialEntry(<redacted>)"

    __str__ = __repr__


class WindowsCredentialNativeApi(Protocol):
    """Injectable test surface for exactly two named reads and cleanup."""

    def read_generic(self, target_name: str) -> NativeCredentialEntry: ...

    def release(self, entry: NativeCredentialEntry) -> None: ...


class ScopedAlpacaSecrets:
    """Short-lived child-only secret pair with no public secret properties."""

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
        del args
        self.close()
        return False

    def use(self, consumer: Callable[[str, str], _ResultT]) -> _ResultT:
        """Pass secrets only to one trusted in-process child consumer call."""

        if self._closed:
            raise WindowsCredentialInvalidError("credential scope is closed")
        if not callable(consumer):
            raise WindowsCredentialInvalidError("credential consumer is invalid")
        return consumer(self._api_key_id, self._api_secret_key)

    def close(self) -> None:
        # Python immutable-string storage cannot be guaranteed to be zeroized.
        self._api_key_id = ""
        self._api_secret_key = ""
        self._closed = True


class WindowsAlpacaCredentialManagerReader:
    """Read exactly two fixed credentials after exact child SID verification."""

    __slots__ = ("_native_api", "_sid_resolver")

    def __init__(self) -> None:
        self._native_api: WindowsCredentialNativeApi = CtypesWindowsCredentialNativeApi()
        self._sid_resolver: Callable[[], str] = resolve_current_token_sid

    @classmethod
    def for_test(
        cls,
        *,
        native_api: WindowsCredentialNativeApi,
        sid_resolver: Callable[[], str],
    ) -> WindowsAlpacaCredentialManagerReader:
        if not callable(getattr(native_api, "read_generic", None)) or not callable(
            getattr(native_api, "release", None)
        ):
            raise TypeError("test credential native API is invalid")
        if not callable(sid_resolver):
            raise TypeError("test SID resolver is invalid")
        instance = cls.__new__(cls)
        instance._native_api = native_api
        instance._sid_resolver = sid_resolver
        return instance

    def read(self, approved_account_sid: str) -> ScopedAlpacaSecrets:
        _require_canonical_sid(approved_account_sid)
        try:
            observed_sid = self._sid_resolver()
        except WindowsCredentialReadError:
            raise
        except Exception:
            raise WindowsCredentialInvalidError(
                "current process SID inspection failed"
            ) from None
        if observed_sid != approved_account_sid:
            raise WindowsCredentialSidMismatchError(
                "current process SID does not match approved Trading SID"
            )

        key_entry: NativeCredentialEntry | None = None
        secret_entry: NativeCredentialEntry | None = None
        scoped: ScopedAlpacaSecrets | None = None
        cleanup_failed = False
        try:
            key_entry = self._read_one(ALPACA_API_KEY_ID_CREDENTIAL_TARGET)
            secret_entry = self._read_one(ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET)
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
            _validate_entry(entry, target_name)
        except WindowsCredentialInvalidError as validation_error:
            try:
                self._native_api.release(entry)
            except Exception:
                raise WindowsCredentialInvalidError(
                    "native credential cleanup failed"
                ) from None
            raise validation_error
        return entry


def _validate_entry(entry: NativeCredentialEntry, target_name: str) -> None:
    if entry.released:
        raise WindowsCredentialInvalidError("credential entry is invalid")
    if entry.target_name != target_name:
        raise WindowsCredentialInvalidError("credential target is inconsistent")
    if entry.credential_type != CRED_TYPE_GENERIC:
        raise WindowsCredentialInvalidError("credential type is unsupported")
    if entry.persistence != CRED_PERSIST_LOCAL_MACHINE:
        raise WindowsCredentialInvalidError("credential persistence is unsupported")
    if (
        type(entry.blob) is not bytearray
        or not entry.blob
        or len(entry.blob) > MAX_WINDOWS_CREDENTIAL_BLOB_BYTES
    ):
        raise WindowsCredentialInvalidError("credential value is invalid")

    native_metadata = (
        entry.native_pointer,
        entry.native_blob_address,
        entry.native_blob_size,
    )
    if all(value is None for value in native_metadata):
        return
    if any(value is None for value in native_metadata):
        raise WindowsCredentialInvalidError("native credential blob range is invalid")
    native_range = _validate_native_blob_range(
        entry.native_blob_address,
        entry.native_blob_size,  # type: ignore[arg-type]
    )
    if native_range is None:
        raise WindowsCredentialInvalidError("credential value is invalid")
    if entry.native_blob_size > MAX_WINDOWS_CREDENTIAL_BLOB_BYTES:  # type: ignore[operator]
        raise WindowsCredentialInvalidError(
            "credential value exceeds the approved copy bound"
        )
    if len(entry.blob) != entry.native_blob_size:
        raise WindowsCredentialInvalidError("credential value is invalid")


def _require_canonical_sid(value: object) -> None:
    if (
        type(value) is not str
        or len(value) > 184
        or _SID_PATTERN.fullmatch(value) is None
    ):
        raise WindowsCredentialInvalidError("approved Trading SID is invalid")


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
    """Narrow CredReadW/CredFree implementation for the C3 child."""

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
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
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
        self._zero_memory = getattr(
            self._ntdll,
            "RtlSecureZeroMemory",
            self._ntdll.RtlZeroMemory,
        )
        self._zero_memory.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._zero_memory.restype = ctypes.c_void_p

    def read_generic(self, target_name: str) -> NativeCredentialEntry:
        if type(target_name) is not str or target_name not in {
            ALPACA_API_KEY_ID_CREDENTIAL_TARGET,
            ALPACA_API_SECRET_KEY_CREDENTIAL_TARGET,
        }:
            raise WindowsCredentialInvalidError("credential target is unsupported")
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

        blob = bytearray()
        blob_size = 0
        blob_address: int | None = None
        try:
            credential = pointer.contents
            blob_size = int(credential.CredentialBlobSize)
            raw_address = ctypes.cast(credential.CredentialBlob, ctypes.c_void_p).value
            blob_address = int(raw_address) if raw_address is not None else None
            native_range = _validate_native_blob_range(blob_address, blob_size)
            copied_size = min(blob_size, MAX_WINDOWS_CREDENTIAL_BLOB_BYTES)
            if copied_size:
                if native_range is None:
                    raise WindowsCredentialInvalidError(
                        "native credential blob range is invalid"
                    )
                blob.extend(ctypes.string_at(native_range[0], copied_size))
            return NativeCredentialEntry(
                target_name=credential.TargetName or "",
                credential_type=int(credential.Type),
                persistence=int(credential.Persist),
                blob=blob,
                native_pointer=pointer,
                native_blob_address=blob_address,
                native_blob_size=blob_size,
            )
        except Exception:
            cleanup_failed = False
            try:
                native_range = _validate_native_blob_range(blob_address, blob_size)
                if native_range is not None:
                    self._zero_memory(*native_range)
            except Exception:
                cleanup_failed = True
            finally:
                for index in range(len(blob)):
                    blob[index] = 0
                try:
                    self._advapi32.CredFree(pointer)
                except Exception:
                    cleanup_failed = True
            if cleanup_failed:
                raise WindowsCredentialInvalidError(
                    "credential read cleanup failed"
                ) from None
            raise WindowsCredentialInvalidError("credential read failed") from None

    def release(self, entry: NativeCredentialEntry) -> None:
        if type(entry) is not NativeCredentialEntry:
            raise WindowsCredentialInvalidError("credential entry is invalid")
        if entry.released:
            return

        native_pointer = entry.native_pointer
        native_blob_address = entry.native_blob_address
        native_blob_size = entry.native_blob_size
        entry.native_pointer = None
        entry.native_blob_address = None
        entry.native_blob_size = None
        entry.released = True

        cleanup_failed = False
        try:
            if native_pointer is None or native_blob_size is None:
                cleanup_failed = True
            else:
                native_range = _validate_native_blob_range(
                    native_blob_address,
                    native_blob_size,
                )
                if native_range is not None:
                    self._zero_memory(*native_range)
        except Exception:
            cleanup_failed = True
        finally:
            for index in range(len(entry.blob)):
                entry.blob[index] = 0
            if native_pointer is not None:
                try:
                    self._advapi32.CredFree(native_pointer)
                except Exception:
                    cleanup_failed = True
        if cleanup_failed:
            raise WindowsCredentialInvalidError("native credential cleanup failed")
