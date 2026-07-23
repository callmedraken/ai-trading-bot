"""Exceptions raised by deterministic portfolio performance analytics."""


class PortfolioAnalyticsError(Exception):
    """Base exception for portfolio performance analytics."""


class PortfolioAnalyticsInputError(PortfolioAnalyticsError, TypeError):
    """Raised when an analyzer receives an unsupported input."""


class InconsistentPortfolioBacktestAuditError(PortfolioAnalyticsError, ValueError):
    """Raised when immutable portfolio backtest audit records disagree."""


class OptimizedSimulationPerformanceError(PortfolioAnalyticsError):
    """Base exception for optimized-simulation performance analytics."""


class InvalidOptimizedSimulationPerformanceRequestError(
    OptimizedSimulationPerformanceError, ValueError
):
    """Raised when an analytics request or valuation policy is malformed."""


class OptimizedSimulationValuationError(
    OptimizedSimulationPerformanceError, ValueError
):
    """Raised when retained prices cannot produce a valid valuation."""


class OptimizedSimulationPerformanceReconciliationError(
    OptimizedSimulationPerformanceError, ValueError
):
    """Raised when immutable simulation audit records do not reconcile."""


class InconsistentOptimizedSimulationPerformanceResultError(
    OptimizedSimulationPerformanceError, ValueError
):
    """Raised when a constructed analytics result is internally inconsistent."""
