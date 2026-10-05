from __future__ import annotations

from dataclasses import asdict
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
    RobinhoodAgenticAccountResolutionError,
    RobinhoodAgenticAccountResolver,
    RobinhoodEquityOrder,
    RobinhoodEquityOrdersPage,
    RobinhoodMcpStreamableHttpTransport,
    RobinhoodReviewReadAdapter,
    create_robinhood_agentic_account_resolver,
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


def _resolver() -> RobinhoodAgenticAccountResolver:
    return RobinhoodAgenticAccountResolver(
        lambda: {
            "data": {
                "accounts": [
                    {"agentic_allowed": True, "account_number": "agentic-account"}
                ]
            }
        }
    )


def _empty_page(next_cursor: str | None = None) -> RobinhoodEquityOrdersPage:
    return RobinhoodEquityOrdersPage(orders=(), next_cursor=next_cursor)


def test_successful_cycle_checks_real_orders_before_persisting(tmp_path) -> None:
    adapter = FakeAdapter(order_pages=[_empty_page(), _empty_page()])
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    cycle = RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver())

    result = cycle.run(
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
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver()).run(
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
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver()).run(
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

    result = RobinhoodReviewPaperCycle(
        adapter, store, account_resolver=_resolver()
    ).run(
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
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver()).run(
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
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver()).run(
            intent=_intent(),
            review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
        )


def test_durable_order_id_is_reused_without_another_robinhood_call(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    first_adapter = FakeAdapter(order_pages=[_empty_page(), _empty_page()])
    first_cycle = RobinhoodReviewPaperCycle(
        first_adapter, store, account_resolver=_resolver()
    )
    first = first_cycle.run(
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    resolver_calls = []

    def unexpected_accounts():
        resolver_calls.append("accounts")
        raise AssertionError("replay must not resolve an account")

    replay_resolver = RobinhoodAgenticAccountResolver(unexpected_accounts)
    replay_adapter = FakeAdapter(order_pages=[])
    replay = RobinhoodReviewPaperCycle(
        replay_adapter, store, account_resolver=replay_resolver
    ).run(
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 1, tzinfo=UTC),
    )

    assert replay.record == first.record
    assert replay.reused_durable_record is True
    assert replay_adapter.calls == []
    assert resolver_calls == []


def test_existing_order_id_with_changed_intent_is_conflict(tmp_path) -> None:
    store = ReviewPaperStore(
        tmp_path / "paper.sqlite",
        starting_cash=Decimal("10000"),
    )
    first_adapter = FakeAdapter(order_pages=[_empty_page(), _empty_page()])
    RobinhoodReviewPaperCycle(first_adapter, store, account_resolver=_resolver()).run(
        intent=_intent(),
        review_received_at=datetime(2026, 10, 2, 15, 0, 2, tzinfo=UTC),
    )

    resolver_calls = []

    def unexpected_accounts():
        resolver_calls.append("accounts")
        raise AssertionError("conflict must not resolve an account")

    conflict_resolver = RobinhoodAgenticAccountResolver(unexpected_accounts)
    with pytest.raises(ReviewPaperConflictError):
        RobinhoodReviewPaperCycle(
            FakeAdapter(order_pages=[]), store, account_resolver=conflict_resolver
        ).run(
            intent=_intent(reason="different signal"),
            review_received_at=datetime(2026, 10, 2, 15, 1, tzinfo=UTC),
        )

    assert resolver_calls == []


def test_new_cycle_resolves_once_before_all_reads_and_review(tmp_path) -> None:
    events = []

    def read_accounts():
        events.append("accounts")
        return {
            "data": {
                "accounts": [
                    {"agentic_allowed": True, "account_number": "canonical-agent"}
                ]
            }
        }

    resolver = RobinhoodAgenticAccountResolver(read_accounts)
    adapter = FakeAdapter(
        order_pages=[
            _empty_page("page-2"),
            _empty_page(),
            _empty_page("page-4"),
            _empty_page(),
        ]
    )
    original_orders = adapter.agentic_equity_orders

    def orders(**kwargs):
        assert events == ["accounts"]
        return original_orders(**kwargs)

    adapter.agentic_equity_orders = orders
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    result = RobinhoodReviewPaperCycle(adapter, store, account_resolver=resolver).run(
        intent=_intent(),
        review_received_at=_review().reviewed_at,
    )
    assert events == ["accounts"]
    assert [name for name, _ in adapter.calls] == [
        "orders",
        "orders",
        "review",
        "orders",
        "orders",
    ]
    assert all(
        payload["account_number"] == "canonical-agent" for _, payload in adapter.calls
    )
    assert "canonical-agent" not in repr(result)
    assert b"canonical-agent" not in (tmp_path / "paper.sqlite").read_bytes()


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"data": {"accounts": []}},
        {"data": {"accounts": [{"agentic_allowed": True, "account_number": ""}]}},
    ],
)
def test_resolution_failure_precedes_orders_review_and_store_mutation(
    tmp_path, response
) -> None:
    resolver = RobinhoodAgenticAccountResolver(lambda: response)
    adapter = FakeAdapter(order_pages=[])
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    before = (tmp_path / "paper.sqlite").read_bytes()
    with pytest.raises(RobinhoodAgenticAccountResolutionError):
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=resolver).run(
            intent=_intent(),
            review_received_at=_review().reviewed_at,
        )
    assert adapter.calls == []
    assert store.history() == ()
    assert (tmp_path / "paper.sqlite").read_bytes() == before


def test_concrete_transport_composition_resolves_once_and_replays_without_calls(
    tmp_path,
) -> None:
    calls = []
    quote = asdict(_review().quote)
    for key, value in quote.items():
        if isinstance(value, Decimal):
            quote[key] = str(value)
        elif isinstance(value, datetime):
            quote[key] = value.isoformat()
    quote["symbol"] = "SPY"

    async def caller(name, arguments):
        calls.append((name, dict(arguments)))
        if name == "get_accounts":
            return {
                "data": {
                    "accounts": [
                        {"agentic_allowed": False, "account_number": "ordinary"},
                        {"agentic_allowed": True, "account_number": "canonical-agent"},
                    ]
                }
            }
        if name == "get_equity_orders":
            return {"data": {"orders": [], "next": ""}}
        if name == "review_equity_order":
            return {
                "data": {
                    "symbol": "SPY",
                    "side": "buy",
                    "type": "market",
                    "quantity": "5",
                    "quote_data": quote,
                    "order_checks": {},
                    "market_data_disclosure": "verbatim disclosure",
                }
            }
        raise AssertionError("unexpected MCP operation")

    transport = RobinhoodMcpStreamableHttpTransport.for_test(caller)
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    cycle = RobinhoodReviewPaperCycle(
        RobinhoodReviewReadAdapter(transport),
        store,
        account_resolver=create_robinhood_agentic_account_resolver(transport),
    )
    result = cycle.run(intent=_intent(), review_received_at=_review().reviewed_at)
    assert [name for name, _ in calls] == [
        "get_accounts",
        "get_equity_orders",
        "review_equity_order",
        "get_equity_orders",
    ]
    assert calls[0][1] == {}
    assert all(
        arguments["account_number"] == "canonical-agent" for _, arguments in calls[1:]
    )
    for name, arguments in calls:
        if name == "get_equity_orders":
            assert arguments["placed_agent"] == "agentic"
            assert arguments["symbol"] == "SPY"
            assert arguments["created_at_gte"] == _intent().proposed_at.isoformat()
    calls.clear()
    assert (
        cycle.run(intent=_intent(), review_received_at=_review().reviewed_at).record
        == result.record
    )
    assert calls == []


@pytest.mark.parametrize(
    "post_case", ["empty", "paginated_empty", "order", "read_failure"]
)
def test_review_failure_always_checks_post_window_and_never_persists(
    tmp_path, monkeypatch, post_case
) -> None:
    review_error = ValueError("review response failed")
    read_error = RuntimeError("post history unavailable")
    pages = [_empty_page()]
    if post_case == "empty":
        pages += [_empty_page()]
    else:
        pages += [_empty_page("post-2"), _empty_page()]
    if post_case == "order":
        pages[-1] = RobinhoodEquityOrdersPage(orders=(_real_order(),), next_cursor=None)

    class FailingReviewAdapter(FakeAdapter):
        def review_market_order(self, **kwargs):
            self.calls.append(("review", dict(kwargs)))
            raise review_error

        def agentic_equity_orders(self, **kwargs):
            if post_case == "read_failure" and any(
                name == "review" for name, _ in self.calls
            ):
                self.calls.append(("orders", dict(kwargs)))
                raise read_error
            return super().agentic_equity_orders(**kwargs)

    adapter = FailingReviewAdapter(order_pages=pages)
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    persistence_calls = []

    def forbidden_persistence(*args, **kwargs):
        persistence_calls.append(True)
        raise AssertionError("review failure must not reach persistence")

    monkeypatch.setattr(store, "record_market_review", forbidden_persistence)
    expected = (
        RobinhoodPaperCycleSafetyError
        if post_case == "order"
        else RuntimeError
        if post_case == "read_failure"
        else ValueError
    )
    with pytest.raises(expected) as caught:
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver()).run(
            intent=_intent(), review_received_at=_review().reviewed_at
        )
    if post_case in {"empty", "paginated_empty"}:
        assert caught.value is review_error
    elif post_case == "read_failure":
        assert caught.value is read_error
    else:
        assert "after_review" in str(caught.value)
    assert [name for name, _ in adapter.calls] == [
        "orders",
        "review",
        "orders",
        *([] if post_case in {"empty", "read_failure"} else ["orders"]),
    ]
    assert all(
        arguments["account_number"] == "agentic-account"
        for _, arguments in adapter.calls
    )
    assert not persistence_calls
    assert store.history() == ()


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_review_process_control_exceptions_propagate_without_being_caught(
    tmp_path, exception
) -> None:
    failure = exception()

    class InterruptedAdapter(FakeAdapter):
        def review_market_order(self, **kwargs):
            self.calls.append(("review", dict(kwargs)))
            raise failure

    adapter = InterruptedAdapter(order_pages=[_empty_page()])
    store = ReviewPaperStore(tmp_path / "paper.sqlite", starting_cash=Decimal("10000"))
    with pytest.raises(exception) as caught:
        RobinhoodReviewPaperCycle(adapter, store, account_resolver=_resolver()).run(
            intent=_intent(), review_received_at=_review().reviewed_at
        )
    assert caught.value is failure
    assert [name for name, _ in adapter.calls] == ["orders", "review"]
    assert store.history() == ()
