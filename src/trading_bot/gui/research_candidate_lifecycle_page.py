"""Selectable, scrollable local lifecycle evidence, with no action controls."""

from dataclasses import fields

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

from trading_bot.gui.research_candidate_lifecycle_audit import (
    COVERAGE_NOTICE,
    ZERO_EFFECT_NOTICE,
    compose_lifecycle_audit,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    RANK_NOTICE,
    ResearchCandidateLifecyclePageState,
)


class ResearchCandidateLifecyclePage(QWidget):
    def __init__(
        self, state: ResearchCandidateLifecyclePageState, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        if type(state) is not ResearchCandidateLifecyclePageState:
            raise TypeError("Exact lifecycle page state required")
        self._state = state
        audit = compose_lifecycle_audit(state)
        self.setObjectName("researchCandidateLifecyclePage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setObjectName("researchLifecycleScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        target = layout

        def label(text: str, name: str = "researchLifecycleDetail") -> QLabel:
            widget = QLabel(text, content)
            widget.setObjectName(name)
            widget.setTextFormat(Qt.TextFormat.PlainText)
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            widget.setWordWrap(True)
            widget.setMinimumWidth(0)
            policy = QSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            policy.setHeightForWidth(True)
            widget.setSizePolicy(policy)
            target.addWidget(widget)
            return widget

        def section(title: str) -> None:
            nonlocal target
            frame = QFrame(content)
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            target = QVBoxLayout(frame)
            target.setSpacing(6)
            layout.addWidget(frame)
            label(title, "operatorSectionTitle")

        label("Research Lifecycle", "pageTitle")
        label(f"{state.status.value}: {state.message}", "researchLifecycleStatus")
        label("Verification covers local artifacts and successor linkage only.")
        label(
            "This inspection grants no source acceptance, promotion eligibility, "
            "production readiness or trading readiness."
        )
        evidence = state.evidence
        if evidence is not None:
            section("Governance / authority boundary")
            for row in audit.governance:
                label(f"{row.label}: {row.value}")
            section("Artifact identity chain")
            label(f"Stage: {evidence.stage.value}", "researchLifecycleStage")
            label(
                "Recorded lineage: BACKTESTED → WALK_FORWARD_PASSED → "
                "139-A binding → 139-B1 observations → 139-B2 qualification → SHADOW"
            )
            for row in audit.artifacts:
                label(f"{row.label}: {row.value}", "researchLifecycleArtifact")
            section("Supporting retained identities")
            for row in audit.supporting:
                label(f"{row.label}: {row.value}")
            label(RANK_NOTICE, "researchLifecycleRankNotice")
            section("Recorded source provenance")
            for row in audit.provenance:
                label(f"{row.label} HEAD: {row.head}")
                label(f"{row.label} TREE: {row.tree}")
            section("Coverage comparison")
            grid = QGridLayout()
            target.addLayout(grid)
            for column, heading in enumerate(
                ("Metric", "Required", "Recorded", "Margin")
            ):
                widget = label(heading, "researchLifecycleCoverageHeading")
                target.removeWidget(widget)
                grid.addWidget(widget, 0, column)
            grid.setColumnStretch(0, 3)
            for column in (1, 2, 3):
                grid.setColumnStretch(column, 1)
            for index, row in enumerate(audit.coverage, start=1):
                for column, value in enumerate(
                    (row.metric, row.required, row.recorded, row.margin)
                ):
                    widget = label(str(value), "researchLifecycleCoverageValue")
                    target.removeWidget(widget)
                    grid.addWidget(widget, index, column)
            label(COVERAGE_NOTICE, "researchLifecycleCoverageNotice")
            section("Zero-effect audit")
            for row in audit.effects:
                label(f"{row.label}: {row.value}")
            label(ZERO_EFFECT_NOTICE, "researchLifecycleZeroEffectNotice")
            section("B1 recorded observation summary")
            observations = evidence.observations
            for title, value in (
                ("Observation count", observations.observation_count),
                ("Distinct session count", observations.distinct_session_count),
                ("First session date", observations.first_session_date.isoformat()),
                ("Last session date", observations.last_session_date.isoformat()),
                (
                    "First observed UTC timestamp",
                    observations.first_observed_at_utc.isoformat(
                        timespec="microseconds"
                    ),
                ),
                (
                    "Last observed UTC timestamp",
                    observations.last_observed_at_utc.isoformat(
                        timespec="microseconds"
                    ),
                ),
            ):
                label(f"{title}: {value}")
            label(
                "Caller-supplied dates and timestamps; no exchange-open or "
                "provider-origin verification."
            )
            section("B2 retained policy / results")
            qualification = evidence.qualification
            for item in fields(qualification):
                value = getattr(qualification, item.name)
                if item.name == "status":
                    value = value.value
                elif item.name == "failure_reasons":
                    value = "None (ordered empty reasons)"
                label(f"{item.name}: {value}")
            label("Coverage evidence does not infer profitability or trading quality.")
        else:
            section("Governance — fixed, no authority")
            for text in (
                "Real observation acquisition: Not connected",
                "Automatic promotion: Disabled",
                "Promotion authority: Not connected",
                "Production compatibility: Not established",
                "PAPER_CANDIDATE: Not materialized",
                "AWAITING_HUMAN_PROMOTION: Not materialized",
                "Trading authority: None",
            ):
                label(text)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
