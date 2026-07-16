from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from trading_bot.domain import Position, Symbol


def test_position_decimal_calculations() -> None:
    position = Position(Symbol("SPY"), Decimal("2.5"), Decimal("100.20"))
    assert position.market_value(Decimal("110.00")) == Decimal("275.000")
    assert position.unrealized_profit_loss(Decimal("110.00")) == Decimal("24.500")
    assert position.unrealized_profit_loss(Decimal("90.00")) == Decimal("-25.500")


@pytest.mark.parametrize("field", ["quantity", "average_cost"])
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_position_rejects_nonpositive_values(field: str, value: Decimal) -> None:
    values = {"quantity": Decimal("1"), "average_cost": Decimal("100")}
    values[field] = value
    with pytest.raises(ValueError, match=field):
        Position(Symbol("SPY"), **values)


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-1")])
def test_position_rejects_nonpositive_current_price(price: Decimal) -> None:
    position = Position(Symbol("SPY"), Decimal("1"), Decimal("100"))
    with pytest.raises(ValueError, match="current_price"):
        position.market_value(price)
    with pytest.raises(ValueError, match="current_price"):
        position.unrealized_profit_loss(price)


def test_position_is_immutable() -> None:
    position = Position(Symbol("SPY"), Decimal("1"), Decimal("100"))
    with pytest.raises(FrozenInstanceError):
        position.quantity = Decimal("2")  # type: ignore[misc]
