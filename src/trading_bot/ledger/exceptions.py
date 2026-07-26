"""Expected accounting failures raised by the paper ledger."""


class LedgerError(Exception):
    """Base class for expected ledger failures."""


class InvalidPaperLedgerInitializationError(LedgerError, ValueError):
    """Raised when explicit opening-account state is invalid."""


class InsufficientCashError(LedgerError):
    """Raised when a purchase would make cash negative."""


class PositionNotFoundError(LedgerError):
    """Raised when attempting to sell a position that is not owned."""


class InsufficientPositionError(LedgerError):
    """Raised when attempting to sell more than the owned quantity."""


class DuplicateFillError(LedgerError):
    """Raised when a fill identifier has already been applied."""


class PriceNotAvailableError(LedgerError):
    """Raised when an open position has no valid valuation price."""
