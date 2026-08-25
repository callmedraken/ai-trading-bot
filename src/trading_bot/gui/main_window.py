"""Qt presentation shell for the GUI application foundation."""

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchPageState,
    ResearchReportStatus,
)
from trading_bot.gui.services import GuiApplicationService

PAGE_IDS = ("home", "research", "paper", "market-data", "system")

_MODE_LABELS = {
    OperatingMode.RESEARCH: "Research",
    OperatingMode.SIMULATED_PAPER: "Simulated Paper",
    OperatingMode.BROKER_PAPER: "Broker Paper",
    OperatingMode.LIVE: "Live",
}

_STATUS_LABELS = {
    PresentationStatus.INFO: "Info",
    PresentationStatus.HEALTHY: "Ready",
    PresentationStatus.UNAVAILABLE: "Unavailable",
    PresentationStatus.BLOCKED: "Blocked",
}

_STATUS_PROPERTIES = {
    PresentationStatus.INFO: "info",
    PresentationStatus.HEALTHY: "healthy",
    PresentationStatus.UNAVAILABLE: "unavailable",
    PresentationStatus.BLOCKED: "blocked",
}


class MainWindow(QMainWindow):
    """Read-only native application shell backed by a GUI service protocol."""

    def __init__(self, service: GuiApplicationService) -> None:
        super().__init__()
        self._overview = service.get_overview()
        self._research_state = service.get_research_state()
        self._page_index = {page_id: index for index, page_id in enumerate(PAGE_IDS)}

        self.setWindowTitle("AI Trading Bot")
        self.resize(1180, 760)
        self.setMinimumSize(920, 620)

        root = QWidget(self)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._navigation = self._build_navigation()
        self._stack = QStackedWidget(root)
        self._stack.setObjectName("pageStack")

        self._stack.addWidget(self._build_home_page(self._overview))
        self._stack.addWidget(self._build_research_page(self._research_state))
        self._stack.addWidget(
            self._build_placeholder_page(
                "Paper Operation",
                "GUI-A1 is read-only and exposes no paper execution controls.",
            )
        )
        self._stack.addWidget(
            self._build_placeholder_page(
                "Market Data",
                "Production capture and credentials are intentionally not connected.",
            )
        )
        self._stack.addWidget(self._build_system_page(self._overview))

        layout.addWidget(self._navigation)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self._navigation.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._navigation.setCurrentRow(0)
        self._apply_style()

    @property
    def page_ids(self) -> tuple[str, ...]:
        """Return the stable GUI-A1 page identifiers."""
        return PAGE_IDS

    @property
    def current_page_id(self) -> str:
        """Return the stable identifier for the currently visible page."""
        index = self._stack.currentIndex()
        return PAGE_IDS[index]

    def select_page(self, page_id: str) -> None:
        """Select one page without invoking any application effect."""
        try:
            index = self._page_index[page_id]
        except KeyError as error:
            raise ValueError(f"unknown GUI page: {page_id}") from error
        self._navigation.setCurrentRow(index)

    def _build_navigation(self) -> QListWidget:
        navigation = QListWidget(self)
        navigation.setObjectName("navigation")
        navigation.setFixedWidth(210)
        navigation.setSpacing(4)

        labels = {
            "home": "Overview",
            "research": "Research",
            "paper": "Paper",
            "market-data": "Market Data",
            "system": "System",
        }
        for page_id in PAGE_IDS:
            item = QListWidgetItem(labels[page_id])
            item.setData(Qt.ItemDataRole.UserRole, page_id)
            navigation.addItem(item)

        return navigation

    def _build_home_page(self, overview: ApplicationOverview) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(18)

        title = QLabel("AI Trading Bot", page)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        mode = QLabel(
            f"{_MODE_LABELS[overview.mode]}  •  {overview.environment}",
            page,
        )
        mode.setObjectName("modeLabel")
        layout.addWidget(mode)

        summary = QLabel(overview.summary, page)
        summary.setObjectName("summaryLabel")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        for index, component in enumerate(overview.components):
            cards.addWidget(
                self._build_status_card(component),
                index // 2,
                index % 2,
            )
        layout.addLayout(cards)
        layout.addStretch(1)
        return page

    def _build_status_card(self, component: ComponentStatus) -> QFrame:
        card = QFrame(self)
        card.setObjectName("statusCard")
        card.setProperty("status", _STATUS_PROPERTIES[component.status])

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        heading = QLabel(component.title, card)
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)

        status = QLabel(_STATUS_LABELS[component.status], card)
        status.setObjectName("cardStatus")
        layout.addWidget(status)

        detail = QLabel(component.detail, card)
        detail.setObjectName("cardDetail")
        detail.setWordWrap(True)
        layout.addWidget(detail)

        return card

    def _build_research_page(self, state: ResearchPageState) -> QWidget:
        page = QWidget(self)
        page.setObjectName("researchPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)

        title = QLabel("Historical Research", page)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        status = QLabel(state.message, page)
        status.setObjectName("summaryLabel")
        status.setWordWrap(True)
        layout.addWidget(status)

        if state.status is ResearchReportStatus.UNAVAILABLE:
            empty = QLabel(
                "Generate a compact JSON report with the existing historical "
                "experiment CLI, then provide it through the GUI research service.",
                page,
            )
            empty.setObjectName("researchEmptyState")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(empty)
            layout.addStretch(1)
            return page

        report = state.report
        if report is None:
            raise RuntimeError("loaded research state is missing its report")
        identity = QLabel(
            f"Report {report.report_id}  •  Experiment {report.experiment_result_id}",
            page,
        )
        identity.setObjectName("researchIdentity")
        identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(identity)

        summary = QLabel(
            f"{report.variant_source}  •  {report.row_count} result(s)  •  "
            f"{report.ranking_summary}",
            page,
        )
        summary.setObjectName("researchSummary")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        metadata = QLabel(report.metadata_summary, page)
        metadata.setObjectName("researchMetadata")
        metadata.setWordWrap(True)
        layout.addWidget(metadata)

        headers = (
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
        table = QTableWidget(report.row_count, len(headers), page)
        table.setObjectName("researchResultsTable")
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setStretchLastSection(True)
        for row_index, row in enumerate(report.rows):
            values = (
                "—" if row.rank is None else str(row.rank),
                row.variant_label,
                row.parameter_label,
                _percentage(row.total_return),
                _percentage(row.maximum_drawdown_percentage),
                _decimal_text(row.turnover),
                str(row.trade_count),
                _optional_decimal(row.exposure),
                _optional_decimal(row.return_over_drawdown),
            )
            for column, value in enumerate(values):
                table.setItem(row_index, column, QTableWidgetItem(value))
        layout.addWidget(table, 1)
        return page

    def _build_placeholder_page(self, title_text: str, body_text: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        title = QLabel(title_text, page)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        body = QLabel(body_text, page)
        body.setObjectName("summaryLabel")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _build_system_page(self, overview: ApplicationOverview) -> QWidget:
        page = self._build_placeholder_page(
            "System",
            (
                "GUI-A1 reports presentation state only; it grants no production "
                "authority."
            ),
        )
        layout = page.layout()
        if layout is None:
            raise RuntimeError("system page layout is missing")

        environment = QLabel(f"Environment: {overview.environment}", page)
        environment.setObjectName("systemDetail")
        mode = QLabel(f"Displayed mode: {_MODE_LABELS[overview.mode]}", page)
        mode.setObjectName("systemDetail")
        layout.insertWidget(2, environment)
        layout.insertWidget(3, mode)
        return page

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111827;
                color: #e5e7eb;
                font-size: 14px;
            }
            QLabel {
                background: transparent;
            }
            QListWidget#navigation {
                background: #0b1220;
                border: 0;
                border-right: 1px solid #263244;
                padding: 22px 10px;
                outline: 0;
            }
            QListWidget#navigation::item {
                border-radius: 8px;
                padding: 11px 12px;
                margin: 2px 0;
                color: #cbd5e1;
            }
            QListWidget#navigation::item:selected {
                background: #1f2937;
                color: #f9fafb;
            }
            QLabel#pageTitle {
                font-size: 28px;
                font-weight: 700;
                color: #f9fafb;
            }
            QLabel#modeLabel {
                font-size: 14px;
                font-weight: 600;
                color: #93c5fd;
            }
            QLabel#summaryLabel, QLabel#cardDetail, QLabel#systemDetail {
                color: #aebbd0;
            }
            QFrame#statusCard {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 10px;
            }
            QLabel#cardTitle {
                font-size: 16px;
                font-weight: 700;
                color: #f8fafc;
            }
            QLabel#cardStatus {
                font-size: 12px;
                font-weight: 700;
                color: #93c5fd;
            }
            QTableWidget#researchResultsTable {
                background: #111827;
                alternate-background-color: #162033;
                color: #e5e7eb;
                gridline-color: #2a3950;
                border: 1px solid #2a3950;
                selection-background-color: #25344a;
                selection-color: #f9fafb;
            }
            QTableWidget#researchResultsTable::item {
                padding: 6px;
            }
            QHeaderView::section {
                background: #182235;
                color: #cbd5e1;
                border: 0;
                border-right: 1px solid #2a3950;
                border-bottom: 1px solid #2a3950;
                padding: 7px 8px;
                font-weight: 600;
            }
            """
        )


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _percentage(value: Decimal) -> str:
    return f"{format(value * 100, 'f')}%"


def _optional_decimal(value: Decimal | None) -> str:
    return "—" if value is None else _decimal_text(value)
