"""Public API for deterministic trading strategies."""

from trading_bot.strategies.exceptions import MovingAverageCrossoverConfigError
from trading_bot.strategies.moving_average import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverEvaluation,
    MovingAverageCrossoverEvaluationStatus,
    MovingAverageCrossoverStrategy,
    evaluate_moving_average_crossover_closes,
)

__all__ = [
    "MovingAverageCrossoverConfig",
    "MovingAverageCrossoverConfigError",
    "MovingAverageCrossoverEvaluation",
    "MovingAverageCrossoverEvaluationStatus",
    "MovingAverageCrossoverStrategy",
    "evaluate_moving_average_crossover_closes",
]
