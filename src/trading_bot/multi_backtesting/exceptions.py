"""Failures raised by deterministic multi-symbol backtests."""

from trading_bot.backtesting import BacktestError


class MultiSymbolBacktestError(BacktestError):
    """Base exception for multi-symbol backtesting."""


class InvalidMultiSymbolBacktestConfigError(MultiSymbolBacktestError):
    """Raised when multi-symbol backtest configuration is invalid."""


class IncompleteMarketFrameError(MultiSymbolBacktestError):
    """Raised when any input frame lacks a requested symbol."""


class MultiSymbolStrategyContractError(MultiSymbolBacktestError):
    """Raised when a strategy violates its point-in-time contract."""


class MultiSymbolBacktestExecutionError(MultiSymbolBacktestError):
    """Raised when an opening fill batch cannot complete."""


class MultiSymbolBacktestAtomicityError(MultiSymbolBacktestError):
    """Raised when run-local components cannot be copied safely."""
