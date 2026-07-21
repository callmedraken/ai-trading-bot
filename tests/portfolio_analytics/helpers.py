"""Explicit immutable multi-symbol backtest audit fixtures."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from trading_bot.domain import (
    Bar,
    Order,
    OrderFill,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Symbol,
    TimeInForce,
)
from trading_bot.execution import OrderEvent, OrderEventType
from trading_bot.ledger import PaperLedger
from trading_bot.market_data import (
    AlignedMarketFrame,
    MissingBarPolicy,
    MultiSymbolHistoricalDataRequest,
)
from trading_bot.multi_backtesting import (
    MultiSymbolBacktestConfig,
    MultiSymbolBacktestResult,
    MultiSymbolBacktestStep,
)
from trading_bot.risk import RiskLimits

SPY = Symbol("SPY")
QQQ = Symbol("QQQ")
SYMBOLS = (SPY, QQQ)
START = datetime(2026, 1, 5, 20, tzinfo=UTC)


def make_fill(
    symbol: Symbol,
    side: OrderSide,
    quantity: str,
    price: str,
    frame_index: int,
    ordinal: int,
    commission: str = "0",
) -> OrderFill:
    return OrderFill(
        UUID(int=1000 + ordinal),
        UUID(int=2000 + ordinal),
        symbol,
        side,
        Decimal(quantity),
        Decimal(price),
        Decimal(commission),
        START + timedelta(days=frame_index),
    )


def make_result(
    fills: tuple[OrderFill, ...] = (),
    *,
    closes: tuple[tuple[str, str], ...] | None = None,
    starting_cash: str = "10000",
) -> MultiSymbolBacktestResult:
    closes = closes or (("100", "100"),) * 5
    timestamps = tuple(START + timedelta(days=index) for index in range(len(closes)))
    request = MultiSymbolHistoricalDataRequest(
        SYMBOLS,
        timestamps[0],
        timestamps[-1] + timedelta(days=1),
        missing_bar_policy=MissingBarPolicy.INTERSECTION,
    )
    frames = []
    for timestamp, price_pair in zip(timestamps, closes, strict=True):
        bars = {}
        for symbol, raw_price in zip(SYMBOLS, price_pair, strict=True):
            price = Decimal(raw_price)
            bars[symbol] = Bar(symbol, timestamp, price, price, price, price, 1000)
        frames.append(AlignedMarketFrame(timestamp, SYMBOLS, bars))

    ledger = PaperLedger(Decimal(starting_cash))
    snapshots = []
    steps = []
    for index, frame in enumerate(frames):
        opening_fills = tuple(
            fill for fill in fills if fill.filled_at == frame.timestamp
        )
        for fill in opening_fills:
            ledger.apply_fill(fill)
        snapshot = ledger.create_account_snapshot(
            {symbol: frame.bars_by_symbol[symbol].close for symbol in SYMBOLS},
            frame.timestamp,
        )
        snapshots.append(snapshot)
        steps.append(
            MultiSymbolBacktestStep(index, frame, opening_fills, snapshot, (), (), ())
        )

    orders = []
    events = []
    for ordinal, fill in enumerate(fills):
        submitted_at = timestamps[max(0, timestamps.index(fill.filled_at) - 1)]
        request_model = OrderRequest(
            fill.order_id,
            fill.symbol,
            fill.side,
            OrderType.MARKET,
            fill.quantity,
            TimeInForce.DAY,
            submitted_at,
        )
        orders.append(
            Order(
                request_model,
                OrderStatus.FILLED,
                fill.quantity,
                fill.price,
            )
        )
        events.extend(
            (
                OrderEvent(
                    UUID(int=3000 + ordinal * 3),
                    fill.order_id,
                    OrderEventType.CREATED,
                    submitted_at,
                ),
                OrderEvent(
                    UUID(int=3001 + ordinal * 3),
                    fill.order_id,
                    OrderEventType.SUBMITTED,
                    submitted_at,
                ),
                OrderEvent(
                    UUID(int=3002 + ordinal * 3),
                    fill.order_id,
                    OrderEventType.FILLED,
                    fill.filled_at,
                    fill.fill_id,
                ),
            )
        )
    config = MultiSymbolBacktestConfig(
        UUID("11111111-2222-3333-4444-555555555555"),
        request,
        Decimal(starting_cash),
        RiskLimits(
            max_position_percent=Decimal("1"),
            max_total_exposure_percent=Decimal("1"),
            minimum_cash_reserve_percent=Decimal("0"),
            allow_fractional_shares=True,
            fractional_increment=Decimal("0.001"),
        ),
    )
    return MultiSymbolBacktestResult(
        config,
        "fixture",
        tuple(frames),
        tuple(steps),
        (),
        (),
        tuple(orders),
        tuple(events),
        fills,
        tuple(snapshots),
        ledger.positions,
        snapshots[-1].equity,
        (),
        frames[0].timestamp,
        frames[-1].timestamp,
    )
