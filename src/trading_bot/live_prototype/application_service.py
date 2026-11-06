"""Cached, effect-disabled service for the real/disarmed desktop prototype."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol

from trading_bot.live_prototype.contracts import (
    ActivityItem,
    CandidateView,
    Command,
    Lifecycle,
    PrototypeCommandResult,
    PrototypeSnapshot,
    Reason,
    ResearchView,
)


class ConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


class RecoveryState(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RECOVERING = "RECOVERING"
    RECONCILED = "RECONCILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    """Public source/config/evidence digests shown by the window, never secrets."""

    source_head: str
    source_tree: str
    configuration_digest: str
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        _require_hex(self.source_head, 40, "source HEAD")
        _require_hex(self.source_tree, 40, "source tree")
        _require_hex(self.configuration_digest, 64, "configuration digest")
        if self.evidence_digest is not None:
            _require_hex(self.evidence_digest, 64, "evidence digest")

    def display_lines(self) -> tuple[str, ...]:
        evidence = self.evidence_digest or "UNAVAILABLE"
        return (
            f"Source HEAD: {self.source_head}",
            f"Source tree: {self.source_tree}",
            f"Configuration SHA-256: {self.configuration_digest}",
            f"Evidence SHA-256 (reference only): {evidence}",
        )


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    """Allowlisted cached connection/recovery facts from an effect-disabled worker."""

    connection: ConnectionState
    recovery: RecoveryState
    signal_as_of: str | None = None
    signal_fresh: bool = False
    quote_as_of: str | None = None
    quote_fresh: bool = False
    reasons: tuple[Reason, ...] = ()

    def __post_init__(self) -> None:
        if type(self.connection) is not ConnectionState:
            raise TypeError("exact connection state required")
        if type(self.recovery) is not RecoveryState:
            raise TypeError("exact recovery state required")
        if type(self.signal_fresh) is not bool or type(self.quote_fresh) is not bool:
            raise TypeError("exact freshness booleans required")
        if type(self.reasons) is not tuple or any(
            type(reason) is not Reason for reason in self.reasons
        ):
            raise TypeError("sanitized reason codes required")
        _validate_timestamp(self.signal_as_of)
        _validate_timestamp(self.quote_as_of)
        if self.signal_fresh and self.signal_as_of is None:
            raise ValueError("fresh signal requires a UTC timestamp")
        if self.quote_fresh and self.quote_as_of is None:
            raise ValueError("fresh quote requires a UTC timestamp")


class ResearchWorker(Protocol):
    def __call__(
        self, stop: Event, publish: Callable[[ResearchView], None]
    ) -> None: ...


class RuntimeWorker(Protocol):
    def __call__(
        self, stop: Event, publish: Callable[[RuntimeObservation], None]
    ) -> None: ...


ReportReader = Callable[[Path], ResearchView]

_BASE_REASONS = (
    Reason.SOURCE_ACCEPTANCE_REQUIRED,
    Reason.DATA_NOT_READY,
    Reason.EXIT_CAPABILITY_UNPROVEN,
)
_UNAVAILABLE_RESEARCH = ResearchView(
    selected="UNAVAILABLE", assumptions=("Comparison report unavailable",)
)


class RealDisarmedApplicationService:
    """Independent cached workers; this service has no provider or order interface."""

    def __init__(
        self,
        identity: ApplicationIdentity,
        *,
        research_worker: ResearchWorker | None = None,
        runtime_worker: RuntimeWorker | None = None,
        report_reader: ReportReader | None = None,
    ) -> None:
        if type(identity) is not ApplicationIdentity:
            raise TypeError("exact application identity required")
        if research_worker is not None and not callable(research_worker):
            raise TypeError("research worker must be callable")
        if runtime_worker is not None and not callable(runtime_worker):
            raise TypeError("runtime worker must be callable")
        if report_reader is not None and not callable(report_reader):
            raise TypeError("report reader must be callable")
        self._identity = identity
        self._research_worker = research_worker or _wait_for_stop
        self._runtime_worker = runtime_worker or _wait_for_stop
        self._report_reader = report_reader
        self._lock = Lock()
        self._stop = Event()
        self._workers: tuple[Thread, ...] = ()
        self._report_worker: Thread | None = None
        self._sequence = 0
        self._connection = ConnectionState.DISCONNECTED
        self._recovery = RecoveryState.NOT_CHECKED
        self._snapshot = PrototypeSnapshot(
            mode="REAL_DISARMED",
            source_head=identity.source_head,
            ready_to_trade=False,
            strategy="UNSELECTED",
            binding_digest=None,
            reasons=_BASE_REASONS + (Reason.RECONCILIATION_REQUIRED,),
        )

    def snapshot(self) -> PrototypeSnapshot:
        with self._lock:
            self._observe_workers()
            return self._snapshot

    def display_details(self) -> tuple[str, ...]:
        with self._lock:
            connection = self._connection.value
            recovery = self._recovery.value
        return self._identity.display_lines() + (
            f"Connection: {connection}",
            f"Recovery: {recovery}",
        )

    def submit(self, command: Command) -> PrototypeCommandResult:
        if type(command) is not Command:
            raise TypeError("exact Command required")
        with self._lock:
            if command in (Command.KILL, Command.EXIT):
                return PrototypeCommandResult(
                    command, False, Reason.EXTERNAL_OPERATOR_REQUIRED
                )
            if command is Command.START:
                return self._start()
            return self._stop_workers()

    def _start(self) -> PrototypeCommandResult:
        command = Command.START
        self._observe_workers()
        if self._snapshot.lifecycle not in (
            Lifecycle.DISARMED,
            Lifecycle.STOPPED,
        ) or self._recovery in (
            RecoveryState.RECONCILIATION_REQUIRED,
            RecoveryState.RECOVERING,
            RecoveryState.UNKNOWN,
        ):
            reason = (
                Reason.RECONCILIATION_REQUIRED
                if self._recovery is not RecoveryState.NOT_CHECKED
                else Reason.COMMAND_REJECTED
            )
            return PrototypeCommandResult(command, False, reason)

        self._stop.clear()
        workers = (
            Thread(
                target=self._run_research,
                name="prototype-real-disarmed-research-worker",
                daemon=False,
            ),
            Thread(
                target=self._run_runtime,
                name="prototype-real-disarmed-runtime-worker",
                daemon=False,
            ),
        )
        self._workers = workers
        self._record(Lifecycle.RUNNING, Reason.DATA_NOT_READY, running=True)
        started: list[Thread] = []
        try:
            for worker in workers:
                worker.start()
                started.append(worker)
        except Exception:
            self._stop.set()
            self._workers = tuple(started)
            lifecycle = Lifecycle.STOPPING if started else Lifecycle.BLOCKED
            self._record(lifecycle, Reason.COMMAND_REJECTED, running=bool(started))
            return PrototypeCommandResult(command, False, Reason.COMMAND_REJECTED)
        return PrototypeCommandResult(command, True, Reason.DATA_NOT_READY)

    def _stop_workers(self) -> PrototypeCommandResult:
        command = Command.STOP
        self._observe_workers()
        workers = self._all_workers()
        if not any(worker.is_alive() for worker in workers):
            self._record(Lifecycle.STOPPED, Reason.WORKERS_STOPPED, running=False)
            return PrototypeCommandResult(command, True, Reason.WORKERS_STOPPED)
        self._stop.set()
        self._record(Lifecycle.STOPPING, Reason.STOP_PENDING, running=True)
        return PrototypeCommandResult(command, True, Reason.STOP_PENDING)

    def request_report(self, path: Path) -> bool:
        """Read one explicitly selected report off-thread and discard invalid views."""
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("explicit absolute comparison-report path required")
        with self._lock:
            self._observe_workers()
            if self._snapshot.lifecycle is Lifecycle.STOPPING or (
                self._report_worker is not None and self._report_worker.is_alive()
            ):
                return False
            worker = Thread(
                target=self._read_report,
                args=(path,),
                name="prototype-real-disarmed-report-reader",
                daemon=False,
            )
            self._report_worker = worker
            try:
                worker.start()
            except Exception:
                self._report_worker = None
                return False
            return True

    def publish_runtime(self, observation: RuntimeObservation) -> None:
        """Install allowlisted cached facts while forcing readiness to remain false."""
        if type(observation) is not RuntimeObservation:
            raise TypeError("exact runtime observation required")
        with self._lock:
            self._connection = observation.connection
            self._recovery = observation.recovery
            reasons = list(_BASE_REASONS)
            reasons.extend(observation.reasons)
            if observation.connection is not ConnectionState.CONNECTED:
                reasons.append(Reason.DATA_NOT_READY)
            if observation.recovery is not RecoveryState.RECONCILED:
                reasons.append(Reason.RECONCILIATION_REQUIRED)
            self._snapshot = replace(
                self._snapshot,
                connected=observation.connection is ConnectionState.CONNECTED,
                ready_to_trade=False,
                signal_as_of=observation.signal_as_of,
                signal_fresh=observation.signal_fresh,
                quote_as_of=observation.quote_as_of,
                quote_fresh=observation.quote_fresh,
                reasons=_unique_reasons(reasons),
            )

    def _publish_research(self, research: ResearchView) -> None:
        if not _valid_research_view(research):
            raise ValueError("non-live descriptive research view required")
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                research=research,
                strategy="UNSELECTED",
                binding_digest=None,
                ready_to_trade=False,
            )

    def _run_research(self) -> None:
        try:
            self._research_worker(self._stop, self._publish_research)
        except Exception:
            self._publish_unavailable_research()

    def _run_runtime(self) -> None:
        try:
            self._runtime_worker(self._stop, self.publish_runtime)
        except Exception:
            with self._lock:
                self._connection = ConnectionState.FAILED
                self._recovery = RecoveryState.UNKNOWN
                self._snapshot = replace(
                    self._snapshot,
                    connected=False,
                    ready_to_trade=False,
                    reasons=_unique_reasons(
                        (
                            *_BASE_REASONS,
                            Reason.DATA_NOT_READY,
                            Reason.RECONCILIATION_REQUIRED,
                        )
                    ),
                )
                self._record(
                    Lifecycle.BLOCKED,
                    Reason.RECONCILIATION_REQUIRED,
                    running=False,
                )
            self._stop.set()

    def _read_report(self, path: Path) -> None:
        try:
            if self._report_reader is None:
                from trading_bot.gui.research_comparison_service import (
                    read_comparison_report,
                )

                reader = read_comparison_report
            else:
                reader = self._report_reader
            research = reader(path)
            self._publish_research(research)
        except Exception:
            self._publish_unavailable_research()

    def _publish_unavailable_research(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                research=_UNAVAILABLE_RESEARCH,
                strategy="UNSELECTED",
                binding_digest=None,
                ready_to_trade=False,
            )

    def _all_workers(self) -> tuple[Thread, ...]:
        return self._workers + (
            (self._report_worker,) if self._report_worker is not None else ()
        )

    def _observe_workers(self) -> None:
        alive = any(worker.is_alive() for worker in self._all_workers())
        if self._snapshot.lifecycle is Lifecycle.STOPPING and not alive:
            self._record(Lifecycle.STOPPED, Reason.WORKERS_STOPPED, running=False)
        elif self._snapshot.lifecycle is Lifecycle.RUNNING and not alive:
            self._record(Lifecycle.BLOCKED, Reason.DATA_NOT_READY, running=False)

    def _record(self, lifecycle: Lifecycle, reason: Reason, *, running: bool) -> None:
        self._sequence += 1
        events = self._snapshot.activity + (
            ActivityItem(self._sequence, reason, lifecycle),
        )
        self._snapshot = replace(
            self._snapshot,
            lifecycle=lifecycle,
            workers_running=running,
            ready_to_trade=False,
            reasons=_unique_reasons((*self._snapshot.reasons, reason)),
            activity=events[-200:],
        )

    def shutdown_complete(self) -> bool:
        with self._lock:
            workers = self._all_workers()
        for worker in workers:
            worker.join(timeout=0)
        with self._lock:
            self._observe_workers()
            return not any(worker.is_alive() for worker in self._all_workers())


def _wait_for_stop(stop: Event, _publish: Callable[[object], None]) -> None:
    stop.wait()


def _require_hex(value: str, length: int, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"exact {label} required")


def _validate_timestamp(value: str | None) -> None:
    if value is None:
        return
    if type(value) is not str:
        raise TypeError("UTC timestamp text required")
    from datetime import datetime, timedelta

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("valid UTC timestamp required") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")


def _valid_research_view(value: object) -> bool:
    if type(value) is not ResearchView or value.live_eligible is not False:
        return False
    if (
        type(value.candidates) is not tuple
        or type(value.selected) is not str
        or type(value.policy) is not str
        or type(value.assumptions) is not tuple
        or any(type(item) is not str for item in value.assumptions)
        or type(value.prior_trials) is not int
        or type(value.new_trials) is not int
        or value.prior_trials < 0
        or value.new_trials < 0
        or any(
            item is not None and type(item) is not str
            for item in (value.bundle_digest, value.dataset_digest)
        )
    ):
        return False
    for candidate in value.candidates:
        if (
            type(candidate) is not CandidateView
            or type(candidate.candidate) is not str
            or type(candidate.qualified) is not bool
            or type(candidate.reasons) is not tuple
            or any(type(item) is not str for item in candidate.reasons)
            or any(
                item is not None and type(item) is not str
                for item in (
                    candidate.base_return,
                    candidate.stress_return,
                    candidate.stress_drawdown,
                    candidate.turnover,
                )
            )
        ):
            return False
    return True


def _unique_reasons(reasons: tuple[Reason, ...] | list[Reason]) -> tuple[Reason, ...]:
    return tuple(dict.fromkeys(reasons))
