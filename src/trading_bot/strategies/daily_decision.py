"""Shared pure daily strategy evaluation; no runtime or execution authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from types import MappingProxyType
from uuid import UUID

from trading_bot.backtesting import BacktestContext
from trading_bot.domain import Bar, Position, Symbol, TradeProposal
from trading_bot.ledger import AccountSnapshot, CompactPaperLedgerState
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import DailySnapshotBar, DailySnapshotVerificationResult
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)
from trading_bot.strategies.history_seed import VerifiedStrategyHistorySeed

_ARITHMETIC_CONTEXT = Context(prec=1024, Emax=999_999, Emin=-999_999)
_ZERO = Decimal("0")


class DailyStrategyDecisionError(ValueError):
    """An account cannot supply the shared deterministic strategy context."""


@dataclass(frozen=True, slots=True)
class PreparedCurrentStrategyDecision:
    """Non-authorizing current-product evidence, with no legacy lineage fields."""

    snapshot_verification: DailySnapshotVerificationResult
    history_seed: VerifiedStrategyHistorySeed
    prior_state: CompactPaperLedgerState
    durable_fill_ids: tuple[UUID, ...]
    strategy_config: MovingAverageCrossoverConfig
    symbol: Symbol
    selected_session: TradingSession
    intended_execution_session: TradingSession
    strategy_run_id: UUID
    strategy_step_index: int
    strategy_proposal: TradeProposal | None
    account_positions: tuple[Position, ...]
    planning_at: datetime
    caller_idempotency_key: str
    max_snapshot_age: timedelta

    def __post_init__(self) -> None:
        if type(self.strategy_config) is not MovingAverageCrossoverConfig:
            raise TypeError("strategy_config must be exact")
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be exact")
        if type(self.snapshot_verification) is not DailySnapshotVerificationResult:
            raise TypeError("snapshot_verification must be exact")
        if type(self.history_seed) is not VerifiedStrategyHistorySeed:
            raise TypeError("history_seed must be exact")
        if type(self.prior_state) is not CompactPaperLedgerState:
            raise TypeError("prior_state must be exact")
        if (
            type(self.durable_fill_ids) is not tuple
            or any(type(item) is not UUID for item in self.durable_fill_ids)
            or len(set(self.durable_fill_ids)) != len(self.durable_fill_ids)
            or type(self.strategy_step_index) is not int
            or self.strategy_step_index != len(self.durable_fill_ids)
            or type(self.strategy_run_id) is not UUID
        ):
            raise ValueError("strategy context must match durable history")
        if (
            type(self.selected_session) is not TradingSession
            or type(self.intended_execution_session) is not TradingSession
            or self.intended_execution_session <= self.selected_session
            or self.history_seed.target_session != self.selected_session
            or self.history_seed.seed.symbol != self.symbol
            or self.history_seed.strategy_config != self.strategy_config
        ):
            raise ValueError("prepared market evidence does not reconcile")
        if (
            type(self.account_positions) is not tuple
            or any(type(item) is not Position for item in self.account_positions)
            or tuple((item.symbol, item.quantity) for item in self.account_positions)
            != tuple(
                (item.symbol, item.quantity) for item in self.prior_state.positions
            )
            or type(self.planning_at) is not datetime
            or self.planning_at.tzinfo is not UTC
            or self.planning_at != self.prior_state.as_of
            or type(self.caller_idempotency_key) is not str
            or not self.caller_idempotency_key
            or type(self.max_snapshot_age) is not timedelta
            or self.max_snapshot_age <= timedelta(0)
        ):
            raise ValueError("prepared account/timing/policy evidence is inconsistent")
        if self.strategy_proposal is not None and (
            type(self.strategy_proposal) is not TradeProposal
            or self.strategy_proposal.symbol != self.symbol
        ):
            raise ValueError("prepared proposal must match symbol")


def evaluate_daily_strategy_decision(
    *,
    run_id: UUID,
    step_index: int,
    current_bar: Bar,
    target_session: TradingSession,
    seed_bars: tuple[DailySnapshotBar, ...],
    compact: CompactPaperLedgerState,
    strategy_config: MovingAverageCrossoverConfig,
    account_positions: tuple[Position, ...] | None = None,
) -> TradeProposal | None:
    """Enter the retained Architecture-94 context and evaluate exactly once."""
    context = _strategy_context(
        run_id,
        step_index,
        current_bar,
        target_session,
        seed_bars,
        compact,
        account_positions,
    )
    return MovingAverageCrossoverStrategy(strategy_config).evaluate(context)


def _strategy_context(
    run_id: UUID,
    step_index: int,
    current_bar: Bar,
    target_session: TradingSession,
    seed_bars: tuple[DailySnapshotBar, ...],
    compact: CompactPaperLedgerState,
    account_positions: tuple[Position, ...] | None = None,
) -> BacktestContext:
    retained_positions = (
        tuple(
            Position(item.symbol, item.quantity, item.average_cost)
            for item in compact.positions
        )
        if account_positions is None
        else account_positions
    )
    if tuple((item.symbol, item.quantity) for item in retained_positions) != tuple(
        (item.symbol, item.quantity) for item in compact.positions
    ):
        raise DailyStrategyDecisionError(
            "marked positions disagree with compact accounting"
        )
    positions = {item.symbol: item for item in retained_positions}
    with localcontext(_ARITHMETIC_CONTEXT):
        market_value = sum(
            (item.quantity * current_bar.close for item in retained_positions),
            start=_ZERO,
        )
        unrealized = sum(
            (
                (current_bar.close - item.average_cost) * item.quantity
                for item in retained_positions
            ),
            start=_ZERO,
        )
        equity = compact.cash + market_value
    if equity <= _ZERO:
        raise DailyStrategyDecisionError(
            "verified marked account equity must be positive"
        )
    account = AccountSnapshot(
        current_bar.timestamp,
        compact.cash,
        market_value,
        equity,
        compact.cash,
        compact.realized_profit_loss,
        unrealized,
    )
    history = tuple(item.bar for item in seed_bars) + (current_bar,)
    return BacktestContext(
        run_id,
        step_index,
        target_session,
        current_bar,
        history,
        account,
        MappingProxyType(positions),
    )
