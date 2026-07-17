"""Immutable configuration, strategy context, audit steps, and results."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from trading_bot.backtesting.exceptions import InvalidBacktestConfigError
from trading_bot.domain import Bar, Order, OrderFill, Position, Symbol, TradeProposal
from trading_bot.domain._validation import normalize_utc, require_decimal
from trading_bot.execution import OrderEvent
from trading_bot.ledger import AccountSnapshot
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import AdjustmentType, HistoricalDataRequest, Timeframe
from trading_bot.risk import RiskDecision, RiskLimits


class BacktestUnexecutedReason(StrEnum):
    END_OF_DATA = "END_OF_DATA"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Complete deterministic inputs for one single-symbol backtest run."""

    run_id: UUID
    data_request: HistoricalDataRequest
    starting_cash: Decimal = Decimal("10000.00")
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    fixed_commission: Decimal = Decimal("0")
    slippage_basis_points: Decimal = Decimal("0")
    trading_enabled: bool = True
    allow_missing_sessions: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, UUID):
            raise InvalidBacktestConfigError("run_id must be a UUID")
        if not isinstance(self.data_request, HistoricalDataRequest):
            raise InvalidBacktestConfigError(
                "data_request must be a HistoricalDataRequest"
            )
        if self.data_request.timeframe is not Timeframe.DAY_1:
            raise InvalidBacktestConfigError("only the 1D timeframe is supported")
        if self.data_request.adjustment is not AdjustmentType.RAW:
            raise InvalidBacktestConfigError("only RAW historical data is supported")
        for field_name in (
            "starting_cash",
            "fixed_commission",
            "slippage_basis_points",
        ):
            try:
                require_decimal(getattr(self, field_name), field_name)
            except TypeError as error:
                raise InvalidBacktestConfigError(str(error)) from error
        if self.starting_cash <= Decimal("0"):
            raise InvalidBacktestConfigError("starting_cash must be greater than zero")
        if self.fixed_commission < Decimal("0"):
            raise InvalidBacktestConfigError("fixed_commission must be zero or greater")
        if not Decimal("0") <= self.slippage_basis_points < Decimal("10000"):
            raise InvalidBacktestConfigError(
                "slippage_basis_points must be between 0 and 10000"
            )
        if not isinstance(self.risk_limits, RiskLimits):
            raise InvalidBacktestConfigError("risk_limits must be RiskLimits")
        if self.risk_limits.estimated_commission != self.fixed_commission:
            raise InvalidBacktestConfigError(
                "risk estimated_commission must equal fixed_commission"
            )
        for field_name in ("trading_enabled", "allow_missing_sessions"):
            if not isinstance(getattr(self, field_name), bool):
                raise InvalidBacktestConfigError(f"{field_name} must be a bool")


@dataclass(frozen=True, slots=True)
class BacktestContext:
    """Point-in-time strategy input containing no future market information."""

    run_id: UUID
    step_index: int
    session: TradingSession
    current_bar: Bar
    history: tuple[Bar, ...]
    account_snapshot: AccountSnapshot
    positions: Mapping[Symbol, Position]

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, UUID):
            raise TypeError("run_id must be a UUID")
        if not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index must be a nonnegative integer")
        if not isinstance(self.session, TradingSession):
            raise TypeError("session must be a TradingSession")
        if not isinstance(self.current_bar, Bar):
            raise TypeError("current_bar must be a Bar")
        history = tuple(self.history)
        if not history or history[-1] != self.current_bar:
            raise ValueError("history must be nonempty and end with current_bar")
        if not isinstance(self.account_snapshot, AccountSnapshot):
            raise TypeError("account_snapshot must be an AccountSnapshot")
        copied_positions = dict(self.positions)
        if not all(
            isinstance(symbol, Symbol)
            and isinstance(position, Position)
            and position.symbol == symbol
            for symbol, position in copied_positions.items()
        ):
            raise TypeError("positions must map symbols to matching Position values")
        object.__setattr__(self, "history", history)
        object.__setattr__(self, "positions", MappingProxyType(copied_positions))


@dataclass(frozen=True, slots=True)
class BacktestStep:
    """One session's actions in their deterministic audit order."""

    step_index: int
    session: TradingSession
    bar: Bar
    opening_fill: OrderFill | None
    account_snapshot: AccountSnapshot
    proposal: TradeProposal | None
    risk_decision: RiskDecision | None
    submitted_order: Order | None
    unexecuted_reason: BacktestUnexecutedReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index must be a nonnegative integer")
        if not isinstance(self.session, TradingSession):
            raise TypeError("session must be a TradingSession")
        if not isinstance(self.bar, Bar):
            raise TypeError("bar must be a Bar")
        if not isinstance(self.account_snapshot, AccountSnapshot):
            raise TypeError("account_snapshot must be an AccountSnapshot")
        if self.proposal is None and self.risk_decision is not None:
            raise ValueError("a risk decision requires a proposal")
        if (
            self.risk_decision is not None
            and self.risk_decision.proposal != self.proposal
        ):
            raise ValueError("risk decision must reference the step proposal")
        if self.submitted_order is not None:
            if self.risk_decision is None:
                raise ValueError("a submitted order requires a risk decision")
            if self.submitted_order.status.value != "SUBMITTED":
                raise ValueError("submitted_order must have SUBMITTED status")
        if self.unexecuted_reason is not None and self.submitted_order is not None:
            raise ValueError("an unexecuted proposal cannot have a submitted order")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Immutable audit output from a completed backtest."""

    config: BacktestConfig
    provider_name: str
    bars: tuple[Bar, ...]
    steps: tuple[BacktestStep, ...]
    proposals: tuple[TradeProposal, ...]
    risk_decisions: tuple[RiskDecision, ...]
    orders: tuple[Order, ...]
    order_events: tuple[OrderEvent, ...]
    fills: tuple[OrderFill, ...]
    account_snapshots: tuple[AccountSnapshot, ...]
    final_positions: Mapping[Symbol, Position]
    final_equity: Decimal
    unexecuted_final_bar_proposals: tuple[TradeProposal, ...]
    start_timestamp: datetime
    end_timestamp: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "bars",
            "steps",
            "proposals",
            "risk_decisions",
            "orders",
            "order_events",
            "fills",
            "account_snapshots",
            "unexecuted_final_bar_proposals",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.bars or not self.steps:
            raise ValueError("completed backtests require bars and steps")
        if len(self.bars) != len(self.steps):
            raise ValueError("there must be exactly one step per bar")
        if len(self.account_snapshots) != len(self.bars):
            raise ValueError("there must be exactly one account snapshot per bar")
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name must be nonblank")
        require_decimal(self.final_equity, "final_equity")
        if self.final_equity != self.account_snapshots[-1].equity:
            raise ValueError("final_equity must equal the final account snapshot")
        positions = dict(self.final_positions)
        object.__setattr__(self, "final_positions", MappingProxyType(positions))
        start = normalize_utc(self.start_timestamp, "start_timestamp")
        end = normalize_utc(self.end_timestamp, "end_timestamp")
        if start != self.bars[0].timestamp or end != self.bars[-1].timestamp:
            raise ValueError("result timestamps must match the first and last bars")
        object.__setattr__(self, "start_timestamp", start)
        object.__setattr__(self, "end_timestamp", end)
