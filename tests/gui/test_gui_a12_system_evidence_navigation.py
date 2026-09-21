"""GUI-A12 System / Evidence cross-navigation tests."""

import os
from decimal import Decimal
from uuid import UUID

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton

from trading_bot.gui import (
    EvidenceNavigationTarget,
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
    SystemAuditEntryView,
    SystemComponentHealthView,
    SystemComponentStatus,
    SystemHealthPageState,
    SystemHealthStatus,
    build_evidence_navigation_target,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.evidence_timeline_page import EvidenceTimelinePage
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.system_health_page import SystemHealthPage

_UUID1 = UUID("11111111-1111-1111-1111-111111111111")
_UUID2 = UUID("22222222-2222-2222-2222-222222222222")


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


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
            "F:\\private\\research-report.json",
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
        return unavailable_market_data_state()

    def get_operator_observability_state(self):
        self.calls += 1
        return unavailable_operator_operations_state()


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("Research", EvidenceTimelineSource.RESEARCH),
        ("Paper Operation", EvidenceTimelineSource.PAPER_OPERATION),
        ("Paper Account", EvidenceTimelineSource.PAPER_ACCOUNT),
        ("Market Data", EvidenceTimelineSource.MARKET_DATA),
        ("Operations", EvidenceTimelineSource.OPERATIONS),
    ),
)
def test_system_audit_mapping_is_closed_and_exact(
    source: str,
    expected: EvidenceTimelineSource,
) -> None:
    target = build_evidence_navigation_target(
        SystemAuditEntryView(source, "Identity", "identifier")
    )

    assert target == EvidenceNavigationTarget(expected, "identifier")


def test_system_audit_mapping_fails_closed_for_unknown_or_overlong_identity() -> None:
    assert (
        build_evidence_navigation_target(
            SystemAuditEntryView("Unknown", "Identity", "identifier")
        )
        is None
    )
    assert (
        build_evidence_navigation_target(
            SystemAuditEntryView("Research", "Identity", "x" * 201)
        )
        is None
    )

    with pytest.raises(ValueError):
        EvidenceNavigationTarget(EvidenceTimelineSource.RESEARCH, "x" * 201)


def test_system_page_only_offers_navigation_for_mappable_audit_entries() -> None:
    application = _application()
    state = SystemHealthPageState(
        SystemHealthStatus.READ_ONLY_READY,
        "Read-only.",
        "Local",
        "Research",
        (
            SystemComponentHealthView(
                "research",
                "Research",
                SystemComponentStatus.AVAILABLE,
                "Available.",
            ),
        ),
        (
            SystemAuditEntryView("Research", "Report ID", str(_UUID1)),
            SystemAuditEntryView("Unknown", "Identity", "unmapped"),
        ),
    )
    page = SystemHealthPage(state)
    page.show()
    application.processEvents()

    buttons = page.findChildren(QPushButton, "systemHealthViewEvidenceButton")
    assert len(buttons) == 1
    assert buttons[0].text() == "View in Evidence"

    page.close()


def test_evidence_navigation_target_matches_exact_identifier_only() -> None:
    application = _application()
    state = EvidenceTimelinePageState(
        "Two entries.",
        (
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RESEARCH,
                "Report",
                "target-id",
                None,
                None,
                "Exact target.",
            ),
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RESEARCH,
                "Experiment",
                "other-id",
                None,
                None,
                "Mentions target-id but is not the target identity.",
            ),
        ),
    )
    page = EvidenceTimelinePage(state)
    page.show()
    application.processEvents()

    page.show_navigation_target(
        EvidenceNavigationTarget(EvidenceTimelineSource.RESEARCH, "target-id")
    )
    application.processEvents()

    readonly = [
        field.text() for field in page.findChildren(QLineEdit) if field.isReadOnly()
    ]
    assert readonly == ["target-id"]

    page.close()


def test_main_window_system_navigation_reuses_existing_evidence_state() -> None:
    application = _application()
    service = _NavigationService()
    window = MainWindow(service)
    window.resize(920, 620)
    window.show()
    application.processEvents()

    assert service.calls == 6
    window.select_page("system")
    buttons = window.findChildren(QPushButton, "systemHealthViewEvidenceButton")
    assert len(buttons) == 2

    buttons[0].click()
    application.processEvents()

    assert window.current_page_id == "evidence"
    assert service.calls == 6

    source = window.findChild(QComboBox, "evidenceTimelineSourceFilter")
    search = window.findChild(QLineEdit, "evidenceTimelineSearch")
    assert source is not None
    assert search is not None
    assert source.currentText() == "Research"
    assert search.text() == str(_UUID1)

    readonly = [
        field.text() for field in window.findChildren(QLineEdit) if field.isReadOnly()
    ]
    assert str(_UUID1) in readonly
    assert str(_UUID2) not in readonly

    window.close()
