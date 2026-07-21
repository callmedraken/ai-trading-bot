"""Exceptions for immutable portfolio-domain contracts."""


class PortfolioDomainError(Exception):
    """Base exception for portfolio-domain validation."""


class InvalidPortfolioStateError(PortfolioDomainError, ValueError):
    """Raised when a current portfolio state is malformed or inconsistent."""


class InvalidTargetPortfolioError(PortfolioDomainError, ValueError):
    """Raised when a target portfolio is structurally invalid."""


class InvalidPortfolioConstraintsError(PortfolioDomainError, ValueError):
    """Raised when a portfolio constraint model is malformed."""


class PortfolioConstraintViolationError(PortfolioDomainError, ValueError):
    """Raised when a valid target violates valid portfolio constraints."""


class InvalidOptimizationRequestError(PortfolioDomainError, ValueError):
    """Raised when an optimization request is malformed."""


class InvalidOptimizationResultError(PortfolioDomainError, ValueError):
    """Raised when an optimization result is internally inconsistent."""


class PortfolioUniverseMismatchError(PortfolioDomainError, ValueError):
    """Raised when two ordered symbol universes do not match exactly."""


class InvalidReturnScenarioError(PortfolioDomainError, ValueError):
    """Raised when one return-scenario row is malformed."""


class InvalidReturnScenarioSetError(PortfolioDomainError, ValueError):
    """Raised when a return-scenario set is malformed or inconsistent."""


class ScenarioUniverseMismatchError(PortfolioDomainError, ValueError):
    """Raised when scenario symbol membership or ordering does not match."""


class ScenarioCompatibilityError(PortfolioDomainError, ValueError):
    """Raised when scenario time or forecast horizon does not match."""
