"""Exceptions raised by deterministic portfolio performance analytics."""


class PortfolioAnalyticsError(Exception):
    """Base exception for portfolio performance analytics."""


class PortfolioAnalyticsInputError(PortfolioAnalyticsError, TypeError):
    """Raised when an analyzer receives an unsupported input."""


class InconsistentPortfolioBacktestAuditError(PortfolioAnalyticsError, ValueError):
    """Raised when immutable portfolio backtest audit records disagree."""
