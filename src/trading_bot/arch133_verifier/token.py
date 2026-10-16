"""Read-only Architecture-103 process-token observation; no account/LSA APIs."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Protocol


class AuthorityPrincipalError(RuntimeError):
    """Sanitized token admission failure."""


def require_windows_platform() -> None:
    if sys.platform != "win32":
        raise AuthorityPrincipalError("Windows token observation unavailable")


ADMINISTRATORS_SID = "S-1-5-32-544"
MAX_TOKEN_INFORMATION_BYTES = 64 * 1024
MAX_TOKEN_GROUPS = 1024
TOKEN_USER = 1
TOKEN_GROUPS = 2
TOKEN_TYPE = 8
TOKEN_ELEVATION = 20
SE_GROUP_ENABLED = 0x4
SE_GROUP_USE_FOR_DENY_ONLY = 0x10


@dataclass(frozen=True, slots=True)
class TradingTokenObservation:
    user_sid: str
    token_type: int
    thread_token_present: bool
    elevated: bool
    groups: tuple[tuple[str, int], ...]


class TradingTokenObserver(Protocol):
    def observe(self) -> TradingTokenObservation: ...


def require_trading_token(
    approved_sid: str, observation: TradingTokenObservation
) -> None:
    """Require exact approved primary, non-impersonating standard-user facts."""
    if (
        type(observation) is not TradingTokenObservation
        or type(approved_sid) is not str
        or not approved_sid.startswith("S-1-5-21-")
        or observation.user_sid != approved_sid
        or type(observation.token_type) is not int
        or observation.token_type != 1
        or observation.thread_token_present is not False
        or observation.elevated is not False
        or type(observation.groups) is not tuple
        or len(observation.groups) > MAX_TOKEN_GROUPS
    ):
        raise AuthorityPrincipalError("PD1B requires the exact standard Trading token")
    seen: set[str] = set()
    for entry in observation.groups:
        if (
            type(entry) is not tuple
            or len(entry) != 2
            or type(entry[0]) is not str
            or type(entry[1]) is not int
            or not 0 <= entry[1] <= 0xFFFFFFFF
            or entry[0] in seen
        ):
            raise AuthorityPrincipalError("PD1B token group evidence is invalid")
        sid, attributes = entry
        seen.add(sid)
        if (
            sid == ADMINISTRATORS_SID
            and attributes & SE_GROUP_ENABLED
            and not attributes & SE_GROUP_USE_FOR_DENY_ONLY
        ):
            raise AuthorityPrincipalError(
                "PD1B rejects enabled Administrators authority"
            )


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("sid", ctypes.c_void_p), ("attributes", ctypes.c_uint32)]


class _TokenGroups(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32), ("groups", _SidAndAttributes * 1)]


def _bounded_sid(buffer: ctypes.Array, used: int, pointer: int) -> str:
    """Decode SID wire fields only after proving the entire SID is in-buffer."""
    offset = pointer - ctypes.addressof(buffer)
    if not 0 <= offset <= used - 8:
        raise AuthorityPrincipalError("token SID pointer is outside returned bytes")
    header = bytes(buffer[offset : offset + 8])
    count = header[1]
    if header[0] != 1 or count > 15 or offset + 8 + count * 4 > used:
        raise AuthorityPrincipalError("token SID has invalid bounded structure")
    raw = bytes(buffer[offset : offset + 8 + count * 4])
    authority = int.from_bytes(raw[2:8], "big")
    subauthorities = [
        str(int.from_bytes(raw[i : i + 4], "little")) for i in range(8, len(raw), 4)
    ]
    return "-".join(("S", "1", str(authority), *subauthorities))


def _parse_user(buffer: ctypes.Array, used: int) -> str:
    if not ctypes.sizeof(_SidAndAttributes) <= used <= ctypes.sizeof(buffer):
        raise AuthorityPrincipalError("TokenUser length is invalid")
    entry = _SidAndAttributes.from_buffer(buffer)
    return _bounded_sid(buffer, used, entry.sid or 0)


def _parse_groups(buffer: ctypes.Array, used: int) -> tuple[tuple[str, int], ...]:
    offset = _TokenGroups.groups.offset
    if not offset <= used <= ctypes.sizeof(buffer):
        raise AuthorityPrincipalError("TokenGroups length is invalid")
    count = ctypes.c_uint32.from_buffer(buffer).value
    if (
        count > MAX_TOKEN_GROUPS
        or offset + count * ctypes.sizeof(_SidAndAttributes) > used
    ):
        raise AuthorityPrincipalError("TokenGroups count exceeds returned bytes/bound")
    entries = (_SidAndAttributes * count).from_buffer(buffer, offset)
    return tuple(
        (_bounded_sid(buffer, used, entry.sid or 0), int(entry.attributes))
        for entry in entries
    )


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


class WindowsTradingTokenObserver:
    """Exact Win32 TOKEN_QUERY observer. Construction itself performs no query."""

    def observe(self) -> TradingTokenObservation:
        require_windows_platform()
        return self._observe(
            ctypes.WinDLL("kernel32", use_last_error=True),
            ctypes.WinDLL("advapi32", use_last_error=True),
            ctypes.get_last_error,
        )

    def _observe(
        self, kernel: object, advapi: object, last_error
    ) -> TradingTokenObservation:
        # This deliberately binds only token-query and handle APIs, never LSA,
        # account lookup, WindowsPrincipal, or group/account mutation APIs.
        handle = ctypes.c_void_p
        dword = ctypes.c_uint32
        boolean = ctypes.c_int32
        process = _bind(kernel, "GetCurrentProcess", [], handle)
        thread = _bind(kernel, "GetCurrentThread", [], handle)
        close = _bind(kernel, "CloseHandle", [handle], boolean)
        open_process = _bind(
            advapi, "OpenProcessToken", [handle, dword, ctypes.POINTER(handle)], boolean
        )
        open_thread = _bind(
            advapi,
            "OpenThreadToken",
            [handle, dword, boolean, ctypes.POINTER(handle)],
            boolean,
        )
        information = _bind(
            advapi,
            "GetTokenInformation",
            [handle, ctypes.c_int32, ctypes.c_void_p, dword, ctypes.POINTER(dword)],
            boolean,
        )

        def thread_present() -> bool:
            token = handle()
            if open_thread(thread(), 0x8, True, ctypes.byref(token)):
                if not token.value:
                    raise AuthorityPrincipalError("OpenThreadToken returned no handle")
                close(token)
                return True
            if last_error() != 1008:  # ERROR_NO_TOKEN is the only accepted absence.
                raise AuthorityPrincipalError("thread token absence is unproven")
            return False

        def query(token: ctypes.c_void_p, kind: int) -> tuple[ctypes.Array, int]:
            size = dword()
            if (
                information(token, kind, None, 0, ctypes.byref(size))
                or last_error() != 122
            ):
                raise AuthorityPrincipalError("token information size query failed")
            if not 1 <= size.value <= MAX_TOKEN_INFORMATION_BYTES:
                raise AuthorityPrincipalError("token information exceeds source bound")
            buffer = ctypes.create_string_buffer(size.value)
            used = dword()
            if not information(token, kind, buffer, size, ctypes.byref(used)):
                raise AuthorityPrincipalError("token information query failed")
            if not 1 <= used.value <= size.value:
                raise AuthorityPrincipalError(
                    "token information returned invalid length"
                )
            return buffer, used.value

        def scalar(token: ctypes.c_void_p, kind: int, allowed: set[int]) -> int:
            # Fixed-size TOKEN_TYPE/TOKEN_ELEVATION fields use their exact
            # native DWORD buffer; not every class supports a zero-size probe.
            buffer = ctypes.create_string_buffer(4)
            used = dword()
            if not information(token, kind, buffer, 4, ctypes.byref(used)):
                raise AuthorityPrincipalError("token scalar query failed")
            if used.value != 4:
                raise AuthorityPrincipalError("token scalar length is invalid")
            value = ctypes.c_uint32.from_buffer(buffer).value
            if value not in allowed:
                raise AuthorityPrincipalError("token scalar value is invalid")
            return value

        impersonating = thread_present()
        token = handle()
        if not open_process(process(), 0x8, ctypes.byref(token)) or not token.value:
            raise AuthorityPrincipalError("primary process token is unavailable")
        try:
            user = _parse_user(*query(token, TOKEN_USER))
            token_type = scalar(token, TOKEN_TYPE, {1, 2})
            elevated = bool(scalar(token, TOKEN_ELEVATION, {0, 1}))
            groups = _parse_groups(*query(token, TOKEN_GROUPS))
            # Repeat independently; do not short-circuit the second native query.
            final_thread = thread_present()
            return TradingTokenObservation(
                user, token_type, impersonating or final_thread, elevated, groups
            )
        finally:
            close(token)
