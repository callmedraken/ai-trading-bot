"""Qt presentation for GUI-A9 System Health & Audit."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.system_health_models import (
    SystemAuditEntryView,
    SystemComponentHealthView,
    SystemComponentStatus,
    SystemHealthPageState,
    SystemHealthStatus,
)

_STATUS_LABELS = {
    SystemComponentStatus.AVAILABLE: "Available",
    SystemComponentStatus.UNAVAILABLE: "Unavailable",
    SystemComponentStatus.BLOCKED: "Blocked",
}

_STATUS_PROPERTIES = {
    SystemComponentStatus.AVAILABLE: "available",
    SystemComponentStatus.UNAVAILABLE: "unavailable",
    SystemComponentStatus.BLOCKED: "blocked",
}


class SystemHealthPage(QWidget):
    """Read-only view derived only from already-acquired GUI presentation state."""

    def __init__(self, state: SystemHealthPageState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if type(state) is not SystemHealthPageState:
            raise TypeError("state must be an exact SystemHealthPageState")
        self._state = state
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setObjectName("systemHealthScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(14)

        title = QLabel("System Health & Audit", content)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        scope = QLabel(
            (
                "Read-only summary of presentation state already acquired by this "
                "GUI. This page does not establish production readiness or grant "
                "authority."
            ),
            content,
        )
        scope.setObjectName("systemHealthScope")
        scope.setTextFormat(Qt.TextFormat.PlainText)
        scope.setWordWrap(True)
        layout.addWidget(scope)

        status = QLabel(
            (
                "Read-only ready"
                if self._state.status is SystemHealthStatus.READ_ONLY_READY
                else "Attention"
            ),
            content,
        )
        status.setObjectName("systemHealthOverallStatus")
        status.setProperty(
            "status",
            "ready"
            if self._state.status is SystemHealthStatus.READ_ONLY_READY
            else "attention",
        )
        layout.addWidget(status)

        message = QLabel(self._state.message, content)
        message.setObjectName("systemHealthMessage")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setWordWrap(True)
        layout.addWidget(message)

        context = QLabel(
            (
                f"Environment: {self._state.environment}  •  "
                f"Displayed mode: {self._state.displayed_mode}"
            ),
            content,
        )
        context.setObjectName("systemHealthContext")
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        layout.addWidget(context)

        heading = QLabel("Presented components", content)
        heading.setObjectName("systemHealthSectionTitle")
        layout.addWidget(heading)

        component_grid = QGridLayout()
        component_grid.setHorizontalSpacing(12)
        component_grid.setVerticalSpacing(12)
        for index, component in enumerate(self._state.components):
            component_grid.addWidget(
                self._component_card(component, content),
                index // 2,
                index % 2,
            )
        layout.addLayout(component_grid)

        audit_heading = QLabel("Bounded audit evidence", content)
        audit_heading.setObjectName("systemHealthSectionTitle")
        layout.addWidget(audit_heading)

        if not self._state.audit_entries:
            empty = QLabel(
                "No loaded/verified/inspected artifact identity is available.",
                content,
            )
            empty.setObjectName("systemHealthEmptyAudit")
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            for index, entry in enumerate(self._state.audit_entries):
                layout.addWidget(self._audit_card(entry, index, content))

        layout.addStretch(1)
        scroll.setWidget(content)

    def _component_card(
        self,
        component: SystemComponentHealthView,
        parent: QWidget,
    ) -> QFrame:
        card = QFrame(parent)
        card.setObjectName("systemHealthComponentCard")
        card.setProperty("status", _STATUS_PROPERTIES[component.status])

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(component.title, card)
        title.setObjectName("systemHealthComponentTitle")
        layout.addWidget(title)

        status = QLabel(_STATUS_LABELS[component.status], card)
        status.setObjectName("systemHealthComponentStatus")
        status.setProperty("status", _STATUS_PROPERTIES[component.status])
        layout.addWidget(status)

        detail = QLabel(component.detail, card)
        detail.setObjectName("systemHealthComponentDetail")
        detail.setTextFormat(Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        layout.addWidget(detail)
        return card

    def _audit_card(
        self,
        entry: SystemAuditEntryView,
        index: int,
        parent: QWidget,
    ) -> QFrame:
        card = QFrame(parent)
        card.setObjectName("systemHealthAuditCard")

        layout = QGridLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(7)

        source = QLabel(f"{entry.source} — {entry.evidence_kind}", card)
        source.setObjectName("systemHealthAuditTitle")
        layout.addWidget(source, 0, 0, 1, 2)

        id_label = QLabel("Identifier", card)
        id_label.setObjectName("systemHealthFieldLabel")
        layout.addWidget(id_label, 1, 0)

        identifier = _readonly_value(entry.identifier, card)
        identifier.setObjectName(f"systemHealthAuditIdentifier{index}")
        layout.addWidget(identifier, 1, 1)

        if entry.sha256 is not None:
            hash_label = QLabel("SHA-256", card)
            hash_label.setObjectName("systemHealthFieldLabel")
            layout.addWidget(hash_label, 2, 0)

            digest = _readonly_value(entry.sha256, card)
            digest.setObjectName(f"systemHealthAuditSha256{index}")
            layout.addWidget(digest, 2, 1)

        layout.setColumnStretch(1, 1)
        return card


def _readonly_value(value: str, parent: QWidget) -> QLineEdit:
    field = QLineEdit(value, parent)
    field.setReadOnly(True)
    field.setCursorPosition(0)
    field.setTextMargins(4, 0, 4, 0)
    return field
