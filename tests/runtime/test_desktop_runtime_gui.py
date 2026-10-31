"""P4 controls in the existing Qt shell; all workers/state are synthetic."""

import os
import time
from threading import Event

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from trading_bot.desktop_runtime import (  # noqa: E402
    DesktopSupervisor,
    Lifecycle,
    LifecycleJournal,
    LocalTradingWorker,
)
from trading_bot.gui.desktop_service import DesktopGuiService  # noqa: E402
from trading_bot.gui.main_window import MainWindow  # noqa: E402


def service():
    return DesktopGuiService()


def pump(application, predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


def test_gui_start_stop_routes_through_service_and_remains_responsive(tmp_path):
    app = QApplication.instance() or QApplication([])
    supervisor = DesktopSupervisor(LifecycleJournal(tmp_path / "lifecycle.jsonl"))
    window = MainWindow(service(), desktop_controller=supervisor)
    window.show()
    control = window._desktop_control
    try:
        assert control.start_button.isEnabled() and not control.stop_button.isEnabled()
        control.start_button.click()
        pump(app, lambda: supervisor.status().state is Lifecycle.RUNNING)
        control.refresh()
        assert not control.start_button.isEnabled() and control.stop_button.isEnabled()
        assert "Trading: RUNNING | Research: RUNNING" in control.status_label.text()
        assert "NOT_CONNECTED" in control.status_label.text()
        ticks = []
        timer = QTimer(window)
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start(1)
        pump(app, lambda: len(ticks) >= 5)
        assert supervisor.status().state is Lifecycle.RUNNING
        window.select_page("research")
        assert window.current_page_id == "research"
        control.stop_button.click()
        pump(app, lambda: supervisor.status().can_close)
        control.refresh()
        assert supervisor.status().state is Lifecycle.STOPPED
        assert control.start_button.isEnabled() and not control.stop_button.isEnabled()
        assert window.close()
    finally:
        supervisor.stop()
        supervisor.wait()
        window.close()


def test_gui_close_asynchronously_stops_and_reconciles(tmp_path):
    app = QApplication.instance() or QApplication([])
    entered, release = Event(), Event()

    class SlowTrading(LocalTradingWorker):
        reconciled = False

        def reconcile_and_close(self, timeout):
            entered.set()
            release.wait(2)
            self.reconciled = super().reconcile_and_close(timeout)
            return self.reconciled

    trading = SlowTrading()
    supervisor = DesktopSupervisor(
        LifecycleJournal(tmp_path / "lifecycle.jsonl"), lambda: trading
    )
    window = MainWindow(service(), desktop_controller=supervisor)
    window.show()
    try:
        window._desktop_control.start_button.click()
        pump(app, lambda: supervisor.status().state is Lifecycle.RUNNING)
        assert not window.close()
        pump(app, entered.is_set)
        assert window.isVisible()
        assert not trading.reconciled
        ticks = []
        QTimer.singleShot(0, lambda: ticks.append(True))
        pump(app, lambda: bool(ticks))
        release.set()
        pump(app, lambda: not window.isVisible())
        assert trading.reconciled
        assert supervisor.status().state is Lifecycle.STOPPED
        assert not (tmp_path / "lifecycle.jsonl.lock").exists()
    finally:
        release.set()
        supervisor.stop()
        supervisor.wait()
        window.close()


def test_gui_refuses_close_on_unconfirmed_worker_shutdown(tmp_path):
    app = QApplication.instance() or QApplication([])

    class FailedClose(LocalTradingWorker):
        def reconcile_and_close(self, timeout):
            super().reconcile_and_close(timeout)
            return False

    supervisor = DesktopSupervisor(
        LifecycleJournal(tmp_path / "lifecycle.jsonl"),
        FailedClose,
        close_timeout=0.1,
    )
    window = MainWindow(service(), desktop_controller=supervisor)
    window.show()
    try:
        window._desktop_control.start_button.click()
        pump(app, lambda: supervisor.status().state is Lifecycle.RUNNING)
        assert not window.close()
        pump(app, lambda: supervisor.status().state is Lifecycle.FAILED)
        window._desktop_control.refresh()
        assert window.isVisible() and not window.close()
        assert "CLOSE_TIMEOUT" in window._desktop_control.status_label.text()
        assert not window._desktop_control.start_button.isEnabled()
    finally:
        supervisor.wait()
        window.hide()
        window.deleteLater()
        app.processEvents()


def test_historical_gui_has_no_current_controls(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(service())
    assert not hasattr(window, "_desktop_control")
    assert window.close()
    app.processEvents()


def test_deferred_historical_gui_exports_resolve_to_original_objects():
    from importlib import import_module

    import trading_bot.gui as gui

    for name, owner in gui._LAZY_EXPORTS.items():
        assert name in gui.__all__
        assert getattr(gui, name) is getattr(import_module(owner), name)
    assert set(gui.__all__) <= set(dir(gui))
