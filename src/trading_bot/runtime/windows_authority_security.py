"""Native Win32 path, SID, handle, and ACL inspection for authority objects."""

from __future__ import annotations

import ctypes
import ntpath
import os
import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import PureWindowsPath
from typing import Any, Self

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    AuthorityObjectError,
    AuthorityPathError,
    AuthorityPrincipalError,
    AuthoritySecurityError,
    WindowsNativeError,
    require_fixed_authority_tree_path,
    require_windows_platform,
)

if os.name == "nt":
    from ctypes import wintypes
else:  # pragma: no cover - only enables safe non-Windows imports
    wintypes = None  # type: ignore[assignment]


# File and standard-right constants used in the reviewed policy.
FILE_READ_DATA = 0x0001
FILE_WRITE_DATA = 0x0002
FILE_APPEND_DATA = 0x0004
FILE_READ_EA = 0x0008
FILE_WRITE_EA = 0x0010
FILE_EXECUTE = 0x0020
FILE_READ_ATTRIBUTES = 0x0080
FILE_WRITE_ATTRIBUTES = 0x0100
DELETE = 0x00010000
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
WRITE_OWNER = 0x00080000
SYNCHRONIZE = 0x00100000
FILE_TRAVERSE = FILE_EXECUTE
FILE_ADD_FILE = FILE_WRITE_DATA
FILE_ADD_SUBDIRECTORY = FILE_APPEND_DATA
FILE_LIST_DIRECTORY = FILE_READ_DATA
FILE_ALL_ACCESS = 0x001F01FF
MUTEX_MODIFY_STATE = 0x0001
MUTEX_ALL_ACCESS = 0x001F0001

FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
OPEN_EXISTING = 3
CREATE_NEW = 1
GENERIC_WRITE = 0x40000000
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10
LG_INCLUDE_INDIRECT = 1
MAX_PREFERRED_LENGTH = 0xFFFFFFFF
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_ALREADY_EXISTS = 183
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_ACCESS_DENIED = 5
INVALID_HANDLE_VALUE = -1

SE_FILE_OBJECT = 1
SE_KERNEL_OBJECT = 6
OWNER_SECURITY_INFORMATION = 0x00000001
DACL_SECURITY_INFORMATION = 0x00000004
PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
SE_DACL_PROTECTED = 0x1000
ACL_REVISION = 2
ACCESS_ALLOWED_ACE_TYPE = 0
ACCESS_DENIED_ACE_TYPE = 1
NO_INHERITANCE = 0
_SID_PATTERN = re.compile(r"^S-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))+$")
_LOCAL_DOS_PATH_PATTERN = re.compile(r"^[A-Za-z]:\\")


class SecurityObjectType(IntEnum):
    """Native object type passed to the Win32 security-information APIs."""

    FILE = SE_FILE_OBJECT
    KERNEL = SE_KERNEL_OBJECT


class AuthorityObjectKind(StrEnum):
    DIRECTORY = "DIRECTORY"
    FILE = "FILE"


@dataclass(frozen=True, slots=True)
class SecurityAce:
    """A normalized non-localized DACL entry."""

    principal_sid: str
    access_mask: int
    ace_type: int = ACCESS_ALLOWED_ACE_TYPE
    ace_flags: int = NO_INHERITANCE

    def __post_init__(self) -> None:
        if (
            type(self.principal_sid) is not str
            or _SID_PATTERN.fullmatch(self.principal_sid) is None
        ):
            raise AuthoritySecurityError("security ACE principal must be a SID")
        if type(self.access_mask) is not int or self.access_mask < 0:
            raise AuthoritySecurityError("security ACE access mask is invalid")
        if type(self.ace_type) is not int or type(self.ace_flags) is not int:
            raise AuthoritySecurityError("security ACE type or flags are invalid")


@dataclass(frozen=True, slots=True)
class SecurityInspection:
    """Authoritative security/path facts obtained from one opened handle."""

    expected_path: str
    final_path: str
    kind: AuthorityObjectKind
    owner_sid: str
    dacl_protected: bool
    aces: tuple[SecurityAce, ...]
    is_reparse_point: bool
    volume_root: str
    filesystem: str


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    """Exact owner/protection/DACL intent for one protected object."""

    owner_sid: str
    aces: tuple[SecurityAce, ...]
    dacl_protected: bool = True

    def matches(self, inspection: SecurityInspection) -> bool:
        return (
            inspection.owner_sid == self.owner_sid
            and inspection.dacl_protected == self.dacl_protected
            and inspection.is_reparse_point is False
            and inspection.aces == self.aces
        )


def _full_admin_system() -> tuple[SecurityAce, SecurityAce]:
    return (
        SecurityAce("S-1-5-32-544", FILE_ALL_ACCESS),
        SecurityAce("S-1-5-18", FILE_ALL_ACCESS),
    )


def _read_file_rights() -> int:
    return (
        FILE_READ_DATA
        | FILE_READ_EA
        | FILE_READ_ATTRIBUTES
        | READ_CONTROL
        | SYNCHRONIZE
    )


def sqlite_trading_file_rights() -> int:
    """Return the reviewed concrete SQLite rights.

    SQLite needs read/write bytes, append/extend support for its persistent
    journal, file attributes, synchronization, byte-range locking, and the
    ``FILE_WRITE_EA`` right requested by the standard Windows SQLite VFS as
    part of ``GENERIC_WRITE``.  It does not receive DELETE, WRITE_DAC, or
    WRITE_OWNER rights; ``FILE_WRITE_EA`` alone does not grant those rights.
    """

    return (
        FILE_READ_DATA
        | FILE_WRITE_DATA
        | FILE_APPEND_DATA
        | FILE_READ_EA
        | FILE_WRITE_EA
        | FILE_READ_ATTRIBUTES
        | FILE_WRITE_ATTRIBUTES
        | READ_CONTROL
        | SYNCHRONIZE
    )


def authority_security_policy(
    object_name: str,
    trading_sid: str,
) -> SecurityPolicy:
    """Build the exact reviewed policy for a fixed authority object."""

    if _SID_PATTERN.fullmatch(trading_sid) is None:
        raise AuthorityPrincipalError("Trading principal must be supplied as a SID")
    admins, system = _full_admin_system()
    if object_name in {"root", "authority"}:
        trading = SecurityAce(
            trading_sid,
            FILE_TRAVERSE
            | FILE_LIST_DIRECTORY
            | FILE_READ_EA
            | FILE_READ_ATTRIBUTES
            | READ_CONTROL
            | SYNCHRONIZE,
        )
    elif object_name in {"bootstrap", "signature"}:
        trading = SecurityAce(trading_sid, _read_file_rights())
    elif object_name in {"database", "journal"}:
        trading = SecurityAce(trading_sid, sqlite_trading_file_rights())
    elif object_name == "capture-output":
        trading = SecurityAce(
            trading_sid,
            FILE_ADD_FILE
            | FILE_ADD_SUBDIRECTORY
            | FILE_LIST_DIRECTORY
            | FILE_READ_EA
            | FILE_READ_ATTRIBUTES
            | FILE_WRITE_ATTRIBUTES
            | READ_CONTROL
            | SYNCHRONIZE,
        )
    elif object_name == "backup":
        return SecurityPolicy("S-1-5-32-544", (admins, system))
    elif object_name == "lifecycle-mutex":
        trading = SecurityAce(
            trading_sid, MUTEX_MODIFY_STATE | READ_CONTROL | SYNCHRONIZE
        )
        return SecurityPolicy(
            "S-1-5-32-544",
            (
                SecurityAce("S-1-5-32-544", MUTEX_ALL_ACCESS),
                SecurityAce("S-1-5-18", MUTEX_ALL_ACCESS),
                trading,
            ),
        )
    else:
        raise AuthoritySecurityError("unknown authority security policy object")
    return SecurityPolicy("S-1-5-32-544", (admins, system, trading))


def authority_parent_security_policy() -> SecurityPolicy:
    """Return the exact policy required for the fixed root's parent."""

    admins, system = _full_admin_system()
    return SecurityPolicy("S-1-5-32-544", (admins, system))


class WindowsHandle:
    """Small deterministic CloseHandle wrapper."""

    def __init__(self, value: int, *, close: bool = True) -> None:
        self.value = value
        self._close = close

    def __enter__(self) -> int:
        return self.value

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._close and self.value not in (0, INVALID_HANDLE_VALUE):
            if os.name == "nt":
                _close_handle(self.value)
            self.value = 0


def _last_error(operation: str) -> WindowsNativeError:
    return WindowsNativeError(operation, ctypes.get_last_error())


def _kernel32() -> ctypes.CDLL:
    require_windows_platform()
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _advapi32() -> ctypes.CDLL:
    require_windows_platform()
    return ctypes.WinDLL("advapi32", use_last_error=True)


def _netapi32() -> ctypes.CDLL:
    require_windows_platform()
    return ctypes.WinDLL("netapi32", use_last_error=True)


def _close_handle(handle: object) -> None:
    close = _kernel32().CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    close(handle)


def _local_free(pointer: object) -> None:
    free = _kernel32().LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    free(pointer)


def _handle_value(handle: object) -> int:
    value = getattr(handle, "value", handle)
    if value is None:
        return 0
    return int(value)


def _require_fixed_open_path(path: str | PureWindowsPath) -> None:
    if str(path) == str(PRODUCTION_AUTHORITY_PATHS.root.parent):
        return
    require_fixed_authority_tree_path(path)


def open_authority_object(
    path: str | PureWindowsPath,
    kind: AuthorityObjectKind,
    *,
    for_update: bool = False,
) -> WindowsHandle:
    """Open an authority object without following reparse points."""

    _require_fixed_open_path(path)
    if type(kind) is not AuthorityObjectKind:
        raise AuthorityObjectError("authority object kind must be explicit")
    require_windows_platform()
    expected = str(path)
    if not expected.startswith("F:\\") or expected.startswith("\\\\"):
        raise AuthorityPathError("authority object is not on the fixed local drive")
    kernel32 = _kernel32()
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        expected,
        FILE_READ_DATA
        | READ_CONTROL
        | FILE_READ_ATTRIBUTES
        | (WRITE_DAC | WRITE_OWNER if for_update else 0),
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT
        | (FILE_FLAG_BACKUP_SEMANTICS if kind is AuthorityObjectKind.DIRECTORY else 0),
        None,
    )
    handle_value = _handle_value(handle)
    if handle_value in (0, INVALID_HANDLE_VALUE):
        raise _last_error("CreateFileW(authority object)")
    return WindowsHandle(handle_value)


def create_authority_directory(
    path: str | PureWindowsPath,
    policy: SecurityPolicy,
) -> None:
    """Create one fixed directory with its reviewed descriptor from the start."""

    require_fixed_authority_tree_path(path)
    require_windows_platform()
    create = _kernel32().CreateDirectoryW
    create.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    create.restype = wintypes.BOOL
    with build_security_attributes(policy) as attributes:
        if not create(str(path), ctypes.byref(attributes.attributes)):
            raise _last_error("CreateDirectoryW(authority object)")


def create_authority_file(
    path: str | PureWindowsPath,
    data: bytes,
    policy: SecurityPolicy,
) -> None:
    """Create and write one fixed file under its reviewed descriptor."""

    require_fixed_authority_tree_path(path)
    if type(data) is not bytes:
        raise AuthorityObjectError("authority file contents must be bytes")
    require_windows_platform()
    create = _kernel32().CreateFileW
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
    write_file = _kernel32().WriteFile
    write_file.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    write_file.restype = wintypes.BOOL
    flush = _kernel32().FlushFileBuffers
    flush.argtypes = [wintypes.HANDLE]
    flush.restype = wintypes.BOOL
    handle = 0
    with build_security_attributes(policy) as attributes:
        raw_handle = create(
            str(path),
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            ctypes.byref(attributes.attributes),
            CREATE_NEW,
            FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        handle = _handle_value(raw_handle)
        if handle in (0, INVALID_HANDLE_VALUE):
            raise _last_error("CreateFileW(authority file)")
        try:
            buffer = ctypes.create_string_buffer(data)
            offset = 0
            while offset < len(data):
                written = wintypes.DWORD()
                if not write_file(
                    handle,
                    ctypes.cast(ctypes.byref(buffer, offset), ctypes.c_void_p),
                    len(data) - offset,
                    ctypes.byref(written),
                    None,
                ):
                    raise _last_error("WriteFile(authority file)")
                if written.value == 0:
                    raise WindowsNativeError("WriteFile(authority file)")
                offset += written.value
            if not flush(handle):
                raise _last_error("FlushFileBuffers(authority file)")
        finally:
            _close_handle(handle)


def read_open_authority_file(handle: int) -> bytes:
    """Read one already-opened fixed file without reopening its path."""

    require_windows_platform()
    get_size = _kernel32().GetFileSizeEx
    get_size.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
    get_size.restype = wintypes.BOOL
    size = ctypes.c_longlong()
    if not get_size(handle, ctypes.byref(size)) or size.value < 0:
        raise _last_error("GetFileSizeEx(authority file)")
    if size.value > 16 * 1024 * 1024:
        raise AuthorityObjectError("authority file is unexpectedly large")
    data = ctypes.create_string_buffer(size.value)
    read_file = _kernel32().ReadFile
    read_file.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    read_file.restype = wintypes.BOOL
    offset = 0
    while offset < size.value:
        read = wintypes.DWORD()
        if not read_file(
            handle,
            ctypes.cast(ctypes.byref(data, offset), ctypes.c_void_p),
            size.value - offset,
            ctypes.byref(read),
            None,
        ):
            raise _last_error("ReadFile(authority file)")
        if read.value == 0:
            raise WindowsNativeError("ReadFile(authority file)")
        offset += read.value
    return data.raw[: size.value]


def _sid_to_string(sid: ctypes.c_void_p) -> str:
    convert = _advapi32().ConvertSidToStringSidW
    convert.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    convert.restype = wintypes.BOOL
    text = ctypes.c_wchar_p()
    if not convert(sid, ctypes.byref(text)):
        raise _last_error("ConvertSidToStringSidW")
    try:
        return text.value or ""
    finally:
        _local_free(ctypes.cast(text, ctypes.c_void_p))


def resolve_current_token_sid() -> str:
    """Return the exact user SID of the current Windows access token."""

    require_windows_platform()
    advapi32 = _advapi32()
    token = wintypes.HANDLE()
    open_token = advapi32.OpenProcessToken
    open_token.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    open_token.restype = wintypes.BOOL
    get_current_process = _kernel32().GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = wintypes.HANDLE
    if not open_token(get_current_process(), 0x0008, ctypes.byref(token)):
        raise _last_error("OpenProcessToken")
    try:
        get_token_information = advapi32.GetTokenInformation
        get_token_information.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_token_information.restype = wintypes.BOOL

        required = wintypes.DWORD()
        get_token_information(token, 1, None, 0, ctypes.byref(required))
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not required.value:
            raise _last_error("GetTokenInformation(TokenUser size)")

        buffer = ctypes.create_string_buffer(required.value)
        if not get_token_information(
            token,
            1,
            buffer,
            required.value,
            ctypes.byref(required),
        ):
            raise _last_error("GetTokenInformation(TokenUser)")

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

        class TokenUser(ctypes.Structure):
            _fields_ = [("user", SidAndAttributes)]

        user = ctypes.cast(buffer, ctypes.POINTER(TokenUser)).contents
        if not user.user.sid:
            raise AuthorityPrincipalError("current Windows token has no user SID")
        return _sid_to_string(user.user.sid)
    finally:
        _close_handle(token)


def resolve_local_trading_sid() -> str:
    """Resolve the local ``Trading`` account through LookupAccountNameW."""

    kernel32 = _kernel32()
    get_computer_name = kernel32.GetComputerNameW
    get_computer_name.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)]
    get_computer_name.restype = wintypes.BOOL
    computer_name = ctypes.create_unicode_buffer(256)
    name_size = wintypes.DWORD(len(computer_name))
    if not get_computer_name(computer_name, ctypes.byref(name_size)):
        raise _last_error("GetComputerNameW")
    if not computer_name.value:
        raise AuthorityPrincipalError("local computer name is unavailable")
    return _lookup_account_sid("Trading", system_name=computer_name.value)


def _lookup_account_sid(
    account_name: str,
    *,
    system_name: str | None = None,
) -> str:
    """Resolve one account/group name and return only its SID."""

    require_windows_platform()
    advapi32 = _advapi32()
    lookup = advapi32.LookupAccountNameW
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
    sid_size = wintypes.DWORD(0)
    domain_size = wintypes.DWORD(0)
    sid_type = wintypes.DWORD(0)
    lookup(
        system_name,
        account_name,
        None,
        ctypes.byref(sid_size),
        None,
        ctypes.byref(domain_size),
        ctypes.byref(sid_type),
    )
    if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
        raise AuthorityPrincipalError("Windows account could not be resolved")
    sid = ctypes.create_string_buffer(sid_size.value)
    domain = ctypes.create_unicode_buffer(domain_size.value)
    if not lookup(
        system_name,
        account_name,
        sid,
        ctypes.byref(sid_size),
        domain,
        ctypes.byref(domain_size),
        ctypes.byref(sid_type),
    ):
        raise _last_error("LookupAccountNameW")
    return _sid_to_string(ctypes.cast(sid, ctypes.c_void_p))


def require_trading_standard_account() -> str:
    """Resolve Trading and require the Win32 standard-user privilege level."""

    require_windows_platform()
    sid = resolve_local_trading_sid()
    netapi32 = _netapi32()

    class UserInfo1(ctypes.Structure):
        _fields_ = [
            ("name", ctypes.c_wchar_p),
            ("password", ctypes.c_wchar_p),
            ("password_age", wintypes.DWORD),
            ("privilege", wintypes.DWORD),
            ("home_dir", ctypes.c_wchar_p),
            ("comment", ctypes.c_wchar_p),
            ("flags", wintypes.DWORD),
            ("script_path", ctypes.c_wchar_p),
        ]

    buffer = ctypes.c_void_p()
    get_info = netapi32.NetUserGetInfo
    get_info.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_info.restype = wintypes.DWORD
    status = int(get_info(None, "Trading", 1, ctypes.byref(buffer)))
    if status != 0 or not buffer.value:
        raise AuthorityPrincipalError(
            "local Trading account information is unavailable"
        )
    try:
        info = ctypes.cast(buffer, ctypes.POINTER(UserInfo1)).contents
        # USER_PRIV_USER = 1.  Do not accept guest or administrator-level
        # account privilege values for the dedicated authority principal.
        if info.privilege != 1:
            raise AuthorityPrincipalError("Trading is not a standard user account")
    finally:
        netapi32.NetApiBufferFree.argtypes = [ctypes.c_void_p]
        netapi32.NetApiBufferFree.restype = wintypes.DWORD
        netapi32.NetApiBufferFree(buffer)
    _require_trading_not_in_privileged_groups(netapi32, sid)
    return sid


def _require_trading_not_in_privileged_groups(
    netapi32: ctypes.CDLL,
    trading_sid: str,
) -> None:
    """Check indirect local-group membership by resolved group SID."""

    class LocalGroupInfo0(ctypes.Structure):
        _fields_ = [("name", ctypes.c_wchar_p)]

    groups = ctypes.c_void_p()
    read = wintypes.DWORD()
    total = wintypes.DWORD()
    get_groups = netapi32.NetUserGetLocalGroups
    get_groups.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    get_groups.restype = wintypes.DWORD
    status = int(
        get_groups(
            None,
            "Trading",
            0,
            LG_INCLUDE_INDIRECT,
            ctypes.byref(groups),
            MAX_PREFERRED_LENGTH,
            ctypes.byref(read),
            ctypes.byref(total),
        )
    )
    if status != 0 or not groups.value:
        raise AuthorityPrincipalError("Trading group membership is unavailable")
    privileged_sids = {
        "S-1-5-32-544",  # Administrators
        "S-1-5-32-548",  # Account Operators
        "S-1-5-32-549",  # Server Operators
        "S-1-5-32-550",  # Print Operators
        "S-1-5-32-551",  # Backup Operators
        "S-1-5-32-552",  # Replicator
    }
    try:
        values = ctypes.cast(
            groups, ctypes.POINTER(LocalGroupInfo0 * read.value)
        ).contents
        for item in values:
            group_sid = _lookup_account_sid(item.name)
            if group_sid == trading_sid:
                continue
            if group_sid in privileged_sids or group_sid.rsplit("-", 1)[-1] in {
                "512",
                "516",
                "518",
                "519",
            }:
                raise AuthorityPrincipalError(
                    "Trading belongs to a privileged Windows group"
                )
    finally:
        netapi32.NetApiBufferFree.argtypes = [ctypes.c_void_p]
        netapi32.NetApiBufferFree.restype = wintypes.DWORD
        netapi32.NetApiBufferFree(groups)


def _normalize_final_authority_path(value: str) -> str:
    """Normalize the only approved Win32 final-path namespace."""

    if type(value) is not str or not value:
        raise AuthorityObjectError("authority final path is invalid")

    if value.startswith("\\\\?\\"):
        local_path = value[4:]
        namespace = local_path.casefold()
        if namespace.startswith("unc\\"):
            raise AuthorityObjectError("authority object resolved to a UNC path")
        if namespace.startswith("globalroot\\"):
            raise AuthorityObjectError("authority object resolved to GLOBALROOT")
        if namespace.startswith("volume{"):
            raise AuthorityObjectError("authority object resolved to a volume path")
        if _LOCAL_DOS_PATH_PATTERN.match(local_path) is None:
            raise AuthorityObjectError("authority final path is not a local DOS path")
        return local_path

    if value.startswith("\\\\.\\"):
        raise AuthorityObjectError("authority object resolved to a device path")
    if value.startswith("\\\\"):
        raise AuthorityObjectError("authority object resolved to a UNC path")
    raise AuthorityObjectError("authority final path has an unsupported namespace")


def _final_path(handle: int) -> str:
    kernel32 = _kernel32()
    get_final = kernel32.GetFinalPathNameByHandleW
    get_final.argtypes = [
        wintypes.HANDLE,
        ctypes.c_wchar_p,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    get_final.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_final(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        raise _last_error("GetFinalPathNameByHandleW")
    return _normalize_final_authority_path(buffer.value)


def _attributes(handle: int) -> tuple[int, int]:
    class FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]

    info = FileAttributeTagInfo()
    get_info = _kernel32().GetFileInformationByHandleEx
    get_info.argtypes = [wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD]
    get_info.restype = wintypes.BOOL
    if not get_info(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise _last_error("GetFileInformationByHandleEx(FileAttributeTagInfo)")
    return info.attributes, info.reparse_tag


def _security(
    handle: int,
    object_type: SecurityObjectType,
) -> tuple[str, bool, tuple[SecurityAce, ...]]:
    if type(object_type) is not SecurityObjectType:
        raise AuthoritySecurityError("native security object type must be explicit")
    advapi32 = _advapi32()
    descriptor = ctypes.c_void_p()
    get_security = advapi32.GetSecurityInfo
    get_security.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_security.restype = wintypes.DWORD
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    status = get_security(
        handle,
        int(object_type),
        OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if status != 0 or not descriptor.value or not owner.value or not dacl.value:
        raise WindowsNativeError("GetSecurityInfo", int(status))
    try:
        get_control = advapi32.GetSecurityDescriptorControl
        get_control.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_control.restype = wintypes.BOOL
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not get_control(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            raise _last_error("GetSecurityDescriptorControl")
        get_acl = advapi32.GetAclInformation

        class AclSizeInformation(ctypes.Structure):
            _fields_ = [
                ("ace_count", wintypes.DWORD),
                ("bytes_in_use", wintypes.DWORD),
                ("bytes_free", wintypes.DWORD),
            ]

        acl_info = AclSizeInformation()
        get_acl.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        get_acl.restype = wintypes.BOOL
        if not get_acl(dacl, ctypes.byref(acl_info), ctypes.sizeof(acl_info), 2):
            raise _last_error("GetAclInformation")

        class AceHeader(ctypes.Structure):
            _fields_ = [
                ("ace_type", ctypes.c_ubyte),
                ("ace_flags", ctypes.c_ubyte),
                ("ace_size", wintypes.WORD),
            ]

        get_ace = advapi32.GetAce
        get_ace.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        get_ace.restype = wintypes.BOOL
        aces: list[SecurityAce] = []
        for index in range(acl_info.ace_count):
            raw = ctypes.c_void_p()
            if not get_ace(dacl, index, ctypes.byref(raw)):
                raise _last_error("GetAce")
            header = ctypes.cast(raw, ctypes.POINTER(AceHeader)).contents
            if header.ace_type not in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
                raise AuthoritySecurityError(
                    "authority DACL contains an unsupported ACE type"
                )
            mask = ctypes.cast(
                raw.value + 4, ctypes.POINTER(wintypes.DWORD)
            ).contents.value
            sid = ctypes.c_void_p(raw.value + 8)
            aces.append(
                SecurityAce(
                    _sid_to_string(sid), int(mask), header.ace_type, header.ace_flags
                )
            )
        return (
            _sid_to_string(owner),
            bool(control.value & SE_DACL_PROTECTED),
            tuple(aces),
        )
    finally:
        _local_free(descriptor)


def _volume(path: str) -> tuple[str, str]:
    root = ctypes.create_unicode_buffer(8)
    get_volume_path = _kernel32().GetVolumePathNameW
    get_volume_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD]
    get_volume_path.restype = wintypes.BOOL
    if not get_volume_path(path, root, len(root)):
        raise _last_error("GetVolumePathNameW")
    fs = ctypes.create_unicode_buffer(64)
    get_info = _kernel32().GetVolumeInformationW
    get_info.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_wchar_p,
        wintypes.DWORD,
    ]
    get_info.restype = wintypes.BOOL
    if not get_info(root, None, 0, None, None, None, fs, len(fs)):
        raise _last_error("GetVolumeInformationW")
    return root.value, fs.value


def inspect_open_authority_object(
    handle: int,
    expected_path: str | PureWindowsPath,
    expected_kind: AuthorityObjectKind,
) -> SecurityInspection:
    """Inspect owner/DACL/type/final-path/reparse state from the opened handle."""

    require_windows_platform()
    expected = str(expected_path)
    final = _final_path(handle)
    if ntpath.normcase(final) != ntpath.normcase(expected):
        raise AuthorityObjectError(
            "authority handle final path is not the fixed target"
        )
    attributes, _reparse_tag = _attributes(handle)
    reparse = bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    if reparse:
        raise AuthorityObjectError("authority object is a reparse point")
    is_directory = bool(attributes & FILE_ATTRIBUTE_DIRECTORY)
    if (expected_kind is AuthorityObjectKind.DIRECTORY) != is_directory:
        raise AuthorityObjectError(
            "authority object type does not match the fixed layout"
        )
    volume_root, filesystem = _volume(final)
    if ntpath.normcase(volume_root) != "f:\\" or filesystem.upper() != "NTFS":
        raise AuthorityObjectError("authority is not on the approved local NTFS volume")
    owner, protected, aces = _security(handle, SecurityObjectType.FILE)
    return SecurityInspection(
        expected_path=expected,
        final_path=final,
        kind=expected_kind,
        owner_sid=owner,
        dacl_protected=protected,
        aces=aces,
        is_reparse_point=reparse,
        volume_root=volume_root,
        filesystem=filesystem,
    )


def inspect_fixed_authority_object(
    path: str | PureWindowsPath,
    kind: AuthorityObjectKind,
    *,
    trading_sid: str | None = None,
) -> SecurityInspection:
    """Open and inspect one exact fixed object, closing its handle deterministically."""

    fixed = next(
        (
            item
            for item in PRODUCTION_AUTHORITY_PATHS.protected_objects
            if str(item) == str(path)
        ),
        None,
    )
    if fixed is None:
        raise AuthorityPathError("path is outside the fixed authority deployment")
    validate_fixed_parent_chain(fixed, trading_sid=trading_sid)
    with open_authority_object(fixed, kind) as handle:
        return inspect_open_authority_object(handle, fixed, kind)


def validate_fixed_parent_chain(
    path: str | PureWindowsPath,
    *,
    trading_sid: str | None = None,
) -> None:
    """Open fixed parents and apply the policy for each directory role."""

    fixed = next(
        (
            item
            for item in PRODUCTION_AUTHORITY_PATHS.protected_objects
            if str(item) == str(path)
        ),
        None,
    )
    if fixed is None:
        raise AuthorityPathError("path is outside the fixed authority deployment")
    parts = PureWindowsPath(fixed).parts
    current = PureWindowsPath(parts[0])
    for part in parts[1:-1]:
        current /= part
        with open_authority_object(current, AuthorityObjectKind.DIRECTORY) as handle:
            if current == PRODUCTION_AUTHORITY_PATHS.root:
                if trading_sid is None:
                    raise AuthorityPrincipalError(
                        "Trading SID is required to validate the authority root"
                    )
                policy = authority_security_policy("root", trading_sid)
            else:
                policy = authority_parent_security_policy()
            _validate_directory_component(handle, current, policy)


def _validate_directory_component(
    handle: int,
    expected_path: PureWindowsPath,
    policy: SecurityPolicy,
) -> None:
    """Validate a parent component before opening the next fixed component."""

    inspection = inspect_open_authority_object(
        handle, expected_path, AuthorityObjectKind.DIRECTORY
    )
    require_security_policy(inspection, policy)


def require_security_policy(
    inspection: SecurityInspection,
    policy: SecurityPolicy,
) -> None:
    """Fail closed on owner, inheritance, ACE, or unexpected-right drift."""

    if not policy.matches(inspection):
        raise AuthoritySecurityError(
            "authority object security does not match reviewed policy"
        )


def inspect_handle_security(
    handle: int,
    object_type: SecurityObjectType,
) -> tuple[str, bool, tuple[SecurityAce, ...]]:
    """Inspect only the owner/DACL of a native security object handle."""

    require_windows_platform()
    return _security(handle, object_type)


class SecurityAttributesBundle:
    """Owned SECURITY_ATTRIBUTES plus all native allocations it references."""

    def __init__(
        self,
        attributes: Any,
        descriptor: ctypes.c_void_p,
        descriptor_buffer: ctypes.Array[ctypes.c_char],
        acl: ctypes.Array[ctypes.c_char],
        sid_buffers: tuple[ctypes.c_void_p, ...],
    ) -> None:
        self.attributes = attributes
        self.descriptor = descriptor
        self.descriptor_buffer = descriptor_buffer
        self.acl = acl
        self.sid_buffers = sid_buffers

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if os.name != "nt":
            return
        for sid in self.sid_buffers:
            _local_free(sid)
        if self.descriptor.value:
            self.descriptor = ctypes.c_void_p()


def _sid_pointer(sid_text: str) -> ctypes.c_void_p:
    convert = _advapi32().ConvertStringSidToSidW
    convert.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    convert.restype = wintypes.BOOL
    sid = ctypes.c_void_p()
    if not convert(sid_text, ctypes.byref(sid)):
        raise _last_error("ConvertStringSidToSidW")
    return sid


def build_security_attributes(policy: SecurityPolicy) -> SecurityAttributesBundle:
    """Build a binary explicit owner/DACL descriptor for a native object."""

    require_windows_platform()
    advapi32 = _advapi32()
    sid_buffers: list[ctypes.c_void_p] = []
    try:
        owner = _sid_pointer(policy.owner_sid)
        sid_buffers.append(owner)
        for ace in policy.aces:
            sid_buffers.append(_sid_pointer(ace.principal_sid))
        get_length = advapi32.GetLengthSid
        get_length.argtypes = [ctypes.c_void_p]
        get_length.restype = wintypes.DWORD
        acl_size = ctypes.sizeof(ctypes.c_ubyte) * 8
        for sid, _ace in zip(sid_buffers[1:], policy.aces, strict=True):
            acl_size += 8 + int(get_length(sid))
        acl = ctypes.create_string_buffer(acl_size)
        initialize_acl = advapi32.InitializeAcl
        initialize_acl.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
        initialize_acl.restype = wintypes.BOOL
        if not initialize_acl(acl, acl_size, ACL_REVISION):
            raise _last_error("InitializeAcl")
        add_allow = advapi32.AddAccessAllowedAceEx
        add_allow.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        add_allow.restype = wintypes.BOOL
        for sid, ace in zip(sid_buffers[1:], policy.aces, strict=True):
            if (
                ace.ace_type != ACCESS_ALLOWED_ACE_TYPE
                or ace.ace_flags != NO_INHERITANCE
            ):
                raise AuthoritySecurityError(
                    "security attribute policy contains unsupported ACE"
                )
            if not add_allow(acl, ACL_REVISION, ace.ace_flags, ace.access_mask, sid):
                raise _last_error("AddAccessAllowedAceEx")

        class SecurityDescriptor(ctypes.Structure):
            _fields_ = [
                ("revision", ctypes.c_ubyte),
                ("sbz1", ctypes.c_ubyte),
                ("control", ctypes.c_ushort),
            ]

        descriptor = ctypes.create_string_buffer(256)
        initialize_sd = advapi32.InitializeSecurityDescriptor
        initialize_sd.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        initialize_sd.restype = wintypes.BOOL
        if not initialize_sd(descriptor, 1):
            raise _last_error("InitializeSecurityDescriptor")
        set_control = advapi32.SetSecurityDescriptorControl
        set_control.argtypes = [ctypes.c_void_p, wintypes.WORD, wintypes.WORD]
        set_control.restype = wintypes.BOOL
        if policy.dacl_protected and not set_control(
            descriptor, SE_DACL_PROTECTED, SE_DACL_PROTECTED
        ):
            raise _last_error("SetSecurityDescriptorControl")
        set_owner = advapi32.SetSecurityDescriptorOwner
        set_owner.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL]
        set_owner.restype = wintypes.BOOL
        if not set_owner(descriptor, owner, False):
            raise _last_error("SetSecurityDescriptorOwner")
        set_dacl = advapi32.SetSecurityDescriptorDacl
        set_dacl.argtypes = [
            ctypes.c_void_p,
            wintypes.BOOL,
            ctypes.c_void_p,
            wintypes.BOOL,
        ]
        set_dacl.restype = wintypes.BOOL
        if not set_dacl(descriptor, True, acl, False):
            raise _last_error("SetSecurityDescriptorDacl")

        class SecurityAttributes(ctypes.Structure):
            _fields_ = [
                ("n_length", wintypes.DWORD),
                ("security_descriptor", ctypes.c_void_p),
                ("inherit_handle", wintypes.BOOL),
            ]

        attributes = SecurityAttributes(
            ctypes.sizeof(SecurityAttributes), ctypes.addressof(descriptor), False
        )
        # The descriptor and ACL are intentionally kept alive by the bundle.
        descriptor_pointer = ctypes.c_void_p(ctypes.addressof(descriptor))
        return SecurityAttributesBundle(
            attributes,
            descriptor_pointer,
            descriptor,
            acl,
            tuple(sid_buffers),
        )
    except BaseException:
        for sid in sid_buffers:
            _local_free(sid)
        raise


def is_current_token_elevated() -> bool:
    """Return token elevation without attempting self-elevation."""

    require_windows_platform()
    advapi32 = _advapi32()
    token = wintypes.HANDLE()
    open_token = advapi32.OpenProcessToken
    open_token.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    open_token.restype = wintypes.BOOL
    get_current_process = _kernel32().GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = wintypes.HANDLE
    if not open_token(
        get_current_process(),
        0x0008,
        ctypes.byref(token),
    ):
        raise _last_error("OpenProcessToken")
    try:

        class TokenElevation(ctypes.Structure):
            _fields_ = [("token_is_elevated", wintypes.DWORD)]

        elevation = TokenElevation()
        size = wintypes.DWORD()
        get_token_information = advapi32.GetTokenInformation
        get_token_information.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_token_information.restype = wintypes.BOOL
        if not get_token_information(
            token,
            20,
            ctypes.byref(elevation),
            ctypes.sizeof(elevation),
            ctypes.byref(size),
        ):
            raise _last_error("GetTokenInformation(TokenElevation)")
        return bool(elevation.token_is_elevated)
    finally:
        _close_handle(token)


def is_current_token_administrator() -> bool:
    """Return whether the current token belongs to BUILTIN\\Administrators."""

    require_windows_platform()
    check_membership = _advapi32().CheckTokenMembership
    check_membership.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.BOOL),
    ]
    check_membership.restype = wintypes.BOOL
    administrators = _sid_pointer("S-1-5-32-544")
    member = wintypes.BOOL()
    try:
        if not check_membership(None, administrators, ctypes.byref(member)):
            raise _last_error("CheckTokenMembership")
        return bool(member.value)
    finally:
        _local_free(administrators)


def require_administrator_token() -> None:
    """Require an already elevated administrator-authorized token."""

    if not is_current_token_elevated() or not is_current_token_administrator():
        from trading_bot.runtime.windows_authority import AdministratorRequiredError

        raise AdministratorRequiredError("administrator elevation is required")


def apply_security_policy(handle: int, policy: SecurityPolicy) -> None:
    """Apply an already reviewed binary owner/DACL policy to an open handle."""

    require_windows_platform()
    with build_security_attributes(policy) as bundle:
        owner = bundle.sid_buffers[0]
        set_security = _advapi32().SetSecurityInfo
        set_security.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        set_security.restype = wintypes.DWORD
        information = (
            OWNER_SECURITY_INFORMATION
            | DACL_SECURITY_INFORMATION
            | PROTECTED_DACL_SECURITY_INFORMATION
        )
        status = set_security(
            handle,
            SE_FILE_OBJECT,
            information,
            owner,
            None,
            bundle.acl,
            None,
        )
        if status != 0:
            raise WindowsNativeError("SetSecurityInfo", int(status))
