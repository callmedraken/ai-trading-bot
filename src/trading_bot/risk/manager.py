"""Deterministic pre-trade risk evaluation."""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from trading_bot.domain import OrderSide, TradeProposal
from trading_bot.risk.models import (
    RiskContext,
    RiskDecision,
    RiskLimits,
    RiskOutcome,
    RiskReason,
    RiskReasonCode,
)


@dataclass(frozen=True, slots=True)
class _QuantityConstraint:
    maximum: Decimal
    reason: RiskReason


class RiskManager:
    """Evaluate proposals without mutating account or market state."""

    def __init__(self, limits: RiskLimits) -> None:
        if not isinstance(limits, RiskLimits):
            raise TypeError("limits must be RiskLimits")
        self._limits = limits

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def evaluate(self, proposal: TradeProposal, context: RiskContext) -> RiskDecision:
        """Return an approved, resized, or rejected deterministic decision."""
        if not isinstance(proposal, TradeProposal):
            raise TypeError("proposal must be a TradeProposal")
        if not isinstance(context, RiskContext):
            raise TypeError("context must be a RiskContext")
        if proposal.side is OrderSide.BUY:
            return self._evaluate_buy(proposal, context)
        return self._evaluate_sell(proposal, context)

    def _evaluate_buy(
        self, proposal: TradeProposal, context: RiskContext
    ) -> RiskDecision:
        if not context.new_trading_enabled:
            return self._reject(
                proposal,
                context,
                RiskReasonCode.TRADING_DISABLED,
                "new trading is disabled",
            )
        if not self._limits.allow_buying:
            return self._reject(
                proposal,
                context,
                RiskReasonCode.BUYING_DISABLED,
                "buying is disabled by risk limits",
            )
        price = context.current_price
        if price is None:
            return self._reject(
                proposal,
                context,
                RiskReasonCode.PRICE_NOT_AVAILABLE,
                f"no current price is available for {proposal.symbol}",
            )

        constraints = self._buy_constraints(proposal, context, price)
        raw_quantity = min(
            proposal.desired_quantity,
            *(constraint.maximum for constraint in constraints),
        )
        binding_reasons = tuple(
            constraint.reason
            for constraint in constraints
            if constraint.maximum == raw_quantity
            and constraint.maximum <= proposal.desired_quantity
        )
        normalized = self._normalize_down(raw_quantity)
        if normalized <= Decimal("0"):
            reasons = binding_reasons + (
                RiskReason(
                    RiskReasonCode.QUANTITY_TOO_SMALL,
                    "no positive quantity satisfies every risk limit",
                    observed=raw_quantity,
                    limit=self._quantity_increment,
                ),
            )
            return RiskDecision(
                proposal,
                RiskOutcome.REJECTED,
                Decimal("0"),
                reasons,
                context.as_of,
            )

        reasons = binding_reasons
        if normalized < raw_quantity:
            reasons += (
                RiskReason(
                    RiskReasonCode.QUANTITY_INCREMENT,
                    "quantity was rounded down to the permitted increment",
                    observed=raw_quantity,
                    limit=self._quantity_increment,
                ),
            )
        outcome = (
            RiskOutcome.APPROVED
            if normalized == proposal.desired_quantity
            else RiskOutcome.RESIZED
        )
        return RiskDecision(proposal, outcome, normalized, reasons, context.as_of)

    def _buy_constraints(
        self, proposal: TradeProposal, context: RiskContext, price: Decimal
    ) -> tuple[_QuantityConstraint, ...]:
        limits = self._limits
        commission = limits.estimated_commission
        current_position = context.positions.get(proposal.symbol)
        current_quantity = (
            current_position.quantity if current_position is not None else Decimal("0")
        )
        constraints = [
            self._constraint(
                max(Decimal("0"), (context.cash - commission) / price),
                RiskReasonCode.CASH_CAPACITY,
                "available cash limits buy quantity",
                context.cash,
                commission,
            ),
            self._constraint(
                max(
                    Decimal("0"),
                    (
                        context.equity * limits.max_position_percent
                        - current_quantity * price
                    )
                    / price,
                ),
                RiskReasonCode.MAX_POSITION_PERCENT,
                "maximum post-trade position percentage limits buy quantity",
                current_quantity * price,
                context.equity * limits.max_position_percent,
            ),
            self._constraint(
                max(
                    Decimal("0"),
                    (
                        context.equity * limits.max_total_exposure_percent
                        - context.total_market_exposure
                    )
                    / price,
                ),
                RiskReasonCode.MAX_TOTAL_EXPOSURE_PERCENT,
                "maximum post-trade total exposure limits buy quantity",
                context.total_market_exposure,
                context.equity * limits.max_total_exposure_percent,
            ),
        ]
        if limits.minimum_cash_reserve_percent > Decimal("0"):
            constraints.append(
                self._constraint(
                    max(
                        Decimal("0"),
                        (
                            context.cash
                            - context.equity * limits.minimum_cash_reserve_percent
                            - commission
                        )
                        / price,
                    ),
                    RiskReasonCode.MINIMUM_CASH_RESERVE,
                    "minimum post-trade cash reserve limits buy quantity",
                    context.cash,
                    context.equity * limits.minimum_cash_reserve_percent,
                )
            )
        if limits.max_order_notional is not None:
            constraints.append(
                self._constraint(
                    limits.max_order_notional / price,
                    RiskReasonCode.MAX_ORDER_NOTIONAL,
                    "maximum order notional limits buy quantity",
                    proposal.desired_quantity * price,
                    limits.max_order_notional,
                )
            )
        if current_position is None and limits.max_new_position_percent is not None:
            constraints.append(
                self._constraint(
                    context.equity * limits.max_new_position_percent / price,
                    RiskReasonCode.MAX_NEW_POSITION_PERCENT,
                    "maximum new-position percentage limits buy quantity",
                    proposal.desired_quantity * price,
                    context.equity * limits.max_new_position_percent,
                )
            )
        return tuple(constraints)

    def _evaluate_sell(
        self, proposal: TradeProposal, context: RiskContext
    ) -> RiskDecision:
        if not self._limits.allow_selling:
            return self._reject(
                proposal,
                context,
                RiskReasonCode.SELLING_DISABLED,
                "selling is disabled by risk limits",
            )
        position = context.positions.get(proposal.symbol)
        if position is None:
            return self._reject(
                proposal,
                context,
                RiskReasonCode.POSITION_NOT_FOUND,
                f"no open position exists for {proposal.symbol}",
            )

        owned = position.quantity
        if proposal.desired_quantity >= owned:
            reasons: tuple[RiskReason, ...] = ()
            outcome = RiskOutcome.APPROVED
            if proposal.desired_quantity > owned:
                outcome = RiskOutcome.RESIZED
                reasons = (
                    RiskReason(
                        RiskReasonCode.SELL_QUANTITY_REDUCED,
                        "sell quantity was reduced to the owned quantity",
                        observed=proposal.desired_quantity,
                        limit=owned,
                    ),
                )
            # Exact liquidation is allowed even when the position is fractional
            # and fractional trading has since been disabled.
            return RiskDecision(proposal, outcome, owned, reasons, context.as_of)

        normalized = self._normalize_down(proposal.desired_quantity)
        if normalized <= Decimal("0"):
            return self._reject(
                proposal,
                context,
                RiskReasonCode.QUANTITY_TOO_SMALL,
                "sell quantity is below the permitted increment",
                observed=proposal.desired_quantity,
                limit=self._quantity_increment,
            )
        if normalized < proposal.desired_quantity:
            reason = RiskReason(
                RiskReasonCode.QUANTITY_INCREMENT,
                "sell quantity was rounded down to the permitted increment",
                observed=proposal.desired_quantity,
                limit=self._quantity_increment,
            )
            return RiskDecision(
                proposal,
                RiskOutcome.RESIZED,
                normalized,
                (reason,),
                context.as_of,
            )
        return RiskDecision(
            proposal, RiskOutcome.APPROVED, normalized, (), context.as_of
        )

    @property
    def _quantity_increment(self) -> Decimal:
        if self._limits.allow_fractional_shares:
            return self._limits.fractional_increment
        return Decimal("1")

    def _normalize_down(self, quantity: Decimal) -> Decimal:
        increment = self._quantity_increment
        units = (quantity / increment).to_integral_value(rounding=ROUND_DOWN)
        return units * increment

    @staticmethod
    def _constraint(
        maximum: Decimal,
        code: RiskReasonCode,
        message: str,
        observed: Decimal,
        limit: Decimal,
    ) -> _QuantityConstraint:
        return _QuantityConstraint(
            maximum=max(Decimal("0"), maximum),
            reason=RiskReason(code, message, observed=observed, limit=limit),
        )

    @staticmethod
    def _reject(
        proposal: TradeProposal,
        context: RiskContext,
        code: RiskReasonCode,
        message: str,
        observed: Decimal | None = None,
        limit: Decimal | None = None,
    ) -> RiskDecision:
        return RiskDecision(
            proposal,
            RiskOutcome.REJECTED,
            Decimal("0"),
            (RiskReason(code, message, observed=observed, limit=limit),),
            context.as_of,
        )
