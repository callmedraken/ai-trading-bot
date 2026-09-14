"""Read-only reconstruction of the frozen Architecture-106 plan artifact."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.portfolio import PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    verified_prior_from_full_lineage,
)
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    WindowsSelectedC3SnapshotReadAuthority,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyPlanRequest,
    build_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.paper_account_lineage_verification import (
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    verify_paper_account_lineage,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    prepare_personal_desktop_paper_account_bundle,
)
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    require_production_paper_publication_freeze,
)
from trading_bot.runtime.strategy_history_seed import (
    VerifiedStrategyHistorySeed,
    verify_strategy_history_seed,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    CallerAssertedNextSessionOpenReference,
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

_PROFILE = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
_MACHINE_AUTHORITY_ID = "223f0d4e-36f9-4b9b-bf0e-febf16fcd3f1"
_AUTHORITY_EPOCH_ID = "e6f3de5d-1412-40ad-a022-8b33e72a5f6d"
_SELECTION_ID = UUID("36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280")
_SELECTED_SHA256 = "31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d"
_SELECTED_BYTE_LENGTH = 1291
_SEED_ID = UUID("5dc95e10-ba22-5b91-94b2-0d851aa8e2d7")
_SEED_SHA256 = "40dda54c82324f358d640cce89e467295b8f5b73a32fed76c52e7ca90d398e64"
_SEED_BYTE_LENGTH = 1060
_GENESIS_SHA256 = "d1a7ff14425c8a797a952860a1102489a4c81cac2a24a45bc3127eb8eb2e9548"
_GENESIS_BYTE_LENGTH = 533
_GENESIS_AS_OF = datetime(2026, 8, 29, 9, 46, 43, 769105, tzinfo=UTC)
_TARGET_SESSION = TradingSession(date(2026, 8, 28))
_OPEN_SESSION = TradingSession(date(2026, 8, 31))
_SYMBOL = Symbol("SPY")


class PersonalDesktopFirstPaperConfigurationError(ValueError):
    """The frozen first Paper-v2 configuration cannot be reconstructed exactly."""


def read_personal_desktop_first_paper_cycle_configuration(
    authority: ValidatedProductionAuthority,
) -> bytes:
    """Reconstruct and replay the exact reviewed 6199-byte first plan artifact."""

    c1 = require_validated_production_authority(authority)
    if (
        c1.machine_authority_id != _MACHINE_AUTHORITY_ID
        or c1.authority_epoch_id != _AUTHORITY_EPOCH_ID
        or c1.approved_account_sid != _PROFILE.approved_trading_sid
    ):
        raise PersonalDesktopFirstPaperConfigurationError(
            "production authority differs from the frozen first operation"
        )
    _require_publication_freeze()
    calendar = BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar())
    history = _load_history_seed(calendar)
    selected = WindowsSelectedC3SnapshotReadAuthority(c1).read_selected_snapshot(
        str(_SELECTION_ID)
    )
    require_selected_c3_snapshot_matches_authority(selected.permit, selected.audit, c1)
    _require_selected(selected)

    bundle = prepare_personal_desktop_paper_account_bundle(
        authority=c1,
        selected_snapshot=selected,
        starting_cash=Decimal("25000"),
    )
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    genesis_verification = verify_genesis_paper_account_checkpoint(
        bundle.genesis_bytes,
        expected_checkpoint_sha256=_GENESIS_SHA256,
        expected_checkpoint_byte_length=_GENESIS_BYTE_LENGTH,
    )
    checkpoint = genesis_verification.checkpoint
    if (
        genesis_verification.status is not PaperAccountCheckpointVerificationStatus.PASS
        or genesis_verification.diagnostics
        or checkpoint is None
        or checkpoint.checkpoint_id != _PROFILE.terminal_checkpoint_id
        or checkpoint.account_state.as_of != _GENESIS_AS_OF
        or checkpoint.account_state.cash != Decimal("25000")
        or checkpoint.account_state.positions
        or checkpoint.account_state.realized_profit_loss != 0
        or checkpoint.metadata
        or anchor.paper_account_id != _PROFILE.paper_account_id
        or anchor.machine_authority_id != _MACHINE_AUTHORITY_ID
        or anchor.approved_trading_sid != _PROFILE.approved_trading_sid
        or anchor.genesis_checkpoint_id != str(_PROFILE.terminal_checkpoint_id)
        or sha256(bundle.genesis_bytes).hexdigest() != _GENESIS_SHA256
        or len(bundle.genesis_bytes) != _GENESIS_BYTE_LENGTH
    ):
        raise PersonalDesktopFirstPaperConfigurationError(
            "reconstructed GENESIS differs from the frozen first operation"
        )
    genesis = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        _PROFILE.terminal_checkpoint_id,
        bundle.genesis_bytes,
        _GENESIS_SHA256,
        _GENESIS_BYTE_LENGTH,
    )
    lineage = verify_paper_account_lineage(
        genesis,
        _PROFILE.terminal_checkpoint_id,
        (),
        (),
        (),
        calendar,
    )
    if (
        lineage.status is not PaperAccountLineageVerificationStatus.PASS
        or lineage.diagnostics
        or lineage.evidence is None
        or lineage.evidence.edge_count != 0
        or lineage.evidence.checkpoint_ids != (_PROFILE.terminal_checkpoint_id,)
    ):
        raise PersonalDesktopFirstPaperConfigurationError(
            "reconstructed first-operation prior lineage is invalid"
        )
    prior = verified_prior_from_full_lineage(lineage)
    audit = selected.audit
    assertion = ManualPaperSelectedC3Assertion(
        audit.selection_id,
        audit.session_id,
        audit.terminal_id,
        audit.snapshot_id,
        audit.artifact_sha256,
        audit.artifact_byte_length,
    )
    plan = build_manual_paper_strategy_plan(
        ManualPaperStrategyPlanRequest(
            selected.verification,
            _PROFILE.paper_account_id,
            assertion,
            prior,
            history,
            MovingAverageCrossoverConfig(3, 5, Decimal("1")),
            str(_PROFILE.caller_idempotency_key),
            CallerAssertedNextSessionOpenReference(
                _SYMBOL, _OPEN_SESSION, Decimal("767.33")
            ),
            _policies(),
            _GENESIS_AS_OF,
            datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
            datetime(2026, 8, 31, 13, 30, tzinfo=UTC),
            (),
        ),
        calendar,
    )
    replayed = verify_manual_paper_strategy_plan(
        plan.artifact_bytes,
        calendar,
        expected_sha256=_PROFILE.plan_sha256,
        expected_byte_length=_PROFILE.plan_byte_length,
        expected_checkpointed_request=plan.checkpointed_request,
    )
    if (
        replayed != plan
        or plan.plan.plan_id != _PROFILE.plan_id
        or plan.checkpointed_request.request_id != _PROFILE.request_id
        or plan.artifact_sha256 != _PROFILE.plan_sha256
        or plan.artifact_byte_length != _PROFILE.plan_byte_length
        or sha256(plan.artifact_bytes).hexdigest() != _PROFILE.plan_sha256
        or len(plan.artifact_bytes) != _PROFILE.plan_byte_length
    ):
        raise PersonalDesktopFirstPaperConfigurationError(
            "reconstructed plan differs from the frozen first operation"
        )
    require_validated_production_authority(c1)
    return plan.artifact_bytes


def _require_publication_freeze() -> None:
    freeze = require_production_paper_publication_freeze()
    if (
        freeze.machine_authority_id != _MACHINE_AUTHORITY_ID
        or freeze.approved_trading_sid != _PROFILE.approved_trading_sid
        or freeze.paper_account_id != _PROFILE.paper_account_id
        or freeze.starting_cash != Decimal("25000")
        or freeze.genesis_as_of != _GENESIS_AS_OF
        or freeze.genesis_sha256 != _GENESIS_SHA256
        or freeze.genesis_byte_length != _GENESIS_BYTE_LENGTH
    ):
        raise PersonalDesktopFirstPaperConfigurationError(
            "Paper-v2 publication freeze differs from the first operation"
        )


def _load_history_seed(calendar: BoundMarketCalendar) -> VerifiedStrategyHistorySeed:
    path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "validation"
        / "evidence"
        / "pd2d1-spy-strategy-history-seed-2026-08-28.json"
    )
    payload = path.read_bytes()
    if len(payload) != _SEED_BYTE_LENGTH or sha256(payload).hexdigest() != _SEED_SHA256:
        raise PersonalDesktopFirstPaperConfigurationError(
            "frozen first-operation history seed bytes are unavailable"
        )
    verified = verify_strategy_history_seed(
        payload,
        expected_symbol=_SYMBOL,
        target_session=_TARGET_SESSION,
        strategy_config=MovingAverageCrossoverConfig(3, 5, Decimal("1")),
        calendar=calendar,
    )
    if verified.seed.seed_id != _SEED_ID:
        raise PersonalDesktopFirstPaperConfigurationError(
            "frozen first-operation history seed identity differs"
        )
    return verified


def _require_selected(selected: object) -> None:
    try:
        audit = selected.audit
        payload = selected.snapshot_bytes
        snapshot = selected.verification.snapshot
    except AttributeError as error:
        raise PersonalDesktopFirstPaperConfigurationError(
            "selected C3 evidence is incomplete"
        ) from error
    if (
        audit.selection_id != _SELECTION_ID
        or audit.snapshot_id != _PROFILE.selected_snapshot_id
        or audit.artifact_sha256 != _SELECTED_SHA256
        or audit.artifact_byte_length != _SELECTED_BYTE_LENGTH
        or type(payload) is not bytes
        or sha256(payload).hexdigest() != _SELECTED_SHA256
        or len(payload) != _SELECTED_BYTE_LENGTH
        or snapshot is None
        or snapshot.snapshot_id != _PROFILE.selected_snapshot_id
        or snapshot.target_session != _TARGET_SESSION
        or snapshot.request.symbols != (_SYMBOL,)
        or len(snapshot.bars) != 1
        or snapshot.bars[0].bar.symbol != _SYMBOL
    ):
        raise PersonalDesktopFirstPaperConfigurationError(
            "selected C3 evidence differs from the frozen first operation"
        )


def _policies() -> VerifiedSnapshotPaperCyclePolicies:
    return VerifiedSnapshotPaperCyclePolicies(
        RebalanceAssumptions(
            fixed_commission=Decimal("0"),
            allow_fractional_quantities=False,
            quantity_increment=Decimal("1"),
            minimum_trade_notional=Decimal("0"),
            minimum_trade_quantity=Decimal("1"),
            target_weight_tolerance=Decimal("0"),
            additional_execution_cash_buffer=Decimal("0"),
            use_planned_sell_proceeds=False,
        ),
        PortfolioConstraints(
            minimum_cash_weight=Decimal("0.90"),
            maximum_cash_weight=Decimal("1"),
            maximum_position_weight=Decimal("0.10"),
            maximum_one_way_rebalance_turnover=Decimal("0.10"),
            minimum_position_weight=None,
            long_only=True,
            allow_leverage=False,
        ),
        RebalanceProposalPolicy(allow_partial_plans=False),
        None,
        RiskLimits(
            max_position_percent=Decimal("0.10"),
            max_total_exposure_percent=Decimal("0.10"),
            max_order_notional=Decimal("2500"),
            max_new_position_percent=Decimal("0.10"),
            minimum_cash_reserve_percent=Decimal("0.90"),
            allow_fractional_shares=False,
            fractional_increment=Decimal("1"),
            allow_buying=True,
            allow_selling=True,
            estimated_commission=Decimal("0"),
        ),
        PortfolioRiskPolicy(allow_sell_proceeds_for_later_buys=False),
        PaperFillPolicy(Decimal("0"), Decimal("0")),
        True,
    )
