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


class HistoricalScenarioGenerationError(PortfolioDomainError):
    """Base exception for deterministic historical scenario generation."""


class InvalidHistoricalScenarioRequestError(
    HistoricalScenarioGenerationError, ValueError
):
    """Raised when a historical scenario request or policy is invalid."""


class HistoricalScenarioChronologyError(HistoricalScenarioGenerationError, ValueError):
    """Raised when historical observations violate temporal requirements."""


class HistoricalScenarioUniverseMismatchError(
    HistoricalScenarioGenerationError, ValueError
):
    """Raised when historical frames do not share one complete ordered universe."""


class HistoricalScenarioPriceError(HistoricalScenarioGenerationError, ValueError):
    """Raised when a historical close price is invalid."""


class HistoricalScenarioProbabilityError(HistoricalScenarioGenerationError, ValueError):
    """Raised when generated scenario probabilities are invalid."""


class HistoricalScenarioReconciliationError(
    HistoricalScenarioGenerationError, ValueError
):
    """Raised when generated domain objects do not reconcile."""


class InconsistentHistoricalScenarioResultError(
    HistoricalScenarioGenerationError, ValueError
):
    """Raised when a historical scenario result is internally inconsistent."""


class InvalidMeanCvarOptimizationRequestError(PortfolioDomainError, ValueError):
    """Raised when a specialized Mean-CVaR request is invalid."""


class InvalidMeanCvarOptimizationResultError(PortfolioDomainError, ValueError):
    """Raised when a specialized Mean-CVaR result is inconsistent."""


class OptimizedTargetAdapterError(PortfolioDomainError):
    """Base exception for optimizer-target certification failures."""


class InvalidOptimizedTargetRequestError(OptimizedTargetAdapterError, ValueError):
    """Raised when an optimizer-target request is malformed."""


class IneligibleOptimizedTargetError(OptimizedTargetAdapterError, ValueError):
    """Raised when an optimizer result cannot supply a certified target."""


class OptimizedTargetStateMismatchError(OptimizedTargetAdapterError, ValueError):
    """Raised when the intended state differs from optimizer inputs."""


class InvalidOptimizedTargetOutputError(OptimizedTargetAdapterError, ValueError):
    """Raised when an optimizer target fails exact structural reconciliation."""


class InconsistentOptimizedTargetResultError(OptimizedTargetAdapterError, ValueError):
    """Raised when a certified target result is internally inconsistent."""
