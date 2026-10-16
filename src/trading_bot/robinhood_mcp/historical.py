"""Strict one-symbol, raw daily Robinhood history at the XNYS boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import NYSEMarketCalendar, TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotBar,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.models import RobinhoodMcpSchemaError
from trading_bot.strategies.history_seed import MAX_STRATEGY_HISTORY_SEED_BARS

_MAX_BYTES = 4 * 1024 * 1024
_PRICE = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


@dataclass(frozen=True, slots=True)
class RobinhoodDailyHistoryRequest:
    """Explicit bounded acquisition; calendar selection precedes provider access."""

    symbol: Symbol
    requested_at: datetime
    long_window: int
    calendar: BoundMarketCalendar

    def __post_init__(self) -> None:
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be exact Symbol")
        if (
            type(self.requested_at) is not datetime
            or self.requested_at.tzinfo is None
            or self.requested_at.utcoffset() is None
        ):
            raise ValueError("requested_at must be explicit aware datetime")
        object.__setattr__(self, "requested_at", self.requested_at.astimezone(UTC))
        if (
            type(self.long_window) is not int
            or not 1 <= self.long_window <= MAX_STRATEGY_HISTORY_SEED_BARS
        ):
            raise ValueError("long_window is outside the supported history bound")
        if (
            type(self.calendar) is not BoundMarketCalendar
            or type(self.calendar.calendar) is not NYSEMarketCalendar
            or self.calendar.descriptor != XNYS_CALENDAR_DESCRIPTOR
        ):
            raise ValueError("calendar must be exact bound XNYS authority")
        # Validate published coverage, completion and calendar agreement now.
        self.sessions()

    def sessions(self) -> tuple[TradingSession, ...]:
        """Freeze exactly long_window predecessors and the prior completed bar."""
        authority = NYSEPublishedRegularSessionAuthority()
        current = self.calendar.previous_session(self.requested_at)
        result = [current]
        for _ in range(self.long_window):
            schedule = authority.schedule_for(result[-1].session_date)
            if schedule is None:
                raise ValueError("XNYS and published session authority disagree")
            result.append(self.calendar.previous_session(schedule.opens_at))
        result.reverse()
        for session in result:
            schedule = authority.schedule_for(session.session_date)
            if schedule is None or schedule.closes_at >= self.requested_at:
                raise ValueError("history session is not published and completed")
        return tuple(result)

    def arguments(self) -> dict[str, object]:
        """Return only the documented historical tool arguments, without defaults."""
        sessions = self.sessions()
        authority = NYSEPublishedRegularSessionAuthority()
        first = authority.schedule_for(sessions[0].session_date)
        last = authority.schedule_for(sessions[-1].session_date)
        assert first is not None and last is not None
        return {
            "symbols": [str(self.symbol)],
            "start_time": first.opens_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": last.closes_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": "day",
            "bounds": "regular",
            "adjustment_type": "none",
        }


@dataclass(frozen=True, slots=True)
class RobinhoodDailyHistory:
    """Parsed values plus exact canonical structured-response audit bytes."""

    request: RobinhoodDailyHistoryRequest
    bars: tuple[DailySnapshotBar, ...]
    response_bytes: bytes


def parse_equity_historicals_response(
    payload: Mapping[str, object], request: RobinhoodDailyHistoryRequest
) -> RobinhoodDailyHistory:
    """Reject unknown fields, partial series, gap fills and ambiguous labels."""
    if type(request) is not RobinhoodDailyHistoryRequest:
        raise TypeError("request must be exact RobinhoodDailyHistoryRequest")
    root = _object(payload, {"data", "guide"}, set())
    if type(root["guide"]) is not str or not root["guide"]:
        raise RobinhoodMcpSchemaError("guide must be nonblank text")
    data = _object(root["data"], {"results"}, {"not_found"})
    if "not_found" in data and data["not_found"] != []:
        raise RobinhoodMcpSchemaError("not_found must be absent or an empty array")
    results = data["results"]
    if type(results) is not list or len(results) != 1:
        raise RobinhoodMcpSchemaError("exactly one historical result is required")
    result = _object(
        results[0], {"symbol", "interval", "bounds", "bars"}, {"adjustment_type"}
    )
    if (
        result["symbol"] != str(request.symbol)
        or result["interval"] != "day"
        or result["bounds"] != "regular"
        or result.get("adjustment_type", "none") != "none"
    ):
        raise RobinhoodMcpSchemaError(
            "history symbol/daily/regular/raw semantics disagree"
        )
    sessions = request.sessions()
    raw_bars = result["bars"]
    if type(raw_bars) is not list or len(raw_bars) != len(sessions):
        raise RobinhoodMcpSchemaError(
            "history must contain every required consecutive XNYS session"
        )
    bars = []
    authority = NYSEPublishedRegularSessionAuthority()
    for raw, session in zip(raw_bars, sessions, strict=True):
        item = _object(
            raw,
            {
                "begins_at",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "session",
                "interpolated",
            },
            set(),
        )
        if item["session"] != "reg" or item["interpolated"] is not False:
            raise RobinhoodMcpSchemaError(
                "history must be explicit regular, non-interpolated evidence"
            )
        text = item["begins_at"]
        if type(text) is not str or _TIMESTAMP.fullmatch(text) is None:
            raise RobinhoodMcpSchemaError("begins_at must be exact RFC3339 UTC seconds")
        try:
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise RobinhoodMcpSchemaError("invalid history timestamp") from error
        schedule = authority.schedule_for(session.session_date)
        # Daily left edges must identify the exact regular-session opening.
        # Do not guess how UTC-midnight/date-only/unknown labels map to XNYS.
        if schedule is None or timestamp != schedule.opens_at:
            raise RobinhoodMcpSchemaError(
                "history timestamp is not the expected XNYS regular-session left edge"
            )
        if (
            timestamp.astimezone(ZoneInfo("America/New_York")).date()
            != session.session_date
        ):
            raise RobinhoodMcpSchemaError("history timestamp/session disagree")
        volume = item["volume"]
        if type(volume) is not int or volume <= 0:
            raise RobinhoodMcpSchemaError(
                "history volume must be positive integer trade evidence"
            )
        try:
            bar = Bar(
                request.symbol,
                timestamp,
                *(
                    _price(item[key])
                    for key in ("open_price", "high_price", "low_price", "close_price")
                ),
                volume,
            )
        except (TypeError, ValueError) as error:
            raise RobinhoodMcpSchemaError("history OHLCV does not reconcile") from error
        bars.append(DailySnapshotBar(session, bar))
    try:
        response_bytes = (
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise RobinhoodMcpSchemaError(
            "history structured response cannot be retained"
        ) from error
    if len(response_bytes) > _MAX_BYTES:
        raise RobinhoodMcpSchemaError("history structured response exceeds byte bound")
    return RobinhoodDailyHistory(request, tuple(bars), response_bytes)


def _object(
    value: object, required: set[str], optional: set[str]
) -> Mapping[str, object]:
    if (
        not isinstance(value, Mapping)
        or not required <= set(value) <= required | optional
    ):
        raise RobinhoodMcpSchemaError("history object has missing or unknown fields")
    return value


def _price(value: object) -> Decimal:
    if type(value) is not str or len(value) > 128 or _PRICE.fullmatch(value) is None:
        raise RobinhoodMcpSchemaError(
            "history price must be bounded positive decimal text"
        )
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed <= 0:
        raise RobinhoodMcpSchemaError("history price must be positive and finite")
    return parsed
