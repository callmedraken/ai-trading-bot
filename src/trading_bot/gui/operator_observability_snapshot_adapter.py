"""Adapt the bounded O2 runtime snapshot into Qt-free Operations-page state."""

from __future__ import annotations

from trading_bot.gui.operator_observability_models import (
    OperatorAccountPositionView,
    OperatorAccountSummaryView,
    OperatorOperationsPageState,
    OperatorOperationsPageStatus,
    OperatorStrategyExplanationStatus,
    OperatorStrategyExplanationView,
)
from trading_bot.runtime.operator_observability_snapshot import (
    OperatorObservabilitySnapshotResult,
)
from trading_bot.runtime.personal_desktop_unattended_daily_cycle import (
    personal_desktop_unattended_strategy_config,
)
from trading_bot.strategies import evaluate_moving_average_crossover_closes


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

    strategy = _strategy_explanation(result, summary)

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
        strategy_explanation=strategy,
    )


def _strategy_explanation(
    result: OperatorObservabilitySnapshotResult,
    account: OperatorAccountSummaryView,
) -> OperatorStrategyExplanationView:
    config = personal_desktop_unattended_strategy_config()
    warmup = result.warmup
    selected = () if warmup is None else warmup.selected_sessions
    symbols = {item.symbol for item in selected}
    if len(symbols) > 1:
        raise OperatorObservabilitySnapshotAdapterError(
            "selected-C3 strategy explanation has multiple symbols"
        )
    symbol = next(iter(symbols), None)
    invested = False
    if symbol is not None:
        invested = any(
            position.symbol == symbol and position.quantity > 0
            for position in account.positions
        )

    closes = tuple(item.close for item in selected)
    evaluation = evaluate_moving_average_crossover_closes(
        closes,
        config,
        invested=invested,
    )
    sessions = tuple(item.session_date for item in selected)
    if len(sessions) > len(evaluation.evaluated_closes):
        sessions = sessions[-len(evaluation.evaluated_closes) :]

    return OperatorStrategyExplanationView(
        status=OperatorStrategyExplanationStatus(evaluation.status.value),
        short_window=config.short_window,
        long_window=config.long_window,
        desired_quantity=config.desired_quantity,
        symbol=symbol,
        sessions=sessions,
        closes=evaluation.evaluated_closes,
        previous_short=evaluation.previous_short,
        previous_long=evaluation.previous_long,
        current_short=evaluation.current_short,
        current_long=evaluation.current_long,
        crossover_side=(
            None
            if evaluation.crossover_side is None
            else evaluation.crossover_side.value
        ),
        actionable_side=(
            None
            if evaluation.actionable_side is None
            else evaluation.actionable_side.value
        ),
        invested=evaluation.invested,
    )
