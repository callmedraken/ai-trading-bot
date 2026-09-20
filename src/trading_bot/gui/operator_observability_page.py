"""Native read-only Operations page for bounded PD4 observability state."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.models import format_decimal_for_display
from trading_bot.gui.operator_observability_models import (
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorWarmupClassification,
)


def _plain_label(text: str, parent: QWidget, object_name: str) -> QLabel:
    label = QLabel(parent)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    return label


class OperatorOperationsPage(QWidget):
    """Render one immutable operator snapshot without exposing any effect control."""

    def __init__(
        self,
        state: OperatorOperationsPageState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if type(state) is not OperatorOperationsPageState:
            raise TypeError("state must be exactly OperatorOperationsPageState")

        self._state = state
        self.setObjectName("operatorOperationsPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        layout.addWidget(_plain_label("Operations", self, "pageTitle"))

        status = _plain_label(
            (
                "Read-only Snapshot"
                if state.status is OperatorOperationsPageStatus.AVAILABLE
                else "Unavailable"
            ),
            self,
            "operatorOperationsStatus",
        )
        status.setProperty(
            "status",
            (
                "verified"
                if state.status is OperatorOperationsPageStatus.AVAILABLE
                else "unavailable"
            ),
        )
        layout.addWidget(status)

        message = _plain_label(
            state.message,
            self,
            "operatorOperationsMessage",
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        if state.status is OperatorOperationsPageStatus.AVAILABLE:
            layout.addWidget(self._build_cycle_summary())
            layout.addWidget(self._build_warmup_panel())
            layout.addWidget(self._build_gate_table())
            layout.addWidget(self._build_account_summary())
            layout.addWidget(self._build_strategy_summary())

        layout.addStretch(1)

    @property
    def operations_state(self) -> OperatorOperationsPageState:
        """Return the immutable state rendered by this page."""
        return self._state

    def _build_cycle_summary(self) -> QFrame:
        state = self._state
        panel = QFrame(self)
        panel.setObjectName("operatorOperationsSummaryPanel")
        form = QFormLayout(panel)
        form.setContentsMargins(18, 16, 18, 16)
        form.setVerticalSpacing(10)

        fields = (
            (
                "Daily cycle",
                state.cycle_classification or "Unavailable",
                "operatorCycleClassification",
            ),
            (
                "Completed XNYS session",
                (
                    state.completed_session.isoformat()
                    if state.completed_session is not None
                    else "Unavailable"
                ),
                "operatorCompletedSession",
            ),
            (
                "Market-data classification",
                state.market_data_classification or "Unavailable",
                "operatorMarketDataClassification",
            ),
            (
                "Selected snapshot",
                (
                    str(state.selected_snapshot_id)
                    if state.selected_snapshot_id is not None
                    else "Unavailable"
                ),
                "operatorSelectedSnapshotId",
            ),
        )
        for field_name, value, object_name in fields:
            form.addRow(
                _plain_label(field_name, panel, "operatorFieldLabel"),
                self._selectable_value(value, panel, object_name),
            )
        return panel

    def _build_warmup_panel(self) -> QFrame:
        state = self._state
        panel = QFrame(self)
        panel.setObjectName("operatorWarmupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = _plain_label(
            "D5 Selected-C3 History",
            panel,
            "operatorSectionTitle",
        )
        layout.addWidget(title)

        if state.warmup is None:
            layout.addWidget(
                _plain_label(
                    "No selected-C3 history is available for this snapshot.",
                    panel,
                    "operatorWarmupProgress",
                )
            )
            return panel

        warmup = state.warmup
        progress = _plain_label(
            (
                f"{warmup.classification.value.upper()}  •  "
                f"{warmup.selected_count} / {warmup.target_count}"
            ),
            panel,
            "operatorWarmupProgress",
        )
        layout.addWidget(progress)

        missing = _plain_label(
            (
                "Missing sessions: none"
                if not warmup.missing_sessions
                else "Missing sessions: "
                + ", ".join(value.isoformat() for value in warmup.missing_sessions)
            ),
            panel,
            "operatorWarmupMissing",
        )
        missing.setWordWrap(True)
        layout.addWidget(missing)

        table = QTableWidget(panel)
        table.setObjectName("operatorSelectedC3Table")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ("Session", "Symbol", "Close", "Snapshot ID", "Selection ID")
        )
        table.setRowCount(len(warmup.selected_sessions))
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionsClickable(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for row, item in enumerate(warmup.selected_sessions):
            values = (
                item.session_date.isoformat(),
                item.symbol,
                format_decimal_for_display(item.close),
                str(item.snapshot_id),
                str(item.selection_id),
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, cell)

        table.setMaximumHeight(215)
        layout.addWidget(table)
        return panel

    def _build_gate_table(self) -> QFrame:
        state = self._state
        if state.gates is None:
            raise RuntimeError("available Operations state is missing gate state")

        panel = QFrame(self)
        panel.setObjectName("operatorGatePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        layout.addWidget(
            _plain_label("Eight Effect Gates", panel, "operatorSectionTitle")
        )

        table = QTableWidget(panel)
        table.setObjectName("operatorEffectGateTable")
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(("Gate", "State"))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionsClickable(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )

        rows = (
            ("Market-data capture", state.gates.market_data_capture),
            ("Decision publication", state.gates.decision_publication),
            ("Paper-v2 production", state.gates.production),
            ("Paper-v2 recovery", state.gates.recovery),
            ("Supervised execution", state.gates.supervised_execution),
            ("Receipt recovery", state.gates.receipt_recovery),
            ("Unattended execution", state.gates.unattended_execution),
            (
                "Unattended storage provisioning",
                state.gates.unattended_storage_provisioning,
            ),
        )
        table.setRowCount(len(rows))
        for row, (name, opened) in enumerate(rows):
            for column, value in enumerate((name, "OPEN" if opened else "Closed")):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, cell)
        table.setMaximumHeight(265)
        layout.addWidget(table)

        overall = _plain_label(
            (
                "All effect gates closed"
                if state.gates.all_closed
                else "One or more effect gates are open"
            ),
            panel,
            "operatorGateSummary",
        )
        overall.setProperty(
            "status", "verified" if state.gates.all_closed else "blocked"
        )
        layout.addWidget(overall)
        return panel

    def _build_account_summary(self) -> QFrame:
        state = self._state
        if state.account is None:
            raise RuntimeError("available Operations state is missing account state")
        account = state.account

        panel = QFrame(self)
        panel.setObjectName("operatorAccountPanel")
        form = QFormLayout(panel)
        form.setContentsMargins(18, 16, 18, 16)
        form.setVerticalSpacing(10)

        fields = (
            ("Paper account", account.paper_account_id, "operatorPaperAccountId"),
            ("Checkpoint ID", str(account.checkpoint_id), "operatorCheckpointId"),
            ("Sequence", str(account.sequence), "operatorCheckpointSequence"),
            ("As-of", account.as_of.isoformat(), "operatorAccountAsOf"),
            (
                "Cash",
                format_decimal_for_display(account.cash),
                "operatorAccountCash",
            ),
            (
                "Realized P&L",
                format_decimal_for_display(account.realized_profit_loss),
                "operatorAccountRealizedPnl",
            ),
            (
                "Positions",
                str(len(account.positions)),
                "operatorAccountPositionCount",
            ),
            (
                "Lineage edges",
                str(account.lineage_edge_count),
                "operatorAccountLineageEdgeCount",
            ),
            (
                "Receipts",
                str(account.receipt_count),
                "operatorAccountReceiptCount",
            ),
        )
        for field_name, value, object_name in fields:
            form.addRow(
                _plain_label(field_name, panel, "operatorFieldLabel"),
                self._selectable_value(value, panel, object_name),
            )
        return panel

    def _build_strategy_summary(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("operatorStrategyPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        layout.addWidget(
            _plain_label("Strategy Readiness", panel, "operatorSectionTitle")
        )

        state = self._state
        if state.strategy_ready:
            text = (
                "Ready: the complete six-session selected-C3 window is available. "
                "This display is non-authoritative for decision publication."
            )
            status = "ready"
        elif state.warmup is None:
            text = "Unavailable: no selected-C3 history window is attached."
            status = "unavailable"
        elif state.warmup.classification is OperatorWarmupClassification.SESSION_GAP:
            text = "Blocked: the required selected-C3 history contains a session gap."
            status = "blocked"
        elif state.warmup.classification is OperatorWarmupClassification.BLOCKED:
            text = "Blocked: selected-C3 history validation failed closed."
            status = "blocked"
        else:
            text = (
                f"Warming up: {state.warmup.selected_count} of "
                f"{state.warmup.target_count} required sessions are selected."
            )
            status = "unavailable"

        readiness = _plain_label(text, panel, "operatorStrategyReadiness")
        readiness.setProperty("status", status)
        readiness.setWordWrap(True)
        layout.addWidget(readiness)
        preview = state.strategy_preview
        preview_message = _plain_label(
            preview.message, panel, "operatorStrategyPreviewMessage"
        )
        preview_message.setWordWrap(True)
        layout.addWidget(preview_message)
        if preview.proposal_id is not None:
            form = QFormLayout()
            for title, value, name in (
                (
                    "Diagnostic proposal ID",
                    str(preview.proposal_id),
                    "operatorStrategyProposalId",
                ),
                ("Reason", preview.reason, "operatorStrategyReason"),
                ("Side", preview.side, "operatorStrategySide"),
                ("Quantity", str(preview.quantity), "operatorStrategyQuantity"),
            ):
                label = _plain_label(value, panel, name)
                label.setWordWrap(True)
                form.addRow(_plain_label(title, panel, "operatorFieldLabel"), label)
            layout.addLayout(form)
        return panel

    def _selectable_value(
        self,
        value: str,
        parent: QWidget,
        object_name: str,
    ) -> QLabel:
        label = _plain_label(value, parent, object_name)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label
