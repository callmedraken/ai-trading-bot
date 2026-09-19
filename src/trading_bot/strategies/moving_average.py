"""Deterministic closing-price moving-average crossover strategy."""

from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from uuid import UUID, uuid5

from trading_bot.backtesting import BacktestContext
from trading_bot.domain import OrderSide, TradeProposal
from trading_bot.strategies.exceptions import MovingAverageCrossoverConfigError

_STRATEGY_NAMESPACE = UUID("d3bdd8f2-5506-5e74-b3f8-8e455b67325c")
_STRATEGY_DECIMAL_CONTEXT = Context(
    prec=28,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)


def _canonical_decimal(value: Decimal) -> str:
    with localcontext(_STRATEGY_DECIMAL_CONTEXT):
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
        previous_short = self._average(closes[-self._config.short_window - 1 : -1])
        previous_long = self._average(closes[-self._config.long_window - 1 : -1])
        current_short = self._average(closes[-self._config.short_window :])
        current_long = self._average(closes[-self._config.long_window :])

        side = None
        if previous_short <= previous_long and current_short > current_long:
            side = OrderSide.BUY
        elif previous_short >= previous_long and current_short < current_long:
            side = OrderSide.SELL
        if side is None:
            return None

        symbol = context.current_bar.symbol
        position = context.positions.get(symbol)
        invested = position is not None and position.quantity > 0
        if (side is OrderSide.BUY and invested) or (
            side is OrderSide.SELL and not invested
        ):
            return None

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

    @staticmethod
    def _average(values: tuple[Decimal, ...]) -> Decimal:
        with localcontext(_STRATEGY_DECIMAL_CONTEXT):
            return sum(values, start=Decimal("0")) / Decimal(len(values))

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
