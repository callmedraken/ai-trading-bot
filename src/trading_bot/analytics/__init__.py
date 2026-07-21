"""Public API for deterministic performance analytics."""

from trading_bot.analytics.analyzer import PerformanceAnalyzer
from trading_bot.analytics.exceptions import (
    AnalyticsError,
    AnalyticsInputError,
    InconsistentBacktestAuditError,
)
from trading_bot.analytics.models import (
    DrawdownAnalysis,
    DrawdownRecord,
    PerformanceReport,
    TradeRealization,
)

__all__ = [
    "AnalyticsError",
    "AnalyticsInputError",
    "DrawdownAnalysis",
    "DrawdownRecord",
    "InconsistentBacktestAuditError",
    "PerformanceAnalyzer",
    "PerformanceReport",
    "TradeRealization",
]
