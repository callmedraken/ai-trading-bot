"""Focused Qt checks for GUI-A4 read-only variant comparison."""
# ruff: noqa: E402

import os
from decimal import Decimal

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
)

from trading_bot.gui.comparison_chart import (
    ResearchComparisonChart,
    _metric_header_positions,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.mock_service import MockGuiApplicationService
from trading_bot.gui.models import (
    ApplicationOverview,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)
from trading_bot.gui.research_page import ResearchPage


def _application() -> QApplication:
    existing = QApplication.instance()
    return existing if existing is not None else QApplication([])


def _row(
    ordinal: int,
    *,
    total_return: str = "0",
    drawdown: str = "0.1",
    one_way_turnover: str = "1",
    variant: str | None = None,
) -> ResearchResultRow:
    return ResearchResultRow(
        caller_ordinal=ordinal,
        rank=ordinal + 1,
        variant_label=variant or f"Variant {ordinal}",
        parameter_label=f"window={ordinal + 2}",
        total_return=Decimal(total_return),
        maximum_drawdown_percentage=Decimal(drawdown),
        aggregate_one_way_turnover=Decimal(one_way_turnover),
        total_fills=ordinal + 3,
        exposure=None,
        return_over_drawdown=None,
    )


def _state(
    rows: tuple[ResearchResultRow, ...], report_id: str = "gui-a4"
) -> ResearchPageState:
    return ResearchPageState(
        status=ResearchReportStatus.LOADED,
        message="Read-only comparison fixture loaded.",
        report=ResearchReportView(
            report_id=report_id,
            experiment_result_id=f"{report_id}-experiment",
            variant_source="EXPLICIT",
            ranking_summary="No ranking policy",
            metadata_summary="No report metadata",
            rows=rows,
        ),
    )


def _page(rows: tuple[ResearchResultRow, ...]) -> ResearchPage:
    _application()
    return ResearchPage(_state(rows), MockGuiApplicationService())


class _WindowResearchService:
    def __init__(self, state: ResearchPageState) -> None:
        self._state = state

    def get_overview(self) -> ApplicationOverview:
        return MockGuiApplicationService().get_overview()

    def get_research_state(self) -> ResearchPageState:
        return self._state


def _main_table(page: ResearchPage) -> QTableWidget:
    table = page.findChild(QTableWidget, "researchResultsTable")
    assert table is not None
    return table


def _comparison_table(page: ResearchPage) -> QTableWidget:
    table = page.findChild(QTableWidget, "researchComparisonTable")
    assert table is not None
    return table


def _select_ordinal(page: ResearchPage, ordinal: int) -> None:
    table = _main_table(page)
    for visual_row in range(table.rowCount()):
        item = table.item(visual_row, 0)
        if item.data(Qt.ItemDataRole.UserRole) == ordinal:
            table.selectRow(visual_row)
            return
    raise AssertionError(f"ordinal {ordinal} is not in the presentation table")


def _add_ordinal(page: ResearchPage, ordinal: int) -> None:
    _select_ordinal(page, ordinal)
    page.add_selected_to_comparison()


def test_gui_a4_chart_header_context_follows_measured_title_width() -> None:
    _application()
    chart = ResearchComparisonChart()
    metrics = QFontMetrics(chart.font())

    title_x, context_x = _metric_header_positions(metrics, "Maximum drawdown")

    assert context_x >= title_x + metrics.horizontalAdvance("Maximum drawdown") + 12
    assert (
        context_x
        + metrics.horizontalAdvance(
            "Lower drawdown is better • larger bars mean more drawdown"
        )
        <= 900
    )


def test_gui_a4_selects_two_to_four_variants_in_stable_report_order() -> None:
    rows = tuple(_row(index) for index in range(4))
    page = _page(rows)

    for ordinal in (3, 1, 2, 0):
        _add_ordinal(page, ordinal)

    assert page.comparison_state.caller_ordinals == (0, 1, 2, 3)
    assert page.comparison_state.is_ready
    table = _comparison_table(page)
    assert [
        table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        for row in range(table.rowCount())
    ] == [0, 1, 2, 3]
    chart = page.findChild(ResearchComparisonChart, "researchComparisonChart")
    assert chart is not None
    assert chart.rows == rows
    page.close()


def test_gui_a4_four_variant_research_content_scrolls_in_main_window() -> None:
    rows = tuple(_row(index) for index in range(4))
    window = MainWindow(_WindowResearchService(_state(rows)))
    window.select_page("research")
    window.show()
    _application().processEvents()

    page = window.findChild(ResearchPage, "researchPage")
    scroll_area = window.findChild(QScrollArea, "researchScrollArea")
    assert page is not None
    assert scroll_area is not None
    assert window.current_page_id == "research"
    assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert (
        scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert scroll_area.viewport().objectName() == "researchScrollViewport"
    assert "#111827" in scroll_area.viewport().styleSheet()

    for ordinal in range(4):
        _add_ordinal(page, ordinal)
    _application().processEvents()

    comparison_table = _comparison_table(page)
    chart = page.findChild(ResearchComparisonChart, "researchComparisonChart")
    assert chart is not None
    assert comparison_table.rowCount() == 4
    assert chart.rows == rows
    assert scroll_area.verticalScrollBar().maximum() > 0

    scroll_area.verticalScrollBar().setValue(scroll_area.verticalScrollBar().maximum())
    assert (
        scroll_area.verticalScrollBar().value()
        == scroll_area.verticalScrollBar().maximum()
    )
    scroll_area.verticalScrollBar().setValue(0)
    assert scroll_area.verticalScrollBar().value() == 0
    window.close()


def test_gui_a4_fifth_variant_is_bounded_without_replacing_selection() -> None:
    rows = tuple(_row(index) for index in range(5))
    page = _page(rows)
    for ordinal in range(4):
        _add_ordinal(page, ordinal)

    _select_ordinal(page, 4)
    page.add_selected_to_comparison()

    assert page.comparison_state.caller_ordinals == (0, 1, 2, 3)
    notice = page.findChild(QLabel, "researchComparisonNotice")
    assert notice is not None
    assert notice.text() == (
        "Comparison is limited to 4 variants. Remove one before adding another."
    )
    page.close()


def test_gui_a4_comparison_identity_survives_sort_and_filter() -> None:
    rows = tuple(_row(index) for index in range(4))
    page = _page(rows)
    _add_ordinal(page, 0)
    _add_ordinal(page, 3)
    original_rows = page.research_state.report.rows  # type: ignore[union-attr]

    table = _main_table(page)
    table.horizontalHeader().sectionClicked.emit(0)
    table.horizontalHeader().sectionClicked.emit(0)
    page.findChild(type(page._filter), "researchFilter").setText("window=2")

    assert page.comparison_state.caller_ordinals == (0, 3)
    assert [row.caller_ordinal for row in page._comparison_chart.rows] == [0, 3]
    assert page.research_state.report is not None
    assert page.research_state.report.rows is original_rows
    page.close()


def test_gui_a4_report_replacement_clears_comparison_only() -> None:
    rows = tuple(_row(index) for index in range(3))
    page = _page(rows)
    _add_ordinal(page, 0)
    _add_ordinal(page, 2)

    replacement_rows = (
        _row(0, variant="Replacement A"),
        _row(1, variant="Replacement B"),
    )
    page.set_research_state(_state(replacement_rows, "gui-a4-replacement"))

    assert page.comparison_state.caller_ordinals == ()
    assert _comparison_table(page).rowCount() == 0
    assert page._comparison_chart.rows == ()
    assert page.research_state.report is not None
    assert page.research_state.report.rows is replacement_rows
    page.close()


def test_gui_a4_return_chart_handles_negative_zero_and_positive_truthfully() -> None:
    rows = (
        _row(0, total_return="-0.1"),
        _row(1, total_return="0"),
        _row(2, total_return="0.2"),
    )
    page = _page(rows)
    for ordinal in (2, 0, 1):
        _add_ordinal(page, ordinal)

    bars = tuple(
        bar
        for bar in page._comparison_chart.bar_layout(600)
        if bar.metric == "total_return"
    )

    assert [bar.caller_ordinal for bar in bars] == [0, 1, 2]
    negative, zero, positive = bars
    assert negative.value == Decimal("-0.1")
    assert negative.start_x < negative.zero_x == negative.end_x
    assert zero.value == Decimal("0")
    assert zero.start_x == zero.zero_x == zero.end_x
    assert positive.value == Decimal("0.2")
    assert positive.start_x == positive.zero_x < positive.end_x
    page.close()


def test_gui_a4_drawdown_direction_and_ties_are_explicit_and_deterministic() -> None:
    rows = (
        _row(0, drawdown="0.1", one_way_turnover="2"),
        _row(1, drawdown="0.2", one_way_turnover="2"),
        _row(2, drawdown="0.1", one_way_turnover="1"),
    )
    page = _page(rows)
    for ordinal in (2, 1, 0):
        _add_ordinal(page, ordinal)

    layout = page._comparison_chart.bar_layout(600)
    drawdowns = [bar for bar in layout if bar.metric == "maximum_drawdown_percentage"]
    one_way_turnovers = [
        bar for bar in layout if bar.metric == "aggregate_one_way_turnover"
    ]

    assert "Lower drawdown is better" in drawdowns[0].context
    assert drawdowns[1].end_x > drawdowns[0].end_x
    assert [bar.caller_ordinal for bar in one_way_turnovers] == [0, 1, 2]
    assert one_way_turnovers[0].value == one_way_turnovers[1].value
    assert one_way_turnovers[0].end_x == one_way_turnovers[1].end_x
    page.close()


def test_gui_a4_remove_clear_and_read_only_table_preserve_source_rows() -> None:
    rows = tuple(_row(index) for index in range(3))
    page = _page(rows)
    _add_ordinal(page, 0)
    _add_ordinal(page, 1)
    _add_ordinal(page, 2)
    comparison_table = _comparison_table(page)

    assert comparison_table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers
    comparison_table.selectRow(1)
    remove = page.findChild(QPushButton, "removeResearchComparisonButton")
    clear = page.findChild(QPushButton, "clearResearchComparisonButton")
    assert remove is not None
    assert clear is not None
    remove.click()
    assert page.comparison_state.caller_ordinals == (0, 2)
    clear.click()

    assert page.comparison_state.caller_ordinals == ()
    assert page.research_state.report is not None
    assert page.research_state.report.rows is rows
    page.close()
