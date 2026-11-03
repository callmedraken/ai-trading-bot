import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.strategy import (
    MIN_COMPLETED_BARS,
    LiveStrategyDecision,
    decide_live_strategy,
)
from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    DailySnapshotBar,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.historical import (
    RobinhoodDailyHistory,
    RobinhoodDailyHistoryRequest,
)


def _history(close: Decimal = Decimal("100")) -> RobinhoodDailyHistory:
    request = RobinhoodDailyHistoryRequest(
        Symbol("SPY"),
        datetime(2026, 11, 2, 14, 0, tzinfo=UTC),
        MIN_COMPLETED_BARS - 1,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
    )
    authority = NYSEPublishedRegularSessionAuthority()
    bars = []
    for index, session in enumerate(request.sessions()):
        schedule = authority.schedule_for(session.session_date)
        assert schedule is not None
        value = close + Decimal(index)
        bars.append(
            DailySnapshotBar(
                session,
                Bar(
                    Symbol("SPY"),
                    schedule.opens_at,
                    value,
                    value,
                    value,
                    value,
                    100,
                ),
            )
        )
    return RobinhoodDailyHistory(request, tuple(bars), b"synthetic")


def test_strategy_uses_completed_raw_daily_bars_and_frozen_base_ma():
    result = decide_live_strategy(_history(), None, TinyLivePolicy())
    assert result.completed_bar_count == MIN_COMPLETED_BARS
    assert result.raw_signal == "BUY"
    assert result.decision is LiveStrategyDecision.BUY
    assert result.previous_completed_session == "2026-10-30"


def test_strategy_never_rebuys_an_invested_position():
    position = type(
        "Position", (), {"symbol": Symbol("SPY"), "quantity": Decimal("1")}
    )()
    result = decide_live_strategy(_history(), position, TinyLivePolicy())
    assert result.decision is LiveStrategyDecision.NO_ACTION


def test_strategy_requires_the_minimum_completed_history():
    history = _history()
    with pytest.raises(ValueError, match="at least 60"):
        decide_live_strategy(
            RobinhoodDailyHistory(history.request, history.bars[:-2], b"synthetic"),
            None,
            TinyLivePolicy(),
        )


@pytest.mark.parametrize("invested", (False, True))
def test_exact_60_strategy_preserves_ma35_50_math_and_digest_material(invested):
    history = _history()
    position = (
        type("Position", (), {"symbol": Symbol("SPY"), "quantity": Decimal("1")})()
        if invested
        else None
    )
    result = decide_live_strategy(history, position, TinyLivePolicy())
    # Exactly 60 closes are 100..159: the last 35 average 142, last 50 134.5.
    assert len(history.bars) == result.completed_bar_count == 60
    assert result.fast_average == "142"
    assert result.slow_average == "134.5"
    material = {
        "schema": "arch147-p6-live-signal/v1",
        "bars": 60,
        "previous_session": "2026-10-30",
        "fast": "142",
        "slow": "134.5",
        "raw_signal": result.raw_signal,
        "invested": invested,
    }
    assert (
        result.values_digest
        == hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()
    )
