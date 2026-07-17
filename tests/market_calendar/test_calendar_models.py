from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from trading_bot.market_calendar import (
    InvalidCalendarInputError,
    TradingSession,
    TradingSessionRange,
)

START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 5, tzinfo=UTC)


def test_trading_session_uses_date_and_is_immutable() -> None:
    session = TradingSession(date(2026, 1, 2))
    assert session.session_date == date(2026, 1, 2)
    with pytest.raises(FrozenInstanceError):
        session.session_date = date(2026, 1, 3)  # type: ignore[misc]
    with pytest.raises(InvalidCalendarInputError, match="date"):
        TradingSession(START)  # type: ignore[arg-type]


def test_range_normalizes_bounds_and_defensively_copies_sessions() -> None:
    local = timezone(timedelta(hours=-8))
    source = [TradingSession(date(2026, 1, 2))]
    result = TradingSessionRange(
        datetime(2025, 12, 31, 16, tzinfo=local),
        datetime(2026, 1, 4, 16, tzinfo=local),
        source,  # type: ignore[arg-type]
    )
    source.clear()
    assert result.request_start == START
    assert result.request_end == END
    assert result.sessions == (TradingSession(date(2026, 1, 2)),)


def test_range_accepts_empty_equal_bounds() -> None:
    result = TradingSessionRange(START, START, ())
    assert result.sessions == ()


def test_range_rejects_naive_reversed_or_unordered_values() -> None:
    with pytest.raises(InvalidCalendarInputError, match="timezone-aware"):
        TradingSessionRange(datetime(2026, 1, 1), END, ())
    with pytest.raises(InvalidCalendarInputError, match="later"):
        TradingSessionRange(END, START, ())
    with pytest.raises(InvalidCalendarInputError, match="ordered"):
        TradingSessionRange(
            START,
            END,
            (
                TradingSession(date(2026, 1, 3)),
                TradingSession(date(2026, 1, 2)),
            ),
        )
    with pytest.raises(InvalidCalendarInputError, match="ordered"):
        TradingSessionRange(
            START,
            END,
            (
                TradingSession(date(2026, 1, 2)),
                TradingSession(date(2026, 1, 2)),
            ),
        )
