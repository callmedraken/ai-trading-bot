from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from trading_bot.backtesting import BacktestConfig, InvalidBacktestConfigError
from trading_bot.domain import Symbol
from trading_bot.market_data import HistoricalDataRequest
from trading_bot.risk import RiskLimits


def request() -> HistoricalDataRequest:
    return HistoricalDataRequest(
        Symbol("SPY"),
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("starting_cash", Decimal("0")),
        ("fixed_commission", Decimal("-1")),
        ("slippage_basis_points", Decimal("-1")),
        ("slippage_basis_points", Decimal("10000")),
    ],
)
def test_config_rejects_invalid_financial_values(field: str, value: Decimal) -> None:
    values = {"run_id": uuid4(), "data_request": request(), field: value}
    with pytest.raises(InvalidBacktestConfigError, match=field):
        BacktestConfig(**values)


def test_config_requires_commission_consistency() -> None:
    with pytest.raises(InvalidBacktestConfigError, match="estimated_commission"):
        BacktestConfig(
            uuid4(),
            request(),
            fixed_commission=Decimal("1"),
            risk_limits=RiskLimits(estimated_commission=Decimal("0")),
        )
