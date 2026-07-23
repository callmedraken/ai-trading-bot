"""Public API for deterministic multi-symbol performance analytics."""

from trading_bot.portfolio_analytics.analyzer import PortfolioPerformanceAnalyzer
from trading_bot.portfolio_analytics.exceptions import (
    InconsistentOptimizedSimulationPerformanceResultError,
    InconsistentPortfolioBacktestAuditError,
    InvalidOptimizedSimulationPerformanceRequestError,
    OptimizedSimulationPerformanceError,
    OptimizedSimulationPerformanceReconciliationError,
    OptimizedSimulationValuationError,
    PortfolioAnalyticsError,
    PortfolioAnalyticsInputError,
)
from trading_bot.portfolio_analytics.models import (
    PortfolioExposureRecord,
    PortfolioPerformanceReport,
    SymbolPerformanceSummary,
)
from trading_bot.portfolio_analytics.optimized_simulation import (
    OptimizedSimulationAllocationDrift,
    OptimizedSimulationEquityObservation,
    OptimizedSimulationEquityPhase,
    OptimizedSimulationFramePerformance,
    OptimizedSimulationOptimizationSummary,
    OptimizedSimulationPerformanceAnalyzer,
    OptimizedSimulationPerformanceDiagnostic,
    OptimizedSimulationPerformanceDiagnosticCode,
    OptimizedSimulationPerformanceRequest,
    OptimizedSimulationPerformanceResult,
    OptimizedSimulationValuationBasis,
    OptimizedSimulationValuationPolicy,
)

__all__ = [
    "InconsistentOptimizedSimulationPerformanceResultError",
    "InconsistentPortfolioBacktestAuditError",
    "InvalidOptimizedSimulationPerformanceRequestError",
    "OptimizedSimulationAllocationDrift",
    "OptimizedSimulationEquityObservation",
    "OptimizedSimulationEquityPhase",
    "OptimizedSimulationFramePerformance",
    "OptimizedSimulationOptimizationSummary",
    "OptimizedSimulationPerformanceAnalyzer",
    "OptimizedSimulationPerformanceDiagnostic",
    "OptimizedSimulationPerformanceDiagnosticCode",
    "OptimizedSimulationPerformanceError",
    "OptimizedSimulationPerformanceReconciliationError",
    "OptimizedSimulationPerformanceRequest",
    "OptimizedSimulationPerformanceResult",
    "OptimizedSimulationValuationBasis",
    "OptimizedSimulationValuationError",
    "OptimizedSimulationValuationPolicy",
    "PortfolioAnalyticsError",
    "PortfolioAnalyticsInputError",
    "PortfolioExposureRecord",
    "PortfolioPerformanceAnalyzer",
    "PortfolioPerformanceReport",
    "SymbolPerformanceSummary",
]
