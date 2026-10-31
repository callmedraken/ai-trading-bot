"""Ordinary offline desktop lifecycle. No trading or research-domain authority.

Generation numbers are local journal chronology, never financial identities.
Worker methods are cooperative: start/request_stop return promptly and close
honours the supplied timeout. The coordinator owns them until confirmed closed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread, current_thread
from typing import Protocol
from uuid import UUID


class Lifecycle(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class Diagnostic(StrEnum):
    NONE = "NONE"
    PRIOR_UNRESOLVED = "PRIOR_UNRESOLVED"
    JOURNAL_INVALID = "JOURNAL_INVALID"
    JOURNAL_IO = "JOURNAL_IO"
    ALREADY_OWNED = "ALREADY_OWNED"
    START_FAILED = "START_FAILED"
    WORKER_FAILED = "WORKER_FAILED"
    CLOSE_TIMEOUT = "CLOSE_TIMEOUT"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"


class RuntimeEvent(StrEnum):
    START_REQUESTED = "START_REQUESTED"
    TRADING_STARTED = "TRADING_STARTED"
    RESEARCH_STARTED = "RESEARCH_STARTED"
    RUNNING = "RUNNING"
    STOP_REQUESTED = "STOP_REQUESTED"
    RESEARCH_STOPPED = "RESEARCH_STOPPED"
    TRADING_RECONCILED = "TRADING_RECONCILED"
    TRADING_STOPPED = "TRADING_STOPPED"
    STOPPED = "STOPPED"
    WORKER_FAILED = "WORKER_FAILED"


@dataclass(frozen=True)
class ArtifactIdentity:
    campaign_id: str
    bundle_id: str

    def __post_init__(self) -> None:
        if any(
            str(UUID(value)) != value for value in (self.campaign_id, self.bundle_id)
        ):
            raise ValueError("canonical artifact identities required")


@dataclass(frozen=True)
class WorkerHealth:
    state: Lifecycle = Lifecycle.STOPPED
    diagnostic: Diagnostic = Diagnostic.NONE
    artifact: ArtifactIdentity | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not Lifecycle or type(self.diagnostic) is not Diagnostic:
            raise TypeError("closed health vocabulary required")
        if self.artifact is not None and type(self.artifact) is not ArtifactIdentity:
            raise TypeError("bounded artifact identity required")


@dataclass(frozen=True)
class DesktopStatus:
    state: Lifecycle
    generation: int
    trading: WorkerHealth
    research: WorkerHealth
    diagnostic: Diagnostic
    can_start: bool
    can_stop: bool
    can_close: bool
    transport: str = "NOT_CONNECTED"
    mode: str = "SIMULATED_PAPER"
    live_enabled: bool = False


class Worker(Protocol):
    def start(self) -> None: ...
    def request_stop(self) -> None: ...
    def close(self, timeout: float) -> bool: ...
    def health(self) -> WorkerHealth: ...


class TradingWorker(Worker, Protocol):
    def reconcile_and_close(self, timeout: float) -> bool: ...


_CACHED_HEALTH_METHODS: dict[type[object], Callable[[object], object]] = {}


def register_cached_health_worker[CachedHealthWorkerT](
    worker_type: type[CachedHealthWorkerT],
) -> type[CachedHealthWorkerT]:
    """Explicitly opt one exact source-owned class into direct cached health.

    The registry captures the class's own original ``health`` implementation.
    Runtime subclasses, class monkeypatches, and per-instance overrides do not
    inherit the registration and remain on the supervisor's bounded call path.
    """
    if not isinstance(worker_type, type):
        raise TypeError("cached-health registration requires a worker class")
    health_method = worker_type.__dict__.get("health")
    if not callable(health_method):
        raise TypeError("cached-health workers must define their own health method")
    previous = _CACHED_HEALTH_METHODS.get(worker_type)
    if previous is not None and previous is not health_method:
        raise ValueError("cached-health worker registration cannot be replaced")
    _CACHED_HEALTH_METHODS[worker_type] = health_method
    return worker_type


def _registered_cached_health_method(
    worker: Worker,
) -> Callable[[object], object] | None:
    worker_type = type(worker)
    registered = _CACHED_HEALTH_METHODS.get(worker_type)
    if registered is None or worker_type.__dict__.get("health") is not registered:
        return None
    try:
        instance_attributes = object.__getattribute__(worker, "__dict__")
    except (AttributeError, TypeError):
        instance_attributes = {}
    if "health" in instance_attributes:
        return None
    return registered


class JournalError(ValueError):
    """Malformed, conflicting or incomplete runtime chronology."""


def _pairs(values: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in values:
        if key in result:
            raise JournalError("duplicate journal field")
        result[key] = value
    return result


class LifecycleJournal:
    """Append/fsync JSONL with strict replay and exclusive application ownership.

    The ordinary create-exclusive lock is deliberately retained after a crash.
    An operator must reconcile stale ownership/unresolved state; P4 never repairs
    or retries it. This is duplicate-instance protection, not hostile-user ACLs.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.state = Lifecycle.STOPPED
        self.generation = 0
        self.sequence = 0
        self._started: set[RuntimeEvent] = set()
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._owned = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("x", encoding="ascii") as handle:
            handle.write("desktop-runtime/v1\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._owned = True
        if not self.path.exists():
            return
        if self.path.is_symlink() or not 0 < self.path.stat().st_size <= 4_000_000:
            raise JournalError("journal size/type")
        with self.path.open("rb") as handle:
            for line in handle:
                if len(line) > 1024 or not line.endswith(b"\n"):
                    raise JournalError("incomplete journal")
                try:
                    row = json.loads(line, object_pairs_hook=_pairs)
                    self._accept(row)
                except (ValueError, TypeError, KeyError, OverflowError) as error:
                    raise JournalError("journal shape/transition") from error

    def _accept(self, row: dict) -> None:
        if type(row) is not dict or set(row) != {
            "schema",
            "sequence",
            "generation",
            "utc",
            "event",
            "diagnostic",
        }:
            raise JournalError("journal fields")
        if (
            row["schema"] != "desktop-runtime/v1"
            or type(row["sequence"]) is not int
            or row["sequence"] != self.sequence + 1
            or type(row["generation"]) is not int
            or type(row["utc"]) is not str
        ):
            raise JournalError("journal identity")
        timestamp = datetime.fromisoformat(row["utc"])
        if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
            raise JournalError("UTC required")
        event = RuntimeEvent(row["event"])
        diagnostic = Diagnostic(row["diagnostic"])
        generation = row["generation"]
        if event is RuntimeEvent.START_REQUESTED:
            if self.state is not Lifecycle.STOPPED or generation != self.generation + 1:
                raise JournalError("unresolved generation")
            self._started.clear()
            state = Lifecycle.STARTING
        else:
            if generation != self.generation or generation == 0:
                raise JournalError("foreign generation")
            state = self.state
            if event is RuntimeEvent.WORKER_FAILED:
                if state is Lifecycle.STOPPED or diagnostic is Diagnostic.NONE:
                    raise JournalError("failure outside lifecycle")
                state = Lifecycle.FAILED
            elif event is RuntimeEvent.STOP_REQUESTED:
                if state not in (Lifecycle.STARTING, Lifecycle.RUNNING):
                    raise JournalError("stop outside active lifecycle")
                state = Lifecycle.STOPPING
            elif event in (RuntimeEvent.TRADING_STARTED, RuntimeEvent.RESEARCH_STARTED):
                if (
                    state not in (Lifecycle.STARTING, Lifecycle.STOPPING)
                    or event in self._started
                ):
                    raise JournalError("duplicate/late worker start")
                if event is RuntimeEvent.RESEARCH_STARTED and (
                    RuntimeEvent.TRADING_STARTED not in self._started
                ):
                    raise JournalError("worker start ordering")
            elif event is RuntimeEvent.RUNNING:
                if (
                    state is not Lifecycle.STARTING
                    or not {RuntimeEvent.TRADING_STARTED, RuntimeEvent.RESEARCH_STARTED}
                    <= self._started
                ):
                    raise JournalError("running before worker start")
                state = Lifecycle.RUNNING
            elif event in (
                RuntimeEvent.RESEARCH_STOPPED,
                RuntimeEvent.TRADING_RECONCILED,
                RuntimeEvent.TRADING_STOPPED,
            ):
                if state not in (Lifecycle.STOPPING, Lifecycle.FAILED):
                    raise JournalError("close outside shutdown")
                if event in self._started:
                    raise JournalError("duplicate close")
                if event is RuntimeEvent.TRADING_STOPPED and (
                    RuntimeEvent.TRADING_RECONCILED not in self._started
                ):
                    raise JournalError("trading close before reconciliation")
            elif event is RuntimeEvent.STOPPED:
                if (
                    state is not Lifecycle.STOPPING
                    or not {
                        RuntimeEvent.RESEARCH_STOPPED,
                        RuntimeEvent.TRADING_RECONCILED,
                        RuntimeEvent.TRADING_STOPPED,
                    }
                    <= self._started
                ):
                    raise JournalError("unconfirmed stop")
                state = Lifecycle.STOPPED
        if (
            event is not RuntimeEvent.WORKER_FAILED
            and diagnostic is not Diagnostic.NONE
        ):
            raise JournalError("unexpected diagnostic")
        self._started.add(event)
        self.sequence = row["sequence"]
        self.generation = generation
        self.state = state

    def append(
        self, event: RuntimeEvent, diagnostic: Diagnostic = Diagnostic.NONE
    ) -> None:
        if not self._owned:
            raise JournalError("journal ownership missing")
        row = {
            "schema": "desktop-runtime/v1",
            "sequence": self.sequence + 1,
            "generation": self.generation + (event is RuntimeEvent.START_REQUESTED),
            "utc": datetime.now(UTC).isoformat(),
            "event": event.value,
            "diagnostic": diagnostic.value,
        }
        # Validate before writing; any failed write poisons this supervisor.
        self._accept(row)
        with self.path.open("ab") as handle:
            handle.write((json.dumps(row, sort_keys=True) + "\n").encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())

    def release(self) -> None:
        if self._owned:
            self._lock_path.unlink()
            self._owned = False


@register_cached_health_worker
class LocalTradingWorker:
    """Inert P4 worker: no strategy, positions, ledger, files or transport."""

    def __init__(self) -> None:
        self._stop = Event()
        self._ready = Event()
        self._thread: Thread | None = None
        self._health = WorkerHealth()
        self._lock = Lock()

    def _publish(self, health: WorkerHealth) -> None:
        with self._lock:
            self._health = health

    def health(self) -> WorkerHealth:
        with self._lock:
            return self._health

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("worker already started")
        self._publish(WorkerHealth(Lifecycle.STARTING))
        self._thread = Thread(target=self._run, name="desktop-trading", daemon=False)
        self._thread.start()
        if not self._ready.wait(1):
            raise RuntimeError("worker readiness timeout")

    def _run(self) -> None:
        self._publish(WorkerHealth(Lifecycle.RUNNING))
        self._ready.set()
        self._stop.wait()
        self._publish(WorkerHealth(Lifecycle.STOPPING))

    def request_stop(self) -> None:
        self._stop.set()

    def close(self, timeout: float) -> bool:
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                return False
        self._publish(WorkerHealth())
        return True

    def reconcile_and_close(self, timeout: float) -> bool:
        # Nothing external exists to reconcile in P4. Confirm local thread exit.
        return self.close(timeout)


@dataclass(frozen=True)
class InspectBundle:
    path: Path
    expected_sha256: str | None = None
    expected_identity: ArtifactIdentity | None = None


def inspect_bundle(job: InspectBundle) -> ArtifactIdentity:
    """The one offline job: read/validate a bounded immutable P3 bundle only."""
    from hashlib import sha256

    from trading_bot.experiments.desktop_research_campaign import (
        read_desktop_campaign_bundle,
    )

    if job.path.suffix.casefold() != ".json" or job.path.anchor.startswith("\\\\"):
        raise ValueError("local JSON required")
    bundle = read_desktop_campaign_bundle(job.path)
    identity = ArtifactIdentity(bundle.campaign_id, bundle.bundle_id)
    # The reader strictly validates canonical bytes, so its canonical encoding
    # is the same bounded payload; no second unbounded/read-racy file read.
    if job.expected_sha256 is not None and (
        sha256(bundle.to_bytes()).hexdigest() != job.expected_sha256
    ):
        raise ValueError("bundle commitment mismatch")
    if job.expected_identity is not None and identity != job.expected_identity:
        raise ValueError("bundle identity mismatch")
    return identity


@register_cached_health_worker
class LocalResearchWorker:
    """Independent state and a one-slot offline queue; no trading reference."""

    def __init__(
        self,
        initial_job: InspectBundle | None = None,
        inspector: Callable[[InspectBundle], ArtifactIdentity] = inspect_bundle,
    ) -> None:
        self._stop = Event()
        self._ready = Event()
        self._thread: Thread | None = None
        self._health = WorkerHealth()
        self._lock = Lock()
        self._jobs: Queue[InspectBundle] = Queue(maxsize=1)
        self._inspector = inspector
        if initial_job is not None:
            self._jobs.put_nowait(initial_job)

    def health(self) -> WorkerHealth:
        with self._lock:
            return self._health

    def _publish(self, health: WorkerHealth) -> None:
        with self._lock:
            self._health = health

    def submit(self, job: InspectBundle) -> bool:
        with self._lock:
            if self._stop.is_set() or self._health.state is not Lifecycle.RUNNING:
                return False
            try:
                self._jobs.put_nowait(job)
            except Full:
                return False
            return True

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("worker already started")
        self._publish(WorkerHealth(Lifecycle.STARTING))
        self._thread = Thread(target=self._run, name="desktop-research", daemon=False)
        self._thread.start()
        if not self._ready.wait(1):
            raise RuntimeError("worker readiness timeout")

    def _run(self) -> None:
        self._publish(WorkerHealth(Lifecycle.RUNNING))
        self._ready.set()
        try:
            while not self._stop.is_set():
                try:
                    job = self._jobs.get(timeout=0.05)
                except Empty:
                    continue
                if self._stop.is_set():
                    break
                identity = self._inspector(job)
                self._publish(WorkerHealth(Lifecycle.RUNNING, artifact=identity))
        except Exception:
            self._publish(WorkerHealth(Lifecycle.FAILED, Diagnostic.ARTIFACT_INVALID))

    def request_stop(self) -> None:
        self._stop.set()

    def close(self, timeout: float) -> bool:
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                return False
        self._publish(WorkerHealth(artifact=self.health().artifact))
        return True


class DesktopSupervisor:
    """One owned coordinator per operator generation; no automatic restart.

    Failed lifecycles are terminal attention states even after successful cleanup.
    Only a clean STOPPED lifecycle may start another generation. Failed cleanup
    retains worker references and application ownership; closing is refused.
    """

    def __init__(
        self,
        journal: LifecycleJournal,
        trading_factory: Callable[[], TradingWorker] = LocalTradingWorker,
        research_factory: Callable[[], Worker] = LocalResearchWorker,
        *,
        close_timeout: float = 2.0,
    ) -> None:
        if not 0 < close_timeout <= 10:
            raise ValueError("close timeout must be in (0, 10]")
        self._journal = journal
        self._trading_factory = trading_factory
        self._research_factory = research_factory
        self._timeout = close_timeout
        self._lock = Lock()
        self._stop = Event()
        self._coordinator: Thread | None = None
        self._trading: TradingWorker | None = None
        self._research: Worker | None = None
        self._trading_health = WorkerHealth()
        self._research_health = WorkerHealth()
        self._state = Lifecycle.STOPPED
        self._diagnostic = Diagnostic.NONE
        self._closed = True
        self._disposed = False
        self._operations: list[tuple[Worker | None, Thread]] = []
        self._operation_timed_out = False
        self._journal_usable = False
        try:
            journal.acquire()
            self._journal_usable = True
            if journal.state is not Lifecycle.STOPPED:
                self._state = Lifecycle.FAILED
                self._diagnostic = Diagnostic.PRIOR_UNRESOLVED
        except FileExistsError:
            self._state = Lifecycle.FAILED
            self._diagnostic = Diagnostic.ALREADY_OWNED
        except (JournalError, ValueError, TypeError):
            self._state = Lifecycle.FAILED
            self._diagnostic = Diagnostic.JOURNAL_INVALID
        except OSError:
            self._state = Lifecycle.FAILED
            self._diagnostic = Diagnostic.JOURNAL_IO

    def status(self) -> DesktopStatus:
        with self._lock:
            busy = self._coordinator is not None and self._coordinator.is_alive()
            return DesktopStatus(
                self._state,
                self._journal.generation,
                self._trading_health,
                self._research_health,
                self._diagnostic,
                self._state is Lifecycle.STOPPED and not busy and not self._disposed,
                self._state in (Lifecycle.STARTING, Lifecycle.RUNNING),
                self._closed and not busy,
            )

    def _record(
        self, event: RuntimeEvent, diagnostic: Diagnostic = Diagnostic.NONE
    ) -> None:
        if self._journal_usable:
            try:
                self._journal.append(event, diagnostic)
            except (OSError, ValueError):
                self._journal_usable = False
                self._state = Lifecycle.FAILED
                self._diagnostic = Diagnostic.JOURNAL_IO
                self._stop.set()
                raise JournalError("journal write failed") from None

    def start(self) -> bool:
        with self._lock:
            if (
                self._disposed
                or self._state is not Lifecycle.STOPPED
                or (self._coordinator is not None and self._coordinator.is_alive())
            ):
                return False
            try:
                self._record(RuntimeEvent.START_REQUESTED)
            except JournalError:
                return False
            self._state = Lifecycle.STARTING
            self._closed = False
            self._operations.clear()
            self._operation_timed_out = False
            self._trading = self._research = None
            self._trading_health = self._research_health = WorkerHealth()
            self._stop.clear()
            self._coordinator = Thread(
                target=self._run, name="desktop-supervisor", daemon=False
            )
            try:
                self._coordinator.start()
            except Exception:
                self._closed = True
                self._fail(Diagnostic.START_FAILED)
                return False
            return True

    def stop(self) -> None:
        with self._lock:
            if self._state in (Lifecycle.STARTING, Lifecycle.RUNNING):
                try:
                    self._record(RuntimeEvent.STOP_REQUESTED)
                    self._state = Lifecycle.STOPPING
                except JournalError:
                    pass
                self._stop.set()

    def _fail(self, code: Diagnostic) -> None:
        self._state = Lifecycle.FAILED
        if self._diagnostic is Diagnostic.NONE:
            self._diagnostic = code
        try:
            self._record(RuntimeEvent.WORKER_FAILED, self._diagnostic)
        except JournalError:
            pass
        self._stop.set()

    def _call(
        self,
        operation: Callable[[], object],
        timeout: float,
        owner: Worker | None = None,
    ) -> object:
        """Bound injected calls without losing ownership of timed-out operations."""
        result: list[object] = []
        completed = Event()

        def invoke() -> None:
            try:
                result.append(operation())
            except BaseException:
                result.append(RuntimeError("bounded worker operation failed"))
            finally:
                completed.set()

        thread = Thread(target=invoke, name="desktop-worker-operation", daemon=False)
        self._operations = [(w, t) for w, t in self._operations if t.is_alive()]
        self._operations.append((owner, thread))
        thread.start()
        if not completed.wait(timeout):
            self._operation_timed_out = True
            raise TimeoutError("worker operation timed out")
        thread.join()
        if isinstance(result[0], BaseException):
            raise RuntimeError("worker operation failed")
        return result[0]

    def _health(self, worker: Worker) -> WorkerHealth:
        # Only classes explicitly registered with their original own method
        # can use the direct path. Unknown/injected workers keep bounded calls.
        cached_health = _registered_cached_health_method(worker)
        if cached_health is not None:
            health = cached_health(worker)
        else:

            def read_untrusted_health() -> object:
                return worker.health()

            health = self._call(read_untrusted_health, self._timeout, worker)
        if type(health) is not WorkerHealth:
            raise TypeError("bounded worker health required")
        return health

    def _run(self) -> None:
        try:
            # Assign ownership before invoking start so partial-start failures
            # always enter cleanup. Stop during STARTING prevents further starts.
            for factory, attribute, event in (
                (self._trading_factory, "_trading", RuntimeEvent.TRADING_STARTED),
                (self._research_factory, "_research", RuntimeEvent.RESEARCH_STARTED),
            ):
                with self._lock:
                    if self._stop.is_set():
                        break

                def construct(factory=factory, attribute=attribute):
                    # Factory constructs only; never starts a worker. Even a late
                    # timed-out result remains assigned to this generation.
                    worker = factory()
                    with self._lock:
                        setattr(self, attribute, worker)
                    return worker

                worker = self._call(construct, self._timeout)
                if self._stop.is_set():
                    break
                self._call(worker.start, self._timeout, worker)
                health = self._health(worker)
                with self._lock:
                    setattr(self, attribute + "_health", health)
                    if health.state is not Lifecycle.RUNNING:
                        raise RuntimeError("worker failed readiness")
                    self._record(event)
            with self._lock:
                if not self._stop.is_set():
                    self._record(RuntimeEvent.RUNNING)
                    self._state = Lifecycle.RUNNING
            while not self._stop.wait(0.05):
                trading_health = self._health(self._trading)
                research_health = self._health(self._research)
                with self._lock:
                    self._trading_health = trading_health
                    self._research_health = research_health
                    if any(
                        health.state is not Lifecycle.RUNNING
                        for health in (trading_health, research_health)
                    ):
                        self._fail(
                            next(
                                (
                                    health.diagnostic
                                    for health in (trading_health, research_health)
                                    if health.diagnostic is not Diagnostic.NONE
                                ),
                                Diagnostic.WORKER_FAILED,
                            )
                        )
        except Exception:
            with self._lock:
                self._fail(
                    Diagnostic.START_FAILED
                    if self._state is Lifecycle.STARTING
                    else Diagnostic.WORKER_FAILED
                )
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        okay = True
        # Signal BOTH before waiting on either. Failure never suppresses the
        # other worker's shutdown/reconciliation attempt.
        for worker in (self._trading, self._research):
            if worker is not None:
                try:
                    self._call(worker.request_stop, self._timeout, worker)
                except Exception:
                    okay = False
        for worker, events, trading in (
            (self._research, (RuntimeEvent.RESEARCH_STOPPED,), False),
            (
                self._trading,
                (RuntimeEvent.TRADING_RECONCILED, RuntimeEvent.TRADING_STOPPED),
                True,
            ),
        ):
            try:
                if worker is not None and any(
                    owner is worker and thread.is_alive()
                    for owner, thread in self._operations
                ):
                    # Never close concurrently with a stuck start/stop/health call.
                    okay = False
                    continue
                close = (
                    (worker.reconcile_and_close if trading else worker.close)
                    if worker is not None
                    else None
                )
                closed = worker is None or self._call(
                    lambda close=close: close(self._timeout),
                    self._timeout + 0.1,
                    worker,
                )
                health = self._health(worker) if worker is not None else WorkerHealth()
                with self._lock:
                    if trading:
                        self._trading_health = health
                    else:
                        self._research_health = health
                if not closed or (health.state is not Lifecycle.STOPPED):
                    okay = False
                    continue
                with self._lock:
                    for event in events:
                        self._record(event)
            except Exception:
                okay = False
        with self._lock:
            okay = (
                okay
                and not self._operation_timed_out
                and not any(thread.is_alive() for _, thread in self._operations)
            )
            self._closed = okay
            if not okay:
                self._fail(Diagnostic.CLOSE_TIMEOUT)
            elif self._state is not Lifecycle.FAILED:
                try:
                    self._record(RuntimeEvent.STOPPED)
                    self._state = Lifecycle.STOPPED
                except JournalError:
                    pass

    def wait(self, timeout: float = 5) -> bool:
        """Bounded test/operator join; never called by the GUI event loop."""
        thread = self._coordinator
        if thread is not None and thread is not current_thread():
            thread.join(timeout)
        return self.status().can_close

    def dispose(self) -> bool:
        """Release application ownership only after confirmed worker closure."""
        with self._lock:
            if not self._closed or (
                self._coordinator is not None and self._coordinator.is_alive()
            ):
                return False
            # Unresolved/malformed journals retain the lock for visible recovery.
            if self._state is Lifecycle.STOPPED:
                self._journal.release()
            self._disposed = True
            return True
