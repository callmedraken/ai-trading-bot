"""Exceptions raised by deterministic performance analytics."""


class AnalyticsError(Exception):
    """Base exception for performance analytics."""


class AnalyticsInputError(AnalyticsError, TypeError):
    """Raised when the analyzer receives an unsupported input."""


class InconsistentBacktestAuditError(AnalyticsError, ValueError):
    """Raised when immutable backtest audit collections disagree."""
