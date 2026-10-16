"""Bounded current-account credential reads; no SDK, provider or write APIs."""

from __future__ import annotations

import ctypes
import json
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

TOKEN_TARGET = "AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1"
CLIENT_INFO_TARGET = "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
CRED_MAX_CREDENTIAL_BLOB_SIZE = 2560
_MAX_ADDRESS = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1


class WindowsOAuthStorageError(RuntimeError):
    """Sanitized storage failure."""


class WindowsOAuthStorageSizeError(WindowsOAuthStorageError):
    """State exceeds the single Windows generic credential record limit."""


def _zero(blob: bytearray) -> None:
    for index in range(len(blob)):
        blob[index] = 0


def _require_target(target: str) -> None:
    if type(target) is not str or target not in {TOKEN_TARGET, CLIENT_INFO_TARGET}:
        raise WindowsOAuthStorageError("OAuth credential target is invalid")


def _blob_range(address: int | None, size: int) -> bool:
    return (
        type(size) is int
        and 0 < size <= CRED_MAX_CREDENTIAL_BLOB_SIZE
        and type(address) is int
        and 0 < address <= _MAX_ADDRESS
        and address + size <= _MAX_ADDRESS + 1
    )


class WindowsCredentialReader:
    """Read-only CredReadW generic records in the current Windows account."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise WindowsOAuthStorageError("Windows OAuth storage is unavailable")
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
        return "WindowsCredentialReader(<redacted>)"

    __str__ = __repr__

    def read_generic(self, target: str) -> bytearray | None:
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
                oversized = size > CRED_MAX_CREDENTIAL_BLOB_SIZE
                if (
                    record.TargetName != target
                    or record.Type != CRED_TYPE_GENERIC
                    or record.Persist != CRED_PERSIST_LOCAL_MACHINE
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
                raise WindowsOAuthStorageSizeError(
                    "OAuth credential exceeds record limit"
                )
            raise WindowsOAuthStorageError("OAuth credential read or cleanup failed")
        return None if missing else blob


@dataclass(frozen=True, slots=True)
class OAuthAvailability:
    persisted_oauth_available: bool
    oauth_storage_reads: int


def _record(blob: bytearray | None) -> dict | None:
    if blob is None:
        return None
    if (
        type(blob) is not bytearray
        or not 0 < len(blob) <= CRED_MAX_CREDENTIAL_BLOB_SIZE
    ):
        raise WindowsOAuthStorageError("OAuth credential rejected")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    value = json.loads(
        blob,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
    )
    if type(value) is not dict:
        raise ValueError
    return value


def _client_available(client: dict) -> bool:
    # Validate the persisted registration's known data fields without importing
    # the SDK package (which exposes provider/request methods). SDK placeholders
    # are inert: absent, None and empty string have the same meaning here.
    value = {
        key: item for key, item in client.items() if item is not None and item != ""
    }
    if type(value.get("client_id")) is not str or not value["client_id"]:
        return False
    strings = (
        "client_secret",
        "issuer",
        "token_endpoint_auth_method",
        "application_type",
        "scope",
        "client_name",
        "software_id",
        "software_version",
    )
    if any(key in value and type(value[key]) is not str for key in strings):
        return False
    for key in ("client_id_issued_at", "client_secret_expires_at"):
        if key in value and type(value[key]) is not int:
            return False
    for key in ("grant_types", "response_types", "contacts", "redirect_uris"):
        if key in value and (
            type(value[key]) is not list
            or any(type(item) is not str for item in value[key])
        ):
            return False
    for uri in value.get("redirect_uris", []):
        if not uri or any(char.isspace() for char in uri) or not urlsplit(uri).scheme:
            return False
    for key in ("client_uri", "logo_uri", "tos_uri", "policy_uri", "jwks_uri"):
        if key in value:
            if type(value[key]) is not str:
                return False
            parsed = urlsplit(value[key])
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return False
    return True


def persisted_oauth_availability() -> OAuthAvailability:
    """Two fixed CredReadW records, never SDK/client/provider composition.

    This availability predicate grants no token or refresh authority. As in the
    accepted get_tokens path, a token requires its associated registration.
    Only the boolean and actual number of native record reads escape.
    """
    native = WindowsCredentialReader()
    blobs = []
    reads = 0
    try:
        for target in (TOKEN_TARGET, CLIENT_INFO_TARGET):
            reads += 1
            blobs.append(native.read_generic(target))
        token, client = (_record(blob) for blob in blobs)
        if token is None:
            return OAuthAvailability(False, reads)
        if client is None:
            raise ValueError
        for record, name in ((token, "access_token"), (client, "client_id")):
            if type(record.get(name)) is not str or not record[name]:
                raise ValueError
        if (
            type(token.get("token_type", "bearer")) is not str
            or token.get("token_type", "bearer").title() != "Bearer"
            or not _client_available(client)
        ):
            raise ValueError
        expiry = token.get("expires_in")
        if expiry is not None and (type(expiry) is not int or expiry <= 0):
            raise ValueError
        for name in ("refresh_token", "scope"):
            if token.get(name) is not None and type(token[name]) is not str:
                raise ValueError
        return OAuthAvailability(True, reads)
    except BaseException:
        raise WindowsOAuthStorageError("OAuth availability failed closed") from None
    finally:
        for blob in blobs:
            if type(blob) is bytearray:
                _zero(blob)
