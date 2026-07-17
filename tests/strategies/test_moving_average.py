from datetime import UTC, date, datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

import pytest

from trading_bot.backtesting import BacktestContext
from trading_bot.domain import Bar, OrderSide, Position, Symbol
from trading_bot.ledger import AccountSnapshot
from trading_bot.market_calendar import TradingSession
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverConfigError,
    MovingAverageCrossoverStrategy,
)

SYMBOL = Symbol("MATEST")
RUN_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_context(
    closes: list[str], *, invested: bool = False, step_index: int | None = None
) -> BacktestContext:
    bars = tuple(
        Bar(
            SYMBOL,
            datetime(2026, 1, index + 2, 20, tzinfo=UTC),
            Decimal(close),
            Decimal(close) + Decimal("1"),
            Decimal(close) - Decimal("1"),
            Decimal(close),
            100,
        )
        for index, close in enumerate(closes)
    )
    positions = (
        {SYMBOL: Position(SYMBOL, Decimal("2.5"), Decimal("10"))} if invested else {}
    )
    snapshot = AccountSnapshot(
        bars[-1].timestamp,
        Decimal("1000"),
        Decimal("0"),
        Decimal("1000"),
        Decimal("1000"),
        Decimal("0"),
        Decimal("0"),
    )
    return BacktestContext(
        RUN_ID,
        len(bars) - 1 if step_index is None else step_index,
        TradingSession(date(2026, 1, len(bars) + 1)),
        bars[-1],
        bars,
        snapshot,
        positions,
    )


@pytest.mark.parametrize(
    ("short", "long", "quantity"),
    [
        (0, 3, Decimal("1")),
        (-1, 3, Decimal("1")),
        (True, 3, Decimal("1")),
        (2, 2, Decimal("1")),
        (3, 2, Decimal("1")),
        (2, 3, Decimal("0")),
        (2, 3, Decimal("-1")),
        (2, 3, Decimal("NaN")),
        (2, 3, Decimal("Infinity")),
    ],
)
def test_config_validation(short: object, long: object, quantity: object) -> None:
    with pytest.raises(MovingAverageCrossoverConfigError):
        MovingAverageCrossoverConfig(short, long, quantity)  # type: ignore[arg-type]


def test_quantity_must_be_decimal() -> None:
    with pytest.raises(MovingAverageCrossoverConfigError, match="Decimal"):
        MovingAverageCrossoverConfig(2, 3, 1)  # type: ignore[arg-type]


def test_insufficient_history_and_no_crossover_return_none() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    )
    assert strategy.evaluate(make_context(["10", "10", "9"])) is None
    assert strategy.evaluate(make_context(["10", "11", "12", "13"])) is None


def test_bullish_crossover_uses_configured_quantity_and_exact_averages() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1.25"))
    )
    proposal = strategy.evaluate(make_context(["10", "10", "9", "12"]))
    assert proposal is not None
    assert proposal.side is OrderSide.BUY
    assert proposal.desired_quantity == Decimal("1.25")
    assert (
        proposal.created_at
        == make_context(["10", "10", "9", "12"]).current_bar.timestamp
    )
    assert "Short SMA (2)=10.5" in proposal.reason
    assert "long SMA (3)=10.33333333333333333333333333" in proposal.reason


def test_bearish_crossover_sells_full_position() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("99"))
    )
    proposal = strategy.evaluate(make_context(["9", "12", "12", "10"], invested=True))
    assert proposal is not None
    assert proposal.side is OrderSide.SELL
    assert proposal.desired_quantity == Decimal("2.5")


def test_position_filter_does_not_delay_or_repeat_crossed_signal() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    )
    assert (
        strategy.evaluate(make_context(["10", "10", "9", "12"], invested=True)) is None
    )
    assert strategy.evaluate(make_context(["10", "9", "12", "13"])) is None
    assert strategy.evaluate(make_context(["9", "12", "12", "10"])) is None
    assert (
        strategy.evaluate(make_context(["12", "12", "10", "9"], invested=True)) is None
    )


def test_current_equality_is_not_a_crossover_but_previous_equality_can_be() -> None:
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(1, 2, Decimal("1"))
    )
    assert strategy.evaluate(make_context(["10", "10", "10"])) is None
    proposal = strategy.evaluate(make_context(["10", "10", "11"]))
    assert proposal is not None and proposal.side is OrderSide.BUY


def test_proposal_ids_are_deterministic_and_include_configuration() -> None:
    context = make_context(["10", "10", "9", "12"], step_index=8)
    first = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1.0"))
    ).evaluate(context)
    equivalent = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1.00"))
    ).evaluate(context)
    different = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("2"))
    ).evaluate(context)
    assert first is not None and equivalent is not None and different is not None
    assert first.proposal_id == equivalent.proposal_id
    assert first.proposal_id != different.proposal_id


def test_evaluation_does_not_mutate_context_positions() -> None:
    context = make_context(["9", "12", "12", "10"], invested=True)
    before = dict(context.positions)
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    )
    strategy.evaluate(context)
    assert isinstance(context.positions, MappingProxyType)
    assert dict(context.positions) == before
