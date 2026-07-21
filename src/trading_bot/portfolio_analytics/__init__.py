"""Public API for deterministic multi-symbol performance analytics."""

from trading_bot.portfolio_analytics.analyzer import PortfolioPerformanceAnalyzer
from trading_bot.portfolio_analytics.exceptions import (
    InconsistentPortfolioBacktestAuditError,
    PortfolioAnalyticsError,
    PortfolioAnalyticsInputError,
)
from trading_bot.portfolio_analytics.models import (
    PortfolioExposureRecord,
    PortfolioPerformanceReport,
    SymbolPerformanceSummary,
)

__all__ = [
    "InconsistentPortfolioBacktestAuditError",
    "PortfolioAnalyticsError",
    "PortfolioAnalyticsInputError",
    "PortfolioExposureRecord",
    "PortfolioPerformanceAnalyzer",
    "PortfolioPerformanceReport",
    "SymbolPerformanceSummary",
]
