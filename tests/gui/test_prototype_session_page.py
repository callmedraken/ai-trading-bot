"""Offscreen tests for the cached prototype Live Session page."""

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from trading_bot.gui.prototype_session_page import LiveSessionPage
from trading_bot.live_prototype.contracts import PrototypeSnapshot, Reason


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_session_page_emits_only_synthetic_start_and_stop_requests():
    application = _application()
    snapshot = PrototypeSnapshot()
    page = LiveSessionPage(snapshot)
    requests: list[str] = []
    page.start_requested.connect(lambda: requests.append("start"))
    page.stop_requested.connect(lambda: requests.append("stop"))
    application.processEvents()

    assert [button.text() for button in page.findChildren(QPushButton)] == [
        "Start synthetic workers",
        "Stop synthetic workers",
    ]
    assert "never arms execution" in page.findChild(QLabel, "sessionScope").text()
    page.start_button.click()
    page.stop_button.click()
    assert requests == ["start", "stop"]
    assert page._snapshot == snapshot
    page.close()


def test_session_page_updates_facts_and_fits_desktop_width():
    application = _application()
    snapshot = PrototypeSnapshot()
    page = LiveSessionPage(snapshot)
    page.update_snapshot(
        replace(
            snapshot,
            connected=True,
            ready_to_trade=False,
            workers_running=True,
            strategy="filtered-trend-base-ma/v1",
            binding_digest="sha256:binding",
            source_head="abc123",
            signal_as_of="2026-11-03T21:00:00Z",
            signal_fresh=True,
            quote_as_of="2026-11-03T21:01:00Z",
            quote_fresh=False,
            exposure="0",
            owned_quantity=None,
            working_orders=None,
            fills=0,
            entries_used=1,
            exits_used=0,
            reasons=(Reason.STALE_QUOTE,),
        )
    )
    application.processEvents()

    assert page.findChild(QLabel, "session_connected").text() == "Connected"
    assert page.findChild(QLabel, "session_ready_to_trade").text() == "Not ready"
    assert page.findChild(QLabel, "session_workers_running").text() == "Running"
    assert (
        page.findChild(QLabel, "session_strategy").text() == "filtered-trend-base-ma/v1"
    )
    assert page.findChild(QLabel, "session_binding_digest").text() == "sha256:binding"
    assert page.findChild(QLabel, "session_source_head").text() == "abc123"
    assert page.findChild(QLabel, "session_signal_as_of").text() == (
        "2026-11-03T21:00:00Z"
    )
    assert page.findChild(QLabel, "session_signal_fresh").text() == "Fresh"
    assert page.findChild(QLabel, "session_quote_fresh").text() == "Not fresh"
    assert page.findChild(QLabel, "session_exposure").text() == "0"
    assert page.findChild(QLabel, "session_owned_quantity").text() == "Unavailable"
    assert page.findChild(QLabel, "session_working_orders").text() == "Unavailable"
    assert page.findChild(QLabel, "session_fills").text() == "0"
    assert page.findChild(QLabel, "session_entries_used").text() == "1"
    assert page.findChild(QLabel, "session_reasons").text() == "STALE_QUOTE"

    page.resize(1366, 768)
    page.show()
    application.processEvents()
    scroll = page.findChild(QScrollArea, "prototypeSessionScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    page.close()
