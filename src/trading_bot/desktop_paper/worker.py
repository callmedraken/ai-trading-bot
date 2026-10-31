"""One cooperative offline worker; SQLite remains the financial authority."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread

from trading_bot.desktop_paper.configuration import (
    PaperEvaluationConfig,
    PaperStrategyEvaluationInput,
    PaperStrategyEvaluator,
)
from trading_bot.desktop_paper.models import PaperCycleInput
from trading_bot.desktop_paper.observations import OpenReplayObservationSource
from trading_bot.desktop_paper.presentation import DesktopPaperSnapshot
from trading_bot.desktop_paper.store import PaperEvaluationStore
from trading_bot.desktop_runtime import (
    Diagnostic,
    Lifecycle,
    WorkerHealth,
    register_cached_health_worker,
)


@register_cached_health_worker
class DesktopPaperWorker:
    """Own a single replay thread, connection and cached immutable snapshots."""

    def __init__(
        self,
        config: PaperEvaluationConfig,
        evaluator: PaperStrategyEvaluator,
        source_factory: Callable[[], OpenReplayObservationSource],
        store_factory: Callable[[], PaperEvaluationStore],
    ) -> None:
        self._config = config
        self._evaluator = evaluator
        self._source_factory = source_factory
        self._store_factory = store_factory
        self._stop = Event()
        self._ready = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._health = WorkerHealth()
        self._snapshot = DesktopPaperSnapshot(
            binding=config.binding, activity="WAITING", diagnostic=""
        )
        self._controls: Queue[tuple[str, bool]] = Queue(maxsize=16)
        self._reconciled = False

    def health(self) -> WorkerHealth:
        with self._lock:
            return self._health

    def snapshot(self) -> DesktopPaperSnapshot:
        with self._lock:
            return self._snapshot

    def _publish(self, state: Lifecycle, **changes: object) -> None:
        with self._lock:
            self._health = WorkerHealth(
                state,
                Diagnostic.WORKER_FAILED
                if state is Lifecycle.FAILED
                else Diagnostic.NONE,
            )
            self._snapshot = replace(self._snapshot, state=state, **changes)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("paper worker already started")
        self._publish(Lifecycle.STARTING)
        self._thread = Thread(target=self._run, name="desktop-paper", daemon=False)
        self._thread.start()
        if not self._ready.wait(1):
            raise RuntimeError("paper worker readiness timeout")
        if self.health().state is Lifecycle.FAILED:
            raise RuntimeError("paper worker initialization failed")

    def request_stop(self) -> None:
        self._stop.set()

    def _control(self, name: str, value: bool) -> bool:
        if type(value) is not bool:
            raise TypeError("boolean control required")
        if self._stop.is_set() or self.health().state is not Lifecycle.RUNNING:
            return False
        try:
            self._controls.put_nowait((name, value))
        except Full:
            return False
        return True

    def latch_kill(self) -> bool:
        return self._control("kill", True)

    def set_new_buys_enabled(self, enabled: bool) -> bool:
        return self._control("new_buys", enabled)

    def _apply_controls(self, store: PaperEvaluationStore) -> None:
        while True:
            try:
                name, value = self._controls.get_nowait()
            except Empty:
                return
            if name == "kill":
                store.latch_kill()
            else:
                store.set_new_buys_enabled(value)

    def _run(self) -> None:
        store = None
        try:
            store = self._store_factory()
            financial = store.load_state()
            source = self._source_factory()
            source.seek_after(financial.cursor_index)
            self._publish(
                Lifecycle.RUNNING,
                financial=financial,
                latest=financial.latest_result,
                activity="WAITING",
                diagnostic="",
            )
            self._ready.set()
            pending_observation = None
            while not self._stop.is_set():
                self._apply_controls(store)
                financial = store.load_state()
                if financial.control.kill_latched:
                    self._publish(
                        Lifecycle.RUNNING, financial=financial, activity="KILL_LATCHED"
                    )
                    self._stop.wait(0.05)
                    continue
                observation = pending_observation or source.next_observation()
                if observation.status == "EXHAUSTED":
                    self._publish(
                        Lifecycle.RUNNING, financial=financial, activity="EXHAUSTED"
                    )
                    self._stop.wait(0.05)
                    continue
                proposal = None
                if not observation.warmup:
                    proposal = self._evaluator.evaluate(
                        PaperStrategyEvaluationInput(
                            self._config.binding,
                            observation.completed_history,
                            observation.executed_at,
                            financial.account,
                        )
                    )
                # Evaluation is pure. Stop observed before admission creates no slot.
                if self._stop.is_set():
                    break
                self._apply_controls(store)
                try:
                    result = store.commit_cycle(
                        PaperCycleInput(
                            execution_session_id=observation.execution_session_id,
                            execution_index=observation.execution_index,
                            symbol=observation.symbol,
                            observation_id=observation.observation_id,
                            completed_history_cutoff=observation.completed_history_cutoff
                            or None,
                            observation_open=observation.observation_open,
                            executed_at=observation.executed_at,
                            proposal=proposal,
                            no_signal_reason=(
                                "WARMUP" if observation.warmup else "NO_SIGNAL"
                            )
                            if proposal is None
                            else None,
                            warmup=observation.warmup,
                        ),
                        stop_requested=self._stop.is_set,
                    )
                except InterruptedError:
                    if not self._stop.is_set():
                        raise
                    break
                pending_observation = (
                    observation if str(result.kind) == "KILL_LATCHED" else None
                )
                self._publish(
                    Lifecycle.RUNNING,
                    financial=store.load_state(),
                    latest=result,
                    activity=str(result.kind),
                    stale=False,
                )
                self._stop.wait(float(self._config.policy.replay_interval_seconds))
            self._publish(Lifecycle.STOPPING, stale=True)
            self._apply_controls(store)
            final = store.load_state()
            self._publish(Lifecycle.STOPPING, financial=final, stale=True)
            self._reconciled = True
        except Exception as error:
            # Failure is terminal for this supervisor generation. A valid durable
            # readback can still prove safe closure; corrupt state cannot.
            if store is not None:
                try:
                    final = store.load_state()
                    self._publish(
                        Lifecycle.STOPPING,
                        financial=final,
                        latest=final.latest_result,
                        stale=True,
                    )
                    self._reconciled = True
                except Exception:
                    self._reconciled = False
            self._publish(
                Lifecycle.FAILED,
                activity="ATTENTION",
                diagnostic="PAPER_RUNTIME_" + type(error).__name__.upper(),
                stale=True,
            )
        finally:
            if store is not None:
                try:
                    store.close()
                except Exception:
                    self._reconciled = False
                    self._publish(
                        Lifecycle.FAILED, diagnostic="PAPER_STORE_CLOSE_FAILED"
                    )
            self._ready.set()

    def reconcile_and_close(self, timeout: float) -> bool:
        if self._thread is None:
            # A supervisor Stop may cancel after construction, before Start.
            # No store or financial operation exists in this worker yet.
            self._reconciled = True
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                return False
        if not self._reconciled:
            return False
        self._publish(Lifecycle.STOPPED, stale=True)
        return True

    def close(self, timeout: float) -> bool:
        return self.reconcile_and_close(timeout)
