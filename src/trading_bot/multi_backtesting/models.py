"""Immutable models for deterministic multi-symbol backtests."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from trading_bot.domain import (
    Order,
    OrderFill,
    OrderStatus,
    Position,
    Symbol,
    TradeProposal,
)
from trading_bot.domain._validation import normalize_utc, require_decimal
from trading_bot.execution import OrderEvent
from trading_bot.ledger import AccountSnapshot
from trading_bot.market_data import (
    AdjustmentType,
    AlignedMarketFrame,
    MultiSymbolHistoricalDataRequest,
    Timeframe,
)
from trading_bot.multi_backtesting.exceptions import (
    InvalidMultiSymbolBacktestConfigError,
)
from trading_bot.risk import RiskDecision, RiskLimits, RiskOutcome


class MultiSymbolUnexecutedReason(StrEnum):
    END_OF_DATA = "END_OF_DATA"


@dataclass(frozen=True, slots=True)
class MultiSymbolBacktestConfig:
    run_id: UUID
    data_request: MultiSymbolHistoricalDataRequest
    starting_cash: Decimal = Decimal("10000")
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    fixed_commission: Decimal = Decimal("0")
    slippage_basis_points: Decimal = Decimal("0")
    trading_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, UUID):
            raise InvalidMultiSymbolBacktestConfigError("run_id must be a UUID")
        if not isinstance(self.data_request, MultiSymbolHistoricalDataRequest):
            raise InvalidMultiSymbolBacktestConfigError(
                "data_request must be a MultiSymbolHistoricalDataRequest"
            )
        if self.data_request.timeframe is not Timeframe.DAY_1:
            raise InvalidMultiSymbolBacktestConfigError("only 1D data is supported")
        if self.data_request.adjustment is not AdjustmentType.RAW:
            raise InvalidMultiSymbolBacktestConfigError("only RAW data is supported")
        for name in ("starting_cash", "fixed_commission", "slippage_basis_points"):
            try:
                require_decimal(getattr(self, name), name)
            except TypeError as error:
                raise InvalidMultiSymbolBacktestConfigError(str(error)) from error
        if self.starting_cash <= 0:
            raise InvalidMultiSymbolBacktestConfigError(
                "starting_cash must be positive"
            )
        if self.fixed_commission < 0:
            raise InvalidMultiSymbolBacktestConfigError(
                "fixed_commission must be nonnegative"
            )
        if not Decimal("0") <= self.slippage_basis_points < Decimal("10000"):
            raise InvalidMultiSymbolBacktestConfigError(
                "slippage_basis_points must be between 0 and 10000"
            )
        if not isinstance(self.risk_limits, RiskLimits):
            raise InvalidMultiSymbolBacktestConfigError(
                "risk_limits must be RiskLimits"
            )
        if self.risk_limits.estimated_commission != self.fixed_commission:
            raise InvalidMultiSymbolBacktestConfigError(
                "risk estimated_commission must equal fixed_commission"
            )
        if not isinstance(self.trading_enabled, bool):
            raise InvalidMultiSymbolBacktestConfigError("trading_enabled must be bool")


@dataclass(frozen=True, slots=True)
class MultiSymbolStrategyContext:
    run_id: UUID
    step_index: int
    timestamp: datetime
    symbols: tuple[Symbol, ...]
    current_frame: AlignedMarketFrame
    history: tuple[AlignedMarketFrame, ...]
    account_snapshot: AccountSnapshot
    positions: Mapping[Symbol, Position]
    active_orders: tuple[Order, ...]

    def __post_init__(self) -> None:
        timestamp = normalize_utc(self.timestamp, "timestamp")
        symbols = tuple(self.symbols)
        history = tuple(self.history)
        positions_source = dict(self.positions)
        positions = {
            symbol: positions_source[symbol]
            for symbol in symbols
            if symbol in positions_source
        }
        active_orders = tuple(self.active_orders)
        if self.current_frame.timestamp != timestamp:
            raise ValueError("current_frame timestamp must match timestamp")
        if not history or history[-1] != self.current_frame:
            raise ValueError("history must end with current_frame")
        if not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index must be a nonnegative integer")
        if any(
            order.status
            not in {
                OrderStatus.PENDING,
                OrderStatus.SUBMITTED,
                OrderStatus.PARTIALLY_FILLED,
            }
            for order in active_orders
        ):
            raise ValueError("active_orders must contain only active orders")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "history", history)
        object.__setattr__(self, "positions", MappingProxyType(positions))
        object.__setattr__(self, "active_orders", active_orders)


@dataclass(frozen=True, slots=True)
class UnexecutedProposal:
    proposal: TradeProposal
    risk_decision: RiskDecision
    reason: MultiSymbolUnexecutedReason

    def __post_init__(self) -> None:
        if self.risk_decision.proposal != self.proposal:
            raise ValueError("risk_decision must reference proposal")
        if self.risk_decision.outcome is RiskOutcome.REJECTED:
            raise ValueError("rejected decisions are not unexecuted proposals")


@dataclass(frozen=True, slots=True)
class MultiSymbolBacktestStep:
    step_index: int
    frame: AlignedMarketFrame
    opening_fills: tuple[OrderFill, ...]
    account_snapshot: AccountSnapshot
    proposals: tuple[TradeProposal, ...]
    risk_decisions: tuple[RiskDecision, ...]
    submitted_orders: tuple[Order, ...]
    unexecuted_proposals: tuple[UnexecutedProposal, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "opening_fills",
            "proposals",
            "risk_decisions",
            "submitted_orders",
            "unexecuted_proposals",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if len(self.proposals) != len(self.risk_decisions):
            raise ValueError("every proposal must have one risk decision")
        if any(
            decision.proposal != proposal
            for proposal, decision in zip(
                self.proposals, self.risk_decisions, strict=True
            )
        ):
            raise ValueError("risk decision order must match proposals")


@dataclass(frozen=True, slots=True)
class MultiSymbolBacktestResult:
    config: MultiSymbolBacktestConfig
    provider_name: str
    frames: tuple[AlignedMarketFrame, ...]
    steps: tuple[MultiSymbolBacktestStep, ...]
    proposals: tuple[TradeProposal, ...]
    risk_decisions: tuple[RiskDecision, ...]
    final_orders: tuple[Order, ...]
    order_events: tuple[OrderEvent, ...]
    fills: tuple[OrderFill, ...]
    account_snapshots: tuple[AccountSnapshot, ...]
    final_positions: Mapping[Symbol, Position]
    final_equity: Decimal
    unexecuted_proposals: tuple[UnexecutedProposal, ...]
    start_timestamp: datetime
    end_timestamp: datetime

    def __post_init__(self) -> None:
        for name in (
            "frames",
            "steps",
            "proposals",
            "risk_decisions",
            "final_orders",
            "order_events",
            "fills",
            "account_snapshots",
            "unexecuted_proposals",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not self.frames or len(self.frames) != len(self.steps):
            raise ValueError("result requires one step per frame")
        if len(self.account_snapshots) != len(self.frames):
            raise ValueError("result requires one snapshot per frame")
        if self.final_equity != self.account_snapshots[-1].equity:
            raise ValueError("final_equity must equal final snapshot equity")
        source = dict(self.final_positions)
        ordered = {
            symbol: source[symbol]
            for symbol in self.config.data_request.symbols
            if symbol in source
        }
        object.__setattr__(self, "final_positions", MappingProxyType(ordered))
        object.__setattr__(
            self,
            "start_timestamp",
            normalize_utc(self.start_timestamp, "start_timestamp"),
        )
        object.__setattr__(
            self, "end_timestamp", normalize_utc(self.end_timestamp, "end_timestamp")
        )
        if self.start_timestamp != self.frames[0].timestamp:
            raise ValueError("start_timestamp must equal the first frame timestamp")
        if self.end_timestamp != self.frames[-1].timestamp:
            raise ValueError("end_timestamp must equal the final frame timestamp")

    @property
    def final_cash(self) -> Decimal:
        return self.account_snapshots[-1].cash

    @property
    def final_realized_profit_loss(self) -> Decimal:
        return self.account_snapshots[-1].realized_profit_loss
