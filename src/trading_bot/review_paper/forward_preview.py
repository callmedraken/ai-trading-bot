"""Effect-free durable forward-paper risk preview; no execution authority."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    Inexact,
    InvalidOperation,
    Overflow,
)

from trading_bot.domain import OrderSide, TradeProposal
from trading_bot.review_paper.risk_context import build_review_paper_risk_context
from trading_bot.review_paper.risk_prices import ReviewPaperRiskPriceSnapshot
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.risk.manager import RiskManager
from trading_bot.risk.models import RiskContext, RiskDecision, RiskLimits, RiskOutcome


def _context(precision: int) -> Context:
    """Use explicit arithmetic authority independent of ambient Decimal state."""
    return Context(
        prec=precision,
        rounding=ROUND_HALF_EVEN,
        Emin=MIN_EMIN,
        Emax=MAX_EMAX,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[Inexact, InvalidOperation, Overflow],
    )


def _sum_context(left: Decimal, right: Decimal) -> Context:
    precision = (
        max(left.adjusted(), right.adjusted())
        - min(left.as_tuple().exponent, right.as_tuple().exponent)
        + 2
    )
    return _context(max(1, precision))


def _multiply(left: Decimal, right: Decimal) -> Decimal:
    return _context(
        len(left.as_tuple().digits) + len(right.as_tuple().digits)
    ).multiply(left, right)


@dataclass(frozen=True, slots=True)
class ReviewPaperForwardPreview:
    """Preserve the supplied inputs and authoritative context/decision exactly."""

    proposal: TradeProposal
    price_snapshot: ReviewPaperRiskPriceSnapshot
    risk_limits: RiskLimits
    risk_context: RiskContext
    risk_decision: RiskDecision

    def __post_init__(self) -> None:
        for name, expected in (
            ("proposal", TradeProposal),
            ("price_snapshot", ReviewPaperRiskPriceSnapshot),
            ("risk_limits", RiskLimits),
            ("risk_context", RiskContext),
            ("risk_decision", RiskDecision),
        ):
            if type(getattr(self, name)) is not expected:
                raise TypeError(f"{name} must be exactly {expected.__name__}")
        if self.risk_decision.proposal is not self.proposal:
            raise ValueError("risk_decision must preserve the exact proposal")
        if self.risk_decision.evaluated_at != self.risk_context.as_of:
            raise ValueError("decision evaluated_at must match context as_of")
        if self.risk_context.as_of != self.price_snapshot.observed_at:
            raise ValueError("context as_of must match snapshot observed_at")
        if self.risk_context.as_of < self.proposal.created_at:
            raise ValueError("context as_of must not precede proposal created_at")
        prices = self.price_snapshot.prices
        if set(prices) != set(self.risk_context.positions) | {self.proposal.symbol}:
            raise ValueError("snapshot symbols must match context and proposal")
        if self.risk_context.current_price != prices[self.proposal.symbol]:
            raise ValueError("context current_price must match snapshot price")
        if (
            self.risk_decision.outcome is RiskOutcome.REJECTED
            and self.risk_decision.approved_quantity != Decimal("0")
        ):
            raise ValueError("rejected decisions must approve zero quantity")
        if self.projected_position_quantity < Decimal("0"):
            raise ValueError("projected position quantity must be nonnegative")
        if self.projected_total_market_exposure < Decimal("0"):
            raise ValueError("projected total market exposure must be nonnegative")

    @property
    def current_position_quantity(self) -> Decimal:
        position = self.risk_context.positions.get(self.proposal.symbol)
        return Decimal("0") if position is None else position.quantity

    @property
    def current_position_market_value(self) -> Decimal:
        return _multiply(
            self.current_position_quantity, self.risk_context.current_price
        )

    @property
    def projected_position_quantity(self) -> Decimal:
        current = self.current_position_quantity
        if self.risk_decision.outcome is RiskOutcome.REJECTED:
            return current
        approved = self.risk_decision.approved_quantity
        context = _sum_context(current, approved)
        if self.proposal.side is OrderSide.BUY:
            return context.add(current, approved)
        return context.subtract(current, approved)

    @property
    def projected_position_market_value(self) -> Decimal:
        return _multiply(
            self.projected_position_quantity, self.risk_context.current_price
        )

    @property
    def projected_total_market_exposure(self) -> Decimal:
        current = self.risk_context.total_market_exposure
        if self.risk_decision.outcome is RiskOutcome.REJECTED:
            return current
        notional = _multiply(
            self.risk_decision.approved_quantity, self.risk_context.current_price
        )
        context = _sum_context(current, notional)
        if self.proposal.side is OrderSide.BUY:
            return context.add(current, notional)
        return context.subtract(current, notional)


def build_review_paper_forward_preview(
    *,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    price_snapshot: ReviewPaperRiskPriceSnapshot,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
) -> ReviewPaperForwardPreview:
    """Compose 131-K and RiskManager once, without acquiring effect authority."""
    for name, value, expected in (
        ("store", store, ReviewPaperStore),
        ("proposal", proposal, TradeProposal),
        ("price_snapshot", price_snapshot, ReviewPaperRiskPriceSnapshot),
        ("risk_limits", risk_limits, RiskLimits),
        ("new_trading_enabled", new_trading_enabled, bool),
    ):
        if type(value) is not expected:
            raise TypeError(f"{name} must be exactly {expected.__name__}")
    risk_context = build_review_paper_risk_context(
        store,
        proposal,
        price_snapshot.prices,
        as_of=price_snapshot.observed_at,
        new_trading_enabled=new_trading_enabled,
    )
    decision = RiskManager(risk_limits).evaluate(proposal, risk_context)
    return ReviewPaperForwardPreview(
        proposal=proposal,
        price_snapshot=price_snapshot,
        risk_limits=risk_limits,
        risk_context=risk_context,
        risk_decision=decision,
    )
