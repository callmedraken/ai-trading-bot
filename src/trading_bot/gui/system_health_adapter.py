"""Pure GUI-A9 adaptation from already-acquired presentation state."""

from __future__ import annotations

from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    MarketDataPageStatus,
)
from trading_bot.gui.models import (
    ApplicationOverview,
    OperatingMode,
    ResearchPageState,
    ResearchReportStatus,
)
from trading_bot.gui.operator_observability_models import (
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorStrategyPreviewStatus,
)
from trading_bot.gui.paper_account_models import (
    PaperAccountPageState,
    PaperAccountPageStatus,
)
from trading_bot.gui.paper_models import (
    PaperInspectionClassification,
    PaperPageState,
    PaperPageStatus,
)
from trading_bot.gui.system_health_models import (
    SystemAuditEntryView,
    SystemComponentHealthView,
    SystemComponentStatus,
    SystemHealthPageState,
    SystemHealthStatus,
)

_MODE_LABELS = {
    OperatingMode.RESEARCH: "Research",
    OperatingMode.SIMULATED_PAPER: "Simulated Paper",
    OperatingMode.BROKER_PAPER: "Broker Paper",
    OperatingMode.LIVE: "Live",
}


def build_system_health_state(
    overview: ApplicationOverview,
    research: ResearchPageState,
    paper: PaperPageState,
    paper_account: PaperAccountPageState,
    market_data: MarketDataPageState,
    operations: OperatorOperationsPageState,
) -> SystemHealthPageState:
    """Build diagnostics without any service reread, I/O, or authority access."""
    expected = (
        (overview, ApplicationOverview, "overview"),
        (research, ResearchPageState, "research"),
        (paper, PaperPageState, "paper"),
        (paper_account, PaperAccountPageState, "paper_account"),
        (market_data, MarketDataPageState, "market_data"),
        (operations, OperatorOperationsPageState, "operations"),
    )
    for value, expected_type, name in expected:
        if type(value) is not expected_type:
            raise TypeError(f"{name} has an unsupported type")

    components = (
        _research_component(research),
        _paper_component(paper),
        _paper_account_component(paper_account),
        _market_data_component(market_data),
        _operations_component(operations),
    )
    audit_entries = (
        *_research_audit(research),
        *_paper_audit(paper),
        *_paper_account_audit(paper_account),
        *_market_data_audit(market_data),
        *_operations_audit(operations),
    )
    status = (
        SystemHealthStatus.ATTENTION
        if any(item.status is SystemComponentStatus.BLOCKED for item in components)
        else SystemHealthStatus.READ_ONLY_READY
    )
    message = {
        SystemHealthStatus.READ_ONLY_READY: (
            "Local read-only presentation has no explicit blocked component; "
            "this is not production or trading readiness."
        ),
        SystemHealthStatus.ATTENTION: (
            "One or more presented components requires attention; no action is "
            "authorized by this page."
        ),
    }[status]
    return SystemHealthPageState(
        status=status,
        message=message,
        environment=overview.environment,
        displayed_mode=_MODE_LABELS[overview.mode],
        components=components,
        audit_entries=audit_entries,
    )


def _research_component(state: ResearchPageState) -> SystemComponentHealthView:
    if state.status is ResearchReportStatus.LOADED:
        return SystemComponentHealthView(
            "research",
            "Research",
            SystemComponentStatus.AVAILABLE,
            "One explicit historical report is loaded read-only.",
        )
    return SystemComponentHealthView(
        "research",
        "Research",
        SystemComponentStatus.UNAVAILABLE,
        "No historical report is currently loaded.",
    )


def _paper_component(state: PaperPageState) -> SystemComponentHealthView:
    if state.status is PaperPageStatus.UNAVAILABLE:
        return SystemComponentHealthView(
            "paper",
            "Paper Operation",
            SystemComponentStatus.UNAVAILABLE,
            "No paper-operation inspection is connected.",
        )
    inspection = state.inspection
    assert inspection is not None
    blocked = inspection.classification in (
        PaperInspectionClassification.BLOCKED,
        PaperInspectionClassification.CONFLICTING,
    )
    return SystemComponentHealthView(
        "paper",
        "Paper Operation",
        (
            SystemComponentStatus.BLOCKED
            if blocked
            else SystemComponentStatus.AVAILABLE
        ),
        (
            f"Inspection classification: {inspection.classification.value}; "
            f"diagnostic: {inspection.diagnostic.value}."
        ),
    )


def _paper_account_component(
    state: PaperAccountPageState,
) -> SystemComponentHealthView:
    if state.status is PaperAccountPageStatus.VERIFIED:
        account = state.account
        assert account is not None
        return SystemComponentHealthView(
            "paper-account",
            "Paper Account",
            SystemComponentStatus.AVAILABLE,
            (
                f"Offline-verified {account.checkpoint_kind.value} checkpoint; "
                f"sequence {account.sequence}."
            ),
        )
    return SystemComponentHealthView(
        "paper-account",
        "Paper Account",
        SystemComponentStatus.UNAVAILABLE,
        "No verified paper-account checkpoint is connected.",
    )


def _market_data_component(state: MarketDataPageState) -> SystemComponentHealthView:
    if state.status is MarketDataPageStatus.VERIFIED:
        snapshot = state.snapshot
        assert snapshot is not None
        return SystemComponentHealthView(
            "market-data",
            "Market Data",
            SystemComponentStatus.AVAILABLE,
            (
                "Offline-verified snapshot for XNYS session "
                f"{snapshot.target_session_date.isoformat()}."
            ),
        )
    return SystemComponentHealthView(
        "market-data",
        "Market Data",
        SystemComponentStatus.UNAVAILABLE,
        "No verified market-data snapshot is connected.",
    )


def _operations_component(
    state: OperatorOperationsPageState,
) -> SystemComponentHealthView:
    if state.status is OperatorOperationsPageStatus.UNAVAILABLE:
        return SystemComponentHealthView(
            "operations",
            "Operations",
            SystemComponentStatus.UNAVAILABLE,
            "Production operator observability is not connected.",
        )
    gates_blocked = state.gates is not None and not state.gates.all_closed
    preview_blocked = (
        state.strategy_preview.status is OperatorStrategyPreviewStatus.BLOCKED
    )
    blocked = gates_blocked or preview_blocked
    return SystemComponentHealthView(
        "operations",
        "Operations",
        (
            SystemComponentStatus.BLOCKED
            if blocked
            else SystemComponentStatus.AVAILABLE
        ),
        (
            "Displayed production observability contains an open effect gate or "
            "blocked strategy preview."
            if blocked
            else "Bounded production observability presentation is available."
        ),
    )


def _research_audit(state: ResearchPageState) -> tuple[SystemAuditEntryView, ...]:
    if state.status is not ResearchReportStatus.LOADED or state.report is None:
        return ()
    return (
        SystemAuditEntryView("Research", "Report ID", state.report.report_id),
        SystemAuditEntryView(
            "Research",
            "Experiment result ID",
            state.report.experiment_result_id,
        ),
    )


def _paper_audit(state: PaperPageState) -> tuple[SystemAuditEntryView, ...]:
    if state.status is not PaperPageStatus.INSPECTED or state.inspection is None:
        return ()
    inspection = state.inspection
    return (
        SystemAuditEntryView(
            "Paper Operation",
            "Operation ID",
            str(inspection.operation_id),
        ),
        SystemAuditEntryView(
            "Paper Operation",
            "Terminal checkpoint ID",
            str(inspection.terminal_checkpoint_id),
        ),
        SystemAuditEntryView(
            "Paper Operation",
            "Application ID",
            str(inspection.application_id),
        ),
    )


def _paper_account_audit(
    state: PaperAccountPageState,
) -> tuple[SystemAuditEntryView, ...]:
    if state.status is not PaperAccountPageStatus.VERIFIED or state.account is None:
        return ()
    return (
        SystemAuditEntryView(
            "Paper Account",
            "Checkpoint ID",
            str(state.account.checkpoint_id),
            state.account.artifact_sha256,
        ),
    )


def _market_data_audit(
    state: MarketDataPageState,
) -> tuple[SystemAuditEntryView, ...]:
    if state.status is not MarketDataPageStatus.VERIFIED or state.snapshot is None:
        return ()
    return (
        SystemAuditEntryView(
            "Market Data",
            "Snapshot ID",
            str(state.snapshot.snapshot_id),
            state.snapshot.artifact_sha256,
        ),
    )


def _operations_audit(
    state: OperatorOperationsPageState,
) -> tuple[SystemAuditEntryView, ...]:
    if state.status is not OperatorOperationsPageStatus.AVAILABLE:
        return ()
    entries: list[SystemAuditEntryView] = []
    if state.selected_snapshot_id is not None:
        entries.append(
            SystemAuditEntryView(
                "Operations",
                "Selected snapshot ID",
                str(state.selected_snapshot_id),
            )
        )
    if state.account is not None:
        entries.append(
            SystemAuditEntryView(
                "Operations",
                "Account checkpoint ID",
                str(state.account.checkpoint_id),
            )
        )
    return tuple(entries)
