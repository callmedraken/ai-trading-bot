"""Bounded, restartable Architecture 148 worker lifecycle.

The worker owns scheduling and context lifetime only.  All state restoration,
broker reconciliation, cycle planning, and stop settlement are injected through
one context-owned session so importing or constructing this module has no I/O
or effect authority.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from trading_bot.live_prototype.l43_runtime import L43SerializedLifecycleInterlock


class WorkerLifecycle(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RECONCILING = "RECONCILING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    lifecycle: WorkerLifecycle
    cycles_completed: int
    last_cycle_at: datetime | None
    stop_requested: bool
    kill_requested: bool
    error_code: str | None


class RuntimeWorkerSession(Protocol):
    """One context-owned runtime session used by the worker thread.

    ``startup_reconcile`` must restore durable state and complete its factual
    reconcile-only pass before returning. ``run_cycle`` may make one effect
    only after its exact durable reservation and lifecycle boundary succeed.
    ``stop_reconcile`` is factual settlement only; it does not place or cancel.
    """

    def startup_reconcile(
        self,
        stop_event: threading.Event,
        lifecycle_interlock: L43SerializedLifecycleInterlock,
    ) -> None: ...

    def run_cycle(
        self,
        stop_event: threading.Event,
        lifecycle_interlock: L43SerializedLifecycleInterlock,
    ) -> object: ...

    def stop_reconcile(self) -> None: ...


class KillControl(Protocol):
    """Explicit safe service boundary over accepted kill-control authority."""

    def request_kill(self) -> None: ...


SessionFactory = Callable[[], AbstractContextManager[RuntimeWorkerSession]]
OwnerLeaseFactory = Callable[[], AbstractContextManager[bool]]
Clock = Callable[[], datetime]
_SAFE_ERROR = re.compile(r"[A-Z0-9_]{1,96}\Z")


class Arch148RuntimeWorker:
    """Run one serialized context-owned session at a bounded cadence."""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        owner_lease_factory: OwnerLeaseFactory,
        cadence: timedelta,
        lifecycle_interlock: L43SerializedLifecycleInterlock | None = None,
        kill_control: KillControl | None = None,
        clock: Clock | None = None,
        thread_name: str = "arch148-runtime-worker",
    ) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be callable")
        if not callable(owner_lease_factory):
            raise TypeError("owner_lease_factory must be callable")
        if (
            not isinstance(cadence, timedelta)
            or cadence <= timedelta(0)
            or cadence > timedelta(hours=1)
        ):
            raise ValueError("cadence must be positive and no longer than one hour")
        if lifecycle_interlock is not None and not isinstance(
            lifecycle_interlock, L43SerializedLifecycleInterlock
        ):
            raise TypeError("lifecycle_interlock must be the accepted L43 interlock")
        if kill_control is not None and not callable(
            getattr(kill_control, "request_kill", None)
        ):
            raise TypeError("kill_control must implement request_kill")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if not isinstance(thread_name, str) or not thread_name.strip():
            raise ValueError("thread_name must be nonblank")

        self._session_factory = session_factory
        self._owner_lease_factory = owner_lease_factory
        self._cadence = cadence
        self._interlock = lifecycle_interlock or L43SerializedLifecycleInterlock()
        self._kill_control = kill_control
        self._clock = clock or (lambda: datetime.now(UTC))
        self._thread_name = thread_name
        self._lock = threading.RLock()
        self._lifecycle = WorkerLifecycle.STOPPED
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._cycles_completed = 0
        self._last_cycle_at: datetime | None = None
        self._error_code: str | None = None
        self._kill_requested = False
        self._kill_latched = False
        self._settlement_started = False

    def start(self) -> bool:
        """Start one worker owner; return false while it is already active."""

        with self._lock:
            if self._kill_latched:
                return False
            if self._thread is not None and self._thread.is_alive():
                return False
            stop_event = threading.Event()
            self._stop_event = stop_event
            self._lifecycle = WorkerLifecycle.STARTING
            self._error_code = None
            self._settlement_started = False
            thread = threading.Thread(
                target=self._run,
                args=(stop_event,),
                name=self._thread_name,
                daemon=False,
            )
            self._thread = thread
            try:
                thread.start()
            except Exception:
                self._lifecycle = WorkerLifecycle.BLOCKED
                self._error_code = "WORKER_START_FAILED"
                self._thread = None
                self._stop_event = None
                return False
            return True

    def stop(self) -> bool:
        """Block new cycles and serialize Stop with an effect boundary."""

        with self._lock:
            event = self._stop_event
            thread = self._thread
            if event is None or thread is None or not thread.is_alive():
                return self._lifecycle in (
                    WorkerLifecycle.STOPPED,
                    WorkerLifecycle.BLOCKED,
                )
            event.set()
            if self._lifecycle in (WorkerLifecycle.STARTING, WorkerLifecycle.RUNNING):
                self._lifecycle = WorkerLifecycle.STOPPING
        self._interlock.request_stop()
        return True

    def kill(self) -> bool:
        """Apply the injected kill control, then stop this worker safely.

        A worker created without an accepted kill-control facade cannot claim
        that Kill succeeded.  The local stop flag is still set to prevent new
        cycles while the missing authority is reported to the caller.
        """

        with self._lock:
            event = self._stop_event
            thread = self._thread
            if (
                event is None
                or thread is None
                or not thread.is_alive()
                or self._settlement_started
            ):
                self._error_code = "KILL_REQUIRES_ACTIVE_SESSION"
                return False
            self._kill_requested = True
            self._kill_latched = True
            event.set()
            if self._lifecycle in (WorkerLifecycle.STARTING, WorkerLifecycle.RUNNING):
                self._lifecycle = WorkerLifecycle.STOPPING
            has_control = self._kill_control is not None
        self._interlock.request_stop()
        if not has_control:
            with self._lock:
                self._error_code = "KILL_CONTROL_UNAVAILABLE"
            return False
        return True

    def snapshot(self) -> WorkerSnapshot:
        with self._lock:
            event = self._stop_event
            return WorkerSnapshot(
                lifecycle=self._lifecycle,
                cycles_completed=self._cycles_completed,
                last_cycle_at=self._last_cycle_at,
                stop_requested=event.is_set() if event is not None else False,
                kill_requested=self._kill_requested,
                error_code=self._error_code,
            )

    def shutdown_complete(self) -> bool:
        with self._lock:
            return self._thread is None or not self._thread.is_alive()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the current thread; return whether it has stopped."""

        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        if thread is threading.current_thread():
            return False
        thread.join(timeout)
        return not thread.is_alive()

    def _run(self, stop_event: threading.Event) -> None:
        bound = False
        failed = False
        try:
            with self._lock:
                should_bind = not stop_event.is_set() or self._kill_requested
                if not should_bind:
                    self._settlement_started = True
            if should_bind:
                self._interlock.bind_cycle(stop_event)
                bound = True
            with self._lock:
                should_open_session = bound and (
                    not stop_event.is_set() or self._kill_requested
                )
                if bound and not should_open_session:
                    self._settlement_started = True
            if should_open_session:
                with self._owner_lease_factory() as lease_acquired:
                    if lease_acquired is not True:
                        raise RuntimeError("runtime ownership lease unavailable")
                    with self._lock:
                        should_run_session = (
                            not stop_event.is_set() or self._kill_requested
                        )
                        if not should_run_session:
                            self._settlement_started = True
                    if should_run_session:
                        if not self._run_owned_session(stop_event):
                            failed = True
        except Exception as exc:
            failed = True
            with self._lock:
                self._error_code = _safe_error_code(exc)
        finally:
            if bound:
                try:
                    self._interlock.unbind_cycle(stop_event)
                except Exception as exc:
                    failed = True
                    with self._lock:
                        self._error_code = _safe_error_code(exc)
            with self._lock:
                if failed:
                    self._lifecycle = WorkerLifecycle.BLOCKED
                else:
                    self._lifecycle = WorkerLifecycle.STOPPED
                self._thread = None
                self._stop_event = None

    def _run_owned_session(self, stop_event: threading.Event) -> bool:
        with self._session_factory() as session:
            if not _session_is_valid(session):
                raise TypeError("runtime session does not satisfy its protocol")
            failed = False
            try:
                with self._lock:
                    kill_requested = self._kill_requested
                if not stop_event.is_set() or kill_requested:
                    with self._lock:
                        if not stop_event.is_set():
                            self._lifecycle = WorkerLifecycle.RECONCILING
                    session.startup_reconcile(stop_event, self._interlock)
                if not stop_event.is_set():
                    with self._lock:
                        if not stop_event.is_set():
                            self._lifecycle = WorkerLifecycle.RUNNING
                while not stop_event.is_set():
                    session.run_cycle(stop_event, self._interlock)
                    with self._lock:
                        self._cycles_completed += 1
                        self._last_cycle_at = _read_clock(self._clock)
                    if stop_event.wait(self._cadence.total_seconds()):
                        break
            except Exception as exc:
                failed = True
                with self._lock:
                    self._error_code = _safe_error_code(exc)
            finally:
                with self._lock:
                    self._lifecycle = WorkerLifecycle.RECONCILING
                    self._settlement_started = True
                    kill_requested = self._kill_requested
                if kill_requested:
                    if self._kill_control is None:
                        failed = True
                        with self._lock:
                            self._error_code = "KILL_CONTROL_UNAVAILABLE"
                    else:
                        try:
                            # This callback runs on the worker thread, never the
                            # GUI thread, after any in-flight cycle has returned.
                            self._kill_control.request_kill()
                        except Exception:
                            failed = True
                            with self._lock:
                                self._error_code = "KILL_CONTROL_FAILED"
                try:
                    session.stop_reconcile()
                except Exception as exc:
                    failed = True
                    with self._lock:
                        self._error_code = _safe_error_code(exc)
            return not failed


def _session_is_valid(session: object) -> bool:
    return all(
        callable(getattr(session, method, None))
        for method in ("startup_reconcile", "run_cycle", "stop_reconcile")
    )


def _read_clock(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("worker clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _safe_error_code(error: BaseException) -> str:
    supplied = getattr(error, "code", None)
    name = supplied if isinstance(supplied, str) else type(error).__name__
    code = name.upper()
    return code if _SAFE_ERROR.fullmatch(code) is not None else "WORKER_FAILED"
