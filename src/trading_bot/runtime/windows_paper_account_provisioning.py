"""Administrator-only, one-way publication of the fixed P3 genesis tree.

This is not an A67 output seam. No cleanup, repair, replacement, or resumption
is provided. Native production acceptance is a separate operator gate.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from uuid import UUID

from trading_bot.runtime.manual_paper_account_authority import (
    MANUAL_PAPER_ACCOUNT_ANCHOR_FILENAME,
    parse_manual_paper_account_anchor,
)
from trading_bot.runtime.manual_paper_account_provisioning import (
    ManualPaperAccountProvisioningBundle,
    ManualPaperAccountProvisioningEvidence,
    verify_manual_paper_account_provisioning_bundle,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.windows_authority import (
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
    build_security_attributes,
    inspect_open_authority_object,
    require_administrator_token,
    require_security_policy,
)
from trading_bot.runtime.windows_authority_validation import (
    require_initialized_supported_authority_evidence,
    validate_installed_authority_complete,
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
        self.published = False
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    def __enter__(self) -> _WindowsPublicationSession:
        return self

    def __exit__(self, *args: object) -> None:
        failed = False
        for retained in reversed(tuple(self.handles.values())):
            try:
                retained.handle.close()
            except Exception:
                failed = True
        self.handles.clear()
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

    def rename_root(self) -> None:
        source = PRODUCTION_PAPER_STAGING_ROOT
        retained = self.handles[source]
        self._inspect(source, retained)
        self._inspect(_PARENT, self.handles[_PARENT])
        self.inventory(source)
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

    def validate_final(self, bundle: ManualPaperAccountProvisioningBundle) -> None:
        self.revalidate()
        layout = _layout(PRODUCTION_PAPER_ROOT, self.checkpoint_id)
        for path, role in layout.items():
            original = self.handles[path]
            # Desired access is read-only. Sharing permits our retained writer;
            # the original handle continues to deny all other writers.
            with self._open(
                path,
                original.directory,
                access=READ_CONTROL | FILE_READ_DATA | FILE_READ_ATTRIBUTES,
                share=FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            ) as handle:
                reopened = _Retained(
                    WindowsHandle(handle, close=False),
                    role,
                    original.directory,
                    original.identity,
                )
                self._inspect(path, reopened)
                if role in {"anchor", "genesis-file"}:
                    expected = (
                        bundle.anchor_bytes
                        if role == "anchor"
                        else bundle.genesis_bytes
                    )
                    if self._read(reopened, len(expected)) != expected:
                        raise ValueError("FINAL_BYTES_MISMATCH")
        self.inventory(PRODUCTION_PAPER_ROOT)
        verify_manual_paper_account_provisioning_bundle(bundle)
        self.revalidate()
        if self.exists(PRODUCTION_PAPER_STAGING_ROOT):
            raise ValueError("STAGING_PRESENT_AFTER_PUBLICATION")


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
            state = PaperAccountPublicationState.PUBLICATION_OUTCOME_UNCERTAIN
            session.rename_root()
            state = PaperAccountPublicationState.PUBLISHED_CANDIDATE
            session.validate_final(bundle)
        return WindowsPaperAccountPublicationEvidence(
            evidence, PaperAccountPublicationState.PUBLISHED_VALIDATED
        )
    except Exception:
        if session is not None and session.published:
            state = PaperAccountPublicationState.PUBLISHED_CANDIDATE
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
