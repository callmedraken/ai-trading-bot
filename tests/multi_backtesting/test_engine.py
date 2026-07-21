from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

import pytest

from trading_bot.domain import Bar, OrderSide, Symbol, TradeProposal
from trading_bot.market_data import (
    AlignedMarketFrame,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
    MultiSymbolHistoricalDataResult,
)
from trading_bot.multi_backtesting import (
    IncompleteMarketFrameError,
    MultiSymbolBacktestConfig,
    MultiSymbolBacktestEngine,
    MultiSymbolBacktestExecutionError,
    MultiSymbolUnexecutedReason,
)
from trading_bot.risk import RiskLimits, RiskOutcome

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
SYMBOLS = (SPY, QQQ)
START = datetime(2026, 1, 1, 20, tzinfo=UTC)
RUN_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_bar(symbol: Symbol, index: int, open_price: str = "100") -> Bar:
    timestamp = START + timedelta(days=index)
    opened = Decimal(open_price)
    return Bar(
        symbol,
        timestamp,
        opened,
        max(opened, Decimal("102")),
        min(opened, Decimal("99")),
        Decimal("100"),
        1000,
    )


def data(
    *, incomplete: bool = False, gap: bool = False
) -> MultiSymbolHistoricalDataResult:
    request = MultiSymbolHistoricalDataRequest(
        SYMBOLS,
        START,
        START + timedelta(days=4),
        missing_bar_policy=MissingBarPolicy.UNION,
    )
    frames = []
    for index in range(3):
        bars = {SPY: make_bar(SPY, index)}
        if not (incomplete and index == 1):
            bars[QQQ] = make_bar(QQQ, index, "1000" if gap and index == 1 else "100")
        frames.append(AlignedMarketFrame(START + timedelta(days=index), SYMBOLS, bars))
    return MultiSymbolHistoricalDataResult(request, tuple(frames), "memory")


class Provider:
    def __init__(self, result: MultiSymbolHistoricalDataResult) -> None:
        self.result = result

    def get_bars(self, request):  # type: ignore[no-untyped-def]
        assert request == self.result.request
        return self.result


def limits() -> RiskLimits:
    return RiskLimits(
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
    )


def config(
    result: MultiSymbolHistoricalDataResult, cash: str = "1000"
) -> MultiSymbolBacktestConfig:
    return MultiSymbolBacktestConfig(RUN_ID, result.request, Decimal(cash), limits())


def proposal(context, symbol: Symbol, side: OrderSide, quantity: str):  # type: ignore[no-untyped-def]
    return TradeProposal.create(
        proposal_id=uuid5(RUN_ID, f"{context.step_index}:{symbol}:{side}"),
        symbol=symbol,
        side=side,
        desired_quantity=Decimal(quantity),
        created_at=context.timestamp,
        reason="test",
    )


class ScheduledStrategy:
    def __init__(self, schedule):  # type: ignore[no-untyped-def]
        self.schedule = schedule
        self.history_lengths = []

    def evaluate(self, context):  # type: ignore[no-untyped-def]
        self.history_lengths.append(len(context.history))
        return tuple(
            proposal(context, symbol, side, quantity)
            for symbol, side, quantity in self.schedule.get(context.step_index, ())
        )


def test_two_symbols_fill_next_open_and_portfolio_is_valued() -> None:
    source = data()
    strategy = ScheduledStrategy(
        {0: ((QQQ, OrderSide.BUY, "2"), (SPY, OrderSide.BUY, "2"))}
    )
    result = MultiSymbolBacktestEngine(Provider(source)).run(config(source), strategy)
    assert [fill.symbol for fill in result.fills] == [SPY, QQQ]
    assert all(fill.filled_at == source.frames[1].timestamp for fill in result.fills)
    assert result.steps[0].opening_fills == ()
    assert len(result.steps[1].opening_fills) == 2
    assert result.account_snapshots[1].positions_market_value == Decimal("400")
    assert result.final_cash == Decimal("600")
    assert tuple(result.final_positions) == SYMBOLS
    assert strategy.history_lengths == [1, 2, 3]


def test_collective_buying_power_is_reserved_in_canonical_order() -> None:
    source = data()
    strategy = ScheduledStrategy(
        {0: ((QQQ, OrderSide.BUY, "8"), (SPY, OrderSide.BUY, "8"))}
    )
    result = MultiSymbolBacktestEngine(Provider(source)).run(config(source), strategy)
    decisions = result.steps[0].risk_decisions
    assert [decision.proposal.symbol for decision in decisions] == [SPY, QQQ]
    assert decisions[0].approved_quantity == Decimal("8")
    assert decisions[1].outcome is RiskOutcome.RESIZED
    assert decisions[1].approved_quantity == Decimal("2")


def test_buy_then_sell_uses_new_proposal_after_opening_fill() -> None:
    source = data()
    strategy = ScheduledStrategy(
        {
            0: ((SPY, OrderSide.BUY, "2"),),
            1: ((SPY, OrderSide.SELL, "2"),),
        }
    )
    result = MultiSymbolBacktestEngine(Provider(source)).run(config(source), strategy)
    assert [fill.side for fill in result.fills] == [OrderSide.BUY, OrderSide.SELL]
    assert result.final_positions == {}
    assert result.final_realized_profit_loss == Decimal("0")


def test_final_frame_approved_proposal_is_terminal_without_order() -> None:
    source = data()
    strategy = ScheduledStrategy({2: ((SPY, OrderSide.BUY, "1"),)})
    result = MultiSymbolBacktestEngine(Provider(source)).run(config(source), strategy)
    assert result.final_orders == ()
    assert len(result.unexecuted_proposals) == 1
    terminal = result.unexecuted_proposals[0]
    assert terminal.reason is MultiSymbolUnexecutedReason.END_OF_DATA
    assert terminal.risk_decision.outcome is RiskOutcome.APPROVED
    assert result.order_events == result.fills == ()


def test_incomplete_input_fails_before_strategy_is_called() -> None:
    source = data(incomplete=True)

    class NeverCalled:
        called = False

        def evaluate(self, context):  # type: ignore[no-untyped-def]
            self.called = True
            return ()

    strategy = NeverCalled()
    with pytest.raises(IncompleteMarketFrameError):
        MultiSymbolBacktestEngine(Provider(source)).run(config(source), strategy)
    assert not strategy.called


def test_next_open_price_gap_fails_entire_batch() -> None:
    source = data(gap=True)
    strategy = ScheduledStrategy(
        {0: ((SPY, OrderSide.BUY, "4"), (QQQ, OrderSide.BUY, "4"))}
    )
    with pytest.raises(MultiSymbolBacktestExecutionError, match="cash"):
        MultiSymbolBacktestEngine(Provider(source)).run(config(source), strategy)


def test_repeated_runs_are_equal() -> None:
    source = data()
    schedule = {0: ((SPY, OrderSide.BUY, "1"), (QQQ, OrderSide.BUY, "1"))}
    engine = MultiSymbolBacktestEngine(Provider(source))
    assert engine.run(config(source), ScheduledStrategy(schedule)) == engine.run(
        config(source), ScheduledStrategy(schedule)
    )
