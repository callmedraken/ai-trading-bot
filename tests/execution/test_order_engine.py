from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest

from trading_bot.domain import (
    OrderFill,
    OrderSide,
    OrderStatus,
    OrderType,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import (
    DuplicateEventError,
    DuplicateFillError,
    DuplicateOrderError,
    ExecutionInstruction,
    FillMismatchError,
    InvalidEventTimeError,
    InvalidOrderTransitionError,
    InvalidRiskDecisionError,
    OrderEngine,
    OrderEventType,
    OrderNotFoundError,
    OverfillError,
)
from trading_bot.risk import (
    RiskDecision,
    RiskOutcome,
    RiskReason,
    RiskReasonCode,
)

T0 = datetime(2026, 1, 2, 12, tzinfo=UTC)
T1 = T0 + timedelta(minutes=1)
T2 = T0 + timedelta(minutes=2)
T3 = T0 + timedelta(minutes=3)
SPY = Symbol("SPY")


def decision(
    quantity: str = "2.5",
    outcome: RiskOutcome = RiskOutcome.APPROVED,
    *,
    proposal_at: datetime = T0,
    evaluated_at: datetime = T0,
) -> RiskDecision:
    desired_quantity = (
        Decimal("5") if outcome is RiskOutcome.RESIZED else Decimal(quantity)
    )
    proposal = TradeProposal.create(
        symbol=SPY,
        side=OrderSide.BUY,
        desired_quantity=desired_quantity,
        created_at=proposal_at,
        reason="test",
    )
    reasons = (
        (RiskReason(RiskReasonCode.CASH_CAPACITY, "cash constrained"),)
        if outcome is not RiskOutcome.APPROVED
        else ()
    )
    approved = Decimal("0") if outcome is RiskOutcome.REJECTED else Decimal(quantity)
    return RiskDecision(proposal, outcome, approved, reasons, evaluated_at)


def instruction(created_at: datetime = T0) -> ExecutionInstruction:
    return ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, created_at)


def create_and_submit(
    engine: OrderEngine, *, quantity: str = "2.5", at: datetime = T1
) -> UUID:
    order = engine.create_order(decision(quantity), instruction())
    engine.submit_order(order.request.order_id, at)
    return order.request.order_id


def fill(
    order_id: UUID,
    *,
    quantity: str = "1",
    price: str = "100",
    filled_at: datetime = T2,
    fill_id: UUID | None = None,
    symbol: Symbol = SPY,
    side: OrderSide = OrderSide.BUY,
) -> OrderFill:
    return OrderFill(
        fill_id=fill_id or uuid4(),
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        commission=Decimal("0"),
        filled_at=filled_at,
    )


def snapshot(engine: OrderEngine) -> tuple[object, ...]:
    return (
        dict(engine.orders),
        engine.get_events(),
        {order_id: engine.get_fills(order_id) for order_id in engine.orders},
    )


def test_approved_and_resized_decisions_create_pending_orders() -> None:
    engine = OrderEngine()
    approved = engine.create_order(decision(), instruction())
    resized = engine.create_order(
        decision("2", RiskOutcome.RESIZED), instruction(), order_id=uuid4()
    )
    assert approved.status is OrderStatus.PENDING
    assert approved.request.quantity == Decimal("2.5")
    assert resized.request.quantity == Decimal("2")
    assert approved.request.submitted_at == T0
    assert [event.event_type for event in engine.get_events()] == [
        OrderEventType.CREATED,
        OrderEventType.CREATED,
    ]


def test_rejected_decision_cannot_create_order() -> None:
    engine = OrderEngine()
    with pytest.raises(InvalidRiskDecisionError):
        engine.create_order(decision(outcome=RiskOutcome.REJECTED), instruction())
    assert snapshot(engine) == ({}, (), {})


def test_creation_accepts_fixed_ids_and_rejects_duplicate_order_or_event() -> None:
    engine = OrderEngine()
    order_id = uuid4()
    event_id = uuid4()
    engine.create_order(decision(), instruction(), order_id=order_id, event_id=event_id)
    before = snapshot(engine)
    with pytest.raises(DuplicateOrderError):
        engine.create_order(decision(), instruction(), order_id=order_id)
    assert snapshot(engine) == before
    with pytest.raises(DuplicateEventError):
        engine.create_order(decision(), instruction(), event_id=event_id)
    assert snapshot(engine) == before


@pytest.mark.parametrize(
    ("proposal_at", "evaluated_at", "created_at"),
    [(T1, T0, T1), (T0, T1, T0)],
)
def test_creation_rejects_inconsistent_chronology_atomically(
    proposal_at: datetime, evaluated_at: datetime, created_at: datetime
) -> None:
    engine = OrderEngine()
    with pytest.raises(InvalidEventTimeError):
        engine.create_order(
            decision(proposal_at=proposal_at, evaluated_at=evaluated_at),
            instruction(created_at),
        )
    assert snapshot(engine) == ({}, (), {})


def test_pending_order_submission_and_equal_timestamp() -> None:
    engine = OrderEngine()
    order = engine.create_order(decision(), instruction())
    submitted = engine.submit_order(order.request.order_id, T0)
    assert submitted.status is OrderStatus.SUBMITTED
    assert engine.get_events()[-1].occurred_at == T0


def test_duplicate_submission_and_early_submission_are_atomic() -> None:
    engine = OrderEngine()
    order = engine.create_order(decision(), instruction())
    before = snapshot(engine)
    with pytest.raises(InvalidEventTimeError):
        engine.submit_order(order.request.order_id, T0 - timedelta(seconds=1))
    assert snapshot(engine) == before
    engine.submit_order(order.request.order_id, T1)
    before = snapshot(engine)
    with pytest.raises(InvalidOrderTransitionError):
        engine.submit_order(order.request.order_id, T2)
    assert snapshot(engine) == before


def test_single_full_fill_and_event_reference() -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine, quantity="2")
    accepted = fill(order_id, quantity="2")
    order = engine.apply_fill(accepted)
    assert order.status is OrderStatus.FILLED
    assert order.average_fill_price == Decimal("100")
    assert engine.get_fills(order_id) == (accepted,)
    assert engine.get_events(order_id)[-1].fill_id == accepted.fill_id


def test_multiple_fractional_fills_calculate_weighted_average() -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine, quantity="2.5")
    first = engine.apply_fill(fill(order_id, quantity="1", price="100"))
    second = engine.apply_fill(
        fill(order_id, quantity="1.5", price="110", filled_at=T3)
    )
    assert first.status is OrderStatus.PARTIALLY_FILLED
    assert second.status is OrderStatus.FILLED
    assert second.average_fill_price == Decimal("106")
    assert second.filled_quantity == Decimal("2.5")


def test_global_duplicate_fill_is_atomic_even_for_another_order() -> None:
    engine = OrderEngine()
    first_order = create_and_submit(engine, quantity="1")
    second_order = create_and_submit(engine, quantity="1")
    fill_id = uuid4()
    engine.apply_fill(fill(first_order, fill_id=fill_id))
    before = snapshot(engine)
    with pytest.raises(DuplicateFillError):
        engine.apply_fill(fill(second_order, fill_id=fill_id))
    assert snapshot(engine) == before


def test_duplicate_event_id_on_fill_is_atomic() -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine)
    used_event_id = engine.get_events()[0].event_id
    before = snapshot(engine)
    with pytest.raises(DuplicateEventError):
        engine.apply_fill(fill(order_id), event_id=used_event_id)
    assert snapshot(engine) == before


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"symbol": Symbol("QQQ")}, FillMismatchError),
        ({"side": OrderSide.SELL}, FillMismatchError),
        ({"quantity": "3"}, OverfillError),
        ({"filled_at": T0}, InvalidEventTimeError),
    ],
)
def test_invalid_fill_is_atomic(
    change: dict[str, object], error: type[Exception]
) -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine)
    before = snapshot(engine)
    with pytest.raises(error):
        engine.apply_fill(fill(order_id, **change))  # type: ignore[arg-type]
    assert snapshot(engine) == before


def test_unknown_pending_and_terminal_fill_rejections() -> None:
    engine = OrderEngine()
    with pytest.raises(OrderNotFoundError):
        engine.apply_fill(fill(uuid4()))
    pending = engine.create_order(decision(), instruction())
    with pytest.raises(InvalidOrderTransitionError):
        engine.apply_fill(fill(pending.request.order_id))
    order_id = create_and_submit(engine, quantity="1")
    engine.apply_fill(fill(order_id))
    with pytest.raises(InvalidOrderTransitionError):
        engine.apply_fill(fill(order_id, filled_at=T3))


def test_fill_cannot_precede_latest_fill_but_equal_time_is_allowed() -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine, quantity="3")
    engine.apply_fill(fill(order_id, filled_at=T2))
    before = snapshot(engine)
    with pytest.raises(InvalidEventTimeError):
        engine.apply_fill(fill(order_id, filled_at=T1))
    assert snapshot(engine) == before
    order = engine.apply_fill(fill(order_id, filled_at=T2))
    assert order.filled_quantity == Decimal("2")


def test_cancel_pending_submitted_and_partially_filled() -> None:
    engine = OrderEngine()
    pending = engine.create_order(decision(), instruction())
    canceled_pending = engine.cancel_order(pending.request.order_id, T1)
    assert canceled_pending.status is OrderStatus.CANCELED

    submitted_id = create_and_submit(engine)
    assert engine.cancel_order(submitted_id, T2).status is OrderStatus.CANCELED

    partial_id = create_and_submit(engine)
    engine.apply_fill(fill(partial_id))
    canceled = engine.cancel_order(partial_id, T3, "user request")
    assert canceled.status is OrderStatus.CANCELED
    assert canceled.filled_quantity == Decimal("1")
    assert canceled.rejection_reason is None
    assert engine.get_events(partial_id)[-1].reason == "user request"


def test_reject_pending_or_submitted_propagates_reason() -> None:
    engine = OrderEngine()
    pending = engine.create_order(decision(), instruction())
    rejected = engine.reject_order(pending.request.order_id, T1, "venue rejected")
    assert rejected.status is OrderStatus.REJECTED
    assert rejected.rejection_reason == "venue rejected"
    assert engine.get_events(pending.request.order_id)[-1].reason == "venue rejected"

    submitted_id = create_and_submit(engine)
    assert (
        engine.reject_order(submitted_id, T2, "invalid request").rejection_reason
        == "invalid request"
    )


def test_blank_rejection_reason_is_atomic() -> None:
    engine = OrderEngine()
    pending = engine.create_order(decision(), instruction())
    before = snapshot(engine)
    with pytest.raises(ValueError, match="nonblank"):
        engine.reject_order(pending.request.order_id, T1, " ")
    assert snapshot(engine) == before


def test_reject_partial_and_terminal_transitions_are_forbidden() -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine)
    engine.apply_fill(fill(order_id))
    before = snapshot(engine)
    with pytest.raises(InvalidOrderTransitionError):
        engine.reject_order(order_id, T3, "late reject")
    assert snapshot(engine) == before
    engine.cancel_order(order_id, T3)
    with pytest.raises(InvalidOrderTransitionError):
        engine.cancel_order(order_id, T3)


@pytest.mark.parametrize("operation", ["cancel", "reject"])
def test_cancel_or_reject_before_latest_event_is_atomic(operation: str) -> None:
    engine = OrderEngine()
    order_id = create_and_submit(engine, at=T2)
    before = snapshot(engine)
    with pytest.raises(InvalidEventTimeError):
        if operation == "cancel":
            engine.cancel_order(order_id, T1)
        else:
            engine.reject_order(order_id, T1, "rejected")
    assert snapshot(engine) == before


def test_duplicate_event_id_on_transition_is_atomic() -> None:
    engine = OrderEngine()
    order = engine.create_order(decision(), instruction())
    duplicate = engine.get_events()[0].event_id
    before = snapshot(engine)
    with pytest.raises(DuplicateEventError):
        engine.submit_order(order.request.order_id, T1, event_id=duplicate)
    assert snapshot(engine) == before


def test_global_events_filter_in_order_and_snapshots_are_read_only() -> None:
    engine = OrderEngine()
    first = engine.create_order(decision(), instruction())
    second = engine.create_order(decision(), instruction())
    engine.submit_order(first.request.order_id, T1)
    engine.cancel_order(second.request.order_id, T1)
    global_events = engine.get_events()
    first_events = engine.get_events(first.request.order_id)
    assert first_events == tuple(
        event for event in global_events if event.order_id == first.request.order_id
    )
    assert isinstance(global_events, tuple)
    assert isinstance(engine.orders, MappingProxyType)
    with pytest.raises(TypeError):
        engine.orders[uuid4()] = first  # type: ignore[index]


def test_fixed_ids_and_timestamps_produce_equal_results() -> None:
    order_id = uuid4()
    created_event = uuid4()
    submitted_event = uuid4()
    engines = (OrderEngine(), OrderEngine())
    results = []
    for engine in engines:
        order = engine.create_order(
            decision(),
            instruction(),
            order_id=order_id,
            event_id=created_event,
        )
        engine.submit_order(order_id, T1, event_id=submitted_event)
        results.append((order, engine.get_events()))
    assert results[0] == results[1]
