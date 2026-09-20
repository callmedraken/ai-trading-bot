"""Effects-closed operator snapshot composition for PD4 observability O2."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.gui.operator_observability_adapters import (
    adapt_effect_gate_state,
    adapt_selected_c3_history_window,
)
from trading_bot.gui.operator_observability_models import (
    OperatorEffectGateState,
    OperatorWarmupView,
)
from trading_bot.market_calendar import TradingSession
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
    SelectedC3StrategyHistoryWindowResult,
    WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority,
    build_retained_selected_c3_strategy_history_binding,
    retain_selected_c3_snapshot_provenance_lifetime,
)
from trading_bot.runtime.personal_desktop_unattended_capture_warmup import (
    PersonalDesktopUnattendedCaptureWarmupGateState,
    personal_desktop_unattended_capture_warmup_gate_state,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    PersonalDesktopUnattendedDailyCycleClassification,
    PersonalDesktopUnattendedDailyCycleResult,
    personal_desktop_unattended_strategy_config,
    run_personal_desktop_unattended_daily_cycle,
)
from trading_bot.runtime.personal_desktop_unattended_market_data_capture import (
    PersonalDesktopUnattendedMarketDataCaptureClassification,
)
from trading_bot.runtime.personal_desktop_unattended_paper_decision_publication import (
    PersonalDesktopUnattendedDecisionPublicationStatus,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    acquire_validated_production_authority,
    require_validated_production_authority,
)

from .personal_desktop_unattended_paper_startup_qualification import (
    PersonalDesktopUnattendedPaperStartupStatus,
)


class OperatorObservabilitySnapshotError(ValueError):
    """O2 could not produce one exact effects-closed operator snapshot."""


@dataclass(frozen=True, slots=True)
class OperatorPaperPositionView:
    """Bounded exact accounting facts for one current paper position."""

    symbol: str
    quantity: Decimal
    total_cost_basis: Decimal
    average_cost: Decimal

    def __post_init__(self) -> None:
        if (
            type(self.symbol) is not str
            or not self.symbol
            or self.symbol != str(Symbol(self.symbol))
        ):
            raise OperatorObservabilitySnapshotError("paper position symbol is invalid")
        for name in ("quantity", "total_cost_basis", "average_cost"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value <= 0:
                raise OperatorObservabilitySnapshotError(
                    f"paper position {name} is invalid"
                )


@dataclass(frozen=True, slots=True)
class OperatorPaperAccountView:
    """Sanitized current Paper-v2 account and lineage summary."""

    paper_account_id: str
    checkpoint_id: UUID
    sequence: int
    as_of: datetime
    cash: Decimal
    realized_profit_loss: Decimal
    positions: tuple[OperatorPaperPositionView, ...]
    lineage_edge_count: int
    receipt_count: int

    def __post_init__(self) -> None:
        if type(self.paper_account_id) is not str or not self.paper_account_id:
            raise OperatorObservabilitySnapshotError("paper account ID is invalid")
        if type(self.checkpoint_id) is not UUID:
            raise OperatorObservabilitySnapshotError("checkpoint ID is invalid")
        if type(self.sequence) is not int or self.sequence < 0:
            raise OperatorObservabilitySnapshotError("checkpoint sequence is invalid")
        if (
            type(self.as_of) is not datetime
            or self.as_of.tzinfo is None
            or self.as_of.utcoffset() is None
        ):
            raise OperatorObservabilitySnapshotError("account as-of is invalid")
        if type(self.cash) is not Decimal or not self.cash.is_finite() or self.cash < 0:
            raise OperatorObservabilitySnapshotError("account cash is invalid")
        if (
            type(self.realized_profit_loss) is not Decimal
            or not self.realized_profit_loss.is_finite()
        ):
            raise OperatorObservabilitySnapshotError("account realized P&L is invalid")
        positions = tuple(self.positions)
        if any(type(item) is not OperatorPaperPositionView for item in positions):
            raise OperatorObservabilitySnapshotError("account positions are invalid")
        if len({item.symbol for item in positions}) != len(positions):
            raise OperatorObservabilitySnapshotError(
                "account position symbols are not unique"
            )
        if type(self.lineage_edge_count) is not int or self.lineage_edge_count < 0:
            raise OperatorObservabilitySnapshotError(
                "account lineage edge count is invalid"
            )
        if type(self.receipt_count) is not int or self.receipt_count < 0:
            raise OperatorObservabilitySnapshotError("account receipt count is invalid")
        object.__setattr__(self, "positions", positions)


@dataclass(frozen=True, slots=True)
class OperatorObservabilitySnapshotResult:
    """One bounded O2 point-in-time observation carrying no mutation authority."""

    cycle_classification: PersonalDesktopUnattendedDailyCycleClassification
    completed_session: TradingSession | None
    market_data_classification: (
        PersonalDesktopUnattendedMarketDataCaptureClassification | None
    )
    selected_snapshot_id: UUID | None
    warmup: OperatorWarmupView | None
    account: OperatorPaperAccountView
    gates: OperatorEffectGateState
    real_effect_performed: bool = False
    pending_decision_id: UUID | None = None
    next_decision_id: UUID | None = None
    invocation_id: UUID | None = None
    operation_id: UUID | None = None
    account_predecessor_checkpoint_id: UUID | None = None
    final_checkpoint_id: UUID | None = None
    decision_publication_status: (
        PersonalDesktopUnattendedDecisionPublicationStatus | None
    ) = None
    settlement_status: PersonalDesktopUnattendedPaperStartupStatus | None = None

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
            type(self.cycle_classification)
            is not PersonalDesktopUnattendedDailyCycleClassification
        ):
            raise OperatorObservabilitySnapshotError("cycle classification is invalid")
        if (
            self.completed_session is not None
            and type(self.completed_session) is not TradingSession
        ):
            raise OperatorObservabilitySnapshotError("completed session is invalid")
        if (
            self.market_data_classification is not None
            and type(self.market_data_classification)
            is not PersonalDesktopUnattendedMarketDataCaptureClassification
        ):
            raise OperatorObservabilitySnapshotError(
                "market-data classification is invalid"
            )
        if any(value is not None and type(value) is not UUID for value in identifiers):
            raise OperatorObservabilitySnapshotError(
                "daily-cycle identifier is invalid"
            )
        if (
            self.decision_publication_status is not None
            and type(self.decision_publication_status)
            is not PersonalDesktopUnattendedDecisionPublicationStatus
        ):
            raise OperatorObservabilitySnapshotError(
                "decision publication status is invalid"
            )
        if (
            self.settlement_status is not None
            and type(self.settlement_status)
            is not PersonalDesktopUnattendedPaperStartupStatus
        ):
            raise OperatorObservabilitySnapshotError("settlement status is invalid")
        if type(self.account) is not OperatorPaperAccountView:
            raise OperatorObservabilitySnapshotError("account view is invalid")
        if type(self.gates) is not OperatorEffectGateState or not self.gates.all_closed:
            raise OperatorObservabilitySnapshotError(
                "operator snapshot requires all effect gates closed"
            )
        if self.real_effect_performed is not False:
            raise OperatorObservabilitySnapshotError(
                "operator snapshot cannot report a real effect"
            )
        if (self.warmup is None) != (self.selected_snapshot_id is None):
            raise OperatorObservabilitySnapshotError(
                "warm-up evidence and selected snapshot must appear together"
            )


@dataclass(frozen=True, slots=True)
class DisposableOperatorObservabilitySnapshotDependencies:
    """Injectable O2 boundaries for deterministic no-effect focused tests."""

    gate_state: Callable[[], PersonalDesktopUnattendedCaptureWarmupGateState]
    run_cycle: Callable[[], PersonalDesktopUnattendedDailyCycleResult]
    acquire_c1: Callable[[], ValidatedProductionAuthority]
    validate_c1: Callable[
        [ValidatedProductionAuthority],
        ValidatedProductionAuthority,
    ]
    read_window: Callable[
        [ValidatedProductionAuthority, PersonalDesktopUnattendedDailyCycleResult],
        SelectedC3StrategyHistoryWindowResult | None,
    ]
    read_account: Callable[
        [ValidatedProductionAuthority],
        OperatorPaperAccountView,
    ]


def read_personal_desktop_operator_observability_snapshot() -> (
    OperatorObservabilitySnapshotResult
):
    """Read one zero-semantic-argument production snapshot with every effect closed."""

    return _read_snapshot(_production_dependencies())


def read_personal_desktop_operator_observability_snapshot_for_test(
    dependencies: DisposableOperatorObservabilitySnapshotDependencies,
) -> OperatorObservabilitySnapshotResult:
    """Exercise O2 through explicit disposable read-only dependencies."""

    if type(dependencies) is not DisposableOperatorObservabilitySnapshotDependencies:
        raise TypeError("operator observability dependencies are invalid")
    return _read_snapshot(dependencies)


def _read_snapshot(
    dependencies: DisposableOperatorObservabilitySnapshotDependencies,
) -> OperatorObservabilitySnapshotResult:
    before = adapt_effect_gate_state(dependencies.gate_state())
    if not before.all_closed:
        raise OperatorObservabilitySnapshotError(
            "all eight effect gates must be closed before O2"
        )

    cycle = dependencies.run_cycle()
    if (
        type(cycle) is not PersonalDesktopUnattendedDailyCycleResult
        or cycle.real_effect_performed is not False
    ):
        raise OperatorObservabilitySnapshotError(
            "effects-closed G6 evidence is invalid"
        )

    c1 = dependencies.validate_c1(dependencies.acquire_c1())
    if type(c1) is not ValidatedProductionAuthority:
        raise OperatorObservabilitySnapshotError("C1 validation result is invalid")
    account = dependencies.read_account(c1)
    if type(account) is not OperatorPaperAccountView:
        raise OperatorObservabilitySnapshotError("account read result is invalid")

    window = dependencies.read_window(c1, cycle)
    warmup = None
    if window is not None:
        warmup = adapt_selected_c3_history_window(window)

    after = adapt_effect_gate_state(dependencies.gate_state())
    if not after.all_closed or after != before:
        raise OperatorObservabilitySnapshotError("effect-gate state changed during O2")

    return OperatorObservabilitySnapshotResult(
        cycle_classification=cycle.classification,
        completed_session=cycle.completed_session,
        market_data_classification=cycle.market_data_classification,
        selected_snapshot_id=cycle.selected_snapshot_id,
        warmup=warmup,
        account=account,
        gates=after,
        real_effect_performed=cycle.real_effect_performed,
        pending_decision_id=cycle.pending_decision_id,
        next_decision_id=cycle.next_decision_id,
        invocation_id=cycle.invocation_id,
        operation_id=cycle.operation_id,
        account_predecessor_checkpoint_id=cycle.account_predecessor_checkpoint_id,
        final_checkpoint_id=cycle.final_checkpoint_id,
        decision_publication_status=cycle.decision_publication_status,
        settlement_status=cycle.settlement_status,
    )


def _production_dependencies() -> DisposableOperatorObservabilitySnapshotDependencies:
    retained_history_bindings: list[SelectedC3StrategyHistoryBinding] = []
    retained_partial_provenance: list[object] = []

    def read_window(
        authority: ValidatedProductionAuthority,
        cycle: PersonalDesktopUnattendedDailyCycleResult,
    ) -> SelectedC3StrategyHistoryWindowResult | None:
        return _read_window_production(
            authority,
            cycle,
            retained_bindings=retained_history_bindings,
            retained_provenance=retained_partial_provenance,
        )

    return DisposableOperatorObservabilitySnapshotDependencies(
        gate_state=personal_desktop_unattended_capture_warmup_gate_state,
        run_cycle=run_personal_desktop_unattended_daily_cycle,
        acquire_c1=acquire_validated_production_authority,
        validate_c1=require_validated_production_authority,
        read_window=read_window,
        read_account=_read_account_production,
    )


def _read_window_production(
    authority: ValidatedProductionAuthority,
    cycle: PersonalDesktopUnattendedDailyCycleResult,
    *,
    retained_bindings: list[SelectedC3StrategyHistoryBinding] | None = None,
    retained_provenance: list[object] | None = None,
) -> SelectedC3StrategyHistoryWindowResult | None:
    c1 = require_validated_production_authority(authority)
    if cycle.selected_snapshot_id is None:
        return None
    if cycle.completed_session is None:
        raise OperatorObservabilitySnapshotError(
            "selected snapshot lacks completed session"
        )
    reader = WindowsPersonalDesktopUnattendedSelectedC3ReadAuthority(c1)
    current = reader.read_selected_snapshot_for_session(cycle.completed_session)
    if current.selected.audit.snapshot_id != cycle.selected_snapshot_id:
        raise OperatorObservabilitySnapshotError(
            "G6 selected snapshot does not match P2"
        )
    config = personal_desktop_unattended_strategy_config()
    window = reader.inspect_strategy_history_window(current, config)
    if type(window) is not SelectedC3StrategyHistoryWindowResult:
        raise OperatorObservabilitySnapshotError(
            "selected-C3 history-window result is invalid"
        )
    if window.classification is SelectedC3StrategyHistoryWindowClassification.READY:
        if (
            len(window.selected) != config.long_window + 1
            or window.selected[-1] != current
        ):
            raise OperatorObservabilitySnapshotError(
                "selected-C3 history-window result is invalid"
            )
        binding = build_retained_selected_c3_strategy_history_binding(
            c1,
            window.selected[:-1],
            current,
            config,
        )
        if retained_bindings is not None:
            retained_bindings.append(binding)
    elif window.selected and retained_provenance is not None:
        retained_provenance.append(
            retain_selected_c3_snapshot_provenance_lifetime(
                tuple(
                    (item.selected.permit, item.selected.audit)
                    for item in window.selected
                ),
                c1,
            )
        )
    return window


def _read_account_production(
    authority: ValidatedProductionAuthority,
) -> OperatorPaperAccountView:
    c1 = require_validated_production_authority(authority)
    configurations = resolve_personal_desktop_historical_cycle_configurations(c1)
    registered = read_personal_desktop_paper_account(
        c1,
        historical_cycle_configuration_payloads=configurations,
    )
    evidence = require_validated_personal_desktop_paper_account(registered)
    return _adapt_account(evidence)


def _adapt_account(
    evidence: PersonalDesktopPaperAccountReadEvidence,
) -> OperatorPaperAccountView:
    if type(evidence) is not PersonalDesktopPaperAccountReadEvidence:
        raise OperatorObservabilitySnapshotError("paper account evidence is invalid")
    prior = evidence.prior_checkpoint
    state = prior.compact_state
    positions = tuple(
        OperatorPaperPositionView(
            symbol=str(item.symbol),
            quantity=item.quantity,
            total_cost_basis=item.total_cost_basis,
            average_cost=item.average_cost,
        )
        for item in state.positions
    )
    return OperatorPaperAccountView(
        paper_account_id=evidence.anchor.paper_account_id,
        checkpoint_id=prior.checkpoint_id,
        sequence=prior.sequence,
        as_of=state.as_of,
        cash=state.cash,
        realized_profit_loss=state.realized_profit_loss,
        positions=positions,
        lineage_edge_count=evidence.lineage.edge_count,
        receipt_count=len(evidence.receipts),
    )
