from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event, get_ident
from time import monotonic, sleep

from trading_bot.portfolio_manager.application_service import (
    PipelineEvaluation,
    PortfolioManagerApplicationService,
    ServiceLifecycle,
    WorkerHealth,
)
from trading_bot.portfolio_manager.models import PortfolioObservation
from trading_bot.portfolio_manager.synthetic_demo import (
    SyntheticDemoObservationSource,
    SyntheticPortfolioPipeline,
    synthetic_account_binding,
)


def _wait_for(condition, timeout: float = 4.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.005)
    return condition()


def _service(state_root, *, clock=None, source=None, pipeline=None, interval=0.05):
    return PortfolioManagerApplicationService(
        account_binding=synthetic_account_binding(),
        state_root=state_root,
        observation_source=source or SyntheticDemoObservationSource(clock=clock),
        pipeline=pipeline or SyntheticPortfolioPipeline(),
        monitoring_interval=interval,
        clock=clock,
    )


def test_start_stop_uses_independent_cached_workers_and_preserves_holdings(tmp_path):
    now = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
    service = _service(tmp_path, clock=lambda: now)
    assert not service.state_path.exists()
    assert service.snapshot().lifecycle is ServiceLifecycle.STOPPED

    try:
        assert service.start()
        assert not service.start()
        assert _wait_for(lambda: service.snapshot().latest is not None)
        before = service.snapshot()
        assert before.observation is not None
        assert before.monitor_health is WorkerHealth.RUNNING
        assert before.research_health is WorkerHealth.RUNNING
        assert before.observation.coverage.order_scope.value == "SYNTHETIC_COMPLETE"
        assert len(before.observation.positions) == 2
        assert before.history
        assert service.state_path.exists()

        service.stop()
        assert _wait_for(service.shutdown_complete)
        after = service.snapshot()
        assert after.lifecycle is ServiceLifecycle.STOPPED
        assert after.observation is not None
        assert after.observation.positions == before.observation.positions
    finally:
        service.stop()
        assert _wait_for(service.shutdown_complete)


def test_stop_drops_analysis_that_has_not_reached_preview_admission(tmp_path):
    started = Event()
    release = Event()

    class DelayedPipeline:
        def __call__(self, observation, *, decision_at) -> PipelineEvaluation:
            started.set()
            release.wait(timeout=3)
            return SyntheticPortfolioPipeline()(observation, decision_at=decision_at)

    service = _service(tmp_path, pipeline=DelayedPipeline())
    try:
        assert service.start()
        assert started.wait(timeout=2)
        before = monotonic()
        service.stop()
        assert monotonic() - before < 0.5
        assert not service.shutdown_complete()
        release.set()
        assert _wait_for(service.shutdown_complete)
        assert service.snapshot().history == ()
    finally:
        release.set()
        service.stop()
        assert _wait_for(service.shutdown_complete)


def test_newer_monitor_snapshot_discards_stale_pipeline_completion(tmp_path):
    now = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
    initial = SyntheticDemoObservationSource(clock=lambda: now).observe()
    first_started = Event()
    release_first = Event()
    second_observed = Event()

    changed_position = replace(
        initial.positions[0],
        quantity=initial.positions[0].quantity + 1,
        available_to_sell=initial.positions[0].available_to_sell + 1,
    )
    newer = replace(
        initial,
        positions=(changed_position, initial.positions[1]),
    )

    class SequenceSource:
        calls = 0

        def observe(self) -> PortfolioObservation:
            self.calls += 1
            if self.calls == 1:
                return initial
            second_observed.set()
            return newer

    class BlockFirstPipeline:
        calls = 0

        def __call__(self, observation, *, decision_at) -> PipelineEvaluation:
            self.calls += 1
            if self.calls == 1:
                first_started.set()
                release_first.wait(timeout=3)
            return SyntheticPortfolioPipeline()(observation, decision_at=decision_at)

    source = SequenceSource()
    pipeline = BlockFirstPipeline()
    service = _service(
        tmp_path,
        clock=lambda: now,
        source=source,
        pipeline=pipeline,
        interval=0.02,
    )
    try:
        assert service.start()
        assert first_started.wait(timeout=2)
        assert second_observed.wait(timeout=2)
        release_first.set()
        assert _wait_for(
            lambda: (
                service.snapshot().latest is not None
                and service.snapshot().latest.portfolio_snapshot_id == newer.snapshot_id
            )
        )
        snapshot = service.snapshot()
        assert len(snapshot.history) == 1
        assert snapshot.history[0].stored.snapshot_id == newer.snapshot_id
        assert snapshot.history[0].stored.snapshot_id != initial.snapshot_id
    finally:
        release_first.set()
        service.stop()
        assert _wait_for(service.shutdown_complete)


def test_restart_same_financial_input_does_not_duplicate_a_completed_intent(tmp_path):
    first_time = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
    second_time = first_time + timedelta(minutes=1)
    first = _service(tmp_path, clock=lambda: first_time)
    second = _service(tmp_path, clock=lambda: second_time)
    try:
        assert first.start()
        assert _wait_for(lambda: first.snapshot().latest is not None)
        first_result = first.snapshot().history[0].stored
        first.stop()
        assert _wait_for(first.shutdown_complete)

        assert second.start()
        assert _wait_for(lambda: second.snapshot().latest is not None)
        after_restart = second.snapshot()
        assert len(after_restart.history) == 1
        assert after_restart.history[0].stored == first_result
        assert after_restart.history[0].stored.intent_key == first_result.intent_key
    finally:
        first.stop()
        second.stop()
        assert _wait_for(first.shutdown_complete)
        assert _wait_for(second.shutdown_complete)


def test_cached_snapshot_reads_do_not_start_workers_or_create_state(tmp_path):
    calls = {"observe": 0, "pipeline": 0}

    class Source:
        def observe(self):
            calls["observe"] += 1
            return SyntheticDemoObservationSource().observe()

    class Pipeline:
        def __call__(self, observation, *, decision_at):
            calls["pipeline"] += 1
            return SyntheticPortfolioPipeline()(observation, decision_at=decision_at)

    service = _service(tmp_path, source=Source(), pipeline=Pipeline())
    before_thread = get_ident()
    for _ in range(5):
        snapshot = service.snapshot()
        assert snapshot.lifecycle is ServiceLifecycle.STOPPED
    assert calls == {"observe": 0, "pipeline": 0}
    assert not service.state_path.exists()
    assert get_ident() == before_thread
