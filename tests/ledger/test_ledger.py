from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
from uuid import uuid4

import pytest

from trading_bot.domain import OrderFill, OrderSide, Position, Symbol
from trading_bot.ledger import (
    DuplicateFillError,
    InsufficientCashError,
    InsufficientPositionError,
    PaperLedger,
    PositionNotFoundError,
    PriceNotAvailableError,
)

NOW = datetime(2026, 1, 2, 12, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def fill(
    side: OrderSide,
    *,
    symbol: Symbol = SPY,
    quantity: str = "1",
    price: str = "100",
    commission: str = "0",
) -> OrderFill:
    return OrderFill(
        fill_id=uuid4(),
        order_id=uuid4(),
        symbol=symbol,
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        commission=Decimal(commission),
        filled_at=NOW,
    )


@pytest.mark.parametrize("starting_cash", [Decimal("0"), Decimal("-1")])
def test_rejects_nonpositive_starting_cash(starting_cash: Decimal) -> None:
    with pytest.raises(ValueError, match="starting_cash"):
        PaperLedger(starting_cash)


def test_initial_account_state() -> None:
    ledger = PaperLedger(Decimal("10000"))
    assert ledger.cash == Decimal("10000")
    assert ledger.realized_profit_loss == Decimal("0")
    assert dict(ledger.positions) == {}
    assert ledger.fills == ()


def test_first_buy_includes_commission_in_cost_basis() -> None:
    ledger = PaperLedger(Decimal("2000"))
    purchase = fill(OrderSide.BUY, quantity="10", commission="2")
    ledger.apply_fill(purchase)
    assert ledger.cash == Decimal("998")
    assert ledger.get_position(SPY) == Position(SPY, Decimal("10"), Decimal("100.2"))
    assert ledger.fills == (purchase,)


def test_additional_buy_recalculates_average_cost() -> None:
    ledger = PaperLedger(Decimal("5000"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="10", price="100", commission="2"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="5", price="120", commission="1"))
    position = ledger.get_position(SPY)
    assert position is not None
    assert position.quantity == Decimal("15")
    assert position.average_cost == Decimal("1603") / Decimal("15")
    assert ledger.cash == Decimal("3397")


def test_buying_multiple_symbols_tracks_separate_positions() -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="2"))
    ledger.apply_fill(fill(OrderSide.BUY, symbol=QQQ, price="200"))
    assert set(ledger.positions) == {SPY, QQQ}


def test_buy_can_use_exact_available_cash() -> None:
    ledger = PaperLedger(Decimal("1002"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="10", commission="2"))
    assert ledger.cash == Decimal("0")


def test_insufficient_cash_is_atomic() -> None:
    ledger = PaperLedger(Decimal("100"))
    first = fill(OrderSide.BUY, price="50")
    ledger.apply_fill(first)
    before = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    with pytest.raises(InsufficientCashError, match="only 50"):
        ledger.apply_fill(fill(OrderSide.BUY, price="51"))
    after = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    assert after == before


def test_partial_sale_preserves_average_cost_and_calculates_profit() -> None:
    ledger = PaperLedger(Decimal("2000"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="10", commission="2"))
    sale = fill(OrderSide.SELL, quantity="4", price="120", commission="1")
    ledger.apply_fill(sale)
    position = ledger.get_position(SPY)
    assert position == Position(SPY, Decimal("6"), Decimal("100.2"))
    assert ledger.cash == Decimal("1477")
    assert ledger.realized_profit_loss == Decimal("78.2")


def test_full_sale_removes_position_and_records_loss() -> None:
    ledger = PaperLedger(Decimal("2000"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="10", commission="2"))
    ledger.apply_fill(fill(OrderSide.SELL, quantity="10", price="90", commission="3"))
    assert ledger.get_position(SPY) is None
    assert SPY not in ledger.positions
    assert ledger.cash == Decimal("1895")
    assert ledger.realized_profit_loss == Decimal("-105")


def test_sell_commission_reduces_realized_profit() -> None:
    without_commission = PaperLedger(Decimal("1000"))
    with_commission = PaperLedger(Decimal("1000"))
    for ledger in (without_commission, with_commission):
        ledger.apply_fill(fill(OrderSide.BUY, quantity="5", price="100"))
    without_commission.apply_fill(fill(OrderSide.SELL, quantity="2", price="110"))
    with_commission.apply_fill(
        fill(OrderSide.SELL, quantity="2", price="110", commission="1.5")
    )
    assert without_commission.realized_profit_loss == Decimal("20")
    assert with_commission.realized_profit_loss == Decimal("18.5")


def test_selling_missing_position_is_atomic() -> None:
    ledger = PaperLedger(Decimal("1000"))
    before = (ledger.cash, ledger.positions, ledger.fills)
    with pytest.raises(PositionNotFoundError, match="SPY"):
        ledger.apply_fill(fill(OrderSide.SELL))
    assert (ledger.cash, ledger.positions, ledger.fills) == before


def test_overselling_is_atomic() -> None:
    ledger = PaperLedger(Decimal("1000"))
    purchase = fill(OrderSide.BUY, quantity="2")
    ledger.apply_fill(purchase)
    before = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    with pytest.raises(InsufficientPositionError, match="owned quantity is 2"):
        ledger.apply_fill(fill(OrderSide.SELL, quantity="2.1"))
    after = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    assert after == before


def test_sell_that_would_make_cash_negative_is_atomic() -> None:
    ledger = PaperLedger(Decimal("100"))
    purchase = fill(OrderSide.BUY, price="100")
    ledger.apply_fill(purchase)
    before = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    with pytest.raises(InsufficientCashError, match="cash negative"):
        ledger.apply_fill(fill(OrderSide.SELL, price="1", commission="2"))
    after = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    assert after == before


def test_duplicate_fill_is_atomic() -> None:
    ledger = PaperLedger(Decimal("1000"))
    purchase = fill(OrderSide.BUY)
    ledger.apply_fill(purchase)
    before = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    with pytest.raises(DuplicateFillError, match=str(purchase.fill_id)):
        ledger.apply_fill(purchase)
    after = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    assert after == before


def test_fill_history_preserves_application_order_and_is_immutable() -> None:
    ledger = PaperLedger(Decimal("1000"))
    first = fill(OrderSide.BUY)
    second = fill(OrderSide.BUY, symbol=QQQ)
    ledger.apply_fill(first)
    ledger.apply_fill(second)
    history = ledger.fills
    assert history == (first, second)
    assert isinstance(history, tuple)
    assert history + (first,) != ledger.fills


def test_returned_positions_cannot_mutate_ledger_state() -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(fill(OrderSide.BUY))
    positions = ledger.positions
    assert isinstance(positions, MappingProxyType)
    with pytest.raises(TypeError):
        positions[QQQ] = Position(QQQ, Decimal("1"), Decimal("1"))  # type: ignore[index]
    assert set(ledger.positions) == {SPY}


def test_empty_account_snapshot() -> None:
    ledger = PaperLedger(Decimal("1000"))
    snapshot = ledger.create_account_snapshot({}, NOW)
    assert snapshot.cash == Decimal("1000")
    assert snapshot.positions_market_value == Decimal("0")
    assert snapshot.equity == Decimal("1000")
    assert snapshot.buying_power == Decimal("1000")
    assert snapshot.realized_profit_loss == Decimal("0")
    assert snapshot.unrealized_profit_loss == Decimal("0")


def test_multiple_position_valuation_and_extra_price() -> None:
    ledger = PaperLedger(Decimal("2000"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="2", commission="1"))
    ledger.apply_fill(fill(OrderSide.BUY, symbol=QQQ, price="200"))
    snapshot = ledger.create_account_snapshot(
        {SPY: Decimal("110"), QQQ: Decimal("190"), Symbol("DIA"): Decimal("1")},
        NOW,
    )
    assert snapshot.cash == Decimal("1599")
    assert snapshot.positions_market_value == Decimal("410")
    assert snapshot.equity == Decimal("2009")
    assert snapshot.buying_power == snapshot.cash
    assert snapshot.unrealized_profit_loss == Decimal("9")


def test_snapshot_includes_cumulative_realized_profit() -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(fill(OrderSide.BUY, quantity="2"))
    ledger.apply_fill(fill(OrderSide.SELL, quantity="1", price="110"))
    snapshot = ledger.create_account_snapshot({SPY: Decimal("105")}, NOW)
    assert snapshot.realized_profit_loss == Decimal("10")
    assert snapshot.unrealized_profit_loss == Decimal("5")


def test_snapshot_rejects_missing_or_invalid_price() -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(fill(OrderSide.BUY))
    with pytest.raises(PriceNotAvailableError, match="no current price"):
        ledger.create_account_snapshot({}, NOW)
    for price in (Decimal("0"), Decimal("-1")):
        with pytest.raises(PriceNotAvailableError, match="positive Decimal"):
            ledger.create_account_snapshot({SPY: price}, NOW)


def test_snapshot_normalizes_timestamp_and_does_not_mutate_state() -> None:
    ledger = PaperLedger(Decimal("1000"))
    ledger.apply_fill(fill(OrderSide.BUY))
    before = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    local = datetime(2026, 1, 2, 4, tzinfo=timezone(timedelta(hours=-8)))
    snapshot = ledger.create_account_snapshot({SPY: Decimal("100")}, local)
    assert snapshot.timestamp == NOW
    assert snapshot.timestamp.tzinfo is UTC
    after = (ledger.cash, ledger.positions, ledger.realized_profit_loss, ledger.fills)
    assert after == before
