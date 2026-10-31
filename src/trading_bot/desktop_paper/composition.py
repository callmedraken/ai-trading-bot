"""Bounded desktop composition. Strategy selection has no production default."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Lock, Thread
from uuid import UUID

from trading_bot.desktop_paper.configuration import (
    PaperEvaluationConfig,
    PaperStrategyEvaluator,
)
from trading_bot.desktop_paper.models import PaperRuntimePolicy
from trading_bot.desktop_paper.observations import OpenReplayObservationSource
from trading_bot.desktop_paper.presentation import DesktopPaperSnapshot
from trading_bot.desktop_paper.store import PaperEvaluationStore
from trading_bot.desktop_paper.worker import DesktopPaperWorker
from trading_bot.desktop_runtime import (
    DesktopStatus,
    DesktopSupervisor,
    Diagnostic,
    Lifecycle,
    LifecycleJournal,
    LocalResearchWorker,
    Worker,
    WorkerHealth,
)

PAPER_DATABASE = Path(r"F:\AI\desktop-bot-state\p5\simulated-paper.sqlite")
PAPER_LIFECYCLE = Path(r"F:\AI\desktop-bot-state\p5\lifecycle.jsonl")
PAPER_ACCOUNT_ID = UUID("ace7bce2-31eb-5b9a-a6c2-04fcced0570f")


class DesktopPaperRuntime:
    """Qt-facing cached controller; financial connections never reach Qt."""

    def __init__(
        self,
        config: PaperEvaluationConfig | None = None,
        *,
        evaluator: PaperStrategyEvaluator | None = None,
        source_factory: Callable[[], OpenReplayObservationSource] | None = None,
        database: Path = PAPER_DATABASE,
        lifecycle: Path = PAPER_LIFECYCLE,
        account_id: UUID = PAPER_ACCOUNT_ID,
        research_factory: Callable[[], Worker] = LocalResearchWorker,
    ) -> None:
        self._lock = Lock()
        self._worker: DesktopPaperWorker | None = None
        self._snapshot = DesktopPaperSnapshot()
        self._control_pending = False
        self._supervisor: DesktopSupervisor | None = None
        self._store_factory: Callable[[], PaperEvaluationStore] | None = None
        # Selection-required is a usable unavailable view and creates no files.
        if config is None:
            return
        if type(config) is not PaperEvaluationConfig:
            raise TypeError("exact paper evaluation config required")
        if (
            type(config.policy) is not PaperRuntimePolicy
            or config.policy != PaperRuntimePolicy()
        ):
            raise ValueError("PAPER_RUNTIME_POLICY_SUCCESSOR_REQUIRED")
        if evaluator is None or source_factory is None:
            raise ValueError(
                "explicit strategy evaluator and observation source required"
            )
        self._snapshot = DesktopPaperSnapshot(
            binding=config.binding, activity="WAITING", diagnostic=""
        )
        self._store_factory = lambda: PaperEvaluationStore(
            database, account_id=account_id, config=config
        )

        def trading_factory() -> DesktopPaperWorker:
            worker = DesktopPaperWorker(
                config, evaluator, source_factory, self._store_factory
            )
            with self._lock:
                self._worker = worker
            return worker

        self._supervisor = DesktopSupervisor(
            LifecycleJournal(lifecycle),
            trading_factory=trading_factory,
            research_factory=research_factory,
        )

    def snapshot(self) -> DesktopPaperSnapshot:
        with self._lock:
            worker = self._worker
            cached = self._snapshot
        return worker.snapshot() if worker is not None else cached

    def status(self) -> DesktopStatus:
        if self._supervisor is not None:
            status = self._supervisor.status()
            with self._lock:
                pending = self._control_pending
            return replace(status, can_start=status.can_start and not pending)
        return DesktopStatus(
            Lifecycle.STOPPED,
            0,
            WorkerHealth(),
            WorkerHealth(),
            Diagnostic.NONE,
            False,
            False,
            True,
        )

    def start(self) -> bool:
        with self._lock:
            if self._control_pending or self._supervisor is None:
                return False
            return self._supervisor.start()

    def stop(self) -> None:
        if self._supervisor is not None:
            self._supervisor.stop()

    def wait(self, timeout: float = 5) -> bool:
        return self._supervisor is None or self._supervisor.wait(timeout)

    def dispose(self) -> bool:
        with self._lock:
            if self._control_pending:
                return False
        return self._supervisor is None or self._supervisor.dispose()

    def latch_kill(self) -> bool:
        with self._lock:
            worker = self._worker
        return worker is not None and worker.latch_kill()

    def set_new_buys_enabled(self, enabled: bool) -> bool:
        with self._lock:
            worker = self._worker
        return worker is not None and worker.set_new_buys_enabled(enabled)

    def clear_kill(self) -> bool:
        """Admit one asynchronous stopped-state transaction; Start is interlocked."""
        with self._lock:
            if (
                self._control_pending
                or self._supervisor is None
                or self._store_factory is None
                or self._supervisor.status().state is not Lifecycle.STOPPED
                or not self._supervisor.status().can_start
            ):
                return False
            self._control_pending = True

        def clear() -> None:
            store = None
            try:
                store = self._store_factory()
                store.clear_kill_when_stopped(active_worker=False)
                financial = store.load_state()
                cached = self.snapshot()
                with self._lock:
                    self._snapshot = replace(cached, financial=financial, stale=True)
                    self._worker = None
            except Exception:
                cached = self.snapshot()
                with self._lock:
                    self._snapshot = replace(
                        cached, diagnostic="PAPER_CONTROL_FAILED", stale=True
                    )
                    self._worker = None
            finally:
                try:
                    if store is not None:
                        store.close()
                except Exception:
                    with self._lock:
                        self._snapshot = replace(
                            self._snapshot,
                            diagnostic="PAPER_STORE_CLOSE_FAILED",
                            stale=True,
                        )
                        self._worker = None
                finally:
                    with self._lock:
                        self._control_pending = False

        Thread(target=clear, name="desktop-paper-control", daemon=False).start()
        return True
