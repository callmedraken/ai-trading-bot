"""Qt presentation for GUI-A10 read-only Evidence Timeline."""

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

from trading_bot.gui.evidence_timeline_models import (
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
)


class EvidenceTimelinePage(QWidget):
    """Read-only timeline derived only from already-acquired GUI state."""

    def __init__(
        self,
        state: EvidenceTimelinePageState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if type(state) is not EvidenceTimelinePageState:
            raise TypeError("state must be an exact EvidenceTimelinePageState")
        self.setObjectName("evidenceTimelinePage")
        self._state = state
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setObjectName("evidenceTimelineScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(14)

        title = QLabel("Evidence Timeline", content)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        scope = QLabel(
            (
                "Read-only timeline of bounded evidence already represented by "
                "this GUI. It is not a durable audit log, production history, or "
                "authority source."
            ),
            content,
        )
        scope.setObjectName("evidenceTimelineScope")
        scope.setTextFormat(Qt.TextFormat.PlainText)
        scope.setWordWrap(True)
        layout.addWidget(scope)

        message = QLabel(self._state.message, content)
        message.setObjectName("evidenceTimelineMessage")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setWordWrap(True)
        layout.addWidget(message)

        if not self._state.entries:
            empty = QLabel(
                "Configure supported explicit read-only artifacts to populate evidence.",
                content,
            )
            empty.setObjectName("evidenceTimelineEmpty")
            empty.setTextFormat(Qt.TextFormat.PlainText)
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            for index, entry in enumerate(self._state.entries):
                layout.addWidget(self._entry_card(entry, index, content))

        layout.addStretch(1)
        scroll.setWidget(content)
        scroll.verticalScrollBar().setValue(0)

    def _entry_card(
        self,
        entry: EvidenceTimelineEntry,
        index: int,
        parent: QWidget,
    ) -> QFrame:
        card = QFrame(parent)
        card.setObjectName("evidenceTimelineCard")

        layout = QGridLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(7)

        heading = QLabel(f"{entry.source.value} — {entry.title}", card)
        heading.setObjectName("evidenceTimelineEntryTitle")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(heading, 0, 0, 1, 2)

        timestamp = QLabel(
            (
                entry.occurred_at.isoformat()
                if entry.occurred_at is not None
                else "Untimed presentation evidence"
            ),
            card,
        )
        timestamp.setObjectName("evidenceTimelineTimestamp")
        timestamp.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(timestamp, 1, 0, 1, 2)

        identifier_label = QLabel("Identifier", card)
        identifier_label.setObjectName("evidenceTimelineFieldLabel")
        identifier_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(identifier_label, 2, 0)

        identifier = _readonly_value(entry.identifier, card)
        identifier.setObjectName(f"evidenceTimelineIdentifier{index}")
        layout.addWidget(identifier, 2, 1)

        row = 3
        if entry.sha256 is not None:
            digest_label = QLabel("SHA-256", card)
            digest_label.setObjectName("evidenceTimelineFieldLabel")
            digest_label.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(digest_label, row, 0)

            digest = _readonly_value(entry.sha256, card)
            digest.setObjectName(f"evidenceTimelineSha256{index}")
            layout.addWidget(digest, row, 1)
            row += 1

        detail_label = QLabel("Detail", card)
        detail_label.setObjectName("evidenceTimelineFieldLabel")
        detail_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(detail_label, row, 0)

        detail = QLabel(entry.detail, card)
        detail.setObjectName("evidenceTimelineDetail")
        detail.setTextFormat(Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        layout.addWidget(detail, row, 1)

        layout.setColumnStretch(1, 1)
        return card


def _readonly_value(value: str, parent: QWidget) -> QLineEdit:
    field = QLineEdit(value, parent)
    field.setReadOnly(True)
    field.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    field.setCursorPosition(0)
    field.setTextMargins(4, 0, 4, 0)
    return field
