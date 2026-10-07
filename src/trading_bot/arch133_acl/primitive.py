"""Shared fixed 133 root policy/native primitive, with standard-library imports only.

No production path, host publisher, runtime, provider, store or scheduler is
importable through this module. Native functions are inert until explicitly called.
"""

from __future__ import annotations

import ctypes
import ntpath
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"
TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
ADMIN_ACES = ((ADMINISTRATORS_SID, 0x1F01FF, 0, 0), (SYSTEM_SID, 0x1F01FF, 0, 0))
ROOT_ACES = ADMIN_ACES + (
    (TRADING_SID, 0x1200AB, 0, 0),
    (TRADING_SID, 0x13019F, 0, 9),
    (ADMINISTRATORS_SID, 0x1F01FF, 0, 9),
    (SYSTEM_SID, 0x1F01FF, 0, 9),
)


class RootAclError(RuntimeError):
    """Fixed diagnostics only; never raw Win32 errors."""


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


def close_handle(handle: int) -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if not _bind(kernel, "CloseHandle", [ctypes.c_void_p], ctypes.c_int32)(handle):
        raise RootAclError("root handle close failed")


def open_directory(path: str, *, mutable: bool = False) -> int:
    """Same Q133-2 root access/share/disposition/no-follow flags."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = _bind(
        kernel,
        "CreateFileW",
        [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ],
        ctypes.c_void_p,
    )
    handle = create(
        path, 0xC00E0081 if mutable else 0x20081, 3, None, 3, 0x02200000, None
    )
    if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
        raise RootAclError("root directory open failed")
    return handle


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


@dataclass(frozen=True, slots=True)
class DirectoryObservation:
    owner_sid: str
    protected: bool
    aces: tuple[tuple[str, int, int, int], ...]
    identity: tuple[int, int]
    filesystem: str = "NTFS"
    reparse: bool = False

    def classification(self) -> str:
        if self.owner_sid == ADMINISTRATORS_SID and self.protected:
            if self.aces == ADMIN_ACES:
                return "ADMIN_SYSTEM_ONLY"
            if self.aces == ROOT_ACES:
                return "EXACT_INTENDED_ROOT"
        return "OTHER_POLICY"


def inspect_directory(handle: int, expected_path: str) -> DirectoryObservation:
    """Independent binary GetSecurityInfo/ACE readback, with no-follow identity.

    The publisher and scratch qualifier both use this readback; no SDDL string
    comparison or successful SetSecurityInfo return alone can admit the root.
    """
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
    final = ctypes.create_unicode_buffer(512)
    get_path = _bind(
        kernel,
        "GetFinalPathNameByHandleW",
        [pointer, ctypes.c_wchar_p, dword, dword],
        dword,
    )
    count = get_path(handle, final, len(final), 0)
    if not 0 < count < len(final) or ntpath.normcase(final.value) != ntpath.normcase(
        "\\\\?\\" + expected_path
    ):
        raise RootAclError("root final path rejected")

    class Information(ctypes.Structure):
        _fields_ = [
            ("attributes", dword),
            ("times", dword * 6),
            ("volume", dword),
            ("size_high", dword),
            ("size_low", dword),
            ("links", dword),
            ("index_high", dword),
            ("index_low", dword),
        ]

    info = Information()
    query = _bind(kernel, "GetFileInformationByHandle", [pointer, pointer], boolean)
    filesystem = ctypes.create_unicode_buffer(32)
    flags = dword()
    volume = _bind(
        kernel,
        "GetVolumeInformationW",
        [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            dword,
            pointer,
            pointer,
            pointer,
            ctypes.c_wchar_p,
            dword,
        ],
        boolean,
    )
    drive = _bind(kernel, "GetDriveTypeW", [ctypes.c_wchar_p], dword)
    if (
        not query(handle, ctypes.byref(info))
        or info.attributes & 0x400
        or not info.attributes & 0x10
        or drive("F:\\") != 3
        or not volume(
            "F:\\",
            None,
            0,
            None,
            None,
            ctypes.byref(flags),
            filesystem,
            len(filesystem),
        )
        or filesystem.value.upper() != "NTFS"
        or not flags.value & 8
    ):
        raise RootAclError("root local NTFS directory rejected")
    owner, dacl, descriptor = pointer(), pointer(), pointer()
    get = _bind(
        advapi,
        "GetSecurityInfo",
        [
            pointer,
            dword,
            dword,
            ctypes.POINTER(pointer),
            pointer,
            ctypes.POINTER(pointer),
            pointer,
            ctypes.POINTER(pointer),
        ],
        dword,
    )
    try:
        if (
            get(
                handle,
                1,
                5,
                ctypes.byref(owner),
                None,
                ctypes.byref(dacl),
                None,
                ctypes.byref(descriptor),
            )
            != 0
            or not owner.value
            or not dacl.value
            or not descriptor.value
        ):
            raise RootAclError("root policy readback failed")
        control, revision = ctypes.c_uint16(), dword()
        get_control = _bind(
            advapi,
            "GetSecurityDescriptorControl",
            [pointer, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(dword)],
            boolean,
        )

        class AclSize(ctypes.Structure):
            _fields_ = [("count", dword), ("used", dword), ("free", dword)]

        size = AclSize()
        get_acl = _bind(
            advapi, "GetAclInformation", [pointer, pointer, dword, dword], boolean
        )
        if (
            not get_control(descriptor, ctypes.byref(control), ctypes.byref(revision))
            or not get_acl(dacl, ctypes.byref(size), ctypes.sizeof(size), 2)
            or size.count > 64
        ):
            raise RootAclError("root policy shape rejected")
        get_ace = _bind(
            advapi, "GetAce", [pointer, dword, ctypes.POINTER(pointer)], boolean
        )
        aces = []
        for index in range(size.count):
            raw = pointer()
            if not get_ace(dacl, index, ctypes.byref(raw)) or not raw.value:
                raise RootAclError("root ACE readback failed")
            header = ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte * 4)).contents
            if header[0] not in (0, 1):
                raise RootAclError("root ACE type rejected")
            mask = ctypes.cast(raw.value + 4, ctypes.POINTER(dword)).contents.value
            aces.append(
                (
                    _sid_text(advapi, kernel, pointer(raw.value + 8)),
                    mask,
                    header[0],
                    header[1],
                )
            )
        return DirectoryObservation(
            _sid_text(advapi, kernel, owner),
            bool(control.value & 0x1000),
            tuple(aces),
            (info.volume, (info.index_high << 32) | info.index_low),
        )
    finally:
        if descriptor.value:
            _bind(kernel, "LocalFree", [pointer], pointer)(descriptor)


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
