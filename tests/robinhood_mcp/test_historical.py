"""134-B3 strict historical schemas and exact acquisition semantics."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Context, localcontext

import pytest

from trading_bot.domain import Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import XNYS_CALENDAR_DESCRIPTOR, BoundMarketCalendar
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter
from trading_bot.robinhood_mcp.historical import (
    RobinhoodDailyHistoryRequest,
    parse_equity_historicals_response,
)
from trading_bot.robinhood_mcp.models import RobinhoodMcpSchemaError


@pytest.fixture
def history_request():
    return make_request()


def make_request(at=datetime(2026, 10, 12, 13, 0, tzinfo=UTC), window=3):
    return RobinhoodDailyHistoryRequest(
        Symbol("SPY"),
        at,
        window,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
    )


def payload_for(history_request):
    authority = NYSEPublishedRegularSessionAuthority()
    return {
        "data": {
            "results": [
                {
                    "symbol": "SPY",
                    "interval": "day",
                    "bounds": "regular",
                    "bars": [
                        {
                            "begins_at": authority.schedule_for(session.session_date)
                            .opens_at.astimezone(UTC)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "open_price": value,
                            "high_price": value,
                            "low_price": value,
                            "close_price": value,
                            "volume": 100,
                            "session": "reg",
                            "interpolated": False,
                        }
                        for session, value in zip(
                            history_request.sessions(),
                            ["10", "10", "9", "12"],
                            strict=True,
                        )
                    ],
                }
            ]
        },
        "guide": "Daily regular trade bars, not official settled closes.",
    }


def test_exact_calendar_selected_request_and_raw_arguments(history_request):
    assert tuple(item.session_date for item in history_request.sessions()) == (
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
        date(2026, 10, 9),
    )
    assert history_request.arguments() == {
        "symbols": ["SPY"],
        "start_time": "2026-10-06T13:30:00Z",
        "end_time": "2026-10-09T20:00:00Z",
        "interval": "day",
        "bounds": "regular",
        "adjustment_type": "none",
    }
    parsed = parse_equity_historicals_response(
        payload_for(history_request), history_request
    )
    assert tuple(item.session for item in parsed.bars) == history_request.sessions()
    with localcontext(Context(prec=2)):
        assert (
            parse_equity_historicals_response(
                payload_for(history_request), history_request
            )
            == parsed
        )


def test_calendar_dst_holiday_and_early_close():
    dst = make_request(datetime(2026, 3, 10, 13, tzinfo=UTC))
    payload = payload_for(dst)
    stamps = [item["begins_at"] for item in payload["data"]["results"][0]["bars"]]
    assert stamps[-2:] == ["2026-03-06T14:30:00Z", "2026-03-09T13:30:00Z"]
    parse_equity_historicals_response(payload, dst)
    early = make_request(datetime(2026, 11, 30, 13, tzinfo=UTC))
    assert date(2026, 11, 26) not in tuple(
        item.session_date for item in early.sessions()
    )
    assert early.arguments()["end_time"] == "2026-11-27T18:00:00Z"
    parse_equity_historicals_response(payload_for(early), early)


@pytest.mark.parametrize(
    "path,value",
    [
        (("extra",), True),
        (("guide",), None),
        (("data", "extra"), True),
        (("data", "not_found"), ["SPY"]),
        (("data", "not_found"), None),
        (("data", "results"), None),
        (("data", "results"), []),
        (("data", "results", 0, "symbol"), "QQQ"),
        (("data", "results", 0, "interval"), "week"),
        (("data", "results", 0, "bounds"), "extended"),
        (("data", "results", 0, "adjustment_type"), "split"),
        (("data", "results", 0, "bars"), None),
        *[
            (("data", "results", 0, "bars", 0, key), value)
            for key, value in [
                ("interpolated", True),
                ("interpolated", 0),
                ("interpolated", None),
                ("session", "pre"),
                ("session", ""),
                ("session", None),
                ("begins_at", "2026-10-06T00:00:00Z"),
                ("begins_at", "2026-10-05T13:30:00Z"),
                ("begins_at", "2026-10-06T13:31:00Z"),
                ("begins_at", "2026-10-06"),
                ("begins_at", "2026-13-06T13:30:00Z"),
                ("volume", 0),
                ("volume", -1),
                ("volume", True),
                ("volume", 1.0),
                ("open_price", 10),
                ("open_price", "NaN"),
                ("open_price", "1e2"),
                ("open_price", "-1"),
                ("open_price", "0"),
                ("open_price", "9" * 129),
                ("low_price", "11"),
                ("high_price", "9"),
                ("close_price", "11"),
                ("gap_filled", False),
            ]
        ],
    ],
)
def test_malformed_incompatible_or_ambiguous_history_fails(
    history_request, path, value
):
    payload = payload_for(history_request)
    node = payload
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises((RobinhoodMcpSchemaError, ValueError)):
        parse_equity_historicals_response(payload, history_request)


@pytest.mark.parametrize(
    "key", ["begins_at", "interpolated", "session", "volume", "close_price"]
)
def test_missing_bar_fields_fail(history_request, key):
    payload = payload_for(history_request)
    del payload["data"]["results"][0]["bars"][0][key]
    with pytest.raises(RobinhoodMcpSchemaError):
        parse_equity_historicals_response(payload, history_request)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "missing", "reversed", "extra", "gap", "future"]
)
def test_session_coverage_is_exact_and_consecutive(history_request, mutation):
    payload = payload_for(history_request)
    bars = payload["data"]["results"][0]["bars"]
    if mutation == "duplicate":
        bars[1] = deepcopy(bars[0])
    elif mutation == "missing":
        bars.pop(1)
    elif mutation == "reversed":
        bars.reverse()
    elif mutation == "extra":
        bars.append(deepcopy(bars[-1]))
    elif mutation == "gap":
        bars[1]["begins_at"] = "2026-10-05T13:30:00Z"
    else:
        bars[-1]["begins_at"] = "2026-10-12T13:30:00Z"
    with pytest.raises(RobinhoodMcpSchemaError):
        parse_equity_historicals_response(payload, history_request)


def test_insufficient_long_window_is_not_padded_or_retried(history_request):
    payload = payload_for(history_request)
    bigger = replace(history_request, long_window=4)
    with pytest.raises(RobinhoodMcpSchemaError, match="every required"):
        parse_equity_historicals_response(payload, bigger)


@pytest.mark.parametrize(
    "values",
    [
        {"symbol": "SPY"},
        {"long_window": True},
        {"long_window": 0},
        {"long_window": 4097},
        {"requested_at": datetime(2026, 10, 12)},
        {"calendar": object()},
        {"requested_at": datetime(2025, 10, 12, 13, tzinfo=UTC)},
    ],
)
def test_request_validation_precedes_provider(history_request, values):
    with pytest.raises((TypeError, ValueError)):
        replace(history_request, **values)


def test_adapter_only_uses_historical_tool_and_exact_arguments(history_request):
    class Transport:
        def __init__(self):
            self.calls = []

        def get_equity_historicals(self, arguments):
            self.calls.append(arguments)
            return payload_for(history_request)

        def __getattr__(self, name):
            raise AssertionError("unexpected capability: " + name)

    transport = Transport()
    adapter = RobinhoodReviewReadAdapter(transport)
    assert adapter.equity_daily_history(history_request).request == history_request
    assert transport.calls == [history_request.arguments()]
    with pytest.raises(TypeError):
        adapter.equity_daily_history({"interval": "minute"})
    assert transport.calls == [history_request.arguments()]
