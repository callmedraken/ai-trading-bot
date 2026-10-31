"""Public, Qt-free presentation contracts for the desktop GUI."""

from importlib import import_module

from trading_bot.gui.evidence_explorer import (
    MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS,
    EvidenceTimelineFilter,
    filter_evidence_timeline_entries,
)
from trading_bot.gui.evidence_navigation import (
    EvidenceNavigationTarget,
    build_evidence_navigation_target,
)
from trading_bot.gui.evidence_source_navigation import (
    EvidenceSourcePage,
    EvidenceSourcePageTarget,
    build_evidence_source_page_target,
)
from trading_bot.gui.evidence_timeline_adapter import build_evidence_timeline_state
from trading_bot.gui.evidence_timeline_models import (
    MAX_EVIDENCE_TIMELINE_ENTRIES,
    MAX_EVIDENCE_TIMELINE_IDENTIFIER_CHARACTERS,
    MAX_EVIDENCE_TIMELINE_TEXT_CHARACTERS,
    EvidenceTimelineEntry,
    EvidenceTimelinePageState,
    EvidenceTimelineSource,
)
from trading_bot.gui.market_data_models import (
    MAX_MARKET_DATA_MESSAGE_CHARACTERS,
    MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS,
    MAX_MARKET_DATA_SYMBOL_CHARACTERS,
    MAX_MARKET_DATA_SYMBOLS,
    MarketDataPageState,
    MarketDataPageStatus,
    VerifiedMarketSnapshotView,
    unavailable_market_data_state,
)
from trading_bot.gui.models import (
    ApplicationOverview,
    ComponentStatus,
    OperatingMode,
    PresentationStatus,
    ResearchComparisonState,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
    format_decimal_for_display,
    format_percentage_for_display,
)
from trading_bot.gui.operator_observability_models import (
    MAX_OPERATOR_ACCOUNT_ID_CHARACTERS,
    MAX_OPERATOR_CLASSIFICATION_CHARACTERS,
    MAX_OPERATOR_MESSAGE_CHARACTERS,
    MAX_OPERATOR_POSITIONS,
    MAX_OPERATOR_SYMBOL_CHARACTERS,
    OPERATOR_WARMUP_TARGET_COUNT,
    OperatorAccountPositionView,
    OperatorAccountSummaryView,
    OperatorEffectGateState,
    OperatorObservabilityState,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorWarmupClassification,
    OperatorWarmupView,
    SelectedC3WarmupSessionView,
    unavailable_operator_operations_state,
)
from trading_bot.gui.paper_account_models import (
    MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS,
    MAX_PAPER_ACCOUNT_POSITIONS,
    MAX_PAPER_ACCOUNT_SYMBOL_CHARACTERS,
    PaperAccountCheckpointKindView,
    PaperAccountPageState,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    VerifiedPaperAccountView,
    unavailable_paper_account_state,
)
from trading_bot.gui.paper_models import (
    MAX_PAPER_RECEIPT_PATH_CHARACTERS,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
    unavailable_paper_state,
)
from trading_bot.gui.production_strategy_models import (
    MAX_PRODUCTION_STRATEGY_BYTES,
    ProductionStrategyContractView,
    ProductionStrategyDiagnostic,
    ProductionStrategyPageState,
    ProductionStrategyPageStatus,
    unavailable_production_strategy_state,
)
from trading_bot.gui.production_strategy_service import (
    ProductionStrategyContractInspectionService,
)
from trading_bot.gui.research_service import CompactReportResearchService
from trading_bot.gui.runtime_evidence_service import (
    ProductionRuntimeEvidenceInspectionService,
)
from trading_bot.gui.runtime_models import (
    MAX_RUNTIME_COUNT,
    MAX_RUNTIME_EVIDENCE_BYTES,
    MAX_RUNTIME_HISTORY,
    RuntimeAclEvidenceView,
    RuntimeAclStatus,
    RuntimeDiagnostic,
    RuntimePageState,
    RuntimePageStatus,
    RuntimePrepareResult,
    RuntimeProvisionStatus,
    RuntimeQualificationEvidenceView,
    RuntimeQualificationStatus,
    RuntimeResult,
    RuntimeSessionEvidenceView,
    RuntimeSessionStatus,
    RuntimeStrategyOutcome,
    RuntimeWriteReadiness,
    unavailable_runtime_state,
)
from trading_bot.gui.services import GuiApplicationService, ResearchReportLoader
from trading_bot.gui.supervisor_adapter import build_supervisor_state
from trading_bot.gui.supervisor_models import (
    SupervisorConsistency,
    SupervisorDiagnostic,
    SupervisorPageState,
    SupervisorPageStatus,
)
from trading_bot.gui.system_health_adapter import build_system_health_state
from trading_bot.gui.system_health_models import (
    MAX_SYSTEM_AUDIT_ENTRIES,
    MAX_SYSTEM_COMPONENTS,
    MAX_SYSTEM_IDENTIFIER_CHARACTERS,
    MAX_SYSTEM_TEXT_CHARACTERS,
    SystemAuditEntryView,
    SystemComponentHealthView,
    SystemComponentStatus,
    SystemHealthPageState,
    SystemHealthStatus,
)

_LAZY_EXPORTS = {
    "PaperOperationInspectionService": "trading_bot.gui.paper_inspection_service",
    "GuiStartupConfiguration": "trading_bot.gui.startup_composition",
    "ReadOnlyGuiApplicationService": "trading_bot.gui.startup_composition",
    "VerifiedGenesisPaperAccountInspectionService": (
        "trading_bot.gui.verified_genesis_paper_account_inspection_service"
    ),
    "VerifiedSnapshotInspectionService": (
        "trading_bot.gui.verified_snapshot_inspection_service"
    ),
    "VerifiedSuccessorPaperAccountInspectionService": (
        "trading_bot.gui.verified_successor_paper_account_inspection_service"
    ),
}

__all__ = [
    "MAX_PRODUCTION_STRATEGY_BYTES",
    "ProductionStrategyContractView",
    "ProductionStrategyDiagnostic",
    "ProductionStrategyPageState",
    "ProductionStrategyPageStatus",
    "unavailable_production_strategy_state",
    "ProductionStrategyContractInspectionService",
    "build_supervisor_state",
    "SupervisorConsistency",
    "SupervisorDiagnostic",
    "SupervisorPageState",
    "SupervisorPageStatus",
    "ProductionRuntimeEvidenceInspectionService",
    "MAX_RUNTIME_EVIDENCE_BYTES",
    "MAX_RUNTIME_COUNT",
    "MAX_RUNTIME_HISTORY",
    "RuntimeAclEvidenceView",
    "RuntimeAclStatus",
    "RuntimeDiagnostic",
    "RuntimePageState",
    "RuntimePageStatus",
    "RuntimePrepareResult",
    "RuntimeProvisionStatus",
    "RuntimeQualificationEvidenceView",
    "RuntimeQualificationStatus",
    "RuntimeResult",
    "RuntimeSessionEvidenceView",
    "RuntimeSessionStatus",
    "RuntimeStrategyOutcome",
    "RuntimeWriteReadiness",
    "unavailable_runtime_state",
    "ApplicationOverview",
    "ComponentStatus",
    "CompactReportResearchService",
    "EvidenceNavigationTarget",
    "EvidenceSourcePage",
    "EvidenceSourcePageTarget",
    "EvidenceTimelineEntry",
    "EvidenceTimelineFilter",
    "EvidenceTimelinePageState",
    "EvidenceTimelineSource",
    "GuiApplicationService",
    "GuiStartupConfiguration",
    "MAX_EVIDENCE_TIMELINE_ENTRIES",
    "MAX_EVIDENCE_TIMELINE_FILTER_CHARACTERS",
    "MAX_EVIDENCE_TIMELINE_IDENTIFIER_CHARACTERS",
    "MAX_EVIDENCE_TIMELINE_TEXT_CHARACTERS",
    "MAX_MARKET_DATA_MESSAGE_CHARACTERS",
    "MAX_MARKET_DATA_PRESENTATION_TEXT_CHARACTERS",
    "MAX_MARKET_DATA_SYMBOL_CHARACTERS",
    "MAX_MARKET_DATA_SYMBOLS",
    "MAX_PAPER_ACCOUNT_MESSAGE_CHARACTERS",
    "MAX_PAPER_ACCOUNT_POSITIONS",
    "MAX_PAPER_ACCOUNT_SYMBOL_CHARACTERS",
    "MAX_OPERATOR_ACCOUNT_ID_CHARACTERS",
    "MAX_OPERATOR_CLASSIFICATION_CHARACTERS",
    "MAX_OPERATOR_MESSAGE_CHARACTERS",
    "MAX_OPERATOR_POSITIONS",
    "MAX_OPERATOR_SYMBOL_CHARACTERS",
    "OPERATOR_WARMUP_TARGET_COUNT",
    "MAX_PAPER_RECEIPT_PATH_CHARACTERS",
    "MAX_SYSTEM_AUDIT_ENTRIES",
    "MAX_SYSTEM_COMPONENTS",
    "MAX_SYSTEM_IDENTIFIER_CHARACTERS",
    "MAX_SYSTEM_TEXT_CHARACTERS",
    "MarketDataPageState",
    "MarketDataPageStatus",
    "OperatingMode",
    "OperatorAccountPositionView",
    "OperatorAccountSummaryView",
    "OperatorEffectGateState",
    "OperatorObservabilityState",
    "OperatorOperationsPageState",
    "OperatorOperationsPageStatus",
    "OperatorWarmupClassification",
    "OperatorWarmupView",
    "SelectedC3WarmupSessionView",
    "PaperAccountCheckpointKindView",
    "PaperAccountPageState",
    "PaperAccountPageStatus",
    "PaperAccountPositionView",
    "PaperInspectionClassification",
    "PaperInspectionDiagnostic",
    "PaperOperationInspectionView",
    "PaperOperationInspectionService",
    "PaperPageState",
    "PaperPageStatus",
    "PresentationStatus",
    "ResearchComparisonState",
    "ResearchPageState",
    "ResearchReportStatus",
    "ResearchReportView",
    "ResearchResultRow",
    "ResearchReportLoader",
    "SystemAuditEntryView",
    "SystemComponentHealthView",
    "SystemComponentStatus",
    "SystemHealthPageState",
    "SystemHealthStatus",
    "ReadOnlyGuiApplicationService",
    "VerifiedMarketSnapshotView",
    "VerifiedPaperAccountView",
    "VerifiedGenesisPaperAccountInspectionService",
    "VerifiedSnapshotInspectionService",
    "VerifiedSuccessorPaperAccountInspectionService",
    "build_evidence_navigation_target",
    "build_evidence_source_page_target",
    "build_evidence_timeline_state",
    "filter_evidence_timeline_entries",
    "build_system_health_state",
    "format_decimal_for_display",
    "format_percentage_for_display",
    "unavailable_market_data_state",
    "unavailable_operator_operations_state",
    "unavailable_paper_account_state",
    "unavailable_paper_state",
]


def __getattr__(name: str) -> object:
    """Load unchanged historical adapters only when explicitly requested."""
    owner = _LAZY_EXPORTS.get(name)
    if owner is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(owner), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
