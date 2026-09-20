"""Desktop application startup for the optional PySide6 GUI."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.services import GuiApplicationService
from trading_bot.gui.startup_composition import (
    GuiStartupConfiguration,
    ReadOnlyGuiApplicationService,
)


def build_startup_service(
    config: GuiStartupConfiguration | None = None,
) -> GuiApplicationService:
    """Compose the bounded GUI service selected by explicit startup input."""
    return ReadOnlyGuiApplicationService(config or GuiStartupConfiguration())


def _parse_startup_arguments(
    argv: Sequence[str],
) -> tuple[GuiStartupConfiguration, tuple[str, ...]]:
    parser = argparse.ArgumentParser(prog="python -m trading_bot.gui")
    parser.add_argument(
        "--research-report",
        type=Path,
        help="read one local compact historical experiment JSON report",
    )
    parser.add_argument(
        "--market-data-snapshot",
        type=Path,
        help="inspect one explicit local daily market-data snapshot",
    )
    parser.add_argument("--market-data-sha256")
    parser.add_argument("--market-data-byte-length", type=int)
    parser.add_argument(
        "--paper-account-genesis",
        type=Path,
        help="inspect one explicit local GENESIS paper-account checkpoint",
    )
    parser.add_argument("--paper-account-sha256")
    parser.add_argument("--paper-account-byte-length", type=int)
    parser.add_argument("--paper-account-prior", type=Path)
    parser.add_argument("--paper-account-snapshot", type=Path)
    parser.add_argument("--paper-account-cycle-report", type=Path)
    parser.add_argument("--paper-account-successor", type=Path)
    parser.add_argument("--paper-account-successor-sha256")
    parser.add_argument("--paper-account-successor-byte-length", type=int)

    arguments, qt_arguments = parser.parse_known_args(argv)
    try:
        config = GuiStartupConfiguration(
            research_report=arguments.research_report,
            market_data_snapshot=arguments.market_data_snapshot,
            market_data_expected_sha256=arguments.market_data_sha256,
            market_data_expected_byte_length=arguments.market_data_byte_length,
            paper_account_genesis=arguments.paper_account_genesis,
            paper_account_expected_sha256=arguments.paper_account_sha256,
            paper_account_expected_byte_length=arguments.paper_account_byte_length,
            paper_account_prior=arguments.paper_account_prior,
            paper_account_snapshot=arguments.paper_account_snapshot,
            paper_account_cycle_report=arguments.paper_account_cycle_report,
            paper_account_successor=arguments.paper_account_successor,
            paper_account_successor_expected_sha256=(
                arguments.paper_account_successor_sha256
            ),
            paper_account_successor_expected_byte_length=(
                arguments.paper_account_successor_byte_length
            ),
        )
    except (TypeError, ValueError) as error:
        parser.error(str(error))
    return config, tuple(qt_arguments)


def run(
    service: GuiApplicationService | None = None,
    *,
    argv: Sequence[str] | None = None,
) -> int:
    """Run the native GUI shell with a bounded application service."""
    startup_arguments = sys.argv[1:] if argv is None else argv
    config, qt_arguments = _parse_startup_arguments(startup_arguments)
    selected_service = service if service is not None else build_startup_service(config)

    application = QApplication([sys.argv[0], *qt_arguments])
    application.setApplicationName("AI Trading Bot")

    window = MainWindow(selected_service)
    window.show()
    return application.exec()
