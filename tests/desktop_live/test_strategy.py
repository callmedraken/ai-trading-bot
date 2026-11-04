import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext

import pytest

from trading_bot.desktop_live.configuration import TinyLivePolicy
from trading_bot.desktop_live.strategy import (
    MIN_COMPLETED_BARS,
    P6_CLOSE_SERIES_INPUT_BASIS,
    LiveStrategyDecision,
    P6CloseSource,
    P6CompletedClose,
    decide_live_strategy,
    decide_live_strategy_from_closes,
)
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.filtered_trend_strategies import (
    _ARITHMETIC_CONTEXT as BASE_MA_ARITHMETIC_CONTEXT,
)
from trading_bot.experiments.filtered_trend_strategies import (
    StrategyConfig,
    _rolling_averages,
    signal,
)
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


def _selected_dates() -> tuple[date, ...]:
    return tuple(item.session.session_date for item in _history().bars)


def _close_inputs(
    values: tuple[Decimal, ...],
    sessions: tuple[date, ...] | None = None,
) -> tuple[tuple[P6CompletedClose, ...], tuple[date, ...]]:
    chosen_sessions = sessions if sessions is not None else _selected_dates()
    assert len(values) == len(chosen_sessions) == MIN_COMPLETED_BARS
    closes = tuple(
        P6CompletedClose(
            session_date,
            value,
            (
                P6CloseSource.ROBINHOOD_OFFICIAL_CLOSE
                if index == MIN_COMPLETED_BARS - 1
                else P6CloseSource.HISTORICAL_DAILY
            ),
        )
        for index, (session_date, value) in enumerate(
            zip(chosen_sessions, values, strict=True)
        )
    )
    return closes, chosen_sessions


def _history_for_close_values(values: tuple[Decimal, ...]) -> RobinhoodDailyHistory:
    history = _history()
    bars = tuple(
        DailySnapshotBar(
            item.session,
            Bar(
                Symbol("SPY"),
                item.bar.timestamp,
                value,
                value,
                value,
                value,
                100,
            ),
        )
        for item, value in zip(history.bars, values, strict=True)
    )
    return RobinhoodDailyHistory(history.request, bars, b"synthetic")


def _position(invested: bool):
    return (
        type("Position", (), {"symbol": Symbol("SPY"), "quantity": Decimal("1")})()
        if invested
        else None
    )


def _deterministic_close_cases() -> tuple[tuple[str, tuple[Decimal, ...]], ...]:
    def values(numbers):
        return tuple(Decimal(number) for number in numbers)

    return (
        ("rising", values(range(100, 160))),
        ("falling", values(range(160, 100, -1))),
        ("equal", values([100] * 60)),
        ("latest_upward_crossover", values([100] * 59 + [105])),
        ("latest_downward_crossover", values([100] * 59 + [95])),
        ("above_boundary", values([90] * 25 + [100] * 35)),
        ("below_boundary", values([100] * 25 + [90] * 35)),
    )


@pytest.mark.parametrize(
    ("case_name", "values"),
    _deterministic_close_cases(),
    ids=lambda value: value if isinstance(value, str) else None,
)
@pytest.mark.parametrize("invested", (False, True))
def test_close_series_matches_accepted_base_ma_for_deterministic_cases(
    case_name: str, values: tuple[Decimal, ...], invested: bool
):
    del case_name
    closes, sessions = _close_inputs(values)
    position = _position(invested)
    policy = TinyLivePolicy()
    result = decide_live_strategy_from_closes(
        closes,
        position,
        policy,
        selected_sessions=sessions,
    )
    history = _history_for_close_values(values)
    expected_raw = signal(
        StrategyConfig("BASE_MA", 35, 50, "none"),
        tuple(item.bar for item in history.bars),
        invested=invested,
    )
    accepted_result = decide_live_strategy(history, position, policy)
    assert result.raw_signal == expected_raw == accepted_result.raw_signal
    assert result.fast_average == accepted_result.fast_average
    assert result.slow_average == accepted_result.slow_average
    assert result.completed_bar_count == 60
    assert result.previous_completed_session == sessions[-1].isoformat()
    assert result.decision is (
        LiveStrategyDecision.BUY
        if expected_raw == "BUY" and not invested
        else LiveStrategyDecision.NO_ACTION
    )


def test_close_series_matches_research_rolling_math_for_high_precision_values():
    values = tuple(
        Decimal("1e70") if index < 10 else Decimal(1) + Decimal(index) / Decimal(10**60)
        for index in range(60)
    )
    closes, sessions = _close_inputs(values)
    with localcontext() as ambient:
        ambient.prec = 7
        actual = decide_live_strategy_from_closes(
            closes, None, TinyLivePolicy(), selected_sessions=sessions
        )
    history = _history_for_close_values(values)
    expected = signal(
        StrategyConfig("BASE_MA", 35, 50, "none"),
        tuple(item.bar for item in history.bars),
        invested=False,
    )
    accepted_result = decide_live_strategy(history, None, TinyLivePolicy())
    assert actual.raw_signal == expected == accepted_result.raw_signal
    with localcontext(BASE_MA_ARITHMETIC_CONTEXT):
        expected_fast = _rolling_averages(values, 35)[-1]
        expected_slow = _rolling_averages(values, 50)[-1]
    assert actual.fast_average == format(expected_fast, "f")
    assert actual.slow_average == format(expected_slow, "f")


def test_close_series_digest_binds_the_composition_basis_and_latest_session():
    values = tuple(Decimal(index) for index in range(100, 160))
    closes, sessions = _close_inputs(values)
    result = decide_live_strategy_from_closes(
        closes, None, TinyLivePolicy(), selected_sessions=sessions
    )
    material = {
        "schema": "arch147-p6-live-signal/v2",
        "completed_count": 60,
        "latest_session": sessions[-1].isoformat(),
        "fast": result.fast_average,
        "slow": result.slow_average,
        "raw_signal": result.raw_signal,
        "invested": False,
        "input_basis": P6_CLOSE_SERIES_INPUT_BASIS,
    }
    assert (
        result.values_digest
        == hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()
    )


def test_close_series_requires_exact_count_session_order_and_source_order():
    values = tuple(Decimal(index) for index in range(100, 160))
    closes, sessions = _close_inputs(values)
    with pytest.raises(ValueError, match="exactly 60 completed closes"):
        decide_live_strategy_from_closes(
            closes[:-1], None, TinyLivePolicy(), selected_sessions=sessions
        )
    with pytest.raises(ValueError, match="exactly 60 completed closes"):
        decide_live_strategy_from_closes(
            closes + (closes[-1],),
            None,
            TinyLivePolicy(),
            selected_sessions=sessions,
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        decide_live_strategy_from_closes(
            closes,
            None,
            TinyLivePolicy(),
            selected_sessions=tuple(reversed(sessions)),
        )
    with pytest.raises(ValueError, match="match selected sessions"):
        decide_live_strategy_from_closes(
            tuple(reversed(closes)),
            None,
            TinyLivePolicy(),
            selected_sessions=sessions,
        )
    bad_sources = closes[:-1] + (
        P6CompletedClose(
            sessions[-1],
            values[-1],
            P6CloseSource.HISTORICAL_DAILY,
        ),
    )
    with pytest.raises(ValueError, match="59 historical and one official"):
        decide_live_strategy_from_closes(
            bad_sources, None, TinyLivePolicy(), selected_sessions=sessions
        )


def test_completed_close_model_is_frozen_and_rejects_invalid_material():
    from dataclasses import FrozenInstanceError

    item = P6CompletedClose(
        date(2026, 1, 2),
        Decimal("100"),
        P6CloseSource.HISTORICAL_DAILY,
    )
    with pytest.raises(FrozenInstanceError):
        item.close = Decimal("101")
    with pytest.raises(ValueError, match="positive finite"):
        P6CompletedClose(date(2026, 1, 2), Decimal("0"), P6CloseSource.HISTORICAL_DAILY)
    with pytest.raises(ValueError, match="positive finite"):
        P6CompletedClose(
            date(2026, 1, 2), Decimal("NaN"), P6CloseSource.HISTORICAL_DAILY
        )
    with pytest.raises(TypeError, match="date"):
        P6CompletedClose(
            datetime(2026, 1, 2),
            Decimal("100"),
            P6CloseSource.HISTORICAL_DAILY,
        )
