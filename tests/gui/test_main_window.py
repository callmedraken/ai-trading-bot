"""Optional offscreen smoke tests for the GUI-A1 Qt shell."""
# ruff: noqa: E402

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit

from trading_bot.gui import (
    ApplicationOverview,
    MarketDataPageState,
    PaperAccountPageState,
    PaperPageState,
    ResearchPageState,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.main_window import PAGE_IDS, MainWindow
from trading_bot.gui.mock_service import (
    MockGuiApplicationService,
    ResearchReportGuiApplicationService,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "cli"
    / "historical-experiment-compact-report-v1-compact.json"
)


class _RecordingService:
    def __init__(self) -> None:
        self.calls = 0

    def get_overview(self) -> ApplicationOverview:
        self.calls += 1
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        self.calls += 1
        return MockGuiApplicationService().get_research_state()

    def get_paper_state(self) -> PaperPageState:
        self.calls += 1
        return unavailable_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        self.calls += 1
        return unavailable_market_data_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        self.calls += 1
        return unavailable_paper_account_state()

    def get_operator_observability_state(self):
        self.calls += 1
        return unavailable_operator_operations_state()


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


def test_main_window_has_stable_pages_and_navigation_is_presentation_only() -> None:
    application = _application()
    service = _RecordingService()
    window = MainWindow(service)

    assert application.applicationName() is not None
    assert window.page_ids == PAGE_IDS
    assert window.current_page_id == "home"
    assert service.calls == 6

    window.select_page("paper")
    assert window.current_page_id == "paper"
    window.select_page("evidence")
    assert window.current_page_id == "evidence"
    window.select_page("system")
    assert window.current_page_id == "system"
    window.select_page("paper")

    assert window.current_page_id == "paper"
    assert service.calls == 6
    window.close()


def test_main_window_rejects_unknown_page() -> None:
    application = _application()
    window = MainWindow(MockGuiApplicationService())

    assert application.applicationName() is not None
    with pytest.raises(ValueError, match="unknown GUI page"):
        window.select_page("credentials")

    window.close()


def test_main_window_default_operator_text_is_current_and_read_only() -> None:
    window = MainWindow(MockGuiApplicationService())
    texts = [label.text() for label in window.findChildren(QLabel)]

    assert all("gui-a1" not in text.casefold() for text in texts)
    assert all("gui-a2" not in text.casefold() for text in texts)
    assert all("mock data" not in text.casefold() for text in texts)
    assert any("read-only" in text.casefold() for text in texts)
    assert any("no production authority" in text.casefold() for text in texts)
    window.close()


def test_main_window_real_report_operator_text_does_not_claim_mock_shell() -> None:
    window = MainWindow(ResearchReportGuiApplicationService(FIXTURE))
    texts = [
        label.text()
        for label in window.findChildren(QLabel)
        if label.objectName() != "researchPath"
    ]

    assert all("gui-a1" not in text.casefold() for text in texts)
    assert all("gui-a2" not in text.casefold() for text in texts)
    assert all("mock" not in text.casefold() for text in texts)
    assert any(
        "local compact research reports may be displayed" in text for text in texts
    )
    assert any("read-only" in text.casefold() for text in texts)
    assert any("no production authority" in text.casefold() for text in texts)
    window.close()


def test_system_page_uses_already_acquired_state_without_service_reread() -> None:
    application = _application()
    service = _RecordingService()
    window = MainWindow(service)

    assert application.applicationName() is not None
    assert service.calls == 6

    window.select_page("system")

    assert service.calls == 6
    texts = [label.text() for label in window.findChildren(QLabel)]
    assert "System Health & Audit" in texts
    assert any("does not establish production readiness" in text for text in texts)

    window.close()


def test_evidence_page_uses_already_acquired_state_without_service_reread() -> None:
    application = _application()
    service = _RecordingService()
    window = MainWindow(service)

    assert application.applicationName() is not None
    assert service.calls == 6

    window.select_page("evidence")

    assert window.current_page_id == "evidence"
    assert service.calls == 6
    texts = [label.text() for label in window.findChildren(QLabel)]
    assert "Evidence Timeline" in texts
    assert any("not a durable audit log" in text for text in texts)

    search = window.findChild(QLineEdit, "evidenceTimelineSearch")
    source = window.findChild(QComboBox, "evidenceTimelineSourceFilter")
    assert search is not None
    assert source is not None

    search.setText("report")
    source.setCurrentText("Research")
    application.processEvents()

    assert service.calls == 6
    window.close()
