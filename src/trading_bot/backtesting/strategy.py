"""Look-ahead-safe strategy callback contract."""

from typing import Protocol

from trading_bot.backtesting.models import BacktestContext
from trading_bot.domain import TradeProposal


class BacktestStrategy(Protocol):
    """Return at most one proposal from the currently visible context."""

    def evaluate(self, context: BacktestContext) -> TradeProposal | None: ...
