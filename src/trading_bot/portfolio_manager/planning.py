"""Dependency-ordered preview plans; this module has no dispatch surface."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.portfolio_manager.decision import Action, DecisionBatch
from trading_bot.portfolio_manager.models import (
    PortfolioObservation,
    _identity,
    canonical_decimal,
)
from trading_bot.portfolio_manager.risk import RiskDisposition, RiskEvaluation

_ZERO = Decimal("0")


class PreviewSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class PreviewLeg:
    leg_id: UUID
    recommendation_id: UUID
    symbol: Symbol
    side: PreviewSide
    quantity: Decimal
    reference_price: Decimal
    gross_notional: Decimal
    estimated_slippage: Decimal
    estimated_commission: Decimal
    depends_on: tuple[UUID, ...] = ()
    preview_only: bool = True
    dispatch_authorized: bool = False

    def __post_init__(self) -> None:
        for name in ("leg_id", "recommendation_id"):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be a UUID")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.side, PreviewSide):
            raise TypeError("side must be PreviewSide")
        for name in (
            "quantity",
            "reference_price",
            "gross_notional",
            "estimated_slippage",
            "estimated_commission",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value < _ZERO:
                raise ValueError(f"{name} must be a nonnegative finite Decimal")
        if self.quantity <= _ZERO or self.reference_price <= _ZERO:
            raise ValueError(
                "preview legs require positive quantity and reference price"
            )
        dependencies = tuple(self.depends_on)
        if any(not isinstance(item, UUID) for item in dependencies):
            raise TypeError("depends_on must contain UUID values")
        if len(set(dependencies)) != len(dependencies):
            raise ValueError("dependencies must be unique")
        if self.preview_only is not True or self.dispatch_authorized is not False:
            raise ValueError("Portfolio Manager preview legs cannot be dispatched")
        object.__setattr__(self, "depends_on", dependencies)


@dataclass(frozen=True, slots=True)
class OrderPlan:
    plan_id: UUID
    account_fingerprint: str | None
    portfolio_snapshot_id: UUID
    decision_batch_id: UUID
    legs: tuple[PreviewLeg, ...]
    blocked: tuple[RiskEvaluation, ...]
    sell_before_buy_dependency: bool = False
    sell_proceeds_assumed_available: Decimal = _ZERO
    preview_only: bool = True
    dispatch_authorized: bool = False

    def __post_init__(self) -> None:
        for name in ("plan_id", "portfolio_snapshot_id", "decision_batch_id"):
            if not isinstance(getattr(self, name), UUID):
                raise TypeError(f"{name} must be a UUID")
        if self.account_fingerprint is not None and (
            len(self.account_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.account_fingerprint
            )
        ):
            raise ValueError(
                "account_fingerprint must be lowercase SHA-256 hex or None"
            )
        legs = tuple(self.legs)
        blocked = tuple(self.blocked)
        if any(not isinstance(item, PreviewLeg) for item in legs):
            raise TypeError("legs must contain PreviewLeg values")
        if any(not isinstance(item, RiskEvaluation) for item in blocked):
            raise TypeError("blocked must contain RiskEvaluation values")
        if not isinstance(self.sell_before_buy_dependency, bool):
            raise TypeError("sell_before_buy_dependency must be a bool")
        if len({item.leg_id for item in legs}) != len(legs):
            raise ValueError("preview leg IDs must be unique")
        if any(item.disposition is not RiskDisposition.BLOCKED for item in blocked):
            raise ValueError("blocked rows must be blocked risk evaluations")
        sides = tuple(item.side for item in legs)
        if sides != tuple(
            sorted(sides, key=lambda side: 0 if side is PreviewSide.SELL else 1)
        ):
            raise ValueError("sell legs must precede buy legs")
        sell_ids = tuple(item.leg_id for item in legs if item.side is PreviewSide.SELL)
        expected_dependencies = sell_ids if self.sell_before_buy_dependency else ()
        for leg in legs:
            if leg.side is PreviewSide.BUY and leg.depends_on != expected_dependencies:
                raise ValueError("buy legs must depend on every approved sell leg")
            if leg.side is PreviewSide.SELL and leg.depends_on:
                raise ValueError("sell legs cannot depend on later legs")
        if (
            not isinstance(self.sell_proceeds_assumed_available, Decimal)
            or not self.sell_proceeds_assumed_available.is_finite()
            or self.sell_proceeds_assumed_available != _ZERO
        ):
            raise ValueError("preview plans cannot assume proposed sell proceeds")
        if self.preview_only is not True or self.dispatch_authorized is not False:
            raise ValueError("Portfolio Manager plans cannot be dispatched")
        if self.plan_id != _plan_id(
            self.account_fingerprint,
            self.portfolio_snapshot_id,
            self.decision_batch_id,
            legs,
            blocked,
            self.sell_before_buy_dependency,
        ):
            raise ValueError("plan_id does not match canonical preview plan identity")
        object.__setattr__(self, "legs", legs)
        object.__setattr__(self, "blocked", blocked)


def _leg_id(
    recommendation_id: UUID,
    side: PreviewSide,
    symbol: Symbol,
    quantity: Decimal,
    price: Decimal,
    slippage: Decimal,
    commission: Decimal,
) -> UUID:
    return _identity(
        "preview-leg",
        (
            str(recommendation_id),
            side.value,
            str(symbol),
            canonical_decimal(quantity),
            canonical_decimal(price),
            canonical_decimal(slippage),
            canonical_decimal(commission),
        ),
    )


def _plan_id(
    account_fingerprint: str | None,
    snapshot_id: UUID,
    batch_id: UUID,
    legs: tuple[PreviewLeg, ...],
    blocked: tuple[RiskEvaluation, ...],
    sell_before_buy_dependency: bool,
) -> UUID:
    values = [
        account_fingerprint or "none",
        str(snapshot_id),
        str(batch_id),
        str(sell_before_buy_dependency),
    ]
    for leg in legs:
        values.extend(("leg", str(leg.leg_id), *(str(item) for item in leg.depends_on)))
    for result in blocked:
        values.extend(
            (
                "blocked",
                str(result.recommendation_id),
                *(item.value for item in result.codes),
            )
        )
    return _identity("preview-plan", tuple(values))


def plan_preview(
    observation: PortfolioObservation,
    decision_batch: DecisionBatch,
    risk_evaluations: tuple[RiskEvaluation, ...],
) -> OrderPlan:
    """Build a deterministic sell-before-buy preview from independent risk results."""
    if not isinstance(observation, PortfolioObservation):
        raise TypeError("observation must be PortfolioObservation")
    if not isinstance(decision_batch, DecisionBatch):
        raise TypeError("decision_batch must be DecisionBatch")
    evaluations = tuple(risk_evaluations)
    if any(not isinstance(item, RiskEvaluation) for item in evaluations):
        raise TypeError("risk_evaluations must contain RiskEvaluation values")
    expected_ids = tuple(
        item.recommendation_id for item in decision_batch.recommendations
    )
    actual_ids = tuple(item.recommendation_id for item in evaluations)
    if actual_ids != expected_ids:
        raise ValueError(
            "risk evaluations must preserve exact recommendation order and coverage"
        )
    if (
        decision_batch.portfolio_snapshot_id != observation.snapshot_id
        or decision_batch.account_fingerprint != observation.account_fingerprint
    ):
        raise ValueError(
            "decision batch must be bound to the observed portfolio and account"
        )
    approved_sells = tuple(
        item
        for item in evaluations
        if item.disposition is RiskDisposition.PREVIEW_APPROVED
        and item.order_side == "SELL"
    )
    approved_buys = tuple(
        item
        for item in evaluations
        if item.disposition is RiskDisposition.PREVIEW_APPROVED
        and item.order_side == "BUY"
    )
    blocked = tuple(
        item for item in evaluations if item.disposition is RiskDisposition.BLOCKED
    )
    for item in evaluations:
        if item.disposition is RiskDisposition.PREVIEW_APPROVED and (
            item.price is None or item.price <= _ZERO
        ):
            raise ValueError(
                "approved preview evaluation requires a positive reference price"
            )
    dependency_required = any(
        item.action is Action.REBALANCE for item in decision_batch.recommendations
    )
    sell_legs = tuple(
        PreviewLeg(
            leg_id=_leg_id(
                item.recommendation_id,
                PreviewSide.SELL,
                item.symbol,
                item.order_quantity,
                item.price,
                item.estimated_slippage,
                item.estimated_commission,
            ),
            recommendation_id=item.recommendation_id,
            symbol=item.symbol,
            side=PreviewSide.SELL,
            quantity=item.order_quantity,
            reference_price=item.price,
            gross_notional=item.estimated_gross_notional,
            estimated_slippage=item.estimated_slippage,
            estimated_commission=item.estimated_commission,
        )
        for item in approved_sells
    )
    dependencies = (
        tuple(item.leg_id for item in sell_legs) if dependency_required else ()
    )
    buy_legs = tuple(
        PreviewLeg(
            leg_id=_leg_id(
                item.recommendation_id,
                PreviewSide.BUY,
                item.symbol,
                item.order_quantity,
                item.price,
                item.estimated_slippage,
                item.estimated_commission,
            ),
            recommendation_id=item.recommendation_id,
            symbol=item.symbol,
            side=PreviewSide.BUY,
            quantity=item.order_quantity,
            reference_price=item.price,
            gross_notional=item.estimated_gross_notional,
            estimated_slippage=item.estimated_slippage,
            estimated_commission=item.estimated_commission,
            depends_on=dependencies,
        )
        for item in approved_buys
    )
    legs = sell_legs + buy_legs
    provisional_id = _plan_id(
        observation.account_fingerprint,
        observation.snapshot_id,
        decision_batch.decision_batch_id,
        legs,
        blocked,
        dependency_required,
    )
    return OrderPlan(
        plan_id=provisional_id,
        account_fingerprint=observation.account_fingerprint,
        portfolio_snapshot_id=observation.snapshot_id,
        decision_batch_id=decision_batch.decision_batch_id,
        legs=legs,
        blocked=blocked,
        sell_before_buy_dependency=dependency_required,
    )
