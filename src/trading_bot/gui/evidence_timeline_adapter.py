"""Pure GUI-A10 adaptation from already-acquired presentation state."""

from __future__ import annotations

from trading_bot.gui.evidence_timeline_models import (
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
)
from trading_bot.gui.market_data_models import (
    MarketDataPageState,
    MarketDataPageStatus,
)
from trading_bot.gui.models import ResearchPageState, ResearchReportStatus
from trading_bot.gui.operator_observability_models import (
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
)
from trading_bot.gui.paper_account_models import (
    PaperAccountPageState,
    PaperAccountPageStatus,
)
from trading_bot.gui.paper_models import PaperPageState, PaperPageStatus
from trading_bot.gui.runtime_models import RuntimePageState
from trading_bot.gui.supervisor_models import SupervisorPageState


def build_evidence_timeline_state(
    research: ResearchPageState,
    paper: PaperPageState,
    paper_account: PaperAccountPageState,
    market_data: MarketDataPageState,
    operations: OperatorOperationsPageState,
    runtime: RuntimePageState,
    supervisor: SupervisorPageState | None = None,
) -> EvidenceTimelinePageState:
    """Build a deterministic timeline without I/O, discovery, or service rereads."""
    expected = (
        (research, ResearchPageState, "research"),
        (paper, PaperPageState, "paper"),
        (paper_account, PaperAccountPageState, "paper_account"),
        (market_data, MarketDataPageState, "market_data"),
        (operations, OperatorOperationsPageState, "operations"),
        (runtime, RuntimePageState, "runtime"),
    )
    for value, expected_type, name in expected:
        if type(value) is not expected_type:
            raise TypeError(f"{name} has an unsupported type")
    if supervisor is not None and type(supervisor) is not SupervisorPageState:
        raise TypeError("Exact SupervisorPageState required")

    entries = (
        *_research_entries(research),
        *_paper_entries(paper),
        *_paper_account_entries(paper_account),
        *_market_data_entries(market_data),
        *_operations_entries(operations),
        *_runtime_entries(runtime),
        *(_supervisor_entries(supervisor) if supervisor is not None else ()),
    )
    timed = [entry for entry in entries if entry.occurred_at is not None]
    untimed = [entry for entry in entries if entry.occurred_at is None]
    timed.sort(key=lambda entry: entry.occurred_at, reverse=True)
    ordered = tuple((*timed, *untimed))

    if not ordered:
        message = (
            "No loaded, verified, or inspected evidence is represented in this "
            "read-only GUI."
        )
    else:
        message = (
            f"{len(ordered)} bounded evidence entr"
            f"{'y' if len(ordered) == 1 else 'ies'} derived from already-acquired "
            "read-only GUI state."
        )
    return EvidenceTimelinePageState(message, ordered)


def _supervisor_entries(
    state: SupervisorPageState,
) -> tuple[EvidenceTimelineEntry, ...]:
    contract = state.production_strategy.contract
    if contract is None:
        return ()
    return (
        EvidenceTimelineEntry(
            EvidenceTimelineSource.SUPERVISOR,
            "Production strategy contract",
            str(contract.contract_id),
            None,
            None,
            f"Target session: {contract.target_session_date.isoformat()}; "
            f"strategy: {contract.strategy_id}/{contract.strategy_version}; "
            f"symbol: {contract.symbol}; HEAD: {contract.source_head}; "
            f"TREE: {contract.source_tree}.",
        ),
    )


def _research_entries(
    state: ResearchPageState,
) -> tuple[EvidenceTimelineEntry, ...]:
    if state.status is not ResearchReportStatus.LOADED or state.report is None:
        return ()
    report = state.report
    detail = (
        f"Loaded compact report with {report.row_count} rows; "
        "no report timestamp is exposed by the GUI model."
    )
    return (
        EvidenceTimelineEntry(
            EvidenceTimelineSource.RESEARCH,
            "Research report",
            report.report_id,
            None,
            None,
            detail,
        ),
        EvidenceTimelineEntry(
            EvidenceTimelineSource.RESEARCH,
            "Experiment result",
            report.experiment_result_id,
            None,
            None,
            "Experiment result identity from the loaded compact report.",
        ),
    )


def _paper_entries(state: PaperPageState) -> tuple[EvidenceTimelineEntry, ...]:
    if state.status is not PaperPageStatus.INSPECTED or state.inspection is None:
        return ()
    inspection = state.inspection
    detail = (
        f"Classification: {inspection.classification.value}; "
        f"diagnostic: {inspection.diagnostic.value}; no timestamp is exposed."
    )
    return (
        EvidenceTimelineEntry(
            EvidenceTimelineSource.PAPER_OPERATION,
            "Operation",
            str(inspection.operation_id),
            None,
            None,
            detail,
        ),
        EvidenceTimelineEntry(
            EvidenceTimelineSource.PAPER_OPERATION,
            "Terminal checkpoint",
            str(inspection.terminal_checkpoint_id),
            None,
            None,
            detail,
        ),
        EvidenceTimelineEntry(
            EvidenceTimelineSource.PAPER_OPERATION,
            "Application",
            str(inspection.application_id),
            None,
            None,
            detail,
        ),
    )


def _paper_account_entries(
    state: PaperAccountPageState,
) -> tuple[EvidenceTimelineEntry, ...]:
    if state.status is not PaperAccountPageStatus.VERIFIED or state.account is None:
        return ()
    account = state.account
    return (
        EvidenceTimelineEntry(
            EvidenceTimelineSource.PAPER_ACCOUNT,
            "Verified checkpoint",
            str(account.checkpoint_id),
            account.as_of,
            account.artifact_sha256,
            (
                f"{account.checkpoint_kind.value} checkpoint; sequence "
                f"{account.sequence}; offline-verified artifact."
            ),
        ),
    )


def _market_data_entries(
    state: MarketDataPageState,
) -> tuple[EvidenceTimelineEntry, ...]:
    if state.status is not MarketDataPageStatus.VERIFIED or state.snapshot is None:
        return ()
    snapshot = state.snapshot
    return (
        EvidenceTimelineEntry(
            EvidenceTimelineSource.MARKET_DATA,
            "Verified market-data snapshot",
            str(snapshot.snapshot_id),
            snapshot.captured_at,
            snapshot.artifact_sha256,
            (
                "Offline-verified snapshot targeting XNYS session "
                f"{snapshot.target_session_date.isoformat()}."
            ),
        ),
    )


def _operations_entries(
    state: OperatorOperationsPageState,
) -> tuple[EvidenceTimelineEntry, ...]:
    if state.status is not OperatorOperationsPageStatus.AVAILABLE:
        return ()
    entries: list[EvidenceTimelineEntry] = []
    if state.selected_snapshot_id is not None:
        detail = "Selected snapshot identity from bounded Operations presentation."
        if state.completed_session is not None:
            detail = (
                f"{detail} Completed session: {state.completed_session.isoformat()}."
            )
        entries.append(
            EvidenceTimelineEntry(
                EvidenceTimelineSource.OPERATIONS,
                "Selected snapshot",
                str(state.selected_snapshot_id),
                None,
                None,
                detail,
            )
        )
    if state.account is not None:
        entries.append(
            EvidenceTimelineEntry(
                EvidenceTimelineSource.OPERATIONS,
                "Displayed account checkpoint",
                str(state.account.checkpoint_id),
                state.account.as_of,
                None,
                (
                    f"Paper account {state.account.paper_account_id}; sequence "
                    f"{state.account.sequence}; bounded Operations presentation."
                ),
            )
        )
    return tuple(entries)


def _runtime_entries(state: RuntimePageState) -> tuple[EvidenceTimelineEntry, ...]:
    entries: list[EvidenceTimelineEntry] = []
    if state.acl is not None:
        acl = state.acl
        entries.append(
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RUNTIME,
                "Runtime ACL evidence",
                acl.runtime_sid_digest or "production-paper-runtime-acl/v1",
                None,
                None,
                f"Recorded {acl.status.value} / {acl.result.value}. {state.message}",
            )
        )
    if state.qualification is not None:
        qualification = state.qualification
        entries.append(
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RUNTIME,
                "Runtime qualification evidence",
                qualification.source_head,
                None,
                None,
                f"Recorded {qualification.status.value}; "
                f"TREE {qualification.source_tree}. "
                f"Not fresh production authority. {state.message}",
            )
        )
    if state.session is not None:
        session = state.session
        entries.append(
            EvidenceTimelineEntry(
                EvidenceTimelineSource.RUNTIME,
                "D1 session evidence",
                str(session.operation_id),
                session.admitted_at or session.wait_started_at,
                None,
                f"Recorded {session.status.value}; "
                f"target {session.target_session.isoformat()}; "
                f"HEAD {session.source_head}; TREE {session.source_tree}; "
                f"contract {session.contract_id}. {state.message}",
            )
        )
    return tuple(entries)
