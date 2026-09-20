"""Pure diagnostic evaluation through the current strategy."""

from dataclasses import fields
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from trading_bot.backtesting import BacktestContext
from trading_bot.domain import Bar, Position, Symbol
from trading_bot.gui.operator_observability_models import (
    OperatorStrategyPreview,
    OperatorStrategyPreviewStatus,
)
from trading_bot.ledger import AccountSnapshot
from trading_bot.market_calendar import TradingSession
from trading_bot.strategies import (
    MovingAverageCrossoverConfig,
    MovingAverageCrossoverStrategy,
)

_MAX_DIAGNOSTIC_ITEMS = 4096


def _pure_data(value: object) -> bool:
    """Reject capabilities/substituted objects before domain evaluation."""
    if type(value) in (str, int, date, datetime, UUID) or isinstance(value, Decimal):
        return True
    if type(value) is tuple:
        return len(value) <= _MAX_DIAGNOSTIC_ITEMS and all(
            _pure_data(item) for item in value
        )
    if type(value) is MappingProxyType:
        return len(value) <= _MAX_DIAGNOSTIC_ITEMS and all(
            _pure_data(key) and _pure_data(item) for key, item in value.items()
        )
    if type(value) in (
        BacktestContext,
        MovingAverageCrossoverConfig,
        TradingSession,
        Bar,
        Position,
        Symbol,
        AccountSnapshot,
    ):
        return all(_pure_data(getattr(value, field.name)) for field in fields(value))
    return False


def evaluate_operator_strategy_preview(
    context: BacktestContext | None = None,
    config: MovingAverageCrossoverConfig | None = None,
) -> OperatorStrategyPreview:
    """Evaluate once; return only already-derived presentation scalars.

    Callers explicitly supply a pure current-domain context, including its run
    identity. O1/O3 facts alone lack that identity; no production context is
    invented from them. No context, proposal, target or prepared decision is
    retained in the returned view. NO_PROPOSAL combines all current None results
    because the public evaluator does not expose intermediate classifications.
    """
    if context is None and config is None:
        return OperatorStrategyPreview()
    try:
        if (
            type(context) is not BacktestContext
            or type(config) is not MovingAverageCrossoverConfig
            or not _pure_data(context)
            or not _pure_data(config)
        ):
            return OperatorStrategyPreview(OperatorStrategyPreviewStatus.BLOCKED)
        proposal = MovingAverageCrossoverStrategy(config).evaluate(context)
        if proposal is None:
            return OperatorStrategyPreview(OperatorStrategyPreviewStatus.NO_PROPOSAL)
        return OperatorStrategyPreview(
            status=OperatorStrategyPreviewStatus.PROPOSAL,
            proposal_id=proposal.proposal_id,
            reason=proposal.reason,
            side=proposal.side.value,
            quantity=proposal.desired_quantity,
        )
    except (TypeError, ValueError, ArithmeticError):
        return OperatorStrategyPreview(OperatorStrategyPreviewStatus.BLOCKED)
