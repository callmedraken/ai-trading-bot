"""Deterministic performance analytics for optimized paper simulations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from trading_bot.analytics import DrawdownAnalysis, DrawdownRecord
from trading_bot.domain import OrderSide, Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution.state_fingerprints import canonical_decimal
from trading_bot.portfolio import MetadataEntry, OptimizationStatus
from trading_bot.portfolio_analytics.exceptions import (
    InconsistentOptimizedSimulationPerformanceResultError,
    InvalidOptimizedSimulationPerformanceRequestError,
    OptimizedSimulationPerformanceReconciliationError,
    OptimizedSimulationValuationError,
)
from trading_bot.risk import RiskOutcome
from trading_bot.runtime import PaperPortfolioCycleStatus

if TYPE_CHECKING:
    from trading_bot.simulation.optimized_paper_portfolio import (
        OptimizedPaperSimulationResult,
    )

_ZERO = Decimal("0")
_ONE = Decimal("1")
_VERSION = "optimized-simulation-performance-v1"
_NAMESPACE = UUID("dfeaacff-681f-5bc9-87c7-02551052880d")
_RESERVED_PREFIX = "optimized_simulation_performance_"


def _finite(value: Decimal, name: str, error_type: type[ValueError]) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise error_type(f"{name} must be a finite Decimal")
    return _ZERO if value == _ZERO else value


def _count(value: int, name: str, error_type: type[ValueError]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise error_type(f"{name} must be a nonnegative integer")


class OptimizedSimulationValuationBasis(StrEnum):
    """Supported price source for portfolio valuation."""

    FRAME_RISK_PRICES = "FRAME_RISK_PRICES"


@dataclass(frozen=True, slots=True)
class OptimizedSimulationValuationPolicy:
    """Explicit valuation policy for optimized-simulation analytics."""

    valuation_basis: OptimizedSimulationValuationBasis = (
        OptimizedSimulationValuationBasis.FRAME_RISK_PRICES
    )

    def __post_init__(self) -> None:
        if (
            self.valuation_basis
            is not OptimizedSimulationValuationBasis.FRAME_RISK_PRICES
        ):
            raise InvalidOptimizedSimulationPerformanceRequestError(
                "only FRAME_RISK_PRICES valuation is supported"
            )


@dataclass(frozen=True, slots=True)
class OptimizedSimulationPerformanceRequest:
    """One traceable request to analyze an immutable simulation result."""

    request_id: UUID
    simulation_result: OptimizedPaperSimulationResult
    valuation_policy: OptimizedSimulationValuationPolicy = (
        OptimizedSimulationValuationPolicy()
    )
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        from trading_bot.simulation.optimized_paper_portfolio import (
            OptimizedPaperSimulationResult,
        )

        error = InvalidOptimizedSimulationPerformanceRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.simulation_result, OptimizedPaperSimulationResult):
            raise error("simulation_result must be an OptimizedPaperSimulationResult")
        if not isinstance(self.valuation_policy, OptimizedSimulationValuationPolicy):
            raise error("valuation_policy must be OptimizedSimulationValuationPolicy")
        if (
            self.valuation_policy.valuation_basis
            is not OptimizedSimulationValuationBasis.FRAME_RISK_PRICES
        ):
            raise error("valuation policy contains an unsupported basis")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error(f"{_RESERVED_PREFIX} metadata keys are reserved")
        object.__setattr__(self, "metadata", metadata)


class OptimizedSimulationEquityPhase(StrEnum):
    PRE_CYCLE = "PRE_CYCLE"
    POST_CYCLE = "POST_CYCLE"


@dataclass(frozen=True, slots=True)
class OptimizedSimulationEquityObservation:
    sequence_index: int
    frame_ordinal: int
    phase: OptimizedSimulationEquityPhase
    timestamp: datetime
    equity: Decimal
    running_peak: Decimal
    drawdown_amount: Decimal
    drawdown_percentage: Decimal

    def __post_init__(self) -> None:
        error = InconsistentOptimizedSimulationPerformanceResultError
        _count(self.sequence_index, "sequence_index", error)
        _count(self.frame_ordinal, "frame_ordinal", error)
        if not isinstance(self.phase, OptimizedSimulationEquityPhase):
            raise error("phase must be OptimizedSimulationEquityPhase")
        try:
            timestamp = normalize_utc(self.timestamp, "timestamp")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        for name in (
            "equity",
            "running_peak",
            "drawdown_amount",
            "drawdown_percentage",
        ):
            _finite(getattr(self, name), name, error)
        if self.equity <= _ZERO or self.running_peak <= _ZERO:
            raise error("observation equity and running peak must be positive")
        if self.running_peak < self.equity:
            raise error("running peak cannot be below equity")
        if self.drawdown_amount != self.running_peak - self.equity:
            raise error("drawdown amount does not reconcile")
        if self.drawdown_percentage != self.drawdown_amount / self.running_peak:
            raise error("drawdown percentage does not reconcile")
        object.__setattr__(self, "timestamp", timestamp)


@dataclass(frozen=True, slots=True)
class OptimizedSimulationAllocationDrift:
    symbol: Symbol
    target_weight: Decimal
    actual_weight: Decimal
    drift: Decimal
    absolute_drift: Decimal

    def __post_init__(self) -> None:
        error = InconsistentOptimizedSimulationPerformanceResultError
        if not isinstance(self.symbol, Symbol):
            raise error("allocation drift symbol must be a Symbol")
        for name in ("target_weight", "actual_weight", "drift", "absolute_drift"):
            _finite(getattr(self, name), name, error)
        if self.target_weight < _ZERO or self.actual_weight < _ZERO:
            raise error("allocation weights must be nonnegative")
        if self.drift != self.actual_weight - self.target_weight:
            raise error("allocation drift does not reconcile")
        if self.absolute_drift != abs(self.drift):
            raise error("absolute allocation drift does not reconcile")


@dataclass(frozen=True, slots=True)
class OptimizedSimulationOptimizationSummary:
    mean_expected_portfolio_return: Decimal
    worst_cvar: Decimal
    minimum_target_cash_weight: Decimal
    maximum_target_cash_weight: Decimal

    def __post_init__(self) -> None:
        error = InconsistentOptimizedSimulationPerformanceResultError
        for name in (
            "mean_expected_portfolio_return",
            "worst_cvar",
            "minimum_target_cash_weight",
            "maximum_target_cash_weight",
        ):
            _finite(getattr(self, name), name, error)
        if not (
            _ZERO
            <= self.minimum_target_cash_weight
            <= self.maximum_target_cash_weight
            <= _ONE
        ):
            raise error("target cash weight extrema are invalid")


class OptimizedSimulationPerformanceDiagnosticCode(StrEnum):
    NO_TRADING_ACTIVITY = "NO_TRADING_ACTIVITY"
    ALL_CYCLES_NO_ACTION = "ALL_CYCLES_NO_ACTION"


@dataclass(frozen=True, slots=True)
class OptimizedSimulationPerformanceDiagnostic:
    code: OptimizedSimulationPerformanceDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, OptimizedSimulationPerformanceDiagnosticCode):
            raise InconsistentOptimizedSimulationPerformanceResultError(
                "diagnostic code has an invalid type"
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise InconsistentOptimizedSimulationPerformanceResultError(
                "diagnostic message must be nonblank"
            )


@dataclass(frozen=True, slots=True)
class OptimizedSimulationFramePerformance:
    frame_id: UUID
    frame_ordinal: int
    source_cycle_result_id: UUID
    as_of: datetime
    filled_at: datetime
    pre_cycle_equity: Decimal
    post_cycle_equity: Decimal
    execution_profit_loss: Decimal
    forward_market_profit_loss: Decimal | None
    period_profit_loss: Decimal
    period_return: Decimal
    cumulative_return: Decimal
    cumulative_simulation_profit_loss: Decimal
    pre_cycle_cash: Decimal
    post_cycle_cash: Decimal
    pre_cycle_gross_exposure: Decimal
    post_cycle_gross_exposure: Decimal
    pre_cycle_net_exposure: Decimal
    post_cycle_net_exposure: Decimal
    pre_cycle_position_count: int
    post_cycle_position_count: int
    frame_simulation_realized_profit_loss: Decimal
    cumulative_simulation_realized_profit_loss: Decimal
    pre_cycle_unrealized_profit_loss: Decimal
    post_cycle_unrealized_profit_loss: Decimal
    unrealized_profit_loss_change: Decimal
    gross_buy_notional: Decimal
    gross_sell_notional: Decimal
    gross_traded_notional: Decimal
    net_buy_notional: Decimal
    one_way_turnover: Decimal
    two_way_turnover: Decimal
    commission_cost: Decimal
    signed_slippage_profit_loss: Decimal
    adverse_slippage_cost: Decimal
    total_execution_cost: Decimal
    order_count: int
    fill_count: int
    approved_risk_count: int
    resized_risk_count: int
    rejected_risk_count: int
    rejected_notional: Decimal
    reduced_notional: Decimal
    optimization_status: OptimizationStatus
    solver_name: str
    expected_portfolio_return: Decimal
    cvar: Decimal
    objective_value: Decimal
    target_cash_weight: Decimal
    target_allocation_count: int
    allocation_drifts: tuple[OptimizedSimulationAllocationDrift, ...]
    actual_cash_weight: Decimal
    cash_weight_drift: Decimal
    absolute_cash_weight_drift: Decimal
    maximum_absolute_allocation_drift: Decimal
    total_absolute_allocation_drift: Decimal

    def __post_init__(self) -> None:
        error = InconsistentOptimizedSimulationPerformanceResultError
        if not isinstance(self.frame_id, UUID) or not isinstance(
            self.source_cycle_result_id, UUID
        ):
            raise error("frame and source cycle IDs must be UUID values")
        _count(self.frame_ordinal, "frame_ordinal", error)
        try:
            as_of = normalize_utc(self.as_of, "as_of")
            filled_at = normalize_utc(self.filled_at, "filled_at")
        except (TypeError, ValueError) as caught:
            raise error(str(caught)) from caught
        if filled_at < as_of:
            raise error("filled_at cannot precede as_of")
        for name in _FRAME_DECIMAL_FIELDS:
            value = getattr(self, name)
            if value is not None:
                _finite(value, name, error)
        for name in _FRAME_COUNT_FIELDS:
            _count(getattr(self, name), name, error)
        if self.pre_cycle_equity <= _ZERO or self.post_cycle_equity <= _ZERO:
            raise error("frame equity values must be positive")
        for name in (
            "pre_cycle_cash",
            "post_cycle_cash",
            "pre_cycle_gross_exposure",
            "post_cycle_gross_exposure",
            "pre_cycle_net_exposure",
            "post_cycle_net_exposure",
            "gross_buy_notional",
            "gross_sell_notional",
            "gross_traded_notional",
            "one_way_turnover",
            "two_way_turnover",
            "commission_cost",
            "adverse_slippage_cost",
            "total_execution_cost",
            "rejected_notional",
            "reduced_notional",
        ):
            if getattr(self, name) < _ZERO:
                raise error(f"{name} must be nonnegative")
        if not isinstance(self.optimization_status, OptimizationStatus):
            raise error("optimization_status must be OptimizationStatus")
        if not isinstance(self.solver_name, str) or not self.solver_name.strip():
            raise error("solver_name must be nonblank")
        try:
            drifts = tuple(self.allocation_drifts)
        except TypeError as caught:
            raise error("allocation_drifts must be iterable") from caught
        if not drifts or not all(
            isinstance(item, OptimizedSimulationAllocationDrift) for item in drifts
        ):
            raise error("allocation_drifts must contain drift records")
        if len({item.symbol for item in drifts}) != len(drifts):
            raise error("allocation drift symbols must be unique")
        if self.gross_traded_notional != (
            self.gross_buy_notional + self.gross_sell_notional
        ) or self.net_buy_notional != (
            self.gross_buy_notional - self.gross_sell_notional
        ):
            raise error("trading notionals do not reconcile")
        if self.execution_profit_loss != (
            self.post_cycle_equity - self.pre_cycle_equity
        ):
            raise error("execution P&L must equal post equity minus pre equity")
        if (
            self.pre_cycle_net_exposure != self.pre_cycle_equity - self.pre_cycle_cash
            or self.post_cycle_net_exposure
            != self.post_cycle_equity - self.post_cycle_cash
            or self.pre_cycle_gross_exposure < abs(self.pre_cycle_net_exposure)
            or self.post_cycle_gross_exposure < abs(self.post_cycle_net_exposure)
        ):
            raise error("frame cash and exposure values do not reconcile")
        if self.one_way_turnover != (
            max(self.gross_buy_notional, self.gross_sell_notional)
            / self.pre_cycle_equity
        ) or self.two_way_turnover != (
            self.gross_traded_notional / self.pre_cycle_equity
        ):
            raise error("frame turnover values do not reconcile")
        if self.total_execution_cost != (
            self.commission_cost + self.adverse_slippage_cost
        ):
            raise error("execution costs do not reconcile")
        if (
            self.order_count != self.fill_count
            or self.order_count != self.approved_risk_count + self.resized_risk_count
            or self.target_allocation_count != len(drifts)
        ):
            raise error("frame trading or allocation counts do not reconcile")
        if self.unrealized_profit_loss_change != (
            self.post_cycle_unrealized_profit_loss
            - self.pre_cycle_unrealized_profit_loss
        ):
            raise error("unrealized P&L change does not reconcile")
        if self.cash_weight_drift != self.actual_cash_weight - self.target_cash_weight:
            raise error("cash weight drift does not reconcile")
        if self.absolute_cash_weight_drift != abs(self.cash_weight_drift):
            raise error("absolute cash drift does not reconcile")
        expected_max = max(
            (self.absolute_cash_weight_drift, *(item.absolute_drift for item in drifts))
        )
        expected_total = self.absolute_cash_weight_drift + sum(
            (item.absolute_drift for item in drifts), start=_ZERO
        )
        if (
            self.maximum_absolute_allocation_drift != expected_max
            or self.total_absolute_allocation_drift != expected_total
        ):
            raise error("allocation drift summaries do not reconcile")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "filled_at", filled_at)
        object.__setattr__(self, "allocation_drifts", drifts)


_FRAME_DECIMAL_FIELDS = (
    "pre_cycle_equity",
    "post_cycle_equity",
    "execution_profit_loss",
    "forward_market_profit_loss",
    "period_profit_loss",
    "period_return",
    "cumulative_return",
    "cumulative_simulation_profit_loss",
    "pre_cycle_cash",
    "post_cycle_cash",
    "pre_cycle_gross_exposure",
    "post_cycle_gross_exposure",
    "pre_cycle_net_exposure",
    "post_cycle_net_exposure",
    "frame_simulation_realized_profit_loss",
    "cumulative_simulation_realized_profit_loss",
    "pre_cycle_unrealized_profit_loss",
    "post_cycle_unrealized_profit_loss",
    "unrealized_profit_loss_change",
    "gross_buy_notional",
    "gross_sell_notional",
    "gross_traded_notional",
    "net_buy_notional",
    "one_way_turnover",
    "two_way_turnover",
    "commission_cost",
    "signed_slippage_profit_loss",
    "adverse_slippage_cost",
    "total_execution_cost",
    "rejected_notional",
    "reduced_notional",
    "expected_portfolio_return",
    "cvar",
    "objective_value",
    "target_cash_weight",
    "actual_cash_weight",
    "cash_weight_drift",
    "absolute_cash_weight_drift",
    "maximum_absolute_allocation_drift",
    "total_absolute_allocation_drift",
)

_FRAME_COUNT_FIELDS = (
    "pre_cycle_position_count",
    "post_cycle_position_count",
    "order_count",
    "fill_count",
    "approved_risk_count",
    "resized_risk_count",
    "rejected_risk_count",
    "target_allocation_count",
)


@dataclass(frozen=True, slots=True)
class OptimizedSimulationPerformanceResult:
    result_id: UUID
    request: OptimizedSimulationPerformanceRequest
    frames: tuple[OptimizedSimulationFramePerformance, ...]
    equity_observations: tuple[OptimizedSimulationEquityObservation, ...]
    drawdowns: DrawdownAnalysis
    initial_equity: Decimal
    final_equity: Decimal
    absolute_simulation_profit_loss: Decimal
    simulation_return: Decimal
    initial_unrealized_profit_loss: Decimal
    final_unrealized_profit_loss: Decimal
    cumulative_simulation_realized_profit_loss: Decimal
    total_gross_buy_notional: Decimal
    total_gross_sell_notional: Decimal
    total_gross_traded_notional: Decimal
    total_net_buy_notional: Decimal
    aggregate_one_way_turnover: Decimal
    aggregate_two_way_turnover: Decimal
    total_commissions: Decimal
    total_signed_slippage_profit_loss: Decimal
    total_adverse_slippage_cost: Decimal
    total_execution_cost: Decimal
    total_order_count: int
    total_fill_count: int
    total_approved_risk_count: int
    total_resized_risk_count: int
    total_rejected_risk_count: int
    total_rejected_notional: Decimal
    total_reduced_notional: Decimal
    applied_cycle_count: int
    no_action_cycle_count: int
    optimization_summary: OptimizedSimulationOptimizationSummary
    maximum_absolute_allocation_drift: Decimal
    total_absolute_allocation_drift: Decimal
    diagnostics: tuple[OptimizedSimulationPerformanceDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        error = InconsistentOptimizedSimulationPerformanceResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, OptimizedSimulationPerformanceRequest):
            raise error("request must be OptimizedSimulationPerformanceRequest")
        try:
            frames = tuple(self.frames)
            observations = tuple(self.equity_observations)
            diagnostics = tuple(self.diagnostics)
        except TypeError as caught:
            raise error("result collections must be iterable") from caught
        if not frames or not all(
            isinstance(item, OptimizedSimulationFramePerformance) for item in frames
        ):
            raise error("frames must contain performance records")
        if tuple(item.frame_ordinal for item in frames) != tuple(range(len(frames))):
            raise error("frame ordinals must be sequential")
        if len(observations) != len(frames) * 2 or not all(
            isinstance(item, OptimizedSimulationEquityObservation)
            for item in observations
        ):
            raise error("equity observations must contain two records per frame")
        for ordinal, frame in enumerate(frames):
            pre, post = observations[ordinal * 2 : ordinal * 2 + 2]
            if (
                pre.sequence_index != ordinal * 2
                or post.sequence_index != ordinal * 2 + 1
                or pre.frame_ordinal != ordinal
                or post.frame_ordinal != ordinal
                or pre.phase is not OptimizedSimulationEquityPhase.PRE_CYCLE
                or post.phase is not OptimizedSimulationEquityPhase.POST_CYCLE
                or pre.timestamp != frame.as_of
                or post.timestamp != frame.filled_at
                or pre.equity != frame.pre_cycle_equity
                or post.equity != frame.post_cycle_equity
            ):
                raise error("equity observation ordering does not match frames")
        if not isinstance(self.drawdowns, DrawdownAnalysis):
            raise error("drawdowns must be DrawdownAnalysis")
        if not isinstance(
            self.optimization_summary, OptimizedSimulationOptimizationSummary
        ):
            raise error("optimization_summary has an invalid type")
        if not all(
            isinstance(item, OptimizedSimulationPerformanceDiagnostic)
            for item in diagnostics
        ):
            raise error("diagnostics contain invalid values")
        for name in _RESULT_DECIMAL_FIELDS:
            _finite(getattr(self, name), name, error)
        for name in _RESULT_COUNT_FIELDS:
            _count(getattr(self, name), name, error)
        _validate_result_aggregates(self, frames, observations, diagnostics)
        expected_id = _performance_result_id(self, frames, observations, diagnostics)
        if self.result_id != expected_id:
            raise error("result_id does not match deterministic analytics identity")
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "equity_observations", observations)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def maximum_drawdown_amount(self) -> Decimal:
        return self.drawdowns.maximum_amount.amount

    @property
    def maximum_drawdown_percentage(self) -> Decimal:
        return self.drawdowns.maximum_percentage.percentage


_RESULT_DECIMAL_FIELDS = (
    "initial_equity",
    "final_equity",
    "absolute_simulation_profit_loss",
    "simulation_return",
    "initial_unrealized_profit_loss",
    "final_unrealized_profit_loss",
    "cumulative_simulation_realized_profit_loss",
    "total_gross_buy_notional",
    "total_gross_sell_notional",
    "total_gross_traded_notional",
    "total_net_buy_notional",
    "aggregate_one_way_turnover",
    "aggregate_two_way_turnover",
    "total_commissions",
    "total_signed_slippage_profit_loss",
    "total_adverse_slippage_cost",
    "total_execution_cost",
    "total_rejected_notional",
    "total_reduced_notional",
    "maximum_absolute_allocation_drift",
    "total_absolute_allocation_drift",
)

_RESULT_COUNT_FIELDS = (
    "total_order_count",
    "total_fill_count",
    "total_approved_risk_count",
    "total_resized_risk_count",
    "total_rejected_risk_count",
    "applied_cycle_count",
    "no_action_cycle_count",
)


@dataclass(frozen=True, slots=True)
class _ReconstructedPosition:
    symbol: Symbol
    quantity: Decimal
    basis: Decimal

    @property
    def average_cost(self) -> Decimal:
        return _ZERO if self.quantity == _ZERO else self.basis / self.quantity


@dataclass(frozen=True, slots=True)
class _ReconstructedPortfolioState:
    symbols: tuple[Symbol, ...]
    positions: tuple[_ReconstructedPosition, ...]
    cash: Decimal

    def by_symbol(self) -> dict[Symbol, _ReconstructedPosition]:
        return {item.symbol: item for item in self.positions}


@dataclass(frozen=True, slots=True)
class _ReconstructedFrame:
    ordinal: int
    pre: _ReconstructedPortfolioState
    post: _ReconstructedPortfolioState
    frame_realized: Decimal
    cumulative_realized: Decimal
    lifetime_realized_baseline: Decimal | None


class OptimizedSimulationPerformanceAnalyzer:
    """Analyze one immutable optimized simulation without rerunning any stage."""

    def analyze(
        self, request: OptimizedSimulationPerformanceRequest
    ) -> OptimizedSimulationPerformanceResult:
        if not isinstance(request, OptimizedSimulationPerformanceRequest):
            raise InvalidOptimizedSimulationPerformanceRequestError(
                "request must be OptimizedSimulationPerformanceRequest"
            )
        self._validate_simulation_audit(request.simulation_result)
        reconstructed = self._reconstruct(request.simulation_result)
        return self._calculate(request, reconstructed)

    @staticmethod
    def _validate_simulation_audit(result: OptimizedPaperSimulationResult) -> None:
        error = OptimizedSimulationPerformanceReconciliationError
        evaluations = result.evaluations
        if not evaluations or len(evaluations) != len(result.request.frames):
            raise error("simulation evaluations must exactly cover request frames")
        order_ids: set[UUID] = set()
        event_ids: set[UUID] = set()
        fill_ids: set[UUID] = set()
        previous = None
        for ordinal, evaluation in enumerate(evaluations):
            frame = evaluation.frame
            cycle = evaluation.cycle_result
            if (
                evaluation.frame_ordinal != ordinal
                or frame != result.request.frames[ordinal]
            ):
                raise error("simulation evaluation order is inconsistent")
            if previous is not None:
                if (
                    frame.as_of <= previous.frame.as_of
                    or frame.as_of < previous.frame.filled_at
                ):
                    raise error("simulation frame chronology is inconsistent")
                if (
                    previous.post_engine_state_id != evaluation.pre_engine_state_id
                    or previous.post_ledger_state_id != evaluation.pre_ledger_state_id
                ):
                    raise error("simulation component state IDs do not chain")
            if (
                cycle.pre_engine_state_id != evaluation.pre_engine_state_id
                or cycle.pre_ledger_state_id != evaluation.pre_ledger_state_id
                or cycle.post_engine_state_id != evaluation.post_engine_state_id
                or cycle.post_ledger_state_id != evaluation.post_ledger_state_id
            ):
                raise error("cycle state IDs differ from the simulation evaluation")
            orders = cycle.order_result.orders
            events = (
                *cycle.order_result.created_events,
                *cycle.submission_result.submitted_events,
                *(item.fill_event for item in cycle.application_result.evaluations),
            )
            fills = cycle.fill_result.fills
            for identifier, seen, name in (
                *((item.request.order_id, order_ids, "order") for item in orders),
                *((item.event_id, event_ids, "event") for item in events),
                *((item.fill_id, fill_ids, "fill") for item in fills),
            ):
                if identifier in seen:
                    raise error(f"duplicate {name} ID in simulation audit")
                seen.add(identifier)
            if len(fills) != len(cycle.application_result.evaluations):
                raise error("fill and application counts differ")
            previous = evaluation
        if (
            evaluations[0].pre_engine_state_id != result.initial_engine_state_id
            or evaluations[0].pre_ledger_state_id != result.initial_ledger_state_id
            or evaluations[-1].post_engine_state_id != result.final_engine_state_id
            or evaluations[-1].post_ledger_state_id != result.final_ledger_state_id
        ):
            raise error("simulation boundary state IDs do not match evaluations")

    @classmethod
    def _reconstruct(
        cls, result: OptimizedPaperSimulationResult
    ) -> tuple[_ReconstructedFrame, ...]:
        output = []
        prior_post = None
        cumulative_realized = _ZERO
        lifetime_baseline = None
        for ordinal, evaluation in enumerate(result.evaluations):
            pre = _state_from_derived(evaluation.derived_state)
            if prior_post is not None:
                _validate_adjacent_states(prior_post, pre)
            post, frame_realized, cumulative_realized, lifetime_baseline = (
                cls._apply_frame(
                    evaluation,
                    pre,
                    cumulative_realized,
                    lifetime_baseline,
                )
            )
            output.append(
                _ReconstructedFrame(
                    ordinal,
                    pre,
                    post,
                    frame_realized,
                    cumulative_realized,
                    lifetime_baseline,
                )
            )
            prior_post = post
        return tuple(output)

    @staticmethod
    def _apply_frame(
        evaluation,
        pre: _ReconstructedPortfolioState,
        cumulative_realized: Decimal,
        lifetime_baseline: Decimal | None,
    ) -> tuple[_ReconstructedPortfolioState, Decimal, Decimal, Decimal | None]:  # type: ignore[no-untyped-def]
        error = OptimizedSimulationPerformanceReconciliationError
        cycle = evaluation.cycle_result
        fills = cycle.fill_result.evaluations
        applications = cycle.application_result.evaluations
        if cycle.status is PaperPortfolioCycleStatus.NO_ACTION:
            if fills or applications or cycle.order_result.orders:
                raise error("NO_ACTION cycle contains trading output")
            if (
                cycle.pre_engine_state_id != cycle.post_engine_state_id
                or cycle.pre_ledger_state_id != cycle.post_ledger_state_id
            ):
                raise error("NO_ACTION cycle changed component state IDs")
            return pre, _ZERO, cumulative_realized, lifetime_baseline
        if cycle.status is not PaperPortfolioCycleStatus.APPLIED or not fills:
            raise error("applied cycle must contain fills")
        positions = pre.by_symbol()
        cash = pre.cash
        frame_realized = _ZERO
        for ordinal, (fill_evaluation, application) in enumerate(
            zip(fills, applications, strict=True)
        ):
            fill = fill_evaluation.fill
            if application.source_fill_ordinal != ordinal or application.fill != fill:
                raise error("fill and application ordering is inconsistent")
            current = positions.get(fill.symbol)
            if current is None:
                raise error("fill symbol is outside the frame universe")
            if fill.side is OrderSide.BUY:
                required = fill.gross_amount + fill.commission
                if required > cash:
                    raise error("buy fill exceeds reconstructed cash")
                updated = _ReconstructedPosition(
                    fill.symbol,
                    current.quantity + fill.quantity,
                    current.basis + required,
                )
                cash -= required
                realized_delta = _ZERO
            else:
                if fill.quantity > current.quantity or current.quantity == _ZERO:
                    raise error("sell fill exceeds reconstructed position")
                removed_basis = current.average_cost * fill.quantity
                cash += fill.gross_amount - fill.commission
                realized_delta = fill.gross_amount - fill.commission - removed_basis
                remaining = current.quantity - fill.quantity
                updated = _ReconstructedPosition(
                    fill.symbol,
                    remaining,
                    _ZERO if remaining == _ZERO else current.basis - removed_basis,
                )
            positions[fill.symbol] = updated
            frame_realized += realized_delta
            cumulative_realized += realized_delta
            expected_public = application.ledger_position_after
            if updated.quantity == _ZERO:
                if expected_public is not None:
                    raise error("application retained a reconstructed flat position")
            elif expected_public is None or (
                expected_public.quantity != updated.quantity
                or expected_public.average_cost != updated.average_cost
            ):
                raise error(
                    "application position does not match average-cost accounting"
                )
            if application.ledger_cash_after != cash:
                raise error("application cash does not match reconstructed accounting")
            candidate_baseline = (
                application.ledger_realized_profit_loss_after - cumulative_realized
            )
            if lifetime_baseline is None:
                lifetime_baseline = candidate_baseline
            elif lifetime_baseline != candidate_baseline:
                raise error("application realized P&L progression is inconsistent")
        post = _ReconstructedPortfolioState(
            pre.symbols,
            tuple(positions[symbol] for symbol in pre.symbols),
            cash,
        )
        return post, frame_realized, cumulative_realized, lifetime_baseline

    @classmethod
    def _calculate(
        cls,
        request: OptimizedSimulationPerformanceRequest,
        reconstructed: tuple[_ReconstructedFrame, ...],
    ) -> OptimizedSimulationPerformanceResult:
        return _calculate_performance(request, reconstructed)


@dataclass(frozen=True, slots=True)
class _Valuation:
    equity: Decimal
    market_value: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    unrealized: Decimal
    position_count: int


def _state_from_derived(state) -> _ReconstructedPortfolioState:  # type: ignore[no-untyped-def]
    error = OptimizedSimulationPerformanceReconciliationError
    positions = []
    for item in state.positions:
        for name in ("quantity", "average_cost", "current_price"):
            _finite(getattr(item, name), name, error)
        positions.append(
            _ReconstructedPosition(
                item.symbol,
                item.quantity,
                item.quantity * item.average_cost,
            )
        )
    _finite(state.cash, "derived state cash", error)
    return _ReconstructedPortfolioState(
        tuple(item.symbol for item in state.positions), tuple(positions), state.cash
    )


def _validate_adjacent_states(
    prior: _ReconstructedPortfolioState, current: _ReconstructedPortfolioState
) -> None:
    error = OptimizedSimulationPerformanceReconciliationError
    if prior.cash != current.cash:
        raise error("prior post-cycle cash differs from next pre-cycle cash")
    prior_by_symbol = prior.by_symbol()
    current_by_symbol = current.by_symbol()
    for symbol, position in prior_by_symbol.items():
        next_position = current_by_symbol.get(symbol)
        if position.quantity > _ZERO and next_position is None:
            raise error("held symbol is missing from the next frame universe")
        if next_position is not None and (
            position.quantity != next_position.quantity
            or position.average_cost != next_position.average_cost
        ):
            raise error("adjacent frame positions or average costs differ")
    for symbol, position in current_by_symbol.items():
        if symbol not in prior_by_symbol and (
            position.quantity != _ZERO or position.basis != _ZERO
        ):
            raise error("a new frame symbol must enter as a flat position")


def _prices(evaluation) -> dict[Symbol, Decimal]:  # type: ignore[no-untyped-def]
    error = OptimizedSimulationValuationError
    prices = {}
    for item in evaluation.frame.prices:
        price = _finite(item.risk_price, f"risk price for {item.symbol}", error)
        if price <= _ZERO:
            raise error(f"risk price for {item.symbol} must be positive")
        if item.symbol in prices:
            raise error("risk price symbols must be unique")
        prices[item.symbol] = price
    return prices


def _value_state(
    state: _ReconstructedPortfolioState,
    prices: dict[Symbol, Decimal],
) -> _Valuation:
    error = OptimizedSimulationValuationError
    market = _ZERO
    gross = _ZERO
    net = _ZERO
    unrealized = _ZERO
    count = 0
    for position in state.positions:
        if position.symbol not in prices:
            raise error(f"missing risk price for {position.symbol}")
        if (
            not position.quantity.is_finite()
            or not position.basis.is_finite()
            or position.quantity < _ZERO
            or position.basis < _ZERO
        ):
            raise error("position quantity and basis must be finite and nonnegative")
        value = position.quantity * prices[position.symbol]
        market += value
        gross += abs(value)
        net += value
        unrealized += value - position.basis
        count += position.quantity > _ZERO
    equity = state.cash + market
    if not equity.is_finite() or equity <= _ZERO:
        raise error("required valuation equity must be finite and strictly positive")
    return _Valuation(equity, market, gross, net, unrealized, count)


def _execution_metrics(evaluation, prices):  # type: ignore[no-untyped-def]
    buy = sell = commission = signed_slippage = adverse = impact = _ZERO
    for item in evaluation.cycle_result.fill_result.evaluations:
        fill = item.fill
        risk_price = prices.get(fill.symbol)
        if risk_price is None:
            raise OptimizedSimulationValuationError(
                f"missing risk price for fill symbol {fill.symbol}"
            )
        commission += fill.commission
        if fill.side is OrderSide.BUY:
            buy += fill.gross_amount
            signed = (item.reference_price - fill.price) * fill.quantity
            impact += fill.quantity * (risk_price - fill.price) - fill.commission
        else:
            sell += fill.gross_amount
            signed = (fill.price - item.reference_price) * fill.quantity
            impact += fill.quantity * (fill.price - risk_price) - fill.commission
        signed_slippage += signed
        adverse += max(-signed, _ZERO)
    return buy, sell, commission, signed_slippage, adverse, impact


def _risk_metrics(evaluation, prices):  # type: ignore[no-untyped-def]
    batch = evaluation.cycle_result.risk_result
    rejected = reduced = _ZERO
    approved = resized = rejected_count = 0
    for item in batch.evaluations:
        decision = item.decision
        price = prices.get(decision.proposal.symbol)
        if price is None:
            raise OptimizedSimulationValuationError(
                f"missing risk price for proposal {decision.proposal.symbol}"
            )
        if decision.outcome is RiskOutcome.APPROVED:
            approved += 1
        elif decision.outcome is RiskOutcome.RESIZED:
            resized += 1
            reduced += (
                decision.proposal.desired_quantity - decision.approved_quantity
            ) * price
        elif decision.outcome is RiskOutcome.REJECTED:
            rejected_count += 1
            rejected += decision.proposal.desired_quantity * price
        else:
            raise OptimizedSimulationPerformanceReconciliationError(
                "risk decision has an unsupported outcome"
            )
    if (
        approved != batch.approved_count
        or resized != batch.resized_count
        or rejected_count != batch.rejected_count
    ):
        raise OptimizedSimulationPerformanceReconciliationError(
            "risk outcome counts do not reconcile"
        )
    return approved, resized, rejected_count, rejected, reduced


def _allocation_metrics(evaluation, post, valuation, prices):  # type: ignore[no-untyped-def]
    error = OptimizedSimulationPerformanceReconciliationError
    target = evaluation.optimized_target_result.target
    if target.symbols != post.symbols:
        raise error("target and reconstructed post-state universes differ")
    positions = post.by_symbol()
    drifts = []
    actual_total = _ZERO
    target_total = target.cash_weight
    for allocation in target.allocations:
        actual = (
            positions[allocation.symbol].quantity * prices[allocation.symbol]
        ) / valuation.equity
        drift = actual - allocation.weight
        drifts.append(
            OptimizedSimulationAllocationDrift(
                allocation.symbol,
                allocation.weight,
                actual,
                drift,
                abs(drift),
            )
        )
        actual_total += actual
        target_total += allocation.weight
    actual_cash = post.cash / valuation.equity
    cash_drift = actual_cash - target.cash_weight
    if target_total != _ONE or actual_total + actual_cash != _ONE:
        raise error("target or actual portfolio weights do not sum exactly to one")
    if sum((item.drift for item in drifts), start=cash_drift) != _ZERO:
        raise error("allocation drifts do not sum exactly to zero")
    maximum = max((abs(cash_drift), *(item.absolute_drift for item in drifts)))
    total = abs(cash_drift) + sum((item.absolute_drift for item in drifts), start=_ZERO)
    return tuple(drifts), actual_cash, cash_drift, maximum, total


def _calculate_performance(
    request: OptimizedSimulationPerformanceRequest,
    reconstructed: tuple[_ReconstructedFrame, ...],
) -> OptimizedSimulationPerformanceResult:
    result = request.simulation_result
    valuations = []
    price_maps = []
    for evaluation, item in zip(result.evaluations, reconstructed, strict=True):
        prices = _prices(evaluation)
        if tuple(prices) != item.pre.symbols:
            raise OptimizedSimulationValuationError(
                "frame risk-price order must equal the derived-state universe"
            )
        pre_value = _value_state(item.pre, prices)
        post_value = _value_state(item.post, prices)
        if pre_value.equity != evaluation.derived_state.equity:
            raise OptimizedSimulationPerformanceReconciliationError(
                "reconstructed pre-cycle equity differs from derived state"
            )
        valuations.append((pre_value, post_value))
        price_maps.append(prices)

    initial_equity = valuations[0][0].equity
    frames = []
    for ordinal, (evaluation, reconstructed_frame, valued, prices) in enumerate(
        zip(result.evaluations, reconstructed, valuations, price_maps, strict=True)
    ):
        pre_value, post_value = valued
        execution = post_value.equity - pre_value.equity
        buy, sell, commission, signed, adverse, fill_impact = _execution_metrics(
            evaluation, prices
        )
        if execution != fill_impact:
            raise OptimizedSimulationPerformanceReconciliationError(
                "execution P&L does not reconcile with fills and risk prices"
            )
        forward = None
        if ordinal + 1 < len(reconstructed):
            next_pre_value = valuations[ordinal + 1][0]
            forward = next_pre_value.equity - post_value.equity
            next_prices = price_maps[ordinal + 1]
            expected_forward = _ZERO
            for position in reconstructed_frame.post.positions:
                if position.quantity == _ZERO:
                    continue
                if position.symbol not in next_prices:
                    raise OptimizedSimulationValuationError(
                        f"next frame lacks held symbol {position.symbol}"
                    )
                expected_forward += position.quantity * (
                    next_prices[position.symbol] - prices[position.symbol]
                )
            if forward != expected_forward:
                raise OptimizedSimulationPerformanceReconciliationError(
                    "forward market P&L does not reconcile with price movement"
                )
        period_pnl = execution if forward is None else execution + forward
        period_return = period_pnl / pre_value.equity
        endpoint_equity = (
            post_value.equity if forward is None else valuations[ordinal + 1][0].equity
        )
        cumulative_pnl = endpoint_equity - initial_equity
        cumulative_return = cumulative_pnl / initial_equity
        approved, resized, rejected_count, rejected, reduced = _risk_metrics(
            evaluation, prices
        )
        drifts, actual_cash, cash_drift, max_drift, total_drift = _allocation_metrics(
            evaluation, reconstructed_frame.post, post_value, prices
        )
        optimization = evaluation.optimization_result
        portfolio = optimization.optimization_result
        if (
            portfolio.status is not OptimizationStatus.OPTIMAL
            or optimization.expected_portfolio_return is None
            or optimization.cvar is None
            or portfolio.objective_value is None
        ):
            raise OptimizedSimulationPerformanceReconciliationError(
                "optimized simulation frame lacks complete optimal metrics"
            )
        values = dict(
            frame_ordinal=ordinal,
            source_cycle_result_id=evaluation.cycle_result.result_id,
            as_of=evaluation.frame.as_of,
            filled_at=evaluation.frame.filled_at,
            pre_cycle_equity=pre_value.equity,
            post_cycle_equity=post_value.equity,
            execution_profit_loss=execution,
            forward_market_profit_loss=forward,
            period_profit_loss=period_pnl,
            period_return=period_return,
            cumulative_return=cumulative_return,
            cumulative_simulation_profit_loss=cumulative_pnl,
            pre_cycle_cash=reconstructed_frame.pre.cash,
            post_cycle_cash=reconstructed_frame.post.cash,
            pre_cycle_gross_exposure=pre_value.gross_exposure,
            post_cycle_gross_exposure=post_value.gross_exposure,
            pre_cycle_net_exposure=pre_value.net_exposure,
            post_cycle_net_exposure=post_value.net_exposure,
            pre_cycle_position_count=pre_value.position_count,
            post_cycle_position_count=post_value.position_count,
            frame_simulation_realized_profit_loss=reconstructed_frame.frame_realized,
            cumulative_simulation_realized_profit_loss=(
                reconstructed_frame.cumulative_realized
            ),
            pre_cycle_unrealized_profit_loss=pre_value.unrealized,
            post_cycle_unrealized_profit_loss=post_value.unrealized,
            unrealized_profit_loss_change=post_value.unrealized - pre_value.unrealized,
            gross_buy_notional=buy,
            gross_sell_notional=sell,
            gross_traded_notional=buy + sell,
            net_buy_notional=buy - sell,
            one_way_turnover=max(buy, sell) / pre_value.equity,
            two_way_turnover=(buy + sell) / pre_value.equity,
            commission_cost=commission,
            signed_slippage_profit_loss=signed,
            adverse_slippage_cost=adverse,
            total_execution_cost=commission + adverse,
            order_count=len(evaluation.cycle_result.order_result.orders),
            fill_count=len(evaluation.cycle_result.fill_result.fills),
            approved_risk_count=approved,
            resized_risk_count=resized,
            rejected_risk_count=rejected_count,
            rejected_notional=rejected,
            reduced_notional=reduced,
            optimization_status=portfolio.status,
            solver_name=portfolio.solver_name,
            expected_portfolio_return=optimization.expected_portfolio_return,
            cvar=optimization.cvar,
            objective_value=portfolio.objective_value,
            target_cash_weight=evaluation.optimized_target_result.target.cash_weight,
            target_allocation_count=len(
                evaluation.optimized_target_result.target.allocations
            ),
            allocation_drifts=drifts,
            actual_cash_weight=actual_cash,
            cash_weight_drift=cash_drift,
            absolute_cash_weight_drift=abs(cash_drift),
            maximum_absolute_allocation_drift=max_drift,
            total_absolute_allocation_drift=total_drift,
        )
        provisional = OptimizedSimulationFramePerformance(UUID(int=0), **values)
        frames.append(
            OptimizedSimulationFramePerformance(
                _frame_identity(request, provisional), **values
            )
        )
    frames_tuple = tuple(frames)
    observations, drawdowns = _equity_observations(frames_tuple)
    return _build_performance_result(request, frames_tuple, observations, drawdowns)


def _equity_observations(
    frames: tuple[OptimizedSimulationFramePerformance, ...],
) -> tuple[tuple[OptimizedSimulationEquityObservation, ...], DrawdownAnalysis]:
    observations = []
    running_peak = frames[0].pre_cycle_equity
    peak_at = frames[0].as_of
    maximum_amount = None
    maximum_percentage = None
    for frame in frames:
        for phase, timestamp, equity in (
            (
                OptimizedSimulationEquityPhase.PRE_CYCLE,
                frame.as_of,
                frame.pre_cycle_equity,
            ),
            (
                OptimizedSimulationEquityPhase.POST_CYCLE,
                frame.filled_at,
                frame.post_cycle_equity,
            ),
        ):
            if equity > running_peak:
                running_peak = equity
                peak_at = timestamp
            amount = running_peak - equity
            percentage = amount / running_peak
            observation = OptimizedSimulationEquityObservation(
                len(observations),
                frame.frame_ordinal,
                phase,
                timestamp,
                equity,
                running_peak,
                amount,
                percentage,
            )
            observations.append(observation)
            record = DrawdownRecord(
                peak_at, timestamp, running_peak, equity, amount, percentage
            )
            if maximum_amount is None or amount > maximum_amount.amount:
                maximum_amount = record
            if maximum_percentage is None or percentage > maximum_percentage.percentage:
                maximum_percentage = record
    assert maximum_amount is not None and maximum_percentage is not None
    return tuple(observations), DrawdownAnalysis(maximum_amount, maximum_percentage)


def _drawdowns_from_observations(
    observations: tuple[OptimizedSimulationEquityObservation, ...],
) -> DrawdownAnalysis:
    error = InconsistentOptimizedSimulationPerformanceResultError
    running_peak = observations[0].equity
    peak_at = observations[0].timestamp
    maximum_amount = None
    maximum_percentage = None
    for observation in observations:
        if observation.equity > running_peak:
            running_peak = observation.equity
            peak_at = observation.timestamp
        amount = running_peak - observation.equity
        percentage = amount / running_peak
        if (
            observation.running_peak != running_peak
            or observation.drawdown_amount != amount
            or observation.drawdown_percentage != percentage
        ):
            raise error("equity observation running drawdown is inconsistent")
        record = DrawdownRecord(
            peak_at,
            observation.timestamp,
            running_peak,
            observation.equity,
            amount,
            percentage,
        )
        if maximum_amount is None or amount > maximum_amount.amount:
            maximum_amount = record
        if maximum_percentage is None or percentage > maximum_percentage.percentage:
            maximum_percentage = record
    assert maximum_amount is not None and maximum_percentage is not None
    return DrawdownAnalysis(maximum_amount, maximum_percentage)


def _build_performance_result(
    request: OptimizedSimulationPerformanceRequest,
    frames: tuple[OptimizedSimulationFramePerformance, ...],
    observations: tuple[OptimizedSimulationEquityObservation, ...],
    drawdowns: DrawdownAnalysis,
) -> OptimizedSimulationPerformanceResult:
    initial = frames[0].pre_cycle_equity
    final = frames[-1].post_cycle_equity
    average_pre = sum(
        (item.pre_cycle_equity for item in frames), start=_ZERO
    ) / Decimal(len(frames))
    one_way_numerator = sum(
        (max(item.gross_buy_notional, item.gross_sell_notional) for item in frames),
        start=_ZERO,
    )
    expected_returns = tuple(item.expected_portfolio_return for item in frames)
    cvars = tuple(item.cvar for item in frames)
    cash_weights = tuple(item.target_cash_weight for item in frames)
    diagnostics = []
    total_fills = sum(item.fill_count for item in frames)
    if total_fills == 0:
        diagnostics.append(
            OptimizedSimulationPerformanceDiagnostic(
                OptimizedSimulationPerformanceDiagnosticCode.NO_TRADING_ACTIVITY,
                "the simulation contains no trading activity",
            )
        )
    if request.simulation_result.no_action_cycle_count == len(frames):
        diagnostics.append(
            OptimizedSimulationPerformanceDiagnostic(
                OptimizedSimulationPerformanceDiagnosticCode.ALL_CYCLES_NO_ACTION,
                "every simulation cycle completed without action",
            )
        )
    values = dict(
        request=request,
        frames=frames,
        equity_observations=observations,
        drawdowns=drawdowns,
        initial_equity=initial,
        final_equity=final,
        absolute_simulation_profit_loss=final - initial,
        simulation_return=(final - initial) / initial,
        initial_unrealized_profit_loss=frames[0].pre_cycle_unrealized_profit_loss,
        final_unrealized_profit_loss=frames[-1].post_cycle_unrealized_profit_loss,
        cumulative_simulation_realized_profit_loss=(
            frames[-1].cumulative_simulation_realized_profit_loss
        ),
        total_gross_buy_notional=sum(
            (item.gross_buy_notional for item in frames), start=_ZERO
        ),
        total_gross_sell_notional=sum(
            (item.gross_sell_notional for item in frames), start=_ZERO
        ),
        total_gross_traded_notional=sum(
            (item.gross_traded_notional for item in frames), start=_ZERO
        ),
        total_net_buy_notional=sum(
            (item.net_buy_notional for item in frames), start=_ZERO
        ),
        aggregate_one_way_turnover=one_way_numerator / average_pre,
        aggregate_two_way_turnover=sum(
            (item.gross_traded_notional for item in frames), start=_ZERO
        )
        / average_pre,
        total_commissions=sum((item.commission_cost for item in frames), start=_ZERO),
        total_signed_slippage_profit_loss=sum(
            (item.signed_slippage_profit_loss for item in frames), start=_ZERO
        ),
        total_adverse_slippage_cost=sum(
            (item.adverse_slippage_cost for item in frames), start=_ZERO
        ),
        total_execution_cost=sum(
            (item.total_execution_cost for item in frames), start=_ZERO
        ),
        total_order_count=sum(item.order_count for item in frames),
        total_fill_count=total_fills,
        total_approved_risk_count=sum(item.approved_risk_count for item in frames),
        total_resized_risk_count=sum(item.resized_risk_count for item in frames),
        total_rejected_risk_count=sum(item.rejected_risk_count for item in frames),
        total_rejected_notional=sum(
            (item.rejected_notional for item in frames), start=_ZERO
        ),
        total_reduced_notional=sum(
            (item.reduced_notional for item in frames), start=_ZERO
        ),
        applied_cycle_count=request.simulation_result.applied_cycle_count,
        no_action_cycle_count=request.simulation_result.no_action_cycle_count,
        optimization_summary=OptimizedSimulationOptimizationSummary(
            sum(expected_returns, start=_ZERO) / Decimal(len(frames)),
            max(cvars),
            min(cash_weights),
            max(cash_weights),
        ),
        maximum_absolute_allocation_drift=max(
            item.maximum_absolute_allocation_drift for item in frames
        ),
        total_absolute_allocation_drift=sum(
            (item.total_absolute_allocation_drift for item in frames), start=_ZERO
        ),
        diagnostics=tuple(diagnostics),
    )
    provisional = SimpleNamespace(**values)
    return OptimizedSimulationPerformanceResult(
        _performance_result_id(
            provisional,
            frames,
            observations,
            tuple(diagnostics),
        ),
        **values,
    )


def _validate_result_aggregates(
    result: OptimizedSimulationPerformanceResult,
    frames: tuple[OptimizedSimulationFramePerformance, ...],
    observations: tuple[OptimizedSimulationEquityObservation, ...],
    diagnostics: tuple[OptimizedSimulationPerformanceDiagnostic, ...],
) -> None:
    error = InconsistentOptimizedSimulationPerformanceResultError
    if result.initial_equity != frames[0].pre_cycle_equity or (
        result.final_equity != frames[-1].post_cycle_equity
    ):
        raise error("initial or final equity does not match frame analytics")
    if result.absolute_simulation_profit_loss != (
        result.final_equity - result.initial_equity
    ) or result.simulation_return != (
        result.absolute_simulation_profit_loss / result.initial_equity
    ):
        raise error("aggregate simulation return does not reconcile")
    if (
        frames[-1].cumulative_return != result.simulation_return
        or frames[-1].cumulative_simulation_profit_loss
        != result.absolute_simulation_profit_loss
    ):
        raise error("final cumulative frame values do not match aggregate values")
    cumulative_realized = _ZERO
    for ordinal, frame in enumerate(frames):
        forward = (
            None
            if ordinal == len(frames) - 1
            else frames[ordinal + 1].pre_cycle_equity - frame.post_cycle_equity
        )
        expected_period = frame.execution_profit_loss + (forward or _ZERO)
        endpoint = (
            frame.post_cycle_equity
            if forward is None
            else frames[ordinal + 1].pre_cycle_equity
        )
        cumulative_realized += frame.frame_simulation_realized_profit_loss
        if (
            frame.forward_market_profit_loss != forward
            or frame.period_profit_loss != expected_period
            or frame.period_return != expected_period / frame.pre_cycle_equity
            or frame.cumulative_simulation_profit_loss
            != endpoint - result.initial_equity
            or frame.cumulative_return
            != frame.cumulative_simulation_profit_loss / result.initial_equity
            or frame.cumulative_simulation_realized_profit_loss != cumulative_realized
        ):
            raise error("frame return or realized P&L progression is inconsistent")
    pnl_identity = (
        result.cumulative_simulation_realized_profit_loss
        + result.final_unrealized_profit_loss
        - result.initial_unrealized_profit_loss
    )
    if pnl_identity != result.absolute_simulation_profit_loss:
        raise error("simulation-relative P&L identity does not reconcile")
    sum_fields = {
        "total_gross_buy_notional": "gross_buy_notional",
        "total_gross_sell_notional": "gross_sell_notional",
        "total_gross_traded_notional": "gross_traded_notional",
        "total_net_buy_notional": "net_buy_notional",
        "total_commissions": "commission_cost",
        "total_signed_slippage_profit_loss": "signed_slippage_profit_loss",
        "total_adverse_slippage_cost": "adverse_slippage_cost",
        "total_execution_cost": "total_execution_cost",
        "total_rejected_notional": "rejected_notional",
        "total_reduced_notional": "reduced_notional",
        "total_absolute_allocation_drift": "total_absolute_allocation_drift",
    }
    for aggregate, frame_field in sum_fields.items():
        expected = sum((getattr(item, frame_field) for item in frames), start=_ZERO)
        if getattr(result, aggregate) != expected:
            raise error(f"{aggregate} does not equal ordered frame sum")
    count_fields = {
        "total_order_count": "order_count",
        "total_fill_count": "fill_count",
        "total_approved_risk_count": "approved_risk_count",
        "total_resized_risk_count": "resized_risk_count",
        "total_rejected_risk_count": "rejected_risk_count",
    }
    for aggregate, frame_field in count_fields.items():
        if getattr(result, aggregate) != sum(
            getattr(item, frame_field) for item in frames
        ):
            raise error(f"{aggregate} does not equal ordered frame count")
    if result.maximum_absolute_allocation_drift != max(
        item.maximum_absolute_allocation_drift for item in frames
    ):
        raise error("maximum allocation drift does not match frames")
    average_pre = sum(
        (item.pre_cycle_equity for item in frames), start=_ZERO
    ) / Decimal(len(frames))
    if result.aggregate_one_way_turnover != sum(
        (max(item.gross_buy_notional, item.gross_sell_notional) for item in frames),
        start=_ZERO,
    ) / average_pre or result.aggregate_two_way_turnover != (
        result.total_gross_traded_notional / average_pre
    ):
        raise error("aggregate turnover values do not reconcile")
    if result.total_gross_traded_notional != (
        result.total_gross_buy_notional + result.total_gross_sell_notional
    ) or result.total_net_buy_notional != (
        result.total_gross_buy_notional - result.total_gross_sell_notional
    ):
        raise error("aggregate trading notionals do not reconcile")
    if result.total_execution_cost != (
        result.total_commissions + result.total_adverse_slippage_cost
    ):
        raise error("aggregate execution costs do not reconcile")
    if result.applied_cycle_count + result.no_action_cycle_count != len(frames):
        raise error("cycle counts do not cover frames")
    source = result.request.simulation_result
    if (
        result.applied_cycle_count != source.applied_cycle_count
        or result.no_action_cycle_count != source.no_action_cycle_count
    ):
        raise error("analytics cycle counts do not match the source simulation")
    expected_codes = []
    if result.total_fill_count == 0:
        expected_codes.append(
            OptimizedSimulationPerformanceDiagnosticCode.NO_TRADING_ACTIVITY
        )
    if result.no_action_cycle_count == len(frames):
        expected_codes.append(
            OptimizedSimulationPerformanceDiagnosticCode.ALL_CYCLES_NO_ACTION
        )
    if tuple(item.code for item in diagnostics) != tuple(expected_codes):
        raise error("diagnostics do not match aggregate activity")
    if tuple(item.sequence_index for item in observations) != tuple(
        range(len(observations))
    ):
        raise error("observation sequence indexes are not contiguous")
    if any(
        current.timestamp < previous.timestamp
        for previous, current in zip(observations, observations[1:], strict=False)
    ):
        raise error("equity observation timestamps must be nondecreasing")
    expected_drawdowns = _drawdowns_from_observations(observations)
    if result.drawdowns != expected_drawdowns:
        raise error("drawdown maxima do not match equity observations")
    summary = result.optimization_summary
    expected_returns = tuple(item.expected_portfolio_return for item in frames)
    cvars = tuple(item.cvar for item in frames)
    cash_weights = tuple(item.target_cash_weight for item in frames)
    if (
        summary.mean_expected_portfolio_return
        != sum(expected_returns, start=_ZERO) / Decimal(len(frames))
        or summary.worst_cvar != max(cvars)
        or summary.minimum_target_cash_weight != min(cash_weights)
        or summary.maximum_target_cash_weight != max(cash_weights)
    ):
        raise error("optimization summary does not match frame metrics")
    for frame, evaluation in zip(
        frames, result.request.simulation_result.evaluations, strict=True
    ):
        if (
            frame.source_cycle_result_id != evaluation.cycle_result.result_id
            or frame.as_of != evaluation.frame.as_of
            or frame.filled_at != evaluation.frame.filled_at
        ):
            raise error("frame source alignment does not match the simulation")
        if frame.frame_id != _frame_identity(result.request, frame):
            raise error("frame_id does not match deterministic analytics identity")


def _frame_identity(
    request: OptimizedSimulationPerformanceRequest,
    frame: OptimizedSimulationFramePerformance,
) -> UUID:
    material = [
        _VERSION,
        str(request.request_id),
        str(request.simulation_result.result_id),
        request.valuation_policy.valuation_basis.value,
        str(frame.frame_ordinal),
        str(frame.source_cycle_result_id),
        frame.as_of.isoformat(),
        frame.filled_at.isoformat(),
    ]
    for name in _FRAME_DECIMAL_FIELDS:
        value = getattr(frame, name)
        material.append("none" if value is None else canonical_decimal(value))
    material.extend(str(getattr(frame, name)) for name in _FRAME_COUNT_FIELDS)
    material.extend(
        (
            frame.optimization_status.value,
            frame.solver_name,
            *(
                f"{item.symbol}:{canonical_decimal(item.target_weight)}:"
                f"{canonical_decimal(item.actual_weight)}:"
                f"{canonical_decimal(item.drift)}"
                for item in frame.allocation_drifts
            ),
        )
    )
    return uuid5(_NAMESPACE, "|".join(material))


def _observation_material(item: OptimizedSimulationEquityObservation) -> str:
    return ":".join(
        (
            str(item.sequence_index),
            str(item.frame_ordinal),
            item.phase.value,
            item.timestamp.isoformat(),
            canonical_decimal(item.equity),
            canonical_decimal(item.running_peak),
            canonical_decimal(item.drawdown_amount),
            canonical_decimal(item.drawdown_percentage),
        )
    )


def _drawdown_material(item: DrawdownRecord) -> str:
    return ":".join(
        (
            item.peak_timestamp.isoformat(),
            item.trough_timestamp.isoformat(),
            canonical_decimal(item.peak_equity),
            canonical_decimal(item.trough_equity),
            canonical_decimal(item.amount),
            canonical_decimal(item.percentage),
        )
    )


def _performance_result_id(
    result,
    frames: tuple[OptimizedSimulationFramePerformance, ...],
    observations: tuple[OptimizedSimulationEquityObservation, ...],
    diagnostics: tuple[OptimizedSimulationPerformanceDiagnostic, ...],
) -> UUID:
    material = [
        _VERSION,
        str(result.request.request_id),
        str(result.request.simulation_result.result_id),
        result.request.valuation_policy.valuation_basis.value,
        *(f"meta={item.key}={item.value}" for item in result.request.metadata),
        *(f"frame={item.frame_id}" for item in frames),
        *(_observation_material(item) for item in observations),
        _drawdown_material(result.drawdowns.maximum_amount),
        _drawdown_material(result.drawdowns.maximum_percentage),
    ]
    for name in _RESULT_DECIMAL_FIELDS:
        material.append(canonical_decimal(getattr(result, name)))
    material.extend(str(getattr(result, name)) for name in _RESULT_COUNT_FIELDS)
    summary = result.optimization_summary
    material.extend(
        canonical_decimal(getattr(summary, name))
        for name in (
            "mean_expected_portfolio_return",
            "worst_cvar",
            "minimum_target_cash_weight",
            "maximum_target_cash_weight",
        )
    )
    material.extend(item.code.value for item in diagnostics)
    return uuid5(_NAMESPACE, "|".join(material))
