"""Read-only Qt rendering of recorded runtime evidence; no effect controls."""

from __future__ import annotations

from datetime import date, datetime
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

from trading_bot.gui.runtime_models import RuntimePageState


class RuntimePage(QWidget):
    """Display one immutable acquired state without services or file access."""

    def __init__(self, state: RuntimePageState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if type(state) is not RuntimePageState:
            raise TypeError("Exact RuntimePageState required")
        self.setObjectName("runtimePage")
        self._state = state
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("runtimeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = self._label("Production Runtime & Session Evidence", content)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        scope = self._label(
            "Read-only, evidence-based presentation. Recorded readiness is not "
            "fresh production authority or current trading authority. This is "
            "not an execution/control surface.",
            content,
        )
        scope.setObjectName("runtimeScope")
        layout.addWidget(scope)
        status = self._label(f"{state.status.value}: {state.message}", content)
        status.setObjectName("runtimeStatus")
        layout.addWidget(status)
        for name, evidence in (
            ("Qualification", state.qualification),
            ("Session", state.session),
        ):
            if evidence is not None:
                self._section(
                    layout,
                    f"Recorded source — {name}",
                    evidence,
                    (
                        ("source_head", "HEAD"),
                        ("source_tree", "TREE"),
                    ),
                )
        if state.acl is not None:
            self._section(
                layout,
                "Runtime security",
                state.acl,
                (
                    ("status", "ACL status"),
                    ("result", "ACL result"),
                    ("runtime_sid_digest", "Runtime-principal digest"),
                    ("acl_apply_attempts", "ACL apply attempts"),
                    ("acl_applies_verified", "Verified ACL applies"),
                    ("parent_mutations", "Parent mutations"),
                    ("recursive_mutations", "Recursive mutations"),
                    ("credential_mutations", "Credential mutations"),
                    ("scheduler_mutations", "Scheduler mutations"),
                    ("provider_calls", "Provider calls"),
                    ("paper_mutations", "Paper mutations"),
                    ("session_mutations", "Session mutations"),
                    ("broker_mutations", "Broker mutations"),
                ),
            )
        if state.qualification is not None:
            qualification = state.qualification
            self._section(
                layout,
                "Recorded SQLite readiness",
                qualification,
                (
                    ("status", "Qualification status"),
                    ("runtime_status", "Runtime status"),
                    ("paper_store_write_readiness", "Paper-store readiness"),
                    ("session_store_write_readiness", "Session-store readiness"),
                    ("paper_records", "Paper records"),
                    ("session_reservations", "Session reservations"),
                ),
            )
            self._section(
                layout,
                "Recorded credential readiness",
                qualification,
                (
                    ("alpaca_credential_reads", "Alpaca credential reads"),
                    ("robinhood_credential_reads", "Robinhood OAuth reads"),
                    ("persisted_oauth_available", "Persisted OAuth available"),
                ),
            )
            self._section(
                layout,
                "Recorded external / trading effects",
                qualification,
                (
                    ("alpaca_http_calls", "Alpaca HTTP calls"),
                    ("robinhood_application_calls", "Robinhood application calls"),
                    ("paper_trade_mutations", "Paper trade mutations"),
                    ("scheduler_mutations", "Scheduler mutations"),
                    ("broker_mutations", "Broker mutations"),
                    ("effect_counts_complete", "Effect counts complete"),
                ),
            )
        if state.session is not None:
            self._section(
                layout,
                "Current / last supplied D1 session",
                state.session,
                (
                    ("target_session", "Target session"),
                    ("status", "Session status"),
                    ("strategy_outcome", "Strategy outcome"),
                    ("historical_provider", "Historical provider"),
                    ("historical_sessions", "Historical session count"),
                    ("wait_started_at", "Wait started"),
                    ("admitted_at", "Admitted"),
                    ("admission_opens_at", "Admission opens"),
                    ("admission_closes_at", "Admission closes"),
                    ("prepare_result", "Prepare result"),
                    ("execute_result", "Execute result"),
                    ("alpaca_reads", "Alpaca reads"),
                    ("strategy_evaluations", "Strategy evaluations"),
                    ("prepare_attempts", "Prepare attempts"),
                    ("execute_attempts", "Execute attempts"),
                    ("robinhood_get_equity_quotes", "Robinhood quote reads"),
                    ("robinhood_get_accounts", "Robinhood account reads"),
                    ("robinhood_get_equity_orders", "Robinhood order reads"),
                    ("robinhood_review_equity_order", "Robinhood reviews"),
                    ("paper_mutations", "Paper mutations"),
                    ("broker_placement_count", "Broker placements"),
                    ("effect_counts_complete", "Effect counts complete"),
                    ("contract_id", "Contract ID"),
                    ("operation_id", "Operation ID"),
                    ("proposal_id", "Proposal ID"),
                    ("order_id", "Order ID"),
                    ("fill_id", "Fill ID"),
                ),
            )
        layout.addStretch(1)
        scroll.setWidget(content)

    @staticmethod
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

    def _section(
        self,
        layout: QVBoxLayout,
        title: str,
        evidence: object,
        rows: tuple[tuple[str, str], ...],
    ) -> None:
        card = QFrame(self)
        card.setObjectName("runtimeEvidenceCard")
        grid = QGridLayout(card)
        grid.setColumnMinimumWidth(0, 180)
        grid.setHorizontalSpacing(14)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self._label(title, card), 0, 0, 1, 2)
        for index, (name, caption) in enumerate(rows, start=1):
            value = getattr(evidence, name)
            if value is None:
                text = "Not recorded / unknown"
            elif isinstance(value, Enum):
                text = value.value
            elif isinstance(value, (date, datetime)):
                text = value.isoformat()
            elif type(value) is tuple:
                text = str(len(value))
            elif type(value) is bool:
                text = "Yes" if value else "No"
            else:
                text = str(value)
            caption_label = self._label(caption, card)
            caption_label.setObjectName(f"runtimeCaption_{name}")
            caption_label.setMinimumWidth(160)
            grid.addWidget(caption_label, index, 0)
            label = self._label(text, card)
            label.setObjectName(f"runtime_{name}")
            grid.addWidget(label, index, 1)
        layout.addWidget(card)
