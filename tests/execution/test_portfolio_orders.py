from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import (
    ExecutionInstruction,
    InconsistentPortfolioOrderBatchResultError,
    InconsistentPortfolioOrderSourceError,
    InvalidPortfolioOrderBatchRequestError,
    OrderEngine,
    OrderEngineError,
    OrderEventType,
    PortfolioOrderBatchRequest,
    PortfolioOrderBatchStatus,
    PortfolioOrderCreationError,
    PortfolioOrderDiagnosticCode,
    PortfolioOrderEngineCopyError,
    PortfolioOrderOrchestrator,
)
from trading_bot.portfolio import MetadataEntry
from trading_bot.risk import (
    PortfolioRiskBatchRequest,
    PortfolioRiskOrchestrator,
    PortfolioRiskPrice,
    RiskContext,
    RiskLimits,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def limits(**changes: object) -> RiskLimits:
    values: dict[str, object] = {
        "max_position_percent": Decimal("1"),
        "max_total_exposure_percent": Decimal("1"),
        "minimum_cash_reserve_percent": Decimal("0"),
        "max_order_notional": None,
        "max_new_position_percent": None,
    }
    values.update(changes)
    return RiskLimits(**values)  # type: ignore[arg-type]


def proposal(
    identifier: int, symbol: Symbol, side: OrderSide, quantity: str
) -> TradeProposal:
    return TradeProposal(
        UUID(int=identifier), symbol, side, Decimal(quantity), NOW, "fixture"
    )


def risk_batch(
    proposals: tuple[TradeProposal, ...],
    *,
    cash: str = "1000",
    risk_limits: RiskLimits | None = None,
):  # type: ignore[no-untyped-def]
    context = RiskContext(
        Decimal(cash), Decimal(cash), {}, None, Decimal("0"), True, NOW
    )
    request = PortfolioRiskBatchRequest(
        UUID(int=50),
        proposals,
        context,
        tuple(PortfolioRiskPrice(item.symbol, Decimal("100")) for item in proposals),
        risk_limits or limits(),
    )
    return PortfolioRiskOrchestrator().evaluate(request)


def instruction() -> ExecutionInstruction:
    return ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, NOW)


def request(batch=None, *, metadata=()):  # type: ignore[no-untyped-def]
    return PortfolioOrderBatchRequest(
        UUID(int=100),
        batch or risk_batch((proposal(1, SPY, OrderSide.BUY, "2"),)),
        instruction(),
        metadata,
    )


def test_approved_buy_creates_pending_order_and_created_event() -> None:
    orchestrator = PortfolioOrderOrchestrator()
    result = orchestrator.create(request())
    assert result.status is PortfolioOrderBatchStatus.CREATED
    assert result.source_evaluation_ordinals == (0,)
    order = result.orders[0]
    assert order.status is OrderStatus.PENDING
    assert order.request.symbol == SPY
    assert order.request.side is OrderSide.BUY
    assert order.request.quantity == Decimal("2")
    assert order.request.order_type is OrderType.MARKET
    assert order.request.time_in_force is TimeInForce.DAY
    assert order.request.submitted_at == NOW
    assert order.request.limit_price is None
    assert result.created_events[0].event_type is OrderEventType.CREATED
    assert result.created_events[0].order_id == order.request.order_id
    assert tuple(orchestrator.engine.orders.values()) == result.orders
    assert orchestrator.engine.get_events() == result.created_events


def test_approved_sell_preserves_side_and_quantity() -> None:
    sell = proposal(1, SPY, OrderSide.SELL, "1")
    position = Position(SPY, Decimal("2"), Decimal("50"))
    context = RiskContext(
        Decimal("800"),
        Decimal("1000"),
        {SPY: position},
        None,
        Decimal("200"),
        True,
        NOW,
    )
    batch = PortfolioRiskOrchestrator().evaluate(
        PortfolioRiskBatchRequest(
            UUID(int=50),
            (sell,),
            context,
            (PortfolioRiskPrice(SPY, Decimal("100")),),
            limits(),
        )
    )
    result = PortfolioOrderOrchestrator().create(request(batch))
    assert result.orders[0].request.side is OrderSide.SELL
    assert result.orders[0].request.quantity == Decimal("1")


def test_resized_quantity_is_used_exactly() -> None:
    batch = risk_batch((proposal(1, SPY, OrderSide.BUY, "20"),), cash="250")
    assert batch.evaluations[0].decision.approved_quantity == Decimal("2.5")
    result = PortfolioOrderOrchestrator().create(request(batch))
    assert result.orders[0].request.quantity == Decimal("2.5")


def test_mixed_batch_filters_rejection_without_reordering() -> None:
    batch = risk_batch(
        (
            proposal(1, SPY, OrderSide.BUY, "8"),
            proposal(2, QQQ, OrderSide.BUY, "8"),
        ),
        cash="800",
    )
    result = PortfolioOrderOrchestrator().create(request(batch))
    assert result.source_evaluation_ordinals == (0,)
    assert result.orders[0].request.symbol == SPY
    assert tuple(item.code for item in result.diagnostics) == (
        PortfolioOrderDiagnosticCode.REJECTED_EVALUATIONS_SKIPPED,
    )


def test_resized_only_partial_has_no_skipped_diagnostic() -> None:
    batch = risk_batch((proposal(1, SPY, OrderSide.BUY, "20"),), cash="250")
    result = PortfolioOrderOrchestrator().create(request(batch))
    assert result.diagnostics == ()


def test_all_rejected_and_no_action_do_not_replace_engine() -> None:
    rejected = risk_batch(
        (proposal(1, SPY, OrderSide.BUY, "1"),),
        risk_limits=limits(allow_buying=False),
    )
    empty = risk_batch(())
    orchestrator = PortfolioOrderOrchestrator()
    original = orchestrator.engine
    rejected_result = orchestrator.create(request(rejected))
    assert orchestrator.engine is original
    assert rejected_result.status is PortfolioOrderBatchStatus.NO_ACTION
    assert rejected_result.diagnostics[0].code is (
        PortfolioOrderDiagnosticCode.REJECTED_EVALUATIONS_SKIPPED
    )
    empty_result = orchestrator.create(request(empty))
    assert orchestrator.engine is original
    assert empty_result.diagnostics[0].code is PortfolioOrderDiagnosticCode.NO_ACTION


def test_instruction_and_chronology_validation_happens_before_engine_copy() -> None:
    batch = risk_batch((proposal(1, SPY, OrderSide.BUY, "1"),))
    with pytest.raises(InvalidPortfolioOrderBatchRequestError):
        PortfolioOrderBatchRequest(
            UUID(int=100),
            batch,
            ExecutionInstruction(OrderType.LIMIT, TimeInForce.DAY, NOW, Decimal("100")),
        )


def test_request_validates_uuid_and_defensively_copies_metadata() -> None:
    batch = risk_batch((proposal(1, SPY, OrderSide.BUY, "1"),))
    with pytest.raises(InvalidPortfolioOrderBatchRequestError, match="UUID"):
        PortfolioOrderBatchRequest("not-a-uuid", batch, instruction())  # type: ignore[arg-type]
    values = [MetadataEntry("source", "fixture")]
    item = PortfolioOrderBatchRequest(
        UUID(int=100),
        batch,
        instruction(),
        values,  # type: ignore[arg-type]
    )
    values.clear()
    assert item.metadata == (MetadataEntry("source", "fixture"),)
    with pytest.raises(InvalidPortfolioOrderBatchRequestError, match="unique"):
        PortfolioOrderBatchRequest(
            UUID(int=100),
            batch,
            instruction(),
            (MetadataEntry("source", "one"), MetadataEntry("source", "two")),
        )
    with pytest.raises(InvalidPortfolioOrderBatchRequestError):
        PortfolioOrderBatchRequest(
            UUID(int=100),
            batch,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.GOOD_TIL_CANCELED, NOW),
        )
    with pytest.raises(InvalidPortfolioOrderBatchRequestError, match="timestamp"):
        PortfolioOrderBatchRequest(
            UUID(int=100),
            batch,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, NOW + timedelta(1)),
        )


def test_metadata_affects_result_but_not_order_or_event_ids() -> None:
    batch = risk_batch((proposal(1, SPY, OrderSide.BUY, "1"),))
    first = PortfolioOrderOrchestrator().create(
        request(batch, metadata=(MetadataEntry("source", "one"),))
    )
    second = PortfolioOrderOrchestrator().create(
        request(batch, metadata=(MetadataEntry("source", "two"),))
    )
    assert first.orders[0].request.order_id == second.orders[0].request.order_id
    assert first.created_events[0].event_id == second.created_events[0].event_id
    assert first.result_id != second.result_id


def test_equal_request_and_engine_state_repeat_exactly() -> None:
    item = request()
    first_orchestrator = PortfolioOrderOrchestrator()
    second_orchestrator = PortfolioOrderOrchestrator()
    first = first_orchestrator.create(item)
    second = second_orchestrator.create(item)
    assert first == second
    assert first_orchestrator.engine.orders == second_orchestrator.engine.orders
    assert first.result_id.version == 5
    assert first.orders[0].request.order_id.version == 5
    assert first.created_events[0].event_id.version == 5


def test_second_identical_batch_on_advanced_engine_fails_before_copy() -> None:
    orchestrator = PortfolioOrderOrchestrator()
    item = request()
    orchestrator.create(item)
    advanced = orchestrator.engine
    with pytest.raises(InconsistentPortfolioOrderSourceError, match="collides"):
        orchestrator.create(item)
    assert orchestrator.engine is advanced


def test_collision_is_rejected_before_engine_copy() -> None:
    class CopyGuardEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("collision path must not copy")

    item = request()
    expected = PortfolioOrderOrchestrator().create(item)
    engine = CopyGuardEngine()
    engine.create_order(
        item.risk_batch.evaluations[0].decision,
        item.instruction,
        order_id=expected.orders[0].request.order_id,
        event_id=expected.created_events[0].event_id,
    )
    orchestrator = PortfolioOrderOrchestrator(engine)
    with pytest.raises(InconsistentPortfolioOrderSourceError, match="collides"):
        orchestrator.create(item)


def test_later_order_failure_leaves_authoritative_engine_unchanged() -> None:
    class FailingEngine(OrderEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def create_order(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            self.calls += 1
            if self.calls == 2:
                raise OrderEngineError("defensive failure")
            return super().create_order(*args, **kwargs)

    batch = risk_batch(
        (
            proposal(1, SPY, OrderSide.BUY, "1"),
            proposal(2, QQQ, OrderSide.BUY, "1"),
        )
    )
    original = FailingEngine()
    orchestrator = PortfolioOrderOrchestrator(original)
    with pytest.raises(PortfolioOrderCreationError) as captured:
        orchestrator.create(request(batch))
    assert isinstance(captured.value.__cause__, OrderEngineError)
    assert orchestrator.engine is original
    assert original.orders == {}


def test_engine_copy_failure_is_focused_and_atomic() -> None:
    class UncopyableEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise RuntimeError("copy disabled")

    engine = UncopyableEngine()
    orchestrator = PortfolioOrderOrchestrator(engine)
    with pytest.raises(PortfolioOrderEngineCopyError) as captured:
        orchestrator.create(request())
    assert isinstance(captured.value.__cause__, RuntimeError)
    assert orchestrator.engine is engine


def test_shadow_reconciliation_failure_is_atomic() -> None:
    class MismatchingEngine(OrderEngine):
        def create_order(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            created = super().create_order(*args, **kwargs)
            return Order(request=created.request, status=OrderStatus.SUBMITTED)

    engine = MismatchingEngine()
    orchestrator = PortfolioOrderOrchestrator(engine)
    with pytest.raises(InconsistentPortfolioOrderBatchResultError):
        orchestrator.create(request())
    assert orchestrator.engine is engine
    assert engine.orders == {}


def test_existing_engine_state_is_preserved_as_prefix() -> None:
    seed_batch = risk_batch((proposal(9, QQQ, OrderSide.BUY, "1"),))
    seed_request = PortfolioOrderBatchRequest(UUID(int=900), seed_batch, instruction())
    orchestrator = PortfolioOrderOrchestrator()
    seed = orchestrator.create(seed_request)
    old_engine = orchestrator.engine
    old_orders = tuple(old_engine.orders.values())
    old_events = old_engine.get_events()
    created = orchestrator.create(request())
    assert orchestrator.engine is not old_engine
    assert tuple(orchestrator.engine.orders.values())[:1] == old_orders
    assert orchestrator.engine.get_events()[:1] == old_events
    assert tuple(orchestrator.engine.orders.values())[-1:] == created.orders
    assert seed.result_id != created.result_id
