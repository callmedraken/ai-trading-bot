"""Cached active-strategy binding presentation."""

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

from trading_bot.live_prototype.contracts import PrototypeSnapshot


class StrategyPage(QWidget):
    """Display the active cached binding without promoting research results."""

    def __init__(
        self, snapshot: PrototypeSnapshot, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("prototypeStrategyPage")
        self._snapshot = _require_snapshot(snapshot)
        self._values: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("prototypeStrategyScroll")
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
        title = _label("Strategy", content)
        title.setObjectName("strategyTitle")
        layout.addWidget(title)
        scope = _label(
            "Your active strategy and its source. Research results remain separate "
            "until a strategy is explicitly selected under the reviewed procedure.",
            content,
        )
        scope.setObjectName("strategyScope")
        layout.addWidget(scope)

        self._add_card(
            layout,
            content,
            "Active strategy binding",
            "strategyActiveBindingCard",
            (
                ("active_strategy", "Active strategy"),
                ("binding_digest", "Binding digest"),
                ("source_head", "Executable source HEAD"),
            ),
        )
        self._add_card(
            layout,
            content,
            "Current session",
            "strategySessionCard",
            (
                ("mode", "Mode"),
                ("lifecycle", "Lifecycle"),
                ("workers_running", "Workers"),
            ),
        )
        self._add_card(
            layout,
            content,
            "Research comparison (descriptive only)",
            "strategyResearchCard",
            (
                ("research_selected", "Research selection"),
                ("research_policy", "Qualification policy"),
                ("research_bundle_digest", "Research report digest"),
                ("research_dataset_digest", "Research dataset identity"),
                ("research_live_eligible", "Research live eligibility"),
            ),
        )
        layout.addStretch(1)
        scroll.setWidget(content)
        self.update_snapshot(snapshot)

    def update_snapshot(self, snapshot: PrototypeSnapshot) -> None:
        """Refresh active and research labels from a cached immutable snapshot."""
        self._snapshot = _require_snapshot(snapshot)
        values = _snapshot_values(snapshot)
        for name, label in self._values.items():
            label.setText(values[name])

    def _add_card(
        self,
        layout: QVBoxLayout,
        parent: QWidget,
        title: str,
        object_name: str,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        card = QFrame(parent)
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        grid.setColumnMinimumWidth(0, 180)
        grid.setColumnStretch(1, 1)
        heading = _label(title, card)
        heading.setObjectName(f"{object_name}Title")
        grid.addWidget(heading, 0, 0, 1, 2)
        for row, (name, caption) in enumerate(fields, start=1):
            caption_label = _label(caption, card)
            caption_label.setObjectName(f"strategyCaption_{name}")
            value_label = _label("", card)
            value_label.setObjectName(f"strategy_{name}")
            self._values[name] = value_label
            grid.addWidget(caption_label, row, 0)
            grid.addWidget(value_label, row, 1)
        layout.addWidget(card)


def _snapshot_values(snapshot: PrototypeSnapshot) -> dict[str, str]:
    research = snapshot.research
    return {
        "active_strategy": _active_strategy(snapshot.strategy),
        "binding_digest": _display(snapshot.binding_digest),
        "source_head": _display(snapshot.source_head),
        "mode": _display(snapshot.mode),
        "lifecycle": _display(snapshot.lifecycle),
        "workers_running": "Running" if snapshot.workers_running else "Stopped",
        "research_selected": _display(research.selected),
        "research_policy": _display(research.policy),
        "research_bundle_digest": _display(research.bundle_digest),
        "research_dataset_digest": _display(research.dataset_digest),
        "research_live_eligible": _display(research.live_eligible),
    }


def _active_strategy(value: object) -> str:
    if value is None or value == "UNSELECTED":
        return "Unavailable (UNSELECTED)"
    return _display(value)


def _require_snapshot(snapshot: PrototypeSnapshot) -> PrototypeSnapshot:
    if type(snapshot) is not PrototypeSnapshot:
        raise TypeError("snapshot must be exactly PrototypeSnapshot")
    return snapshot


def _display(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, Enum):
        value = value.value
    elif isinstance(value, bool):
        value = "Yes" if value else "No"
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
