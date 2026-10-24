"""D1S3 fixed, read-only native observation adapters.

The Architecture-133 handle implementation is reused without changing its
release-path admission policy. This adapter admits a separate, closed D1S3
read namespace. It has no write, process-start, or external-effect surface.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime
from enum import StrEnum
from pathlib import PureWindowsPath
from zoneinfo import ZoneInfo

from trading_bot.arch133_acl.read_only import (
    ADMIN_ACES,
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)
from trading_bot.arch133_verifier.token import (
    WindowsTradingTokenObserver,
    require_trading_token,
)
from trading_bot.review_paper.successor_readiness import (
    SuccessorReleaseDeclaration,
    SuccessorRootObservation,
)
from trading_bot.review_paper.successor_readiness import (
    SuccessorStoreClassification as RootClass,
)
from trading_bot.review_paper.successor_soak import snapshot
from trading_bot.review_paper.successor_soak_admission import ManualProcessObservation
from trading_bot.review_paper.successor_soak_contract import (
    MAX_BYTES,
    PARENT_NAME,
    PRODUCTION_ROOT,
    PROGRESSING,
    SESSION_NAMES,
    STORE_IDENTITY,
    SessionTerminal,
    SuccessorLineage,
    canonical,
)
from trading_bot.supervised_release.bundle import MAX_FILE_BYTES
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstalledEvidence,
    ObjectFacts,
    ObserverNative,
    ReadSession,
    ReleasePaths,
)
from trading_bot.supervised_release.model import DURABLE_DATA_ROOT, PRODUCTION_PYTHON
from trading_bot.supervised_release.native_read import (
    NativeObservationError,
    WindowsObserver,
    WindowsReadSession,
    bind,
    close_native_handle,
    windows_libraries,
)
from trading_bot.supervised_release.observer import (
    check_object,
    observe_installed_release,
    observe_parent,
)
from trading_bot.supervised_release.runtime_admission import (
    CONFIGURATION_PATHS,
    DLLS_ROOT,
    LIB_ROOT,
    NO_PYCACHE,
    RUNTIME_PARENT,
    RUNTIME_ROOT,
    SITE_PACKAGES,
    ZIP_PATH,
    DependencyObservation,
    ProcessObservation,
    ProjectModuleOrigin,
    RuntimeObjectKind,
    RuntimeObjectObservation,
    RuntimeStatus,
    RuntimeSubstrateObservation,
    admit_runtime_host,
)
from trading_bot.supervised_release.runtime_isolation import InstalledRuntimeMaterial

NAMES = (PARENT_NAME, *SESSION_NAMES)
MAX_OBJECTS = 20002


class Ownership(StrEnum):
    CURRENT_EXACT = "CURRENT_EXACT"
    GONE_OR_MISMATCHED = "GONE_OR_MISMATCHED"
    UNPROVEN = "UNPROVEN"


def observe_runtime_binary(session: ReadSession, volume: int) -> ObjectFacts:
    """Observe production Python without starting a runtime process."""
    facts = []
    for path, directory in ((RUNTIME_ROOT, True), (PRODUCTION_PYTHON, False)):
        fact = check_object(
            session.object(path, directory=directory),
            path,
            directory=directory,
            volume=volume,
            image_policy=False,
        )
        if fact.owner not in {ADMINISTRATORS_SID, SYSTEM_SID} or any(
            kind != 0
            or flags & ~0x13
            or (sid not in {ADMINISTRATORS_SID, SYSTEM_SID} and mask & ~0x1200A9)
            for sid, mask, kind, flags in fact.aces
        ):
            raise ValueError("production Python policy rejected")
        facts.append(fact)
    data = session.read(PRODUCTION_PYTHON, MAX_FILE_BYTES)
    if (
        len(data) != facts[1].size
        or hashlib.sha256(data).hexdigest() != PYTHON_SHA256
        or session.python_version() != PYTHON_VERSION
        or any(
            session.object(row.path, directory=row.kind == "directory") != row
            for row in facts
        )
    ):
        raise ValueError("production Python observation rejected")
    return facts[1]


def current_manual_identity() -> ManualProcessObservation:
    """Observe only this process's PID, native birth, and NY session date."""
    kernel, _ = windows_libraries()
    process = bind(kernel, "GetCurrentProcess", [], ctypes.c_void_p)()
    times = [ctypes.c_uint64() for _ in range(4)]
    if (
        not bind(kernel, "GetProcessTimes", [ctypes.c_void_p] * 5, ctypes.c_int32)(
            process, *(ctypes.byref(value) for value in times)
        )
        or not times[0].value
    ):
        raise NativeObservationError("current process birth unproven")
    return ManualProcessObservation(
        os.getpid(),
        "windows-filetime:" + str(times[0].value),
        datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
    )


def observe_exact_owner(process: ManualProcessObservation) -> Ownership:
    """Query only the replayed PID; never enumerate or select another process.

    A different live production PID remains UNPROVEN: a process handle alone
    cannot prove its immutable import/substrate admission. Definite PID reuse,
    exit, or a different executable can prove the reservation orphaned.
    """
    if type(process) is not ManualProcessObservation:
        raise ValueError("exact replayed manual process required")
    if process.pid > 0xFFFFFFFF:
        return Ownership.UNPROVEN
    kernel, _ = windows_libraries()
    handle = bind(
        kernel,
        "OpenProcess",
        [ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint32],
        ctypes.c_void_p,
    )(0x1000, False, process.pid)  # QUERY_LIMITED_INFORMATION only
    if not handle:
        return (
            Ownership.GONE_OR_MISMATCHED
            if ctypes.get_last_error() == 87
            else Ownership.UNPROVEN
        )
    try:
        times = [ctypes.c_uint64() for _ in range(4)]
        if not bind(kernel, "GetProcessTimes", [ctypes.c_void_p] * 5, ctypes.c_int32)(
            handle, *(ctypes.byref(value) for value in times)
        ):
            return Ownership.UNPROVEN
        birth = "windows-filetime:" + str(times[0].value)
        code = ctypes.c_uint32()
        if not bind(
            kernel,
            "GetExitCodeProcess",
            [ctypes.c_void_p, ctypes.c_void_p],
            ctypes.c_int32,
        )(handle, ctypes.byref(code)):
            return Ownership.UNPROVEN
        if code.value != 259 or birth != process.birth:
            return Ownership.GONE_OR_MISMATCHED
        size = ctypes.c_uint32(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if not bind(
            kernel,
            "QueryFullProcessImageNameW",
            [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_void_p],
            ctypes.c_int32,
        )(handle, 0, path, ctypes.byref(size)):
            return Ownership.UNPROVEN
        if path.value != PRODUCTION_PYTHON:
            return Ownership.GONE_OR_MISMATCHED
        return (
            Ownership.CURRENT_EXACT
            if process.pid == os.getpid()
            else Ownership.UNPROVEN
        )
    finally:
        close_native_handle(kernel, handle)


class D1S3ReadPaths:
    """Only the fixed root/files, runtime substrate, and accepted ancestors."""

    def admit(self, path: str) -> str:
        if type(path) is not str or str(PureWindowsPath(path)) != path:
            raise ValueError("canonical D1S3 read path required")
        if path in (
            *ANCESTORS,
            DURABLE_DATA_ROOT,
            PRODUCTION_ROOT,
            NO_PYCACHE,
            *CONFIGURATION_PATHS,
        ) or path in tuple(PRODUCTION_ROOT + "\\" + name for name in NAMES):
            return path
        if path == RUNTIME_ROOT or path.startswith(RUNTIME_ROOT + "\\"):
            parts = PureWindowsPath(path).relative_to(RUNTIME_ROOT).parts
            for part in parts:
                if (
                    not part
                    or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in part)
                    or part in {".", ".."}
                    or part.endswith((".", " "))
                    or part.split(".")[0].rstrip(" ").upper()
                    in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                    or re.fullmatch(r"(?:COM|LPT)[0-9]", part.split(".")[0].upper())
                ):
                    raise ValueError("runtime component alias rejected")
            return path
        raise ValueError("outside fixed D1S3 read namespace")


class D1S3ReadSession(WindowsReadSession):
    """Reuse no-follow handles, canonical paths, ACLs, and bounded reads."""

    def __init__(self, release_paths: ReleasePaths) -> None:
        super().__init__(release_paths)
        # This is a separate read-only adapter, never a ReleasePaths extension
        # supplied to the Architecture-133 installer or image observer.
        self.paths = D1S3ReadPaths()


class D1S3NativeReader:
    def __init__(self, declaration: SuccessorReleaseDeclaration) -> None:
        self._paths = ReleasePaths(declaration.release_id)

    @contextmanager
    def read_session(self) -> Iterator[D1S3ReadSession]:
        session = D1S3ReadSession(self._paths)
        try:
            observe_parent(session)
            yield session
        finally:
            session.close()


class _ReplayStorage:
    """Read capability only; snapshot cannot reserve or append through this."""

    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def read(self, name: str) -> bytes | None:
        if name not in NAMES:
            raise ValueError("fixed evidence name required")
        return self._payloads.get(name)


class NativeSuccessorRootObserver:
    def __init__(
        self,
        declaration: SuccessorReleaseDeclaration,
        runtime: NativeRuntimeObserver,
        *,
        reader: D1S3NativeReader | None = None,
        image_observer: ObserverNative | None = None,
    ) -> None:
        self._declaration = declaration
        self._image = WindowsObserver() if image_observer is None else image_observer
        self._reader = reader if reader is not None else D1S3NativeReader(declaration)
        self._runtime = runtime
        self._lineage = SuccessorLineage(
            InstalledRuntimeMaterial.from_manifest(
                declaration.release.manifest,
                binding_sha256=declaration.binding.sha256,
                durable_store_identities=(STORE_IDENTITY,),
            )
        )
        self._previous: tuple | None = None
        self._drifted = False

    def observe_root(self) -> SuccessorRootObservation:
        try:
            with self._reader.read_session() as session:
                parent = check_object(
                    session.object(DURABLE_DATA_ROOT, directory=True),
                    DURABLE_DATA_ROOT,
                    directory=True,
                    volume=observe_parent(session).identity[0],
                    image_policy=False,
                )
                if (
                    parent.owner != ADMINISTRATORS_SID
                    or parent.protected is not True
                    or parent.aces != ADMIN_ACES
                ):
                    raise ValueError("durable parent policy rejected")
                root = session.object(PRODUCTION_ROOT, directory=True)
                if root is None:
                    value = SuccessorRootObservation(
                        RootClass.ABSENT_ELIGIBLE, parent_identity=parent.identity
                    )
                    signature = (parent, None)
                else:
                    value, signature = self._observe_present(session, parent, root)
                if value.classification in {
                    RootClass.EMPTY_FRESH_ADMITTED,
                    RootClass.ALREADY_BOUND_EXACT,
                    RootClass.ACTIVE_CURRENT_EXACT,
                } and tuple(sorted(session.names(PRODUCTION_ROOT))) != tuple(
                    sorted(value.names)
                ):
                    self._drifted = True
                if session.object(DURABLE_DATA_ROOT, directory=True) != parent:
                    self._drifted = True
                if session.object(PRODUCTION_ROOT, directory=True) != root:
                    self._drifted = True
                if self._previous is not None and signature != self._previous:
                    self._drifted = True
                self._previous = signature
                if self._drifted:
                    return replace(
                        value, classification=RootClass.REPLACED_OBJECT, stable=False
                    )
                return value
        except (OSError, NativeObservationError):
            return SuccessorRootObservation(RootClass.INDETERMINATE, stable=False)
        except (ValueError, TypeError):
            return SuccessorRootObservation(
                RootClass.WRONG_PARENT_OR_POLICY, stable=False
            )
        except (Exception, KeyboardInterrupt):
            return SuccessorRootObservation(RootClass.INDETERMINATE, stable=False)

    def _observe_present(
        self, session, parent, root
    ) -> tuple[SuccessorRootObservation, tuple]:
        facts = dict(
            identity=root.identity,
            parent_identity=parent.identity,
            kind=root.kind,
            filesystem=root.filesystem,
            local=root.local,
            reparse=root.reparse,
            links=root.links,
            owner=root.owner,
            protected=root.protected,
            aces=root.aces,
        )
        if root.reparse or root.links != 1 or root.identity == parent.identity:
            return SuccessorRootObservation(RootClass.ALIAS_OR_REPARSE, **facts), (
                parent,
                root,
            )
        try:
            check_object(
                root, PRODUCTION_ROOT, directory=True, volume=parent.identity[0]
            )
        except ValueError:
            return SuccessorRootObservation(
                RootClass.WRONG_PARENT_OR_POLICY, **facts
            ), (parent, root)
        names = session.names(PRODUCTION_ROOT)
        if len(names) != len(set(name.casefold() for name in names)):
            return SuccessorRootObservation(RootClass.ALIAS_OR_REPARSE, **facts), (
                parent,
                root,
                names,
            )
        names = (
            tuple(name for name in NAMES if name in names)
            if set(names) <= set(NAMES)
            else names
        )
        facts["names"] = names
        if not names:
            value = SuccessorRootObservation(RootClass.EMPTY_FRESH_ADMITTED, **facts)
            return value, (parent, root, names)
        if any(name not in NAMES for name in names):
            return SuccessorRootObservation(RootClass.CONFLICTING_FOREIGN, **facts), (
                parent,
                root,
                names,
            )
        payloads, objects = {}, []
        identities = {parent.identity, root.identity}
        for name in names:
            path = PRODUCTION_ROOT + "\\" + name
            row = session.object(path, directory=False)
            if row is not None and (
                row.reparse or row.links != 1 or row.identity in identities
            ):
                return SuccessorRootObservation(RootClass.ALIAS_OR_REPARSE, **facts), (
                    parent,
                    root,
                    names,
                )
            row = check_object(row, path, directory=False, volume=parent.identity[0])
            identities.add(row.identity)
            payloads[name] = session.read(path, MAX_BYTES)
            if session.object(path, directory=False) != row:
                self._drifted = True
            objects.append((row, hashlib.sha256(payloads[name]).hexdigest()))
        signature = (parent, root, names, tuple(objects))
        if set(session.names(PRODUCTION_ROOT)) != set(names):
            self._drifted = True
        try:
            state = snapshot(_ReplayStorage(payloads), self._lineage)
        except (ValueError, TypeError, KeyError):
            return SuccessorRootObservation(
                RootClass.MALFORMED, malformed=True, **facts
            ), signature
        try:
            installed = observe_installed_release(
                self._declaration.release, self._declaration.binding, native=self._image
            )
        except (ValueError, OSError, NativeObservationError):
            return SuccessorRootObservation(RootClass.INDETERMINATE, **facts), signature
        try:
            self._check_runtime_evidence(state, root, installed)
        except ValueError:
            return SuccessorRootObservation(
                RootClass.MALFORMED, malformed=True, **facts
            ), signature
        if state.terminal is not None:
            return SuccessorRootObservation(
                RootClass.CONSUMED,
                consumed=True,
                evidence_complete=True,
                store_identity=STORE_IDENTITY,
                **facts,
            ), signature
        progressing = (
            names == (PARENT_NAME, SESSION_NAMES[0])
            and len(state.parent.rows) == 6
            and state.parent.rows[-1]["event"] == "SESSION_01_FINAL"
            and len(state.children) == 1
            and state.children[0].rows[-1]["event"] == "SESSION_FINAL"
            and SessionTerminal(state.children[0].rows[-1]["data"]["terminal"])
            in PROGRESSING
        )
        if progressing:
            return SuccessorRootObservation(
                RootClass.ALREADY_BOUND_EXACT,
                store_identity=STORE_IDENTITY,
                evidence_complete=True,
                **facts,
            ), signature
        children = state.children
        if children and children[-1].rows[-1]["event"] != "SESSION_FINAL":
            child = children[-1]
            ordinal = child.header["ordinal"]
            process = ManualProcessObservation(**child.header["process"])
            if process.observed_date != child.header["target_session"]:
                ownership = Ownership.GONE_OR_MISMATCHED
            else:
                ownership = self._runtime.observe_owner(process)
            classification = {
                Ownership.CURRENT_EXACT: RootClass.ACTIVE_CURRENT_EXACT,
                Ownership.GONE_OR_MISMATCHED: RootClass.CONSUMED,
                Ownership.UNPROVEN: RootClass.INDETERMINATE,
            }[ownership]
            if ordinal != len(children):
                raise ValueError("fixed ordinal replay mismatch")
            return SuccessorRootObservation(
                classification,
                store_identity=STORE_IDENTITY,
                evidence_complete=True,
                consumed=classification is RootClass.CONSUMED,
                **facts,
            ), signature
        # A canonical but incomplete post-reservation/finalization prefix has
        # no accepted controller continuation. Preserve it; never repair/retry.
        return SuccessorRootObservation(
            RootClass.CONSUMED,
            consumed=True,
            store_identity=STORE_IDENTITY,
            evidence_complete=False,
            **facts,
        ), signature

    @staticmethod
    def _check_runtime_evidence(
        state, root: ObjectFacts, installed: InstalledEvidence
    ) -> None:
        expected = {
            "image_identity": list(installed.image_identity),
            "python_identity": list(installed.python_identity),
            "store_identity": list(root.identity),
        }
        for evidence in (state.parent, *state.children):
            for row in evidence.rows:
                if row["event"] == "RUNTIME_HOST_ADMITTED" and row["data"] != expected:
                    raise ValueError("replayed runtime/store identity mismatch")

    def observe_manual_process(self) -> ManualProcessObservation:
        return self._runtime.observe_manual_process()


class NativeRuntimeObserver:
    """Current-process observations only; no PID argument, search, or launch."""

    def __init__(
        self,
        declaration: SuccessorReleaseDeclaration,
        *,
        reader: D1S3NativeReader | None = None,
        image_observer: ObserverNative | None = None,
    ) -> None:
        self._declaration = declaration
        self._image = WindowsObserver() if image_observer is None else image_observer
        self._reader = reader if reader is not None else D1S3NativeReader(declaration)
        self._root = ReleasePaths(declaration.release_id).final
        self._launcher = (
            self._root
            + "\\"
            + declaration.release.manifest.launcher_relative_path.replace("/", "\\")
        )

    def _current_process(self) -> None:
        if (
            sys.platform != "win32"
            or sys.executable != PRODUCTION_PYTHON
            or tuple(sys.argv) != (self._launcher,)
            or tuple(sys.orig_argv)
            != (PRODUCTION_PYTHON, "-I", "-S", "-B", self._launcher)
            or os.getcwd() != self._root
            or not sys.flags.isolated
            or not sys.flags.no_site
            or not sys.dont_write_bytecode
            or sys.pycache_prefix != NO_PYCACHE
            or any(
                name in sys.modules
                for name in ("site", "sitecustomize", "usercustomize")
            )
        ):
            raise ValueError("current process is not an immutable manual runtime")

    def observe_manual_process(self) -> ManualProcessObservation:
        self._current_process()
        installed = observe_installed_release(
            self._declaration.release, self._declaration.binding, native=self._image
        )
        admission = admit_runtime_host(
            self._declaration.release,
            self._declaration.binding,
            installed,
            image_observer=self._image,
            runtime_observer=self,
        )
        if admission.status is not RuntimeStatus.VERIFIED:
            raise ValueError("exact current manual runtime is not admitted")
        return current_manual_identity()

    def observe_owner(self, process: ManualProcessObservation) -> Ownership:
        ownership = observe_exact_owner(process)
        if ownership is Ownership.CURRENT_EXACT:
            try:
                current = self.observe_manual_process()
            except (ValueError, OSError, NativeObservationError):
                return Ownership.UNPROVEN
            if current != process:
                return Ownership.GONE_OR_MISMATCHED
        return ownership

    def observe_process(self) -> ProcessObservation:
        self._current_process()
        modules = tuple(sys.modules.items())
        if len(modules) > MAX_OBJECTS:
            raise ValueError("module inventory budget exceeded")
        origins = []
        inventory = self._declaration.source_policy.source_paths
        for name, module in modules:
            if name == "trading_bot" or name.startswith("trading_bot."):
                path = getattr(module, "__file__", None)
                if (
                    type(path) is not str
                    or not path.startswith(self._root + "\\")
                    or path[len(self._root) + 1 :].replace("\\", "/") not in inventory
                ):
                    raise ValueError("mutable or unproven project module")
                origins.append(ProjectModuleOrigin(name, path))
        if not origins:
            raise ValueError("project module inventory absent")
        with self._reader.read_session() as session:
            absent = session.object(NO_PYCACHE, directory=True) is None
        return ProcessObservation(
            sys.platform,
            sys.executable,
            ".".join(map(str, sys.version_info[:3])),
            bool(sys.flags.isolated),
            bool(sys.flags.no_site),
            sys.dont_write_bytecode,
            tuple(sys.argv),
            os.getcwd(),
            sys.pycache_prefix,
            absent,
            tuple(sys.path),
            tuple(sorted(origins, key=lambda row: row.name)),
            True,
            False,
            False,
            False,
            False,
        )

    def observe_substrate(self) -> RuntimeSubstrateObservation:
        self._current_process()
        token = WindowsTradingTokenObserver().observe()
        require_trading_token(TRADING_SID, token)
        with self._reader.read_session() as session:
            parent = session.object(RUNTIME_PARENT, directory=True)
            check_object(parent, RUNTIME_PARENT, directory=True, image_policy=False)
            objects, directories = {}, {}
            pending = [(RUNTIME_ROOT, True)]
            identities = set()
            while pending:
                path, directory = pending.pop()
                row = check_object(
                    session.object(path, directory=directory),
                    path,
                    directory=directory,
                    volume=parent.identity[0],
                    image_policy=False,
                )
                if row.identity in identities or len(objects) >= MAX_OBJECTS:
                    raise ValueError("runtime aliases or inventory budget rejected")
                identities.add(row.identity)
                objects[path] = row
                if directory:
                    names = session.names(path)
                    if len(names) != len({name.casefold() for name in names}):
                        raise ValueError("runtime namespace aliases rejected")
                    directories[path] = names
                    for name in names:
                        child = path + "\\" + name
                        observed = session.object(child, directory=True)
                        if observed is None:
                            raise ValueError("runtime object disappeared")
                        pending.append((child, observed.kind == "directory"))
            objects[RUNTIME_PARENT] = parent
            rows = []
            for path, row in sorted(objects.items()):
                if row.owner not in {ADMINISTRATORS_SID, SYSTEM_SID} or any(
                    kind != 0
                    or flags & ~0x13
                    or (
                        sid not in {ADMINISTRATORS_SID, SYSTEM_SID} and mask & ~0x1200A9
                    )
                    for sid, mask, kind, flags in row.aces
                ):
                    raise ValueError("runtime substrate permits mutation")
                rows.append(
                    RuntimeObjectObservation(
                        path,
                        path,
                        RuntimeObjectKind(row.kind),
                        row.owner,
                        row.filesystem,
                        row.local,
                        row.reparse,
                        row.identity,
                        row.links,
                        0,
                        True,
                    )
                )
            absent = tuple(
                path
                for path in CONFIGURATION_PATHS
                if session.object(path, directory=False) is None
            )
            if absent != CONFIGURATION_PATHS:
                raise ValueError("runtime configuration override present")
            dependencies = []
            modules = tuple(sys.modules.items())
            if len(modules) > MAX_OBJECTS:
                raise ValueError("dependency inventory budget exceeded")
            for name, module in modules:
                if (
                    name == "__main__"
                    or name == "trading_bot"
                    or name.startswith("trading_bot.")
                ):
                    continue
                origin = getattr(getattr(module, "__spec__", None), "origin", None)
                if origin in {"built-in", "frozen"}:
                    category = "builtin" if origin == "built-in" else "frozen"
                    dependencies.append(
                        DependencyObservation(name, category, category, None)
                    )
                elif (
                    type(origin) is str
                    and origin in objects
                    and objects[origin].kind == "file"
                ):
                    dependencies.append(
                        DependencyObservation(name, "runtime", origin, origin)
                    )
                else:
                    raise ValueError("dependency origin unproven")
            for path, row in objects.items():
                if session.object(path, directory=row.kind == "directory") != row:
                    raise ValueError("runtime object drift")
            if any(
                set(session.names(path)) != set(names)
                for path, names in directories.items()
            ):
                raise ValueError("runtime namespace drift")
            if any(
                session.object(path, directory=False) is not None for path in absent
            ):
                raise ValueError("configuration absence drift")
            fingerprint = hashlib.sha256(
                canonical([asdict(objects[path]) for path in sorted(objects)])
            ).hexdigest()
        roots = tuple(sys.path[2:])
        if not roots or any(
            path not in {ZIP_PATH, DLLS_ROOT, LIB_ROOT, RUNTIME_ROOT} for path in roots
        ):
            raise ValueError("runtime search path escaped fixed substrate")
        missing = tuple(path for path in (DLLS_ROOT, ZIP_PATH) if path not in objects)
        return RuntimeSubstrateObservation(
            RUNTIME_PARENT,
            RUNTIME_ROOT,
            SITE_PACKAGES,
            token.user_sid,
            True,
            token.elevated,
            tuple(rows),
            True,
            True,
            True,
            absent,
            True,
            roots,
            missing,
            tuple(sorted(dependencies, key=lambda row: row.name)),
            True,
            fingerprint,
            fingerprint,
        )
