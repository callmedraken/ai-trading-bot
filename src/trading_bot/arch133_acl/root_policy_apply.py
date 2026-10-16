"""Frozen root-policy application to an already-open handle; no creation authority."""

from __future__ import annotations

import ctypes
from contextvars import ContextVar

from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    ROOT_ACES,
    RootAclError,
)

_native_attempts: ContextVar[int] = ContextVar("root_policy_native_attempts", default=0)


def native_application_attempts() -> int:
    """Read the current context's actual SetSecurityInfo invocation count."""
    return _native_attempts.get()


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    if name == "SetSecurityInfo":

        def invoke(*values):
            _native_attempts.set(_native_attempts.get() + 1)
            return function(*values)

        return invoke
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
