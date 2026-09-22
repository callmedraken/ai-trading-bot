"""GUI-A13 Evidence -> source-page navigation tests."""

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from trading_bot.gui import (
    EvidenceSourcePage,
    EvidenceSourcePageTarget,
    EvidenceTimelineEntry,
    EvidenceTimelineSource,
    MarketDataPageState,
    MarketDataPageStatus,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
    VerifiedMarketSnapshotView,
    build_evidence_source_page_target,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.evidence_timeline_page import EvidenceTimelinePage
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService

_UUID1 = UUID("11111111-1111-1111-1111-111111111111")
_UUID2 = UUID("22222222-2222-2222-2222-222222222222")
_UUID3 = UUID("33333333-3333-3333-3333-333333333333")
_NOW = datetime(2026, 9, 20, 20, 0, tzinfo=UTC)


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


def _entry(source: EvidenceTimelineSource) -> EvidenceTimelineEntry:
    return EvidenceTimelineEntry(
        source,
        "Evidence",
        "identifier",
        None,
        None,
        "Already-presented evidence.",
    )


@pytest.mark.parametrize(
    ("source", "page_id"),
    (
        (EvidenceTimelineSource.RESEARCH, EvidenceSourcePage.RESEARCH),
        (
            EvidenceTimelineSource.PAPER_OPERATION,
            EvidenceSourcePage.PAPER_OPERATION,
        ),
        (EvidenceTimelineSource.PAPER_ACCOUNT, EvidenceSourcePage.PAPER_ACCOUNT),
        (EvidenceTimelineSource.MARKET_DATA, EvidenceSourcePage.MARKET_DATA),
        (EvidenceTimelineSource.OPERATIONS, EvidenceSourcePage.OPERATIONS),
    ),
)
def test_evidence_source_mapping_is_closed_and_exact(
    source: EvidenceTimelineSource,
    page_id: EvidenceSourcePage,
) -> None:
    target = build_evidence_source_page_target(_entry(source))

    assert target == EvidenceSourcePageTarget(source, page_id)
    assert not hasattr(target, "identifier")


def test_source_page_target_rejects_mismatched_pair() -> None:
    with pytest.raises(ValueError):
        EvidenceSourcePageTarget(
            EvidenceTimelineSource.RESEARCH,
            EvidenceSourcePage.MARKET_DATA,
        )


def _research_loaded() -> ResearchPageState:
    row = ResearchResultRow(
        0,
        1,
        "Variant",
        "Parameter=1",
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        0,
        None,
        None,
    )
    return ResearchPageState(
        ResearchReportStatus.LOADED,
        "Loaded.",
        ResearchReportView(
            str(_UUID1),
            str(_UUID2),
            "GRID",
            "Unranked",
            "No metadata",
            (row,),
            "F:\\private\\research.json",
        ),
    )


def _market_verified() -> MarketDataPageState:
    return MarketDataPageState(
        MarketDataPageStatus.VERIFIED,
        "Verified.",
        VerifiedMarketSnapshotView(
            _UUID3,
            date(2026, 9, 20),
            ("SPY",),
            "test-provider",
            "daily-bars",
            "test-feed",
            "a" * 64,
            123,
            _NOW,
            _NOW,
            "b" * 64,
            12,
            "application/json",
        ),
    )


class _NavigationService:
    def __init__(self) -> None:
        self.calls = 0

    def get_overview(self):
        self.calls += 1
        return MockGuiApplicationService().get_overview()

    def get_research_state(self):
        self.calls += 1
        return _research_loaded()

    def get_paper_state(self):
        self.calls += 1
        return unavailable_paper_state()

    def get_paper_account_state(self):
        self.calls += 1
        return unavailable_paper_account_state()

    def get_market_data_state(self):
        self.calls += 1
        return _market_verified()

    def get_operator_observability_state(self):
        self.calls += 1
        return unavailable_operator_operations_state()


def _source_button(
    page: EvidenceTimelinePage,
    heading_prefix: str,
) -> QPushButton:
    for card in page.findChildren(QFrame, "evidenceTimelineCard"):
        title = card.findChild(QLabel, "evidenceTimelineEntryTitle")
        if title is not None and title.text().startswith(heading_prefix):
            button = card.findChild(QPushButton, "evidenceTimelineViewSourceButton")
            if button is None:
                raise AssertionError(f"source button missing for {heading_prefix}")
            return button
    raise AssertionError(f"evidence card missing for {heading_prefix}")


def test_main_window_evidence_navigation_reuses_already_acquired_source_pages() -> None:
    application = _application()
    service = _NavigationService()
    window = MainWindow(service)
    window.resize(920, 620)
    window.show()
    application.processEvents()

    assert service.calls == 6
    window.select_page("evidence")
    page = window.findChild(EvidenceTimelinePage, "evidenceTimelinePage")
    assert page is not None

    research = _source_button(page, "Research — Research report")
    research.click()
    application.processEvents()

    assert window.current_page_id == "research"
    assert service.calls == 6

    window.select_page("evidence")
    market = _source_button(page, "Market Data — Verified market-data snapshot")
    market.click()
    application.processEvents()

    assert window.current_page_id == "market-data"
    assert service.calls == 6

    window.close()
