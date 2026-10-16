"""Closed read-only governance facts, never supervisor/promotion authority."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from trading_bot.gui.production_strategy_models import ProductionStrategyPageState
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState,
)
from trading_bot.gui.runtime_models import RuntimePageState


class SupervisorPageStatus(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    ATTENTION = "ATTENTION"


class SupervisorConsistency(Enum):
    NOT_CHECKED = "NOT_CHECKED"
    CONSISTENT = "CONSISTENT"
    CONFLICTING = "CONFLICTING"


class SupervisorDiagnostic(Enum):
    UNAVAILABLE = (
        "D2 supervisor runtime is not connected; no relevant evidence is selected."
    )
    RECORDED = (
        "Read-only recorded evidence is available; "
        "D2 supervisor runtime is not connected."
    )
    ATTENTION = (
        "Selected recorded evidence requires attention; "
        "D2 supervisor runtime is not connected."
    )
    CONFLICTING = "Production contract and recorded D1 session identities conflict."


@dataclass(frozen=True, slots=True)
class SupervisorPageState:
    status: SupervisorPageStatus
    diagnostic: SupervisorDiagnostic
    consistency: SupervisorConsistency
    production_strategy: ProductionStrategyPageState
    runtime: RuntimePageState
    research_report_id: UUID | None = None
    research_experiment_result_id: UUID | None = None
    research_lifecycle: ResearchCandidateLifecyclePageState | None = None
    supervisor_connected: bool = field(default=False, init=False)
    automatic_promotion_enabled: bool = field(default=False, init=False)
    human_promotion_required: bool = field(default=True, init=False)
    promotion_authority_connected: bool = field(default=False, init=False)
    can_research_replace_production: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (
            self.research_lifecycle is not None
            and type(self.research_lifecycle) is not ResearchCandidateLifecyclePageState
        ):
            raise TypeError("Exact lifecycle presentation state required")
        for value, kind in (
            (self.status, SupervisorPageStatus),
            (self.diagnostic, SupervisorDiagnostic),
            (self.consistency, SupervisorConsistency),
            (self.production_strategy, ProductionStrategyPageState),
            (self.runtime, RuntimePageState),
        ):
            if type(value) is not kind:
                raise TypeError("Exact Supervisor presentation types required")
        for value in (self.research_report_id, self.research_experiment_result_id):
            if value is not None and type(value) is not UUID:
                raise TypeError("Exact bounded research identity required")
        if (self.research_report_id is None) != (
            self.research_experiment_result_id is None
        ):
            raise ValueError("Research identity pair required")
        expected = {
            SupervisorDiagnostic.UNAVAILABLE: SupervisorPageStatus.UNAVAILABLE,
            SupervisorDiagnostic.RECORDED: SupervisorPageStatus.AVAILABLE,
            SupervisorDiagnostic.ATTENTION: SupervisorPageStatus.ATTENTION,
            SupervisorDiagnostic.CONFLICTING: SupervisorPageStatus.ATTENTION,
        }[self.diagnostic]
        if self.status is not expected:
            raise ValueError("Supervisor classifications conflict")
        if (self.consistency is SupervisorConsistency.CONFLICTING) != (
            self.diagnostic is SupervisorDiagnostic.CONFLICTING
        ):
            raise ValueError("Supervisor consistency diagnostic conflict")
        contract = self.production_strategy.contract
        session = self.runtime.session
        if contract is None or session is None:
            if self.consistency is not SupervisorConsistency.NOT_CHECKED:
                raise ValueError("Comparison requires both contract and session")
        else:
            matches = (
                contract.contract_id == session.contract_id
                and contract.source_head == session.source_head
                and contract.source_tree == session.source_tree
                and contract.target_session_date == session.target_session
            )
            if self.consistency is not (
                SupervisorConsistency.CONSISTENT
                if matches
                else SupervisorConsistency.CONFLICTING
            ):
                raise ValueError(
                    "Consistency must describe the exact recorded identities"
                )

    @property
    def message(self) -> str:
        return self.diagnostic.value

    @property
    def research_message(self) -> str:
        return (
            "Research evidence available. Historical experiment report loaded."
            if self.research_report_id is not None
            else "Research evidence not connected."
        )
