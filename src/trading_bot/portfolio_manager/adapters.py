"""Validated adapters into strict portfolio models when all fields are known."""

from __future__ import annotations

from decimal import MAX_EMAX, MIN_EMIN, localcontext

from trading_bot.portfolio import PortfolioPositionState, PortfolioState
from trading_bot.portfolio_manager.models import (
    ObservationCondition,
    PortfolioObservation,
    decimal_multiply,
)


class PortfolioStateAdapterError(ValueError):
    """The observation lacks facts required by the strict portfolio model."""


_MAX_CONTEXT_PRECISION = 100_000


def _context_precision(values) -> int:  # type: ignore[no-untyped-def]
    parts = tuple(value.as_tuple() for value in values)
    lowest_exponent = min(part.exponent for part in parts)
    aligned_digits = max(
        len(part.digits) + part.exponent - lowest_exponent for part in parts
    )
    # Extra digits account for a carry across all portfolio rows.
    return max(28, aligned_digits + len(str(len(parts))) + 4)


def to_portfolio_state(observation: PortfolioObservation) -> PortfolioState:
    """Convert only a complete, account-matched, valued positive portfolio.

    The strict optimizer model requires every open holding to have a positive
    average cost and requires equity to equal locally valued positions plus
    cash. This adapter never fills unknown fields or substitutes broker equity.
    """
    if not isinstance(observation, PortfolioObservation):
        raise TypeError("observation must be PortfolioObservation")
    blocking = {
        ObservationCondition.ACCOUNT_NOT_BOUND,
        ObservationCondition.ACCOUNT_MISMATCH,
        ObservationCondition.PORTFOLIO_INCOMPLETE,
        ObservationCondition.POSITIONS_INCOMPLETE,
        ObservationCondition.QUOTES_INCOMPLETE,
        ObservationCondition.MISSING_PRICE,
        ObservationCondition.MISSING_VALUATION,
        ObservationCondition.NEGATIVE_CASH,
        ObservationCondition.UNSUPPORTED_ASSET,
        ObservationCondition.ASSET_TYPE_UNKNOWN,
        ObservationCondition.SHORT_POSITION,
        ObservationCondition.POSITION_TYPE_UNKNOWN,
        ObservationCondition.BROKER_EQUITY_DIFFERS_FROM_LOCAL,
        ObservationCondition.STALE_PRICE,
        ObservationCondition.PAGINATION_INCOMPLETE,
        ObservationCondition.ORDER_SCOPE_INCOMPLETE,
        ObservationCondition.UNKNOWN_ORDER_OWNER,
        ObservationCondition.UNKNOWN_ORDER_STATE,
        ObservationCondition.DUPLICATE_ORDER_ID,
        ObservationCondition.RECONCILIATION_UNCERTAIN,
    }
    if blocking.intersection(observation.conditions):
        raise PortfolioStateAdapterError("OBSERVATION_NOT_STRICTLY_VALUED")
    if not observation.positions:
        raise PortfolioStateAdapterError("STRICT_MODEL_REQUIRES_NONEMPTY_POSITIONS")
    if observation.cash is None or observation.locally_computed_equity is None:
        raise PortfolioStateAdapterError("OBSERVATION_VALUATION_MISSING")
    converted: list[PortfolioPositionState] = []
    for position in observation.positions:
        if (
            position.quantity <= 0
            or position.average_cost is None
            or position.average_cost <= 0
            or position.current_price is None
        ):
            raise PortfolioStateAdapterError("POSITION_COST_OR_CHRONOLOGY_UNSUPPORTED")
        converted.append(
            PortfolioPositionState(
                symbol=position.symbol,
                quantity=position.quantity,
                average_cost=position.average_cost,
                current_price=position.current_price,
            )
        )
    try:
        precise_values = [observation.cash]
        precise_values.extend(
            decimal_multiply(position.quantity, position.current_price)
            for position in observation.positions
        )
        precision = _context_precision(precise_values)
        if precision > _MAX_CONTEXT_PRECISION:
            raise PortfolioStateAdapterError("STRICT_STATE_PRECISION_BOUND_EXCEEDED")
        with localcontext() as context:
            context.prec = precision
            context.Emax = MAX_EMAX
            context.Emin = MIN_EMIN
            return PortfolioState(
                as_of=observation.observed_at,
                positions=tuple(converted),
                cash=observation.cash,
                equity=observation.locally_computed_equity,
            )
    except PortfolioStateAdapterError:
        raise
    except (TypeError, ValueError, ArithmeticError):
        raise PortfolioStateAdapterError("STRICT_PORTFOLIO_STATE_REJECTED") from None
