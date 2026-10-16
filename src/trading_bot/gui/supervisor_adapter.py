"""Pure Supervisor composition from already-acquired GUI states."""

from uuid import UUID

from trading_bot.gui.models import ResearchPageState, ResearchReportStatus
from trading_bot.gui.production_strategy_models import (
    ProductionStrategyPageState,
    ProductionStrategyPageStatus,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState,
    ResearchCandidateLifecyclePageStatus,
)
from trading_bot.gui.runtime_models import RuntimePageState, RuntimePageStatus
from trading_bot.gui.supervisor_models import (
    SupervisorConsistency,
    SupervisorDiagnostic,
    SupervisorPageState,
    SupervisorPageStatus,
)


def build_supervisor_state(
    research: ResearchPageState,
    runtime: RuntimePageState,
    production_strategy: ProductionStrategyPageState,
    research_lifecycle: ResearchCandidateLifecyclePageState | None = None,
) -> SupervisorPageState:
    """Compare only contract/session semantic identities; no reads or effects."""
    if (
        research_lifecycle is not None
        and type(research_lifecycle) is not ResearchCandidateLifecyclePageState
    ):
        raise TypeError("Exact lifecycle state required")
    for value, kind in (
        (research, ResearchPageState),
        (runtime, RuntimePageState),
        (production_strategy, ProductionStrategyPageState),
    ):
        if type(value) is not kind:
            raise TypeError("Exact acquired GUI states required")
    consistency = SupervisorConsistency.NOT_CHECKED
    contract = production_strategy.contract
    session = runtime.session
    if contract is not None and session is not None:
        matches = (
            contract.contract_id == session.contract_id
            and contract.source_head == session.source_head
            and contract.source_tree == session.source_tree
            and contract.target_session_date == session.target_session
        )
        consistency = (
            SupervisorConsistency.CONSISTENT
            if matches
            else SupervisorConsistency.CONFLICTING
        )
    report_id = result_id = None
    if research.status is ResearchReportStatus.LOADED:
        report = research.report
        assert report is not None
        # The report adapter supplies canonical UUIDs. Do not propagate source
        # paths, report messages or arbitrary free-form identifiers here.
        try:
            report_id = UUID(report.report_id)
            result_id = UUID(report.experiment_result_id)
            if (
                str(report_id) != report.report_id
                or str(result_id) != report.experiment_result_id
            ):
                report_id = result_id = None
        except (ValueError, AttributeError):
            report_id = result_id = None
    if consistency is SupervisorConsistency.CONFLICTING:
        diagnostic = SupervisorDiagnostic.CONFLICTING
    elif (
        production_strategy.status is ProductionStrategyPageStatus.ATTENTION
        or runtime.status is RuntimePageStatus.ATTENTION
        or (
            research_lifecycle is not None
            and research_lifecycle.status
            is ResearchCandidateLifecyclePageStatus.ATTENTION
        )
    ):
        diagnostic = SupervisorDiagnostic.ATTENTION
    elif (
        contract is not None
        or runtime.status is RuntimePageStatus.AVAILABLE
        or report_id is not None
        or (research_lifecycle is not None and research_lifecycle.evidence is not None)
    ):
        diagnostic = SupervisorDiagnostic.RECORDED
    else:
        diagnostic = SupervisorDiagnostic.UNAVAILABLE
    status = {
        SupervisorDiagnostic.UNAVAILABLE: SupervisorPageStatus.UNAVAILABLE,
        SupervisorDiagnostic.RECORDED: SupervisorPageStatus.AVAILABLE,
        SupervisorDiagnostic.ATTENTION: SupervisorPageStatus.ATTENTION,
        SupervisorDiagnostic.CONFLICTING: SupervisorPageStatus.ATTENTION,
    }[diagnostic]
    return SupervisorPageState(
        status,
        diagnostic,
        consistency,
        production_strategy,
        runtime,
        report_id,
        result_id,
        research_lifecycle,
    )
