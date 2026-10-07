"""Shared fixed 133 root policy/native primitive, with standard-library imports only.

No production path, host publisher, runtime, provider, store or scheduler is
importable through this module. Native functions are inert until explicitly called.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterator
from contextlib import contextmanager

from trading_bot.arch133_acl.read_only import (
    ADMIN_ACES as ADMIN_ACES,
)
from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID as ADMINISTRATORS_SID,
)
from trading_bot.arch133_acl.read_only import (
    ROOT_ACES as ROOT_ACES,
)
from trading_bot.arch133_acl.read_only import (
    SYSTEM_SID as SYSTEM_SID,
)
from trading_bot.arch133_acl.read_only import (
    TRADING_SID as TRADING_SID,
)
from trading_bot.arch133_acl.read_only import (
    DirectoryObservation as DirectoryObservation,
)
from trading_bot.arch133_acl.read_only import (
    RootAclError as RootAclError,
)
from trading_bot.arch133_acl.read_only import (
    close_handle as close_handle,
)
from trading_bot.arch133_acl.read_only import (
    inspect_directory as inspect_directory,
)
from trading_bot.arch133_acl.read_only import (
    open_directory as open_directory,
)


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def apply_root_policy_status(handle: int) -> int:
    """The exact 133-H conversion/SetSecurityInfo primitive, without retry.

    A DWORD is returned verbatim, never GetLastError, HRESULT conversion, text
    formatting, or an exception payload. The caller must fail closed on nonzero.
    """
    sddl = f"O:{ADMINISTRATORS_SID}D:P" + "".join(
        f"(A;{'OIIO' if ace[3] == 9 else ''};0x{ace[1]:x};;;{ace[0]})"
        for ace in ROOT_ACES
    )
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    boolean = ctypes.c_int32
    dword = ctypes.c_uint32
    free = _bind(kernel, "LocalFree", [pointer], pointer)
    convert = _bind(
        advapi,
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        [ctypes.c_wchar_p, dword, ctypes.POINTER(pointer), ctypes.POINTER(dword)],
        boolean,
    )
    get_owner = _bind(
        advapi,
        "GetSecurityDescriptorOwner",
        [pointer, ctypes.POINTER(pointer), ctypes.POINTER(boolean)],
        boolean,
    )
    get_dacl = _bind(
        advapi,
        "GetSecurityDescriptorDacl",
        [
            pointer,
            ctypes.POINTER(boolean),
            ctypes.POINTER(pointer),
            ctypes.POINTER(boolean),
        ],
        boolean,
    )
    set_security = _bind(
        advapi,
        "SetSecurityInfo",
        [pointer, dword, dword, pointer, pointer, pointer, pointer],
        dword,
    )
    descriptor, owner, dacl = pointer(), pointer(), pointer()
    present, defaulted = boolean(), boolean()
    try:
        if not convert(sddl, 1, ctypes.byref(descriptor), None) or not descriptor.value:
            raise RootAclError("publication root descriptor rejected")
        if (
            not get_owner(descriptor, ctypes.byref(owner), ctypes.byref(defaulted))
            or not owner.value
            or not get_dacl(
                descriptor,
                ctypes.byref(present),
                ctypes.byref(dacl),
                ctypes.byref(defaulted),
            )
            or not present.value
            or not dacl.value
        ):
            raise RootAclError("publication root descriptor rejected")
        # SE_FILE_OBJECT; OWNER | DACL | PROTECTED_DACL_SECURITY_INFORMATION.
        status = set_security(handle, 1, 0x80000005, owner, None, dacl, None)
        if type(status) is not int or not 0 <= status <= 0xFFFFFFFF:
            raise RootAclError("root ACL status rejected")
        return status
    finally:
        if descriptor.value:
            free(descriptor)


def create_admin_directory(path: str) -> None:
    """Exact binary Administrator/SYSTEM creation policy shared by both callers."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = _bind(
        kernel, "CreateDirectoryW", [ctypes.c_wchar_p, ctypes.c_void_p], ctypes.c_int32
    )
    with admin_security_attributes() as attributes:
        if not create(path, ctypes.byref(attributes)):
            raise RootAclError("root directory create failed")


@contextmanager
def admin_security_attributes() -> Iterator[ctypes.Structure]:
    """A103's binary builder specialized to its exact two-ACE ADMIN_POLICY.

    Both root creators call this implementation. It preserves the original
    revision, ACL sizing, control, owner/DACL and non-inheritable handle fields.
    """
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    free = _bind(kernel, "LocalFree", [pointer], pointer)
    buffers = []
    try:
        convert = _bind(
            advapi,
            "ConvertStringSidToSidW",
            [ctypes.c_wchar_p, ctypes.POINTER(pointer)],
            boolean,
        )
        for text in (ADMINISTRATORS_SID, ADMINISTRATORS_SID, SYSTEM_SID):
            sid = pointer()
            if not convert(text, ctypes.byref(sid)) or not sid.value:
                raise RootAclError("root creation SID rejected")
            buffers.append(sid)
        length = _bind(advapi, "GetLengthSid", [pointer], dword)
        size = 8 + sum(8 + int(length(sid)) for sid in buffers[1:])
        acl = ctypes.create_string_buffer(size)
        initialize = _bind(advapi, "InitializeAcl", [pointer, dword, dword], boolean)
        add = _bind(
            advapi,
            "AddAccessAllowedAceEx",
            [pointer, dword, dword, dword, pointer],
            boolean,
        )
        if not initialize(acl, size, 2):
            raise RootAclError("root creation ACL rejected")
        for sid in buffers[1:]:
            if not add(acl, 2, 0, 0x1F01FF, sid):
                raise RootAclError("root creation ACE rejected")
        descriptor = ctypes.create_string_buffer(256)
        init = _bind(advapi, "InitializeSecurityDescriptor", [pointer, dword], boolean)
        control = _bind(
            advapi,
            "SetSecurityDescriptorControl",
            [pointer, ctypes.c_uint16, ctypes.c_uint16],
            boolean,
        )
        owner = _bind(
            advapi, "SetSecurityDescriptorOwner", [pointer, pointer, boolean], boolean
        )
        dacl = _bind(
            advapi,
            "SetSecurityDescriptorDacl",
            [pointer, boolean, pointer, boolean],
            boolean,
        )
        if (
            not init(descriptor, 1)
            or not control(descriptor, 0x1000, 0x1000)
            or not owner(descriptor, buffers[0], False)
            or not dacl(descriptor, True, acl, False)
        ):
            raise RootAclError("root creation descriptor rejected")

        class Attributes(ctypes.Structure):
            _fields_ = [
                ("length", dword),
                ("descriptor", pointer),
                ("inherit_handle", boolean),
            ]

        yield Attributes(ctypes.sizeof(Attributes), ctypes.addressof(descriptor), False)
    finally:
        for sid in buffers:
            free(sid)


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
