from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.desktop_runtime import LifecycleJournal
from trading_bot.domain import OrderSide, Position
from trading_bot.live_prototype.contracts import Command, Lifecycle
from trading_bot.live_prototype.l43_runtime import L43SerializedLifecycleInterlock
from trading_bot.live_runtime.application import CycleApplicationService
from trading_bot.live_runtime.gui_adapter import Arch148RuntimeDisplayCache
from trading_bot.live_runtime.identity import create_order_intent
from trading_bot.live_runtime.models import (
    SQQQ,
    TQQQ,
    UNIVERSE_SYMBOLS,
    AccountFacts,
    AdmissionBlocker,
    ApprovalFacts,
    BrokerOrderFact,
    BrokerReviewFacts,
    BrokerSnapshot,
    CompletedBar,
    CycleResult,
    CycleStatus,
    ExecutionProfile,
    IntentKind,
    IntentLifecycle,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    OrderState,
    OwnedPositionRecord,
    PriceObservation,
    ProtectiveStopCancelCandidate,
    ReviewStatus,
    RuntimeState,
    ScopeFacts,
    SignalAnalysis,
    SourceIdentity,
    TargetPosition,
    TradabilityFacts,
)
from trading_bot.live_runtime.order_tracker import (
    OrderTracker,
    OrderWriteAction,
    TrackedOrder,
    validate_order_write_reservation,
)
from trading_bot.live_runtime.service import (
    Arch148RuntimeBindings,
    Arch148RuntimeService,
    _cancel_decision_fresh,
    _reviewable,
    lifecycle_journal_owner_lease,
)
from trading_bot.live_runtime.worker import (
    Arch148RuntimeWorker,
    WorkerLifecycle,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.risk import RiskLimits, RiskManager


class _Session:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.cycle_entered = threading.Event()
        self.release_cycle = threading.Event()
        self.startup_entered = threading.Event()
        self.release_startup = threading.Event()
        self.fail_stop = False
        self.interlock_allowed: list[bool] = []

    def startup_reconcile(self, stop_event, lifecycle_interlock) -> None:
        self.events.append("startup")
        self.startup_entered.set()
        self.release_startup.wait(2)

    def run_cycle(self, stop_event, lifecycle_interlock) -> object:
        self.events.append("cycle")
        with lifecycle_interlock.effect_boundary() as allowed:
            self.interlock_allowed.append(allowed)
        self.cycle_entered.set()
        self.release_cycle.wait(2)
        return object()

    def stop_reconcile(self) -> None:
        self.events.append("stop_reconcile")
        if self.fail_stop:
            raise RuntimeError("sanitized in worker")


class _KillControl:
    def __init__(self) -> None:
        self.calls = 0
        self.thread_id: int | None = None

    def request_kill(self) -> None:
        self.calls += 1
        self.thread_id = threading.get_ident()


class _LeaseJournal:
    def __init__(self, *, fail_acquire: bool = False) -> None:
        self.events: list[str] = []
        self.fail_acquire = fail_acquire

    def acquire(self) -> None:
        self.events.append("acquire")
        if self.fail_acquire:
            raise RuntimeError("stale journal lock")

    def release(self) -> None:
        self.events.append("release")


class _RuntimeStore:
    def __init__(self, state: RuntimeState) -> None:
        self.state = state

    def load(self, owner_id, source_identity):
        if (
            owner_id != self.state.owner_id
            or source_identity != self.state.source_identity
        ):
            return None
        return self.state

    def compare_and_swap(self, expected_revision, next_state):
        if self.state.revision != expected_revision:
            return False
        self.state = next_state
        return True


class _RuntimeMarketProvider:
    def read_snapshot(self, as_of):
        current_open = datetime.combine(as_of.astimezone(_NY).date(), time(9, 30), _NY)
        previous_open = current_open - timedelta(days=1)
        bars = [
            CompletedBar(
                previous_open + timedelta(minutes=5 * index),
                Decimal("100"),
                Decimal("100"),
                Decimal("100"),
                Decimal("100"),
                10,
            )
            for index in range(78)
        ]
        for index, close_text in enumerate(("101", "102", "103")):
            close = Decimal(close_text)
            bars.append(
                CompletedBar(
                    current_open + timedelta(minutes=5 * index),
                    close,
                    close,
                    close,
                    close,
                    10,
                )
            )
        prices = {
            symbol: PriceObservation(symbol, Decimal("5"), as_of)
            for symbol in (TQQQ, SQQQ)
        }
        return MarketSnapshot(as_of, tuple(bars), (), prices)


_NY = ZoneInfo("America/New_York")
_AS_OF = datetime(2026, 11, 18, 9, 45, tzinfo=_NY).astimezone(UTC)
_CANCEL_AS_OF = datetime(2026, 11, 18, 20, 55, tzinfo=UTC)
_SOURCE = SourceIdentity("a" * 40, "b" * 40)
_OWNER = UUID("cf31acbf-a42a-55e6-a034-fb93b915ac12")
_SESSION = "session_148a_worker"
_ACCOUNT = "account_148a_worker"


class _RuntimeBrokerAdapter:
    def __init__(self) -> None:
        self.read_calls = 0
        self.review_calls = 0
        self.place_calls = 0
        self.cancel_calls = 0
        self.place_entered = threading.Event()
        self.block_place = False
        self.release_place = threading.Event()
        self.release_place.set()
        self.reservation = None
        self.cancel_reservation = None
        self._filled_order = None
        self.initial_positions: dict = {}
        self.initial_position_owners: dict = {}
        self.initial_orders: tuple[BrokerOrderFact, ...] = ()
        self.cancelled_provider_order_ids: set[str] = set()

    def read_snapshot(self, as_of, state):
        self.read_calls += 1
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
        positions = dict(self.initial_positions)
        position_owners = dict(self.initial_position_owners)
        orders = tuple(
            replace(
                order,
                state=(
                    OrderState.CANCELED
                    if order.provider_order_id in self.cancelled_provider_order_ids
                    else order.state
                ),
                remaining_quantity=(
                    Decimal("0")
                    if order.provider_order_id in self.cancelled_provider_order_ids
                    else order.remaining_quantity
                ),
                observed_at=as_of,
            )
            for order in self.initial_orders
        )
        if self._filled_order is not None:
            intent = next(
                item
                for item in state.intents
                if item.intent_id == self._filled_order.intent_id
            )
            positions[intent.symbol] = Position(
                intent.symbol,
                intent.quantity,
                Decimal("5"),
            )
            position_owners[intent.symbol] = intent.intent_id
            orders += (self._filled_order,)
        return BrokerSnapshot(
            as_of,
            state.source_identity,
            state.session_fingerprint,
            state.revision,
            account,
            positions,
            position_owners,
            orders,
            scope,
            scope,
            tradability,
            approvals,
            None,
        )

    def review_order(self, intent, broker, *, observed_at):
        self.review_calls += 1
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

    def place_order(self, *, state, reservation, permit, broker, observed_at):
        assert validate_order_write_reservation(state, reservation)
        assert permit.consume(reservation, action=OrderWriteAction.PLACE)
        self.place_calls += 1
        self.reservation = reservation
        intent = next(
            item for item in state.intents if item.intent_id == reservation.intent_id
        )
        self._filled_order = BrokerOrderFact(
            "provider-order-1",
            state.account_fingerprint,
            state.source_identity,
            intent.intent_id,
            intent.ref_id,
            intent.kind,
            intent.symbol,
            intent.side,
            OrderState.FILLED,
            intent.quantity,
            intent.quantity,
            Decimal("0"),
            intent.stop_price,
            observed_at,
            Decimal("5"),
        )
        self.place_entered.set()
        if self.block_place:
            self.release_place.wait(2)
        return SimpleNamespace(status="PLACED")

    def cancel_order(self, *, state, reservation, permit, broker, observed_at):
        assert validate_order_write_reservation(state, reservation)
        assert permit.consume(reservation, action=OrderWriteAction.CANCEL)
        self.cancel_calls += 1
        self.cancel_reservation = reservation
        self.cancelled_provider_order_ids.add(reservation.target_provider_order_id)
        return SimpleNamespace(status="CANCEL_REQUESTED")


class _AllowFakeEffects:
    def allows_place(self, intent, *, state, result, broker):
        return True


class _AllowFakeCancellation:
    def allows_cancel(self, candidate, *, state, result, broker):
        return True


class _AdvanceClockCancelAuthority:
    def __init__(self, clock_values: dict[str, datetime]) -> None:
        self.clock_values = clock_values

    def allows_cancel(self, candidate, *, state, result, broker):
        self.clock_values["now"] += timedelta(seconds=16)
        return True


def _held_stop_state(as_of: datetime) -> RuntimeState:
    entry = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=1,
        kind=IntentKind.ENTRY,
        symbol=TQQQ,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        stop_price=None,
        created_at=as_of,
        lifecycle=IntentLifecycle.RECONCILED,
    )
    stop = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=2,
        kind=IntentKind.PROTECTIVE_STOP,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=Decimal("1"),
        stop_price=Decimal("97"),
        created_at=as_of,
        lifecycle=IntentLifecycle.RECONCILED,
    )
    fact = BrokerOrderFact(
        "provider-stop-owned",
        _ACCOUNT,
        _SOURCE,
        stop.intent_id,
        stop.ref_id,
        IntentKind.PROTECTIVE_STOP,
        TQQQ,
        OrderSide.SELL,
        OrderState.OPEN,
        Decimal("1"),
        Decimal("0"),
        Decimal("1"),
        Decimal("97"),
        as_of,
    )
    return RuntimeState(
        _OWNER,
        _SOURCE,
        _SESSION,
        _ACCOUNT,
        1,
        3,
        (entry, stop),
        {
            TQQQ: OwnedPositionRecord(
                TQQQ,
                entry.intent_id,
                Decimal("1"),
                Decimal("100"),
                Decimal("97"),
                stop.intent_id,
            )
        },
        (),
        tracked_orders=(
            TrackedOrder(
                stop.intent_id,
                stop.ref_id,
                provider_order_id=fact.provider_order_id,
                last_fact=fact,
            ),
        ),
    )


def _arch148_runtime_service(
    *,
    effect_authority,
    display_cache,
    binding_clock=None,
    cadence=None,
    cycle_result=None,
    cancel_effect_authority=None,
    execution_profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    initial_state=None,
    tracker_store=None,
):
    state = initial_state or RuntimeState(
        _OWNER, _SOURCE, _SESSION, _ACCOUNT, 0, 1, (), {}, ()
    )
    store = _RuntimeStore(state)
    broker_adapter = _RuntimeBrokerAdapter()
    broker_adapter.initial_positions = {
        symbol: Position(symbol, record.quantity, record.average_entry_fill)
        for symbol, record in state.positions.items()
    }
    broker_adapter.initial_position_owners = {
        symbol: record.entry_intent_id for symbol, record in state.positions.items()
    }
    broker_adapter.initial_orders = tuple(
        tracked.last_fact
        for tracked in state.tracked_orders
        if tracked.last_fact is not None
    )
    application = CycleApplicationService(
        risk_manager=RiskManager(RiskLimits(max_order_notional=Decimal("10"))),
        state_store=store,
        session_authority=NYSEPublishedRegularSessionAuthority(),
    )
    if cycle_result is not None:
        application.run_cycle = lambda request: cycle_result

    @contextmanager
    def bindings_factory():
        yield Arch148RuntimeBindings(
            _OWNER,
            _SOURCE,
            _SESSION,
            application,
            store,
            OrderTracker(tracker_store or store),
            _RuntimeMarketProvider(),
            broker_adapter,
            binding_clock or (lambda: _AS_OF),
            execution_profile,
        )

    service = Arch148RuntimeService(
        bindings_factory,
        owner_lease_factory=_owner_lease_factory(),
        cadence=cadence or timedelta(milliseconds=10),
        effect_authority=effect_authority,
        cancel_effect_authority=cancel_effect_authority,
        display_cache=display_cache,
        worker_clock=lambda: _AS_OF,
    )
    return service, store, broker_adapter


def _factory(session: _Session):
    @contextmanager
    def create_session():
        session.events.append("enter")
        try:
            yield session
        finally:
            session.events.append("exit")

    return create_session


def _owner_lease_factory(lock: threading.Lock | None = None):
    @contextmanager
    def claim_owner():
        if lock is not None and not lock.acquire(blocking=False):
            yield False
            return
        try:
            yield True
        finally:
            if lock is not None:
                lock.release()

    return claim_owner


def _worker(session: _Session, **kwargs) -> Arch148RuntimeWorker:
    kwargs.setdefault("owner_lease_factory", _owner_lease_factory())
    return Arch148RuntimeWorker(
        _factory(session),
        cadence=timedelta(milliseconds=10),
        clock=lambda: datetime(2026, 11, 19, 17, 0, tzinfo=UTC),
        **kwargs,
    )


def test_startup_reconcile_precedes_cycles_and_stop_settlement() -> None:
    session = _Session()
    session.release_startup.set()
    worker = _worker(session)

    assert worker.start()
    assert session.cycle_entered.wait(1)
    assert worker.snapshot().lifecycle is WorkerLifecycle.RUNNING
    session.release_cycle.set()
    assert worker.stop()
    assert worker.wait(1)

    assert session.events == [
        "enter",
        "startup",
        "cycle",
        "stop_reconcile",
        "exit",
    ]
    assert worker.snapshot().lifecycle is WorkerLifecycle.STOPPED
    assert worker.shutdown_complete()


def test_stop_during_inflight_cycle_blocks_next_cycle_and_settles_once() -> None:
    session = _Session()
    session.release_startup.set()
    worker = _worker(session)

    assert worker.start()
    assert session.cycle_entered.wait(1)
    assert session.interlock_allowed == [True]
    assert worker.stop()
    assert worker.snapshot().stop_requested
    session.release_cycle.set()
    assert worker.wait(1)

    assert session.events.count("cycle") == 1
    assert session.events.count("stop_reconcile") == 1
    assert worker.snapshot().lifecycle is WorkerLifecycle.STOPPED


def test_stop_during_startup_runs_no_cycle() -> None:
    session = _Session()
    worker = _worker(session)

    assert worker.start()
    assert session.startup_entered.wait(1)
    assert worker.snapshot().lifecycle is WorkerLifecycle.RECONCILING
    assert worker.stop()
    session.release_startup.set()
    assert worker.wait(1)

    assert session.events == ["enter", "startup", "stop_reconcile", "exit"]
    assert worker.snapshot().cycles_completed == 0
    assert worker.snapshot().lifecycle is WorkerLifecycle.STOPPED


def test_stop_while_claiming_owner_does_not_open_runtime_session() -> None:
    entered_lease = threading.Event()
    release_lease = threading.Event()

    @contextmanager
    def blocking_lease():
        entered_lease.set()
        release_lease.wait(2)
        yield True

    session = _Session()
    worker = _worker(session, owner_lease_factory=blocking_lease)

    assert worker.start()
    assert entered_lease.wait(1)
    assert worker.stop()
    release_lease.set()
    assert worker.wait(1)

    assert session.events == []
    assert worker.snapshot().lifecycle is WorkerLifecycle.STOPPED


def test_owner_lease_prevents_a_second_worker_instance() -> None:
    owner_lock = threading.Lock()
    first_session = _Session()
    first_session.release_startup.set()
    first = _worker(
        first_session,
        owner_lease_factory=_owner_lease_factory(owner_lock),
    )
    assert first.start()
    assert first_session.cycle_entered.wait(1)

    second_session = _Session()
    second_session.release_startup.set()
    second = _worker(
        second_session,
        owner_lease_factory=_owner_lease_factory(owner_lock),
    )
    assert second.start()
    assert second.wait(1)
    assert second.snapshot().lifecycle is WorkerLifecycle.BLOCKED
    assert second_session.events == []

    assert first.stop()
    first_session.release_cycle.set()
    assert first.wait(1)


def test_lifecycle_journal_owner_lease_preserves_acquire_and_release_boundary() -> None:
    journal = _LeaseJournal()
    lease_factory = lifecycle_journal_owner_lease(journal)

    with lease_factory() as acquired:
        assert acquired is True
        assert journal.events == ["acquire"]

    assert journal.events == ["acquire", "release"]


def test_lifecycle_journal_owner_lease_does_not_repair_acquire_failure() -> None:
    journal = _LeaseJournal(fail_acquire=True)
    lease_factory = lifecycle_journal_owner_lease(journal)

    try:
        with lease_factory():
            raise AssertionError("a failed acquire cannot enter the lease")
    except RuntimeError as exc:
        assert str(exc) == "stale journal lock"
    else:
        raise AssertionError("failed acquire must propagate")

    assert journal.events == ["acquire"]


def test_lifecycle_journal_owner_lease_uses_existing_exclusive_lock(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "arch148-runtime.jsonl"
    first_lease = lifecycle_journal_owner_lease(LifecycleJournal(journal_path))
    second_lease = lifecycle_journal_owner_lease(LifecycleJournal(journal_path))
    lock_path = journal_path.with_suffix(journal_path.suffix + ".lock")

    with first_lease() as acquired:
        assert acquired is True
        assert lock_path.exists()
        try:
            with second_lease():
                raise AssertionError("a second journal owner must be excluded")
        except FileExistsError:
            pass
        else:
            raise AssertionError("the exclusive journal lock must reject a peer")
        assert lock_path.exists()

    assert not lock_path.exists()


def test_failed_stop_settlement_is_not_retried_and_blocks_worker() -> None:
    session = _Session()
    session.release_startup.set()
    session.fail_stop = True
    worker = _worker(session)

    assert worker.start()
    assert session.cycle_entered.wait(1)
    session.release_cycle.set()
    assert worker.stop()
    assert worker.wait(1)

    assert session.events.count("stop_reconcile") == 1
    assert worker.snapshot().lifecycle is WorkerLifecycle.BLOCKED
    assert worker.snapshot().error_code == "RUNTIMEERROR"


def test_kill_requires_injected_control_and_requests_it_once() -> None:
    session = _Session()
    session.release_startup.set()
    no_authority_worker = _worker(session)

    assert no_authority_worker.start()
    assert session.cycle_entered.wait(1)
    assert not no_authority_worker.kill()
    session.release_cycle.set()
    assert no_authority_worker.wait(1)
    assert no_authority_worker.snapshot().kill_requested
    assert no_authority_worker.snapshot().error_code == "KILL_CONTROL_UNAVAILABLE"

    second_session = _Session()
    second_session.release_startup.set()
    kill_control = _KillControl()
    worker = _worker(second_session, kill_control=kill_control)
    assert worker.start()
    assert second_session.cycle_entered.wait(1)
    assert worker.kill()
    second_session.release_cycle.set()
    assert worker.wait(1)
    assert kill_control.calls == 1
    assert kill_control.thread_id != threading.get_ident()


def test_interlock_binding_is_released_after_worker_exit() -> None:
    session = _Session()
    session.release_startup.set()
    interlock = L43SerializedLifecycleInterlock()
    worker = _worker(session, lifecycle_interlock=interlock)

    assert worker.start()
    assert session.cycle_entered.wait(1)
    session.release_cycle.set()
    assert worker.stop()
    assert worker.wait(1)

    with interlock.effect_boundary() as admitted:
        assert not admitted


def test_injected_service_replans_reserves_once_and_reconciles_fake_fill() -> None:
    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=_AllowFakeEffects(),
        display_cache=cache,
    )
    broker_adapter.block_place = True
    broker_adapter.release_place.clear()

    assert service.submit(Command.START).accepted
    assert broker_adapter.place_entered.wait(2)
    assert broker_adapter.review_calls == 1
    assert broker_adapter.place_calls == 1
    assert broker_adapter.reservation is not None
    assert broker_adapter.reservation.review_revision == 0
    assert broker_adapter.reservation.expected_revision == 1
    assert service.submit(Command.STOP).accepted
    assert not service.shutdown_complete()
    broker_adapter.release_place.set()
    assert service.wait(2)

    assert store.state.revision >= 3
    assert store.state.intents[0].lifecycle is IntentLifecycle.RECONCILED
    assert TQQQ in store.state.positions
    assert cache.read().actual_position == "TQQQ"
    assert cache.read().hard_stop_price == store.state.positions[TQQQ].hard_stop_price


def test_service_without_effect_gate_never_reviews_or_places() -> None:
    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=None,
        display_cache=cache,
    )

    assert service.submit(Command.START).accepted
    deadline = threading.Event()
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    while cache.read().health != "AUTHORIZATION_MISSING" and datetime.now(UTC) < end_at:
        deadline.wait(0.005)
    assert cache.read().health == "AUTHORIZATION_MISSING"
    assert service.submit(Command.STOP).accepted
    assert service.wait(2)

    assert broker_adapter.review_calls == 0
    assert broker_adapter.place_calls == 0
    assert store.state.revision == 0


def test_place_authority_does_not_authorize_policy_stop_cancellation() -> None:
    stop_intent_id = UUID("bf249ee4-e48b-5d21-9daa-74cb7776e911")
    fact = BrokerOrderFact(
        "provider-stop-1",
        _ACCOUNT,
        _SOURCE,
        stop_intent_id,
        "stop-ref-1",
        IntentKind.PROTECTIVE_STOP,
        TQQQ,
        OrderSide.SELL,
        OrderState.OPEN,
        Decimal("1"),
        Decimal("0"),
        Decimal("1"),
        Decimal("97"),
        _AS_OF,
    )
    held_price = PriceObservation(TQQQ, Decimal("100"), _AS_OF)
    candidate = ProtectiveStopCancelCandidate(
        stop_intent_id,
        "stop-ref-1",
        "provider-stop-1",
        "c" * 64,
        fact,
        held_price,
        0,
        (AdmissionBlocker.FORCED_FLAT,),
    )
    signal = SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.BEARISH,
        None,
        None,
        None,
        "READY",
    )
    status = CycleStatus(
        _AS_OF,
        MarketRegime.BEARISH,
        None,
        TargetPosition.FLAT,
        TargetPosition.TQQQ,
        IntentKind.EXIT,
        (AdmissionBlocker.FORCED_FLAT,),
        (AdmissionBlocker.FORCED_FLAT,),
        False,
        False,
        "EXIT_REQUIRED",
    )
    cycle_result = CycleResult(signal, status, None, None, candidate)
    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=_AllowFakeEffects(),
        display_cache=cache,
        cadence=timedelta(minutes=1),
        cycle_result=cycle_result,
    )

    assert service.submit(Command.START).accepted
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    poll = threading.Event()
    while (
        cache.read().health != "CANCEL_AUTHORIZATION_MISSING"
        and datetime.now(UTC) < end_at
    ):
        poll.wait(0.005)
    assert cache.read().health == "CANCEL_AUTHORIZATION_MISSING"
    assert service.submit(Command.STOP).accepted
    assert service.wait(2)

    assert broker_adapter.review_calls == 0
    assert broker_adapter.place_calls == 0
    assert broker_adapter.cancel_calls == 0
    assert store.state.revision == 0


def test_exact_policy_stop_cancel_reserves_once_and_short_circuits_cycle() -> None:
    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=None,
        cancel_effect_authority=_AllowFakeCancellation(),
        display_cache=cache,
        binding_clock=lambda: _CANCEL_AS_OF,
        cadence=timedelta(minutes=1),
        initial_state=_held_stop_state(_CANCEL_AS_OF),
    )

    assert service.submit(Command.START).accepted
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    poll = threading.Event()
    while broker_adapter.cancel_calls == 0 and datetime.now(UTC) < end_at:
        poll.wait(0.005)
    assert broker_adapter.cancel_calls == 1
    assert broker_adapter.cancel_reservation is not None
    assert broker_adapter.cancel_reservation.action is OrderWriteAction.CANCEL
    assert broker_adapter.cancel_reservation.target_provider_order_id == (
        "provider-stop-owned"
    )
    assert store.state.pending_exit is not None

    assert service.submit(Command.STOP).accepted
    assert service.wait(2)
    assert broker_adapter.cancel_calls == 1
    assert broker_adapter.place_calls == 0
    assert broker_adapter.review_calls == 0


def test_cancel_authority_delay_expires_quote_before_durable_reservation() -> None:
    clock_values = {"now": _CANCEL_AS_OF}
    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=None,
        cancel_effect_authority=_AdvanceClockCancelAuthority(clock_values),
        display_cache=cache,
        binding_clock=lambda: clock_values["now"],
        cadence=timedelta(minutes=1),
        initial_state=_held_stop_state(_CANCEL_AS_OF),
    )

    assert service.submit(Command.START).accepted
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    poll = threading.Event()
    while (
        cache.read().health != "CANCEL_CANDIDATE_STALE" and datetime.now(UTC) < end_at
    ):
        poll.wait(0.005)
    assert cache.read().health == "CANCEL_CANDIDATE_STALE"
    assert service.submit(Command.STOP).accepted
    assert service.wait(2)

    assert broker_adapter.cancel_calls == 0
    assert not store.state.write_reservations
    assert store.state.revision == 1


def test_fractional_research_profile_never_reaches_order_adapter() -> None:
    intent = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=1,
        kind=IntentKind.ENTRY,
        symbol=TQQQ,
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        stop_price=None,
        created_at=_AS_OF,
    )
    signal = SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.BULLISH,
        MarketRegime.BULLISH,
        None,
        None,
        "READY",
    )
    status = CycleStatus(
        _AS_OF,
        MarketRegime.BULLISH,
        MarketRegime.BULLISH,
        TargetPosition.TQQQ,
        TargetPosition.FLAT,
        IntentKind.ENTRY,
        (),
        (),
        False,
        False,
        "READY",
        ExecutionProfile.FRACTIONAL_RESEARCH_PAPER,
    )
    cycle_result = CycleResult(signal, status, intent, None)
    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=_AllowFakeEffects(),
        display_cache=cache,
        cadence=timedelta(minutes=1),
        cycle_result=cycle_result,
        execution_profile=ExecutionProfile.FRACTIONAL_RESEARCH_PAPER,
    )

    assert service.submit(Command.START).accepted
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    poll = threading.Event()
    while (
        cache.read().health != "EXECUTION_PROFILE_BLOCKED"
        and datetime.now(UTC) < end_at
    ):
        poll.wait(0.005)
    assert cache.read().health == "EXECUTION_PROFILE_BLOCKED"
    assert service.submit(Command.STOP).accepted
    assert service.wait(2)

    assert broker_adapter.review_calls == 0
    assert broker_adapter.place_calls == 0
    assert broker_adapter.cancel_calls == 0
    assert store.state.revision == 0


def test_cancel_decision_requires_exact_fresh_held_symbol_quote() -> None:
    state = _held_stop_state(_CANCEL_AS_OF)
    market = _RuntimeMarketProvider().read_snapshot(_CANCEL_AS_OF)
    stop_intent = state.intents[1]
    tracked = state.tracked_orders[0]
    assert tracked.last_fact is not None
    candidate = ProtectiveStopCancelCandidate(
        stop_intent.intent_id,
        stop_intent.ref_id,
        tracked.provider_order_id or "missing",
        stop_intent.terms_digest,
        tracked.last_fact,
        market.execution_prices[TQQQ],
        state.revision,
        (AdmissionBlocker.FORCED_FLAT,),
    )
    signal = SignalAnalysis(
        MarketQuality.GAP,
        None,
        None,
        None,
        None,
        "MARKET_DATA_GAP",
    )
    status = CycleStatus(
        _CANCEL_AS_OF,
        None,
        None,
        TargetPosition.FLAT,
        TargetPosition.TQQQ,
        IntentKind.EXIT,
        (AdmissionBlocker.FORCED_FLAT,),
        (AdmissionBlocker.FORCED_FLAT,),
        True,
        False,
        "EXIT_REQUIRED",
        ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    result = CycleResult(signal, status, None, None, candidate)

    assert _cancel_decision_fresh(
        candidate,
        result,
        state,
        market=market,
        planned_as_of=_CANCEL_AS_OF,
        effect_at=_CANCEL_AS_OF,
    )
    assert not _cancel_decision_fresh(
        candidate,
        result,
        state,
        market=market,
        planned_as_of=_CANCEL_AS_OF,
        effect_at=_CANCEL_AS_OF + timedelta(seconds=16),
    )


def test_service_construction_and_cached_gui_reads_are_effect_free() -> None:
    cache = Arch148RuntimeDisplayCache()
    service, _, broker_adapter = _arch148_runtime_service(
        effect_authority=None,
        display_cache=cache,
    )

    assert broker_adapter.read_calls == 0
    assert service.snapshot().lifecycle is Lifecycle.STOPPED
    assert service.display_details()
    assert broker_adapter.read_calls == 0
    assert service.shutdown_complete()


def test_runtime_bindings_reject_split_cas_stores_before_provider_reads() -> None:
    alternate_state = RuntimeState(
        _OWNER,
        _SOURCE,
        _SESSION,
        _ACCOUNT,
        0,
        1,
        (),
        {},
        (),
    )
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=None,
        display_cache=Arch148RuntimeDisplayCache(),
        tracker_store=_RuntimeStore(alternate_state),
    )

    assert service.submit(Command.START).accepted
    assert service.wait(2)

    assert service.snapshot().lifecycle is Lifecycle.BLOCKED
    assert broker_adapter.read_calls == 0
    assert store.state.revision == 0


def test_service_refuses_may_when_market_facts_expire_before_reservation() -> None:
    samples = 0

    def binding_clock():
        nonlocal samples
        samples += 1
        return _AS_OF if samples <= 3 else _AS_OF + timedelta(seconds=16)

    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=_AllowFakeEffects(),
        display_cache=cache,
        binding_clock=binding_clock,
        cadence=timedelta(minutes=1),
    )

    assert service.submit(Command.START).accepted
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    poll = threading.Event()
    while cache.read().health != "BROKER_FACTS_STALE" and datetime.now(UTC) < end_at:
        poll.wait(0.005)
    assert cache.read().health == "BROKER_FACTS_STALE"
    assert service.submit(Command.STOP).accepted
    assert service.wait(2)

    assert broker_adapter.review_calls == 1
    assert broker_adapter.place_calls == 0
    assert store.state.revision == 1
    assert not store.state.write_reservations


def test_service_stale_after_may_never_invokes_or_retries_place() -> None:
    samples = 0

    def binding_clock():
        nonlocal samples
        samples += 1
        return _AS_OF if samples <= 5 else _AS_OF + timedelta(seconds=16)

    cache = Arch148RuntimeDisplayCache()
    service, store, broker_adapter = _arch148_runtime_service(
        effect_authority=_AllowFakeEffects(),
        display_cache=cache,
        binding_clock=binding_clock,
        cadence=timedelta(minutes=1),
    )

    assert service.submit(Command.START).accepted
    end_at = datetime.now(UTC) + timedelta(seconds=2)
    poll = threading.Event()
    while cache.read().health != "BROKER_FACTS_STALE" and datetime.now(UTC) < end_at:
        poll.wait(0.005)
    assert cache.read().health == "BROKER_FACTS_STALE"
    assert service.submit(Command.STOP).accepted
    assert service.wait(2)

    assert broker_adapter.review_calls == 1
    assert broker_adapter.place_calls == 0
    assert len(store.state.write_reservations) == 1
    assert store.state.intents[0].lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
    assert service.snapshot().lifecycle is Lifecycle.BLOCKED


def test_reviewer_accepts_action_specific_stop_and_exit_candidates() -> None:
    signal = SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.BULLISH,
        None,
        None,
        None,
        "READY",
    )
    stop = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=1,
        kind=IntentKind.PROTECTIVE_STOP,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=Decimal("0.1"),
        stop_price=Decimal("97"),
        created_at=_AS_OF,
    )
    stop_status = CycleStatus(
        _AS_OF,
        MarketRegime.BULLISH,
        None,
        TargetPosition.TQQQ,
        TargetPosition.TQQQ,
        IntentKind.PROTECTIVE_STOP,
        (AdmissionBlocker.STOP_UNPROTECTED,),
        (),
        False,
        False,
        "EXIT_REQUIRED",
    )
    stop_result = CycleResult(signal, stop_status, stop, None)
    assert _reviewable(stop_result, stop)

    exit_intent = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=2,
        kind=IntentKind.EXIT,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=Decimal("0.1"),
        stop_price=None,
        created_at=_AS_OF,
    )
    exit_status = CycleStatus(
        _AS_OF,
        MarketRegime.BEARISH,
        None,
        TargetPosition.FLAT,
        TargetPosition.TQQQ,
        IntentKind.EXIT,
        (AdmissionBlocker.FORCED_FLAT,),
        (AdmissionBlocker.FORCED_FLAT,),
        False,
        False,
        "EXIT_REQUIRED",
    )
    exit_result = CycleResult(signal, exit_status, exit_intent, None)
    assert _reviewable(exit_result, exit_intent)
