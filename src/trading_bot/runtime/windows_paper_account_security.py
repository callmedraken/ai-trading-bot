"""Read-only, paper-specific fixed-path Windows object boundary for P3.

No C1 path guard is changed. Open handles pin every parent and payload until
inventory verification ends. No create, ACL write, rename, or repair API exists.
"""

from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from pathlib import PureWindowsPath

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityError,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_security import (
    FILE_ADD_SUBDIRECTORY,
    FILE_ALL_ACCESS,
    FILE_FLAG_BACKUP_SEMANTICS,
    FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    FILE_READ_DATA,
    FILE_READ_EA,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    FILE_TRAVERSE,
    OPEN_EXISTING,
    READ_CONTROL,
    SYNCHRONIZE,
    AuthorityObjectKind,
    SecurityAce,
    SecurityPolicy,
    authority_security_policy,
    inspect_open_authority_object,
    require_security_policy,
)

PRODUCTION_PAPER_ROOT = PureWindowsPath(r"F:\AITradingBot\Paper")
_ADMINISTRATORS = "S-1-5-32-544"
_SYSTEM = "S-1-5-18"
_READ = (
    FILE_READ_DATA | FILE_READ_EA | FILE_READ_ATTRIBUTES | READ_CONTROL | SYNCHRONIZE
)


class PaperAccountSecurityError(WindowsAuthorityError):
    """A fixed paper object could not be safely read."""


def enumerate_paper_directory(path: str, limit: int) -> tuple[str, ...]:
    """Bound one directory listing; callers must separately pin its identity."""
    names = []
    with os.scandir(path) as entries:
        for entry in entries:
            if len(names) >= limit:
                raise PaperAccountSecurityError("paper inventory limit exceeded")
            names.append(entry.name)
    return tuple(names)


def require_fixed_paper_path(path: str | PureWindowsPath) -> PureWindowsPath:
    """Accept canonical paper descendants only, never aliases or device paths."""
    raw = str(path)
    candidate = PureWindowsPath(raw)
    if (
        raw != str(candidate)
        or not raw.startswith(str(PRODUCTION_PAPER_ROOT))
        or not candidate.is_relative_to(PRODUCTION_PAPER_ROOT)
        or len(candidate.parts) > 7
        or any(
            part in {".", ".."}
            or part.endswith((".", " "))
            or any(char in part for char in ':<>"|?*')
            or re.fullmatch(
                r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?",
                part,
                re.IGNORECASE,
            )
            for part in candidate.parts[1:]
        )
    ):
        raise PaperAccountSecurityError("paper path is outside the fixed layout")
    return candidate


def paper_account_security_policy(
    role: str, trading_sid: str, *, owner_sid: str = _ADMINISTRATORS
) -> SecurityPolicy:
    """Exact protected, noninheriting P3 paper object policy.

    Separately provisioned anchor/genesis are administrator-owned, Trading-read
    only. The root allows creation of operation/transition directories, but no
    replacement of its immutable files. Finalized A64/67 output objects admit
    the approved creator owners; their ordinary data rights do not grant ACE or
    owner editing. Provisioning/security normalization is deliberately absent.
    """
    immutable = role in {"anchor", "genesis-file", "genesis-directory", "root"}
    if (immutable and owner_sid != _ADMINISTRATORS) or owner_sid not in {
        _ADMINISTRATORS,
        _SYSTEM,
        trading_sid,
    }:
        raise PaperAccountSecurityError("paper object owner is not approved")
    rights = _READ
    if role in {"root", "genesis-directory", "output-directory"}:
        rights |= FILE_TRAVERSE
    if role == "root":
        rights |= FILE_ADD_SUBDIRECTORY
    elif role in {"output-file", "output-directory"}:
        # Match ordinary file/dir data access, excluding WRITE_DAC/WRITE_OWNER.
        rights = FILE_ALL_ACCESS & ~0x000C0000
    elif role not in {"anchor", "genesis-file", "genesis-directory"}:
        raise PaperAccountSecurityError("paper object security role is invalid")
    return SecurityPolicy(
        owner_sid,
        (
            SecurityAce(_ADMINISTRATORS, FILE_ALL_ACCESS),
            SecurityAce(_SYSTEM, FILE_ALL_ACCESS),
            SecurityAce(trading_sid, rights),
        ),
    )


class _FileInfo(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("created", wintypes.FILETIME),
        ("accessed", wintypes.FILETIME),
        ("written", wintypes.FILETIME),
        ("volume", wintypes.DWORD),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD),
        ("index_high", wintypes.DWORD),
        ("index_low", wintypes.DWORD),
    ]


class WindowsPaperAccountReadSession:
    """Production-only bounded reader. Callers supply only recognized names.

    Directory sharing excludes deletion. Payload sharing excludes both writing
    and deletion. Security/type/final-path and identity are checked at open and
    again at completion, while all handles remain open.
    """

    def __init__(self, trading_sid: str) -> None:
        require_windows_platform()
        self._sid = trading_sid
        self._handles: dict[str, tuple[int, bool, str, tuple[int, ...]]] = {}
        self._listings: dict[str, tuple[frozenset[str], int]] = {}
        self._native = ctypes.WinDLL("kernel32", use_last_error=True)

    def __enter__(self) -> WindowsPaperAccountReadSession:
        return self

    def __exit__(self, *args: object) -> None:
        failed = False
        close = self._native.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        for handle, *_ in reversed(tuple(self._handles.values())):
            failed = not close(handle) or failed
        self._handles.clear()
        if failed:
            raise PaperAccountSecurityError("paper read handle close failed")

    def _facts(self, handle: int, directory: bool) -> tuple[int, ...]:
        get_type = self._native.GetFileType
        get_type.argtypes = [wintypes.HANDLE]
        get_type.restype = wintypes.DWORD
        if get_type(handle) != 1:  # FILE_TYPE_DISK; excludes devices and pipes.
            raise PaperAccountSecurityError("paper object is not a disk object")
        info = _FileInfo()
        get_info = self._native.GetFileInformationByHandle
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInfo)]
        get_info.restype = wintypes.BOOL
        if not get_info(handle, ctypes.byref(info)):
            raise PaperAccountSecurityError("paper object identity is unavailable")
        if bool(info.attributes & 0x10) != directory or info.attributes & (
            0x400 | 0x40
        ):
            raise PaperAccountSecurityError("paper object type is unsafe")
        identity = (info.volume, info.index_high, info.index_low)
        if not directory:
            identity += (
                info.size_high,
                info.size_low,
                info.written.dwHighDateTime,
                info.written.dwLowDateTime,
                info.links,
            )
        return identity

    def _inspect(self, handle: int, path: str, directory: bool, role: str) -> None:
        if role == "c1-parent":
            # C1's administrator-controlled deployment parent deliberately grants
            # Trading no READ_CONTROL/list right. Pin it with zero desired access
            # and validate type/reparse/final identity, without weakening its ACL.
            final = self._native.GetFinalPathNameByHandleW
            final.argtypes = [
                wintypes.HANDLE,
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            final.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            count = final(handle, buffer, len(buffer), 0)
            if (
                not 0 < count < len(buffer)
                or buffer.value.casefold() != ("\\\\?\\" + path).casefold()
            ):
                raise PaperAccountSecurityError("paper parent final path is unsafe")
            return
        inspection = inspect_open_authority_object(
            handle,
            path,
            AuthorityObjectKind.DIRECTORY if directory else AuthorityObjectKind.FILE,
        )
        if role == "snapshot":
            # Historical authority is exact bytes, not current file ACL identity.
            # The C1 parent trust boundary is checked and pinned separately.
            return
        if role in {"authority", "capture-output"}:
            policy = authority_security_policy(role, self._sid)
        else:
            policy = paper_account_security_policy(
                role, self._sid, owner_sid=inspection.owner_sid
            )
        require_security_policy(inspection, policy)

    def _open(self, path: str, directory: bool, role: str) -> int:
        if path in self._handles:
            handle, old_directory, old_role, _ = self._handles[path]
            if (directory, role) != (old_directory, old_role):
                raise PaperAccountSecurityError("paper object role changed")
            return handle
        create = self._native.CreateFileW
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
            0
            if role == "c1-parent"
            else FILE_READ_DATA | READ_CONTROL | FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | (FILE_SHARE_WRITE if directory else 0),
            None,
            OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT
            | (FILE_FLAG_BACKUP_SEMANTICS if directory else 0),
            None,
        )
        if handle in {None, 0, -1, ctypes.c_void_p(-1).value}:
            raise PaperAccountSecurityError("paper object could not be opened")
        # Register immediately so even a failed inspection deterministically closes.
        self._handles[path] = (handle, directory, role, ())
        self._inspect(handle, path, directory, role)
        facts = self._facts(handle, directory)
        self._handles[path] = (handle, directory, role, facts)
        return handle

    def _parent(self) -> None:
        self._open(str(PRODUCTION_AUTHORITY_PATHS.root.parent), True, "c1-parent")

    def _paper_open(self, path: str, directory: bool, role: str) -> int:
        fixed = require_fixed_paper_path(path)
        self._parent()
        if fixed != PRODUCTION_PAPER_ROOT and str(fixed.parent) not in self._handles:
            raise PaperAccountSecurityError("paper parent has not been pinned")
        return self._open(str(fixed), directory, role)

    def inventory(self, path: str, role: str, limit: int) -> tuple[str, ...]:
        """Bounded enumeration of one pinned paper directory, never C3 output."""
        self._paper_open(path, True, role)
        names = enumerate_paper_directory(path, limit)
        self._listings[path] = (frozenset(names), limit)
        return names

    def read(self, path: str, role: str, limit: int) -> bytes:
        if role == "snapshot":
            fixed = PureWindowsPath(path)
            root = PRODUCTION_AUTHORITY_PATHS.capture_output
            if (
                str(fixed) != path
                or fixed.parent != root
                or re.fullmatch(
                    r"daily-market-data-snapshot-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json",
                    fixed.name,
                )
                is None
            ):
                raise PaperAccountSecurityError("historical snapshot path is invalid")
            self._parent()
            self._open(str(root.parent), True, "authority")
            self._open(str(root), True, "capture-output")
            handle = self._open(path, False, role)
        else:
            handle = self._paper_open(path, False, role)
        before = self._facts(handle, False)
        size = (before[3] << 32) | before[4]
        if not 0 < size <= limit:
            raise PaperAccountSecurityError("paper artifact length is invalid")
        seek = self._native.SetFilePointerEx
        seek.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        seek.restype = wintypes.BOOL
        if not seek(handle, 0, None, 0):
            raise PaperAccountSecurityError("paper artifact seek failed")
        read = self._native.ReadFile
        read.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        read.restype = wintypes.BOOL
        payload = bytearray()
        while len(payload) <= limit:
            requested = min(65536, limit + 1 - len(payload))
            buffer = ctypes.create_string_buffer(requested)
            count = wintypes.DWORD()
            if not read(handle, buffer, requested, ctypes.byref(count), None):
                raise PaperAccountSecurityError("paper artifact read failed")
            if count.value == 0:
                break
            payload.extend(buffer.raw[: count.value])
        if len(payload) != size or self._facts(handle, False) != before:
            raise PaperAccountSecurityError("paper artifact changed during read")
        return bytes(payload)

    def finish(self) -> None:
        """Reconcile all pinned objects and the complete bounded inventories."""
        for path, (handle, directory, role, facts) in self._handles.items():
            self._inspect(handle, path, directory, role)
            if self._facts(handle, directory) != facts:
                raise PaperAccountSecurityError("paper object identity changed")
        for path, (names, limit) in self._listings.items():
            if frozenset(enumerate_paper_directory(path, limit)) != names:
                raise PaperAccountSecurityError("paper inventory changed")
