"""Native Windows no-follow inventory for the protected P124-1 operator run.

This module has no import-time production access. A call to collect_inventory
must happen only in the separately authorized Administrator host checkpoint.
"""

from __future__ import annotations

import ctypes
import dataclasses
import ntpath
import os
from contextlib import ExitStack
from ctypes import wintypes
from functools import lru_cache

from scripts import d10_python_substrate_harness as h
from trading_bot.runtime import personal_desktop_d10_python_substrate as q

FILE_READ_ATTRIBUTES = 0x80
READ_CONTROL = 0x20000
FILE_LIST_DIRECTORY = 0x1
FILE_SHARE_READ = 0x1
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
SE_FILE_OBJECT = 1
OWNER_SECURITY_INFORMATION = 1
GROUP_SECURITY_INFORMATION = 2
DACL_SECURITY_INFORMATION = 4
SE_DACL_PROTECTED = 0x1000
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
INVALID_HANDLE = ctypes.c_void_p(-1).value


class NativeFailure(h.CollectionBlocked):
    """Windows API failure or inadmissible native observation."""


class ByHandleInfo(ctypes.Structure):
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


class AclSize(ctypes.Structure):
    _fields_ = [
        ("count", wintypes.DWORD),
        ("used", wintypes.DWORD),
        ("free", wintypes.DWORD),
    ]


class AceHeader(ctypes.Structure):
    _fields_ = [
        ("ace_type", ctypes.c_ubyte),
        ("flags", ctypes.c_ubyte),
        ("size", wintypes.WORD),
    ]


def _check(ok: object, name: str) -> None:
    if not ok:
        raise NativeFailure(f"{name} failed: {ctypes.get_last_error()}")


@lru_cache(maxsize=3)
def _dll(name: str) -> object:
    if os.name != "nt":
        raise NativeFailure("Windows required")
    if name not in {"kernel32", "advapi32", "bcrypt"}:
        raise NativeFailure("unreviewed native DLL")
    return ctypes.WinDLL(q.SYSTEM32 + "\\" + name + ".dll", use_last_error=True)


def _bind(dll: object, name: str, args: list[object], result: object) -> object:
    func = getattr(dll, name)
    func.argtypes = args
    func.restype = result
    return func


def _sid(pointer: object) -> str:
    advapi = _dll("advapi32")
    convert = _bind(
        advapi,
        "ConvertSidToStringSidW",
        [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)],
        wintypes.BOOL,
    )
    value = ctypes.c_wchar_p()
    _check(convert(pointer, ctypes.byref(value)), "ConvertSidToStringSidW")
    try:
        if not value.value:
            raise NativeFailure("empty SID")
        return value.value
    finally:
        free = _bind(_dll("kernel32"), "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)
        free(ctypes.cast(value, ctypes.c_void_p))


def _security(handle: int) -> tuple[str, bool, tuple[q.Ace, ...]]:
    advapi = _dll("advapi32")
    get = _bind(
        advapi,
        "GetSecurityInfo",
        [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ],
        wintypes.DWORD,
    )
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    status = get(
        handle,
        SE_FILE_OBJECT,
        OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if status or not owner.value or not dacl.value or not descriptor.value:
        raise NativeFailure(f"GetSecurityInfo failed: {status}")
    try:
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        get_control = _bind(
            advapi,
            "GetSecurityDescriptorControl",
            [
                ctypes.c_void_p,
                ctypes.POINTER(wintypes.WORD),
                ctypes.POINTER(wintypes.DWORD),
            ],
            wintypes.BOOL,
        )
        _check(
            get_control(descriptor, ctypes.byref(control), ctypes.byref(revision)),
            "GetSecurityDescriptorControl",
        )
        info = AclSize()
        acl_info = _bind(
            advapi,
            "GetAclInformation",
            [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD],
            wintypes.BOOL,
        )
        _check(
            acl_info(dacl, ctypes.byref(info), ctypes.sizeof(info), 2),
            "GetAclInformation",
        )
        if info.count > 1_024:
            raise NativeFailure("ACE count bound")
        get_ace = _bind(
            advapi,
            "GetAce",
            [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)],
            wintypes.BOOL,
        )
        valid_sid = _bind(advapi, "IsValidSid", [ctypes.c_void_p], wintypes.BOOL)
        sid_length = _bind(advapi, "GetLengthSid", [ctypes.c_void_p], wintypes.DWORD)
        aces: list[q.Ace] = []
        for index in range(info.count):
            raw = ctypes.c_void_p()
            _check(get_ace(dacl, index, ctypes.byref(raw)), "GetAce")
            header = ctypes.cast(raw, ctypes.POINTER(AceHeader)).contents
            if header.ace_type not in (0, 1) or header.size < 16:
                raise NativeFailure("unsupported DACL ACE layout")
            sid_pointer = ctypes.c_void_p(raw.value + 8)
            if (
                not valid_sid(sid_pointer)
                or sid_length(sid_pointer) < 8
                or sid_length(sid_pointer) + 8 > header.size
            ):
                raise NativeFailure("malformed DACL ACE SID")
            mask = ctypes.cast(
                raw.value + 4, ctypes.POINTER(wintypes.DWORD)
            ).contents.value
            aces.append(
                q.Ace(
                    _sid(sid_pointer),
                    int(mask),
                    int(header.ace_type),
                    int(header.flags),
                )
            )
        return _sid(owner), bool(control.value & SE_DACL_PROTECTED), tuple(aces)
    finally:
        free = _bind(_dll("kernel32"), "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)
        free(descriptor)


def _fixed(path: str) -> None:
    if path == q.SYSTEM32 or (
        ntpath.dirname(path) == q.SYSTEM32
        and ntpath.basename(path).casefold().endswith(".dll")
        and ":" not in ntpath.basename(path)
        and not ntpath.basename(path).endswith((" ", "."))
        and ntpath.normpath(path) == path
    ):
        return
    if path in (q.VOLUME, q.ROOT, q.RUNTIME):
        return
    if (
        path.startswith(q.RUNTIME + "\\")
        and ntpath.normpath(path) == path
        and not any(
            part in ("", ".", "..") or ":" in part or part.endswith((" ", "."))
            for part in path[len(q.RUNTIME) + 1 :].split("\\")
        )
    ):
        return
    raise NativeFailure("path outside fixed runtime inventory")


def _open(path: str) -> int:
    _fixed(path)
    kernel = _dll("kernel32")
    create = _bind(
        kernel,
        "CreateFileW",
        [
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ],
        wintypes.HANDLE,
    )
    handle = create(
        path,
        FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | READ_CONTROL,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle in (None, 0, INVALID_HANDLE):
        raise NativeFailure(f"CreateFileW failed: {ctypes.get_last_error()}")
    return int(handle)


def _close(handle: int) -> None:
    close = _bind(_dll("kernel32"), "CloseHandle", [wintypes.HANDLE], wintypes.BOOL)
    _check(close(handle), "CloseHandle")


def _inspect(path: str, handle: int) -> tuple[q.ObjectEvidence, int]:
    kernel = _dll("kernel32")
    get_final = _bind(
        kernel,
        "GetFinalPathNameByHandleW",
        [wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD],
        wintypes.DWORD,
    )
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_final(handle, buffer, len(buffer), 0)
    if not length or length >= len(buffer) or not buffer.value.startswith("\\\\?\\"):
        raise NativeFailure("final native path unavailable")
    final = buffer.value[4:]
    if final != path:
        raise NativeFailure("final native path differs")
    info = ByHandleInfo()
    get_info = _bind(
        kernel,
        "GetFileInformationByHandle",
        [wintypes.HANDLE, ctypes.POINTER(ByHandleInfo)],
        wintypes.BOOL,
    )
    _check(get_info(handle, ctypes.byref(info)), "GetFileInformationByHandle")
    if info.attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        raise NativeFailure("reparse object")
    kind = (
        q.Kind.DIRECTORY if info.attributes & FILE_ATTRIBUTE_DIRECTORY else q.Kind.FILE
    )
    root = ctypes.create_unicode_buffer(8)
    volume_path = _bind(
        kernel,
        "GetVolumePathNameW",
        [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD],
        wintypes.BOOL,
    )
    _check(volume_path(final, root, len(root)), "GetVolumePathNameW")
    get_drive = _bind(kernel, "GetDriveTypeW", [ctypes.c_wchar_p], wintypes.UINT)
    drive_type = int(get_drive(root.value))
    fs = ctypes.create_unicode_buffer(64)
    serial = wintypes.DWORD()
    volume_info = _bind(
        kernel,
        "GetVolumeInformationW",
        [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            wintypes.DWORD,
        ],
        wintypes.BOOL,
    )
    _check(
        volume_info(root.value, None, 0, ctypes.byref(serial), None, None, fs, len(fs)),
        "GetVolumeInformationW",
    )
    if serial.value != info.volume_serial:
        raise NativeFailure("volume serial mismatch")
    owner, protected, aces = _security(handle)
    evidence = q.ObjectEvidence(
        path,
        final,
        kind,
        owner,
        protected,
        aces,
        False,
        drive_type,
        root.value,
        fs.value,
        int(info.volume_serial),
        (int(info.file_index_high) << 32) | int(info.file_index_low),
        int(info.links),
    )
    return evidence, int(info.attributes)


def _children(path: str) -> tuple[str, ...]:
    _fixed(path)
    try:
        with os.scandir(path) as scan:
            names = tuple(entry.name for entry in scan)
    except OSError as exc:
        raise NativeFailure("native directory enumeration failed") from exc
    if len(names) > h.MAX_OBJECTS or len(names) != len({n.casefold() for n in names}):
        raise NativeFailure("directory inventory bound or case collision")
    if any(
        not n
        or n in (".", "..")
        or "\\" in n
        or "/" in n
        or ":" in n
        or n.endswith((" ", "."))
        for n in names
    ):
        raise NativeFailure("malformed direct child name")
    return tuple(sorted(names))


def _absent(path: str) -> None:
    if path not in (*q.CONFIG_NAMES, q.ZIP, q.DLLS):
        raise NativeFailure("unreviewed absence probe")
    kernel = _dll("kernel32")
    create = _bind(
        kernel,
        "CreateFileW",
        [
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ],
        wintypes.HANDLE,
    )
    handle = create(
        path,
        FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle not in (None, 0, INVALID_HANDLE):
        _close(int(handle))
        raise NativeFailure("required absent name is present")
    if ctypes.get_last_error() != ERROR_FILE_NOT_FOUND:
        raise NativeFailure(f"absence probe indeterminate: {ctypes.get_last_error()}")


def collect_inventory() -> h.NativeSnapshot:
    """Open/pin every fixed runtime object, then reobserve before closing."""
    if os.name != "nt":
        raise NativeFailure("Windows required")
    with ExitStack() as stack:
        handles: dict[str, int] = {}
        first: dict[str, tuple[q.ObjectEvidence, int]] = {}

        def admit(path: str) -> None:
            if len(handles) >= h.MAX_OBJECTS:
                raise NativeFailure("inventory object bound")
            handle = _open(path)
            stack.callback(_close, handle)
            handles[path] = handle
            first[path] = _inspect(path, handle)

        admit(q.VOLUME)
        admit(q.ROOT)
        admit(q.RUNTIME)
        pending = [q.RUNTIME]
        children: dict[str, tuple[str, ...]] = {
            q.VOLUME: _children(q.VOLUME),
            q.ROOT: _children(q.ROOT),
        }
        if "AITradingBot" not in children[q.VOLUME]:
            raise NativeFailure("volume root missing fixed child")
        if "runtime" not in children[q.ROOT]:
            raise NativeFailure("installation root missing runtime")
        while pending:
            parent = pending.pop()
            parent_children = _children(parent)
            children[parent] = parent_children
            for name in parent_children:
                path = ntpath.join(parent, name)
                admit(path)
                if first[path][0].kind is q.Kind.DIRECTORY:
                    pending.append(path)
        rows: list[h.NativeObject] = []
        for path in sorted(handles):
            evidence, attributes = first[path]
            child_names = children.get(path, ())
            evidence = dataclasses.replace(evidence, children=child_names)
            parent = ntpath.dirname(path)
            parent_id = None if path == q.VOLUME else first[parent][0].file_index
            rows.append(
                h.NativeObject(evidence, attributes, len(evidence.aces), parent_id)
            )
        for path, handle in handles.items():
            if first[path] != _inspect(path, handle):
                raise NativeFailure("pinned identity/security drift")
            if path in children and children[path] != _children(path):
                raise NativeFailure("pinned directory inventory drift")
        inventory_paths = {row.evidence.path for row in rows}
        for path in q.CONFIG_NAMES:
            _absent(path)
        absent_optional: list[str] = []
        for path in (q.DLLS, q.ZIP):
            if path not in inventory_paths:
                _absent(path)
                absent_optional.append(path)
        return h.NativeSnapshot(
            tuple(rows), q.CONFIG_NAMES, tuple(absent_optional), True, True, True
        )


def _descriptor(handle: int) -> int:
    """Return a LocalFree-owned absolute security descriptor for AccessCheck."""
    get = _bind(
        _dll("advapi32"),
        "GetSecurityInfo",
        [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ],
        wintypes.DWORD,
    )
    pointer = ctypes.c_void_p()
    status = get(
        handle,
        SE_FILE_OBJECT,
        OWNER_SECURITY_INFORMATION
        | GROUP_SECURITY_INFORMATION
        | DACL_SECURITY_INFORMATION,
        None,
        None,
        None,
        None,
        ctypes.byref(pointer),
    )
    if status or not pointer.value:
        raise NativeFailure(f"GetSecurityInfo(AccessCheck) failed: {status}")
    return int(pointer.value)


class GenericMapping(ctypes.Structure):
    _fields_ = [
        ("read", wintypes.DWORD),
        ("write", wintypes.DWORD),
        ("execute", wintypes.DWORD),
        ("all", wintypes.DWORD),
    ]


def _access_check(descriptor: int, token: int, desired: int) -> tuple[int, bool]:
    access = _bind(
        _dll("advapi32"),
        "AccessCheck",
        [
            ctypes.c_void_p,
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(GenericMapping),
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.BOOL),
        ],
        wintypes.BOOL,
    )
    mapping = GenericMapping(q.FILE_READ, 0x00120116, 0x001200A0, q.ALL_ACCESS)
    privileges = ctypes.create_string_buffer(65536)
    privilege_length = wintypes.DWORD(len(privileges))
    granted = wintypes.DWORD()
    status = wintypes.BOOL()
    _check(
        access(
            descriptor,
            token,
            desired,
            ctypes.byref(mapping),
            privileges,
            ctypes.byref(privilege_length),
            ctypes.byref(granted),
            ctypes.byref(status),
        ),
        "AccessCheck",
    )
    privilege_count = ctypes.cast(
        privileges, ctypes.POINTER(wintypes.DWORD)
    ).contents.value
    if privilege_count:
        raise NativeFailure("AccessCheck used a token privilege")
    return int(granted.value), bool(status.value)


def _trading_token(pid: int) -> tuple[object, h.TokenObservation]:
    """Pin an actual non-admin Trading process token; PID is only a lookup hint."""
    if type(pid) is not int or pid <= 0:
        raise NativeFailure("Trading process ID invalid")
    try:
        import win32api
        import win32security

        process = win32api.OpenProcess(0x1000, False, pid)
        try:
            token = win32security.OpenProcessToken(
                process, win32security.TOKEN_QUERY | win32security.TOKEN_DUPLICATE
            )
        finally:
            process.Close()
        try:
            duplicate = win32security.DuplicateToken(
                token, win32security.SecurityImpersonation
            )
        finally:
            token.Close()
        sid = win32security.ConvertSidToStringSid(
            win32security.GetTokenInformation(duplicate, win32security.TokenUser)[0]
        )
        groups = win32security.GetTokenInformation(duplicate, win32security.TokenGroups)
        enabled_groups = tuple(
            sorted(
                win32security.ConvertSidToStringSid(group_sid)
                for group_sid, attributes in groups
                if attributes & 0x4
            )
        )
        privileges = win32security.GetTokenInformation(
            duplicate, win32security.TokenPrivileges
        )
        enabled_privileges = tuple(
            sorted(
                win32security.LookupPrivilegeName(None, luid)
                for luid, attributes in privileges
                if attributes & 0x2
            )
        )
        elevated = bool(
            win32security.GetTokenInformation(duplicate, win32security.TokenElevation)
        )
        member_admin = q.ADMIN in enabled_groups
        dangerous = {
            "SeBackupPrivilege",
            "SeRestorePrivilege",
            "SeTakeOwnershipPrivilege",
            "SeSecurityPrivilege",
            "SeDebugPrivilege",
        }
        if dangerous.intersection(enabled_privileges):
            duplicate.Close()
            raise NativeFailure("Trading token has enabled bypass privilege")
        facts = h.TokenObservation(
            sid,
            not member_admin and not elevated,
            elevated,
            enabled_groups,
            enabled_privileges,
            True,
            True,
        )
        if facts.sid != q.TRADING or not facts.non_admin or facts.elevated:
            duplicate.Close()
            raise NativeFailure("process token is not exact non-admin Trading")
        return duplicate, facts
    except Exception as exc:
        raise NativeFailure("Trading token acquisition failed") from exc


def collect_trading_access(
    paths: tuple[str, ...], trading_pid: int
) -> h.TradingObservation:
    """AccessCheck against the pinned actual Trading token; no ACL mutation."""
    token, facts = _trading_token(trading_pid)
    try:
        with ExitStack() as stack:
            handles: dict[str, int] = {}
            observed: dict[str, tuple[q.ObjectEvidence, int]] = {}
            for path in paths:
                _fixed(path)
                handle = _open(path)
                stack.callback(_close, handle)
                handles[path] = handle
                observed[path] = _inspect(path, handle)
            rows: list[h.NativeAccess] = []
            for path in paths:
                descriptor = _descriptor(handles[path])
                free = _bind(
                    _dll("kernel32"),
                    "LocalFree",
                    [ctypes.c_void_p],
                    ctypes.c_void_p,
                )
                try:
                    maximum, _ = _access_check(descriptor, int(token), 0x02000000)
                    exact, exact_status = _access_check(
                        descriptor, int(token), q.MUTATION_MASK
                    )
                    _, delete_status = _access_check(descriptor, int(token), 0x00010000)
                    parent_path = q.VOLUME if path == q.VOLUME else ntpath.dirname(path)
                    parent_descriptor = _descriptor(handles[parent_path])
                    try:
                        _, replace_status = _access_check(
                            parent_descriptor, int(token), 0x00000040
                        )
                    finally:
                        free(parent_descriptor)
                    granted = maximum & q.MUTATION_MASK
                    owner, protected, aces = _security(handles[path])
                    owner_again, protected_again, aces_again = _security(handles[path])
                    rows.append(
                        h.NativeAccess(
                            q.TradingAccessEvidence(
                                path,
                                q.MUTATION_MASK,
                                granted,
                                not delete_status and not replace_status,
                            ),
                            True,
                            exact_status,
                            delete_status,
                            replace_status,
                            True,
                            True,
                            owner == owner_again
                            and protected == protected_again
                            and aces == aces_again
                            and exact == 0,
                        )
                    )
                finally:
                    free(descriptor)
            for path, handle in handles.items():
                if observed[path] != _inspect(path, handle):
                    raise NativeFailure("Trading-side pinned security identity drift")
            return h.TradingObservation(facts, tuple(rows))
    finally:
        token.Close()


_DIAGNOSTIC_CODE = r"""
import sys
startup_site_absent = "site" not in sys.modules
startup_hooks_absent = all(
    name not in sys.modules for name in ("sitecustomize", "usercustomize")
)
import contextlib, ctypes, dataclasses, datetime, hashlib, json, ntpath, os
import re, subprocess, uuid, sysconfig
from ctypes import wintypes

purelib = sysconfig.get_path("purelib")
platlib = sysconfig.get_path("platlib")
json.dumps({})  # Warm the encoder before the final dependency inventory.
kernel = ctypes.WinDLL(r"C:\Windows\System32\kernel32.dll", use_last_error=True)
psapi = ctypes.WinDLL(r"C:\Windows\System32\psapi.dll", use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
psapi.EnumProcessModulesEx.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE),
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD
]
psapi.EnumProcessModulesEx.restype = wintypes.BOOL
psapi.GetModuleFileNameExW.argtypes = [
    wintypes.HANDLE, wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD
]
psapi.GetModuleFileNameExW.restype = wintypes.DWORD
process = kernel.GetCurrentProcess()
def loaded_modules():
    modules = (wintypes.HANDLE * 4096)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(
        process, modules, ctypes.sizeof(modules), ctypes.byref(needed), 3
    ):
        raise SystemExit("EnumProcessModulesEx failed")
    if (
        not needed.value
        or needed.value >= ctypes.sizeof(modules)
        or needed.value % ctypes.sizeof(wintypes.HANDLE)
    ):
        raise SystemExit("module inventory empty, malformed, or truncated")
    result = []
    for index in range(needed.value // ctypes.sizeof(wintypes.HANDLE)):
        buffer = ctypes.create_unicode_buffer(32768)
        length = psapi.GetModuleFileNameExW(
            process, modules[index], buffer, len(buffer)
        )
        if not length or length >= len(buffer):
            raise SystemExit("GetModuleFileNameExW failed")
        result.append(buffer.value)
    return result
loaded = loaded_modules()
dependencies = []
for name, module in sorted(sys.modules.items()):
    if name == "__main__":
        continue
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None)
    if origin is None:
        raise SystemExit("unknown module origin: " + name)
    dependencies.append([name, origin])
if sorted(loaded_modules()) != sorted(loaded):
    raise SystemExit("mapped module inventory drifted")
result = {
    "executable": sys.executable,
    "prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "version": ".".join(map(str, sys.version_info[:3])),
    "isolated": bool(sys.flags.isolated),
    "no_site": bool(sys.flags.no_site),
    "dont_write_bytecode": bool(sys.flags.dont_write_bytecode),
    "pycache_prefix": sys.pycache_prefix,
    "sys_path": sys.path,
    "purelib": purelib,
    "platlib": platlib,
    "site_main_called": not startup_site_absent,
    "pth_processed": not startup_hooks_absent or not startup_site_absent,
    "dependencies": dependencies,
    "loaded_modules": loaded,
}
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


def _diagnostic_path(path: str) -> str:
    """Resolve a reported runtime file through a fresh native no-follow handle."""
    if path.startswith(q.ZIP + "\\"):
        path = q.ZIP
    _fixed(path)
    handle = _open(path)
    try:
        item, _ = _inspect(path, handle)
        if item.kind is not q.Kind.FILE:
            raise NativeFailure("diagnostic dependency is not a file")
    finally:
        _close(handle)
    return path


def collect_diagnostic() -> h.Diagnostic:
    """Invoke only the fixed production interpreter; never import D10 source."""
    import json
    import subprocess

    argv = (q.PYTHON, *q.FLAGS, "-c")
    if os.name != "nt":
        raise NativeFailure("Windows required")
    try:
        completed = subprocess.run(
            [*argv, _DIAGNOSTIC_CODE],
            input=b"",
            capture_output=True,
            cwd=q.RUNTIME,
            env={"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeFailure("fixed interpreter diagnostic failed") from exc
    if (
        completed.returncode
        or not completed.stdout
        or len(completed.stdout) > 4_000_000
    ):
        raise NativeFailure("fixed interpreter diagnostic failed or overflowed")
    try:
        raw = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise NativeFailure("diagnostic JSON invalid") from exc
    if type(raw) is not dict or set(raw) != {
        "executable",
        "prefix",
        "base_prefix",
        "version",
        "isolated",
        "no_site",
        "dont_write_bytecode",
        "pycache_prefix",
        "sys_path",
        "purelib",
        "platlib",
        "site_main_called",
        "pth_processed",
        "dependencies",
        "loaded_modules",
    }:
        raise NativeFailure("diagnostic field set differs")
    for name in (
        "executable",
        "prefix",
        "base_prefix",
        "version",
        "pycache_prefix",
        "purelib",
        "platlib",
    ):
        if type(raw[name]) is not str:
            raise NativeFailure("diagnostic string type differs")
    for name in (
        "isolated",
        "no_site",
        "dont_write_bytecode",
        "site_main_called",
        "pth_processed",
    ):
        if type(raw[name]) is not bool:
            raise NativeFailure("diagnostic flag type differs")
    if type(raw["sys_path"]) is not list or not all(
        type(path) is str for path in raw["sys_path"]
    ):
        raise NativeFailure("sys.path transcript malformed")
    if type(raw["dependencies"]) is not list or not raw["dependencies"]:
        raise NativeFailure("module dependency transcript empty")
    if type(raw["loaded_modules"]) is not list or not raw["loaded_modules"]:
        raise NativeFailure("mapped module transcript empty")
    dependencies: list[h.Dependency] = []
    runtime_files: set[str] = {q.PYTHON}
    for pair in raw["dependencies"]:
        if (
            type(pair) is not list
            or len(pair) != 2
            or not all(type(value) is str for value in pair)
        ):
            raise NativeFailure("module dependency row malformed")
        name, origin = pair
        if origin in ("built-in", "builtin"):
            dependencies.append(h.Dependency(name, "builtin", None, "builtin"))
        elif origin == "frozen":
            dependencies.append(h.Dependency(name, "frozen", None, "frozen"))
        else:
            final = _diagnostic_path(origin)
            runtime_files.add(final)
            dependencies.append(h.Dependency(name, origin, final, "runtime"))
    system_dlls: set[str] = set()
    for path in raw["loaded_modules"]:
        if type(path) is not str:
            raise NativeFailure("mapped module path malformed")
        if path == q.PYTHON:
            continue
        if path.startswith(q.RUNTIME + "\\"):
            runtime_files.add(_diagnostic_path(path))
        elif ntpath.dirname(path).casefold() == q.SYSTEM32.casefold():
            if not path.casefold().endswith(".dll"):
                raise NativeFailure("non-DLL System32 module")
            system_dlls.add(path)
        else:
            raise NativeFailure("mapped module outside reviewed runtime/System32")
    if not system_dlls:
        raise NativeFailure("empty System32 loaded-DLL transcript")
    imports = q.ImportEvidence(
        raw["executable"],
        raw["prefix"],
        raw["base_prefix"],
        raw["version"],
        q.FLAGS,
        raw["isolated"],
        raw["no_site"],
        raw["dont_write_bytecode"],
        raw["pycache_prefix"],
        tuple(raw["sys_path"]),
        tuple(sorted(runtime_files)),
        tuple(sorted(system_dlls)),
        raw["purelib"],
        raw["platlib"],
        raw["site_main_called"],
        raw["pth_processed"],
    )
    return h.Diagnostic(
        imports,
        argv,
        tuple(dependencies),
        h.GUARD_IMPORTS,
        True,
        not raw["site_main_called"] and not raw["pth_processed"],
    )


def collect_system_dlls(
    paths: tuple[str, ...], trading_pid: int
) -> h.SystemDllObservation:
    """Read exact direct System32 DLLs and test actual Trading effective rights."""
    if not paths or len(paths) > h.MAX_DEPENDENCIES:
        raise NativeFailure("System32 DLL count bound")
    if len(paths) != len(set(paths)):
        raise NativeFailure("duplicate System32 DLL path")
    token, facts = _trading_token(trading_pid)
    if facts.sid != q.TRADING:
        token.Close()
        raise NativeFailure("Trading SID differs")
    try:
        with ExitStack() as stack:
            parent_handle = _open(q.SYSTEM32)
            stack.callback(_close, parent_handle)
            parent, _ = _inspect(q.SYSTEM32, parent_handle)
            if parent.kind is not q.Kind.DIRECTORY:
                raise NativeFailure("System32 parent is not a directory")
            parent_descriptor = _descriptor(parent_handle)
            stack.callback(
                _bind(
                    _dll("kernel32"), "LocalFree", [ctypes.c_void_p], ctypes.c_void_p
                ),
                parent_descriptor,
            )
            parent_maximum, _ = _access_check(parent_descriptor, int(token), 0x02000000)
            _, parent_exact = _access_check(
                parent_descriptor, int(token), q.MUTATION_MASK
            )
            _, parent_delete = _access_check(parent_descriptor, int(token), 0x00010000)
            _, parent_delete_child = _access_check(parent_descriptor, int(token), 0x40)
            if (
                parent_maximum & q.MUTATION_MASK
                or parent_exact
                or parent_delete
                or parent_delete_child
            ):
                raise NativeFailure("Trading can mutate System32 parent")
            parent_access = q.TradingAccessEvidence(
                q.SYSTEM32, q.MUTATION_MASK, 0, True
            )
            rows: list[h.SystemDll] = []
            handles: dict[str, int] = {}
            observed: dict[str, q.ObjectEvidence] = {}
            for path in sorted(paths):
                if ntpath.dirname(
                    path
                ).casefold() != q.SYSTEM32.casefold() or not ntpath.basename(
                    path
                ).casefold().endswith(".dll"):
                    raise NativeFailure("DLL is not direct System32 child")
                handle = _open(path)
                stack.callback(_close, handle)
                handles[path] = handle
                item, _ = _inspect(path, handle)
                observed[path] = item
                if item.kind is not q.Kind.FILE or item.links != 1:
                    raise NativeFailure("System32 DLL object differs")
                descriptor = _descriptor(handle)
                try:
                    maximum, _ = _access_check(descriptor, int(token), 0x02000000)
                    _, exact_status = _access_check(
                        descriptor, int(token), q.MUTATION_MASK
                    )
                    _, delete_status = _access_check(descriptor, int(token), 0x00010000)
                finally:
                    _bind(
                        _dll("kernel32"),
                        "LocalFree",
                        [ctypes.c_void_p],
                        ctypes.c_void_p,
                    )(descriptor)
                if exact_status or maximum & q.MUTATION_MASK or delete_status:
                    raise NativeFailure("Trading can mutate System32 DLL")
                rows.append(
                    h.SystemDll(
                        path,
                        item.final_path,
                        item.owner_sid,
                        item.dacl_protected,
                        item.aces,
                        0,
                        True,
                        True,
                        True,
                    )
                )
            if parent != _inspect(q.SYSTEM32, parent_handle)[0]:
                raise NativeFailure("System32 parent identity/security drift")
            for path, handle in handles.items():
                if _inspect(path, handle)[0] != observed[path]:
                    raise NativeFailure("System32 DLL identity/security drift")
            return h.SystemDllObservation(
                parent, parent_access, tuple(rows), True, True, True
            )
    finally:
        token.Close()


_PUBLIC_KEY = bytes.fromhex(
    "04f2e83034f58cc1e27b1ff6511df503c31d4103782b2992ee64ebb7a9e734a3"
    "548c5daaa5e5c69e83c2f2c2c825c26b61efd356680eed3d60822585c04493ba61"
)
_D10_ATTESTATION = q.ROOT + r"\D10\deployment.attestation.json"
_D10_SIGNATURE = q.ROOT + r"\D10\deployment.attestation.sig"


def _read_fixed_signed_input(path: str, limit: int) -> bytes:
    if path not in (_D10_ATTESTATION, _D10_SIGNATURE):
        raise NativeFailure("unreviewed signed input path")
    create = _bind(
        _dll("kernel32"),
        "CreateFileW",
        [
            ctypes.c_wchar_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ],
        wintypes.HANDLE,
    )
    handle = create(
        path,
        0x1 | FILE_READ_ATTRIBUTES | READ_CONTROL,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle in (None, 0, INVALID_HANDLE):
        raise NativeFailure("fixed signed input unavailable")
    try:
        final = ctypes.create_unicode_buffer(32768)
        get_final = _bind(
            _dll("kernel32"),
            "GetFinalPathNameByHandleW",
            [wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD],
            wintypes.DWORD,
        )
        length = get_final(handle, final, len(final), 0)
        if (
            not length
            or length >= len(final)
            or final.value[:4] != chr(92) * 2 + "?" + chr(92)
            or final.value[4:] != path
        ):
            raise NativeFailure("fixed signed input final path differs")
        info = ByHandleInfo()
        get_info = _bind(
            _dll("kernel32"),
            "GetFileInformationByHandle",
            [wintypes.HANDLE, ctypes.POINTER(ByHandleInfo)],
            wintypes.BOOL,
        )
        _check(get_info(handle, ctypes.byref(info)), "GetFileInformationByHandle")
        if (
            info.attributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY)
            or info.links != 1
        ):
            raise NativeFailure("fixed signed input object differs")
        size = (int(info.size_high) << 32) | int(info.size_low)
        if size <= 0 or size > limit:
            raise NativeFailure("fixed signed input size bound")
        buffer = ctypes.create_string_buffer(size)
        received = wintypes.DWORD()
        read = _bind(
            _dll("kernel32"),
            "ReadFile",
            [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ],
            wintypes.BOOL,
        )
        _check(read(handle, buffer, size, ctypes.byref(received), None), "ReadFile")
        if received.value != size:
            raise NativeFailure("fixed signed input short read")
        second = ByHandleInfo()
        _check(get_info(handle, ctypes.byref(second)), "GetFileInformationByHandle")
        if bytes(info) != bytes(second):
            raise NativeFailure("fixed signed input identity drift")
        return buffer.raw
    finally:
        _close(int(handle))


def _verify_signed_a123(attestation: bytes, signature: bytes) -> None:
    """Verify exact P-256/SHA-256 P1363 signature using Windows CNG."""
    import hashlib

    if len(signature) != 64 or len(_PUBLIC_KEY) != 65 or _PUBLIC_KEY[0] != 4:
        raise NativeFailure("D10 signature envelope malformed")
    bcrypt = _dll("bcrypt")
    algorithm = ctypes.c_void_p()
    key = ctypes.c_void_p()
    open_algorithm = _bind(
        bcrypt,
        "BCryptOpenAlgorithmProvider",
        [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            wintypes.ULONG,
        ],
        ctypes.c_long,
    )
    import_key = _bind(
        bcrypt,
        "BCryptImportKeyPair",
        [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            wintypes.ULONG,
            wintypes.ULONG,
        ],
        ctypes.c_long,
    )
    verify = _bind(
        bcrypt,
        "BCryptVerifySignature",
        [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.ULONG,
            ctypes.c_void_p,
            wintypes.ULONG,
            wintypes.ULONG,
        ],
        ctypes.c_long,
    )
    try:
        if open_algorithm(ctypes.byref(algorithm), "ECDSA_P256", None, 0):
            raise NativeFailure("CNG P-256 unavailable")
        blob = (ctypes.c_ubyte * 72).from_buffer_copy(
            (0x31534345).to_bytes(4, "little")
            + (32).to_bytes(4, "little")
            + _PUBLIC_KEY[1:]
        )
        if import_key(
            algorithm, None, "ECCPUBLICBLOB", ctypes.byref(key), blob, len(blob), 0
        ):
            raise NativeFailure("CNG P-256 public key rejected")
        digest = (ctypes.c_ubyte * 32).from_buffer_copy(
            hashlib.sha256(attestation).digest()
        )
        raw = (ctypes.c_ubyte * 64).from_buffer_copy(signature)
        if verify(key, None, digest, 32, raw, 64, 0):
            raise NativeFailure("signed A123 attestation invalid")
    finally:
        if key.value:
            destroy = _bind(
                bcrypt, "BCryptDestroyKey", [ctypes.c_void_p], ctypes.c_long
            )
            if destroy(key):
                raise NativeFailure("CNG key release failed")
        if algorithm.value:
            close = _bind(
                bcrypt,
                "BCryptCloseAlgorithmProvider",
                [ctypes.c_void_p, wintypes.ULONG],
                ctypes.c_long,
            )
            if close(algorithm, 0):
                raise NativeFailure("CNG algorithm release failed")


def collect_signed_a123_identity() -> h.SignedA123Identity:
    """Read only fixed D10 trust names; parse only after detached verification."""
    import hashlib

    from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
        D10_SIGNING_KEY_ID,
        parse_deployment_attestation,
    )

    attestation_bytes = _read_fixed_signed_input(_D10_ATTESTATION, 64 * 1024)
    signature = _read_fixed_signed_input(_D10_SIGNATURE, 64)
    _verify_signed_a123(attestation_bytes, signature)
    attestation = parse_deployment_attestation(attestation_bytes)
    if attestation.signing_key_id != D10_SIGNING_KEY_ID:
        raise NativeFailure("D10 signing key identity differs")
    return h.SignedA123Identity(
        attestation.production_python,
        attestation.production_python_version,
        hashlib.sha256(attestation_bytes).hexdigest(),
        True,
        True,
    )


def require_administrator() -> None:
    """Require an elevated Administrator token for the native inventory phase."""
    try:
        import win32api
        import win32security

        process = win32api.GetCurrentProcess()
        token = win32security.OpenProcessToken(process, win32security.TOKEN_QUERY)
        try:
            elevated = bool(
                win32security.GetTokenInformation(token, win32security.TokenElevation)
            )
            admin_sid = win32security.CreateWellKnownSid(
                win32security.WinBuiltinAdministratorsSid, None
            )
            admin = bool(win32security.CheckTokenMembership(None, admin_sid))
        finally:
            token.Close()
    except Exception as exc:
        raise NativeFailure("Administrator token proof unavailable") from exc
    if not elevated or not admin:
        raise NativeFailure("elevated Administrator token required")


class WindowsCollector:
    """Bound P124-1 source-only operator adapter; no paths can be selected."""

    def __init__(self, trading_pid: int) -> None:
        if type(trading_pid) is not int or trading_pid <= 0:
            raise NativeFailure("Trading process ID invalid")
        require_administrator()
        self._trading_pid = trading_pid

    def inventory(self) -> h.NativeSnapshot:
        return collect_inventory()

    def trading(self, paths: tuple[str, ...]) -> h.TradingObservation:
        return collect_trading_access(paths, self._trading_pid)

    def diagnostic(self) -> h.Diagnostic:
        return collect_diagnostic()

    def system_dlls(self, paths: tuple[str, ...]) -> h.SystemDllObservation:
        return collect_system_dlls(paths, self._trading_pid)

    def signed_a123_identity(self) -> h.SignedA123Identity:
        return collect_signed_a123_identity()


def main(argv: list[str] | None = None) -> int:
    """Protected operator entry point. Source-only tests never call this."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="P124-1 native substrate collector")
    parser.add_argument("--trading-pid", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = args.output
    if type(output) is not str or not ntpath.isabs(output):
        parser.error("output must be an absolute non-production file path")
    if output != ntpath.normpath(output) or output.startswith("\\"):
        parser.error("output path is noncanonical")
    try:
        in_production = (
            ntpath.commonpath((output, q.ROOT)).casefold() == q.ROOT.casefold()
        )
    except ValueError:
        in_production = False
    if in_production:
        parser.error("output cannot be inside the production root")
    parent = ntpath.dirname(output)
    if os.path.realpath(parent).casefold() != parent.casefold():
        parser.error("output parent redirects")
    try:
        payload = h.collect(WindowsCollector(args.trading_pid))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except (h.CollectionBlocked, OSError, ValueError) as exc:
        print(f"P124-1 BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
