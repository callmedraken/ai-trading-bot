from datetime import UTC, date, datetime
from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_UP,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
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
    MovingAverageCrossoverEvaluationStatus,
    MovingAverageCrossoverStrategy,
    evaluate_moving_average_crossover_closes,
)
from trading_bot.strategies import moving_average as moving_average_module

SYMBOL = Symbol("MATEST")
RUN_ID = UUID("11111111-2222-3333-4444-555555555555")
GOLDEN_PROPOSAL_ID = UUID("f596497b-11fd-5213-9ccb-9960a4b10ec1")
GOLDEN_REASON = (
    "Short SMA (2)=10.5 crossed above long SMA (3)=10.33333333333333333333333333."
)
AMBIENT_CONTEXTS = (
    pytest.param(Context(prec=28, rounding=ROUND_HALF_EVEN), id="historical-default"),
    pytest.param(Context(prec=6, rounding=ROUND_DOWN), id="low-precision-down"),
    pytest.param(Context(prec=50, rounding=ROUND_UP), id="high-precision-up"),
)


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


def test_decimal_subclass_configuration_remains_accepted() -> None:
    class CompatibleDecimal(Decimal):
        pass

    quantity = CompatibleDecimal("1.00")
    config = MovingAverageCrossoverConfig(2, 3, quantity)
    proposal = MovingAverageCrossoverStrategy(config).evaluate(
        make_context(["10", "10", "9", "12"])
    )
    plain = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    ).evaluate(make_context(["10", "10", "9", "12"]))

    assert config.desired_quantity is quantity
    assert proposal is not None and plain is not None
    assert proposal.desired_quantity is quantity
    assert proposal.proposal_id == plain.proposal_id


def test_strategy_decimal_context_freezes_historical_python_defaults() -> None:
    context = moving_average_module._STRATEGY_DECIMAL_CONTEXT

    assert context.prec == 28
    assert context.rounding == ROUND_HALF_EVEN
    assert context.Emin == -999999
    assert context.Emax == 999999
    assert context.capitals == 1
    assert context.clamp == 0
    assert {signal for signal, trapped in context.traps.items() if trapped} == {
        InvalidOperation,
        DivisionByZero,
        Overflow,
    }


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


@pytest.mark.parametrize("ambient_context", AMBIENT_CONTEXTS)
def test_golden_proposal_is_ambient_decimal_context_independent(
    ambient_context: Context,
) -> None:
    context = make_context(["10", "10", "9", "12"])
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1.23456789"))
    )

    with localcontext(ambient_context):
        proposal = strategy.evaluate(context)

    assert proposal is not None
    assert proposal.proposal_id == GOLDEN_PROPOSAL_ID
    assert proposal.reason == GOLDEN_REASON
    assert proposal.side is OrderSide.BUY
    assert proposal.desired_quantity == Decimal("1.23456789")


@pytest.mark.parametrize("ambient_context", AMBIENT_CONTEXTS)
def test_o4_six_session_vector_is_ambient_decimal_context_independent(
    ambient_context: Context,
) -> None:
    closes = tuple(
        Decimal(value)
        for value in ("764.29", "760.88", "757.39", "754.05", "762.6", "761.69")
    )

    with localcontext(ambient_context):
        evaluation = evaluate_moving_average_crossover_closes(
            closes,
            MovingAverageCrossoverConfig(3, 5, Decimal("1")),
            invested=False,
        )

    assert evaluation.previous_short == Decimal("758.0133333333333333333333333")
    assert evaluation.previous_long == Decimal("759.842")
    assert evaluation.current_short == Decimal("759.4466666666666666666666667")
    assert evaluation.current_long == Decimal("759.322")
    assert evaluation.crossover_side is OrderSide.BUY
    assert evaluation.actionable_side is OrderSide.BUY
    assert evaluation.status is MovingAverageCrossoverEvaluationStatus.BUY


def test_evaluation_does_not_mutate_context_positions() -> None:
    context = make_context(["9", "12", "12", "10"], invested=True)
    before = dict(context.positions)
    strategy = MovingAverageCrossoverStrategy(
        MovingAverageCrossoverConfig(2, 3, Decimal("1"))
    )
    strategy.evaluate(context)
    assert isinstance(context.positions, MappingProxyType)
    assert dict(context.positions) == before


def test_close_explanation_matches_bullish_strategy_arithmetic() -> None:
    evaluation = evaluate_moving_average_crossover_closes(
        (
            Decimal("10"),
            Decimal("10"),
            Decimal("9"),
            Decimal("12"),
        ),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
        invested=False,
    )

    assert evaluation.status is MovingAverageCrossoverEvaluationStatus.BUY
    assert evaluation.evaluated_closes == (
        Decimal("10"),
        Decimal("10"),
        Decimal("9"),
        Decimal("12"),
    )
    assert evaluation.previous_short == Decimal("9.5")
    assert evaluation.previous_long == Decimal("9.666666666666666666666666667")
    assert evaluation.current_short == Decimal("10.5")
    assert evaluation.current_long == Decimal("10.33333333333333333333333333")
    assert evaluation.crossover_side is OrderSide.BUY
    assert evaluation.actionable_side is OrderSide.BUY


def test_close_explanation_reports_position_filter_without_delaying_signal() -> None:
    evaluation = evaluate_moving_average_crossover_closes(
        (
            Decimal("10"),
            Decimal("10"),
            Decimal("9"),
            Decimal("12"),
        ),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
        invested=True,
    )

    assert evaluation.status is MovingAverageCrossoverEvaluationStatus.POSITION_FILTERED
    assert evaluation.crossover_side is OrderSide.BUY
    assert evaluation.actionable_side is None


def test_close_explanation_reports_incomplete_history_without_averages() -> None:
    evaluation = evaluate_moving_average_crossover_closes(
        (Decimal("10"), Decimal("11"), Decimal("12")),
        MovingAverageCrossoverConfig(3, 5, Decimal("1")),
        invested=False,
    )

    assert (
        evaluation.status is MovingAverageCrossoverEvaluationStatus.INSUFFICIENT_HISTORY
    )
    assert evaluation.evaluated_closes == (
        Decimal("10"),
        Decimal("11"),
        Decimal("12"),
    )
    assert evaluation.previous_short is None
    assert evaluation.previous_long is None
    assert evaluation.current_short is None
    assert evaluation.current_long is None
    assert evaluation.crossover_side is None
    assert evaluation.actionable_side is None


def test_close_explanation_uses_only_latest_required_window() -> None:
    evaluation = evaluate_moving_average_crossover_closes(
        (
            Decimal("999"),
            Decimal("10"),
            Decimal("10"),
            Decimal("9"),
            Decimal("12"),
        ),
        MovingAverageCrossoverConfig(2, 3, Decimal("1")),
        invested=False,
    )

    assert evaluation.evaluated_closes == (
        Decimal("10"),
        Decimal("10"),
        Decimal("9"),
        Decimal("12"),
    )
    assert evaluation.status is MovingAverageCrossoverEvaluationStatus.BUY
