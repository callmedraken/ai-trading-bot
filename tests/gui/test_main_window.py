"""Optional offscreen smoke tests for the GUI-A1 Qt shell."""
# ruff: noqa: E402

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from trading_bot.gui import ApplicationOverview, ResearchPageState
from trading_bot.gui.main_window import PAGE_IDS, MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService


class _RecordingService:
    def __init__(self) -> None:
        self.calls = 0

    def get_overview(self) -> ApplicationOverview:
        self.calls += 1
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        self.calls += 1
        return MockGuiApplicationService().get_research_state()


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
    assert service.calls == 2

    window.select_page("system")

    assert window.current_page_id == "system"
    assert service.calls == 2
    window.close()


def test_main_window_rejects_unknown_page() -> None:
    application = _application()
    window = MainWindow(MockGuiApplicationService())

    assert application.applicationName() is not None
    with pytest.raises(ValueError, match="unknown GUI page"):
        window.select_page("credentials")

    window.close()
