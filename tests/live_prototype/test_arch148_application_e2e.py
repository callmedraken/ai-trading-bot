"""Fake-only end-to-end Architecture 148 worker/application composition."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import Position
from trading_bot.live_prototype.contracts import Command, Lifecycle
from trading_bot.live_runtime.application import CycleApplicationService
from trading_bot.live_runtime.gui_adapter import Arch148RuntimeDisplayCache
from trading_bot.live_runtime.models import (
    SQQQ,
    TQQQ,
    UNIVERSE_SYMBOLS,
    AccountFacts,
    ApprovalFacts,
    BrokerOrderFact,
    BrokerReviewFacts,
    BrokerSnapshot,
    CompletedBar,
    ExecutionProfile,
    IntentKind,
    IntentLifecycle,
    MarketSnapshot,
    OrderState,
    PriceObservation,
    ReviewStatus,
    RuntimeState,
    ScopeFacts,
    SourceIdentity,
    TargetPosition,
    TradabilityFacts,
)
from trading_bot.live_runtime.order_tracker import (
    OrderTracker,
    OrderWriteAction,
    validate_order_write_reservation,
)
from trading_bot.live_runtime.service import (
    Arch148RuntimeBindings,
    Arch148RuntimeService,
)
from trading_bot.live_runtime.state_store import SQLiteRuntimeStateStore
from trading_bot.live_runtime.strategy import (
    MarketQuality,
    MarketRegime,
    analyze_market,
    confirmed_regime_exit,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.risk import RiskLimits, RiskManager

_OWNER = UUID("0b968db5-3257-53d1-8b55-cad031a045a8")
_SOURCE = SourceIdentity("a" * 40, "b" * 40)
_ACCOUNT = "c" * 64
_SESSION = "d" * 64
_NY = ZoneInfo("America/New_York")
_OPEN_AS_OF = datetime(2026, 11, 19, 15, 45, tzinfo=UTC)
_NEUTRAL_AS_OF = datetime(2026, 11, 19, 17, 0, tzinfo=UTC)
_BAR_WIDTH = timedelta(minutes=5)
_TEST_PRICE = Decimal("5")


class _MutableClock:
    def __init__(self, value: datetime) -> None:
        self._lock = threading.Lock()
        self._value = value

    def __call__(self) -> datetime:
        with self._lock:
            return self._value

    def set(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("test clock must be timezone-aware")
        with self._lock:
            self._value = value.astimezone(UTC)


class _SyntheticQQQMarket:
    def __init__(
        self, mode: str = "BULLISH", *, timeline: list[tuple] | None = None
    ) -> None:
        self.mode = mode
        self.read_count = 0
        self.last_as_of: datetime | None = None
        self.timeline = timeline if timeline is not None else []

    def read_snapshot(self, as_of: datetime) -> MarketSnapshot:
        self.read_count += 1
        self.last_as_of = as_of
        self.timeline.append(("MARKET_SNAPSHOT", self.mode, as_of))
        authority = NYSEPublishedRegularSessionAuthority()
        current_date = as_of.astimezone(_NY).date()
        current_schedule = authority.schedule_for(current_date)
        previous_schedule = authority.schedule_for(current_date - timedelta(days=1))
        assert current_schedule is not None and previous_schedule is not None
        bars = [
            _bar(previous_schedule.opens_at + index * _BAR_WIDTH, Decimal("100"))
            for index in range(78)
        ]
        completed_count = int((as_of - current_schedule.opens_at) // _BAR_WIDTH)
        completed_count = min(78, max(0, completed_count))
        for index in range(completed_count):
            if self.mode == "BULLISH":
                close = Decimal("101") + Decimal("0.1") * index
            elif self.mode == "NEUTRAL":
                close = Decimal("100")
            elif self.mode == "BEARISH":
                close = Decimal("100") - Decimal("0.2") * index
            elif self.mode == "MISSING_CURRENT_OPEN" and index == 0:
                continue
            else:
                close = Decimal("100")
            bars.append(_bar(current_schedule.opens_at + index * _BAR_WIDTH, close))
        prices = {
            symbol: PriceObservation(symbol, _TEST_PRICE, as_of)
            for symbol in (TQQQ, SQQQ)
        }
        return MarketSnapshot(as_of, tuple(bars), (), prices)


def _bar(timestamp: datetime, close: Decimal) -> CompletedBar:
    return CompletedBar(timestamp, close, close, close, close, 100)


class _FakeBrokerAdapter:
    """Exact fake broker facade; all reads and writes stay in-memory."""

    def __init__(
        self,
        *,
        ambiguous_next_place: bool = False,
        ambiguous_place_kind: IntentKind | None = None,
        timeline: list[tuple] | None = None,
    ) -> None:
        self.snapshot_reads = 0
        self.reviewed: list[tuple[IntentKind, object]] = []
        self.events: list[tuple[str, IntentKind, object]] = []
        self.place_states: list[RuntimeState] = []
        self.place_reservations = []
        self.cancel_reservations = []
        self.snapshots: list[BrokerSnapshot] = []
        self._positions: dict = {}
        self._position_owners: dict = {}
        self._orders: dict[str, BrokerOrderFact] = {}
        self._next_order_number = 1
        self.ambiguous_next_place = ambiguous_next_place
        self.ambiguous_place_kind = ambiguous_place_kind
        self.timeline = timeline if timeline is not None else []

    def read_snapshot(self, as_of: datetime, state: RuntimeState) -> BrokerSnapshot:
        self.snapshot_reads += 1
        account = AccountFacts(
            state.account_fingerprint,
            True,
            True,
            Decimal("10000"),
            Decimal("10000"),
            Decimal("10000"),
            Decimal("10000"),
            Decimal("0"),
            as_of,
        )
        scope = ScopeFacts(state.account_fingerprint, True, True, 1, as_of)
        approvals = ApprovalFacts(
            state.account_fingerprint,
            state.source_identity,
            state.session_fingerprint,
            state.revision,
            False,
            (),
            True,
            as_of,
        )
        tradability = {
            symbol: TradabilityFacts(
                symbol, as_of, True, False, True, True, True, True, True
            )
            for symbol in UNIVERSE_SYMBOLS
        }
        orders = tuple(
            replace(order, observed_at=as_of) for order in self._orders.values()
        )
        snapshot = BrokerSnapshot(
            as_of,
            state.source_identity,
            state.session_fingerprint,
            state.revision,
            account,
            dict(self._positions),
            dict(self._position_owners),
            orders,
            scope,
            scope,
            tradability,
            approvals,
            None,
        )
        self.snapshots.append(snapshot)
        self.timeline.append(
            ("BROKER_SNAPSHOT", tuple(symbol.value for symbol in snapshot.positions))
        )
        return snapshot

    def review_order(
        self,
        intent,
        broker: BrokerSnapshot,
        *,
        observed_at: datetime,
    ) -> BrokerReviewFacts:
        self.reviewed.append((intent.kind, intent.symbol))
        self.timeline.append(("REVIEW", intent.kind.value, intent.symbol.value))
        return BrokerReviewFacts(
            broker.account.fingerprint,
            broker.source_identity,
            broker.session_fingerprint,
            broker.state_revision,
            intent.ref_id,
            intent.terms_digest,
            ReviewStatus.ACCEPTED,
            (),
            False,
            observed_at,
        )

    def place_order(
        self,
        *,
        state: RuntimeState,
        reservation,
        permit,
        broker: BrokerSnapshot,
        observed_at: datetime,
    ) -> object:
        assert validate_order_write_reservation(state, reservation)
        assert permit.consume(reservation, action=OrderWriteAction.PLACE)
        intent = next(
            item for item in state.intents if item.intent_id == reservation.intent_id
        )
        self.events.append(("PLACE", intent.kind, intent.symbol))
        self.timeline.append(("PLACE", intent.kind.value, intent.symbol.value))
        self.place_states.append(state)
        self.place_reservations.append(reservation)
        if self.ambiguous_next_place or self.ambiguous_place_kind is intent.kind:
            self.ambiguous_next_place = False
            self.ambiguous_place_kind = None
            raise RuntimeError("fake placement outcome is ambiguous")
        provider_id = f"fake-provider-order-{self._next_order_number}"
        self._next_order_number += 1
        if intent.kind is IntentKind.ENTRY:
            order = _fact(
                intent,
                provider_id,
                OrderState.FILLED,
                observed_at,
                filled=intent.quantity,
                remaining=Decimal("0"),
                average_fill=_TEST_PRICE,
            )
            self._positions[intent.symbol] = Position(
                intent.symbol, intent.quantity, _TEST_PRICE
            )
            self._position_owners[intent.symbol] = intent.intent_id
        elif intent.kind is IntentKind.PROTECTIVE_STOP:
            order = _fact(
                intent,
                provider_id,
                OrderState.OPEN,
                observed_at,
                filled=Decimal("0"),
                remaining=intent.quantity,
                average_fill=None,
            )
        elif intent.kind is IntentKind.EXIT:
            order = _fact(
                intent,
                provider_id,
                OrderState.FILLED,
                observed_at,
                filled=intent.quantity,
                remaining=Decimal("0"),
                average_fill=_TEST_PRICE,
            )
            self._positions.pop(intent.symbol, None)
            self._position_owners.pop(intent.symbol, None)
        else:
            raise AssertionError(f"unexpected intent kind {intent.kind}")
        self._orders[provider_id] = order
        return SimpleNamespace(status="PLACED")

    def cancel_order(
        self,
        *,
        state: RuntimeState,
        reservation,
        permit,
        broker: BrokerSnapshot,
        observed_at: datetime,
    ) -> object:
        assert validate_order_write_reservation(state, reservation)
        assert permit.consume(reservation, action=OrderWriteAction.CANCEL)
        target = reservation.target_provider_order_id
        assert target is not None and target in self._orders
        current = self._orders[target]
        assert current.state in (OrderState.OPEN, OrderState.PARTIALLY_FILLED)
        self.events.append(("CANCEL", current.kind, current.symbol))
        self.timeline.append(("CANCEL", current.kind.value, current.symbol.value))
        self.cancel_reservations.append(reservation)
        self._orders[target] = replace(
            current,
            state=OrderState.CANCELED,
            observed_at=observed_at,
        )
        return SimpleNamespace(status="CANCEL_REQUESTED")


def _fact(
    intent,
    provider_id: str,
    state: OrderState,
    observed_at: datetime,
    *,
    filled: Decimal,
    remaining: Decimal,
    average_fill: Decimal | None,
) -> BrokerOrderFact:
    return BrokerOrderFact(
        provider_id,
        _ACCOUNT,
        _SOURCE,
        intent.intent_id,
        intent.ref_id,
        intent.kind,
        intent.symbol,
        intent.side,
        state,
        intent.quantity,
        filled,
        remaining,
        intent.stop_price,
        observed_at,
        average_fill,
    )


class _TQQQOnlyAuthority:
    """Explicit fake policy: this E2E never authorizes inverse re-entry."""

    def allows_place(self, intent, *, state, result, broker) -> bool:
        return intent.symbol == TQQQ


class _BothEtfAuthority:
    """Explicit fake policy admitting either reviewed ETF entry."""

    def allows_place(self, intent, *, state, result, broker) -> bool:
        return intent.symbol in (TQQQ, SQQQ)


class _ExactCancelAuthority:
    def allows_cancel(self, candidate, *, state, result, broker) -> bool:
        return candidate.fact.provider_order_id in {
            fact.provider_order_id
            for fact in broker.orders
            if fact.kind is IntentKind.PROTECTIVE_STOP
        }


def _initial_state() -> RuntimeState:
    return RuntimeState(_OWNER, _SOURCE, _SESSION, _ACCOUNT, 0, 1, (), {}, ())


def _lease_factory(lock: threading.Lock):
    @contextmanager
    def lease():
        if not lock.acquire(blocking=False):
            yield False
            return
        try:
            yield True
        finally:
            lock.release()

    return lease


def _service(
    *,
    store: SQLiteRuntimeStateStore,
    clock: _MutableClock,
    market: _SyntheticQQQMarket,
    broker: _FakeBrokerAdapter,
    lease_lock: threading.Lock,
    cadence: timedelta,
    display_cache: Arch148RuntimeDisplayCache,
    effect_authority=None,
) -> Arch148RuntimeService:
    application = CycleApplicationService(
        risk_manager=RiskManager(RiskLimits(max_order_notional=Decimal("10"))),
        state_store=store,
        session_authority=NYSEPublishedRegularSessionAuthority(),
    )

    @contextmanager
    def bindings_factory():
        yield Arch148RuntimeBindings(
            _OWNER,
            _SOURCE,
            _SESSION,
            application,
            store,
            OrderTracker(store),
            market,
            broker,
            clock,
            execution_profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
        )

    return Arch148RuntimeService(
        bindings_factory,
        owner_lease_factory=_lease_factory(lease_lock),
        cadence=cadence,
        effect_authority=effect_authority or _TQQQOnlyAuthority(),
        cancel_effect_authority=_ExactCancelAuthority(),
        display_cache=display_cache,
        worker_clock=clock,
    )


@pytest.fixture
def cleanup_services(request):
    services = []

    def register(service):
        services.append(service)
        return service

    def stop_services() -> None:
        for service in services:
            if service.snapshot().lifecycle is not Lifecycle.STOPPED:
                service.submit(Command.STOP)
            service.wait(3)

    request.addfinalizer(stop_services)
    return register


def _wait_for(predicate, *, timeout: float = 6.0, diagnostic=None) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    details = diagnostic() if diagnostic is not None else ""
    assert predicate(), f"timed out waiting for fake runtime state: {details}"


def _diagnostic(service, cache, store, broker) -> str:
    state = store.load(_OWNER, _SOURCE)
    worker = service.snapshot()
    facts = cache.read()
    events = tuple(
        (kind, action.value, symbol.value) for kind, action, symbol in broker.events
    )
    reviews = tuple((kind.value, symbol.value) for kind, symbol in broker.reviewed)
    intents = tuple((item.kind.value, item.lifecycle.value) for item in state.intents)
    positions = tuple(symbol.value for symbol in state.positions)
    return (
        f"events={events!r}; reviews={reviews!r}; "
        f"lifecycle={worker.lifecycle.value}/{worker.restricted_live_reason_code}; "
        f"health={facts.health}; blockers={facts.blockers!r}; "
        f"intents={intents!r}; positions={positions!r}; "
        f"pending_exit={state.pending_exit!r}"
    )


def test_start_warms_signal_places_and_protects_then_exits_through_cancel(
    tmp_path: Path,
    cleanup_services,
) -> None:
    clock = _MutableClock(_OPEN_AS_OF)
    timeline: list[tuple] = []
    market = _SyntheticQQQMarket("BULLISH", timeline=timeline)
    broker = _FakeBrokerAdapter(timeline=timeline)
    authority = NYSEPublishedRegularSessionAuthority()
    bullish = analyze_market(market.read_snapshot(_OPEN_AS_OF), authority=authority)
    assert bullish.quality is MarketQuality.READY
    assert bullish.entry_confirmation is MarketRegime.BULLISH
    assert bullish.latest is not None and bullish.previous is not None
    assert bullish.latest.bar_end - bullish.previous.bar_end == _BAR_WIDTH
    timeline.clear()

    state_store = SQLiteRuntimeStateStore.create(
        tmp_path / "arch148-e2e.sqlite", _initial_state()
    )
    cache = Arch148RuntimeDisplayCache()
    service = cleanup_services(
        _service(
            store=state_store,
            clock=clock,
            market=market,
            broker=broker,
            lease_lock=threading.Lock(),
            cadence=timedelta(milliseconds=500),
            display_cache=cache,
            effect_authority=_BothEtfAuthority(),
        )
    )

    assert service.snapshot().lifecycle is Lifecycle.STOPPED
    assert broker.snapshot_reads == 0
    assert service.submit(Command.START).accepted
    _wait_for(lambda: len(broker.place_reservations) >= 1)
    entry_state = broker.place_states[0]
    entry_intent = next(
        item for item in entry_state.intents if item.kind is IntentKind.ENTRY
    )
    assert entry_intent.symbol == TQQQ
    assert entry_intent.quantity == Decimal("2")
    assert entry_intent.lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
    assert entry_state.proposal_reviews[-1].ref_id == entry_intent.ref_id
    assert broker.place_reservations[0].action is OrderWriteAction.PLACE

    _wait_for(
        lambda: len(broker.place_reservations) >= 2,
        diagnostic=lambda: _diagnostic(service, cache, state_store, broker),
    )
    _wait_for(
        lambda: (
            TQQQ in state_store.load(_OWNER, _SOURCE).positions
            and state_store.load(_OWNER, _SOURCE).positions[TQQQ].stop_intent_id
            is not None
        )
    )
    protected = state_store.load(_OWNER, _SOURCE)
    owned = protected.positions[TQQQ]
    assert owned.quantity == Decimal("2")
    assert owned.average_entry_fill == _TEST_PRICE
    assert owned.hard_stop_price == Decimal("4.85")
    assert owned.stop_intent_id is not None
    stop_intent = next(
        item for item in protected.intents if item.intent_id == owned.stop_intent_id
    )
    assert stop_intent.kind is IntentKind.PROTECTIVE_STOP
    assert stop_intent.quantity == Decimal("2")
    assert stop_intent.stop_price == Decimal("4.85")
    assert broker.place_states[1].intents[-1].lifecycle is (
        IntentLifecycle.MAY_HAVE_OCCURRED
    )

    market.mode = "BEARISH"
    bearish_market = market.read_snapshot(_NEUTRAL_AS_OF)
    bearish_signal = analyze_market(bearish_market, authority=authority)
    assert bearish_signal.quality is MarketQuality.READY
    assert bearish_signal.latest is not None
    assert bearish_signal.previous is not None
    assert bearish_signal.latest.candidate is MarketRegime.BEARISH
    assert bearish_signal.previous.candidate is MarketRegime.BEARISH
    assert confirmed_regime_exit(bearish_signal, TargetPosition.TQQQ)
    clock.set(_NEUTRAL_AS_OF)
    _wait_for(lambda: len(broker.cancel_reservations) == 1)
    cancel_reservation = broker.cancel_reservations[0]
    assert cancel_reservation.action is OrderWriteAction.CANCEL
    assert cancel_reservation.target_provider_order_id is not None
    assert broker.events[:3] == [
        ("PLACE", IntentKind.ENTRY, TQQQ),
        ("PLACE", IntentKind.PROTECTIVE_STOP, TQQQ),
        ("CANCEL", IntentKind.PROTECTIVE_STOP, TQQQ),
    ]

    _wait_for(
        lambda: len(broker.place_reservations) >= 3,
        diagnostic=lambda: _diagnostic(service, cache, state_store, broker),
    )
    exit_state = broker.place_states[2]
    exit_intent = next(
        item
        for item in exit_state.intents
        if item.lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
    )
    assert exit_intent.kind is IntentKind.EXIT
    assert exit_intent.symbol == TQQQ
    assert exit_intent.quantity == Decimal("2")
    assert broker.place_reservations[2].action is OrderWriteAction.PLACE
    assert (IntentKind.EXIT, TQQQ) in broker.reviewed
    _wait_for(lambda: not state_store.load(_OWNER, _SOURCE).positions)
    flat_state = state_store.load(_OWNER, _SOURCE)
    assert flat_state.positions == {}
    assert (IntentKind.ENTRY, SQQQ) not in broker.reviewed
    assert not any(
        kind is IntentKind.ENTRY and symbol == SQQQ for _, kind, symbol in broker.events
    )
    _wait_for(
        lambda: (IntentKind.ENTRY, SQQQ) in broker.reviewed,
        diagnostic=lambda: _diagnostic(service, cache, state_store, broker),
    )

    exit_place_index = timeline.index(("PLACE", IntentKind.EXIT.value, TQQQ.value))
    sqqq_review_index = next(
        index
        for index, event in enumerate(timeline)
        if index > exit_place_index
        and event[:3] == ("REVIEW", IntentKind.ENTRY.value, SQQQ.value)
    )
    flat_snapshot_indices = tuple(
        index
        for index, event in enumerate(timeline)
        if exit_place_index < index < sqqq_review_index
        and event[0] == "BROKER_SNAPSHOT"
        and event[1] == ()
    )
    first_later_market_index = next(
        index
        for index, event in enumerate(timeline)
        if exit_place_index < index < sqqq_review_index
        and event[0] == "MARKET_SNAPSHOT"
    )
    assert len(flat_snapshot_indices) >= 3
    assert flat_snapshot_indices[2] < first_later_market_index

    _wait_for(
        lambda: len(broker.place_reservations) >= 5,
        diagnostic=lambda: _diagnostic(service, cache, state_store, broker),
    )
    _wait_for(
        lambda: (
            SQQQ in state_store.load(_OWNER, _SOURCE).positions
            and state_store.load(_OWNER, _SOURCE).positions[SQQQ].stop_intent_id
            is not None
        )
    )
    sqqq_state = state_store.load(_OWNER, _SOURCE)
    sqqq_position = sqqq_state.positions[SQQQ]
    assert sqqq_position.quantity == Decimal("2")
    assert sqqq_position.hard_stop_price == Decimal("4.85")
    assert (IntentKind.ENTRY, SQQQ) in broker.reviewed
    assert (IntentKind.PROTECTIVE_STOP, SQQQ) in broker.reviewed

    assert service.submit(Command.STOP).accepted
    assert service.wait(3)
    final_state = state_store.load(_OWNER, _SOURCE)
    assert TQQQ not in final_state.positions
    assert SQQQ in final_state.positions
    assert final_state.pending_exit is None
    assert all(
        intent.lifecycle is IntentLifecycle.RECONCILED
        for intent in final_state.intents
        if intent.kind
        in (IntentKind.ENTRY, IntentKind.PROTECTIVE_STOP, IntentKind.EXIT)
    )
    assert [item.action for item in final_state.write_reservations] == [
        OrderWriteAction.PLACE,
        OrderWriteAction.PLACE,
        OrderWriteAction.CANCEL,
        OrderWriteAction.PLACE,
        OrderWriteAction.PLACE,
        OrderWriteAction.PLACE,
    ]
    assert broker.events == [
        ("PLACE", IntentKind.ENTRY, TQQQ),
        ("PLACE", IntentKind.PROTECTIVE_STOP, TQQQ),
        ("CANCEL", IntentKind.PROTECTIVE_STOP, TQQQ),
        ("PLACE", IntentKind.EXIT, TQQQ),
        ("PLACE", IntentKind.ENTRY, SQQQ),
        ("PLACE", IntentKind.PROTECTIVE_STOP, SQQQ),
    ]
    sqqq_entry_event = ("PLACE", IntentKind.ENTRY, SQQQ)
    assert broker.events.index(sqqq_entry_event) > broker.events.index(
        ("PLACE", IntentKind.EXIT, TQQQ)
    )
    assert broker.cancel_reservations[0].target_provider_order_id is not None
    assert final_state.positions[SQQQ].stop_intent_id is not None
    assert final_state.positions[SQQQ].stop_intent_id == next(
        intent.intent_id
        for intent in final_state.intents
        if intent.kind is IntentKind.PROTECTIVE_STOP and intent.symbol == SQQQ
    )
    assert service.snapshot().lifecycle is Lifecycle.STOPPED
    assert cache.read().health == "STOP_RECONCILED"


def test_ambiguous_place_restarts_read_only_without_a_second_write(
    tmp_path: Path,
    cleanup_services,
) -> None:
    clock = _MutableClock(_OPEN_AS_OF)
    market = _SyntheticQQQMarket("BULLISH")
    broker = _FakeBrokerAdapter(ambiguous_next_place=True)
    store_path = tmp_path / "arch148-ambiguous.sqlite"
    first_store = SQLiteRuntimeStateStore.create(store_path, _initial_state())
    first = cleanup_services(
        _service(
            store=first_store,
            clock=clock,
            market=market,
            broker=broker,
            lease_lock=threading.Lock(),
            cadence=timedelta(milliseconds=10),
            display_cache=Arch148RuntimeDisplayCache(),
        )
    )

    assert first.submit(Command.START).accepted
    _wait_for(lambda: len(broker.place_reservations) == 1)
    assert first.wait(5)
    persisted = first_store.load(_OWNER, _SOURCE)
    assert persisted.intents[0].lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
    assert len(persisted.write_reservations) == 1
    assert broker.events == [("PLACE", IntentKind.ENTRY, TQQQ)]

    reopened_store = SQLiteRuntimeStateStore.open(
        store_path,
        owner_id=_OWNER,
        source_identity=_SOURCE,
        account_fingerprint=_ACCOUNT,
        session_fingerprint=_SESSION,
    )
    restarted = cleanup_services(
        _service(
            store=reopened_store,
            clock=clock,
            market=market,
            broker=broker,
            lease_lock=threading.Lock(),
            cadence=timedelta(milliseconds=10),
            display_cache=Arch148RuntimeDisplayCache(),
        )
    )
    assert restarted.submit(Command.START).accepted
    assert restarted.wait(3)

    assert len(broker.place_reservations) == 1
    assert broker.events == [("PLACE", IntentKind.ENTRY, TQQQ)]
    assert broker.reviewed == [(IntentKind.ENTRY, TQQQ)]
    assert reopened_store.load(_OWNER, _SOURCE).write_reservations == (
        persisted.write_reservations
    )
    assert restarted.snapshot().lifecycle is Lifecycle.BLOCKED


def test_ambiguous_protective_stop_keeps_holding_blocked_without_retry(
    tmp_path: Path,
    cleanup_services,
) -> None:
    clock = _MutableClock(_OPEN_AS_OF)
    market = _SyntheticQQQMarket("BULLISH")
    broker = _FakeBrokerAdapter(ambiguous_place_kind=IntentKind.PROTECTIVE_STOP)
    store = SQLiteRuntimeStateStore.create(
        tmp_path / "arch148-stop-ambiguous.sqlite", _initial_state()
    )
    cache = Arch148RuntimeDisplayCache()
    service = cleanup_services(
        _service(
            store=store,
            clock=clock,
            market=market,
            broker=broker,
            lease_lock=threading.Lock(),
            cadence=timedelta(milliseconds=100),
            display_cache=cache,
        )
    )

    assert service.submit(Command.START).accepted
    _wait_for(
        lambda: len(broker.events) >= 2,
        diagnostic=lambda: _diagnostic(service, cache, store, broker),
    )
    protective_attempts = tuple(
        event for event in broker.events if event[1] is IntentKind.PROTECTIVE_STOP
    )
    assert protective_attempts == (broker.events[1],)
    reads_after_ambiguous_place = broker.snapshot_reads
    _wait_for(lambda: broker.snapshot_reads > reads_after_ambiguous_place)

    state = store.load(_OWNER, _SOURCE)
    assert set(state.positions) == {TQQQ}
    assert state.positions[TQQQ].stop_intent_id is None
    stop_intents = tuple(
        intent for intent in state.intents if intent.kind is IntentKind.PROTECTIVE_STOP
    )
    assert len(stop_intents) == 1
    assert stop_intents[0].lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
    assert sum(event[1] is IntentKind.PROTECTIVE_STOP for event in broker.events) == 1
    assert service.submit(Command.STOP).accepted
    assert service.wait(3)
    assert broker.events == [
        ("PLACE", IntentKind.ENTRY, TQQQ),
        ("PLACE", IntentKind.PROTECTIVE_STOP, TQQQ),
    ]
