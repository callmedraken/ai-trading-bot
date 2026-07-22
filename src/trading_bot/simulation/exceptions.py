"""Expected failures from deterministic paper portfolio simulations."""

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
