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
