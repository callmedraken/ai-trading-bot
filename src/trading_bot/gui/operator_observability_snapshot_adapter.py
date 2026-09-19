"""Adapt the bounded O2 runtime snapshot into Qt-free Operations-page state."""

from __future__ import annotations

from trading_bot.gui.operator_observability_models import (
    OperatorAccountPositionView,
    OperatorAccountSummaryView,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
)
from trading_bot.runtime.operator_observability_snapshot import (
    OperatorObservabilitySnapshotResult,
)


class OperatorObservabilitySnapshotAdapterError(ValueError):
    """The bounded O2 result cannot be represented safely by the GUI."""


def adapt_operator_observability_snapshot(
    result: OperatorObservabilitySnapshotResult,
) -> OperatorOperationsPageState:
    """Copy one exact O2 result into immutable GUI presentation state."""

    if type(result) is not OperatorObservabilitySnapshotResult:
        raise OperatorObservabilitySnapshotAdapterError(
            "operator snapshot result type is invalid"
        )
    if result.real_effect_performed is not False:
        raise OperatorObservabilitySnapshotAdapterError(
            "operator snapshot cannot contain a real effect"
        )

    account = result.account
    positions = tuple(
        OperatorAccountPositionView(
            symbol=item.symbol,
            quantity=item.quantity,
            total_cost_basis=item.total_cost_basis,
            average_cost=item.average_cost,
        )
        for item in account.positions
    )
    summary = OperatorAccountSummaryView(
        paper_account_id=account.paper_account_id,
        checkpoint_id=account.checkpoint_id,
        sequence=account.sequence,
        as_of=account.as_of,
        cash=account.cash,
        realized_profit_loss=account.realized_profit_loss,
        positions=positions,
        lineage_edge_count=account.lineage_edge_count,
        receipt_count=account.receipt_count,
    )

    return OperatorOperationsPageState(
        status=OperatorOperationsPageStatus.AVAILABLE,
        message=(
            "Current production observability snapshot; read-only and non-authorizing."
        ),
        cycle_classification=result.cycle_classification.value,
        completed_session=(
            None
            if result.completed_session is None
            else result.completed_session.session_date
        ),
        market_data_classification=(
            None
            if result.market_data_classification is None
            else result.market_data_classification.value
        ),
        selected_snapshot_id=result.selected_snapshot_id,
        warmup=result.warmup,
        gates=result.gates,
        account=summary,
    )
