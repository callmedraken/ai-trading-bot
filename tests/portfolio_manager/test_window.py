# ruff: noqa: E402

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, get_ident
from time import monotonic, sleep

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

from trading_bot.portfolio_manager.application_service import (
    PortfolioManagerApplicationService,
)
from trading_bot.portfolio_manager.synthetic_demo import (
    SyntheticDemoObservationSource,
    SyntheticPortfolioPipeline,
    synthetic_account_binding,
)
from trading_bot.portfolio_manager.window import PortfolioManagerWindow


def _application() -> QApplication:
    current = QApplication.instance()
    return current if current is not None else QApplication([])


def _pump_until(application, condition, timeout: float = 5.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        application.processEvents()
        if condition():
            return True
        sleep(0.005)
    application.processEvents()
    return condition()


def test_window_renders_cached_synthetic_portfolio_and_preview(tmp_path):
    application = _application()
    now = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
    service = PortfolioManagerApplicationService(
        account_binding=synthetic_account_binding(),
        state_root=tmp_path,
        observation_source=SyntheticDemoObservationSource(clock=lambda: now),
        pipeline=SyntheticPortfolioPipeline(),
        monitoring_interval=0.05,
        clock=lambda: now,
    )
    window = PortfolioManagerWindow(service, refresh_ms=50)
    window.show()
    application.processEvents()
    try:
        safety = window.findChild(QLabel, "portfolioManagerSafetyBanner")
        start = window.findChild(QPushButton, "portfolioManagerStart")
        assert safety is not None and "SYNTHETIC / DISARMED" in safety.text()
        assert start is not None and start.isEnabled()
        start.click()
        assert _pump_until(application, lambda: service.snapshot().latest is not None)
        assert _pump_until(
            application,
            lambda: any(
                item.text() == "GLD"
                for item in window._recommendations.findItems(
                    "GLD", Qt.MatchFlag.MatchExactly
                )
            ),
        )
        tables = window.findChildren(QTableWidget)
        assert len(tables) == 4
        assert any(
            item.text() == "3.25"
            for table in tables
            for item in table.findItems("3.25", Qt.MatchFlag.MatchExactly)
        )
        assert any(
            item.text() == "GLD"
            for table in tables
            for item in table.findItems("GLD", Qt.MatchFlag.MatchExactly)
        )
        gld_row = window._recommendations.findItems("GLD", Qt.MatchFlag.MatchExactly)[
            0
        ].row()
        provider_notes = window._recommendations.item(gld_row, 6)
        assert provider_notes is not None
        assert "SYNTHETIC_REFERENCE_UNVALIDATED" in provider_notes.text()
        stop = window.findChild(QPushButton, "portfolioManagerStop")
        assert stop is not None and stop.isEnabled()
        stop.click()
        assert _pump_until(application, service.shutdown_complete)
        assert service.snapshot().observation is not None
        assert service.snapshot().observation.positions[0].quantity == Decimal("3.25")
    finally:
        window.close()
        application.processEvents()
        service.stop()
        assert _pump_until(application, service.shutdown_complete)


def test_close_waits_asynchronously_for_slow_observation_worker(tmp_path):
    application = _application()
    started = Event()
    release = Event()
    ui_thread = get_ident()

    class SlowSource:
        def observe(self):
            started.set()
            release.wait(timeout=4)
            return SyntheticDemoObservationSource().observe()

    service = PortfolioManagerApplicationService(
        account_binding=synthetic_account_binding(),
        state_root=tmp_path,
        observation_source=SlowSource(),
        pipeline=SyntheticPortfolioPipeline(),
        monitoring_interval=0.05,
    )
    window = PortfolioManagerWindow(service, refresh_ms=50)
    window.show()
    application.processEvents()
    try:
        start = window.findChild(QPushButton, "portfolioManagerStart")
        assert start is not None
        start.click()
        assert started.wait(timeout=2)
        before = monotonic()
        window.close()
        assert monotonic() - before < 0.5
        application.processEvents()
        assert window.isVisible()
        assert not service.shutdown_complete()
        assert get_ident() == ui_thread

        release.set()
        assert _pump_until(application, lambda: not window.isVisible())
        assert service.shutdown_complete()
    finally:
        release.set()
        service.stop()
        assert _pump_until(application, service.shutdown_complete)
        if window.isVisible():
            window.close()
            application.processEvents()
