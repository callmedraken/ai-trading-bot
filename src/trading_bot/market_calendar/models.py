"""Immutable public market-calendar results."""

from dataclasses import dataclass
from datetime import date, datetime

from trading_bot.domain._validation import normalize_utc
from trading_bot.market_calendar.exceptions import InvalidCalendarInputError


@dataclass(frozen=True, slots=True, order=True)
class TradingSession:
    """An exchange-local calendar date with a regular trading session."""

    session_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.session_date, date) or isinstance(
            self.session_date, datetime
        ):
            raise InvalidCalendarInputError("session_date must be a date")


@dataclass(frozen=True, slots=True)
class TradingSessionRange:
    """Immutable sessions returned for the original half-open request bounds."""

    request_start: datetime
    request_end: datetime
    sessions: tuple[TradingSession, ...]

    def __post_init__(self) -> None:
        try:
            request_start = normalize_utc(self.request_start, "request_start")
            request_end = normalize_utc(self.request_end, "request_end")
        except (TypeError, ValueError) as error:
            raise InvalidCalendarInputError(str(error)) from error
        if request_start > request_end:
            raise InvalidCalendarInputError(
                "request_start must not be later than request_end"
            )
        try:
            sessions = tuple(self.sessions)
        except TypeError as error:
            raise InvalidCalendarInputError("sessions must be iterable") from error
        previous = None
        for session in sessions:
            if not isinstance(session, TradingSession):
                raise InvalidCalendarInputError(
                    "sessions must contain only TradingSession values"
                )
            if previous is not None and session.session_date <= previous:
                raise InvalidCalendarInputError(
                    "sessions must be unique and chronologically ordered"
                )
            previous = session.session_date
        object.__setattr__(self, "request_start", request_start)
        object.__setattr__(self, "request_end", request_end)
        object.__setattr__(self, "sessions", sessions)
