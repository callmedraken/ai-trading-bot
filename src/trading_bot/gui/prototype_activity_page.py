"""Read-only cached activity and health presentation for the live prototype."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_bot.live_prototype.contracts import Lifecycle, PrototypeSnapshot

_MAX_ACTIVITY_ROWS = 200
_MAX_REASON_ROWS = 16
_MAX_TIMESTAMP_LENGTH = 120
_UNAVAILABLE = "Unavailable"


class ActivityHealthPage(QWidget):
    """Display a bounded view of an already-cached immutable snapshot."""

    def __init__(
        self,
        snapshot: PrototypeSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._build()
        self.update_snapshot(snapshot)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = _plain_label("Activity & Health", self, "prototypeActivityTitle")
        layout.addWidget(title)

        health = QGridLayout()
        health.setHorizontalSpacing(14)
        health.setVerticalSpacing(8)
        self._lifecycle_value = _add_readout(
            health, 0, "Lifecycle", "prototypeLifecycleValue", self
        )
        self._signal_freshness_value = _add_readout(
            health, 1, "Signal freshness", "prototypeSignalFreshnessValue", self
        )
        self._quote_freshness_value = _add_readout(
            health, 2, "Quote freshness", "prototypeQuoteFreshnessValue", self
        )
        self._reasons_value = _add_readout(
            health, 3, "Uncertainty / reasons", "prototypeReasonsValue", self
        )
        self._working_orders_value = _add_readout(
            health, 4, "Working orders", "prototypeWorkingOrdersValue", self
        )
        self._fills_value = _add_readout(
            health, 5, "Fills", "prototypeFillsValue", self
        )
        self._entries_value = _add_readout(
            health, 6, "Entries used", "prototypeEntriesValue", self
        )
        self._exits_value = _add_readout(
            health, 7, "Exits used", "prototypeExitsValue", self
        )
        health.setColumnStretch(1, 1)
        layout.addLayout(health)

        heading = _plain_label("Recent activity", self, "prototypeActivityHeading")
        layout.addWidget(heading)

        self._empty_activity = _plain_label(
            "No activity is available.", self, "prototypeActivityEmpty"
        )
        self._empty_activity.setWordWrap(True)
        layout.addWidget(self._empty_activity)

        self._activity_table = QTableWidget(0, 3, self)
        self._activity_table.setObjectName("prototypeActivityTable")
        self._activity_table.setHorizontalHeaderLabels(
            ["Sequence", "Lifecycle", "Reason"]
        )
        self._activity_table.verticalHeader().setVisible(False)
        self._activity_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._activity_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._activity_table.setSortingEnabled(False)
        self._activity_table.setWordWrap(False)
        self._activity_table.setMinimumHeight(180)
        self._activity_table.setMaximumHeight(360)
        header = self._activity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._activity_table)

    def update_snapshot(self, snapshot: PrototypeSnapshot) -> None:
        """Refresh from a bounded cached value; this method performs no I/O."""
        if type(snapshot) is not PrototypeSnapshot:
            raise TypeError("snapshot must be an exact PrototypeSnapshot")

        self._lifecycle_value.setText(snapshot.lifecycle.value)
        self._signal_freshness_value.setText(
            _freshness_text(snapshot.signal_as_of, snapshot.signal_fresh)
        )
        self._quote_freshness_value.setText(
            _freshness_text(snapshot.quote_as_of, snapshot.quote_fresh)
        )
        self._reasons_value.setText(_reasons_text(snapshot))
        self._working_orders_value.setText(_optional_count(snapshot.working_orders))
        self._fills_value.setText(_optional_count(snapshot.fills))
        self._entries_value.setText(str(snapshot.entries_used))
        self._exits_value.setText(str(snapshot.exits_used))

        activity = snapshot.activity
        visible_items = activity[-_MAX_ACTIVITY_ROWS:]
        table = self._activity_table
        table.setUpdatesEnabled(False)
        try:
            table.clearContents()
            table.setRowCount(len(visible_items))
            for row, item in enumerate(visible_items):
                values = (str(item.sequence), item.lifecycle.value, item.reason.value)
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(value))
            self._empty_activity.setVisible(not visible_items)
        finally:
            table.setUpdatesEnabled(True)
            table.viewport().update()


def _plain_label(text: str, parent: QWidget, object_name: str) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _add_readout(
    layout: QGridLayout,
    row: int,
    caption: str,
    object_name: str,
    parent: QWidget,
) -> QLabel:
    name = _plain_label(caption, parent, f"{object_name}Label")
    value = _plain_label(_UNAVAILABLE, parent, object_name)
    value.setWordWrap(True)
    layout.addWidget(name, row, 0)
    layout.addWidget(value, row, 1)
    return value


def _freshness_text(as_of: str | None, fresh: bool) -> str:
    if as_of is None:
        return _UNAVAILABLE
    timestamp = as_of.replace("\r", " ").replace("\n", " ")
    if len(timestamp) > _MAX_TIMESTAMP_LENGTH:
        timestamp = f"{timestamp[: _MAX_TIMESTAMP_LENGTH - 1]}…"
    status = "Fresh" if fresh else "Stale"
    return f"{status} · as of {timestamp}"


def _optional_count(value: int | None) -> str:
    return _UNAVAILABLE if value is None else str(value)


def _reasons_text(snapshot: PrototypeSnapshot) -> str:
    reasons = snapshot.reasons
    shown = tuple(reason.value for reason in reasons[:_MAX_REASON_ROWS])
    details = ", ".join(shown) if shown else "None reported"
    if snapshot.lifecycle is Lifecycle.UNKNOWN:
        details = f"Lifecycle UNKNOWN · {details}"
    if len(reasons) > _MAX_REASON_ROWS:
        details = f"{details} · {len(reasons) - _MAX_REASON_ROWS} more omitted"
    return details
