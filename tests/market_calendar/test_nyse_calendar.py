from datetime import UTC, date, datetime, time
from types import MappingProxyType
from zoneinfo import ZoneInfo

import pytest

from trading_bot.market_calendar import (
    MAX_SUPPORTED_YEAR,
    MIN_SUPPORTED_YEAR,
    CalendarDateOutOfRangeError,
    InvalidCalendarInputError,
    MarketCalendar,
    NYSEMarketCalendar,
    TradingSession,
)

NEW_YORK = ZoneInfo("America/New_York")


def local_noon(year: int, month: int, day: int) -> datetime:
    return datetime.combine(
        date(year, month, day), time(12), tzinfo=NEW_YORK
    ).astimezone(UTC)


def test_supported_year_constants_are_public_and_stable() -> None:
    assert MIN_SUPPORTED_YEAR == 1998
    assert MAX_SUPPORTED_YEAR == 2100


def test_calendar_satisfies_protocol_and_handles_weekdays_and_weekends() -> None:
    calendar: MarketCalendar = NYSEMarketCalendar()
    assert calendar.is_trading_session(local_noon(2026, 1, 5))
    assert not calendar.is_trading_session(local_noon(2026, 1, 3))
    assert not calendar.is_trading_session(local_noon(2026, 1, 4))


@pytest.mark.parametrize(
    ("month", "day"),
    [
        (1, 1),
        (1, 15),
        (2, 19),
        (3, 29),
        (5, 27),
        (6, 19),
        (7, 4),
        (9, 2),
        (11, 28),
        (12, 25),
    ],
)
def test_major_2024_nyse_holidays(month: int, day: int) -> None:
    assert not NYSEMarketCalendar().is_trading_session(local_noon(2024, month, day))


def test_non_nyse_federal_holidays_remain_sessions() -> None:
    calendar = NYSEMarketCalendar()
    assert calendar.is_trading_session(local_noon(2024, 10, 14))
    assert calendar.is_trading_session(local_noon(2024, 11, 11))


def test_observed_holidays_and_new_year_saturday_exception() -> None:
    calendar = NYSEMarketCalendar()
    assert not calendar.is_trading_session(local_noon(2021, 7, 5))
    assert not calendar.is_trading_session(local_noon(2021, 12, 24))
    assert calendar.is_trading_session(local_noon(2021, 12, 31))
    assert not calendar.is_trading_session(local_noon(2023, 1, 2))


def test_juneteenth_effective_year() -> None:
    calendar = NYSEMarketCalendar()
    assert calendar.is_trading_session(local_noon(2021, 6, 18))
    assert not calendar.is_trading_session(local_noon(2022, 6, 20))


def test_good_friday_computus_across_years() -> None:
    calendar = NYSEMarketCalendar()
    assert not calendar.is_trading_session(local_noon(2025, 4, 18))
    assert not calendar.is_trading_session(local_noon(2038, 4, 23))


def test_next_and_previous_sessions_are_strict_and_iterative() -> None:
    calendar = NYSEMarketCalendar()
    friday = local_noon(2024, 3, 29)  # Good Friday
    assert calendar.next_session(friday) == TradingSession(date(2024, 4, 1))
    assert calendar.previous_session(friday) == TradingSession(date(2024, 3, 28))
    monday = local_noon(2024, 4, 1)
    assert calendar.next_session(monday) == TradingSession(date(2024, 4, 2))
    assert calendar.previous_session(monday) == TradingSession(date(2024, 3, 28))


def test_sessions_between_is_half_open_and_preserves_request_bounds() -> None:
    calendar = NYSEMarketCalendar()
    start = local_noon(2024, 7, 3)
    end = local_noon(2024, 7, 8)
    result = calendar.sessions_between(start, end)
    assert result.request_start == start
    assert result.request_end == end
    assert result.sessions == (
        TradingSession(date(2024, 7, 3)),
        TradingSession(date(2024, 7, 5)),
    )


def test_empty_and_weekend_only_ranges() -> None:
    calendar = NYSEMarketCalendar()
    same = local_noon(2024, 7, 6)
    assert calendar.sessions_between(same, same).sessions == ()
    assert (
        calendar.sessions_between(
            local_noon(2024, 7, 6), local_noon(2024, 7, 8)
        ).sessions
        == ()
    )


def test_leap_year_and_year_boundary_ranges() -> None:
    calendar = NYSEMarketCalendar()
    leap = calendar.sessions_between(local_noon(2024, 2, 28), local_noon(2024, 3, 1))
    assert TradingSession(date(2024, 2, 29)) in leap.sessions
    boundary = calendar.sessions_between(
        local_noon(2024, 12, 30), local_noon(2025, 1, 3)
    )
    assert boundary.sessions == (
        TradingSession(date(2024, 12, 30)),
        TradingSession(date(2024, 12, 31)),
        TradingSession(date(2025, 1, 2)),
    )


def test_dst_transition_uses_exchange_local_date() -> None:
    calendar = NYSEMarketCalendar()
    before_local_midnight = datetime(2024, 3, 11, 3, 30, tzinfo=UTC)
    after_local_midnight = datetime(2024, 3, 11, 4, 30, tzinfo=UTC)
    assert not calendar.is_trading_session(before_local_midnight)  # Sunday
    assert calendar.is_trading_session(after_local_midnight)  # Monday


def test_holiday_cache_uses_reused_frozenset_per_year() -> None:
    calendar = NYSEMarketCalendar()
    assert dict(calendar.holiday_cache) == {}
    first = calendar._holidays_for_year(2024)
    second = calendar._holidays_for_year(2024)
    assert first is second
    assert isinstance(first, frozenset)
    assert isinstance(calendar.holiday_cache, MappingProxyType)
    assert calendar.holiday_cache[2024] is first


def test_naive_inputs_and_reversed_ranges_are_rejected() -> None:
    calendar = NYSEMarketCalendar()
    with pytest.raises(InvalidCalendarInputError, match="timezone-aware"):
        calendar.is_trading_session(datetime(2024, 1, 2))
    with pytest.raises(InvalidCalendarInputError, match="later"):
        calendar.sessions_between(local_noon(2024, 1, 3), local_noon(2024, 1, 2))


def test_supported_year_boundaries_fail_closed() -> None:
    calendar = NYSEMarketCalendar()
    with pytest.raises(CalendarDateOutOfRangeError):
        calendar.is_trading_session(local_noon(MIN_SUPPORTED_YEAR - 1, 12, 31))
    with pytest.raises(CalendarDateOutOfRangeError):
        calendar.is_trading_session(local_noon(MAX_SUPPORTED_YEAR + 1, 1, 1))
    with pytest.raises(CalendarDateOutOfRangeError):
        calendar.previous_session(local_noon(MIN_SUPPORTED_YEAR, 1, 1))
    with pytest.raises(CalendarDateOutOfRangeError):
        calendar.next_session(local_noon(MAX_SUPPORTED_YEAR, 12, 31))


def test_repeated_calls_are_deterministic() -> None:
    calendar = NYSEMarketCalendar()
    value = local_noon(2026, 1, 2)
    assert calendar.next_session(value) == calendar.next_session(value)
