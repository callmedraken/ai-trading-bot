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
