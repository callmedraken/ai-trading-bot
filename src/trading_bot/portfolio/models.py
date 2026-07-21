"""Immutable deterministic portfolio-domain contracts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.market_data import Timeframe
from trading_bot.portfolio.exceptions import (
    InvalidOptimizationRequestError,
    InvalidOptimizationResultError,
    InvalidPortfolioConstraintsError,
    InvalidPortfolioStateError,
    InvalidTargetPortfolioError,
    PortfolioConstraintViolationError,
    PortfolioUniverseMismatchError,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _decimal(value: Decimal, name: str, error_type: type[ValueError]) -> Decimal:
    if not isinstance(value, Decimal):
        raise error_type(f"{name} must be a Decimal")
    if not value.is_finite():
        raise error_type(f"{name} must be finite")
    return _ZERO if value == _ZERO else value


def _uuid(value: UUID, name: str, error_type: type[ValueError]) -> None:
    if not isinstance(value, UUID):
        raise error_type(f"{name} must be a UUID")


def _metadata(
    values: tuple["MetadataEntry", ...], error_type: type[ValueError]
) -> tuple["MetadataEntry", ...]:
    try:
        items = tuple(values)
    except TypeError as error:
        raise error_type("metadata must be iterable") from error
    if not all(isinstance(item, MetadataEntry) for item in items):
        raise error_type("metadata must contain only MetadataEntry values")
    keys = tuple(item.key for item in items)
    if len(set(keys)) != len(keys):
        raise error_type("metadata keys must be unique")
    return items


@dataclass(frozen=True, slots=True)
class MetadataEntry:
    """One deterministic string metadata entry."""

    key: str
    value: str

    def __post_init__(self) -> None:
        for name in ("key", "value"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must be nonblank")


@dataclass(frozen=True, slots=True)
class PortfolioPositionState:
    """One explicit open or flat symbol entry in a current portfolio."""

    symbol: Symbol
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidPortfolioStateError("symbol must be a Symbol")
        for name in ("quantity", "average_cost", "current_price"):
            object.__setattr__(
                self,
                name,
                _decimal(getattr(self, name), name, InvalidPortfolioStateError),
            )
        if self.quantity < _ZERO:
            raise InvalidPortfolioStateError("quantity must be nonnegative")
        if self.current_price <= _ZERO:
            raise InvalidPortfolioStateError("current_price must be positive")
        if self.quantity == _ZERO and self.average_cost != _ZERO:
            raise InvalidPortfolioStateError(
                "flat position entries require zero average_cost"
            )
        if self.quantity > _ZERO and self.average_cost <= _ZERO:
            raise InvalidPortfolioStateError(
                "open position entries require positive average_cost"
            )

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.current_price


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """A complete ordered portfolio valuation at one exact UTC timestamp."""

    as_of: datetime
    positions: tuple[PortfolioPositionState, ...]
    cash: Decimal
    equity: Decimal

    def __post_init__(self) -> None:
        try:
            as_of = normalize_utc(self.as_of, "as_of")
        except (TypeError, ValueError) as error:
            raise InvalidPortfolioStateError(str(error)) from error
        try:
            positions = tuple(self.positions)
        except TypeError as error:
            raise InvalidPortfolioStateError("positions must be iterable") from error
        if not positions:
            raise InvalidPortfolioStateError("positions must not be empty")
        if not all(isinstance(item, PortfolioPositionState) for item in positions):
            raise InvalidPortfolioStateError(
                "positions must contain only PortfolioPositionState values"
            )
        symbols = tuple(item.symbol for item in positions)
        if len(set(symbols)) != len(symbols):
            raise InvalidPortfolioStateError("position symbols must be unique")
        cash = _decimal(self.cash, "cash", InvalidPortfolioStateError)
        equity = _decimal(self.equity, "equity", InvalidPortfolioStateError)
        if cash < _ZERO:
            raise InvalidPortfolioStateError("cash must be nonnegative")
        if equity <= _ZERO:
            raise InvalidPortfolioStateError("equity must be positive")
        expected_equity = cash + sum(
            (item.market_value for item in positions), start=_ZERO
        )
        if equity != expected_equity:
            raise InvalidPortfolioStateError(
                "equity must equal cash plus derived position market values"
            )
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "equity", equity)

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        return tuple(item.symbol for item in self.positions)

    @property
    def position_weights(self) -> tuple[Decimal, ...]:
        return tuple(item.market_value / self.equity for item in self.positions)

    @property
    def cash_weight(self) -> Decimal:
        return self.cash / self.equity


@dataclass(frozen=True, slots=True)
class TargetAllocation:
    """One symbol's explicit target weight."""

    symbol: Symbol
    weight: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidTargetPortfolioError("symbol must be a Symbol")
        weight = _decimal(self.weight, "weight", InvalidTargetPortfolioError)
        if not _ZERO <= weight <= _ONE:
            raise InvalidTargetPortfolioError("weight must be between zero and one")
        object.__setattr__(self, "weight", weight)


class AllocationSource(StrEnum):
    MANUAL = "MANUAL"
    OPTIMIZER = "OPTIMIZER"
    IMPORTED = "IMPORTED"


@dataclass(frozen=True, slots=True)
class TargetPortfolio:
    """A structurally valid complete ordered target allocation."""

    target_id: UUID
    as_of: datetime
    allocations: tuple[TargetAllocation, ...]
    cash_weight: Decimal
    source: AllocationSource
    source_name: str | None = None
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        _uuid(self.target_id, "target_id", InvalidTargetPortfolioError)
        try:
            as_of = normalize_utc(self.as_of, "as_of")
        except (TypeError, ValueError) as error:
            raise InvalidTargetPortfolioError(str(error)) from error
        try:
            allocations = tuple(self.allocations)
        except TypeError as error:
            raise InvalidTargetPortfolioError("allocations must be iterable") from error
        if not allocations or not all(
            isinstance(item, TargetAllocation) for item in allocations
        ):
            raise InvalidTargetPortfolioError(
                "allocations must contain at least one TargetAllocation"
            )
        symbols = tuple(item.symbol for item in allocations)
        if len(set(symbols)) != len(symbols):
            raise InvalidTargetPortfolioError("allocation symbols must be unique")
        cash_weight = _decimal(
            self.cash_weight, "cash_weight", InvalidTargetPortfolioError
        )
        if not _ZERO <= cash_weight <= _ONE:
            raise InvalidTargetPortfolioError(
                "cash_weight must be between zero and one"
            )
        total = cash_weight + sum((item.weight for item in allocations), start=_ZERO)
        if total != _ONE:
            raise InvalidTargetPortfolioError(
                "symbol weights plus cash_weight must equal exactly one"
            )
        if not isinstance(self.source, AllocationSource):
            raise InvalidTargetPortfolioError("source must be an AllocationSource")
        if self.source_name is not None and (
            not isinstance(self.source_name, str) or not self.source_name.strip()
        ):
            raise InvalidTargetPortfolioError(
                "source_name must be nonblank when provided"
            )
        if self.source is AllocationSource.OPTIMIZER and self.source_name is None:
            raise InvalidTargetPortfolioError("optimizer targets require source_name")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "allocations", allocations)
        object.__setattr__(self, "cash_weight", cash_weight)
        object.__setattr__(
            self, "metadata", _metadata(self.metadata, InvalidTargetPortfolioError)
        )

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        return tuple(item.symbol for item in self.allocations)

    def total_weight_change(self, state: PortfolioState) -> Decimal:
        self._require_state_universe(state)
        symbol_change = sum(
            (
                abs(target.weight - current)
                for target, current in zip(
                    self.allocations, state.position_weights, strict=True
                )
            ),
            start=_ZERO,
        )
        return symbol_change + abs(self.cash_weight - state.cash_weight)

    def one_way_rebalance_turnover(self, state: PortfolioState) -> Decimal:
        return self.total_weight_change(state) / Decimal("2")

    def _require_state_universe(self, state: PortfolioState) -> None:
        if not isinstance(state, PortfolioState):
            raise TypeError("state must be a PortfolioState")
        if self.symbols != state.symbols:
            raise PortfolioUniverseMismatchError(
                "target and state ordered universes must match exactly"
            )


@dataclass(frozen=True, slots=True)
class PortfolioConstraints:
    """Allocation-stage constraints, separate from trade-level risk limits."""

    minimum_cash_weight: Decimal = _ZERO
    maximum_cash_weight: Decimal = _ONE
    maximum_position_weight: Decimal = _ONE
    maximum_one_way_rebalance_turnover: Decimal | None = None
    minimum_position_weight: Decimal | None = None
    long_only: bool = True
    allow_leverage: bool = False

    def __post_init__(self) -> None:
        for name in (
            "minimum_cash_weight",
            "maximum_cash_weight",
            "maximum_position_weight",
        ):
            object.__setattr__(
                self,
                name,
                _decimal(getattr(self, name), name, InvalidPortfolioConstraintsError),
            )
        if not _ZERO <= self.minimum_cash_weight <= _ONE:
            raise InvalidPortfolioConstraintsError(
                "minimum_cash_weight must be between zero and one"
            )
        if not _ZERO <= self.maximum_cash_weight <= _ONE:
            raise InvalidPortfolioConstraintsError(
                "maximum_cash_weight must be between zero and one"
            )
        if self.minimum_cash_weight > self.maximum_cash_weight:
            raise InvalidPortfolioConstraintsError(
                "minimum_cash_weight cannot exceed maximum_cash_weight"
            )
        if not _ZERO < self.maximum_position_weight <= _ONE:
            raise InvalidPortfolioConstraintsError(
                "maximum_position_weight must be positive and at most one"
            )
        for name in (
            "maximum_one_way_rebalance_turnover",
            "minimum_position_weight",
        ):
            value = getattr(self, name)
            if value is not None:
                value = _decimal(value, name, InvalidPortfolioConstraintsError)
                object.__setattr__(self, name, value)
        if (
            self.maximum_one_way_rebalance_turnover is not None
            and self.maximum_one_way_rebalance_turnover < _ZERO
        ):
            raise InvalidPortfolioConstraintsError(
                "maximum_one_way_rebalance_turnover must be nonnegative"
            )
        if self.minimum_position_weight is not None and not (
            _ZERO < self.minimum_position_weight <= self.maximum_position_weight
        ):
            raise InvalidPortfolioConstraintsError(
                "minimum_position_weight must be positive and no greater than maximum"
            )
        if self.long_only is not True:
            raise InvalidPortfolioConstraintsError("long_only must remain true")
        if self.allow_leverage is not False:
            raise InvalidPortfolioConstraintsError("allow_leverage must remain false")

    def validate_target(self, state: PortfolioState, target: TargetPortfolio) -> None:
        if not isinstance(state, PortfolioState):
            raise TypeError("state must be a PortfolioState")
        if not isinstance(target, TargetPortfolio):
            raise TypeError("target must be a TargetPortfolio")
        if state.symbols != target.symbols:
            raise PortfolioUniverseMismatchError(
                "target and state ordered universes must match exactly"
            )
        if not (
            self.minimum_cash_weight <= target.cash_weight <= self.maximum_cash_weight
        ):
            raise PortfolioConstraintViolationError(
                "target cash weight is outside configured bounds"
            )
        for allocation in target.allocations:
            if allocation.weight > self.maximum_position_weight:
                raise PortfolioConstraintViolationError(
                    f"target weight for {allocation.symbol} exceeds maximum"
                )
            if (
                self.minimum_position_weight is not None
                and allocation.weight > _ZERO
                and allocation.weight < self.minimum_position_weight
            ):
                raise PortfolioConstraintViolationError(
                    f"positive target weight for {allocation.symbol} is below minimum"
                )
        if self.maximum_one_way_rebalance_turnover is not None:
            turnover = target.one_way_rebalance_turnover(state)
            if turnover > self.maximum_one_way_rebalance_turnover:
                raise PortfolioConstraintViolationError(
                    "target one-way rebalance turnover exceeds maximum"
                )


@dataclass(frozen=True, slots=True)
class ExpectedReturn:
    """Total arithmetic return forecast for one ordered symbol."""

    symbol: Symbol
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, Symbol):
            raise InvalidOptimizationRequestError("symbol must be a Symbol")
        object.__setattr__(
            self,
            "value",
            _decimal(self.value, "value", InvalidOptimizationRequestError),
        )


@dataclass(frozen=True, slots=True)
class ForecastHorizon:
    """The exact, non-annualized period covered by expected returns."""

    periods: int
    timeframe: Timeframe

    def __post_init__(self) -> None:
        if (
            not isinstance(self.periods, int)
            or isinstance(self.periods, bool)
            or self.periods <= 0
        ):
            raise InvalidOptimizationRequestError("periods must be a positive integer")
        if self.timeframe is not Timeframe.DAY_1:
            raise InvalidOptimizationRequestError(
                "forecast horizon currently supports only Timeframe.DAY_1"
            )


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationRequest:
    """Solver-independent immutable portfolio optimization input."""

    request_id: UUID
    state: PortfolioState
    constraints: PortfolioConstraints
    expected_returns: tuple[ExpectedReturn, ...]
    forecast_horizon: ForecastHorizon
    risk_aversion: Decimal
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        _uuid(self.request_id, "request_id", InvalidOptimizationRequestError)
        if not isinstance(self.state, PortfolioState):
            raise InvalidOptimizationRequestError("state must be a PortfolioState")
        if not isinstance(self.constraints, PortfolioConstraints):
            raise InvalidOptimizationRequestError(
                "constraints must be PortfolioConstraints"
            )
        try:
            expected_returns = tuple(self.expected_returns)
        except TypeError as error:
            raise InvalidOptimizationRequestError(
                "expected_returns must be iterable"
            ) from error
        if not all(isinstance(item, ExpectedReturn) for item in expected_returns):
            raise InvalidOptimizationRequestError(
                "expected_returns must contain ExpectedReturn values"
            )
        if tuple(item.symbol for item in expected_returns) != self.state.symbols:
            raise InvalidOptimizationRequestError(
                "expected_returns must exactly match the state universe order"
            )
        if not isinstance(self.forecast_horizon, ForecastHorizon):
            raise InvalidOptimizationRequestError(
                "forecast_horizon must be a ForecastHorizon"
            )
        risk_aversion = _decimal(
            self.risk_aversion, "risk_aversion", InvalidOptimizationRequestError
        )
        if risk_aversion < _ZERO:
            raise InvalidOptimizationRequestError("risk_aversion must be nonnegative")
        object.__setattr__(self, "expected_returns", expected_returns)
        object.__setattr__(self, "risk_aversion", risk_aversion)
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata, InvalidOptimizationRequestError),
        )

    @property
    def as_of(self) -> datetime:
        return self.state.as_of


class OptimizationStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNBOUNDED = "UNBOUNDED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class OptimizationDiagnosticLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class OptimizationDiagnostic:
    """One stable solver diagnostic in application order."""

    code: str
    message: str
    level: OptimizationDiagnosticLevel
    value: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("code", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidOptimizationResultError(f"{name} must be nonblank")
        if not isinstance(self.level, OptimizationDiagnosticLevel):
            raise InvalidOptimizationResultError(
                "level must be an OptimizationDiagnosticLevel"
            )
        if self.value is not None:
            object.__setattr__(
                self,
                "value",
                _decimal(self.value, "value", InvalidOptimizationResultError),
            )


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationResult:
    """Validated immutable output from a portfolio optimizer implementation."""

    result_id: UUID
    request: PortfolioOptimizationRequest
    status: OptimizationStatus
    solver_name: str
    target: TargetPortfolio | None = None
    objective_value: Decimal | None = None
    diagnostics: tuple[OptimizationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        _uuid(self.result_id, "result_id", InvalidOptimizationResultError)
        if not isinstance(self.request, PortfolioOptimizationRequest):
            raise InvalidOptimizationResultError(
                "request must be a PortfolioOptimizationRequest"
            )
        if not isinstance(self.status, OptimizationStatus):
            raise InvalidOptimizationResultError("status must be an OptimizationStatus")
        if not isinstance(self.solver_name, str) or not self.solver_name.strip():
            raise InvalidOptimizationResultError("solver_name must be nonblank")
        if self.objective_value is not None:
            object.__setattr__(
                self,
                "objective_value",
                _decimal(
                    self.objective_value,
                    "objective_value",
                    InvalidOptimizationResultError,
                ),
            )
        try:
            diagnostics = tuple(self.diagnostics)
        except TypeError as error:
            raise InvalidOptimizationResultError(
                "diagnostics must be iterable"
            ) from error
        if not all(isinstance(item, OptimizationDiagnostic) for item in diagnostics):
            raise InvalidOptimizationResultError(
                "diagnostics must contain OptimizationDiagnostic values"
            )
        successful = self.status in {
            OptimizationStatus.OPTIMAL,
            OptimizationStatus.FEASIBLE,
        }
        if successful:
            if not isinstance(self.target, TargetPortfolio):
                raise InvalidOptimizationResultError(
                    "successful results require a target"
                )
            if self.target.as_of != self.request.as_of:
                raise InvalidOptimizationResultError(
                    "successful target as_of must equal request as_of"
                )
            if self.target.source is not AllocationSource.OPTIMIZER:
                raise InvalidOptimizationResultError(
                    "successful target source must be OPTIMIZER"
                )
            if self.target.source_name != self.solver_name:
                raise InvalidOptimizationResultError(
                    "target source_name must equal solver_name"
                )
            self.request.constraints.validate_target(self.request.state, self.target)
        else:
            if self.target is not None or self.objective_value is not None:
                raise InvalidOptimizationResultError(
                    "unsuccessful results prohibit target and objective_value"
                )
            if not diagnostics:
                raise InvalidOptimizationResultError(
                    "unsuccessful results require at least one diagnostic"
                )
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def request_id(self) -> UUID:
        return self.request.request_id
