"""Disabled fixed-path Win32 PD1C effects; never constructed by disposable tests."""

from __future__ import annotations

import ctypes
from pathlib import Path

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_publication import (
    paper_publication_layout,
    publication_entry_path,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
)
from trading_bot.runtime.windows_authority_security import (
    FILE_ALL_ACCESS,
    AuthorityObjectKind,
    SecurityAce,
    SecurityPolicy,
    WindowsHandle,
    apply_security_policy,
    build_security_attributes,
)


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


class WindowsPaperPublicationApi(security.WindowsPaperReadNativeApi):
    """No alternate roots, delete API, replacement flag, or production test switch.

    The publisher holds the trusted parent chain throughout. New objects start
    with explicit administrator/SYSTEM security; the algorithm then applies and
    verifies the final PD1B role policies before publication.
    """

    def __init__(self, genesis_id: str) -> None:
        if security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not True:
            raise PersonalDesktopPaperAccountError(
                "PD1C native production effects are disabled"
            )
        super().__init__()
        self._paths = {
            publication_entry_path(Path(root), entry): entry.spec
            for root in (
                security.PERSONAL_DESKTOP_PAPER_V2_ROOT,
                security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
            )
            for entry in paper_publication_layout(genesis_id)
        }
        self._created: dict[int, str] = {}
        self._attempted = False
        self._renamed = False

    def _require_gate(self) -> None:
        if security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is not True:
            raise PersonalDesktopPaperAccountError(
                "PD1C native production effects are disabled"
            )

    def _spec(self, path: str):
        if type(path) is not str or path not in self._paths:
            raise AuthorityPathError(
                "PD1C native path is outside the fixed publication layout"
            )
        return self._paths[path]

    def occupied(self, path: str) -> bool:
        if path not in {
            security.PERSONAL_DESKTOP_PAPER_V2_ROOT,
            security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT,
        }:
            raise AuthorityPathError(
                "PD1C occupancy only inspects fixed publication names"
            )
        attributes = _bind(
            self._kernel, "GetFileAttributesW", [ctypes.c_wchar_p], ctypes.c_uint32
        )
        if attributes(path) != 0xFFFFFFFF:
            return True  # Includes reparse points and wrong object kinds.
        if ctypes.get_last_error() == 2:  # Only FILE_NOT_FOUND proves child absence.
            return False
        raise AuthorityObjectError("PD1C fixed child absence is unproven")

    def _open(
        self,
        path: str,
        kind: AuthorityObjectKind,
        *,
        create_new: bool = False,
        writable: bool = False,
    ) -> WindowsHandle:
        if self._spec(path).kind is not kind:
            raise AuthorityObjectError("PD1C native object kind does not match layout")
        create = _bind(
            self._kernel,
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

        def invoke(attributes: object) -> WindowsHandle:
            value = create(
                path,
                0xC00E0080
                if writable
                else 0x20081,  # read/write, READ_CONTROL/DAC/OWNER
                3 if writable or kind is AuthorityObjectKind.DIRECTORY else 1,
                attributes,
                1 if create_new else 3,
                0x02200000,
                None,
            )
            if value in (None, 0, -1, ctypes.c_void_p(-1).value):
                raise AuthorityObjectError("PD1C create-new/open-existing failed")
            return WindowsHandle(value)

        if create_new:
            with build_security_attributes(self._initial_policy()) as attributes:
                return invoke(ctypes.byref(attributes.attributes))
        return invoke(None)

    def open(self, path: str, kind: AuthorityObjectKind) -> WindowsHandle:
        return self._open(path, kind)

    def _initial_policy(self) -> SecurityPolicy:
        return SecurityPolicy(
            security.ADMINISTRATORS_SID,
            (
                SecurityAce(security.ADMINISTRATORS_SID, FILE_ALL_ACCESS),
                SecurityAce(security.SYSTEM_SID, FILE_ALL_ACCESS),
            ),
        )

    def _require_create(self, path: str) -> None:
        self._require_gate()
        self._spec(path)
        staging = security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
        if self._renamed or not (path == staging or path.startswith(staging + "\\")):
            raise AuthorityPathError("PD1C creation is confined to unpublished staging")
        if path == staging:
            if self._attempted:
                raise AuthorityObjectError(
                    "PD1C staging creation was already attempted"
                )
            self._attempted = True
        elif not self._attempted:
            raise AuthorityObjectError("PD1C staging must be created first")

    def create_directory(self, path: str) -> WindowsHandle:
        self._require_create(path)
        if self._spec(path).kind is not AuthorityObjectKind.DIRECTORY:
            raise AuthorityObjectError("PD1C directory does not match role")
        create = _bind(
            self._kernel,
            "CreateDirectoryW",
            [ctypes.c_wchar_p, ctypes.c_void_p],
            ctypes.c_int32,
        )
        with build_security_attributes(self._initial_policy()) as attributes:
            if not create(path, ctypes.byref(attributes.attributes)):
                raise AuthorityObjectError("PD1C staging directory create-new failed")
        handle = self._open(path, AuthorityObjectKind.DIRECTORY, writable=True)
        self._created[handle.value] = path
        return handle

    def create_file(self, path: str) -> WindowsHandle:
        self._require_create(path)
        handle = self._open(
            path, AuthorityObjectKind.FILE, create_new=True, writable=True
        )
        self._created[handle.value] = path
        return handle

    def _require_write_handle(self, handle: WindowsHandle) -> str:
        self._require_gate()
        if handle.value not in self._created or self._renamed:
            raise AuthorityObjectError(
                "PD1C mutation requires a held staging create handle"
            )
        return self._created[handle.value]

    def write(self, handle: WindowsHandle, payload: bytes) -> None:
        path = self._require_write_handle(handle)
        spec = self._spec(path)
        if (
            spec.kind is not AuthorityObjectKind.FILE
            or type(payload) is not bytes
            or not 0 < len(payload) <= spec.maximum_bytes
        ):
            raise AuthorityObjectError("PD1C write does not match bounded file role")
        write = _bind(
            self._kernel,
            "WriteFile",
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_void_p,
            ],
            ctypes.c_int32,
        )
        buffer = ctypes.create_string_buffer(payload)
        offset = 0
        while offset < len(payload):
            count = ctypes.c_uint32()
            if (
                not write(
                    handle.value,
                    ctypes.byref(buffer, offset),
                    len(payload) - offset,
                    ctypes.byref(count),
                    None,
                )
                or not 0 < count.value <= len(payload) - offset
            ):
                raise AuthorityObjectError("PD1C exact file write failed")
            offset += count.value

    def flush(self, handle: WindowsHandle) -> None:
        self._require_write_handle(handle)
        flush = _bind(
            self._kernel, "FlushFileBuffers", [ctypes.c_void_p], ctypes.c_int32
        )
        if not flush(handle.value):
            raise AuthorityObjectError("PD1C file flush failed")

    def apply_policy(self, handle: WindowsHandle, policy: SecurityPolicy) -> None:
        self._require_write_handle(handle)
        apply_security_policy(handle.value, policy)

    def close(self, handle: WindowsHandle) -> None:
        if not handle.value:
            return
        close = _bind(self._kernel, "CloseHandle", [ctypes.c_void_p], ctypes.c_int32)
        if not close(handle.value):
            # Retain the registration on failure. Neither this call nor the
            # publication algorithm retries a close with an uncertain result.
            raise AuthorityObjectError("PD1C publication handle close failed")
        self._created.pop(handle.value, None)
        handle.value = 0

    def rename_no_clobber(self, staging: str, final: str) -> None:
        self._require_gate()
        if (
            staging != security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
            or final != security.PERSONAL_DESKTOP_PAPER_V2_ROOT
            or self._created
            or not self._attempted
            or self._renamed
        ):
            raise AuthorityPathError(
                "PD1C rename requires closed handles and exact fixed names"
            )
        self._renamed = True  # Native failure/response loss never allows retry.
        move = _bind(
            self._kernel,
            "MoveFileExW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32],
            ctypes.c_int32,
        )
        # WRITE_THROUGH only: no REPLACE_EXISTING, COPY_ALLOWED or delayed move.
        if not move(staging, final, 0x8):
            raise AuthorityObjectError("PD1C same-parent no-clobber rename failed")
