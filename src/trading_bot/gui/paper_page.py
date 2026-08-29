"""Qt presentation for the bounded read-only Paper page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QVBoxLayout, QWidget

from trading_bot.gui.paper_models import (
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
)


def _plain_label(text: str, parent: QWidget, object_name: str) -> QLabel:
    label = QLabel(parent)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    return label


class PaperPage(QWidget):
    """Render one immutable paper-operation presentation state."""

    def __init__(self, state: PaperPageState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if type(state) is not PaperPageState:
            raise TypeError("state must be exactly PaperPageState")

        self._state = state
        self.setObjectName("paperPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        layout.addWidget(_plain_label("Paper Operation", self, "pageTitle"))
        layout.addWidget(_plain_label(state.message, self, "paperMessage"))

        message = self.findChild(QLabel, "paperMessage")
        if message is None:
            raise RuntimeError("paper message label is missing")
        message.setObjectName("summaryLabel")
        message.setWordWrap(True)

        if state.status is PaperPageStatus.UNAVAILABLE:
            status = _plain_label("Unavailable", self, "paperStatus")
            status.setProperty("status", "unavailable")
            layout.insertWidget(1, status)
        else:
            inspection = state.inspection
            if type(inspection) is not PaperOperationInspectionView:
                raise RuntimeError("inspected paper state is missing its inspection")
            layout.addWidget(self._build_inspection_details(inspection))

        layout.addStretch(1)

    @property
    def paper_state(self) -> PaperPageState:
        """Return the immutable state rendered by this page."""
        return self._state

    def _build_inspection_details(
        self, inspection: PaperOperationInspectionView
    ) -> QFrame:
        details = QFrame(self)
        details.setObjectName("paperDetailPanel")
        form = QFormLayout(details)
        form.setContentsMargins(18, 16, 18, 16)
        form.setVerticalSpacing(10)

        fields = (
            ("Classification", inspection.classification.value, "paperClassification"),
            ("Diagnostic", inspection.diagnostic.value, "paperDiagnostic"),
            ("Operation ID", str(inspection.operation_id), "paperOperationId"),
            (
                "Terminal checkpoint ID",
                str(inspection.terminal_checkpoint_id),
                "paperTerminalCheckpointId",
            ),
            ("Application ID", str(inspection.application_id), "paperApplicationId"),
            (
                "Receipt path",
                (
                    inspection.receipt_path
                    if inspection.receipt_path is not None
                    else "Not retained"
                ),
                "paperReceiptPath",
            ),
        )
        for field_name, value, object_name in fields:
            field_label = _plain_label(field_name, details, "paperFieldLabel")
            field_value = _plain_label(value, details, object_name)
            field_value.setWordWrap(True)
            field_value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form.addRow(field_label, field_value)

        return details
