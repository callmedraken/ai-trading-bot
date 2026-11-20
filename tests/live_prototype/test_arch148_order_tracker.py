from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Position
from trading_bot.live_runtime.application import (
    CycleApplicationService,
    ReconciliationRequest,
)
from trading_bot.live_runtime.identity import create_order_intent
from trading_bot.live_runtime.models import (
    TQQQ,
    TRADED_SYMBOLS,
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
    InProcessWritePermit,
    OrderTracker,
    OrderWriteAction,
    OrderWriteStatus,
    TrackedOrder,
    validate_order_write_reservation,
)
from trading_bot.live_runtime.state_store import (
    RuntimeStateStoreCorrupt,
    RuntimeStateStoreIdentityError,
    RuntimeStateStoreUnavailable,
    SQLiteRuntimeStateStore,
)
from trading_bot.risk import RiskLimits, RiskManager

_OWNER = UUID("c2579776-61bb-4c7b-8ea6-ae2d0ed6fa2b")
_SOURCE = SourceIdentity("a" * 40, "b" * 40)
_ACCOUNT = "account-fingerprint-1"
_SESSION = "session-fingerprint-1"
_NOW = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)


def _empty_state(*, revision: int = 0) -> RuntimeState:
    return RuntimeState(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        account_fingerprint=_ACCOUNT,
        revision=revision,
        next_sequence=1,
        intents=(),
        positions={},
        approval_receipts=(),
    )


def _intent(
    state: RuntimeState,
    *,
    kind: IntentKind = IntentKind.ENTRY,
    lifecycle: IntentLifecycle = IntentLifecycle.PROPOSED,
    sequence: int | None = None,
):
    symbol = TQQQ
    side = OrderSide.BUY
    quantity = Decimal("0.1")
    stop_price = None
    if kind is IntentKind.PROTECTIVE_STOP:
        side = OrderSide.SELL
        stop_price = Decimal("97")
    return create_order_intent(
        owner_id=state.owner_id,
        source_identity=state.source_identity,
        logical_sequence=state.next_sequence if sequence is None else sequence,
        kind=kind,
        symbol=symbol,
        side=side,
        quantity=quantity,
        stop_price=stop_price,
        created_at=_NOW,
        lifecycle=lifecycle,
    )


def _review(
    intent, state: RuntimeState, revision: int, observed_at: datetime
) -> BrokerReviewFacts:
    return BrokerReviewFacts(
        account_fingerprint=state.account_fingerprint,
        source_identity=state.source_identity,
        session_fingerprint=state.session_fingerprint,
        state_revision=revision,
        ref_id=intent.ref_id,
        terms_digest=intent.terms_digest,
        status=ReviewStatus.ACCEPTED,
        warnings=(),
        approval_required=False,
        observed_at=observed_at,
    )


def _order(
    intent,
    state: RuntimeState,
    *,
    status: OrderState = OrderState.OPEN,
    observed_at: datetime = _NOW,
    provider_order_id: str = "provider-order-1",
    include_source: bool = True,
    include_intent: bool = True,
    include_ref: bool = True,
    filled: Decimal = Decimal("0"),
) -> BrokerOrderFact:
    return BrokerOrderFact(
        provider_order_id=provider_order_id,
        account_fingerprint=state.account_fingerprint,
        source_identity=state.source_identity if include_source else None,
        intent_id=intent.intent_id if include_intent else None,
        ref_id=intent.ref_id if include_ref else None,
        kind=intent.kind,
        symbol=intent.symbol,
        side=intent.side,
        state=status,
        requested_quantity=intent.quantity,
        filled_quantity=filled,
        remaining_quantity=intent.quantity - filled,
        stop_price=intent.stop_price,
        observed_at=observed_at,
        average_fill_price=Decimal("100") if filled else None,
    )


def _broker(
    state: RuntimeState,
    *,
    as_of: datetime,
    review: BrokerReviewFacts | None = None,
    orders: tuple[BrokerOrderFact, ...] = (),
    positions=None,
    position_owners=None,
) -> BrokerSnapshot:
    scope = ScopeFacts(
        account_fingerprint=state.account_fingerprint,
        all_agents=True,
        exhausted=True,
        page_count=1,
        observed_at=as_of,
        symbols=None,
    )
    approvals = ApprovalFacts(
        account_fingerprint=state.account_fingerprint,
        source_identity=state.source_identity,
        session_fingerprint=state.session_fingerprint,
        state_revision=state.revision,
        setting_enabled=False,
        unresolved_refs=(),
        exhaustive=True,
        observed_at=as_of,
    )
    tradability = {
        symbol: TradabilityFacts(
            symbol=symbol,
            observed_at=as_of,
            active=True,
            halted=False,
            regular_session_eligible=True,
            fractional_entry_supported=True,
            stop_market_supported=True,
            fractional_stop_supported=True,
            exact_stop_price_supported=True,
        )
        for symbol in TRADED_SYMBOLS
    }
    return BrokerSnapshot(
        observed_at=as_of,
        source_identity=state.source_identity,
        session_fingerprint=state.session_fingerprint,
        state_revision=state.revision,
        account=AccountFacts(
            fingerprint=state.account_fingerprint,
            active=True,
            agentic_allowed=True,
            cash=Decimal("1000"),
            buying_power=Decimal("1000"),
            unleveraged_buying_power=Decimal("1000"),
            equity=Decimal("1000"),
            total_market_exposure=Decimal("0"),
            observed_at=as_of,
        ),
        positions={} if positions is None else positions,
        position_owners={} if position_owners is None else position_owners,
        orders=orders,
        position_scope=scope,
        order_scope=scope,
        tradability=tradability,
        approvals=approvals,
        review=review,
    )


def _open_state(path: Path, state: RuntimeState) -> SQLiteRuntimeStateStore:
    return SQLiteRuntimeStateStore.open(
        path,
        owner_id=state.owner_id,
        source_identity=state.source_identity,
        account_fingerprint=state.account_fingerprint,
        session_fingerprint=state.session_fingerprint,
    )


def test_sqlite_cas_restores_exact_place_reservation_and_issues_one_shot_permit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.sqlite"
    initial = _empty_state()
    first_store = SQLiteRuntimeStateStore.create(path, initial)
    intent = _intent(initial)
    reviewed = _review(intent, initial, 0, _NOW)
    proposed = replace(
        initial,
        revision=1,
        next_sequence=2,
        intents=(intent,),
        proposal_reviews=(reviewed,),
    )
    assert first_store.compare_and_swap(0, proposed)

    second_store = _open_state(path, proposed)
    restored = second_store.load(_OWNER, _SOURCE)
    assert restored == proposed
    fresh_broker = _broker(restored, as_of=_NOW + timedelta(seconds=1))
    reserved = OrderTracker(second_store).begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=1,
        intent_id=intent.intent_id,
        broker=fresh_broker,
        as_of=_NOW + timedelta(seconds=1),
    )

    assert reserved is not None
    assert reserved.state.revision == 2
    assert reserved.state.intents[0].lifecycle is IntentLifecycle.MAY_HAVE_OCCURRED
    assert reserved.reservation.action is OrderWriteAction.PLACE
    assert reserved.reservation.review == reviewed
    assert reserved.reservation.review_revision == 0
    assert reserved.reservation.approval_id is None
    assert reserved.reservation.target_provider_order_id is None
    assert reserved.state.tracked_orders == (
        TrackedOrder(intent.intent_id, intent.ref_id),
    )
    assert validate_order_write_reservation(reserved.state, reserved.reservation)
    with ThreadPoolExecutor(max_workers=8) as pool:
        consumed = list(
            pool.map(
                lambda _: reserved.permit.consume(
                    reserved.reservation, action=OrderWriteAction.PLACE
                ),
                range(32),
            )
        )
    assert sum(consumed) == 1
    assert not reserved.permit.consume(
        reserved.reservation, action=OrderWriteAction.CANCEL
    )
    assert not first_store.compare_and_swap(1, replace(proposed, revision=2))

    restored_again = _open_state(path, proposed).load(_OWNER, _SOURCE)
    assert restored_again == reserved.state
    assert validate_order_write_reservation(restored_again, reserved.reservation)
    assert not hasattr(restored_again, "permit")
    with pytest.raises(TypeError):
        InProcessWritePermit(reserved.reservation)
    assert (
        OrderTracker(second_store).begin_place(
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_revision=2,
            intent_id=intent.intent_id,
            broker=_broker(restored_again, as_of=_NOW + timedelta(seconds=2)),
            as_of=_NOW + timedelta(seconds=2),
        )
        is None
    )


def test_exact_late_order_fact_keeps_raw_provider_ids_and_avoids_timestamp_churn(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.sqlite"
    state = _empty_state()
    store = SQLiteRuntimeStateStore.create(path, state)
    intent = _intent(state)
    reviewed = _review(intent, state, 0, _NOW)
    proposed = replace(
        state,
        revision=1,
        next_sequence=2,
        intents=(intent,),
        proposal_reviews=(reviewed,),
    )
    assert store.compare_and_swap(0, proposed)
    reserved = OrderTracker(store).begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=1,
        intent_id=intent.intent_id,
        broker=_broker(proposed, as_of=_NOW + timedelta(seconds=1)),
        as_of=_NOW + timedelta(seconds=1),
    )
    assert reserved is not None

    raw_fact = _order(
        intent,
        reserved.state,
        include_source=False,
        include_intent=False,
        include_ref=False,
        observed_at=_NOW + timedelta(seconds=2),
    )
    tracked_state = OrderTracker(store).record_order_fact(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=2,
        fact=raw_fact,
        as_of=_NOW + timedelta(seconds=2),
        reservation=reserved.reservation,
    )
    assert tracked_state is not None
    tracked = tracked_state.tracked_orders[0]
    assert tracked.intent_id == intent.intent_id
    assert tracked.ref_id == intent.ref_id
    assert tracked.provider_order_id == "provider-order-1"
    assert tracked.last_fact is raw_fact
    assert tracked.last_fact.intent_id is None
    assert tracked.last_fact.ref_id is None
    assert tracked_state.write_reservations[0].status is OrderWriteStatus.OBSERVED

    reopened = _open_state(path, tracked_state)
    assert reopened.load(_OWNER, _SOURCE) == tracked_state
    later_snapshot = _broker(
        tracked_state,
        as_of=_NOW + timedelta(seconds=3),
        orders=(replace(raw_fact, observed_at=_NOW + timedelta(seconds=3)),),
    )
    no_churn = OrderTracker(reopened).record_broker_snapshot(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=tracked_state.revision,
        broker=later_snapshot,
        as_of=_NOW + timedelta(seconds=3),
    )
    assert no_churn == tracked_state
    partial_fact = replace(
        raw_fact,
        state=OrderState.PARTIALLY_FILLED,
        filled_quantity=Decimal("0.02"),
        remaining_quantity=Decimal("0.08"),
        average_fill_price=Decimal("100"),
        observed_at=_NOW + timedelta(seconds=4),
    )
    partial_state = OrderTracker(reopened).record_broker_snapshot(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=tracked_state.revision,
        broker=_broker(
            tracked_state,
            as_of=_NOW + timedelta(seconds=4),
            orders=(partial_fact,),
        ),
        as_of=_NOW + timedelta(seconds=4),
    )
    assert partial_state is not None
    assert partial_state.revision == tracked_state.revision + 1
    assert partial_state.tracked_orders[0].intent_id == intent.intent_id
    assert partial_state.tracked_orders[0].last_fact.intent_id is None
    assert partial_state.tracked_orders[0].last_fact.ref_id is None
    repeated_partial = replace(partial_fact, observed_at=_NOW + timedelta(seconds=5))
    assert (
        OrderTracker(reopened).record_broker_snapshot(
            owner_id=_OWNER,
            source_identity=_SOURCE,
            expected_revision=partial_state.revision,
            broker=_broker(
                partial_state,
                as_of=_NOW + timedelta(seconds=5),
                orders=(repeated_partial,),
            ),
            as_of=_NOW + timedelta(seconds=5),
        )
        == partial_state
    )


def test_unknown_and_late_terminal_settlement_never_rearms_place(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.sqlite"
    state = _empty_state()
    store = SQLiteRuntimeStateStore.create(path, state)
    intent = _intent(state)
    reviewed = _review(intent, state, 0, _NOW)
    proposed = replace(
        state,
        revision=1,
        next_sequence=2,
        intents=(intent,),
        proposal_reviews=(reviewed,),
    )
    assert store.compare_and_swap(0, proposed)
    reservation = OrderTracker(store).begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=1,
        intent_id=intent.intent_id,
        broker=_broker(proposed, as_of=_NOW),
        as_of=_NOW,
    )
    assert reservation is not None
    unknown = OrderTracker(store).mark_unknown(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=2,
        operation_id=reservation.reservation.operation_id,
    )
    assert unknown is not None
    assert unknown.intents[0].lifecycle is IntentLifecycle.UNKNOWN
    assert unknown.write_reservations[0].status is OrderWriteStatus.UNKNOWN
    assert (
        OrderTracker(store).begin_place(
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_revision=3,
            intent_id=intent.intent_id,
            broker=_broker(unknown, as_of=_NOW + timedelta(seconds=1)),
            as_of=_NOW + timedelta(seconds=1),
        )
        is None
    )

    late_fill = _order(
        intent,
        unknown,
        status=OrderState.FILLED,
        observed_at=_NOW + timedelta(seconds=2),
        filled=intent.quantity,
    )
    settled = OrderTracker(store).record_order_fact(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=3,
        fact=late_fill,
        as_of=_NOW + timedelta(seconds=2),
        reservation=unknown.write_reservations[0],
    )
    assert settled is not None
    assert settled.intents[0].lifecycle is IntentLifecycle.UNKNOWN
    assert settled.tracked_orders[0].last_fact.state is OrderState.FILLED
    assert settled.write_reservations[0].status is OrderWriteStatus.TERMINAL
    assert (
        OrderTracker(store).begin_place(
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_revision=4,
            intent_id=intent.intent_id,
            broker=_broker(settled, as_of=_NOW + timedelta(seconds=3)),
            as_of=_NOW + timedelta(seconds=3),
        )
        is None
    )


def test_cancel_reservation_is_a_distinct_single_use_operation(tmp_path: Path) -> None:
    entry = _intent(_empty_state(), lifecycle=IntentLifecycle.RECONCILED, sequence=1)
    stop = _intent(
        _empty_state(),
        kind=IntentKind.PROTECTIVE_STOP,
        lifecycle=IntentLifecycle.RECONCILED,
        sequence=2,
    )
    open_stop_fact = _order(stop, _empty_state(revision=2))
    state = replace(
        _empty_state(revision=2),
        next_sequence=3,
        intents=(entry, stop),
        positions={
            TQQQ: OwnedPositionRecord(
                TQQQ,
                entry.intent_id,
                Decimal("0.1"),
                Decimal("100"),
                Decimal("97"),
                stop.intent_id,
            )
        },
        tracked_orders=(
            TrackedOrder(
                stop.intent_id,
                stop.ref_id,
                provider_order_id=open_stop_fact.provider_order_id,
                last_fact=open_stop_fact,
            ),
        ),
    )
    path = tmp_path / "cancel.sqlite"
    store = SQLiteRuntimeStateStore.create(path, state)
    current_stop_fact = _order(
        stop,
        state,
        include_source=False,
        include_intent=False,
        include_ref=False,
        observed_at=_NOW,
    )
    snapshot = _broker(
        state,
        as_of=_NOW,
        orders=(current_stop_fact,),
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
    )
    result = OrderTracker(store).begin_cancel(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=2,
        candidate=ProtectiveStopCancelCandidate(
            intent_id=stop.intent_id,
            ref_id=stop.ref_id,
            provider_order_id=open_stop_fact.provider_order_id,
            terms_digest=stop.terms_digest,
            fact=current_stop_fact,
            held_price=PriceObservation(TQQQ, Decimal("96"), _NOW),
            expected_state_revision=2,
            exit_reasons=(AdmissionBlocker.STOP_BREACH,),
        ),
        broker=snapshot,
        as_of=_NOW,
    )
    assert result is not None
    assert result.reservation.action is OrderWriteAction.CANCEL
    assert (
        result.reservation.target_provider_order_id == open_stop_fact.provider_order_id
    )
    assert result.reservation.review is None
    assert result.state.intents[1].lifecycle is IntentLifecycle.RECONCILED
    assert result.state.pending_exit is not None
    assert result.state.pending_exit.exit_reasons == (AdmissionBlocker.STOP_BREACH,)
    assert result.state.tracked_orders[0].intent_id == stop.intent_id
    assert result.state.tracked_orders[0].last_fact.intent_id is None
    assert result.state.tracked_orders[0].last_fact.ref_id is None
    assert validate_order_write_reservation(result.state, result.reservation)
    assert result.permit.consume(result.reservation, action=OrderWriteAction.CANCEL)
    assert not result.permit.consume(result.reservation, action=OrderWriteAction.CANCEL)

    fresh_state = store.load(_OWNER, _SOURCE)
    assert (
        OrderTracker(store).begin_cancel(
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_revision=fresh_state.revision,
            candidate=ProtectiveStopCancelCandidate(
                intent_id=stop.intent_id,
                ref_id=stop.ref_id,
                provider_order_id=open_stop_fact.provider_order_id,
                terms_digest=stop.terms_digest,
                fact=open_stop_fact,
                held_price=PriceObservation(TQQQ, Decimal("96"), _NOW),
                expected_state_revision=fresh_state.revision,
                exit_reasons=(AdmissionBlocker.STOP_BREACH,),
            ),
            broker=_broker(
                fresh_state, as_of=_NOW + timedelta(seconds=1), orders=(open_stop_fact,)
            ),
            as_of=_NOW + timedelta(seconds=1),
        )
        is None
    )


def test_reconcile_only_advances_facts_without_strategy_or_proposals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _empty_state(revision=1)
    intent = _intent(state, lifecycle=IntentLifecycle.UNKNOWN, sequence=1)
    state = replace(state, next_sequence=2, intents=(intent,))
    fact = _order(intent, state)

    class Store:
        def __init__(self) -> None:
            self.state = state
            self.cas = 0

        def load(self, owner_id, source_identity):
            return self.state

        def compare_and_swap(self, expected_revision, next_state):
            self.cas += 1
            if self.state.revision != expected_revision:
                return False
            self.state = next_state
            return True

    def forbidden_analysis(*args, **kwargs):
        raise AssertionError("reconcile_only must not run market strategy")

    store = Store()
    monkeypatch.setattr(
        "trading_bot.live_runtime.application.analyze_market", forbidden_analysis
    )
    app = CycleApplicationService(
        risk_manager=RiskManager(RiskLimits(max_order_notional=Decimal("10"))),
        state_store=store,
    )
    result = app.reconcile_only(
        ReconciliationRequest(
            as_of=_NOW,
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_state_revision=1,
            broker=_broker(state, as_of=_NOW, orders=(fact,)),
        )
    )
    assert result.state is not None
    assert result.state.tracked_orders[0].last_fact == fact
    assert result.state.intents[0].lifecycle is IntentLifecycle.UNKNOWN
    assert result.state_advanced
    assert store.cas == 1
    assert not hasattr(result, "intent")
    assert not hasattr(result, "effect_proposal")


def test_fact_batch_rejects_provider_id_collision_across_intents() -> None:
    from trading_bot.live_runtime.order_tracker import (
        OrderTrackerError,
        apply_broker_order_facts,
    )

    base = _empty_state(revision=2)
    first = _intent(base, lifecycle=IntentLifecycle.RECONCILED, sequence=1)
    second = create_order_intent(
        owner_id=base.owner_id,
        source_identity=base.source_identity,
        logical_sequence=2,
        kind=IntentKind.EXIT,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=Decimal("0.1"),
        stop_price=None,
        created_at=_NOW,
        lifecycle=IntentLifecycle.RECONCILED,
    )
    state = replace(base, next_sequence=3, intents=(first, second))
    first_fact = _order(first, state, provider_order_id="provider-shared")
    second_fact = _order(second, state, provider_order_id="provider-shared")
    with pytest.raises(OrderTrackerError):
        apply_broker_order_facts(state, (first_fact, second_fact), as_of=_NOW)


def test_sqlite_store_fails_closed_on_missing_mismatched_and_corrupt_state(
    tmp_path: Path,
) -> None:
    state = _empty_state()
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(RuntimeStateStoreUnavailable):
        _open_state(missing, state)

    path = tmp_path / "runtime.sqlite"
    store = SQLiteRuntimeStateStore.create(path, state)
    with pytest.raises(RuntimeStateStoreIdentityError):
        SQLiteRuntimeStateStore.open(
            path,
            owner_id=UUID("d2579776-61bb-4c7b-8ea6-ae2d0ed6fa2b"),
            source_identity=_SOURCE,
            account_fingerprint=_ACCOUNT,
            session_fingerprint=_SESSION,
        )
    with pytest.raises(RuntimeStateStoreIdentityError):
        SQLiteRuntimeStateStore.create(path, state)
    assert store.load(_OWNER, _SOURCE) == state

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE runtime_state SET state_json = '{}' WHERE singleton = 1"
        )
    with pytest.raises(RuntimeStateStoreCorrupt):
        _open_state(path, state).load(_OWNER, _SOURCE)
