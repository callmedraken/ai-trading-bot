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


class HistoricalExperimentComparisonError(HistoricalExperimentError):
    """Base exception for explicit historical experiment comparisons."""


class InvalidHistoricalExperimentRankingPolicyError(
    HistoricalExperimentComparisonError, ValueError
):
    """Raised when an explicit ranking policy is malformed."""


class HistoricalExperimentMetricError(HistoricalExperimentComparisonError, ValueError):
    """Raised when a selected comparison metric is invalid."""


class HistoricalExperimentRankingError(HistoricalExperimentComparisonError):
    """Raised when a deterministic total ordering cannot be established."""


class HistoricalExperimentComparisonReconciliationError(
    HistoricalExperimentComparisonError, ValueError
):
    """Raised when locally generated ranked records do not reconcile."""


class InconsistentHistoricalExperimentComparisonResultError(
    HistoricalExperimentComparisonError, ValueError
):
    """Raised when a retained comparison result is inconsistent."""


class HistoricalExperimentGridError(HistoricalExperimentError):
    """Base exception for explicit historical experiment grids."""


class InvalidHistoricalExperimentGridSpecificationError(
    HistoricalExperimentGridError, ValueError
):
    """Raised when a grid specification is malformed."""


class HistoricalExperimentGridAxisError(HistoricalExperimentGridError, ValueError):
    """Raised when grid axis structure is malformed or ambiguous."""


class HistoricalExperimentGridSizeError(HistoricalExperimentGridError, ValueError):
    """Raised when a grid exceeds its explicit caller limit."""


class HistoricalExperimentGridValueError(HistoricalExperimentGridError, ValueError):
    """Raised when an explicit axis value is invalid."""


class HistoricalExperimentGridVariantError(HistoricalExperimentGridError, ValueError):
    """Raised when one explicit combination cannot produce a unique variant."""

    def __init__(
        self,
        message: str,
        *,
        ordinal: int | None = None,
        assignments: tuple = (),
        parameter=None,  # type: ignore[no-untyped-def]
        cause: BaseException | None = None,
    ) -> None:
        self.ordinal = ordinal
        self.assignments = assignments
        self.parameter = parameter
        self.cause = cause
        super().__init__(message)


class HistoricalExperimentGridReconciliationError(
    HistoricalExperimentGridError, ValueError
):
    """Raised when locally generated grid rows do not reconcile."""


class InconsistentHistoricalExperimentGridResultError(
    HistoricalExperimentGridError, ValueError
):
    """Raised when a retained grid result is inconsistent."""
