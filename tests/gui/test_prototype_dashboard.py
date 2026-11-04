"""Offscreen tests for the cached prototype dashboard."""

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from trading_bot.gui.prototype_dashboard import DashboardPage
from trading_bot.live_prototype.contracts import PrototypeSnapshot, Reason


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_dashboard_shows_cached_facts_and_unavailable_values():
    application = _application()
    snapshot = PrototypeSnapshot()
    page = DashboardPage(snapshot)
    application.processEvents()

    assert page.findChild(QLabel, "dashboard_mode").text() == "SYNTHETIC"
    assert page.findChild(QLabel, "dashboard_lifecycle").text() == "DISARMED"
    assert page.findChild(QLabel, "dashboard_connected").text() == "Disconnected"
    assert page.findChild(QLabel, "dashboard_ready_to_trade").text() == "Not ready"
    assert page.findChild(QLabel, "dashboard_workers_running").text() == "Stopped"
    assert page.findChild(QLabel, "dashboard_binding_digest").text() == "Unavailable"
    assert page.findChild(QLabel, "dashboard_source_head").text() == "Unavailable"
    assert page.findChild(QLabel, "dashboard_exposure").text() == "Unavailable"
    assert page.findChild(QLabel, "dashboard_working_orders").text() == "Unavailable"
    assert page.findChild(QLabel, "dashboard_fills").text() == "Unavailable"
    assert page.findChild(QLabel, "dashboard_entries_used").text() == "0"
    assert page.findChild(QLabel, "dashboard_exits_used").text() == "0"
    assert page.findChild(QLabel, "dashboard_reasons").text() == "SYNTHETIC_ONLY"
    assert page.findChildren(QPushButton) == []
    page.close()


def test_dashboard_update_separates_connection_and_uses_plain_text():
    application = _application()
    snapshot = PrototypeSnapshot()
    page = DashboardPage(snapshot)
    page.update_snapshot(
        replace(
            snapshot,
            connected=True,
            ready_to_trade=False,
            quote_as_of="<quote timestamp>",
            quote_fresh=False,
            reasons=(Reason.STALE_QUOTE,),
        )
    )
    application.processEvents()

    assert page.findChild(QLabel, "dashboard_connected").text() == "Connected"
    assert page.findChild(QLabel, "dashboard_ready_to_trade").text() == "Not ready"
    quote_time = page.findChild(QLabel, "dashboard_quote_as_of")
    assert quote_time.text() == "<quote timestamp>"
    assert quote_time.textFormat() == Qt.TextFormat.PlainText
    assert page.findChild(QLabel, "dashboard_quote_fresh").text() == "Not fresh"
    assert page.findChild(QLabel, "dashboard_reasons").text() == "STALE_QUOTE"

    page.resize(1366, 768)
    page.show()
    application.processEvents()
    scroll = page.findChild(QScrollArea, "prototypeDashboardScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    page.close()
