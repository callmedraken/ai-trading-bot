"""Qt presentation for bounded read-only historical research exploration."""

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.models import (
    ResearchPageState,
    ResearchReportStatus,
    ResearchResultRow,
)
from trading_bot.gui.research_service import (
    MAX_RESEARCH_FILTER_CHARACTERS,
    CompactReportResearchService,
    filter_research_rows,
)

_HEADERS = (
    "Rank",
    "Variant",
    "Parameters",
    "Total return",
    "Max drawdown",
    "Turnover",
    "Trades",
    "Exposure",
    "Return / drawdown",
)
_SORTABLE_COLUMN_COUNT = 7


class _SortableTableItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: object, caller_ordinal: int) -> None:
        super().__init__(text)
        self._sort_value = (sort_value, caller_ordinal)
        self.setData(Qt.ItemDataRole.UserRole, caller_ordinal)
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _SortableTableItem):
            return self._sort_value < other._sort_value  # type: ignore[operator]
        return super().__lt__(other)


class ResearchPage(QWidget):
    """Explore one bounded compact report without mutating source or domain state."""

    def __init__(self, state: ResearchPageState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._report = state.report
        self.setObjectName("researchPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        title = QLabel("Historical Research", self)
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self._open_button = QPushButton("Open Report…", self)
        self._open_button.setObjectName("openResearchReportButton")
        self._open_button.clicked.connect(self.open_report)
        heading.addWidget(self._open_button)
        layout.addLayout(heading)

        self._status = QLabel(self)
        self._status.setObjectName("summaryLabel")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._path = QLabel(self)
        self._path.setObjectName("researchPath")
        self._path.setWordWrap(True)
        self._path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._path)

        self._identity = QLabel(self)
        self._identity.setObjectName("researchIdentity")
        self._identity.setWordWrap(True)
        self._identity.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._identity)

        self._summary = QLabel(self)
        self._summary.setObjectName("researchSummary")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._metadata = QLabel(self)
        self._metadata.setObjectName("researchMetadata")
        self._metadata.setWordWrap(True)
        layout.addWidget(self._metadata)

        self._empty = QLabel(self)
        self._empty.setObjectName("researchEmptyState")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._empty)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("researchFilter")
        self._filter.setPlaceholderText("Filter variants or parameter assignments")
        self._filter.setClearButtonEnabled(True)
        self._filter.setMaxLength(MAX_RESEARCH_FILTER_CHARACTERS)
        self._filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter)

        self._table = QTableWidget(0, len(_HEADERS), self)
        self._table.setObjectName("researchResultsTable")
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionsClickable(True)
        self._sort_column: int | None = None
        self._sort_order: Qt.SortOrder | None = None
        self._table.horizontalHeader().setSortIndicatorShown(False)
        self._table.horizontalHeader().sectionClicked.connect(self._sort_table)
        self._table.itemSelectionChanged.connect(self._update_selected_detail)
        layout.addWidget(self._table, 1)

        self._detail = QFrame(self)
        self._detail.setObjectName("researchDetailPanel")
        detail_layout = QFormLayout(self._detail)
        detail_layout.setContentsMargins(14, 12, 14, 12)
        self._detail_values: dict[str, QLabel] = {}
        for key, label in (
            ("rank", "Rank"),
            ("variant", "Variant"),
            ("parameters", "Parameters"),
            ("return", "Total return"),
            ("drawdown", "Maximum drawdown"),
            ("turnover", "Turnover"),
            ("trades", "Trade count"),
            ("exposure", "Exposure"),
            ("return_drawdown", "Return / drawdown"),
        ):
            value = QLabel("—", self._detail)
            value.setObjectName(f"researchDetail{key.title().replace('_', '')}")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._detail_values[key] = value
            detail_layout.addRow(label, value)
        layout.addWidget(self._detail)

        self.set_research_state(state)

    @property
    def research_state(self) -> ResearchPageState:
        """Return the current immutable research presentation state."""
        return self._state

    def open_report(self) -> None:
        """Select and load one local compact JSON report through the adapter."""
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open Compact Historical Experiment Report",
            "",
            "Compact historical experiment reports (*.json)",
        )
        if not selected:
            return
        self.set_research_state(
            CompactReportResearchService(Path(selected)).get_research_state()
        )

    def set_research_state(self, state: ResearchPageState) -> None:
        """Replace only the displayed bounded research state."""
        if type(state) is not ResearchPageState:
            raise TypeError("state must be exactly ResearchPageState")
        self._state = state
        self._report = state.report
        self._status.setText(state.message)
        self._filter.clear()
        self._reset_sort_state()
        self._table.setRowCount(0)
        self._set_detail(None)

        loaded = state.status is ResearchReportStatus.LOADED
        report = state.report
        if loaded and report is None:
            raise RuntimeError("loaded research state is missing its report")

        self._path.setText(
            "Report path: "
            + (
                "Unavailable"
                if report is None
                else report.source_path or "Not specified"
            )
        )
        self._identity.setVisible(loaded)
        self._summary.setVisible(loaded)
        self._metadata.setVisible(loaded)
        self._filter.setVisible(loaded)
        self._table.setVisible(loaded)
        self._detail.setVisible(loaded)
        self._empty.setVisible(not loaded)

        if not loaded or report is None:
            self._identity.clear()
            self._summary.clear()
            self._metadata.clear()
            self._empty.setText(
                "Open a supported compact historical experiment JSON report to "
                "explore its read-only results."
            )
            return

        self._empty.clear()
        self._identity.setText(
            f"Report {report.report_id}  •  Experiment {report.experiment_result_id}"
        )
        self._summary.setText(
            f"{report.variant_source}  •  {report.row_count} result(s)  •  "
            f"{report.ranking_summary}"
        )
        self._metadata.setText(report.metadata_summary)
        self._populate_table(report.rows)
        if self._table.rowCount():
            self._table.selectRow(0)

    def _populate_table(self, rows: tuple[ResearchResultRow, ...]) -> None:
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                (
                    "—" if row.rank is None else str(row.rank),
                    (row.rank is None, 0 if row.rank is None else row.rank),
                ),
                (row.variant_label, row.variant_label.casefold()),
                (row.parameter_label, row.parameter_label.casefold()),
                (_percentage(row.total_return), row.total_return),
                (
                    _percentage(row.maximum_drawdown_percentage),
                    row.maximum_drawdown_percentage,
                ),
                (_decimal_text(row.turnover), row.turnover),
                (str(row.trade_count), row.trade_count),
                (
                    _optional_decimal(row.exposure),
                    (
                        row.exposure is None,
                        Decimal("0") if row.exposure is None else row.exposure,
                    ),
                ),
                (
                    _optional_decimal(row.return_over_drawdown),
                    (
                        row.return_over_drawdown is None,
                        (
                            Decimal("0")
                            if row.return_over_drawdown is None
                            else row.return_over_drawdown
                        ),
                    ),
                ),
            )
            for column, (text, sort_value) in enumerate(values):
                self._table.setItem(
                    row_index,
                    column,
                    _SortableTableItem(text, sort_value, row.caller_ordinal),
                )

    def _sort_table(self, column: int) -> None:
        if not 0 <= column < _SORTABLE_COLUMN_COUNT:
            return
        if self._sort_column == column:
            order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = Qt.SortOrder.AscendingOrder
        self._sort_column = column
        self._sort_order = order
        self._table.sortItems(column, order)
        header = self._table.horizontalHeader()
        header.setSortIndicator(column, order)
        header.setSortIndicatorShown(True)

    def _reset_sort_state(self) -> None:
        self._sort_column = None
        self._sort_order = None
        self._table.horizontalHeader().setSortIndicatorShown(False)

    def _apply_filter(self, query: str) -> None:
        report = self._report
        if report is None:
            return
        matches = {
            row.caller_ordinal for row in filter_research_rows(report.rows, query)
        }
        for table_row in range(self._table.rowCount()):
            item = self._table.item(table_row, 0)
            ordinal = item.data(Qt.ItemDataRole.UserRole)
            self._table.setRowHidden(table_row, ordinal not in matches)
        current = self._table.currentRow()
        if current < 0 or self._table.isRowHidden(current):
            self._table.clearSelection()
            for table_row in range(self._table.rowCount()):
                if not self._table.isRowHidden(table_row):
                    self._table.selectRow(table_row)
                    break

    def _update_selected_detail(self) -> None:
        selected = self._table.selectedItems()
        report = self._report
        if not selected or report is None:
            self._set_detail(None)
            return
        ordinal = selected[0].data(Qt.ItemDataRole.UserRole)
        self._set_detail(report.rows[ordinal])

    def _set_detail(self, row: ResearchResultRow | None) -> None:
        if row is None:
            for value in self._detail_values.values():
                value.setText("—")
            return
        values = {
            "rank": "—" if row.rank is None else str(row.rank),
            "variant": row.variant_label,
            "parameters": row.parameter_label,
            "return": _percentage(row.total_return),
            "drawdown": _percentage(row.maximum_drawdown_percentage),
            "turnover": _decimal_text(row.turnover),
            "trades": str(row.trade_count),
            "exposure": _optional_decimal(row.exposure),
            "return_drawdown": _optional_decimal(row.return_over_drawdown),
        }
        for key, value in values.items():
            self._detail_values[key].setText(value)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _percentage(value: Decimal) -> str:
    return f"{format(value * 100, 'f')}%"


def _optional_decimal(value: Decimal | None) -> str:
    return "Unavailable" if value is None else _decimal_text(value)
