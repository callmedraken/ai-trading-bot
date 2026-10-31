"""Launch P4's local desktop bot. Start is always a separate GUI action."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_bot.desktop_runtime import (  # noqa: E402
    ArtifactIdentity,
    DesktopSupervisor,
    InspectBundle,
    LifecycleJournal,
    LocalResearchWorker,
)

ACCEPTED_CAMPAIGN = "11d55269-7e13-57aa-a3bf-1e20e486204b"
ACCEPTED_BUNDLE = "b771cf92-a09f-5f18-86d3-e03b65e04fe9"
ACCEPTED_SHA256 = "b883298824f346bca0cf41e83b214f35229f741aab784130602ed7eeea66f66d"
RESEARCH_BUNDLE = (
    Path(r"F:\AI\ai-trading-bot\reports\research\desktop-v1")
    / ACCEPTED_CAMPAIGN
    / "bundle.json"
)
RUNTIME_JOURNAL = Path(r"F:\AI\desktop-bot-state\p4\lifecycle.jsonl")


def build_supervisor() -> DesktopSupervisor:
    """Fixed separate durable state; workers have no shared mutable domain state."""
    job = InspectBundle(
        RESEARCH_BUNDLE,
        ACCEPTED_SHA256,
        ArtifactIdentity(ACCEPTED_CAMPAIGN, ACCEPTED_BUNDLE),
    )
    return DesktopSupervisor(
        LifecycleJournal(RUNTIME_JOURNAL),
        research_factory=lambda: LocalResearchWorker(job),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.parse_args(argv)
    # Import Qt only for an actual launch; --help is a read-only source command.
    from PySide6.QtWidgets import QApplication

    from trading_bot.gui.desktop_service import DesktopGuiService
    from trading_bot.gui.main_window import MainWindow

    application = QApplication([sys.argv[0]])
    application.setApplicationName("AI Trading Bot")
    supervisor = build_supervisor()
    try:
        service = DesktopGuiService(RESEARCH_BUNDLE)
        window = MainWindow(service, desktop_controller=supervisor)
        window.show()
        result = application.exec()
    finally:
        # Also contain non-window Qt quits/startup errors. No force kill and no
        # successful exit claim while a worker is unresolved.
        supervisor.stop()
        closed = supervisor.wait(5)
        if closed:
            supervisor.dispose()
    return result if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
