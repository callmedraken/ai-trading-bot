"""Launch P5's desktop view. Paper strategy selection is currently required."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_bot.desktop_paper.composition import DesktopPaperRuntime  # noqa: E402


def build_runtime() -> DesktopPaperRuntime:
    """No strategy is accepted: unavailable composition creates no P5 state."""
    return DesktopPaperRuntime()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.parse_args(argv)
    from PySide6.QtWidgets import QApplication

    from trading_bot.gui.desktop_service import DesktopGuiService
    from trading_bot.gui.main_window import MainWindow

    application = QApplication([sys.argv[0]])
    application.setApplicationName("AI Trading Bot")
    runtime = build_runtime()
    try:
        window = MainWindow(
            DesktopGuiService(), desktop_controller=runtime, paper_controller=runtime
        )
        window.show()
        result = application.exec()
    finally:
        runtime.stop()
        closed = runtime.wait(5)
        if closed:
            runtime.dispose()
    return result if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
