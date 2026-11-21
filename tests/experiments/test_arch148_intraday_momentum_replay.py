"""Synthetic-only replay tests for the frozen Architecture 148 policy."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import arch148_intraday as intraday
from trading_bot.experiments import arch148_sparse_backtest as sparse_backtest
from trading_bot.experiments.arch148_churn_policy import OPPOSITE_CONFIRMATION_EXIT
from trading_bot.experiments.arch148_intraday import (
    CONSERVATIVE_COSTS,
    ZERO_COST,
    BacktestCostModel,
)
from trading_bot.experiments.arch148_intraday_momentum_research import (
    OPENING_DRIVE_POLICY_ID,
    OpeningDriveNoTradeReason,
    run_opening_drive_replay,
)

_DAY_ONE = date(2023, 11, 21)
_DAY_TWO = date(2023, 11, 22)
_EARLY_CLOSE = date(2023, 11, 24)
_TEST_AUTHORITY = intraday.HistoricalIntradaySessionAuthority()


def _replay(dataset, *, cost_model=ZERO_COST):
    return run_opening_drive_replay(
        dataset, authority=_TEST_AUTHORITY, cost_model=cost_model
    )


def _entry_index(session_date: date) -> int:
    schedule = _TEST_AUTHORITY.schedule_for(session_date)
    assert schedule is not None
    return intraday.session_slots(session_date, _TEST_AUTHORITY).index(
        schedule.closes_at - timedelta(minutes=35)
    )


def _force_flat_index(session_date: date) -> int:
    schedule = _TEST_AUTHORITY.schedule_for(session_date)
    assert schedule is not None
    return intraday.session_slots(session_date, _TEST_AUTHORITY).index(
        schedule.closes_at - timedelta(minutes=5)
    )


def _dataset(
    days: tuple[date, ...],
    *,
    missing: set[tuple[str, date, int]] | None = None,
    overrides: dict[tuple[str, date, int], tuple[str, str, str, str]] | None = None,
) -> intraday.SparseIntradayDataset:
    missing = missing or set()
    overrides = overrides or {}
    datasets = []
    for symbol in intraday.INTRADAY_SYMBOLS:
        bars = []
        for session_date in days:
            for index, timestamp in enumerate(
                intraday.session_slots(session_date, _TEST_AUTHORITY)
            ):
                if (symbol, session_date, index) in missing:
                    continue
                values = overrides.get(
                    (symbol, session_date, index),
                    ("100", "101", "99", "100"),
                )
                bars.append(
                    Bar(
                        Symbol(symbol),
                        timestamp,
                        Decimal(values[0]),
                        Decimal(values[1]),
                        Decimal(values[2]),
                        Decimal(values[3]),
                        100,
                    )
                )
        datasets.append(intraday.IntradaySymbolDataset(symbol, tuple(bars)))
    start = datetime(days[0].year, days[0].month, days[0].day, tzinfo=UTC)
    end_date = days[-1] + timedelta(days=1)
    end = datetime(end_date.year, end_date.month, end_date.day, tzinfo=UTC)
    return intraday.SparseIntradayDataset(start, end, tuple(datasets))


def _positive_drive_overrides(
    *,
    previous_close: str = "100",
    first_half_close: str = "102",
) -> dict[tuple[str, date, int], tuple[str, str, str, str]]:
    previous_last = len(intraday.session_slots(_DAY_ONE, _TEST_AUTHORITY)) - 1
    return {
        ("QQQ", _DAY_ONE, previous_last): (
            previous_close,
            previous_close,
            previous_close,
            previous_close,
        ),
        ("QQQ", _DAY_TWO, 5): (
            first_half_close,
            first_half_close,
            first_half_close,
            first_half_close,
        ),
    }


def _capture_for(result, session_date: date):
    return next(
        item for item in result.session_captures if item.session_date == session_date
    )


def test_previous_session_close_direction_early_close_and_exact_schedule() -> None:
    overrides = _positive_drive_overrides()
    previous_last = len(intraday.session_slots(_DAY_TWO, _TEST_AUTHORITY)) - 1
    overrides[("QQQ", _DAY_TWO, previous_last)] = (
        "300",
        "301",
        "299",
        "300",
    )
    overrides[("QQQ", _EARLY_CLOSE, 5)] = ("297", "298", "296", "297")
    regular = _TEST_AUTHORITY.schedule_for(_DAY_TWO)
    early = _TEST_AUTHORITY.schedule_for(_EARLY_CLOSE)
    assert regular is not None and early is not None
    regular_entry_index = _entry_index(_DAY_TWO)
    regular_force_index = _force_flat_index(_DAY_TWO)
    overrides[("QQQ", _DAY_TWO, regular_entry_index)] = (
        "200",
        "201",
        "199",
        "200",
    )
    overrides[("QQQ", _DAY_TWO, regular_force_index)] = (
        "202",
        "301",
        "201",
        "300",
    )
    dataset = _dataset((_DAY_ONE, _DAY_TWO, _EARLY_CLOSE), overrides=overrides)

    replay = _replay(dataset)

    first = _capture_for(replay, _DAY_TWO)
    early_capture = _capture_for(replay, _EARLY_CLOSE)
    assert first.previous_session_date == _DAY_ONE
    assert first.opening_drive_return == Decimal("0.02")
    assert first.target_symbol == "TQQQ"
    assert first.policy_entry_eligible
    assert first.entry_at == regular.closes_at - timedelta(minutes=35)
    assert first.force_flat_at == regular.closes_at - timedelta(minutes=5)
    assert first.qqq_late_window_return == Decimal("0.01")
    assert early_capture.previous_session_date == _DAY_TWO
    assert early_capture.opening_drive_return == Decimal("-0.01")
    assert early_capture.target_symbol == "SQQQ"
    assert early_capture.early_close
    assert early_capture.entry_at == early.closes_at - timedelta(minutes=35)
    assert early_capture.force_flat_at == early.closes_at - timedelta(minutes=5)
    assert replay.backtest_result.trade_count == 2
    assert all(
        trade.exit_reason == "FORCED_FLAT" for trade in replay.backtest_result.trades
    )
    assert replay.backtest_result.trades[0].exit_at == first.force_flat_at
    assert replay.backtest_result.trades[1].exit_at == early_capture.force_flat_at


@pytest.mark.parametrize("missing_index", range(6))
def test_each_missing_opening_slot_blocks_the_six_bar_signal(
    missing_index: int,
) -> None:
    dataset = _dataset(
        (_DAY_ONE, _DAY_TWO),
        missing={("QQQ", _DAY_TWO, missing_index)},
        overrides=_positive_drive_overrides(),
    )

    replay = _replay(dataset)

    capture = _capture_for(replay, _DAY_TWO)
    assert (
        capture.no_trade_reason
        is OpeningDriveNoTradeReason.INCOMPLETE_FIRST_HALF_HOUR_QQQ
    )
    assert capture.opening_drive_return is None
    assert capture.target_symbol is None
    assert not capture.policy_entry_eligible
    assert replay.backtest_result.trade_count == 0


def test_zero_drive_has_no_direction_or_trade() -> None:
    overrides = _positive_drive_overrides(first_half_close="100")
    dataset = _dataset((_DAY_ONE, _DAY_TWO), overrides=overrides)

    replay = _replay(dataset)

    capture = _capture_for(replay, _DAY_TWO)
    assert capture.opening_drive_return == Decimal("0")
    assert capture.target_symbol is None
    assert capture.no_trade_reason is OpeningDriveNoTradeReason.ZERO_OPENING_DRIVE
    assert replay.backtest_result.trade_count == 0


def test_opening_return_uses_sparse_decimal_context_not_ambient_precision() -> None:
    overrides = _positive_drive_overrides(previous_close="90", first_half_close="101")
    dataset = _dataset((_DAY_ONE, _DAY_TWO), overrides=overrides)
    with localcontext() as context:
        context.prec = 2
        replay = _replay(dataset)

    capture = _capture_for(replay, _DAY_TWO)
    with localcontext(sparse_backtest.sparse_backtest_decimal_context()):
        expected = Decimal("101") / Decimal("90") - Decimal("1")
    assert capture.opening_drive_return == expected
    assert capture.opening_drive_return.as_tuple().exponent < -2


def test_missing_scheduled_target_bar_does_not_fill_later() -> None:
    entry_index = _entry_index(_DAY_TWO)
    dataset = _dataset(
        (_DAY_ONE, _DAY_TWO),
        missing={("TQQQ", _DAY_TWO, entry_index)},
        overrides=_positive_drive_overrides(),
    )

    replay = _replay(dataset)

    capture = _capture_for(replay, _DAY_TWO)
    assert capture.target_symbol == "TQQQ"
    assert (
        capture.no_trade_reason is OpeningDriveNoTradeReason.MISSING_SCHEDULED_ENTRY_BAR
    )
    assert not capture.policy_entry_eligible
    assert replay.backtest_result.trades == ()


def test_data_safety_at_entry_is_separate_from_policy_eligibility() -> None:
    entry_index = _entry_index(_DAY_TWO)
    dataset = _dataset(
        (_DAY_ONE, _DAY_TWO),
        missing={("QQQ", _DAY_TWO, entry_index - 1)},
        overrides=_positive_drive_overrides(),
    )

    replay = _replay(dataset)

    capture = _capture_for(replay, _DAY_TWO)
    assert capture.policy_entry_eligible
    assert capture.no_trade_reason is OpeningDriveNoTradeReason.QQQ_DATA_SAFETY_AT_ENTRY
    assert capture.entry_data_quality is not None
    assert capture.entry_data_quality is not intraday.MarketQuality.READY
    assert replay.backtest_result.trade_count == 0


def test_scheduled_mode_skips_indicator_stream_and_never_reenters_or_flips(
    monkeypatch,
) -> None:
    entry_index = _entry_index(_DAY_TWO)
    overrides = _positive_drive_overrides()
    overrides[("TQQQ", _DAY_TWO, entry_index)] = ("100", "101", "96", "100")
    dataset = _dataset((_DAY_ONE, _DAY_TWO), overrides=overrides)

    def forbidden_indicator_stream(*args, **kwargs):
        raise AssertionError("scheduled mode must not construct indicators")

    monkeypatch.setattr(
        sparse_backtest, "_CompletedBarSignalStream", forbidden_indicator_stream
    )
    replay = _replay(dataset)

    assert OPENING_DRIVE_POLICY_ID == "OPENING_DRIVE_LATE_CAPTURE_V1"
    assert replay.backtest_result.trade_count == 1
    assert replay.backtest_result.trades[0].symbol == "TQQQ"
    assert (
        replay.backtest_result.trades[0].entry_at
        == replay.backtest_result.trades[0].exit_at
    )
    assert replay.backtest_result.trades[0].exit_reason == "STOP"
    assert replay.backtest_result.reversal_exits == 0


def test_entry_bar_stop_is_immediate_and_later_gap_exits_at_real_open() -> None:
    entry_index = _entry_index(_DAY_TWO)
    overrides = _positive_drive_overrides()
    overrides[("TQQQ", _DAY_TWO, entry_index)] = ("100", "101", "96", "100")
    immediate = _replay(_dataset((_DAY_ONE, _DAY_TWO), overrides=overrides))
    immediate_trade = immediate.backtest_result.trades[0]
    assert immediate_trade.entry_at == immediate_trade.exit_at
    assert immediate_trade.exit_reason == "STOP"
    assert immediate_trade.exit_price == Decimal("97.00")

    overrides[("TQQQ", _DAY_TWO, entry_index)] = ("100", "101", "98", "100")
    overrides[("TQQQ", _DAY_TWO, entry_index + 1)] = (
        "95",
        "96",
        "94",
        "95",
    )
    gap = _replay(_dataset((_DAY_ONE, _DAY_TWO), overrides=overrides))
    gap_trade = gap.backtest_result.trades[0]
    assert gap_trade.exit_reason == "STOP"
    assert gap_trade.exit_at == gap_trade.entry_at + timedelta(minutes=5)
    assert gap_trade.exit_price == Decimal("95")


def test_stop_precedes_a_pending_safety_exit_and_missing_held_marks_are_omitted() -> (
    None
):
    entry_index = _entry_index(_DAY_TWO)
    overrides = _positive_drive_overrides()
    overrides[("TQQQ", _DAY_TWO, entry_index + 3)] = (
        "95",
        "96",
        "94",
        "95",
    )
    missing = {
        ("QQQ", _DAY_TWO, entry_index + 1),
        ("TQQQ", _DAY_TWO, entry_index + 2),
    }
    replay = _replay(
        _dataset((_DAY_ONE, _DAY_TWO), missing=missing, overrides=overrides)
    )

    capture = _capture_for(replay, _DAY_TWO)
    trade = replay.backtest_result.trades[0]
    assert capture.entry_data_quality is intraday.MarketQuality.READY
    assert trade.exit_reason == "STOP"
    assert trade.exit_at == trade.entry_at + timedelta(minutes=15)
    assert replay.backtest_result.stop_hit_count == 1
    assert replay.missing_held_session_dates == (_DAY_TWO,)
    assert all(
        mark.at != trade.entry_at + timedelta(minutes=10)
        for mark in replay.equity_marks
    )


def test_pending_safety_exit_fills_before_new_forced_flat() -> None:
    entry_index = _entry_index(_DAY_TWO)
    force_index = _force_flat_index(_DAY_TWO)
    missing = {("QQQ", _DAY_TWO, entry_index + 1)}
    missing.update(
        ("TQQQ", _DAY_TWO, index) for index in range(entry_index + 2, force_index)
    )
    replay = _replay(
        _dataset(
            (_DAY_ONE, _DAY_TWO), missing=missing, overrides=_positive_drive_overrides()
        )
    )

    trade = replay.backtest_result.trades[0]
    assert trade.exit_at == _capture_for(replay, _DAY_TWO).force_flat_at
    assert trade.exit_reason == "SAFETY"
    assert replay.backtest_result.forced_flat_count == 0
    assert replay.missing_held_session_dates == (_DAY_TWO,)


def test_forced_flat_precedes_new_safety_exit_at_same_open() -> None:
    force_index = _force_flat_index(_DAY_TWO)
    dataset = _dataset(
        (_DAY_ONE, _DAY_TWO),
        missing={("QQQ", _DAY_TWO, force_index - 1)},
        overrides=_positive_drive_overrides(),
    )

    replay = _replay(dataset)

    trade = replay.backtest_result.trades[0]
    assert trade.exit_reason == "FORCED_FLAT"
    assert trade.exit_at == _capture_for(replay, _DAY_TWO).force_flat_at
    assert replay.backtest_result.forced_flat_count == 1


def test_unexecutable_final_forced_flat_keeps_sparse_replay_failure() -> None:
    force_index = _force_flat_index(_DAY_TWO)
    dataset = _dataset(
        (_DAY_ONE, _DAY_TWO),
        missing={("TQQQ", _DAY_TWO, force_index)},
        overrides=_positive_drive_overrides(),
    )

    with pytest.raises(intraday.Arch148IntradayError, match="forced-flat requirement"):
        _replay(dataset)


def test_exact_cost_cases_and_session_capital_compounds_continuously() -> None:
    overrides = _positive_drive_overrides()
    entry_index = _entry_index(_DAY_TWO)
    force_index = _force_flat_index(_DAY_TWO)
    overrides[("TQQQ", _DAY_TWO, entry_index)] = ("100", "101", "99", "100")
    overrides[("TQQQ", _DAY_TWO, force_index)] = ("110", "111", "109", "110")
    previous_last = len(intraday.session_slots(_DAY_TWO, _TEST_AUTHORITY)) - 1
    overrides[("QQQ", _DAY_TWO, previous_last)] = ("300", "301", "299", "300")
    overrides[("QQQ", _EARLY_CLOSE, 5)] = ("297", "298", "296", "297")
    dataset = _dataset((_DAY_ONE, _DAY_TWO, _EARLY_CLOSE), overrides=overrides)

    zero = _replay(dataset)
    conservative = _replay(dataset, cost_model=CONSERVATIVE_COSTS)

    assert (
        zero.backtest_result.cost_adjusted_strategy_return
        == zero.backtest_result.gross_strategy_return
    )
    assert (
        conservative.backtest_result.cost_adjusted_strategy_return
        < conservative.backtest_result.gross_strategy_return
    )
    assert zero.backtest_result.trades[0].quantity == Decimal("100")
    assert zero.backtest_result.trades[1].quantity == Decimal("110")
    assert len(zero.trade_turnovers) == zero.backtest_result.trade_count
    assert len(conservative.trade_turnovers) == conservative.backtest_result.trade_count
    with localcontext(sparse_backtest.sparse_backtest_decimal_context()):
        assert sum(zero.trade_turnovers, Decimal("0")) == zero.backtest_result.turnover
        assert (
            sum(conservative.trade_turnovers, Decimal("0"))
            == conservative.backtest_result.turnover
        )
    assert zero == _replay(dataset)

    with pytest.raises(ValueError, match="two frozen"):
        run_opening_drive_replay(
            dataset,
            authority=_TEST_AUTHORITY,
            cost_model=BacktestCostModel("OTHER", Decimal("1"), Decimal("0")),
        )


def test_scheduled_sparse_seam_requires_control_and_exact_close_relative_entries() -> (
    None
):
    dataset = _dataset((_DAY_ONE, _DAY_TWO), overrides=_positive_drive_overrides())
    schedule = _TEST_AUTHORITY.schedule_for(_DAY_TWO)
    assert schedule is not None
    valid_entry = schedule.closes_at - timedelta(minutes=35)

    with pytest.raises(intraday.Arch148IntradayError, match="regime-exit policies"):
        sparse_backtest.run_sparse_backtest(
            dataset,
            scheduled_entries={valid_entry: "TQQQ"},
            scheduled_authority=_TEST_AUTHORITY,
            churn_policy=OPPOSITE_CONFIRMATION_EXIT,
        )
    with pytest.raises(intraday.Arch148IntradayError, match="close-minus-35"):
        sparse_backtest.run_sparse_backtest(
            dataset,
            scheduled_entries={valid_entry + timedelta(minutes=5): "TQQQ"},
            scheduled_authority=_TEST_AUTHORITY,
        )


def test_replay_uses_only_the_explicit_preconstructed_authority(monkeypatch) -> None:
    dataset = _dataset((_DAY_ONE, _DAY_TWO), overrides=_positive_drive_overrides())

    def forbidden_authority_load(self, *args, **kwargs):
        raise AssertionError("scheduled replay must not load schedule authority")

    monkeypatch.setattr(
        intraday.HistoricalIntradaySessionAuthority,
        "__init__",
        forbidden_authority_load,
    )

    replay = _replay(dataset)

    assert replay.backtest_result.trade_count == 1


def test_post_window_qqq_diagnostic_does_not_change_entry_or_trade() -> None:
    overrides = _positive_drive_overrides()
    entry_index = _entry_index(_DAY_TWO)
    force_index = _force_flat_index(_DAY_TWO)
    first = dict(overrides)
    first[("QQQ", _DAY_TWO, entry_index)] = ("200", "201", "199", "200")
    first[("QQQ", _DAY_TWO, force_index)] = ("202", "203", "201", "202")
    second = dict(first)
    second[("QQQ", _DAY_TWO, force_index)] = ("220", "221", "219", "220")

    first_replay = _replay(_dataset((_DAY_ONE, _DAY_TWO), overrides=first))
    second_replay = _replay(_dataset((_DAY_ONE, _DAY_TWO), overrides=second))

    assert first_replay.backtest_result.trades == second_replay.backtest_result.trades
    assert _capture_for(first_replay, _DAY_TWO).target_symbol == "TQQQ"
    assert (
        _capture_for(first_replay, _DAY_TWO).qqq_late_window_return
        != _capture_for(second_replay, _DAY_TWO).qqq_late_window_return
    )
