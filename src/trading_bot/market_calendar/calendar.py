"""Source-independent market-calendar contract."""

from datetime import datetime
from typing import Protocol

from trading_bot.market_calendar.models import TradingSession, TradingSessionRange


class MarketCalendar(Protocol):
    """Structural interface for deterministic trading-session calendars."""

    def is_trading_session(self, value: datetime) -> bool: ...

    def next_session(self, value: datetime) -> TradingSession: ...

    def previous_session(self, value: datetime) -> TradingSession: ...

    def sessions_between(
        self, start: datetime, end: datetime
    ) -> TradingSessionRange: ...
