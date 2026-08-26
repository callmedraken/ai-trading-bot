"""Expected failures raised by historical market-data providers."""

from enum import StrEnum


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


class DailySnapshotError(Exception):
    """Base class for provider-neutral daily snapshot failures."""


class DailySnapshotValidationError(DailySnapshotError, ValueError):
    """Base class for invalid daily snapshot values."""


class InvalidDailySnapshotRequestError(DailySnapshotValidationError):
    """Raised when a daily snapshot request is invalid."""


class InvalidDailySnapshotCalendarError(DailySnapshotValidationError):
    """Raised when a calendar is absent, unsupported, or inconsistently bound."""


class InvalidDailySnapshotProviderError(DailySnapshotValidationError):
    """Raised when a provider contract or descriptor is invalid."""


class InvalidDailySnapshotResponseError(DailySnapshotValidationError):
    """Raised when a provider response envelope is invalid."""


class InvalidDailySnapshotModelError(DailySnapshotValidationError):
    """Raised when an accepted snapshot model is internally inconsistent."""


class DailySnapshotSerializationError(DailySnapshotError, ValueError):
    """Raised when canonical snapshot JSON cannot be parsed or serialized."""


class DailySnapshotVerificationError(DailySnapshotError, ValueError):
    """Raised when verification arguments are invalid."""


class DailySnapshotReplayError(DailySnapshotError, ValueError):
    """Raised when replay is requested from an unverified snapshot."""


class AlpacaDailySnapshotError(DailySnapshotError):
    """Base class for sanitized Alpaca daily-snapshot failures."""


class AlpacaCredentialError(AlpacaDailySnapshotError, ValueError):
    """Raised when runtime Alpaca credentials are absent or invalid."""


class AlpacaTransportFailureStage(StrEnum):
    """Closed sanitized location of an Alpaca HTTPS transport failure."""

    REQUEST = "REQUEST"
    RESPONSE_START = "RESPONSE_START"
    RESPONSE_METADATA = "RESPONSE_METADATA"
    RESPONSE_BODY = "RESPONSE_BODY"
    UNKNOWN = "UNKNOWN"


class AlpacaResponseMetadataFailureReason(StrEnum):
    """Closed sanitized reason for response-metadata transport failure."""

    ACQUISITION = "ACQUISITION"
    MALFORMED = "MALFORMED"
    DUPLICATE_RELEVANT_HEADER = "DUPLICATE_RELEVANT_HEADER"
    UNSUPPORTED_CONTENT_ENCODING = "UNSUPPORTED_CONTENT_ENCODING"
    UNSUPPORTED_TRANSFER_ENCODING = "UNSUPPORTED_TRANSFER_ENCODING"
    TRANSFER_LENGTH_CONFLICT = "TRANSFER_LENGTH_CONFLICT"
    INVALID_CONTENT_LENGTH = "INVALID_CONTENT_LENGTH"
    INVALID_REQUEST_ID = "INVALID_REQUEST_ID"
    MISSING_CONTENT_TYPE = "MISSING_CONTENT_TYPE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    UNSUPPORTED_CHARSET = "UNSUPPORTED_CHARSET"
    INVALID_CONTENT_TYPE_PARAMETERS = "INVALID_CONTENT_TYPE_PARAMETERS"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    GENERIC = "GENERIC"


class AlpacaTransportError(AlpacaDailySnapshotError):
    """Raised when the one permitted HTTPS attempt cannot complete safely."""

    def __init__(
        self,
        stage: AlpacaTransportFailureStage
        | object = AlpacaTransportFailureStage.UNKNOWN,
        *,
        metadata_reason: AlpacaResponseMetadataFailureReason | object = None,
    ) -> None:
        # Legacy callers may still pass a sanitized message. Discard all such
        # caller-provided material rather than retaining it in args/repr.
        if type(stage) is not AlpacaTransportFailureStage:
            stage = AlpacaTransportFailureStage.UNKNOWN
        if stage is AlpacaTransportFailureStage.RESPONSE_METADATA:
            if type(metadata_reason) is not AlpacaResponseMetadataFailureReason:
                metadata_reason = AlpacaResponseMetadataFailureReason.GENERIC
        else:
            metadata_reason = None
        self.stage = stage
        self.metadata_reason = metadata_reason
        message = f"Alpaca HTTPS transport failed at stage {stage.value}"
        if metadata_reason is not None:
            message += f" ({metadata_reason.value})"
        super().__init__(message)


class AlpacaHttpStatusError(AlpacaDailySnapshotError):
    """Raised for a sanitized non-200 Alpaca response."""

    def __init__(
        self,
        status: int,
        *,
        request_id: str | None = None,
        provider_code: int | None = None,
    ) -> None:
        self.status = status
        self.request_id = request_id
        self.provider_code = provider_code
        message = f"Alpaca market-data request failed with HTTP status {status}"
        if provider_code is not None:
            message += f" and provider code {provider_code}"
        if request_id is not None:
            message += f" (request ID {request_id})"
        super().__init__(message)


class AlpacaResponseError(AlpacaDailySnapshotError, ValueError):
    """Raised when a successful Alpaca entity violates the fixed schema."""
