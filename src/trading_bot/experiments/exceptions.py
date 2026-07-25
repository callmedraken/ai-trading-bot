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


class HistoricalExperimentReportError(HistoricalExperimentError):
    """Base exception for compact historical experiment reports."""


class InvalidHistoricalExperimentReportInputError(
    HistoricalExperimentReportError, ValueError
):
    """Raised when compact-report source input is malformed."""


class HistoricalExperimentReportGridError(HistoricalExperimentReportError, ValueError):
    """Raised when supplied grid provenance is unrelated or inconsistent."""


class HistoricalExperimentReportRankingError(
    HistoricalExperimentReportError, ValueError
):
    """Raised when supplied ranking provenance is unrelated or inconsistent."""


class HistoricalExperimentReportMetricError(
    HistoricalExperimentReportError, ValueError
):
    """Raised when projected metrics or comparison values are malformed."""


class HistoricalExperimentReportReconciliationError(
    HistoricalExperimentReportError, ValueError
):
    """Raised when locally projected report rows do not reconcile."""


class InconsistentHistoricalExperimentReportError(
    HistoricalExperimentReportError, ValueError
):
    """Raised when a retained compact report is internally inconsistent."""


class HistoricalExperimentPairwiseError(HistoricalExperimentError):
    """Base exception for deterministic pairwise experiment analysis."""


class InvalidHistoricalExperimentPairwisePolicyError(
    HistoricalExperimentPairwiseError, ValueError
):
    """Raised when a pairwise comparison policy is malformed."""


class HistoricalExperimentPairwiseReportError(
    HistoricalExperimentPairwiseError, ValueError
):
    """Raised when a compact source report cannot support pairwise analysis."""


class HistoricalExperimentPairwiseMetricError(
    HistoricalExperimentPairwiseError, ValueError
):
    """Raised when a selected pairwise metric value is malformed."""


class HistoricalExperimentPairwiseArithmeticError(HistoricalExperimentPairwiseError):
    """Raised when exact pairwise arithmetic cannot be completed."""


class HistoricalExperimentPairwiseReconciliationError(
    HistoricalExperimentPairwiseError, ValueError
):
    """Raised when locally generated pairwise records do not reconcile."""


class InconsistentHistoricalExperimentPairwiseResultError(
    HistoricalExperimentPairwiseError, ValueError
):
    """Raised when a retained pairwise result is internally inconsistent."""


class HistoricalExperimentParetoError(HistoricalExperimentError):
    """Base exception for deterministic Pareto experiment analysis."""


class InvalidHistoricalExperimentParetoPolicyError(
    HistoricalExperimentParetoError, ValueError
):
    """Raised when a Pareto policy is malformed."""


class HistoricalExperimentParetoReportError(
    HistoricalExperimentParetoError, ValueError
):
    """Raised when a compact source report cannot support Pareto analysis."""


class HistoricalExperimentParetoMetricError(
    HistoricalExperimentParetoError, ValueError
):
    """Raised when a selected Pareto metric value is malformed."""


class HistoricalExperimentParetoReconciliationError(
    HistoricalExperimentParetoError, ValueError
):
    """Raised when locally generated Pareto relationships do not reconcile."""


class InconsistentHistoricalExperimentParetoResultError(
    HistoricalExperimentParetoError, ValueError
):
    """Raised when a retained Pareto result is internally inconsistent."""


class HistoricalExperimentWalkForwardError(HistoricalExperimentError):
    """Base exception for walk-forward experiment evaluation."""


class InvalidHistoricalExperimentWalkForwardRequestError(
    HistoricalExperimentWalkForwardError, ValueError
):
    """Raised when a walk-forward request or policy is malformed."""


class HistoricalExperimentWalkForwardFoldError(HistoricalExperimentWalkForwardError):
    """Raised when one fold fails at a known execution stage."""

    def __init__(
        self,
        fold_ordinal: int,
        fold_id: UUID,
        stage: str,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        self.fold_ordinal = fold_ordinal
        self.fold_id = fold_id
        self.stage = stage
        self.cause = cause
        super().__init__(message)


class HistoricalExperimentWalkForwardDataError(
    HistoricalExperimentWalkForwardError, ValueError
):
    """Raised when a fold's historical slice or schedule is invalid."""


class HistoricalExperimentWalkForwardSelectionError(
    HistoricalExperimentWalkForwardError, ValueError
):
    """Raised when training output cannot certify rank-one selection."""


class HistoricalExperimentWalkForwardExecutionError(
    HistoricalExperimentWalkForwardError
):
    """Raised when a child experiment, comparison, or report fails."""


class HistoricalExperimentWalkForwardReconciliationError(
    HistoricalExperimentWalkForwardError, ValueError
):
    """Raised when generated walk-forward provenance does not reconcile."""


class InconsistentHistoricalExperimentWalkForwardResultError(
    HistoricalExperimentWalkForwardError, ValueError
):
    """Raised when a retained walk-forward result is inconsistent."""


class HistoricalExperimentWalkForwardAggregateError(HistoricalExperimentError):
    """Base exception for deterministic walk-forward aggregate analytics."""


class InvalidHistoricalExperimentWalkForwardAggregatePolicyError(
    HistoricalExperimentWalkForwardAggregateError, ValueError
):
    """Raised when a walk-forward aggregate policy is malformed."""


class HistoricalExperimentWalkForwardAggregateSourceError(
    HistoricalExperimentWalkForwardAggregateError, ValueError
):
    """Raised when walk-forward source evidence cannot support aggregation."""


class HistoricalExperimentWalkForwardAggregateMetricError(
    HistoricalExperimentWalkForwardAggregateError, ValueError
):
    """Raised when a selected aggregate metric value is malformed."""


class HistoricalExperimentWalkForwardAggregateOperationError(
    HistoricalExperimentWalkForwardAggregateError, ValueError
):
    """Raised when a metric requests an ineligible aggregate operation."""


class HistoricalExperimentWalkForwardAggregateArithmeticError(
    HistoricalExperimentWalkForwardAggregateError
):
    """Raised when exact aggregate arithmetic cannot be completed."""


class HistoricalExperimentWalkForwardAggregateReconciliationError(
    HistoricalExperimentWalkForwardAggregateError, ValueError
):
    """Raised when generated aggregate evidence does not reconcile."""


class InconsistentHistoricalExperimentWalkForwardAggregateResultError(
    HistoricalExperimentWalkForwardAggregateError, ValueError
):
    """Raised when a retained walk-forward aggregate result is inconsistent."""


class HistoricalExperimentWalkForwardStabilityError(HistoricalExperimentError):
    """Base exception for deterministic walk-forward stability analysis."""


class InvalidHistoricalExperimentWalkForwardStabilityPolicyError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when a walk-forward stability policy is malformed."""


class HistoricalExperimentWalkForwardStabilitySourceError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when retained walk-forward evidence is invalid."""


class HistoricalExperimentWalkForwardStabilityAggregateSourceError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when optional aggregate provenance does not reconcile."""


class HistoricalExperimentWalkForwardStabilityMetricError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when a selected stability metric value is malformed."""


class HistoricalExperimentWalkForwardStabilityOperationError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when a metric requests an ineligible stability operation."""


class HistoricalExperimentWalkForwardStabilityComparabilityError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when folds do not satisfy an explicit comparability rule."""


class HistoricalExperimentWalkForwardStabilityArithmeticError(
    HistoricalExperimentWalkForwardStabilityError
):
    """Raised when exact stability arithmetic cannot be completed."""


class HistoricalExperimentWalkForwardStabilityReconciliationError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when generated stability evidence does not reconcile."""


class InconsistentHistoricalExperimentWalkForwardStabilityResultError(
    HistoricalExperimentWalkForwardStabilityError, ValueError
):
    """Raised when a retained walk-forward stability result is inconsistent."""
