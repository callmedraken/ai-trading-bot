"""Synthetic GUI/application acceptance for the live prototype."""

import os
from pathlib import Path
from threading import Event
from time import monotonic, sleep

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QPushButton

import trading_bot.gui.research_comparison_service as comparison_service
from trading_bot.live_prototype.contracts import Command, Lifecycle, ResearchView
from trading_bot.live_prototype.synthetic_service import SyntheticApplicationService
from trading_bot.live_prototype.window import PrototypeWindow


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wait_for(application: QApplication, condition, timeout: float = 3.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        application.processEvents()
        if condition():
            return True
        sleep(0.01)
    application.processEvents()
    return condition()


def _show_window(service: SyntheticApplicationService) -> PrototypeWindow:
    window = PrototypeWindow(service)
    window.show()
    _application().processEvents()
    return window


def _open_report(
    window: PrototypeWindow,
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
) -> None:
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args: (str(path), "Comparison report (*.json)"),
    )
    action = next(
        item
        for item in window.menuBar().actions()
        if item.text() == "Open comparison report..."
    )
    action.trigger()


def _stop_and_close(
    application: QApplication,
    service: SyntheticApplicationService,
    window: PrototypeWindow,
) -> None:
    service.submit(Command.STOP)
    _wait_for(application, service.shutdown_complete)
    window.close()
    application.processEvents()


def test_session_buttons_start_and_stop_only_synthetic_workers():
    application = _application()
    service = SyntheticApplicationService()
    window = _show_window(service)
    try:
        start = window.findChild(QPushButton, "sessionStartSyntheticWorkers")
        stop = window.findChild(QPushButton, "sessionStopSyntheticWorkers")
        assert start is not None
        assert stop is not None
        start.click()
        assert _wait_for(
            application,
            lambda: service.snapshot().lifecycle is Lifecycle.RUNNING,
        )
        running = service.snapshot()
        assert running.mode == "SYNTHETIC"
        assert running.workers_running
        assert not running.ready_to_trade

        stop.click()
        assert _wait_for(
            application,
            lambda: (
                service.shutdown_complete()
                and service.snapshot().lifecycle is Lifecycle.STOPPED
            ),
        )
        stopped = service.snapshot()
        assert not stopped.workers_running
        assert not stopped.ready_to_trade
        assert service.shutdown_complete()
    finally:
        _stop_and_close(application, service, window)


def test_close_waits_for_worker_and_delayed_report_reader(monkeypatch, tmp_path: Path):
    application = _application()
    service = SyntheticApplicationService()
    window = _show_window(service)
    entered = Event()
    release = Event()
    report_path = tmp_path / "synthetic-delayed-report.json"
    expected_view = ResearchView(
        selected="NONE_QUALIFIES",
        assumptions=("Synthetic report reader completed",),
        live_eligible=False,
    )

    def delayed_read(_path: Path) -> ResearchView:
        entered.set()
        if not release.wait(timeout=4):
            raise TimeoutError("synthetic test barrier timed out")
        return expected_view

    monkeypatch.setattr(comparison_service, "read_comparison_report", delayed_read)
    before = service.snapshot()
    try:
        start = window.findChild(QPushButton, "sessionStartSyntheticWorkers")
        assert start is not None
        start.click()
        assert _wait_for(application, lambda: service.snapshot().workers_running)

        _open_report(window, monkeypatch, report_path)
        assert entered.wait(timeout=2)
        window.close()
        application.processEvents()
        assert window.isVisible()
        stopping = service.snapshot()
        assert stopping.lifecycle is Lifecycle.STOPPING
        assert not service.shutdown_complete()

        release.set()
        assert _wait_for(application, service.shutdown_complete)
        window._refresh()
        application.processEvents()
        assert not window.isVisible()

        after = service.snapshot()
        assert after.lifecycle is Lifecycle.STOPPED
        assert not after.workers_running
        assert not after.ready_to_trade
        assert after.strategy == before.strategy
        assert after.binding_digest == before.binding_digest
        assert after.research == expected_view
        assert service.shutdown_complete()
    finally:
        release.set()
        _stop_and_close(application, service, window)


def test_report_read_failure_is_fixed_and_does_not_change_live_state(
    monkeypatch, tmp_path: Path
):
    application = _application()
    service = SyntheticApplicationService()
    window = _show_window(service)
    report_path = tmp_path / "synthetic-private-report.json"
    raw_failure = "private report payload and " + str(report_path)

    def failed_read(_path: Path) -> ResearchView:
        raise ValueError(raw_failure)

    monkeypatch.setattr(comparison_service, "read_comparison_report", failed_read)
    before = service.snapshot()
    try:
        _open_report(window, monkeypatch, report_path)
        assert _wait_for(application, service.shutdown_complete)
        window._refresh()

        after = service.snapshot()
        assert after.research.selected == "UNAVAILABLE"
        assert after.research.assumptions == ("Comparison report unavailable",)
        assert after.strategy == before.strategy
        assert after.binding_digest == before.binding_digest
        assert after.ready_to_trade is False
        assert after.mode == "SYNTHETIC"
        displayed = "\n".join(label.text() for label in window.findChildren(QLabel))
        assert "Comparison report unavailable" in displayed
        assert raw_failure not in displayed
        assert str(report_path) not in displayed
        assert page_has_only_synthetic_requests(window)
    finally:
        _stop_and_close(application, service, window)


def page_has_only_synthetic_requests(window: PrototypeWindow) -> bool:
    allowed = {"Start synthetic workers", "Stop synthetic workers"}
    return all(button.text() in allowed for button in window.findChildren(QPushButton))
