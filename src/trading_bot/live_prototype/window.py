"""Five-page synthetic and real/disarmed composition over cached service state."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.prototype_activity_page import ActivityHealthPage
from trading_bot.gui.prototype_dashboard import DashboardPage
from trading_bot.gui.prototype_research_page import ResearchPage
from trading_bot.gui.prototype_session_page import LiveSessionPage
from trading_bot.gui.prototype_strategy_page import StrategyPage
from trading_bot.live_prototype.contracts import (
    Command,
    PrototypeCommandResult,
    PrototypeSnapshot,
)


class _WindowApplicationService(Protocol):
    """Small window contract shared by synthetic and real/disarmed services."""

    def snapshot(self) -> PrototypeSnapshot: ...
    def submit(self, command: Command) -> PrototypeCommandResult: ...
    def request_report(self, path: Path) -> bool: ...
    def shutdown_complete(self) -> bool: ...


class PrototypeWindow(QMainWindow):
    def __init__(
        self, service: _WindowApplicationService, *, mode: str | None = None
    ) -> None:
        super().__init__()
        self._service = service
        self._closing = False
        snapshot = service.snapshot()
        self._mode = mode if mode is not None else snapshot.mode
        if self._mode not in ("SYNTHETIC", "REAL_DISARMED"):
            raise ValueError("explicit synthetic or real/disarmed mode required")
        if snapshot.mode != self._mode:
            raise ValueError("window mode must match the composed application service")
        self.setWindowTitle(f"Trading research prototype - {self._mode}")
        self.resize(1366, 768)
        self.setMinimumSize(960, 600)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        self._banner = QLabel(central)
        self._banner.setTextFormat(Qt.TextFormat.PlainText)
        self._banner.setWordWrap(True)
        self._banner.setObjectName("prototypeSafetyBanner")
        layout.addWidget(self._banner)
        self._identity_details = QLabel(central)
        self._identity_details.setTextFormat(Qt.TextFormat.PlainText)
        self._identity_details.setWordWrap(True)
        self._identity_details.setObjectName("prototypeIdentityDetails")
        layout.addWidget(self._identity_details)
        body = QHBoxLayout()
        navigation = QListWidget(central)
        navigation.setObjectName("prototypeNavigation")
        navigation.setMaximumWidth(180)
        stack = QStackedWidget(central)
        snapshot = service.snapshot()
        self._pages = (
            DashboardPage(snapshot),
            ResearchPage(snapshot),
            StrategyPage(snapshot),
            LiveSessionPage(snapshot),
            ActivityHealthPage(snapshot),
        )
        for label, page in zip(
            ("Dashboard", "Research", "Strategy", "Live Session", "Activity / Health"),
            self._pages,
            strict=True,
        ):
            navigation.addItem(label)
            stack.addWidget(page)
        navigation.currentRowChanged.connect(stack.setCurrentIndex)
        navigation.setCurrentRow(0)
        self._pages[3].start_requested.connect(lambda: self._submit(Command.START))
        self._pages[3].stop_requested.connect(lambda: self._submit(Command.STOP))
        self._configure_session_controls()
        body.addWidget(navigation)
        body.addWidget(stack, 1)
        layout.addLayout(body, 1)
        self.setCentralWidget(central)
        open_report = self.menuBar().addAction("Open comparison report...")
        open_report.triggered.connect(self._open_report)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self._render_status(snapshot)
        self._timer.start()

    def _configure_session_controls(self) -> None:
        if self._mode == "SYNTHETIC":
            return
        page = self._pages[3]
        page.start_button.setText("Start disarmed workers")
        page.start_button.setObjectName("sessionStartDisarmedWorkers")
        page.stop_button.setText("Stop disarmed workers")
        page.stop_button.setObjectName("sessionStopDisarmedWorkers")
        for name, value in (
            (
                "sessionScope",
                "Start or stop independent disarmed application workers.",
            ),
            ("sessionRequestHeading", "Real/disarmed application"),
            (
                "sessionRequestNote",
                "Worker status is observational; order mutations are unavailable.",
            ),
        ):
            label = page.findChild(QLabel, name)
            if label is not None:
                label.setText(value)

    def _open_report(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open comparison evidence", "", "Comparison report (*.json)"
        )
        if path and not self._closing:
            self._service.request_report(Path(path))

    def _submit(self, command: Command) -> None:
        result = self._service.submit(command)
        if not result.accepted:
            self._banner.setText("Command rejected: " + result.reason.value)
        self._refresh()

    def _refresh(self) -> None:
        snapshot = self._service.snapshot()
        for page in self._pages:
            page.update_snapshot(snapshot)
        self._render_status(snapshot)
        if self._closing and self._service.shutdown_complete():
            self.close()

    def _render_status(self, snapshot: PrototypeSnapshot) -> None:
        reasons = getattr(snapshot, "reasons", ())
        reason_text = (
            ", ".join(getattr(reason, "value", str(reason)) for reason in reasons)
            or "No blockers reported"
        )
        if self._mode == "SYNTHETIC":
            self._banner.setText(
                "Synthetic workspace | explicit worker start | live effects unavailable"
            )
            details = ("Source/configuration/evidence identity: synthetic workspace",)
        else:
            ready = (
                "READY"
                if getattr(snapshot, "ready_to_trade", False)
                and self._mode != "REAL_DISARMED"
                else "BLOCKED"
            )
            self._banner.setText(
                f"REAL_DISARMED workspace | order mutation unavailable | "
                f"trading readiness: {ready} | blockers: {reason_text}"
            )
            display_details = getattr(self._service, "display_details", None)
            details = display_details() if callable(display_details) else ()
        self._identity_details.setText("\n".join(details))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing:
            self._closing = True
            self._service.submit(Command.STOP)
        if self._service.shutdown_complete():
            self._timer.stop()
            event.accept()
        else:
            self._banner.setText(
                "Stopping application workers; waiting for confirmed shutdown"
            )
            event.ignore()
