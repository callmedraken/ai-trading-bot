"""Read-only elevated Administrator token admission, with no object mutation APIs."""

from __future__ import annotations

import ctypes

from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
    RootAclError,
    close_handle,
)


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def _sid_text(advapi: object, kernel: object, sid: object) -> str:
    text = ctypes.c_wchar_p()
    convert = _bind(
        advapi,
        "ConvertSidToStringSidW",
        [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)],
        ctypes.c_int32,
    )
    if not convert(sid, ctypes.byref(text)) or not text.value:
        raise RootAclError("root SID observation failed")
    try:
        value = text.value
        if len(value) > 184:
            raise RootAclError("root SID bound rejected")
        return value
    finally:
        _bind(kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)(text)


def administrator_sid() -> str:
    """Require an elevated enabled Administrators token; exclude SYSTEM/Trading."""
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    token, admin = pointer(), pointer()
    current = _bind(kernel, "GetCurrentProcess", [], pointer)
    open_token = _bind(
        advapi, "OpenProcessToken", [pointer, dword, ctypes.POINTER(pointer)], boolean
    )
    if not open_token(current(), 8, ctypes.byref(token)) or not token.value:
        raise RootAclError("root administrator token rejected")
    free = _bind(kernel, "LocalFree", [pointer], pointer)
    try:
        convert = _bind(
            advapi,
            "ConvertStringSidToSidW",
            [ctypes.c_wchar_p, ctypes.POINTER(pointer)],
            boolean,
        )
        membership = _bind(
            advapi,
            "CheckTokenMembership",
            [pointer, pointer, ctypes.POINTER(boolean)],
            boolean,
        )
        query = _bind(
            advapi,
            "GetTokenInformation",
            [pointer, dword, pointer, dword, ctypes.POINTER(dword)],
            boolean,
        )
        enabled, elevated, size = boolean(), dword(), dword()
        if (
            not convert(ADMINISTRATORS_SID, ctypes.byref(admin))
            or not admin.value
            or not membership(None, admin, ctypes.byref(enabled))
            or not enabled.value
            or not query(
                token,
                20,
                ctypes.byref(elevated),
                ctypes.sizeof(elevated),
                ctypes.byref(size),
            )
            or elevated.value != 1
        ):
            raise RootAclError("root administrator token rejected")
        buffer = ctypes.create_string_buffer(512)
        if not query(token, 1, buffer, len(buffer), ctypes.byref(size)):
            raise RootAclError("root administrator identity rejected")
        user = ctypes.cast(buffer, ctypes.POINTER(pointer)).contents
        sid = _sid_text(advapi, kernel, user)
        if sid in {SYSTEM_SID, TRADING_SID}:
            raise RootAclError("root administrator identity rejected")
        return sid
    finally:
        if admin.value:
            free(admin)
        close_handle(token.value)
