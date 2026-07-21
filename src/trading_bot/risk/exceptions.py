"""Exceptions for deterministic collective risk orchestration."""


class PortfolioRiskOrchestrationError(Exception):
    """Base exception for collective risk orchestration."""


class InvalidPortfolioRiskBatchRequestError(
    PortfolioRiskOrchestrationError, ValueError
):
    """Raised when a batch request is malformed or inconsistent."""


class PortfolioRiskDecisionError(PortfolioRiskOrchestrationError):
    """Raised when RiskManager returns an inconsistent decision."""


class PortfolioRiskReservationError(PortfolioRiskOrchestrationError, ArithmeticError):
    """Raised when provisional reservation arithmetic is invalid."""


class InconsistentPortfolioRiskBatchResultError(
    PortfolioRiskOrchestrationError, ValueError
):
    """Raised when an immutable batch result does not reconcile."""
