"""Structural protocol for future portfolio optimizer implementations."""

from typing import Protocol

from trading_bot.portfolio.models import (
    PortfolioOptimizationRequest,
    PortfolioOptimizationResult,
)


class PortfolioOptimizer(Protocol):
    """Solver-independent optimizer boundary."""

    def optimize(
        self, request: PortfolioOptimizationRequest
    ) -> PortfolioOptimizationResult: ...
