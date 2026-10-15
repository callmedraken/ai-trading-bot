"""Selectable, scrollable local lifecycle evidence, with no action controls."""

from dataclasses import fields

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
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

        def label(text: str, name: str = "researchLifecycleDetail") -> None:
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

        label("Research Lifecycle", "pageTitle")
        label(f"{state.status.value}: {state.message}", "researchLifecycleStatus")
        label("Verification covers local artifacts and successor linkage only.")
        label(
            "This inspection grants no source acceptance, promotion eligibility, "
            "production readiness or trading readiness."
        )
        evidence = state.evidence
        if evidence is not None:
            label(f"Stage: {evidence.stage.value}", "researchLifecycleStage")
            label(
                "Recorded lineage: BACKTESTED → WALK_FORWARD_PASSED → "
                "139-A binding → 139-B1 observations → 139-B2 qualification → SHADOW"
            )
            for title, value in (
                ("SHADOW candidate ID", evidence.shadow_candidate_id),
                (
                    "WALK_FORWARD_PASSED candidate ID",
                    evidence.walk_forward_passed_candidate_id,
                ),
                ("BACKTESTED ancestor candidate ID", evidence.backtested_candidate_id),
                (
                    "Walk-forward qualification ID",
                    evidence.walk_forward_qualification_id,
                ),
                ("139-A binding ID", evidence.binding_id),
                ("B1 observation batch ID", evidence.observation_batch_id),
                ("B2 qualification ID", evidence.qualification_id),
                ("Report ID", evidence.report_id),
                ("Experiment result ID", evidence.experiment_result_id),
                ("Variant ID", evidence.variant_id),
                ("Caller ordinal", evidence.caller_ordinal),
                ("Variant name", evidence.variant_name),
                (
                    "Original rank",
                    "Unranked" if evidence.rank is None else evidence.rank,
                ),
            ):
                label(f"{title}: {value}")
            label(RANK_NOTICE, "researchLifecycleRankNotice")
            label("Recorded source provenance", "operatorSectionTitle")
            for title, source in (
                ("Candidate", evidence.candidate_source),
                (
                    "Walk-forward qualification",
                    evidence.walk_forward_qualification_source,
                ),
                ("139-A binding", evidence.binding_source),
                ("B1 observation", evidence.observation_source),
                ("B2 qualification", evidence.qualification_source),
            ):
                label(f"{title} HEAD: {source.head}")
                label(f"{title} TREE: {source.tree}")
            label("B1 recorded observation summary", "operatorSectionTitle")
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
            for item in fields(observations.zero_effects):
                value = getattr(observations.zero_effects, item.name)
                label(f"{item.name.upper()}: {value}")
            label("B2 recorded coverage qualification", "operatorSectionTitle")
            qualification = evidence.qualification
            for item in fields(qualification):
                value = getattr(qualification, item.name)
                if item.name == "status":
                    value = value.value
                elif item.name == "failure_reasons":
                    value = "None (ordered empty reasons)"
                label(f"{item.name}: {value}")
            label("Coverage evidence does not infer profitability or trading quality.")
        label("Governance — fixed, no authority", "operatorSectionTitle")
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
