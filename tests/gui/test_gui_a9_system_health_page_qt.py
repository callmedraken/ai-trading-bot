"""GUI-A9 Qt System Health page tests."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from trading_bot.gui import (
    SystemAuditEntryView,
    SystemComponentHealthView,
    SystemComponentStatus,
    SystemHealthPageState,
    SystemHealthStatus,
)
from trading_bot.gui.system_health_page import SystemHealthPage


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


def _state() -> SystemHealthPageState:
    return SystemHealthPageState(
        SystemHealthStatus.READ_ONLY_READY,
        "No explicit blocked component is present; this is not production readiness.",
        "Local read-only GUI",
        "Research",
        (
            SystemComponentHealthView(
                "research",
                "Research",
                SystemComponentStatus.AVAILABLE,
                "One explicit historical report is loaded read-only.",
            ),
            SystemComponentHealthView(
                "operations",
                "Operations",
                SystemComponentStatus.UNAVAILABLE,
                "Production observability is not connected.",
            ),
        ),
        (
            SystemAuditEntryView(
                "Market Data",
                "Snapshot ID",
                "12345678-1234-1234-1234-123456789abc",
                "a" * 64,
            ),
        ),
    )


def test_system_health_page_is_read_only_and_exposes_selectable_audit_values() -> None:
    application = _application()
    page = SystemHealthPage(_state())
    page.resize(710, 560)
    page.show()
    application.processEvents()

    fields = page.findChildren(QLineEdit)
    assert len(fields) == 2
    assert all(field.isReadOnly() for field in fields)
    assert fields[0].text() == "12345678-1234-1234-1234-123456789abc"
    assert fields[1].text() == "a" * 64
    assert page.findChildren(QPushButton) == []

    page.close()


def test_system_health_page_minimum_content_width_remains_usable() -> None:
    application = _application()
    page = SystemHealthPage(_state())
    page.resize(710, 500)
    page.show()
    application.processEvents()

    fields = page.findChildren(QLineEdit)
    assert all(field.width() > 100 for field in fields)
    assert all(field.isReadOnly() for field in fields)

    page.close()
