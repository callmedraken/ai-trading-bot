"""Deterministic, broker-independent order lifecycle management."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID, uuid4

from trading_bot.domain import (
    Order,
    OrderFill,
    OrderRequest,
    OrderStatus,
)
from trading_bot.domain._validation import normalize_utc
from trading_bot.execution.exceptions import (
    DuplicateEventError,
    DuplicateFillError,
    DuplicateOrderError,
    FillMismatchError,
    InvalidEventTimeError,
    InvalidOrderTransitionError,
    InvalidRiskDecisionError,
    OrderNotFoundError,
    OverfillError,
)
from trading_bot.execution.models import (
    ExecutionInstruction,
    OrderEvent,
    OrderEventType,
)
from trading_bot.risk import RiskDecision, RiskOutcome


class OrderEngine:
    """Manage immutable order snapshots, fills, and lifecycle audit events."""

    def __init__(self) -> None:
        self._orders: dict[UUID, Order] = {}
        self._fills_by_order: dict[UUID, list[OrderFill]] = {}
        self._events: list[OrderEvent] = []
        self._event_ids: set[UUID] = set()
        self._fill_ids: set[UUID] = set()

    @property
    def orders(self) -> Mapping[UUID, Order]:
        return MappingProxyType(dict(self._orders))

    def create_order(
        self,
        decision: RiskDecision,
        instruction: ExecutionInstruction,
        *,
        order_id: UUID | None = None,
        event_id: UUID | None = None,
    ) -> Order:
        """Create a pending order from a successful risk decision."""
        if not isinstance(decision, RiskDecision):
            raise TypeError("decision must be a RiskDecision")
        if not isinstance(instruction, ExecutionInstruction):
            raise TypeError("instruction must be an ExecutionInstruction")
        if decision.outcome is RiskOutcome.REJECTED:
            raise InvalidRiskDecisionError(
                "rejected risk decisions cannot create orders"
            )
        if decision.approved_quantity <= Decimal("0"):
            raise InvalidRiskDecisionError(
                "approved quantity must be greater than zero"
            )
        if decision.evaluated_at < decision.proposal.created_at:
            raise InvalidEventTimeError(
                "risk evaluation cannot precede proposal creation"
            )
        if instruction.created_at < decision.evaluated_at:
            raise InvalidEventTimeError(
                "order request creation cannot precede risk evaluation"
            )

        new_order_id = self._prepare_order_id(order_id)
        new_event_id = self._prepare_event_id(event_id)
        request = OrderRequest(
            order_id=new_order_id,
            symbol=decision.proposal.symbol,
            side=decision.proposal.side,
            order_type=instruction.order_type,
            quantity=decision.approved_quantity,
            time_in_force=instruction.time_in_force,
            # In this version submitted_at records request creation. Actual
            # submission time is represented by the SUBMITTED lifecycle event.
            submitted_at=instruction.created_at,
            limit_price=instruction.limit_price,
        )
        order = Order(request=request)
        event = OrderEvent(
            event_id=new_event_id,
            order_id=new_order_id,
            event_type=OrderEventType.CREATED,
            occurred_at=instruction.created_at,
        )

        self._orders[new_order_id] = order
        self._fills_by_order[new_order_id] = []
        self._append_event(event)
        return order

    def submit_order(
        self,
        order_id: UUID,
        submitted_at: datetime,
        *,
        event_id: UUID | None = None,
    ) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.PENDING:
            self._invalid_transition(order, "submit")
        occurred_at = self._prepare_transition_time(order_id, submitted_at)
        new_event_id = self._prepare_event_id(event_id)
        updated = Order(
            request=order.request,
            status=OrderStatus.SUBMITTED,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
        )
        event = OrderEvent(
            new_event_id, order_id, OrderEventType.SUBMITTED, occurred_at
        )
        self._orders[order_id] = updated
        self._append_event(event)
        return updated

    def apply_fill(self, fill: OrderFill, *, event_id: UUID | None = None) -> Order:
        if not isinstance(fill, OrderFill):
            raise TypeError("fill must be an OrderFill")
        if fill.fill_id in self._fill_ids:
            raise DuplicateFillError(f"fill {fill.fill_id} has already been applied")
        order = self._require_order(fill.order_id)
        if order.status not in {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}:
            self._invalid_transition(order, "fill")
        if fill.symbol != order.request.symbol:
            raise FillMismatchError("fill symbol does not match the order symbol")
        if fill.side is not order.request.side:
            raise FillMismatchError("fill side does not match the order side")
        self._prepare_transition_time(fill.order_id, fill.filled_at)
        new_event_id = self._prepare_event_id(event_id)

        new_quantity = order.filled_quantity + fill.quantity
        if new_quantity > order.request.quantity:
            raise OverfillError(
                f"fill quantity {fill.quantity} exceeds remaining quantity "
                f"{order.remaining_quantity}"
            )
        previous_weighted = (
            order.filled_quantity * order.average_fill_price
            if order.average_fill_price is not None
            else Decimal("0")
        )
        new_average = (previous_weighted + fill.quantity * fill.price) / new_quantity
        new_status = (
            OrderStatus.FILLED
            if new_quantity == order.request.quantity
            else OrderStatus.PARTIALLY_FILLED
        )
        updated = Order(
            request=order.request,
            status=new_status,
            filled_quantity=new_quantity,
            average_fill_price=new_average,
        )
        event_type = (
            OrderEventType.FILLED
            if new_status is OrderStatus.FILLED
            else OrderEventType.PARTIALLY_FILLED
        )
        event = OrderEvent(
            new_event_id,
            fill.order_id,
            event_type,
            fill.filled_at,
            fill_id=fill.fill_id,
        )

        self._orders[fill.order_id] = updated
        self._fills_by_order[fill.order_id].append(fill)
        self._fill_ids.add(fill.fill_id)
        self._append_event(event)
        return updated

    def cancel_order(
        self,
        order_id: UUID,
        canceled_at: datetime,
        reason: str | None = None,
        *,
        event_id: UUID | None = None,
    ) -> Order:
        order = self._require_order(order_id)
        if order.status not in {
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        }:
            self._invalid_transition(order, "cancel")
        occurred_at = self._prepare_transition_time(order_id, canceled_at)
        new_event_id = self._prepare_event_id(event_id)
        updated = Order(
            request=order.request,
            status=OrderStatus.CANCELED,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
        )
        event = OrderEvent(
            new_event_id,
            order_id,
            OrderEventType.CANCELED,
            occurred_at,
            reason=reason,
        )
        self._orders[order_id] = updated
        self._append_event(event)
        return updated

    def reject_order(
        self,
        order_id: UUID,
        rejected_at: datetime,
        reason: str,
        *,
        event_id: UUID | None = None,
    ) -> Order:
        order = self._require_order(order_id)
        if order.status not in {OrderStatus.PENDING, OrderStatus.SUBMITTED}:
            self._invalid_transition(order, "reject")
        occurred_at = self._prepare_transition_time(order_id, rejected_at)
        new_event_id = self._prepare_event_id(event_id)
        updated = Order(
            request=order.request,
            status=OrderStatus.REJECTED,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
            rejection_reason=reason,
        )
        event = OrderEvent(
            new_event_id,
            order_id,
            OrderEventType.REJECTED,
            occurred_at,
            reason=reason,
        )
        self._orders[order_id] = updated
        self._append_event(event)
        return updated

    def get_order(self, order_id: UUID) -> Order | None:
        return self._orders.get(order_id)

    def get_fills(self, order_id: UUID) -> tuple[OrderFill, ...]:
        self._require_order(order_id)
        return tuple(self._fills_by_order[order_id])

    def get_events(self, order_id: UUID | None = None) -> tuple[OrderEvent, ...]:
        if order_id is None:
            return tuple(self._events)
        self._require_order(order_id)
        return tuple(event for event in self._events if event.order_id == order_id)

    def _require_order(self, order_id: UUID) -> Order:
        if not isinstance(order_id, UUID):
            raise TypeError("order_id must be a UUID")
        try:
            return self._orders[order_id]
        except KeyError as error:
            raise OrderNotFoundError(f"order {order_id} is not managed") from error

    def _prepare_order_id(self, order_id: UUID | None) -> UUID:
        candidate = uuid4() if order_id is None else order_id
        if not isinstance(candidate, UUID):
            raise TypeError("order_id must be a UUID")
        if candidate in self._orders:
            raise DuplicateOrderError(f"order {candidate} is already managed")
        return candidate

    def _prepare_event_id(self, event_id: UUID | None) -> UUID:
        candidate = uuid4() if event_id is None else event_id
        if not isinstance(candidate, UUID):
            raise TypeError("event_id must be a UUID")
        if candidate in self._event_ids:
            raise DuplicateEventError(f"event {candidate} has already been recorded")
        return candidate

    def _prepare_transition_time(
        self, order_id: UUID, occurred_at: datetime
    ) -> datetime:
        normalized = normalize_utc(occurred_at, "transition timestamp")
        latest = next(
            event.occurred_at
            for event in reversed(self._events)
            if event.order_id == order_id
        )
        if normalized < latest:
            raise InvalidEventTimeError(
                f"transition timestamp {normalized.isoformat()} precedes latest event "
                f"timestamp {latest.isoformat()}"
            )
        return normalized

    def _append_event(self, event: OrderEvent) -> None:
        self._events.append(event)
        self._event_ids.add(event.event_id)

    @staticmethod
    def _invalid_transition(order: Order, action: str) -> None:
        raise InvalidOrderTransitionError(
            f"cannot {action} order {order.request.order_id} from {order.status.value}"
        )
