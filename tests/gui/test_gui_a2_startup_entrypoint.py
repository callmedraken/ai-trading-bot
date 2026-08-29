"""Focused normal-entrypoint composition checks for GUI-A2."""
# ruff: noqa: E402

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from trading_bot.gui import ResearchReportStatus, app

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "cli"
    / "historical-experiment-compact-report-v1-compact.json"
)


def test_gui_a2_normal_startup_composes_explicit_report_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_states = []

    class _Application:
        def __init__(self, argv: list[str]) -> None:
            assert "--research-report" not in argv

        def setApplicationName(self, name: str) -> None:
            assert name == "AI Trading Bot"

        def exec(self) -> int:
            return 0

    class _Window:
        def __init__(self, service) -> None:  # type: ignore[no-untyped-def]
            captured_states.append(service.get_research_state())

        def show(self) -> None:
            return None

    monkeypatch.setattr(app, "QApplication", _Application)
    monkeypatch.setattr(app, "MainWindow", _Window)

    result = app.run(argv=("--research-report", str(FIXTURE)))

    assert result == 0
    assert len(captured_states) == 1
    assert captured_states[0].status is ResearchReportStatus.LOADED
    assert captured_states[0].report is not None
    assert captured_states[0].report.row_count == 4


def test_gui_a2_startup_defaults_and_missing_path_are_bounded(tmp_path: Path) -> None:
    preview = app.build_startup_service(None).get_research_state()
    missing = app.build_startup_service(
        tmp_path / "gui-a2-missing-startup-report.json"
    ).get_research_state()

    assert preview.status is ResearchReportStatus.UNAVAILABLE
    assert missing.status is ResearchReportStatus.UNAVAILABLE
    assert preview == missing
