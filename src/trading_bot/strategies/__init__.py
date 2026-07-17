"""Public API for deterministic trading strategies."""

from trading_bot.strategies.exceptions import MovingAverageCrossoverConfigError
from trading_bot.strategies.moving_average import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

__all__ = [
    "MovingAverageCrossoverConfig",
    "MovingAverageCrossoverConfigError",
    "MovingAverageCrossoverStrategy",
]
