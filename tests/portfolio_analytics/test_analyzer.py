from dataclasses import replace
from decimal import Decimal

import pytest
from tests.portfolio_analytics.helpers import QQQ, SPY, make_fill, make_result

from trading_bot.domain import OrderSide, Symbol
from trading_bot.portfolio_analytics import (
    InconsistentPortfolioBacktestAuditError,
    PortfolioAnalyticsInputError,
    PortfolioPerformanceAnalyzer,
)


def test_requires_multi_symbol_result() -> None:
    with pytest.raises(PortfolioAnalyticsInputError):
        PortfolioPerformanceAnalyzer().analyze(object())  # type: ignore[arg-type]


def test_no_trade_report_contains_ordered_zero_symbol_summaries() -> None:
    result = make_result()
    report = PortfolioPerformanceAnalyzer().analyze(result)
    assert report.absolute_profit_loss == Decimal("0")
    assert report.total_return == Decimal("0")
    assert report.realization_count == 0
    assert report.profit_factor is None
    assert report.executed_notional == report.turnover == Decimal("0")
    assert report.time_in_market_percentage == Decimal("0")
    assert tuple(item.symbol for item in report.symbol_summaries) == (SPY, QQQ)
    assert all(item.total_executed_notional == 0 for item in report.symbol_summaries)


def test_independent_average_cost_partial_exits_and_commissions() -> None:
    fills = (
        make_fill(SPY, OrderSide.BUY, "10", "10", 1, 1, "2"),
        make_fill(QQQ, OrderSide.BUY, "2", "30", 1, 2, "1"),
        make_fill(SPY, OrderSide.BUY, "10", "20", 2, 3, "2"),
        make_fill(QQQ, OrderSide.SELL, "2", "25", 3, 4, "1"),
        make_fill(SPY, OrderSide.SELL, "5", "25", 3, 5, "1"),
    )
    result = make_result(fills)
    report = PortfolioPerformanceAnalyzer().analyze(result)
    qqq, spy = report.trade_realizations
    assert qqq.symbol == QQQ and qqq.net_profit_loss == Decimal("-12")
    assert spy.symbol == SPY and spy.average_entry_cost == Decimal("15.2")
    assert spy.net_profit_loss == Decimal("48")
    assert [item.exit_fill_id for item in report.trade_realizations] == [
        fills[3].fill_id,
        fills[4].fill_id,
    ]
    assert report.winning_realization_count == 1
    assert report.losing_realization_count == 1
    assert report.gross_profit == Decimal("48")
    assert report.gross_loss == Decimal("-12")
    assert report.profit_factor == Decimal("4")
    assert report.executed_notional == Decimal("535")
    spy_summary, qqq_summary = report.symbol_summaries
    assert spy_summary.final_quantity == Decimal("15")
    assert spy_summary.final_average_cost == Decimal("15.2")
    assert spy_summary.final_unrealized_profit_loss == Decimal("1272")
    assert qqq_summary.final_quantity == Decimal("0")


def test_full_exit_resets_entry_time_before_reentry() -> None:
    fills = (
        make_fill(SPY, OrderSide.BUY, "1", "10", 1, 1),
        make_fill(SPY, OrderSide.SELL, "1", "11", 2, 2),
        make_fill(SPY, OrderSide.BUY, "1", "12", 3, 3),
        make_fill(SPY, OrderSide.SELL, "1", "13", 4, 4),
    )
    report = PortfolioPerformanceAnalyzer().analyze(make_result(fills))
    assert report.trade_realizations[0].entry_started_at == fills[0].filled_at
    assert report.trade_realizations[1].entry_started_at == fills[2].filled_at


def test_breakeven_is_in_win_rate_denominator() -> None:
    fills = (
        make_fill(SPY, OrderSide.BUY, "2", "10", 1, 1),
        make_fill(SPY, OrderSide.SELL, "1", "11", 2, 2),
        make_fill(SPY, OrderSide.SELL, "1", "10", 3, 3),
    )
    report = PortfolioPerformanceAnalyzer().analyze(make_result(fills))
    assert report.winning_realization_count == 1
    assert report.breakeven_realization_count == 1
    assert report.win_rate == Decimal("0.5")


def test_turnover_exposure_and_final_unrealized_profit_loss() -> None:
    fills = (make_fill(SPY, OrderSide.BUY, "10", "10", 1, 1),)
    result = make_result(fills, closes=(("10", "10"),) * 4 + (("12", "10"),))
    report = PortfolioPerformanceAnalyzer().analyze(result)
    average_equity = sum(
        (snapshot.equity for snapshot in result.account_snapshots), Decimal("0")
    ) / Decimal("5")
    assert report.turnover == Decimal("100") / average_equity
    assert report.time_in_market_percentage == Decimal("0.8")
    assert report.symbol_summaries[0].final_market_value == Decimal("120")
    assert report.symbol_summaries[0].final_unrealized_profit_loss == Decimal("20")
    assert report.absolute_profit_loss == Decimal("20")


def test_separate_dollar_and_percentage_drawdowns() -> None:
    result = make_result()
    equities = (
        Decimal("100"),
        Decimal("60"),
        Decimal("200"),
        Decimal("150"),
        Decimal("210"),
    )
    snapshots = tuple(
        replace(
            snapshot,
            cash=equity,
            equity=equity,
            buying_power=equity,
        )
        for snapshot, equity in zip(result.account_snapshots, equities, strict=True)
    )
    object.__setattr__(result, "account_snapshots", snapshots)
    object.__setattr__(
        result,
        "steps",
        tuple(
            replace(step, account_snapshot=snapshot)
            for step, snapshot in zip(result.steps, snapshots, strict=True)
        ),
    )
    object.__setattr__(result, "final_equity", equities[-1])
    object.__setattr__(result.config, "starting_cash", Decimal("210"))
    report = PortfolioPerformanceAnalyzer().analyze(result)
    assert report.drawdowns.maximum_amount.amount == Decimal("50")
    assert report.drawdowns.maximum_percentage.percentage == Decimal("0.4")


def test_duplicate_fill_unknown_symbol_and_oversell_fail() -> None:
    buy = make_fill(SPY, OrderSide.BUY, "1", "10", 1, 1)
    result = make_result((buy,))
    object.__setattr__(result, "fills", (buy, buy))
    object.__setattr__(result.steps[1], "opening_fills", (buy, buy))
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="duplicate fill"):
        PortfolioPerformanceAnalyzer().analyze(result)

    result = make_result((buy,))
    object.__setattr__(buy, "symbol", Symbol("DIA"))
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="universe"):
        PortfolioPerformanceAnalyzer().analyze(result)

    sell = make_fill(SPY, OrderSide.BUY, "1", "10", 1, 2)
    oversold = make_result((sell,))
    object.__setattr__(sell, "side", OrderSide.SELL)
    object.__setattr__(oversold.final_orders[0].request, "side", OrderSide.SELL)
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="exceeds"):
        PortfolioPerformanceAnalyzer().analyze(oversold)


def test_fill_chronology_and_step_frame_timestamp_are_audited() -> None:
    first = make_fill(SPY, OrderSide.BUY, "1", "10", 1, 1)
    second = make_fill(QQQ, OrderSide.BUY, "1", "10", 2, 2)
    result = make_result((first, second))
    object.__setattr__(first, "filled_at", second.filled_at)
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="opening fill"):
        PortfolioPerformanceAnalyzer().analyze(result)


def test_order_fill_and_final_audit_mismatches_fail() -> None:
    fill = make_fill(SPY, OrderSide.BUY, "1", "10", 1, 1)
    result = make_result((fill,))
    object.__setattr__(fill, "order_id", fill.fill_id)
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="unknown"):
        PortfolioPerformanceAnalyzer().analyze(result)

    result = make_result((make_fill(SPY, OrderSide.BUY, "1", "10", 1, 2),))
    object.__setattr__(
        result.account_snapshots[-1], "unrealized_profit_loss", Decimal("1")
    )
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="unrealized"):
        PortfolioPerformanceAnalyzer().analyze(result)


def test_final_position_and_realized_profit_loss_mismatches_fail() -> None:
    fill = make_fill(SPY, OrderSide.BUY, "1", "10", 1, 3)
    result = make_result((fill,))
    object.__setattr__(result.final_positions[SPY], "average_cost", Decimal("11"))
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="position"):
        PortfolioPerformanceAnalyzer().analyze(result)

    fills = (
        make_fill(SPY, OrderSide.BUY, "1", "10", 1, 4),
        make_fill(SPY, OrderSide.SELL, "1", "11", 2, 5),
    )
    result = make_result(fills)
    object.__setattr__(
        result.account_snapshots[-1], "realized_profit_loss", Decimal("999")
    )
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="realized"):
        PortfolioPerformanceAnalyzer().analyze(result)


def test_alignment_validation_and_repeated_analysis_preserve_input() -> None:
    result = make_result((make_fill(SPY, OrderSide.BUY, "1", "10", 1, 1),))
    analyzer = PortfolioPerformanceAnalyzer()
    before = (result.frames, result.steps, result.fills, result.final_positions)
    assert analyzer.analyze(result) == analyzer.analyze(result)
    assert (result.frames, result.steps, result.fills, result.final_positions) == before

    bad = make_result()
    object.__setattr__(bad.steps[0], "step_index", 2)
    with pytest.raises(InconsistentPortfolioBacktestAuditError, match="step indexes"):
        analyzer.analyze(bad)
