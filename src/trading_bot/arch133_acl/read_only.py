"""Shared inert root observation and exact handle-open semantics."""

from __future__ import annotations

import ctypes
import hashlib
import ntpath
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


class RootOpenError(RootAclError):
    """Numeric status only; no native error text."""

    def __init__(self, win32_error: int) -> None:
        super().__init__("root directory open failed")
        self.win32_error = win32_error


MUTABLE_ROOT_ACCESS = 0xC00E0081
ROOT_SHARE_MODE = 3
ROOT_DISPOSITION = 3
ROOT_FLAGS = 0x02200000


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
        path,
        MUTABLE_ROOT_ACCESS if mutable else 0x20081,
        ROOT_SHARE_MODE,
        None,
        ROOT_DISPOSITION,
        ROOT_FLAGS,
        None,
    )
    if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
        raise RootOpenError(ctypes.get_last_error())
    return handle


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
    return _inspect(handle, expected_path, descriptor_hash=False)[0]


def inspect_directory_security(
    handle: int, expected_path: str
) -> tuple[DirectoryObservation, str]:
    """Independent binary observation and owner/group/DACL descriptor SHA-256."""
    return _inspect(handle, expected_path, descriptor_hash=True)


def _inspect(
    handle: int, expected_path: str, *, descriptor_hash: bool
) -> tuple[DirectoryObservation, str]:
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
    owner, group, dacl, descriptor = pointer(), pointer(), pointer(), pointer()
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
                7 if descriptor_hash else 5,
                ctypes.byref(owner),
                ctypes.byref(group) if descriptor_hash else None,
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
        digest = ""
        if descriptor_hash:
            length = _bind(advapi, "GetSecurityDescriptorLength", [pointer], dword)(
                descriptor
            )
            if not 20 <= length <= 65536:
                raise RootAclError("root descriptor bound rejected")
            digest = hashlib.sha256(ctypes.string_at(descriptor, length)).hexdigest()
        observed = DirectoryObservation(
            _sid_text(advapi, kernel, owner),
            bool(control.value & 0x1000),
            tuple(aces),
            (info.volume, (info.index_high << 32) | info.index_low),
        )
        return observed, digest
    finally:
        if descriptor.value:
            _bind(kernel, "LocalFree", [pointer], pointer)(descriptor)
