"""Expected failures raised by historical market-data providers."""


class HistoricalDataError(Exception):
    """Base class for historical market-data failures."""


class HistoricalDataValidationError(HistoricalDataError):
    """Base class for invalid requests or results."""


class InvalidHistoricalDataRequestError(HistoricalDataValidationError):
    """Raised when a historical-data request is invalid."""


class InvalidHistoricalDataResultError(HistoricalDataValidationError):
    """Raised when a historical-data result violates its request."""


class InvalidMultiSymbolHistoricalDataRequestError(HistoricalDataValidationError):
    """Raised when a multi-symbol request is invalid."""


class InvalidMultiSymbolHistoricalDataResultError(HistoricalDataValidationError):
    """Raised when aligned multi-symbol data violates its request."""


class DuplicateRequestedSymbolError(HistoricalDataValidationError):
    """Raised when a requested universe repeats a symbol."""


class EmptyAlignedHistoricalDataError(HistoricalDataValidationError):
    """Raised when alignment produces no timestamp frames."""


class DuplicateBarTimestampError(HistoricalDataValidationError):
    """Raised when more than one bar has the same timestamp."""


class HistoricalDataNotFoundError(HistoricalDataError):
    """Raised when a requested local data source does not exist."""


class InconsistentProviderResultError(HistoricalDataError):
    """Raised when a constituent provider returns an inconsistent result."""


class UnsupportedTimeframeError(HistoricalDataError):
    """Raised when a provider cannot serve the requested timeframe."""


class UnsupportedAdjustmentError(HistoricalDataError):
    """Raised when a provider cannot serve the requested adjustment."""


class CSVSchemaError(HistoricalDataError):
    """Raised when a CSV file does not have the required structure."""


class CSVRowError(HistoricalDataError):
    """Raised when a CSV row cannot be parsed into a valid bar."""
