"""Expected failures from deterministic paper portfolio simulations."""

from datetime import datetime
from uuid import UUID

from trading_bot.portfolio.models import OptimizationStatus


class PaperPortfolioSimulationError(Exception):
    """Base exception for paper portfolio simulation failures."""


class InvalidPaperPortfolioSimulationRequestError(
    PaperPortfolioSimulationError, ValueError
):
    """Raised when a simulation request or frame collection is malformed."""


class InvalidPaperPortfolioSimulationFrameError(
    PaperPortfolioSimulationError, ValueError
):
    """Raised when one statically supplied simulation frame is malformed."""


class PaperPortfolioSimulationStateDerivationError(PaperPortfolioSimulationError):
    """Raised when ledger state cannot produce a valid frame portfolio state."""


class PaperPortfolioSimulationCycleError(PaperPortfolioSimulationError):
    """Raised when one atomic runtime cycle fails."""

    def __init__(self, frame_ordinal: int, message: str) -> None:
        self.frame_ordinal = frame_ordinal
        super().__init__(message)


class PaperPortfolioSimulationStateMismatchError(
    PaperPortfolioSimulationError, ValueError
):
    """Raised when runtime state does not match the retained cycle audit."""


class InconsistentPaperPortfolioSimulationResultError(
    PaperPortfolioSimulationError, ValueError
):
    """Raised when an immutable simulation result does not reconcile."""


class OptimizedPaperSimulationError(PaperPortfolioSimulationError):
    """Base exception for optimizer-driven paper simulations."""


class InvalidOptimizedPaperSimulationRequestError(
    OptimizedPaperSimulationError, ValueError
):
    """Raised when an optimized simulation request is malformed."""


class InvalidOptimizedPaperSimulationFrameError(
    OptimizedPaperSimulationError, ValueError
):
    """Raised when an optimized simulation frame is malformed."""


class OptimizedPaperSimulationOptimizationError(OptimizedPaperSimulationError):
    """Raised when one frame cannot produce an optimal portfolio."""

    def __init__(
        self,
        frame_ordinal: int,
        message: str,
        *,
        status: OptimizationStatus | None = None,
        diagnostic_codes: tuple[str, ...] = (),
    ) -> None:
        self.frame_ordinal = frame_ordinal
        self.status = status
        self.diagnostic_codes = diagnostic_codes
        super().__init__(message)


class OptimizedPaperSimulationCertificationError(OptimizedPaperSimulationError):
    """Raised when optimizer target certification fails for one frame."""

    def __init__(self, frame_ordinal: int, message: str) -> None:
        self.frame_ordinal = frame_ordinal
        super().__init__(message)


class InconsistentOptimizedPaperSimulationResultError(
    OptimizedPaperSimulationError, ValueError
):
    """Raised when an optimized simulation audit result does not reconcile."""


class RollingHistoricalSimulationError(PaperPortfolioSimulationError):
    """Base exception for rolling historical optimized simulations."""


class InvalidRollingHistoricalSimulationRequestError(
    RollingHistoricalSimulationError, ValueError
):
    """Raised when a rolling historical request is malformed."""


class RollingHistoricalScheduleError(RollingHistoricalSimulationError, ValueError):
    """Raised when an explicit rebalance schedule is invalid."""


class RollingHistoricalWindowError(RollingHistoricalSimulationError, ValueError):
    """Raised when an exact trailing historical window cannot be constructed."""


class RollingHistoricalScenarioGenerationError(RollingHistoricalSimulationError):
    """Raised when scenario generation fails for one rolling frame."""

    def __init__(
        self, frame_ordinal: int, rebalance_timestamp: datetime, message: str
    ) -> None:
        self.frame_ordinal = frame_ordinal
        self.rebalance_timestamp = rebalance_timestamp
        super().__init__(message)


class RollingHistoricalFrameConstructionError(RollingHistoricalSimulationError):
    """Raised when optimized frame or request construction fails."""


class RollingHistoricalSimulationExecutionError(RollingHistoricalSimulationError):
    """Raised when the supplied optimized simulator fails."""

    def __init__(
        self,
        message: str,
        *,
        frame_ordinal: int | None = None,
        rebalance_timestamp: datetime | None = None,
    ) -> None:
        self.frame_ordinal = frame_ordinal
        self.rebalance_timestamp = rebalance_timestamp
        super().__init__(message)


class RollingHistoricalPerformanceError(RollingHistoricalSimulationError):
    """Raised when post-simulation analytics fails."""

    def __init__(self, simulation_result_id: UUID, message: str) -> None:
        self.simulation_result_id = simulation_result_id
        super().__init__(message)


class RollingHistoricalSimulationReconciliationError(
    RollingHistoricalSimulationError, ValueError
):
    """Raised when prepared, live, or downstream audit state disagrees."""


class InconsistentRollingHistoricalSimulationResultError(
    RollingHistoricalSimulationError, ValueError
):
    """Raised when an immutable rolling result is internally inconsistent."""
