from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.review_paper import (
    ReviewPaperConflictError,
    ReviewPaperIntent,
    ReviewPaperStore,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    canonical_order_checks,
)
from trading_bot.risk import RiskOutcome
from trading_bot.robinhood_mcp import (
    RobinhoodEquityOrder,
    RobinhoodEquityOrdersPage,
)
from trading_bot.robinhood_paper_cycle import (
    RobinhoodPaperCycleSafetyError,
    RobinhoodReviewPaperCycle,
)


def _intent(
    *,
    reason: str = "validated signal",
) -> ReviewPaperIntent:
    return ReviewPaperIntent(
        proposal_id=UUID("11111111-1111-1111-1111-111111111111"),
        order_id=UUID("22222222-2222-2222-2222-222222222222"),
        symbol=Symbol("SPY"),
        side=OrderSide.BUY,
        desired_quantity=Decimal("10"),
        approved_quantity=Decimal("5"),
        risk_outcome=RiskOutcome.RESIZED,
        risk_reason_codes=("MAX_POSITION_PERCENT",),
        proposal_reason=reason,
        proposal_confidence=Decimal("0.75"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        proposed_at=datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
    )


def _review() -> RobinhoodEquityOrderReview:
    quote_time = datetime(2026, 10, 2, 15, 0, 1, tzinfo=UTC)
    return RobinhoodEquityOrderReview(
        symbol=Symbol("SPY"),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("5"),
        quote=RobinhoodReviewQuote(
            symbol=Symbol("SPY"),
            adjusted_previous_close=Decimal("495"),
            ask_price=Decimal("500"),
            bid_price=Decimal("499.90"),
            has_traded=True,
            last_non_reg_trade_price=None,
            last_trade_price=Decimal("499.95"),
            previous_close=Decimal("495"),
            previous_close_date="2026-10-01",
            state="active",
            venue_ask_time=quote_time,
            venue_bid_time=quote_time,
            venue_last_non_reg_trade_time=None,
            venue_last_trade_time=quote_time,
        ),
        order_checks_json=canonical_order_checks({}),
        reviewed_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        market_data_disclosure="verbatim disclosure",
    )


def _real_order(
    *,
    order_id: str = "real-order-1",
    placed_agent: str = "agentic",
) -> RobinhoodEquityOrder:
    return RobinhoodEquityOrder(
        order_id=order_id,
        symbol=Symbol("SPY"),
        side=OrderSide.BUY,
        state="filled",
        placed_agent=placed_agent,
        created_at=datetime(2026, 10, 2, 15, 0, 1, tzinfo=UTC),
        last_transaction_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        market_hours="regular_hours",
        time_in_force="gfd",
        order_type="market",
        trigger="immediate",
        quantity=Decimal("5"),
        cumulative_quantity=Decimal("5"),
        average_price=Decimal("500"),
        price=None,
        stop_price=None,
        fees=Decimal("0"),
        ref_id=None,
        reject_reason=None,
        instrument_id="instrument-1",
        dollar_based_amount=None,
        executions=(),
    )


class FakeAdapter:
    def __init__(
        self,
        *,
        order_pages: list[RobinhoodEquityOrdersPage],
    ) -> None:
        self._order_pages = list(order_pages)
        self.calls: list[tuple[str, object]] = []

    def agentic_equity_orders(self, **kwargs) -> RobinhoodEquityOrdersPage:
        self.calls.append(("orders", dict(kwargs)))
        if not self._order_pages:
            raise AssertionError("unexpected order-history call")
        return self._order_pages.pop(0)

    def review_market_order(self, **kwargs) -> RobinhoodEquityOrderReview:
        self.calls.append(("review", dict(kwargs)))
        return _review()


def _empty_page(next_cursor: str | None = None) -> RobinhoodEquityOrdersPage:
    return RobinhoodEquityOrdersPage(orders=(), next_cursor=next_cursor)


def test_successful_cycle_checks_real_orders_before_persisting(tmp_path) -> None:
    adapter = FakeAdapter(order_pages=[_empty_page(), _empty_page()])
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    cycle = RobinhoodReviewPaperCycle(adapter, store)

    result = cycle.run(
        account_number="agentic-account",
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    assert result.reused_durable_record is False
    assert result.baseline_order_pages == 1
    assert result.post_review_order_pages == 1
    assert result.record.fill_price == Decimal("500")
    assert store.history() == (result.record,)
    assert [name for name, _ in adapter.calls] == ["orders", "review", "orders"]


def test_existing_real_order_blocks_before_review(tmp_path) -> None:
    adapter = FakeAdapter(
        order_pages=[
            RobinhoodEquityOrdersPage(
                orders=(_real_order(),),
                next_cursor=None,
            )
        ]
    )
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(RobinhoodPaperCycleSafetyError, match="before_review"):
        RobinhoodReviewPaperCycle(adapter, store).run(
            account_number="agentic-account",
            intent=_intent(),
            review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )

    assert store.history() == ()
    assert [name for name, _ in adapter.calls] == ["orders"]


def test_real_order_after_review_blocks_synthetic_fill(tmp_path) -> None:
    adapter = FakeAdapter(
        order_pages=[
            _empty_page(),
            RobinhoodEquityOrdersPage(
                orders=(_real_order(),),
                next_cursor=None,
            ),
        ]
    )
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(RobinhoodPaperCycleSafetyError, match="after_review"):
        RobinhoodReviewPaperCycle(adapter, store).run(
            account_number="agentic-account",
            intent=_intent(),
            review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )

    assert store.history() == ()
    assert [name for name, _ in adapter.calls] == ["orders", "review", "orders"]


def test_order_history_paginates_until_terminal_cursor(tmp_path) -> None:
    adapter = FakeAdapter(
        order_pages=[
            _empty_page("cursor-2"),
            _empty_page(),
            _empty_page("cursor-4"),
            _empty_page(),
        ]
    )
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    result = RobinhoodReviewPaperCycle(adapter, store).run(
        account_number="agentic-account",
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    assert result.baseline_order_pages == 2
    assert result.post_review_order_pages == 2
    order_calls = [payload for name, payload in adapter.calls if name == "orders"]
    assert order_calls[1]["cursor"] == "cursor-2"
    assert order_calls[3]["cursor"] == "cursor-4"


def test_repeated_pagination_cursor_fails_closed(tmp_path) -> None:
    adapter = FakeAdapter(
        order_pages=[
            _empty_page("repeat"),
            _empty_page("repeat"),
        ]
    )
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(RobinhoodPaperCycleSafetyError, match="cursor repeated"):
        RobinhoodReviewPaperCycle(adapter, store).run(
            account_number="agentic-account",
            intent=_intent(),
            review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )

    assert store.history() == ()


def test_non_agentic_order_in_filtered_response_fails_closed(tmp_path) -> None:
    adapter = FakeAdapter(
        order_pages=[
            RobinhoodEquityOrdersPage(
                orders=(_real_order(placed_agent="user"),),
                next_cursor=None,
            )
        ]
    )
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )

    with pytest.raises(RobinhoodPaperCycleSafetyError, match="non-agentic"):
        RobinhoodReviewPaperCycle(adapter, store).run(
            account_number="agentic-account",
            intent=_intent(),
            review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )


def test_durable_order_id_is_reused_without_another_robinhood_call(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    first_adapter = FakeAdapter(order_pages=[_empty_page(), _empty_page()])
    first_cycle = RobinhoodReviewPaperCycle(first_adapter, store)
    first = first_cycle.run(
        account_number="agentic-account",
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    replay_adapter = FakeAdapter(order_pages=[])
    replay = RobinhoodReviewPaperCycle(replay_adapter, store).run(
        account_number="agentic-account",
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 1, tzinfo=UTC),
    )

    assert replay.record == first.record
    assert replay.reused_durable_record is True
    assert replay_adapter.calls == []


def test_existing_order_id_with_changed_intent_is_conflict(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    first_adapter = FakeAdapter(order_pages=[_empty_page(), _empty_page()])
    RobinhoodReviewPaperCycle(first_adapter, store).run(
        account_number="agentic-account",
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    with pytest.raises(ReviewPaperConflictError):
        RobinhoodReviewPaperCycle(FakeAdapter(order_pages=[]), store).run(
            account_number="agentic-account",
            intent=_intent(reason="different signal"),
            review_received_at=datetime(2026, 10, 2, 15, 1, tzinfo=UTC),
        )
