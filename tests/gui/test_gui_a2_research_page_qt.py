"""Optional Qt construction checks for the GUI-A2 Research page."""
# ruff: noqa: E402

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTableWidget

from trading_bot.gui import (
    ApplicationOverview,
    CompactReportResearchService,
    MarketDataPageState,
    unavailable_market_data_state,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.models import ResearchPageState
from trading_bot.gui.paper_models import PaperPageState, unavailable_paper_state

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "cli"
    / "historical-experiment-compact-report-v1-compact.json"
)


class _GuiA2RecordingService:
    def __init__(self) -> None:
        self.overview_calls = 0
        self.research_calls = 0

    def get_overview(self) -> ApplicationOverview:
        self.overview_calls += 1
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        self.research_calls += 1
        return CompactReportResearchService(FIXTURE).get_research_state()

    def get_paper_state(self) -> PaperPageState:
        return unavailable_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        return unavailable_market_data_state()


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def test_gui_a2_research_page_constructs_bounded_read_only_table() -> None:
    application = _application()
    service = _GuiA2RecordingService()
    window = MainWindow(service)

    window.select_page("research")
    table = window.findChild(QTableWidget, "researchResultsTable")

    assert application.applicationName() is not None
    assert window.current_page_id == "research"
    assert table is not None
    assert table.rowCount() == 4
    assert table.columnCount() == 9
    assert table.item(0, 0).text() == "1"
    assert table.item(0, 1).text().startswith("Grid Base")
    assert table.horizontalHeaderItem(5).text() == "One-way turnover"
    assert table.horizontalHeaderItem(6).text() == "Fills"
    assert service.overview_calls == 1
    assert service.research_calls == 1

    window.select_page("system")

    assert service.overview_calls == 1
    assert service.research_calls == 1
    window.close()
