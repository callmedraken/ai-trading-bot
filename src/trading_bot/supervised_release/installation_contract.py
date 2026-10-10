"""Fixed namespace, immutable facts and separated native capabilities for 133-AC."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol

from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)
from trading_bot.supervised_release.model import (
    PRODUCTION_PYTHON,
    RELEASES_BASE,
    release_root,
)

IMAGE_ACES = (
    (ADMINISTRATORS_SID, 0x1F01FF, 0, 0),
    (SYSTEM_SID, 0x1F01FF, 0, 0),
    (TRADING_SID, 0x1200A9, 0, 0),
)
PYTHON_VERSION = "3.14.3"
PYTHON_SHA256 = "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
ANCESTORS = ("F:\\", r"F:\AITradingBot", RELEASES_BASE)
PRESERVED_ROOTS = (
    PureWindowsPath(r"F:\AI\temp\arch133y-rename-qualification"),
    PureWindowsPath(r"F:\AI\temp\arch133z-rename-qualification"),
)


@dataclass(frozen=True, slots=True)
class ReleasePaths:
    release_id: str

    def __post_init__(self) -> None:
        release_root(self.release_id)

    @property
    def final(self) -> str:
        return release_root(self.release_id)

    @property
    def staging(self) -> str:
        return self.final + ".installing"

    def admit(self, path: str) -> str:
        """Lexical rejection precedes all native observations, even on aliases."""
        if type(path) is not str:
            raise ValueError("fixed logical path required")
        windows = PureWindowsPath(path)
        if any(windows == root or root in windows.parents for root in PRESERVED_ROOTS):
            raise ValueError("preserved namespace forbidden")
        if ".." in windows.parts or path != str(windows):
            raise ValueError("canonical path required")
        if path in (*ANCESTORS, r"F:\AITradingBot\runtime", PRODUCTION_PYTHON):
            return path
        for root in (self.final, self.staging):
            if path == root:
                return path
            if path.startswith(root + "\\"):
                name = path[len(root) + 1 :].replace("\\", "/")
                # Public foundation validation rejects ADS, devices, traversal,
                # absolute paths and trailing-dot/space aliases for directories too.
                # A public synthetic source entry validates each lexical component;
                # directory names and manifest.json are not source inventory files.
                from trading_bot.supervised_release.model import ReleaseInventoryEntry

                ReleaseInventoryEntry("src/" + name + "/probe.py", "0" * 64)
                return path
        raise ValueError("outside fixed release namespace")

    def child(self, root: str, name: str) -> str:
        if root not in (self.final, self.staging):
            raise ValueError("exact derived image root required")
        return self.admit(root + "\\" + name.replace("/", "\\"))


@dataclass(frozen=True, slots=True)
class ObjectFacts:
    path: str
    kind: str
    identity: tuple[int, int]
    owner: str
    protected: bool
    aces: tuple[tuple[str, int, int, int], ...]
    filesystem: str = "NTFS"
    local: bool = True
    persistent_acls: bool = True
    reparse: bool = False
    links: int = 1
    size: int = 0


class InstallStatus(StrEnum):
    INSTALLED_VERIFIED = "INSTALLED_VERIFIED"
    ALREADY_INSTALLED_VERIFIED = "ALREADY_INSTALLED_VERIFIED"
    BLOCKED = "BLOCKED"
    INDETERMINATE = "INDETERMINATE"


class InstallDisposition(StrEnum):
    VERIFIED = "VERIFIED"
    NO_INSTALLATION_EFFECT = "NO_INSTALLATION_EFFECT"
    PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY = "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY"


class InstallReason(StrEnum):
    VERIFIED = "VERIFIED"
    INPUT = "INPUT"
    HOST = "HOST"
    PARENT = "PARENT"
    FINAL_CONFLICT = "FINAL_CONFLICT"
    STAGING_EXISTS = "STAGING_EXISTS"
    MATERIALIZATION = "MATERIALIZATION"
    STAGING_VERIFICATION = "STAGING_VERIFICATION"
    PUBLICATION = "PUBLICATION"
    FINAL_VERIFICATION = "FINAL_VERIFICATION"
    SESSION_CLOSE = "SESSION_CLOSE"


@dataclass(frozen=True, slots=True)
class InstalledEvidence:
    release_id: str
    manifest_sha256: str
    binding_sha256: str
    parent_identity: tuple[int, int]
    image_identity: tuple[int, int]
    python_identity: tuple[int, int]
    python_version: str = PYTHON_VERSION
    python_sha256: str = PYTHON_SHA256
    dependency_closure: str = "UNPROVEN"


@dataclass(frozen=True, slots=True)
class InstallResult:
    status: InstallStatus
    disposition: InstallDisposition
    reason: InstallReason
    evidence: InstalledEvidence | None = None


class ReadSession(Protocol):
    def object(self, path: str, *, directory: bool) -> ObjectFacts | None: ...
    def names(self, path: str) -> tuple[str, ...]: ...
    def read(self, path: str, limit: int) -> bytes: ...
    def python_version(self) -> str: ...


class WriteSession(ReadSession, Protocol):
    def create_directory(self, path: str) -> None: ...
    def write_file(self, path: str, data: bytes) -> None: ...
    def seal_staging(self) -> None: ...
    def publish(self, staging_identity: tuple[int, int]) -> bool: ...


class ObserverNative(Protocol):
    def read_session(
        self, paths: ReleasePaths
    ) -> AbstractContextManager[ReadSession]: ...


class InstallerNative(ObserverNative, Protocol):
    def require_administrator_host(self) -> None: ...
    def install_session(
        self, paths: ReleasePaths
    ) -> AbstractContextManager[WriteSession]: ...
