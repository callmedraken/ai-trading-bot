"""Cached sanitized broker baseline display; no connect or order controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from trading_bot.desktop_paper.robinhood_reconciliation import (
        RobinhoodReconciliationSnapshot,
    )


class RobinhoodReadPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("robinhoodReadPanel")
        layout = QVBoxLayout(self)
        self.status_label = QLabel(self)
        self.observations_label = QLabel(self)
        for label in (self.status_label, self.observations_label):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.set_observation(None)

    def set_observation(
        self, snapshot: RobinhoodReconciliationSnapshot | None, *, failed: bool = False
    ) -> None:
        """Render memory only; a prior read never arms trading or claims LIVE."""
        if failed:
            state = "RECONCILIATION_FAILED"
            snapshot = None
        else:
            state = "NOT_CONNECTED" if snapshot is None else snapshot.status
        positions = "unavailable" if snapshot is None else str(len(snapshot.positions))
        self.status_label.setText("Robinhood: " + state)
        self.observations_label.setText(
            f"account resolved = {'no' if snapshot is None else 'yes'}; "
            f"positions observed = {positions}; "
            f"SPY quote observed = {'no' if snapshot is None else 'yes'}; "
            f"order-history baseline observed = {'no' if snapshot is None else 'yes'}; "
            "broker mutation enabled = false"
        )
