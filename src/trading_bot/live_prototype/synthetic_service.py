"""Isolated cached worker seam. It has no broker, credential or order capability."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event, Lock, Thread

from trading_bot.live_prototype.contracts import (
    ActivityItem,
    Command,
    Lifecycle,
    PrototypeCommandResult,
    PrototypeSnapshot,
    Reason,
    ResearchView,
)


class SyntheticApplicationService:
    """Start/Stop manages one synthetic worker; no method can arm a trade."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._stop = Event()
        self._worker: Thread | None = None
        self._report_worker: Thread | None = None
        self._snapshot = PrototypeSnapshot()
        self._sequence = 0

    def snapshot(self) -> PrototypeSnapshot:
        with self._lock:
            self._observe_shutdown()
            return self._snapshot

    def set_research_view(self, view: ResearchView) -> None:
        """Install a prevalidated worker-produced view without changing binding."""
        if type(view) is not ResearchView or view.live_eligible:
            raise ValueError("synthetic research view required")
        with self._lock:
            self._snapshot = replace(self._snapshot, research=view)

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
            reasons=(Reason.SYNTHETIC_ONLY, reason),
            activity=events[-200:],
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
                if self._worker is not None and self._worker.is_alive():
                    return PrototypeCommandResult(
                        command, False, Reason.COMMAND_REJECTED
                    )
                if self._snapshot.lifecycle is Lifecycle.STOPPING:
                    return PrototypeCommandResult(command, False, Reason.STOP_PENDING)
                self._stop.clear()
                self._record(Lifecycle.RUNNING, Reason.SYNTHETIC_ONLY, running=True)
                self._worker = Thread(
                    target=self._run, name="prototype-synthetic-worker", daemon=False
                )
                try:
                    self._worker.start()
                except RuntimeError:
                    self._worker = None
                    self._record(
                        Lifecycle.BLOCKED, Reason.COMMAND_REJECTED, running=False
                    )
                    return PrototypeCommandResult(
                        command, False, Reason.COMMAND_REJECTED
                    )
                return PrototypeCommandResult(command, True, Reason.SYNTHETIC_ONLY)
            if not any(
                t is not None and t.is_alive()
                for t in (self._worker, self._report_worker)
            ):
                self._record(Lifecycle.STOPPED, Reason.WORKERS_STOPPED, running=False)
                return PrototypeCommandResult(command, True, Reason.WORKERS_STOPPED)
            self._record(Lifecycle.STOPPING, Reason.STOP_PENDING, running=True)
            self._stop.set()
            return PrototypeCommandResult(command, True, Reason.STOP_PENDING)

    def _run(self) -> None:
        self._stop.wait()

    def request_report(self, path: Path) -> bool:
        """Read one explicitly chosen report off the Qt thread; never run a campaign."""
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("explicit absolute comparison-report path required")
        with self._lock:
            if self._snapshot.lifecycle is Lifecycle.STOPPING or (
                self._report_worker is not None and self._report_worker.is_alive()
            ):
                return False
            self._report_worker = Thread(
                target=self._read_report,
                args=(path,),
                name="prototype-comparison-reader",
                daemon=False,
            )
            try:
                self._report_worker.start()
            except RuntimeError:
                self._report_worker = None
                return False
            return True

    def _read_report(self, path: Path) -> None:
        try:
            from trading_bot.gui.research_comparison_service import (
                read_comparison_report,
            )

            view = read_comparison_report(path)
            if type(view) is not ResearchView or view.live_eligible:
                raise ValueError("invalid presentation")
        except Exception:
            view = ResearchView(
                selected="UNAVAILABLE", assumptions=("Comparison report unavailable",)
            )
        self.set_research_view(view)

    def _observe_shutdown(self) -> None:
        alive = any(
            t is not None and t.is_alive() for t in (self._worker, self._report_worker)
        )
        if not alive and self._snapshot.lifecycle is Lifecycle.STOPPING:
            self._record(Lifecycle.STOPPED, Reason.WORKERS_STOPPED, running=False)
        elif self._snapshot.lifecycle is Lifecycle.RUNNING and (
            self._worker is None or not self._worker.is_alive()
        ):
            self._record(Lifecycle.BLOCKED, Reason.COMMAND_REJECTED, running=False)

    def shutdown_complete(self) -> bool:
        """Nonblocking termination confirmation for every application worker."""
        with self._lock:
            workers = tuple(
                t for t in (self._worker, self._report_worker) if t is not None
            )
        for worker in workers:
            worker.join(timeout=0)
        with self._lock:
            self._observe_shutdown()
            return not any(t.is_alive() for t in workers)
