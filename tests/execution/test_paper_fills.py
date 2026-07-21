from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import (
    OrderSide,
    OrderType,
    Position,
    Symbol,
    TimeInForce,
    TradeProposal,
)
from trading_bot.execution import (
    ExecutionInstruction,
    InconsistentPaperFillBatchResultError,
    InconsistentPaperFillSourceError,
    InvalidPaperFillBatchRequestError,
    PaperFillBatchRequest,
    PaperFillBatchResult,
    PaperFillBatchStatus,
    PaperFillDiagnosticCode,
    PaperFillGenerator,
    PaperFillPolicy,
    PaperFillPrice,
    PaperOrderSubmitter,
    PaperSubmissionBatchRequest,
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
SUBMITTED_AT = NOW + timedelta(minutes=1)
FILLED_AT = NOW + timedelta(minutes=2)
SPY = Symbol("SPY")
QQQ = Symbol("QQQ")


def _proposal(identifier: int, symbol: Symbol, side: OrderSide) -> TradeProposal:
    return TradeProposal(UUID(int=identifier), symbol, side, Decimal("2"), NOW, "test")


def _submission(
    proposals: tuple[TradeProposal, ...] | None = None,
):  # type: ignore[no-untyped-def]
    proposals = (
        proposals if proposals is not None else (_proposal(1, SPY, OrderSide.BUY),)
    )
    sell_symbols = tuple(
        item.symbol for item in proposals if item.side is OrderSide.SELL
    )
    positions = {
        symbol: Position(symbol, Decimal("2"), Decimal("100"))
        for symbol in sell_symbols
    }
    exposure = Decimal("200") * len(positions)
    context = RiskContext(
        Decimal("1000"),
        Decimal("1000") + exposure,
        positions,
        None,
        exposure,
        True,
        NOW,
    )
    risk = PortfolioRiskOrchestrator().evaluate(
        PortfolioRiskBatchRequest(
            UUID(int=50),
            proposals,
            context,
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
    order_orchestrator = PortfolioOrderOrchestrator()
    order_batch = order_orchestrator.create(
        PortfolioOrderBatchRequest(
            UUID(int=100),
            risk,
            ExecutionInstruction(OrderType.MARKET, TimeInForce.DAY, NOW),
        )
    )
    submitter = PaperOrderSubmitter(order_orchestrator.engine)
    submission = submitter.submit(
        PaperSubmissionBatchRequest(UUID(int=200), order_batch, SUBMITTED_AT)
    )
    return submission, submitter.engine


def _request(
    submission=None,
    *,
    prices=None,
    filled_at=FILLED_AT,
    policy=None,
    metadata=(),
):  # type: ignore[no-untyped-def]
    if submission is None:
        submission, _ = _submission()
    if prices is None:
        prices = tuple(
            PaperFillPrice(order.request.order_id, Decimal("100"))
            for order in submission.orders
        )
    return PaperFillBatchRequest(
        UUID(int=300),
        submission,
        filled_at,
        prices,
        policy or PaperFillPolicy(),
        metadata,
    )


def test_buy_fill_is_full_unapplied_and_zero_slippage() -> None:
    submission, engine = _submission()
    before_orders = engine.orders
    before_events = engine.get_events()
    result = PaperFillGenerator().generate(_request(submission))
    assert result.status is PaperFillBatchStatus.GENERATED
    assert result.evaluations[0].source_order_ordinal == 0
    assert result.evaluations[0].reference_price == Decimal("100")
    assert result.evaluations[0].slippage_amount == Decimal("0")
    fill = result.fills[0]
    assert fill.quantity == submission.orders[0].request.quantity
    assert fill.price == Decimal("100")
    assert fill.commission == Decimal("0")
    assert fill.filled_at == FILLED_AT
    assert engine.orders == before_orders
    assert engine.get_events() == before_events
    assert engine.get_fills(fill.order_id) == ()


def test_mixed_buy_sell_slippage_commission_and_ordering() -> None:
    submission, _ = _submission(
        (_proposal(1, SPY, OrderSide.SELL), _proposal(2, QQQ, OrderSide.BUY))
    )
    result = PaperFillGenerator().generate(
        _request(
            submission,
            policy=PaperFillPolicy(Decimal("100"), Decimal("1.25")),
        )
    )
    assert tuple(fill.side for fill in result.fills) == (
        OrderSide.SELL,
        OrderSide.BUY,
    )
    assert tuple(fill.price for fill in result.fills) == (
        Decimal("99"),
        Decimal("101"),
    )
    assert tuple(item.slippage_amount for item in result.evaluations) == (
        Decimal("1"),
        Decimal("1"),
    )
    assert all(fill.commission == Decimal("1.25") for fill in result.fills)


def test_equal_later_and_normalized_timestamps() -> None:
    submission, _ = _submission()
    equal = PaperFillGenerator().generate(_request(submission, filled_at=SUBMITTED_AT))
    assert equal.fills[0].filled_at == SUBMITTED_AT
    local = FILLED_AT.astimezone(timezone(timedelta(hours=-7)))
    item = _request(submission, filled_at=local)
    assert item.filled_at == FILLED_AT
    assert PaperFillGenerator().generate(item).fills[0].filled_at == FILLED_AT
    with pytest.raises(InconsistentPaperFillSourceError, match="precedes"):
        PaperFillGenerator().generate(
            _request(submission, filled_at=SUBMITTED_AT - timedelta(seconds=1))
        )


def test_request_metadata_uuid_and_naive_time_validation() -> None:
    submission, _ = _submission()
    with pytest.raises(InvalidPaperFillBatchRequestError, match="UUID"):
        replace(_request(submission), request_id="bad")  # type: ignore[arg-type]
    with pytest.raises(InvalidPaperFillBatchRequestError, match="timezone-aware"):
        replace(_request(submission), filled_at=datetime(2026, 7, 21, 20))
    values = [MetadataEntry("source", "test")]
    item = _request(submission, metadata=values)
    values.clear()
    assert item.metadata == (MetadataEntry("source", "test"),)
    with pytest.raises(InvalidPaperFillBatchRequestError, match="unique"):
        _request(
            submission,
            metadata=(MetadataEntry("a", "1"), MetadataEntry("a", "2")),
        )


@pytest.mark.parametrize(
    "value",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), 100],
)
def test_reference_price_validation(value: object) -> None:
    with pytest.raises(InvalidPaperFillBatchRequestError):
        PaperFillPrice(UUID(int=1), value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("slippage", "commission"),
    [
        (Decimal("-1"), Decimal("0")),
        (Decimal("10000"), Decimal("0")),
        (Decimal("NaN"), Decimal("0")),
        (Decimal("Infinity"), Decimal("0")),
        (Decimal("0"), Decimal("-1")),
        (Decimal("0"), Decimal("NaN")),
        (Decimal("0"), Decimal("Infinity")),
    ],
)
def test_policy_validation(slippage: Decimal, commission: Decimal) -> None:
    with pytest.raises(InvalidPaperFillBatchRequestError):
        PaperFillPolicy(slippage, commission)


def test_price_coverage_must_be_exact_and_ordered() -> None:
    submission, _ = _submission(
        (_proposal(1, SPY, OrderSide.BUY), _proposal(2, QQQ, OrderSide.BUY))
    )
    prices = tuple(
        PaperFillPrice(order.request.order_id, Decimal("100"))
        for order in submission.orders
    )
    for invalid in (prices[:1], prices + (prices[0],), tuple(reversed(prices))):
        with pytest.raises(InvalidPaperFillBatchRequestError):
            PaperFillGenerator().generate(_request(submission, prices=invalid))


def test_no_action_requires_empty_prices_and_returns_diagnostic() -> None:
    submission, _ = _submission(())
    result = PaperFillGenerator().generate(_request(submission, prices=()))
    assert result.status is PaperFillBatchStatus.NO_ACTION
    assert result.evaluations == () and result.fills == ()
    assert result.diagnostics[0].code is PaperFillDiagnosticCode.NO_ACTION
    with pytest.raises(InvalidPaperFillBatchRequestError):
        PaperFillGenerator().generate(
            _request(
                submission,
                prices=(PaperFillPrice(UUID(int=1), Decimal("100")),),
            )
        )


def test_deterministic_identity_and_metadata_scope() -> None:
    submission, _ = _submission()
    first = PaperFillGenerator().generate(_request(submission))
    second = PaperFillGenerator().generate(_request(submission))
    assert first == second
    assert first.result_id.version == 5
    assert first.fills[0].fill_id.version == 5
    with_metadata = PaperFillGenerator().generate(
        _request(submission, metadata=(MetadataEntry("source", "test"),))
    )
    assert with_metadata.result_id != first.result_id
    assert with_metadata.fills[0].fill_id == first.fills[0].fill_id


def test_result_tampering_is_rejected_and_inputs_are_immutable() -> None:
    submission, _ = _submission()
    request = _request(submission)
    result = PaperFillGenerator().generate(request)
    altered = replace(result.evaluations[0], slippage_amount=Decimal("1"))
    with pytest.raises(InconsistentPaperFillBatchResultError):
        PaperFillBatchResult(
            result.result_id,
            request,
            result.status,
            (altered,),
            result.diagnostics,
        )
    assert request.submission_batch == submission
    assert request.prices[0].reference_price == Decimal("100")
