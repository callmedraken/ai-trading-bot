"""D1S4 create-new immutable bytes in the single derived final release tree.

Inert at import. There is one bounded materialization entry point and no caller
selected destination. All handles close before independent image observation.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import PureWindowsPath

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import MAX_FILE_BYTES, VerifiedRelease
from trading_bot.supervised_release.installation_contract import IMAGE_ACES, ObjectFacts
from trading_bot.supervised_release.native_read import (
    NativeObservationError,
    WindowsReadSession,
    bind,
    close_native_handle,
    windows_libraries,
)
from trading_bot.supervised_release.observer import (
    check_object,
    observe_parent,
    replay_inputs,
)


@contextmanager
def image_security_attributes() -> Iterator[ctypes.Structure]:
    """Apply exact protected immutable-image owner/DACL at object creation."""
    kernel, advapi = windows_libraries()
    descriptor = ctypes.c_void_p()
    sddl = (
        "O:"
        + IMAGE_ACES[0][0]
        + "D:P"
        + "".join(f"(A;;0x{mask:x};;;{sid})" for sid, mask, _, _ in IMAGE_ACES)
    )
    if (
        not bind(
            advapi,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p],
            ctypes.c_int32,
        )(sddl, 1, ctypes.byref(descriptor), None)
        or not descriptor.value
    ):
        raise NativeObservationError("direct creation security rejected")
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


class _DirectSession(WindowsReadSession):
    """Private capability: derived inventory only, no path-taking public writes."""

    def __init__(self, release: VerifiedRelease, binding: RuntimeBinding) -> None:
        super().__init__(replay_inputs(release, binding))
        self.release = release
        self.directories = tuple(
            sorted(
                {
                    parent.as_posix()
                    for item in release.bundle.files
                    for parent in PureWindowsPath(item.relative_path).parents
                    if str(parent) != "."
                },
                key=lambda name: (name.count("/"), name),
            )
        )
        self.created = False

    def _pin_parent(self, path: str) -> None:
        parent = str(PureWindowsPath(path).parent)
        check_object(self.object(parent, directory=True), parent, directory=True)

    def _create_directory(self, name: str | None) -> None:
        if name is None:
            if self.created:
                raise NativeObservationError("direct root already consumed")
            path = self.paths.final
            self.created = True
        else:
            if not self.created or name not in self.directories:
                raise NativeObservationError("derived child required")
            path = self.paths.child(self.paths.final, name)
        self._pin_parent(path)
        with image_security_attributes() as attributes:
            if not bind(
                self.kernel,
                "CreateDirectoryW",
                [ctypes.c_wchar_p, ctypes.c_void_p],
                ctypes.c_int32,
            )(path, ctypes.byref(attributes)):
                raise NativeObservationError("direct directory create failed")
        check_object(self.object(path, directory=True), path, directory=True)

    def _write_inventory_file(self, ordinal: int) -> None:
        if (
            type(ordinal) is not int
            or not 0 <= ordinal < len(self.release.bundle.files)
            or not self.created
        ):
            raise NativeObservationError("exact inventory ordinal required")
        item = self.release.bundle.files[ordinal]
        path = self.paths.child(self.paths.final, item.relative_path)
        self._pin_parent(path)
        data = item.data
        if type(data) is not bytes or len(data) > MAX_FILE_BYTES:
            raise NativeObservationError("bounded direct bytes required")
        handle = None
        invalid = (None, 0, ctypes.c_void_p(-1).value)
        try:
            with image_security_attributes() as attributes:
                # GENERIC_WRITE; zero sharing; CREATE_NEW; no-follow/write-through.
                handle = bind(
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
                )(path, 0x40000000, 0, ctypes.byref(attributes), 1, 0x80200080, None)
            if handle in invalid:
                raise NativeObservationError("direct file create failed")
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
                raise NativeObservationError("direct bounded write failed")
            if not bind(
                self.kernel, "FlushFileBuffers", [ctypes.c_void_p], ctypes.c_int32
            )(handle):
                raise NativeObservationError("direct file flush failed")
        finally:
            if handle not in invalid:
                close_native_handle(self.kernel, handle)

    def materialize(self) -> None:
        self._create_directory(None)
        for name in self.directories:
            self._create_directory(name)
        for ordinal in range(len(self.release.bundle.files)):
            self._write_inventory_file(ordinal)

    def close(self) -> None:
        failed = False
        for handle in reversed(tuple(self.handles.values())):
            try:
                close_native_handle(self.kernel, handle)
            except (Exception, KeyboardInterrupt, SystemExit):
                failed = True
        self.handles.clear()
        if failed:
            raise NativeObservationError("direct materialization close ambiguous")


def materialize_release(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    expected_parent: ObjectFacts,
    expected_python: ObjectFacts,
) -> bool:
    """Derive every destination; create exactly once and close every handle."""
    from trading_bot.supervised_release.successor_direct_installation import (
        observe_python,
    )

    windows_libraries()
    administrator_sid()
    session = _DirectSession(release, binding)
    try:
        parent = observe_parent(session)
        python = observe_python(session, parent.identity[0])
        if (
            parent != expected_parent
            or python != expected_python
            or session.object(session.paths.final, directory=True) is not None
        ):
            raise NativeObservationError("direct creation admission rejected")
        session.materialize()
    finally:
        session.close()
    return True
