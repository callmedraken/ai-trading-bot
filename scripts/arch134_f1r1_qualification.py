"""134-F1R1-C1 disposable no-effect qualification operator (stdlib only).

This namespace has no production admission, deployment or trading capability.
The interpreter is observed, never described as Architecture-133 production Python.
"""

from __future__ import annotations

import argparse
import ast
import errno
import hashlib
import json
import os
import stat
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath

if __package__:
    from .arch134_f1r1_qualification_process import (
        QualificationProcessEvidence,
        current_process,
        observe_process,
    )
else:
    from arch134_f1r1_qualification_process import (
        QualificationProcessEvidence,
        current_process,
        observe_process,
    )

SCHEMA = "arch134-f1r1-c1-qualification/v1"
ROOT = Path(r"F:\AI\temp\qualification\arch134-f1r1-host-isolation")
PRODUCTION = PureWindowsPath(r"F:\AITradingBot")
MAX_BYTES = 1024 * 1024
SOURCE_NAMES = (
    "arch134_f1r1_qualification.py",
    "arch134_f1r1_qualification_process.py",
    "arch134_f1r1_qualification_reference.json",
    "run_arch134_f1r1_qualification.py",
)
COMMANDS = ("prepare", "run", "status", "stop", "verify")
PROTECTED_COUNTERS = (
    "F1_EFFECTS",
    "CREDENTIAL_EFFECTS",
    "PROVIDER_EFFECTS",
    "SCHEDULER_EFFECTS",
    "INSTALLATION_EFFECTS",
    "PAPER_EFFECTS",
    "BROKER_EFFECTS",
    "D1_EFFECTS",
    "D2_EFFECTS",
    "LIVE_EFFECTS",
)
# Generated from pure replay of the accepted B Git source; pinned by C1 source gate.
REFERENCE_SHA256 = "c778c80f6be76c8099a94a58091d733ebecf91abd19f76303161465de48909f1"


class QualificationStatus(StrEnum):
    READY = "READY_FOR_F1R1_C2_EXTERNAL_QUALIFICATION"
    RUNNING = "HOST_QUALIFICATION_RUNNING_SAFE"
    COMPLETED = "HOST_QUALIFICATION_COMPLETED"
    ABRUPT = "ABRUPT_DISAPPEARANCE"
    FAILED = "CAUGHT_INTERNAL_FAILURE"
    UNPROVEN = "QUALIFICATION_LIVENESS_UNPROVEN"
    TRANSITION = "QUALIFICATION_TRANSITION_IN_PROGRESS"


class QualificationReason(StrEnum):
    EXACT_FIXTURE = "EXACT_DISPOSABLE_FIXTURE_AND_INTERPRETER"
    REJECTED = "QUALIFICATION_ADMISSION_REJECTED"


class QualificationError(ValueError):
    """Preserve all evidence and return for review; never repair or retry."""


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zeros() -> dict[str, int]:
    return dict.fromkeys(PROTECTED_COUNTERS, 0)


def unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError("duplicate qualification field")
        result[key] = value
    return result


def decode(data: bytes) -> dict:
    value = json.loads(data, object_pairs_hook=unique)
    if type(value) is not dict or canonical(value) != data:
        raise QualificationError("canonical qualification object required")
    return value


def fields(value: object, expected: set[str]) -> None:
    if type(value) is not dict or set(value) != expected:
        raise QualificationError("closed qualification fields required")


def safe_namespace(path: Path) -> None:
    text = str(path)
    windows = PureWindowsPath(text)
    if text.startswith(("\\\\", "\\??\\")) or any(
        part.endswith((".", " ")) or ":" in part for part in windows.parts[1:]
    ):
        raise QualificationError("qualification path alias rejected")
    if windows == PRODUCTION or PRODUCTION in windows.parents:
        raise QualificationError("production namespace forbidden")
    if not path.is_absolute() or ".." in path.parts:
        raise QualificationError("canonical absolute qualification namespace required")
    for item in (path, *path.parents):
        if not item.exists() and not item.is_symlink():
            continue
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise QualificationError("link or reparse namespace rejected")


def file_identity(info: os.stat_result) -> tuple[int, int]:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_ino:
        raise QualificationError("single-link regular qualification file required")
    return info.st_dev, info.st_ino


def read(path: Path, limit: int = MAX_BYTES) -> bytes:
    safe_namespace(path)
    before = path.stat()
    identity = file_identity(before)
    if before.st_size > limit:
        raise QualificationError("qualification byte bound exceeded")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if file_identity(opened) != identity:
            raise QualificationError("qualification file changed")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    final = path.stat()
    safe_namespace(path)
    if (
        file_identity(final) != identity
        or file_identity(after) != identity
        or len(data) != before.st_size
        or len(data) > limit
        or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (final.st_size, final.st_mtime_ns, final.st_ctime_ns)
        or (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    ):
        raise QualificationError("qualification file observation unstable")
    return data


def exclusive(path: Path, data: bytes) -> None:
    safe_namespace(path)
    with path.open("xb") as stream:
        if stream.write(data) != len(data):
            raise OSError("short qualification write")
        stream.flush()
        os.fsync(stream.fileno())
    if read(path) != data:
        raise QualificationError("qualification durable readback failed")


@dataclass(frozen=True, slots=True, init=False)
class QualificationPaths:
    root: Path

    def __init__(self, root: Path | None = None, *, _test_only: bool = False):
        selected = ROOT if root is None else root
        if not _test_only and selected != ROOT:
            raise QualificationError("fixed qualification root required")
        safe_namespace(selected)
        object.__setattr__(self, "root", selected)

    @classmethod
    def fixed(cls) -> QualificationPaths:
        if os.name != "nt":
            raise QualificationError("fixed operator requires Windows")
        return cls(ROOT)

    @classmethod
    def _for_tests(cls, root: Path) -> QualificationPaths:
        """Python-only injection. Never exposed through argv or environment."""
        return cls(root, _test_only=True)

    def __post_init__(self) -> None:
        safe_namespace(self.root)

    @property
    def fixture(self) -> Path:
        return self.root / "fixture"

    def state(self, name: str) -> Path:
        if name not in {
            "lease.lock",
            "process.json",
            "lifecycle.jsonl",
            "stop.json",
            "result.json",
            "duplicate.json",
        }:
            raise QualificationError("fixed qualification artifact required")
        return self.root / name


@dataclass(frozen=True, slots=True)
class QualificationInterpreterEvidence:
    executable: str
    version: str
    sha256: str
    file_identity: tuple[int, int]


def interpreter() -> QualificationInterpreterEvidence:
    if sys.version_info < (3, 12):  # noqa: UP036 - explicit standalone admission
        raise QualificationError("qualification requires Python 3.12 or newer")
    executable = Path(current_process().executable).resolve(strict=True)
    safe_namespace(executable)
    data = read(executable, 64 * MAX_BYTES)
    return QualificationInterpreterEvidence(
        str(executable),
        ".".join(map(str, sys.version_info[:3])),
        sha(data),
        file_identity(executable.stat()),
    )


@dataclass(frozen=True, slots=True)
class QualificationFixtureManifest:
    source_inventory: tuple[tuple[str, str], ...]
    predecessor_sha256: str
    interpreter: QualificationInterpreterEvidence

    @property
    def runtime_id(self) -> str:
        # Operational qualification identity: no clock, PID, cwd or path inputs.
        return "qualification-" + sha(
            canonical(
                {
                    "namespace": SCHEMA,
                    "source_inventory": self.source_inventory,
                    "predecessor_sha256": self.predecessor_sha256,
                    "interpreter_sha256": self.interpreter.sha256,
                    "interpreter_version": self.interpreter.version,
                }
            )
        )

    def to_dict(self) -> dict:
        return dict(
            schema=SCHEMA,
            runtime_id=self.runtime_id,
            source_inventory=dict(self.source_inventory),
            predecessor_sha256=self.predecessor_sha256,
            interpreter=asdict(self.interpreter),
            protected_effects=zeros(),
            materialization="QUALIFICATION_ONLY_LOCAL_MATERIALIZATION",
        )


@dataclass(frozen=True, slots=True)
class QualificationFixtureEvidence:
    manifest: QualificationFixtureManifest
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class QualificationAdmissionResult:
    status: QualificationStatus | None
    reason: QualificationReason
    evidence: QualificationFixtureEvidence | None


def reference(path: Path) -> dict:
    data = read(path)
    if sha(data) != REFERENCE_SHA256:
        raise QualificationError("accepted logical predecessor reference drift")
    return decode(data)


def prepare(paths: QualificationPaths, *, source: Path | None = None) -> dict:
    """Materialize only a new disposable fixture; preserve partial/consumed state."""
    if paths.root.exists():
        return status(paths)
    source = source or Path(__file__).resolve().parent
    predecessor = reference(source / SOURCE_NAMES[2])
    if predecessor["source_head"] != "3f2e75f3daee40dfcf094b6057ae1a91f8de8928":
        raise QualificationError("accepted B reference required")
    payloads = {name: read(source / name) for name in SOURCE_NAMES}
    # Initial preparation consumes reviewed source-pin DATA only; never imports
    # the production checkpoint runner. Later admission never opens this checkout.
    tree = ast.parse(
        read(source / "checkpoint_runner.py", 2 * MAX_BYTES).decode("utf-8-sig")
    )
    declarations = [
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ARCH134_F1R1_C1_SOURCE_PINS"
    ]
    if len(declarations) != 1:
        raise QualificationError("reviewed C1 source inventory required")
    pins = ast.literal_eval(declarations[0])
    for name, payload in payloads.items():
        blob = payload.replace(b"\r\n", b"\n")
        actual = hashlib.sha1(
            b"blob " + str(len(blob)).encode() + b"\0" + blob
        ).hexdigest()
        if type(pins) is not dict or pins.get("scripts/" + name) != actual:
            raise QualificationError("prepare source differs from reviewed C1 pins")
    observed = interpreter()
    manifest = QualificationFixtureManifest(
        tuple((n, sha(b)) for n, b in sorted(payloads.items())),
        REFERENCE_SHA256,
        observed,
    )
    # No production installer, ACL elevation, release-root mutation or deployment.
    paths.root.mkdir(parents=True, exist_ok=False)
    paths.fixture.mkdir()
    for name, payload in payloads.items():
        exclusive(paths.fixture / name, payload)
    exclusive(paths.fixture / "manifest.json", canonical(manifest.to_dict()))
    exclusive(paths.state("lease.lock"), b"\0")
    for path in (
        *[paths.fixture / n for n in SOURCE_NAMES],
        paths.fixture / "manifest.json",
    ):
        path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    # Read-only attributes deter accidental edits, not an Administrator/ACL claim.
    return status(paths)


def admit_fixture(paths: QualificationPaths) -> QualificationAdmissionResult:
    try:
        safe_namespace(paths.root)
        expected_names = {*SOURCE_NAMES, "manifest.json"}
        if set(p.name for p in paths.fixture.iterdir()) != expected_names:
            raise QualificationError("qualification fixture inventory drift")
        raw = read(paths.fixture / "manifest.json")
        value = decode(raw)
        fields(
            value,
            {
                "schema",
                "runtime_id",
                "source_inventory",
                "predecessor_sha256",
                "interpreter",
                "protected_effects",
                "materialization",
            },
        )
        declared = value["source_inventory"]
        fields(declared, set(SOURCE_NAMES))
        for name in SOURCE_NAMES:
            if sha(read(paths.fixture / name)) != declared[name]:
                raise QualificationError("qualification source byte drift")
        reference(paths.fixture / SOURCE_NAMES[2])
        actual = interpreter()
        manifest = QualificationFixtureManifest(
            tuple(sorted(declared.items())),
            REFERENCE_SHA256,
            actual,
        )
        if canonical(manifest.to_dict()) != raw:
            raise QualificationError("fixture/interpreter identity drift")
        return QualificationAdmissionResult(
            QualificationStatus.READY,
            QualificationReason.EXACT_FIXTURE,
            QualificationFixtureEvidence(manifest, sha(raw)),
        )
    except (OSError, ValueError, TypeError, KeyError):
        return QualificationAdmissionResult(None, QualificationReason.REJECTED, None)


def require_fixture(paths: QualificationPaths) -> QualificationFixtureEvidence:
    admitted = admit_fixture(paths)
    if admitted.status is not QualificationStatus.READY or admitted.evidence is None:
        raise QualificationError("qualification fixture admission rejected")
    return admitted.evidence


def _lock(stream, *, shared: bool = False) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(
            stream.fileno(), msvcrt.LK_NBRLCK if shared else msvcrt.LK_NBLCK, 1
        )
    else:
        import fcntl

        fcntl.flock(
            stream.fileno(),
            (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB,
        )


def _unlock(stream) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class QualificationHostLease:
    """One disposable byte-range lease. No takeover, timeout, retry or deletion."""

    def __init__(self, paths: QualificationPaths):
        self.paths = paths
        self.stream = None
        self.identity = None
        self.attempted = False

    def acquire(self, runtime_id: str) -> bool:
        if self.attempted or not runtime_id.startswith("qualification-"):
            raise QualificationError("single qualification acquisition only")
        self.attempted = True
        path = self.paths.state("lease.lock")
        safe_namespace(path)
        identity = file_identity(path.stat())
        stream = path.open("r+b")
        try:
            if file_identity(os.fstat(stream.fileno())) != identity:
                raise QualificationError("lease file replaced")
            _lock(stream)
        except OSError as exc:
            stream.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
        except Exception:
            stream.close()
            raise
        if file_identity(path.stat()) != identity:
            stream.close()
            raise QualificationError("lease file replaced")
        self.stream, self.identity = stream, identity
        return True

    def release(self) -> None:
        if self.stream is None:
            raise QualificationError("qualification lease not held")
        try:
            if file_identity(self.paths.state("lease.lock").stat()) != self.identity:
                raise QualificationError("lease file replaced")
            _unlock(self.stream)
        finally:
            self.stream.close()
            self.stream = None


def lease_state(paths: QualificationPaths) -> str:
    """Read-handle shared-lock probe. Never writes or becomes host authority."""
    path = paths.state("lease.lock")
    safe_namespace(path)
    identity = file_identity(path.stat())
    with path.open("rb") as stream:
        if file_identity(os.fstat(stream.fileno())) != identity:
            raise QualificationError("lease probe identity drift")
        try:
            _lock(stream, shared=True)
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
            state = "HELD"
        else:
            _unlock(stream)
            state = "FREE"
        if file_identity(path.stat()) != identity:
            raise QualificationError("lease probe identity drift")
    return state


EVENTS = (
    "HOST_ENTERED",
    "SUPERVISOR_LOCK_ACQUIRED",
    "SUPERVISOR_LOOP_ENTERED",
    "SAFE_WAITING",
)
TERMINALS = {"NORMAL_RETURN", "CAUGHT_INTERNAL_FAILURE"}


def journal(paths: QualificationPaths, runtime_id: str) -> tuple[dict, ...]:
    path = paths.state("lifecycle.jsonl")
    if not path.exists():
        return ()
    data = read(path, 16384)
    if not data or not data.endswith(b"\n"):
        raise QualificationError("partial qualification lifecycle")
    rows = tuple(decode(line) for line in data.splitlines())
    if not 1 <= len(rows) <= 5:
        raise QualificationError("bounded qualification lifecycle required")
    for index, row in enumerate(rows):
        fields(row, {"schema", "runtime_id", "sequence", "event", "protected_effects"})
        if (
            row["schema"] != SCHEMA
            or row["runtime_id"] != runtime_id
            or type(row["sequence"]) is not int
            or row["sequence"] != index + 1
            or canonical(row["protected_effects"]) != canonical(zeros())
            or (index < 4 and row["event"] != EVENTS[index])
            or (index == 4 and row["event"] not in TERMINALS)
        ):
            raise QualificationError("qualification lifecycle replay rejected")
    return rows


def append(paths: QualificationPaths, runtime_id: str, event: str) -> None:
    rows = journal(paths, runtime_id)
    row = dict(
        schema=SCHEMA,
        runtime_id=runtime_id,
        sequence=len(rows) + 1,
        event=event,
        protected_effects=zeros(),
    )
    if (
        (len(rows) < 4 and event != EVENTS[len(rows)])
        or (len(rows) == 4 and event not in TERMINALS)
        or len(rows) >= 5
    ):
        raise QualificationError("qualification lifecycle transition rejected")
    path = paths.state("lifecycle.jsonl")
    safe_namespace(path)
    mode = "xb" if not rows else "ab"
    with path.open(mode) as stream:
        payload = canonical(row) + b"\n"
        if stream.write(payload) != len(payload):
            raise OSError("short lifecycle write")
        stream.flush()
        os.fsync(stream.fileno())
    if journal(paths, runtime_id) != (*rows, row):
        raise QualificationError("qualification lifecycle readback failed")


def request_stop(paths: QualificationPaths) -> dict:
    evidence = require_fixture(paths)
    runtime_id = evidence.manifest.runtime_id
    value = dict(schema=SCHEMA, runtime_id=runtime_id, signal="QUALIFICATION_STOP_ONLY")
    path = paths.state("stop.json")
    if path.exists():
        if read(path) != canonical(value):
            raise QualificationError("qualification stop signal drift")
    else:
        observed = status(paths, _allow_duplicate=True)
        if observed["QUALIFICATION_STATUS"] != QualificationStatus.RUNNING:
            raise QualificationError("only the admitted waiting qualification may stop")
        exclusive(path, canonical(value))
    return {"STOP_SIGNAL": "QUALIFICATION_STOP_REQUESTED", "RUNTIME_ID": runtime_id}


def stop_requested(paths: QualificationPaths, runtime_id: str) -> bool:
    path = paths.state("stop.json")
    if not path.exists():
        return False
    if read(path) != canonical(
        dict(schema=SCHEMA, runtime_id=runtime_id, signal="QUALIFICATION_STOP_ONLY")
    ):
        raise QualificationError("qualification stop signal rejected")
    return True


class QualificationHost:
    """C1-only host. Cannot consume or produce production runtime material."""

    def __init__(self, paths: QualificationPaths):
        self.paths = paths

    def run(self, *, wait_once: Callable[[], None] | None = None) -> dict:
        paths = self.paths
        fixture = require_fixture(paths)
        runtime_id = fixture.manifest.runtime_id
        # The host must be executing copied source, even in disposable tests.
        if Path(__file__).resolve() != (paths.fixture / SOURCE_NAMES[0]).resolve():
            raise QualificationError("host executable source must be the fixture")
        observer_origin = Path(
            sys.modules[current_process.__module__].__file__
        ).resolve()
        if observer_origin != (paths.fixture / SOURCE_NAMES[1]).resolve():
            raise QualificationError("process observer must execute from fixture")
        if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
            raise QualificationError("isolated -I -S -B qualification process required")
        if any(
            paths.state(n).exists()
            for n in ("duplicate.json", "stop.json", "result.json")
        ):
            raise QualificationError("qualification evidence consumed; no retry")
        if journal(paths, runtime_id) and not paths.state("process.json").exists():
            raise QualificationError("qualification lifecycle without process claim")
        process = current_process()
        if process.executable != fixture.manifest.interpreter.executable:
            raise QualificationError("qualification process interpreter mismatch")
        # Reserve the sole attempt BEFORE acquisition: even an early crash consumes it.
        try:
            exclusive(
                paths.state("process.json"),
                canonical(
                    dict(
                        schema=SCHEMA,
                        runtime_id=runtime_id,
                        process=asdict(process),
                        lease_identity=file_identity(paths.state("lease.lock").stat()),
                        manifest_sha256=fixture.manifest_sha256,
                        source_origin=str(Path(__file__).resolve()),
                        protected_effects=zeros(),
                    )
                ),
            )
        except FileExistsError:
            marker = paths.state("duplicate.json")
            if not marker.exists():
                exclusive(
                    marker,
                    canonical(
                        dict(
                            schema=SCHEMA,
                            runtime_id=runtime_id,
                            event="DUPLICATE_HOST_REJECTED",
                        )
                    ),
                )
            raise QualificationError(
                "duplicate or consumed qualification attempt"
            ) from None
        lease = QualificationHostLease(paths)
        if not lease.acquire(runtime_id):
            raise QualificationError(
                "qualification lease rejected; preserve consumed attempt"
            )
        try:
            for event in EVENTS:
                append(paths, runtime_id, event)
            print("QUALIFICATION_STATUS=SAFE_WAITING", flush=True)
            print("RUNTIME_ID=" + runtime_id, flush=True)
            terminal = "NORMAL_RETURN"
            try:
                while not stop_requested(paths, runtime_id):
                    if wait_once is None:
                        time.sleep(0.1)
                    else:
                        wait_once()
            except Exception:
                terminal = "CAUGHT_INTERNAL_FAILURE"
            append(paths, runtime_id, terminal)
            # Terminal append has flushed, fsynced and replayed before release.
            lease.release()
            exclusive(
                paths.state("result.json"),
                canonical(
                    dict(
                        schema=SCHEMA,
                        runtime_id=runtime_id,
                        terminal=terminal,
                        lifecycle_sha256=sha(read(paths.state("lifecycle.jsonl"))),
                        manifest_sha256=fixture.manifest_sha256,
                        lease_released_after_terminal=True,
                        protected_effects=zeros(),
                    )
                ),
            )
            return status(paths)
        finally:
            # OS ownership also closes on abrupt death. No evidence repair/retry.
            if lease.stream is not None:
                lease.stream.close()
                lease.stream = None


def status(paths: QualificationPaths, *, _allow_duplicate: bool = False) -> dict:
    fixture = require_fixture(paths)
    runtime_id = fixture.manifest.runtime_id
    if paths.state("duplicate.json").exists() and not _allow_duplicate:
        raise QualificationError("duplicate-host evidence preserved")
    lease_before = lease_state(paths)
    rows = journal(paths, runtime_id)
    process_path = paths.state("process.json")
    process_state = "NOT_STARTED"
    process = None
    if process_path.exists():
        value = decode(read(process_path))
        fields(
            value,
            {
                "schema",
                "runtime_id",
                "process",
                "lease_identity",
                "manifest_sha256",
                "source_origin",
                "protected_effects",
            },
        )
        fields(value["process"], {"pid", "birth", "executable"})
        if (
            value["schema"] != SCHEMA
            or value["runtime_id"] != runtime_id
            or value["manifest_sha256"] != fixture.manifest_sha256
            or value["source_origin"]
            != str((paths.fixture / SOURCE_NAMES[0]).resolve())
            or value["lease_identity"]
            != list(file_identity(paths.state("lease.lock").stat()))
            or canonical(value["protected_effects"]) != canonical(zeros())
            or type(value["process"]["pid"]) is not int
            or type(value["process"]["birth"]) is not str
            or not value["process"]["birth"]
            or value["process"]["executable"] != fixture.manifest.interpreter.executable
        ):
            raise QualificationError("qualification process evidence rejected")
        process = QualificationProcessEvidence(**value["process"])
        try:
            observed = observe_process(process.pid)
            process_state = (
                "GONE"
                if observed is None
                else ("ALIVE_EXACT" if observed == process else "IDENTITY_MISMATCH")
            )
        except OSError:
            process_state = "UNKNOWN"
    lease_after = lease_state(paths)
    last = rows[-1]["event"] if rows else "NONE"
    count = sum(r["event"] == "SUPERVISOR_LOCK_ACQUIRED" for r in rows)
    if lease_before != lease_after:
        classification = QualificationStatus.TRANSITION
    elif process_state == "IDENTITY_MISMATCH":
        raise QualificationError("PID reuse or stale process evidence")
    elif process_state == "UNKNOWN":
        classification = QualificationStatus.UNPROVEN
    elif last in TERMINALS:
        if process is None:
            raise QualificationError(
                "terminal lifecycle without process/lease evidence"
            )
        result = paths.state("result.json")
        if lease_after != "FREE" or not result.exists():
            classification = QualificationStatus.TRANSITION
        else:
            expected = dict(
                schema=SCHEMA,
                runtime_id=runtime_id,
                terminal=last,
                lifecycle_sha256=sha(read(paths.state("lifecycle.jsonl"))),
                manifest_sha256=fixture.manifest_sha256,
                lease_released_after_terminal=True,
                protected_effects=zeros(),
            )
            if read(result) != canonical(expected) or count != 1:
                raise QualificationError("qualification terminal evidence rejected")
            classification = (
                QualificationStatus.COMPLETED
                if last == "NORMAL_RETURN"
                else QualificationStatus.FAILED
            )
    elif (
        process_state == "ALIVE_EXACT"
        and lease_after == "HELD"
        and last == "SAFE_WAITING"
        and count == 1
    ):
        classification = QualificationStatus.RUNNING
    elif process_state == "NOT_STARTED" and not rows and lease_after == "FREE":
        classification = QualificationStatus.READY
    elif process_state == "ALIVE_EXACT":
        classification = QualificationStatus.TRANSITION
    else:
        classification = QualificationStatus.ABRUPT
    if classification is QualificationStatus.READY and any(
        paths.state(n).exists() for n in ("stop.json", "result.json")
    ):
        raise QualificationError("unexpected qualification state before start")
    return dict(
        QUALIFICATION_STATUS=classification.value,
        RUNTIME_ID=runtime_id,
        LEASE_STATE=lease_after,
        PROCESS_STATE=process_state,
        QUALIFICATION_INTERPRETER=asdict(fixture.manifest.interpreter),
        FIXTURE_LAUNCHER=str(paths.fixture / "run_arch134_f1r1_qualification.py"),
        PROCESS_IDENTITY=None if process is None else asdict(process),
        LIFECYCLE_STATUS=(
            last
            if last in TERMINALS
            else (
                "ACTIVE_NONTERMINAL"
                if classification is QualificationStatus.RUNNING
                else ("NOT_STARTED" if not rows else "ABRUPT_OR_UNPROVEN_NONTERMINAL")
            )
        ),
        LAST_LIFECYCLE_EVENT=last,
        LIFECYCLE_RECORD_COUNT=len(rows),
        HOST_LEASE_AUTHORITIES=count,
        READINESS=QualificationStatus.READY.value,
        PROTECTED_EFFECT_COUNTERS=zeros(),
        FIXTURE_MATERIALIZATION="QUALIFICATION_ONLY_LOCAL_MATERIALIZATION",
        SUCCESSOR_SOAK_AUTHORITY="NONE",
    )


def verify(paths: QualificationPaths) -> dict:
    result = status(paths)
    if result["QUALIFICATION_STATUS"] not in {
        QualificationStatus.READY,
        QualificationStatus.RUNNING,
        QualificationStatus.COMPLETED,
    }:
        raise QualificationError(result["QUALIFICATION_STATUS"])
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="C1 disposable qualification only; zero trading authority"
    )
    result.add_argument("command", choices=COMMANDS)
    return result


def main(
    argv: list[str] | None = None, *, _test_paths: QualificationPaths | None = None
) -> int:
    args = parser().parse_args(argv)
    try:
        paths = _test_paths or QualificationPaths.fixed()
        if args.command == "prepare":
            result = prepare(paths)
        elif args.command == "run":
            fixture = require_fixture(paths)
            launcher = paths.fixture / "run_arch134_f1r1_qualification.py"
            if Path(__file__).resolve() != (paths.fixture / SOURCE_NAMES[0]).resolve():
                if _test_paths is not None:
                    raise QualificationError(
                        "test host must explicitly enter copied fixture"
                    )
                os.execv(
                    fixture.manifest.interpreter.executable,
                    [
                        fixture.manifest.interpreter.executable,
                        "-I",
                        "-S",
                        "-B",
                        str(launcher),
                        "run",
                    ],
                )
                raise QualificationError("qualification re-exec returned")
            result = QualificationHost(paths).run()
            if result["QUALIFICATION_STATUS"] != QualificationStatus.COMPLETED:
                print(canonical(result).decode(), flush=True)
                return 2
        elif args.command == "stop":
            result = request_stop(paths)
        elif args.command == "verify":
            result = verify(paths)
        else:
            result = status(paths)
        print(canonical(result).decode(), flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(
            "QUALIFICATION_REJECTED=" + type(exc).__name__, file=sys.stderr, flush=True
        )
        return 2
