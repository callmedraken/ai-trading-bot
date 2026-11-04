from dataclasses import FrozenInstanceError
from threading import enumerate as threads
from time import monotonic

import pytest

from trading_bot.live_prototype.contracts import (
    Command,
    EffectDisposition,
    Lifecycle,
    Reason,
    ResearchView,
)
from trading_bot.live_prototype.synthetic_service import SyntheticApplicationService


def test_construction_and_read_have_no_worker_or_effect(tmp_path):
    before = tuple(threads())
    service = SyntheticApplicationService()
    snapshot = service.snapshot()
    assert snapshot.lifecycle is Lifecycle.DISARMED
    assert not snapshot.ready_to_trade
    assert snapshot.working_orders is snapshot.exposure is None
    assert tuple(threads()) == before
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(FrozenInstanceError):
        snapshot.connected = True


def test_start_stop_and_repeated_start_leave_no_orphan():
    service = SyntheticApplicationService()
    try:
        assert service.submit(Command.START).accepted
        assert service.snapshot().workers_running
        assert not service.submit(Command.START).accepted
        assert not service.snapshot().ready_to_trade
        assert service.submit(Command.STOP).accepted
        deadline = monotonic() + 2
        while not service.shutdown_complete() and monotonic() < deadline:
            pass
        assert service.shutdown_complete()
        assert service.snapshot().lifecycle is Lifecycle.STOPPED
        assert not service.snapshot().workers_running
        assert service.submit(Command.START).accepted
    finally:
        service.submit(Command.STOP)
        deadline = monotonic() + 2
        while not service.shutdown_complete() and monotonic() < deadline:
            pass
        assert service.shutdown_complete()


@pytest.mark.parametrize("command", (Command.KILL, Command.EXIT))
def test_no_effect_command_or_research_view_can_enable_live(command):
    service = SyntheticApplicationService()
    before = service.snapshot()
    result = service.submit(command)
    assert not result.accepted
    assert result.reason is Reason.EXTERNAL_OPERATOR_REQUIRED
    assert result.disposition is EffectDisposition.NO_EFFECT
    assert service.snapshot() == before
    service.set_research_view(ResearchView(selected="NONE_QUALIFIES"))
    assert service.snapshot().strategy == "UNSELECTED"
    assert not service.snapshot().ready_to_trade
    with pytest.raises(ValueError):
        service.set_research_view(ResearchView(live_eligible=True))


def test_events_are_bounded_and_stop_without_start_is_idempotent():
    service = SyntheticApplicationService()
    for _ in range(220):
        assert service.submit(Command.STOP).accepted
    events = service.snapshot().activity
    assert len(events) == 200
    assert events[0].sequence == 21
    assert events[-1].sequence == 220
    with pytest.raises(TypeError):
        service.submit("START")


def test_worker_start_failure_does_not_leave_unjoinable_thread(monkeypatch):
    service = SyntheticApplicationService()

    def fail_start(self):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        "trading_bot.live_prototype.synthetic_service.Thread.start", fail_start
    )
    assert not service.submit(Command.START).accepted
    assert service.shutdown_complete()
    assert service.snapshot().lifecycle is Lifecycle.BLOCKED
