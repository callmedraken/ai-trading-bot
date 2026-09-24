"""A124-2 fixed D10 native read substrate.

This self-contained file has no top-level action. A124-3 adds cryptographic,
inventory, lease, and second-stage orchestration after this admission boundary.
"""

from __future__ import annotations

import ctypes
import ntpath
import os
import re
from contextlib import ExitStack
from ctypes import wintypes
from dataclasses import dataclass

D10_ROOT = r"F:\AITradingBot\D10"
D10_LAUNCH_GUARD = D10_ROOT + r"\launch-guard.py"
D10_ATTESTATION = D10_ROOT + r"\deployment.attestation.json"
D10_SIGNATURE = D10_ROOT + r"\deployment.attestation.sig"
D10_MANIFEST = D10_ROOT + r"\executable-manifest.json"
D10_SOURCE_ROOT = D10_ROOT + r"\source"
D10_SOURCE_PACKAGE_ROOT = D10_SOURCE_ROOT + r"\src"
D10_SECOND_STAGE_LAUNCHER = (
    D10_SOURCE_ROOT + r"\scripts\run_personal_desktop_unattended_one_week_soak.py"
)
D10_CACHE_PREFIX = D10_ROOT + r"\no-pycache"
D10_PRODUCTION_PYTHON = r"F:\AITradingBot\runtime\python.exe"
# Measured with -I -S. Path identity only; A124-4 qualifies runtime security.
D10_PRODUCTION_SITE_PACKAGES = r"F:\AITradingBot\runtime\Lib\site-packages"
TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"
ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"

_DIRECTORIES = (D10_ROOT, D10_SOURCE_ROOT)
_TRUST_FILES = (D10_LAUNCH_GUARD, D10_ATTESTATION, D10_SIGNATURE, D10_MANIFEST)
_INSTALLING = tuple(path + ".installing" for path in (*_TRUST_FILES, D10_SOURCE_ROOT))
_ABSENT = (*_INSTALLING, D10_CACHE_PREFIX)
_FIXED = frozenset((*_DIRECTORIES, *_TRUST_FILES))
_FILE_LIMITS = {
    D10_LAUNCH_GUARD: 512 * 1024,
    D10_ATTESTATION: 64 * 1024,
    D10_SIGNATURE: 64,
    D10_MANIFEST: 8 * 1024 * 1024,
}
_AGGREGATE_LIMIT = sum(_FILE_LIMITS.values())

FILE_READ_DATA = 0x0001
FILE_READ_EA = 0x0008
FILE_TRAVERSE = 0x0020
FILE_READ_ATTRIBUTES = 0x0080
READ_CONTROL = 0x00020000
SYNCHRONIZE = 0x00100000
FILE_ALL_ACCESS = 0x001F01FF
TRADING_FILE_READ = (
    FILE_READ_DATA | FILE_READ_EA | FILE_READ_ATTRIBUTES | READ_CONTROL | SYNCHRONIZE
)
TRADING_DIRECTORY_READ = TRADING_FILE_READ | FILE_TRAVERSE
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
SE_DACL_PROTECTED = 0x1000
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INSUFFICIENT_BUFFER = 122
DRIVE_FIXED = 3
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.I)


class GuardBlocked(RuntimeError):
    """A D10 pre-source admission fact is absent or ambiguous."""


class _NativeError(GuardBlocked):
    def __init__(self, operation: str, code: int) -> None:
        super().__init__(f"{operation} failed ({code})")
        self.code = code


@dataclass(frozen=True, slots=True)
class Ace:
    sid: str
    mask: int
    ace_type: int = 0
    flags: int = 0


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    owner: str
    protected: bool
    aces: tuple[Ace, ...]


DIRECTORY_POLICY = SecurityPolicy(
    ADMINISTRATORS_SID,
    True,
    (
        Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
        Ace(SYSTEM_SID, FILE_ALL_ACCESS),
        Ace(TRADING_SID, TRADING_DIRECTORY_READ),
    ),
)
FILE_POLICY = SecurityPolicy(
    ADMINISTRATORS_SID,
    True,
    (
        Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
        Ace(SYSTEM_SID, FILE_ALL_ACCESS),
        Ace(TRADING_SID, TRADING_FILE_READ),
    ),
)


@dataclass(frozen=True, slots=True)
class ObjectFacts:
    final_path: str
    attributes: int
    drive_type: int
    volume_root: str
    filesystem: str
    volume_serial: int
    file_index: int
    links: int
    size: int
    owner: str
    protected: bool
    aces: tuple[Ace, ...]


@dataclass(frozen=True, slots=True)
class _TrustBytes:
    guard: bytes
    attestation: bytes
    signature: bytes
    manifest: bytes


def _require_fixed(path: str) -> None:
    if type(path) is not str or path not in _FIXED:
        raise GuardBlocked("path is outside fixed D10 trust objects")


def _source_path(relative: str) -> str:
    """Admit one canonical manifest-relative source path without touching disk."""
    if type(relative) is not str or not relative or relative.startswith("/"):
        raise GuardBlocked("source path is not relative")
    if "\\" in relative or ":" in relative or "\x00" in relative:
        raise GuardBlocked("source path has alternate syntax")
    if not (
        relative.startswith("src/trading_bot/")
        or relative == "scripts/run_personal_desktop_unattended_one_week_soak.py"
    ):
        raise GuardBlocked("source path is outside the sealed inventory")
    for component in relative.split("/"):
        if (
            component in ("", ".", "..")
            or component.endswith((".", " "))
            or _DEVICE.fullmatch(component)
            or component.casefold() == "__pycache__"
            or component.casefold().endswith((".pyc", ".pyo"))
            or any(ord(char) < 32 or char in '<>"|?*' for char in component)
        ):
            raise GuardBlocked("source path has unsafe component")
    path = D10_SOURCE_ROOT + "\\" + relative.replace("/", "\\")
    if not path.startswith(D10_SOURCE_ROOT + "\\") or ntpath.normpath(path) != path:
        raise GuardBlocked("source path escaped sealed root")
    return path


def _expected_path(path: str) -> None:
    if path in _FIXED:
        return
    if not path.startswith(D10_SOURCE_ROOT + "\\"):
        raise GuardBlocked("native open is outside fixed D10")
    relative = path[len(D10_SOURCE_ROOT) + 1 :].replace("\\", "/")
    if relative in ("src", "src/trading_bot", "scripts"):
        return
    if relative.startswith("src/trading_bot/"):
        _source_path(relative + "/placeholder.py")
        return
    if _source_path(relative) != path:
        raise GuardBlocked("native source path is not canonical")


def _require_facts(path: str, directory: bool, facts: ObjectFacts) -> None:
    if (
        type(facts) is not ObjectFacts
        or facts.final_path != path
        or bool(facts.attributes & FILE_ATTRIBUTE_DIRECTORY) != directory
        or facts.attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or facts.drive_type != DRIVE_FIXED
        or facts.volume_root != "F:\\"
        or facts.filesystem != "NTFS"
    ):
        raise GuardBlocked("D10 object path, type, or volume changed")
    policy = DIRECTORY_POLICY if directory else FILE_POLICY
    if (facts.owner, facts.protected, facts.aces) != (
        policy.owner,
        policy.protected,
        policy.aces,
    ):
        raise GuardBlocked("D10 object owner or DACL differs")
    if not directory and facts.links != 1:
        raise GuardBlocked("D10 file is hard-linked")


def _stable(before: ObjectFacts, after: ObjectFacts) -> None:
    if before != after:
        raise GuardBlocked("D10 pinned object drifted")


def _read_fixed_trust_material(native: _Native | None = None) -> _TrustBytes:
    """Private A124-3 input; handles and authority never escape this operation."""
    backend = _Native() if native is None else native
    with ExitStack() as stack:
        pinned: list[tuple[str, bool, int, ObjectFacts]] = []
        for path in (*_DIRECTORIES, *_TRUST_FILES):
            directory = path in _DIRECTORIES
            handle = backend.open(path, directory=directory)
            stack.callback(backend.close, handle)
            facts = backend.inspect(handle)
            _require_facts(path, directory, facts)
            pinned.append((path, directory, handle, facts))
        for path in _ABSENT:
            backend.require_absent(path)
        values: dict[str, bytes] = {}
        total = 0
        for path, _, handle, facts in pinned:
            if path not in _FILE_LIMITS:
                continue
            limit = _FILE_LIMITS[path]
            if facts.size <= 0 or facts.size > limit:
                raise GuardBlocked("D10 trust-file size is out of bounds")
            total += facts.size
            if total > _AGGREGATE_LIMIT:
                raise GuardBlocked("D10 trust-material aggregate is too large")
            data = backend.read_exact(handle, facts.size)
            if type(data) is not bytes or len(data) != facts.size:
                raise GuardBlocked("D10 same-handle read length differs")
            values[path] = data
        if len(values[D10_SIGNATURE]) != 64:
            raise GuardBlocked("detached D10 signature length differs")
        for path, directory, handle, before in pinned:
            after = backend.inspect(handle)
            _require_facts(path, directory, after)
            _stable(before, after)
        return _TrustBytes(
            values[D10_LAUNCH_GUARD],
            values[D10_ATTESTATION],
            values[D10_SIGNATURE],
            values[D10_MANIFEST],
        )


def verify_fixed_trust_material() -> tuple[int, int, int, int]:
    """Sanitized read-only evidence, with no raw bytes or native handles."""
    require_trading_principal()
    material = _read_fixed_trust_material()
    return tuple(
        len(part)
        for part in (
            material.guard,
            material.attestation,
            material.signature,
            material.manifest,
        )
    )


def _win_dll(name: str) -> object:
    if os.name != "nt":
        raise GuardBlocked("D10 native verification requires Windows")
    return ctypes.WinDLL(name, use_last_error=True)


def _error(operation: str) -> _NativeError:
    return _NativeError(operation, ctypes.get_last_error())


def _sid_string(pointer: object) -> str:
    advapi = _win_dll("advapi32")
    convert = advapi.ConvertSidToStringSidW
    convert.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    convert.restype = wintypes.BOOL
    value = ctypes.c_wchar_p()
    if not convert(pointer, ctypes.byref(value)):
        raise _error("ConvertSidToStringSidW")
    try:
        if not value.value:
            raise GuardBlocked("empty Windows SID")
        return value.value
    finally:
        _local_free(ctypes.cast(value, ctypes.c_void_p))


def _local_free(pointer: object) -> None:
    free = _win_dll("kernel32").LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    free(pointer)


def _security(handle: int) -> tuple[str, bool, tuple[Ace, ...]]:
    advapi = _win_dll("advapi32")
    get = advapi.GetSecurityInfo
    get.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get.restype = wintypes.DWORD
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    status = get(
        handle,
        1,
        0x1 | 0x4,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if status or not owner.value or not dacl.value or not descriptor.value:
        raise _NativeError("GetSecurityInfo", int(status))
    try:
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        get_control = advapi.GetSecurityDescriptorControl
        get_control.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_control.restype = wintypes.BOOL
        if not get_control(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            raise _error("GetSecurityDescriptorControl")

        class AclSize(ctypes.Structure):
            _fields_ = [
                ("count", wintypes.DWORD),
                ("used", wintypes.DWORD),
                ("free", wintypes.DWORD),
            ]

        info = AclSize()
        acl_info = advapi.GetAclInformation
        acl_info.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        acl_info.restype = wintypes.BOOL
        if not acl_info(dacl, ctypes.byref(info), ctypes.sizeof(info), 2):
            raise _error("GetAclInformation")
        if info.count != 3:
            raise GuardBlocked("D10 DACL ACE count differs")

        class AceHeader(ctypes.Structure):
            _fields_ = [
                ("ace_type", ctypes.c_ubyte),
                ("flags", ctypes.c_ubyte),
                ("size", wintypes.WORD),
            ]

        get_ace = advapi.GetAce
        get_ace.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        get_ace.restype = wintypes.BOOL
        aces: list[Ace] = []
        for index in range(info.count):
            raw = ctypes.c_void_p()
            if not get_ace(dacl, index, ctypes.byref(raw)):
                raise _error("GetAce")
            header = ctypes.cast(raw, ctypes.POINTER(AceHeader)).contents
            if header.ace_type != 0 or header.size < 12:
                raise GuardBlocked("D10 DACL contains unsupported ACE")
            mask = ctypes.cast(
                raw.value + 4, ctypes.POINTER(wintypes.DWORD)
            ).contents.value
            sid = _sid_string(ctypes.c_void_p(raw.value + 8))
            aces.append(Ace(sid, int(mask), header.ace_type, header.flags))
        return _sid_string(owner), bool(control.value & SE_DACL_PROTECTED), tuple(aces)
    finally:
        _local_free(descriptor)


class _ByHandleInfo(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("creation_low", wintypes.DWORD),
        ("creation_high", wintypes.DWORD),
        ("access_low", wintypes.DWORD),
        ("access_high", wintypes.DWORD),
        ("write_low", wintypes.DWORD),
        ("write_high", wintypes.DWORD),
        ("volume_serial", wintypes.DWORD),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD),
        ("file_index_high", wintypes.DWORD),
        ("file_index_low", wintypes.DWORD),
    ]


class _Native:
    """Private ctypes read surface. Paths are checked before every Win32 open."""

    def open(self, path: str, *, directory: bool) -> int:
        _expected_path(path)
        create = _win_dll("kernel32").CreateFileW
        create.argtypes = [
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        handle = create(
            path,
            FILE_READ_DATA | FILE_READ_ATTRIBUTES | READ_CONTROL | SYNCHRONIZE,
            1,  # FILE_SHARE_READ only: pinned objects cannot be replaced.
            None,
            3,  # OPEN_EXISTING
            FILE_FLAG_OPEN_REPARSE_POINT
            | (FILE_FLAG_BACKUP_SEMANTICS if directory else 0),
            None,
        )
        if handle in (None, 0, _INVALID_HANDLE):
            raise _error("CreateFileW(D10)")
        return int(handle)

    def close(self, handle: int) -> None:
        close = _win_dll("kernel32").CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        if not close(handle):
            raise _error("CloseHandle(D10)")

    def require_absent(self, path: str) -> None:
        if path not in _ABSENT:
            raise GuardBlocked("presence probe is outside reserved D10 names")
        create = _win_dll("kernel32").CreateFileW
        create.argtypes = [
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        handle = create(
            path,
            FILE_READ_ATTRIBUTES,
            1,
            None,
            3,
            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle not in (None, 0, _INVALID_HANDLE):
            self.close(int(handle))
            raise GuardBlocked("reserved D10 name is present")
        error = ctypes.get_last_error()
        if error not in (ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND):
            raise _NativeError("CreateFileW(reserved D10 name)", error)

    def inspect(self, handle: int) -> ObjectFacts:
        kernel = _win_dll("kernel32")
        get_final = kernel.GetFinalPathNameByHandleW
        get_final.argtypes = [
            wintypes.HANDLE,
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        get_final.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_final(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise _error("GetFinalPathNameByHandleW")
        if not buffer.value.startswith("\\\\?\\"):
            raise GuardBlocked("D10 final path namespace differs")
        final = buffer.value[4:]
        _expected_path(final)

        class AttributeTag(ctypes.Structure):
            _fields_ = [("attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]

        tag = AttributeTag()
        get_ex = kernel.GetFileInformationByHandleEx
        get_ex.argtypes = [
            wintypes.HANDLE,
            wintypes.INT,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        get_ex.restype = wintypes.BOOL
        if not get_ex(handle, 9, ctypes.byref(tag), ctypes.sizeof(tag)):
            raise _error("GetFileInformationByHandleEx")
        info = _ByHandleInfo()
        get_info = kernel.GetFileInformationByHandle
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandleInfo)]
        get_info.restype = wintypes.BOOL
        if not get_info(handle, ctypes.byref(info)):
            raise _error("GetFileInformationByHandle")
        if tag.attributes != info.attributes:
            raise GuardBlocked("D10 attribute inspections differ")

        get_volume_path = kernel.GetVolumePathNameW
        get_volume_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD]
        get_volume_path.restype = wintypes.BOOL
        root = ctypes.create_unicode_buffer(8)
        if not get_volume_path(final, root, len(root)):
            raise _error("GetVolumePathNameW")
        get_drive = kernel.GetDriveTypeW
        get_drive.argtypes = [ctypes.c_wchar_p]
        get_drive.restype = wintypes.UINT
        drive_type = int(get_drive(root.value))
        fs = ctypes.create_unicode_buffer(64)
        serial = wintypes.DWORD()
        get_volume_info = kernel.GetVolumeInformationW
        get_volume_info.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            wintypes.DWORD,
        ]
        get_volume_info.restype = wintypes.BOOL
        if not get_volume_info(
            root.value, None, 0, ctypes.byref(serial), None, None, fs, len(fs)
        ):
            raise _error("GetVolumeInformationW")
        if info.volume_serial != serial.value:
            raise GuardBlocked("D10 handle volume serial differs")
        size = ctypes.c_longlong((int(info.size_high) << 32) | int(info.size_low))
        if not info.attributes & FILE_ATTRIBUTE_DIRECTORY:
            get_size = kernel.GetFileSizeEx
            get_size.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
            get_size.restype = wintypes.BOOL
            if not get_size(handle, ctypes.byref(size)):
                raise _error("GetFileSizeEx")
        owner, protected, aces = _security(handle)
        return ObjectFacts(
            final,
            int(info.attributes),
            drive_type,
            root.value,
            fs.value,
            int(info.volume_serial),
            (int(info.file_index_high) << 32) | int(info.file_index_low),
            int(info.links),
            int(size.value),
            owner,
            protected,
            aces,
        )

    def read_exact(self, handle: int, size: int) -> bytes:
        if type(size) is not int or size <= 0 or size > _AGGREGATE_LIMIT:
            raise GuardBlocked("D10 read length is outside bounds")
        kernel = _win_dll("kernel32")
        current = ctypes.c_longlong()
        get_size = kernel.GetFileSizeEx
        get_size.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
        get_size.restype = wintypes.BOOL
        if not get_size(handle, ctypes.byref(current)) or current.value != size:
            raise GuardBlocked("D10 trust-file length drifted")
        set_pointer = kernel.SetFilePointerEx
        set_pointer.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        set_pointer.restype = wintypes.BOOL
        if not set_pointer(handle, 0, None, 0):
            raise _error("SetFilePointerEx")
        read_file = kernel.ReadFile
        read_file.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        read_file.restype = wintypes.BOOL
        data = ctypes.create_string_buffer(size)
        offset = 0
        while offset < size:
            received = wintypes.DWORD()
            chunk = min(size - offset, 1024 * 1024)
            if not read_file(
                handle, ctypes.byref(data, offset), chunk, ctypes.byref(received), None
            ):
                raise _error("ReadFile")
            if received.value == 0:
                raise GuardBlocked("D10 same-handle read ended early")
            offset += received.value
        return data.raw


def _token_information(token: int, information_class: int) -> ctypes.Array:
    get = _win_dll("advapi32").GetTokenInformation
    get.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    get.restype = wintypes.BOOL
    required = wintypes.DWORD()
    get(token, information_class, None, 0, ctypes.byref(required))
    if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not required.value:
        raise _error("GetTokenInformation(size)")
    if required.value > 65536:
        raise GuardBlocked("Windows token information is oversized")
    buffer = ctypes.create_string_buffer(required.value)
    if not get(
        token, information_class, buffer, required.value, ctypes.byref(required)
    ):
        raise _error("GetTokenInformation")
    return buffer


def _current_token_facts() -> tuple[str, bool, bool]:
    advapi = _win_dll("advapi32")
    kernel = _win_dll("kernel32")
    open_token = advapi.OpenProcessToken
    open_token.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    open_token.restype = wintypes.BOOL
    current_process = kernel.GetCurrentProcess
    current_process.argtypes = []
    current_process.restype = wintypes.HANDLE
    token = wintypes.HANDLE()
    if not open_token(current_process(), 0x0008, ctypes.byref(token)):
        raise _error("OpenProcessToken")
    try:

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

        user_bytes = _token_information(token, 1)
        user = ctypes.cast(user_bytes, ctypes.POINTER(SidAndAttributes)).contents
        if not user.sid:
            raise GuardBlocked("Windows token user SID is absent")
        user_sid = _sid_string(user.sid)
        elevation_bytes = _token_information(token, 20)
        elevated = bool(
            ctypes.cast(elevation_bytes, ctypes.POINTER(wintypes.DWORD)).contents.value
        )

        convert = advapi.ConvertStringSidToSidW
        convert.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
        convert.restype = wintypes.BOOL
        admins = ctypes.c_void_p()
        if not convert(ADMINISTRATORS_SID, ctypes.byref(admins)):
            raise _error("ConvertStringSidToSidW")
        try:
            check = advapi.CheckTokenMembership
            check.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                ctypes.POINTER(wintypes.BOOL),
            ]
            check.restype = wintypes.BOOL
            member = wintypes.BOOL()
            if not check(None, admins, ctypes.byref(member)):
                raise _error("CheckTokenMembership")
            return user_sid, elevated, bool(member.value)
        finally:
            _local_free(admins)
    finally:
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        if not close(token):
            raise _error("CloseHandle(token)")


def _resolved_local_trading_sid() -> str:
    kernel = _win_dll("kernel32")
    get_name = kernel.GetComputerNameW
    get_name.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)]
    get_name.restype = wintypes.BOOL
    computer = ctypes.create_unicode_buffer(256)
    length = wintypes.DWORD(len(computer))
    if not get_name(computer, ctypes.byref(length)) or not computer.value:
        raise _error("GetComputerNameW")
    lookup = _win_dll("advapi32").LookupAccountNameW
    lookup.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_wchar_p,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    lookup.restype = wintypes.BOOL
    sid_size = wintypes.DWORD()
    domain_size = wintypes.DWORD()
    sid_type = wintypes.DWORD()
    account = computer.value + r"\Trading"
    lookup(
        None,
        account,
        None,
        ctypes.byref(sid_size),
        None,
        ctypes.byref(domain_size),
        ctypes.byref(sid_type),
    )
    if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
        raise _error("LookupAccountNameW(size)")
    if not sid_size.value or sid_size.value > 256 or domain_size.value > 256:
        raise GuardBlocked("local Trading account SID size is invalid")
    sid = ctypes.create_string_buffer(sid_size.value)
    domain = ctypes.create_unicode_buffer(domain_size.value)
    if not lookup(
        None,
        account,
        sid,
        ctypes.byref(sid_size),
        domain,
        ctypes.byref(domain_size),
        ctypes.byref(sid_type),
    ):
        raise _error("LookupAccountNameW")
    if domain.value.casefold() != computer.value.casefold() or sid_type.value != 1:
        raise GuardBlocked("Trading did not resolve as a local user")
    return _sid_string(ctypes.cast(sid, ctypes.c_void_p))


def require_trading_principal() -> None:
    """Require the exact frozen non-elevated, non-admin local Trading identity."""
    token_sid, elevated, admin_member = _current_token_facts()
    local_sid = _resolved_local_trading_sid()
    if token_sid != TRADING_SID or local_sid != TRADING_SID or elevated or admin_member:
        raise GuardBlocked("current Trading principal differs from frozen policy")


def inspect_sealed_source_file(
    relative: str, native: _Native | None = None
) -> ObjectFacts:
    """Read-only per-file admission for a later complete manifest inventory."""
    target = _source_path(relative)
    backend = _Native() if native is None else native
    parts = relative.split("/")
    parents = [D10_ROOT, D10_SOURCE_ROOT]
    current = D10_SOURCE_ROOT
    for part in parts[:-1]:
        current += "\\" + part
        parents.append(current)
    with ExitStack() as stack:
        pinned: list[tuple[str, bool, int, ObjectFacts]] = []
        for path in (*parents, target):
            directory = path != target
            handle = backend.open(path, directory=directory)
            stack.callback(backend.close, handle)
            facts = backend.inspect(handle)
            _require_facts(path, directory, facts)
            pinned.append((path, directory, handle, facts))
        for path, directory, handle, before in pinned:
            after = backend.inspect(handle)
            _require_facts(path, directory, after)
            _stable(before, after)
        return pinned[-1][3]
