"""Focused Qt exploration checks for the GUI-A3 Research page."""
# ruff: noqa: E402

import os
from decimal import Decimal
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
)

from trading_bot.gui import (
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import (
    MockGuiApplicationService,
    ResearchReportGuiApplicationService,
)
from trading_bot.gui.research_page import ResearchPage
from trading_bot.gui.research_service import MAX_RESEARCH_FILTER_CHARACTERS

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "cli"
    / "historical-experiment-compact-report-v1-compact.json"
)


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _loaded_window() -> tuple[MainWindow, ResearchPage]:
    _application()
    window = MainWindow(ResearchReportGuiApplicationService(FIXTURE))
    page = window.findChild(ResearchPage, "researchPage")
    assert page is not None
    return window, page


def _visible_rows(table: QTableWidget) -> list[int]:
    return [row for row in range(table.rowCount()) if not table.isRowHidden(row)]


def _table_ordinals(table: QTableWidget) -> list[int]:
    return [
        table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        for row in range(table.rowCount())
    ]


def _in_memory_state(rows: tuple[ResearchResultRow, ...]) -> ResearchPageState:
    return ResearchPageState(
        status=ResearchReportStatus.LOADED,
        message="In-memory report loaded.",
        report=ResearchReportView(
            report_id="gui-a3-report",
            experiment_result_id="gui-a3-experiment",
            variant_source="EXPLICIT",
            ranking_summary="No ranking policy",
            metadata_summary="No report metadata",
            rows=rows,
        ),
    )


def _row(
    caller_ordinal: int,
    *,
    rank: int | None = 1,
    turnover: Decimal | None = None,
    trade_count: int | None = None,
) -> ResearchResultRow:
    return ResearchResultRow(
        caller_ordinal=caller_ordinal,
        rank=rank,
        variant_label="Same variant",
        parameter_label="Same parameters",
        total_return=Decimal("0"),
        maximum_drawdown_percentage=Decimal("0"),
        turnover=(Decimal(caller_ordinal) if turnover is None else turnover),
        trade_count=caller_ordinal if trade_count is None else trade_count,
        exposure=None,
        return_over_drawdown=None,
    )


def test_gui_a3_cancel_open_report_is_effect_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, page = _loaded_window()
    initial_state = page.research_state
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    button = page.findChild(QPushButton, "openResearchReportButton")
    assert button is not None
    button.click()

    assert page.research_state is initial_state
    assert table.rowCount() == 4
    window.close()


def test_gui_a3_valid_report_replacement_updates_only_research_presentation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replacement = tmp_path / "gui-a3-replacement-report.json"
    replacement.write_bytes(FIXTURE.read_bytes())
    window, page = _loaded_window()
    overview = window._overview
    initial_report = page.research_state.report
    assert initial_report is not None

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(replacement), "Compact reports (*.json)"),
    )
    page.open_report()

    report = page.research_state.report
    assert report is not None
    assert report.report_id == initial_report.report_id
    assert report.rows == initial_report.rows
    assert report.source_path == str(replacement.resolve())
    assert report.source_path != initial_report.source_path
    path_label = page.findChild(QLabel, "researchPath")
    assert path_label is not None
    assert path_label.text() == f"Report path: {replacement.resolve()}"
    assert window._overview is overview
    window.close()


def test_gui_a3_invalid_replacement_uses_bounded_unavailable_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = tmp_path / "gui-a3-invalid-report.json"
    invalid.write_text('{"raw_parser_detail":', encoding="utf-8")
    window, page = _loaded_window()

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(invalid), "Compact reports (*.json)"),
    )
    page.open_report()

    assert page.research_state.status is ResearchReportStatus.UNAVAILABLE
    assert page.research_state.report is None
    assert page.research_state.message == (
        "No supported compact historical experiment report is available."
    )
    assert "parser" not in page.research_state.message.casefold()
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None
    assert table.rowCount() == 0
    window.close()


def test_gui_a3_filtering_is_case_insensitive_deterministic_and_bounded() -> None:
    window, page = _loaded_window()
    table = page.findChild(QTableWidget, "researchResultsTable")
    filter_box = page.findChild(QLineEdit, "researchFilter")
    assert table is not None
    assert filter_box is not None

    filter_box.setText("risk_aversion=2")
    first = [table.item(row, 1).text() for row in _visible_rows(table)]
    filter_box.setText("RISK_AVERSION=2")
    second = [table.item(row, 1).text() for row in _visible_rows(table)]

    assert first == second
    assert len(first) == 2
    assert all("RISK_AVERSION=2" in value for value in first)

    filter_box.setText("x" * (MAX_RESEARCH_FILTER_CHARACTERS + 50))
    assert len(filter_box.text()) == MAX_RESEARCH_FILTER_CHARACTERS
    assert _visible_rows(table) == []
    window.close()


def test_gui_a3_sorting_preserves_model_and_selection_updates_detail() -> None:
    window, page = _loaded_window()
    table = page.findChild(QTableWidget, "researchResultsTable")
    detail_rank = page.findChild(QLabel, "researchDetailRank")
    detail_variant = page.findChild(QLabel, "researchDetailVariant")
    assert table is not None
    assert detail_rank is not None
    assert detail_variant is not None
    report = page.research_state.report
    assert report is not None
    original_rows = report.rows

    header = table.horizontalHeader()
    header.sectionClicked.emit(0)
    assert header.isSortIndicatorShown()
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
    assert [table.item(row, 0).text() for row in range(4)] == [
        "1",
        "2",
        "3",
        "4",
    ]

    header.sectionClicked.emit(0)

    assert [table.item(row, 0).text() for row in range(4)] == ["4", "3", "2", "1"]
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    assert page.research_state.report is report
    assert report.rows is original_rows
    assert [row.rank for row in report.rows] == [1, 2, 3, 4]

    table.selectRow(0)
    assert detail_rank.text() == "4"
    assert detail_variant.text() == report.rows[3].variant_label
    window.close()


def test_gui_a3_rank_sort_handles_multiple_unranked_rows_without_mutation() -> None:
    rows = (
        _row(0, rank=None),
        _row(1, rank=None),
        _row(2, rank=1),
    )
    page = ResearchPage(_in_memory_state(rows))
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None
    report = page.research_state.report
    assert report is not None
    original_rows = report.rows

    table.horizontalHeader().sectionClicked.emit(0)

    assert _table_ordinals(table) == [2, 0, 1]
    assert report.rows is original_rows
    assert report.rows == rows
    page.close()


@pytest.mark.parametrize("column", range(7))
def test_gui_a3_equal_primary_values_use_caller_ordinal(column: int) -> None:
    rows = tuple(
        _row(
            ordinal,
            rank=None,
            turnover=Decimal("0") if column == 5 else Decimal(ordinal),
            trade_count=0 if column == 6 else ordinal,
        )
        for ordinal in range(3)
    )
    page = ResearchPage(_in_memory_state(rows))
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None
    auxiliary_column = 6 if column != 6 else 5

    header = table.horizontalHeader()
    header.sectionClicked.emit(auxiliary_column)
    header.sectionClicked.emit(auxiliary_column)
    assert _table_ordinals(table) == [2, 1, 0]
    header.sectionClicked.emit(column)

    assert _table_ordinals(table) == [0, 1, 2]
    page.close()


@pytest.mark.parametrize("unsupported_column", (7, 8))
def test_gui_a3_unsupported_header_click_does_not_reorder(
    unsupported_column: int,
) -> None:
    window, page = _loaded_window()
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None
    header = table.horizontalHeader()
    header.sectionClicked.emit(0)
    header.sectionClicked.emit(0)
    before = _table_ordinals(table)

    header.sectionClicked.emit(unsupported_column)

    assert _table_ordinals(table) == before
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    window.close()


def test_gui_a3_table_and_selected_detail_remain_read_only() -> None:
    window, page = _loaded_window()
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None

    assert table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers
    for column in range(table.columnCount()):
        assert not table.item(0, column).flags() & Qt.ItemFlag.ItemIsEditable

    table.selectRow(1)
    expected = page.research_state.report
    assert expected is not None
    row = expected.rows[1]
    details = {
        "researchDetailRank": str(row.rank),
        "researchDetailVariant": row.variant_label,
        "researchDetailParameters": row.parameter_label,
        "researchDetailReturn": "0%",
        "researchDetailDrawdown": "0%",
        "researchDetailTurnover": "0.599994",
        "researchDetailTrades": "1",
        "researchDetailExposure": "Unavailable",
        "researchDetailReturnDrawdown": "Unavailable",
    }
    for object_name, expected_text in details.items():
        label = page.findChild(QLabel, object_name)
        assert label is not None
        assert label.text() == expected_text
    window.close()


def test_gui_a3_empty_preview_still_offers_open_report() -> None:
    _application()
    window = MainWindow(MockGuiApplicationService())
    page = window.findChild(ResearchPage, "researchPage")
    assert page is not None
    assert page.research_state.status is ResearchReportStatus.UNAVAILABLE
    assert page.findChild(QPushButton, "openResearchReportButton") is not None
    window.close()


def test_gui_a3_open_rejects_non_json_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unsupported = tmp_path / "gui-a3-report.txt"
    unsupported.write_bytes(FIXTURE.read_bytes())
    window, page = _loaded_window()

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(unsupported), "Compact reports (*.json)"),
    )
    page.open_report()

    assert page.research_state.status is ResearchReportStatus.UNAVAILABLE
    assert page.research_state.report is None
    assert page.research_state.message == (
        "No supported compact historical experiment report is available."
    )
    window.close()
