"""Pure regular-session admission over an explicit authoritative schedule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

_NEW_YORK = ZoneInfo("America/New_York")


class ReviewPaperSessionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    NON_SESSION_DATE = "NON_SESSION_DATE"
    BEFORE_REGULAR_WINDOW = "BEFORE_REGULAR_WINDOW"
    OPENING_BUFFER = "OPENING_BUFFER"
    CLOSING_BUFFER = "CLOSING_BUFFER"
    AFTER_REGULAR_WINDOW = "AFTER_REGULAR_WINDOW"


def _normalize_utc(value: datetime, field_name: str) -> datetime:
    # Match the repository datetime convention without importing private helpers.
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ReviewPaperSessionSchedule:
    session_date: date
    opens_at: datetime
    closes_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.session_date, date) or isinstance(
            self.session_date, datetime
        ):
            raise TypeError("session_date must be a date, not datetime")
        opens_at = _normalize_utc(self.opens_at, "opens_at")
        closes_at = _normalize_utc(self.closes_at, "closes_at")
        if opens_at >= closes_at:
            raise ValueError("opens_at must precede closes_at")
        if opens_at.astimezone(_NEW_YORK).date() != self.session_date:
            raise ValueError("opens_at must map to session_date in America/New_York")
        if closes_at.astimezone(_NEW_YORK).date() != self.session_date:
            raise ValueError("closes_at must map to session_date in America/New_York")
        object.__setattr__(self, "opens_at", opens_at)
        object.__setattr__(self, "closes_at", closes_at)


def _session_status(
    schedule: ReviewPaperSessionSchedule,
    as_of: datetime,
    admission_opens_at: datetime,
    admission_closes_at: datetime,
) -> ReviewPaperSessionStatus:
    if as_of.astimezone(_NEW_YORK).date() != schedule.session_date:
        return ReviewPaperSessionStatus.NON_SESSION_DATE
    if as_of < schedule.opens_at:
        return ReviewPaperSessionStatus.BEFORE_REGULAR_WINDOW
    if as_of < admission_opens_at:
        return ReviewPaperSessionStatus.OPENING_BUFFER
    if as_of < admission_closes_at:
        return ReviewPaperSessionStatus.ADMITTED
    if as_of < schedule.closes_at:
        return ReviewPaperSessionStatus.CLOSING_BUFFER
    return ReviewPaperSessionStatus.AFTER_REGULAR_WINDOW


@dataclass(frozen=True, slots=True)
class ReviewPaperSessionAdmission:
    status: ReviewPaperSessionStatus
    as_of: datetime
    session_date: date
    opens_at: datetime
    closes_at: datetime
    admission_opens_at: datetime
    admission_closes_at: datetime

    def __post_init__(self) -> None:
        if type(self.status) is not ReviewPaperSessionStatus:
            raise TypeError("status must be a ReviewPaperSessionStatus")
        schedule = ReviewPaperSessionSchedule(
            self.session_date, self.opens_at, self.closes_at
        )
        as_of = _normalize_utc(self.as_of, "as_of")
        admission_opens_at = _normalize_utc(
            self.admission_opens_at, "admission_opens_at"
        )
        admission_closes_at = _normalize_utc(
            self.admission_closes_at, "admission_closes_at"
        )
        if not (
            schedule.opens_at
            <= admission_opens_at
            < admission_closes_at
            <= schedule.closes_at
        ):
            raise ValueError(
                "admission interval must be nonempty within regular window"
            )
        if self.status != _session_status(
            schedule, as_of, admission_opens_at, admission_closes_at
        ):
            raise ValueError("status must agree with as_of and session windows")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "opens_at", schedule.opens_at)
        object.__setattr__(self, "closes_at", schedule.closes_at)
        object.__setattr__(self, "admission_opens_at", admission_opens_at)
        object.__setattr__(self, "admission_closes_at", admission_closes_at)


def admit_review_paper_session(
    *,
    schedule: ReviewPaperSessionSchedule,
    as_of: datetime,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
) -> ReviewPaperSessionAdmission:
    """Classify an explicit instant by exchange-local date and half-open windows."""
    if type(schedule) is not ReviewPaperSessionSchedule:
        raise TypeError("schedule must be exactly ReviewPaperSessionSchedule")
    as_of = _normalize_utc(as_of, "as_of")
    if type(opening_buffer) is not timedelta:
        raise TypeError("opening_buffer must be exactly timedelta")
    if type(closing_buffer) is not timedelta:
        raise TypeError("closing_buffer must be exactly timedelta")
    if opening_buffer < timedelta(0):
        raise ValueError("opening_buffer must be nonnegative")
    if closing_buffer < timedelta(0):
        raise ValueError("closing_buffer must be nonnegative")
    duration = schedule.closes_at - schedule.opens_at
    # Reject consuming buffers before arithmetic that could overflow datetime.
    if opening_buffer >= duration or closing_buffer >= duration - opening_buffer:
        raise ValueError("buffers must leave a nonempty admission interval")
    admission_opens_at = schedule.opens_at + opening_buffer
    admission_closes_at = schedule.closes_at - closing_buffer
    return ReviewPaperSessionAdmission(
        status=_session_status(
            schedule, as_of, admission_opens_at, admission_closes_at
        ),
        as_of=as_of,
        session_date=schedule.session_date,
        opens_at=schedule.opens_at,
        closes_at=schedule.closes_at,
        admission_opens_at=admission_opens_at,
        admission_closes_at=admission_closes_at,
    )
