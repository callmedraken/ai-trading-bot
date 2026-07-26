from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    CalendarDescriptor,
    DailySnapshotCaptureRequest,
    InvalidDailySnapshotRequestError,
    ProviderDescriptor,
    Timeframe,
)


def test_capture_request_normalizes_time_and_preserves_caller_order() -> None:
    request = DailySnapshotCaptureRequest(
        UUID("b6754746-7fba-5c85-a794-b946804ebe89"),
        (Symbol("spy"), Symbol("qqq")),
        datetime.fromisoformat("2025-01-07T10:00:00-08:00"),
        XNYS_CALENDAR_DESCRIPTOR,
    )

    assert request.symbols == (Symbol("SPY"), Symbol("QQQ"))
    assert request.requested_at == datetime(2025, 1, 7, 18, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        request.symbols = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "symbols",
    [
        (),
        (Symbol("SPY"), Symbol("SPY")),
        tuple(Symbol(f"S{index}") for index in range(101)),
        (Symbol("SPY"), "QQQ"),
    ],
)
def test_capture_request_rejects_invalid_universes(symbols) -> None:
    with pytest.raises(InvalidDailySnapshotRequestError):
        DailySnapshotCaptureRequest(
            UUID("b6754746-7fba-5c85-a794-b946804ebe89"),
            symbols,
            datetime(2025, 1, 7, tzinfo=UTC),
            XNYS_CALENDAR_DESCRIPTOR,
        )


def test_capture_request_supports_only_exact_xnys_daily_raw_contract() -> None:
    values = {
        "request_id": UUID("b6754746-7fba-5c85-a794-b946804ebe89"),
        "symbols": (Symbol("SPY"),),
        "requested_at": datetime(2025, 1, 7, tzinfo=UTC),
        "calendar": XNYS_CALENDAR_DESCRIPTOR,
    }
    with pytest.raises(InvalidDailySnapshotRequestError):
        DailySnapshotCaptureRequest(
            **values,
            timeframe="1D",  # type: ignore[arg-type]
        )
    with pytest.raises(InvalidDailySnapshotRequestError):
        DailySnapshotCaptureRequest(
            **values,
            adjustment=AdjustmentType.SPLIT_ADJUSTED,
        )
    with pytest.raises(InvalidDailySnapshotRequestError):
        DailySnapshotCaptureRequest(
            **{
                **values,
                "calendar": CalendarDescriptor(
                    "XNYS", "different-version", "America/New_York"
                ),
            }
        )
    assert Timeframe.DAY_1.value == "1D"


def test_provider_descriptor_rejects_bool_version_and_non_ascii_text() -> None:
    with pytest.raises(ValueError):
        ProviderDescriptor("provider", True, "daily", "feed")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ProviderDescriptor("prøvider", 1, "daily", "feed")
