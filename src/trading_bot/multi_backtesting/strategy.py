"""Point-in-time multi-symbol strategy protocol."""

from typing import Protocol

from trading_bot.domain import TradeProposal
from trading_bot.multi_backtesting.models import MultiSymbolStrategyContext


class MultiSymbolBacktestStrategy(Protocol):
    def evaluate(
        self, context: MultiSymbolStrategyContext
    ) -> tuple[TradeProposal, ...]: ...
