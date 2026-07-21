from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

import trading_bot.execution.paper_fill_application as application_module
from trading_bot.domain import (
    Order,
    OrderFill,
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
    InconsistentPaperFillApplicationResultError,
    InvalidPaperFillApplicationBatchRequestError,
    OrderEngine,
    OrderEventType,
    PaperFillApplicationBatchRequest,
    PaperFillApplicationBatchStatus,
    PaperFillApplicationDiagnosticCode,
    PaperFillApplicationEngineCopyError,
    PaperFillApplicationEventCollisionError,
    PaperFillApplicationLedgerCopyError,
    PaperFillApplier,
    PaperFillBatchRequest,
    PaperFillGenerator,
    PaperFillLedgerApplyError,
    PaperFillPolicy,
    PaperFillPrice,
    PaperOrderSubmitter,
    PaperSubmissionBatchRequest,
    PortfolioOrderBatchRequest,
    PortfolioOrderOrchestrator,
)
from trading_bot.ledger import PaperLedger
from trading_bot.portfolio import MetadataEntry
from trading_bot.risk import (
    PortfolioRiskBatchRequest,
    PortfolioRiskOrchestrator,
    PortfolioRiskPrice,
    RiskContext,
    RiskLimits,
)

NOW = datetime(2026, 7, 21, 20, tzinfo=UTC)
SUBMITTED_AT = NOW + timedelta(minutes=1)
FILLED_AT = NOW + timedelta(minutes=2)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _proposal(identifier: int, symbol: Symbol, side: OrderSide) -> TradeProposal:
    return TradeProposal(UUID(int=identifier), symbol, side, Decimal("2"), NOW, "test")


def _pipeline(
    proposals: tuple[TradeProposal, ...] | None = None,
    *,
    price: str = "100",
    commission: str = "0",
):  # type: ignore[no-untyped-def]
    proposals = (
        proposals if proposals is not None else (_proposal(1, SPY, OrderSide.BUY),)
    )
    sell_symbols = tuple(
        item.symbol for item in proposals if item.side is OrderSide.SELL
    )
    risk_positions = {
        symbol: Position(symbol, Decimal("2"), Decimal("100"))
        for symbol in sell_symbols
    }
    exposure = Decimal("200") * len(risk_positions)
    risk = PortfolioRiskOrchestrator().evaluate(
        PortfolioRiskBatchRequest(
            UUID(int=50),
            proposals,
            RiskContext(
                Decimal("1000"),
                Decimal("1000") + exposure,
                risk_positions,
                None,
                exposure,
                True,
                NOW,
            ),
            tuple(
                PortfolioRiskPrice(item.symbol, Decimal("100")) for item in proposals
            ),
            RiskLimits(
                max_position_percent=Decimal("1"),
                max_total_exposure_percent=Decimal("1"),
                minimum_cash_reserve_percent=Decimal("0"),
            ),
        )
    )
    orderer = PortfolioOrderOrchestrator()
    orders = orderer.create(
        PortfolioOrderBatchRequest(
            UUID(int=100),
            risk,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, NOW),
        )
    )
    submitter = PaperOrderSubmitter(orderer.engine)
    submission = submitter.submit(
        PaperSubmissionBatchRequest(UUID(int=200), orders, SUBMITTED_AT)
    )
    fill_request = PaperFillBatchRequest(
        UUID(int=300),
        submission,
        FILLED_AT,
        tuple(
            PaperFillPrice(order.request.order_id, Decimal(price))
            for order in submission.orders
        ),
        PaperFillPolicy(Decimal("0"), Decimal(commission)),
    )
    fills = PaperFillGenerator().generate(fill_request)
    return fills, submitter.engine


def _request(fill_batch, metadata=()):  # type: ignore[no-untyped-def]
    return PaperFillApplicationBatchRequest(UUID(int=400), fill_batch, metadata)


def _seed_position(
    ledger: PaperLedger,
    symbol: Symbol,
    quantity: str = "2",
    price: str = "100",
) -> OrderFill:
    fill = OrderFill(
        uuid4(),
        uuid4(),
        symbol,
        OrderSide.BUY,
        Decimal(quantity),
        Decimal(price),
        Decimal("0"),
        NOW,
    )
    ledger.apply_fill(fill)
    return fill


def test_buy_applies_identical_fill_to_engine_and_ledger() -> None:
    batch, engine = _pipeline(commission="1")
    ledger = PaperLedger(Decimal("1000"))
    old_engine = engine
    old_ledger = ledger
    applier = PaperFillApplier(engine, ledger)
    result = applier.apply(_request(batch))
    assert result.status is PaperFillApplicationBatchStatus.APPLIED
    evaluation = result.evaluations[0]
    fill = batch.fills[0]
    assert evaluation.fill == fill
    assert evaluation.updated_order.status is OrderStatus.FILLED
    assert evaluation.updated_order.filled_quantity == fill.quantity
    assert evaluation.updated_order.average_fill_price == fill.price
    assert evaluation.fill_event.event_type is OrderEventType.FILLED
    assert evaluation.fill_event.fill_id == fill.fill_id
    assert applier.engine.get_fills(fill.order_id) == (fill,)
    assert applier.ledger.fills == (fill,)
    assert evaluation.ledger_cash_after == Decimal("799")
    assert evaluation.ledger_position_after == Position(
        SPY, Decimal("2"), Decimal("100.5")
    )
    assert applier.engine is not old_engine and applier.ledger is not old_ledger
    assert old_engine.get_fills(fill.order_id) == () and old_ledger.fills == ()


def test_sell_commission_realized_pnl_and_full_liquidation() -> None:
    batch, engine = _pipeline(
        (_proposal(1, SPY, OrderSide.SELL),), price="110", commission="2"
    )
    ledger = PaperLedger(Decimal("1000"))
    prior = _seed_position(ledger, SPY)
    result = PaperFillApplier(engine, ledger).apply(_request(batch))
    evaluation = result.evaluations[0]
    assert evaluation.ledger_cash_after == Decimal("1018")
    assert evaluation.ledger_position_after is None
    assert evaluation.ledger_realized_profit_loss_after == Decimal("18")
    assert result.request.fill_batch.fills[0].commission == Decimal("2")
    assert ledger.fills == (prior,)


def test_mixed_order_preserves_order_and_cumulative_audit() -> None:
    batch, engine = _pipeline(
        (_proposal(1, SPY, OrderSide.SELL), _proposal(2, QQQ, OrderSide.BUY))
    )
    ledger = PaperLedger(Decimal("1000"))
    _seed_position(ledger, SPY)
    result = PaperFillApplier(engine, ledger).apply(_request(batch))
    assert tuple(item.fill for item in result.evaluations) == batch.fills
    assert tuple(item.ledger_cash_after for item in result.evaluations) == (
        Decimal("1000"),
        Decimal("800"),
    )
    assert result.evaluations[0].ledger_position_after is None
    assert result.evaluations[1].ledger_position_after == Position(
        QQQ, Decimal("2"), Decimal("100")
    )


def test_request_validation_and_metadata_copy() -> None:
    batch, _ = _pipeline()
    with pytest.raises(InvalidPaperFillApplicationBatchRequestError, match="UUID"):
        PaperFillApplicationBatchRequest("bad", batch)  # type: ignore[arg-type]
    values = [MetadataEntry("source", "test")]
    item = _request(batch, values)
    values.clear()
    assert item.metadata == (MetadataEntry("source", "test"),)
    with pytest.raises(InvalidPaperFillApplicationBatchRequestError, match="unique"):
        _request(batch, (MetadataEntry("a", "1"), MetadataEntry("a", "2")))


def test_no_action_copies_neither_component() -> None:
    batch, _ = _pipeline(())

    class UncopyableEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("NO_ACTION must not copy engine")

    class UncopyableLedger(PaperLedger):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("NO_ACTION must not copy ledger")

    engine = UncopyableEngine()
    ledger = UncopyableLedger(Decimal("1000"))
    applier = PaperFillApplier(engine, ledger)
    result = applier.apply(_request(batch))
    assert applier.engine is engine and applier.ledger is ledger
    assert result.status is PaperFillApplicationBatchStatus.NO_ACTION
    assert result.evaluations == ()
    assert result.diagnostics[0].code is PaperFillApplicationDiagnosticCode.NO_ACTION
    assert result.pre_engine_state_id == result.post_engine_state_id
    assert result.pre_ledger_state_id == result.post_ledger_state_id


def test_insufficient_cash_discards_engine_and_ledger_shadows() -> None:
    batch, engine = _pipeline()
    ledger = PaperLedger(Decimal("100"))
    applier = PaperFillApplier(engine, ledger)
    before_orders = engine.orders
    before_events = engine.get_events()
    with pytest.raises(PaperFillLedgerApplyError):
        applier.apply(_request(batch))
    assert applier.engine is engine and applier.ledger is ledger
    assert engine.orders == before_orders and engine.get_events() == before_events
    assert ledger.cash == Decimal("100") and ledger.fills == ()


def test_later_fill_failure_discards_all_shadow_work() -> None:
    batch, engine = _pipeline(
        (_proposal(1, SPY, OrderSide.BUY), _proposal(2, QQQ, OrderSide.BUY))
    )
    ledger = PaperLedger(Decimal("250"))
    applier = PaperFillApplier(engine, ledger)
    with pytest.raises(PaperFillLedgerApplyError):
        applier.apply(_request(batch))
    assert all(
        order.status is OrderStatus.SUBMITTED for order in engine.orders.values()
    )
    assert ledger.cash == Decimal("250") and ledger.fills == ()


def test_engine_and_ledger_copy_failures_are_distinct() -> None:
    batch, engine = _pipeline()

    class UncopyableEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise RuntimeError("engine copy disabled")

    engine.__class__ = UncopyableEngine
    ledger = PaperLedger(Decimal("1000"))
    with pytest.raises(PaperFillApplicationEngineCopyError):
        PaperFillApplier(engine, ledger).apply(_request(batch))

    batch, engine = _pipeline()

    class UncopyableLedger(PaperLedger):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise RuntimeError("ledger copy disabled")

    ledger = PaperLedger(Decimal("1000"))
    ledger.__class__ = UncopyableLedger
    with pytest.raises(PaperFillApplicationLedgerCopyError):
        PaperFillApplier(engine, ledger).apply(_request(batch))


def test_event_collision_is_rejected_before_copy(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    batch, engine = _pipeline()
    existing_id = engine.get_events()[0].event_id

    class CopyGuardEngine(OrderEngine):
        def __deepcopy__(self, memo):  # noqa: ANN001, ANN204
            raise AssertionError("collision must be detected before copying")

    engine.__class__ = CopyGuardEngine
    monkeypatch.setattr(application_module, "uuid5", lambda *_: existing_id)
    with pytest.raises(PaperFillApplicationEventCollisionError):
        PaperFillApplier(engine, PaperLedger(Decimal("1000"))).apply(_request(batch))


def test_reconciliation_failure_is_atomic() -> None:
    batch, engine = _pipeline()

    class MismatchingEngine(OrderEngine):
        def apply_fill(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            filled = super().apply_fill(*args, **kwargs)
            return Order(request=filled.request, status=OrderStatus.SUBMITTED)

    engine.__class__ = MismatchingEngine
    ledger = PaperLedger(Decimal("1000"))
    applier = PaperFillApplier(engine, ledger)
    with pytest.raises(InconsistentPaperFillApplicationResultError):
        applier.apply(_request(batch))
    assert applier.engine is engine and applier.ledger is ledger
    assert engine.get_fills(batch.fills[0].order_id) == () and ledger.fills == ()


def test_identity_repeatability_metadata_and_state_ids() -> None:
    batch1, engine1 = _pipeline()
    batch2, engine2 = _pipeline()
    first_applier = PaperFillApplier(engine1, PaperLedger(Decimal("1000")))
    second_applier = PaperFillApplier(engine2, PaperLedger(Decimal("1000")))
    first = first_applier.apply(_request(batch1))
    second = second_applier.apply(_request(batch2))
    assert first == second
    assert first.result_id.version == 5
    assert first.pre_engine_state_id.version == 5
    assert first.pre_ledger_state_id.version == 5
    assert first.evaluations[0].fill_event.event_id.version == 5

    batch, engine = _pipeline()
    with_metadata = PaperFillApplier(engine, PaperLedger(Decimal("1000"))).apply(
        _request(batch, (MetadataEntry("source", "test"),))
    )
    assert with_metadata.result_id != first.result_id
    assert (
        with_metadata.evaluations[0].fill_event.event_id
        == first.evaluations[0].fill_event.event_id
    )
