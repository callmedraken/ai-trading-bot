from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.ledger import PositionNotFoundError
from trading_bot.review_paper import (
    ReviewPaperConflictError,
    ReviewPaperIntent,
    ReviewPaperStore,
    ReviewPaperStoreError,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    UnsupportedReviewPaperOrderError,
    canonical_order_checks,
)
from trading_bot.risk import RiskOutcome


def _intent(
    *,
    order_id: UUID = UUID("22222222-2222-2222-2222-222222222222"),
    side: OrderSide = OrderSide.BUY,
    desired: Decimal = Decimal("10"),
    approved: Decimal = Decimal("10"),
    outcome: RiskOutcome = RiskOutcome.APPROVED,
    order_type: OrderType = OrderType.MARKET,
    proposed_at: datetime | None = None,
) -> ReviewPaperIntent:
    return ReviewPaperIntent(
        proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
        order_id=order_id,
        symbol=Symbol("SPY"),
        side=side,
        desired_quantity=desired,
        approved_quantity=approved,
        risk_outcome=outcome,
        risk_reason_codes=(
            () if outcome is RiskOutcome.APPROVED else ("MAX_POSITION_PERCENT",)
        ),
        proposal_reason="model saw a validated trend signal",
        proposal_confidence=Decimal("0.72"),
        order_type=order_type,
        time_in_force=TimeInForce.DAY,
        proposed_at=proposed_at or datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
        limit_price=Decimal("500") if order_type is OrderType.LIMIT else None,
    )


def _review(
    *,
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("10"),
    bid: Decimal = Decimal("499"),
    ask: Decimal = Decimal("500"),
    quote_time: datetime | None = None,
    checks: dict[str, object] | None = None,
) -> RobinhoodEquityOrderReview:
    observed = quote_time or datetime(2026, 10, 2, 15, 0, 1, tzinfo=UTC)
    quote = RobinhoodReviewQuote(
        symbol=Symbol("SPY"),
        adjusted_previous_close=Decimal("495"),
        ask_price=ask,
        bid_price=bid,
        has_traded=True,
        last_non_reg_trade_price=None,
        last_trade_price=Decimal("499.5"),
        previous_close=Decimal("495"),
        previous_close_date="2026-10-01",
        state="active",
        venue_ask_time=observed,
        venue_bid_time=observed,
        venue_last_non_reg_trade_time=None,
        venue_last_trade_time=observed,
    )
    return RobinhoodEquityOrderReview(
        symbol=Symbol("SPY"),
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        quote=quote,
        order_checks_json=canonical_order_checks(checks or {}),
        reviewed_at=observed + timedelta(milliseconds=20),
        market_data_disclosure="Bid/ask disclosure exactly as returned",
    )


def test_market_buy_is_durable_idempotent_and_reconstructable(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    intent = _intent()
    review = _review()

    first = store.record_market_review(
        intent,
        review,
        slippage_basis_points=Decimal("10"),
    )
    second = store.record_market_review(
        intent,
        review,
        slippage_basis_points=Decimal("10"),
    )

    assert first == second
    assert first.fill_price == Decimal("500.500")
    assert len(store.history()) == 1

    ledger = store.reconstruct_ledger()
    assert ledger.cash == Decimal("4995.000")
    position = ledger.get_position(Symbol("SPY"))
    assert position is not None
    assert position.quantity == Decimal("10")
    assert position.average_cost == Decimal("500.500")

    reopened = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    assert reopened.history() == (first,)


def test_same_order_id_with_different_review_is_conflict(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    intent = _intent()
    store.record_market_review(intent, _review())

    with pytest.raises(ReviewPaperConflictError):
        store.record_market_review(intent, _review(ask=Decimal("501")))


def test_review_must_echo_exact_risk_approved_order(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(ReviewPaperConflictError):
        store.record_market_review(_intent(), _review(quantity=Decimal("9")))


def test_sell_closes_virtual_position_and_realizes_profit(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    store.record_market_review(
        _intent(),
        _review(bid=Decimal("99"), ask=Decimal("100")),
    )
    sell_time = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
    sell_intent = _intent(
        order_id=UUID("33333333-3333-3333-3333-333333333333"),
        side=OrderSide.SELL,
        proposed_at=sell_time,
    )
    store.record_market_review(
        sell_intent,
        _review(
            side=OrderSide.SELL,
            bid=Decimal("110"),
            ask=Decimal("111"),
            quote_time=sell_time + timedelta(seconds=1),
        ),
    )

    ledger = store.reconstruct_ledger()
    assert ledger.cash == Decimal("10100")
    assert ledger.get_position(Symbol("SPY")) is None
    assert ledger.realized_profit_loss == Decimal("100")


def test_sell_without_virtual_position_is_not_persisted(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(PositionNotFoundError):
        store.record_market_review(
            _intent(side=OrderSide.SELL),
            _review(side=OrderSide.SELL),
        )

    assert store.history() == ()


def test_nonempty_robinhood_order_checks_are_preserved_not_interpreted(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    review = _review(
        checks={
            "alert_type": "EXAMPLE_FUTURE_ALERT",
            "example_future_alert_details": {"message": "broker warning"},
        }
    )

    record = store.record_market_review(_intent(), review)

    assert record.review.order_checks_json == (
        '{"alert_type":"EXAMPLE_FUTURE_ALERT",'
        '"example_future_alert_details":{"message":"broker warning"}}'
    )


def test_zero_side_specific_quote_cannot_create_paper_fill(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(ValueError, match="must be positive"):
        store.record_market_review(_intent(), _review(ask=Decimal("0")))

    assert store.history() == ()


def test_quote_timestamp_must_not_precede_proposal(tmp_path) -> None:
    proposed = datetime(2026, 10, 2, 15, 0, 1, tzinfo=UTC)
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(ValueError, match="cannot precede proposal"):
        store.record_market_review(
            _intent(proposed_at=proposed),
            _review(quote_time=proposed - timedelta(microseconds=1)),
        )


def test_limit_order_is_explicitly_out_of_scope_for_phase_a2(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(UnsupportedReviewPaperOrderError):
        store.record_market_review(
            _intent(order_type=OrderType.LIMIT),
            _review(),
        )


def test_store_rejects_different_starting_cash_on_reopen(tmp_path) -> None:
    path = tmp_path / "paper.sqlite"
    ReviewPaperStore(path, starting_cash=Decimal("10000"))

    with pytest.raises(ReviewPaperStoreError, match="starting_cash mismatch"):
        ReviewPaperStore(path, starting_cash=Decimal("25000"))


def test_account_snapshot_uses_virtual_paper_state(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    store.record_market_review(
        _intent(),
        _review(bid=Decimal("99"), ask=Decimal("100")),
    )

    snapshot = store.create_account_snapshot(
        {Symbol("SPY"): Decimal("105")},
        timestamp=datetime(2026, 10, 2, 20, 0, tzinfo=UTC),
    )

    assert snapshot.cash == Decimal("9000")
    assert snapshot.positions_market_value == Decimal("1050")
    assert snapshot.equity == Decimal("10050")
    assert snapshot.unrealized_profit_loss == Decimal("50")
