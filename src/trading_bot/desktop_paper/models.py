"""Immutable financial models for the local simulated-paper runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from trading_bot.domain import Order, OrderFill, Position, Symbol, TradeProposal
from trading_bot.domain._validation import (
    normalize_utc,
    require_decimal,
    require_positive_decimal,
)
from trading_bot.execution import OrderEvent
from trading_bot.risk import RiskContext, RiskDecision


class PaperCycleKind(StrEnum):
    """The durable result class for one replay session."""

    WARMUP = "WARMUP"
    NO_SIGNAL = "NO_SIGNAL"
    RISK_REJECTED = "RISK_REJECTED"
    FILLED = "FILLED"
    KILL_LATCHED = "KILL_LATCHED"


@dataclass(frozen=True, slots=True)
class PaperRuntimePolicy:
    """Independent, versioned policy for local simulated paper evaluation."""

    mode: str = "SIMULATED_PAPER"
    purpose: str = "PAPER_EVALUATION"
    source_lane: str = "OPEN_REPLAY"
    starting_cash: Decimal = Decimal("100000")
    max_position_percent: Decimal = Decimal("0.20")
    max_total_exposure_percent: Decimal = Decimal("0.80")
    max_new_position_percent: Decimal = Decimal("0.20")
    minimum_cash_reserve_percent: Decimal = Decimal("0.10")
    max_order_notional: Decimal = Decimal("20000")
    allow_fractional_shares: bool = False
    allow_buying: bool = True
    allow_selling: bool = True
    estimated_commission: Decimal = Decimal("1")
    fill_commission: Decimal = Decimal("1")
    adverse_slippage_bps: Decimal = Decimal("5")
    replay_interval_seconds: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if self.mode != "SIMULATED_PAPER":
            raise ValueError("mode must be SIMULATED_PAPER")
        if self.purpose != "PAPER_EVALUATION":
            raise ValueError("purpose must be PAPER_EVALUATION")
        if self.source_lane != "OPEN_REPLAY":
            raise ValueError("source_lane must be OPEN_REPLAY")
        for name in (
            "starting_cash",
            "max_position_percent",
            "max_total_exposure_percent",
            "max_new_position_percent",
            "max_order_notional",
        ):
            require_positive_decimal(getattr(self, name), name)
        for name in (
            "minimum_cash_reserve_percent",
            "estimated_commission",
            "fill_commission",
            "adverse_slippage_bps",
            "replay_interval_seconds",
        ):
            require_decimal(getattr(self, name), name)
        for name in (
            "max_position_percent",
            "max_total_exposure_percent",
            "max_new_position_percent",
            "minimum_cash_reserve_percent",
        ):
            if getattr(self, name) > Decimal("1"):
                raise ValueError(f"{name} must be no greater than 1")
        if self.minimum_cash_reserve_percent < Decimal("0"):
            raise ValueError("minimum_cash_reserve_percent must be nonnegative")
        for name in (
            "estimated_commission",
            "fill_commission",
            "adverse_slippage_bps",
            "replay_interval_seconds",
        ):
            if getattr(self, name) < Decimal("0"):
                raise ValueError(f"{name} must be nonnegative")
        if self.adverse_slippage_bps >= Decimal("10000"):
            raise ValueError("adverse_slippage_bps must be below 10000")
        for name in ("allow_fractional_shares", "allow_buying", "allow_selling"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True, slots=True)
class PaperCycleInput:
    """One immutable source observation and the strategy's optional proposal."""

    execution_session_id: str
    execution_index: int
    symbol: Symbol
    observation_id: UUID
    completed_history_cutoff: str | None
    observation_open: Decimal
    executed_at: datetime
    proposal: TradeProposal | None = None
    no_signal_reason: str | None = None
    warmup: bool = False
    current_marks: Mapping[Symbol, Decimal] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.execution_session_id, str)
            or not self.execution_session_id.strip()
        ):
            raise ValueError("execution_session_id must be nonblank")
        if (
            not isinstance(self.execution_index, int)
            or isinstance(self.execution_index, bool)
            or self.execution_index < 1
        ):
            raise ValueError("execution_index must be a positive integer")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.observation_id, UUID):
            raise TypeError("observation_id must be a UUID")
        if self.completed_history_cutoff is not None and (
            not isinstance(self.completed_history_cutoff, str)
            or not self.completed_history_cutoff.strip()
        ):
            raise ValueError("completed_history_cutoff must be nonblank when supplied")
        require_positive_decimal(self.observation_open, "observation_open")
        object.__setattr__(
            self, "executed_at", normalize_utc(self.executed_at, "executed_at")
        )
        if not isinstance(self.warmup, bool):
            raise TypeError("warmup must be a bool")
        if self.proposal is not None:
            if not isinstance(self.proposal, TradeProposal):
                raise TypeError("proposal must be a TradeProposal or None")
            if self.proposal.symbol != self.symbol:
                raise ValueError("proposal symbol must match observation symbol")
            if self.proposal.created_at > self.executed_at:
                raise ValueError("proposal cannot be created after its execution mark")
            if self.warmup:
                raise ValueError("warmup cycles cannot contain a proposal")
            if self.no_signal_reason is not None:
                raise ValueError("proposal cycles cannot also have a no-signal reason")
        elif not self.warmup and (
            not isinstance(self.no_signal_reason, str)
            or not self.no_signal_reason.strip()
        ):
            raise ValueError("no-signal cycles require a nonblank reason")
        elif (
            self.warmup
            and self.no_signal_reason is not None
            and (
                not isinstance(self.no_signal_reason, str)
                or not self.no_signal_reason.strip()
            )
        ):
            raise ValueError("warmup reason must be nonblank when supplied")
        marks = dict(self.current_marks or {})
        if any(not isinstance(symbol, Symbol) for symbol in marks):
            raise TypeError("current_marks keys must be Symbols")
        for symbol, price in marks.items():
            require_positive_decimal(price, f"current mark for {symbol}")
        if self.symbol in marks and marks[self.symbol] != self.observation_open:
            raise ValueError(
                "current mark for the execution symbol must equal observation_open"
            )
        marks[self.symbol] = self.observation_open
        object.__setattr__(self, "current_marks", MappingProxyType(marks))


@dataclass(frozen=True, slots=True)
class PaperControlState:
    """Durable control version observed by a committed financial cycle."""

    version: int
    kill_latched: bool
    new_buys_enabled: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 0
        ):
            raise ValueError("control version must be a nonnegative integer")
        if not isinstance(self.kill_latched, bool) or not isinstance(
            self.new_buys_enabled, bool
        ):
            raise TypeError("control values must be bools")


@dataclass(frozen=True, slots=True)
class PaperAccountState:
    """Exact ledger accounting with optional complete-market valuation."""

    cash: Decimal
    positions: Mapping[Symbol, Position]
    realized_profit_loss: Decimal
    marked_equity: Decimal | None
    unrealized_profit_loss: Decimal | None
    fills: tuple[OrderFill, ...] = ()

    def __post_init__(self) -> None:
        require_decimal(self.cash, "cash")
        require_decimal(self.realized_profit_loss, "realized_profit_loss")
        if self.marked_equity is not None:
            require_positive_decimal(self.marked_equity, "marked_equity")
        if self.unrealized_profit_loss is not None:
            require_decimal(self.unrealized_profit_loss, "unrealized_profit_loss")
        copied = dict(self.positions)
        for symbol, position in copied.items():
            if (
                not isinstance(symbol, Symbol)
                or not isinstance(position, Position)
                or position.symbol != symbol
            ):
                raise TypeError("positions must map Symbols to matching Positions")
        object.__setattr__(self, "positions", MappingProxyType(copied))
        if not isinstance(self.fills, tuple):
            raise TypeError("fills must be a tuple")
        if not all(isinstance(fill, OrderFill) for fill in self.fills):
            raise TypeError("fills must contain OrderFill values")
        if (self.marked_equity is None) != (self.unrealized_profit_loss is None):
            raise ValueError(
                "equity and unrealized P&L must both be available or unavailable"
            )


@dataclass(frozen=True, slots=True)
class PaperCycleResult:
    """Complete durable readback for one cycle, including its full effect chain."""

    cycle_id: UUID
    kind: PaperCycleKind
    input: PaperCycleInput
    configuration_revision_id: UUID
    risk_context: RiskContext | None
    risk_decision: RiskDecision | None
    order: Order | None
    fill: OrderFill | None
    order_events: tuple[OrderEvent, ...]
    account: PaperAccountState
    cursor_index: int
    control: PaperControlState
    diagnostic: str | None = None

    @property
    def cycle_input(self) -> PaperCycleInput:
        """Named alias for UI/runtime callers that present the input evidence."""
        return self.input

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, UUID):
            raise TypeError("cycle_id must be a UUID")
        if not isinstance(self.kind, PaperCycleKind):
            raise TypeError("kind must be a PaperCycleKind")
        if not isinstance(self.input, PaperCycleInput):
            raise TypeError("input must be a PaperCycleInput")
        if not isinstance(self.configuration_revision_id, UUID):
            raise TypeError("configuration_revision_id must be a UUID")
        if self.risk_context is not None and not isinstance(
            self.risk_context, RiskContext
        ):
            raise TypeError("risk_context must be RiskContext or None")
        if self.risk_decision is not None and not isinstance(
            self.risk_decision, RiskDecision
        ):
            raise TypeError("risk_decision must be RiskDecision or None")
        if self.order is not None and not isinstance(self.order, Order):
            raise TypeError("order must be Order or None")
        if self.fill is not None and not isinstance(self.fill, OrderFill):
            raise TypeError("fill must be OrderFill or None")
        if not isinstance(self.order_events, tuple) or not all(
            isinstance(event, OrderEvent) for event in self.order_events
        ):
            raise TypeError("order_events must be a tuple of OrderEvent")
        if not isinstance(self.account, PaperAccountState):
            raise TypeError("account must be a PaperAccountState")
        if (
            self.kind is not PaperCycleKind.KILL_LATCHED
            and self.cursor_index != self.input.execution_index
        ):
            raise ValueError("cursor index must match the execution index")
        if not isinstance(self.control, PaperControlState):
            raise TypeError("control must be a PaperControlState")
        if self.kind is PaperCycleKind.FILLED:
            if self.risk_decision is None or self.order is None or self.fill is None:
                raise ValueError(
                    "filled cycles require a risk decision, order, and fill"
                )


@dataclass(frozen=True, slots=True)
class PaperStoreSnapshot:
    """Validated current store state returned without exposing SQLite handles."""

    account_id: UUID
    configuration_revision_id: UUID
    account: PaperAccountState
    cursor_index: int
    execution_session_id: str | None
    control: PaperControlState
    latest_result: PaperCycleResult | None

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, UUID) or not isinstance(
            self.configuration_revision_id, UUID
        ):
            raise TypeError(
                "account and configuration revision identities must be UUIDs"
            )
        if not isinstance(self.account, PaperAccountState):
            raise TypeError("account must be a PaperAccountState")
        if not isinstance(self.control, PaperControlState):
            raise TypeError("control must be a PaperControlState")
        if (
            not isinstance(self.cursor_index, int)
            or isinstance(self.cursor_index, bool)
            or self.cursor_index < 0
        ):
            raise ValueError("cursor_index must be a nonnegative integer")
        if self.cursor_index == 0 and self.execution_session_id is not None:
            raise ValueError("an empty cursor cannot have an execution session")
        if self.cursor_index > 0 and (
            not isinstance(self.execution_session_id, str)
            or not self.execution_session_id
        ):
            raise ValueError("a consumed cursor requires its execution session")
