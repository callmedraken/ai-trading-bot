"""Exceptions for deterministic rebalance planning."""


class RebalanceError(Exception):
    """Base exception for rebalance planning."""


class InvalidRebalanceRequestError(RebalanceError, ValueError):
    """Raised when a planning request is malformed."""


class InvalidRebalanceAssumptionsError(RebalanceError, ValueError):
    """Raised when planner assumptions are malformed."""


class RebalanceUniverseMismatchError(RebalanceError, ValueError):
    """Raised when state and target ordered universes differ."""


class StaleRebalanceTargetError(RebalanceError, ValueError):
    """Raised when state and target timestamps differ."""


class RebalanceTargetConstraintError(RebalanceError, ValueError):
    """Raised when a requested target violates supplied constraints."""


class RebalancePlanningError(RebalanceError):
    """Raised when the planner cannot construct a valid result."""


class InconsistentRebalancePlanError(RebalanceError, ValueError):
    """Raised when immutable plan fields do not reconcile locally."""


class RebalanceProposalError(RebalanceError):
    """Base exception for rebalance-plan proposal conversion."""


class InvalidRebalanceProposalRequestError(RebalanceProposalError, ValueError):
    """Raised when a proposal-conversion request is malformed."""


class RebalancePlanNotEligibleError(RebalanceProposalError):
    """Raised when plan status is not eligible for proposal conversion."""


class RebalanceProposalCreationError(RebalanceProposalError):
    """Raised when a planned trade cannot produce a valid proposal."""


class InconsistentRebalanceProposalResultError(RebalanceProposalError, ValueError):
    """Raised when conversion inputs or output do not reconcile locally."""
