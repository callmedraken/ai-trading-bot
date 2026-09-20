"""Focused normal-entrypoint composition checks for GUI-A2."""
# ruff: noqa: E402

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from trading_bot.gui import (
    GuiStartupConfiguration,
    OperatorOperationsPageStatus,
    ResearchReportStatus,
    app,
)

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
        GuiStartupConfiguration(
            research_report=tmp_path / "gui-a2-missing-startup-report.json"
        )
    ).get_research_state()

    assert preview.status is ResearchReportStatus.UNAVAILABLE
    assert missing.status is ResearchReportStatus.UNAVAILABLE
    assert preview == missing


def test_gui_startup_never_invokes_production_operator_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.gui.operator_strategy_preview as preview_module
    import trading_bot.runtime.operator_observability_snapshot as snapshot_module
    from trading_bot.strategies import MovingAverageCrossoverStrategy

    def _unexpected_production_call():
        raise AssertionError("GUI startup must not invoke production O2")

    monkeypatch.setattr(
        snapshot_module,
        "read_personal_desktop_operator_observability_snapshot",
        _unexpected_production_call,
    )
    monkeypatch.setattr(
        preview_module,
        "evaluate_operator_strategy_preview",
        _unexpected_production_call,
    )
    monkeypatch.setattr(
        MovingAverageCrossoverStrategy, "evaluate", _unexpected_production_call
    )
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
            captured_states.append(service.get_operator_observability_state())

        def show(self) -> None:
            return None

    monkeypatch.setattr(app, "QApplication", _Application)
    monkeypatch.setattr(app, "MainWindow", _Window)

    assert app.run(argv=()) == 0
    assert len(captured_states) == 1
    assert captured_states[0].status is OperatorOperationsPageStatus.UNAVAILABLE

def test_gui_a8_parser_builds_explicit_read_only_configuration() -> None:
    config, qt_arguments = app._parse_startup_arguments(
        (
            "--research-report",
            str(FIXTURE),
            "--market-data-snapshot",
            "snapshot.json",
            "--market-data-sha256",
            "a" * 64,
            "--market-data-byte-length",
            "123",
            "--paper-account-genesis",
            "genesis.json",
            "--paper-account-sha256",
            "b" * 64,
            "--paper-account-byte-length",
            "456",
            "-platform",
            "offscreen",
        )
    )

    assert config == GuiStartupConfiguration(
        research_report=FIXTURE,
        market_data_snapshot=Path("snapshot.json"),
        market_data_expected_sha256="a" * 64,
        market_data_expected_byte_length=123,
        paper_account_genesis=Path("genesis.json"),
        paper_account_expected_sha256="b" * 64,
        paper_account_expected_byte_length=456,
    )
    assert qt_arguments == ("-platform", "offscreen")


def test_gui_a8_partial_successor_configuration_fails_before_qt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_qt(*args, **kwargs):
        raise AssertionError("invalid GUI-A8 configuration must fail before Qt")

    monkeypatch.setattr(app, "QApplication", _unexpected_qt)

    with pytest.raises(SystemExit) as error:
        app.run(
            argv=(
                "--paper-account-prior",
                "prior.json",
                "--paper-account-successor",
                "successor.json",
            )
        )

    assert error.value.code == 2


def test_gui_a8_recognized_arguments_are_not_forwarded_to_qt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_config = []
    captured_qt_argv = []

    class _Service:
        pass

    class _Application:
        def __init__(self, argv: list[str]) -> None:
            captured_qt_argv.append(tuple(argv))

        def setApplicationName(self, name: str) -> None:
            assert name == "AI Trading Bot"

        def exec(self) -> int:
            return 0

    class _Window:
        def __init__(self, service) -> None:  # type: ignore[no-untyped-def]
            assert type(service) is _Service

        def show(self) -> None:
            return None

    def _service(config: GuiStartupConfiguration):
        captured_config.append(config)
        return _Service()

    monkeypatch.setattr(app, "QApplication", _Application)
    monkeypatch.setattr(app, "MainWindow", _Window)
    monkeypatch.setattr(app, "build_startup_service", _service)

    assert (
        app.run(
            argv=(
                "--market-data-snapshot",
                "snapshot.json",
                "--paper-account-genesis",
                "genesis.json",
                "-platform",
                "offscreen",
            )
        )
        == 0
    )

    assert captured_config == [
        GuiStartupConfiguration(
            market_data_snapshot=Path("snapshot.json"),
            paper_account_genesis=Path("genesis.json"),
        )
    ]
    assert len(captured_qt_argv) == 1
    assert captured_qt_argv[0][1:] == ("-platform", "offscreen")

