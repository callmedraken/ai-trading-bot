"""Architecture-128 R4B Windows staging/read/rename adapters.

Importing this module performs no host observation or mutation.
Constructors bind native libraries only. Production mutation remains separately
authorization-gated and requires a later Architecture-128 operator to invoke
these fixed adapters.
"""

from __future__ import annotations

import ctypes
import ntpath
from ctypes import wintypes
from dataclasses import replace

from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_protected_replacement_windows as legacy_windows
from scripts.d10_protected_deployment import (
    DeploymentBlocked,
    NativeObject,
    require_native_object,
    require_parent_native_object,
)
from scripts.d10_protected_deployment_windows import WindowsDeploymentBackend

_TRUST_NAMES = (
    "deployment.attestation.json",
    "deployment.attestation.sig",
    "executable-manifest.json",
)
_TRUST_INSTALLING = tuple(
    r4.STAGING_PATH + "\\" + name + ".installing" for name in _TRUST_NAMES
)
_TRUST_FINAL = tuple(r4.STAGING_PATH + "\\" + name for name in _TRUST_NAMES)
_GUARD_INSTALLING = r4.STAGING_PATH + r"\launch-guard.py.installing"
_GUARD_FINAL = r4.STAGING_PATH + r"\launch-guard.py"
_SOURCE_INSTALLING = r4.STAGING_PATH + r"\source.installing"
_SOURCE_FINAL = r4.STAGING_PATH + r"\source"

_ALLOWED_FIXED_FILES = {
    "launch-guard.py",
    "deployment.attestation.json",
    "deployment.attestation.sig",
    "executable-manifest.json",
    "activation.lease.json",
    "activation.lease.json.installing",
    "activation.lease.json.tmp",
    "no-pycache",
    "launch-guard.py.installing",
    "source.installing",
    "deployment.attestation.json.installing",
    "deployment.attestation.sig.installing",
    "executable-manifest.json.installing",
}


class WindowsArch128StagingBackend(WindowsDeploymentBackend):
    """Create-only writer confined to the exact Architecture-128 staging root."""

    _creation_root = r4.STAGING_PATH

    def _allowed_directory_create(self, path: str) -> bool:
        return path == r4.NEW_EVIDENCE_ROOT or super()._allowed_directory_create(path)

    def _allowed_file_create(self, path: str) -> bool:
        return path in _TRUST_INSTALLING or super()._allowed_file_create(path)

    @staticmethod
    def _allowed_publication_pair(
        installing_path: str,
        final_path: str,
    ) -> bool:
        allowed = {
            (_GUARD_INSTALLING, _GUARD_FINAL),
            (_SOURCE_INSTALLING, _SOURCE_FINAL),
            *zip(_TRUST_INSTALLING, _TRUST_FINAL, strict=True),
        }
        return (installing_path, final_path) in allowed

    def publish_create_only(self, installing_path: str, final_path: str) -> None:
        if not self._allowed_publication_pair(installing_path, final_path):
            raise DeploymentBlocked("arch128_publication_path_unreviewed")
        move = self._bind(
            self._kernel,
            "MoveFileW",
            [ctypes.c_wchar_p, ctypes.c_wchar_p],
            wintypes.BOOL,
        )
        if not move(installing_path, final_path):
            raise DeploymentBlocked("arch128_create_only_publication_failed")

    def _allowed_object_path(self, path: str, *, directory: bool) -> bool:
        if type(path) is not str or ntpath.normpath(path) != path:
            return False
        if directory and path == r4.PARENT_PATH:
            return True
        if directory and path in (r4.STAGING_PATH, r4.NEW_EVIDENCE_ROOT):
            return True

        final_source = _SOURCE_FINAL
        installing_source = _SOURCE_INSTALLING

        if directory and path == final_source:
            return True
        if path.startswith(final_source + "\\"):
            mapped = installing_source + path[len(final_source) :]
            allowed = self._source_directories if directory else self._source_files
            return mapped in allowed

        if directory:
            return False

        return path in {
            _GUARD_FINAL,
            *_TRUST_FINAL,
        }


class WindowsArch128ReadOnlyReader(legacy_windows._WindowsReplacementReader):
    """No-follow reader limited to exact Architecture-128 replacement paths."""

    @staticmethod
    def _allowed(path: str, *, directory: bool | None) -> bool:
        if type(path) is not str or ntpath.normpath(path) != path:
            return False
        if path == r4.PARENT_PATH:
            return directory is True
        if path == r4.HISTORICAL_S5R8_RETIRED_PATH:
            return directory in (True, None)

        for root in (r4.CANONICAL_PATH, r4.STAGING_PATH, r4.RETIRED_PATH):
            if path == root:
                return directory in (True, None)
            if not path.startswith(root + "\\"):
                continue

            relative = path[len(root) + 1 :]
            if relative in ("source", "evidence"):
                return directory is True

            if relative.startswith("source\\"):
                source_relative = relative[len("source\\") :]
                parts = source_relative.split("\\")
                return (
                    all(
                        part
                        and part not in (".", "..")
                        and not part.endswith((" ", "."))
                        for part in parts
                    )
                    and parts[0] in ("src", "scripts")
                    and not any(":" in part or "/" in part for part in parts)
                    and directory in (True, False)
                )

            return relative in _ALLOWED_FIXED_FILES and directory in (False, None)

        return False

    def _open_rename_source(self, path: str) -> int:
        if path not in (r4.CANONICAL_PATH, r4.STAGING_PATH):
            raise legacy_windows.AdmissionBlocked("arch128_rename_source_unreviewed")

        create = self._bind(
            self._kernel,
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
            legacy_windows._DELETE
            | legacy_windows._READ_CONTROL
            | legacy_windows._SYNCHRONIZE
            | legacy_windows._FILE_LIST_DIRECTORY
            | legacy_windows._FILE_READ_ATTRIBUTES,
            legacy_windows._FILE_SHARE_READ,
            None,
            legacy_windows._OPEN_EXISTING,
            legacy_windows._FILE_FLAG_OPEN_REPARSE_POINT
            | legacy_windows._FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise legacy_windows.AdmissionBlocked(
                "arch128_rename_source_open_unavailable"
            )
        return int(handle)


class _FileRenameInformation(ctypes.Structure):
    _fields_ = [
        ("replace_if_exists", ctypes.c_ubyte),
        ("root_directory", ctypes.c_void_p),
        ("file_name_length", ctypes.c_uint32),
        ("file_name", ctypes.c_uint16 * 1),
    ]


class _IoStatusUnion(ctypes.Union):
    _fields_ = [("status", ctypes.c_int32), ("pointer", ctypes.c_void_p)]


class _IoStatusBlock(ctypes.Structure):
    _anonymous_ = ("result",)
    _fields_ = [("result", _IoStatusUnion), ("information", ctypes.c_size_t)]


def _fixed_rename_info(step: r4.RenameStep, parent_handle: int):
    _, destination = r4.fixed_rename_paths(step)
    leaf = destination.rsplit("\\", 1)[-1]
    if (
        type(parent_handle) is not int
        or parent_handle in (0, ctypes.c_void_p(-1).value)
        or not leaf
        or any(character in leaf for character in "\\/\x00:")
    ):
        raise legacy_windows.AdmissionBlocked("arch128_rename_destination_invalid")

    encoded = leaf.encode("utf-16-le")
    offset = _FileRenameInformation.file_name.offset
    buffer = ctypes.create_string_buffer(offset + len(encoded))
    info = _FileRenameInformation.from_buffer(buffer)
    info.replace_if_exists = 0
    info.root_directory = parent_handle
    info.file_name_length = len(encoded)
    ctypes.memmove(ctypes.addressof(buffer) + offset, encoded, len(encoded))
    return buffer


def _set_fixed_rename(
    native: WindowsArch128ReadOnlyReader,
    step: r4.RenameStep,
    source_handle: int,
    parent_handle: int,
) -> tuple[int, _IoStatusBlock, int]:
    info = _fixed_rename_info(step, parent_handle)
    set_information = native._bind(
        native._ntdll,
        "NtSetInformationFile",
        [
            wintypes.HANDLE,
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
        ],
        ctypes.c_int32,
    )
    io_status = _IoStatusBlock()
    io_status.status = -1
    io_status.information = ctypes.c_size_t(-1).value
    submitted_size = len(info)
    status = set_information(
        source_handle,
        ctypes.byref(io_status),
        ctypes.byref(info),
        submitted_size,
        legacy_windows._FILE_RENAME_INFORMATION_CLASS,
    )
    return status & 0xFFFFFFFF, io_status, submitted_size


def rename_fixed_step(
    native: WindowsArch128ReadOnlyReader,
    step: r4.RenameStep,
    expected_source: NativeObject,
    expected_parent: NativeObject,
) -> r4.MutationOutcome:
    """Perform one exact handle-pinned no-replace rename; uncertainty is terminal."""

    source_path, destination_path = r4.fixed_rename_paths(step)
    parent_handle: int | None = None
    source_handle: int | None = None
    native_succeeded = False
    cleanup_ambiguous = False
    outcome = r4.MutationOutcome.INDETERMINATE

    try:
        if (
            type(native) is not WindowsArch128ReadOnlyReader
            or type(expected_source) is not NativeObject
            or type(expected_parent) is not NativeObject
        ):
            raise legacy_windows.AdmissionBlocked(
                "arch128_rename_admitted_identity_missing"
            )

        parent_handle = native._open_rename_parent()
        source_handle = native._open_rename_source(source_path)
        parent_before = native._inspect(parent_handle, r4.PARENT_PATH)
        source_before = native._inspect(source_handle, source_path)

        require_parent_native_object(parent_before)
        require_native_object(source_before, source_path, directory=True)

        if (
            parent_before != expected_parent
            or source_before != expected_source
            or source_before.volume_serial != parent_before.volume_serial
            or source_before.volume_root != parent_before.volume_root
        ):
            raise legacy_windows.AdmissionBlocked(
                "arch128_rename_pinned_identity_drift"
            )

        if native.absent(destination_path) is not True:
            raise legacy_windows.AdmissionBlocked("arch128_rename_destination_present")

        if (
            native._inspect(parent_handle, r4.PARENT_PATH) != parent_before
            or native._inspect(source_handle, source_path) != source_before
        ):
            raise legacy_windows.AdmissionBlocked("arch128_rename_pre_call_drift")

        status, io_status, submitted_size = _set_fixed_rename(
            native,
            step,
            source_handle,
            parent_handle,
        )
        if status != 0:
            return r4.MutationOutcome.INDETERMINATE

        native_succeeded = True
        if io_status.status != 0 or not 0 <= io_status.information <= submitted_size:
            raise legacy_windows.AdmissionBlocked(
                "arch128_rename_completion_unverified"
            )

        expected_after = replace(source_before, final_path=destination_path)
        if (
            native._inspect(source_handle, source_path) != expected_after
            or native._inspect(parent_handle, r4.PARENT_PATH) != parent_before
        ):
            raise legacy_windows.AdmissionBlocked("arch128_rename_post_call_drift")

        outcome = r4.MutationOutcome.SUCCESS
    except Exception:
        outcome = r4.MutationOutcome.INDETERMINATE
    finally:
        for handle in (source_handle, parent_handle):
            if handle is None:
                continue
            try:
                native._close(handle)
            except Exception:
                cleanup_ambiguous = True

    if cleanup_ambiguous or (
        native_succeeded and outcome is not r4.MutationOutcome.SUCCESS
    ):
        return r4.MutationOutcome.INDETERMINATE
    return outcome
