"""Focused acceptance for the disarmed application composition."""

from __future__ import annotations

import os
from threading import Event
from threading import enumerate as threads
from time import monotonic, sleep

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from trading_bot.live_prototype.application import (
    ApplicationMode,
    compose_application_service,
)
from trading_bot.live_prototype.application_service import (
    ApplicationIdentity,
    ConnectionState,
    RealDisarmedApplicationService,
    RecoveryState,
    RuntimeObservation,
)
from trading_bot.live_prototype.contracts import (
    Command,
    EffectDisposition,
    Lifecycle,
    Reason,
    ResearchView,
)
from trading_bot.live_prototype.synthetic_service import SyntheticApplicationService

IDENTITY = ApplicationIdentity(
    source_head="a" * 40,
    source_tree="b" * 40,
    configuration_digest="c" * 64,
    evidence_digest="d" * 64,
)


def _wait_for(condition, timeout: float = 3.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.01)
    return condition()


def test_composition_requires_an_explicit_supported_mode_and_identity():
    with pytest.raises(TypeError):
        compose_application_service("SYNTHETIC")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compose_application_service(ApplicationMode.REAL_DISARMED)
    with pytest.raises(ValueError):
        compose_application_service(ApplicationMode.SYNTHETIC, identity=IDENTITY)

    synthetic = compose_application_service(ApplicationMode.SYNTHETIC)
    real = compose_application_service(ApplicationMode.REAL_DISARMED, identity=IDENTITY)
    assert type(synthetic) is SyntheticApplicationService
    assert type(real) is RealDisarmedApplicationService
    assert synthetic.snapshot().mode == "SYNTHETIC"
    assert real.snapshot().mode == "REAL_DISARMED"
    assert not real.snapshot().ready_to_trade


def test_real_disarmed_construction_and_snapshot_are_cached_and_effect_free():
    before = tuple(threads())
    service = compose_application_service(
        ApplicationMode.REAL_DISARMED, identity=IDENTITY
    )
    first = service.snapshot()
    second = service.snapshot()

    assert first.lifecycle is Lifecycle.DISARMED
    assert first.mode == "REAL_DISARMED"
    assert first.source_head == IDENTITY.source_head
    assert not first.connected
    assert not first.ready_to_trade
    assert not first.workers_running
    assert first.binding_digest is None
    assert first.reasons == (
        Reason.SOURCE_ACCEPTANCE_REQUIRED,
        Reason.DATA_NOT_READY,
        Reason.EXIT_CAPABILITY_UNPROVEN,
        Reason.RECONCILIATION_REQUIRED,
    )
    assert first == second
    assert tuple(threads()) == before


@pytest.mark.parametrize("command", (Command.KILL, Command.EXIT))
def test_real_disarmed_mode_rejects_order_mutation_commands(command: Command):
    service = RealDisarmedApplicationService(IDENTITY)
    before = service.snapshot()

    result = service.submit(command)

    assert not result.accepted
    assert result.reason is Reason.EXTERNAL_OPERATOR_REQUIRED
    assert result.disposition is EffectDisposition.NO_EFFECT
    assert service.snapshot() == before


def test_real_disarmed_start_runs_independent_workers_and_stop_joins_both():
    research_entered = Event()
    runtime_entered = Event()
    research_exited = Event()
    runtime_exited = Event()

    def research_worker(stop: Event, _publish) -> None:
        research_entered.set()
        stop.wait()
        research_exited.set()

    def runtime_worker(stop: Event, _publish) -> None:
        runtime_entered.set()
        stop.wait()
        runtime_exited.set()

    service = RealDisarmedApplicationService(
        IDENTITY,
        research_worker=research_worker,
        runtime_worker=runtime_worker,
    )
    try:
        result = service.submit(Command.START)
        assert result.accepted
        assert research_entered.wait(timeout=2)
        assert runtime_entered.wait(timeout=2)
        running = service.snapshot()
        assert running.lifecycle is Lifecycle.RUNNING
        assert running.workers_running
        assert not running.ready_to_trade

        stopped = service.submit(Command.STOP)
        assert stopped.accepted
        assert stopped.reason is Reason.STOP_PENDING
        assert _wait_for(service.shutdown_complete)
        assert research_exited.is_set()
        assert runtime_exited.is_set()
        final = service.snapshot()
        assert final.lifecycle is Lifecycle.STOPPED
        assert not final.workers_running
        assert not final.ready_to_trade
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


def test_connected_reconciled_fresh_observation_stays_disarmed():
    service = RealDisarmedApplicationService(IDENTITY)

    service.publish_runtime(
        RuntimeObservation(
            connection=ConnectionState.CONNECTED,
            recovery=RecoveryState.RECONCILED,
            signal_as_of="2026-11-05T21:00:00Z",
            signal_fresh=True,
            quote_as_of="2026-11-06T16:00:00Z",
            quote_fresh=True,
        )
    )

    snapshot = service.snapshot()
    assert snapshot.connected
    assert snapshot.signal_fresh and snapshot.quote_fresh
    assert not snapshot.ready_to_trade
    assert Reason.SOURCE_ACCEPTANCE_REQUIRED in snapshot.reasons
    assert Reason.EXIT_CAPABILITY_UNPROVEN in snapshot.reasons


def test_invalid_report_cannot_change_real_binding_or_readiness(tmp_path):
    path = tmp_path / "malformed-report.json"
    service = RealDisarmedApplicationService(
        IDENTITY,
        report_reader=lambda _path: ResearchView(
            selected="UNSAFE_SELECTION", live_eligible=True
        ),
    )
    before = service.snapshot()

    assert service.request_report(path)
    assert _wait_for(service.shutdown_complete)

    after = service.snapshot()
    assert after.research.selected == "UNAVAILABLE"
    assert after.research.assumptions == ("Comparison report unavailable",)
    assert after.strategy == before.strategy == "UNSELECTED"
    assert after.binding_digest == before.binding_digest is None
    assert after.source_head == IDENTITY.source_head
    assert not after.ready_to_trade


def test_real_disarmed_window_shows_blockers_and_public_identities():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from trading_bot.live_prototype.window import PrototypeWindow

    app = QApplication.instance() or QApplication([])
    service = RealDisarmedApplicationService(IDENTITY)
    window = PrototypeWindow(service, mode="REAL_DISARMED")
    try:
        banner = window.findChild(QLabel, "prototypeSafetyBanner")
        identities = window.findChild(QLabel, "prototypeIdentityDetails")
        start = window.findChild(QPushButton, "sessionStartDisarmedWorkers")
        stop = window.findChild(QPushButton, "sessionStopDisarmedWorkers")
        assert banner is not None and identities is not None
        assert start is not None and stop is not None
        assert "REAL_DISARMED" in banner.text()
        assert "BLOCKED" in banner.text()
        assert "SOURCE_ACCEPTANCE_REQUIRED" in banner.text()
        assert IDENTITY.source_head in identities.text()
        assert IDENTITY.source_tree in identities.text()
        assert IDENTITY.configuration_digest in identities.text()
        assert IDENTITY.evidence_digest in identities.text()
        assert all(
            button.text() in {"Start disarmed workers", "Stop disarmed workers"}
            for button in window.findChildren(QPushButton)
        )

        window.show()
        app.processEvents()
        start.click()
        assert _wait_for(lambda: service.snapshot().workers_running)
        assert not service.snapshot().ready_to_trade
        stop.click()
        assert _wait_for(service.shutdown_complete)
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)
        window.close()
        app.processEvents()
