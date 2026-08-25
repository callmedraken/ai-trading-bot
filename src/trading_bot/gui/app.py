"""Desktop application startup for the optional PySide6 GUI."""

import sys

from PySide6.QtWidgets import QApplication

from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.services import GuiApplicationService


def run(service: GuiApplicationService | None = None) -> int:
    """Run the native GUI shell with a bounded application service."""
    application = QApplication(sys.argv)
    application.setApplicationName("AI Trading Bot")

    window = MainWindow(service or MockGuiApplicationService())
    window.show()
    return application.exec()
