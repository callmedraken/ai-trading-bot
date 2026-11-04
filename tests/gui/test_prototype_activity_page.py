"""Headless tests for the live prototype's cached Activity/Health page."""

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

from trading_bot.gui.prototype_activity_page import ActivityHealthPage
from trading_bot.live_prototype.contracts import (
    ActivityItem,
    Lifecycle,
    PrototypeSnapshot,
    Reason,
)


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def test_page_displays_cached_health_freshness_reasons_and_counters() -> None:
    application = _application()
    page = ActivityHealthPage(PrototypeSnapshot())
    snapshot = replace(
        PrototypeSnapshot(),
        lifecycle=Lifecycle.UNKNOWN,
        signal_as_of="2026-11-03T18:15:00Z",
        signal_fresh=True,
        quote_as_of="2026-11-03T18:14:00Z",
        quote_fresh=False,
        working_orders=None,
        fills=2,
        entries_used=1,
        exits_used=0,
        reasons=(Reason.AMBIGUOUS_EFFECT, Reason.RECONCILIATION_REQUIRED),
    )

    page.update_snapshot(snapshot)

    assert page.findChild(QLabel, "prototypeLifecycleValue").text() == "UNKNOWN"
    signal = page.findChild(QLabel, "prototypeSignalFreshnessValue").text()
    quote = page.findChild(QLabel, "prototypeQuoteFreshnessValue").text()
    reasons = page.findChild(QLabel, "prototypeReasonsValue").text()
    assert signal == "Fresh · as of 2026-11-03T18:15:00Z"
    assert quote == "Stale · as of 2026-11-03T18:14:00Z"
    assert reasons == ("Lifecycle UNKNOWN · AMBIGUOUS_EFFECT, RECONCILIATION_REQUIRED")
    assert page.findChild(QLabel, "prototypeWorkingOrdersValue").text() == "Unavailable"
    assert page.findChild(QLabel, "prototypeFillsValue").text() == "2"
    assert page.findChild(QLabel, "prototypeEntriesValue").text() == "1"
    assert page.findChild(QLabel, "prototypeExitsValue").text() == "0"

    page.close()
    application.processEvents()


def test_activity_table_preserves_last_200_items_and_handles_empty_history() -> None:
    application = _application()
    page = ActivityHealthPage(PrototypeSnapshot())
    table = page.findChild(QTableWidget, "prototypeActivityTable")
    empty = page.findChild(QLabel, "prototypeActivityEmpty")
    assert table is not None
    assert empty is not None
    assert table.rowCount() == 0
    assert empty.isHidden() is False

    activity = tuple(
        ActivityItem(index, Reason.NO_ACTION, Lifecycle.STOPPED) for index in range(250)
    )
    page.update_snapshot(replace(PrototypeSnapshot(), activity=activity))

    assert table.rowCount() == 200
    assert table.item(0, 0).text() == "50"
    assert table.item(199, 0).text() == "249"
    assert table.item(0, 1).text() == "STOPPED"
    assert table.item(199, 2).text() == "NO_ACTION"
    assert empty.isHidden() is True

    page.update_snapshot(PrototypeSnapshot())
    assert table.rowCount() == 0
    assert empty.isHidden() is False

    page.close()
    application.processEvents()


def test_page_uses_plain_text_and_does_not_expose_other_snapshot_values() -> None:
    application = _application()
    snapshot = replace(
        PrototypeSnapshot(),
        mode="raw-account-value",
        strategy="raw-secret-value",
        binding_digest="raw-binding-value",
        source_head="raw-source-value",
        signal_as_of="<b>literal timestamp</b>",
    )
    page = ActivityHealthPage(snapshot)
    page.update_snapshot(snapshot)

    labels = page.findChildren(QLabel)
    assert labels
    assert all(label.textFormat() is Qt.TextFormat.PlainText for label in labels)
    assert page.findChild(QLabel, "prototypeSignalFreshnessValue").text() == (
        "Stale · as of <b>literal timestamp</b>"
    )
    visible_text = "\n".join(
        [label.text() for label in labels]
        + [
            page.findChild(QTableWidget, "prototypeActivityTable")
            .horizontalHeaderItem(index)
            .text()
            for index in range(3)
        ]
    )
    assert "raw-account-value" not in visible_text
    assert "raw-secret-value" not in visible_text
    assert "raw-binding-value" not in visible_text
    assert "raw-source-value" not in visible_text
    assert page.findChildren(QPushButton) == []

    page.close()
    application.processEvents()
