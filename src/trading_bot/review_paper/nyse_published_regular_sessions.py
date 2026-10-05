"""Architecture 131-S frozen NYSE-published core-equity regular sessions.

This manifest knows only published 2026-2028 sessions, not emergency closures.
Refreshing it requires an explicit reviewed source change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from trading_bot.review_paper.session_admission import ReviewPaperSessionSchedule

_NEW_YORK = ZoneInfo("America/New_York")
_FULL_MARKET_CLOSURES = frozenset(
    (
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
        date(2027, 1, 1),
        date(2027, 1, 18),
        date(2027, 2, 15),
        date(2027, 3, 26),
        date(2027, 5, 31),
        date(2027, 6, 18),
        date(2027, 7, 5),
        date(2027, 9, 6),
        date(2027, 11, 25),
        date(2027, 12, 24),
        date(2028, 1, 17),
        date(2028, 2, 21),
        date(2028, 4, 14),
        date(2028, 5, 29),
        date(2028, 6, 19),
        date(2028, 7, 4),
        date(2028, 9, 4),
        date(2028, 11, 23),
        date(2028, 12, 25),
    )
)
_EARLY_CLOSES = frozenset(
    (
        date(2026, 11, 27),
        date(2026, 12, 24),
        date(2027, 11, 26),
        date(2028, 7, 3),
        date(2028, 11, 24),
    )
)


class UnsupportedNYSEPublishedSessionYearError(ValueError):
    """The frozen published manifest has no authority for the requested year."""


@dataclass(frozen=True, slots=True)
class NYSEPublishedRegularSessionAuthority:
    """Pure published-session lookup with immutable, non-configurable identity."""

    source_name: str = field(default="NYSE", init=False)
    source_scope: str = field(default="NYSE core equity regular session", init=False)
    manifest_version: str = field(
        default="nyse-published-regular-sessions-2026-2028/v1", init=False
    )
    supported_years: tuple[int, ...] = field(default=(2026, 2027, 2028), init=False)
    source_as_of: date = field(default=date(2026, 10, 4), init=False)

    def schedule_for(self, session_date: date) -> ReviewPaperSessionSchedule | None:
        """Return the published regular session or an explicit non-session date."""
        if type(session_date) is not date:
            raise TypeError("session_date must be exactly date, not datetime")
        if session_date.year not in self.supported_years:
            raise UnsupportedNYSEPublishedSessionYearError(
                f"unsupported NYSE published session year: {session_date.year}"
            )
        if session_date.weekday() >= 5 or session_date in _FULL_MARKET_CLOSURES:
            return None
        close_hour = 13 if session_date in _EARLY_CLOSES else 16
        return ReviewPaperSessionSchedule(
            session_date=session_date,
            opens_at=datetime.combine(session_date, time(9, 30), _NEW_YORK),
            closes_at=datetime.combine(session_date, time(close_hour), _NEW_YORK),
        )
