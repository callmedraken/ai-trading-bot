"""P6 composition over the existing broker-independent RiskManager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from uuid import UUID, uuid5

from trading_bot.desktop_live.configuration import (
    LIVE_SYMBOL,
    MAX_BOT_GROSS_EXPOSURE_DOLLARS,
    MAX_ORDER_DOLLARS,
    TinyLivePolicy,
)
from trading_bot.desktop_paper.robinhood_read import (
    EquityPositionObservation,
    PortfolioObservation,
)
from trading_bot.domain import OrderSide, Position, Symbol, TradeProposal
from trading_bot.risk import (
    RiskContext,
    RiskDecision,
    RiskLimits,
    RiskManager,
    RiskOutcome,
    RiskReason,
    RiskReasonCode,
)
from trading_bot.robinhood_mcp.models import RobinhoodQuoteData

P6_ORDER_ID_NAMESPACE = UUID("1100c7fd-6559-5dfd-b5f2-0b57e4f77ec0")


@dataclass(frozen=True, slots=True)
class LiveRiskResult:
    decision: RiskDecision
    approved_quantity: Decimal
    requested_dollars: Decimal
    current_price: Decimal
    context: RiskContext


def p6_risk_limits() -> RiskLimits:
    """Return strict limits; provider buying power is deliberately absent."""
    return RiskLimits(
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        max_order_notional=MAX_ORDER_DOLLARS,
        max_new_position_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
        allow_fractional_shares=True,
        fractional_increment=Decimal("0.001"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("0"),
    )


def build_live_risk(
    *,
    portfolio: PortfolioObservation,
    positions: tuple[EquityPositionObservation, ...],
    quote: RobinhoodQuoteData,
    as_of: datetime,
    policy: TinyLivePolicy,
    target_session: str,
) -> LiveRiskResult:
    """Create the P6 RiskContext and evaluate a one-share BUY intent."""
    if not isinstance(policy, TinyLivePolicy):
        raise TypeError("policy must be TinyLivePolicy")
    if quote.symbol != LIVE_SYMBOL:
        raise ValueError("P6 risk requires the SPY quote")
    price, _ = quote.current_trade_candidate()
    if portfolio.cash < 0 or portfolio.equity_value <= 0:
        raise ValueError("cash/equity cannot prove a covered non-leveraged order")
    mapping: dict[Symbol, Position] = {}
    exposure = Decimal("0")
    for observed in positions:
        if observed.symbol != "SPY":
            raise ValueError("P6 first-live baseline cannot contain a non-SPY position")
        if observed.position_type == "short":
            raise ValueError("P6 does not support short positions")
        if observed.position_type == "long":
            if observed.average_buy_price is None:
                raise ValueError("long position cost is required for risk context")
            position = Position(
                Symbol(observed.symbol),
                observed.quantity,
                observed.average_buy_price,
            )
            mapping[position.symbol] = position
            exposure += position.market_value(price)
    context = RiskContext(
        cash=portfolio.cash,
        equity=portfolio.equity_value,
        positions=mapping,
        current_price=price,
        total_market_exposure=exposure,
        new_trading_enabled=True,
        as_of=as_of,
    )
    proposal = TradeProposal.create(
        symbol=LIVE_SYMBOL,
        side=OrderSide.BUY,
        desired_quantity=Decimal("1"),
        created_at=as_of,
        reason=f"P6_FILTERED_TREND_BUY:{target_session}",
        proposal_id=uuid5(
            P6_ORDER_ID_NAMESPACE,
            f"{policy.policy_id}:{target_session}:{price}",
        ),
    )
    decision = RiskManager(p6_risk_limits()).evaluate(proposal, context)
    if decision.outcome is RiskOutcome.REJECTED:
        return LiveRiskResult(decision, Decimal("0"), Decimal("0"), price, context)
    requested = (decision.approved_quantity * price).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    if requested <= 0 or requested > MAX_ORDER_DOLLARS:
        rejected = RiskDecision(
            proposal,
            RiskOutcome.REJECTED,
            Decimal("0"),
            (
                RiskReason(
                    RiskReasonCode.MAX_ORDER_NOTIONAL,
                    "P6 dollar conversion is outside the source-owned ceiling",
                    observed=requested,
                    limit=MAX_ORDER_DOLLARS,
                ),
            ),
            as_of,
        )
        return LiveRiskResult(rejected, Decimal("0"), Decimal("0"), price, context)
    if exposure + requested > MAX_BOT_GROSS_EXPOSURE_DOLLARS:
        rejected = RiskDecision(
            proposal,
            RiskOutcome.REJECTED,
            Decimal("0"),
            (
                RiskReason(
                    RiskReasonCode.MAX_TOTAL_EXPOSURE_PERCENT,
                    "P6 gross exposure ceiling would be exceeded",
                    observed=exposure + requested,
                    limit=MAX_BOT_GROSS_EXPOSURE_DOLLARS,
                ),
            ),
            as_of,
        )
        return LiveRiskResult(rejected, Decimal("0"), Decimal("0"), price, context)
    if portfolio.cash < requested or portfolio.equity_value < requested:
        rejected = RiskDecision(
            proposal,
            RiskOutcome.REJECTED,
            Decimal("0"),
            (
                RiskReason(
                    RiskReasonCode.CASH_CAPACITY,
                    "cash and equity do not prove a non-leveraged purchase",
                    observed=min(portfolio.cash, portfolio.equity_value),
                    limit=requested,
                ),
            ),
            as_of,
        )
        return LiveRiskResult(rejected, Decimal("0"), Decimal("0"), price, context)
    return LiveRiskResult(
        decision,
        decision.approved_quantity,
        requested,
        price,
        context,
    )
