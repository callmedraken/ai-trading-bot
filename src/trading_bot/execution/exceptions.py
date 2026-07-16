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
