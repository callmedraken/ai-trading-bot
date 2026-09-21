"""GUI-A10 Qt Evidence Timeline page tests."""

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
)

from trading_bot.gui import (
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
)
from trading_bot.gui.evidence_timeline_page import EvidenceTimelinePage


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


def _state() -> EvidenceTimelinePageState:
    return EvidenceTimelinePageState(
        "Two bounded evidence entries.",
        (
            EvidenceTimelineEntry(
                EvidenceTimelineSource.MARKET_DATA,
                "Verified market-data snapshot",
                "12345678-1234-1234-1234-123456789abc",
                datetime(2026, 9, 20, 20, 0, tzinfo=UTC),
                "a" * 64,
                "Offline-verified snapshot.",
            ),
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RESEARCH,
                "Research report",
                "report-id",
                None,
                None,
                "Untimed compact report identity.",
            ),
        ),
    )


def test_evidence_timeline_page_is_read_only_and_has_no_effect_controls() -> None:
    application = _application()
    page = EvidenceTimelinePage(_state())
    page.resize(710, 560)
    page.show()
    application.processEvents()

    fields = [field for field in page.findChildren(QLineEdit) if field.isReadOnly()]
    assert [field.text() for field in fields] == [
        "12345678-1234-1234-1234-123456789abc",
        "a" * 64,
        "report-id",
    ]
    assert all(field.isReadOnly() for field in fields)
    assert page.findChildren(QPushButton) == []

    page.close()


def test_evidence_timeline_minimum_content_width_and_initial_scroll_are_usable() -> (
    None
):
    application = _application()
    entries = tuple(
        EvidenceTimelineEntry(
            EvidenceTimelineSource.RESEARCH,
            f"Evidence {index}",
            f"identifier-{index}",
            None,
            None,
            "Untimed presentation evidence.",
        )
        for index in range(8)
    )
    page = EvidenceTimelinePage(EvidenceTimelinePageState("Eight entries.", entries))
    page.resize(710, 500)
    page.show()
    application.processEvents()

    scroll = page.findChild(QScrollArea, "evidenceTimelineScroll")
    assert scroll is not None
    assert scroll.verticalScrollBar().value() == 0
    readonly_fields = [
        field for field in page.findChildren(QLineEdit) if field.isReadOnly()
    ]
    assert all(field.width() > 100 for field in readonly_fields)

    page.close()


def test_evidence_explorer_filters_locally_and_has_distinct_no_match_state() -> None:
    application = _application()
    page = EvidenceTimelinePage(_state())
    page.resize(710, 560)
    page.show()
    application.processEvents()

    search = page.findChild(QLineEdit, "evidenceTimelineSearch")
    source = page.findChild(QComboBox, "evidenceTimelineSourceFilter")
    count = page.findChild(QLabel, "evidenceTimelineFilterCount")

    assert search is not None
    assert source is not None
    assert count is not None
    assert count.text() == "Showing 2 of 2 entries."

    source.setCurrentText("Research")
    application.processEvents()
    assert count.text() == "Showing 1 of 2 entries."
    readonly = [
        field.text()
        for field in page.findChildren(QLineEdit)
        if field.isReadOnly()
    ]
    assert readonly == ["report-id"]

    search.setText("does-not-match")
    application.processEvents()
    assert count.text() == "Showing 0 of 2 entries."
    empty = page.findChild(QLabel, "evidenceTimelineEmpty")
    assert empty is not None
    assert "matches the current local filters" in empty.text()

    page.close()
