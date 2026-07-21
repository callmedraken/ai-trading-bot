from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.portfolio import (
    AllocationSource,
    PortfolioConstraints,
    PortfolioPositionState,
    PortfolioState,
    TargetAllocation,
    TargetPortfolio,
)
from trading_bot.rebalancing import (
    InvalidRebalanceAssumptionsError,
    InvalidRebalanceRequestError,
    RebalanceAssumptions,
    RebalancePlanRequest,
    RebalanceTargetConstraintError,
    RebalanceUniverseMismatchError,
    StaleRebalanceTargetError,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def state() -> PortfolioState:
    return PortfolioState(
        NOW,
        (
            PortfolioPositionState(SPY, Decimal("25"), Decimal("8"), Decimal("10")),
            PortfolioPositionState(QQQ, Decimal("0"), Decimal("0"), Decimal("10")),
        ),
        Decimal("750"),
        Decimal("1000"),
    )


def target(as_of: datetime = NOW) -> TargetPortfolio:
    return TargetPortfolio(
        UUID(int=2),
        as_of,
        (
            TargetAllocation(SPY, Decimal("0.2")),
            TargetAllocation(QQQ, Decimal("0.2")),
        ),
        Decimal("0.6"),
        AllocationSource.MANUAL,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("fixed_commission", Decimal("-1")),
        ("fixed_commission", Decimal("Infinity")),
        ("quantity_increment", Decimal("0")),
        ("minimum_trade_notional", Decimal("-1")),
        ("minimum_trade_quantity", Decimal("-1")),
        ("target_weight_tolerance", Decimal("1.1")),
        ("additional_execution_cash_buffer", Decimal("-1")),
    ),
)
def test_assumptions_reject_invalid_decimals(field: str, value: Decimal) -> None:
    values = {field: value}
    with pytest.raises(InvalidRebalanceAssumptionsError):
        RebalanceAssumptions(**values)  # type: ignore[arg-type]


def test_whole_share_mode_requires_unit_increment() -> None:
    with pytest.raises(InvalidRebalanceAssumptionsError, match="whole-share"):
        RebalanceAssumptions(
            allow_fractional_quantities=False,
            quantity_increment=Decimal("0.5"),
        )


def test_request_validates_id_universe_timestamp_and_constraints() -> None:
    with pytest.raises(InvalidRebalanceRequestError, match="UUID"):
        RebalancePlanRequest(  # type: ignore[arg-type]
            "bad", state(), target(), RebalanceAssumptions()
        )
    reversed_target = TargetPortfolio(
        UUID(int=2),
        NOW,
        tuple(reversed(target().allocations)),
        Decimal("0.6"),
        AllocationSource.MANUAL,
    )
    with pytest.raises(RebalanceUniverseMismatchError):
        RebalancePlanRequest(
            UUID(int=1), state(), reversed_target, RebalanceAssumptions()
        )
    with pytest.raises(StaleRebalanceTargetError):
        RebalancePlanRequest(
            UUID(int=1),
            state(),
            target(NOW + timedelta(days=1)),
            RebalanceAssumptions(),
        )
    with pytest.raises(RebalanceTargetConstraintError):
        RebalancePlanRequest(
            UUID(int=1),
            state(),
            target(),
            RebalanceAssumptions(),
            PortfolioConstraints(maximum_position_weight=Decimal("0.1")),
        )
