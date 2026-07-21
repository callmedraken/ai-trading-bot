"""Expected failures raised by the broker-independent order engine."""


class OrderEngineError(Exception):
    """Base class for expected order-engine failures."""


class InvalidRiskDecisionError(OrderEngineError):
    """Raised when a risk decision cannot create an order."""


class OrderNotFoundError(OrderEngineError):
    """Raised when an order identifier is not managed by the engine."""


class InvalidOrderTransitionError(OrderEngineError):
    """Raised when an order cannot make the requested state transition."""


class DuplicateOrderError(OrderEngineError):
    """Raised when an order identifier is already managed."""


class DuplicateEventError(OrderEngineError):
    """Raised when an event identifier has already been recorded."""


class DuplicateFillError(OrderEngineError):
    """Raised when a fill identifier has already been accepted globally."""


class FillMismatchError(OrderEngineError):
    """Raised when fill identity data does not match its managed order."""


class OverfillError(OrderEngineError):
    """Raised when a fill exceeds the order's remaining quantity."""


class InvalidEventTimeError(OrderEngineError):
    """Raised when lifecycle chronology is inconsistent."""


class PortfolioOrderOrchestrationError(Exception):
    """Base exception for atomic portfolio order construction."""


class InvalidPortfolioOrderBatchRequestError(
    PortfolioOrderOrchestrationError, ValueError
):
    """Raised when an order-orchestration request is malformed."""


class InconsistentPortfolioOrderSourceError(
    PortfolioOrderOrchestrationError, ValueError
):
    """Raised when a collective-risk source is inconsistent."""


class PortfolioOrderEngineCopyError(PortfolioOrderOrchestrationError):
    """Raised when the authoritative engine cannot be copied safely."""


class PortfolioOrderCreationError(PortfolioOrderOrchestrationError):
    """Raised when shadow-engine order construction fails."""


class InconsistentPortfolioOrderBatchResultError(
    PortfolioOrderOrchestrationError, ValueError
):
    """Raised when created orders, events, or result identity do not reconcile."""


class PaperSubmissionOrchestrationError(Exception):
    """Base exception for deterministic paper-order submission."""


class InvalidPaperSubmissionBatchRequestError(
    PaperSubmissionOrchestrationError, ValueError
):
    """Raised when a paper-submission request is malformed."""


class InconsistentPaperSubmissionSourceError(
    PaperSubmissionOrchestrationError, ValueError
):
    """Raised when source orders do not match authoritative engine state."""


class PaperSubmissionEventCollisionError(PaperSubmissionOrchestrationError):
    """Raised when a deterministic submitted-event ID is unavailable."""


class PaperSubmissionEngineCopyError(PaperSubmissionOrchestrationError):
    """Raised when the authoritative engine cannot be copied safely."""


class PaperOrderSubmissionError(PaperSubmissionOrchestrationError):
    """Raised when shadow-engine submission fails."""


class InconsistentPaperSubmissionBatchResultError(
    PaperSubmissionOrchestrationError, ValueError
):
    """Raised when submitted shadow state or result output does not reconcile."""


class PaperFillGenerationError(Exception):
    """Base exception for deterministic paper-fill generation."""


class InvalidPaperFillBatchRequestError(PaperFillGenerationError, ValueError):
    """Raised when paper-fill inputs are malformed."""


class InconsistentPaperFillSourceError(PaperFillGenerationError, ValueError):
    """Raised when a submission result is not eligible for fill generation."""


class PaperFillIdentityError(PaperFillGenerationError):
    """Raised when generated fill identities are not unique."""


class PaperFillCreationError(PaperFillGenerationError):
    """Raised when an immutable fill candidate cannot be constructed."""


class InconsistentPaperFillBatchResultError(PaperFillGenerationError, ValueError):
    """Raised when generated evaluations or result identity do not reconcile."""
