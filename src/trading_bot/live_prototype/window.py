"""Current five-page synthetic composition; effects stay outside the GUI."""

from __future__ import annotations

from pathlib import Path

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
from trading_bot.live_prototype.contracts import Command
from trading_bot.live_prototype.synthetic_service import SyntheticApplicationService


class PrototypeWindow(QMainWindow):
    def __init__(self, service: SyntheticApplicationService) -> None:
        super().__init__()
        self._service = service
        self._closing = False
        self.setWindowTitle("Trading research prototype - synthetic workspace")
        self.resize(1366, 768)
        self.setMinimumSize(960, 600)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        self._banner = QLabel(
            "Synthetic workspace | explicit worker start | live effects unavailable",
            central,
        )
        self._banner.setTextFormat(Qt.TextFormat.PlainText)
        self._banner.setWordWrap(True)
        self._banner.setObjectName("prototypeSafetyBanner")
        layout.addWidget(self._banner)
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
        body.addWidget(navigation)
        body.addWidget(stack, 1)
        layout.addLayout(body, 1)
        self.setCentralWidget(central)
        open_report = self.menuBar().addAction("Open comparison report...")
        open_report.triggered.connect(self._open_report)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

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
        if self._closing and self._service.shutdown_complete():
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing:
            self._closing = True
            self._service.submit(Command.STOP)
        if self._service.shutdown_complete():
            self._timer.stop()
            event.accept()
        else:
            self._banner.setText(
                "Stopping synthetic workers; waiting for confirmed shutdown"
            )
            event.ignore()
