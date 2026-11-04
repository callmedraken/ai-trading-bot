"""Cached, read-only dashboard for the current live prototype."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
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
        "Session status",
        (0, 0),
        ("mode", "lifecycle", "connected", "ready_to_trade", "workers_running"),
    ),
    ("Strategy and source", (0, 1), ("strategy", "binding_digest", "source_head")),
    (
        "Signal and quote",
        (1, 0),
        ("signal_as_of", "signal_fresh", "quote_as_of", "quote_fresh"),
    ),
    (
        "Exposure and activity",
        (1, 1),
        (
            "exposure",
            "owned_quantity",
            "working_orders",
            "fills",
            "entries_used",
            "exits_used",
        ),
    ),
    ("Current reasons", (2, 0), ("reasons",)),
)


class DashboardPage(QWidget):
    """Render an immutable cached snapshot without services or file access."""

    def __init__(
        self, snapshot: PrototypeSnapshot, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("prototypeDashboardPage")
        self._snapshot = _require_snapshot(snapshot)
        self._values: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("prototypeDashboardScroll")
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
        title = _label("Dashboard", content)
        title.setObjectName("dashboardTitle")
        layout.addWidget(title)
        scope = _label(
            "Your session, strategy, market data and exposure at a glance.",
            content,
        )
        scope.setObjectName("dashboardScope")
        layout.addWidget(scope)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        for heading, (row, column), names in _GROUPS:
            card = QFrame(content)
            card.setObjectName(f"dashboardCard_{row}_{column}")
            card.setFrameShape(QFrame.Shape.StyledPanel)
            grid = QGridLayout(card)
            grid.setContentsMargins(12, 10, 12, 10)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(7)
            grid.setColumnMinimumWidth(0, 132)
            grid.setColumnStretch(1, 1)
            heading_label = _label(heading, card)
            grid.addWidget(heading_label, 0, 0, 1, 2)
            captions = dict(_FIELDS)
            for index, name in enumerate(names, start=1):
                caption = _label(captions[name], card)
                caption.setObjectName(f"dashboardCaption_{name}")
                value = _label("", card)
                value.setObjectName(f"dashboard_{name}")
                self._values[name] = value
                grid.addWidget(caption, index, 0)
                grid.addWidget(value, index, 1)
            cards.addWidget(card, row, column, 1, 2 if name == "reasons" else 1)
        layout.addLayout(cards)
        layout.addStretch(1)
        scroll.setWidget(content)
        self.update_snapshot(snapshot)

    def update_snapshot(self, snapshot: PrototypeSnapshot) -> None:
        """Replace the rendered cache with a new immutable snapshot."""
        self._snapshot = _require_snapshot(snapshot)
        for name, value in _snapshot_values(snapshot).items():
            self._values[name].setText(value)


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
