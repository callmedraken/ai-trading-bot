"""Cached Qt presentation for the current local simulated-paper runtime."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trading_bot.desktop_paper.models import (
    PaperAccountState,
    PaperControlState,
    PaperCycleResult,
    PaperStoreSnapshot,
)
from trading_bot.desktop_paper.presentation import DesktopPaperSnapshot
from trading_bot.desktop_runtime import DesktopStatus, Lifecycle


class DesktopPaperController(Protocol):
    """Qt uses cached views and explicit user commands only."""

    def snapshot(self) -> DesktopPaperSnapshot: ...
    def status(self) -> DesktopStatus: ...
    def latch_kill(self) -> bool: ...
    def set_new_buys_enabled(self, enabled: bool) -> bool: ...
    def clear_kill(self) -> bool: ...


def _scalar(value: object) -> str:
    if value is None:
        return "None"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if type(value) is bool:
        return "True" if value else "False"
    return str(value)


def _bounded_text(value: object, *, limit: int = 256) -> str:
    rendered = _scalar(value)
    if len(rendered) <= limit:
        return rendered
    return rendered[: limit - 1] + "…"


def _positions_text(positions: Mapping[object, object]) -> str:
    if not positions:
        return "None"
    return "; ".join(
        f"{_scalar(symbol)}: quantity={_scalar(position.quantity)}, "
        f"average_cost={_scalar(position.average_cost)}"
        for symbol, position in positions.items()
    )


def _account_text(account: PaperAccountState) -> str:
    marked_equity = (
        _scalar(account.marked_equity)
        if account.marked_equity is not None
        else "Unavailable (incomplete marks)"
    )
    unrealized = (
        _scalar(account.unrealized_profit_loss)
        if account.unrealized_profit_loss is not None
        else "Unavailable (incomplete marks)"
    )
    last_fill = _fill_text(account.fills[-1]) if account.fills else "None"
    return (
        f"cash={_scalar(account.cash)}; "
        f"positions={_positions_text(account.positions)}; "
        f"realized_profit_loss={_scalar(account.realized_profit_loss)}; "
        f"marked_equity={marked_equity}; unrealized_profit_loss={unrealized}; "
        f"fills_count={len(account.fills)}; latest_fill={last_fill}"
    )


def _control_text(control: PaperControlState | None) -> str:
    if control is None:
        return "Unavailable (no durable control snapshot)"
    return (
        f"version={control.version}; kill_latched={_scalar(control.kill_latched)}; "
        f"new_buys_enabled={_scalar(control.new_buys_enabled)}"
    )


def _proposal_text(value: object) -> str:
    if value is None:
        return "None"
    return (
        f"proposal_id={_scalar(value.proposal_id)}; symbol={_scalar(value.symbol)}; "
        f"side={_scalar(value.side)}; "
        f"desired_quantity={_scalar(value.desired_quantity)}; "
        f"created_at={_scalar(value.created_at)}; reason={_scalar(value.reason)}; "
        f"confidence={_scalar(value.confidence)}"
    )


def _risk_context_text(value: object) -> str:
    if value is None:
        return "Unavailable (no risk context for this cycle)"
    return (
        f"cash={_scalar(value.cash)}; equity={_scalar(value.equity)}; "
        f"positions={_positions_text(value.positions)}; "
        f"current_price={_scalar(value.current_price)}; "
        f"total_market_exposure={_scalar(value.total_market_exposure)}; "
        f"new_trading_enabled={_scalar(value.new_trading_enabled)}; "
        f"as_of={_scalar(value.as_of)}"
    )


def _risk_decision_text(value: object) -> str:
    if value is None:
        return "Unavailable (no risk decision for this cycle)"
    reasons = (
        "; ".join(
            f"code={_scalar(reason.code)}, message={_scalar(reason.message)}, "
            f"observed={_scalar(reason.observed)}, limit={_scalar(reason.limit)}"
            for reason in value.reasons
        )
        or "None"
    )
    return (
        f"outcome={_scalar(value.outcome)}; "
        f"approved_quantity={_scalar(value.approved_quantity)}; "
        f"evaluated_at={_scalar(value.evaluated_at)}; reasons=[{reasons}]"
    )


def _order_text(value: object) -> str:
    if value is None:
        return "Unavailable (no order for this cycle)"
    request = value.request
    return (
        f"order_id={_scalar(request.order_id)}; symbol={_scalar(request.symbol)}; "
        f"side={_scalar(request.side)}; type={_scalar(request.order_type)}; "
        f"quantity={_scalar(request.quantity)}; "
        f"time_in_force={_scalar(request.time_in_force)}; "
        f"submitted_at={_scalar(request.submitted_at)}; "
        f"limit_price={_scalar(request.limit_price)}; status={_scalar(value.status)}; "
        f"filled_quantity={_scalar(value.filled_quantity)}; "
        f"average_fill_price={_scalar(value.average_fill_price)}; "
        f"rejection_reason={_scalar(value.rejection_reason)}"
    )


def _fill_text(value: object) -> str:
    if value is None:
        return "Unavailable (no fill for this cycle)"
    return (
        f"fill_id={_scalar(value.fill_id)}; order_id={_scalar(value.order_id)}; "
        f"symbol={_scalar(value.symbol)}; side={_scalar(value.side)}; "
        f"quantity={_scalar(value.quantity)}; price={_scalar(value.price)}; "
        f"commission={_scalar(value.commission)}; filled_at={_scalar(value.filled_at)}"
    )


def _events_text(cycle: PaperCycleResult | None) -> str:
    if cycle is None or not cycle.order_events:
        return "None"
    return "; ".join(
        f"event_id={_scalar(event.event_id)}; order_id={_scalar(event.order_id)}; "
        f"type={_scalar(event.event_type)}; occurred_at={_scalar(event.occurred_at)}; "
        f"fill_id={_scalar(event.fill_id)}; reason={_scalar(event.reason)}"
        for event in cycle.order_events
    )


def _input_text(cycle: PaperCycleResult) -> str:
    value = cycle.input
    cutoff = (
        value.completed_history_cutoff
        if value.completed_history_cutoff is not None
        else "None (no completed history)"
    )
    marks = (
        "; ".join(
            f"{_scalar(symbol)}={_scalar(price)}"
            for symbol, price in value.current_marks.items()
        )
        or "None"
    )
    return (
        f"execution_session_id={_scalar(value.execution_session_id)}; "
        f"execution_index={_scalar(value.execution_index)}; "
        f"symbol={_scalar(value.symbol)}; "
        f"observation_id={_scalar(value.observation_id)}; "
        f"completed_history_cutoff={cutoff}; "
        f"observation_open={_scalar(value.observation_open)}; "
        f"executed_at={_scalar(value.executed_at)}; "
        f"proposal=[{_proposal_text(value.proposal)}]; "
        f"no_signal_reason={_scalar(value.no_signal_reason)}; "
        f"warmup={_scalar(value.warmup)}; current_marks=[{marks}] (cached cycle marks)"
    )


def _cycle_text(cycle: PaperCycleResult | None) -> str:
    if cycle is None:
        return "No completed cycle is available."
    return "\n".join(
        (
            f"cycle_id={_scalar(cycle.cycle_id)}; kind={_scalar(cycle.kind)}; "
            f"configuration_revision_id={_scalar(cycle.configuration_revision_id)}; "
            f"cursor_index={_scalar(cycle.cursor_index)}",
            f"input: {_input_text(cycle)}",
            f"risk_context: {_risk_context_text(cycle.risk_context)}",
            f"risk_decision: {_risk_decision_text(cycle.risk_decision)}",
            f"order: {_order_text(cycle.order)}",
            f"fill: {_fill_text(cycle.fill)}",
            f"order_events: {_events_text(cycle)}",
            f"account: {_account_text(cycle.account)}",
            f"control: {_control_text(cycle.control)}",
            f"diagnostic: {_bounded_text(cycle.diagnostic)}",
        )
    )


class DesktopPaperPanel(QFrame):
    """Display the latest immutable snapshot; never read the financial store."""

    def __init__(
        self,
        controller: DesktopPaperController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._fields: dict[str, QLabel] = {}
        self.setObjectName("desktopPaperPanel")
        self.setMaximumHeight(390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title = QLabel("Simulated Paper Evaluation", self)
        title.setObjectName("desktopPaperTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(title)

        self.selection_label = QLabel(self)
        self.selection_label.setObjectName("desktopPaperSelection")
        self._plain(self.selection_label)
        layout.addWidget(self.selection_label)
        self.availability_label = QLabel(self)
        self.availability_label.setObjectName("desktopPaperAvailability")
        self._plain(self.availability_label)
        layout.addWidget(self.availability_label)

        controls = QVBoxLayout()
        buttons = QVBoxLayout()
        self.kill_button = QPushButton("Latch kill", self)
        self.kill_button.setObjectName("desktopPaperKill")
        self.clear_kill_button = QPushButton("Clear kill (stopped)", self)
        self.clear_kill_button.setObjectName("desktopPaperClearKill")
        self.new_buys_checkbox = QCheckBox("Allow new buys", self)
        self.new_buys_checkbox.setObjectName("desktopPaperNewBuys")
        self.kill_button.clicked.connect(self._latch_kill)
        self.clear_kill_button.clicked.connect(self._clear_kill)
        self.new_buys_checkbox.toggled.connect(self._set_new_buys)
        buttons.addWidget(self.kill_button)
        buttons.addWidget(self.new_buys_checkbox)
        buttons.addWidget(self.clear_kill_button)
        controls.addLayout(buttons)
        layout.addLayout(controls)

        self._details = QWidget(self)
        self._form = QFormLayout(self._details)
        self._form.setContentsMargins(2, 2, 2, 2)
        self._form.setVerticalSpacing(3)
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("desktopPaperDetailsScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(170)
        self._scroll.setWidget(self._details)
        layout.addWidget(self._scroll, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(250)
        self.refresh()

    @staticmethod
    def _plain(label: QLabel) -> None:
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def _set_field(self, key: str, title: str, value: str) -> None:
        value_label = self._fields.get(key)
        if value_label is None:
            title_label = QLabel(title, self._details)
            title_label.setObjectName(f"desktopPaperFieldLabel{key}")
            self._plain(title_label)
            value_label = QLabel(self._details)
            value_label.setObjectName(f"desktopPaperField{key}")
            self._plain(value_label)
            self._fields[key] = value_label
            self._form.addRow(title_label, value_label)
        value_label.setText(value)

    def _binding_fields(self, snapshot: DesktopPaperSnapshot) -> None:
        binding = snapshot.binding
        if binding is None:
            self.selection_label.setText("Paper strategy: Selection required")
            missing = "Unavailable (strategy selection required)"
            fields = (
                ("Strategy family", "Family"),
                ("Strategy version", "Version"),
                ("Symbol", "Symbol"),
                ("Parameters", "Parameters"),
                ("Research campaign ID", "CampaignId"),
                ("Research bundle ID", "BundleId"),
                ("Research candidate ID", "CandidateId"),
                ("Provenance digest", "ProvenanceDigest"),
            )
            for title, key in fields:
                self._set_field(key, title, missing)
            self._set_field("QualificationPolicy", "Qualification policy", "None")
            self._set_field("LiveEligible", "Live eligible", "False")
            return

        self.selection_label.setText(
            f"Paper strategy: {binding.strategy_family} "
            f"{binding.strategy_version} · {binding.symbol}"
        )
        parameters = (
            "; ".join(
                f"{name}={_scalar(value)}" for name, value in binding.parameter_set
            )
            or "None"
        )
        for title, key, value in (
            ("Strategy family", "Family", binding.strategy_family),
            ("Strategy version", "Version", binding.strategy_version),
            ("Symbol", "Symbol", str(binding.symbol)),
            ("Parameters", "Parameters", parameters),
            ("Research campaign ID", "CampaignId", str(binding.research_campaign_id)),
            ("Research bundle ID", "BundleId", str(binding.research_bundle_id)),
            (
                "Research candidate ID",
                "CandidateId",
                str(binding.research_candidate_id),
            ),
            ("Provenance digest", "ProvenanceDigest", binding.provenance_digest),
            (
                "Purpose",
                "BindingPurpose",
                _scalar(binding.purpose),
            ),
            (
                "Qualification policy",
                "QualificationPolicy",
                _scalar(binding.qualification_policy),
            ),
            ("Live eligible", "LiveEligible", _scalar(binding.live_eligible)),
        ):
            self._set_field(key, title, value)

    def _financial_fields(
        self,
        financial: PaperStoreSnapshot | None,
        latest: PaperCycleResult | None,
    ) -> PaperControlState | None:
        if financial is None:
            for key, title in (
                ("AccountId", "Account ID"),
                ("ConfigRevision", "Configuration revision"),
                ("Cursor", "Consumed session cursor"),
                ("ExecutionSession", "Last execution session (cached)"),
                ("Account", "Financial account"),
                ("StoreLatest", "Store latest cycle"),
            ):
                self._set_field(key, title, "Unavailable (no financial snapshot)")
            control = latest.control if latest is not None else None
            self._set_field("Control", "Durable controls", _control_text(control))
            return control

        self._set_field("AccountId", "Account ID", _scalar(financial.account_id))
        self._set_field(
            "ConfigRevision",
            "Configuration revision",
            _scalar(financial.configuration_revision_id),
        )
        self._set_field(
            "Cursor", "Consumed session cursor", _scalar(financial.cursor_index)
        )
        self._set_field(
            "ExecutionSession",
            "Last execution session (cached)",
            _scalar(financial.execution_session_id),
        )
        self._set_field(
            "Account", "Financial account", _account_text(financial.account)
        )
        self._set_field(
            "StoreLatest",
            "Store latest cycle",
            (
                f"{_scalar(financial.latest_result.kind)} · "
                f"{_scalar(financial.latest_result.cycle_id)}"
                if financial.latest_result is not None
                else "No completed cycle is available."
            ),
        )
        self._set_field("Control", "Durable controls", _control_text(financial.control))
        return financial.control

    def refresh(self) -> None:
        """Refresh from controller-owned immutable memory only."""
        snapshot = self._controller.snapshot()
        status = self._controller.status()
        self.selection_label.setToolTip("")
        if snapshot.binding is None:
            self.selection_label.setToolTip("PAPER_EVALUATION_SELECTION_REQUIRED")
        self._binding_fields(snapshot)
        availability = (
            "Trading unavailable until an accepted "
            "PAPER_EVALUATION binding is installed."
            if snapshot.binding is None
            else "An explicit PAPER_EVALUATION binding is configured."
        )
        self.availability_label.setText(availability)

        self._set_field(
            "SnapshotState", "Paper snapshot state", _scalar(snapshot.state)
        )
        self._set_field(
            "LifecycleState", "Application lifecycle", _scalar(status.state)
        )
        self._set_field("Activity", "Paper activity", _bounded_text(snapshot.activity))
        self._set_field(
            "Diagnostic",
            "Diagnostic",
            _bounded_text(snapshot.diagnostic) if snapshot.diagnostic else "None",
        )
        self._set_field(
            "Stale",
            "Snapshot stale",
            (
                "True — cached financial values, marks, and session may be stale"
                if snapshot.stale
                else "False — cached financial values, marks, and session are current"
            ),
        )
        self._set_field("Mode", "Mode", _scalar(snapshot.mode))
        self._set_field("Purpose", "Purpose", _scalar(snapshot.purpose))
        self._set_field("SourceLane", "Source lane", _scalar(snapshot.source_lane))
        self._set_field(
            "FinancialAvailability",
            "Financial snapshot availability",
            "Available" if snapshot.financial is not None else "Unavailable",
        )

        control = self._financial_fields(snapshot.financial, snapshot.latest)
        self._set_field(
            "LatestCycle", "Latest worker cycle", _cycle_text(snapshot.latest)
        )
        self._set_field(
            "LatestStoreCycleDetails",
            "Latest stored cycle details",
            _cycle_text(
                snapshot.financial.latest_result
                if snapshot.financial is not None
                else None
            ),
        )

        kill_latched = control.kill_latched if control is not None else False
        new_buys_enabled = control.new_buys_enabled if control is not None else False
        self.kill_button.setEnabled(status.can_stop and not kill_latched)
        self.new_buys_checkbox.blockSignals(True)
        self.new_buys_checkbox.setChecked(new_buys_enabled)
        self.new_buys_checkbox.blockSignals(False)
        self.new_buys_checkbox.setEnabled(status.can_stop and not kill_latched)
        self.new_buys_checkbox.setVisible(control is not None)
        self.clear_kill_button.setEnabled(
            status.state is Lifecycle.STOPPED and status.can_start and kill_latched
        )

    def _latch_kill(self) -> None:
        self._controller.latch_kill()
        self.refresh()

    def _set_new_buys(self, enabled: bool) -> None:
        self._controller.set_new_buys_enabled(enabled)
        self.refresh()

    def _clear_kill(self) -> None:
        self._controller.clear_kill()
        self.refresh()
