from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce
from trading_bot.review_paper import (
    ReviewPaperIntent,
    ReviewPaperPerformanceHistoryEmptyError,
    ReviewPaperPerformanceStore,
    ReviewPaperQuoteError,
    ReviewPaperStore,
    ReviewPaperValuationConflictError,
    RobinhoodEquityOrderReview,
    RobinhoodReviewQuote,
    canonical_order_checks,
)
from trading_bot.risk import RiskOutcome
from trading_bot.robinhood_mcp import (
    RobinhoodEquityQuoteResult,
    RobinhoodEquityQuotesResponse,
    RobinhoodQuoteData,
)


def _intent(
    *,
    order_id: str,
    side: OrderSide,
    proposed_at: datetime,
    reason: str,
) -> ReviewPaperIntent:
    return ReviewPaperIntent(
        proposal_id=UUID(order_id.replace("2", "1")),
        order_id=UUID(order_id),
        symbol=Symbol("SPY"),
        side=side,
        desired_quantity=Decimal("10"),
        approved_quantity=Decimal("10"),
        risk_outcome=RiskOutcome.APPROVED,
        risk_reason_codes=(),
        proposal_reason=reason,
        proposal_confidence=Decimal("0.8"),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        proposed_at=proposed_at,
    )


def _review(
    *,
    side: OrderSide,
    price: Decimal,
    at: datetime,
) -> RobinhoodEquityOrderReview:
    bid = price if side is OrderSide.SELL else price - Decimal("0.1")
    ask = price if side is OrderSide.BUY else price + Decimal("0.1")
    return RobinhoodEquityOrderReview(
        symbol=Symbol("SPY"),
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal("10"),
        quote=RobinhoodReviewQuote(
            symbol=Symbol("SPY"),
            adjusted_previous_close=Decimal("95"),
            ask_price=ask,
            bid_price=bid,
            has_traded=True,
            last_non_reg_trade_price=None,
            last_trade_price=price,
            previous_close=Decimal("95"),
            previous_close_date="2026-10-01",
            state="active",
            venue_ask_time=at,
            venue_bid_time=at,
            venue_last_non_reg_trade_time=None,
            venue_last_trade_time=at,
        ),
        order_checks_json=canonical_order_checks({}),
        reviewed_at=at + timedelta(milliseconds=10),
        market_data_disclosure="verbatim",
    )


def _quotes(
    *,
    price: Decimal,
    source_at: datetime,
    symbol: str = "SPY",
) -> RobinhoodEquityQuotesResponse:
    quote = RobinhoodQuoteData(
        symbol=Symbol(symbol),
        adjusted_previous_close=Decimal("95"),
        ask_price=price + Decimal("0.1"),
        bid_price=price - Decimal("0.1"),
        has_traded=True,
        last_non_reg_trade_price=None,
        last_trade_price=price,
        previous_close=Decimal("95"),
        previous_close_date="2026-10-01",
        state="active",
        venue_ask_time=source_at,
        venue_bid_time=source_at,
        venue_last_non_reg_trade_time=None,
        venue_last_trade_time=source_at,
    )
    return RobinhoodEquityQuotesResponse(
        results=(RobinhoodEquityQuoteResult(quote=quote, close=None),),
    )


def _store_with_buy(tmp_path) -> ReviewPaperStore:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    proposed = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
    store.record_market_review(
        _intent(
            order_id="22222222-2222-2222-2222-222222222222",
            side=OrderSide.BUY,
            proposed_at=proposed,
            reason="buy signal",
        ),
        _review(
            side=OrderSide.BUY,
            price=Decimal("100"),
            at=proposed + timedelta(seconds=1),
        ),
    )
    return store


def test_valuation_is_durable_idempotent_and_auditable(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    performance = ReviewPaperPerformanceStore(store)
    at = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)
    response = _quotes(price=Decimal("110"), source_at=at - timedelta(seconds=2))

    first = performance.record_quotes(
        response,
        observed_at=at,
        max_quote_age=timedelta(minutes=1),
    )
    second = performance.record_quotes(
        response,
        observed_at=at,
        max_quote_age=timedelta(minutes=1),
    )

    assert first == second
    assert first.account.equity == Decimal("10100")
    assert first.account.unrealized_profit_loss == Decimal("100")
    assert first.marks[0].price == Decimal("110")
    assert first.marks[0].source_at == at - timedelta(seconds=2)

    reopened = ReviewPaperPerformanceStore(store)
    assert reopened.history() == (first,)


def test_stale_quote_is_rejected_without_valuation(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    performance = ReviewPaperPerformanceStore(store)
    at = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)

    with pytest.raises(ReviewPaperQuoteError, match="stale"):
        performance.record_quotes(
            _quotes(price=Decimal("110"), source_at=at - timedelta(minutes=2)),
            observed_at=at,
            max_quote_age=timedelta(minutes=1),
        )

    assert performance.history() == ()


def test_future_quote_is_rejected(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    performance = ReviewPaperPerformanceStore(store)
    at = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)

    with pytest.raises(ReviewPaperQuoteError, match="future"):
        performance.record_quotes(
            _quotes(price=Decimal("110"), source_at=at + timedelta(seconds=1)),
            observed_at=at,
            max_quote_age=timedelta(minutes=1),
        )


def test_quote_symbols_must_exactly_match_open_positions(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    performance = ReviewPaperPerformanceStore(store)
    at = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)

    with pytest.raises(ReviewPaperQuoteError, match="exactly match"):
        performance.record_quotes(
            RobinhoodEquityQuotesResponse(results=()),
            observed_at=at,
            max_quote_age=timedelta(minutes=1),
        )


def test_conflicting_same_timestamp_is_rejected(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    performance = ReviewPaperPerformanceStore(store)
    at = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)
    performance.record_quotes(
        _quotes(price=Decimal("110"), source_at=at),
        observed_at=at,
        max_quote_age=timedelta(minutes=1),
    )

    with pytest.raises(ReviewPaperValuationConflictError):
        performance.record_quotes(
            _quotes(price=Decimal("111"), source_at=at),
            observed_at=at,
            max_quote_age=timedelta(minutes=1),
        )


def test_report_tracks_return_drawdown_and_open_unrealized_pnl(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    performance = ReviewPaperPerformanceStore(store)
    one = datetime(2026, 10, 2, 20, 0, tzinfo=UTC)
    two = one + timedelta(days=1)
    three = two + timedelta(days=1)

    for at, price in (
        (one, Decimal("110")),
        (two, Decimal("80")),
        (three, Decimal("150")),
    ):
        performance.record_quotes(
            _quotes(price=price, source_at=at),
            observed_at=at,
            max_quote_age=timedelta(minutes=1),
        )

    report = performance.report()

    assert report.latest.account.equity == Decimal("10500")
    assert report.absolute_profit_loss == Decimal("500")
    assert report.total_return == Decimal("0.05")
    assert report.maximum_drawdown_amount == Decimal("300")
    assert report.maximum_drawdown_percentage == Decimal("300") / Decimal("10100")
    assert report.valuation_count == 3
    assert report.paper_trade_count == 1
    assert report.closed_trade_count == 0
    assert report.win_rate == Decimal("0")


def test_sell_realization_retains_exit_model_attribution(tmp_path) -> None:
    store = _store_with_buy(tmp_path)
    sell_proposed = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
    store.record_market_review(
        _intent(
            order_id="33333333-3333-3333-3333-333333333333",
            side=OrderSide.SELL,
            proposed_at=sell_proposed,
            reason="model exit signal",
        ),
        _review(
            side=OrderSide.SELL,
            price=Decimal("120"),
            at=sell_proposed + timedelta(seconds=1),
        ),
    )
    performance = ReviewPaperPerformanceStore(store)
    at = datetime(2026, 10, 3, 20, 0, tzinfo=UTC)
    performance.record_quotes(
        RobinhoodEquityQuotesResponse(results=()),
        observed_at=at,
        max_quote_age=timedelta(minutes=1),
    )

    report = performance.report()

    assert report.latest.account.equity == Decimal("10200")
    assert report.latest.account.realized_profit_loss == Decimal("200")
    assert report.latest.account.unrealized_profit_loss == Decimal("0")
    assert report.closed_trade_count == 1
    assert report.winning_trade_count == 1
    assert report.win_rate == Decimal("1")
    realization = report.realizations[0]
    assert realization.net_profit_loss == Decimal("200")
    assert realization.exit_reason == "model exit signal"
    assert realization.exit_confidence == Decimal("0.8")
    assert realization.exit_paper_trade_id == store.history()[1].paper_trade_id


def test_report_requires_at_least_one_valuation(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    performance = ReviewPaperPerformanceStore(store)

    with pytest.raises(ReviewPaperPerformanceHistoryEmptyError):
        performance.report()
