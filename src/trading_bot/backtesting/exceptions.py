"""Expected failures raised by deterministic backtests."""


class BacktestError(Exception):
    """Base class for backtest failures."""


class InvalidBacktestConfigError(BacktestError):
    """Raised when backtest configuration is inconsistent."""


class InsufficientHistoricalDataError(BacktestError):
    """Raised when no bars are available to run a backtest."""


class BacktestCalendarAlignmentError(BacktestError):
    """Raised when bars do not align with expected trading sessions."""


class StrategyContractError(BacktestError):
    """Raised when a strategy violates its deterministic boundary."""


class ActiveOrderError(BacktestError):
    """Raised when a strategy proposes a trade while an order remains active."""


class BacktestExecutionError(BacktestError):
    """Raised when a deterministic next-open fill cannot be completed."""


class BacktestAtomicityError(BacktestError):
    """Raised when run-local execution components cannot be copied safely."""
