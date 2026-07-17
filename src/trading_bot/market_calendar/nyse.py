"""Deterministic regular-session calendar for the New York Stock Exchange."""

from datetime import date, datetime, timedelta
from types import MappingProxyType
from zoneinfo import ZoneInfo

from trading_bot.domain._validation import normalize_utc
from trading_bot.market_calendar.exceptions import (
    CalendarDateOutOfRangeError,
    InvalidCalendarInputError,
)
from trading_bot.market_calendar.models import TradingSession, TradingSessionRange

MIN_SUPPORTED_YEAR = 1998
MAX_SUPPORTED_YEAR = 2100

_NEW_YORK = ZoneInfo("America/New_York")
_ONE_DAY = timedelta(days=1)


class NYSEMarketCalendar:
    """Calculate regular NYSE sessions without external data or current time."""

    def __init__(self) -> None:
        self._holiday_cache: dict[int, frozenset[date]] = {}

    @property
    def holiday_cache(self) -> MappingProxyType[int, frozenset[date]]:
        """Return a read-only snapshot of already calculated holiday years."""
        return MappingProxyType(dict(self._holiday_cache))

    def is_trading_session(self, value: datetime) -> bool:
        local_date = self._exchange_date(value)
        self._require_supported_date(local_date)
        return self._is_session_date(local_date)

    def next_session(self, value: datetime) -> TradingSession:
        current = self._exchange_date(value)
        self._require_supported_date(current)
        current += _ONE_DAY
        while current.year <= MAX_SUPPORTED_YEAR:
            if self._is_session_date(current):
                return TradingSession(current)
            current += _ONE_DAY
        raise CalendarDateOutOfRangeError(
            f"next session is later than supported year {MAX_SUPPORTED_YEAR}"
        )

    def previous_session(self, value: datetime) -> TradingSession:
        current = self._exchange_date(value)
        self._require_supported_date(current)
        current -= _ONE_DAY
        while current.year >= MIN_SUPPORTED_YEAR:
            if self._is_session_date(current):
                return TradingSession(current)
            current -= _ONE_DAY
        raise CalendarDateOutOfRangeError(
            f"previous session is earlier than supported year {MIN_SUPPORTED_YEAR}"
        )

    def sessions_between(self, start: datetime, end: datetime) -> TradingSessionRange:
        request_start = self._normalize_input(start, "start")
        request_end = self._normalize_input(end, "end")
        if request_start > request_end:
            raise InvalidCalendarInputError("start must not be later than end")
        start_date = request_start.astimezone(_NEW_YORK).date()
        end_date = request_end.astimezone(_NEW_YORK).date()
        self._require_supported_range(start_date, end_date)

        sessions = []
        current = start_date
        while current < end_date:
            if self._is_session_date(current):
                sessions.append(TradingSession(current))
            current += _ONE_DAY
        return TradingSessionRange(request_start, request_end, tuple(sessions))

    def _is_session_date(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self._holidays_for_year(value.year)

    def _holidays_for_year(self, year: int) -> frozenset[date]:
        self._require_supported_year(year)
        cached = self._holiday_cache.get(year)
        if cached is not None:
            return cached
        holidays = frozenset(
            {
                self._observed_new_year(year),
                self._nth_weekday(year, 1, 0, 3),
                self._nth_weekday(year, 2, 0, 3),
                self._easter_sunday(year) - timedelta(days=2),
                self._last_weekday(year, 5, 0),
                self._observed_fixed(date(year, 7, 4)),
                self._nth_weekday(year, 9, 0, 1),
                self._nth_weekday(year, 11, 3, 4),
                self._observed_fixed(date(year, 12, 25)),
                *({self._observed_fixed(date(year, 6, 19))} if year >= 2022 else set()),
            }
        )
        self._holiday_cache[year] = holidays
        return holidays

    @staticmethod
    def _exchange_date(value: datetime) -> date:
        return (
            NYSEMarketCalendar._normalize_input(value, "value")
            .astimezone(_NEW_YORK)
            .date()
        )

    @staticmethod
    def _normalize_input(value: datetime, field_name: str) -> datetime:
        try:
            return normalize_utc(value, field_name)
        except (TypeError, ValueError) as error:
            raise InvalidCalendarInputError(str(error)) from error

    @staticmethod
    def _observed_new_year(year: int) -> date:
        holiday = date(year, 1, 1)
        if holiday.weekday() == 6:
            return holiday + _ONE_DAY
        return holiday

    @staticmethod
    def _observed_fixed(holiday: date) -> date:
        if holiday.weekday() == 5:
            return holiday - _ONE_DAY
        if holiday.weekday() == 6:
            return holiday + _ONE_DAY
        return holiday

    @staticmethod
    def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> date:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (ordinal - 1))

    @staticmethod
    def _last_weekday(year: int, month: int, weekday: int) -> date:
        if month == 12:
            final = date(year + 1, 1, 1) - _ONE_DAY
        else:
            final = date(year, month + 1, 1) - _ONE_DAY
        offset = (final.weekday() - weekday) % 7
        return final - timedelta(days=offset)

    @staticmethod
    def _easter_sunday(year: int) -> date:
        """Return Gregorian Easter using the anonymous Gregorian computus."""
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        ell = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * ell) // 451
        month = (h + ell - 7 * m + 114) // 31
        day = (h + ell - 7 * m + 114) % 31 + 1
        return date(year, month, day)

    @staticmethod
    def _require_supported_year(year: int) -> None:
        if not MIN_SUPPORTED_YEAR <= year <= MAX_SUPPORTED_YEAR:
            raise CalendarDateOutOfRangeError(
                f"year {year} is outside supported range "
                f"{MIN_SUPPORTED_YEAR}-{MAX_SUPPORTED_YEAR}"
            )

    @classmethod
    def _require_supported_date(cls, value: date) -> None:
        cls._require_supported_year(value.year)

    @classmethod
    def _require_supported_range(cls, start: date, end: date) -> None:
        cls._require_supported_date(start)
        if end.year == MAX_SUPPORTED_YEAR + 1 and end == date(end.year, 1, 1):
            return
        cls._require_supported_date(end)
