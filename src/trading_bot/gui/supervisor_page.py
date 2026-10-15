"""Plain-text, scrollable Supervisor presentation with zero effect controls."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from trading_bot.gui.supervisor_models import SupervisorPageState


class SupervisorPage(QWidget):
    """Render an immutable snapshot without holding a service or reader."""

    def __init__(
        self, state: SupervisorPageState, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        if type(state) is not SupervisorPageState:
            raise TypeError("Exact SupervisorPageState required")
        self.setObjectName("supervisorPage")
        self._state = state
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("supervisorScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        def label(text: str, name: str = "supervisorDetail") -> None:
            widget = QLabel(text, content)
            widget.setObjectName(name)
            widget.setTextFormat(Qt.TextFormat.PlainText)
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            widget.setWordWrap(True)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            layout.addWidget(widget)

        label("Supervisor & Governance", "pageTitle")
        label(f"{state.status.value}: {state.message}", "supervisorStatus")
        label("Supervisor connection", "operatorSectionTitle")
        label("CURRENT CONNECTION: D2 supervisor runtime: Not connected")
        label("Recorded trading evidence", "operatorSectionTitle")
        session = state.runtime.session
        if session is None:
            label("No D1 session evidence is selected.")
        else:
            label(
                f"Recorded D1 status: {session.status.value}",
                "supervisorRecordedStatus",
            )
            label(f"Recorded target session: {session.target_session.isoformat()}")
            label(f"Recorded contract ID: {session.contract_id}")
        label("Production strategy", "operatorSectionTitle")
        contract = state.production_strategy.contract
        if contract is None:
            label(state.production_strategy.message)
        else:
            for title, value in (
                ("Contract ID", contract.contract_id),
                ("Target session", contract.target_session_date.isoformat()),
                ("Strategy", f"{contract.strategy_id} / {contract.strategy_version}"),
                ("Symbol", contract.symbol),
                ("Short window", contract.short_window),
                ("Long window", contract.long_window),
                ("Desired quantity", format(contract.desired_quantity, "f")),
                ("HEAD", contract.source_head),
                ("TREE", contract.source_tree),
            ):
                label(f"{title}: {value}")
        label("Research evidence", "operatorSectionTitle")
        label(state.research_message)
        if state.research_report_id is not None:
            label(f"Report ID: {state.research_report_id}")
            label(f"Experiment result ID: {state.research_experiment_result_id}")
        label("Strategy Promotion", "operatorSectionTitle")
        lifecycle = state.research_lifecycle
        if lifecycle is not None:
            label(lifecycle.message)
            if lifecycle.evidence is not None:
                label("Research candidate stage: SHADOW")
                label(f"Candidate ID: {lifecycle.evidence.shadow_candidate_id}")
            label("Human promotion required: Yes\nProduction replacement: Disabled")
            label("Production compatibility: Not established")
        label(
            "Automatic promotion: Disabled\nHuman promotion: Required\n"
            "Promotion authority: Not connected"
        )
        label(
            "Research evidence may inform future strategy review. "
            "It cannot replace the production strategy automatically."
        )
        label("Cross-evidence consistency", "operatorSectionTitle")
        label(state.consistency.value, "supervisorConsistency")
        label("D2 target behavior — future design", "operatorSectionTitle")
        label(
            "TARGET D2 DESIGN ONLY: PC ON -> supervisor reconciles current reality; "
            "research may remain operational while the trading plane waits; "
            "research never self-promotes."
        )
        label(
            "Future vocabulary: RECONCILE, PREMARKET_WAIT, TRADING, "
            "NEXT_SESSION_WAIT, BLOCKED. No D2 effects are implemented."
        )
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
