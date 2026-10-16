"""Inert Win32 read-only observer; held no-delete ancestors and bounded handles.

No subprocess, Python execution, credential, scheduler or mutation capability.
Every native path is admitted lexically before Win32 observes it.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    ObjectFacts,
    ReleasePaths,
)
from trading_bot.supervised_release.model import PRODUCTION_PYTHON


class NativeObservationError(RuntimeError):
    """Sanitized fixed diagnostics only."""


def bind(library: object, name: str, arguments: list, result: object):
    """Typed Win32 binding; exported only for the narrow installation backend."""
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


def windows_libraries() -> tuple[object, object]:
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise NativeObservationError("supported 64-bit Windows host required")
    return (
        ctypes.WinDLL("kernel32", use_last_error=True),
        ctypes.WinDLL("advapi32", use_last_error=True),
    )


def close_native_handle(kernel: object, handle: int) -> None:
    if not bind(kernel, "CloseHandle", [ctypes.c_void_p], ctypes.c_int32)(handle):
        raise NativeObservationError("native close failed")


def sid_text(advapi: object, kernel: object, sid: object) -> str:
    text = ctypes.c_wchar_p()
    if (
        not bind(
            advapi,
            "ConvertSidToStringSidW",
            [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)],
            ctypes.c_int32,
        )(sid, ctypes.byref(text))
        or not text.value
    ):
        raise NativeObservationError("SID observation failed")
    try:
        if len(text.value) > 184:
            raise NativeObservationError("SID budget exceeded")
        return text.value
    finally:
        bind(kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)(text)


class WindowsReadSession:
    """One observation scope; facts always reconstructed from locked handles."""

    def __init__(self, paths: ReleasePaths) -> None:
        if type(paths) is not ReleasePaths:
            raise NativeObservationError("fixed paths required")
        self.paths = paths
        self.kernel, self.advapi = windows_libraries()
        self.handles: dict[str, int] = {}

    def directory_access(self, path: str) -> int:
        return 0x120089  # READ_CONTROL, SYNCHRONIZE, list/read attributes

    def open_object(self, path: str, *, directory: bool) -> int | None:
        self.paths.admit(path)
        # Never follow an unobserved ancestor, including runtime/image descendants.
        from pathlib import PureWindowsPath

        parent = str(PureWindowsPath(path).parent)
        if parent != path and parent not in self.handles:
            fact = self.object(parent, directory=True)
            if fact is None or fact.kind != "directory" or fact.reparse:
                raise NativeObservationError("ancestor object rejected")
        if path in self.handles:
            return self.handles[path]
        create = bind(
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
        )
        handle = create(
            path,
            self.directory_access(path) if directory else 0x120089,
            3 if directory else 1,
            None,
            3,
            0x02200000,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            if ctypes.get_last_error() in (2, 3):
                return None
            raise NativeObservationError("object open failed")
        self.handles[path] = handle
        return handle

    def object(self, path: str, *, directory: bool) -> ObjectFacts | None:
        handle = self.open_object(path, directory=directory)
        if handle is None:
            return None
        pointer, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
        final = ctypes.create_unicode_buffer(1024)
        count = bind(
            self.kernel,
            "GetFinalPathNameByHandleW",
            [pointer, ctypes.c_wchar_p, dword, dword],
            dword,
        )(handle, final, len(final), 0)
        if not 0 < count < len(final) or final.value != "\\\\?\\" + path:
            raise NativeObservationError("canonical object path rejected")

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
        filesystem = ctypes.create_unicode_buffer(32)
        serial, flags = dword(), dword()
        if (
            bind(self.kernel, "GetFileType", [pointer], dword)(handle) != 1
            or not bind(
                self.kernel, "GetFileInformationByHandle", [pointer, pointer], boolean
            )(handle, ctypes.byref(info))
            or not bind(
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
            raise NativeObservationError("object volume facts rejected")
        owner, dacl, descriptor = pointer(), pointer(), pointer()
        try:
            if bind(
                self.advapi,
                "GetSecurityInfo",
                [pointer, dword, dword, pointer, pointer, pointer, pointer, pointer],
                dword,
            )(
                handle,
                1,
                5,
                ctypes.byref(owner),
                None,
                ctypes.byref(dacl),
                None,
                ctypes.byref(descriptor),
            ) or not all((owner.value, dacl.value, descriptor.value)):
                raise NativeObservationError("security readback failed")
            control, revision = ctypes.c_uint16(), dword()

            class AclSize(ctypes.Structure):
                _fields_ = [("count", dword), ("used", dword), ("free", dword)]

            size = AclSize()
            if (
                not bind(
                    self.advapi,
                    "GetSecurityDescriptorControl",
                    [pointer, pointer, pointer],
                    boolean,
                )(descriptor, ctypes.byref(control), ctypes.byref(revision))
                or not bind(
                    self.advapi,
                    "GetAclInformation",
                    [pointer, pointer, dword, dword],
                    boolean,
                )(dacl, ctypes.byref(size), ctypes.sizeof(size), 2)
                or size.count > 64
            ):
                raise NativeObservationError("ACL shape rejected")
            aces = []
            for index in range(size.count):
                raw = pointer()
                if (
                    not bind(self.advapi, "GetAce", [pointer, dword, pointer], boolean)(
                        dacl, index, ctypes.byref(raw)
                    )
                    or not raw.value
                ):
                    raise NativeObservationError("ACE readback failed")
                header = ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte * 4)).contents
                if header[0] not in (0, 1) or (header[2] | header[3] << 8) < 12:
                    raise NativeObservationError("ACE shape rejected")
                mask = ctypes.cast(raw.value + 4, ctypes.POINTER(dword)).contents.value
                aces.append(
                    (
                        sid_text(self.advapi, self.kernel, pointer(raw.value + 8)),
                        mask,
                        header[0],
                        header[1],
                    )
                )
            return ObjectFacts(
                path,
                "directory" if info.attributes & 0x10 else "file",
                (info.volume, (info.index_high << 32) | info.index_low),
                sid_text(self.advapi, self.kernel, owner),
                bool(control.value & 0x1000),
                tuple(aces),
                filesystem.value,
                bind(self.kernel, "GetDriveTypeW", [ctypes.c_wchar_p], dword)("F:\\")
                == 3,
                bool(flags.value & 8),
                bool(info.attributes & 0x400),
                info.links,
                (info.size_high << 32) | info.size_low,
            )
        finally:
            if descriptor.value:
                bind(self.kernel, "LocalFree", [pointer], pointer)(descriptor)

    def names(self, path: str) -> tuple[str, ...]:
        self.paths.admit(path)
        handle = self.handles[path]
        buffer = ctypes.create_string_buffer(65536)
        query = bind(
            self.kernel,
            "GetFileInformationByHandleEx",
            [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        names = []
        # Bounded enumeration, not a retry/poll loop. One restart then continuation.
        for page in range(20002):
            if not query(handle, 11 if page == 0 else 10, buffer, len(buffer)):
                if ctypes.get_last_error() == 18:
                    return tuple(names)
                raise NativeObservationError("namespace observation failed")
            raw = buffer.raw
            offset = 0
            while True:
                if offset + 104 > len(raw):
                    raise NativeObservationError("directory record bound rejected")
                next_offset = int.from_bytes(raw[offset : offset + 4], "little")
                length = int.from_bytes(raw[offset + 60 : offset + 64], "little")
                if (
                    length % 2
                    or not 0 < length <= 510
                    or offset + 104 + length > len(raw)
                ):
                    raise NativeObservationError("directory name bound rejected")
                name = raw[offset + 104 : offset + 104 + length].decode("utf-16-le")
                if name not in (".", ".."):
                    names.append(name)
                    if len(names) > 20002:
                        raise NativeObservationError("namespace budget exceeded")
                if next_offset == 0:
                    break
                if next_offset < 104 + length or next_offset % 8:
                    raise NativeObservationError("directory offset rejected")
                offset += next_offset
        raise NativeObservationError("namespace page budget exceeded")

    def read(self, path: str, limit: int) -> bytes:
        self.paths.admit(path)
        handle = self.handles[path]
        before = self.object(path, directory=False)
        if (
            before is None
            or before.kind != "file"
            or before.reparse
            or not 0 <= before.size <= limit
        ):
            raise NativeObservationError("file read budget rejected")
        buffer = ctypes.create_string_buffer(before.size + 1)
        read = ctypes.c_uint32()
        if not bind(
            self.kernel,
            "ReadFile",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ],
            ctypes.c_int32,
        )(handle, buffer, len(buffer), ctypes.byref(read), None):
            raise NativeObservationError("file read failed")
        if read.value != before.size or self.object(path, directory=False) != before:
            raise NativeObservationError("file observation drift")
        return buffer.raw[: read.value]

    def python_version(self) -> str:
        self.paths.admit(PRODUCTION_PYTHON)
        if PRODUCTION_PYTHON not in self.handles:
            raise NativeObservationError("Python handle observation required")
        # Read version resources while the separately hashed binary is locked
        # against write/delete; never execute Python to discover its version.
        version = ctypes.WinDLL("version", use_last_error=True)
        pointer, dword = ctypes.c_void_p, ctypes.c_uint32
        size = bind(
            version, "GetFileVersionInfoSizeW", [ctypes.c_wchar_p, pointer], dword
        )(PRODUCTION_PYTHON, None)
        if not 0 < size <= 65536:
            raise NativeObservationError("Python version budget rejected")
        data = ctypes.create_string_buffer(size)
        if not bind(
            version,
            "GetFileVersionInfoW",
            [ctypes.c_wchar_p, dword, dword, pointer],
            ctypes.c_int32,
        )(PRODUCTION_PYTHON, 0, size, data):
            raise NativeObservationError("Python version observation failed")
        value, length = pointer(), dword()
        if not bind(
            version,
            "VerQueryValueW",
            [pointer, ctypes.c_wchar_p, pointer, pointer],
            ctypes.c_int32,
        )(
            data,
            r"\StringFileInfo\000004b0\ProductVersion",
            ctypes.byref(value),
            ctypes.byref(length),
        ):
            raise NativeObservationError("Python product version rejected")
        if not value.value or not 0 < length.value <= 64:
            raise NativeObservationError("Python version shape rejected")
        return ctypes.wstring_at(value, length.value).rstrip("\0")

    def close(self) -> None:
        failed = False
        for handle in reversed(tuple(self.handles.values())):
            try:
                close_native_handle(self.kernel, handle)
            except NativeObservationError:
                failed = True
        self.handles.clear()
        if failed:
            raise NativeObservationError("observation scope close failed")


class WindowsObserver:
    @contextmanager
    def read_session(self, paths: ReleasePaths) -> Iterator[WindowsReadSession]:
        session = WindowsReadSession(paths)
        try:
            # Ancestors are locked without delete-sharing for the whole scope.
            for path in ANCESTORS:
                facts = session.object(path, directory=True)
                if facts is None or facts.kind != "directory" or facts.reparse:
                    raise NativeObservationError("fixed ancestor rejected")
            yield session
        finally:
            session.close()
