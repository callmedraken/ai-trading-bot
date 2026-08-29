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
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.comparison_chart import ResearchComparisonChart
from trading_bot.gui.models import (
    MAX_RESEARCH_COMPARISON_VARIANTS,
    MIN_RESEARCH_COMPARISON_VARIANTS,
    ResearchComparisonState,
    ResearchPageState,
    ResearchReportStatus,
    ResearchResultRow,
    format_decimal_for_display,
    format_percentage_for_display,
)
from trading_bot.gui.research_service import (
    MAX_RESEARCH_FILTER_CHARACTERS,
    filter_research_rows,
)
from trading_bot.gui.services import ResearchReportLoader

_HEADERS = (
    "Rank",
    "Variant",
    "Parameters",
    "Total return",
    "Max drawdown",
    "One-way turnover",
    "Fills",
    "Exposure",
    "Return / drawdown",
)
_SORTABLE_COLUMN_COUNT = 7
_COMPARISON_HEADERS = _HEADERS[:_SORTABLE_COLUMN_COUNT]


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

    def __init__(
        self,
        state: ResearchPageState,
        loader: ResearchReportLoader,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader = loader
        self._state = state
        self._report = state.report
        self._comparison_state = ResearchComparisonState()
        self.setObjectName("researchPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName("researchScrollArea")
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.viewport().setObjectName("researchScrollViewport")
        self._scroll_area.viewport().setStyleSheet("background: #111827;")

        content = QWidget(self._scroll_area)
        content.setObjectName("researchScrollContent")
        content.setStyleSheet("background: #111827;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 26, 28, 26)
        content_layout.setSpacing(12)

        heading = QHBoxLayout()
        title = QLabel("Historical Research", self)
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        self._open_button = QPushButton("Open Report…", self)
        self._open_button.setObjectName("openResearchReportButton")
        self._open_button.clicked.connect(self.open_report)
        heading.addWidget(self._open_button)
        content_layout.addLayout(heading)

        self._status = QLabel(self)
        self._status.setObjectName("summaryLabel")
        self._status.setWordWrap(True)
        content_layout.addWidget(self._status)

        self._path = QLabel(self)
        self._path.setObjectName("researchPath")
        self._path.setWordWrap(True)
        self._path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_layout.addWidget(self._path)

        self._identity = QLabel(self)
        self._identity.setObjectName("researchIdentity")
        self._identity.setWordWrap(True)
        self._identity.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_layout.addWidget(self._identity)

        self._summary = QLabel(self)
        self._summary.setObjectName("researchSummary")
        self._summary.setWordWrap(True)
        content_layout.addWidget(self._summary)

        self._metadata = QLabel(self)
        self._metadata.setObjectName("researchMetadata")
        self._metadata.setWordWrap(True)
        content_layout.addWidget(self._metadata)

        self._empty = QLabel(self)
        self._empty.setObjectName("researchEmptyState")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(self._empty)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("researchFilter")
        self._filter.setPlaceholderText("Filter variants or parameter assignments")
        self._filter.setClearButtonEnabled(True)
        self._filter.setMaxLength(MAX_RESEARCH_FILTER_CHARACTERS)
        self._filter.textChanged.connect(self._apply_filter)
        content_layout.addWidget(self._filter)

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
        content_layout.addWidget(self._table, 1)

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
            ("one_way_turnover", "One-way turnover"),
            ("fills", "Total fills"),
            ("exposure", "Exposure"),
            ("return_drawdown", "Return / drawdown"),
        ):
            value = QLabel("—", self._detail)
            value.setObjectName(f"researchDetail{key.title().replace('_', '')}")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._detail_values[key] = value
            detail_layout.addRow(label, value)
        content_layout.addWidget(self._detail)
        self._comparison = QFrame(self)
        self._comparison.setObjectName("researchComparisonPanel")
        comparison_layout = QVBoxLayout(self._comparison)
        comparison_layout.setContentsMargins(14, 12, 14, 12)
        comparison_heading = QHBoxLayout()
        comparison_title = QLabel("Variant comparison", self._comparison)
        comparison_title.setObjectName("researchComparisonTitle")
        comparison_heading.addWidget(comparison_title)
        comparison_heading.addStretch(1)
        self._comparison_count = QLabel(self._comparison)
        self._comparison_count.setObjectName("researchComparisonCount")
        comparison_heading.addWidget(self._comparison_count)
        comparison_layout.addLayout(comparison_heading)

        comparison_actions = QHBoxLayout()
        self._add_comparison_button = QPushButton(
            "Add selected result", self._comparison
        )
        self._add_comparison_button.setObjectName("addResearchComparisonButton")
        self._add_comparison_button.clicked.connect(self.add_selected_to_comparison)
        comparison_actions.addWidget(self._add_comparison_button)
        self._remove_comparison_button = QPushButton(
            "Remove comparison", self._comparison
        )
        self._remove_comparison_button.setObjectName("removeResearchComparisonButton")
        self._remove_comparison_button.clicked.connect(self.remove_selected_comparison)
        comparison_actions.addWidget(self._remove_comparison_button)
        self._clear_comparison_button = QPushButton(
            "Clear comparison", self._comparison
        )
        self._clear_comparison_button.setObjectName("clearResearchComparisonButton")
        self._clear_comparison_button.clicked.connect(self.clear_comparison)
        comparison_actions.addWidget(self._clear_comparison_button)
        comparison_actions.addStretch(1)
        comparison_layout.addLayout(comparison_actions)

        self._comparison_notice = QLabel(self._comparison)
        self._comparison_notice.setObjectName("researchComparisonNotice")
        self._comparison_notice.setWordWrap(True)
        comparison_layout.addWidget(self._comparison_notice)

        self._comparison_table = QTableWidget(
            0, len(_COMPARISON_HEADERS), self._comparison
        )
        self._comparison_table.setObjectName("researchComparisonTable")
        self._comparison_table.setHorizontalHeaderLabels(_COMPARISON_HEADERS)
        self._comparison_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._comparison_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._comparison_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._comparison_table.setAlternatingRowColors(True)
        self._comparison_table.verticalHeader().setVisible(False)
        self._comparison_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._comparison_table.horizontalHeader().setStretchLastSection(True)
        comparison_layout.addWidget(self._comparison_table)

        self._comparison_chart = ResearchComparisonChart(self._comparison)
        comparison_layout.addWidget(self._comparison_chart)
        content_layout.addWidget(self._comparison)
        self._scroll_area.setWidget(content)
        layout.addWidget(self._scroll_area, 1)

        for label in (
            title,
            self._status,
            self._path,
            self._identity,
            self._summary,
            self._metadata,
            self._empty,
            *self._detail_values.values(),
            comparison_title,
            self._comparison_count,
            self._comparison_notice,
        ):
            label.setTextFormat(Qt.TextFormat.PlainText)

        self.set_research_state(state)

    @property
    def research_state(self) -> ResearchPageState:
        """Return the current immutable research presentation state."""
        return self._state

    @property
    def comparison_state(self) -> ResearchComparisonState:
        """Return the bounded GUI-only comparison selection."""
        return self._comparison_state

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
        self.set_research_state(self._loader.load_research_report(Path(selected)))

    def set_research_state(self, state: ResearchPageState) -> None:
        """Replace only the displayed bounded research state."""
        if type(state) is not ResearchPageState:
            raise TypeError("state must be exactly ResearchPageState")
        self._state = state
        self._report = state.report
        self._comparison_state = ResearchComparisonState()
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
        self._comparison.setVisible(loaded)
        self._empty.setVisible(not loaded)
        self._refresh_comparison()

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

    def add_selected_to_comparison(self) -> None:
        """Add the selected result identity to the bounded comparison."""
        selected = self._table.selectedItems()
        if not selected or self._report is None:
            return
        ordinal = selected[0].data(Qt.ItemDataRole.UserRole)
        previous = self._comparison_state
        self._comparison_state = previous.select(ordinal)
        if self._comparison_state is previous and previous.count >= 4:
            self._comparison_notice.setText(
                "Comparison is limited to 4 variants. Remove one before adding another."
            )
            return
        self._refresh_comparison()

    def remove_selected_comparison(self) -> None:
        """Remove the explicitly selected row from the comparison."""
        selected = self._comparison_table.selectedItems()
        if not selected:
            return
        ordinal = selected[0].data(Qt.ItemDataRole.UserRole)
        self._comparison_state = self._comparison_state.remove(ordinal)
        self._refresh_comparison()

    def clear_comparison(self) -> None:
        """Clear all GUI-only comparison identities."""
        self._comparison_state = self._comparison_state.clear()
        self._refresh_comparison()

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
                (
                    _decimal_text(row.aggregate_one_way_turnover),
                    row.aggregate_one_way_turnover,
                ),
                (str(row.total_fills), row.total_fills),
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
            "one_way_turnover": _decimal_text(row.aggregate_one_way_turnover),
            "fills": str(row.total_fills),
            "exposure": _optional_decimal(row.exposure),
            "return_drawdown": _optional_decimal(row.return_over_drawdown),
        }
        for key, value in values.items():
            self._detail_values[key].setText(value)

    def _refresh_comparison(self) -> None:
        report = self._report
        rows_by_ordinal = (
            {} if report is None else {row.caller_ordinal: row for row in report.rows}
        )
        selected_rows = tuple(
            rows_by_ordinal[ordinal]
            for ordinal in self._comparison_state.caller_ordinals
            if ordinal in rows_by_ordinal
        )
        if len(selected_rows) != self._comparison_state.count:
            self._comparison_state = ResearchComparisonState(
                tuple(row.caller_ordinal for row in selected_rows)
            )

        count = self._comparison_state.count
        self._comparison_count.setText(
            f"{count} / {MAX_RESEARCH_COMPARISON_VARIANTS} slots selected"
        )
        if count < MIN_RESEARCH_COMPARISON_VARIANTS:
            self._comparison_notice.setText(
                "Select a result above, then add 2 to 4 variants for comparison."
            )
        else:
            self._comparison_notice.setText(
                f"Comparing {count} variants in stable report order."
            )

        self._comparison_table.clearContents()
        self._comparison_table.setRowCount(len(selected_rows))
        for row_index, row in enumerate(selected_rows):
            values = (
                "—" if row.rank is None else str(row.rank),
                row.variant_label,
                row.parameter_label,
                _percentage(row.total_return),
                _percentage(row.maximum_drawdown_percentage),
                _decimal_text(row.aggregate_one_way_turnover),
                str(row.total_fills),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.caller_ordinal)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._comparison_table.setItem(row_index, column, item)
        self._remove_comparison_button.setEnabled(bool(selected_rows))
        self._clear_comparison_button.setEnabled(bool(selected_rows))
        self._add_comparison_button.setEnabled(
            report is not None and count < MAX_RESEARCH_COMPARISON_VARIANTS
        )
        self._comparison_chart.set_rows(
            selected_rows if self._comparison_state.is_ready else ()
        )


def _decimal_text(value: Decimal) -> str:
    return format_decimal_for_display(value)


def _percentage(value: Decimal) -> str:
    return format_percentage_for_display(value)


def _optional_decimal(value: Decimal | None) -> str:
    return "Unavailable" if value is None else _decimal_text(value)
