"""Expected failures from deterministic paper portfolio simulations."""


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
