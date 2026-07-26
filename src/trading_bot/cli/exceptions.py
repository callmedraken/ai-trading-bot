"""Expected failures from the optimized simulation command-line adapter."""

from uuid import UUID

from trading_bot.portfolio import OptimizationStatus


class OptimizedSimulationCliError(Exception):
    """Base exception for expected optimized-simulation CLI failures."""


class ConfigReadError(OptimizedSimulationCliError):
    """Raised when the configuration file cannot be read as UTF-8 text."""


class ConfigJsonError(OptimizedSimulationCliError):
    """Raised when configuration text is not valid JSON."""


class ConfigValidationError(OptimizedSimulationCliError, ValueError):
    """Raised when a configuration value fails schema or domain validation."""

    def __init__(self, field_path: str, message: str) -> None:
        self.field_path = field_path
        super().__init__(f"{field_path}: {message}")


class OptimizerCliError(OptimizedSimulationCliError):
    """Raised when an optimization frame does not produce an optimal result."""

    def __init__(
        self,
        frame_ordinal: int,
        message: str,
        *,
        status: OptimizationStatus | None = None,
        diagnostic_codes: tuple[str, ...] = (),
    ) -> None:
        self.frame_ordinal = frame_ordinal
        self.status = status
        self.diagnostic_codes = diagnostic_codes
        super().__init__(message)


class SimulationCliError(OptimizedSimulationCliError):
    """Raised when certification, runtime, or reconciliation fails."""


class AnalyticsCliError(OptimizedSimulationCliError):
    """Raised when post-simulation performance analysis fails."""

    def __init__(self, source_simulation_result_id: UUID, message: str) -> None:
        self.source_simulation_result_id = source_simulation_result_id
        super().__init__(message)


class AuditOutputError(OptimizedSimulationCliError):
    """Raised when deterministic audit output cannot be produced or replaced."""


class RollingHistoricalCliError(Exception):
    """Base exception for expected rolling historical CLI failures."""


class RollingHistoricalConfigError(RollingHistoricalCliError, ValueError):
    """Raised when rolling-specific configuration is inconsistent."""


class HistoricalDataCliError(RollingHistoricalCliError):
    """Raised when configured local historical data cannot be loaded."""


class RollingInitializationCliError(RollingHistoricalCliError):
    """Raised when deterministic simulator initialization fails."""


class RollingExecutionCliError(RollingHistoricalCliError):
    """Raised when rolling preparation, execution, or analytics fails."""


class RollingAuditOutputError(RollingHistoricalCliError):
    """Raised when the complete rolling audit cannot be constructed."""


class HistoricalExperimentCliError(Exception):
    """Base exception for expected historical-experiment CLI failures."""


class HistoricalExperimentDataError(HistoricalExperimentCliError):
    """Raised when configured local historical data cannot be loaded."""


class HistoricalExperimentInitializationCliError(HistoricalExperimentCliError):
    """Raised when one fresh experiment simulator cannot be initialized."""


class HistoricalExperimentExecutionCliError(HistoricalExperimentCliError):
    """Raised when experiment execution, isolation, or reconciliation fails."""


class HistoricalExperimentAuditError(HistoricalExperimentCliError):
    """Raised when experiment audit construction or reconciliation fails."""


class HistoricalExperimentReportOutputError(HistoricalExperimentCliError):
    """Raised when compact report output cannot be serialized or written."""


class HistoricalExperimentPairwiseOutputError(HistoricalExperimentCliError):
    """Raised when pairwise output cannot be serialized."""


class HistoricalExperimentParetoOutputError(HistoricalExperimentCliError):
    """Raised when Pareto output cannot be serialized."""


class WalkForwardExperimentCliError(Exception):
    """Base exception for expected walk-forward CLI failures."""


class WalkForwardExperimentDataError(WalkForwardExperimentCliError):
    """Raised when configured walk-forward history cannot be loaded."""


class WalkForwardExperimentInitializationCliError(WalkForwardExperimentCliError):
    """Raised when a child simulator cannot be initialized."""


class WalkForwardExperimentExecutionCliError(WalkForwardExperimentCliError):
    """Raised when walk-forward execution or reconciliation fails."""


class WalkForwardExperimentOutputError(WalkForwardExperimentCliError):
    """Raised when walk-forward output cannot be serialized or written."""


class ResearchSessionManifestError(WalkForwardExperimentOutputError, ValueError):
    """Raised when a research-session manifest is invalid or cannot be built."""


class ResearchSessionManifestVerificationError(ResearchSessionManifestError):
    """Raised when offline artifact verification fails."""


class ResearchSessionManifestReadError(Exception):
    """Raised when a retained research-session manifest cannot be read."""


class ResearchSessionManifestJsonError(Exception):
    """Raised when retained research-session manifest JSON is invalid."""


class ResearchSessionBundleError(Exception):
    """Base exception for expected portable research-bundle failures."""


class ResearchSessionBundlePlanError(ResearchSessionBundleError, ValueError):
    """Raised when a deterministic bundle path plan is invalid."""


class ResearchSessionBundleSourceVerificationError(ResearchSessionBundleError):
    """Raised when source artifacts do not pass offline verification."""

    def __init__(self, result: object) -> None:
        self.result = result
        super().__init__("source research-session verification failed")


class ResearchSessionBundleSourceArtifactError(ResearchSessionBundleError):
    """Raised when a source artifact changes or becomes unsafe during copying."""

    def __init__(self, artifact: object, status: object) -> None:
        self.artifact = artifact
        self.status = status
        super().__init__("source artifact failed revalidation during copying")


class ResearchSessionBundleOutputError(ResearchSessionBundleError):
    """Raised for destination, staging, copy, verification, or cleanup failures."""

    def __init__(
        self,
        message: str,
        *,
        cleanup_message: str | None = None,
        primary_error: Exception | None = None,
    ) -> None:
        self.cleanup_message = cleanup_message
        self.primary_error = primary_error
        super().__init__(message)


class ResearchSessionArchiveError(Exception):
    """Base exception for canonical research-bundle archive failures."""


class ResearchSessionArchiveArgumentError(ResearchSessionArchiveError, ValueError):
    """Raised when archive API arguments are invalid."""


class ResearchSessionArchiveReadError(ResearchSessionArchiveError):
    """Raised when an archive cannot be opened or read safely."""


class ResearchSessionArchiveStructureError(ResearchSessionArchiveError, ValueError):
    """Raised when archive structure is unsupported or noncanonical."""


class ResearchSessionArchiveByteLengthMismatchError(ResearchSessionArchiveError):
    """Raised when retained or expected byte length does not match."""


class ResearchSessionArchiveHashMismatchError(ResearchSessionArchiveError):
    """Raised when retained or expected SHA-256 does not match."""


class ResearchSessionArchiveSourceVerificationError(ResearchSessionArchiveError):
    """Raised when the completed source bundle does not verify."""

    def __init__(self, result: object) -> None:
        self.result = result
        super().__init__("source research bundle verification failed")


class ResearchSessionArchiveSourceEntryError(ResearchSessionArchiveError):
    """Raised when a bundle entry becomes unsafe during archive creation."""

    def __init__(self, path: str, status: object) -> None:
        self.path = path
        self.status = status
        super().__init__("source bundle entry failed revalidation")


class ResearchSessionArchiveOutputError(ResearchSessionArchiveError):
    """Raised for archive destination, staging, or finalization failures."""

    def __init__(
        self,
        message: str,
        *,
        cleanup_message: str | None = None,
        primary_error: Exception | None = None,
    ) -> None:
        self.cleanup_message = cleanup_message
        self.primary_error = primary_error
        super().__init__(message)
