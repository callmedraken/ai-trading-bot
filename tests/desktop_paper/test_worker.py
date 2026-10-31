"""Single worker lifecycle and admission fault tests with temporary stores."""

import time
from dataclasses import FrozenInstanceError
from decimal import Decimal
from threading import Event
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.desktop_paper.store import PaperEvaluationStore
from trading_bot.desktop_paper.worker import DesktopPaperWorker
from trading_bot.desktop_runtime import DesktopSupervisor, Lifecycle, LifecycleJournal


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


def store_factory(path, config, hook=None):
    return lambda: PaperEvaluationStore(
        path,
        account_id=uuid5(NAMESPACE_URL, "worker-test-account"),
        config=config,
        fault_hook=hook,
    )


def test_clean_stop_reopen_restores_account_and_exhaustion(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    factory = store_factory(tmp_path / "paper.sqlite", paper_config)
    first = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, factory
    )
    first.start()
    try:
        wait_for(lambda: first.snapshot().activity == "EXHAUSTED")
        before = first.snapshot().financial
        assert before.cursor_index == 4
        assert first.health().state is Lifecycle.RUNNING
    finally:
        first.request_stop()
        assert first.reconcile_and_close(2)
    second = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, factory
    )
    second.start()
    try:
        wait_for(lambda: second.snapshot().activity == "EXHAUSTED")
        assert second.snapshot().financial == before
        assert second.snapshot().latest == before.latest_result
    finally:
        second.request_stop()
        assert second.reconcile_and_close(2)


def test_stop_during_evaluation_does_not_admit_next_transaction(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    entered, release = Event(), Event()

    class BlockingEvaluator:
        def evaluate(self, value):
            entered.set()
            assert release.wait(3)
            return paper_evaluator.evaluate(value)

    factory = store_factory(tmp_path / "paper.sqlite", paper_config)
    worker = DesktopPaperWorker(
        paper_config, BlockingEvaluator(), paper_source_factory, factory
    )
    worker.start()
    try:
        assert entered.wait(2)
        worker.request_stop()
        release.set()
        assert worker.reconcile_and_close(2)
        assert worker.snapshot().financial.cursor_index == 1
        assert worker.snapshot().financial.account.fills == ()
    finally:
        release.set()
        worker.request_stop()
        worker.close(2)


def test_kill_pauses_without_consuming_future_session(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    factory = store_factory(tmp_path / "paper.sqlite", paper_config)
    store = factory()
    store.latch_kill()
    store.close()
    worker = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, factory
    )
    worker.start()
    try:
        wait_for(lambda: worker.snapshot().activity == "KILL_LATCHED")
        assert worker.snapshot().financial.cursor_index == 0
        assert worker.snapshot().financial.account.fills == ()
    finally:
        worker.request_stop()
        assert worker.close(2)


def test_snapshot_is_cached_and_does_not_open_store(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    calls = []
    factory = store_factory(tmp_path / "paper.sqlite", paper_config)

    def tracked():
        calls.append(True)
        return factory()

    worker = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, tracked
    )
    for _ in range(30):
        assert worker.snapshot().financial is None
        worker.health()
    assert calls == []
    worker.request_stop()
    assert worker.close(0.1)
    assert calls == []


def test_paper_worker_cached_health_uses_no_poll_operation_thread(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
    monkeypatch,
):
    worker = DesktopPaperWorker(
        paper_config,
        paper_evaluator,
        paper_source_factory,
        store_factory(tmp_path / "paper.sqlite", paper_config),
    )
    supervisor = DesktopSupervisor(LifecycleJournal(tmp_path / "lifecycle.jsonl"))

    def forbidden(*args, **kwargs):
        raise AssertionError("cached health started a bounded polling operation")

    monkeypatch.setattr(supervisor, "_call", forbidden)
    try:
        for _ in range(30):
            assert supervisor._health(worker).state is Lifecycle.STOPPED
    finally:
        assert supervisor.dispose()


def test_evaluator_sees_only_immutable_prior_account_and_completed_history(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    seen = []

    class InspectingEvaluator:
        def evaluate(self, value):
            assert value.prior_account is not None
            assert all(
                bar.timestamp < value.execution_timestamp
                for bar in value.completed_history
            )
            with pytest.raises(FrozenInstanceError):
                value.prior_account.cash = Decimal("0")
            with pytest.raises(TypeError):
                value.prior_account.positions[value.binding.symbol] = None
            seen.append(value)
            return paper_evaluator.evaluate(value)

    factory = store_factory(tmp_path / "paper.sqlite", paper_config)
    worker = DesktopPaperWorker(
        paper_config, InspectingEvaluator(), paper_source_factory, factory
    )
    worker.start()
    try:
        wait_for(lambda: worker.snapshot().activity == "EXHAUSTED")
        assert len(seen) == 3
        assert seen[0].prior_account.cash == paper_config.policy.starting_cash
        assert seen[1].prior_account.fills == (
            worker.snapshot().financial.account.fills[0],
        )
    finally:
        worker.request_stop()
        assert worker.close(2)


def test_stop_during_admitted_fill_finishes_one_truthful_transaction(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    entered, release = Event(), Event()
    admitted = []

    def hook(stage):
        if stage == "before_commit":
            admitted.append(stage)
            if len(admitted) == 2:
                entered.set()
                assert release.wait(3)

    factory = store_factory(tmp_path / "paper.sqlite", paper_config, hook)
    worker = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, factory
    )
    worker.start()
    try:
        assert entered.wait(2)
        worker.request_stop()
        release.set()
        assert worker.close(2)
        final = worker.snapshot().financial
        assert final.cursor_index == 2
        assert len(final.account.fills) == 1
        assert final.latest_result.fill == final.account.fills[0]
    finally:
        release.set()
        worker.request_stop()
        worker.close(2)


def test_kill_queued_during_admitted_fill_precedes_next_cycle(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    entered, release = Event(), Event()
    admitted = []

    def hook(stage):
        if stage == "before_commit":
            admitted.append(stage)
            if len(admitted) == 2:
                entered.set()
                assert release.wait(3)

    factory = store_factory(tmp_path / "paper.sqlite", paper_config, hook)
    worker = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, factory
    )
    worker.start()
    try:
        assert entered.wait(2)
        assert worker.latch_kill()
        release.set()
        wait_for(lambda: worker.snapshot().activity == "KILL_LATCHED")
        final = worker.snapshot().financial
        assert final.cursor_index == 2
        assert len(final.account.fills) == 1
        assert final.control.kill_latched
    finally:
        release.set()
        worker.request_stop()
        assert worker.close(2)


def test_kill_during_evaluation_does_not_consume_unadmitted_session(
    tmp_path,
    paper_config,
    paper_source_factory,
    paper_evaluator,
):
    entered, release = Event(), Event()

    class BlockingEvaluator:
        def evaluate(self, value):
            entered.set()
            assert release.wait(3)
            return paper_evaluator.evaluate(value)

    factory = store_factory(tmp_path / "paper.sqlite", paper_config)
    worker = DesktopPaperWorker(
        paper_config, BlockingEvaluator(), paper_source_factory, factory
    )
    worker.start()
    try:
        assert entered.wait(2)
        assert worker.latch_kill()
        release.set()
        wait_for(lambda: worker.snapshot().activity == "KILL_LATCHED")
        assert worker.snapshot().financial.cursor_index == 1
        assert worker.snapshot().financial.account.fills == ()
    finally:
        release.set()
        worker.request_stop()
        assert worker.close(2)
    store = factory()
    store.clear_kill_when_stopped(active_worker=False)
    store.close()
    resumed = DesktopPaperWorker(
        paper_config, paper_evaluator, paper_source_factory, factory
    )
    resumed.start()
    try:
        wait_for(lambda: resumed.snapshot().activity == "EXHAUSTED")
        assert resumed.snapshot().financial.cursor_index == 4
        assert len(resumed.snapshot().financial.account.fills) == 3
    finally:
        resumed.request_stop()
        assert resumed.close(2)
