"""Expected failures from the optimized simulation command-line adapter."""

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


class AuditOutputError(OptimizedSimulationCliError):
    """Raised when deterministic audit output cannot be produced or replaced."""
