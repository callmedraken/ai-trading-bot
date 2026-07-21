from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trading_bot.portfolio_analytics import PortfolioExposureRecord


def test_exposure_record_is_immutable_and_validates_ratio() -> None:
    record = PortfolioExposureRecord(
        datetime(2026, 1, 5, tzinfo=UTC),
        Decimal("25"),
        Decimal("100"),
        Decimal("0.25"),
        True,
    )
    with pytest.raises(FrozenInstanceError):
        record.equity = Decimal("1")  # type: ignore[misc]
    with pytest.raises(ValueError, match="does not match"):
        PortfolioExposureRecord(
            record.timestamp,
            Decimal("25"),
            Decimal("100"),
            Decimal("0.5"),
            True,
        )


def test_exposure_record_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        PortfolioExposureRecord(
            datetime(2026, 1, 5, tzinfo=UTC),
            Decimal("0"),
            Decimal("Infinity"),
            Decimal("0"),
            False,
        )
