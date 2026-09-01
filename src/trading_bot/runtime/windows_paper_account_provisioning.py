"""Administrator-only, one-way publication of the fixed P3 genesis tree.

This is not an A67 output seam. Ordinary publication never resumes staging;
P3-R1 recovery accepts only the frozen incident. Neither operation cleans up,
repairs, or replaces state. Native production acceptance is a separate gate.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import PureWindowsPath
from uuid import UUID

from trading_bot.runtime.manual_paper_account_authority import (
    MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME,
    parse_manual_paper_account_anchor,
)
from trading_bot.runtime.manual_paper_account_provisioning import (
    ManualPaperAccountProvisioningBundle,
    ManualPaperAccountProvisioningEvidence,
    ManualPaperAccountProvisioningManifest,
    verify_manual_paper_account_provisioning_bundle,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityError,
    require_windows_platform,
)
from trading_bot.runtime.windows_authority_security import (
    CREATE_NEW,
    DELETE,
    FILE_FLAG_BACKUP_SEMANTICS,
    FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    FILE_READ_DATA,
    FILE_SHARE_DELETE,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    FILE_WRITE_DATA,
    OPEN_EXISTING,
    READ_CONTROL,
    AuthorityObjectKind,
    SecurityPolicy,
    WindowsHandle,
    authority_parent_security_policy,
    authority_security_policy,
    build_security_attributes,
    inspect_open_authority_object,
    require_administrator_token,
    require_security_policy,
)
from trading_bot.runtime.windows_authority_validation import (
    require_initialized_supported_authority_evidence,
    validate_installed_authority_complete,
)
from trading_bot.runtime.windows_p3_r1_recovery_authorization import (
    P3R1RecoveryPermit,
    authorize_p3_r1_recovery,
    consume_p3_r1_recovery_permit,
)
from trading_bot.runtime.windows_paper_account_security import (
    PRODUCTION_PAPER_ROOT,
    enumerate_paper_directory,
    paper_account_security_policy,
)

PRODUCTION_PAPER_STAGING_ROOT = PureWindowsPath(
    r"F:\AITradingBot\.Paper.provisioning-v1"
)
_PARENT = PureWindowsPath(r"F:\AITradingBot")
_RUNTIME = _PARENT / "runtime"

# Architecture 94 accepted v2 bundle / Architecture 95 incident evidence. These
# are assertions, never a request to construct or regenerate this account.
_P3_R1_BUNDLE = ManualPaperAccountProvisioningEvidence(
    ManualPaperAccountProvisioningManifest(
        UUID("d1510a4b-6ebf-58ef-92a4-e743ca91151e"),
        "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1",
        "S-1-5-21-1397534616-3988210162-180023805-1009",
        UUID("7b7b83ba-69e2-5ed8-a033-b4306cd1ffc7"),
        "b6172753ee4f30a82265ff38b341c3de42869ba6af7ccb69739234135183026d",
        534,
        "650b977db5ea5f5f1d89e3ed5bf52dfb5b2c5c44c3b34ccceb6d22dd492df871",
        411,
    ),
    "8505eddd07be2f90d1211ee49a9cac4829d0faff9d88d0dc4c609b209a2e8801",
    522,
)
_P3_R1_BOOTSTRAP = "53b8b72ab18b1c477c5eab50857e4dc2d47efc6e74030e380ed6a53387922ae4"
_P3_R1_DATABASE = (
    "6a8fb988d1cb223fbb66b09e8dab1e0de4b6aafd148dfdf01df08029203f4b76",
    331776,
)


class PaperAccountPublicationState(StrEnum):
    NOT_PUBLISHED = "NOT_PUBLISHED"
    STAGING_REQUIRES_MANUAL_RECOVERY = "STAGING_REQUIRES_MANUAL_RECOVERY"
    EXISTING_FINAL = "EXISTING_FINAL"
    EXISTING_FINAL_AND_STAGING = "EXISTING_FINAL_AND_STAGING"
    PUBLICATION_OUTCOME_UNCERTAIN = "PUBLICATION_OUTCOME_UNCERTAIN"
    PUBLISHED_CANDIDATE = "PUBLISHED_CANDIDATE"
    PUBLISHED_VALIDATED = "PUBLISHED_VALIDATED"


class WindowsPaperAccountProvisioningError(WindowsAuthorityError):
    """Only bounded classification/state escape the native boundary."""

    def __init__(self, code: str, state: PaperAccountPublicationState) -> None:
        self.code = code
        self.state = state
        super().__init__(f"{code}:{state.value}")


@dataclass(frozen=True, slots=True)
class WindowsPaperAccountPublicationEvidence:
    bundle: ManualPaperAccountProvisioningEvidence
    state: PaperAccountPublicationState
    final_root: str = str(PRODUCTION_PAPER_ROOT)


@dataclass(frozen=True, slots=True)
class P3R1RecoveryEvidence:
    publication: WindowsPaperAccountPublicationEvidence
    # Root and descendants, in fixed layout order; identities are audit only.
    native_identities: tuple[tuple[str, tuple[object, ...]], ...]
    authority_database_sha256: str
    authority_database_byte_length: int
    first_production_mutation: str = "P3_R1_ROOT_RENAME"


def _layout(root: PureWindowsPath, checkpoint_id: UUID) -> dict[PureWindowsPath, str]:
    directory = root / f"paper-account-genesis-{checkpoint_id}"
    return {
        root: "root",
        directory: "genesis-directory",
        directory / f"paper-account-checkpoint-{checkpoint_id}.json": "genesis-file",
        root / MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME: "anchor",
    }


def require_fixed_paper_provisioning_path(
    path: str | PureWindowsPath,
    genesis_checkpoint_id: UUID,
) -> PureWindowsPath:
    """Exact v1 inventory only, including spelling; never a caller root seam."""
    if type(genesis_checkpoint_id) is not UUID:
        raise ValueError("PROVISIONING_PATH_INVALID")
    raw = str(path)
    allowed = {
        str(item)
        for root in (PRODUCTION_PAPER_ROOT, PRODUCTION_PAPER_STAGING_ROOT)
        for item in _layout(root, genesis_checkpoint_id)
    }
    if raw not in allowed:
        raise ValueError("PROVISIONING_PATH_INVALID")
    return PureWindowsPath(raw)


class _FileIdInfo(ctypes.Structure):
    _fields_ = [("volume", ctypes.c_ulonglong), ("identifier", ctypes.c_ubyte * 16)]


class _FileStandardInfo(ctypes.Structure):
    _fields_ = [
        ("allocation", ctypes.c_longlong),
        ("size", ctypes.c_longlong),
        ("links", wintypes.DWORD),
        ("delete_pending", ctypes.c_ubyte),
        ("directory", ctypes.c_ubyte),
    ]


class _PaperRootRenameInfo(ctypes.Structure):
    # FILE_RENAME_INFO's union is a DWORD on current Windows. Flags=0 means
    # ReplaceIfExists=False, with no POSIX/replace flags enabled.
    _fields_ = [
        ("flags", wintypes.DWORD),
        ("root_directory", wintypes.HANDLE),
        ("name_length", wintypes.DWORD),
        ("name", wintypes.WCHAR * 1),
    ]


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("pid", wintypes.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent_pid", wintypes.DWORD),
        ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("executable", wintypes.WCHAR * 260),
    ]


@dataclass
class _Retained:
    handle: WindowsHandle
    role: str
    directory: bool
    identity: tuple[object, ...]


class _WindowsPublicationSession:
    """Paper-only native mutation boundary, never attached to the P3 reader."""

    def __init__(self, evidence: ManualPaperAccountProvisioningEvidence) -> None:
        require_windows_platform()
        self.evidence = evidence
        self.sid = evidence.manifest.approved_trading_sid
        self.checkpoint_id = evidence.manifest.genesis_checkpoint_id
        self.handles: dict[PureWindowsPath, _Retained] = {}
        self.staging_identities: dict[PureWindowsPath, tuple[object, ...]] = {}
        self.database_handles: dict[PureWindowsPath, _Retained] = {}
        self.published = False
        self.rename_attempted = False
        self.final_appeared = False
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    def __enter__(self) -> _WindowsPublicationSession:
        return self

    def __exit__(self, *args: object) -> None:
        failed = False
        retained_handles = (*self.database_handles.values(), *self.handles.values())
        for retained in reversed(retained_handles):
            try:
                retained.handle.close()
            except Exception:
                failed = True
        self.handles.clear()
        self.database_handles.clear()
        if failed:
            raise ValueError("HANDLE_CLOSE_FAILED")

    def _call(
        self, name: str, result: object, args: list[object], *values: object
    ) -> object:
        function = getattr(self.kernel, name)
        function.restype = result
        function.argtypes = args
        return function(*values)

    def _open(
        self,
        path: PureWindowsPath,
        directory: bool,
        *,
        access: int,
        share: int,
        disposition: int = OPEN_EXISTING,
        attributes: object = None,
    ) -> WindowsHandle:
        handle = self._call(
            "CreateFileW",
            wintypes.HANDLE,
            [
                ctypes.c_wchar_p,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ],
            str(path),
            access,
            share,
            attributes,
            disposition,
            FILE_FLAG_OPEN_REPARSE_POINT
            | (FILE_FLAG_BACKUP_SEMANTICS if directory else 0),
            None,
        )
        if handle in (None, 0, -1, ctypes.c_void_p(-1).value):
            raise ValueError("OBJECT_OPEN_FAILED")
        return WindowsHandle(handle)

    def _facts(self, handle: int, directory: bool) -> tuple[object, ...]:
        if self._call("GetFileType", wintypes.DWORD, [wintypes.HANDLE], handle) != 1:
            raise ValueError("OBJECT_NOT_DISK")
        identity = _FileIdInfo()
        standard = _FileStandardInfo()
        for info_class, info in ((18, identity), (1, standard)):
            if not self._call(
                "GetFileInformationByHandleEx",
                wintypes.BOOL,
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
                handle,
                info_class,
                ctypes.byref(info),
                ctypes.sizeof(info),
            ):
                raise ValueError("OBJECT_IDENTITY_UNAVAILABLE")
        if bool(standard.directory) != directory or standard.delete_pending:
            raise ValueError("OBJECT_TYPE_CHANGED")
        if not directory and standard.links != 1:
            raise ValueError("OBJECT_LINKED")
        return (identity.volume, bytes(identity.identifier)) + (
            () if directory else (standard.size, standard.links)
        )

    def _inspect(self, path: PureWindowsPath, retained: _Retained) -> None:
        inspection = inspect_open_authority_object(
            retained.handle.value,
            path,
            AuthorityObjectKind.DIRECTORY
            if retained.directory
            else AuthorityObjectKind.FILE,
        )
        if retained.role != "volume":
            policy = (
                authority_parent_security_policy()
                if retained.role == "parent"
                else authority_security_policy(retained.role, self.sid)
                if retained.role in {"authority", "database"}
                else paper_account_security_policy(retained.role, self.sid)
            )
            require_security_policy(inspection, policy)
        if self._facts(retained.handle.value, retained.directory) != retained.identity:
            raise ValueError("OBJECT_IDENTITY_CHANGED")

    def _retain(
        self, path: PureWindowsPath, handle: WindowsHandle, role: str, directory: bool
    ) -> None:
        # Record ownership before anything can fail, so every handle is closed.
        retained = _Retained(handle, role, directory, ())
        self.handles[path] = retained
        retained.identity = self._facts(handle.value, directory)
        self._inspect(path, retained)

    def validate_parent(self) -> None:
        for path, role in ((PureWindowsPath("F:/"), "volume"), (_PARENT, "parent")):
            handle = self._open(
                path,
                True,
                access=READ_CONTROL | FILE_READ_ATTRIBUTES,
                share=FILE_SHARE_READ | FILE_SHARE_WRITE,
            )
            self._retain(path, handle, role, True)

    def require_quiescent_runtime(self) -> None:
        """Reject other sealed-runtime Python processes; never terminate them.

        The operator must keep the runtime quiescent for the whole operation.
        These bounded snapshots detect violations, not grant scheduling authority.
        """
        snapshot = self._call(
            "CreateToolhelp32Snapshot",
            wintypes.HANDLE,
            [wintypes.DWORD, wintypes.DWORD],
            2,
            0,
        )
        if snapshot in (None, 0, -1, ctypes.c_void_p(-1).value):
            raise ValueError("RECOVERY_PROCESS_SNAPSHOT_FAILED")
        with WindowsHandle(snapshot) as snapshot_handle:
            entry = _ProcessEntry()
            entry.size = ctypes.sizeof(entry)
            operation = "Process32FirstW"
            count = 0
            while self._call(
                operation,
                wintypes.BOOL,
                [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)],
                snapshot_handle,
                ctypes.byref(entry),
            ):
                count += 1
                if count > 65536:
                    raise ValueError("RECOVERY_PROCESS_LIMIT")
                operation = "Process32NextW"
                if entry.pid == os.getpid() or entry.executable.casefold() not in {
                    "python.exe",
                    "pythonw.exe",
                }:
                    continue
                process = self._call(
                    "OpenProcess",
                    wintypes.HANDLE,
                    [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                    0x1000,
                    False,
                    entry.pid,  # PROCESS_QUERY_LIMITED_INFORMATION
                )
                if not process:
                    raise ValueError("RECOVERY_PROCESS_IDENTITY_UNPROVEN")
                with WindowsHandle(process) as process_handle:
                    buffer = ctypes.create_unicode_buffer(32768)
                    size = wintypes.DWORD(len(buffer))
                    if not self._call(
                        "QueryFullProcessImageNameW",
                        wintypes.BOOL,
                        [
                            wintypes.HANDLE,
                            wintypes.DWORD,
                            ctypes.c_wchar_p,
                            ctypes.POINTER(wintypes.DWORD),
                        ],
                        process_handle,
                        0,
                        buffer,
                        ctypes.byref(size),
                    ):
                        raise ValueError("RECOVERY_PROCESS_IDENTITY_UNPROVEN")
                    if PureWindowsPath(buffer.value).is_relative_to(_RUNTIME):
                        raise ValueError("RECOVERY_RUNTIME_NOT_QUIESCENT")
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES only
                raise ValueError("RECOVERY_PROCESS_ENUMERATION_FAILED")

    def open_recovery_database(self) -> None:
        if self.evidence != _P3_R1_BUNDLE or self.database_handles:
            raise ValueError("RECOVERY_DATABASE_BOUNDARY_INVALID")
        for path, role, directory in (
            (PRODUCTION_AUTHORITY_PATHS.root, "authority", True),
            (PRODUCTION_AUTHORITY_PATHS.database, "database", False),
        ):
            handle = self._open(
                path,
                directory,
                access=READ_CONTROL | FILE_READ_DATA | FILE_READ_ATTRIBUTES,
                share=FILE_SHARE_READ,
            )
            retained = _Retained(handle, role, directory, ())
            self.database_handles[path] = retained
            retained.identity = self._facts(handle.value, directory)
            self._inspect(path, retained)
        self.validate_recovery_database()

    def validate_recovery_database(self) -> None:
        for path, retained in self.database_handles.items():
            self._inspect(path, retained)
        retained = self.database_handles[PRODUCTION_AUTHORITY_PATHS.database]
        payload = self._read(retained, _P3_R1_DATABASE[1])
        if (sha256(payload).hexdigest(), len(payload)) != _P3_R1_DATABASE:
            raise ValueError("RECOVERY_DATABASE_MISMATCH")
        for path, retained in self.database_handles.items():
            self._inspect(path, retained)

    def exists(self, root: PureWindowsPath) -> bool:
        if (
            root not in (PRODUCTION_PAPER_ROOT, PRODUCTION_PAPER_STAGING_ROOT)
            or _PARENT not in self.handles
        ):
            raise ValueError("ROOT_PROBE_INVALID")
        # Only ERROR_FILE_NOT_FOUND proves absence under the retained parent.
        # Access failures, aliases and dangling reparse points cannot mean absent.
        value = self._call(
            "GetFileAttributesW", wintypes.DWORD, [ctypes.c_wchar_p], str(root)
        )
        if value != 0xFFFFFFFF:
            return True
        if ctypes.get_last_error() != 2:
            raise ValueError("ROOT_ABSENCE_UNPROVEN")
        return False

    def create_directory(
        self, path: PureWindowsPath, role: str, policy: SecurityPolicy
    ) -> None:
        self._require_creation(path, role, policy)
        with build_security_attributes(policy) as security:
            if not self._call(
                "CreateDirectoryW",
                wintypes.BOOL,
                [ctypes.c_wchar_p, ctypes.c_void_p],
                str(path),
                ctypes.byref(security.attributes),
            ):
                raise ValueError("DIRECTORY_CREATE_NEW_FAILED")
        handle = self._open(
            path,
            True,
            access=READ_CONTROL
            | FILE_READ_DATA
            | FILE_READ_ATTRIBUTES
            | (DELETE if role == "root" else 0),
            share=FILE_SHARE_READ | (0 if role == "root" else FILE_SHARE_DELETE),
        )
        self._retain(path, handle, role, True)

    def _require_creation(
        self, path: PureWindowsPath, role: str, policy: SecurityPolicy
    ) -> None:
        require_fixed_paper_provisioning_path(path, self.checkpoint_id)
        if (
            self.published
            or _layout(PRODUCTION_PAPER_STAGING_ROOT, self.checkpoint_id).get(path)
            != role
            or path.parent not in self.handles
            or path in self.handles
            or policy != paper_account_security_policy(role, self.sid)
        ):
            raise ValueError("CREATION_BOUNDARY_INVALID")
        self._inspect(path.parent, self.handles[path.parent])

    def create_file(
        self, path: PureWindowsPath, role: str, payload: bytes, policy: SecurityPolicy
    ) -> bytes:
        self._require_creation(path, role, policy)
        if role not in {"genesis-file", "anchor"}:
            raise ValueError("FILE_ROLE_INVALID")
        with build_security_attributes(policy) as security:
            handle = self._open(
                path,
                False,
                access=FILE_READ_DATA
                | FILE_WRITE_DATA
                | FILE_READ_ATTRIBUTES
                | READ_CONTROL,
                share=FILE_SHARE_READ | FILE_SHARE_DELETE,
                disposition=CREATE_NEW,
                attributes=ctypes.byref(security.attributes),
            )
            self._retain(path, handle, role, False)
        written = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(payload)
        if not self._call(
            "WriteFile",
            wintypes.BOOL,
            [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ],
            handle.value,
            buffer,
            len(payload),
            ctypes.byref(written),
            None,
        ) or written.value != len(payload):
            raise ValueError("FILE_WRITE_FAILED")
        if not self._call(
            "FlushFileBuffers", wintypes.BOOL, [wintypes.HANDLE], handle.value
        ):
            raise ValueError("FILE_FLUSH_FAILED")
        retained = self.handles[path]
        before = retained.identity
        retained.identity = self._facts(handle.value, False)
        if retained.identity[:2] != before[:2] or retained.identity[2] != len(payload):
            raise ValueError("WRITTEN_IDENTITY_CHANGED")
        self._inspect(path, retained)
        return self._read(retained, len(payload))

    def _read(self, retained: _Retained, length: int) -> bytes:
        handle = retained.handle.value
        if (
            self._facts(handle, False) != retained.identity
            or retained.identity[2] != length
        ):
            raise ValueError("READ_IDENTITY_CHANGED")
        if not self._call(
            "SetFilePointerEx",
            wintypes.BOOL,
            [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD],
            handle,
            0,
            None,
            0,
        ):
            raise ValueError("FILE_SEEK_FAILED")
        buffer = ctypes.create_string_buffer(length + 1)
        count = wintypes.DWORD()
        if (
            not self._call(
                "ReadFile",
                wintypes.BOOL,
                [
                    wintypes.HANDLE,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                    ctypes.c_void_p,
                ],
                handle,
                buffer,
                length + 1,
                ctypes.byref(count),
                None,
            )
            or count.value != length
            or self._facts(handle, False) != retained.identity
        ):
            raise ValueError("FILE_READ_FAILED")
        return buffer.raw[:length]

    def inventory(self, root: PureWindowsPath) -> None:
        layout = _layout(root, self.checkpoint_id)
        for path, role in layout.items():
            if role in {"root", "genesis-directory"}:
                names = enumerate_paper_directory(str(path), 3)
                expected = {child.name for child in layout if child.parent == path}
                if len(names) != len(expected) or set(names) != expected:
                    raise ValueError("INVENTORY_MISMATCH")

    def revalidate(self) -> None:
        for path, retained in self.handles.items():
            self._inspect(path, retained)

    def open_staging(self) -> None:
        """Open the existing exact tree; never create, repair, or resume writes."""
        for path, role in _layout(
            PRODUCTION_PAPER_STAGING_ROOT, self.checkpoint_id
        ).items():
            self._inspect(path.parent, self.handles[path.parent])
            directory = role in {"root", "genesis-directory"}
            handle = self._open(
                path,
                directory,
                access=READ_CONTROL
                | FILE_READ_DATA
                | FILE_READ_ATTRIBUTES
                | (DELETE if role == "root" else 0),
                share=FILE_SHARE_READ,
            )
            self._retain(path, handle, role, directory)

    def validate_tree(
        self, root: PureWindowsPath, bundle: ManualPaperAccountProvisioningBundle
    ) -> None:
        self.revalidate()
        self.inventory(root)
        payloads = {}
        for path, role in _layout(root, self.checkpoint_id).items():
            retained = self.handles[path]
            self._inspect(path, retained)
            if role in {"anchor", "genesis-file"}:
                expected = (
                    bundle.anchor_bytes if role == "anchor" else bundle.genesis_bytes
                )
                payloads[role] = self._read(retained, len(expected))
                if payloads[role] != expected:
                    raise ValueError("TREE_BYTES_MISMATCH")
        # Verify the bytes read from the objects, not just the input bundle.
        observed = ManualPaperAccountProvisioningBundle(
            payloads["genesis-file"], payloads["anchor"], bundle.manifest_bytes
        )
        if verify_manual_paper_account_provisioning_bundle(observed) != self.evidence:
            raise ValueError("TREE_EVIDENCE_MISMATCH")
        self.revalidate()
        self.inventory(root)

    def prepare_rename(self, bundle: ManualPaperAccountProvisioningBundle) -> None:
        source = PRODUCTION_PAPER_STAGING_ROOT
        self.validate_tree(source, bundle)
        self.staging_identities = {
            path: self.handles[path].identity
            for path in _layout(source, self.checkpoint_id)
        }
        self.revalidate()
        self.inventory(source)
        if self.exists(PRODUCTION_PAPER_ROOT):
            self.final_appeared = True
            raise ValueError("FINAL_APPEARED")
        failed = False
        for path in reversed(tuple(self.staging_identities)):
            if path == source:
                continue
            # Remove before close: an uncertain close must never be retried,
            # including by __exit__. Any failure blocks the root rename.
            retained = self.handles.pop(path)
            try:
                retained.handle.close()
            except Exception:
                failed = True
        if failed:
            raise ValueError("DESCENDANT_CLOSE_FAILED")
        self.require_rename_ready()

    def require_rename_ready(self) -> None:
        source = PRODUCTION_PAPER_STAGING_ROOT
        if (
            self.rename_attempted
            or set(self.staging_identities) != set(_layout(source, self.checkpoint_id))
            or set(self.handles) != {PureWindowsPath("F:/"), _PARENT, source}
            or self.handles[source].identity != self.staging_identities[source]
        ):
            raise ValueError("ROOT_RENAME_NOT_READY")
        self.revalidate()
        self.inventory(source)
        if self.exists(PRODUCTION_PAPER_ROOT):
            self.final_appeared = True
            raise ValueError("FINAL_APPEARED")

    def require_exact_final_root(self) -> None:
        """Check the raw native path, without case folding or normalization."""
        retained = self.handles[PRODUCTION_PAPER_ROOT]
        buffer = ctypes.create_unicode_buffer(32768)
        count = self._call(
            "GetFinalPathNameByHandleW",
            wintypes.DWORD,
            [wintypes.HANDLE, ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD],
            retained.handle.value,
            buffer,
            len(buffer),
            0,
        )
        if not 0 < count < len(buffer) or buffer.value != (
            "\\\\?\\" + str(PRODUCTION_PAPER_ROOT)
        ):
            raise ValueError("RETAINED_ROOT_FINAL_PATH_MISMATCH")
        self._inspect(PRODUCTION_PAPER_ROOT, retained)

    def rename_root(self) -> None:
        source = PRODUCTION_PAPER_STAGING_ROOT
        retained = self.handles[source]
        self.require_rename_ready()
        # A paper-specific retained-root rename. Destination and flags are not
        # caller inputs. C1 rename/path helpers remain untouched.
        name = str(PRODUCTION_PAPER_ROOT).encode("utf-16-le")
        size = max(
            ctypes.sizeof(_PaperRootRenameInfo),
            _PaperRootRenameInfo.name.offset + len(name),
        )
        buffer = ctypes.create_string_buffer(size)
        info = _PaperRootRenameInfo.from_buffer(buffer)
        info.flags = 0
        info.root_directory = None
        info.name_length = len(name)
        ctypes.memmove(
            ctypes.addressof(buffer) + _PaperRootRenameInfo.name.offset, name, len(name)
        )
        # FIRST_PRODUCTION_MUTATION=P3_R1_ROOT_RENAME for recovery. No native
        # operation intervenes between this conservative marker and the call.
        self.rename_attempted = True
        if not self._call(
            "SetFileInformationByHandle",
            wintypes.BOOL,
            [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
            retained.handle.value,
            3,
            buffer,
            size,
        ):
            raise ValueError("ROOT_RENAME_FAILED")
        self.published = True
        self.handles = {
            PRODUCTION_PAPER_ROOT / path.relative_to(source)
            if path.is_relative_to(source)
            else path: item
            for path, item in self.handles.items()
        }
        self.require_exact_final_root()
        if self.exists(source) or not self.exists(PRODUCTION_PAPER_ROOT):
            raise ValueError("PUBLICATION_NAMESPACE_MISMATCH")

    def rename_recovery_root(self, permit: P3R1RecoveryPermit) -> None:
        """Consume signed recovery provenance at the native mutation seam."""

        consume_p3_r1_recovery_permit(permit)
        self.rename_root()

    def validate_final(self, bundle: ManualPaperAccountProvisioningBundle) -> None:
        layout = _layout(PRODUCTION_PAPER_ROOT, self.checkpoint_id)
        for path, role in layout.items():
            if role == "root":
                continue
            directory = role == "genesis-directory"
            handle = self._open(
                path,
                directory,
                access=READ_CONTROL | FILE_READ_DATA | FILE_READ_ATTRIBUTES,
                share=FILE_SHARE_READ,
            )
            self._retain(path, handle, role, directory)
            original_path = PRODUCTION_PAPER_STAGING_ROOT / path.relative_to(
                PRODUCTION_PAPER_ROOT
            )
            if self.handles[path].identity != self.staging_identities[original_path]:
                raise ValueError("DESCENDANT_IDENTITY_CHANGED")
        self.validate_tree(PRODUCTION_PAPER_ROOT, bundle)
        self.require_exact_final_root()
        if self.exists(PRODUCTION_PAPER_STAGING_ROOT) or not self.exists(
            PRODUCTION_PAPER_ROOT
        ):
            raise ValueError("PUBLICATION_NAMESPACE_MISMATCH")


def _publish(
    bundle: ManualPaperAccountProvisioningBundle,
    expected: ManualPaperAccountProvisioningEvidence,
    session_factory: Callable[
        [ManualPaperAccountProvisioningEvidence], _WindowsPublicationSession
    ],
) -> WindowsPaperAccountPublicationEvidence:
    state = PaperAccountPublicationState.NOT_PUBLISHED
    session = None
    try:
        evidence = verify_manual_paper_account_provisioning_bundle(bundle)
        if type(expected) is not ManualPaperAccountProvisioningEvidence:
            raise ValueError("EXPECTED_EVIDENCE_REQUIRED")
        expected.__post_init__()
        if evidence != expected:
            raise ValueError("EXPECTED_EVIDENCE_MISMATCH")
        session = session_factory(evidence)
        with session:
            session.validate_parent()
            final_exists = session.exists(PRODUCTION_PAPER_ROOT)
            staging_exists = session.exists(PRODUCTION_PAPER_STAGING_ROOT)
            if final_exists or staging_exists:
                state = (
                    PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING
                    if final_exists and staging_exists
                    else PaperAccountPublicationState.EXISTING_FINAL
                    if final_exists
                    else PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY
                )
                raise ValueError("EXISTING_STATE")
            layout = _layout(
                PRODUCTION_PAPER_STAGING_ROOT, evidence.manifest.genesis_checkpoint_id
            )
            state = PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY
            for path, role in layout.items():
                policy = paper_account_security_policy(
                    role, evidence.manifest.approved_trading_sid
                )
                if role in {"root", "genesis-directory"}:
                    session.create_directory(path, role, policy)
                else:
                    payload = (
                        bundle.genesis_bytes
                        if role == "genesis-file"
                        else bundle.anchor_bytes
                    )
                    reread = session.create_file(path, role, payload, policy)
                    if reread != payload:
                        raise ValueError("STAGING_BYTES_MISMATCH")
                    if role == "genesis-file":
                        verification = verify_genesis_paper_account_checkpoint(reread)
                        verification.__post_init__()
                        if (
                            verification.status
                            is not PaperAccountCheckpointVerificationStatus.PASS
                        ):
                            raise ValueError("STAGING_GENESIS_INVALID")
                    elif parse_manual_paper_account_anchor(
                        reread
                    ) != parse_manual_paper_account_anchor(bundle.anchor_bytes):
                        raise ValueError("STAGING_ANCHOR_INVALID")
            session.inventory(PRODUCTION_PAPER_STAGING_ROOT)
            session.revalidate()
            if session.exists(PRODUCTION_PAPER_ROOT):
                state = PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING
                raise ValueError("FINAL_APPEARED")
            session.prepare_rename(bundle)
            session.rename_root()
            state = PaperAccountPublicationState.PUBLISHED_CANDIDATE
            session.validate_final(bundle)
        return WindowsPaperAccountPublicationEvidence(
            evidence, PaperAccountPublicationState.PUBLISHED_VALIDATED
        )
    except Exception:
        if session is not None and session.published:
            state = PaperAccountPublicationState.PUBLISHED_CANDIDATE
        elif session is not None and session.rename_attempted:
            state = PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN
        elif session is not None and session.final_appeared:
            state = PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING
        raise WindowsPaperAccountProvisioningError(
            "PUBLICATION_BLOCKED", state
        ) from None


def publish_manual_paper_account(
    *,
    bundle: ManualPaperAccountProvisioningBundle,
    expected: ManualPaperAccountProvisioningEvidence,
) -> WindowsPaperAccountPublicationEvidence:
    """Publish only prebuilt, exactly reviewed bytes after Administrator/C1 proof.

    Operator prerequisites: accepted sealed release, exact reviewed deployment
    checkpoint, and runtime quiescence. No scalar builder or root override is
    available here. Acceptance under non-admin Trading remains a separate gate.
    """
    try:
        require_administrator_token()
        if (
            sys.executable != r"F:\AITradingBot\runtime\python.exe"
            or not PureWindowsPath(__file__).is_relative_to(
                PureWindowsPath(r"F:\AITradingBot\runtime")
            )
        ):
            raise ValueError("SEALED_RUNTIME_REQUIRED")
        evidence = verify_manual_paper_account_provisioning_bundle(bundle)
        if (
            type(expected) is not ManualPaperAccountProvisioningEvidence
            or evidence != expected
        ):
            raise ValueError("EXPECTED_EVIDENCE_MISMATCH")
        validation = validate_installed_authority_complete()
        require_initialized_supported_authority_evidence(validation)
        bootstrap = validation.bootstrap_verification.bootstrap
        if (
            bootstrap.machine_authority_id != evidence.manifest.machine_authority_id
            or bootstrap.approved_account_sid != evidence.manifest.approved_trading_sid
        ):
            raise ValueError("INSTALLED_AUTHORITY_MISMATCH")
    except Exception:
        raise WindowsPaperAccountProvisioningError(
            "PRECONDITION_BLOCKED", PaperAccountPublicationState.NOT_PUBLISHED
        ) from None
    return _publish(bundle, expected, _WindowsPublicationSession)


def recover_p3_r1_retained_staging(
    *,
    bundle: ManualPaperAccountProvisioningBundle,
    authorization_bytes: bytes,
    signature: bytes,
) -> P3R1RecoveryEvidence:
    """Recover only the frozen Architecture-95 incident, once, without repair.

    Authorization/signature inputs are transport bytes only. No root, account,
    operator, release, replacement, cleanup, resume, or creation option exists.
    Failures retain the candidate state and must never be blindly rerun.
    """
    state = PaperAccountPublicationState.NOT_PUBLISHED
    session = None
    try:
        permit = authorize_p3_r1_recovery(authorization_bytes, signature)
        evidence = verify_manual_paper_account_provisioning_bundle(bundle)
        if evidence != _P3_R1_BUNDLE:
            raise ValueError("RECOVERY_FROZEN_BUNDLE_MISMATCH")
        session = _WindowsPublicationSession(evidence)
        with session:
            session.require_quiescent_runtime()
            session.validate_parent()
            final = session.exists(PRODUCTION_PAPER_ROOT)
            staging = session.exists(PRODUCTION_PAPER_STAGING_ROOT)
            if final or not staging:
                state = (
                    PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING
                    if final and staging
                    else PaperAccountPublicationState.EXISTING_FINAL
                    if final
                    else PaperAccountPublicationState.NOT_PUBLISHED
                )
                raise ValueError("RECOVERY_STATE_NOT_ADMITTED")
            state = PaperAccountPublicationState.STAGING_REQUIRES_MANUAL_RECOVERY
            session.open_recovery_database()
            session.open_staging()
            session.prepare_rename(bundle)
            session.validate_recovery_database()
            session.require_quiescent_runtime()
            session.rename_recovery_root(permit)
            state = PaperAccountPublicationState.PUBLISHED_CANDIDATE
            session.validate_final(bundle)
            session.validate_recovery_database()
        return P3R1RecoveryEvidence(
            WindowsPaperAccountPublicationEvidence(
                evidence, PaperAccountPublicationState.PUBLISHED_VALIDATED
            ),
            tuple(
                (str(path.relative_to(PRODUCTION_PAPER_STAGING_ROOT)), identity)
                for path, identity in session.staging_identities.items()
            ),
            *_P3_R1_DATABASE,
        )
    except Exception:
        if session is not None and session.published:
            state = PaperAccountPublicationState.PUBLISHED_CANDIDATE
        elif session is not None and session.rename_attempted:
            state = PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN
        elif session is not None and session.final_appeared:
            state = PaperAccountPublicationState.EXISTING_FINAL_AND_STAGING
        raise WindowsPaperAccountProvisioningError(
            "P3_R1_RECOVERY_BLOCKED", state
        ) from None
