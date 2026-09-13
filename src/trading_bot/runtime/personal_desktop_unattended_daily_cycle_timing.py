"""Pure Architecture-111 XNYS regular-open timing policy."""

from __future__ import annotations

from datetime import UTC, datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

from trading_bot.market_calendar import (
    CalendarDateOutOfRangeError,
    InvalidCalendarInputError,
    NYSEMarketCalendar,
    TradingSession,
)
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar

PERSONAL_DESKTOP_UNATTENDED_DAILY_CYCLE_TIMING_POLICY_VERSION = (
    "xnys-regular-session-timing-v1"
)

_NEW_YORK = ZoneInfo("America/New_York")
_REGULAR_OPEN = time(9, 30)
_SESSION_ANCHOR = time(12)


class PersonalDesktopUnattendedDailyCycleTimingError(ValueError):
    """A supplied session or timestamp cannot satisfy the frozen timing policy."""


class PersonalDesktopPreOpenDecisionEligibility(StrEnum):
    """Closed pre-open publication eligibility classifications."""

    ELIGIBLE = "ELIGIBLE"
    MISSED_DEADLINE = "MISSED_DEADLINE"


def completed_xnys_session_at(observed_at: datetime) -> TradingSession:
    """Return the exact completed XNYS session at one factual observation."""

    observed = _utc(observed_at)
    try:
        session = BoundMarketCalendar(
            XNYS_CALENDAR_DESCRIPTOR,
            NYSEMarketCalendar(),
        ).previous_session(observed)
    except (CalendarDateOutOfRangeError, InvalidCalendarInputError) as error:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "completed XNYS session cannot be derived"
        ) from error
    _require_modeled_session(session)
    return session


def xnys_regular_open(session: TradingSession) -> datetime:
    """Return the frozen 09:30 America/New_York regular open in UTC."""

    _require_modeled_session(session)
    return datetime.combine(
        session.session_date,
        _REGULAR_OPEN,
        tzinfo=_NEW_YORK,
    ).astimezone(UTC)


def next_xnys_execution_session(session: TradingSession) -> TradingSession:
    """Return the first modeled XNYS session strictly after ``session``."""

    _require_modeled_session(session)
    anchor = datetime.combine(
        session.session_date,
        _SESSION_ANCHOR,
        tzinfo=_NEW_YORK,
    )
    try:
        result = NYSEMarketCalendar().next_session(anchor)
    except (CalendarDateOutOfRangeError, InvalidCalendarInputError) as error:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "next XNYS execution session cannot be derived"
        ) from error
    if type(result) is not TradingSession or result <= session:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "next XNYS execution session is invalid"
        )
    return result


def classify_pre_open_decision_eligibility(
    execution_session: TradingSession,
    observed_at: datetime,
) -> PersonalDesktopPreOpenDecisionEligibility:
    """Classify whether a decision may still be finalized before regular open."""

    deadline = xnys_regular_open(execution_session)
    observed = _utc(observed_at)
    if observed < deadline:
        return PersonalDesktopPreOpenDecisionEligibility.ELIGIBLE
    return PersonalDesktopPreOpenDecisionEligibility.MISSED_DEADLINE


def _require_modeled_session(session: TradingSession) -> None:
    if type(session) is not TradingSession:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "session must be an exact TradingSession"
        )
    anchor = datetime.combine(
        session.session_date,
        _SESSION_ANCHOR,
        tzinfo=_NEW_YORK,
    )
    try:
        modeled = NYSEMarketCalendar().is_trading_session(anchor)
    except (CalendarDateOutOfRangeError, InvalidCalendarInputError) as error:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "session is outside the supported XNYS calendar"
        ) from error
    if modeled is not True:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "session is not a modeled XNYS trading session"
        )


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PersonalDesktopUnattendedDailyCycleTimingError(
            "observed_at must be an exact timezone-aware datetime"
        )
    return value.astimezone(UTC)
