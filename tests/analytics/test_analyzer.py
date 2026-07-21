from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from trading_bot.analytics import (
    InconsistentBacktestAuditError,
    PerformanceAnalyzer,
)
from trading_bot.backtesting import BacktestConfig, BacktestResult, BacktestStep
from trading_bot.domain import Bar, OrderFill, OrderSide, Symbol
from trading_bot.ledger import AccountSnapshot, PaperLedger
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import HistoricalDataRequest
from trading_bot.risk import RiskLimits

SYMBOL = Symbol("MATEST")
START = datetime(2026, 1, 5, 20, tzinfo=UTC)


def fill(
    side: OrderSide, quantity: str, price: str, index: int, commission: str = "0"
) -> OrderFill:
    return OrderFill(
        uuid4(),
        uuid4(),
        SYMBOL,
        side,
        Decimal(quantity),
        Decimal(price),
        Decimal(commission),
        START + timedelta(days=index),
    )


def result_with_fills(fills: tuple[OrderFill, ...]) -> BacktestResult:
    times = tuple(START + timedelta(days=index) for index in range(5))
    bars = tuple(
        Bar(
            SYMBOL,
            timestamp,
            Decimal("20"),
            Decimal("21"),
            Decimal("19"),
            Decimal("20"),
            100,
        )
        for timestamp in times
    )
    ledger = PaperLedger(Decimal("1000"))
    snapshots = []
    for timestamp in times:
        for item in fills:
            if item.filled_at == timestamp:
                ledger.apply_fill(item)
        snapshots.append(
            ledger.create_account_snapshot({SYMBOL: Decimal("20")}, timestamp)
        )
    steps = tuple(
        BacktestStep(
            index,
            TradingSession(timestamp.date()),
            bars[index],
            None,
            snapshots[index],
            None,
            None,
            None,
        )
        for index, timestamp in enumerate(times)
    )
    request = HistoricalDataRequest(SYMBOL, times[0], times[-1] + timedelta(days=1))
    config = BacktestConfig(
        UUID("11111111-1111-1111-1111-111111111111"),
        request,
        Decimal("1000"),
        risk_limits=RiskLimits(estimated_commission=Decimal("0")),
    )
    return BacktestResult(
        config,
        "test",
        bars,
        steps,
        (),
        (),
        (),
        (),
        fills,
        tuple(snapshots),
        ledger.positions,
        snapshots[-1].equity,
        (),
        bars[0].timestamp,
        bars[-1].timestamp,
    )


def test_no_trade_metrics_are_zero_and_profit_factor_is_undefined() -> None:
    report = PerformanceAnalyzer().analyze(result_with_fills(()))
    assert report.absolute_profit_loss == Decimal("0")
    assert report.total_return == Decimal("0")
    assert report.closed_trade_count == 0
    assert report.win_rate == Decimal("0")
    assert report.profit_factor is None
    assert report.turnover == Decimal("0")
    assert report.average_gross_exposure == Decimal("0")
    assert report.time_in_market_percentage == Decimal("0")


def test_average_cost_partial_realizations_preserve_entry_start_and_commissions() -> (
    None
):
    fills = (
        fill(OrderSide.BUY, "10", "10", 0, "2"),
        fill(OrderSide.BUY, "10", "20", 1, "2"),
        fill(OrderSide.SELL, "5", "25", 2, "1"),
        fill(OrderSide.SELL, "15", "14", 3, "1"),
    )
    report = PerformanceAnalyzer().analyze(result_with_fills(fills))
    first, second = report.trade_realizations
    assert first.average_entry_cost == Decimal("15.2")
    assert first.entry_cost_basis == Decimal("76.0")
    assert first.net_profit_loss == Decimal("48.0")
    assert second.net_profit_loss == Decimal("-19.0")
    assert first.entry_started_at == second.entry_started_at == fills[0].filled_at
    assert report.closed_trade_count == 2
    assert report.winning_trade_count == 1
    assert report.losing_trade_count == 1
    assert report.win_rate == Decimal("0.5")
    assert report.gross_profit == Decimal("48.0")
    assert report.gross_loss == Decimal("-19.0")
    assert report.profit_factor == Decimal("48") / Decimal("19")


def test_breakeven_realization_is_in_win_rate_denominator() -> None:
    fills = (
        fill(OrderSide.BUY, "2", "10", 0),
        fill(OrderSide.SELL, "1", "11", 1),
        fill(OrderSide.SELL, "1", "10", 2),
    )
    report = PerformanceAnalyzer().analyze(result_with_fills(fills))
    assert report.winning_trade_count == 1
    assert report.breakeven_trade_count == 1
    assert report.win_rate == Decimal("0.5")


def test_entry_start_resets_after_full_exit() -> None:
    fills = (
        fill(OrderSide.BUY, "1", "10", 0),
        fill(OrderSide.SELL, "1", "11", 1),
        fill(OrderSide.BUY, "1", "10", 2),
        fill(OrderSide.SELL, "1", "11", 3),
    )
    report = PerformanceAnalyzer().analyze(result_with_fills(fills))
    assert report.trade_realizations[0].entry_started_at == fills[0].filled_at
    assert report.trade_realizations[1].entry_started_at == fills[2].filled_at


def test_dollar_and_percentage_drawdowns_are_tracked_separately() -> None:
    result = result_with_fills(())
    equities = (
        Decimal("100"),
        Decimal("60"),
        Decimal("200"),
        Decimal("150"),
        Decimal("210"),
    )
    snapshots = tuple(
        AccountSnapshot(
            bar.timestamp,
            equity,
            Decimal("0"),
            equity,
            equity,
            Decimal("0"),
            Decimal("0"),
        )
        for bar, equity in zip(result.bars, equities, strict=True)
    )
    object.__setattr__(result, "account_snapshots", snapshots)
    object.__setattr__(result, "final_equity", equities[-1])
    report = PerformanceAnalyzer().analyze(result)
    assert report.drawdowns.maximum_amount.amount == Decimal("50")
    assert report.drawdowns.maximum_amount.peak_equity == Decimal("200")
    assert report.drawdowns.maximum_percentage.percentage == Decimal("0.4")
    assert report.drawdowns.maximum_percentage.peak_equity == Decimal("100")


def test_turnover_and_snapshot_exposure_use_documented_formulas() -> None:
    fills = (
        fill(OrderSide.BUY, "10", "10", 0),
        fill(OrderSide.SELL, "10", "11", 2),
    )
    report = PerformanceAnalyzer().analyze(result_with_fills(fills))
    assert report.turnover == Decimal("210") / Decimal("1046")
    assert report.time_in_market_percentage == Decimal("0.4")
    assert report.maximum_gross_exposure == Decimal("200") / Decimal("1100")


def test_duplicate_out_of_order_mismatched_and_out_of_interval_fills_fail() -> None:
    valid = fill(OrderSide.BUY, "1", "10", 1)
    result = result_with_fills((valid,))
    object.__setattr__(result, "fills", (valid, valid))
    with pytest.raises(InconsistentBacktestAuditError, match="duplicate"):
        PerformanceAnalyzer().analyze(result)

    later = fill(OrderSide.BUY, "1", "10", 2)
    earlier = fill(OrderSide.BUY, "1", "10", 1)
    result = result_with_fills((earlier, later))
    object.__setattr__(result, "fills", (later, earlier))
    with pytest.raises(InconsistentBacktestAuditError, match="nondecreasing"):
        PerformanceAnalyzer().analyze(result)

    result = result_with_fills((valid,))
    object.__setattr__(valid, "symbol", Symbol("SPY"))
    with pytest.raises(InconsistentBacktestAuditError, match="symbol"):
        PerformanceAnalyzer().analyze(result)

    outside = replace(valid, symbol=SYMBOL, filled_at=START - timedelta(days=1))
    result = result_with_fills(())
    object.__setattr__(result, "fills", (outside,))
    with pytest.raises(InconsistentBacktestAuditError, match="outside"):
        PerformanceAnalyzer().analyze(result)


def test_oversell_and_zero_equity_positive_exposure_fail() -> None:
    result = result_with_fills(())
    object.__setattr__(result, "fills", (fill(OrderSide.SELL, "1", "10", 0),))
    with pytest.raises(InconsistentBacktestAuditError, match="exceeds"):
        PerformanceAnalyzer().analyze(result)

    result = result_with_fills(())
    bad = result.account_snapshots[0]
    object.__setattr__(bad, "positions_market_value", Decimal("1"))
    object.__setattr__(bad, "equity", Decimal("0"))
    object.__setattr__(
        result, "account_snapshots", (bad, *result.account_snapshots[1:])
    )
    with pytest.raises(InconsistentBacktestAuditError, match="positive exposure"):
        PerformanceAnalyzer().analyze(result)


def test_repeated_analysis_is_equal_and_does_not_mutate_result() -> None:
    result = result_with_fills(
        (fill(OrderSide.BUY, "1", "10", 0), fill(OrderSide.SELL, "1", "11", 1))
    )
    before = result.fills
    analyzer = PerformanceAnalyzer()
    assert analyzer.analyze(result) == analyzer.analyze(result)
    assert result.fills == before


def test_snapshot_audit_validation_fails_closed() -> None:
    analyzer = PerformanceAnalyzer()

    empty = result_with_fills(())
    object.__setattr__(empty, "account_snapshots", ())
    with pytest.raises(InconsistentBacktestAuditError, match="at least one"):
        analyzer.analyze(empty)

    wrong_count = result_with_fills(())
    object.__setattr__(
        wrong_count, "account_snapshots", wrong_count.account_snapshots[:-1]
    )
    with pytest.raises(InconsistentBacktestAuditError, match="equal counts"):
        analyzer.analyze(wrong_count)

    reversed_times = result_with_fills(())
    snapshots = list(reversed_times.account_snapshots)
    snapshots[0], snapshots[1] = snapshots[1], snapshots[0]
    object.__setattr__(reversed_times, "account_snapshots", tuple(snapshots))
    with pytest.raises(InconsistentBacktestAuditError, match="nondecreasing"):
        analyzer.analyze(reversed_times)

    wrong_final = result_with_fills(())
    object.__setattr__(wrong_final, "final_equity", Decimal("999"))
    with pytest.raises(InconsistentBacktestAuditError, match="final snapshot"):
        analyzer.analyze(wrong_final)

    nonfinite = result_with_fills(())
    object.__setattr__(nonfinite.account_snapshots[0], "equity", Decimal("Infinity"))
    with pytest.raises(InconsistentBacktestAuditError, match="finite"):
        analyzer.analyze(nonfinite)


def test_realized_profit_loss_must_match_reconstruction() -> None:
    result = result_with_fills(
        (fill(OrderSide.BUY, "1", "10", 0), fill(OrderSide.SELL, "1", "11", 1))
    )
    object.__setattr__(
        result.account_snapshots[-1], "realized_profit_loss", Decimal("999")
    )
    with pytest.raises(InconsistentBacktestAuditError, match="realized P&L"):
        PerformanceAnalyzer().analyze(result)


def test_zero_equity_and_zero_exposure_have_zero_ratios() -> None:
    result = result_with_fills(())
    zero_snapshots = tuple(
        AccountSnapshot(
            snapshot.timestamp,
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
        )
        for snapshot in result.account_snapshots
    )
    object.__setattr__(result, "account_snapshots", zero_snapshots)
    object.__setattr__(result, "final_equity", Decimal("0"))
    report = PerformanceAnalyzer().analyze(result)
    assert report.turnover == Decimal("0")
    assert report.average_gross_exposure == Decimal("0")
    assert report.maximum_gross_exposure == Decimal("0")
