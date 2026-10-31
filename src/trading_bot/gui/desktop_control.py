"""Current desktop lifecycle controls, separate from historical evidence views."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from trading_bot.desktop_runtime import DesktopSupervisor


class DesktopControl(QWidget):
    """Widgets call only the injected supervisor service; no worker access."""

    def __init__(self, controller: DesktopSupervisor, parent: QWidget) -> None:
        super().__init__(parent)
        self._controller = controller
        layout = QVBoxLayout(self)
        title = QLabel("Desktop bot · inert trading worker · LIVE disabled", self)
        layout.addWidget(title)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("desktopStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start", self)
        self.start_button.setObjectName("desktopStart")
        self.stop_button = QPushButton("Stop", self)
        self.stop_button.setObjectName("desktopStop")
        self.start_button.clicked.connect(controller.start)
        self.stop_button.clicked.connect(controller.stop)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(50)
        self.refresh()

    def refresh(self) -> None:
        status = self._controller.status()
        artifact = status.research.artifact
        self.status_label.setText(
            f"Application: {status.state.value} | Generation: {status.generation}\n"
            f"Trading: {status.trading.state.value} | "
            f"Research: {status.research.state.value}\n"
            f"Transport: {status.transport} (deferred to P5)\n"
            f"Diagnostic: {status.diagnostic.value}\n"
            + (
                f"Campaign: {artifact.campaign_id}\nBundle: {artifact.bundle_id}"
                if artifact
                else "Research: awaiting local bundle verification"
            )
        )
        self.start_button.setEnabled(status.can_start)
        self.stop_button.setEnabled(status.can_stop)
