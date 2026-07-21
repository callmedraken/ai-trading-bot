"""Immutable request and audit models for deterministic rebalance planning."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.portfolio import (
    MetadataEntry,
    PortfolioConstraints,
    PortfolioConstraintViolationError,
    PortfolioState,
    PortfolioUniverseMismatchError,
    TargetPortfolio,
)
from trading_bot.rebalancing.exceptions import (
    InconsistentRebalancePlanError,
    InvalidRebalanceAssumptionsError,
    InvalidRebalanceRequestError,
    RebalanceTargetConstraintError,
    RebalanceUniverseMismatchError,
    StaleRebalanceTargetError,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _decimal(value: Decimal, name: str, error_type: type[ValueError]) -> Decimal:
    if not isinstance(value, Decimal):
        raise error_type(f"{name} must be a Decimal")
    if not value.is_finite():
        raise error_type(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


@dataclass(frozen=True, slots=True)
class RebalanceAssumptions:
    fixed_commission: Decimal = _ZERO
    allow_fractional_quantities: bool = True
    quantity_increment: Decimal = Decimal("0.001")
    minimum_trade_notional: Decimal = _ZERO
    minimum_trade_quantity: Decimal = _ZERO
    target_weight_tolerance: Decimal = _ZERO
    additional_execution_cash_buffer: Decimal = _ZERO
    use_planned_sell_proceeds: bool = True

    def __post_init__(self) -> None:
        for name in (
            "fixed_commission",
            "quantity_increment",
            "minimum_trade_notional",
            "minimum_trade_quantity",
            "target_weight_tolerance",
            "additional_execution_cash_buffer",
        ):
            object.__setattr__(
                self,
                name,
                _decimal(getattr(self, name), name, InvalidRebalanceAssumptionsError),
            )
        if self.fixed_commission < _ZERO:
            raise InvalidRebalanceAssumptionsError(
                "fixed_commission must be nonnegative"
            )
        if not _ZERO < self.quantity_increment <= _ONE:
            raise InvalidRebalanceAssumptionsError(
                "quantity_increment must be positive and at most one"
            )
        for name in (
            "minimum_trade_notional",
            "minimum_trade_quantity",
            "additional_execution_cash_buffer",
        ):
            if getattr(self, name) < _ZERO:
                raise InvalidRebalanceAssumptionsError(f"{name} must be nonnegative")
        if not _ZERO <= self.target_weight_tolerance <= _ONE:
            raise InvalidRebalanceAssumptionsError(
                "target_weight_tolerance must be between zero and one"
            )
        for name in (
            "allow_fractional_quantities",
            "use_planned_sell_proceeds",
        ):
            if not isinstance(getattr(self, name), bool):
                raise InvalidRebalanceAssumptionsError(f"{name} must be a bool")
        if not self.allow_fractional_quantities and self.quantity_increment != _ONE:
            raise InvalidRebalanceAssumptionsError(
                "whole-share mode requires quantity_increment equal to one"
            )


@dataclass(frozen=True, slots=True)
class RebalancePlanRequest:
    request_id: UUID
    state: PortfolioState
    target: TargetPortfolio
    assumptions: RebalanceAssumptions
    constraints: PortfolioConstraints | None = None
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise InvalidRebalanceRequestError("request_id must be a UUID")
        if not isinstance(self.state, PortfolioState):
            raise InvalidRebalanceRequestError("state must be a PortfolioState")
        if not isinstance(self.target, TargetPortfolio):
            raise InvalidRebalanceRequestError("target must be a TargetPortfolio")
        if not isinstance(self.assumptions, RebalanceAssumptions):
            raise InvalidRebalanceRequestError(
                "assumptions must be RebalanceAssumptions"
            )
        if self.state.symbols != self.target.symbols:
            raise RebalanceUniverseMismatchError(
                "state and target ordered universes must match exactly"
            )
        if self.state.as_of != self.target.as_of:
            raise StaleRebalanceTargetError(
                "state and target as_of timestamps must match exactly"
            )
        if self.constraints is not None:
            if not isinstance(self.constraints, PortfolioConstraints):
                raise InvalidRebalanceRequestError(
                    "constraints must be PortfolioConstraints or None"
                )
            try:
                self.constraints.validate_target(self.state, self.target)
            except PortfolioUniverseMismatchError as error:
                raise RebalanceUniverseMismatchError(str(error)) from error
            except PortfolioConstraintViolationError as error:
                raise RebalanceTargetConstraintError(str(error)) from error
        try:
            metadata = tuple(self.metadata)
        except TypeError as error:
            raise InvalidRebalanceRequestError("metadata must be iterable") from error
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise InvalidRebalanceRequestError(
                "metadata must contain MetadataEntry values"
            )
        if len({item.key for item in metadata}) != len(metadata):
            raise InvalidRebalanceRequestError("metadata keys must be unique")
        object.__setattr__(self, "metadata", metadata)

    @property
    def as_of(self):  # type: ignore[no-untyped-def]
        return self.state.as_of


class PlannedTradeSide(StrEnum):
    SELL = "SELL"
    BUY = "BUY"


@dataclass(frozen=True, slots=True)
class PlannedTrade:
    planned_trade_id: UUID
    symbol: Symbol
    side: PlannedTradeSide
    symbol_ordinal: int
    current_price: Decimal
    current_quantity: Decimal
    target_weight: Decimal
    target_market_value: Decimal
    target_quantity: Decimal
    requested_quantity: Decimal
    planned_quantity: Decimal
    estimated_gross_notional: Decimal
    estimated_commission: Decimal
    estimated_net_cash_effect: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.planned_trade_id, UUID):
            raise InconsistentRebalancePlanError("planned_trade_id must be a UUID")
        if not isinstance(self.symbol, Symbol):
            raise InconsistentRebalancePlanError("symbol must be a Symbol")
        if not isinstance(self.side, PlannedTradeSide):
            raise InconsistentRebalancePlanError("side must be a PlannedTradeSide")
        if (
            not isinstance(self.symbol_ordinal, int)
            or isinstance(self.symbol_ordinal, bool)
            or self.symbol_ordinal < 0
        ):
            raise InconsistentRebalancePlanError(
                "symbol_ordinal must be a nonnegative integer"
            )
        for name in (
            "current_price",
            "current_quantity",
            "target_weight",
            "target_market_value",
            "target_quantity",
            "requested_quantity",
            "planned_quantity",
            "estimated_gross_notional",
            "estimated_commission",
            "estimated_net_cash_effect",
        ):
            object.__setattr__(
                self,
                name,
                _decimal(getattr(self, name), name, InconsistentRebalancePlanError),
            )
        if self.current_price <= _ZERO:
            raise InconsistentRebalancePlanError("current_price must be positive")
        for name in (
            "current_quantity",
            "target_weight",
            "target_market_value",
            "target_quantity",
            "requested_quantity",
            "planned_quantity",
            "estimated_gross_notional",
            "estimated_commission",
        ):
            if getattr(self, name) < _ZERO:
                raise InconsistentRebalancePlanError(f"{name} must be nonnegative")
        if self.requested_quantity <= _ZERO or self.planned_quantity <= _ZERO:
            raise InconsistentRebalancePlanError(
                "requested and planned quantities must be positive"
            )
        if self.planned_quantity > self.requested_quantity:
            raise InconsistentRebalancePlanError(
                "planned_quantity cannot exceed requested_quantity"
            )
        if self.side is PlannedTradeSide.SELL and (
            self.planned_quantity > self.current_quantity
        ):
            raise InconsistentRebalancePlanError(
                "planned sell cannot exceed current quantity"
            )
        if self.estimated_gross_notional != (
            self.planned_quantity * self.current_price
        ):
            raise InconsistentRebalancePlanError(
                "gross notional must equal planned quantity times price"
            )
        expected_cash = (
            self.estimated_gross_notional - self.estimated_commission
            if self.side is PlannedTradeSide.SELL
            else -(self.estimated_gross_notional + self.estimated_commission)
        )
        if self.estimated_net_cash_effect != expected_cash:
            raise InconsistentRebalancePlanError(
                "net cash effect does not match trade side"
            )


class UnplannedAllocationReason(StrEnum):
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    COMMISSION_EXCEEDS_SELL_PROCEEDS = "COMMISSION_EXCEEDS_SELL_PROCEEDS"
    ROUNDED_TO_ZERO = "ROUNDED_TO_ZERO"
    BELOW_MINIMUM_QUANTITY = "BELOW_MINIMUM_QUANTITY"
    BELOW_MINIMUM_NOTIONAL = "BELOW_MINIMUM_NOTIONAL"
    INSUFFICIENT_BUY_CASH = "INSUFFICIENT_BUY_CASH"
    QUANTITY_ROUNDING = "QUANTITY_ROUNDING"


@dataclass(frozen=True, slots=True)
class RebalanceDeviation:
    symbol: Symbol
    symbol_ordinal: int
    target_weight: Decimal
    estimated_achieved_weight: Decimal
    signed_weight_deviation: Decimal
    absolute_weight_deviation: Decimal
    target_market_value: Decimal
    estimated_achieved_market_value: Decimal
    target_quantity: Decimal
    estimated_achieved_quantity: Decimal
    limiting_reason: UnplannedAllocationReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InconsistentRebalancePlanError("symbol must be a Symbol")
        if (
            not isinstance(self.symbol_ordinal, int)
            or isinstance(self.symbol_ordinal, bool)
            or self.symbol_ordinal < 0
        ):
            raise InconsistentRebalancePlanError(
                "symbol_ordinal must be a nonnegative integer"
            )
        for name in (
            "target_weight",
            "estimated_achieved_weight",
            "signed_weight_deviation",
            "absolute_weight_deviation",
            "target_market_value",
            "estimated_achieved_market_value",
            "target_quantity",
            "estimated_achieved_quantity",
        ):
            _decimal(getattr(self, name), name, InconsistentRebalancePlanError)
        if self.signed_weight_deviation != (
            self.estimated_achieved_weight - self.target_weight
        ):
            raise InconsistentRebalancePlanError("signed deviation does not reconcile")
        if self.absolute_weight_deviation != abs(self.signed_weight_deviation):
            raise InconsistentRebalancePlanError(
                "absolute deviation does not reconcile"
            )
        for name in (
            "target_weight",
            "estimated_achieved_weight",
            "absolute_weight_deviation",
            "target_market_value",
            "estimated_achieved_market_value",
            "target_quantity",
            "estimated_achieved_quantity",
        ):
            if getattr(self, name) < _ZERO:
                raise InconsistentRebalancePlanError(f"{name} must be nonnegative")
        if self.limiting_reason is not None and not isinstance(
            self.limiting_reason, UnplannedAllocationReason
        ):
            raise InconsistentRebalancePlanError(
                "limiting_reason must be UnplannedAllocationReason or None"
            )


class RebalanceStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_ACTION = "NO_ACTION"
    INFEASIBLE = "INFEASIBLE"


class RebalanceDiagnosticCode(StrEnum):
    CANONICAL_FUNDING_PRIORITY_APPLIED = "CANONICAL_FUNDING_PRIORITY_APPLIED"
    PROTECTED_CASH_UNAVAILABLE = "PROTECTED_CASH_UNAVAILABLE"
    NONPOSITIVE_ENDING_EQUITY = "NONPOSITIVE_ENDING_EQUITY"


@dataclass(frozen=True, slots=True)
class RebalanceDiagnostic:
    code: RebalanceDiagnosticCode
    message: str
    symbol: Symbol | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, RebalanceDiagnosticCode):
            raise InconsistentRebalancePlanError(
                "code must be a RebalanceDiagnosticCode"
            )
        if not isinstance(self.message, str) or not self.message.strip():
            raise InconsistentRebalancePlanError("message must be nonblank")
        if self.symbol is not None and not isinstance(self.symbol, Symbol):
            raise InconsistentRebalancePlanError("symbol must be Symbol or None")


@dataclass(frozen=True, slots=True)
class RebalancePlan:
    plan_id: UUID
    request: RebalancePlanRequest
    status: RebalanceStatus
    trades: tuple[PlannedTrade, ...]
    deviations: tuple[RebalanceDeviation, ...]
    diagnostics: tuple[RebalanceDiagnostic, ...]
    planning_equity: Decimal
    target_cash_value: Decimal
    estimated_starting_cash: Decimal
    estimated_gross_sell_proceeds: Decimal
    estimated_gross_buy_cost: Decimal
    estimated_commissions: Decimal
    estimated_ending_cash: Decimal
    estimated_ending_equity: Decimal
    estimated_achieved_cash_weight: Decimal | None
    estimated_target_cash_value_at_ending_equity: Decimal | None
    cash_value_deviation: Decimal | None
    cash_weight_deviation: Decimal | None
    estimated_constraints_satisfied: bool

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, UUID):
            raise InconsistentRebalancePlanError("plan_id must be a UUID")
        if not isinstance(self.request, RebalancePlanRequest):
            raise InconsistentRebalancePlanError(
                "request must be a RebalancePlanRequest"
            )
        if not isinstance(self.status, RebalanceStatus):
            raise InconsistentRebalancePlanError("status must be RebalanceStatus")
        for name, item_type in (
            ("trades", PlannedTrade),
            ("deviations", RebalanceDeviation),
            ("diagnostics", RebalanceDiagnostic),
        ):
            items = tuple(getattr(self, name))
            if not all(isinstance(item, item_type) for item in items):
                raise InconsistentRebalancePlanError(f"invalid {name}")
            object.__setattr__(self, name, items)
        if len(self.deviations) != len(self.request.state.symbols):
            raise InconsistentRebalancePlanError(
                "one deviation is required per configured symbol"
            )
        if tuple(item.symbol for item in self.deviations) != self.request.state.symbols:
            raise InconsistentRebalancePlanError(
                "deviations must follow configured symbol order"
            )
        ids = tuple(item.planned_trade_id for item in self.trades)
        symbols = tuple(item.symbol for item in self.trades)
        if len(set(ids)) != len(ids) or len(set(symbols)) != len(symbols):
            raise InconsistentRebalancePlanError("trade IDs and symbols must be unique")
        seen_buy = False
        last_ordinal = -1
        for trade in self.trades:
            if trade.side is PlannedTradeSide.BUY:
                if not seen_buy:
                    seen_buy = True
                    last_ordinal = -1
            elif seen_buy:
                raise InconsistentRebalancePlanError("sells must precede buys")
            if trade.symbol_ordinal <= last_ordinal:
                raise InconsistentRebalancePlanError(
                    "trade ordinals must increase within each side"
                )
            last_ordinal = trade.symbol_ordinal
            if trade.symbol_ordinal >= len(self.request.state.positions):
                raise InconsistentRebalancePlanError(
                    "trade symbol ordinal is outside the universe"
                )
            position = self.request.state.positions[trade.symbol_ordinal]
            allocation = self.request.target.allocations[trade.symbol_ordinal]
            if (
                trade.symbol != position.symbol
                or trade.current_price != position.current_price
                or trade.current_quantity != position.quantity
                or trade.target_weight != allocation.weight
            ):
                raise InconsistentRebalancePlanError(
                    "trade does not match state and target at its ordinal"
                )
            target_value = allocation.weight * self.request.state.equity
            target_quantity = target_value / position.current_price
            if (
                trade.target_market_value != target_value
                or trade.target_quantity != target_quantity
            ):
                raise InconsistentRebalancePlanError(
                    "trade target values do not reconcile"
                )
            requested = (
                position.quantity - target_quantity
                if trade.side is PlannedTradeSide.SELL
                else target_quantity - position.quantity
            )
            if trade.requested_quantity != requested:
                raise InconsistentRebalancePlanError(
                    "trade requested quantity does not reconcile"
                )
            if trade.estimated_commission != self.request.assumptions.fixed_commission:
                raise InconsistentRebalancePlanError(
                    "trade commission does not match assumptions"
                )
            exact_full_exit = (
                trade.side is PlannedTradeSide.SELL
                and allocation.weight == _ZERO
                and trade.planned_quantity == position.quantity
            )
            if not exact_full_exit and (
                trade.planned_quantity % self.request.assumptions.quantity_increment
                != _ZERO
            ):
                raise InconsistentRebalancePlanError(
                    "non-liquidation trade must align to quantity increment"
                )
        for name in (
            "planning_equity",
            "target_cash_value",
            "estimated_starting_cash",
            "estimated_gross_sell_proceeds",
            "estimated_gross_buy_cost",
            "estimated_commissions",
            "estimated_ending_cash",
            "estimated_ending_equity",
        ):
            _decimal(getattr(self, name), name, InconsistentRebalancePlanError)
        expected_cash = (
            self.estimated_starting_cash
            + self.estimated_gross_sell_proceeds
            - self.estimated_gross_buy_cost
            - self.estimated_commissions
        )
        if self.estimated_ending_cash != expected_cash:
            raise InconsistentRebalancePlanError("ending cash does not reconcile")
        if self.estimated_ending_cash < _ZERO:
            raise InconsistentRebalancePlanError("ending cash cannot be negative")
        if self.planning_equity != self.request.state.equity:
            raise InconsistentRebalancePlanError(
                "planning equity must equal current state equity"
            )
        if self.target_cash_value != (
            self.request.target.cash_weight * self.planning_equity
        ):
            raise InconsistentRebalancePlanError("target cash value does not reconcile")
        if self.estimated_starting_cash != self.request.state.cash:
            raise InconsistentRebalancePlanError(
                "starting cash must equal request state cash"
            )
        if self.estimated_gross_sell_proceeds != sum(
            (item.estimated_gross_notional for item in self.planned_sells),
            start=_ZERO,
        ):
            raise InconsistentRebalancePlanError("gross sell proceeds do not reconcile")
        if self.estimated_gross_buy_cost != sum(
            (item.estimated_gross_notional for item in self.planned_buys),
            start=_ZERO,
        ):
            raise InconsistentRebalancePlanError("gross buy cost does not reconcile")
        if self.estimated_commissions != sum(
            (item.estimated_commission for item in self.trades), start=_ZERO
        ):
            raise InconsistentRebalancePlanError("commissions do not reconcile")
        achieved_value = sum(
            (item.estimated_achieved_market_value for item in self.deviations),
            start=_ZERO,
        )
        if self.estimated_ending_equity != self.estimated_ending_cash + achieved_value:
            raise InconsistentRebalancePlanError("ending equity does not reconcile")
        optional_names = (
            "estimated_achieved_cash_weight",
            "estimated_target_cash_value_at_ending_equity",
            "cash_value_deviation",
            "cash_weight_deviation",
        )
        if self.status is RebalanceStatus.INFEASIBLE:
            if self.trades:
                raise InconsistentRebalancePlanError(
                    "infeasible plans cannot contain trades"
                )
        elif any(getattr(self, name) is None for name in optional_names):
            raise InconsistentRebalancePlanError(
                "feasible plans require calculated cash metrics"
            )
        if all(getattr(self, name) is not None for name in optional_names):
            achieved_cash_weight = (
                self.estimated_ending_cash / self.estimated_ending_equity
            )
            target_cash_at_end = (
                self.request.target.cash_weight * self.estimated_ending_equity
            )
            if self.estimated_achieved_cash_weight != achieved_cash_weight:
                raise InconsistentRebalancePlanError(
                    "achieved cash weight does not reconcile"
                )
            if self.estimated_target_cash_value_at_ending_equity != target_cash_at_end:
                raise InconsistentRebalancePlanError(
                    "ending target cash value does not reconcile"
                )
            if self.cash_value_deviation != (
                self.estimated_ending_cash - target_cash_at_end
            ):
                raise InconsistentRebalancePlanError(
                    "cash value deviation does not reconcile"
                )
            if self.cash_weight_deviation != (
                achieved_cash_weight - self.request.target.cash_weight
            ):
                raise InconsistentRebalancePlanError(
                    "cash weight deviation does not reconcile"
                )
        if not isinstance(self.estimated_constraints_satisfied, bool):
            raise InconsistentRebalancePlanError(
                "estimated_constraints_satisfied must be bool"
            )

    @property
    def planned_sells(self) -> tuple[PlannedTrade, ...]:
        return tuple(item for item in self.trades if item.side is PlannedTradeSide.SELL)

    @property
    def planned_buys(self) -> tuple[PlannedTrade, ...]:
        return tuple(item for item in self.trades if item.side is PlannedTradeSide.BUY)
