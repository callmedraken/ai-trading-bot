"""Effects-closed Architecture-111 unattended daily-cycle controller."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from trading_bot.execution import PaperFillPolicy
from trading_bot.market_calendar import TradingSession
from trading_bot.portfolio import PortfolioConstraints
from trading_bot.rebalancing import RebalanceAssumptions, RebalanceProposalPolicy
from trading_bot.risk import PortfolioRiskPolicy, RiskLimits
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperSelectedC3Assertion,
    ManualPaperStrategyDecisionRequest,
    ManualPaperStrategyPlanArtifactBinding,
    PreparedManualPaperStrategyDecision,
    build_manual_paper_strategy_decision,
    complete_manual_paper_strategy_plan,
)
from trading_bot.runtime.personal_desktop_historical_cycle_configurations import (
    resolve_personal_desktop_historical_cycle_configurations,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.personal_desktop_unattended_c3_history import (
    SelectedC3StrategyHistoryBinding,
    SelectedC3StrategyHistoryWindowClassification,
    SessionIndexedSelectedC3SnapshotReadResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
    build_selected_c3_strategy_history_binding,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle_timing import (
    next_xnys_execution_session,
    xnys_regular_open,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification,
    PersonalDesktopUnattendedMarketDataCaptureResult,
    reconcile_personal_desktop_unattended_market_data_capture,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_intent import (
    PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_POLICY_VERSION,
    PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    bind_personal_desktop_unattended_paper_decision_intent,
    create_personal_desktop_unattended_paper_decision_intent,
    personal_desktop_unattended_decision_calendar,
    verify_personal_desktop_unattended_paper_decision_intent,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationStatus,
    qualify_personal_desktop_unattended_decision_publication,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_storage import (
    FinalizedUnattendedDecisionForSessionClassification,
    FinalizedUnattendedDecisionForSessionResult,
    find_finalized_unattended_decision_for_execution_session,
    require_finalized_unattended_decision_for_execution_session,
)
from trading_bot.runtime.verified_c3_daily_bar_open import (
    build_c3_verified_daily_bar_open_binding,
)
from trading_bot.runtime.verified_snapshot_preparation import (
    VerifiedSnapshotPaperCyclePolicies,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

from .personal_desktop_unattended_paper_startup_qualification import (
    PersonalDesktopUnattendedPaperStartupStatus,
    qualify_personal_desktop_unattended_paper_startup_from_verified_plan,
)

PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_PROFILE_VERSION = (
    "personal-desktop-unattended-daily-cycle-profile/v1"
)
PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_IDEMPOTENCY_MATERIAL_VERSION = (
    "personal-desktop-unattended-daily-cycle-idempotency/v1"
)
PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_IDEMPOTENCY_NAMESPACE = UUID(
    "e9f228cd-e814-5df2-aae1-c9fa19fc45af"
)


class PersonalDesktopUnattendedDailyCycleClassification(StrEnum):
    """Bounded non-authorizing G6 classifications."""

    NO_NEW_COMPLETED_SESSION = "NO_NEW_COMPLETED_SESSION"
    CAPTURE_REQUIRED = "CAPTURE_REQUIRED"
    WARMING_UP = "WARMING_UP"
    DECISION_READY = "DECISION_READY"
    DECISION_ALREADY_FINALIZED = "DECISION_ALREADY_FINALIZED"
    EXECUTION_READY = "EXECUTION_READY"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    RECEIPT_RECOVERY_REQUIRED = "RECEIPT_RECOVERY_REQUIRED"
    MISSED_DECISION_DEADLINE = "MISSED_DECISION_DEADLINE"
    SESSION_GAP = "SESSION_GAP"
    PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS = "PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS"
    BLOCKED = "BLOCKED"


_Cycle = PersonalDesktopUnattendedDailyCycleClassification
_Capture = PersonalDesktopUnattendedMarketDataCaptureClassification
_Startup = PersonalDesktopUnattendedPaperStartupStatus


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedDailyCycleResult:
    """Sanitized point-in-time result carrying no reusable authority."""

    classification: PersonalDesktopUnattendedDailyCycleClassification
    completed_session: TradingSession | None = None
    selected_snapshot_id: UUID | None = None
    pending_decision_id: UUID | None = None
    next_decision_id: UUID | None = None
    invocation_id: UUID | None = None
    operation_id: UUID | None = None
    account_predecessor_checkpoint_id: UUID | None = None
    final_checkpoint_id: UUID | None = None
    market_data_classification: (
        PersonalDesktopUnattendedMarketDataCaptureClassification | None
    ) = None
    decision_publication_status: (
        PersonalDesktopUnattendedDecisionPublicationStatus | None
    ) = None
    settlement_status: PersonalDesktopUnattendedPaperStartupStatus | None = None
    real_effect_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.selected_snapshot_id,
            self.pending_decision_id,
            self.next_decision_id,
            self.invocation_id,
            self.operation_id,
            self.account_predecessor_checkpoint_id,
            self.final_checkpoint_id,
        )
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedDailyCycleClassification
            or (
                self.completed_session is not None
                and type(self.completed_session) is not TradingSession
            )
            or any(
                value is not None and type(value) is not UUID for value in identifiers
            )
            or (
                self.market_data_classification is not None
                and type(self.market_data_classification)
                is not PersonalDesktopUnattendedMarketDataCaptureClassification
            )
            or (
                self.decision_publication_status is not None
                and type(self.decision_publication_status)
                is not PersonalDesktopUnattendedDecisionPublicationStatus
            )
            or (
                self.settlement_status is not None
                and type(self.settlement_status)
                is not PersonalDesktopUnattendedPaperStartupStatus
            )
            or self.real_effect_performed is not False
        ):
            raise ValueError("unattended daily-cycle result is invalid")


@dataclass(frozen=True, slots=True)
class _SettlementResult:
    status: PersonalDesktopUnattendedPaperStartupStatus
    invocation_id: UUID | None = None
    operation_id: UUID | None = None
    final_checkpoint_id: UUID | None = None
    configuration_payload: bytes | None = None


class _InsufficientAuthoritativeHistory(Exception):
    """Normal leading C3 warm-up, distinct from invalid selected evidence."""


class _AuthoritativeHistorySessionGap(Exception):
    """Established selected-C3 chronology contains a required-session gap."""


@dataclass(frozen=True, slots=True)
class DisposablePersonalDesktopUnattendedDailyCycleDependencies:
    """Explicit disposable seams for deterministic G6 fault-matrix tests."""

    validate_c1: Callable[[object], object]
    reconcile_market_data: Callable[
        [object, datetime], PersonalDesktopUnattendedMarketDataCaptureResult
    ]
    read_selected: Callable[
        [object, TradingSession], SessionIndexedSelectedC3SnapshotReadResult
    ]
    find_pending: Callable[
        [object, TradingSession], FinalizedUnattendedDecisionForSessionResult
    ]
    require_pending: Callable[
        [object, FinalizedUnattendedDecisionForSessionResult],
        PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None,
    ]
    settle_pending: Callable[
        [
            object,
            SessionIndexedSelectedC3SnapshotReadResult,
            SessionIndexedSelectedC3SnapshotReadResult,
            PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
            tuple[bytes, ...],
        ],
        _SettlementResult,
    ]
    read_account: Callable[[object, tuple[bytes, ...]], object]
    require_account: Callable[[object], PersonalDesktopPaperAccountReadEvidence]
    build_history: Callable[
        [
            object,
            SessionIndexedSelectedC3SnapshotReadResult,
            MovingAverageCrossoverConfig,
        ],
        SelectedC3StrategyHistoryBinding,
    ]
    build_next_decision: Callable[
        [
            object,
            SessionIndexedSelectedC3SnapshotReadResult,
            SelectedC3StrategyHistoryBinding,
            PersonalDesktopPaperAccountReadEvidence,
            datetime,
            MovingAverageCrossoverConfig,
            VerifiedSnapshotPaperCyclePolicies,
        ],
        PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    ]
    qualify_decision: Callable[
        [object, PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding, datetime],
        Any,
    ]
    historical_configurations: Callable[[object], tuple[bytes, ...]]
    gate_state: Callable[[], tuple[bool, bool, bool, bool, bool, bool, bool, bool]]


def personal_desktop_unattended_strategy_config() -> MovingAverageCrossoverConfig:
    """Return the frozen Architecture-111 SPY crossover configuration."""

    return MovingAverageCrossoverConfig(3, 5, Decimal("1"))


def personal_desktop_unattended_paper_policies() -> VerifiedSnapshotPaperCyclePolicies:
    """Return the accepted conservative Architecture-94 personal-desktop policy."""

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
        PaperFillPolicy(
            slippage_basis_points=Decimal("0"),
            fixed_commission=Decimal("0"),
        ),
        True,
    )


def derive_personal_desktop_unattended_daily_cycle_idempotency_key(
    paper_account_id: str,
    predecessor_checkpoint_id: UUID,
    current: SessionIndexedSelectedC3SnapshotReadResult,
) -> UUID:
    """Derive restart-stable G3 caller idempotency from semantic predecessors."""

    if (
        type(paper_account_id) is not str
        or not paper_account_id
        or type(predecessor_checkpoint_id) is not UUID
        or type(current) is not SessionIndexedSelectedC3SnapshotReadResult
    ):
        raise ValueError("daily-cycle idempotency inputs are invalid")
    audit = current.selected.audit
    execution_session = next_xnys_execution_session(current.session)
    material = _framed_material(
        (
            PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_IDEMPOTENCY_MATERIAL_VERSION,
            paper_account_id,
            str(predecessor_checkpoint_id),
            current.session.session_date.isoformat(),
            str(audit.selection_id),
            str(audit.session_id),
            str(audit.terminal_id),
            str(audit.snapshot_id),
            audit.artifact_sha256,
            str(audit.artifact_byte_length),
            execution_session.session_date.isoformat(),
            PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_PROFILE_VERSION,
            PERSONAL_DESKTOP_UNATTENDED_PAPER_DECISION_POLICY_VERSION,
        )
    )
    return uuid5(
        PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_IDEMPOTENCY_NAMESPACE, material
    )


def run_personal_desktop_unattended_daily_cycle() -> (
    PersonalDesktopUnattendedDailyCycleResult
):
    """Run one zero-semantic-argument, effects-closed production daily cycle."""

    try:
        dependencies = _production_dependencies()
        authority = acquire_validated_production_authority()
        authority = require_validated_production_authority(authority)
        observed_at = datetime.now(UTC)
        return _run_daily_cycle(authority, observed_at, dependencies, production=True)
    except Exception:
        return PersonalDesktopUnattendedDailyCycleResult(
            PersonalDesktopUnattendedDailyCycleClassification.BLOCKED
        )


def run_personal_desktop_unattended_daily_cycle_for_test(
    authority: object,
    observed_at: datetime,
    dependencies: DisposablePersonalDesktopUnattendedDailyCycleDependencies,
) -> PersonalDesktopUnattendedDailyCycleResult:
    """Run G6 through explicit disposable dependencies and factual test time."""

    if (
        type(dependencies)
        is not DisposablePersonalDesktopUnattendedDailyCycleDependencies
    ):
        raise TypeError("disposable daily-cycle dependencies are invalid")
    return _run_daily_cycle(authority, observed_at, dependencies, production=False)


def _run_daily_cycle(
    authority: object,
    observed_at: datetime,
    dependencies: DisposablePersonalDesktopUnattendedDailyCycleDependencies,
    *,
    production: bool,
) -> PersonalDesktopUnattendedDailyCycleResult:
    market_data = None
    completed = None
    selected = None
    pending_id = None
    settlement = None
    account_predecessor = None
    try:
        if type(observed_at) is not datetime or observed_at.tzinfo is None:
            raise ValueError("daily-cycle observation must be timezone-aware")
        observed_at = observed_at.astimezone(UTC)
        gates = dependencies.gate_state()
        if (
            type(gates) is not tuple
            or len(gates) != 8
            or any(value is not False for value in gates)
        ):
            raise RuntimeError("all eight production effect gates must remain closed")
        c1 = dependencies.validate_c1(authority)
        market_data = dependencies.reconcile_market_data(c1, observed_at)
        if type(market_data) is not PersonalDesktopUnattendedMarketDataCaptureResult:
            raise TypeError("G5 result type is invalid")
        completed = market_data.eligible_completed_session
        g5 = market_data.classification
        if g5 is not _Capture.NO_NEW_COMPLETED_SESSION:
            if market_data.invocation is None or production:
                return _result(_map_market_data(g5), market_data=market_data)
        selected = dependencies.read_selected(c1, completed)
        if selected.session != completed:
            raise ValueError("selected C3 session differs from G5 completed session")

        discovery = dependencies.find_pending(c1, completed)
        if (
            type(discovery) is not FinalizedUnattendedDecisionForSessionResult
            or discovery.execution_session != completed
        ):
            raise TypeError("finalized-decision discovery result is invalid")
        if (
            discovery.classification
            is FinalizedUnattendedDecisionForSessionClassification.BLOCKED
        ):
            return _result(
                PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
                market_data=market_data,
                selected=selected,
            )
        pending = dependencies.require_pending(c1, discovery)
        historical = tuple(dependencies.historical_configurations(c1))
        account = None
        if pending is not None:
            pending_id = pending.decision.decision_id
            _require_pending_decision(pending, completed, selected)
            original = dependencies.read_selected(c1, pending.decision.selected_session)
            _require_original_decision_snapshot(pending, original)
            settlement = dependencies.settle_pending(
                c1,
                original,
                selected,
                pending,
                historical,
            )
            if type(settlement) is not _SettlementResult:
                raise TypeError("settlement result type is invalid")
            mapped = _map_settlement(settlement.status)
            if mapped in {
                PersonalDesktopUnattendedDailyCycleClassification.EXECUTION_READY,
                PersonalDesktopUnattendedDailyCycleClassification.RECEIPT_RECOVERY_REQUIRED,
                PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
            }:
                return _result(
                    mapped,
                    market_data=market_data,
                    selected=selected,
                    pending_id=pending_id,
                    settlement=settlement,
                )
            if settlement.configuration_payload is None:
                raise ValueError("safe settlement omitted its configuration payload")
            historical = _include_configuration_once(
                historical, settlement.configuration_payload
            )

        account_authority = dependencies.read_account(c1, historical)
        account = dependencies.require_account(account_authority)
        account_predecessor = account.prior_checkpoint.checkpoint_id
        if pending is not None and settlement is not None:
            prior = pending.decision.predecessor_checkpoint_id
            if account_predecessor == prior:
                raise ValueError(
                    "already-applied settlement did not advance the account"
                )

        config = personal_desktop_unattended_strategy_config()
        try:
            history = dependencies.build_history(c1, selected, config)
        except _InsufficientAuthoritativeHistory:
            return _result(
                PersonalDesktopUnattendedDailyCycleClassification.WARMING_UP,
                market_data=market_data,
                selected=selected,
                pending_id=pending_id,
                settlement=settlement,
                account_predecessor=account_predecessor,
            )
        except _AuthoritativeHistorySessionGap:
            return _result(
                PersonalDesktopUnattendedDailyCycleClassification.SESSION_GAP,
                market_data=market_data,
                selected=selected,
                pending_id=pending_id,
                settlement=settlement,
                account_predecessor=account_predecessor,
            )
        except Exception:
            return _result(
                PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
                market_data=market_data,
                selected=selected,
                pending_id=pending_id,
                settlement=settlement,
                account_predecessor=account_predecessor,
            )
        next_decision = dependencies.build_next_decision(
            c1,
            selected,
            history,
            account,
            observed_at,
            config,
            personal_desktop_unattended_paper_policies(),
        )
        qualification = dependencies.qualify_decision(c1, next_decision, observed_at)
        final = _map_publication(qualification.status)
        if (
            settlement is not None
            and settlement.status
            is PersonalDesktopUnattendedPaperStartupStatus.ALREADY_APPLIED
            and final
            in {
                PersonalDesktopUnattendedDailyCycleClassification.DECISION_READY,
                PersonalDesktopUnattendedDailyCycleClassification.DECISION_ALREADY_FINALIZED,
            }
        ):
            final = PersonalDesktopUnattendedDailyCycleClassification.ALREADY_APPLIED
        return _result(
            final,
            market_data=market_data,
            selected=selected,
            pending_id=pending_id,
            next_decision_id=next_decision.decision.decision_id,
            qualification=qualification,
            settlement=settlement,
            account_predecessor=account_predecessor,
        )
    except Exception:
        return PersonalDesktopUnattendedDailyCycleResult(
            PersonalDesktopUnattendedDailyCycleClassification.BLOCKED,
            completed_session=completed,
            selected_snapshot_id=(
                selected.selected.audit.snapshot_id if selected is not None else None
            ),
            pending_decision_id=pending_id,
            account_predecessor_checkpoint_id=account_predecessor,
            market_data_classification=(
                market_data.classification if market_data is not None else None
            ),
            settlement_status=settlement.status if settlement is not None else None,
        )


def _production_dependencies() -> (
    DisposablePersonalDesktopUnattendedDailyCycleDependencies
):
    retained_selected_readers: list[
        WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority
    ] = []

    def read_selected(
        authority: object, session: TradingSession
    ) -> SessionIndexedSelectedC3SnapshotReadResult:
        reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(
            authority  # type: ignore[arg-type]
        )
        retained_selected_readers.append(reader)
        return reader.read_selected_snapshot_for_session(session)

    def find_pending(
        authority: object, session: TradingSession
    ) -> FinalizedUnattendedDecisionForSessionResult:
        return find_finalized_unattended_decision_for_execution_session(
            session,
            authority,  # type: ignore[arg-type]
        )

    def require_pending(
        authority: object, result: FinalizedUnattendedDecisionForSessionResult
    ) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding | None:
        return require_finalized_unattended_decision_for_execution_session(
            result,
            authority,  # type: ignore[arg-type]
        )

    def read_account(authority: object, configurations: tuple[bytes, ...]) -> object:
        return read_personal_desktop_paper_account(
            authority,  # type: ignore[arg-type]
            historical_cycle_configuration_payloads=configurations,
        )

    return DisposablePersonalDesktopUnattendedDailyCycleDependencies(
        validate_c1=require_validated_production_authority,
        reconcile_market_data=lambda authority, observed: (
            reconcile_personal_desktop_unattended_market_data_capture(
                authority,
                observed,  # type: ignore[arg-type]
            )
        ),
        read_selected=read_selected,
        find_pending=find_pending,
        require_pending=require_pending,
        settle_pending=_settle_pending_production,
        read_account=read_account,
        require_account=require_validated_personal_desktop_paper_account,
        build_history=_build_history_production,
        build_next_decision=_build_next_decision_production,
        qualify_decision=lambda authority, decision, observed: (
            qualify_personal_desktop_unattended_decision_publication(
                authority,
                decision,
                observed,  # type: ignore[arg-type]
            )
        ),
        historical_configurations=(
            resolve_personal_desktop_historical_cycle_configurations
        ),
        gate_state=_all_eight_gate_state,
    )


def _settle_pending_production(
    authority: object,
    original_selected: SessionIndexedSelectedC3SnapshotReadResult,
    execution_selected: SessionIndexedSelectedC3SnapshotReadResult,
    pending: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    historical: tuple[bytes, ...],
) -> _SettlementResult:
    c1 = require_validated_production_authority(authority)
    open_binding = build_c3_verified_daily_bar_open_binding(
        execution_selected.selected, c1
    )
    plan = complete_manual_paper_strategy_plan(
        pending.decision.prepared_decision,
        open_binding,
        personal_desktop_unattended_decision_calendar(),
    )
    _require_completed_plan(pending, plan, execution_selected)
    startup = qualify_personal_desktop_unattended_paper_startup_from_verified_plan(
        c1,
        original_selected.selected,
        plan,
        historical_cycle_configuration_payloads=(*historical, plan.artifact_bytes),
    )
    return _SettlementResult(
        startup.status,
        startup.invocation_id,
        startup.operation_id,
        None,
        plan.artifact_bytes,
    )


def _build_history_production(
    authority: object,
    current: SessionIndexedSelectedC3SnapshotReadResult,
    config: MovingAverageCrossoverConfig,
) -> SelectedC3StrategyHistoryBinding:
    c1 = require_validated_production_authority(authority)
    reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
    window = reader.inspect_strategy_history_window(current, config)
    if (
        window.classification
        is SelectedC3StrategyHistoryWindowClassification.WARMING_UP
    ):
        raise _InsufficientAuthoritativeHistory
    if (
        window.classification
        is SelectedC3StrategyHistoryWindowClassification.SESSION_GAP
    ):
        raise _AuthoritativeHistorySessionGap
    if (
        window.classification is not SelectedC3StrategyHistoryWindowClassification.READY
        or len(window.selected) != config.long_window + 1
        or window.selected[-1] != current
    ):
        raise ValueError("selected-C3 history-window result is invalid")
    return build_selected_c3_strategy_history_binding(
        c1, window.selected[:-1], current, config
    )


def _include_configuration_once(
    historical: tuple[bytes, ...], payload: bytes
) -> tuple[bytes, ...]:
    key = (hashlib.sha256(payload).hexdigest(), len(payload))
    for existing in historical:
        if (hashlib.sha256(existing).hexdigest(), len(existing)) == key:
            if existing != payload:
                raise ValueError("historical configuration digest conflict")
            return historical
    return (*historical, payload)


def _build_next_decision_production(
    authority: object,
    current: SessionIndexedSelectedC3SnapshotReadResult,
    history: SelectedC3StrategyHistoryBinding,
    account: PersonalDesktopPaperAccountReadEvidence,
    observed_at: datetime,
    config: MovingAverageCrossoverConfig,
    policies: VerifiedSnapshotPaperCyclePolicies,
) -> PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding:
    c1 = require_validated_production_authority(authority)
    audit = current.selected.audit
    prior = account.prior_checkpoint
    execution_session = next_xnys_execution_session(current.session)
    modeled_open = xnys_regular_open(execution_session)
    caller_idempotency = derive_personal_desktop_unattended_daily_cycle_idempotency_key(
        account.anchor.paper_account_id, prior.checkpoint_id, current
    )
    prepared = build_manual_paper_strategy_decision(
        ManualPaperStrategyDecisionRequest(
            current.selected.verification,
            account.anchor.paper_account_id,
            ManualPaperSelectedC3Assertion(
                audit.selection_id,
                audit.session_id,
                audit.terminal_id,
                audit.snapshot_id,
                audit.artifact_sha256,
                audit.artifact_byte_length,
            ),
            prior,
            history.verified_seed,
            config,
            str(caller_idempotency),
            policies,
            observed_at,
            modeled_open,
            modeled_open,
            (),
        ),
        personal_desktop_unattended_decision_calendar(),
    )
    decision = create_personal_desktop_unattended_paper_decision_intent(
        prepared,
        history,
        c1,
        expected_paper_account_id=account.anchor.paper_account_id,
        expected_predecessor_checkpoint_id=prior.checkpoint_id,
    )
    return bind_personal_desktop_unattended_paper_decision_intent(decision)


def _require_pending_decision(
    pending: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    completed: TradingSession,
    selected: SessionIndexedSelectedC3SnapshotReadResult,
) -> None:
    replayed = verify_personal_desktop_unattended_paper_decision_intent(
        pending.artifact_bytes,
        personal_desktop_unattended_decision_calendar(),
        expected_decision_id=pending.decision.decision_id,
        expected_artifact_sha256=pending.artifact_sha256,
        expected_artifact_byte_length=pending.artifact_byte_length,
    )
    if (
        replayed != pending
        or pending.decision.intended_execution_session != completed
        or pending.decision.selected_session >= completed
        or selected.session != completed
    ):
        raise ValueError("pending decision does not target the completed session")


def _require_original_decision_snapshot(
    pending: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    original: SessionIndexedSelectedC3SnapshotReadResult,
) -> None:
    evidence = pending.decision.current_c3
    audit = original.selected.audit
    if (
        original.session != pending.decision.selected_session
        or original.selected.snapshot_bytes != evidence.snapshot_artifact
        or audit.selection_id != evidence.selection_id
        or audit.session_id != evidence.session_id
        or audit.terminal_id != evidence.terminal_id
        or audit.snapshot_id != evidence.snapshot_id
        or audit.artifact_sha256 != evidence.artifact_sha256
        or audit.artifact_byte_length != evidence.artifact_byte_length
    ):
        raise ValueError("durable decision current-C3 evidence is not exact")


def _require_completed_plan(
    pending: PersonalDesktopUnattendedPaperDecisionIntentArtifactBinding,
    plan: ManualPaperStrategyPlanArtifactBinding,
    execution_selected: SessionIndexedSelectedC3SnapshotReadResult,
) -> None:
    prepared: PreparedManualPaperStrategyDecision = pending.decision.prepared_decision
    if (
        plan.plan.paper_account_id != pending.decision.paper_account_id
        or plan.plan.prior_checkpoint.checkpoint_id
        != pending.decision.predecessor_checkpoint_id
        or plan.plan.selected_c3_assertion != prepared.selected_c3_assertion
        or plan.plan.caller_idempotency_key != prepared.caller_idempotency_key
        or execution_selected.session != pending.decision.intended_execution_session
    ):
        raise ValueError("completed Architecture-94 plan identity is inconsistent")


def _all_eight_gate_state() -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    from trading_bot.runtime import personal_desktop_paper_account_security as security
    from trading_bot.runtime import (
        personal_desktop_paper_receipt_recovery_execution as receipt,
    )
    from trading_bot.runtime import (
        personal_desktop_supervised_paper_operation_execution as supervised,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_market_data_capture as capture,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_decision_publication as publication,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_operation_execution as unattended,
    )
    from trading_bot.runtime import (
        personal_desktop_unattended_paper_storage_provisioning as provisioning,
    )

    return (
        capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED,
        publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        receipt.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def _map_market_data(
    value: PersonalDesktopUnattendedMarketDataCaptureClassification,
) -> PersonalDesktopUnattendedDailyCycleClassification:
    mapping = {
        _Capture.CAPTURE_REQUIRED: _Cycle.CAPTURE_REQUIRED,
        _Capture.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS: (
            _Cycle.PROVIDER_ATTEMPT_CONSUMED_OR_AMBIGUOUS
        ),
        _Capture.SESSION_GAP: _Cycle.SESSION_GAP,
        _Capture.BLOCKED: _Cycle.BLOCKED,
    }
    return mapping.get(value, _Cycle.BLOCKED)


def _map_settlement(
    value: PersonalDesktopUnattendedPaperStartupStatus,
) -> PersonalDesktopUnattendedDailyCycleClassification:
    mapping = {
        _Startup.HEALTHY_NO_PENDING_INVOCATION: _Cycle.EXECUTION_READY,
        _Startup.READY_SAME_INVOCATION: _Cycle.EXECUTION_READY,
        _Startup.ALREADY_APPLIED: _Cycle.ALREADY_APPLIED,
        _Startup.RECEIPT_RECOVERY_REQUIRED: _Cycle.RECEIPT_RECOVERY_REQUIRED,
        _Startup.BLOCKED: _Cycle.BLOCKED,
    }
    return mapping[value]


def _map_publication(
    value: object,
) -> PersonalDesktopUnattendedDailyCycleClassification:
    statuses = PersonalDesktopUnattendedDecisionPublicationStatus
    mapping = {
        statuses.DECISION_ALREADY_FINALIZED: _Cycle.DECISION_ALREADY_FINALIZED,
        statuses.DECISION_READY: _Cycle.DECISION_READY,
        statuses.DECISION_READY_EFFECTS_DISABLED: _Cycle.DECISION_READY,
        statuses.MISSED_DECISION_DEADLINE: _Cycle.MISSED_DECISION_DEADLINE,
        statuses.BLOCKED: _Cycle.BLOCKED,
    }
    return mapping.get(value, _Cycle.BLOCKED)


def _result(
    classification: PersonalDesktopUnattendedDailyCycleClassification,
    *,
    market_data: PersonalDesktopUnattendedMarketDataCaptureResult,
    selected: SessionIndexedSelectedC3SnapshotReadResult | None = None,
    pending_id: UUID | None = None,
    next_decision_id: UUID | None = None,
    qualification: object | None = None,
    settlement: _SettlementResult | None = None,
    account_predecessor: UUID | None = None,
) -> PersonalDesktopUnattendedDailyCycleResult:
    return PersonalDesktopUnattendedDailyCycleResult(
        classification,
        completed_session=market_data.eligible_completed_session,
        selected_snapshot_id=(
            selected.selected.audit.snapshot_id if selected is not None else None
        ),
        pending_decision_id=pending_id,
        next_decision_id=next_decision_id,
        invocation_id=settlement.invocation_id if settlement is not None else None,
        operation_id=settlement.operation_id if settlement is not None else None,
        account_predecessor_checkpoint_id=account_predecessor,
        final_checkpoint_id=(
            settlement.final_checkpoint_id if settlement is not None else None
        ),
        market_data_classification=market_data.classification,
        decision_publication_status=(
            qualification.status if qualification is not None else None
        ),
        settlement_status=settlement.status if settlement is not None else None,
    )


def _framed_material(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
