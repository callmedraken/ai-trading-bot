"""Pure certification of optimizer-produced target portfolios."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid5

from trading_bot.portfolio.exceptions import (
    InconsistentOptimizedTargetResultError,
    IneligibleOptimizedTargetError,
    InvalidOptimizedTargetOutputError,
    InvalidOptimizedTargetRequestError,
    OptimizedTargetStateMismatchError,
)
from trading_bot.portfolio.mean_cvar import MeanCvarOptimizationResult
from trading_bot.portfolio.models import (
    AllocationSource,
    MetadataEntry,
    OptimizationStatus,
    PortfolioState,
    TargetAllocation,
    TargetPortfolio,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_VERSION = "optimizer-target-adapter-v1"
_NAMESPACE = UUID("be2e219f-2371-51d6-a915-4ce3a081e054")
_RESERVED_PREFIX = "optimized_target_"


def _canonical_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("identity Decimal values must be finite Decimal values")
    normalized = _ZERO if value == _ZERO else value.normalize()
    return format(normalized, "f")


@dataclass(frozen=True, slots=True)
class OptimizedTargetRequest:
    request_id: UUID
    optimization_result: MeanCvarOptimizationResult
    state: PortfolioState
    metadata: tuple[MetadataEntry, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidOptimizedTargetRequestError
        if not isinstance(self.request_id, UUID):
            raise error("request_id must be a UUID")
        if not isinstance(self.optimization_result, MeanCvarOptimizationResult):
            raise error("optimization_result must be a MeanCvarOptimizationResult")
        if not isinstance(self.state, PortfolioState):
            raise error("state must be a PortfolioState")
        try:
            metadata = tuple(self.metadata)
        except TypeError as caught:
            raise error("metadata must be iterable") from caught
        if not all(isinstance(item, MetadataEntry) for item in metadata):
            raise error("metadata must contain MetadataEntry values")
        if len({item.key for item in metadata}) != len(metadata):
            raise error("metadata keys must be unique")
        if any(item.key.startswith(_RESERVED_PREFIX) for item in metadata):
            raise error("optimized_target_ metadata keys are reserved")
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True, slots=True)
class OptimizedTargetResult:
    result_id: UUID
    request: OptimizedTargetRequest
    target: TargetPortfolio

    def __post_init__(self) -> None:
        error = InconsistentOptimizedTargetResultError
        if not isinstance(self.result_id, UUID):
            raise error("result_id must be a UUID")
        if not isinstance(self.request, OptimizedTargetRequest):
            raise error("request must be an OptimizedTargetRequest")
        if not isinstance(self.target, TargetPortfolio):
            raise error("target must be a TargetPortfolio")
        source_target = self.request.optimization_result.optimization_result.target
        if source_target is None or self.target != source_target:
            raise error("target must equal the optimizer result target")
        if self.target.target_id != source_target.target_id:
            raise error("target ID must match the optimizer result target ID")
        if self.result_id != _result_id(self.request, self.target):
            raise error("result_id does not match deterministic identity")


class OptimizedTargetPortfolioFactory:
    """Certify an exact optimizer target for one exact intended state."""

    def create(self, request: OptimizedTargetRequest) -> OptimizedTargetResult:
        if not isinstance(request, OptimizedTargetRequest):
            raise TypeError("request must be an OptimizedTargetRequest")
        mean_cvar = request.optimization_result
        portfolio_result = mean_cvar.optimization_result
        if (
            portfolio_result.status is not OptimizationStatus.OPTIMAL
            or portfolio_result.target is None
        ):
            raise IneligibleOptimizedTargetError(
                "only OPTIMAL optimizer results with a target are eligible"
            )
        base = mean_cvar.request.base_request
        if request.state != base.state:
            raise OptimizedTargetStateMismatchError(
                "intended state must exactly equal the optimizer base state"
            )
        target = portfolio_result.target
        if not isinstance(target, TargetPortfolio):
            raise InvalidOptimizedTargetOutputError(
                "optimizer target must be a TargetPortfolio"
            )
        expected_symbols = request.state.symbols
        if (
            tuple(item.symbol for item in base.expected_returns) != expected_symbols
            or mean_cvar.request.scenarios.symbols != expected_symbols
        ):
            raise OptimizedTargetStateMismatchError(
                "state, forecasts, and scenarios must share exact symbol order"
            )
        if (
            base.as_of != request.state.as_of
            or mean_cvar.request.scenarios.as_of != request.state.as_of
            or target.as_of != request.state.as_of
        ):
            raise OptimizedTargetStateMismatchError(
                "state, optimizer inputs, scenarios, and target timestamps must match"
            )
        _validate_target(target, portfolio_result.solver_name, expected_symbols)
        return OptimizedTargetResult(_result_id(request, target), request, target)


def _validate_target(
    target: TargetPortfolio,
    solver_name: str,
    expected_symbols: tuple,
) -> None:
    error = InvalidOptimizedTargetOutputError
    if not isinstance(target, TargetPortfolio):
        raise error("optimizer target must be a TargetPortfolio")
    allocations = target.allocations
    if not allocations or not all(
        isinstance(item, TargetAllocation) for item in allocations
    ):
        raise error("target allocations must contain TargetAllocation values")
    symbols = tuple(item.symbol for item in allocations)
    if symbols != expected_symbols or len(set(symbols)) != len(symbols):
        raise error("target allocations must preserve the exact unique symbol order")
    for allocation in allocations:
        weight = allocation.weight
        if (
            not isinstance(weight, Decimal)
            or not weight.is_finite()
            or not _ZERO <= weight <= _ONE
        ):
            raise error("target allocation weights must be finite Decimals in [0, 1]")
    cash = target.cash_weight
    if (
        not isinstance(cash, Decimal)
        or not cash.is_finite()
        or not _ZERO <= cash <= _ONE
    ):
        raise error("target cash weight must be a finite Decimal in [0, 1]")
    if cash + sum((item.weight for item in allocations), start=_ZERO) != _ONE:
        raise error("target cash and allocation weights must total exactly one")
    if (
        target.source is not AllocationSource.OPTIMIZER
        or target.source_name != solver_name
    ):
        raise error("target optimizer source provenance does not match solver name")


def _state_fingerprint(state: PortfolioState) -> str:
    return "|".join(
        (
            state.as_of.isoformat(),
            _canonical_decimal(state.cash),
            _canonical_decimal(state.equity),
            *(
                ":".join(
                    (
                        str(item.symbol),
                        _canonical_decimal(item.quantity),
                        _canonical_decimal(item.average_cost),
                        _canonical_decimal(item.current_price),
                    )
                )
                for item in state.positions
            ),
        )
    )


def _result_id(request: OptimizedTargetRequest, target: TargetPortfolio) -> UUID:
    portfolio_result = request.optimization_result.optimization_result
    material = "|".join(
        (
            _VERSION,
            str(request.request_id),
            str(portfolio_result.result_id),
            str(target.target_id),
            _state_fingerprint(request.state),
            target.as_of.isoformat(),
            *(
                f"{item.symbol}:{_canonical_decimal(item.weight)}"
                for item in target.allocations
            ),
            _canonical_decimal(target.cash_weight),
            *(f"{item.key}={item.value}" for item in request.metadata),
        )
    )
    return uuid5(_NAMESPACE, material)
