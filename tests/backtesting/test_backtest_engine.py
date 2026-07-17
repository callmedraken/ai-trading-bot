from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4, uuid5

import pytest

from trading_bot.backtesting import (
    BacktestCalendarAlignmentError,
    BacktestConfig,
    BacktestEngine,
    BacktestExecutionError,
    BacktestUnexecutedReason,
    InsufficientHistoricalDataError,
    StrategyContractError,
)
from trading_bot.domain import (
    Bar,
    OrderFill,
    OrderSide,
    OrderStatus,
    OrderType,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import ExecutionInstruction, OrderEngine
from trading_bot.ledger import PaperLedger
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    AdjustmentType,
    HistoricalDataRequest,
    HistoricalDataResult,
    Timeframe,
)
from trading_bot.risk import RiskDecision, RiskLimits, RiskOutcome

SPY = Symbol("SPY")
START = datetime(2026, 1, 2, 12, tzinfo=UTC)
END = datetime(2026, 1, 8, 12, tzinfo=UTC)
BAR_TIMES = (
    datetime(2026, 1, 2, 21, tzinfo=UTC),
    datetime(2026, 1, 5, 21, tzinfo=UTC),
    datetime(2026, 1, 6, 21, tzinfo=UTC),
    datetime(2026, 1, 7, 21, tzinfo=UTC),
)


def make_bar(index: int, *, open_price: str | None = None) -> Bar:
    base = Decimal("100") + Decimal(index * 10)
    open_value = Decimal(open_price) if open_price is not None else base
    return Bar(
        symbol=SPY,
        timestamp=BAR_TIMES[index],
        open=open_value,
        high=max(open_value, base + Decimal("2")),
        low=min(open_value, base - Decimal("2")),
        close=base + Decimal("1"),
        volume=1000,
    )


class InMemoryProvider:
    def __init__(self, bars: tuple[Bar, ...]) -> None:
        self.bars = bars

    def get_bars(self, request: HistoricalDataRequest) -> HistoricalDataResult:
        return HistoricalDataResult(request, self.bars, "memory")


class NoTradeStrategy:
    def evaluate(self, context):  # type: ignore[no-untyped-def]
        return None


class ScheduledStrategy:
    def __init__(self, schedule: dict[int, tuple[OrderSide, str]]) -> None:
        self.schedule = schedule
        self.history_lengths: list[int] = []

    def evaluate(self, context):  # type: ignore[no-untyped-def]
        self.history_lengths.append(len(context.history))
        selected = self.schedule.get(context.step_index)
        if selected is None:
            return None
        side, quantity = selected
        return TradeProposal.create(
            proposal_id=uuid5(context.run_id, f"proposal:{context.step_index}"),
            symbol=SPY,
            side=side,
            desired_quantity=Decimal(quantity),
            created_at=context.current_bar.timestamp,
            reason="test",
        )


def request() -> HistoricalDataRequest:
    return HistoricalDataRequest(SPY, START, END, Timeframe.DAY_1, AdjustmentType.RAW)


def liberal_limits(commission: str = "0", **overrides: object) -> RiskLimits:
    values: dict[str, object] = {
        "max_position_percent": Decimal("1"),
        "max_total_exposure_percent": Decimal("1"),
        "minimum_cash_reserve_percent": Decimal("0"),
        "allow_fractional_shares": True,
        "fractional_increment": Decimal("0.001"),
        "estimated_commission": Decimal(commission),
    }
    values.update(overrides)
    return RiskLimits(**values)  # type: ignore[arg-type]


def config(**overrides: object) -> BacktestConfig:
    values: dict[str, object] = {
        "run_id": UUID("11111111-1111-1111-1111-111111111111"),
        "data_request": request(),
        "starting_cash": Decimal("10000"),
        "risk_limits": liberal_limits(),
    }
    values.update(overrides)
    return BacktestConfig(**values)  # type: ignore[arg-type]


def run(
    bars: tuple[Bar, ...], strategy: object, settings: BacktestConfig | None = None
):  # type: ignore[no-untyped-def]
    return BacktestEngine(InMemoryProvider(bars), NYSEMarketCalendar()).run(
        settings or config(),
        strategy,  # type: ignore[arg-type]
    )


def test_empty_data_is_rejected() -> None:
    with pytest.raises(InsufficientHistoricalDataError):
        run((), NoTradeStrategy())


def test_no_trade_run_has_one_close_snapshot_per_bar() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    result = run(bars, NoTradeStrategy())
    assert len(result.steps) == len(bars)
    assert len(result.account_snapshots) == len(bars)
    assert result.orders == result.fills == result.proposals == ()
    assert result.final_equity == Decimal("10000")


def test_buy_uses_next_bar_open_and_step_keeps_submitted_snapshot() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    result = run(bars, ScheduledStrategy({0: (OrderSide.BUY, "2")}))
    assert result.steps[0].submitted_order is not None
    assert result.steps[0].submitted_order.status is OrderStatus.SUBMITTED
    assert result.steps[0].opening_fill is None
    assert result.steps[1].opening_fill == result.fills[0]
    assert result.fills[0].price == bars[1].open
    assert result.orders[0].status is OrderStatus.FILLED
    assert result.orders[0].filled_quantity == Decimal("2")


def test_buy_then_sell_realized_profit_and_audit_order() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    strategy = ScheduledStrategy({0: (OrderSide.BUY, "2"), 1: (OrderSide.SELL, "2")})
    result = run(bars, strategy)
    assert [fill.side for fill in result.fills] == [OrderSide.BUY, OrderSide.SELL]
    assert result.final_positions == {}
    assert result.account_snapshots[2].realized_profit_loss == Decimal("20")
    step = result.steps[1]
    assert step.opening_fill is not None
    assert step.account_snapshot.cash == Decimal("9780")
    assert step.proposal is not None
    assert step.risk_decision is not None
    assert step.submitted_order is not None


def test_strategy_never_receives_future_bars() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    strategy = ScheduledStrategy({})
    run(bars, strategy)
    assert strategy.history_lengths == [1, 2, 3, 4]


def test_final_bar_proposal_is_risk_evaluated_but_not_ordered() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    result = run(bars, ScheduledStrategy({3: (OrderSide.BUY, "1")}))
    final = result.steps[-1]
    assert final.proposal is not None
    assert final.risk_decision is not None
    assert final.submitted_order is None
    assert final.unexecuted_reason is BacktestUnexecutedReason.END_OF_DATA
    assert result.orders == ()
    assert result.unexecuted_final_bar_proposals == (final.proposal,)


def test_risk_rejection_and_resize_are_audited() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    rejected = run(
        bars,
        ScheduledStrategy({0: (OrderSide.BUY, "1")}),
        config(trading_enabled=False),
    )
    assert rejected.risk_decisions[0].outcome is RiskOutcome.REJECTED
    assert rejected.orders == ()

    limits = liberal_limits(max_order_notional=Decimal("150"))
    resized = run(
        bars,
        ScheduledStrategy({0: (OrderSide.BUY, "2")}),
        config(risk_limits=limits),
    )
    assert resized.risk_decisions[0].outcome is RiskOutcome.RESIZED
    assert resized.orders[0].request.quantity == Decimal("1.485")


def test_commission_and_buy_sell_slippage() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    settings = config(
        risk_limits=liberal_limits("1"),
        fixed_commission=Decimal("1"),
        slippage_basis_points=Decimal("100"),
    )
    result = run(
        bars,
        ScheduledStrategy({0: (OrderSide.BUY, "1"), 1: (OrderSide.SELL, "1")}),
        settings,
    )
    assert result.fills[0].price == bars[1].open * Decimal("1.01")
    assert result.fills[1].price == bars[2].open * Decimal("0.99")
    assert all(fill.commission == Decimal("1") for fill in result.fills)


def test_price_gap_failure_raises_and_does_not_complete() -> None:
    bars = (make_bar(0), make_bar(1, open_price="2000"), make_bar(2), make_bar(3))
    settings = config(starting_cash=Decimal("1000"))
    with pytest.raises(BacktestExecutionError):
        run(bars, ScheduledStrategy({0: (OrderSide.BUY, "9")}), settings)


def test_calendar_missing_session_policy() -> None:
    bars = (make_bar(0), make_bar(2), make_bar(3))
    with pytest.raises(BacktestCalendarAlignmentError, match="missing"):
        run(bars, NoTradeStrategy())
    result = run(bars, NoTradeStrategy(), config(allow_missing_sessions=True))
    assert len(result.steps) == 3


def test_non_session_and_duplicate_derived_session_are_rejected() -> None:
    weekend = Bar(
        SPY,
        datetime(2026, 1, 3, 21, tzinfo=UTC),
        Decimal("100"),
        Decimal("102"),
        Decimal("99"),
        Decimal("101"),
        1,
    )
    with pytest.raises(BacktestCalendarAlignmentError, match="not an NYSE"):
        run((weekend,), NoTradeStrategy(), config(allow_missing_sessions=True))
    duplicate = Bar(
        SPY,
        BAR_TIMES[0].replace(hour=22),
        Decimal("100"),
        Decimal("102"),
        Decimal("99"),
        Decimal("101"),
        1,
    )
    with pytest.raises(BacktestCalendarAlignmentError, match="multiple bars"):
        run(
            (make_bar(0), duplicate),
            NoTradeStrategy(),
            config(allow_missing_sessions=True),
        )


def test_duplicate_or_mistimed_strategy_proposals_are_rejected() -> None:
    duplicate_id = uuid4()

    class BadStrategy:
        def evaluate(self, context):  # type: ignore[no-untyped-def]
            return TradeProposal.create(
                proposal_id=duplicate_id,
                symbol=SPY,
                side=OrderSide.BUY,
                desired_quantity=Decimal("1"),
                created_at=context.current_bar.timestamp,
                reason="bad",
            )

    bars = tuple(make_bar(index) for index in range(4))
    with pytest.raises(StrategyContractError, match="duplicate proposal_id"):
        run(bars, BadStrategy())

    class MistimedStrategy:
        def evaluate(self, context):  # type: ignore[no-untyped-def]
            return TradeProposal.create(
                symbol=SPY,
                side=OrderSide.BUY,
                desired_quantity=Decimal("1"),
                created_at=BAR_TIMES[-1],
                reason="future",
            )

    with pytest.raises(StrategyContractError, match="must equal"):
        run(bars, MistimedStrategy())


def test_repeated_runs_with_fixed_inputs_are_equal() -> None:
    bars = tuple(make_bar(index) for index in range(4))
    first = run(bars, ScheduledStrategy({0: (OrderSide.BUY, "1")}))
    second = run(bars, ScheduledStrategy({0: (OrderSide.BUY, "1")}))
    assert first == second


def test_order_engine_and_ledger_copy_safely_and_failure_is_atomic() -> None:
    orders = OrderEngine()
    ledger = PaperLedger(Decimal("100"))
    proposal = TradeProposal.create(
        symbol=SPY,
        side=OrderSide.BUY,
        desired_quantity=Decimal("1"),
        created_at=BAR_TIMES[0],
        reason="copy test",
    )
    risk = RiskDecision(proposal, RiskOutcome.APPROVED, Decimal("1"), (), BAR_TIMES[0])
    order = orders.create_order(
        risk,
        ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, BAR_TIMES[0]),
    )
    orders.submit_order(order.request.order_id, BAR_TIMES[0])
    assert deepcopy(orders).orders == orders.orders
    assert deepcopy(ledger).cash == ledger.cash
    bad_fill = OrderFill(
        uuid4(),
        order.request.order_id,
        SPY,
        OrderSide.BUY,
        Decimal("1"),
        Decimal("101"),
        Decimal("0"),
        BAR_TIMES[1],
    )
    orders_before = dict(orders.orders)
    events_before = orders.get_events()
    with pytest.raises(BacktestExecutionError):
        BacktestEngine._apply_fill_atomically(orders, ledger, bad_fill, uuid4())
    assert dict(orders.orders) == orders_before
    assert orders.get_events() == events_before
    assert ledger.cash == Decimal("100")
    assert ledger.fills == ()
