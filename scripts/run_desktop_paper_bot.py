"""Launch P5's local simulated-paper view from an accepted research binding."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_bot.desktop_paper.composition import DesktopPaperRuntime  # noqa: E402
from trading_bot.desktop_paper.evaluator import (  # noqa: E402
    FilteredTrendBaseMaEvaluator,
)
from trading_bot.desktop_paper.observations import (  # noqa: E402
    OpenReplayObservationSource,
)
from trading_bot.desktop_paper.research_binding import (  # noqa: E402
    ACCEPTED_FILTERED_TREND_BUNDLE_PATH,
    PaperEvaluationBindingRejected,
    load_accepted_paper_evaluation_config,
)


def build_runtime(
    bundle_path: Path = ACCEPTED_FILTERED_TREND_BUNDLE_PATH,
) -> DesktopPaperRuntime:
    """Compose P5 only from the explicitly validated external bundle."""
    try:
        config = load_accepted_paper_evaluation_config(bundle_path)
    except PaperEvaluationBindingRejected as error:
        diagnostic = str(error).split(":", 1)[0]
        if "PAPER_EVALUATION_SELECTION_REQUIRED" in str(error):
            diagnostic = "PAPER_EVALUATION_SELECTION_REQUIRED"
        return DesktopPaperRuntime(unavailable_diagnostic=diagnostic)

    def source_factory() -> OpenReplayObservationSource:
        from trading_bot.experiments.historical_research_desktop import (
            DesktopResearchStorage,
        )

        return OpenReplayObservationSource.from_storage(
            DesktopResearchStorage.production(),
            symbol=config.binding.symbol,
            minimum_history_bars=50,
        )

    return DesktopPaperRuntime(
        config,
        evaluator=FilteredTrendBaseMaEvaluator(),
        source_factory=source_factory,
    )


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
