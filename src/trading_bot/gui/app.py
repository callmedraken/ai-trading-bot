"""Desktop application startup for the optional PySide6 GUI."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import (
    MockGuiApplicationService,
    ResearchReportGuiApplicationService,
)
from trading_bot.gui.services import GuiApplicationService


def build_startup_service(
    research_report: Path | None,
) -> GuiApplicationService:
    """Compose the bounded GUI service selected by explicit startup input."""
    if research_report is None:
        return MockGuiApplicationService()
    return ResearchReportGuiApplicationService(research_report)


def _parse_startup_arguments(
    argv: Sequence[str],
) -> tuple[Path | None, tuple[str, ...]]:
    parser = argparse.ArgumentParser(prog="python -m trading_bot.gui")
    parser.add_argument(
        "--research-report",
        type=Path,
        help="read one local compact historical experiment JSON report",
    )
    arguments, qt_arguments = parser.parse_known_args(argv)
    return arguments.research_report, tuple(qt_arguments)


def run(
    service: GuiApplicationService | None = None,
    *,
    argv: Sequence[str] | None = None,
) -> int:
    """Run the native GUI shell with a bounded application service."""
    startup_arguments = sys.argv[1:] if argv is None else argv
    research_report, qt_arguments = _parse_startup_arguments(startup_arguments)
    selected_service = (
        service if service is not None else build_startup_service(research_report)
    )

    application = QApplication([sys.argv[0], *qt_arguments])
    application.setApplicationName("AI Trading Bot")

    window = MainWindow(selected_service)
    window.show()
    return application.exec()
