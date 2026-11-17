"""Fake-only desktop lifecycle checks for the restricted-live application."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Event, Lock
from threading import enumerate as threads
from time import monotonic, sleep

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from trading_bot.live_prototype.application import (
    ApplicationMode,
    compose_application_service,
)
from trading_bot.live_prototype.contracts import (
    Command,
    Lifecycle,
    Reason,
    ResearchView,
    RestrictedLiveStatus,
)
from trading_bot.live_prototype.l43_runtime import L43RuntimeObservation
from trading_bot.live_prototype.restricted_live_application_service import (
    RestrictedLiveApplicationService,
)

_SOURCE_HEAD = "a" * 40
_SOURCE_TREE = "b" * 40


def _wait_for(condition, timeout: float = 3.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.01)
    return condition()


class _FakeRuntime:
    def __init__(
        self,
        status: RestrictedLiveStatus = RestrictedLiveStatus.NO_ACTION,
        *,
        release: Event | None = None,
    ) -> None:
        self.source_head = _SOURCE_HEAD
        self.source_tree = _SOURCE_TREE
        self.status = status
        self.release = release
        self.entered = Event()
        self.may_have_occurred = Event()
        self.reconciliation_started = Event()
        self.reconciled = Event()
        self._lock = Lock()
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.lineage_token = object()
        self.lineages_used: list[object] = []

    def run_cycle(self, stop: Event) -> L43RuntimeObservation:
        del stop  # The runtime completes its current fake reconciliation boundary.
        with self._lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.lineages_used.append(self.lineage_token)
        self.entered.set()
        self.may_have_occurred.set()
        self.reconciliation_started.set()
        try:
            if self.release is not None and not self.release.wait(timeout=4):
                raise TimeoutError("fake reconciliation barrier expired")
            self.reconciled.set()
            return L43RuntimeObservation(self.status, "FAKE_STATUS")
        finally:
            with self._lock:
                self.active -= 1


def _service(
    runtime: _FakeRuntime,
    *,
    research_worker=None,
    report_reader=None,
    interval: float = 60.0,
) -> RestrictedLiveApplicationService:
    return RestrictedLiveApplicationService(
        runtime=runtime,
        research_worker=research_worker,
        report_reader=report_reader,
        cycle_interval_seconds=interval,
    )


def test_construction_is_cached_effect_free_and_pins_runtime_source():
    before = tuple(threads())
    runtime = _FakeRuntime()
    service = _service(runtime)

    first = service.snapshot()
    second = service.snapshot()

    assert first == second
    assert first.lifecycle is Lifecycle.DISARMED
    assert first.mode == "RESTRICTED_LIVE"
    assert first.restricted_live_status is RestrictedLiveStatus.STOPPED
    assert first.source_head == _SOURCE_HEAD
    assert first.source_tree == _SOURCE_TREE
    assert not first.restricted_live_enabled
    assert not first.effect_authority_granted
    assert not first.ready_to_trade
    assert runtime.calls == 0
    assert tuple(threads()) == before


def test_factory_selects_restricted_service_with_source_owned_runtime(monkeypatch):
    from trading_bot.live_prototype import l43_runtime

    runtime = _FakeRuntime()
    calls = []

    def build(repo_root):
        calls.append(repo_root)
        return runtime

    monkeypatch.setattr(l43_runtime, "build_production_l43_runtime", build)
    service = compose_application_service(ApplicationMode.RESTRICTED_LIVE)

    assert type(service) is RestrictedLiveApplicationService
    assert calls == [Path(__file__).resolve().parents[2]]
    assert service.snapshot().source_head == _SOURCE_HEAD
    assert service.snapshot().source_tree == _SOURCE_TREE
    assert runtime.calls == 0


def test_restricted_mode_never_falls_back_when_canonical_composition_fails(
    monkeypatch,
):
    from trading_bot.live_prototype import l43_runtime

    def fail_closed(_repo_root):
        raise RuntimeError("canonical production prerequisites unavailable")

    monkeypatch.setattr(l43_runtime, "build_production_l43_runtime", fail_closed)

    with pytest.raises(RuntimeError, match="canonical production prerequisites"):
        compose_application_service(ApplicationMode.RESTRICTED_LIVE)


def test_start_is_idempotent_stop_finishes_boundary_and_report_runs_independently(
    tmp_path,
):
    release = Event()
    runtime = _FakeRuntime(RestrictedLiveStatus.ENTRY_RECONCILED, release=release)
    research_entered = Event()
    research_stopped = Event()
    expected_report = ResearchView(
        selected="NONE_QUALIFIES",
        assumptions=("Fake report loaded during runtime",),
        live_eligible=False,
    )

    def research_worker(stop: Event, _publish) -> None:
        research_entered.set()
        stop.wait()
        research_stopped.set()

    service = _service(
        runtime,
        research_worker=research_worker,
        report_reader=lambda _path: expected_report,
    )
    try:
        first = service.submit(Command.START)
        assert first.accepted
        assert runtime.entered.wait(timeout=2)
        assert research_entered.wait(timeout=2)

        second = service.submit(Command.START)
        assert second.accepted
        assert runtime.calls == 1
        runtime_workers = [
            worker
            for worker in service._desktop_workers.workers
            if worker.name == "prototype-restricted-live-runtime-worker"
        ]
        assert len(runtime_workers) == 1

        assert service.request_report(tmp_path / "explicit-report.json")
        assert _wait_for(lambda: service.snapshot().research == expected_report)

        stopped = service.submit(Command.STOP)
        assert stopped.accepted
        assert stopped.reason is Reason.STOP_PENDING
        stopping = service.snapshot()
        assert stopping.lifecycle is Lifecycle.STOPPING
        assert not stopping.restricted_live_enabled
        assert not service.shutdown_complete()
        assert runtime.may_have_occurred.is_set()
        assert runtime.reconciliation_started.is_set()
        assert not runtime.reconciled.is_set()

        release.set()
        assert _wait_for(service.shutdown_complete)
        final = service.snapshot()
        assert final.lifecycle is Lifecycle.STOPPED
        assert final.restricted_live_status is RestrictedLiveStatus.ENTRY_RECONCILED
        assert final.restricted_live_reason_code == "FAKE_STATUS"
        assert not final.workers_running
        assert not final.restricted_live_enabled
        assert not final.ready_to_trade
        assert not final.effect_authority_granted
        assert runtime.reconciled.is_set()
        assert research_stopped.is_set()
        assert runtime.calls == 1
        assert runtime.max_active == 1
    finally:
        release.set()
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


@pytest.mark.parametrize(
    "status",
    (
        RestrictedLiveStatus.NO_ACTION,
        RestrictedLiveStatus.ENTRY_PENDING,
        RestrictedLiveStatus.SELL_PENDING,
        RestrictedLiveStatus.ENTRY_RECONCILED,
        RestrictedLiveStatus.SELL_RECONCILED,
        RestrictedLiveStatus.REVIEW_ACCEPTED,
        RestrictedLiveStatus.BLOCKED,
        RestrictedLiveStatus.AUTHORIZATION_MISSING,
        RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED,
        RestrictedLiveStatus.EFFECT_UNKNOWN,
    ),
)
def test_runtime_outcomes_remain_truthful_after_stop(status):
    runtime = _FakeRuntime(status)
    service = _service(runtime)

    try:
        assert service.submit(Command.START).accepted
        assert runtime.entered.wait(timeout=2)
        assert _wait_for(lambda: service.snapshot().restricted_live_status is status)

        assert service.submit(Command.STOP).accepted
        assert _wait_for(service.shutdown_complete)
        snapshot = service.snapshot()
        assert snapshot.lifecycle is Lifecycle.STOPPED
        assert snapshot.restricted_live_status is status
        assert not snapshot.ready_to_trade
        assert not snapshot.effect_authority_granted
        assert runtime.calls == 1
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


def test_restart_reuses_the_composed_runtime_and_existing_lineage():
    runtime = _FakeRuntime()
    service = _service(runtime)

    try:
        assert service.submit(Command.START).accepted
        assert _wait_for(lambda: runtime.calls == 1)
        assert service.submit(Command.STOP).accepted
        assert _wait_for(service.shutdown_complete)

        assert service.submit(Command.START).accepted
        assert _wait_for(lambda: runtime.calls == 2)
        assert runtime.lineages_used == [runtime.lineage_token] * 2
        assert runtime.max_active == 1
        assert service.submit(Command.STOP).accepted
        assert _wait_for(service.shutdown_complete)
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


def test_runtime_exception_is_unknown_and_not_retried():
    class FailingRuntime(_FakeRuntime):
        def run_cycle(self, stop: Event) -> L43RuntimeObservation:
            del stop
            self.calls += 1
            self.entered.set()
            raise RuntimeError("opaque post-effect failure")

    runtime = FailingRuntime()
    service = _service(runtime)

    assert service.submit(Command.START).accepted
    assert runtime.entered.wait(timeout=2)
    assert _wait_for(service.shutdown_complete)
    snapshot = service.snapshot()
    assert snapshot.lifecycle is Lifecycle.BLOCKED
    assert snapshot.restricted_live_status is RestrictedLiveStatus.EFFECT_UNKNOWN
    assert runtime.calls == 1
    assert snapshot.restricted_live_reason_code == "RUNTIME_CYCLE_EXCEPTION"
    assert not snapshot.ready_to_trade
    assert not snapshot.effect_authority_granted


def test_manual_start_after_unknown_reuses_runtime_without_automatic_retry():
    runtime = _FakeRuntime(RestrictedLiveStatus.EFFECT_UNKNOWN)
    service = _service(runtime)

    try:
        assert service.submit(Command.START).accepted
        assert _wait_for(service.shutdown_complete)
        assert runtime.calls == 1
        assert (
            service.snapshot().restricted_live_status
            is RestrictedLiveStatus.EFFECT_UNKNOWN
        )

        runtime.status = RestrictedLiveStatus.BLOCKED
        assert service.submit(Command.START).accepted
        assert _wait_for(lambda: runtime.calls == 2)
        assert service.submit(Command.STOP).accepted
        assert _wait_for(service.shutdown_complete)
        assert runtime.calls == 2
        assert service.snapshot().restricted_live_status is RestrictedLiveStatus.BLOCKED
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)


def test_launcher_sanitizes_restricted_composition_failure_without_fallback(
    monkeypatch, capsys
):
    from trading_bot.live_prototype import l43_runtime
    from trading_bot.live_prototype.application import main

    def fail_closed(_repo_root):
        raise RuntimeError("sensitive local path or git output")

    monkeypatch.setattr(l43_runtime, "build_production_l43_runtime", fail_closed)

    assert main(["--mode", "RESTRICTED_LIVE"]) == 2
    assert capsys.readouterr().err.strip() == (
        "RESTRICTED_LIVE_COMPOSITION_FAILED; no fallback mode selected"
    )


def test_restricted_live_window_shows_lifecycle_separate_from_authority():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from trading_bot.live_prototype.window import PrototypeWindow

    app = QApplication.instance() or QApplication([])
    runtime = _FakeRuntime()
    service = _service(runtime)
    window = PrototypeWindow(service, mode="RESTRICTED_LIVE")
    try:
        banner = window.findChild(QLabel, "prototypeSafetyBanner")
        details = window.findChild(QLabel, "prototypeIdentityDetails")
        start = window.findChild(QPushButton, "sessionStartRestrictedLiveRuntime")
        stop = window.findChild(QPushButton, "sessionStopRestrictedLiveRuntime")
        assert banner is not None and details is not None
        assert start is not None and stop is not None
        assert "RESTRICTED_LIVE" in banner.text()
        assert "effect authority: NOT GRANTED" in banner.text()
        assert "readiness: BLOCKED" in banner.text()
        assert _SOURCE_HEAD in details.text()
        assert _SOURCE_TREE in details.text()
        assert all(
            button.text()
            in {"Start restricted-live runtime", "Stop restricted-live runtime"}
            for button in window.findChildren(QPushButton)
        )

        window.show()
        app.processEvents()
        start.click()
        assert runtime.entered.wait(timeout=2)
        assert _wait_for(
            lambda: (
                service.snapshot().restricted_live_status
                is RestrictedLiveStatus.NO_ACTION
            )
        )
        window._refresh()
        assert "status: NO_ACTION" in banner.text()
        assert "effect authority: NOT GRANTED" in banner.text()
        assert "diagnostic: FAKE_STATUS" in banner.text()
        stop.click()
        assert _wait_for(service.shutdown_complete)
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)
        window.close()
        app.processEvents()
