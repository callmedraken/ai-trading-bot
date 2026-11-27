"""Runnable, fake-only Architecture 152 Portfolio Manager desktop app."""

# The worktree src root must be installed before importing the local package.
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(_SOURCE_ROOT) not in sys.path:
    # Direct-file launch binds imports to this exact F: worktree, regardless of
    # the shared virtual environment's editable-install target.
    sys.path.insert(0, str(_SOURCE_ROOT))

from trading_bot.portfolio_manager.application_service import (
    PortfolioManagerApplicationService,
)
from trading_bot.portfolio_manager.synthetic_demo import (
    SyntheticDemoObservationSource,
    SyntheticPortfolioPipeline,
    synthetic_account_binding,
)

PM1_STATE_ROOT = Path(r"F:\AI\portfolio-manager-state\pm1")


def build_synthetic_service(
    *, state_root: str | Path = PM1_STATE_ROOT
) -> PortfolioManagerApplicationService:
    """Build the no-provider demo service; no files open until Start."""
    return PortfolioManagerApplicationService(
        account_binding=synthetic_account_binding(),
        state_root=state_root,
        observation_source=SyntheticDemoObservationSource(),
        pipeline=SyntheticPortfolioPipeline(),
    )


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="portfolio-manager-pm1",
        description=(
            "Synthetic, disarmed Portfolio Manager demo. Start and Stop control "
            "local workers only; order dispatch and live provider access are absent."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    parser.parse_args(argv)
    if PM1_STATE_ROOT.drive.casefold() != "f:":
        print("Portfolio Manager state must remain on F:", file=sys.stderr)
        return 2
    try:
        from PySide6.QtWidgets import QApplication

        from trading_bot.portfolio_manager.window import PortfolioManagerWindow
    except ImportError:
        print(
            "PySide6 is required for the Portfolio Manager desktop app", file=sys.stderr
        )
        return 2

    service = build_synthetic_service()
    application = QApplication.instance() or QApplication([])
    application.setApplicationName("AI Trading Bot Portfolio Manager")
    window = PortfolioManagerWindow(service)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
