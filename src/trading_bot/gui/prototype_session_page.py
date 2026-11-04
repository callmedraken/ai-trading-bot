"""Cached live-session status and synthetic worker request controls."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from trading_bot.live_prototype.contracts import PrototypeSnapshot, Reason

_FIELDS = (
    ("mode", "Mode"),
    ("lifecycle", "Lifecycle"),
    ("connected", "Connection"),
    ("ready_to_trade", "Trading readiness"),
    ("workers_running", "Workers"),
    ("strategy", "Strategy"),
    ("binding_digest", "Binding digest"),
    ("source_head", "Executable source HEAD"),
    ("signal_as_of", "Signal as of"),
    ("signal_fresh", "Signal freshness"),
    ("quote_as_of", "Quote as of"),
    ("quote_fresh", "Quote freshness"),
    ("exposure", "Exposure"),
    ("owned_quantity", "Owned quantity"),
    ("working_orders", "Working orders"),
    ("fills", "Fills"),
    ("entries_used", "Entries used"),
    ("exits_used", "Exits used"),
    ("reasons", "Reasons"),
)
_GROUPS = (
    (
        "Session state",
        ("mode", "lifecycle", "connected", "ready_to_trade", "workers_running"),
    ),
    ("Strategy and source binding", ("strategy", "binding_digest", "source_head")),
    (
        "Signal and quote freshness",
        ("signal_as_of", "signal_fresh", "quote_as_of", "quote_fresh"),
    ),
    (
        "Exposure and session budgets",
        (
            "exposure",
            "owned_quantity",
            "working_orders",
            "fills",
            "entries_used",
            "exits_used",
        ),
    ),
    ("Current reasons", ("reasons",)),
)


class LiveSessionPage(QWidget):
    """Present cached session facts and emit synthetic-only request signals."""

    start_requested = Signal()
    stop_requested = Signal()

    def __init__(
        self, snapshot: PrototypeSnapshot, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("prototypeLiveSessionPage")
        self._snapshot = _require_snapshot(snapshot)
        self._values: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("prototypeSessionScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget(scroll)
        content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = _label("Live Session", content)
        title.setObjectName("sessionTitle")
        layout.addWidget(title)
        scope = _label(
            "Start or stop the isolated synthetic session. Start never arms execution.",
            content,
        )
        scope.setObjectName("sessionScope")
        layout.addWidget(scope)

        request_heading = _label("Synthetic session", content)
        request_heading.setObjectName("sessionRequestHeading")
        layout.addWidget(request_heading)
        note = _label(
            "Start and Stop control the isolated synthetic worker.",
            content,
        )
        note.setObjectName("sessionRequestNote")
        layout.addWidget(note)
        actions = QHBoxLayout()
        self.start_button = QPushButton("Start synthetic workers", content)
        self.start_button.setObjectName("sessionStartSyntheticWorkers")
        self.start_button.clicked.connect(self._emit_start_requested)
        self.stop_button = QPushButton("Stop synthetic workers", content)
        self.stop_button.setObjectName("sessionStopSyntheticWorkers")
        self.stop_button.clicked.connect(self._emit_stop_requested)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        for index, (heading, names) in enumerate(_GROUPS):
            card = QFrame(content)
            card.setObjectName(f"sessionCard_{index}")
            card.setFrameShape(QFrame.Shape.StyledPanel)
            grid = QGridLayout(card)
            grid.setContentsMargins(12, 10, 12, 10)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(7)
            grid.setColumnMinimumWidth(0, 160)
            grid.setColumnStretch(1, 1)
            heading_label = _label(heading, card)
            grid.addWidget(heading_label, 0, 0, 1, 2)
            captions = dict(_FIELDS)
            for row, name in enumerate(names, start=1):
                caption = _label(captions[name], card)
                caption.setObjectName(f"sessionCaption_{name}")
                value = _label("", card)
                value.setObjectName(f"session_{name}")
                self._values[name] = value
                grid.addWidget(caption, row, 0)
                grid.addWidget(value, row, 1)
            layout.addWidget(card)
        layout.addStretch(1)
        scroll.setWidget(content)
        self.update_snapshot(snapshot)

    def update_snapshot(self, snapshot: PrototypeSnapshot) -> None:
        """Replace the rendered cache with a new immutable snapshot."""
        self._snapshot = _require_snapshot(snapshot)
        for name, value in _snapshot_values(snapshot).items():
            self._values[name].setText(value)

    def _emit_start_requested(self, _checked: bool = False) -> None:
        self.start_requested.emit()

    def _emit_stop_requested(self, _checked: bool = False) -> None:
        self.stop_requested.emit()


def _require_snapshot(snapshot: PrototypeSnapshot) -> PrototypeSnapshot:
    if type(snapshot) is not PrototypeSnapshot:
        raise TypeError("snapshot must be exactly PrototypeSnapshot")
    return snapshot


def _snapshot_values(snapshot: PrototypeSnapshot) -> dict[str, str]:
    return {
        "mode": _display(snapshot.mode),
        "lifecycle": _display(snapshot.lifecycle),
        "connected": "Connected" if snapshot.connected else "Disconnected",
        "ready_to_trade": "Ready" if snapshot.ready_to_trade else "Not ready",
        "workers_running": "Running" if snapshot.workers_running else "Stopped",
        "strategy": _display(snapshot.strategy),
        "binding_digest": _display(snapshot.binding_digest),
        "source_head": _display(snapshot.source_head),
        "signal_as_of": _display(snapshot.signal_as_of),
        "signal_fresh": "Fresh" if snapshot.signal_fresh else "Not fresh",
        "quote_as_of": _display(snapshot.quote_as_of),
        "quote_fresh": "Fresh" if snapshot.quote_fresh else "Not fresh",
        "exposure": _display(snapshot.exposure),
        "owned_quantity": _display(snapshot.owned_quantity),
        "working_orders": _display(snapshot.working_orders),
        "fills": _display(snapshot.fills),
        "entries_used": _display(snapshot.entries_used),
        "exits_used": _display(snapshot.exits_used),
        "reasons": _reasons(snapshot.reasons),
    }


def _reasons(reasons: tuple[Reason, ...] | None) -> str:
    if reasons is None:
        return "Unavailable"
    if not reasons:
        return "None reported"
    return ", ".join(reason.value for reason in reasons)


def _display(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label
