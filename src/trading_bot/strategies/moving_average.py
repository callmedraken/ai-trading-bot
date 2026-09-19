"""Deterministic closing-price moving-average crossover strategy."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.backtesting import BacktestContext
from trading_bot.domain import OrderSide, TradeProposal
from trading_bot.strategies.exceptions import MovingAverageCrossoverConfigError

_STRATEGY_NAMESPACE = UUID("d3bdd8f2-5506-5e74-b3f8-8e455b67325c")


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


@dataclass(frozen=True, slots=True)
class MovingAverageCrossoverConfig:
    """Validated parameters for one moving-average crossover strategy."""

    short_window: int
    long_window: int
    desired_quantity: Decimal

    def __post_init__(self) -> None:
        for field_name in ("short_window", "long_window"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise MovingAverageCrossoverConfigError(
                    f"{field_name} must be a positive integer"
                )
        if self.long_window <= self.short_window:
            raise MovingAverageCrossoverConfigError(
                "long_window must be greater than short_window"
            )
        if not isinstance(self.desired_quantity, Decimal):
            raise MovingAverageCrossoverConfigError(
                "desired_quantity must be a Decimal"
            )
        if not self.desired_quantity.is_finite() or self.desired_quantity <= 0:
            raise MovingAverageCrossoverConfigError(
                "desired_quantity must be finite and greater than zero"
            )


class MovingAverageCrossoverEvaluationStatus(StrEnum):
    """Deterministic outcome of the crossover arithmetic plus position filter."""

    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NO_CROSSOVER = "NO_CROSSOVER"
    POSITION_FILTERED = "POSITION_FILTERED"
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class MovingAverageCrossoverEvaluation:
    """Pure explanation of the exact arithmetic used by the strategy."""

    status: MovingAverageCrossoverEvaluationStatus
    evaluated_closes: tuple[Decimal, ...]
    previous_short: Decimal | None
    previous_long: Decimal | None
    current_short: Decimal | None
    current_long: Decimal | None
    crossover_side: OrderSide | None
    actionable_side: OrderSide | None
    invested: bool

    def __post_init__(self) -> None:
        if type(self.status) is not MovingAverageCrossoverEvaluationStatus:
            raise TypeError("status must be exact MovingAverageCrossoverEvaluationStatus")
        if type(self.evaluated_closes) is not tuple or any(
            type(value) is not Decimal or not value.is_finite() or value <= 0
            for value in self.evaluated_closes
        ):
            raise ValueError("evaluated_closes must be positive finite Decimals")
        if type(self.invested) is not bool:
            raise TypeError("invested must be an exact bool")
        averages = (
            self.previous_short,
            self.previous_long,
            self.current_short,
            self.current_long,
        )
        if self.status is MovingAverageCrossoverEvaluationStatus.INSUFFICIENT_HISTORY:
            if any(value is not None for value in averages) or any(
                value is not None for value in (self.crossover_side, self.actionable_side)
            ):
                raise ValueError("insufficient history cannot expose crossover values")
            return
        if any(type(value) is not Decimal or not value.is_finite() for value in averages):
            raise ValueError("complete evaluation requires finite Decimal averages")
        if self.status is MovingAverageCrossoverEvaluationStatus.NO_CROSSOVER:
            if self.crossover_side is not None or self.actionable_side is not None:
                raise ValueError("NO_CROSSOVER cannot expose a side")
        elif self.status is MovingAverageCrossoverEvaluationStatus.POSITION_FILTERED:
            if type(self.crossover_side) is not OrderSide or self.actionable_side is not None:
                raise ValueError("POSITION_FILTERED requires only a raw crossover side")
        elif self.status is MovingAverageCrossoverEvaluationStatus.BUY:
            if self.crossover_side is not OrderSide.BUY or self.actionable_side is not OrderSide.BUY:
                raise ValueError("BUY evaluation side mismatch")
        elif self.status is MovingAverageCrossoverEvaluationStatus.SELL:
            if self.crossover_side is not OrderSide.SELL or self.actionable_side is not OrderSide.SELL:
                raise ValueError("SELL evaluation side mismatch")


def evaluate_moving_average_crossover_closes(
    closes: tuple[Decimal, ...],
    config: MovingAverageCrossoverConfig,
    *,
    invested: bool,
) -> MovingAverageCrossoverEvaluation:
    """Explain the exact close-only crossover logic used by the strategy."""

    if type(closes) is not tuple or any(
        type(value) is not Decimal or not value.is_finite() or value <= 0
        for value in closes
    ):
        raise ValueError("closes must be a tuple of positive finite Decimals")
    if not isinstance(config, MovingAverageCrossoverConfig):
        raise TypeError("config must be a MovingAverageCrossoverConfig")
    if type(invested) is not bool:
        raise TypeError("invested must be an exact bool")

    required = config.long_window + 1
    if len(closes) < required:
        return MovingAverageCrossoverEvaluation(
            MovingAverageCrossoverEvaluationStatus.INSUFFICIENT_HISTORY,
            closes,
            None,
            None,
            None,
            None,
            None,
            None,
            invested,
        )

    evaluated = closes[-required:]
    previous_short = _average(evaluated[-config.short_window - 1 : -1])
    previous_long = _average(evaluated[-config.long_window - 1 : -1])
    current_short = _average(evaluated[-config.short_window :])
    current_long = _average(evaluated[-config.long_window :])

    side = None
    if previous_short <= previous_long and current_short > current_long:
        side = OrderSide.BUY
    elif previous_short >= previous_long and current_short < current_long:
        side = OrderSide.SELL

    if side is None:
        status = MovingAverageCrossoverEvaluationStatus.NO_CROSSOVER
        actionable = None
    elif (side is OrderSide.BUY and invested) or (
        side is OrderSide.SELL and not invested
    ):
        status = MovingAverageCrossoverEvaluationStatus.POSITION_FILTERED
        actionable = None
    else:
        status = (
            MovingAverageCrossoverEvaluationStatus.BUY
            if side is OrderSide.BUY
            else MovingAverageCrossoverEvaluationStatus.SELL
        )
        actionable = side

    return MovingAverageCrossoverEvaluation(
        status,
        evaluated,
        previous_short,
        previous_long,
        current_short,
        current_long,
        side,
        actionable,
        invested,
    )


def _average(values: tuple[Decimal, ...]) -> Decimal:
    return sum(values, start=Decimal("0")) / Decimal(len(values))


class MovingAverageCrossoverStrategy:
    """Generate proposals only at genuine consecutive-average crossovers."""

    def __init__(self, config: MovingAverageCrossoverConfig) -> None:
        if not isinstance(config, MovingAverageCrossoverConfig):
            raise TypeError("config must be a MovingAverageCrossoverConfig")
        self._config = config

    @property
    def config(self) -> MovingAverageCrossoverConfig:
        return self._config

    def evaluate(self, context: BacktestContext) -> TradeProposal | None:
        """Evaluate a point-in-time history without retaining portfolio state."""
        if not isinstance(context, BacktestContext):
            raise TypeError("context must be a BacktestContext")
        if len(context.history) < self._config.long_window + 1:
            return None

        closes = tuple(bar.close for bar in context.history)
        symbol = context.current_bar.symbol
        position = context.positions.get(symbol)
        invested = position is not None and position.quantity > 0
        evaluation = evaluate_moving_average_crossover_closes(
            closes,
            self._config,
            invested=invested,
        )
        side = evaluation.actionable_side
        if side is None:
            return None
        current_short = evaluation.current_short
        current_long = evaluation.current_long
        if current_short is None or current_long is None:
            raise RuntimeError("actionable crossover evaluation lacks current averages")

        quantity = (
            self._config.desired_quantity
            if side is OrderSide.BUY
            else position.quantity  # type: ignore[union-attr]
        )
        direction = "above" if side is OrderSide.BUY else "below"
        reason = (
            f"Short SMA ({self._config.short_window})={current_short} crossed "
            f"{direction} long SMA ({self._config.long_window})={current_long}."
        )
        return TradeProposal.create(
            proposal_id=self._proposal_id(context, side),
            symbol=symbol,
            side=side,
            desired_quantity=quantity,
            created_at=context.current_bar.timestamp,
            reason=reason,
        )

    def _proposal_id(self, context: BacktestContext, side: OrderSide) -> UUID:
        identity = ":".join(
            (
                str(context.run_id),
                str(self._config.short_window),
                str(self._config.long_window),
                _canonical_decimal(self._config.desired_quantity),
                str(context.step_index),
                side.value,
            )
        )
        return uuid5(_STRATEGY_NAMESPACE, identity)
