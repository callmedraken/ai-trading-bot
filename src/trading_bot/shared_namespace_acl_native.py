"""Private R1 exact-handle backend. No public target/policy-taking ACL writer.

Target opens are OPEN_EXISTING, no-follow, exclusive-share and WRITE_DAC only
beyond read rights. Exclusive target handles suppress SetSecurityInfo child
propagation; no descendant is opened for mutation and no owner is rewritten.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from pathlib import PureWindowsPath

from trading_bot import shared_namespace_acl_recovery as contract


class _NativeError(RuntimeError):
    """Closed numeric-free diagnostics; never arbitrary native error strings."""


def _bind(library: object, name: str, arguments: list, result: object):
    match name:
        case "CreateFileW":
            function = library.CreateFileW
        case "GetFinalPathNameByHandleW":
            function = library.GetFinalPathNameByHandleW
        case "GetFileType":
            function = library.GetFileType
        case "GetFileInformationByHandle":
            function = library.GetFileInformationByHandle
        case "GetVolumeInformationByHandleW":
            function = library.GetVolumeInformationByHandleW
        case "GetSecurityInfo":
            function = library.GetSecurityInfo
        case "GetSecurityDescriptorLength":
            function = library.GetSecurityDescriptorLength
        case "GetSecurityDescriptorControl":
            function = library.GetSecurityDescriptorControl
        case "GetAclInformation":
            function = library.GetAclInformation
        case "GetAce":
            function = library.GetAce
        case "ConvertSidToStringSidW":
            function = library.ConvertSidToStringSidW
        case "GetDriveTypeW":
            function = library.GetDriveTypeW
        case "CloseHandle":
            function = library.CloseHandle
        case "LocalFree":
            function = library.LocalFree
        case "ConvertStringSecurityDescriptorToSecurityDescriptorW":
            function = library.ConvertStringSecurityDescriptorToSecurityDescriptorW
        case "GetSecurityDescriptorDacl":
            function = library.GetSecurityDescriptorDacl
        case "SetSecurityInfo":
            function = library.SetSecurityInfo
        case _:
            raise _NativeError("R1_BINDING_REJECTED")
    function.argtypes, function.restype = arguments, result
    return function


def _sid(advapi: object, kernel: object, sid: object) -> str:
    text = ctypes.c_wchar_p()
    if (
        not _bind(
            advapi,
            "ConvertSidToStringSidW",
            [ctypes.c_void_p, ctypes.c_void_p],
            ctypes.c_int32,
        )(sid, ctypes.byref(text))
        or not text.value
    ):
        raise _NativeError("R1_SID_REJECTED")
    try:
        if len(text.value) > 184:
            raise _NativeError("R1_SID_BUDGET_REJECTED")
        return text.value
    finally:
        if _bind(kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)(text):
            raise _NativeError("R1_SID_CLOSE_REJECTED")


class _FixedPaths:
    def admit(self, path: str) -> str:
        if type(path) is not str or path not in contract.OBSERVED_PATHS:
            raise _NativeError("R1_FIXED_PATH_REJECTED")
        return path


class _Session:
    def __init__(self, *, mutable: bool = False) -> None:
        if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise _NativeError("R1_WINDOWS_HOST_REJECTED")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        self.handles = {}
        self.paths = _FixedPaths()
        self._mutable = mutable

    def open_object(self, path: str, *, directory: bool) -> int | None:
        self.paths.admit(path)
        if directory is not (path != contract.RUNTIME_PATHS[1]):
            raise _NativeError("R1_OBJECT_KIND_REJECTED")
        parent = str(PureWindowsPath(path).parent)
        if parent != path and parent not in self.handles:
            fact = self.object(parent, directory=True)
            if fact is None or fact.reparse or fact.kind != "directory":
                raise _NativeError("R1_ANCESTOR_REJECTED")
        if path in self.handles:
            return self.handles[path]
        target = self._mutable and path in contract.TARGET_PATHS
        handle = _bind(
            self.kernel,
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
            0x160089 if target else 0x120089,
            0 if target else (3 if directory else 1),
            None,
            3,
            0x02200000,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise _NativeError("R1_FIXED_OPEN_REJECTED")
        self.handles[path] = handle
        return handle

    def object(self, path: str, *, directory: bool) -> contract.ObjectFacts:
        return self._evidence(path, directory=directory).facts

    def _evidence(self, path: str, *, directory: bool) -> contract.SecurityEvidence:
        handle = self.open_object(path, directory=directory)
        pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
        final = ctypes.create_unicode_buffer(1024)
        count = _bind(
            self.kernel,
            "GetFinalPathNameByHandleW",
            [pointer, ctypes.c_wchar_p, dword, dword],
            dword,
        )(handle, final, len(final), 0)
        if not 0 < count < len(final) or final.value != "\\\\?\\" + path:
            raise _NativeError("R1_CANONICAL_PATH_REJECTED")

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
        serial, flags = dword(), dword()
        filesystem = ctypes.create_unicode_buffer(32)
        if (
            _bind(self.kernel, "GetFileType", [pointer], dword)(handle) != 1
            or not _bind(
                self.kernel, "GetFileInformationByHandle", [pointer, pointer], boolean
            )(handle, ctypes.byref(info))
            or not _bind(
                self.kernel,
                "GetVolumeInformationByHandleW",
                [
                    pointer,
                    ctypes.c_wchar_p,
                    dword,
                    pointer,
                    pointer,
                    pointer,
                    ctypes.c_wchar_p,
                    dword,
                ],
                boolean,
            )(
                handle,
                None,
                0,
                ctypes.byref(serial),
                None,
                ctypes.byref(flags),
                filesystem,
                len(filesystem),
            )
            or serial.value != info.volume
        ):
            raise _NativeError("R1_VOLUME_FACTS_REJECTED")
        owner, group, dacl, descriptor = pointer(), pointer(), pointer(), pointer()
        try:
            status = _bind(
                self.advapi,
                "GetSecurityInfo",
                [pointer, dword, dword, pointer, pointer, pointer, pointer, pointer],
                dword,
            )(
                handle,
                1,
                7,
                ctypes.byref(owner),
                ctypes.byref(group),
                ctypes.byref(dacl),
                None,
                ctypes.byref(descriptor),
            )
            if status != 0 or not all(
                (owner.value, group.value, dacl.value, descriptor.value)
            ):
                raise _NativeError("R1_DESCRIPTOR_REJECTED")
            length = _bind(
                self.advapi, "GetSecurityDescriptorLength", [pointer], dword
            )(descriptor)
            if not 20 <= length <= 65536:
                raise _NativeError("R1_DESCRIPTOR_BUDGET_REJECTED")
            digest = hashlib.sha256(ctypes.string_at(descriptor, length)).hexdigest()
            control, revision = ctypes.c_uint16(), dword()

            class AclSize(ctypes.Structure):
                _fields_ = [("count", dword), ("used", dword), ("free", dword)]

            size = AclSize()
            if (
                not _bind(
                    self.advapi,
                    "GetSecurityDescriptorControl",
                    [pointer, pointer, pointer],
                    boolean,
                )(descriptor, ctypes.byref(control), ctypes.byref(revision))
                or not _bind(
                    self.advapi,
                    "GetAclInformation",
                    [pointer, pointer, dword, dword],
                    boolean,
                )(dacl, ctypes.byref(size), ctypes.sizeof(size), 2)
                or size.count > 64
            ):
                raise _NativeError("R1_ACL_SHAPE_REJECTED")
            aces = []
            for index in range(size.count):
                raw = pointer()
                if (
                    not _bind(
                        self.advapi, "GetAce", [pointer, dword, pointer], boolean
                    )(dacl, index, ctypes.byref(raw))
                    or not raw.value
                ):
                    raise _NativeError("R1_ACE_REJECTED")
                header = ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte * 4)).contents
                if header[0] not in (0, 1) or (header[2] | header[3] << 8) < 12:
                    raise _NativeError("R1_ACE_SHAPE_REJECTED")
                mask = ctypes.cast(raw.value + 4, ctypes.POINTER(dword)).contents.value
                aces.append(
                    (
                        _sid(self.advapi, self.kernel, pointer(raw.value + 8)),
                        mask,
                        header[0],
                        header[1],
                    )
                )
            return contract.SecurityEvidence(
                contract.ObjectFacts(
                    path,
                    "directory" if info.attributes & 0x10 else "file",
                    (info.volume, (info.index_high << 32) | info.index_low),
                    _sid(self.advapi, self.kernel, owner),
                    bool(control.value & 0x1000),
                    tuple(aces),
                    filesystem.value,
                    _bind(self.kernel, "GetDriveTypeW", [ctypes.c_wchar_p], dword)(
                        contract.VOLUME_PATH
                    )
                    == 3,
                    bool(flags.value & 8),
                    bool(info.attributes & 0x400),
                    info.links,
                    (info.size_high << 32) | info.size_low,
                ),
                digest,
            )
        finally:
            if descriptor.value:
                if _bind(self.kernel, "LocalFree", [pointer], pointer)(descriptor):
                    raise _NativeError("R1_DESCRIPTOR_CLOSE_REJECTED")

    def snapshot(self) -> tuple[contract.SecurityEvidence, ...]:
        rows = []
        for path in contract.OBSERVED_PATHS:
            directory = path != contract.RUNTIME_PATHS[1]
            first = self._evidence(path, directory=directory)
            if self._evidence(path, directory=directory) != first:
                raise _NativeError("R1_SECURITY_OBSERVATION_DRIFT")
            rows.append(first)
        return tuple(rows)

    def close(self) -> None:
        failed = False
        for handle in reversed(tuple(self.handles.values())):
            try:
                if not _bind(
                    self.kernel, "CloseHandle", [ctypes.c_void_p], ctypes.c_int32
                )(handle):
                    failed = True
            except BaseException:
                failed = True
        self.handles.clear()
        if failed:
            raise _NativeError("R1_HANDLE_CLOSE_REJECTED")


def _observe() -> tuple[contract.SecurityEvidence, ...]:
    session = _Session()
    try:
        return session.snapshot()
    finally:
        session.close()


class _PinnedTargets:
    def __init__(self) -> None:
        self._session = None
        self._next = 0
        self._used = False
        self._source = None
        self._plan = None
        self.last_status = None

    def __enter__(self) -> _PinnedTargets:
        if self._used:
            raise _NativeError("R1_SESSION_CONSUMED")
        self._used = True
        contract.require_administrator()
        self._source = contract.admit_source()
        self._session = _Session(mutable=True)
        try:
            # snapshot opens and pins both targets before any ACL mutation.
            before = self.snapshot()
            if contract.classify_baseline(before) != "FROZEN_DRIFT":
                raise _NativeError("R1_PINNED_BASELINE_REJECTED")
            self._plan = contract.recovery_plan(self._source, before)
            return self
        except BaseException:
            self._session.close()
            self._session = None
            raise

    def snapshot(self) -> tuple[contract.SecurityEvidence, ...]:
        if self._session is None:
            raise _NativeError("R1_SESSION_CLOSED")
        return self._session.snapshot()

    def apply_next(self) -> int:
        if (
            self._session is None
            or self._plan is None
            or self._next >= 2
            or os.environ.get(contract.AUTH_ENV) != contract.AUTH_VALUE
            or os.environ.get(contract.PLAN_ENV)
            != hashlib.sha256(contract.canonical(self._plan)).hexdigest()
            or contract.admit_source() != self._source
            or contract.observe_attempt(self._plan) != "CONSUMED"
        ):
            raise _NativeError("R1_NATIVE_AUTHORITY_REJECTED")
        before = self.snapshot()
        contract.validate_scope(before)
        for index, row in enumerate(before[1:3]):
            expected = (
                contract.POST_ACES[index]
                if index < self._next
                else contract.PRE_ACES[index]
            )
            if row.facts.aces != expected or (
                index >= self._next
                and row.descriptor_sha256 != contract.PRE_HASHES[index]
            ):
                raise _NativeError("R1_NATIVE_FENCE_DRIFT")
        if contract.recovery_plan(self._source, before) != self._plan:
            raise _NativeError("R1_NATIVE_NON_TARGET_DRIFT")
        self.last_status = None
        index = self._next
        self._next += (
            1  # Burn before entering the native primitive, even on interrupts.
        )
        session = self._session
        pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
        descriptor, dacl = pointer(), pointer()
        present, defaulted = boolean(), boolean()
        # Source-owned tuples only. Every target ACE has zero inheritance flags.
        sddl = "D:P" + "".join(
            f"(A;;0x{mask:x};;;{sid})" for sid, mask, _, _ in contract.POST_ACES[index]
        )
        try:
            if (
                not _bind(
                    session.advapi,
                    "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                    [ctypes.c_wchar_p, dword, pointer, pointer],
                    boolean,
                )(sddl, 1, ctypes.byref(descriptor), None)
                or not descriptor.value
            ):
                raise _NativeError("R1_EXACT_DESCRIPTOR_REJECTED")
            if (
                not _bind(
                    session.advapi,
                    "GetSecurityDescriptorDacl",
                    [pointer, pointer, pointer, pointer],
                    boolean,
                )(
                    descriptor,
                    ctypes.byref(present),
                    ctypes.byref(dacl),
                    ctypes.byref(defaulted),
                )
                or not present.value
                or not dacl.value
            ):
                raise _NativeError("R1_EXACT_DACL_REJECTED")
            # SE_FILE_OBJECT; DACL | PROTECTED_DACL only, owner/group/SACL NULL.
            status = _bind(
                session.advapi,
                "SetSecurityInfo",
                [pointer, dword, dword, pointer, pointer, pointer, pointer],
                dword,
            )(
                session.handles[contract.TARGET_PATHS[index]],
                1,
                0x80000004,
                None,
                None,
                dacl,
                None,
            )
            self.last_status = status
            if type(status) is not int or not 0 <= status <= 0xFFFFFFFF:
                self._next = 2
                raise _NativeError("R1_DWORD_REJECTED")
            if status != 0:
                self._next = 2
            return status
        except BaseException:
            self._next = 2
            raise
        finally:
            if descriptor.value:
                if _bind(session.kernel, "LocalFree", [pointer], pointer)(descriptor):
                    self._next = 2
                    raise _NativeError("R1_DESCRIPTOR_CLOSE_REJECTED")

    def __exit__(self, *_exc) -> None:
        if self._session is not None:
            session, self._session = self._session, None
            session.close()
