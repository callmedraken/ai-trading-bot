"""Focused offscreen Qt tests for GUI-A7b3 Paper Account rendering."""

# ruff: noqa: E402

from __future__ import annotations

import inspect
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
)

from trading_bot.gui import (
    ApplicationOverview,
    MarketDataPageState,
    PaperAccountCheckpointKindView,
    PaperAccountPageState,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    PaperPageState,
    ResearchPageState,
    VerifiedPaperAccountView,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.paper_account_page import PaperAccountPage

_AS_OF = datetime(2026, 8, 27, 22, 0, tzinfo=UTC)
_CHECKPOINT_ID = UUID("00000000-0000-0000-0000-000000000201")
_LINEAGE_ID = UUID("00000000-0000-0000-0000-000000000202")
_ACCOUNT_STATE_ID = UUID("00000000-0000-0000-0000-000000000203")
_COMPACT_STATE_ID = UUID("00000000-0000-0000-0000-000000000204")
_ARTIFACT_SHA256 = "a" * 64
_CASH = Decimal("100000000000000000000.12345678901234567890")
_REALIZED = Decimal("-0.000000000000000000000000000000000000123")


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _position(
    symbol: str = "SPY",
    quantity: str = "2",
    total_cost_basis: str = "20",
    average_cost: str = "10",
) -> PaperAccountPositionView:
    return PaperAccountPositionView(
        symbol=symbol,
        quantity=Decimal(quantity),
        total_cost_basis=Decimal(total_cost_basis),
        average_cost=Decimal(average_cost),
    )


def _account(
    *,
    kind: PaperAccountCheckpointKindView = PaperAccountCheckpointKindView.GENESIS,
    sequence: int = 0,
    positions: tuple[PaperAccountPositionView, ...] = (_position(),),
) -> VerifiedPaperAccountView:
    return VerifiedPaperAccountView(
        checkpoint_kind=kind,
        sequence=sequence,
        checkpoint_id=_CHECKPOINT_ID,
        lineage_id=_LINEAGE_ID,
        account_state_id=_ACCOUNT_STATE_ID,
        compact_state_id=_COMPACT_STATE_ID,
        as_of=_AS_OF,
        cash=_CASH,
        realized_profit_loss=_REALIZED,
        positions=positions,
        artifact_sha256=_ARTIFACT_SHA256,
        artifact_byte_length=123456789012345,
    )


def _state(
    *,
    kind: PaperAccountCheckpointKindView = PaperAccountCheckpointKindView.GENESIS,
    sequence: int = 0,
    positions: tuple[PaperAccountPositionView, ...] = (_position(),),
    message: str = "One local GENESIS paper-account checkpoint was verified offline.",
) -> PaperAccountPageState:
    return PaperAccountPageState(
        status=PaperAccountPageStatus.VERIFIED,
        message=message,
        account=_account(kind=kind, sequence=sequence, positions=positions),
    )


def test_unavailable_page_renders_title_status_message_only() -> None:
    _application()
    state = PaperAccountPageState(
        status=PaperAccountPageStatus.UNAVAILABLE,
        message="Bounded unavailable paper-account message.",
        account=None,
    )

    page = PaperAccountPage(state)
    texts = [label.text() for label in page.findChildren(QLabel)]

    assert texts == [
        "Paper Account",
        "Bounded unavailable paper-account message.",
        "Unavailable",
    ]
    assert page.findChild(QLabel, "paperAccountCheckpointId") is None
    assert page.findChild(QLabel, "paperAccountScopeNotice") is None
    assert page.findChildren(QTableWidget) == []
    assert page.findChildren(QPushButton) == []


def test_paper_account_page_rejects_incorrect_state_type() -> None:
    _application()

    with pytest.raises(TypeError, match="PaperAccountPageState"):
        PaperAccountPage(object())  # type: ignore[arg-type]


def test_verified_genesis_page_renders_all_common_fields() -> None:
    _application()
    page = PaperAccountPage(_state())

    expected = {
        "paperAccountCheckpointKind": "GENESIS",
        "paperAccountSequence": "0",
        "paperAccountCheckpointId": str(_CHECKPOINT_ID),
        "paperAccountLineageId": str(_LINEAGE_ID),
        "paperAccountAccountStateId": str(_ACCOUNT_STATE_ID),
        "paperAccountCompactStateId": str(_COMPACT_STATE_ID),
        "paperAccountAsOf": _AS_OF.isoformat(),
        "paperAccountCash": str(_CASH),
        "paperAccountRealizedProfitLoss": "-0.000000000000000000000000000000000000123",
        "paperAccountArtifactSha256": _ARTIFACT_SHA256,
        "paperAccountArtifactByteLength": "123456789012345",
    }

    assert page.findChild(QLabel, "paperAccountStatus").text() == "Verified Offline"
    assert page.findChild(QLabel, "paperAccountScopeNotice").text() == (
        "Offline-verified checkpoint state; not an "
        "operationally selected current account."
    )
    for object_name, expected_text in expected.items():
        label = page.findChild(QLabel, object_name)
        assert label is not None
        assert label.text() == expected_text


def test_verified_successor_page_renders_positive_sequence_and_common_fields() -> None:
    _application()
    page = PaperAccountPage(
        _state(
            kind=PaperAccountCheckpointKindView.CYCLE_SUCCESSOR,
            sequence=7,
        )
    )

    assert page.findChild(QLabel, "paperAccountCheckpointKind").text() == (
        "CYCLE_SUCCESSOR"
    )
    assert page.findChild(QLabel, "paperAccountSequence").text() == "7"
    assert page.findChild(QLabel, "paperAccountCheckpointId").text() == str(
        _CHECKPOINT_ID
    )
    assert page.findChild(QLabel, "paperAccountCash").text() == str(_CASH)
    assert (
        page.findChild(QLabel, "paperAccountRealizedProfitLoss").text()
        == "-0.000000000000000000000000000000000000123"
    )


def test_multiple_positions_preserve_supplied_order() -> None:
    _application()
    positions = (
        _position("QQQ", "3", "30", "10"),
        _position("SPY", "2", "20", "10"),
        _position("DIA", "5", "55", "11"),
    )
    page = PaperAccountPage(_state(positions=positions))
    table = page.findChild(QTableWidget, "paperAccountPositionsTable")

    assert table is not None
    assert [table.item(row, 0).text() for row in range(table.rowCount())] == [
        "QQQ",
        "SPY",
        "DIA",
    ]


def test_position_table_is_read_only_and_does_not_enable_sorting() -> None:
    _application()
    positions = (
        _position("QQQ"),
        _position("SPY"),
    )
    page = PaperAccountPage(_state(positions=positions))
    table = page.findChild(QTableWidget, "paperAccountPositionsTable")

    assert table is not None
    assert table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers
    assert table.verticalHeader().isHidden() is True
    assert table.columnCount() == 4
    assert [
        table.horizontalHeaderItem(column).text()
        for column in range(table.columnCount())
    ] == ["Symbol", "Quantity", "Total Cost Basis", "Average Cost"]
    header = table.horizontalHeader()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.Stretch
    assert table.isSortingEnabled() is False
    assert table.horizontalHeader().sectionsClickable() is False
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            assert not table.item(row, column).flags() & Qt.ItemFlag.ItemIsEditable

    before = [table.item(row, 0).text() for row in range(table.rowCount())]
    table.horizontalHeader().sectionClicked.emit(0)
    assert [table.item(row, 0).text() for row in range(table.rowCount())] == before


def test_decimal_fields_use_exact_non_float_text() -> None:
    _application()
    position = _position(
        quantity="12345678901234567890",
        total_cost_basis="12345678901234567890",
        average_cost="1",
    )
    page = PaperAccountPage(_state(positions=(position,)))
    table = page.findChild(QTableWidget, "paperAccountPositionsTable")

    assert table is not None
    assert page.findChild(QLabel, "paperAccountCash").text() == (
        "100000000000000000000.12345678901234567890"
    )
    assert page.findChild(QLabel, "paperAccountRealizedProfitLoss").text() == (
        "-0.000000000000000000000000000000000000123"
    )
    assert table.item(0, 1).text() == "12345678901234567890"
    assert table.item(0, 2).text() == "12345678901234567890"
    assert table.item(0, 3).text() == "1"


def test_uuid_and_digest_values_are_mouse_selectable() -> None:
    _application()
    page = PaperAccountPage(_state())
    selectable = Qt.TextInteractionFlag.TextSelectableByMouse

    for object_name in (
        "paperAccountCheckpointId",
        "paperAccountLineageId",
        "paperAccountAccountStateId",
        "paperAccountCompactStateId",
        "paperAccountArtifactSha256",
    ):
        label = page.findChild(QLabel, object_name)
        assert label is not None
        assert label.textInteractionFlags() & selectable


def test_all_model_derived_labels_are_explicit_plain_text() -> None:
    _application()
    state = _state(message="<b>literal account message</b>")
    page = PaperAccountPage(state)

    message = page.findChild(QLabel, "paperAccountMessage")
    assert message is not None
    assert message.text() == "<b>literal account message</b>"
    assert message.textFormat() is Qt.TextFormat.PlainText
    assert all(
        label.textFormat() is Qt.TextFormat.PlainText
        for label in page.findChildren(QLabel)
    )


def test_default_mock_service_returns_unavailable_paper_account_state() -> None:
    assert (
        MockGuiApplicationService().get_paper_account_state()
        == unavailable_paper_account_state()
    )


class _RecordingService:
    def __init__(self, paper_account_state: PaperAccountPageState) -> None:
        self.paper_account_state = paper_account_state
        self.paper_account_calls = 0

    def get_overview(self) -> ApplicationOverview:
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        return MockGuiApplicationService().get_research_state()

    def get_paper_state(self) -> PaperPageState:
        return MockGuiApplicationService().get_paper_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        self.paper_account_calls += 1
        return self.paper_account_state

    def get_market_data_state(self) -> MarketDataPageState:
        return unavailable_market_data_state()

    def get_operator_observability_state(self):
        return unavailable_operator_operations_state()

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        return MockGuiApplicationService().load_research_report(artifact_path)


def test_main_window_acquires_paper_account_once_and_navigation_reuses_state() -> None:
    _application()
    state = _state()
    service = _RecordingService(state)
    window = MainWindow(service)

    assert window.page_ids == (
        "home",
        "research",
        "paper",
        "paper-account",
        "market-data",
        "operations",
        "evidence",
        "system",
    )
    assert window.current_page_id == "home"
    assert service.paper_account_calls == 1

    page = window.findChild(PaperAccountPage, "paperAccountPage")
    assert page is not None
    assert page.paper_account_state is state

    window.select_page("paper-account")
    assert window.current_page_id == "paper-account"
    window.select_page("system")
    assert window.current_page_id == "system"
    window.select_page("paper-account")

    assert window.current_page_id == "paper-account"
    assert service.paper_account_calls == 1
    window.close()


def test_main_window_has_no_compatibility_fallback_for_account_service() -> None:
    source = inspect.getsource(MainWindow)

    assert "hasattr" not in source
    assert "AttributeError" not in source


def test_minimum_window_width_keeps_paper_account_digest_visible() -> None:
    application = _application()
    window = MainWindow(_RecordingService(_state()))
    window.resize(920, 620)
    window.show()
    window.select_page("paper-account")
    application.processEvents()

    label = window.findChild(QLabel, "paperAccountArtifactSha256")
    assert label is not None
    assert label.text() == _ARTIFACT_SHA256
    assert label.font().pixelSize() == 10
    assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse

    window.close()
