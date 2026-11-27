"""Small Qt dashboard over cached Portfolio Manager worker state."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_bot.portfolio_manager.application_service import (
    HistoryEntry,
    OutcomePresentation,
    PortfolioManagerApplicationService,
    PortfolioManagerSnapshot,
)
from trading_bot.portfolio_manager.models import decimal_sum


class PortfolioManagerWindow(QMainWindow):
    """Start/Stop dashboard with no provider or execution controls."""

    def __init__(
        self, service: PortfolioManagerApplicationService, *, refresh_ms: int = 250
    ) -> None:
        super().__init__()
        if not isinstance(service, PortfolioManagerApplicationService):
            raise TypeError("PortfolioManagerApplicationService required")
        if type(refresh_ms) is not int or refresh_ms < 50:
            raise ValueError("refresh_ms must be at least 50 milliseconds")
        self._service = service
        self._closing = False
        self.setWindowTitle("Portfolio Manager — Synthetic Preview")
        self.resize(1280, 850)
        self.setMinimumSize(1000, 700)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self._safety = QLabel(central)
        self._safety.setObjectName("portfolioManagerSafetyBanner")
        self._safety.setTextFormat(Qt.TextFormat.PlainText)
        self._safety.setWordWrap(True)
        layout.addWidget(self._safety)

        controls = QHBoxLayout()
        self._lifecycle = QLabel(central)
        self._lifecycle.setObjectName("portfolioManagerLifecycle")
        self._start = QPushButton("Start monitoring and research", central)
        self._start.setObjectName("portfolioManagerStart")
        self._stop = QPushButton("Stop workers", central)
        self._stop.setObjectName("portfolioManagerStop")
        self._start.clicked.connect(self._start_workers)
        self._stop.clicked.connect(self._stop_workers)
        controls.addWidget(self._lifecycle, 1)
        controls.addWidget(self._start)
        controls.addWidget(self._stop)
        layout.addLayout(controls)

        self._account = QLabel(central)
        self._account.setObjectName("portfolioManagerAccount")
        self._portfolio_summary = QLabel(central)
        self._portfolio_summary.setObjectName("portfolioManagerTotals")
        self._worker_health = QLabel(central)
        self._worker_health.setObjectName("portfolioManagerWorkerHealth")
        layout.addWidget(self._account)
        layout.addWidget(self._portfolio_summary)
        layout.addWidget(self._worker_health)

        summary_layout = QGridLayout()
        self._holdings = _table(
            (
                "Symbol",
                "Quantity",
                "Available to sell",
                "Average cost",
                "Price",
                "Unrealized P&L",
            ),
            central,
        )
        self._recommendations = _table(
            (
                "Symbol",
                "Scope",
                "Action",
                "Target quantity",
                "Risk",
                "Evidence",
                "Rationale / provider diagnostics",
            ),
            central,
        )
        self._previews = _table(
            ("Symbol", "Side", "Quantity", "Reference price", "Plan status", "Reasons"),
            central,
        )
        self._history = _table(
            (
                "Decision time",
                "Strategy",
                "Snapshot",
                "Recommendations",
                "Preview legs",
            ),
            central,
        )
        summary_layout.addWidget(QLabel("Adopted holdings", central), 0, 0)
        summary_layout.addWidget(self._holdings, 1, 0)
        summary_layout.addWidget(QLabel("Recommendations and risk", central), 2, 0)
        summary_layout.addWidget(self._recommendations, 3, 0)
        summary_layout.addWidget(QLabel("Preview only — no dispatch", central), 4, 0)
        summary_layout.addWidget(self._previews, 5, 0)
        summary_layout.addWidget(QLabel("Durable decision history", central), 6, 0)
        summary_layout.addWidget(self._history, 7, 0)
        layout.addLayout(summary_layout, 1)
        self.setCentralWidget(central)

        self._timer = QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self._refresh)
        self._refresh()
        self._timer.start()

    def _start_workers(self) -> None:
        self._service.start()
        self._refresh()

    def _stop_workers(self) -> None:
        self._service.stop()
        self._refresh()

    def _refresh(self) -> None:
        snapshot = self._service.snapshot()
        self._lifecycle.setText(f"Lifecycle: {snapshot.lifecycle.value}")
        self._account.setText(
            "Synthetic account binding: " + snapshot.account_fingerprint[:12] + "…"
        )
        self._safety.setText(
            "SYNTHETIC / DISARMED — preview plans are informational; "
            "order dispatch, live placement, and provider credentials are unavailable."
        )
        self._worker_health.setText(
            f"Monitoring: {snapshot.monitor_health.value} | "
            f"Research: {snapshot.research_health.value} | "
            f"Diagnostic: {snapshot.diagnostic or 'NONE'}"
        )
        running = snapshot.lifecycle.value in {"STARTING", "RUNNING", "STOPPING"}
        self._start.setEnabled(not running and not self._closing)
        self._stop.setEnabled(running and not self._closing)
        self._render_portfolio(snapshot)
        self._render_presentation(snapshot.latest, snapshot.observation)
        self._render_history(snapshot.history)
        if self._closing and self._service.shutdown_complete():
            self._timer.stop()
            self.close()

    def _render_portfolio(self, snapshot: PortfolioManagerSnapshot) -> None:
        observation = snapshot.observation
        if observation is None:
            self._portfolio_summary.setText("Portfolio: waiting for an observation")
            self._holdings.setRowCount(0)
            return
        long_positions = tuple(
            position for position in observation.positions if position.quantity > 0
        )
        exposure = (
            None
            if any(
                position.market_value is None or not position.supported
                for position in long_positions
            )
            else decimal_sum([position.market_value for position in long_positions])
        )
        self._portfolio_summary.setText(
            "Cash: "
            f"{_money(observation.cash)} | Broker-reported equity: "
            f"{_money(observation.broker_reported_equity)} | Locally valued equity: "
            f"{_money(observation.locally_computed_equity)} | Long exposure: "
            f"{_money(exposure)} | Order coverage: "
            f"{observation.coverage.order_scope.value} | Observed: "
            f"{observation.observed_at.isoformat()}"
        )
        account_mismatch = snapshot.diagnostic == "ACCOUNT_BINDING_MISMATCH" or (
            observation.observed_account_fingerprint is not None
            and observation.observed_account_fingerprint != snapshot.account_fingerprint
        )
        account_status = (
            "MISMATCH"
            if account_mismatch
            else "BOUND"
            if observation.coverage.account_bound
            else "UNBOUND"
        )
        self._account.setText(
            "Account status: "
            + account_status
            + " | Observation status: "
            + ("COMPLETE" if observation.preview_eligible else "INCOMPLETE")
            + " | Conditions: "
            + (", ".join(item.value for item in observation.conditions) or "NONE")
            + " | Fingerprint: "
            + snapshot.account_fingerprint[:12]
            + "…"
        )
        rows = []
        for position in observation.positions:
            rows.append(
                (
                    str(position.symbol),
                    _money(position.quantity),
                    _money(position.available_to_sell),
                    _money(position.average_cost),
                    _money(position.current_price),
                    _money(position.unrealized_pnl),
                )
            )
        _set_rows(self._holdings, rows)

    def _render_presentation(
        self, result: OutcomePresentation | None, observation
    ) -> None:
        if result is None:
            self._recommendations.setRowCount(0)
            self._previews.setRowCount(0)
            return
        held_symbols = (
            set()
            if observation is None
            else {str(item.symbol) for item in observation.positions}
        )
        _set_rows(
            self._recommendations,
            [
                (
                    item.symbol,
                    "HELD" if item.symbol in held_symbols else "OPPORTUNITY",
                    item.action,
                    item.target_quantity or "—",
                    item.risk_status
                    + (
                        ": " + ", ".join(item.risk_reasons) if item.risk_reasons else ""
                    ),
                    "AVAILABLE" if item.evidence_available else "UNAVAILABLE",
                    item.rationale
                    + (
                        " | Provider: " + "; ".join(item.provider_diagnostics)
                        if item.provider_diagnostics
                        else ""
                    ),
                )
                for item in result.decisions
            ],
        )
        _set_rows(
            self._previews,
            [
                (
                    item.symbol,
                    item.side,
                    item.quantity,
                    item.reference_price or "—",
                    item.status,
                    ", ".join(item.reasons) or "No risk block; disarmed preview only",
                )
                for item in result.preview_legs
            ],
        )

    def _render_history(self, history: tuple[HistoryEntry, ...]) -> None:
        _set_rows(
            self._history,
            [
                (
                    entry.presentation.decision_at.isoformat(),
                    entry.presentation.strategy_id
                    + " "
                    + entry.presentation.strategy_version,
                    str(entry.stored.snapshot_id)[:12] + "…",
                    str(len(entry.presentation.decisions)),
                    str(len(entry.presentation.preview_legs)),
                )
                for entry in reversed(history)
            ],
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing:
            self._closing = True
            self._service.stop()
        if self._service.shutdown_complete():
            self._timer.stop()
            event.accept()
        else:
            self._lifecycle.setText("Lifecycle: STOPPING — waiting for worker shutdown")
            event.ignore()


def _table(headers: tuple[str, ...], parent: QWidget) -> QTableWidget:
    table = QTableWidget(parent)
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSortingEnabled(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _set_rows(table: QTableWidget, rows: list[tuple[str, ...]]) -> None:
    table.setRowCount(len(rows))
    for row_index, values in enumerate(rows):
        for column_index, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_index, column_index, item)


def _money(value: Decimal | None) -> str:
    if value is None:
        return "Unknown"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
