"""Qt presentation for GUI-A10/A11 read-only Evidence Timeline."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.evidence_explorer import (
    MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS,
    EvidenceTimelineFilter,
    filter_evidence_timeline_entries,
)
from trading_bot.gui.evidence_navigation import EvidenceNavigationTarget
from trading_bot.gui.evidence_source_navigation import (
    EvidenceSourcePageTarget,
    build_evidence_source_page_target,
)
from trading_bot.gui.evidence_timeline_models import (
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
)


class EvidenceTimelinePage(QWidget):
    """Read-only timeline and local explorer over already-acquired GUI state."""

    source_navigation_requested = Signal(object)

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
        self._sources = (None, *tuple(EvidenceTimelineSource))
        self._navigation_target: EvidenceNavigationTarget | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("evidenceTimelineScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self._scroll)

        content = QWidget(self._scroll)
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

        explorer_title = QLabel("Evidence explorer", content)
        explorer_title.setObjectName("evidenceTimelineExplorerTitle")
        explorer_title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(explorer_title)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self._search = QLineEdit(content)
        self._search.setObjectName("evidenceTimelineSearch")
        self._search.setPlaceholderText("Search displayed evidence")
        self._search.setMaxLength(MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter_changed)
        controls.addWidget(self._search, 1)

        self._source = QComboBox(content)
        self._source.setObjectName("evidenceTimelineSourceFilter")
        self._source.addItem("All sources")
        for source in EvidenceTimelineSource:
            self._source.addItem(source.value)
        self._source.currentIndexChanged.connect(self._on_filter_changed)
        controls.addWidget(self._source)

        layout.addLayout(controls)

        self._count = QLabel(content)
        self._count.setObjectName("evidenceTimelineFilterCount")
        self._count.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._count)

        self._entries_host = QWidget(content)
        self._entries_host.setObjectName("evidenceTimelineEntriesHost")
        self._entries_layout = QVBoxLayout(self._entries_host)
        self._entries_layout.setContentsMargins(0, 0, 0, 0)
        self._entries_layout.setSpacing(12)
        layout.addWidget(self._entries_host)

        layout.addStretch(1)
        self._scroll.setWidget(content)
        self._refresh_entries()
        self._scroll.verticalScrollBar().setValue(0)

    def show_navigation_target(self, target: EvidenceNavigationTarget) -> None:
        """Show one exact System-audit identity without rereading any service."""
        if type(target) is not EvidenceNavigationTarget:
            raise TypeError("target must be an exact EvidenceNavigationTarget")

        source_index = self._sources.index(target.source)
        source_blocker = QSignalBlocker(self._source)
        search_blocker = QSignalBlocker(self._search)
        self._source.setCurrentIndex(source_index)
        self._search.setText(target.identifier)
        del search_blocker
        del source_blocker

        self._navigation_target = target
        self._refresh_entries()
        self._scroll.verticalScrollBar().setValue(0)

    def _on_filter_changed(self) -> None:
        self._navigation_target = None
        self._refresh_entries()

    def _refresh_entries(self) -> None:
        source = self._sources[self._source.currentIndex()]
        filter_state = EvidenceTimelineFilter(self._search.text(), source)
        entries = filter_evidence_timeline_entries(self._state, filter_state)
        if self._navigation_target is not None:
            target = self._navigation_target
            entries = tuple(
                entry
                for entry in entries
                if entry.source is target.source
                and entry.identifier == target.identifier
            )

        self._clear_entry_widgets()
        total = len(self._state.entries)
        noun = "entry" if total == 1 else "entries"
        self._count.setText(f"Showing {len(entries)} of {total} {noun}.")

        if not self._state.entries:
            self._entries_layout.addWidget(
                self._empty_label(
                    "Configure supported explicit read-only artifacts to populate "
                    "evidence."
                )
            )
            return

        if not entries:
            self._entries_layout.addWidget(
                self._empty_label(
                    "No represented evidence matches the current local filters."
                )
            )
            return

        for index, entry in enumerate(entries):
            self._entries_layout.addWidget(self._entry_card(entry, index))

    def _clear_entry_widgets(self) -> None:
        while self._entries_layout.count():
            item = self._entries_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _empty_label(self, text: str) -> QLabel:
        empty = QLabel(text, self._entries_host)
        empty.setObjectName("evidenceTimelineEmpty")
        empty.setTextFormat(Qt.TextFormat.PlainText)
        empty.setWordWrap(True)
        return empty

    def _entry_card(
        self,
        entry: EvidenceTimelineEntry,
        index: int,
    ) -> QFrame:
        card = QFrame(self._entries_host)
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
        row += 1

        target = build_evidence_source_page_target(entry)
        navigate = QPushButton("View source page", card)
        navigate.setObjectName("evidenceTimelineViewSourceButton")
        navigate.clicked.connect(
            lambda _checked=False, target=target: self._emit_source_target(target)
        )
        layout.addWidget(navigate, row, 1, alignment=Qt.AlignmentFlag.AlignRight)

        layout.setColumnStretch(1, 1)
        return card

    def _emit_source_target(self, target: EvidenceSourcePageTarget) -> None:
        self.source_navigation_requested.emit(target)


def _readonly_value(value: str, parent: QWidget) -> QLineEdit:
    field = QLineEdit(value, parent)
    field.setReadOnly(True)
    field.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    field.setCursorPosition(0)
    field.setTextMargins(4, 0, 4, 0)
    return field
