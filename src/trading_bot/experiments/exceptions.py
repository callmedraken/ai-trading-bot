"""Expected failures from deterministic historical experiments."""

from uuid import UUID


class HistoricalExperimentError(Exception):
    """Base exception for historical experiment failures."""


class InvalidHistoricalExperimentRequestError(HistoricalExperimentError, ValueError):
    """Raised when shared experiment input is malformed."""


class HistoricalExperimentVariantError(HistoricalExperimentError, ValueError):
    """Raised when one explicit variant is malformed."""


class _VariantFailure(HistoricalExperimentError):
    def __init__(
        self,
        variant_ordinal: int,
        variant_id: UUID,
        variant_name: str,
        stage: str,
        message: str,
    ) -> None:
        self.variant_ordinal = variant_ordinal
        self.variant_id = variant_id
        self.variant_name = variant_name
        self.stage = stage
        super().__init__(message)


class HistoricalExperimentInitializationError(_VariantFailure):
    """Raised when a factory fails or its initialized state is incorrect."""


class HistoricalExperimentIsolationError(_VariantFailure):
    """Raised when a mutable component is reused across variants."""


class HistoricalExperimentExecutionError(_VariantFailure):
    """Raised when one rolling historical variant fails."""


class HistoricalExperimentReconciliationError(HistoricalExperimentError, ValueError):
    """Raised when live execution relationships or immutable inputs disagree."""


class InconsistentHistoricalExperimentResultError(
    HistoricalExperimentError, ValueError
):
    """Raised when a retained experiment run or result is inconsistent."""
