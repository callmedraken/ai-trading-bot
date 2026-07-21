"""Public deterministic multi-symbol backtesting API."""

from trading_bot.multi_backtesting.engine import MultiSymbolBacktestEngine
from trading_bot.multi_backtesting.exceptions import (
    IncompleteMarketFrameError,
    InvalidMultiSymbolBacktestConfigError,
    MultiSymbolBacktestAtomicityError,
    MultiSymbolBacktestError,
    MultiSymbolBacktestExecutionError,
    MultiSymbolStrategyContractError,
)
from trading_bot.multi_backtesting.models import (
    MultiSymbolBacktestConfig,
    MultiSymbolBacktestResult,
    MultiSymbolBacktestStep,
    MultiSymbolStrategyContext,
    MultiSymbolUnexecutedReason,
    UnexecutedProposal,
)
from trading_bot.multi_backtesting.strategy import MultiSymbolBacktestStrategy

__all__ = [
    "IncompleteMarketFrameError",
    "InvalidMultiSymbolBacktestConfigError",
    "MultiSymbolBacktestAtomicityError",
    "MultiSymbolBacktestConfig",
    "MultiSymbolBacktestEngine",
    "MultiSymbolBacktestError",
    "MultiSymbolBacktestExecutionError",
    "MultiSymbolBacktestResult",
    "MultiSymbolBacktestStep",
    "MultiSymbolBacktestStrategy",
    "MultiSymbolStrategyContext",
    "MultiSymbolStrategyContractError",
    "MultiSymbolUnexecutedReason",
    "UnexecutedProposal",
]
