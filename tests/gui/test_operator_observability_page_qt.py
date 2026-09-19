"""Focused offscreen Qt tests for the PD4 Operations page."""

# ruff: noqa: E402

import ast
import inspect
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

import trading_bot.gui.operator_observability_page as operations_page_module
from trading_bot.gui import (
    ApplicationOverview,
    MarketDataPageState,
    OperatorAccountSummaryView,
    OperatorEffectGateState,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorStrategyExplanationStatus,
    OperatorStrategyExplanationView,
    OperatorWarmupClassification,
    OperatorWarmupView,
    PaperAccountPageState,
    PaperPageState,
    ResearchPageState,
    SelectedC3WarmupSessionView,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.operator_observability_page import OperatorOperationsPage

_REQUIRED = (
    date(2026, 9, 11),
    date(2026, 9, 14),
    date(2026, 9, 15),
    date(2026, 9, 16),
    date(2026, 9, 17),
    date(2026, 9, 18),
)
_SNAPSHOT_ID = UUID("680b260f-08c9-5923-87bb-b5f0a4701380")
_CHECKPOINT_ID = UUID("ed4640e5-0630-525d-b916-d50e31e3ba2a")


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _gates() -> OperatorEffectGateState:
    return OperatorEffectGateState(
        market_data_capture=False,
        decision_publication=False,
        production=False,
        recovery=False,
        supervised_execution=False,
        receipt_recovery=False,
        unattended_execution=False,
        unattended_storage_provisioning=False,
    )


def _warmup() -> OperatorWarmupView:
    selected = tuple(
        SelectedC3WarmupSessionView(
            session_date=session,
            symbol="SPY",
            close=Decimal("760") + Decimal(index) / Decimal("10"),
            snapshot_id=UUID(int=100 + index),
            selection_id=UUID(int=200 + index),
        )
        for index, session in enumerate(_REQUIRED, start=1)
    )
    return OperatorWarmupView(
        classification=OperatorWarmupClassification.READY,
        required_sessions=_REQUIRED,
        selected_sessions=selected,
    )


def _strategy_explanation() -> OperatorStrategyExplanationView:
    return OperatorStrategyExplanationView(
        status=OperatorStrategyExplanationStatus.BUY,
        short_window=3,
        long_window=5,
        desired_quantity=Decimal("1"),
        symbol="SPY",
        sessions=_REQUIRED,
        closes=(
            Decimal("764.29"),
            Decimal("760.88"),
            Decimal("757.39"),
            Decimal("754.05"),
            Decimal("762.6"),
            Decimal("761.69"),
        ),
        previous_short=Decimal("758.0133333333333333333333333"),
        previous_long=Decimal("759.842"),
        current_short=Decimal("759.4466666666666666666666667"),
        current_long=Decimal("759.322"),
        crossover_side="BUY",
        actionable_side="BUY",
        invested=False,
    )


def _state(
    *,
    message: str = "Current production observability snapshot; read-only.",
) -> OperatorOperationsPageState:
    return OperatorOperationsPageState(
        status=OperatorOperationsPageStatus.AVAILABLE,
        message=message,
        cycle_classification="BLOCKED",
        completed_session=date(2026, 9, 18),
        market_data_classification="NO_NEW_COMPLETED_SESSION",
        selected_snapshot_id=_SNAPSHOT_ID,
        warmup=_warmup(),
        gates=_gates(),
        account=OperatorAccountSummaryView(
            paper_account_id="9415cd7b-bf36-5fba-bd58-a0f99119dc21",
            checkpoint_id=_CHECKPOINT_ID,
            sequence=1,
            as_of=datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
            cash=Decimal("25000"),
            realized_profit_loss=Decimal("0"),
            positions=(),
            lineage_edge_count=1,
            receipt_count=1,
        ),
        strategy_explanation=_strategy_explanation(),
    )


def test_unavailable_operations_page_is_bounded_and_has_no_effect_controls() -> None:
    _application()
    page = OperatorOperationsPage(unavailable_operator_operations_state())

    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "Operations" in texts
    assert "Unavailable" in texts
    assert page.findChild(QTableWidget, "operatorSelectedC3Table") is None
    assert page.findChild(QTableWidget, "operatorEffectGateTable") is None
    assert page.findChildren(QPushButton) == []


def test_available_page_renders_warmup_gates_account_and_strategy_readiness() -> None:
    _application()
    page = OperatorOperationsPage(_state())

    assert page.findChild(QLabel, "operatorCycleClassification").text() == "BLOCKED"
    assert page.findChild(QLabel, "operatorCompletedSession").text() == "2026-09-18"
    assert (
        page.findChild(QLabel, "operatorMarketDataClassification").text()
        == "NO_NEW_COMPLETED_SESSION"
    )
    assert page.findChild(QLabel, "operatorSelectedSnapshotId").text() == str(
        _SNAPSHOT_ID
    )

    progress = page.findChild(QLabel, "operatorWarmupProgress")
    assert progress is not None
    assert progress.text() == "READY  •  6 / 6"

    selected = page.findChild(QTableWidget, "operatorSelectedC3Table")
    assert selected is not None
    assert selected.rowCount() == 6
    assert selected.columnCount() == 5
    assert selected.item(0, 0).text() == "2026-09-11"
    assert selected.item(5, 0).text() == "2026-09-18"
    assert selected.item(0, 1).text() == "SPY"

    gates = page.findChild(QTableWidget, "operatorEffectGateTable")
    assert gates is not None
    assert gates.rowCount() == 8
    assert all(gates.item(row, 1).text() == "Closed" for row in range(8))
    assert page.findChild(QLabel, "operatorGateSummary").text() == (
        "All effect gates closed"
    )

    assert page.findChild(QLabel, "operatorCheckpointId").text() == str(_CHECKPOINT_ID)
    assert page.findChild(QLabel, "operatorAccountCash").text() == "25000"
    assert page.findChild(QLabel, "operatorAccountPositionCount").text() == "0"
    assert page.findChild(QLabel, "operatorStrategyReadiness").text() == (
        "BUY: source-owned SMA 3/5 evaluation."
    )
    assert page.findChild(QLabel, "operatorStrategySymbol").text() == "SPY"
    assert page.findChild(QLabel, "operatorStrategyDesiredQuantity").text() == "1"
    assert page.findChild(QLabel, "operatorStrategySessions").text() == (
        "2026-09-11, 2026-09-14, 2026-09-15, 2026-09-16, 2026-09-17, 2026-09-18"
    )
    assert page.findChild(QLabel, "operatorStrategyCloses").text() == (
        "764.29, 760.88, 757.39, 754.05, 762.6, 761.69"
    )
    assert page.findChild(QLabel, "operatorStrategyPreviousShort").text() == (
        "758.0133333333333333333333333"
    )
    assert page.findChild(QLabel, "operatorStrategyPreviousLong").text() == "759.842"
    assert page.findChild(QLabel, "operatorStrategyCurrentShort").text() == (
        "759.4466666666666666666666667"
    )
    assert page.findChild(QLabel, "operatorStrategyCurrentLong").text() == "759.322"
    assert page.findChild(QLabel, "operatorStrategyCrossoverSide").text() == "BUY"
    assert page.findChild(QLabel, "operatorStrategyAccountState").text() == "Flat"
    assert page.findChild(QLabel, "operatorStrategyActionableSide").text() == "BUY"
    assert (
        "not D7 publication authority"
        in page.findChild(QLabel, "operatorStrategyAuthorityNotice").text()
    )
    assert page.findChildren(QPushButton) == []


def test_operations_page_renders_service_text_as_literal_plain_text() -> None:
    _application()
    page = OperatorOperationsPage(_state(message="<b>literal operator message</b>"))

    message = page.findChild(QLabel, "operatorOperationsMessage")
    assert message is not None
    assert message.text() == "<b>literal operator message</b>"
    assert message.textFormat() is Qt.TextFormat.PlainText
    assert all(
        label.textFormat() is Qt.TextFormat.PlainText
        for label in page.findChildren(QLabel)
    )


def test_operations_tables_are_read_only_and_unsortable() -> None:
    _application()
    page = OperatorOperationsPage(_state())

    for object_name in ("operatorSelectedC3Table", "operatorEffectGateTable"):
        table = page.findChild(QTableWidget, object_name)
        assert table is not None
        assert table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers
        assert table.isSortingEnabled() is False
        assert table.horizontalHeader().sectionsClickable() is False
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                assert not table.item(row, column).flags() & Qt.ItemFlag.ItemIsEditable


def test_operations_page_rejects_wrong_state_type() -> None:
    _application()

    with pytest.raises(TypeError, match="OperatorOperationsPageState"):
        OperatorOperationsPage(object())  # type: ignore[arg-type]


class _RecordingService:
    def __init__(self, state: OperatorOperationsPageState) -> None:
        self.state = state
        self.operations_calls = 0

    def get_overview(self) -> ApplicationOverview:
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        return MockGuiApplicationService().get_research_state()

    def get_paper_state(self) -> PaperPageState:
        return unavailable_paper_state()

    def get_market_data_state(self) -> MarketDataPageState:
        return unavailable_market_data_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        return unavailable_paper_account_state()

    def get_operator_observability_state(self) -> OperatorOperationsPageState:
        self.operations_calls += 1
        return self.state

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        return MockGuiApplicationService().load_research_report(artifact_path)


def test_main_window_acquires_operations_state_once_and_reuses_it() -> None:
    _application()
    state = _state()
    service = _RecordingService(state)
    window = MainWindow(service)

    assert "operations" in window.page_ids
    assert service.operations_calls == 1

    page = window.findChild(OperatorOperationsPage, "operatorOperationsPage")
    assert page is not None
    assert page.operations_state is state

    window.select_page("operations")
    assert window.current_page_id == "operations"
    window.select_page("system")
    window.select_page("operations")

    assert service.operations_calls == 1
    window.close()


def test_operations_page_has_no_runtime_or_effect_control_dependency() -> None:
    source = inspect.getsource(operations_page_module)
    tree = ast.parse(source)

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        module.startswith("trading_bot.runtime") for module in imported_modules
    )
    assert "QPushButton" not in source

    called_names = {
        (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert {"publish", "provision", "execute"}.isdisjoint(called_names)
