from datetime import UTC, datetime, timedelta, timezone
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
    InconsistentPaperSubmissionBatchResultError,
    InconsistentPaperSubmissionSourceError,
    InvalidPaperSubmissionBatchRequestError,
    OrderEngine,
    OrderEngineError,
    OrderEventType,
    PaperOrderSubmissionError,
    PaperOrderSubmitter,
    PaperSubmissionBatchRequest,
    PaperSubmissionBatchStatus,
    PaperSubmissionDiagnosticCode,
    PaperSubmissionEngineCopyError,
    PaperSubmissionEventCollisionError,
    PortfolioOrderBatchRequest,
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
LATER = NOW + timedelta(minutes=5)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _proposal(
    identifier: int, symbol: Symbol, side: OrderSide = OrderSide.BUY
) -> TradeProposal:
    return TradeProposal(UUID(int=identifier), symbol, side, Decimal("1"), NOW, "test")


def _order_batch(
    proposals: tuple[TradeProposal, ...] | None = None,
    *,
    engine: OrderEngine | None = None,
):  # type: ignore[no-untyped-def]
    proposals = proposals if proposals is not None else (_proposal(1, SPY),)
    sell_symbols = tuple(
        item.symbol for item in proposals if item.side is OrderSide.SELL
    )
    positions = {
        symbol: Position(symbol, Decimal("1"), Decimal("100"))
        for symbol in sell_symbols
    }
    exposure = Decimal("100") * len(positions)
    context = RiskContext(
        Decimal("1000"),
        Decimal("1000") + exposure,
        positions,
        None,
        exposure,
        True,
        NOW,
    )
    limits = RiskLimits(
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        minimum_cash_reserve_percent=Decimal("0"),
    )
    risk = PortfolioRiskOrchestrator().evaluate(
        PortfolioRiskBatchRequest(
            UUID(int=50),
            proposals,
            context,
            tuple(
                PortfolioRiskPrice(item.symbol, Decimal("100")) for item in proposals
            ),
            limits,
        )
    )
    orchestrator = PortfolioOrderOrchestrator(engine)
    result = orchestrator.create(
        PortfolioOrderBatchRequest(
            UUID(int=100),
            risk,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, NOW),
        )
    )
    return result, orchestrator.engine


def _request(order_batch=None, *, submitted_at=LATER, metadata=()):  # type: ignore[no-untyped-def]
    if order_batch is None:
        order_batch, _ = _order_batch()
    return PaperSubmissionBatchRequest(
        UUID(int=200), order_batch, submitted_at, metadata
    )


def test_one_buy_submits_exactly_without_financial_changes() -> None:
    source, engine = _order_batch()
    original = source.orders[0]
    submitter = PaperOrderSubmitter(engine)
    result = submitter.submit(_request(source))
    assert result.status is PaperSubmissionBatchStatus.SUBMITTED
    submitted = result.orders[0]
    assert submitted.status is OrderStatus.SUBMITTED
    assert submitted.request == original.request
    assert submitted.filled_quantity == original.filled_quantity
    assert submitted.average_fill_price == original.average_fill_price
    event = result.submitted_events[0]
    assert event.event_type is OrderEventType.SUBMITTED
    assert event.order_id == original.request.order_id
    assert event.occurred_at == LATER
    assert event.fill_id is None and event.reason is None
    assert submitter.engine.get_fills(original.request.order_id) == ()


def test_sell_and_mixed_source_order_are_preserved() -> None:
    proposals = (
        _proposal(1, SPY, OrderSide.SELL),
        _proposal(2, QQQ),
    )
    source, engine = _order_batch(proposals)
    result = PaperOrderSubmitter(engine).submit(_request(source))
    assert tuple(item.request.order_id for item in result.orders) == tuple(
        item.request.order_id for item in source.orders
    )
    assert tuple(item.order_id for item in result.submitted_events) == tuple(
        item.request.order_id for item in source.orders
    )
    assert result.orders[0].request.side is OrderSide.SELL
    assert result.orders[1].request.side is OrderSide.BUY


def test_equal_and_later_timestamps_and_utc_normalization() -> None:
    source, engine = _order_batch()
    equal = PaperOrderSubmitter(engine).submit(_request(source, submitted_at=NOW))
    assert equal.submitted_events[0].occurred_at == NOW
    source, engine = _order_batch()
    local = LATER.astimezone(timezone(timedelta(hours=-7)))
    item = _request(source, submitted_at=local)
    assert item.submitted_at == LATER
    assert (
        PaperOrderSubmitter(engine).submit(item).submitted_events[0].occurred_at
        == LATER
    )


def test_request_validation_and_earlier_timestamp() -> None:
    source, _ = _order_batch()
    with pytest.raises(InvalidPaperSubmissionBatchRequestError):
        PaperSubmissionBatchRequest(UUID(int=1), source, datetime(2026, 1, 1))
    with pytest.raises(InvalidPaperSubmissionBatchRequestError, match="UUID"):
        PaperSubmissionBatchRequest("bad", source, NOW)  # type: ignore[arg-type]
    values = [MetadataEntry("source", "test")]
    item = _request(source, metadata=values)
    values.clear()
    assert item.metadata == (MetadataEntry("source", "test"),)
    with pytest.raises(InconsistentPaperSubmissionSourceError, match="precedes"):
        PaperOrderSubmitter(_order_batch()[1]).submit(
            _request(source, submitted_at=NOW - timedelta(seconds=1))
        )


def test_no_action_does_not_copy_or_replace_engine() -> None:
    source, _ = _order_batch(())

    class CopyGuardEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("NO_ACTION must not copy")

    engine = CopyGuardEngine()
    submitter = PaperOrderSubmitter(engine)
    result = submitter.submit(_request(source))
    assert submitter.engine is engine
    assert result.status is PaperSubmissionBatchStatus.NO_ACTION
    assert result.orders == () and result.submitted_events == ()
    assert result.diagnostics[0].code is PaperSubmissionDiagnosticCode.NO_ACTION


def test_missing_mismatched_and_nonpending_sources_fail_closed() -> None:
    source, engine = _order_batch()
    with pytest.raises(InconsistentPaperSubmissionSourceError, match="not managed"):
        PaperOrderSubmitter(OrderEngine()).submit(_request(source))
    other_source, other_engine = _order_batch()
    other_engine.cancel_order(other_source.orders[0].request.order_id, NOW)
    with pytest.raises(InconsistentPaperSubmissionSourceError, match="does not equal"):
        PaperOrderSubmitter(other_engine).submit(_request(source))
    submitter = PaperOrderSubmitter(engine)
    submitter.submit(_request(source))
    with pytest.raises(InconsistentPaperSubmissionSourceError, match="PENDING"):
        submitter.submit(_request(source))
    assert other_source.orders[0] == source.orders[0]


def test_deterministic_identity_metadata_and_repeatability() -> None:
    source1, engine1 = _order_batch()
    source2, engine2 = _order_batch()
    first = PaperOrderSubmitter(engine1).submit(_request(source1))
    second = PaperOrderSubmitter(engine2).submit(_request(source2))
    assert first == second
    assert first.result_id.version == 5
    assert first.submitted_events[0].event_id.version == 5
    with_metadata = PaperOrderSubmitter(_order_batch()[1]).submit(
        _request(source1, metadata=(MetadataEntry("source", "metadata"),))
    )
    assert with_metadata.result_id != first.result_id
    assert (
        with_metadata.submitted_events[0].event_id == first.submitted_events[0].event_id
    )


def test_event_collision_is_detected_before_copy() -> None:
    source, engine = _order_batch()
    expected = PaperOrderSubmitter(engine).submit(_request(source))

    class CopyGuardEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("collision must be detected before copy")

    source, guarded = _order_batch()
    guarded.__class__ = CopyGuardEngine
    guarded.create_order(
        source.request.risk_batch.evaluations[0].decision,
        source.request.instruction,
        order_id=UUID(int=999),
        event_id=expected.submitted_events[0].event_id,
    )
    with pytest.raises(PaperSubmissionEventCollisionError):
        PaperOrderSubmitter(guarded).submit(_request(source))


def test_copy_and_later_submission_failures_are_atomic() -> None:
    class UncopyableEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise RuntimeError("disabled")

    source, engine = _order_batch()
    engine.__class__ = UncopyableEngine
    submitter = PaperOrderSubmitter(engine)
    with pytest.raises(PaperSubmissionEngineCopyError):
        submitter.submit(_request(source))
    assert submitter.engine is engine

    class FailingEngine(OrderEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def submit_order(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            self.calls += 1
            if self.calls == 2:
                raise OrderEngineError("failure")
            return super().submit_order(*args, **kwargs)

    source, engine = _order_batch(
        (_proposal(1, SPY), _proposal(2, QQQ)), engine=FailingEngine()
    )
    submitter = PaperOrderSubmitter(engine)
    before_orders = engine.orders
    before_events = engine.get_events()
    with pytest.raises(PaperOrderSubmissionError):
        submitter.submit(_request(source))
    assert submitter.engine is engine
    assert engine.orders == before_orders
    assert engine.get_events() == before_events


def test_reconciliation_failure_preserves_authoritative_engine() -> None:
    class MismatchingEngine(OrderEngine):
        def submit_order(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            submitted = super().submit_order(*args, **kwargs)
            return Order(request=submitted.request, status=OrderStatus.PENDING)

    source, engine = _order_batch(engine=MismatchingEngine())
    submitter = PaperOrderSubmitter(engine)
    with pytest.raises(InconsistentPaperSubmissionBatchResultError):
        submitter.submit(_request(source))
    assert submitter.engine is engine
    assert engine.get_order(source.orders[0].request.order_id) == source.orders[0]


def test_existing_state_and_events_are_preserved() -> None:
    source, engine = _order_batch((_proposal(1, SPY), _proposal(2, QQQ)))
    old_order_ids = tuple(engine.orders)
    old_events = engine.get_events()
    submitter = PaperOrderSubmitter(engine)
    result = submitter.submit(_request(source))
    assert tuple(submitter.engine.orders) == old_order_ids
    assert submitter.engine.get_events()[: len(old_events)] == old_events
    assert submitter.engine.get_events()[len(old_events) :] == result.submitted_events
    assert all(submitter.engine.get_fills(order_id) == () for order_id in old_order_ids)
