"""GUI-A10 pure Evidence Timeline adapter tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from trading_bot.gui import (
    EvidenceTimelineSource,
    MarketDataPageState,
    MarketDataPageStatus,
    OperatorAccountSummaryView,
    OperatorEffectGateState,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorStrategyPreview,
    OperatorWarmupClassification,
    OperatorWarmupView,
    PaperAccountCheckpointKindView,
    PaperAccountPageState,
    PaperAccountPageStatus,
    PaperAccountPositionView,
    PaperInspectionClassification,
    PaperInspectionDiagnostic,
    PaperOperationInspectionView,
    PaperPageState,
    PaperPageStatus,
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
    SelectedC3WarmupSessionView,
    VerifiedMarketSnapshotView,
    VerifiedPaperAccountView,
    build_evidence_timeline_state,
    unavailable_market_data_state,
    unavailable_operator_operations_state,
    unavailable_paper_account_state,
    unavailable_paper_state,
)

_UUID1 = UUID("11111111-1111-1111-1111-111111111111")
_UUID2 = UUID("22222222-2222-2222-2222-222222222222")
_UUID3 = UUID("33333333-3333-3333-3333-333333333333")
_UUID4 = UUID("44444444-4444-4444-4444-444444444444")
_UUID5 = UUID("55555555-5555-5555-5555-555555555555")
_UUID6 = UUID("66666666-6666-6666-6666-666666666666")
_UUID7 = UUID("77777777-7777-7777-7777-777777777777")
_MARKET_TIME = datetime(2026, 9, 20, 22, 0, tzinfo=UTC)
_ACCOUNT_TIME = datetime(2026, 9, 19, 22, 0, tzinfo=UTC)
_OPERATIONS_TIME = datetime(2026, 9, 18, 22, 0, tzinfo=UTC)


def _research() -> ResearchPageState:
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
        "Loaded.",
        ResearchReportView(
            str(_UUID1),
            str(_UUID2),
            "GRID",
            "Unranked",
            "No metadata",
            (row,),
            "F:\\private\\research-report.json",
        ),
    )


def _paper() -> PaperPageState:
    return PaperPageState(
        PaperPageStatus.INSPECTED,
        "Inspected.",
        PaperOperationInspectionView(
            PaperInspectionClassification.PENDING,
            _UUID3,
            _UUID4,
            _UUID5,
            PaperInspectionDiagnostic.PENDING,
            "F:\\private\\receipt.json",
        ),
    )


def _paper_account() -> PaperAccountPageState:
    return PaperAccountPageState(
        PaperAccountPageStatus.VERIFIED,
        "Verified.",
        VerifiedPaperAccountView(
            PaperAccountCheckpointKindView.GENESIS,
            0,
            _UUID6,
            _UUID1,
            _UUID2,
            _UUID3,
            _ACCOUNT_TIME,
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


def _market_data() -> MarketDataPageState:
    return MarketDataPageState(
        MarketDataPageStatus.VERIFIED,
        "Verified.",
        VerifiedMarketSnapshotView(
            _UUID7,
            date(2026, 9, 20),
            ("SPY",),
            "test-provider",
            "daily-bars",
            "test-feed",
            "b" * 64,
            456,
            _MARKET_TIME,
            _MARKET_TIME - timedelta(minutes=1),
            "c" * 64,
            12,
            "application/json",
        ),
    )


def _operations() -> OperatorOperationsPageState:
    required = tuple(date(2026, 9, 10) + timedelta(days=index) for index in range(6))
    selected = SelectedC3WarmupSessionView(
        required[0],
        "SPY",
        Decimal("100"),
        _UUID7,
        _UUID5,
    )
    warmup = OperatorWarmupView(
        OperatorWarmupClassification.WARMING_UP,
        required,
        (selected,),
    )
    gates = OperatorEffectGateState(
        False,
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
        _UUID4,
        1,
        _OPERATIONS_TIME,
        Decimal("900"),
        Decimal("10"),
        (),
        1,
        1,
    )
    return OperatorOperationsPageState(
        OperatorOperationsPageStatus.AVAILABLE,
        "Available.",
        completed_session=date(2026, 9, 20),
        selected_snapshot_id=_UUID7,
        warmup=warmup,
        gates=gates,
        account=account,
        strategy_preview=OperatorStrategyPreview(),
    )


def test_unavailable_states_produce_truthful_empty_timeline() -> None:
    state = build_evidence_timeline_state(
        ResearchPageState(ResearchReportStatus.UNAVAILABLE, "Unavailable.", None),
        unavailable_paper_state(),
        unavailable_paper_account_state(),
        unavailable_market_data_state(),
        unavailable_operator_operations_state(),
    )

    assert state.entries == ()
    assert "No loaded" in state.message


def test_timeline_orders_timed_newest_first_then_stable_untimed_evidence() -> None:
    state = build_evidence_timeline_state(
        _research(),
        _paper(),
        _paper_account(),
        _market_data(),
        _operations(),
    )

    assert tuple(entry.identifier for entry in state.entries[:3]) == (
        str(_UUID7),
        str(_UUID6),
        str(_UUID4),
    )
    assert tuple(entry.occurred_at for entry in state.entries[:3]) == (
        _MARKET_TIME,
        _ACCOUNT_TIME,
        _OPERATIONS_TIME,
    )

    untimed = state.entries[3:]
    assert tuple(entry.source for entry in untimed) == (
        EvidenceTimelineSource.RESEARCH,
        EvidenceTimelineSource.RESEARCH,
        EvidenceTimelineSource.PAPER_OPERATION,
        EvidenceTimelineSource.PAPER_OPERATION,
        EvidenceTimelineSource.PAPER_OPERATION,
        EvidenceTimelineSource.OPERATIONS,
    )
    assert tuple(entry.identifier for entry in untimed) == (
        str(_UUID1),
        str(_UUID2),
        str(_UUID3),
        str(_UUID4),
        str(_UUID5),
        str(_UUID7),
    )


def test_timeline_excludes_paths_and_copies_only_bounded_identity_and_hashes() -> None:
    state = build_evidence_timeline_state(
        _research(),
        _paper(),
        _paper_account(),
        _market_data(),
        _operations(),
    )

    rendered = "\n".join(
        " | ".join(
            (
                entry.source.value,
                entry.title,
                entry.identifier,
                entry.sha256 or "",
                entry.detail,
            )
        )
        for entry in state.entries
    )
    assert str(_UUID1) in rendered
    assert str(_UUID7) in rendered
    assert "a" * 64 in rendered
    assert "b" * 64 in rendered
    assert "private" not in rendered.casefold()
    assert "receipt.json" not in rendered.casefold()
    assert "research-report.json" not in rendered.casefold()
