"""Expected failures raised by deterministic market calendars."""


class MarketCalendarError(Exception):
    """Base class for market-calendar failures."""


class InvalidCalendarInputError(MarketCalendarError):
    """Raised when a calendar input or result is invalid."""


class CalendarDateOutOfRangeError(MarketCalendarError):
    """Raised when a date lies outside the supported calendar range."""
