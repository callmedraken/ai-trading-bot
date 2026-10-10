"""133-AE pure immutable runtime-host admission model.

This module owns no native collector, scheduler, credential, provider or execution
surface. Callers must supply independently collected read-only observations.
Dependency closure intentionally remains UNPROVEN until a later reviewed real-host
substrate qualification is accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol

from trading_bot.arch133_acl.read_only import (
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)
from trading_bot.supervised_release.binding import DEPENDENCY_CLOSURE, RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease
from trading_bot.supervised_release.installation_contract import (
    PYTHON_VERSION,
    InstalledEvidence,
    ObserverNative,
)
from trading_bot.supervised_release.model import (
    DURABLE_DATA_ROOT,
    PRODUCTION_PYTHON,
    project_scheduler_action,
    release_root,
)
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    replay_inputs,
)

RUNTIME_PARENT = r"F:\AITradingBot"
RUNTIME_ROOT = RUNTIME_PARENT + r"\runtime"
LIB_ROOT = RUNTIME_ROOT + r"\Lib"
DLLS_ROOT = RUNTIME_ROOT + r"\DLLs"
SITE_PACKAGES = LIB_ROOT + r"\site-packages"
ZIP_PATH = RUNTIME_ROOT + r"\python314.zip"
NO_PYCACHE = DURABLE_DATA_ROOT + r"\no-pycache"
CONFIGURATION_PATHS = (
    RUNTIME_PARENT + r"\pyvenv.cfg",
    RUNTIME_ROOT + r"\pyvenv.cfg",
    RUNTIME_ROOT + r"\python._pth",
    RUNTIME_ROOT + r"\python3._pth",
    RUNTIME_ROOT + r"\python314._pth",
)
_ALLOWED_SEARCH_ROOTS = frozenset((RUNTIME_ROOT, LIB_ROOT, DLLS_ROOT, ZIP_PATH))


class RuntimeStatus(StrEnum):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class RuntimeReason(StrEnum):
    VERIFIED = "VERIFIED"
    INPUT_OR_IMAGE = "INPUT_OR_IMAGE"
    PROCESS = "PROCESS"
    SUBSTRATE = "SUBSTRATE"
    DRIFT = "DRIFT"


class RuntimeObjectKind(StrEnum):
    DIRECTORY = "directory"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class ProjectModuleOrigin:
    name: str
    path: str


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    platform: str
    executable: str
    python_version: str
    isolated: bool
    no_site: bool
    dont_write_bytecode: bool
    argv: tuple[str, ...]
    working_directory: str
    pycache_prefix: str
    pycache_absent: bool
    sys_path: tuple[str, ...]
    project_module_origins: tuple[ProjectModuleOrigin, ...]
    project_modules_complete: bool
    site_main_called: bool
    pth_processed: bool
    sitecustomize_loaded: bool
    usercustomize_loaded: bool


@dataclass(frozen=True, slots=True)
class RuntimeObjectObservation:
    path: str
    final_path: str
    kind: RuntimeObjectKind
    owner_sid: str
    filesystem: str
    local: bool
    reparse: bool
    identity: tuple[int, int]
    links: int
    trading_mutation_granted: int
    rename_replace_denied: bool


@dataclass(frozen=True, slots=True)
class DependencyObservation:
    name: str
    category: str
    origin: str
    final_path: str | None


@dataclass(frozen=True, slots=True)
class RuntimeSubstrateObservation:
    runtime_parent: str
    runtime_root: str
    site_packages: str
    trading_sid: str
    trading_non_admin: bool
    trading_elevated: bool
    objects: tuple[RuntimeObjectObservation, ...]
    inventory_complete: bool
    native_no_follow: bool
    pinned_and_rechecked: bool
    configuration_absent: tuple[str, ...]
    configuration_scan_complete: bool
    runtime_search_roots: tuple[str, ...]
    absent_search_roots: tuple[str, ...]
    dependencies: tuple[DependencyObservation, ...]
    dependencies_complete: bool
    before_fingerprint: str
    after_fingerprint: str


class RuntimeObserver(Protocol):
    def observe_process(self) -> ProcessObservation: ...

    def observe_substrate(self) -> RuntimeSubstrateObservation: ...


@dataclass(frozen=True, slots=True)
class RuntimeAdmissionEvidence:
    release_id: str
    manifest_sha256: str
    binding_sha256: str
    image_identity: tuple[int, int]
    python_identity: tuple[int, int]
    release_root: str
    source_root: str
    launcher: str
    site_packages: str
    dependency_closure: str = DEPENDENCY_CLOSURE


@dataclass(frozen=True, slots=True)
class RuntimeAdmissionResult:
    status: RuntimeStatus
    reason: RuntimeReason
    evidence: RuntimeAdmissionEvidence | None = None


def _canonical(path: object) -> bool:
    if type(path) is not str or not path or path.startswith("\\\\"):
        return False
    value = PureWindowsPath(path)
    return str(value) == path and ".." not in value.parts


def _under(path: str, root: str) -> bool:
    value = PureWindowsPath(path)
    parent = PureWindowsPath(root)
    return value == parent or parent in value.parents


def _case_unique(paths: tuple[str, ...]) -> bool:
    return len({path.casefold() for path in paths}) == len(paths)


def _validate_process(
    value: ProcessObservation,
    release: VerifiedRelease,
    *,
    root: str,
    source_root: str,
    launcher: str,
    substrate: RuntimeSubstrateObservation,
) -> None:
    if type(value) is not ProcessObservation:
        raise ValueError("exact process observation required")
    if (
        value.platform != "win32"
        or value.executable != PRODUCTION_PYTHON
        or value.python_version != PYTHON_VERSION
        or value.isolated is not True
        or value.no_site is not True
        or value.dont_write_bytecode is not True
        or value.argv != (launcher,)
        or value.working_directory != root
        or value.pycache_prefix != NO_PYCACHE
        or value.pycache_absent is not True
        or value.project_modules_complete is not True
        or value.site_main_called is not False
        or value.pth_processed is not False
        or value.sitecustomize_loaded is not False
        or value.usercustomize_loaded is not False
        or type(value.sys_path) is not tuple
        or len(value.sys_path) < 3
        or value.sys_path[:2] != (source_root, SITE_PACKAGES)
        or not _case_unique(value.sys_path)
        or value.sys_path[2:] != substrate.runtime_search_roots
    ):
        raise ValueError("runtime process facts differ")
    action = project_scheduler_action(release.manifest)
    if (
        action.executable != value.executable
        or action.working_directory != root
        or action.arguments != ("-I", "-S", "-B", launcher)
    ):
        raise ValueError("scheduler/runtime projection differs")
    inventory = {item.relative_path for item in release.manifest.source_inventory}
    origins = value.project_module_origins
    if (
        type(origins) is not tuple
        or not origins
        or len({item.name for item in origins if type(item) is ProjectModuleOrigin})
        != len(origins)
    ):
        raise ValueError("project module coverage invalid")
    package_root = source_root + r"\trading_bot"
    for item in origins:
        if (
            type(item) is not ProjectModuleOrigin
            or type(item.name) is not str
            or not item.name.startswith("trading_bot")
            or not _canonical(item.path)
            or not _under(item.path, package_root)
        ):
            raise ValueError("project module origin outside immutable release")
        relative = item.path[len(root) + 1 :].replace("\\", "/")
        if relative not in inventory:
            raise ValueError("project module is not in verified release inventory")


def _validate_substrate(value: RuntimeSubstrateObservation) -> None:
    if (
        type(value) is not RuntimeSubstrateObservation
        or value.runtime_parent != RUNTIME_PARENT
        or value.runtime_root != RUNTIME_ROOT
        or value.site_packages != SITE_PACKAGES
        or value.trading_sid != TRADING_SID
        or value.trading_non_admin is not True
        or value.trading_elevated is not False
        or value.inventory_complete is not True
        or value.native_no_follow is not True
        or value.pinned_and_rechecked is not True
        or value.configuration_scan_complete is not True
        or value.configuration_absent != CONFIGURATION_PATHS
        or value.dependencies_complete is not True
        or type(value.before_fingerprint) is not str
        or not value.before_fingerprint
        or value.after_fingerprint != value.before_fingerprint
    ):
        raise ValueError("runtime substrate observation incomplete")
    roots = value.runtime_search_roots
    if (
        type(roots) is not tuple
        or not roots
        or LIB_ROOT not in roots
        or not _case_unique(roots)
        or any(root not in _ALLOWED_SEARCH_ROOTS for root in roots)
        or SITE_PACKAGES in roots
    ):
        raise ValueError("runtime search roots differ")
    absent = value.absent_search_roots
    if (
        type(absent) is not tuple
        or not _case_unique(absent)
        or any(root not in {DLLS_ROOT, ZIP_PATH} for root in absent)
    ):
        raise ValueError("absent search-root evidence invalid")
    objects = value.objects
    if type(objects) is not tuple or not objects:
        raise ValueError("runtime object inventory absent")
    by_path: dict[str, RuntimeObjectObservation] = {}
    identities: set[tuple[int, int]] = set()
    for item in objects:
        if (
            type(item) is not RuntimeObjectObservation
            or type(item.kind) is not RuntimeObjectKind
        ):
            raise ValueError("runtime object row invalid")
        if (
            not _canonical(item.path)
            or item.path != item.final_path
            or item.path.casefold() in by_path
            or item.owner_sid not in {ADMINISTRATORS_SID, SYSTEM_SID}
            or item.filesystem != "NTFS"
            or item.local is not True
            or item.reparse is not False
            or type(item.identity) is not tuple
            or len(item.identity) != 2
            or any(type(part) is not int or part <= 0 for part in item.identity)
            or item.identity in identities
            or type(item.links) is not int
            or item.links < 1
            or (item.kind is RuntimeObjectKind.FILE and item.links != 1)
            or type(item.trading_mutation_granted) is not int
            or item.trading_mutation_granted != 0
            or item.rename_replace_denied is not True
            or (item.path != RUNTIME_PARENT and not _under(item.path, RUNTIME_ROOT))
        ):
            raise ValueError("runtime object policy differs")
        identities.add(item.identity)
        by_path[item.path.casefold()] = item
    for path in absent:
        if path.casefold() in by_path:
            raise ValueError("absent search root is present")
    required = {
        RUNTIME_PARENT: RuntimeObjectKind.DIRECTORY,
        RUNTIME_ROOT: RuntimeObjectKind.DIRECTORY,
        PRODUCTION_PYTHON: RuntimeObjectKind.FILE,
        LIB_ROOT: RuntimeObjectKind.DIRECTORY,
        SITE_PACKAGES: RuntimeObjectKind.DIRECTORY,
    }
    for path, kind in required.items():
        row = by_path.get(path.casefold())
        if row is None or row.kind is not kind:
            raise ValueError("required runtime object missing")
    for path in roots:
        present = path.casefold() in by_path
        missing = path in absent
        if present == missing:
            raise ValueError("runtime search-root state contradictory")
    dependencies = value.dependencies
    if type(dependencies) is not tuple or not dependencies:
        raise ValueError("dependency transcript absent")
    names: set[str] = set()
    for item in dependencies:
        if type(item) is not DependencyObservation or item.name in names:
            raise ValueError("dependency row invalid")
        names.add(item.name)
        if item.category in {"builtin", "frozen"}:
            if item.origin != item.category or item.final_path is not None:
                raise ValueError("builtin/frozen dependency origin differs")
            continue
        if item.category != "runtime" or item.final_path is None:
            raise ValueError("dependency category differs")
        if (
            not _canonical(item.origin)
            or not _canonical(item.final_path)
            or not _under(item.origin, RUNTIME_ROOT)
            or not _under(item.final_path, RUNTIME_ROOT)
        ):
            raise ValueError("runtime dependency escaped protected substrate")
        final = by_path.get(item.final_path.casefold())
        if final is None or final.kind is not RuntimeObjectKind.FILE:
            raise ValueError("runtime dependency final object unproven")


def admit_runtime_host(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    *,
    image_observer: ObserverNative,
    runtime_observer: RuntimeObserver,
) -> RuntimeAdmissionResult:
    """Validate immutable release/process/substrate facts without effect authority."""
    reason = RuntimeReason.INPUT_OR_IMAGE
    try:
        replay_inputs(release, binding)
        if (
            type(installed) is not InstalledEvidence
            or image_observer is None
            or runtime_observer is None
            or DEPENDENCY_CLOSURE != "UNPROVEN"
        ):
            raise ValueError
        first_image = observe_installed_release(
            release, binding, native=image_observer
        )
        if (
            first_image != installed
            or first_image.dependency_closure != DEPENDENCY_CLOSURE
        ):
            raise ValueError
        root = release_root(release.manifest.release_id)
        source_root = root + r"\src"
        launcher = (
            root
            + "\\"
            + release.manifest.launcher_relative_path.replace("/", "\\")
        )
        reason = RuntimeReason.SUBSTRATE
        first_substrate = runtime_observer.observe_substrate()
        _validate_substrate(first_substrate)
        reason = RuntimeReason.PROCESS
        first_process = runtime_observer.observe_process()
        _validate_process(
            first_process,
            release,
            root=root,
            source_root=source_root,
            launcher=launcher,
            substrate=first_substrate,
        )
        reason = RuntimeReason.DRIFT
        second_substrate = runtime_observer.observe_substrate()
        second_process = runtime_observer.observe_process()
        if first_substrate != second_substrate or first_process != second_process:
            raise ValueError
        _validate_substrate(second_substrate)
        _validate_process(
            second_process,
            release,
            root=root,
            source_root=source_root,
            launcher=launcher,
            substrate=second_substrate,
        )
        second_image = observe_installed_release(
            release, binding, native=image_observer
        )
        if second_image != first_image:
            raise ValueError
        evidence = RuntimeAdmissionEvidence(
            release.manifest.release_id,
            release.expected_manifest_sha256,
            binding.sha256,
            first_image.image_identity,
            first_image.python_identity,
            root,
            source_root,
            launcher,
            SITE_PACKAGES,
        )
        return RuntimeAdmissionResult(
            RuntimeStatus.VERIFIED, RuntimeReason.VERIFIED, evidence
        )
    except Exception:
        return RuntimeAdmissionResult(RuntimeStatus.BLOCKED, reason)
