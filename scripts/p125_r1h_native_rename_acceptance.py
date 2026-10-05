"""Inert, disposable-only P125-R1H-A transport diagnosis; no production imports."""

from __future__ import annotations

import argparse
import ctypes
import json
import ntpath
import os
import re
import secrets
import stat
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

_SCHEMA = "p125-r1h-native-rename-acceptance/v1"
_EXECUTE = "--execute-disposable-r1h-acceptance"
_TEMP = r"F:\AI\temp"
_PRODUCTION = r"F:\AITradingBot"
_PREFIX = "p125-r1h-native-acceptance-"
_DESTINATION = "destination"
_DELETE = 0x00010000
_READ_CONTROL = 0x00020000
_SYNCHRONIZE = 0x00100000
_SOURCE_ACCESS = _DELETE | _READ_CONTROL | _SYNCHRONIZE | 0x0001 | 0x0080
_PARENT_ACCESS = 0x0001 | 0x0004 | 0x0020 | 0x0080 | _READ_CONTROL | _SYNCHRONIZE
_NOFOLLOW_DIRECTORY = 0x00200000 | 0x02000000
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_POINTER_MAX = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1


class _Blocked(Exception):
    """Internal failure; never serialize exception material."""


class _Case(StrEnum):
    WIN32_FROZEN_CONTROL = "WIN32_FROZEN_CONTROL"
    WIN32_EXACT_LENGTH = "WIN32_EXACT_LENGTH"
    NT_NATIVE_ANCHORED = "NT_NATIVE_ANCHORED"


class _Api(StrEnum):
    WIN32 = "SetFileInformationByHandle"
    NT = "NtSetInformationFile"


class _Status(StrEnum):
    PASS = "PASS"
    NATIVE_FAILURE = "NATIVE_FAILURE"
    BLOCKED = "BLOCKED"
    PROOF_FAILURE = "PROOF_FAILURE"


# Deliberately identical to the frozen production BYTE[1] representation.
class _FileRenameInfo(ctypes.Structure):
    _fields_ = [
        ("replace_if_exists", ctypes.c_ubyte),
        ("root_directory", ctypes.c_void_p),
        ("file_name_length", ctypes.c_uint32),
        ("file_name", ctypes.c_ubyte * 1),
    ]


class _RenameFlags(ctypes.Union):
    _fields_ = [("replace_if_exists", ctypes.c_ubyte), ("flags", ctypes.c_uint32)]


class _FileRenameInformation(ctypes.Structure):
    _anonymous_ = ("choice",)
    _fields_ = [
        ("choice", _RenameFlags),
        ("root_directory", ctypes.c_void_p),
        ("file_name_length", ctypes.c_uint32),
        ("file_name", ctypes.c_uint16 * 1),
    ]


class _IoStatusUnion(ctypes.Union):
    _fields_ = [("status", ctypes.c_int32), ("pointer", ctypes.c_void_p)]


class _IoStatusBlock(ctypes.Structure):
    _anonymous_ = ("choice",)
    _fields_ = [("choice", _IoStatusUnion), ("information", ctypes.c_size_t)]


class _ByHandleInfo(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint32)
        for name in (
            "attributes",
            "creation_low",
            "creation_high",
            "access_low",
            "access_high",
            "write_low",
            "write_high",
            "volume_serial",
            "size_high",
            "size_low",
            "links",
            "file_index_high",
            "file_index_low",
        )
    ]


def _require_layout() -> None:
    width = ctypes.sizeof(ctypes.c_void_p)
    if width not in (4, 8):
        raise _Blocked
    root, length, name, size = (8, 16, 20, 24) if width == 8 else (4, 8, 12, 16)
    for layout in (_FileRenameInfo, _FileRenameInformation):
        if (
            layout.replace_if_exists.offset != 0
            or layout.root_directory.offset != root
            or layout.file_name_length.offset != length
            or layout.file_name.offset != name
            or ctypes.sizeof(layout) != size
            or ctypes.alignment(layout) != width
        ):
            raise _Blocked
    if (
        ctypes.sizeof(_IoStatusUnion) != width
        or _IoStatusBlock.status.offset != 0
        or _IoStatusBlock.information.offset != width
        or ctypes.sizeof(_IoStatusBlock) != 2 * width
        or ctypes.alignment(_IoStatusBlock) != width
        or ctypes.sizeof(_ByHandleInfo) != 52
    ):
        raise _Blocked


def _u32(value: int) -> int:
    if type(value) is not int or not -0x80000000 <= value <= 0xFFFFFFFF:
        raise _Blocked
    return value & 0xFFFFFFFF


def _require_disposable_path(path: str) -> str:
    """Reject production explicitly, then admit only the fixed tiny namespace."""
    if type(path) is not str:
        raise _Blocked
    normalized = ntpath.normcase(ntpath.normpath(path))
    production = ntpath.normcase(_PRODUCTION)
    if normalized == production or normalized.startswith(production + "\\"):
        raise _Blocked
    if ntpath.normpath(path) != path:
        raise _Blocked
    match = re.fullmatch(re.escape(_TEMP + "\\" + _PREFIX) + r"[0-9a-f]{32}(.*)", path)
    if match is None:
        raise _Blocked
    suffix = match.group(1)
    allowed = {""}
    for case in _Case:
        parent = "\\" + case.value.lower()
        allowed.update((parent, parent + "\\source", parent + "\\" + _DESTINATION))
    if suffix not in allowed:
        raise _Blocked
    return path[: len(path) - len(suffix)] if suffix else path


def _stat_identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


class _DisposableSpace:
    """Own exactly one exclusive root; remove only known, empty owned directories."""

    def __init__(self) -> None:
        self.root = _TEMP + "\\" + _PREFIX + secrets.token_hex(16)
        _require_disposable_path(self.root)
        self._owned: dict[str, tuple[int, int]] = {}
        self._sources: dict[_Case, tuple[int, int]] = {}
        self._created = False
        self._made: set[str] = set()

    def paths(self, case: _Case) -> tuple[str, str, str]:
        parent = self.root + "\\" + case.value.lower()
        return parent, parent + "\\source", parent + "\\" + _DESTINATION

    def guard(self, path: str, *, missing_leaf: bool = False) -> os.stat_result | None:
        if _require_disposable_path(path) != self.root:
            raise _Blocked
        # Check every existing ancestor, including the fixed temp ancestry.
        parts = [path]
        while ntpath.dirname(parts[-1]) != parts[-1]:
            parts.append(ntpath.dirname(parts[-1]))
        result = None
        for candidate in reversed(parts):
            try:
                result = os.lstat(candidate)
            except FileNotFoundError:
                if candidate == path and missing_leaf:
                    return None
                raise _Blocked from None
            if (
                not stat.S_ISDIR(result.st_mode)
                or stat.S_ISLNK(result.st_mode)
                or getattr(result, "st_file_attributes", 0) & 0x400
                or ntpath.normcase(str(Path(candidate).resolve(strict=True)))
                != ntpath.normcase(candidate)
                or (
                    candidate in self._owned
                    and _stat_identity(result) != self._owned[candidate]
                )
            ):
                raise _Blocked
        return result

    def _mkdir(self, path: str) -> os.stat_result:
        if self.guard(path, missing_leaf=True) is not None:
            raise _Blocked
        os.mkdir(path)  # Exclusive creation, never parents=True or exist_ok=True.
        self._made.add(path)
        info = self.guard(path)
        if info is None or not info.st_ino:
            raise _Blocked
        self._owned[path] = _stat_identity(info)
        return info

    def create(self) -> None:
        self._mkdir(self.root)
        self._created = True

    def prepare(self, case: _Case) -> None:
        if not self._created:
            raise _Blocked
        parent, source, destination = self.paths(case)
        self._mkdir(parent)
        self._sources[case] = _stat_identity(self._mkdir(source))
        if self.guard(destination, missing_leaf=True) is not None:
            raise _Blocked

    def cleanup(self) -> bool:
        if not self._created:
            return not self._made
        exact = True
        # Only fixed empty directories are eligible for removal.
        for case in _Case:
            parent, source, destination = self.paths(case)
            try:
                if self.guard(parent, missing_leaf=True) is None:
                    continue
            except Exception:
                exact = False
                continue
            for path in (source, destination, parent):
                try:
                    info = self.guard(path, missing_leaf=True)
                    if info is None:
                        continue
                    expected = (
                        self._sources.get(case)
                        if path in (source, destination)
                        else self._owned.get(parent)
                    )
                    if expected is None or _stat_identity(info) != expected:
                        raise _Blocked
                    os.rmdir(
                        path
                    )  # Empty directories only; unexpected contents survive.
                except Exception:
                    exact = False
        try:
            self.guard(self.root)
            os.rmdir(self.root)
        except Exception:
            exact = False
        return exact


@dataclass(frozen=True)
class _Object:
    final_path: str
    volume: int
    file_id: int
    attributes: int
    links: int

    def at(self, path: str) -> _Object:
        return _Object(path, self.volume, self.file_id, self.attributes, self.links)


@dataclass
class _Request:
    buffer: object
    size: int
    name_length: int
    io: _IoStatusBlock


def _buffer_size(case: _Case) -> int:
    name_length = len(_DESTINATION.encode("utf-16-le"))
    if case is _Case.WIN32_FROZEN_CONTROL:
        return ctypes.sizeof(_FileRenameInfo) + name_length + 2
    if case is _Case.WIN32_EXACT_LENGTH:
        return _FileRenameInfo.file_name.offset + name_length
    # Documented native allocation: sizeof(struct) plus name bytes.
    return ctypes.sizeof(_FileRenameInformation) + name_length


def _request(case: _Case, parent_handle: int) -> _Request:
    _require_layout()
    if type(parent_handle) is not int or parent_handle in (0, _INVALID_HANDLE):
        raise _Blocked
    encoded = _DESTINATION.encode("utf-16-le")
    layout = (
        _FileRenameInformation if case is _Case.NT_NATIVE_ANCHORED else _FileRenameInfo
    )
    size = _buffer_size(case)
    buffer = ctypes.create_string_buffer(size)
    info = layout.from_buffer(buffer)
    info.replace_if_exists = 0
    info.root_directory = parent_handle
    info.file_name_length = len(encoded)
    ctypes.memmove(
        ctypes.addressof(buffer) + layout.file_name.offset, encoded, len(encoded)
    )
    io = _IoStatusBlock()
    io.status = -1
    io.information = _POINTER_MAX
    return _Request(buffer, size, len(encoded), io)


@dataclass(frozen=True)
class _Call:
    win32_bool: bool | None = None
    win32_error: int | None = None
    ntstatus: int | None = None
    io_status: int | None = None
    io_information: int | None = None

    def exact_success(self, case: _Case, size: int) -> bool:
        if case is _Case.NT_NATIVE_ANCHORED:
            return (
                self.ntstatus == 0
                and self.io_status == 0
                and type(self.io_information) is int
                and 0 <= self.io_information <= size
            )
        return self.win32_bool is True and self.win32_error is None


class _WindowsNative:
    def __init__(self, space: _DisposableSpace) -> None:
        if os.name != "nt":
            raise _Blocked
        _require_layout()
        self.space = space
        kernel = ctypes.WinDLL(r"C:\Windows\System32\kernel32.dll", use_last_error=True)
        native = ctypes.WinDLL(r"C:\Windows\System32\ntdll.dll")
        handle = ctypes.c_void_p
        u32 = ctypes.c_uint32
        pointer = ctypes.c_void_p
        self._create = self._bind(
            kernel,
            "CreateFileW",
            [ctypes.c_wchar_p, u32, u32, pointer, u32, u32, handle],
            handle,
        )
        self._close = self._bind(kernel, "CloseHandle", [handle], ctypes.c_int32)
        self._final = self._bind(
            kernel,
            "GetFinalPathNameByHandleW",
            [handle, ctypes.c_wchar_p, u32, u32],
            u32,
        )
        self._info = self._bind(
            kernel,
            "GetFileInformationByHandle",
            [handle, ctypes.POINTER(_ByHandleInfo)],
            ctypes.c_int32,
        )
        self._attributes = self._bind(
            kernel, "GetFileAttributesW", [ctypes.c_wchar_p], u32
        )
        self._set = self._bind(
            kernel,
            "SetFileInformationByHandle",
            [handle, ctypes.c_int32, pointer, u32],
            ctypes.c_int32,
        )
        self._nt_set = self._bind(
            native,
            "NtSetInformationFile",
            [handle, ctypes.POINTER(_IoStatusBlock), pointer, u32, ctypes.c_int32],
            ctypes.c_int32,
        )
        # Retain supplied output storage through closes, including unexpected PENDING.
        self._requests: list[_Request] = []

    @staticmethod
    def _bind(library: object, name: str, args: list[object], result: object):
        function = getattr(library, name)
        function.argtypes = args
        function.restype = result
        return function

    def open(self, path: str, *, parent: bool = False, probe: bool = False) -> int:
        self.space.guard(path)
        access = 0x0080 if probe else (_PARENT_ACCESS if parent else _SOURCE_ACCESS)
        # Frozen handles share READ only. A fresh read-attributes probe shares all
        # access already granted to the pinned DELETE handle.
        handle = self._create(
            path, access, 7 if probe else 1, None, 3, _NOFOLLOW_DIRECTORY, None
        )
        if handle in (None, 0, _INVALID_HANDLE):
            raise _Blocked
        return int(handle)

    def close(self, handle: int) -> bool:
        return bool(self._close(handle))

    def inspect(self, handle: int) -> _Object:
        final = ctypes.create_unicode_buffer(32768)
        length = self._final(handle, final, len(final), 0)
        if not length or length >= len(final) or not final.value.startswith("\\\\?\\"):
            raise _Blocked
        path = final.value[4:]
        self.space.guard(path)
        info = _ByHandleInfo()
        if not self._info(handle, ctypes.byref(info)):
            raise _Blocked
        identity = (info.file_index_high << 32) | info.file_index_low
        if (
            not identity
            or info.links != 1
            or not info.attributes & 0x10
            or info.attributes & 0x400
        ):
            raise _Blocked
        return _Object(path, info.volume_serial, identity, info.attributes, info.links)

    def present(self, path: str) -> bool:
        self.space.guard(path, missing_leaf=True)
        attributes = self._attributes(path)
        if attributes != 0xFFFFFFFF:
            if attributes & 0x400 or not attributes & 0x10:
                raise _Blocked
            return True
        error = ctypes.get_last_error()
        if error not in (2, 3):
            raise _Blocked
        return False

    def rename(self, case: _Case, source: int, request: _Request) -> _Call:
        self._requests.append(request)
        if case is _Case.NT_NATIVE_ANCHORED:
            result = self._nt_set(
                source,
                ctypes.byref(request.io),
                ctypes.byref(request.buffer),
                request.size,
                10,
            )
            return _Call(
                ntstatus=_u32(result),
                io_status=_u32(request.io.status),
                io_information=int(request.io.information),
            )
        ctypes.set_last_error(0)
        result = self._set(source, 3, ctypes.byref(request.buffer), request.size)
        if not result:
            error = ctypes.get_last_error()  # Must precede every other native call.
            return _Call(win32_bool=False, win32_error=_u32(error))
        return _Call(win32_bool=True)


@dataclass(frozen=True)
class _Evidence:
    case: _Case
    api: _Api
    passed_buffer_size: int
    FileNameLength: int
    RootDirectory_non_null: bool = False
    win32_bool: bool | None = None
    win32_error: int | None = None
    ntstatus: int | None = None
    io_status: int | None = None
    io_information: int | None = None
    source_present_after: bool | None = None
    destination_present_after: bool | None = None
    same_object_after: bool = False
    parent_stable: bool = False
    close_exact: bool = False
    status: _Status = _Status.BLOCKED


def _run_case(
    case: _Case, space: _DisposableSpace, native: _WindowsNative
) -> _Evidence:
    parent_path, source_path, destination_path = space.paths(case)
    request = _request(case, 1)  # Size evidence also available on pre-call failure.
    parent = source = probe = None
    call = _Call()
    source_present = destination_present = None
    same = stable = opened = absent = reported_success = complete = False
    close_exact = True
    called = False
    try:
        space.prepare(case)
        parent = native.open(parent_path, parent=True)
        source = native.open(source_path)
        before_parent = native.inspect(parent)
        before_source = native.inspect(source)
        if (
            before_parent.final_path != parent_path
            or before_source.final_path != source_path
            or before_source.volume != before_parent.volume
        ):
            raise _Blocked
        opened = True
        absent = native.present(destination_path) is False
        if (
            not absent
            or native.inspect(parent) != before_parent
            or native.inspect(source) != before_source
        ):
            raise _Blocked
        request = _request(case, parent)
        called = True
        call = native.rename(case, source, request)
        reported_success = call.exact_success(case, request.size)
        # Observe failures too; no native result substitutes for filesystem proof.
        source_present = native.present(source_path)
        destination_present = native.present(destination_path)
        pinned_source = native.inspect(source)
        stable = native.inspect(parent) == before_parent
        if destination_present:
            probe = native.open(destination_path, probe=True)
            fresh_destination = native.inspect(probe)
            same = (
                pinned_source == before_source.at(destination_path)
                and fresh_destination == pinned_source
            )
        complete = True
    except Exception:
        complete = False
    finally:
        for handle in (probe, source, parent):
            if handle is not None:
                try:
                    if native.close(handle) is not True:
                        close_exact = False
                except Exception:
                    close_exact = False
    close_exact = close_exact and opened
    passed = (
        opened
        and absent
        and called
        and reported_success
        and complete
        and source_present is False
        and destination_present is True
        and same
        and stable
        and close_exact
    )
    status = (
        _Status.PASS
        if passed
        else (
            _Status.NATIVE_FAILURE
            if called and not reported_success
            else _Status.PROOF_FAILURE
            if called
            else _Status.BLOCKED
        )
    )
    return _Evidence(
        case,
        _Api.NT if case is _Case.NT_NATIVE_ANCHORED else _Api.WIN32,
        request.size,
        request.name_length,
        called and parent not in (None, 0, _INVALID_HANDLE),
        call.win32_bool,
        call.win32_error,
        call.ntstatus,
        call.io_status,
        call.io_information,
        source_present,
        destination_present,
        same,
        stable,
        close_exact,
        status,
    )


@dataclass(frozen=True)
class _Transcript:
    cases: tuple[_Evidence, ...]
    cleanup: str
    status: str
    schema: str = _SCHEMA

    def canonical_json(self) -> str:
        return json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False
        )


def _execute() -> _Transcript:
    space: _DisposableSpace | None = None
    records: list[_Evidence] = []
    try:
        space = _DisposableSpace()
        native = _WindowsNative(space)
        space.create()
        for case in _Case:
            records.append(_run_case(case, space, native))
    except Exception:
        # Preserve any frozen records and fill missing cases with bounded unknowns.
        for case in tuple(_Case)[len(records) :]:
            records.append(
                _Evidence(
                    case,
                    _Api.NT if case is _Case.NT_NATIVE_ANCHORED else _Api.WIN32,
                    _buffer_size(case),
                    len(_DESTINATION.encode("utf-16-le")),
                )
            )
    # Immutable case records are frozen before cleanup starts.
    evidence = tuple(records)
    try:
        cleanup = "PASS" if space is None or space.cleanup() else "FAILURE"
    except Exception:
        cleanup = "FAILURE"
    status = (
        "COMPLETE"
        if all(item.RootDirectory_non_null for item in evidence)
        else "BLOCKED"
    )
    return _Transcript(evidence, cleanup, status)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Rejected caller arguments can themselves contain paths or secrets.
        self.exit(2, "invalid_arguments\n")


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(_EXECUTE, action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_disposable_r1h_acceptance:
        return 0
    transcript = _execute()
    print(transcript.canonical_json())
    return 0 if transcript.status == "COMPLETE" and transcript.cleanup == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
