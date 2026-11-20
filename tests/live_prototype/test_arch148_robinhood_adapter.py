"""Fake-only tests for the Architecture 148 Robinhood MCP adapter."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Position, Symbol
from trading_bot.live_runtime.identity import create_order_intent
from trading_bot.live_runtime.models import (
    TQQQ,
    UNIVERSE_SYMBOLS,
    AccountFacts,
    AdmissionBlocker,
    ApprovalFacts,
    BrokerOrderFact,
    BrokerReviewFacts,
    BrokerSnapshot,
    IntentKind,
    IntentLifecycle,
    OrderState,
    OwnedPositionRecord,
    PriceObservation,
    ProtectiveStopCancelCandidate,
    ReviewStatus,
    RuntimeState,
    ScopeFacts,
    SourceIdentity,
    TradabilityFacts,
)
from trading_bot.live_runtime.order_tracker import (
    OrderTracker,
    TrackedOrder,
)
from trading_bot.live_runtime.robinhood_adapter import (
    RobinhoodAdapterCapabilities,
    RobinhoodAdapterIdentityError,
    RobinhoodAdapterUnavailableError,
    RobinhoodEffectStatus,
    RobinhoodMcpAdapter,
)

_NOW = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)
_ACCOUNT = "ACCOUNT-148"
_ACCOUNT_FP = hashlib.sha256(_ACCOUNT.encode("utf-8")).hexdigest()
_SOURCE = SourceIdentity("1" * 40, "2" * 40)
_SESSION = "a" * 64
_OWNER = UUID("00000000-0000-0000-0000-000000000148")


def _quote(symbol: str, at: datetime = _NOW) -> dict[str, object]:
    stamp = at.isoformat()
    return {
        "symbol": symbol,
        "adjusted_previous_close": "99",
        "ask_price": "101",
        "bid_price": "100",
        "has_traded": True,
        "last_non_reg_trade_price": None,
        "last_trade_price": "100.5",
        "previous_close": "99",
        "previous_close_date": "2026-11-18",
        "state": "active",
        "venue_ask_time": stamp,
        "venue_bid_time": stamp,
        "venue_last_non_reg_trade_time": None,
        "venue_last_trade_time": stamp,
    }


def _review_response(
    *,
    symbol: str = "TQQQ",
    side: str = "buy",
    order_type: str = "market",
    quantity: str = "10",
    stop_price: str | None = None,
    time_in_force: str = "gfd",
) -> dict[str, object]:
    data: dict[str, object] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
        "quote_data": _quote(symbol),
        "order_checks": {},
        "customer_approval_required": False,
        "market_hours": "regular_hours",
        "time_in_force": time_in_force,
    }
    if stop_price is not None:
        data["stop_price"] = stop_price
    return {"data": data}


def _order_row(
    *,
    order_id: str = "entry-order",
    symbol: str = "TQQQ",
    side: str = "buy",
    state: str = "filled",
    quantity: str = "10",
    filled: str = "10",
    average: str | None = "100",
    ref_id: str | None = None,
    order_type: str = "market",
    stop_price: str | None = None,
) -> dict[str, object]:
    return {
        "id": order_id,
        "symbol": symbol,
        "side": side,
        "state": state,
        "placed_agent": "agentic",
        "created_at": _NOW.isoformat(),
        "last_transaction_at": _NOW.isoformat(),
        "market_hours": "regular_hours",
        "time_in_force": "gtc" if stop_price is not None else "gfd",
        "type": order_type,
        "trigger": "stop" if stop_price is not None else "immediate",
        "quantity": quantity,
        "cumulative_quantity": filled,
        "average_price": average,
        "price": None,
        "stop_price": stop_price,
        "fees": "0",
        "ref_id": ref_id,
        "reject_reason": None,
        "instrument_id": f"instrument-{symbol}",
        "dollar_based_amount": None,
        "executions": [],
    }


class _World:
    def __init__(self) -> None:
        self.factory_calls = 0
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.position_pages: dict[str | None, Mapping[str, object]] = {
            None: {"data": {"positions": [], "next": None}}
        }
        self.order_pages: dict[str | None, Mapping[str, object]] = {
            None: {"data": {"orders": [], "next": None}}
        }
        self.approval_pages: dict[str | None, Mapping[str, object]] = {
            None: {"data": {"approvals": [], "next": None}}
        }
        self.review_payload: Mapping[str, object] = _review_response()
        self.place_payload: Mapping[str, object] | None = None
        self.cancel_payload: Mapping[str, object] | None = None
        self.opens = 0
        self.closes = 0

    def factory(self) -> _FakeTransport:
        self.factory_calls += 1
        return _FakeTransport(self)


class _FakeTransport:
    """Only records fake tool calls; never opens OAuth or a real MCP session."""

    def __init__(self, world: _World) -> None:
        self.world = world

    def __enter__(self) -> _FakeTransport:
        self.world.opens += 1
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        del exc_type, exc, traceback
        self.world.closes += 1
        return False

    def _record(self, name: str, arguments: Mapping[str, object]) -> None:
        self.world.calls.append((name, dict(arguments)))

    def get_accounts(self) -> Mapping[str, object]:
        self._record("get_accounts", {})
        return {
            "data": {
                "accounts": [
                    {
                        "account_number": _ACCOUNT,
                        "agentic_allowed": True,
                        "brokerage_account_type": "individual",
                        "state": "active",
                        "deactivated": False,
                        "permanently_deactivated": False,
                    }
                ]
            }
        }

    def get_portfolio(self, arguments: Mapping[str, object]) -> Mapping[str, object]:
        self._record("get_portfolio", arguments)
        return {
            "data": {
                "total_value": "10000",
                "cash": "8000",
                "equity_value": "2000",
                "currency": "USD",
                "buying_power": {
                    "display_currency": "USD",
                    "buying_power": "500",
                    "unleveraged_buying_power": "300",
                },
            }
        }

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("get_equity_positions", arguments)
        return self.world.position_pages.get(arguments.get("cursor"), {})

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("get_equity_orders", arguments)
        return self.world.order_pages.get(arguments.get("cursor"), {})

    def get_equity_quotes(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("get_equity_quotes", arguments)
        symbols = arguments.get("symbols")
        return {
            "data": {
                "results": [{"quote": _quote(str(symbol))} for symbol in symbols or ()]
            }
        }

    def get_equity_tradability(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("get_equity_tradability", arguments)
        symbol = arguments["symbols"][0]
        return {
            "data": {
                "results": [
                    {
                        "symbol": symbol,
                        "state": "active",
                        "halted": False,
                        "tradeable": True,
                        "regular_session_eligible": True,
                        "fractional_entry_supported": True,
                        "fractional_tradability": "tradable",
                        "account_type_tradabilities": [
                            {
                                "account_type": "individual",
                                "account_type_tradability": "tradable",
                            }
                        ],
                        "stop_market_supported": True,
                        "fractional_stop_supported": False,
                        "exact_stop_price_supported": True,
                    }
                ]
            }
        }

    def get_trade_approval_setting(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("get_trade_approval_setting", arguments)
        return {"data": {"enabled": False}}

    def get_trade_approvals(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("get_trade_approvals", arguments)
        return self.world.approval_pages.get(arguments.get("cursor"), {})

    def review_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("review_equity_order", arguments)
        return self.world.review_payload

    def place_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("place_equity_order", arguments)
        return self.world.place_payload or {
            "data": {
                "order": {
                    "id": "provider-order-148",
                    "ref_id": arguments.get("ref_id"),
                }
            }
        }

    def cancel_equity_order(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        self._record("cancel_equity_order", arguments)
        return self.world.cancel_payload or {
            "data": {
                "order": {
                    "id": arguments.get("order_id"),
                    "state": "pending_cancel",
                }
            }
        }


def _capabilities() -> RobinhoodAdapterCapabilities:
    return RobinhoodAdapterCapabilities(
        test_only_positions_account_wide=True,
        test_only_orders_account_wide_all_agents=True,
        test_only_approval_requests_exhaustive=True,
        test_only_stop_market_gtc_supported=True,
    )


def _state(
    *,
    revision: int = 0,
    intents=(),
    positions=None,
    tracked_orders=(),
    proposal_reviews=(),
    account_fingerprint: str = _ACCOUNT_FP,
) -> RuntimeState:
    return RuntimeState(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        account_fingerprint=account_fingerprint,
        revision=revision,
        next_sequence=1
        + max((intent.logical_sequence for intent in intents), default=0),
        intents=tuple(intents),
        positions={} if positions is None else positions,
        approval_receipts=(),
        proposal_reviews=tuple(proposal_reviews),
        tracked_orders=tuple(tracked_orders),
        write_reservations=(),
    )


def _entry_intent(
    *,
    lifecycle: IntentLifecycle = IntentLifecycle.PROPOSED,
    quantity: Decimal = Decimal("10"),
    created_at: datetime = _NOW,
):
    return create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=1,
        kind=IntentKind.ENTRY,
        symbol=TQQQ,
        side=OrderSide.BUY,
        quantity=quantity,
        stop_price=None,
        created_at=created_at,
        lifecycle=lifecycle,
    )


def _stop_intent(
    *,
    lifecycle: IntentLifecycle = IntentLifecycle.PROPOSED,
    quantity: Decimal = Decimal("10"),
):
    return create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=2,
        kind=IntentKind.PROTECTIVE_STOP,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=quantity,
        stop_price=Decimal("97"),
        created_at=_NOW,
        lifecycle=lifecycle,
    )


def _broker(
    state: RuntimeState,
    *,
    orders: tuple[BrokerOrderFact, ...] = (),
    positions: Mapping[Symbol, Position] | None = None,
    position_owners: Mapping[Symbol, UUID | None] | None = None,
    review: BrokerReviewFacts | None = None,
    observed_at: datetime = _NOW,
) -> BrokerSnapshot:
    scope = ScopeFacts(
        account_fingerprint=_ACCOUNT_FP,
        all_agents=True,
        exhausted=True,
        page_count=1,
        observed_at=observed_at,
    )
    return BrokerSnapshot(
        observed_at=observed_at,
        source_identity=state.source_identity,
        session_fingerprint=state.session_fingerprint,
        state_revision=state.revision,
        account=AccountFacts(
            _ACCOUNT_FP,
            True,
            True,
            Decimal("8000"),
            Decimal("500"),
            Decimal("300"),
            Decimal("2000"),
            Decimal("2000"),
            observed_at,
        ),
        positions={} if positions is None else positions,
        position_owners={} if position_owners is None else position_owners,
        orders=orders,
        position_scope=scope,
        order_scope=scope,
        tradability={
            symbol: TradabilityFacts(
                symbol,
                observed_at,
                True,
                False,
                True,
                True,
                True,
                False,
                True,
            )
            for symbol in UNIVERSE_SYMBOLS
        },
        approvals=ApprovalFacts(
            _ACCOUNT_FP,
            state.source_identity,
            state.session_fingerprint,
            state.revision,
            False,
            (),
            True,
            observed_at,
            (),
        ),
        review=review,
    )


def _review_for(intent, state: RuntimeState, at: datetime = _NOW):
    return BrokerReviewFacts(
        account_fingerprint=state.account_fingerprint,
        source_identity=state.source_identity,
        session_fingerprint=state.session_fingerprint,
        state_revision=state.revision,
        ref_id=intent.ref_id,
        terms_digest=intent.terms_digest,
        status=ReviewStatus.ACCEPTED,
        warnings=(),
        approval_required=False,
        observed_at=at,
    )


class _MemoryStore:
    def __init__(self, state: RuntimeState) -> None:
        self.state = state

    def load(self, owner_id: UUID, source_identity: SourceIdentity):
        if (
            self.state.owner_id != owner_id
            or self.state.source_identity != source_identity
        ):
            return None
        return self.state

    def compare_and_swap(
        self, expected_revision: int, next_state: RuntimeState
    ) -> bool:
        if self.state.revision != expected_revision:
            return False
        self.state = next_state
        return True


def _adapter(world: _World, *, complete: bool = True) -> RobinhoodMcpAdapter:
    return RobinhoodMcpAdapter(
        world.factory,
        capabilities=_capabilities() if complete else None,
    )


def test_construction_is_inert_and_default_scope_is_not_promoted() -> None:
    world = _World()
    adapter = _adapter(world, complete=False)
    state = _state()

    assert world.factory_calls == 0
    assert world.calls == []
    snapshot = adapter.read_snapshot(_NOW, state)

    assert snapshot.position_scope.exhausted
    assert not snapshot.position_scope.all_agents
    assert snapshot.order_scope.exhausted
    assert not snapshot.order_scope.all_agents
    assert not snapshot.approvals.exhaustive
    assert (
        "get_equity_orders",
        {"account_number": _ACCOUNT, "placed_agent": "agentic"},
    ) in world.calls
    assert world.opens == world.closes == 1


def test_fake_complete_reads_paginate_and_bind_first_entry_fill_without_ref_echo() -> (
    None
):
    intent = _entry_intent(lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED)
    tracked = TrackedOrder(
        intent.intent_id, intent.ref_id, provider_order_id="entry-order"
    )
    state = _state(intents=(intent,), tracked_orders=(tracked,))
    world = _World()
    world.position_pages = {
        None: {
            "data": {
                "positions": [
                    {
                        "symbol": "TQQQ",
                        "quantity": "10",
                        "shares_available_for_sells": "10",
                        "average_buy_price": "100",
                        "type": "long",
                    }
                ],
                "next": "position-page-2",
            }
        },
        "position-page-2": {"data": {"positions": [], "next": None}},
    }
    world.order_pages = {
        None: {
            "data": {
                "orders": [_order_row(ref_id=None)],
                "next": "order-page-2",
            }
        },
        "order-page-2": {"data": {"orders": [], "next": None}},
    }
    adapter = _adapter(world)

    snapshot = adapter.read_snapshot(_NOW, state)

    assert snapshot.position_scope.all_agents and snapshot.position_scope.exhausted
    assert snapshot.order_scope.all_agents and snapshot.order_scope.exhausted
    assert snapshot.position_scope.page_count == snapshot.order_scope.page_count == 2
    assert snapshot.positions[TQQQ] == Position(TQQQ, Decimal("10"), Decimal("100"))
    assert snapshot.orders[0].ref_id is None
    assert snapshot.orders[0].intent_id == intent.intent_id
    assert snapshot.position_owners[TQQQ] == intent.intent_id
    assert [
        arguments for name, arguments in world.calls if name == "get_equity_positions"
    ] == [
        {"account_number": _ACCOUNT},
        {"account_number": _ACCOUNT, "cursor": "position-page-2"},
    ]
    assert [
        arguments for name, arguments in world.calls if name == "get_equity_orders"
    ] == [
        {"account_number": _ACCOUNT},
        {"account_number": _ACCOUNT, "cursor": "order-page-2"},
    ]


def test_first_fill_can_bind_unique_may_entry_without_ref_or_provider_id() -> None:
    intent = _entry_intent()
    initial = _state(intents=(intent,))
    world = _World()
    adapter = _adapter(world)
    before = adapter.read_snapshot(_NOW, initial)
    review = adapter.review_order(intent, before, observed_at=_NOW)
    reviewed = replace(before, review=review)
    store = _MemoryStore(initial)
    reserved = OrderTracker(store).begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=initial.revision,
        intent_id=intent.intent_id,
        broker=reviewed,
        as_of=_NOW,
    )
    assert reserved is not None
    assert reserved.state.positions == {}
    assert reserved.state.tracked_orders[0].provider_order_id is None

    world.position_pages = {
        None: {
            "data": {
                "positions": [
                    {
                        "symbol": "TQQQ",
                        "quantity": "10",
                        "shares_available_for_sells": "10",
                        "average_buy_price": "100",
                        "type": "long",
                    }
                ],
                "next": None,
            }
        }
    }
    world.order_pages = {
        None: {"data": {"orders": [_order_row(ref_id=None)], "next": None}}
    }

    snapshot = adapter.read_snapshot(_NOW, reserved.state)

    assert snapshot.orders[0].ref_id is None
    assert snapshot.orders[0].provider_order_id == "entry-order"
    assert snapshot.orders[0].intent_id == intent.intent_id
    assert snapshot.position_owners[TQQQ] == intent.intent_id


def test_missing_cursor_and_account_drift_never_claim_complete_scope() -> None:
    state = _state()
    world = _World()
    world.order_pages[None] = {"data": {"orders": []}}
    adapter = _adapter(world)

    snapshot = adapter.read_snapshot(_NOW, state)
    assert not snapshot.order_scope.exhausted
    assert not snapshot.order_scope.all_agents

    wrong = _state(account_fingerprint="b" * 64)
    other_world = _World()
    with pytest.raises(RobinhoodAdapterIdentityError):
        _adapter(other_world).read_snapshot(_NOW, wrong)
    assert other_world.calls == [("get_accounts", {})]


def test_quote_and_review_queries_keep_exact_regular_hours_terms() -> None:
    intent = _entry_intent()
    state = _state(intents=(intent,))
    world = _World()
    adapter = _adapter(world)
    broker = adapter.read_snapshot(_NOW, state)

    prices = adapter.read_quotes(_NOW, now=_NOW)
    review = adapter.review_order(intent, broker, observed_at=_NOW)

    assert tuple(prices) == UNIVERSE_SYMBOLS
    assert prices[TQQQ].price == Decimal("100.5")
    assert (
        "get_equity_quotes",
        {"symbols": ["QQQ", "TQQQ", "SQQQ"]},
    ) in world.calls
    review_call = next(
        args for name, args in world.calls if name == "review_equity_order"
    )
    assert review_call == {
        "account_number": _ACCOUNT,
        "market_hours": "regular_hours",
        "quantity": "10",
        "side": "buy",
        "symbol": "TQQQ",
        "time_in_force": "gfd",
        "type": "market",
    }
    assert review.ref_id == intent.ref_id
    assert review.terms_digest == intent.terms_digest
    assert review.status is ReviewStatus.ACCEPTED
    assert review.state_revision == state.revision
    assert not any(name == "place_equity_order" for name, _ in world.calls)


def test_stop_review_uses_whole_share_gTC_stop_market_and_blocks_fractional() -> None:
    intent = _stop_intent()
    state = _state(intents=(intent,))
    world = _World()
    world.review_payload = _review_response(
        side="sell",
        order_type="stop_market",
        quantity="10",
        stop_price="97",
        time_in_force="gtc",
    )
    adapter = _adapter(world)
    broker = adapter.read_snapshot(_NOW, state)

    review = adapter.review_order(intent, broker, observed_at=_NOW)

    args = next(args for name, args in world.calls if name == "review_equity_order")
    assert args == {
        "account_number": _ACCOUNT,
        "market_hours": "regular_hours",
        "quantity": "10",
        "side": "sell",
        "stop_price": "97",
        "symbol": "TQQQ",
        "time_in_force": "gtc",
        "type": "stop_market",
    }
    assert review.status is ReviewStatus.ACCEPTED

    fractional = _stop_intent(quantity=Decimal("10.5"))
    before = world.factory_calls
    with pytest.raises(RobinhoodAdapterUnavailableError):
        adapter.review_order(fractional, broker, observed_at=_NOW)
    assert world.factory_calls == before


def test_place_requires_durable_reservation_and_consumes_one_shot_permit() -> None:
    intent = _entry_intent()
    initial = _state(intents=(intent,))
    world = _World()
    adapter = _adapter(world)
    broker = adapter.read_snapshot(_NOW, initial)
    review = adapter.review_order(intent, broker, observed_at=_NOW)
    reviewed = BrokerSnapshot(
        broker.observed_at,
        broker.source_identity,
        broker.session_fingerprint,
        broker.state_revision,
        broker.account,
        broker.positions,
        broker.position_owners,
        broker.orders,
        broker.position_scope,
        broker.order_scope,
        broker.tradability,
        broker.approvals,
        review,
    )
    store = _MemoryStore(initial)
    reservation_result = OrderTracker(store).begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=initial.revision,
        intent_id=intent.intent_id,
        broker=reviewed,
        as_of=_NOW,
    )
    assert reservation_result is not None
    factory_calls_before_forged_permit = world.factory_calls
    with pytest.raises(RobinhoodAdapterUnavailableError):
        adapter.place_order(
            state=reservation_result.state,
            reservation=reservation_result.reservation,
            broker=reviewed,
            permit=object(),  # type: ignore[arg-type]
            observed_at=_NOW,
        )
    assert world.factory_calls == factory_calls_before_forged_permit

    stale_tradability = dict(reviewed.tradability)
    stale_tradability[TQQQ] = replace(
        stale_tradability[TQQQ], observed_at=_NOW - timedelta(minutes=1)
    )
    stale_broker = replace(reviewed, tradability=stale_tradability)
    with pytest.raises(RobinhoodAdapterUnavailableError):
        adapter.place_order(
            state=reservation_result.state,
            reservation=reservation_result.reservation,
            broker=stale_broker,
            permit=reservation_result.permit,
            observed_at=_NOW,
        )
    assert not any(name == "place_equity_order" for name, _ in world.calls)

    outcome = adapter.place_order(
        state=reservation_result.state,
        reservation=reservation_result.reservation,
        broker=reviewed,
        permit=reservation_result.permit,
        observed_at=_NOW,
    )

    assert outcome.status is RobinhoodEffectStatus.PLACED
    assert outcome.provider_order_id == "provider-order-148"
    place_args = next(
        args for name, args in world.calls if name == "place_equity_order"
    )
    review_args = next(
        args for name, args in world.calls if name == "review_equity_order"
    )
    assert place_args == {**review_args, "ref_id": intent.ref_id}
    with pytest.raises(RobinhoodAdapterUnavailableError):
        adapter.place_order(
            state=reservation_result.state,
            reservation=reservation_result.reservation,
            broker=reviewed,
            permit=reservation_result.permit,
            observed_at=_NOW,
        )
    assert sum(name == "place_equity_order" for name, _ in world.calls) == 1


def test_cancel_requires_exact_tracked_stop_ownership_and_its_own_permit() -> None:
    entry = _entry_intent(lifecycle=IntentLifecycle.RECONCILED)
    stop = _stop_intent(lifecycle=IntentLifecycle.RECONCILED)
    entry_fact = BrokerOrderFact(
        "entry-order",
        _ACCOUNT_FP,
        _SOURCE,
        entry.intent_id,
        entry.ref_id,
        IntentKind.ENTRY,
        TQQQ,
        OrderSide.BUY,
        OrderState.FILLED,
        Decimal("10"),
        Decimal("10"),
        Decimal("0"),
        None,
        _NOW,
        Decimal("100"),
    )
    stop_fact = BrokerOrderFact(
        "stop-order",
        _ACCOUNT_FP,
        _SOURCE,
        stop.intent_id,
        stop.ref_id,
        IntentKind.PROTECTIVE_STOP,
        TQQQ,
        OrderSide.SELL,
        OrderState.OPEN,
        Decimal("10"),
        Decimal("0"),
        Decimal("10"),
        Decimal("97"),
        _NOW,
    )
    state = _state(
        revision=4,
        intents=(entry, stop),
        positions={
            TQQQ: OwnedPositionRecord(
                TQQQ,
                entry.intent_id,
                Decimal("10"),
                Decimal("100"),
                Decimal("97"),
                stop.intent_id,
            )
        },
        tracked_orders=(
            TrackedOrder(
                entry.intent_id,
                entry.ref_id,
                provider_order_id="entry-order",
                last_fact=entry_fact,
            ),
            TrackedOrder(
                stop.intent_id,
                stop.ref_id,
                provider_order_id="stop-order",
                last_fact=stop_fact,
            ),
        ),
    )
    broker = _broker(
        state,
        orders=(entry_fact, stop_fact),
        positions={TQQQ: Position(TQQQ, Decimal("10"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
    )
    store = _MemoryStore(state)
    candidate = ProtectiveStopCancelCandidate(
        intent_id=stop.intent_id,
        ref_id=stop.ref_id,
        provider_order_id="stop-order",
        terms_digest=stop.terms_digest,
        fact=stop_fact,
        held_price=PriceObservation(TQQQ, Decimal("96"), _NOW),
        expected_state_revision=state.revision,
        exit_reasons=(AdmissionBlocker.STOP_BREACH,),
    )
    reservation_result = OrderTracker(store).begin_cancel(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=state.revision,
        candidate=candidate,
        broker=broker,
        as_of=_NOW,
    )
    assert reservation_result is not None

    world = _World()
    adapter = _adapter(world)
    bad_broker = BrokerSnapshot(
        broker.observed_at,
        broker.source_identity,
        broker.session_fingerprint,
        broker.state_revision,
        broker.account,
        broker.positions,
        broker.position_owners,
        (entry_fact,),
        broker.position_scope,
        broker.order_scope,
        broker.tradability,
        broker.approvals,
        None,
    )
    with pytest.raises(RobinhoodAdapterUnavailableError):
        adapter.cancel_order(
            state=reservation_result.state,
            reservation=reservation_result.reservation,
            broker=bad_broker,
            permit=reservation_result.permit,
            observed_at=_NOW,
        )
    assert world.factory_calls == 0

    outcome = adapter.cancel_order(
        state=reservation_result.state,
        reservation=reservation_result.reservation,
        broker=broker,
        permit=reservation_result.permit,
        observed_at=_NOW,
    )
    assert outcome.status is RobinhoodEffectStatus.CANCEL_REQUESTED
    assert outcome.provider_order_id == "stop-order"
    assert [args for name, args in world.calls if name == "cancel_equity_order"] == [
        {"account_number": _ACCOUNT, "order_id": "stop-order"}
    ]
