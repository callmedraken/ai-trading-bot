"""Current-product fixed Alpaca CredReadW boundary; no operational authority."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from typing import TypeVar

CREDENTIAL_POLICY = "windows-credential-manager-alpaca-market-data/v3"
API_KEY_TARGET = "AITradingBot/MarketData/Alpaca/ApiKeyId/v3"
API_SECRET_TARGET = "AITradingBot/MarketData/Alpaca/ApiSecretKey/v3"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
CRED_MAX_CREDENTIAL_BLOB_SIZE = 2560
MAX_SECRET_BYTES = 1024
_MAX_ADDRESS = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1


class AlpacaCredentialReadError(RuntimeError):
    """Sanitized storage failure."""


class AlpacaCredentialSizeError(AlpacaCredentialReadError):
    """State exceeds the single Windows generic credential record limit."""


def _zero(blob: bytearray) -> None:
    for index in range(len(blob)):
        blob[index] = 0


def _require_target(target: str) -> None:
    if type(target) is not str or target not in {API_KEY_TARGET, API_SECRET_TARGET}:
        raise AlpacaCredentialReadError("Alpaca credential target is invalid")


def _blob_range(address: int | None, size: int) -> bool:
    return (
        type(size) is int
        and 0 < size <= CRED_MAX_CREDENTIAL_BLOB_SIZE
        and type(address) is int
        and 0 < address <= _MAX_ADDRESS
        and address + size <= _MAX_ADDRESS + 1
    )


class _WindowsCredentialReader:
    """Read-only CredReadW generic records in the current Windows account."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise AlpacaCredentialReadError("Windows Alpaca storage is unavailable")
        from ctypes import wintypes

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

        self._credential = Credential
        self._api = ctypes.WinDLL("advapi32", use_last_error=True)
        pointer = ctypes.POINTER(Credential)
        self._api.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(pointer),
        ]
        self._api.CredReadW.restype = wintypes.BOOL
        self._api.CredFree.argtypes = [ctypes.c_void_p]
        self._api.CredFree.restype = None
        ntdll = ctypes.WinDLL("ntdll")
        self._zero_memory = getattr(ntdll, "RtlSecureZeroMemory", ntdll.RtlZeroMemory)
        self._zero_memory.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._zero_memory.restype = ctypes.c_void_p

    def __repr__(self) -> str:
        return "_WindowsCredentialReader(<redacted>)"

    __str__ = __repr__

    def read_fixed(self, target: str) -> bytearray | None:
        _require_target(target)
        pointer = ctypes.POINTER(self._credential)()
        blob = bytearray()
        address = None
        size = 0
        failed = False
        oversized = False
        missing = False
        cleanup_failed = False
        try:
            if not self._api.CredReadW(
                target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)
            ):
                missing = ctypes.get_last_error() == 1168
                failed = not missing
            else:
                record = pointer.contents
                size = int(record.CredentialBlobSize)
                address = ctypes.cast(record.CredentialBlob, ctypes.c_void_p).value
                oversized = size > MAX_SECRET_BYTES
                if (
                    record.TargetName != target
                    or record.Type != CRED_TYPE_GENERIC
                    or record.Persist != CRED_PERSIST_LOCAL_MACHINE
                    or oversized
                    or not _blob_range(address, size)
                ):
                    failed = True
                else:
                    # Copy directly to mutable Python storage.
                    blob = bytearray(size)
                    destination = (ctypes.c_ubyte * size).from_buffer(blob)
                    ctypes.memmove(destination, address, size)
        except Exception:
            failed = True
        finally:
            if bool(pointer):
                try:
                    if address is None:
                        size = int(pointer.contents.CredentialBlobSize)
                        address = ctypes.cast(
                            pointer.contents.CredentialBlob, ctypes.c_void_p
                        ).value
                    if _blob_range(address, size):
                        self._zero_memory(address, size)
                except Exception:
                    cleanup_failed = True
                finally:
                    try:
                        self._api.CredFree(pointer)
                    except Exception:
                        cleanup_failed = True
        if failed or oversized or cleanup_failed:
            _zero(blob)
            if oversized:
                raise AlpacaCredentialSizeError(
                    "Alpaca credential exceeds record limit"
                )
            raise AlpacaCredentialReadError("Alpaca credential read or cleanup failed")
        return None if missing else blob


_Result = TypeVar("_Result")


class ScopedAlpacaSecrets:
    """Short-lived redacted pair; immutable Python strings cannot be zeroized."""

    __slots__ = ("_key", "_secret", "_closed")

    def __init__(self, key: str, secret: str) -> None:
        self._key, self._secret, self._closed = key, secret, False

    def __repr__(self) -> str:
        return "ScopedAlpacaSecrets(<redacted>)"

    __str__ = __repr__

    def __enter__(self) -> ScopedAlpacaSecrets:
        if self._closed:
            raise AlpacaCredentialReadError("credential scope closed")
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def use(self, consumer: Callable[[str, str], _Result]) -> _Result:
        if self._closed:
            raise AlpacaCredentialReadError("credential scope closed")
        try:
            return consumer(self._key, self._secret)
        except Exception:
            raise AlpacaCredentialReadError("credential consumer failed") from None

    def close(self) -> None:
        self._key = self._secret = ""
        self._closed = True


def _decode(blob: bytearray | None) -> str:
    if type(blob) is not bytearray or not 0 < len(blob) <= MAX_SECRET_BYTES:
        raise AlpacaCredentialReadError("credential absent or invalid")
    try:
        value = blob.decode("utf-8", errors="strict")
    except Exception:
        raise AlpacaCredentialReadError("credential malformed") from None
    if not value or value != value.strip() or any(c in value for c in "\r\n\0"):
        raise AlpacaCredentialReadError("credential malformed")
    return value


def read_current_product_alpaca_secrets() -> ScopedAlpacaSecrets:
    """Read only the two established records; never consult process environment."""
    blobs = []
    try:
        reader = _WindowsCredentialReader()
        for target in (API_KEY_TARGET, API_SECRET_TARGET):
            blobs.append(reader.read_fixed(target))
        key, secret = (_decode(blob) for blob in blobs)
        return ScopedAlpacaSecrets(key, secret)
    except Exception:
        raise AlpacaCredentialReadError("Alpaca credential readiness failed") from None
    finally:
        for blob in blobs:
            if type(blob) is bytearray:
                _zero(blob)


def validate_alpaca_credential_bytes(blob: bytearray) -> None:
    """Apply the same strict secret invariants to interactive/provisioned bytes."""
    _decode(blob)


def read_fixed_current_product_credential(target: str) -> bytearray | None:
    """Read a fixed v3 record; caller owns and must clear the mutable copy."""
    _require_target(target)
    blob = _WindowsCredentialReader().read_fixed(target)
    if blob is not None:
        failed = False
        try:
            validate_alpaca_credential_bytes(blob)
        except Exception:
            failed = True
        if failed:
            _zero(blob)
            raise AlpacaCredentialReadError("Alpaca credential readiness failed")
    return blob
