"""Focused offscreen Qt tests for the GUI-A5b2 Paper page."""
# ruff: noqa: E402

import os
from pathlib import Path
from uuid import UUID

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from trading_bot.gui import (
    ApplicationOverview,
    MarketDataPageState,
    OperatorOperationsPageState,
    PaperAccountPageState,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
    ResearchPageState,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.paper_page import PaperPage

_OPERATION_ID = UUID("00000000-0000-0000-0000-000000000001")
_CHECKPOINT_ID = UUID("00000000-0000-0000-0000-000000000002")
_APPLICATION_ID = UUID("00000000-0000-0000-0000-000000000003")


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _inspected_state(
    *,
    message: str = "One paper operation was inspected read-only.",
    receipt_path: str | None = None,
) -> PaperPageState:
    return PaperPageState(
        status=PaperPageStatus.INSPECTED,
        message=message,
        inspection=PaperOperationInspectionView(
            classification=PaperInspectionClassification.PENDING,
            operation_id=_OPERATION_ID,
            terminal_checkpoint_id=_CHECKPOINT_ID,
            application_id=_APPLICATION_ID,
            diagnostic=PaperInspectionDiagnostic.PENDING,
            receipt_path=receipt_path,
        ),
    )


class _RecordingService:
    def __init__(self, paper_state: PaperPageState) -> None:
        self.paper_state = paper_state
        self.paper_calls = 0

    def get_overview(self) -> ApplicationOverview:
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        return MockGuiApplicationService().get_research_state()

    def get_paper_state(self) -> PaperPageState:
        self.paper_calls += 1
        return self.paper_state

    def get_market_data_state(self) -> MarketDataPageState:
        return unavailable_market_data_state()

    def get_paper_account_state(self) -> PaperAccountPageState:
        return unavailable_paper_account_state()

    def get_operator_observability_state(self) -> OperatorOperationsPageState:
        return unavailable_operator_operations_state()

    def load_research_report(self, artifact_path: Path) -> ResearchPageState:
        return MockGuiApplicationService().load_research_report(artifact_path)


def test_unavailable_page_renders_only_bounded_message_and_status() -> None:
    _application()
    page = PaperPage(
        PaperPageState(
            status=PaperPageStatus.UNAVAILABLE,
            message="Bounded unavailable message.",
            inspection=None,
        )
    )

    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "Bounded unavailable message." in texts
    assert "Unavailable" in texts
    assert str(_OPERATION_ID) not in texts
    assert page.findChild(QLabel, "paperClassification") is None
    assert page.findChild(QLabel, "paperDiagnostic") is None
    assert page.findChildren(QPushButton) == []


def test_inspected_page_renders_each_bounded_field() -> None:
    _application()
    page = PaperPage(_inspected_state(receipt_path="receipts/operation.json"))
    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "One paper operation was inspected read-only." in texts
    assert PaperInspectionClassification.PENDING.value in texts
    assert PaperInspectionDiagnostic.PENDING.value in texts
    assert str(_OPERATION_ID) in texts
    assert str(_CHECKPOINT_ID) in texts
    assert str(_APPLICATION_ID) in texts
    assert "receipts/operation.json" in texts
    assert page.findChildren(QPushButton) == []


def test_inspected_page_handles_absent_receipt_neutrally() -> None:
    _application()
    page = PaperPage(_inspected_state())

    receipt = page.findChild(QLabel, "paperReceiptPath")

    assert receipt is not None
    assert receipt.text() == "Not retained"


def test_service_derived_text_is_rendered_as_literal_plain_text() -> None:
    _application()
    page = PaperPage(
        _inspected_state(
            message="<b>literal message</b>",
            receipt_path="<i>literal receipt</i>",
        )
    )

    message = page.findChild(QLabel, "summaryLabel")
    receipt = page.findChild(QLabel, "paperReceiptPath")

    assert message is not None
    assert receipt is not None
    assert message.text() == "<b>literal message</b>"
    assert receipt.text() == "<i>literal receipt</i>"
    assert message.textFormat() is Qt.TextFormat.PlainText
    assert receipt.textFormat() is Qt.TextFormat.PlainText
    assert all(
        label.textFormat() is Qt.TextFormat.PlainText
        for label in page.findChildren(QLabel)
    )


def test_navigation_does_not_reinspect_paper_state() -> None:
    _application()
    service = _RecordingService(unavailable_paper_state())
    window = MainWindow(service)

    assert service.paper_calls == 1
    window.select_page("paper")
    window.select_page("system")
    window.select_page("paper")

    assert service.paper_calls == 1
    window.close()
