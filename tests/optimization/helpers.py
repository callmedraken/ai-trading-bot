from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.market_data import Timeframe
from trading_bot.portfolio import (
    ExpectedReturn,
    ForecastHorizon,
    MeanCvarOptimizationParameters,
    MeanCvarOptimizationRequest,
    PortfolioConstraints,
    PortfolioOptimizationRequest,
    PortfolioPositionState,
    PortfolioState,
    ReturnScenario,
    ReturnScenarioSet,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
HORIZON = ForecastHorizon(5, Timeframe.DAY_1)


def mean_cvar_request(
    *,
    constraints: PortfolioConstraints | None = None,
    parameters: MeanCvarOptimizationParameters | None = None,
    expected: tuple[str, str] = ("0.10", "0.04"),
) -> MeanCvarOptimizationRequest:
    state = PortfolioState(
        NOW,
        (
            PortfolioPositionState(SPY, Decimal("2"), Decimal("100"), Decimal("100")),
            PortfolioPositionState(QQQ, Decimal("2"), Decimal("100"), Decimal("100")),
        ),
        Decimal("600"),
        Decimal("1000"),
    )
    base = PortfolioOptimizationRequest(
        UUID(int=10),
        state,
        constraints or PortfolioConstraints(),
        (
            ExpectedReturn(SPY, Decimal(expected[0])),
            ExpectedReturn(QQQ, Decimal(expected[1])),
        ),
        HORIZON,
        Decimal("2"),
    )
    scenarios = ReturnScenarioSet(
        UUID(int=20),
        NOW,
        HORIZON,
        (SPY, QQQ),
        (
            ReturnScenario(
                UUID(int=21), (Decimal("0.10"), Decimal("0.02")), Decimal("0.25")
            ),
            ReturnScenario(
                UUID(int=22),
                (Decimal("-0.20"), Decimal("0.01")),
                Decimal("0.75"),
            ),
        ),
        Decimal("0.01"),
    )
    return MeanCvarOptimizationRequest(
        base,
        scenarios,
        parameters or MeanCvarOptimizationParameters(Decimal("0.75")),
    )


def solver_result(status: int, x: list[float] | None = None) -> SimpleNamespace:
    return SimpleNamespace(status=status, x=x, message=f"status {status}", nit=3)


def fake_solver(result: SimpleNamespace):
    def solve(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return result

    return solve
