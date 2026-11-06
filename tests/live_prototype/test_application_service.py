from threading import Event, get_ident
from threading import enumerate as threads
from time import monotonic, sleep

from trading_bot.live_prototype.application_service import (
    ApplicationIdentity,
    ConnectionState,
    RealDisarmedApplicationService,
    RecoveryState,
    RuntimeObservation,
)
from trading_bot.live_prototype.contracts import (
    Command,
    Lifecycle,
    Reason,
    ResearchView,
)


def _identity() -> ApplicationIdentity:
    return ApplicationIdentity(
        source_head="1" * 40,
        source_tree="2" * 40,
        configuration_digest="3" * 64,
        evidence_digest="4" * 64,
    )


def _wait_for(condition, timeout: float = 2.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.005)
    return condition()


def test_construction_and_snapshot_do_not_start_workers_or_touch_provider():
    calls: list[str] = []

    def research_worker(_stop, _publish):
        calls.append("research")

    def runtime_worker(_stop, _publish):
        calls.append("runtime")

    before = tuple(threads())
    service = RealDisarmedApplicationService(
        _identity(),
        research_worker=research_worker,
        runtime_worker=runtime_worker,
    )
    snapshot = service.snapshot()

    assert snapshot.mode == "REAL_DISARMED"
    assert snapshot.lifecycle is Lifecycle.DISARMED
    assert not snapshot.ready_to_trade
    assert not snapshot.workers_running
    assert snapshot.source_head == "1" * 40
    assert snapshot.binding_digest is None
    assert tuple(threads()) == before
    assert calls == []
    assert all("account" not in line.lower() for line in service.display_details())


def test_start_runs_independent_research_and_runtime_workers_then_stops():
    research_started = Event()
    runtime_started = Event()
    worker_ids: list[int] = []

    def research_worker(stop, publish):
        worker_ids.append(get_ident())
        publish(ResearchView(selected="NONE_QUALIFIES"))
        research_started.set()
        stop.wait()

    def runtime_worker(stop, publish):
        worker_ids.append(get_ident())
        runtime_started.set()
        stop.wait()

    service = RealDisarmedApplicationService(
        _identity(),
        research_worker=research_worker,
        runtime_worker=runtime_worker,
    )
    try:
        result = service.submit(Command.START)
        assert result.accepted
        assert research_started.wait(timeout=2)
        assert runtime_started.wait(timeout=2)
        running = service.snapshot()
        assert running.lifecycle is Lifecycle.RUNNING
        assert running.workers_running
        assert not running.ready_to_trade
        assert running.research.selected == "NONE_QUALIFIES"
        assert running.strategy == "UNSELECTED"
        assert running.binding_digest is None
        assert len(set(worker_ids)) == 2
        assert service.submit(Command.STOP).accepted
        assert _wait_for(service.shutdown_complete)
        assert service.snapshot().lifecycle is Lifecycle.STOPPED
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


def test_connection_and_recovery_are_cached_and_never_grant_readiness():
    published = Event()

    def runtime_worker(stop, publish):
        publish(
            RuntimeObservation(
                connection=ConnectionState.CONNECTED,
                recovery=RecoveryState.RECONCILIATION_REQUIRED,
                reasons=(Reason.DATA_NOT_READY,),
            )
        )
        published.set()
        stop.wait()

    service = RealDisarmedApplicationService(_identity(), runtime_worker=runtime_worker)
    try:
        service.submit(Command.START)
        assert published.wait(timeout=2)
        snapshot = service.snapshot()
        assert snapshot.connected
        assert not snapshot.ready_to_trade
        assert Reason.RECONCILIATION_REQUIRED in snapshot.reasons
        assert "Connection: CONNECTED" in service.display_details()
        assert "Recovery: RECONCILIATION_REQUIRED" in service.display_details()
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


def test_unknown_recovery_blocks_a_new_start():
    published = Event()

    def runtime_worker(stop, publish):
        publish(
            RuntimeObservation(
                connection=ConnectionState.DISCONNECTED,
                recovery=RecoveryState.UNKNOWN,
            )
        )
        published.set()
        stop.wait()

    service = RealDisarmedApplicationService(_identity(), runtime_worker=runtime_worker)
    service.submit(Command.START)
    assert published.wait(timeout=2)
    service.submit(Command.STOP)
    assert _wait_for(service.shutdown_complete)

    rejected = service.submit(Command.START)
    assert not rejected.accepted
    assert rejected.reason is Reason.RECONCILIATION_REQUIRED
    assert not service.snapshot().ready_to_trade


def test_malformed_report_cannot_change_binding_or_identity(tmp_path):
    raw_failure = "private account-like payload"

    def malformed_reader(_path):
        raise ValueError(raw_failure)

    identity = _identity()
    service = RealDisarmedApplicationService(identity, report_reader=malformed_reader)
    assert service.request_report(tmp_path / "not-opened.json")
    assert _wait_for(service.shutdown_complete)
    snapshot = service.snapshot()

    assert snapshot.research.selected == "UNAVAILABLE"
    assert snapshot.research.assumptions == ("Comparison report unavailable",)
    assert snapshot.strategy == "UNSELECTED"
    assert snapshot.binding_digest is None
    assert snapshot.source_head == identity.source_head
    assert not snapshot.ready_to_trade
    assert raw_failure not in "\n".join(service.display_details())


def test_live_eligible_research_view_is_rejected_without_binding_change(tmp_path):
    identity = _identity()
    service = RealDisarmedApplicationService(
        identity,
        report_reader=lambda _path: ResearchView(
            selected="UNTRUSTED", live_eligible=True
        ),
    )
    assert service.request_report(tmp_path / "untrusted-report.json")
    assert _wait_for(service.shutdown_complete)

    snapshot = service.snapshot()
    assert snapshot.research.selected == "UNAVAILABLE"
    assert snapshot.strategy == "UNSELECTED"
    assert snapshot.binding_digest is None
    assert snapshot.source_head == identity.source_head
    assert not snapshot.ready_to_trade
