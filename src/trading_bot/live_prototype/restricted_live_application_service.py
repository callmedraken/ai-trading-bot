"""Lifecycle-only desktop service for the closed-by-default L43 runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from math import isfinite
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol

from trading_bot.live_prototype.application_service import (
    DesktopWorkers,
    ReportReader,
    ResearchWorker,
    valid_research_view,
)
from trading_bot.live_prototype.contracts import (
    ActivityItem,
    Command,
    Lifecycle,
    PrototypeCommandResult,
    PrototypeSnapshot,
    Reason,
    ResearchView,
    RestrictedLiveStatus,
)


class _Runtime(Protocol):
    def run_cycle(self, stop: Event) -> object: ...

    @property
    def source_head(self) -> str: ...

    @property
    def source_tree(self) -> str: ...


Runtime = _Runtime

_UNAVAILABLE_RESEARCH = ResearchView(
    selected="UNAVAILABLE", assumptions=("Comparison report unavailable",)
)

_STATUS_REASON = {
    RestrictedLiveStatus.STOPPED: Reason.WORKERS_STOPPED,
    RestrictedLiveStatus.RUNNING_READ_ONLY: Reason.DATA_NOT_READY,
    RestrictedLiveStatus.NO_ACTION: Reason.NO_ACTION,
    RestrictedLiveStatus.ENTRY_PENDING: Reason.ENTRY_PENDING,
    RestrictedLiveStatus.SELL_PENDING: Reason.SELL_PENDING,
    RestrictedLiveStatus.ENTRY_RECONCILED: Reason.ENTRY_RECONCILED,
    RestrictedLiveStatus.SELL_RECONCILED: Reason.SELL_RECONCILED,
    RestrictedLiveStatus.REVIEW_ACCEPTED: Reason.NO_ACTION,
    RestrictedLiveStatus.BLOCKED: Reason.RECONCILIATION_REQUIRED,
    RestrictedLiveStatus.AUTHORIZATION_MISSING: Reason.AUTHORIZATION_MISSING,
    RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED: Reason.MANUAL_CLOSE_REQUIRED,
    RestrictedLiveStatus.EFFECT_UNKNOWN: Reason.EFFECT_UNKNOWN,
}


class RestrictedLiveApplicationService:
    """Run one serialized L43 worker and independent descriptive research workers.

    The service controls only worker lifecycle. The production composition is
    source-pinned before the window opens; providers and durable L43 state stay
    lazy until Start. Start never grants authority. The default research worker
    waits idle until a separate source is supplied; the independent report
    worker can still load an explicitly selected comparison report.
    """

    def __init__(
        self,
        *,
        runtime: Runtime,
        research_worker: ResearchWorker | None = None,
        report_reader: ReportReader | None = None,
        cycle_interval_seconds: float = 60.0,
    ) -> None:
        if not callable(getattr(runtime, "run_cycle", None)):
            raise TypeError("production L43 runtime required")
        source_head = getattr(runtime, "source_head", None)
        source_tree = getattr(runtime, "source_tree", None)
        _require_hex(source_head, 40, "source HEAD")
        _require_hex(source_tree, 40, "source tree")
        if research_worker is not None and not callable(research_worker):
            raise TypeError("research worker must be callable")
        if report_reader is not None and not callable(report_reader):
            raise TypeError("report reader must be callable")
        if (
            type(cycle_interval_seconds) not in (int, float)
            or not isfinite(cycle_interval_seconds)
            or cycle_interval_seconds <= 0
        ):
            raise ValueError("positive runtime cycle interval required")

        self._runtime = runtime
        self._research_worker = research_worker or _wait_for_stop
        self._report_reader = report_reader
        self._cycle_interval_seconds = float(cycle_interval_seconds)
        self._lock = Lock()
        self._desktop_workers = DesktopWorkers()
        self._stop = self._desktop_workers.stop_event
        self._sequence = 0
        self._snapshot = PrototypeSnapshot(
            mode="RESTRICTED_LIVE",
            ready_to_trade=False,
            strategy="UNSELECTED",
            source_head=source_head,
            source_tree=source_tree,
            reasons=(Reason.DATA_NOT_READY, Reason.RECONCILIATION_REQUIRED),
        )

    def snapshot(self) -> PrototypeSnapshot:
        with self._lock:
            self._observe_workers()
            return self._snapshot

    def display_details(self) -> tuple[str, ...]:
        with self._lock:
            enabled = self._snapshot.restricted_live_enabled
            status = self._snapshot.restricted_live_status.value
            reason_code = self._snapshot.restricted_live_reason_code or "NOT_RUN"
        return (
            f"Source HEAD pin: {self._snapshot.source_head}",
            f"Source tree pin: {self._snapshot.source_tree}",
            f"Restricted-live runtime enabled: {'YES' if enabled else 'NO'}",
            f"Last runtime status: {status}",
            f"Last runtime diagnostic: {reason_code}",
            "Effect authority: NOT GRANTED BY APPLICATION START",
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
        self._observe_workers()
        if self._snapshot.lifecycle is Lifecycle.RUNNING:
            return PrototypeCommandResult(
                Command.START,
                True,
                _STATUS_REASON[self._snapshot.restricted_live_status],
            )
        if self._snapshot.lifecycle is Lifecycle.STOPPING or any(
            worker.is_alive() for worker in self._desktop_workers.workers
        ):
            return PrototypeCommandResult(Command.START, False, Reason.STOP_PENDING)

        started_ok, started = self._desktop_workers.start_workers(
            (
                (
                    "prototype-restricted-live-research-worker",
                    self._run_research,
                    (),
                ),
                (
                    "prototype-restricted-live-runtime-worker",
                    self._run_runtime,
                    (),
                ),
            )
        )
        self._snapshot = replace(
            self._snapshot,
            restricted_live_status=RestrictedLiveStatus.RUNNING_READ_ONLY,
            restricted_live_enabled=True,
            effect_authority_granted=False,
            ready_to_trade=False,
            restricted_live_reason_code="RUNTIME_ENABLED",
            reasons=(Reason.DATA_NOT_READY, Reason.RECONCILIATION_REQUIRED),
        )
        self._record(Lifecycle.RUNNING, Reason.DATA_NOT_READY, running=True)
        if not started_ok:
            self._stop.set()
            lifecycle = Lifecycle.STOPPING if started else Lifecycle.BLOCKED
            self._snapshot = replace(
                self._snapshot,
                restricted_live_status=RestrictedLiveStatus.BLOCKED,
                restricted_live_enabled=False,
                ready_to_trade=False,
                restricted_live_reason_code="WORKER_START_FAILED",
                reasons=(Reason.RECONCILIATION_REQUIRED,),
            )
            self._record(lifecycle, Reason.COMMAND_REJECTED, running=bool(started))
            return PrototypeCommandResult(Command.START, False, Reason.COMMAND_REJECTED)
        return PrototypeCommandResult(Command.START, True, Reason.DATA_NOT_READY)

    def _stop_workers(self) -> PrototypeCommandResult:
        workers = self._all_workers()
        if not any(worker.is_alive() for worker in workers):
            self._snapshot = replace(
                self._snapshot,
                restricted_live_status=(
                    RestrictedLiveStatus.STOPPED
                    if self._snapshot.restricted_live_status
                    is RestrictedLiveStatus.RUNNING_READ_ONLY
                    else self._snapshot.restricted_live_status
                ),
                restricted_live_enabled=False,
                ready_to_trade=False,
                restricted_live_reason_code=(
                    "STOPPED_BEFORE_FIRST_CYCLE"
                    if self._snapshot.restricted_live_status
                    is RestrictedLiveStatus.RUNNING_READ_ONLY
                    else self._snapshot.restricted_live_reason_code
                ),
            )
            self._record(Lifecycle.STOPPED, Reason.WORKERS_STOPPED, running=False)
            return PrototypeCommandResult(Command.STOP, True, Reason.WORKERS_STOPPED)
        self._stop.set()
        self._snapshot = replace(
            self._snapshot,
            restricted_live_enabled=False,
            ready_to_trade=False,
        )
        if self._snapshot.lifecycle is not Lifecycle.STOPPING:
            self._record(Lifecycle.STOPPING, Reason.STOP_PENDING, running=True)
        return PrototypeCommandResult(Command.STOP, True, Reason.STOP_PENDING)

    def request_report(self, path: Path) -> bool:
        """Read one explicitly selected descriptive report off-thread."""
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("explicit absolute comparison-report path required")
        with self._lock:
            self._observe_workers()
            if self._snapshot.lifecycle is Lifecycle.STOPPING or (
                self._desktop_workers.report_worker_active
            ):
                return False
            return self._desktop_workers.start_report_worker(
                name="prototype-restricted-live-report-reader",
                target=self._read_report,
                args=(path,),
            )

    def publish_research(self, research: object) -> None:
        """Install only validated non-live descriptive research data."""
        if not valid_research_view(research):
            raise ValueError("non-live descriptive research view required")
        with self._lock:
            self._snapshot = replace(self._snapshot, research=research)

    def _run_research(self) -> None:
        try:
            self._research_worker(self._stop, self.publish_research)
        except Exception:
            self._publish_unavailable_research()

    def _run_runtime(self) -> None:
        while not self._stop.is_set():
            try:
                observation = self._runtime.run_cycle(self._stop)
                status = self._publish_runtime_observation(observation)
                if status is RestrictedLiveStatus.EFFECT_UNKNOWN:
                    return
            except Exception:
                # An escaped in-cycle failure may follow a provider effect.
                # Preserve that ambiguity and never schedule another cycle.
                self._stop.set()
                self._block_runtime(
                    RestrictedLiveStatus.EFFECT_UNKNOWN,
                    "RUNTIME_CYCLE_EXCEPTION",
                )
                return
            if self._stop.wait(self._cycle_interval_seconds):
                break

    def _publish_runtime_observation(self, observation: object) -> RestrictedLiveStatus:
        from trading_bot.live_prototype.l43_runtime import (
            L43RuntimeObservation,
        )

        if (
            type(observation) is not L43RuntimeObservation
            or type(observation.status) is not RestrictedLiveStatus
        ):
            raise TypeError("exact sanitized L43 runtime observation required")
        if observation.status is RestrictedLiveStatus.EFFECT_UNKNOWN:
            self._stop.set()
            self._block_runtime(observation.status, observation.reason_code)
            return observation.status
        self._publish_status(observation.status, observation.reason_code)
        return observation.status

    def _publish_status(self, status: RestrictedLiveStatus, reason_code: str) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                restricted_live_status=status,
                restricted_live_reason_code=reason_code,
                restricted_live_enabled=(
                    self._snapshot.restricted_live_enabled and not self._stop.is_set()
                ),
                effect_authority_granted=False,
                ready_to_trade=False,
                reasons=(_STATUS_REASON[status],),
            )

    def _block_runtime(self, status: RestrictedLiveStatus, reason_code: str) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                restricted_live_status=status,
                restricted_live_reason_code=reason_code,
                restricted_live_enabled=False,
                effect_authority_granted=False,
                ready_to_trade=False,
                reasons=(_STATUS_REASON[status],),
            )
            self._record(
                Lifecycle.BLOCKED,
                _STATUS_REASON[status],
                running=self._desktop_workers.any_active(),
            )

    def _read_report(self, path: Path) -> None:
        try:
            if self._report_reader is None:
                from trading_bot.gui.research_comparison_service import (
                    read_comparison_report,
                )

                reader = read_comparison_report
            else:
                reader = self._report_reader
            self.publish_research(reader(path))
        except Exception:
            self._publish_unavailable_research()

    def _publish_unavailable_research(self) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, research=_UNAVAILABLE_RESEARCH)

    def _all_workers(self) -> tuple[Thread, ...]:
        return self._desktop_workers.all_workers()

    def _observe_workers(self) -> None:
        workers = self._all_workers()
        alive = any(worker.is_alive() for worker in workers)
        runtime_alive = self._desktop_workers.worker_active(
            "prototype-restricted-live-runtime-worker"
        )
        if self._snapshot.lifecycle is Lifecycle.STOPPING and not alive:
            if (
                self._snapshot.restricted_live_status
                is RestrictedLiveStatus.RUNNING_READ_ONLY
            ):
                self._snapshot = replace(
                    self._snapshot,
                    restricted_live_status=RestrictedLiveStatus.STOPPED,
                    restricted_live_reason_code=(
                        "STOPPED_BEFORE_FIRST_CYCLE"
                        if self._snapshot.restricted_live_status
                        is RestrictedLiveStatus.RUNNING_READ_ONLY
                        else self._snapshot.restricted_live_reason_code
                    ),
                )
            self._record(Lifecycle.STOPPED, Reason.WORKERS_STOPPED, running=False)
        elif self._snapshot.lifecycle is Lifecycle.RUNNING and not runtime_alive:
            self._snapshot = replace(
                self._snapshot,
                restricted_live_status=RestrictedLiveStatus.BLOCKED,
                restricted_live_enabled=False,
                ready_to_trade=False,
                restricted_live_reason_code="RUNTIME_WORKER_EXITED",
            )
            self._stop.set()
            self._record(
                Lifecycle.BLOCKED,
                Reason.RECONCILIATION_REQUIRED,
                running=alive,
            )
        elif self._snapshot.workers_running != alive:
            self._snapshot = replace(self._snapshot, workers_running=alive)

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
            effect_authority_granted=False,
            reasons=(reason,),
            activity=events[-200:],
        )

    def shutdown_complete(self) -> bool:
        with self._lock:
            self._desktop_workers.join_all()
        with self._lock:
            self._observe_workers()
            return not any(worker.is_alive() for worker in self._all_workers())


def _wait_for_stop(stop: Event, _publish: Callable[[object], None]) -> None:
    """Keep the optional research worker idle until a source is supplied."""

    stop.wait()


def _require_hex(value: object, length: int, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"exact {label} pin required")
