"""Expected failures from deterministic paper portfolio cycles."""


class PaperPortfolioRuntimeError(Exception):
    """Base exception for paper portfolio runtime failures."""


class InvalidPaperPortfolioCycleRequestError(PaperPortfolioRuntimeError, ValueError):
    """Raised when cycle inputs or metadata are malformed."""


class InconsistentPaperPortfolioRuntimeStateError(
    PaperPortfolioRuntimeError, ValueError
):
    """Raised when cycle state does not match the authoritative ledger."""


class PaperPortfolioCycleEngineCopyError(PaperPortfolioRuntimeError):
    """Raised when the runtime engine cannot be copied for an active cycle."""


class PaperPortfolioCycleLedgerCopyError(PaperPortfolioRuntimeError):
    """Raised when the runtime ledger cannot be copied for an active cycle."""


class PaperPortfolioPlanningError(PaperPortfolioRuntimeError):
    """Raised when deterministic rebalance planning fails."""


class PaperPortfolioProposalError(PaperPortfolioRuntimeError):
    """Raised when plan-to-proposal conversion fails."""


class PaperPortfolioRiskError(PaperPortfolioRuntimeError):
    """Raised when collective risk orchestration fails."""


class PaperPortfolioOrderError(PaperPortfolioRuntimeError):
    """Raised when portfolio order construction fails."""


class PaperPortfolioSubmissionError(PaperPortfolioRuntimeError):
    """Raised when local paper submission fails."""


class PaperPortfolioFillGenerationError(PaperPortfolioRuntimeError):
    """Raised when paper fill generation fails."""


class PaperPortfolioFillApplicationError(PaperPortfolioRuntimeError):
    """Raised when atomic fill application fails."""


class InconsistentPaperPortfolioCycleResultError(
    PaperPortfolioRuntimeError, ValueError
):
    """Raised when the complete stage audit chain does not reconcile."""
