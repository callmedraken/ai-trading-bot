"""Read-only presentation of the separately controlled P6 live state."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QVBoxLayout, QWidget


@dataclass(frozen=True, slots=True)
class LiveGuiState:
    """Sanitized cached live state; it contains no account or credential data."""

    status: str
    message: str
    symbol: str = "SPY"
    strategy: str = "FILTERED_TREND_BASE_MA / filtered-trend-base-ma/v1"
    order_ceiling: str = "$10.00"
    plan_sha256: str = ""
    placement_available: bool = False


def unavailable_live_state() -> LiveGuiState:
    """Return the safe default before a separately reviewed live checkpoint."""

    return LiveGuiState(
        status="UNAVAILABLE",
        message=(
            "Tiny-live execution is unavailable in the GUI. "
            "Use the separately reviewed preflight and operator-controlled "
            "execution boundary; this panel never arms or places orders."
        ),
    )


def _label(text: str, parent: QWidget, object_name: str) -> QLabel:
    label = QLabel(parent)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(text)
    return label


class LiveStatePanel(QFrame):
    """Render cached live facts without creating an arm or placement control."""

    def __init__(self, state: LiveGuiState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if type(state) is not LiveGuiState:
            raise TypeError("state must be exactly LiveGuiState")
        self.state = state
        self.setObjectName("liveStatePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        layout.addWidget(_label("Tiny live · read-only status", self, "liveTitle"))
        status = _label(state.status, self, "liveStatus")
        status.setProperty("status", state.status.casefold())
        layout.addWidget(status)
        layout.addWidget(_label(state.message, self, "liveMessage"))
        facts = QFormLayout()
        facts.addRow(
            _label("Symbol", self, "liveFieldLabel"),
            _label(state.symbol, self, "liveSymbol"),
        )
        facts.addRow(
            _label("Strategy", self, "liveFieldLabel"),
            _label(state.strategy, self, "liveStrategy"),
        )
        facts.addRow(
            _label("Order ceiling", self, "liveFieldLabel"),
            _label(state.order_ceiling, self, "liveOrderCeiling"),
        )
        facts.addRow(
            _label("Plan", self, "liveFieldLabel"),
            _label(state.plan_sha256 or "none", self, "livePlan"),
        )
        layout.addLayout(facts)
