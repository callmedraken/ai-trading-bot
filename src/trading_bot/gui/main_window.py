"""Qt presentation shell for the GUI application foundation."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.market_data_page import MarketDataPage
from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
)
from trading_bot.gui.paper_page import PaperPage
from trading_bot.gui.research_page import ResearchPage
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
        research_state = service.get_research_state()
        paper_state = service.get_paper_state()
        market_data_state = service.get_market_data_state()
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
        self._research_page = ResearchPage(research_state, service, self)
        self._stack.addWidget(self._research_page)
        self._paper_page = PaperPage(paper_state, self)
        self._stack.addWidget(self._paper_page)
        self._market_data_page = MarketDataPage(market_data_state, self)
        self._stack.addWidget(self._market_data_page)
        self._stack.addWidget(self._build_system_page(self._overview))

        layout.addWidget(self._navigation)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self._navigation.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._navigation.setCurrentRow(0)
        self._apply_style()

    @property
    def page_ids(self) -> tuple[str, ...]:
        """Return the stable GUI page identifiers."""
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
        mode.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(mode)

        summary = QLabel(overview.summary, page)
        summary.setObjectName("summaryLabel")
        summary.setTextFormat(Qt.TextFormat.PlainText)
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
        heading.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(heading)

        status = QLabel(_STATUS_LABELS[component.status], card)
        status.setObjectName("cardStatus")
        status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(status)

        detail = QLabel(component.detail, card)
        detail.setObjectName("cardDetail")
        detail.setTextFormat(Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        layout.addWidget(detail)

        return card

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
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _build_system_page(self, overview: ApplicationOverview) -> QWidget:
        page = self._build_placeholder_page(
            "System",
            (
                "The GUI is a presentation layer only; it grants no production "
                "authority."
            ),
        )
        layout = page.layout()
        if layout is None:
            raise RuntimeError("system page layout is missing")

        environment = QLabel(f"Environment: {overview.environment}", page)
        environment.setObjectName("systemDetail")
        environment.setTextFormat(Qt.TextFormat.PlainText)
        mode = QLabel(f"Displayed mode: {_MODE_LABELS[overview.mode]}", page)
        mode.setObjectName("systemDetail")
        mode.setTextFormat(Qt.TextFormat.PlainText)
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
            QLabel#researchPath, QLabel#researchMetadata {
                color: #94a3b8;
            }
            QLabel#paperStatus {
                color: #fbbf24;
                font-weight: 700;
            }
            QLabel#paperFieldLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QLabel#paperClassification, QLabel#paperDiagnostic,
            QLabel#paperOperationId, QLabel#paperTerminalCheckpointId,
            QLabel#paperApplicationId, QLabel#paperReceiptPath {
                color: #e5e7eb;
            }
            QFrame#paperDetailPanel {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QLabel#marketDataStatus[status="verified"] {
                color: #86efac;
                font-weight: 700;
            }
            QLabel#marketDataStatus[status="unavailable"] {
                color: #fbbf24;
                font-weight: 700;
            }
            QLabel#marketDataFieldLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QLabel#marketDataSnapshotId, QLabel#marketDataTargetSession,
            QLabel#marketDataSymbols, QLabel#marketDataProviderId,
            QLabel#marketDataProviderOperation, QLabel#marketDataProviderFeed,
            QLabel#marketDataArtifactSha256, QLabel#marketDataArtifactByteLength,
            QLabel#marketDataCapturedAt, QLabel#marketDataProviderAsOf,
            QLabel#marketDataSourcePayloadSha256,
            QLabel#marketDataSourcePayloadByteLength,
            QLabel#marketDataSourcePayloadMediaType {
                color: #e5e7eb;
            }
            QFrame#marketDataDetailPanel {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QLineEdit#researchFilter {
                background: #0b1220;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 7px;
                padding: 8px 10px;
            }
            QPushButton#openResearchReportButton,
            QPushButton#addResearchComparisonButton,
            QPushButton#removeResearchComparisonButton,
            QPushButton#clearResearchComparisonButton {
                background: #2563eb;
                color: #f8fafc;
                border: 0;
                border-radius: 7px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton#openResearchReportButton:hover,
            QPushButton#addResearchComparisonButton:hover,
            QPushButton#removeResearchComparisonButton:hover,
            QPushButton#clearResearchComparisonButton:hover {
                background: #1d4ed8;
            }
            QFrame#researchDetailPanel, QFrame#researchComparisonPanel {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QLabel#researchComparisonTitle {
                font-size: 16px;
                font-weight: 700;
                color: #f8fafc;
            }
            QLabel#researchComparisonCount, QLabel#researchComparisonNotice {
                color: #94a3b8;
            }
            QTableWidget#researchResultsTable,
            QTableWidget#researchComparisonTable {
                background: #111827;
                alternate-background-color: #162033;
                color: #e5e7eb;
                gridline-color: #2a3950;
                border: 1px solid #2a3950;
                selection-background-color: #25344a;
                selection-color: #f9fafb;
            }
            QTableWidget#researchResultsTable::item,
            QTableWidget#researchComparisonTable::item {
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
