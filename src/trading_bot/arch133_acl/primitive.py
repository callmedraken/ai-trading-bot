"""Shared fixed 133 root policy/native primitive, with standard-library imports only.

No production path, host publisher, runtime, provider, store or scheduler is
importable through this module. Native functions are inert until explicitly called.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterator
from contextlib import contextmanager

from trading_bot.arch133_acl.administrator import administrator_sid as administrator_sid
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
from trading_bot.arch133_acl.root_policy_apply import (
    apply_root_policy_status as apply_root_policy_status,
)


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


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
