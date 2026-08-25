"""Optional offscreen smoke tests for the GUI-A1 Qt shell."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from trading_bot.gui.main_window import MainWindow, PAGE_IDS  # noqa: E402
from trading_bot.gui.mock_service import MockGuiApplicationService  # noqa: E402


class _RecordingService:
    def __init__(self) -> None:
        self.calls = 0

    def get_overview(self):
        self.calls += 1
        return MockGuiApplicationService().get_overview()


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


def test_main_window_has_stable_pages_and_navigation_is_presentation_only() -> None:
    _application()
    service = _RecordingService()
    window = MainWindow(service)

    assert window.page_ids == PAGE_IDS
    assert window.current_page_id == "home"
    assert service.calls == 1

    window.select_page("system")

    assert window.current_page_id == "system"
    assert service.calls == 1
    window.close()


def test_main_window_rejects_unknown_page() -> None:
    _application()
    window = MainWindow(MockGuiApplicationService())

    with pytest.raises(ValueError, match="unknown GUI page"):
        window.select_page("credentials")

    window.close()
