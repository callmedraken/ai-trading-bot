"""Public API for deterministic single-symbol historical backtesting."""

from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.backtesting.exceptions import (
    ActiveOrderError,
    BacktestAtomicityError,
    BacktestCalendarAlignmentError,
    BacktestError,
    BacktestExecutionError,
    InsufficientHistoricalDataError,
    InvalidBacktestConfigError,
    StrategyContractError,
)
from trading_bot.backtesting.models import (
    BacktestConfig,
    BacktestContext,
    BacktestResult,
    BacktestStep,
    BacktestUnexecutedReason,
)
from trading_bot.backtesting.strategy import BacktestStrategy

__all__ = [
    "ActiveOrderError",
    "BacktestAtomicityError",
    "BacktestCalendarAlignmentError",
    "BacktestConfig",
    "BacktestContext",
    "BacktestEngine",
    "BacktestError",
    "BacktestExecutionError",
    "BacktestResult",
    "BacktestStep",
    "BacktestStrategy",
    "BacktestUnexecutedReason",
    "InsufficientHistoricalDataError",
    "InvalidBacktestConfigError",
    "StrategyContractError",
]
