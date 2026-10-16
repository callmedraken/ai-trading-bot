"""Only an explicit CLI/config path composes strategy inspection."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import Symbol
from trading_bot.gui import (
    GuiStartupConfiguration,
    ProductionStrategyPageStatus,
    ReadOnlyGuiApplicationService,
    startup_composition,
)
from trading_bot.gui.app import _parse_startup_arguments
from trading_bot.gui.models import PresentationStatus
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig
from trading_bot.strategies.production import ProductionStrategyContract


def test_absence_does_not_instantiate_or_read(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Strategy reader or file I/O instantiated by default")

    monkeypatch.setattr(
        startup_composition, "ProductionStrategyContractInspectionService", forbidden
    )
    monkeypatch.setattr(Path, "open", forbidden)
    service = ReadOnlyGuiApplicationService(GuiStartupConfiguration())
    assert (
        service.get_production_strategy_state().status
        is ProductionStrategyPageStatus.UNAVAILABLE
    )
    assert (
        next(
            c for c in service.get_overview().components if c.key == "supervisor"
        ).status
        is PresentationStatus.UNAVAILABLE
    )
    with pytest.raises(TypeError):
        GuiStartupConfiguration(production_strategy_contract="selected.json")


def test_flag_is_consumed_before_qt_forwarding():
    config, qt = _parse_startup_arguments(
        ["--production-strategy-contract", "selected.json", "-platform", "offscreen"]
    )
    assert config.production_strategy_contract == Path("selected.json")
    assert qt == ("-platform", "offscreen")


@pytest.mark.parametrize("valid", [True, False])
def test_overview_and_strategy_share_one_acquisition(tmp_path, monkeypatch, valid):
    path = tmp_path / "selected.json"
    contract = ProductionStrategyContract(
        date(2026, 10, 12),
        "a" * 40,
        "b" * 40,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
    )
    path.write_text(contract.to_json() if valid else "invalid", encoding="utf-8")
    original = Path.open
    opens = []

    def opened(selected, *args, **kwargs):
        assert selected == path
        opens.append(selected)
        return original(selected, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(production_strategy_contract=path)
    )
    overview = service.get_overview()
    state = service.get_production_strategy_state()
    service.get_overview()
    assert state is service.get_production_strategy_state()
    assert opens == [path]
    component = next(c for c in overview.components if c.key == "supervisor")
    assert component.status is (
        PresentationStatus.INFO if valid else PresentationStatus.BLOCKED
    )


def test_dedicated_gui_ci_changes_only_presentation_branch_scope():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/gui-source-gates.yml").read_text()
    assert '- "feature/gui-*"' in workflow
    for retained in (
        "pull_request:",
        "workflow_dispatch:",
        "windows-latest",
        'python-version: "3.14"',
        '".[dev,gui]"',
        "import PySide6",
        "tests/gui",
        "ruff check",
        "ruff format --check",
        "git diff --check",
    ):
        assert retained in workflow
    repository_gate = (
        root / ".github/workflows/checkpoint-source-gates.yml"
    ).read_text()
    assert "feature/gui-*" not in repository_gate
