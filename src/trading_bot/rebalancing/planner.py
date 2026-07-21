"""Deterministic current-price rebalance planner."""

from decimal import ROUND_DOWN, Decimal
from uuid import UUID, uuid5

from trading_bot.portfolio import PortfolioConstraints
from trading_bot.rebalancing.exceptions import RebalancePlanningError
from trading_bot.rebalancing.models import (
    PlannedTrade,
    PlannedTradeSide,
    RebalanceDeviation,
    RebalanceDiagnostic,
    RebalanceDiagnosticCode,
    RebalancePlan,
    RebalancePlanRequest,
    RebalanceStatus,
    UnplannedAllocationReason,
)

_ZERO = Decimal("0")
_TWO = Decimal("2")
_REBALANCE_NAMESPACE = UUID("f39ed7fe-b600-5a46-8331-2fab8bd00c42")


class RebalancePlanner:
    """Create an immutable estimate without authorizing or executing trades."""

    def plan(self, request: RebalancePlanRequest) -> RebalancePlan:
        if not isinstance(request, RebalancePlanRequest):
            raise TypeError("request must be a RebalancePlanRequest")
        assumptions = request.assumptions
        equity = request.state.equity
        tolerance = assumptions.target_weight_tolerance
        positions = request.state.positions
        allocations = request.target.allocations
        reasons: dict[int, UnplannedAllocationReason] = {}
        sells = []

        for ordinal, (position, allocation) in enumerate(
            zip(positions, allocations, strict=True)
        ):
            target_value = allocation.weight * equity
            target_quantity = target_value / position.current_price
            requested = position.quantity - target_quantity
            weight_difference = abs(position.market_value / equity - allocation.weight)
            if requested <= _ZERO:
                if weight_difference <= tolerance:
                    reasons[ordinal] = UnplannedAllocationReason.WITHIN_TOLERANCE
                continue
            if weight_difference <= tolerance:
                reasons[ordinal] = UnplannedAllocationReason.WITHIN_TOLERANCE
                continue
            full_exit = allocation.weight == _ZERO
            planned = (
                position.quantity
                if full_exit
                else self._round_down(requested, assumptions.quantity_increment)
            )
            planned = min(planned, position.quantity)
            if planned <= _ZERO:
                reasons[ordinal] = UnplannedAllocationReason.ROUNDED_TO_ZERO
                continue
            notional = planned * position.current_price
            if notional <= assumptions.fixed_commission:
                reasons[ordinal] = (
                    UnplannedAllocationReason.COMMISSION_EXCEEDS_SELL_PROCEEDS
                )
                continue
            if planned < assumptions.minimum_trade_quantity:
                reasons[ordinal] = UnplannedAllocationReason.BELOW_MINIMUM_QUANTITY
                continue
            if notional < assumptions.minimum_trade_notional:
                reasons[ordinal] = UnplannedAllocationReason.BELOW_MINIMUM_NOTIONAL
                continue
            if not full_exit and planned < requested:
                reasons[ordinal] = UnplannedAllocationReason.QUANTITY_ROUNDING
            sells.append(
                self._trade(
                    request,
                    PlannedTradeSide.SELL,
                    ordinal,
                    target_value,
                    target_quantity,
                    requested,
                    planned,
                )
            )

        gross_sell_proceeds = sum(
            (trade.estimated_gross_notional for trade in sells), start=_ZERO
        )
        sell_commissions = assumptions.fixed_commission * Decimal(len(sells))
        cash_after_sells = request.state.cash + gross_sell_proceeds - sell_commissions
        target_cash_value = request.target.cash_weight * equity
        protected_cash = (
            target_cash_value + assumptions.additional_execution_cash_buffer
        )
        if (
            cash_after_sells < protected_cash
            and assumptions.additional_execution_cash_buffer > _ZERO
        ):
            return self._infeasible(
                request,
                RebalanceDiagnosticCode.PROTECTED_CASH_UNAVAILABLE,
                "target cash plus additional execution buffer cannot be protected",
            )

        funding_cash = (
            cash_after_sells
            if assumptions.use_planned_sell_proceeds
            else request.state.cash - sell_commissions
        )
        remaining_budget = max(_ZERO, funding_cash - protected_cash)
        buys = []
        funding_priority_applied = False
        earlier_buy_reserved_cash = False
        for ordinal, (position, allocation) in enumerate(
            zip(positions, allocations, strict=True)
        ):
            target_value = allocation.weight * equity
            target_quantity = target_value / position.current_price
            requested = target_quantity - position.quantity
            weight_difference = abs(position.market_value / equity - allocation.weight)
            if requested <= _ZERO:
                continue
            if weight_difference <= tolerance:
                reasons[ordinal] = UnplannedAllocationReason.WITHIN_TOLERANCE
                continue
            rounded_desired = self._round_down(
                requested, assumptions.quantity_increment
            )
            affordable = _ZERO
            if remaining_budget > assumptions.fixed_commission:
                affordable = self._round_down(
                    (remaining_budget - assumptions.fixed_commission)
                    / position.current_price,
                    assumptions.quantity_increment,
                )
            planned = min(rounded_desired, affordable)
            if planned <= _ZERO:
                reasons[ordinal] = (
                    UnplannedAllocationReason.INSUFFICIENT_BUY_CASH
                    if affordable <= _ZERO and rounded_desired > _ZERO
                    else UnplannedAllocationReason.ROUNDED_TO_ZERO
                )
                if affordable < rounded_desired and earlier_buy_reserved_cash:
                    funding_priority_applied = True
                continue
            notional = planned * position.current_price
            if planned < assumptions.minimum_trade_quantity:
                reasons[ordinal] = UnplannedAllocationReason.BELOW_MINIMUM_QUANTITY
                continue
            if notional < assumptions.minimum_trade_notional:
                reasons[ordinal] = UnplannedAllocationReason.BELOW_MINIMUM_NOTIONAL
                continue
            required_cash = notional + assumptions.fixed_commission
            if required_cash > remaining_budget:
                raise RebalancePlanningError(
                    "rounded buy unexpectedly exceeds remaining budget"
                )
            remaining_budget -= required_cash
            if remaining_budget < _ZERO:
                raise RebalancePlanningError("buy funding made budget negative")
            if planned < rounded_desired:
                reasons[ordinal] = UnplannedAllocationReason.INSUFFICIENT_BUY_CASH
                if earlier_buy_reserved_cash:
                    funding_priority_applied = True
            elif rounded_desired < requested:
                reasons[ordinal] = UnplannedAllocationReason.QUANTITY_ROUNDING
            earlier_buy_reserved_cash = True
            buys.append(
                self._trade(
                    request,
                    PlannedTradeSide.BUY,
                    ordinal,
                    target_value,
                    target_quantity,
                    requested,
                    planned,
                )
            )

        trades = tuple((*sells, *buys))
        diagnostics = ()
        if funding_priority_applied:
            diagnostics = (
                RebalanceDiagnostic(
                    RebalanceDiagnosticCode.CANONICAL_FUNDING_PRIORITY_APPLIED,
                    "configured symbol order reduced or skipped a later buy",
                ),
            )
        gross_buy_cost = sum(
            (trade.estimated_gross_notional for trade in buys), start=_ZERO
        )
        commissions = assumptions.fixed_commission * Decimal(len(trades))
        ending_cash = (
            request.state.cash + gross_sell_proceeds - gross_buy_cost - commissions
        )
        if ending_cash < _ZERO:
            return self._infeasible(
                request,
                RebalanceDiagnosticCode.PROTECTED_CASH_UNAVAILABLE,
                "estimated ending cash would be negative",
            )
        achieved_quantities = [position.quantity for position in positions]
        for trade in trades:
            if trade.side is PlannedTradeSide.SELL:
                achieved_quantities[trade.symbol_ordinal] -= trade.planned_quantity
            else:
                achieved_quantities[trade.symbol_ordinal] += trade.planned_quantity
        achieved_values = tuple(
            quantity * position.current_price
            for quantity, position in zip(achieved_quantities, positions, strict=True)
        )
        ending_equity = ending_cash + sum(achieved_values, start=_ZERO)
        if ending_equity <= _ZERO:
            return self._infeasible(
                request,
                RebalanceDiagnosticCode.NONPOSITIVE_ENDING_EQUITY,
                "estimated ending equity would be nonpositive",
            )
        achieved_weights = tuple(value / ending_equity for value in achieved_values)
        deviations = self._deviations(
            request,
            tuple(achieved_quantities),
            achieved_values,
            achieved_weights,
            reasons,
        )
        achieved_cash_weight = ending_cash / ending_equity
        target_cash_at_end = request.target.cash_weight * ending_equity
        cash_value_deviation = ending_cash - target_cash_at_end
        cash_weight_deviation = achieved_cash_weight - request.target.cash_weight
        constraints_satisfied = self._constraints_satisfied(
            request.constraints,
            request,
            achieved_weights,
            achieved_cash_weight,
        )
        all_within = (
            all(item.absolute_weight_deviation <= tolerance for item in deviations)
            and abs(cash_weight_deviation) <= tolerance
        )
        if not trades and all_within:
            status = RebalanceStatus.NO_ACTION
        elif trades and all_within and constraints_satisfied:
            status = RebalanceStatus.COMPLETE
        else:
            status = RebalanceStatus.PARTIAL
        return RebalancePlan(
            self._plan_id(request),
            request,
            status,
            trades,
            deviations,
            diagnostics,
            equity,
            target_cash_value,
            request.state.cash,
            gross_sell_proceeds,
            gross_buy_cost,
            commissions,
            ending_cash,
            ending_equity,
            achieved_cash_weight,
            target_cash_at_end,
            cash_value_deviation,
            cash_weight_deviation,
            constraints_satisfied,
        )

    @staticmethod
    def _round_down(value: Decimal, increment: Decimal) -> Decimal:
        units = (value / increment).to_integral_value(rounding=ROUND_DOWN)
        result = units * increment
        return _ZERO if result == _ZERO else result

    @classmethod
    def _trade(
        cls,
        request: RebalancePlanRequest,
        side: PlannedTradeSide,
        ordinal: int,
        target_value: Decimal,
        target_quantity: Decimal,
        requested: Decimal,
        planned: Decimal,
    ) -> PlannedTrade:
        position = request.state.positions[ordinal]
        allocation = request.target.allocations[ordinal]
        gross = planned * position.current_price
        commission = request.assumptions.fixed_commission
        cash_effect = (
            gross - commission
            if side is PlannedTradeSide.SELL
            else -(gross + commission)
        )
        return PlannedTrade(
            cls._trade_id(request, side, position.symbol, ordinal),
            position.symbol,
            side,
            ordinal,
            position.current_price,
            position.quantity,
            allocation.weight,
            target_value,
            target_quantity,
            requested,
            planned,
            gross,
            commission,
            cash_effect,
        )

    @staticmethod
    def _deviations(
        request,
        quantities,
        values,
        weights,
        reasons,
    ):  # type: ignore[no-untyped-def]
        result = []
        for ordinal, (position, allocation, quantity, value, weight) in enumerate(
            zip(
                request.state.positions,
                request.target.allocations,
                quantities,
                values,
                weights,
                strict=True,
            )
        ):
            target_value = allocation.weight * request.state.equity
            signed = weight - allocation.weight
            result.append(
                RebalanceDeviation(
                    position.symbol,
                    ordinal,
                    allocation.weight,
                    weight,
                    signed,
                    abs(signed),
                    target_value,
                    value,
                    target_value / position.current_price,
                    quantity,
                    reasons.get(ordinal),
                )
            )
        return tuple(result)

    @staticmethod
    def _constraints_satisfied(
        constraints: PortfolioConstraints | None,
        request: RebalancePlanRequest,
        weights: tuple[Decimal, ...],
        cash_weight: Decimal,
    ) -> bool:
        if constraints is None:
            return True
        if not (
            constraints.minimum_cash_weight
            <= cash_weight
            <= constraints.maximum_cash_weight
        ):
            return False
        for weight in weights:
            if weight > constraints.maximum_position_weight:
                return False
            if (
                constraints.minimum_position_weight is not None
                and weight > _ZERO
                and weight < constraints.minimum_position_weight
            ):
                return False
        maximum_turnover = constraints.maximum_one_way_rebalance_turnover
        if maximum_turnover is not None:
            total_change = sum(
                (
                    abs(achieved - current)
                    for achieved, current in zip(
                        weights, request.state.position_weights, strict=True
                    )
                ),
                start=_ZERO,
            ) + abs(cash_weight - request.state.cash_weight)
            if total_change / _TWO > maximum_turnover:
                return False
        return True

    @classmethod
    def _infeasible(
        cls,
        request: RebalancePlanRequest,
        code: RebalanceDiagnosticCode,
        message: str,
    ) -> RebalancePlan:
        weights = request.state.position_weights
        values = tuple(item.market_value for item in request.state.positions)
        quantities = tuple(item.quantity for item in request.state.positions)
        deviations = cls._deviations(request, quantities, values, weights, {})
        cash_weight = request.state.cash_weight
        target_cash = request.target.cash_weight * request.state.equity
        target_cash_at_end = target_cash
        return RebalancePlan(
            cls._plan_id(request),
            request,
            RebalanceStatus.INFEASIBLE,
            (),
            deviations,
            (RebalanceDiagnostic(code, message),),
            request.state.equity,
            target_cash,
            request.state.cash,
            _ZERO,
            _ZERO,
            _ZERO,
            request.state.cash,
            request.state.equity,
            cash_weight,
            target_cash_at_end,
            request.state.cash - target_cash_at_end,
            cash_weight - request.target.cash_weight,
            cls._constraints_satisfied(
                request.constraints, request, weights, cash_weight
            ),
        )

    @staticmethod
    def _plan_id(request: RebalancePlanRequest) -> UUID:
        return uuid5(_REBALANCE_NAMESPACE, f"plan:{request.request_id}")

    @staticmethod
    def _trade_id(
        request: RebalancePlanRequest,
        side: PlannedTradeSide,
        symbol,
        ordinal: int,
    ) -> UUID:
        identity = f"trade:{request.request_id}:{side.value}:{symbol}:{ordinal}"
        return uuid5(_REBALANCE_NAMESPACE, identity)
