"""Qt presentation for one bounded verified paper-account state."""

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
from trading_bot.gui.paper_account_models import (
    PaperAccountPageState,
    PaperAccountPageStatus,
    VerifiedPaperAccountView,
)


def _plain_label(text: str, parent: QWidget, object_name: str) -> QLabel:
    label = QLabel(parent)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    return label


class PaperAccountPage(QWidget):
    """Render one immutable read-only paper-account presentation state."""

    def __init__(
        self,
        state: PaperAccountPageState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if type(state) is not PaperAccountPageState:
            raise TypeError("state must be exactly PaperAccountPageState")

        self._state = state
        self.setObjectName("paperAccountPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        layout.addWidget(_plain_label("Paper Account", self, "pageTitle"))

        message = _plain_label(state.message, self, "paperAccountMessage")
        message.setWordWrap(True)
        layout.addWidget(message)

        if state.status is PaperAccountPageStatus.UNAVAILABLE:
            status = _plain_label("Unavailable", self, "paperAccountStatus")
            status.setProperty("status", "unavailable")
            layout.insertWidget(1, status)
        else:
            account = state.account
            if type(account) is not VerifiedPaperAccountView:
                raise RuntimeError(
                    "verified paper-account state is missing its account"
                )
            status = _plain_label("Verified Offline", self, "paperAccountStatus")
            status.setProperty("status", "verified")
            layout.insertWidget(1, status)

            scope = _plain_label(
                (
                    "Offline-verified checkpoint state; not an operationally "
                    "selected current account."
                ),
                self,
                "paperAccountScopeNotice",
            )
            scope.setWordWrap(True)
            layout.addWidget(scope)
            layout.addWidget(self._build_account_details(account))
            layout.addWidget(self._build_positions_table(account))

        layout.addStretch(1)

    @property
    def paper_account_state(self) -> PaperAccountPageState:
        """Return the immutable state rendered by this page."""
        return self._state

    def _build_account_details(self, account: VerifiedPaperAccountView) -> QFrame:
        details = QFrame(self)
        details.setObjectName("paperAccountDetailPanel")
        form = QFormLayout(details)
        form.setContentsMargins(18, 16, 18, 16)
        form.setVerticalSpacing(10)

        fields = (
            (
                "Checkpoint kind",
                account.checkpoint_kind.value,
                "paperAccountCheckpointKind",
            ),
            ("Checkpoint sequence", str(account.sequence), "paperAccountSequence"),
            ("Checkpoint ID", str(account.checkpoint_id), "paperAccountCheckpointId"),
            ("Lineage ID", str(account.lineage_id), "paperAccountLineageId"),
            (
                "Account-state ID",
                str(account.account_state_id),
                "paperAccountAccountStateId",
            ),
            (
                "Compact-state ID",
                str(account.compact_state_id),
                "paperAccountCompactStateId",
            ),
            ("As-of", account.as_of.isoformat(), "paperAccountAsOf"),
            (
                "Cash",
                format_decimal_for_display(account.cash),
                "paperAccountCash",
            ),
            (
                "Cumulative realized P&L",
                format_decimal_for_display(account.realized_profit_loss),
                "paperAccountRealizedProfitLoss",
            ),
            (
                "Checkpoint artifact SHA-256",
                account.artifact_sha256,
                "paperAccountArtifactSha256",
            ),
            (
                "Checkpoint artifact bytes",
                str(account.artifact_byte_length),
                "paperAccountArtifactByteLength",
            ),
        )
        for field_name, value, object_name in fields:
            field_label = _plain_label(
                field_name,
                details,
                "paperAccountFieldLabel",
            )
            field_value = _plain_label(value, details, object_name)
            field_value.setWordWrap(True)
            field_value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form.addRow(field_label, field_value)

        return details

    def _build_positions_table(self, account: VerifiedPaperAccountView) -> QTableWidget:
        table = QTableWidget(self)
        table.setObjectName("paperAccountPositionsTable")
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ("Symbol", "Quantity", "Total Cost Basis", "Average Cost")
        )
        table.verticalHeader().setVisible(False)
        horizontal_header = table.horizontalHeader()
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(account.positions))
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionsClickable(False)
        table.horizontalHeader().setStretchLastSection(True)

        for row, position in enumerate(account.positions):
            values = (
                position.symbol,
                format_decimal_for_display(position.quantity),
                format_decimal_for_display(position.total_cost_basis),
                format_decimal_for_display(position.average_cost),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, item)

        table.setSortingEnabled(False)
        return table
