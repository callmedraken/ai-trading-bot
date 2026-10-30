"""Dedicated fixed-root, create-only, rename-free B2 custody boundary.

Native methods are effectful ONLY when explicitly invoked by a future reviewed
custodian. Import, construction and source tests never touch the fixed roots.
"""

from __future__ import annotations

import ctypes
import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from functools import wraps
from hashlib import sha256
from pathlib import PureWindowsPath
from typing import Protocol
from uuid import UUID

from trading_bot.experiments.historical_research_acquisition import (
    CustodyInspection,
    CustodyPersistencePlan,
    PersistenceReceipt,
)
from trading_bot.experiments.historical_research_custody import (
    CUSTODY_ROOT,
    CUSTODY_SDDL,
    OPEN_ROOT,
    HistoricalResearchCustodyError,
    HistoricalResearchCustodyEvidence,
    canonical_json_bytes,
    historical_research_normalized_csv,
    require_accepted_historical_session_authority,
)
from trading_bot.experiments.historical_research_dataset import (
    HistoricalResearchPartitionRole,
    parse_historical_research_csv,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityInspection,
    WindowsHandle,
    inspect_open_authority_object,
    inspect_security_object_identity,
)

CUSTODY_PARENT = str(PureWindowsPath(CUSTODY_ROOT).parent)
OPEN_PARENT = str(PureWindowsPath(OPEN_ROOT).parent)
ATTEMPT_CLAIM_PATH = CUSTODY_PARENT + r"\.arch146-v1-attempt.json"
OPEN_SDDL = "O:BAG:BAD:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;BU)"
ADMIN = "S-1-5-32-544"
SYSTEM = "S-1-5-18"
USERS = "S-1-5-32-545"
PROTECTED_FILES = frozenset(
    {
        "normalized/holdout/SPY.csv",
        "corporate-actions/sidecar.json",
        "manifests/open.json",
        "manifests/holdout.json",
        "manifests/snapshot.json",
        "terminal.json",
    }
)
OPEN_FILES = (
    "normalized/open/SPY.csv",
    "manifests/open-partition.json",
    "manifests/holdout-commitment.json",
    "manifests/dataset-commitment.json",
    "manifests/custody-evidence.json",
)


def _error() -> HistoricalResearchCustodyError:
    return HistoricalResearchCustodyError("B2 custody STOP/reconciliation required")


def _protected_relative(relative: str) -> None:
    if type(relative) is not str or not (
        relative in PROTECTED_FILES
        or re.fullmatch(r"vendor-raw/(bars|corporate-actions)/[0-9]{4}\.json", relative)
    ):
        raise _error()


def _require_native_destination(path: str, *, opened: bool, directory: bool) -> None:
    root = PureWindowsPath(OPEN_ROOT if opened else CUSTODY_ROOT)
    candidate = PureWindowsPath(path)
    if any(part in {".", ".."} or ":" in part for part in candidate.parts[1:]):
        raise _error()
    if path == ATTEMPT_CLAIM_PATH and not opened and not directory:
        return
    if candidate == root and directory:
        return
    if root not in candidate.parents:
        raise _error()
    relative = candidate.relative_to(root).as_posix()
    allowed = OPEN_FILES if opened else PROTECTED_FILES
    if directory:
        prefixes = {
            str(PureWindowsPath(item).parent).replace("\\", "/") for item in allowed
        }
        prefixes.update(
            {
                "normalized",
                "vendor-raw",
                "vendor-raw/bars",
                "vendor-raw/corporate-actions",
                "manifests",
                "corporate-actions",
            }
        )
        if relative not in prefixes:
            raise _error()
    elif opened:
        if relative not in OPEN_FILES:
            raise _error()
    else:
        _protected_relative(relative)


@dataclass(frozen=True, slots=True)
class CustodyFreshState:
    """Non-price facts from the fixed native observer, not caller readiness flags."""

    classification: str
    local_ntfs: bool
    non_reparse: bool
    parent_policy: bool
    claim_absent: bool
    protected_absent: bool
    open_absent: bool

    def verify(self) -> None:
        if self.classification != "FRESH" or any(
            value is not True
            for value in (
                self.local_ntfs,
                self.non_reparse,
                self.parent_policy,
                self.claim_absent,
                self.protected_absent,
                self.open_absent,
            )
        ):
            raise _error()


class CustodyNative(Protocol):
    """Required trusted native port; injection exists only in the test constructor."""

    def observe_fresh(self) -> CustodyFreshState: ...
    def create_directory(self, path: str, *, opened: bool) -> None: ...
    def create_file(
        self, path: str, body: bytes, *, opened: bool
    ) -> PersistenceReceipt: ...
    def inspect_created(self, paths: tuple[tuple[str, bool], ...]) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class CustodyPartialState:
    """Internal handle facts; only validated fixed facts may enter public evidence."""

    classification: str
    parent: SecurityInspection | None = None
    local_fixed: bool = False
    absent: tuple[bool, ...] = ()
    close_ambiguous: bool = False


class WindowsCustodyNative:
    """Handle-based Win32 I/O; no broad provisioning or publication operator."""

    def __init__(self) -> None:
        self._directories: dict[str, int] = {}

    def _api(self, library: str, name: str, arguments: list, result):
        if os.name != "nt":
            raise _error()
        function = getattr(ctypes.WinDLL(library, use_last_error=True), name)
        function.argtypes, function.restype = arguments, result
        return function

    def _close(self, handle: int) -> None:
        if not self._api("kernel32", "CloseHandle", [ctypes.c_void_p], ctypes.c_int)(
            handle
        ):
            raise _error()

    def _open(self, path: str, *, create: bool = False, attributes=None) -> int:
        directory = not create
        handle = self._api(
            "kernel32",
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
        )(
            path,
            0xC0020080 if create else 0x20080,
            0 if create else 3,
            attributes,
            1 if create else 3,
            0x00200000 | (0x80000000 if create else 0x02000000),
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            code = ctypes.get_last_error()
            if not create and code in (2, 3):
                raise FileNotFoundError
            raise _error()
        try:
            kind = (
                AuthorityObjectKind.DIRECTORY if directory else AuthorityObjectKind.FILE
            )
            inspect_open_authority_object(handle, path, kind)
        except BaseException:
            self._close(handle)
            raise
        return handle

    def _security(
        self, handle: int, path: str, *, directory: bool, opened: bool
    ) -> None:
        facts = inspect_open_authority_object(
            handle,
            path,
            AuthorityObjectKind.DIRECTORY if directory else AuthorityObjectKind.FILE,
        )
        flags = 3 if directory else 0
        expected = [(ADMIN, 0x1F01FF, 0, flags), (SYSTEM, 0x1F01FF, 0, flags)]
        if opened:
            expected.append((USERS, 0x1200A9, 0, flags))
        actual = tuple(
            (a.principal_sid, a.access_mask, a.ace_type, a.ace_flags)
            for a in facts.aces
        )
        if (
            facts.owner_sid != ADMIN
            or facts.dacl_protected is not True
            or Counter(actual) != Counter(expected)
        ):
            raise _error()

    def _hold(self, path: str) -> int:
        if path not in self._directories:
            self._directories[path] = self._open(path)
        handle = self._directories[path]
        inspect_open_authority_object(handle, path, AuthorityObjectKind.DIRECTORY)
        return handle

    def _parents(self, path: str) -> None:
        if (
            self._api("kernel32", "GetDriveTypeW", [ctypes.c_wchar_p], ctypes.c_uint32)(
                "F:\\"
            )
            != 3
        ):
            raise _error()
        parent = PureWindowsPath(path).parent
        for item in (*reversed(parent.parents), parent):
            self._hold(str(item))

    def _absent(self, path: str) -> bool:
        # FILE_READ_ATTRIBUTES, no-follow, no data read. Existing ANY kind is STOP.
        handle = self._api(
            "kernel32",
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
        )(path, 0x80, 3, None, 3, 0x02200000, None)
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            if ctypes.get_last_error() in (2, 3):
                return True
            raise _error()
        self._close(handle)
        return False

    def observe_fresh(self) -> CustodyFreshState:
        try:
            for root in (CUSTODY_ROOT, OPEN_ROOT):
                self._parents(root)
            self._security(
                self._hold(CUSTODY_PARENT), CUSTODY_PARENT, directory=True, opened=False
            )
            absent = tuple(
                self._absent(p)
                for p in (
                    ATTEMPT_CLAIM_PATH,
                    CUSTODY_ROOT,
                    OPEN_ROOT,
                )
            )
            return CustodyFreshState(
                "FRESH" if all(absent) else "EXISTING_OR_PARTIAL_STOP",
                True,
                True,
                True,
                *absent,
            )
        except Exception:
            return CustodyFreshState(
                "UNPROVEN_STOP", False, False, False, False, False, False
            )

    def observe_partial_state_readonly(self) -> CustodyPartialState:
        """Hold only the protected parent chain and probe four fixed absences.

        OPEN's parent need not exist. Every open is OPEN_EXISTING/no-follow,
        without data access or delete sharing. All handles, including existing
        absence targets of any kind, close in reverse order before returning.
        This method deliberately does not enter observe_fresh() or its state.
        """
        handles: list[int] = []
        state = CustodyPartialState("HOST_UNKNOWN")

        def open_existing(path: str, access: int) -> int | None:
            handle = self._api(
                "kernel32",
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
            )(path, access, 3, None, 3, 0x02200000, None)
            if handle in (None, 0, ctypes.c_void_p(-1).value):
                if ctypes.get_last_error() in (2, 3):
                    return None
                raise _error()
            handles.append(handle)
            return handle

        try:
            local_fixed = (
                self._api(
                    "kernel32", "GetDriveTypeW", [ctypes.c_wchar_p], ctypes.c_uint32
                )("F:\\")
                == 3
            )
            if not local_fixed:
                state = CustodyPartialState("HOST_VOLUME_POLICY")
            else:
                parent = None
                fixed_parent = PureWindowsPath(CUSTODY_PARENT)
                for item in (*reversed(fixed_parent.parents), fixed_parent):
                    path = str(item)
                    handle = open_existing(path, 0x20080)
                    if handle is None:
                        raise FileNotFoundError
                    parent = inspect_open_authority_object(
                        handle, path, AuthorityObjectKind.DIRECTORY
                    )
                if parent is not None:
                    parent = replace(
                        parent,
                        aces=tuple(
                            sorted(
                                parent.aces,
                                key=lambda ace: (
                                    ace.principal_sid,
                                    ace.access_mask,
                                    ace.ace_type,
                                    ace.ace_flags,
                                ),
                            )
                        ),
                    )
                absent = tuple(
                    open_existing(path, 0x80) is None
                    for path in (
                        ATTEMPT_CLAIM_PATH,
                        CUSTODY_ROOT,
                        OPEN_PARENT,
                        OPEN_ROOT,
                    )
                )
                state = CustodyPartialState("OBSERVED", parent, local_fixed, absent)
        except FileNotFoundError:
            state = CustodyPartialState("HOST_PARENT_UNAVAILABLE")
        except Exception:
            state = CustodyPartialState("HOST_UNKNOWN")
        finally:
            failed = False
            for handle in reversed(handles):
                try:
                    self._close(handle)
                except Exception:
                    failed = True
            if failed:
                state = replace(state, close_ambiguous=True)
        return state

    def _attributes(self, sddl: str):
        native = self

        class Attributes:
            def __enter__(self):
                class SA(ctypes.Structure):
                    _fields_ = [
                        ("length", ctypes.c_uint32),
                        ("descriptor", ctypes.c_void_p),
                        ("inherit", ctypes.c_int),
                    ]

                self.descriptor = ctypes.c_void_p()
                if not native._api(
                    "advapi32",
                    "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                    [
                        ctypes.c_wchar_p,
                        ctypes.c_uint32,
                        ctypes.POINTER(ctypes.c_void_p),
                        ctypes.c_void_p,
                    ],
                    ctypes.c_int,
                )(sddl, 1, ctypes.byref(self.descriptor), None):
                    raise _error()
                self.attributes = SA(ctypes.sizeof(SA), self.descriptor, 0)
                return ctypes.byref(self.attributes)

            def __exit__(self, *args):
                if native._api(
                    "kernel32", "LocalFree", [ctypes.c_void_p], ctypes.c_void_p
                )(self.descriptor):
                    raise _error()

        return Attributes()

    def flush_namespace(self) -> None:
        # NTFS namespace durability is not inferred from closing a directory.
        create = self._api(
            "kernel32",
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
        handle = create(r"\\.\F:", 0xC0000000, 3, None, 3, 0, None)
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise _error()
        try:
            if not self._api(
                "kernel32", "FlushFileBuffers", [ctypes.c_void_p], ctypes.c_int
            )(handle):
                raise _error()
        finally:
            self._close(handle)

    def create_directory(self, path: str, *, opened: bool) -> None:
        _require_native_destination(path, opened=opened, directory=True)
        self._parents(path)
        with self._attributes(OPEN_SDDL if opened else CUSTODY_SDDL) as attributes:
            if not self._api(
                "kernel32",
                "CreateDirectoryW",
                [ctypes.c_wchar_p, ctypes.c_void_p],
                ctypes.c_int,
            )(path, attributes):
                raise _error()
        self._security(self._hold(path), path, directory=True, opened=opened)
        self.flush_namespace()

    def create_file(
        self, path: str, body: bytes, *, opened: bool
    ) -> PersistenceReceipt:
        _require_native_destination(path, opened=opened, directory=False)
        self._parents(path)
        # Files have an explicit protected DACL too; never inherit broader grants.
        sddl = (OPEN_SDDL if opened else CUSTODY_SDDL).replace("OICI;", ";")
        with self._attributes(sddl) as attributes:
            handle = self._open(path, create=True, attributes=attributes)
        try:
            self._security(handle, path, directory=False, opened=opened)
            identity = inspect_security_object_identity(
                WindowsHandle(handle, close=False)
            )
            if identity[2] != 1:
                raise _error()
            written = ctypes.c_uint32()
            buffer = ctypes.create_string_buffer(body)
            if not self._api(
                "kernel32",
                "WriteFile",
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p,
                ],
                ctypes.c_int,
            )(handle, buffer, len(body), ctypes.byref(written), None):
                raise _error()
            if written.value != len(body):
                raise _error()
            if not self._api(
                "kernel32", "FlushFileBuffers", [ctypes.c_void_p], ctypes.c_int
            )(handle):
                raise _error()
            self.flush_namespace()
            offset = ctypes.c_int64()
            if not self._api(
                "kernel32",
                "SetFilePointerEx",
                [
                    ctypes.c_void_p,
                    ctypes.c_int64,
                    ctypes.POINTER(ctypes.c_int64),
                    ctypes.c_uint32,
                ],
                ctypes.c_int,
            )(handle, 0, ctypes.byref(offset), 0):
                raise _error()
            read = ctypes.c_uint32()
            readback = ctypes.create_string_buffer(len(body) + 1)
            if not self._api(
                "kernel32",
                "ReadFile",
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p,
                ],
                ctypes.c_int,
            )(handle, readback, len(body) + 1, ctypes.byref(read), None):
                raise _error()
            if read.value != len(body) or readback.raw[: read.value] != body:
                raise _error()
            self._security(handle, path, directory=False, opened=opened)
            if (
                inspect_security_object_identity(WindowsHandle(handle, close=False))
                != identity
            ):
                raise _error()
        finally:
            self._close(handle)
        return PersistenceReceipt(path, sha256(body).hexdigest(), len(body), True)

    def inspect_created(self, paths: tuple[tuple[str, bool], ...]) -> None:
        for path, opened in paths:
            self._parents(path)
            self._security(self._hold(path), path, directory=True, opened=opened)

    def close(self) -> None:
        failed = False
        for handle in reversed(tuple(self._directories.values())):
            try:
                self._close(handle)
            except Exception:
                failed = True
        self._directories.clear()
        if failed:
            raise _error()


def _terminal_on_error(method):
    """Any ambiguous custody method consumes this adapter; never retry it."""

    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException:
            self._terminal = True
            try:
                self._native.close()
            except Exception:
                pass
            raise _error() from None

    return guarded


class WindowsHistoricalResearchCustody:
    """B1 protocol adapter with an irreversible durable claim and no cleanup API."""

    def __init__(self) -> None:
        self._native = WindowsCustodyNative()
        self._test_only = False
        self._used = False
        self._claimed = False
        self._prepared = False
        self._terminal = False
        self._directories: dict[str, bool] = {}
        self._protected: dict[str, bytes] = {}
        self._opened = False

    @classmethod
    def for_test(cls, native: CustodyNative) -> WindowsHistoricalResearchCustody:
        result = cls()
        result._native, result._test_only = native, True
        return result

    @_terminal_on_error
    def claim_attempt(self, attempt_id: str, plan: CustodyPersistencePlan) -> bool:
        if self._used:
            raise _error()
        self._used = True
        if (
            type(plan) is not CustodyPersistencePlan
            or plan != CustodyPersistencePlan()
            or type(attempt_id) is not str
            or str(UUID(attempt_id)) != attempt_id
        ):
            raise _error()
        self._native.observe_fresh().verify()
        body = canonical_json_bytes(
            {
                "schema": "arch146-b2-attempt-claim/v1",
                "attempt_id": attempt_id,
                "state": "CONSUMED",
            }
        )
        receipt = self._native.create_file(ATTEMPT_CLAIM_PATH, body, opened=False)
        receipt.verify(ATTEMPT_CLAIM_PATH, body)
        self._claimed = True
        return True

    @_terminal_on_error
    def prepare_protected(self, plan: CustodyPersistencePlan) -> None:
        if (
            not self._claimed
            or self._prepared
            or self._terminal
            or type(plan) is not CustodyPersistencePlan
            or plan != CustodyPersistencePlan()
        ):
            raise _error()
        self._native.create_directory(CUSTODY_ROOT, opened=False)
        self._directories[CUSTODY_ROOT] = False
        self._prepared = True

    def inspect(self) -> CustodyInspection:
        if not self._prepared or self._terminal:
            raise _error()
        self._native.inspect_created(tuple(self._directories.items()))
        return CustodyInspection(
            CUSTODY_ROOT, OPEN_ROOT, ADMIN, CUSTODY_SDDL, True, True, True
        )

    def _persist(self, root: str, relative: str, body: bytes, *, opened: bool):
        if (
            not self._prepared
            or self._terminal
            or type(body) is not bytes
            or not 0 < len(body) <= 64 * 1024 * 1024
        ):
            raise _error()
        path = PureWindowsPath(root).joinpath(*relative.split("/"))
        for parent in reversed(path.parent.parents):
            if (
                parent == PureWindowsPath(root)
                or PureWindowsPath(root) in parent.parents
            ):
                self._directory(str(parent), opened)
        self._directory(str(path.parent), opened)
        receipt = self._native.create_file(str(path), body, opened=opened)
        receipt.verify(str(path), body)
        return PersistenceReceipt(relative, receipt.digest, receipt.byte_size, True)

    def _directory(self, path: str, opened: bool):
        if path not in self._directories:
            self._native.create_directory(path, opened=opened)
            self._directories[path] = opened

    @_terminal_on_error
    def persist_protected(self, relative_path: str, body: bytes) -> PersistenceReceipt:
        _protected_relative(relative_path)
        if relative_path == "terminal.json" or relative_path in self._protected:
            raise _error()
        self.inspect().verify()
        receipt = self._persist(CUSTODY_ROOT, relative_path, body, opened=False)
        self._protected[relative_path] = body
        return receipt

    @_terminal_on_error
    def materialize_open(
        self, files: tuple[tuple[str, bytes], ...]
    ) -> tuple[PersistenceReceipt, ...]:
        if (
            self._opened
            or type(files) is not tuple
            or tuple(path for path, _ in files) != OPEN_FILES
        ):
            raise _error()
        self._opened = True
        values = dict(files)
        evidence = HistoricalResearchCustodyEvidence.from_bytes(values[OPEN_FILES[-1]])
        authority = published_historical_session_authority()
        require_accepted_historical_session_authority(authority)
        data = parse_historical_research_csv(
            values[OPEN_FILES[0]], HistoricalResearchPartitionRole.OPEN
        )
        authority.verify(data)
        if historical_research_normalized_csv(data.bars) != values[OPEN_FILES[0]]:
            raise _error()
        for public, protected, expected in (
            (
                OPEN_FILES[1],
                "manifests/open.json",
                evidence.open_manifest.to_json().encode(),
            ),
            (
                OPEN_FILES[2],
                "manifests/holdout.json",
                evidence.holdout_manifest.to_json().encode(),
            ),
            (
                OPEN_FILES[3],
                "manifests/snapshot.json",
                evidence.snapshot.to_json().encode(),
            ),
        ):
            if values[public] != expected or self._protected.get(protected) != expected:
                raise _error()
        if (
            sha256(values[OPEN_FILES[0]]).hexdigest()
            != evidence.open_manifest.normalized_file_sha256
            or "normalized/holdout/SPY.csv" not in self._protected
        ):
            raise _error()
        self.inspect().verify()
        self._directory(OPEN_ROOT, True)
        return tuple(
            self._persist(OPEN_ROOT, path, body, opened=True) for path, body in files
        )

    def record_terminal(self, state: str, stage: str) -> None:
        if (
            self._terminal
            or not self._claimed
            or state
            not in {
                "STOP_RECONCILIATION_REQUIRED",
                "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION",
            }
            or re.fullmatch(r"[A-Z_]{1,96}", stage) is None
        ):
            raise _error()
        try:
            self._persist(
                CUSTODY_ROOT,
                "terminal.json",
                canonical_json_bytes({"state": state, "stage": stage}),
                opened=False,
            )
        finally:
            self._terminal = True
            self._native.close()
