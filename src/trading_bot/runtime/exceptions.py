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


class VerifiedSnapshotPaperCyclePreparationError(Exception):
    """Base class for verified-snapshot paper-cycle preparation failures."""

    def __init__(self, diagnostic: object) -> None:
        self.diagnostic = diagnostic
        detail = getattr(diagnostic, "detail", None)
        super().__init__(
            detail
            if isinstance(detail, str)
            else "verified-snapshot paper-cycle preparation failed"
        )


class InvalidVerifiedSnapshotPaperCyclePreparationRequestError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when a preparation request or one of its values is invalid."""


class VerifiedSnapshotPaperCycleSnapshotError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when verified snapshot evidence cannot be accepted or reconciled."""


class VerifiedSnapshotPaperCycleUniverseError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when account, target, or open-reference universes do not reconcile."""


class VerifiedSnapshotPaperCycleTargetError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when explicit quantity targets cannot form exact planner inputs."""


class VerifiedSnapshotPaperCycleTemporalError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when sessions or caller-supplied timestamps are inconsistent."""


class VerifiedSnapshotPaperCyclePolicyError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when duplicated planner, risk, and fill policies disagree."""


class InconsistentPreparedVerifiedSnapshotPaperCycleError(
    VerifiedSnapshotPaperCyclePreparationError,
    ValueError,
):
    """Raised when an immutable prepared result does not reconcile."""


class VerifiedSnapshotPaperCycleExecutionError(Exception):
    """Base class for prepared verified-snapshot execution failures."""


class InvalidPreparedVerifiedSnapshotPaperCycleError(
    VerifiedSnapshotPaperCycleExecutionError,
    TypeError,
):
    """Raised when execution does not receive an exact prepared result."""


class VerifiedSnapshotPaperCycleInitializationError(
    VerifiedSnapshotPaperCycleExecutionError
):
    """Raised when the fresh private paper ledger cannot be initialized."""


class VerifiedSnapshotPaperCycleRequestReconstructionError(
    VerifiedSnapshotPaperCycleExecutionError
):
    """Raised when exact existing runtime inputs cannot be reconstructed."""


class VerifiedSnapshotPaperCycleRuntimeExecutionError(
    VerifiedSnapshotPaperCycleExecutionError
):
    """Raised when the existing paper runtime cannot complete its one cycle."""


class VerifiedSnapshotPaperCycleApplicationError(
    VerifiedSnapshotPaperCycleRuntimeExecutionError
):
    """Raised when existing atomic fill application fails."""


class VerifiedSnapshotPaperCycleInsufficientCashError(
    VerifiedSnapshotPaperCycleApplicationError
):
    """Raised when asserted fill prices cause atomic insufficient-cash failure."""


class VerifiedSnapshotPaperCycleReconciliationError(
    VerifiedSnapshotPaperCycleExecutionError,
    ValueError,
):
    """Raised when private runtime state and immutable evidence do not reconcile."""


class InconsistentVerifiedSnapshotPaperCycleResultError(
    VerifiedSnapshotPaperCycleReconciliationError
):
    """Raised when an immutable adapter result is internally inconsistent."""


class VerifiedSnapshotPaperCycleReportError(Exception):
    """Base class for canonical cycle-report failures."""


class VerifiedSnapshotPaperCycleReportSyntaxError(
    VerifiedSnapshotPaperCycleReportError, ValueError
):
    """Raised when report bytes are not bounded strict JSON input."""


class VerifiedSnapshotPaperCycleReportSchemaError(
    VerifiedSnapshotPaperCycleReportError, ValueError
):
    """Raised when report JSON violates canonical schema 1."""


class VerifiedSnapshotPaperCycleReportReconciliationError(
    VerifiedSnapshotPaperCycleReportError, ValueError
):
    """Raised when parsed retained models do not reconcile."""


class VerifiedSnapshotPaperCycleReportVerificationError(
    VerifiedSnapshotPaperCycleReportError, ValueError
):
    """Raised when offline verification arguments or evidence are invalid."""


class VerifiedSnapshotPaperCycleReplayError(
    VerifiedSnapshotPaperCycleReportError, ValueError
):
    """Raised when replay access is attempted without a complete PASS."""
