"""Qt presentation shell for the GUI application foundation."""

from dataclasses import replace
from typing import Protocol

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
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

from trading_bot.desktop_paper.presentation import DesktopPaperSnapshot
from trading_bot.desktop_runtime import DesktopStatus, DesktopSupervisor
from trading_bot.gui.desktop_control import DesktopControl
from trading_bot.gui.desktop_paper_panel import DesktopPaperPanel
from trading_bot.gui.evidence_navigation import EvidenceNavigationTarget
from trading_bot.gui.evidence_source_navigation import EvidenceSourcePageTarget
from trading_bot.gui.evidence_timeline_adapter import build_evidence_timeline_state
from trading_bot.gui.evidence_timeline_page import EvidenceTimelinePage
from trading_bot.gui.market_data_page import MarketDataPage
from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
)
from trading_bot.gui.operator_observability_page import OperatorOperationsPage
from trading_bot.gui.paper_account_page import PaperAccountPage
from trading_bot.gui.paper_page import PaperPage
from trading_bot.gui.research_candidate_lifecycle_page import (
    ResearchCandidateLifecyclePage,
)
from trading_bot.gui.research_page import ResearchPage
from trading_bot.gui.runtime_page import RuntimePage
from trading_bot.gui.services import GuiApplicationService
from trading_bot.gui.supervisor_adapter import build_supervisor_state
from trading_bot.gui.supervisor_page import SupervisorPage
from trading_bot.gui.system_health_adapter import build_system_health_state
from trading_bot.gui.system_health_page import SystemHealthPage

PAGE_IDS = (
    "home",
    "research",
    "research-lifecycle",
    "paper",
    "paper-account",
    "market-data",
    "operations",
    "runtime",
    "supervisor",
    "evidence",
    "system",
)

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


class DesktopPaperRuntimeController(Protocol):
    """Qt lifecycle and cached snapshot boundary for the P5 runtime."""

    def snapshot(self) -> DesktopPaperSnapshot: ...
    def status(self) -> DesktopStatus: ...
    def start(self) -> bool: ...
    def stop(self) -> None: ...
    def dispose(self) -> bool: ...


class MainWindow(QMainWindow):
    """Artifact presentation shell with optional current desktop controls."""

    def __init__(
        self,
        service: GuiApplicationService,
        *,
        desktop_controller: DesktopSupervisor | None = None,
        paper_controller: DesktopPaperRuntimeController | None = None,
    ) -> None:
        super().__init__()
        self._desktop_controller: (
            DesktopSupervisor | DesktopPaperRuntimeController | None
        ) = paper_controller if paper_controller is not None else desktop_controller
        self._desktop_close_pending = False
        self._overview = service.get_overview()
        if paper_controller is None and desktop_controller is not None:
            self._overview = replace(
                self._overview,
                mode=OperatingMode.SIMULATED_PAPER,
                environment="Local desktop · P4 inert workers",
                summary=(
                    "Start runs the local trading and offline research workers. "
                    "Trading is inert; external transport is not connected. "
                    "Stop reconciles and closes both before manual updates."
                ),
            )
        if paper_controller is not None:
            selected = paper_controller.snapshot().binding is not None
            self._overview = replace(
                self._overview,
                mode=OperatingMode.SIMULATED_PAPER,
                environment="Local desktop · simulated paper evaluation",
                summary=(
                    (
                        "The desktop runs a local simulated-paper evaluation over "
                        "the OPEN replay lane. Paper strategy: Selection required. "
                        "Trading unavailable until an accepted PAPER_EVALUATION "
                        "binding is installed."
                    )
                    if not selected
                    else (
                        "The desktop runs a local simulated-paper evaluation over "
                        "the OPEN replay lane using the explicitly configured "
                        "PAPER_EVALUATION binding. LIVE is unavailable."
                    )
                ),
                components=(
                    ComponentStatus(
                        key="paper",
                        title="Simulated paper evaluation",
                        status=(
                            PresentationStatus.INFO
                            if selected
                            else PresentationStatus.UNAVAILABLE
                        ),
                        detail=(
                            "Explicit paper strategy binding is configured."
                            if selected
                            else "Paper strategy: Selection required"
                        ),
                    ),
                    ComponentStatus(
                        key="research",
                        title="Offline research",
                        status=PresentationStatus.INFO,
                        detail=(
                            "Research artifacts remain read-only and do not select "
                            "the paper strategy."
                        ),
                    ),
                ),
            )
        research_state = service.get_research_state()
        paper_state = service.get_paper_state()
        paper_account_state = service.get_paper_account_state()
        market_data_state = service.get_market_data_state()
        operations_state = service.get_operator_observability_state()
        runtime_state = service.get_runtime_state()
        strategy_state = service.get_production_strategy_state()
        lifecycle_state = service.get_research_candidate_lifecycle_state()
        supervisor_state = build_supervisor_state(
            research_state, runtime_state, strategy_state, lifecycle_state
        )
        evidence_timeline_state = build_evidence_timeline_state(
            research_state,
            paper_state,
            paper_account_state,
            market_data_state,
            operations_state,
            runtime_state,
            supervisor_state,
            lifecycle_state,
        )
        system_health_state = build_system_health_state(
            self._overview,
            research_state,
            paper_state,
            paper_account_state,
            market_data_state,
            operations_state,
            runtime_state,
            supervisor_state,
            lifecycle_state,
        )
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

        home = self._build_home_page(self._overview)
        if self._desktop_controller is not None:
            if paper_controller is not None:
                self._desktop_control = DesktopControl(
                    paper_controller,
                    home,
                    heading=(
                        "Desktop bot · local simulated-paper evaluation · LIVE disabled"
                    ),
                    transport_note="no broker connection",
                    research_waiting=(
                        "Research: idle; no bundle acquisition or campaign scheduled"
                    ),
                )
            else:
                self._desktop_control = DesktopControl(desktop_controller, home)
            home.layout().insertWidget(0, self._desktop_control)
            self._desktop_close_timer = QTimer(self)
            self._desktop_close_timer.timeout.connect(self._finish_desktop_close)
            self._desktop_close_timer.start(50)
        self._stack.addWidget(home)
        self._research_page = ResearchPage(research_state, service, self)
        self._stack.addWidget(self._research_page)
        self._research_lifecycle_page = ResearchCandidateLifecyclePage(
            lifecycle_state, self
        )
        self._stack.addWidget(self._research_lifecycle_page)
        self._paper_page = PaperPage(paper_state, self)
        if paper_controller is not None:
            self._desktop_paper_panel = DesktopPaperPanel(
                paper_controller, self._paper_page
            )
            self._paper_page.layout().insertWidget(0, self._desktop_paper_panel)
        self._stack.addWidget(self._paper_page)
        self._paper_account_page = PaperAccountPage(paper_account_state, self)
        self._stack.addWidget(self._paper_account_page)
        self._market_data_page = MarketDataPage(market_data_state, self)
        self._stack.addWidget(self._market_data_page)
        self._operations_page = OperatorOperationsPage(operations_state, self)
        self._stack.addWidget(self._operations_page)
        self._runtime_page = RuntimePage(runtime_state, self)
        self._stack.addWidget(self._runtime_page)
        self._supervisor_page = SupervisorPage(supervisor_state, self)
        self._stack.addWidget(self._supervisor_page)
        self._evidence_timeline_page = EvidenceTimelinePage(
            evidence_timeline_state,
            self,
        )
        self._evidence_timeline_page.source_navigation_requested.connect(
            self._show_evidence_source_page_target
        )
        self._stack.addWidget(self._evidence_timeline_page)
        self._system_health_page = SystemHealthPage(system_health_state, self)
        self._system_health_page.evidence_navigation_requested.connect(
            self._show_evidence_navigation_target
        )
        self._stack.addWidget(self._system_health_page)

        layout.addWidget(self._navigation)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

        self._navigation.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._navigation.setCurrentRow(0)
        self._apply_style()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Asynchronous normal Stop on close; failed closure refuses GUI exit."""
        if self._desktop_controller is None:
            super().closeEvent(event)
            return
        if self._desktop_controller.status().can_close:
            if self._desktop_controller.dispose():
                event.accept()
                return
        self._desktop_close_pending = True
        self._desktop_controller.stop()
        event.ignore()

    def _finish_desktop_close(self) -> None:
        if self._desktop_close_pending and self._desktop_controller.status().can_close:
            self.close()

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

    def _show_evidence_navigation_target(
        self,
        target: EvidenceNavigationTarget,
    ) -> None:
        if type(target) is not EvidenceNavigationTarget:
            raise TypeError("target must be an exact EvidenceNavigationTarget")
        self.select_page("evidence")
        self._evidence_timeline_page.show_navigation_target(target)

    def _show_evidence_source_page_target(
        self,
        target: EvidenceSourcePageTarget,
    ) -> None:
        if type(target) is not EvidenceSourcePageTarget:
            raise TypeError("target must be an exact EvidenceSourcePageTarget")
        self.select_page(target.page_id.value)

    def _build_navigation(self) -> QListWidget:
        navigation = QListWidget(self)
        navigation.setObjectName("navigation")
        navigation.setFixedWidth(210)
        navigation.setSpacing(4)

        labels = {
            "home": "Overview",
            "research": "Research",
            "research-lifecycle": "Research Lifecycle",
            "paper": "Paper",
            "paper-account": "Paper Account",
            "market-data": "Market Data",
            "operations": "Operations",
            "runtime": "Runtime",
            "supervisor": "Supervisor",
            "evidence": "Evidence",
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
            QLabel#paperAccountStatus[status="verified"] {
                color: #86efac;
                font-weight: 700;
            }
            QLabel#paperAccountStatus[status="unavailable"] {
                color: #fbbf24;
                font-weight: 700;
            }
            QLabel#paperAccountMessage, QLabel#paperAccountScopeNotice {
                color: #aebbd0;
            }
            QLabel#paperAccountFieldLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QLabel#paperAccountCheckpointKind,
            QLabel#paperAccountSequence,
            QLabel#paperAccountCheckpointId,
            QLabel#paperAccountLineageId,
            QLabel#paperAccountAccountStateId,
            QLabel#paperAccountCompactStateId,
            QLabel#paperAccountAsOf,
            QLabel#paperAccountCash,
            QLabel#paperAccountRealizedProfitLoss,
            QLabel#paperAccountArtifactSha256,
            QLabel#paperAccountArtifactByteLength {
                color: #e5e7eb;
            }
            QFrame#paperAccountDetailPanel {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QTableWidget#paperAccountPositionsTable {
                background: #111827;
                alternate-background-color: #162033;
                color: #e5e7eb;
                gridline-color: #2a3950;
                border: 1px solid #2a3950;
                selection-background-color: #25344a;
                selection-color: #f9fafb;
            }
            QTableWidget#paperAccountPositionsTable::item {
                padding: 6px;
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
            QLabel#paperAccountArtifactSha256,
            QLabel#marketDataArtifactSha256,
            QLabel#marketDataSourcePayloadSha256 {
                font-size: 10px;
            }
            QLabel#operatorOperationsStatus[status="verified"],
            QLabel#operatorGateSummary[status="verified"],
            QLabel#operatorStrategyReadiness[status="ready"] {
                color: #86efac;
                font-weight: 700;
            }
            QLabel#operatorOperationsStatus[status="unavailable"],
            QLabel#operatorStrategyReadiness[status="unavailable"] {
                color: #fbbf24;
                font-weight: 700;
            }
            QLabel#operatorGateSummary[status="blocked"],
            QLabel#operatorStrategyReadiness[status="blocked"] {
                color: #fca5a5;
                font-weight: 700;
            }
            QLabel#operatorOperationsMessage, QLabel#operatorWarmupMissing {
                color: #aebbd0;
            }
            QLabel#operatorSectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #f8fafc;
            }
            QLabel#operatorFieldLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QFrame#operatorOperationsSummaryPanel,
            QFrame#operatorWarmupPanel,
            QFrame#operatorGatePanel,
            QFrame#operatorAccountPanel,
            QFrame#operatorStrategyPanel {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QTableWidget#operatorSelectedC3Table,
            QTableWidget#operatorEffectGateTable {
                background: #111827;
                alternate-background-color: #162033;
                color: #e5e7eb;
                gridline-color: #2a3950;
                border: 1px solid #2a3950;
                selection-background-color: #25344a;
                selection-color: #f9fafb;
            }
            QFrame#marketDataDetailPanel {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QLabel#systemHealthScope,
            QLabel#systemHealthMessage,
            QLabel#systemHealthContext,
            QLabel#systemHealthComponentDetail,
            QLabel#systemHealthEmptyAudit {
                color: #aebbd0;
            }
            QLabel#systemHealthOverallStatus[status="ready"],
            QLabel#systemHealthComponentStatus[status="available"] {
                color: #86efac;
                font-weight: 700;
            }
            QLabel#systemHealthOverallStatus[status="attention"],
            QLabel#systemHealthComponentStatus[status="blocked"] {
                color: #fca5a5;
                font-weight: 700;
            }
            QLabel#systemHealthComponentStatus[status="unavailable"] {
                color: #fbbf24;
                font-weight: 700;
            }
            QLabel#systemHealthSectionTitle,
            QLabel#systemHealthComponentTitle,
            QLabel#systemHealthAuditTitle {
                color: #f8fafc;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#systemHealthFieldLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QFrame#systemHealthComponentCard,
            QFrame#systemHealthAuditCard {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QPushButton#systemHealthViewEvidenceButton {
                background: transparent;
                color: #93c5fd;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 9px;
                font-weight: 600;
            }
            QPushButton#systemHealthViewEvidenceButton:hover {
                background: #1f2937;
                color: #bfdbfe;
            }
            QPushButton#evidenceTimelineViewSourceButton {
                background: transparent;
                color: #93c5fd;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 9px;
                font-weight: 600;
            }
            QPushButton#evidenceTimelineViewSourceButton:hover {
                background: #1f2937;
                color: #bfdbfe;
            }
            QLineEdit[readOnly="true"] {
                background: #0b1220;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 7px;
            }
            QScrollArea#systemHealthScroll {
                background: transparent;
                border: 0;
            }
            QLabel#evidenceTimelineScope,
            QLabel#evidenceTimelineMessage,
            QLabel#evidenceTimelineEmpty,
            QLabel#evidenceTimelineDetail,
            QLabel#evidenceTimelineTimestamp {
                color: #aebbd0;
            }
            QLabel#evidenceTimelineEntryTitle,
            QLabel#evidenceTimelineExplorerTitle {
                color: #f8fafc;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#evidenceTimelineFilterCount {
                color: #94a3b8;
            }
            QLabel#evidenceTimelineFieldLabel {
                color: #94a3b8;
                font-weight: 600;
            }
            QFrame#evidenceTimelineCard {
                background: #182235;
                border: 1px solid #2a3950;
                border-radius: 8px;
            }
            QScrollArea#evidenceTimelineScroll {
                background: transparent;
                border: 0;
            }
            QLineEdit#evidenceTimelineSearch,
            QComboBox#evidenceTimelineSourceFilter {
                background: #0b1220;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 7px;
                padding: 7px 9px;
            }
            QComboBox#evidenceTimelineSourceFilter QAbstractItemView {
                background: #0b1220;
                color: #e5e7eb;
                selection-background-color: #25344a;
                selection-color: #f9fafb;
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
