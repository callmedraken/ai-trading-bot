"""GUI-A9 pure System Health adapter tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from trading_bot.gui import (
    ApplicationOverview,
    MarketDataPageState,
    MarketDataPageStatus,
    OperatingMode,
    PaperAccountCheckpointKindView,
    PaperAccountPageState,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
    PresentationStatus,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
    SystemComponentStatus,
    SystemHealthStatus,
    VerifiedMarketSnapshotView,
    VerifiedPaperAccountView,
    build_system_health_state,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)
from trading_bot.gui.models import ComponentStatus
from trading_bot.gui.operator_observability_models import (
    OperatorAccountSummaryView,
    OperatorEffectGateState,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorStrategyPreview,
    OperatorStrategyPreviewStatus,
)

_UUID1 = UUID("11111111-1111-1111-1111-111111111111")
_UUID2 = UUID("22222222-2222-2222-2222-222222222222")
_UUID3 = UUID("33333333-3333-3333-3333-333333333333")
_UUID4 = UUID("44444444-4444-4444-4444-444444444444")
_UUID5 = UUID("55555555-5555-5555-5555-555555555555")
_UUID6 = UUID("66666666-6666-6666-6666-666666666666")
_NOW = datetime(2026, 9, 20, 20, 0, tzinfo=UTC)


def _overview() -> ApplicationOverview:
    return ApplicationOverview(
        OperatingMode.RESEARCH,
        "Local read-only GUI",
        "Read-only presentation.",
        (
            ComponentStatus(
                "research",
                "Research",
                PresentationStatus.INFO,
                "Research presentation.",
            ),
        ),
    )


def _research_loaded() -> ResearchPageState:
    row = ResearchResultRow(
        0,
        1,
        "Variant",
        "Parameter=1",
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        0,
        None,
        None,
    )
    return ResearchPageState(
        ResearchReportStatus.LOADED,
        "Loaded read-only.",
        ResearchReportView(
            str(_UUID1),
            str(_UUID2),
            "GRID",
            "Unranked",
            "No metadata",
            (row,),
            "F:\\private\\research.json",
        ),
    )


def _paper_blocked() -> PaperPageState:
    return PaperPageState(
        PaperPageStatus.INSPECTED,
        "Inspected.",
        PaperOperationInspectionView(
            PaperInspectionClassification.BLOCKED,
            _UUID1,
            _UUID2,
            _UUID3,
            PaperInspectionDiagnostic.INVALID_OPERATION_STATE,
            "F:\\private\\receipt.json",
        ),
    )


def _paper_account_verified() -> PaperAccountPageState:
    return PaperAccountPageState(
        PaperAccountPageStatus.VERIFIED,
        "Verified offline.",
        VerifiedPaperAccountView(
            PaperAccountCheckpointKindView.GENESIS,
            0,
            _UUID1,
            _UUID2,
            _UUID3,
            _UUID4,
            _NOW,
            Decimal("1000"),
            Decimal("0"),
            (
                PaperAccountPositionView(
                    "SPY",
                    Decimal("2"),
                    Decimal("20"),
                    Decimal("10"),
                ),
            ),
            "a" * 64,
            123,
        ),
    )


def _market_verified() -> MarketDataPageState:
    return MarketDataPageState(
        MarketDataPageStatus.VERIFIED,
        "Verified offline.",
        VerifiedMarketSnapshotView(
            _UUID5,
            date(2026, 9, 18),
            ("SPY",),
            "test-provider",
            "daily-bars",
            "test-feed",
            "b" * 64,
            456,
            _NOW,
            _NOW,
            "c" * 64,
            12,
            "application/json",
        ),
    )


def _operations(
    *,
    open_gate: bool = False,
    blocked_preview: bool = False,
) -> OperatorOperationsPageState:
    gates = OperatorEffectGateState(
        open_gate,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )
    account = OperatorAccountSummaryView(
        "paper-v2",
        _UUID6,
        0,
        _NOW,
        Decimal("1000"),
        Decimal("0"),
        (),
        0,
        0,
    )
    preview = OperatorStrategyPreview(
        OperatorStrategyPreviewStatus.BLOCKED
        if blocked_preview
        else OperatorStrategyPreviewStatus.UNAVAILABLE
    )
    return OperatorOperationsPageState(
        OperatorOperationsPageStatus.AVAILABLE,
        "Bounded observability.",
        gates=gates,
        account=account,
        strategy_preview=preview,
    )


def test_unavailable_sources_are_neutral_read_only_health() -> None:
    state = build_system_health_state(
        _overview(),
        ResearchPageState(
            ResearchReportStatus.UNAVAILABLE,
            "Unavailable.",
            None,
        ),
        unavailable_paper_state(),
        unavailable_paper_account_state(),
        unavailable_market_data_state(),
        unavailable_operator_operations_state(),
    )

    assert state.status is SystemHealthStatus.READ_ONLY_READY
    assert all(
        item.status is SystemComponentStatus.UNAVAILABLE for item in state.components
    )
    assert state.audit_entries == ()


def test_loaded_verified_sources_copy_only_bounded_audit_identity() -> None:
    state = build_system_health_state(
        _overview(),
        _research_loaded(),
        unavailable_paper_state(),
        _paper_account_verified(),
        _market_verified(),
        unavailable_operator_operations_state(),
    )

    assert state.status is SystemHealthStatus.READ_ONLY_READY
    assert tuple(item.status for item in state.components) == (
        SystemComponentStatus.AVAILABLE,
        SystemComponentStatus.UNAVAILABLE,
        SystemComponentStatus.AVAILABLE,
        SystemComponentStatus.AVAILABLE,
        SystemComponentStatus.UNAVAILABLE,
    )
    rendered = "\n".join(
        " | ".join(
            (
                entry.source,
                entry.evidence_kind,
                entry.identifier,
                entry.sha256 or "",
            )
        )
        for entry in state.audit_entries
    )
    assert str(_UUID1) in rendered
    assert str(_UUID2) in rendered
    assert str(_UUID5) in rendered
    assert "a" * 64 in rendered
    assert "b" * 64 in rendered
    assert "private" not in rendered.casefold()
    assert "receipt" not in rendered.casefold()


def test_blocked_paper_inspection_sets_attention_without_receipt_path() -> None:
    state = build_system_health_state(
        _overview(),
        ResearchPageState(ResearchReportStatus.UNAVAILABLE, "Unavailable.", None),
        _paper_blocked(),
        unavailable_paper_account_state(),
        unavailable_market_data_state(),
        unavailable_operator_operations_state(),
    )

    assert state.status is SystemHealthStatus.ATTENTION
    paper = next(item for item in state.components if item.key == "paper")
    assert paper.status is SystemComponentStatus.BLOCKED
    rendered = "\n".join(entry.identifier for entry in state.audit_entries)
    assert str(_UUID1) in rendered
    assert "private" not in rendered.casefold()
    assert "receipt" not in rendered.casefold()


def test_operations_open_gate_or_blocked_preview_sets_attention() -> None:
    for operations in (
        _operations(open_gate=True),
        _operations(blocked_preview=True),
    ):
        state = build_system_health_state(
            _overview(),
            ResearchPageState(
                ResearchReportStatus.UNAVAILABLE,
                "Unavailable.",
                None,
            ),
            unavailable_paper_state(),
            unavailable_paper_account_state(),
            unavailable_market_data_state(),
            operations,
        )

        assert state.status is SystemHealthStatus.ATTENTION
        component = next(item for item in state.components if item.key == "operations")
        assert component.status is SystemComponentStatus.BLOCKED
        assert any(
            entry.identifier == str(_UUID6) for entry in state.audit_entries
        )
