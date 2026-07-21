"""Exceptions for optional numerical optimization adapters."""


class OptimizationAdapterError(Exception):
    """Base exception for numerical-adapter failures."""


class CpuOptimizerUnavailableError(OptimizationAdapterError):
    """Raised internally when the optional SciPy dependency is unavailable."""


class NumericalConversionError(OptimizationAdapterError, ValueError):
    """Raised when solver output cannot be converted safely."""


class SolverOutputError(OptimizationAdapterError, ValueError):
    """Raised when a nominally successful solver output is malformed."""


class PostSolveValidationError(OptimizationAdapterError, ValueError):
    """Raised when cleaned output violates exact domain constraints."""
