"""GUI-A10 Qt Evidence Timeline page tests."""

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QScrollArea

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

    fields = page.findChildren(QLineEdit)
    assert [field.text() for field in fields] == [
        "12345678-1234-1234-1234-123456789abc",
        "a" * 64,
        "report-id",
    ]
    assert all(field.isReadOnly() for field in fields)
    assert page.findChildren(QPushButton) == []

    page.close()


def test_evidence_timeline_minimum_content_width_and_initial_scroll_are_usable(
) -> None:
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
    assert all(field.width() > 100 for field in page.findChildren(QLineEdit))

    page.close()
