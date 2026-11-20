"""Focused fake-only coverage for the Architecture 148-A runtime skeleton."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain import OrderSide, Position, Symbol
from trading_bot.live_runtime.application import (
    CycleApplicationService,
    CycleRequest,
    ReconciliationStatus,
    reconcile_order_intent,
)
from trading_bot.live_runtime.identity import create_order_intent
from trading_bot.live_runtime.models import (
    QQQ,
    SQQQ,
    TQQQ,
    AccountFacts,
    AdmissionBlocker,
    ApprovalFacts,
    ApprovalRequestStatus,
    BrokerOrderFact,
    BrokerReviewFacts,
    BrokerSnapshot,
    CompletedBar,
    ExecutionProfile,
    IntentKind,
    IntentLifecycle,
    MarketQuality,
    MarketRegime,
    MarketSnapshot,
    OrderState,
    OwnedPositionRecord,
    PriceObservation,
    ProviderApprovalFact,
    ReviewStatus,
    RuntimeState,
    ScopeFacts,
    SignalAnalysis,
    SignalPoint,
    SourceIdentity,
    TargetPosition,
    TradabilityFacts,
)
from trading_bot.live_runtime.strategy import (
    HardStopPolicy,
    SessionReason,
    analyze_market,
    confirmed_regime_exit,
    session_decision,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.risk import RiskLimits, RiskManager

_NY = ZoneInfo("America/New_York")
_OWNER = UUID("cf31acbf-a42a-55e6-a034-fb93b915ac12")
_SOURCE = SourceIdentity("a" * 40, "b" * 40)
_ACCOUNT = "account_148a_001"
_SESSION = "session_148a_001"
_AS_OF = datetime(2026, 11, 18, 9, 45, tzinfo=_NY).astimezone(UTC)
_NEXT_AS_OF = datetime(2026, 11, 18, 9, 50, tzinfo=_NY).astimezone(UTC)
_SYMBOLS = (QQQ, TQQQ, SQQQ)


def _market(
    as_of: datetime = _AS_OF,
    current_prices: tuple[str, ...] = ("101", "102", "103"),
    *,
    in_progress: tuple[CompletedBar, ...] = (),
    include_previous: bool = True,
    omit_current_count: int = 0,
) -> MarketSnapshot:
    local_as_of = as_of.astimezone(_NY)
    current_open = datetime.combine(local_as_of.date(), time(9, 30), _NY)
    previous_open = current_open - timedelta(days=1)
    bars: list[CompletedBar] = []
    if include_previous:
        bars.extend(
            CompletedBar(
                previous_open + timedelta(minutes=5 * index),
                Decimal("100"),
                Decimal("100"),
                Decimal("100"),
                Decimal("100"),
                10,
            )
            for index in range(78)
        )
    count = min(
        len(current_prices),
        max(0, int((local_as_of - current_open).total_seconds() // 300)),
    )
    for index, price_text in enumerate(current_prices[:count]):
        price = Decimal(price_text)
        bars.append(
            CompletedBar(
                current_open + timedelta(minutes=5 * index),
                price,
                price,
                price,
                price,
                10,
            )
        )
    if omit_current_count:
        for index in range(omit_current_count):
            target = current_open + timedelta(minutes=5 * index)
            bars = [bar for bar in bars if bar.timestamp != target]
    prices = {
        symbol: PriceObservation(symbol, Decimal("100"), as_of)
        for symbol in (TQQQ, SQQQ)
    }
    return MarketSnapshot(as_of, tuple(bars), in_progress, prices)


def _state(
    *,
    revision: int = 0,
    next_sequence: int = 1,
    intents=(),
    positions=None,
    receipts=(),
    source: SourceIdentity = _SOURCE,
    owner: UUID = _OWNER,
    session: str = _SESSION,
    account: str = _ACCOUNT,
) -> RuntimeState:
    return RuntimeState(
        owner,
        source,
        session,
        account,
        revision,
        next_sequence,
        tuple(intents),
        {} if positions is None else positions,
        tuple(receipts),
    )


class _MemoryStore:
    def __init__(self, state: RuntimeState) -> None:
        self.state = state
        self.cas_calls = 0
        self.load_calls = 0

    def load(self, owner_id: UUID, source_identity: SourceIdentity) -> RuntimeState:
        self.load_calls += 1
        return self.state

    def compare_and_swap(
        self, expected_revision: int, next_state: RuntimeState
    ) -> bool:
        self.cas_calls += 1
        if self.state.revision != expected_revision:
            return False
        self.state = next_state
        return True


def _broker(
    state: RuntimeState,
    as_of: datetime,
    *,
    positions=None,
    position_owners=None,
    orders=(),
    review: BrokerReviewFacts | None = None,
    approval_requests=(),
    setting_enabled: bool | None = False,
    scope_symbols: tuple[Symbol, ...] | None = None,
    state_revision: int | None = None,
) -> BrokerSnapshot:
    revision = state.revision if state_revision is None else state_revision
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
    scope = ScopeFacts(
        state.account_fingerprint,
        True,
        True,
        1,
        as_of,
        scope_symbols,
    )
    approvals = ApprovalFacts(
        state.account_fingerprint,
        state.source_identity,
        state.session_fingerprint,
        revision,
        setting_enabled,
        (),
        True,
        as_of,
        tuple(approval_requests),
    )
    tradability = {
        symbol: TradabilityFacts(
            symbol, as_of, True, False, True, True, True, True, True
        )
        for symbol in _SYMBOLS
    }
    return BrokerSnapshot(
        as_of,
        state.source_identity,
        state.session_fingerprint,
        revision,
        account,
        {} if positions is None else positions,
        {} if position_owners is None else position_owners,
        tuple(orders),
        scope,
        scope,
        tradability,
        approvals,
        review,
    )


def _review(intent, state: RuntimeState, as_of: datetime, *, approval=False):
    return BrokerReviewFacts(
        state.account_fingerprint,
        state.source_identity,
        state.session_fingerprint,
        state.revision,
        intent.ref_id,
        intent.terms_digest,
        ReviewStatus.ACCEPTED,
        (),
        approval,
        as_of,
    )


def _service(store: _MemoryStore) -> CycleApplicationService:
    return CycleApplicationService(
        risk_manager=RiskManager(RiskLimits(max_order_notional=Decimal("10"))),
        state_store=store,
    )


def _run(
    service: CycleApplicationService,
    state: RuntimeState,
    broker: BrokerSnapshot,
    market: MarketSnapshot,
    *,
    expected_revision: int | None = None,
    owner: UUID = _OWNER,
    source: SourceIdentity = _SOURCE,
):
    return service.run_cycle(
        CycleRequest(
            market.as_of,
            owner,
            source,
            state.session_fingerprint,
            state.revision if expected_revision is None else expected_revision,
            market,
            broker,
        )
    )


def _entry_intent(
    state: RuntimeState,
    as_of: datetime,
    *,
    symbol: Symbol = TQQQ,
    quantity: Decimal = Decimal("0.1"),
    lifecycle: IntentLifecycle = IntentLifecycle.PROPOSED,
    sequence: int | None = None,
):
    return create_order_intent(
        owner_id=state.owner_id,
        source_identity=state.source_identity,
        logical_sequence=state.next_sequence if sequence is None else sequence,
        kind=IntentKind.ENTRY,
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        stop_price=None,
        created_at=as_of,
        lifecycle=lifecycle,
    )


def _stop_intent(
    state: RuntimeState,
    as_of: datetime,
    *,
    lifecycle: IntentLifecycle = IntentLifecycle.PROPOSED,
    sequence: int | None = None,
    quantity: Decimal = Decimal("0.1"),
):
    return create_order_intent(
        owner_id=state.owner_id,
        source_identity=state.source_identity,
        logical_sequence=state.next_sequence if sequence is None else sequence,
        kind=IntentKind.PROTECTIVE_STOP,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=quantity,
        stop_price=Decimal("97"),
        created_at=as_of,
        lifecycle=lifecycle,
    )


def _order(
    intent,
    as_of: datetime,
    state: RuntimeState,
    *,
    status: OrderState,
    filled: Decimal = Decimal("0"),
    remaining: Decimal | None = None,
    average_fill: Decimal | None = None,
    attach_metadata: bool = False,
):
    return BrokerOrderFact(
        f"provider-{intent.logical_sequence}",
        state.account_fingerprint,
        state.source_identity if attach_metadata else None,
        intent.intent_id if attach_metadata else None,
        intent.ref_id,
        intent.kind,
        intent.symbol,
        intent.side,
        status,
        intent.quantity,
        filled,
        intent.quantity - filled if remaining is None else remaining,
        intent.stop_price,
        as_of,
        average_fill,
    )


def _owned_state(as_of: datetime, *, with_stop: bool = False):
    entry = _entry_intent(
        _state(), as_of, lifecycle=IntentLifecycle.RECONCILED, sequence=1
    )
    intents = [entry]
    stop_id = None
    revision = 1
    next_sequence = 2
    if with_stop:
        stop = _stop_intent(
            _state(), as_of, lifecycle=IntentLifecycle.RECONCILED, sequence=2
        )
        intents.append(stop)
        stop_id = stop.intent_id
        revision = 2
        next_sequence = 3
    record = OwnedPositionRecord(
        TQQQ,
        entry.intent_id,
        Decimal("0.1"),
        Decimal("100"),
        Decimal("97"),
        stop_id,
    )
    return (
        _state(
            revision=revision,
            next_sequence=next_sequence,
            intents=tuple(intents),
            positions={TQQQ: record},
        ),
        entry,
        (intents[1] if with_stop else None),
    )


def test_completed_bar_regimes_warmup_vwap_and_confirmation() -> None:
    bullish = analyze_market(_market())
    assert bullish.quality is MarketQuality.READY
    assert bullish.current_candidate is MarketRegime.BULLISH
    assert bullish.entry_confirmation is MarketRegime.BULLISH
    assert bullish.latest is not None
    assert bullish.latest.session_vwap == Decimal("102")
    assert bullish.latest.ema20 == Decimal(
        "100.536011229888780909189072454378576827556419393"
    )
    assert bullish.latest.ema50 == Decimal(
        "100.229202946076546727879925518842677401602701827"
    )
    assert bullish.latest.rsi14 == Decimal("100")

    market = _market()
    bars = list(market.completed_bars)
    current_indices = [
        index
        for index, bar in enumerate(bars)
        if bar.timestamp.astimezone(_NY).date() == date(2026, 11, 18)
    ]
    typical_bars = (
        ("101", "102", "100", "101"),
        ("102", "104", "100", "102"),
        ("103", "104", "100", "103"),
    )
    for index, (open_, high, low, close) in zip(
        current_indices, typical_bars, strict=True
    ):
        bars[index] = replace(
            bars[index],
            open=Decimal(open_),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
        )
    typical = analyze_market(replace(market, completed_bars=tuple(bars)))
    assert typical.latest is not None
    assert typical.latest.session_vwap == Decimal(
        "101.777777777777777777777777777777777777777777778"
    )

    bearish = analyze_market(_market(current_prices=("99", "98", "97")))
    assert bearish.quality is MarketQuality.READY
    assert bearish.current_candidate is MarketRegime.BEARISH
    assert bearish.entry_confirmation is MarketRegime.BEARISH

    neutral = analyze_market(_market(current_prices=("100", "100", "100")))
    assert neutral.quality is MarketQuality.READY
    assert neutral.current_candidate is MarketRegime.NEUTRAL
    assert neutral.entry_confirmation is None
    assert neutral.latest is not None and neutral.latest.rsi14 == Decimal("50")

    warmup = analyze_market(_market(include_previous=False))
    assert warmup.quality is MarketQuality.INSUFFICIENT_WARMUP


def test_shared_regime_exit_requires_two_completed_non_supporting_bars() -> None:
    previous = SignalPoint(
        _AS_OF - timedelta(minutes=5),
        Decimal("99"),
        Decimal("100"),
        Decimal("101"),
        Decimal("102"),
        Decimal("40"),
        MarketRegime.BEARISH,
    )
    latest = SignalPoint(
        _AS_OF,
        Decimal("98"),
        Decimal("100"),
        Decimal("100"),
        Decimal("101"),
        Decimal("42"),
        MarketRegime.BEARISH,
    )
    one_completed = SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.BEARISH,
        None,
        latest,
        None,
        "ONE_COMPLETED_BAR",
    )
    two_completed = SignalAnalysis(
        MarketQuality.READY,
        MarketRegime.BEARISH,
        MarketRegime.BEARISH,
        latest,
        previous,
        "TWO_COMPLETED_BARS",
    )
    assert not confirmed_regime_exit(one_completed, TargetPosition.TQQQ)
    assert confirmed_regime_exit(two_completed, TargetPosition.TQQQ)
    assert not confirmed_regime_exit(two_completed, TargetPosition.SQQQ)


def test_in_progress_bars_are_ignored_and_missing_completed_slot_blocks() -> None:
    base = _market()
    in_progress = CompletedBar(
        datetime(2026, 11, 18, 9, 45, tzinfo=_NY),
        Decimal("500"),
        Decimal("500"),
        Decimal("500"),
        Decimal("500"),
        100,
    )
    with_unfinished = replace(base, in_progress_bars=(in_progress,))
    assert analyze_market(with_unfinished) == analyze_market(base)

    one_bar_at_boundary = _market(
        datetime(2026, 11, 18, 9, 40, tzinfo=_NY).astimezone(UTC),
        current_prices=("101",),
    )
    gap = analyze_market(one_bar_at_boundary)
    assert gap.quality is MarketQuality.GAP
    assert gap.reason == "MISSING_LATEST_COMPLETED_BAR"

    no_current_bars = _market(
        datetime(2026, 11, 18, 9, 35, tzinfo=_NY).astimezone(UTC),
        current_prices=(),
    )
    assert analyze_market(no_current_bars).quality is MarketQuality.GAP


def test_sparse_history_and_current_vwap_open_are_handled_separately() -> None:
    market = _market()
    prior = [
        bar
        for bar in market.completed_bars
        if bar.timestamp.date() == date(2026, 11, 17)
    ]
    current = [
        bar
        for bar in market.completed_bars
        if bar.timestamp.date() == date(2026, 11, 18)
    ]
    assert prior and current
    missing_tail = replace(
        market,
        completed_bars=tuple(prior[:-1] + current),
    )
    recovered = analyze_market(missing_tail)
    assert recovered.quality is MarketQuality.READY
    assert recovered.latest is not None

    missing_open = replace(
        market,
        completed_bars=tuple(prior + current[1:]),
    )
    result = analyze_market(missing_open)
    assert result.quality is MarketQuality.GAP
    assert result.reason == "SESSION_VWAP_START_MISSING"


def test_indicator_and_stop_math_ignore_ambient_decimal_context() -> None:
    expected = analyze_market(_market())
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        observed = analyze_market(_market())
        threshold = HardStopPolicy().threshold(Decimal("123456789123456789.123456789"))
    assert observed == expected
    assert threshold == Decimal("119753085449753085.44975308533")
    policy = HardStopPolicy()
    assert policy.threshold(Decimal("100")) == Decimal("97.00")
    assert policy.threshold(Decimal("100"), Decimal("96")) == Decimal("97.00")
    assert policy.threshold(Decimal("100"), Decimal("98")) == Decimal("98")
    assert policy.is_breached(Decimal("97"), Decimal("97"))


def test_session_boundaries_and_published_early_close() -> None:
    authority = NYSEPublishedRegularSessionAuthority()
    session_date = date(2026, 11, 18)
    schedule = authority.schedule_for(session_date)
    assert schedule is not None
    assert (
        session_decision(schedule.opens_at - timedelta(minutes=1)).reason
        is SessionReason.BEFORE_SESSION
    )
    assert session_decision(schedule.opens_at).reason is SessionReason.OPENING_EXCLUSION
    assert session_decision(schedule.opens_at + timedelta(minutes=15)).can_enter
    assert (
        session_decision(schedule.closes_at - timedelta(minutes=30)).reason
        is SessionReason.CLOSING_EXCLUSION
    )
    forced = session_decision(schedule.closes_at - timedelta(minutes=5))
    assert forced.force_flat and forced.reason is SessionReason.FORCED_FLAT
    after = session_decision(schedule.closes_at)
    assert after.force_flat and after.reason is SessionReason.AFTER_SESSION

    early = authority.schedule_for(date(2026, 11, 27))
    assert early is not None
    assert (early.closes_at - early.opens_at) == timedelta(hours=3, minutes=30)
    assert session_decision(early.closes_at - timedelta(minutes=5)).force_flat


def test_stable_intent_identity_binds_sequence_owner_source_and_economics() -> None:
    state = _state()
    first = _entry_intent(state, _AS_OF)
    same = _entry_intent(state, _AS_OF)
    assert first.intent_id == same.intent_id
    assert first.ref_id == same.ref_id
    assert first.terms_digest == same.terms_digest
    assert first.ref_id != _entry_intent(state, _AS_OF, sequence=2).ref_id
    assert (
        first.ref_id
        != _entry_intent(
            _state(owner=UUID("3e51a902-9648-5ee2-b218-c81aa7c7584b")), _AS_OF
        ).ref_id
    )
    assert (
        first.ref_id
        != _entry_intent(
            _state(source=SourceIdentity("c" * 40, "d" * 40)), _AS_OF
        ).ref_id
    )
    assert first.ref_id != _entry_intent(state, _AS_OF, quantity=Decimal("0.2")).ref_id


def test_entry_is_review_bound_risk_sized_and_effect_free() -> None:
    state = _state()
    intent = _entry_intent(state, _AS_OF)
    broker = _broker(state, _AS_OF, review=_review(intent, state, _AS_OF))
    store = _MemoryStore(state)
    result = _run(_service(store), state, broker, _market())

    assert result.status.action is IntentKind.ENTRY
    assert result.intent is not None and result.intent.ref_id == intent.ref_id
    assert result.effect_proposal is not None
    assert result.effect_proposal.execution_attempted is False
    assert result.effect_proposal.intent.quantity * Decimal("100") <= Decimal("10")
    assert store.state.revision == 1
    assert store.cas_calls == 1
    assert not hasattr(_service(store), "executor")


def test_entry_blocks_on_review_tradability_and_power_facts() -> None:
    state = _state()
    intent = _entry_intent(state, _AS_OF)
    review_only_approval = _broker(
        state,
        _AS_OF,
        review=_review(intent, state, _AS_OF, approval=True),
    )
    store = _MemoryStore(state)
    result = _run(_service(store), state, review_only_approval, _market())
    assert result.effect_proposal is None
    assert AdmissionBlocker.APPROVAL_REQUIRED in result.status.blockers
    assert not store.state.approval_receipts

    missing_review = _broker(state, _AS_OF)
    result = _run(_service(_MemoryStore(state)), state, missing_review, _market())
    assert AdmissionBlocker.BROKER_REVIEW_MISSING in result.status.blockers

    limited = _broker(state, _AS_OF, review=_review(intent, state, _AS_OF))
    limited = replace(limited, tradability={})
    result = _run(_service(_MemoryStore(state)), state, limited, _market())
    assert AdmissionBlocker.TRADABILITY_UNKNOWN in result.status.blockers
    assert result.effect_proposal is None

    no_power = replace(
        _broker(state, _AS_OF, review=_review(intent, state, _AS_OF)),
        account=replace(
            _broker(state, _AS_OF).account,
            cash=Decimal("0"),
            buying_power=Decimal("0"),
            unleveraged_buying_power=Decimal("0"),
        ),
    )
    result = _run(_service(_MemoryStore(state)), state, no_power, _market())
    assert AdmissionBlocker.BUYING_POWER_UNSAFE in result.status.blockers
    assert result.effect_proposal is None

    blocked_tradability = dict(_broker(state, _AS_OF).tradability)
    blocked_tradability[TQQQ] = replace(blocked_tradability[TQQQ], active=False)
    untradable = replace(
        _broker(state, _AS_OF, review=_review(intent, state, _AS_OF)),
        tradability=blocked_tradability,
    )
    result = _run(_service(_MemoryStore(state)), state, untradable, _market())
    assert AdmissionBlocker.NOT_TRADABLE in result.status.blockers
    assert result.effect_proposal is None

    stop_incompatible_facts = dict(_broker(state, _AS_OF).tradability)
    stop_incompatible_facts[TQQQ] = replace(
        stop_incompatible_facts[TQQQ], fractional_stop_supported=False
    )
    stop_incompatible = replace(
        _broker(state, _AS_OF, review=_review(intent, state, _AS_OF)),
        tradability=stop_incompatible_facts,
    )
    result = _run(_service(_MemoryStore(state)), state, stop_incompatible, _market())
    assert AdmissionBlocker.STOP_INCOMPATIBLE in result.status.blockers
    assert result.effect_proposal is None


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("rejected", AdmissionBlocker.BROKER_REVIEW_REJECTED),
        ("warning", AdmissionBlocker.BROKER_REVIEW_WARNING),
        ("ref", AdmissionBlocker.BROKER_REVIEW_MISMATCH),
        ("digest", AdmissionBlocker.BROKER_REVIEW_MISMATCH),
        ("state", AdmissionBlocker.BROKER_REVIEW_MISMATCH),
        ("stale", AdmissionBlocker.BROKER_REVIEW_STALE),
    ],
)
def test_review_rejection_warning_staleness_and_mismatch_block(
    change: str, expected: AdmissionBlocker
) -> None:
    state = _state()
    intent = _entry_intent(state, _AS_OF)
    review = _review(intent, state, _AS_OF)
    if change == "rejected":
        review = replace(review, status=ReviewStatus.REJECTED)
    elif change == "warning":
        review = replace(review, warnings=("broker warning",))
    elif change == "ref":
        review = replace(review, ref_id="different-ref")
    elif change == "digest":
        review = replace(review, terms_digest="0" * 64)
    elif change == "state":
        review = replace(review, state_revision=1)
    elif change == "stale":
        review = replace(review, observed_at=_AS_OF - timedelta(seconds=31))
    broker = _broker(state, _AS_OF, review=review)
    result = _run(_service(_MemoryStore(state)), state, broker, _market())
    assert expected in result.status.blockers
    assert result.effect_proposal is None


def test_provider_approval_receipt_requires_exact_read_fact() -> None:
    proposed = _state()
    intent = _entry_intent(
        proposed, _AS_OF, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED
    )
    state = _state(intents=(intent,), next_sequence=2)
    approval = ProviderApprovalFact(
        "approval-123",
        state.account_fingerprint,
        state.source_identity,
        state.session_fingerprint,
        state.revision,
        intent.intent_id,
        intent.ref_id,
        intent.symbol,
        intent.side,
        intent.quantity,
        ApprovalRequestStatus.PENDING,
        _AS_OF,
    )
    broker = _broker(state, _AS_OF, approval_requests=(approval,))
    store = _MemoryStore(state)
    result = _run(_service(store), state, broker, _market())
    assert result.effect_proposal is None
    assert store.state.revision == 1
    assert store.state.intents[0].lifecycle is IntentLifecycle.APPROVAL_REQUIRED
    assert store.state.approval_receipts[0].approval_id == "approval-123"
    assert AdmissionBlocker.APPROVAL_PENDING in result.status.blockers


def test_state_revision_binding_failure_never_calls_cas() -> None:
    intent = _entry_intent(
        _state(), _AS_OF, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED
    )
    state = _state(intents=(intent,), next_sequence=2)
    order = _order(
        intent,
        _AS_OF,
        state,
        status=OrderState.FILLED,
        filled=Decimal("0.1"),
        remaining=Decimal("0"),
        average_fill=Decimal("100"),
    )
    broker = _broker(state, _AS_OF, orders=(order,), state_revision=1)
    store = _MemoryStore(state)
    result = _run(
        _service(store),
        state,
        broker,
        _market(),
        expected_revision=1,
    )
    assert AdmissionBlocker.STATE_CONFLICT in result.status.blockers
    assert store.cas_calls == 0
    assert store.state.revision == 0


def test_scoped_entry_reconciliation_requires_unique_exact_terminal_facts() -> None:
    pending = _entry_intent(
        _state(), _AS_OF, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED
    )
    state = _state(intents=(pending,), next_sequence=2)
    exact = _order(
        pending,
        _AS_OF,
        state,
        status=OrderState.FILLED,
        filled=Decimal("0.1"),
        remaining=Decimal("0"),
        average_fill=Decimal("100"),
    )
    position = Position(TQQQ, Decimal("0.1"), Decimal("100"))
    broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: position},
        position_owners={TQQQ: pending.intent_id},
        orders=(exact,),
    )
    result = reconcile_order_intent(
        pending,
        state,
        broker,
        expected_session_fingerprint=state.session_fingerprint,
        as_of=_AS_OF,
    )
    assert result.status is ReconciliationStatus.RECONCILED_ENTRY
    assert result.next_state is not None
    assert result.next_state.positions[TQQQ].hard_stop_price == Decimal("97.00")

    no_match = replace(broker, orders=())
    assert (
        reconcile_order_intent(
            pending,
            state,
            no_match,
            expected_session_fingerprint=state.session_fingerprint,
            as_of=_AS_OF,
        ).status
        is ReconciliationStatus.NO_MATCH_BLOCKED
    )
    duplicate = replace(broker, orders=(exact, exact))
    assert (
        reconcile_order_intent(
            pending,
            state,
            duplicate,
            expected_session_fingerprint=state.session_fingerprint,
            as_of=_AS_OF,
        ).status
        is ReconciliationStatus.DUPLICATE_MATCHES_BLOCKED
    )
    partial = replace(
        exact,
        state=OrderState.PARTIALLY_FILLED,
        filled_quantity=Decimal("0.05"),
        remaining_quantity=Decimal("0.05"),
    )
    assert (
        reconcile_order_intent(
            pending,
            state,
            replace(broker, orders=(partial,)),
            expected_session_fingerprint=state.session_fingerprint,
            as_of=_AS_OF,
        ).status
        is ReconciliationStatus.PARTIAL_FILL_BLOCKED
    )


def test_conflicting_etf_holdings_are_unknown_not_flat() -> None:
    state, entry, _ = _owned_state(_AS_OF)
    positions = {
        TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100")),
        SQQQ: Position(SQQQ, Decimal("0.1"), Decimal("100")),
    }
    broker = _broker(
        state,
        _AS_OF,
        positions=positions,
        position_owners={TQQQ: entry.intent_id, SQQQ: None},
    )
    result = _run(_service(_MemoryStore(state)), state, broker, _market())
    assert result.status.actual_position is None
    assert result.status.desired_position is TargetPosition.FLAT
    assert AdmissionBlocker.POSITION_CONFLICT in result.status.blockers


def test_first_entry_then_stop_recovery_and_filled_stop_flatten() -> None:
    state = _state()
    entry = _entry_intent(state, _AS_OF)
    entry_broker = _broker(state, _AS_OF, review=_review(entry, state, _AS_OF))
    store = _MemoryStore(state)
    service = _service(store)
    entry_result = _run(service, state, entry_broker, _market())
    assert entry_result.effect_proposal is not None
    persisted_entry = store.state.intents[0]

    ambiguous_entry = replace(
        persisted_entry, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED
    )
    store.state = replace(store.state, intents=(ambiguous_entry,))
    filled_entry = _order(
        ambiguous_entry,
        _AS_OF,
        store.state,
        status=OrderState.FILLED,
        filled=Decimal("0.1"),
        remaining=Decimal("0"),
        average_fill=Decimal("100"),
        attach_metadata=False,
    )
    owned_broker = _broker(
        store.state,
        _AS_OF,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: ambiguous_entry.intent_id},
        orders=(filled_entry,),
    )
    reconciled_entry = _run(service, store.state, owned_broker, _market())
    assert store.state.positions[TQQQ].hard_stop_price == Decimal("97.00")
    assert (
        AdmissionBlocker.STATE_ADVANCED_THIS_CYCLE in reconciled_entry.status.blockers
    )

    state = store.state
    stop = _stop_intent(state, _AS_OF, sequence=state.next_sequence)
    no_stop = _broker(
        state,
        _AS_OF,
        positions=owned_broker.positions,
        position_owners=owned_broker.position_owners,
        review=_review(stop, state, _AS_OF),
    )
    stop_result = _run(service, state, no_stop, _market())
    assert stop_result.effect_proposal is not None
    assert stop_result.effect_proposal.intent.kind is IntentKind.PROTECTIVE_STOP
    assert stop_result.effect_proposal.intent.stop_price == Decimal("97.00")

    state = store.state
    proposed_stop = store.state.intents[-1]
    attempted_stop = replace(proposed_stop, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED)
    attempted_state = replace(
        state,
        revision=state.revision + 1,
        intents=state.intents[:-1] + (attempted_stop,),
    )
    assert store.compare_and_swap(state.revision, attempted_state)
    state = store.state
    proposed_stop = attempted_stop
    open_stop = _order(
        proposed_stop,
        _AS_OF,
        state,
        status=OrderState.OPEN,
        remaining=Decimal("0.1"),
        attach_metadata=False,
    )
    open_broker = _broker(
        state,
        _AS_OF,
        positions=owned_broker.positions,
        position_owners=owned_broker.position_owners,
        orders=(open_stop,),
    )
    recovered = _run(service, state, open_broker, _market())
    assert store.state.positions[TQQQ].stop_intent_id == proposed_stop.intent_id
    assert store.state.intents[-1].lifecycle is IntentLifecycle.RECONCILED
    assert AdmissionBlocker.STATE_ADVANCED_THIS_CYCLE in recovered.status.blockers
    assert not recovered.status.live_ready

    state = store.state
    ready_broker = _broker(
        state,
        _AS_OF,
        positions=owned_broker.positions,
        position_owners=owned_broker.position_owners,
        orders=(open_stop,),
    )
    ready = _run(service, state, ready_broker, _market())
    assert ready.status.protective_stop_ready
    assert not ready.status.live_ready
    assert ready.status.execution_profile is ExecutionProfile.FRACTIONAL_RESEARCH_PAPER
    assert ready.effect_proposal is None

    state = store.state
    filled_stop = replace(
        open_stop,
        state=OrderState.FILLED,
        filled_quantity=Decimal("0.1"),
        remaining_quantity=Decimal("0"),
    )
    flat_broker = _broker(state, _AS_OF, orders=(filled_stop,))
    reverse = _run(
        service,
        state,
        flat_broker,
        _market(current_prices=("99", "98", "97")),
    )
    assert not store.state.positions
    assert reverse.status.actual_position is TargetPosition.FLAT
    assert AdmissionBlocker.SAME_CYCLE_FLIP_BLOCKED in reverse.status.blockers
    assert reverse.effect_proposal is None

    state = store.state
    later_entry = _entry_intent(
        state, _NEXT_AS_OF, symbol=SQQQ, sequence=state.next_sequence
    )
    later_broker = _broker(
        state,
        _NEXT_AS_OF,
        review=_review(later_entry, state, _NEXT_AS_OF),
    )
    later_cycle = _run(
        service,
        state,
        later_broker,
        _market(_NEXT_AS_OF, current_prices=("99", "98", "97", "96")),
    )
    assert later_cycle.effect_proposal is not None
    assert later_cycle.effect_proposal.intent.symbol == SQQQ


def test_confirmed_reversal_exits_then_reconciles_flat_before_inverse_entry() -> None:
    state, entry, _ = _owned_state(_AS_OF)
    exit_intent = create_order_intent(
        owner_id=state.owner_id,
        source_identity=state.source_identity,
        logical_sequence=state.next_sequence,
        kind=IntentKind.EXIT,
        symbol=TQQQ,
        side=OrderSide.SELL,
        quantity=Decimal("0.1"),
        stop_price=None,
        created_at=_AS_OF,
    )
    held_broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
        review=_review(exit_intent, state, _AS_OF),
    )
    store = _MemoryStore(state)
    service = _service(store)
    bearish = _market(current_prices=("99", "98", "97"))
    exit_result = _run(service, state, held_broker, bearish)
    assert exit_result.effect_proposal is not None
    assert exit_result.effect_proposal.intent.kind is IntentKind.EXIT
    assert exit_result.effect_proposal.intent.symbol == TQQQ

    state = store.state
    ambiguous_exit = replace(
        store.state.intents[-1], lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED
    )
    store.state = replace(
        store.state,
        intents=store.state.intents[:-1] + (ambiguous_exit,),
    )
    filled_exit = _order(
        ambiguous_exit,
        _AS_OF,
        store.state,
        status=OrderState.FILLED,
        filled=Decimal("0.1"),
        remaining=Decimal("0"),
    )
    flat_broker = _broker(store.state, _AS_OF, orders=(filled_exit,))
    settled = _run(service, store.state, flat_broker, bearish)
    assert not store.state.positions
    assert settled.status.actual_position is TargetPosition.FLAT
    assert AdmissionBlocker.SAME_CYCLE_FLIP_BLOCKED in settled.status.blockers
    assert settled.effect_proposal is None

    state = store.state
    inverse = _entry_intent(
        state, _NEXT_AS_OF, symbol=SQQQ, sequence=state.next_sequence
    )
    next_cycle_broker = _broker(
        state,
        _NEXT_AS_OF,
        review=_review(inverse, state, _NEXT_AS_OF),
    )
    next_cycle = _run(
        service,
        state,
        next_cycle_broker,
        _market(_NEXT_AS_OF, current_prices=("99", "98", "97", "96")),
    )
    assert next_cycle.effect_proposal is not None
    assert next_cycle.effect_proposal.intent.kind is IntentKind.ENTRY
    assert next_cycle.effect_proposal.intent.symbol == SQQQ


def test_quote_breach_reason_outranks_safety_regime_and_forced_flat() -> None:
    as_of = datetime(2026, 11, 18, 15, 55, tzinfo=_NY).astimezone(UTC)
    falling = tuple(str(100 - index) for index in range(1, 78))
    market = _market(as_of, current_prices=falling)
    prices = dict(market.execution_prices)
    prices[TQQQ] = PriceObservation(TQQQ, Decimal("96"), as_of)
    market = replace(market, execution_prices=prices)
    state, entry, _ = _owned_state(as_of)
    broker = _broker(
        state,
        as_of,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
    )
    broker = replace(broker, observed_at=as_of - timedelta(seconds=31))

    result = _run(_service(_MemoryStore(state)), state, broker, market)
    assert result.status.mandatory_exit_reasons == (
        AdmissionBlocker.STOP_BREACH,
        AdmissionBlocker.SAFETY_FAILURE,
        AdmissionBlocker.REGIME_EXIT,
        AdmissionBlocker.FORCED_FLAT,
    )
    assert result.status.action is IntentKind.EXIT
    assert result.effect_proposal is None


def test_state_digest_and_account_drift_fail_closed_without_cas() -> None:
    state = _state()
    intent = _entry_intent(state, _AS_OF, lifecycle=IntentLifecycle.MAY_HAVE_OCCURRED)
    state = _state(intents=(intent,), next_sequence=2)
    object.__setattr__(intent, "terms_digest", "tampered")
    broker = _broker(state, _AS_OF)
    store = _MemoryStore(state)
    result = _run(_service(store), state, broker, _market())
    assert AdmissionBlocker.STATE_IDENTITY_MISMATCH in result.status.blockers
    assert store.cas_calls == 0
    assert result.effect_proposal is None

    valid_state = _state()
    drifted = replace(
        _broker(valid_state, _AS_OF),
        account=replace(
            _broker(valid_state, _AS_OF).account,
            fingerprint="account_drift_001",
        ),
    )
    drift_store = _MemoryStore(valid_state)
    drift_result = _run(_service(drift_store), valid_state, drifted, _market())
    assert AdmissionBlocker.ACCOUNT_IDENTITY_MISMATCH in drift_result.status.blockers
    assert drift_store.cas_calls == 0
    assert drift_result.effect_proposal is None


@pytest.mark.parametrize(
    ("status", "filled", "remaining", "position_quantity"),
    [
        (OrderState.CANCELED, Decimal("0"), Decimal("0.1"), Decimal("0.1")),
        (OrderState.REJECTED, Decimal("0.02"), Decimal("0.08"), Decimal("0.08")),
    ],
)
def test_exact_terminal_cancel_releases_stop_before_replacement(
    status: OrderState,
    filled: Decimal,
    remaining: Decimal,
    position_quantity: Decimal,
) -> None:
    state, entry, stop = _owned_state(_AS_OF, with_stop=True)
    assert stop is not None
    terminal = _order(
        stop,
        _AS_OF,
        state,
        status=status,
        filled=filled,
        remaining=remaining,
    )
    position = Position(TQQQ, position_quantity, Decimal("100"))
    broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: position},
        position_owners={TQQQ: entry.intent_id},
        orders=(terminal,),
    )
    store = _MemoryStore(state)
    result = _run(_service(store), state, broker, _market())
    assert result.effect_proposal is None
    record = store.state.positions[TQQQ]
    assert record.quantity == position_quantity
    assert record.stop_intent_id is None
    assert AdmissionBlocker.STATE_ADVANCED_THIS_CYCLE in result.status.blockers
    next_state = store.state
    replacement = _stop_intent(
        next_state,
        _AS_OF,
        sequence=next_state.next_sequence,
        quantity=position_quantity,
    )
    replacement_broker = _broker(
        next_state,
        _AS_OF,
        positions={TQQQ: position},
        position_owners={TQQQ: entry.intent_id},
        review=_review(replacement, next_state, _AS_OF),
    )
    proposed_replacement = _run(
        _service(store), next_state, replacement_broker, _market()
    )
    assert proposed_replacement.effect_proposal is not None
    assert (
        proposed_replacement.effect_proposal.intent.kind is IntentKind.PROTECTIVE_STOP
    )
    assert proposed_replacement.effect_proposal.intent.quantity == position_quantity


def test_proposed_stop_cannot_bind_an_unexpected_open_provider_row() -> None:
    state, entry, _ = _owned_state(_AS_OF)
    proposed = _stop_intent(state, _AS_OF, sequence=state.next_sequence)
    state = replace(
        state,
        revision=state.revision + 1,
        next_sequence=state.next_sequence + 1,
        intents=state.intents + (proposed,),
    )
    open_stop = _order(
        proposed,
        _AS_OF,
        state,
        status=OrderState.OPEN,
        remaining=Decimal("0.1"),
    )
    broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
        orders=(open_stop,),
    )
    store = _MemoryStore(state)
    result = _run(_service(store), state, broker, _market())
    assert AdmissionBlocker.STOP_CONFLICT in result.status.blockers
    assert result.effect_proposal is None
    assert store.cas_calls == 0


def test_triggered_partial_stop_is_never_live_ready_or_competed_with() -> None:
    state, entry, stop = _owned_state(_AS_OF, with_stop=True)
    assert stop is not None
    partial = _order(
        stop,
        _AS_OF,
        state,
        status=OrderState.PARTIALLY_FILLED,
        filled=Decimal("0.02"),
        remaining=Decimal("0.08"),
    )
    broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: Position(TQQQ, Decimal("0.08"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
        orders=(partial,),
    )
    store = _MemoryStore(state)
    result = _run(_service(store), state, broker, _market())
    assert not result.status.live_ready
    assert not result.status.protective_stop_ready
    assert AdmissionBlocker.SAFETY_FAILURE in result.status.mandatory_exit_reasons
    assert result.status.action is IntentKind.EXIT
    assert result.effect_proposal is None
    assert store.state.positions[TQQQ].quantity == Decimal("0.08")


def test_missing_bound_stop_row_blocks_replacement_and_exit() -> None:
    state, _, _ = _owned_state(_AS_OF, with_stop=True)
    broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: state.intents[0].intent_id},
        orders=(),
    )
    bearish = _market(current_prices=("99", "98", "97"))
    result = _run(_service(_MemoryStore(state)), state, broker, bearish)
    assert result.status.action is IntentKind.EXIT
    assert AdmissionBlocker.STOP_CONFLICT in result.status.blockers
    assert result.effect_proposal is None


def test_after_close_keeps_forced_exit_reason_but_never_queues_exit() -> None:
    state, entry, _ = _owned_state(_AS_OF)
    as_of = datetime(2026, 11, 18, 16, 5, tzinfo=_NY).astimezone(UTC)
    market = _market(as_of, current_prices=("100",) * 78)
    broker = _broker(
        state,
        as_of,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
    )
    result = _run(_service(_MemoryStore(state)), state, broker, market)
    assert AdmissionBlocker.FORCED_FLAT in result.status.mandatory_exit_reasons
    assert AdmissionBlocker.AFTER_SESSION_NO_QUEUE in result.status.blockers
    assert result.status.action is IntentKind.EXIT
    assert result.effect_proposal is None


@pytest.mark.parametrize("quote_state", ("missing", "stale"))
def test_missing_or_stale_held_quote_is_safety_failure(quote_state: str) -> None:
    state, entry, _ = _owned_state(_AS_OF)
    market = _market()
    quotes = dict(market.execution_prices)
    if quote_state == "missing":
        quotes.pop(TQQQ)
    else:
        quotes[TQQQ] = PriceObservation(
            TQQQ, Decimal("100"), _AS_OF - timedelta(seconds=16)
        )
    market = replace(market, execution_prices=quotes)
    broker = _broker(
        state,
        _AS_OF,
        positions={TQQQ: Position(TQQQ, Decimal("0.1"), Decimal("100"))},
        position_owners={TQQQ: entry.intent_id},
    )
    result = _run(_service(_MemoryStore(state)), state, broker, market)
    assert AdmissionBlocker.PRICE_STALE in result.status.blockers
    assert AdmissionBlocker.SAFETY_FAILURE in result.status.mandatory_exit_reasons
    assert result.status.action is IntentKind.EXIT
    assert result.effect_proposal is None


def test_current_bounded_scope_is_exact_pair_or_account_wide() -> None:
    state = _state()
    account_wide = _broker(state, _AS_OF, scope_symbols=None)
    bounded = _broker(state, _AS_OF, scope_symbols=(TQQQ, SQQQ))
    assert account_wide.order_scope.symbols is None
    assert bounded.order_scope.symbols == (TQQQ, SQQQ)
    with pytest.raises(ValueError, match="exactly TQQQ then SQQQ"):
        ScopeFacts(_ACCOUNT, True, True, 1, _AS_OF, (TQQQ,))


def test_import_construction_and_help_have_no_provider_boundary() -> None:
    state = _state()
    store = _MemoryStore(state)
    service = _service(store)
    assert isinstance(service, CycleApplicationService)
    assert store.load_calls == 0
    assert store.cas_calls == 0

    repo_root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repo_root / "src")
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import sys; import trading_bot.live_runtime; "
                "assert 'robin_stocks' not in sys.modules; "
                "assert 'trading_bot.robinhood_mcp.session' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=environment,
    )
    assert process.returncode == 0, process.stderr

    from trading_bot.live_runtime.__main__ import main

    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
