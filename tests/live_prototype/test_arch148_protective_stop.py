from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Position
from trading_bot.live_runtime import application as application_module
from trading_bot.live_runtime.application import (
    CycleApplicationService,
    CycleRequest,
    ReconciliationRequest,
    validate_protective_stop_cancel_candidate,
)
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
    CycleResult,
    ExecutionProfile,
    IntentKind,
    IntentLifecycle,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    OrderState,
    OwnedPositionRecord,
    PriceObservation,
    ReviewStatus,
    RuntimeState,
    ScopeFacts,
    SignalAnalysis,
    SourceIdentity,
    TradabilityFacts,
)
from trading_bot.live_runtime.order_tracker import (
    OrderTracker,
    OrderWriteAction,
    OrderWriteStatus,
    TrackedOrder,
)
from trading_bot.live_runtime.state_store import SQLiteRuntimeStateStore
from trading_bot.live_runtime.strategy import HardStopPolicy
from trading_bot.risk import RiskLimits, RiskManager

_OWNER = UUID("711aa670-b3e1-4e89-95f1-93f81fa428b0")
_SOURCE = SourceIdentity("a" * 40, "b" * 40)
_ACCOUNT = "arch148-stop-account"
_SESSION = "arch148-stop-session"
_AS_OF = datetime(2026, 11, 18, 14, 45, tzinfo=UTC)
_NEXT = _AS_OF + timedelta(seconds=1)


class _MemoryStore:
    def __init__(self, state: RuntimeState) -> None:
        self.state = state

    def load(self, owner_id: UUID, source_identity: SourceIdentity) -> RuntimeState:
        assert owner_id == self.state.owner_id
        assert source_identity == self.state.source_identity
        return self.state

    def compare_and_swap(
        self, expected_revision: int, next_state: RuntimeState
    ) -> bool:
        if self.state.revision != expected_revision:
            return False
        self.state = next_state
        return True


def _state_with_stop(quantity: Decimal = Decimal("1")) -> RuntimeState:
    entry = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=1,
        kind=IntentKind.ENTRY,
        symbol=TQQQ,
        side=OrderSide.BUY,
        quantity=quantity,
        stop_price=None,
        created_at=_AS_OF - timedelta(minutes=5),
        lifecycle=IntentLifecycle.RECONCILED,
    )
    threshold = HardStopPolicy().threshold(Decimal("5"))
    stop = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=2,
        kind=IntentKind.PROTECTIVE_STOP,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=quantity,
        stop_price=threshold,
        created_at=_AS_OF - timedelta(minutes=1),
        lifecycle=IntentLifecycle.RECONCILED,
    )
    fact = _order_fact(stop, _AS_OF - timedelta(seconds=1))
    return RuntimeState(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        account_fingerprint=_ACCOUNT,
        revision=2,
        next_sequence=3,
        intents=(entry, stop),
        positions={
            TQQQ: OwnedPositionRecord(
                symbol=TQQQ,
                entry_intent_id=entry.intent_id,
                quantity=quantity,
                average_entry_fill=Decimal("5"),
                hard_stop_price=threshold,
                stop_intent_id=stop.intent_id,
            )
        },
        approval_receipts=(),
        tracked_orders=(
            TrackedOrder(
                intent_id=stop.intent_id,
                ref_id=stop.ref_id,
                provider_order_id=fact.provider_order_id,
                last_fact=fact,
            ),
        ),
    )


def _flat_state() -> RuntimeState:
    return RuntimeState(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        account_fingerprint=_ACCOUNT,
        revision=0,
        next_sequence=1,
        intents=(),
        positions={},
        approval_receipts=(),
    )


def _order_fact(
    intent,
    observed_at: datetime,
    *,
    state: OrderState = OrderState.OPEN,
    filled: Decimal = Decimal("0"),
    include_ref: bool = False,
    include_intent: bool = False,
    provider_order_id: str | None = None,
) -> BrokerOrderFact:
    return BrokerOrderFact(
        provider_order_id=provider_order_id or f"provider-{intent.logical_sequence}",
        account_fingerprint=_ACCOUNT,
        source_identity=None,
        intent_id=intent.intent_id if include_intent else None,
        ref_id=intent.ref_id if include_ref else None,
        kind=intent.kind,
        symbol=intent.symbol,
        side=intent.side,
        state=state,
        requested_quantity=intent.quantity,
        filled_quantity=filled,
        remaining_quantity=intent.quantity - filled,
        stop_price=intent.stop_price,
        observed_at=observed_at,
        average_fill_price=Decimal("4.80") if filled else None,
    )


def _broker(
    state: RuntimeState,
    as_of: datetime,
    *,
    orders: tuple[BrokerOrderFact, ...] = (),
    positions: dict | None = None,
    position_owners: dict | None = None,
    review: BrokerReviewFacts | None = None,
    cash: Decimal = Decimal("10"),
    buying_power: Decimal = Decimal("10"),
    unleveraged_buying_power: Decimal = Decimal("10"),
) -> BrokerSnapshot:
    scope = ScopeFacts(
        account_fingerprint=state.account_fingerprint,
        all_agents=True,
        exhausted=True,
        page_count=1,
        observed_at=as_of,
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
        for symbol in UNIVERSE_SYMBOLS
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
            cash=cash,
            buying_power=buying_power,
            unleveraged_buying_power=unleveraged_buying_power,
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


def _owned_broker(state: RuntimeState, as_of: datetime, **kwargs) -> BrokerSnapshot:
    record = state.positions[TQQQ]
    kwargs.setdefault(
        "positions",
        {TQQQ: Position(TQQQ, record.quantity, record.average_entry_fill)},
    )
    kwargs.setdefault("position_owners", {TQQQ: record.entry_intent_id})
    if "orders" not in kwargs:
        kwargs["orders"] = (
            _order_fact(
                next(
                    item
                    for item in state.intents
                    if item.intent_id == record.stop_intent_id
                ),
                as_of,
            ),
        )
    return _broker(state, as_of, **kwargs)


def _market(
    as_of: datetime,
    price: Decimal,
    *,
    observed_at: datetime | None = None,
) -> MarketSnapshot:
    return MarketSnapshot(
        as_of=as_of,
        completed_bars=(),
        in_progress_bars=(),
        execution_prices={
            TQQQ: PriceObservation(
                TQQQ,
                price,
                as_of if observed_at is None else observed_at,
            )
        },
    )


def _signal(*, entry: MarketRegime | None = None) -> SignalAnalysis:
    return SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.BULLISH,
        entry,
        None,
        None,
        "FAKE_READY_SIGNAL",
    )


def _service(store, monkeypatch, *, entry: MarketRegime | None = None):
    monkeypatch.setattr(
        application_module,
        "analyze_market",
        lambda *_args, **_kwargs: _signal(entry=entry),
    )
    return CycleApplicationService(
        risk_manager=RiskManager(
            RiskLimits(
                max_order_notional=Decimal("10"),
                minimum_cash_reserve_percent=Decimal("0"),
            )
        ),
        state_store=store,
    )


def _cycle(
    service: CycleApplicationService,
    state: RuntimeState,
    broker: BrokerSnapshot,
    market: MarketSnapshot,
    *,
    profile: ExecutionProfile = ExecutionProfile.FRACTIONAL_RESEARCH_PAPER,
) -> CycleResult:
    return service.run_cycle(
        CycleRequest(
            as_of=market.as_of,
            owner_id=state.owner_id,
            source_identity=state.source_identity,
            session_fingerprint=state.session_fingerprint,
            expected_state_revision=state.revision,
            market=market,
            broker=broker,
            execution_profile=profile,
        )
    )


def _review(intent, state: RuntimeState, as_of: datetime) -> BrokerReviewFacts:
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
        observed_at=as_of,
    )


def test_cancel_candidate_requires_exact_stop_and_fresh_held_quote(monkeypatch) -> None:
    state = _state_with_stop()
    stop = state.intents[1]
    order = _order_fact(stop, _AS_OF)
    broker = _owned_broker(state, _AS_OF, orders=(order,))
    service = _service(_MemoryStore(state), monkeypatch)

    result = _cycle(
        service,
        state,
        broker,
        _market(_AS_OF, Decimal("4.80")),
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )

    candidate = result.cancel_candidate
    assert candidate is not None
    assert result.status.action is IntentKind.EXIT
    assert result.effect_proposal is None
    assert candidate.exit_reasons == (AdmissionBlocker.STOP_BREACH,)
    assert candidate.fact.ref_id is None and candidate.fact.intent_id is None
    assert validate_protective_stop_cancel_candidate(
        candidate, state, broker, as_of=_AS_OF
    )

    stale_quote = replace(
        candidate,
        held_price=PriceObservation(
            TQQQ, Decimal("4.80"), _AS_OF - timedelta(seconds=16)
        ),
    )
    assert not validate_protective_stop_cancel_candidate(
        stale_quote, state, broker, as_of=_AS_OF
    )
    conflicting_order = replace(order, ref_id="foreign-ref")
    conflicting_broker = _owned_broker(state, _AS_OF, orders=(conflicting_order,))
    assert not validate_protective_stop_cancel_candidate(
        candidate, state, conflicting_broker, as_of=_AS_OF
    )

    stale_market = _market(
        _AS_OF,
        Decimal("4.80"),
        observed_at=_AS_OF - timedelta(seconds=16),
    )
    stale_result = _cycle(
        service,
        state,
        broker,
        stale_market,
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    assert stale_result.cancel_candidate is None


def test_paper_not_live_ready_and_protected_requires_whole_share(
    monkeypatch,
) -> None:
    state = _state_with_stop()
    broker = _owned_broker(state, _AS_OF)
    service = _service(_MemoryStore(state), monkeypatch)
    market = _market(_AS_OF, Decimal("5.10"))

    paper = _cycle(service, state, broker, market)
    assert paper.status.protective_stop_ready
    assert not paper.status.live_ready
    assert paper.status.execution_profile is ExecutionProfile.FRACTIONAL_RESEARCH_PAPER
    with pytest.raises(ValueError, match="live_ready requires"):
        replace(paper.status, live_ready=True)

    protected = _cycle(
        service,
        state,
        broker,
        market,
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    assert protected.status.protective_stop_ready
    assert protected.status.live_ready

    fractional_state = _state_with_stop(Decimal("0.5"))
    fractional_broker = _owned_broker(fractional_state, _AS_OF)
    fractional_service = _service(_MemoryStore(fractional_state), monkeypatch)
    fractional = _cycle(
        fractional_service,
        fractional_state,
        fractional_broker,
        market,
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    assert not fractional.status.live_ready
    assert (
        AdmissionBlocker.WHOLE_SHARE_STOP_AUTHORITY_REQUIRED
        in fractional.status.blockers
    )


def test_protected_entry_uses_integral_quantity_under_cash_and_ten_dollar_caps(
    monkeypatch,
) -> None:
    state = _flat_state()
    entry = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=state.next_sequence,
        kind=IntentKind.ENTRY,
        symbol=TQQQ,
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        stop_price=None,
        created_at=_AS_OF,
    )
    broker = _broker(state, _AS_OF, review=_review(entry, state, _AS_OF))
    store = _MemoryStore(state)
    service = _service(store, monkeypatch, entry=MarketRegime.BULLISH)
    result = _cycle(
        service,
        state,
        broker,
        _market(_AS_OF, Decimal("6")),
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    assert result.effect_proposal is not None
    assert result.effect_proposal.intent.quantity == Decimal("1")
    assert result.effect_proposal.intent.quantity * Decimal("6") <= Decimal("10")

    no_share_state = _flat_state()
    no_share_store = _MemoryStore(no_share_state)
    no_share_service = _service(no_share_store, monkeypatch, entry=MarketRegime.BULLISH)
    no_share = _cycle(
        no_share_service,
        no_share_state,
        _broker(no_share_state, _AS_OF),
        _market(_AS_OF, Decimal("12")),
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    assert no_share.effect_proposal is None
    assert (
        AdmissionBlocker.WHOLE_SHARE_STOP_AUTHORITY_REQUIRED in no_share.status.blockers
    )


def test_pending_exit_survives_cancel_unknown_restart_and_exit_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _state_with_stop()
    stop = initial.intents[1]
    open_fact = _order_fact(stop, _AS_OF)
    broker = _owned_broker(initial, _AS_OF, orders=(open_fact,))
    service = _service(_MemoryStore(initial), monkeypatch)
    plan = _cycle(
        service,
        initial,
        broker,
        _market(_AS_OF, Decimal("4.80")),
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    candidate = plan.cancel_candidate
    assert candidate is not None

    path = tmp_path / "pending-exit.sqlite"
    store = SQLiteRuntimeStateStore.create(path, initial)
    service = _service(store, monkeypatch)
    reserved = OrderTracker(store).begin_cancel(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=initial.revision,
        candidate=candidate,
        broker=broker,
        as_of=_AS_OF,
    )
    assert reserved is not None
    assert reserved.state.pending_exit is not None
    assert reserved.state.pending_exit.exit_intent_id is None
    assert reserved.permit.consume(reserved.reservation, action=OrderWriteAction.CANCEL)

    restored = SQLiteRuntimeStateStore.open(
        path,
        owner_id=_OWNER,
        source_identity=_SOURCE,
        account_fingerprint=_ACCOUNT,
        session_fingerprint=_SESSION,
    )
    unknown = OrderTracker(restored).mark_unknown(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=reserved.state.revision,
        operation_id=reserved.reservation.operation_id,
    )
    assert unknown is not None
    assert unknown.pending_exit == reserved.state.pending_exit
    assert unknown.write_reservations[-1].status is OrderWriteStatus.UNKNOWN

    restored_again = SQLiteRuntimeStateStore.open(
        path,
        owner_id=_OWNER,
        source_identity=_SOURCE,
        account_fingerprint=_ACCOUNT,
        session_fingerprint=_SESSION,
    )
    assert restored_again.load(_OWNER, _SOURCE).pending_exit == unknown.pending_exit
    retry_broker = _owned_broker(
        unknown,
        _NEXT,
        orders=(_order_fact(stop, _NEXT),),
    )
    retry_candidate = replace(
        candidate,
        fact=_order_fact(stop, _NEXT),
        held_price=PriceObservation(TQQQ, Decimal("4.80"), _NEXT),
        expected_state_revision=unknown.revision,
    )
    assert (
        OrderTracker(restored_again).begin_cancel(
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_revision=unknown.revision,
            candidate=retry_candidate,
            broker=retry_broker,
            as_of=_NEXT,
        )
        is None
    )

    cancel_time = _AS_OF + timedelta(seconds=2)
    canceled_fact = _order_fact(stop, cancel_time, state=OrderState.CANCELED)
    canceled_broker = _owned_broker(
        unknown,
        cancel_time,
        orders=(canceled_fact,),
    )
    outcome = service.reconcile_only(
        ReconciliationRequest(
            as_of=cancel_time,
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_state_revision=unknown.revision,
            broker=canceled_broker,
        )
    )
    assert outcome.state is not None
    assert outcome.state.pending_exit is not None
    assert outcome.state.pending_exit.exit_intent_id is None
    assert outcome.state.positions[TQQQ].stop_intent_id is None
    assert outcome.state.tracked_orders[0].last_fact.state is OrderState.CANCELED

    proposal_time = cancel_time + timedelta(seconds=1)
    proposal_state = restored_again.load(_OWNER, _SOURCE)
    exit_intent = create_order_intent(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        logical_sequence=proposal_state.next_sequence,
        kind=IntentKind.EXIT,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=proposal_state.positions[TQQQ].quantity,
        stop_price=None,
        created_at=proposal_time,
    )
    exit_broker = _owned_broker(
        proposal_state,
        proposal_time,
        orders=(canceled_fact,),
        review=_review(exit_intent, proposal_state, proposal_time),
    )
    proposal_result = _cycle(
        service,
        proposal_state,
        exit_broker,
        _market(proposal_time, Decimal("4.80")),
        profile=ExecutionProfile.PROTECTED_WHOLE_SHARE,
    )
    assert proposal_result.effect_proposal is not None
    assert proposal_result.effect_proposal.intent.kind is IntentKind.EXIT
    proposed_state = restored_again.load(_OWNER, _SOURCE)
    assert proposed_state.pending_exit is not None
    assert proposed_state.pending_exit.exit_intent_id == exit_intent.intent_id
    assert (
        next(
            item
            for item in proposed_state.intents
            if item.intent_id == exit_intent.intent_id
        ).lifecycle
        is IntentLifecycle.PROPOSED
    )

    after_proposal_restart = SQLiteRuntimeStateStore.open(
        path,
        owner_id=_OWNER,
        source_identity=_SOURCE,
        account_fingerprint=_ACCOUNT,
        session_fingerprint=_SESSION,
    )
    restarted_state = after_proposal_restart.load(_OWNER, _SOURCE)
    assert restarted_state.pending_exit == proposed_state.pending_exit
    assert restarted_state.positions[TQQQ].stop_intent_id is None

    rejected_path = tmp_path / "pending-exit-rejected.sqlite"
    rejected_store = SQLiteRuntimeStateStore.create(rejected_path, proposed_state)
    rejected_tracker = OrderTracker(rejected_store)
    rejected_place = rejected_tracker.begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=proposed_state.revision,
        intent_id=exit_intent.intent_id,
        broker=_owned_broker(
            proposed_state,
            proposal_time + timedelta(seconds=1),
            orders=(canceled_fact,),
        ),
        as_of=proposal_time + timedelta(seconds=1),
    )
    assert rejected_place is not None
    rejected_time = proposal_time + timedelta(seconds=2)
    rejected_fact = _order_fact(
        exit_intent,
        rejected_time,
        state=OrderState.REJECTED,
        include_ref=True,
        include_intent=True,
    )
    rejected_service = _service(rejected_store, monkeypatch)
    rejected_outcome = rejected_service.reconcile_only(
        ReconciliationRequest(
            as_of=rejected_time,
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_state_revision=rejected_place.state.revision,
            broker=_owned_broker(
                rejected_place.state,
                rejected_time,
                orders=(canceled_fact, rejected_fact),
            ),
        )
    )
    assert rejected_outcome.state is not None
    assert rejected_outcome.state.positions[TQQQ].quantity == Decimal("1")
    assert rejected_outcome.state.pending_exit == proposed_state.pending_exit
    rejected_exit_track = next(
        item
        for item in rejected_outcome.state.tracked_orders
        if item.intent_id == exit_intent.intent_id
    )
    assert rejected_exit_track.last_fact == rejected_fact
    assert (
        next(
            item
            for item in rejected_outcome.state.write_reservations
            if item.intent_id == exit_intent.intent_id
        ).status
        is OrderWriteStatus.TERMINAL
    )
    rejected_restart = SQLiteRuntimeStateStore.open(
        rejected_path,
        owner_id=_OWNER,
        source_identity=_SOURCE,
        account_fingerprint=_ACCOUNT,
        session_fingerprint=_SESSION,
    )
    assert (
        rejected_restart.load(_OWNER, _SOURCE).pending_exit
        == proposed_state.pending_exit
    )

    reservation = OrderTracker(after_proposal_restart).begin_place(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        session_fingerprint=_SESSION,
        expected_revision=restarted_state.revision,
        intent_id=exit_intent.intent_id,
        broker=_owned_broker(
            restarted_state,
            proposal_time + timedelta(seconds=1),
            orders=(canceled_fact,),
        ),
        as_of=proposal_time + timedelta(seconds=1),
    )
    assert reservation is not None
    assert reservation.state.pending_exit == proposed_state.pending_exit
    unknown_exit = OrderTracker(after_proposal_restart).mark_unknown(
        owner_id=_OWNER,
        source_identity=_SOURCE,
        expected_revision=reservation.state.revision,
        operation_id=reservation.reservation.operation_id,
    )
    assert unknown_exit is not None
    assert unknown_exit.pending_exit == proposed_state.pending_exit

    fill_time = proposal_time + timedelta(seconds=3)
    filled_exit = _order_fact(
        exit_intent,
        fill_time,
        state=OrderState.FILLED,
        filled=exit_intent.quantity,
        include_ref=True,
        include_intent=True,
        provider_order_id="provider-exit-fill",
    )
    exit_facts_broker = _broker(
        unknown_exit,
        fill_time,
        orders=(canceled_fact, filled_exit),
        positions={},
        position_owners={},
    )
    settled = service.reconcile_only(
        ReconciliationRequest(
            as_of=fill_time,
            owner_id=_OWNER,
            source_identity=_SOURCE,
            session_fingerprint=_SESSION,
            expected_state_revision=unknown_exit.revision,
            broker=exit_facts_broker,
        )
    )
    assert settled.state is not None
    assert settled.settled_exit
    assert settled.state.pending_exit is None
    assert settled.state.positions == {}
