from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trading_bot.ledger import AccountSnapshot

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def snapshot(**overrides: object) -> AccountSnapshot:
    values: dict[str, object] = {
        "timestamp": NOW,
        "cash": Decimal("100"),
        "positions_market_value": Decimal("50"),
        "equity": Decimal("150"),
        "buying_power": Decimal("100"),
        "realized_profit_loss": Decimal("10"),
        "unrealized_profit_loss": Decimal("-5"),
    }
    values.update(overrides)
    return AccountSnapshot(**values)  # type: ignore[arg-type]


def test_valid_snapshot_is_immutable() -> None:
    account = snapshot()
    with pytest.raises(FrozenInstanceError):
        account.cash = Decimal("0")  # type: ignore[misc]


def test_snapshot_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        snapshot(timestamp=datetime(2026, 1, 2))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("cash", Decimal("-1"), "cash cannot be negative"),
        ("positions_market_value", Decimal("-1"), "cannot be negative"),
        ("equity", Decimal("149"), "equity must equal"),
        ("buying_power", Decimal("99"), "buying_power must equal cash"),
    ],
)
def test_snapshot_rejects_inconsistent_values(
    field: str, value: Decimal, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        snapshot(**{field: value})
