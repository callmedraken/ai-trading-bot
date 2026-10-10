"""Narrow Win32 staging writes and one same-parent no-replace publication.

Inert at import. No alternate production destination or execute CLI exists.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterator
from contextlib import contextmanager

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.supervised_release.bundle import MAX_FILE_BYTES
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    IMAGE_ACES,
    ReleasePaths,
)
from trading_bot.supervised_release.model import RELEASES_BASE
from trading_bot.supervised_release.native_read import (
    NativeObservationError,
    WindowsObserver,
    WindowsReadSession,
    bind,
    close_native_handle,
    windows_libraries,
)
from trading_bot.supervised_release.observer import check_object


@contextmanager
def image_security_attributes() -> Iterator[ctypes.Structure]:
    """Exact protected owner/DACL supplied AT CREATE, never inherited writable."""
    kernel, advapi = windows_libraries()
    descriptor = ctypes.c_void_p()
    sddl = (
        "O:"
        + IMAGE_ACES[0][0]
        + "D:P"
        + "".join(f"(A;;0x{mask:x};;;{sid})" for sid, mask, _, _ in IMAGE_ACES)
    )
    convert = bind(
        advapi,
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p],
        ctypes.c_int32,
    )
    if not convert(sddl, 1, ctypes.byref(descriptor), None) or not descriptor.value:
        raise NativeObservationError("creation security descriptor rejected")
    try:

        class Attributes(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_uint32),
                ("descriptor", ctypes.c_void_p),
                ("inherit_handle", ctypes.c_int32),
            ]

        yield Attributes(ctypes.sizeof(Attributes), descriptor, False)
    finally:
        bind(kernel, "LocalFree", [ctypes.c_void_p], ctypes.c_void_p)(descriptor)


class WindowsWriteSession(WindowsReadSession):
    def directory_access(self, path: str) -> int:
        if path == RELEASES_BASE:
            return 0x12008D  # add subdirectory for handle-relative publication
        if path == self.paths.staging and getattr(self, "publishing", False):
            return 0x130089  # DELETE only on our staging object for publication
        return super().directory_access(path)

    def admit_staging(self, path: str, *, file: bool = False) -> None:
        self.paths.admit(path)
        if not path.startswith(self.paths.staging + "\\") and (
            file or path != self.paths.staging
        ):
            raise NativeObservationError("only staging mutation allowed")

    def pin_creation_parent(self, path: str) -> None:
        from pathlib import PureWindowsPath

        parent = str(PureWindowsPath(path).parent)
        check_object(self.object(parent, directory=True), parent, directory=True)

    def create_directory(self, path: str) -> None:
        self.admit_staging(path)
        self.pin_creation_parent(path)
        with image_security_attributes() as attributes:
            if not bind(
                self.kernel,
                "CreateDirectoryW",
                [ctypes.c_wchar_p, ctypes.c_void_p],
                ctypes.c_int32,
            )(path, ctypes.byref(attributes)):
                raise NativeObservationError("staging directory create failed")
        check_object(self.object(path, directory=True), path, directory=True)

    def write_file(self, path: str, data: bytes) -> None:
        self.admit_staging(path, file=True)
        self.pin_creation_parent(path)
        if type(data) is not bytes or len(data) > MAX_FILE_BYTES:
            raise NativeObservationError("bounded write required")
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
        with image_security_attributes() as attributes:
            # CREATE_NEW, no sharing, no-follow, write-through; never overwrite.
            handle = create(
                path, 0x40000000, 0, ctypes.byref(attributes), 1, 0x80200080, None
            )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise NativeObservationError("staging file create failed")
        try:
            buffer = ctypes.create_string_buffer(data)
            written = ctypes.c_uint32()
            if not bind(
                self.kernel,
                "WriteFile",
                [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                ],
                ctypes.c_int32,
            )(
                handle, buffer, len(data), ctypes.byref(written), None
            ) or written.value != len(data):
                raise NativeObservationError("staging bounded write failed")
            if not bind(
                self.kernel, "FlushFileBuffers", [ctypes.c_void_p], ctypes.c_int32
            )(handle):
                raise NativeObservationError("staging flush failed")
        finally:
            close_native_handle(self.kernel, handle)

    def seal_staging(self) -> None:
        """Release materialization handles, preserving every created object."""
        failed = False
        for path in reversed(tuple(self.handles)):
            if path == self.paths.staging or path.startswith(self.paths.staging + "\\"):
                handle = self.handles.pop(path)
                try:
                    close_native_handle(self.kernel, handle)
                except NativeObservationError:
                    failed = True
        if failed:
            raise NativeObservationError("staging materialization close failed")

    def publish(self, staging_identity: tuple[int, int]) -> bool:
        """One FileRenameInfo request, ReplaceIfExists FALSE, pinned parent handle.

        This consumes only the exact derived staging name, never another release.
        A failed or ambiguous call is returned once; no retry/rollback is available.
        """
        self.publishing = True
        self.paths.admit(self.paths.final)
        self.paths.admit(self.paths.staging)
        parent = check_object(
            self.object(RELEASES_BASE, directory=True), RELEASES_BASE, directory=True
        )
        staging = check_object(
            self.object(self.paths.staging, directory=True),
            self.paths.staging,
            directory=True,
            volume=parent.identity[0],
        )
        if staging.identity != staging_identity:
            raise NativeObservationError("staging publication identity drift")
        handle = self.handles.pop(self.paths.staging)
        try:

            class Rename(ctypes.Structure):
                _fields_ = [
                    ("replace", ctypes.c_ubyte),
                    ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32),
                    ("name", ctypes.c_uint16 * 1),
                ]

            encoded = self.paths.release_id.encode("utf-16-le")
            size = Rename.name.offset + len(encoded)
            buffer = ctypes.create_string_buffer(size)
            record = ctypes.cast(buffer, ctypes.POINTER(Rename)).contents
            record.replace = 0
            record.root = self.handles[RELEASES_BASE]
            record.length = len(encoded)
            ctypes.memmove(
                ctypes.addressof(buffer) + Rename.name.offset, encoded, len(encoded)
            )
            return bool(
                bind(
                    self.kernel,
                    "SetFileInformationByHandle",
                    [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
                    ctypes.c_int32,
                )(handle, 3, buffer, size)
            )
        finally:
            close_native_handle(self.kernel, handle)


class WindowsInstaller(WindowsObserver):
    def require_administrator_host(self) -> None:
        windows_libraries()
        administrator_sid()

    @contextmanager
    def install_session(self, paths: ReleasePaths) -> Iterator[WindowsWriteSession]:
        session = WindowsWriteSession(paths)
        try:
            for path in ANCESTORS:
                facts = session.object(path, directory=True)
                if facts is None or facts.kind != "directory" or facts.reparse:
                    raise NativeObservationError("fixed ancestor rejected")
            yield session
        finally:
            session.close()
