"""Independent, preview-only risk evaluation for PM recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from trading_bot.domain import Symbol
from trading_bot.domain._validation import normalize_utc
from trading_bot.portfolio_manager.decision import (
    Action,
    DecisionBatch,
    MarketResearchInput,
    Recommendation,
)
from trading_bot.portfolio_manager.models import (
    ObservationCondition,
    OrderCoverage,
    OrderOwnership,
    PortfolioObservation,
    decimal_multiply,
    decimal_negate,
    decimal_subtract,
    decimal_sum,
)
from trading_bot.risk.models import RiskLimits

_ZERO = Decimal("0")
_ONE = Decimal("1")
_BPS = Decimal("10000")


class RiskDisposition(StrEnum):
    NO_ORDER = "NO_ORDER"
    PREVIEW_APPROVED = "PREVIEW_APPROVED"
    BLOCKED = "BLOCKED"


class RiskCode(StrEnum):
    NO_ORDER_REQUESTED = "NO_ORDER_REQUESTED"
    ACCOUNT_NOT_BOUND = "ACCOUNT_NOT_BOUND"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    RESEARCH_MISMATCH = "RESEARCH_MISMATCH"
    BATCH_MISMATCH = "BATCH_MISMATCH"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    STALE_RESEARCH = "STALE_RESEARCH"
    ORDER_SCOPE_INCOMPLETE = "ORDER_SCOPE_INCOMPLETE"
    ORDER_OWNERSHIP_UNKNOWN = "ORDER_OWNERSHIP_UNKNOWN"
    ORDER_STATE_UNKNOWN = "ORDER_STATE_UNKNOWN"
    DUPLICATE_ORDER_ID = "DUPLICATE_ORDER_ID"
    PENDING_ORDER_CONFLICT = "PENDING_ORDER_CONFLICT"
    UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"
    SHORT_POSITION = "SHORT_POSITION"
    POSITION_TYPE_UNKNOWN = "POSITION_TYPE_UNKNOWN"
    NEGATIVE_CASH = "NEGATIVE_CASH"
    INCOMPLETE_VALUATION = "INCOMPLETE_VALUATION"
    MISSING_UNLEVERAGED_BUYING_POWER = "MISSING_UNLEVERAGED_BUYING_POWER"
    STALE_PRICE = "STALE_PRICE"
    PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
    PRICE_SOURCE_CONFLICT = "PRICE_SOURCE_CONFLICT"
    RECOMMENDATION_EVIDENCE_UNAVAILABLE = "RECOMMENDATION_EVIDENCE_UNAVAILABLE"
    DECISION_TIME_MISMATCH = "DECISION_TIME_MISMATCH"
    INCOMPLETE_OBSERVATION = "INCOMPLETE_OBSERVATION"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    MISSING_BUYING_POWER = "MISSING_BUYING_POWER"
    INVALID_TARGET_QUANTITY = "INVALID_TARGET_QUANTITY"
    AVAILABLE_TO_SELL = "AVAILABLE_TO_SELL"
    SELL_COST_FLOOR = "SELL_COST_FLOOR"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    INSUFFICIENT_UNLEVERAGED_BUYING_POWER = "INSUFFICIENT_UNLEVERAGED_BUYING_POWER"
    CASH_RESERVE = "CASH_RESERVE"
    MAX_ORDER_NOTIONAL = "MAX_ORDER_NOTIONAL"
    MAX_POSITION_WEIGHT = "MAX_POSITION_WEIGHT"
    MAX_TOTAL_EXPOSURE_WEIGHT = "MAX_TOTAL_EXPOSURE_WEIGHT"
    REBALANCE_DEPENDENCY_BLOCKED = "REBALANCE_DEPENDENCY_BLOCKED"


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Conservative PM limits, separate from strategy/provider decisions."""

    maximum_observation_age: timedelta = timedelta(minutes=5)
    maximum_quote_age: timedelta = timedelta(minutes=5)
    maximum_position_weight: Decimal = Decimal("0.25")
    maximum_total_exposure_weight: Decimal = Decimal("0.75")
    minimum_cash_reserve_weight: Decimal = Decimal("0.10")
    estimated_commission: Decimal = Decimal("1")
    slippage_bps: Decimal = Decimal("5")
    maximum_order_notional: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("maximum_observation_age", "maximum_quote_age"):
            value = getattr(self, name)
            if not isinstance(value, timedelta) or value <= timedelta(0):
                raise ValueError(f"{name} must be a positive timedelta")
        for name in (
            "maximum_position_weight",
            "maximum_total_exposure_weight",
            "minimum_cash_reserve_weight",
            "estimated_commission",
            "slippage_bps",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise TypeError(f"{name} must be a finite Decimal")
        for name in ("maximum_position_weight", "maximum_total_exposure_weight"):
            if not _ZERO < getattr(self, name) <= _ONE:
                raise ValueError(f"{name} must be greater than zero and at most one")
        if not _ZERO <= self.minimum_cash_reserve_weight < _ONE:
            raise ValueError(
                "minimum_cash_reserve_weight must be from zero to below one"
            )
        if self.estimated_commission < _ZERO or self.slippage_bps < _ZERO:
            raise ValueError("commission and slippage must be nonnegative")
        if self.slippage_bps >= _BPS:
            raise ValueError("slippage_bps must be below 10000")
        if self.maximum_order_notional is not None and (
            not isinstance(self.maximum_order_notional, Decimal)
            or not self.maximum_order_notional.is_finite()
            or self.maximum_order_notional <= _ZERO
        ):
            raise ValueError("maximum_order_notional must be positive or None")
        # Reuse the established limits contract for the overlapping allocation,
        # reserve, notional, and commission configuration. PM adds quote age and
        # slippage policy around incomplete broker observations.
        _ = self.shared_risk_limits

    @property
    def shared_risk_limits(self) -> RiskLimits:
        return RiskLimits(
            max_position_percent=self.maximum_position_weight,
            max_total_exposure_percent=self.maximum_total_exposure_weight,
            max_order_notional=self.maximum_order_notional,
            minimum_cash_reserve_percent=self.minimum_cash_reserve_weight,
            allow_fractional_shares=True,
            estimated_commission=self.estimated_commission,
        )

    @property
    def slippage_rate(self) -> Decimal:
        return decimal_multiply(self.slippage_bps, Decimal("0.0001"))


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    recommendation_id: UUID
    symbol: Symbol
    disposition: RiskDisposition
    codes: tuple[RiskCode, ...]
    price: Decimal | None
    order_side: str | None
    order_quantity: Decimal
    estimated_gross_notional: Decimal
    estimated_slippage: Decimal
    estimated_commission: Decimal
    preview_only: bool = True
    dispatch_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.recommendation_id, UUID):
            raise TypeError("recommendation_id must be a UUID")
        if not isinstance(self.symbol, Symbol):
            raise TypeError("symbol must be a Symbol")
        if not isinstance(self.disposition, RiskDisposition):
            raise TypeError("disposition must be RiskDisposition")
        codes = tuple(self.codes)
        if any(not isinstance(item, RiskCode) for item in codes):
            raise TypeError("codes must contain RiskCode values")
        if len(set(codes)) != len(codes):
            raise ValueError("risk codes must be unique")
        for name in (
            "price",
            "order_quantity",
            "estimated_gross_notional",
            "estimated_slippage",
            "estimated_commission",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or value < _ZERO
            ):
                raise ValueError(f"{name} must be nonnegative finite Decimal")
        if self.order_side not in {None, "BUY", "SELL"}:
            raise ValueError("order_side must be BUY, SELL or None")
        if self.disposition is RiskDisposition.NO_ORDER and (
            self.order_side is not None or self.order_quantity != _ZERO
        ):
            raise ValueError("NO_ORDER cannot contain an order")
        if self.disposition is RiskDisposition.PREVIEW_APPROVED and (
            self.order_side is None or self.order_quantity <= _ZERO or codes
        ):
            raise ValueError(
                "preview approval requires a positive quantity and no blockers"
            )
        if self.disposition is RiskDisposition.BLOCKED and (
            not codes or self.order_side is not None or self.order_quantity != _ZERO
        ):
            raise ValueError("blocked evaluations require diagnostics and no order")
        if self.price is not None and self.price <= _ZERO:
            raise ValueError("price must be positive when supplied")
        if self.preview_only is not True or self.dispatch_authorized is not False:
            raise ValueError(
                "PM1 risk evaluations are preview-only and non-dispatchable"
            )
        object.__setattr__(self, "codes", codes)


def _base_codes(
    observation: PortfolioObservation,
    research: MarketResearchInput,
    batch: DecisionBatch,
    recommendation: Recommendation,
    policy: RiskPolicy,
    decision_at: datetime,
) -> list[RiskCode]:
    codes: list[RiskCode] = []
    if observation.account_fingerprint is None:
        codes.append(RiskCode.ACCOUNT_NOT_BOUND)
    if (
        observation.account_fingerprint != observation.observed_account_fingerprint
        or ObservationCondition.ACCOUNT_MISMATCH in observation.conditions
    ):
        codes.append(RiskCode.ACCOUNT_MISMATCH)
    if (
        recommendation.portfolio_snapshot_id != observation.snapshot_id
        or batch.portfolio_snapshot_id != observation.snapshot_id
    ):
        codes.append(RiskCode.SNAPSHOT_MISMATCH)
    if (
        research.portfolio_snapshot_id != observation.snapshot_id
        or recommendation.research_input_id != research.research_input_id
        or batch.research_input_id != research.research_input_id
    ):
        codes.append(RiskCode.RESEARCH_MISMATCH)
    if (
        recommendation.account_fingerprint != observation.account_fingerprint
        or batch.account_fingerprint != observation.account_fingerprint
    ):
        codes.append(RiskCode.BATCH_MISMATCH)
    if recommendation.decision_at != decision_at or batch.decision_at != decision_at:
        codes.append(RiskCode.DECISION_TIME_MISMATCH)
    if (
        decision_at < observation.observed_at
        or decision_at - observation.observed_at > policy.maximum_observation_age
    ):
        codes.append(RiskCode.STALE_OBSERVATION)
    if (
        decision_at < research.observed_at
        or decision_at - research.observed_at > policy.maximum_observation_age
    ):
        codes.append(RiskCode.STALE_RESEARCH)
    if observation.coverage.order_scope is not OrderCoverage.SYNTHETIC_COMPLETE:
        codes.append(RiskCode.ORDER_SCOPE_INCOMPLETE)
    if any(item.ownership is OrderOwnership.UNKNOWN for item in observation.orders):
        codes.append(RiskCode.ORDER_OWNERSHIP_UNKNOWN)
    if ObservationCondition.UNKNOWN_ORDER_STATE in observation.conditions:
        codes.append(RiskCode.ORDER_STATE_UNKNOWN)
    if ObservationCondition.DUPLICATE_ORDER_ID in observation.conditions:
        codes.append(RiskCode.DUPLICATE_ORDER_ID)
    if any(item.quantity < _ZERO for item in observation.positions):
        codes.append(RiskCode.SHORT_POSITION)
    if any(item.position_type.value == "UNKNOWN" for item in observation.positions):
        codes.append(RiskCode.POSITION_TYPE_UNKNOWN)
    if any(not item.supported for item in observation.positions):
        codes.append(RiskCode.UNSUPPORTED_ASSET)
    if (
        observation.cash is None
        or observation.locally_computed_equity is None
        or observation.broker_reported_equity is None
    ):
        codes.append(RiskCode.INCOMPLETE_VALUATION)
    if observation.cash is not None and observation.cash < _ZERO:
        codes.append(RiskCode.NEGATIVE_CASH)
    if observation.unleveraged_buying_power is None:
        codes.append(RiskCode.MISSING_UNLEVERAGED_BUYING_POWER)
    if observation.buying_power is None:
        codes.append(RiskCode.MISSING_BUYING_POWER)
    if ObservationCondition.BROKER_EQUITY_DIFFERS_FROM_LOCAL in observation.conditions:
        codes.append(RiskCode.INCOMPLETE_VALUATION)
    if not recommendation.evidence_available or not research.evidence_available:
        codes.append(RiskCode.RECOMMENDATION_EVIDENCE_UNAVAILABLE)
    if not observation.preview_eligible:
        codes.append(RiskCode.INCOMPLETE_OBSERVATION)
    if not observation.coverage.pagination_complete:
        codes.append(RiskCode.PAGINATION_INCOMPLETE)
    for position in observation.positions:
        if position.quantity == _ZERO:
            continue
        if position.current_price is None or position.price_observed_at is None:
            codes.append(RiskCode.PRICE_UNAVAILABLE)
        elif (
            position.price_observed_at > decision_at
            or decision_at - position.price_observed_at > policy.maximum_quote_age
        ):
            codes.append(RiskCode.STALE_PRICE)
    return list(dict.fromkeys(codes))


def _price_for(
    observation: PortfolioObservation,
    research: MarketResearchInput,
    symbol: Symbol,
) -> tuple[Decimal | None, datetime | None, RiskCode | None]:
    position = next(
        (item for item in observation.positions if item.symbol == symbol), None
    )
    research_quote = research.quote_for(symbol)
    if position is not None:
        if position.current_price is None or position.price_observed_at is None:
            return None, None, RiskCode.PRICE_UNAVAILABLE
        if research_quote is not None and (
            research_quote.price != position.current_price
            or research_quote.observed_at != position.price_observed_at
        ):
            return None, None, RiskCode.PRICE_SOURCE_CONFLICT
        return position.current_price, position.price_observed_at, None
    if research_quote is None:
        return None, None, RiskCode.PRICE_UNAVAILABLE
    return research_quote.price, research_quote.observed_at, None


def _evaluate_one(
    observation: PortfolioObservation,
    research: MarketResearchInput,
    batch: DecisionBatch,
    recommendation: Recommendation,
    policy: RiskPolicy,
    decision_at: datetime,
    *,
    current_quantities: dict[Symbol, Decimal],
    current_exposure: list[Decimal],
    local_equity: Decimal | None,
    starting_cash: Decimal | None,
    buy_budget: Decimal | None,
    reserved_buy_cash: list[Decimal],
) -> RiskEvaluation:
    if recommendation.action in {Action.HOLD, Action.NO_ACTION}:
        return RiskEvaluation(
            recommendation.recommendation_id,
            recommendation.symbol,
            RiskDisposition.NO_ORDER,
            (RiskCode.NO_ORDER_REQUESTED,),
            None,
            None,
            _ZERO,
            _ZERO,
            _ZERO,
            _ZERO,
        )
    codes = _base_codes(
        observation, research, batch, recommendation, policy, decision_at
    )
    position = next(
        (
            item
            for item in observation.positions
            if item.symbol == recommendation.symbol
        ),
        None,
    )
    if any(
        order.symbol == recommendation.symbol and order.pending
        for order in observation.orders
    ):
        codes.append(RiskCode.PENDING_ORDER_CONFLICT)
    price, quote_at, price_error = _price_for(
        observation, research, recommendation.symbol
    )
    if price_error is not None:
        codes.append(price_error)
    if quote_at is not None and (
        quote_at > decision_at or decision_at - quote_at > policy.maximum_quote_age
    ):
        codes.append(RiskCode.STALE_PRICE)
    if not recommendation.evidence_available:
        codes.append(RiskCode.RECOMMENDATION_EVIDENCE_UNAVAILABLE)
    current = current_quantities.get(recommendation.symbol, _ZERO)
    target = recommendation.target_quantity
    order_side: str | None = None
    order_quantity = _ZERO
    gross = _ZERO
    slippage = _ZERO
    commission = _ZERO
    disposition = RiskDisposition.BLOCKED
    if target is None or target < _ZERO:
        codes.append(RiskCode.INVALID_TARGET_QUANTITY)
    elif recommendation.action is Action.SELL and (target != _ZERO or current <= _ZERO):
        codes.append(RiskCode.INVALID_TARGET_QUANTITY)
    elif recommendation.action is Action.REDUCE and not (_ZERO < target < current):
        codes.append(RiskCode.INVALID_TARGET_QUANTITY)
    elif recommendation.action is Action.BUY and target <= current:
        codes.append(RiskCode.INVALID_TARGET_QUANTITY)
    elif recommendation.action is Action.REBALANCE and target == current:
        disposition = RiskDisposition.NO_ORDER
        return RiskEvaluation(
            recommendation.recommendation_id,
            recommendation.symbol,
            disposition,
            (RiskCode.NO_ORDER_REQUESTED,),
            price,
            None,
            _ZERO,
            _ZERO,
            _ZERO,
            _ZERO,
        )
    elif target is not None and target != current:
        quantity_delta = decimal_subtract(target, current)
        order_quantity = (
            quantity_delta if quantity_delta > _ZERO else quantity_delta.copy_abs()
        )
        order_side = "BUY" if quantity_delta > _ZERO else "SELL"
        if price is None:
            codes.append(RiskCode.PRICE_UNAVAILABLE)
        else:
            gross = decimal_multiply(order_quantity, price)
            slippage = decimal_multiply(gross, policy.slippage_rate)
            commission = policy.estimated_commission
            if (
                policy.maximum_order_notional is not None
                and gross > policy.maximum_order_notional
            ):
                codes.append(RiskCode.MAX_ORDER_NOTIONAL)
            if order_side == "SELL":
                available = _ZERO if position is None else position.available_to_sell
                if order_quantity > available:
                    codes.append(RiskCode.AVAILABLE_TO_SELL)
                if gross <= decimal_sum([slippage, commission]):
                    codes.append(RiskCode.SELL_COST_FLOOR)
            else:
                if (
                    starting_cash is None
                    or observation.unleveraged_buying_power is None
                    or observation.buying_power is None
                ):
                    codes.append(RiskCode.MISSING_UNLEVERAGED_BUYING_POWER)
                elif buy_budget is None:
                    codes.append(RiskCode.INSUFFICIENT_CASH)
                else:
                    outflow = decimal_sum([gross, slippage, commission])
                    projected_reserved = decimal_sum([reserved_buy_cash[0], outflow])
                    if projected_reserved > buy_budget:
                        codes.append(RiskCode.INSUFFICIENT_CASH)
                    if projected_reserved > observation.unleveraged_buying_power:
                        codes.append(RiskCode.INSUFFICIENT_UNLEVERAGED_BUYING_POWER)
                    if projected_reserved > observation.buying_power:
                        codes.append(RiskCode.INSUFFICIENT_UNLEVERAGED_BUYING_POWER)
                if local_equity is None or price is None:
                    codes.append(RiskCode.INCOMPLETE_VALUATION)
                else:
                    resulting_value = decimal_multiply(target, price)
                    max_position_value = decimal_multiply(
                        local_equity, policy.maximum_position_weight
                    )
                    projected_exposure = decimal_sum(
                        [current_exposure[0], decimal_multiply(order_quantity, price)]
                    )
                    max_exposure = decimal_multiply(
                        local_equity, policy.maximum_total_exposure_weight
                    )
                    if resulting_value > max_position_value:
                        codes.append(RiskCode.MAX_POSITION_WEIGHT)
                    if projected_exposure > max_exposure:
                        codes.append(RiskCode.MAX_TOTAL_EXPOSURE_WEIGHT)
            if not codes:
                disposition = RiskDisposition.PREVIEW_APPROVED
                if order_side == "BUY":
                    reserved_buy_cash[0] = decimal_sum(
                        [reserved_buy_cash[0], gross, slippage, commission]
                    )
                delta_exposure = decimal_multiply(order_quantity, price)
                if order_side == "BUY":
                    current_exposure[0] = decimal_sum(
                        [current_exposure[0], delta_exposure]
                    )
                current_quantities[recommendation.symbol] = target
    unique_codes = tuple(dict.fromkeys(codes))
    return RiskEvaluation(
        recommendation.recommendation_id,
        recommendation.symbol,
        disposition,
        unique_codes,
        price,
        order_side if disposition is RiskDisposition.PREVIEW_APPROVED else None,
        order_quantity if disposition is RiskDisposition.PREVIEW_APPROVED else _ZERO,
        gross if disposition is RiskDisposition.PREVIEW_APPROVED else _ZERO,
        slippage if disposition is RiskDisposition.PREVIEW_APPROVED else _ZERO,
        commission if disposition is RiskDisposition.PREVIEW_APPROVED else _ZERO,
    )


def evaluate_recommendations(
    observation: PortfolioObservation,
    research: MarketResearchInput,
    batch: DecisionBatch,
    policy: RiskPolicy,
    *,
    decision_at: datetime,
) -> tuple[RiskEvaluation, ...]:
    """Independently evaluate recommendations with deterministic reservations."""
    if not isinstance(observation, PortfolioObservation):
        raise TypeError("observation must be PortfolioObservation")
    if not isinstance(research, MarketResearchInput):
        raise TypeError("research must be MarketResearchInput")
    if not isinstance(batch, DecisionBatch):
        raise TypeError("batch must be DecisionBatch")
    if not isinstance(policy, RiskPolicy):
        raise TypeError("policy must be RiskPolicy")
    stamp = normalize_utc(decision_at, "decision_at")
    positions = {item.symbol: item for item in observation.positions}
    local_equity = observation.locally_computed_equity
    starting_cash = observation.cash
    unleveraged_buying_power = observation.unleveraged_buying_power
    available_cash = (
        min(starting_cash, observation.buying_power, unleveraged_buying_power)
        if starting_cash is not None
        and observation.buying_power is not None
        and unleveraged_buying_power is not None
        else None
    )
    if available_cash is None or local_equity is None:
        buy_budget = None
    else:
        reserve = decimal_multiply(local_equity, policy.minimum_cash_reserve_weight)
        buy_budget = max(_ZERO, decimal_sum([available_cash, decimal_negate(reserve)]))
    quantities = {symbol: position.quantity for symbol, position in positions.items()}
    exposure = decimal_sum(
        [
            item.market_value
            for item in observation.positions
            if item.market_value is not None and item.quantity > _ZERO
        ]
    )
    reserved_buy_cash = [_ZERO]
    current_exposure = [exposure]
    original = batch.recommendations

    def direction(item: Recommendation) -> int:
        current = quantities.get(item.symbol, _ZERO)
        target = item.target_quantity
        if item.action in {Action.SELL, Action.REDUCE}:
            return 0
        if item.action is Action.BUY:
            return 1
        if item.action is Action.REBALANCE and target is not None and target != current:
            return 0 if target < current else 1
        return 2

    # Actual sell legs are evaluated first. Buy exposure still starts from the
    # observed portfolio, so hypothetical sells never create risk headroom.
    evaluated: dict[UUID, RiskEvaluation] = {}
    sells = tuple(item for item in original if direction(item) == 0)
    buys = tuple(item for item in original if direction(item) == 1)
    no_orders = tuple(item for item in original if direction(item) == 2)
    for recommendation in sells:
        evaluated[recommendation.recommendation_id] = _evaluate_one(
            observation,
            research,
            batch,
            recommendation,
            policy,
            stamp,
            current_quantities=quantities,
            current_exposure=current_exposure,
            local_equity=local_equity,
            starting_cash=starting_cash,
            buy_budget=buy_budget,
            reserved_buy_cash=reserved_buy_cash,
        )
    rebalance_active = any(item.action is Action.REBALANCE for item in original)
    blocked_rebalance_sell = rebalance_active and any(
        evaluated[item.recommendation_id].disposition is RiskDisposition.BLOCKED
        for item in sells
    )
    for recommendation in buys:
        if blocked_rebalance_sell:
            evaluated[recommendation.recommendation_id] = RiskEvaluation(
                recommendation_id=recommendation.recommendation_id,
                symbol=recommendation.symbol,
                disposition=RiskDisposition.BLOCKED,
                codes=(RiskCode.REBALANCE_DEPENDENCY_BLOCKED,),
                price=None,
                order_side=None,
                order_quantity=_ZERO,
                estimated_gross_notional=_ZERO,
                estimated_slippage=_ZERO,
                estimated_commission=_ZERO,
            )
            continue
        evaluated[recommendation.recommendation_id] = _evaluate_one(
            observation,
            research,
            batch,
            recommendation,
            policy,
            stamp,
            current_quantities=quantities,
            current_exposure=current_exposure,
            local_equity=local_equity,
            starting_cash=starting_cash,
            buy_budget=buy_budget,
            reserved_buy_cash=reserved_buy_cash,
        )
    for recommendation in no_orders:
        evaluated[recommendation.recommendation_id] = _evaluate_one(
            observation,
            research,
            batch,
            recommendation,
            policy,
            stamp,
            current_quantities=quantities,
            current_exposure=current_exposure,
            local_equity=local_equity,
            starting_cash=starting_cash,
            buy_budget=buy_budget,
            reserved_buy_cash=reserved_buy_cash,
        )
    return tuple(evaluated[item.recommendation_id] for item in original)
