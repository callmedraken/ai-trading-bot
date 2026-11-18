from __future__ import annotations

import asyncio
import hashlib
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from tests.live_prototype.test_l43_effect_operator import (
    _CURRENT,
    _ENTRY_ORDER_ID,
    _EXIT_ORDER_ID,
    _IDENTITY,
    _ORIGIN_ANCHOR,
    _OWNED,
    _affirmative_review,
    _Authorizer,
    _FakeMcpSession,
    _input_result,
    _operator,
    _owned_state,
    _plan_for_state,
    _Reconciler,
    _state_path,
)
from tests.live_prototype.test_l43_effect_operator import (
    _pre_effect as _operator_pre_effect,
)
from tests.live_prototype.test_l43_pre_effect_observation import (
    _NOW as _observer_now,
)
from tests.live_prototype.test_l43_pre_effect_observation import (
    _dependencies as _observer_dependencies,
)
from tests.live_prototype.test_l43_pre_effect_observation import (
    _origin as _observer_origin,
)
from tests.live_prototype.test_l43_pre_effect_observation import (
    _state_path as _observer_state_path,
)

from trading_bot.live_prototype import l43_runtime
from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.contracts import RestrictedLiveStatus
from trading_bot.live_prototype.durable_state import (
    BlockReason,
    DurableState,
    DurableStateStore,
    IntentKind,
    IntentStatus,
    L43OriginAnchor,
    L43SellReviewState,
    L43SellReviewStatus,
    ManualCloseBasis,
    ManualCloseRequired,
    OrderState,
    OrderStatus,
    RuntimeIdentity,
)
from trading_bot.live_prototype.l43_effect_operator import (
    L43AuthorizationRequest,
    L43EffectOutcome,
    L43EffectResult,
    L43EffectStage,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PreEffectOutcome,
    L43PreEffectResult,
)
from trading_bot.live_prototype.l43_production_owner import L43SourceIdentity
from trading_bot.live_prototype.l43_provider_contracts import L43AccountIdentity
from trading_bot.live_prototype.l43_state import L43StateSession, L43StateSnapshot
from trading_bot.live_prototype.tiny_live_policy import ManualCloseTrigger
from trading_bot.robinhood_mcp.l43_production_composition import (
    L43ProductionPreEffectComposition,
)

_NOW = datetime(1970, 1, 1, tzinfo=UTC)
_SOURCE = L43SourceIdentity(source_head="8" * 40, source_tree="9" * 40)


class _PauseAfterGrantAuthorizer(_Authorizer):
    def __init__(self, stage: L43EffectStage) -> None:
        super().__init__()
        self._stage = stage
        self.grant_returned = threading.Event()
        self.release = threading.Event()

    def authorize(self, request: L43AuthorizationRequest):
        grant = super().authorize(request)
        if request.stage is self._stage and grant is not None:
            self.grant_returned.set()
            if not self.release.wait(timeout=4):
                raise TimeoutError("authorization barrier expired")
        return grant


def _origin() -> L43OriginAnchor:
    identity = RuntimeIdentity(
        account_fingerprint=hashlib.sha256(b"runtime-account").hexdigest(),
        source_head="1" * 40,
        source_tree="2" * 40,
        config_digest="3" * 64,
        binding_digest="4" * 64,
        lifecycle_id=str(UUID("00000000-0000-0000-0000-000000000147")),
    )
    return L43OriginAnchor(
        runtime_identity=identity,
        journal_sha256="5" * 64,
        initialization_event_sha256="6" * 64,
        consumed_observation_sha256="7" * 64,
    )


def _snapshot(
    *,
    entry: OrderState | None = None,
    exit_order: OrderState | None = None,
    sell_review: L43SellReviewState | None = None,
    manual_close: ManualCloseRequired | None = None,
    blocked_reason: BlockReason | None = None,
    reconciled: bool = True,
) -> L43StateSnapshot:
    origin = _origin()
    state = DurableState(
        identity=origin.runtime_identity,
        baseline_quantity=Decimal("0"),
        entry=entry,
        exit=exit_order,
        reconciled=reconciled,
        blocked_reason=blocked_reason,
        last_sequence=10,
        journal_hash="a" * 64,
        l43_origin=origin,
        sell_review=sell_review,
        manual_close=manual_close,
    )
    return L43StateSnapshot(
        origin=origin,
        state=state,
        last_sequence=state.last_sequence,
        journal_sha256=state.journal_hash,
        sell_review_pending=state.sell_review_pending,
        review_active=False,
        manual_close_required=state.manual_close_required or state.sell_review_pending,
        manual_follow_up_required=state.manual_follow_up_required,
    )


class _SnapshotSession:
    def __init__(self, snapshot: L43StateSnapshot) -> None:
        self._snapshot = snapshot

    def __enter__(self) -> _SnapshotSession:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def snapshot(self) -> L43StateSnapshot:
        return self._snapshot


class _FakeOperator:
    def __init__(self, *, result: L43EffectResult | None = None) -> None:
        self.result = result or _effect_result(
            L43EffectStage.ENTRY_PLACEMENT,
            L43EffectOutcome.ENTRY_PENDING,
            "ENTRY_ORDER_KNOWN_WORKING",
        )
        self.settlement_calls: list[tuple[object, ...]] = []
        self.place_entry_calls = 0
        self.review_calls = 0
        self.place_sell_calls = 0

    async def settle_pending_order(self, *, stage, intent_id, provider_order_id=None):
        self.settlement_calls.append((stage, intent_id, provider_order_id))
        return self.result

    async def place_entry(self, *_args, **_kwargs):
        self.place_entry_calls += 1
        return self.result

    async def review_sell(self, *_args, **_kwargs):
        self.review_calls += 1
        return self.result

    async def place_sell(self, *_args, **_kwargs):
        self.place_sell_calls += 1
        return self.result

    def persist_observed_manual_close(self, *_args, **_kwargs):
        return self.result


def _effect_result(
    stage: L43EffectStage,
    outcome: L43EffectOutcome,
    reason_code: str,
) -> L43EffectResult:
    return L43EffectResult(
        stage=stage,
        outcome=outcome,
        reason_code=reason_code,
        evidence_sha256="b" * 64,
        plan_binding_sha256=None,
        authorization_sha256=None,
        state_last_sequence=None,
        state_tail_sha256=None,
    )


def _pre_effect(outcome: L43PreEffectOutcome) -> L43PreEffectResult:
    evidence = b"{}"
    return L43PreEffectResult(
        outcome=outcome,
        blockers=(),
        evidence_sha256=hashlib.sha256(evidence).hexdigest(),
        evidence_json=evidence,
        plan=None,
        observed_at=_NOW,
        robinhood_read_count=0,
        robinhood_page_count=0,
        alpaca_provider_call_count=0,
        credential_read_count=0,
    )


def _runtime(
    snapshot: L43StateSnapshot,
    *,
    operator: object | None = None,
    observer=None,
    source: L43SourceIdentity = _SOURCE,
    source_reader=None,
    component_factory=None,
) -> l43_runtime.L43Runtime:
    selected_operator = _FakeOperator() if operator is None else operator
    components = l43_runtime._RuntimeComponents(
        session_factory=lambda: _SnapshotSession(snapshot),
        observer=(
            (lambda _sink: _pre_effect(L43PreEffectOutcome.NO_ACTION_SIGNAL))
            if observer is None
            else observer
        ),
        operator=selected_operator,
    )
    return l43_runtime.L43Runtime(
        expected_source=source,
        source_reader=(lambda: source) if source_reader is None else source_reader,
        components_factory=(
            (lambda _effect_boundary: components)
            if component_factory is None
            else component_factory
        ),
    )


def test_production_builder_pins_only_local_git_source_until_start(monkeypatch):
    calls: list[str] = []

    def forbidden(*_args, **_kwargs):
        calls.append("production-components")
        raise AssertionError("builder must not load production prerequisites")

    monkeypatch.setattr(
        L43ProductionPreEffectComposition,
        "for_production",
        classmethod(forbidden),
    )
    root = Path(__file__).resolve().parents[2]
    runtime = l43_runtime.build_production_l43_runtime(root)

    assert runtime.source_head
    assert runtime.source_tree
    assert len(runtime.source_head) == 40
    assert len(runtime.source_tree) == 40
    assert calls == []


def test_ambient_environment_and_caller_claims_cannot_authorize_runtime(
    monkeypatch,
):
    monkeypatch.setenv("ARCH147_L43_AUTHORIZATION_GRANTED", "true")
    monkeypatch.setenv("ARCH147_L43_AUTHORITY_SHA256", "a" * 64)
    root = Path(__file__).resolve().parents[2]
    runtime = l43_runtime.build_production_l43_runtime(root)
    request = L43AuthorizationRequest(
        stage=L43EffectStage.ENTRY_PLACEMENT,
        plan_binding_sha256="1" * 64,
        state_last_sequence=1,
        state_tail_sha256="2" * 64,
        source_head="3" * 40,
        source_tree="4" * 40,
        config_digest="5" * 64,
        binding_digest="6" * 64,
        account_fingerprint="7" * 64,
        target_session="2026-11-17",
        signal_inputs_digest="8" * 64,
    )

    with pytest.raises(TypeError):
        l43_runtime.build_production_l43_runtime(
            root,
            authorized=True,
            authority_sha256="a" * 64,
        )

    assert runtime._components is None
    assert l43_runtime._DefaultDenyAuthorizer().authorize(request) is None


def test_locked_reobserver_detaches_snapshot_and_reads_outside_event_loop(
    monkeypatch,
    tmp_path: Path,
):
    path, _ = _observer_state_path(tmp_path)
    _, origin_anchor = _observer_origin()
    dependencies, read_boundary, _, _ = _observer_dependencies(
        state_path=path,
        as_of=_observer_now,
        decision=SignalDecision.BUY,
    )
    read_threads: list[int] = []
    caller_thread = threading.get_ident()

    def assert_no_running_loop() -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise AssertionError("synchronous observer read ran on an event loop")

    for method_name in (
        "get_accounts",
        "get_equity_positions",
        "get_equity_orders",
    ):
        original_method = getattr(read_boundary, method_name)

        def checked_method(*args, _original=original_method, **kwargs):
            assert_no_running_loop()
            read_threads.append(threading.get_ident())
            return _original(*args, **kwargs)

        setattr(read_boundary, method_name, checked_method)

    original_observer = l43_runtime.observe_l43_pre_effect
    detached_snapshots: list[L43StateSnapshot] = []

    def checked_observer(detached, **kwargs):
        assert_no_running_loop()
        snapshot = detached.state_snapshot_reader()
        assert type(snapshot) is L43StateSnapshot
        assert snapshot.state.identity == origin_anchor.runtime_identity
        detached_snapshots.append(snapshot)
        return original_observer(detached, **kwargs)

    monkeypatch.setattr(l43_runtime, "observe_l43_pre_effect", checked_observer)
    reobserver = l43_runtime._locked_reobserver(dependencies)

    async def invoke_while_locked():
        with L43StateSession.open_existing(path, origin_anchor) as session:
            locked_snapshot = session.snapshot()
            result = reobserver(session)
            return result, locked_snapshot

    result, locked_snapshot = asyncio.run(invoke_while_locked())

    assert result.outcome is L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
    assert detached_snapshots == [locked_snapshot]
    assert read_threads
    assert all(thread_id != caller_thread for thread_id in read_threads)


def test_source_mismatch_blocks_before_component_or_state_access():
    component_calls = 0
    state_calls = 0

    def components(_effect_boundary):
        nonlocal component_calls
        component_calls += 1
        raise AssertionError("source mismatch must precede composition")

    def source_reader():
        return L43SourceIdentity("a" * 40, "b" * 40)

    runtime = _runtime(
        _snapshot(),
        source=_SOURCE,
        source_reader=source_reader,
        component_factory=components,
    )
    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.BLOCKED
    assert result.reason_code == "EXECUTABLE_SOURCE_CHANGED"
    assert component_calls == state_calls == 0


def test_stopped_cycle_performs_no_composition_or_state_open():
    component_calls = 0

    def components(_effect_boundary):
        nonlocal component_calls
        component_calls += 1
        raise AssertionError("stopped cycle must not compose")

    runtime = _runtime(_snapshot(), component_factory=components)
    stop = threading.Event()
    stop.set()

    result = runtime.run_cycle(stop)

    assert result.status is RestrictedLiveStatus.STOPPED
    assert component_calls == 0


def test_no_action_signal_returns_without_operator_effects():
    operator = _FakeOperator()
    runtime = _runtime(
        _snapshot(),
        operator=operator,
        observer=lambda _sink: _pre_effect(L43PreEffectOutcome.NO_ACTION_SIGNAL),
    )

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.NO_ACTION
    assert result.reason_code == "NO_ACTION_SIGNAL"
    assert operator.place_entry_calls == operator.review_calls == 0
    assert operator.place_sell_calls == 0
    assert operator.settlement_calls == []


def test_bound_pending_entry_settles_without_observation_or_new_effect():
    entry = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000101",
        requested_dollars=Decimal("10.00"),
        provider_order_id="bound-entry-order",
        status=IntentStatus.WORKING,
    )
    operator = _FakeOperator()
    observer_calls = 0

    def observer(_sink):
        nonlocal observer_calls
        observer_calls += 1
        raise AssertionError("pending settlement must precede new observation")

    runtime = _runtime(
        _snapshot(entry=entry, reconciled=False), operator=operator, observer=observer
    )
    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.ENTRY_PENDING
    assert operator.settlement_calls == [
        (L43EffectStage.ENTRY_PLACEMENT, entry.intent_id, entry.provider_order_id)
    ]
    assert operator.place_entry_calls == operator.review_calls == observer_calls == 0


def test_accepted_review_does_not_hide_bound_working_sell_settlement():
    entry = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000102",
        requested_dollars=Decimal("10.00"),
        provider_order_id="bound-entry-order",
        status=IntentStatus.FILLED,
        cumulative_quantity=Decimal("0.5"),
        cumulative_notional=Decimal("10.00"),
    )
    exit_order = OrderState(
        kind=IntentKind.EXIT,
        intent_id="00000000-0000-0000-0000-000000000103",
        requested_quantity=Decimal("0.5"),
        provider_order_id="bound-sell-order",
        status=IntentStatus.WORKING,
    )
    review = L43SellReviewState(
        status=L43SellReviewStatus.ACCEPTED,
        proposal_sha256="c" * 64,
        arguments_sha256="d" * 64,
        started_at_sequence=8,
        review_evidence_sha256="e" * 64,
    )
    operator = _FakeOperator(
        result=_effect_result(
            L43EffectStage.SELL_PLACEMENT,
            L43EffectOutcome.SELL_PENDING,
            "SELL_ORDER_KNOWN_WORKING",
        )
    )
    observer_calls = 0

    def observer(_sink):
        nonlocal observer_calls
        observer_calls += 1
        raise AssertionError("pending SELL settlement must precede another review")

    runtime = _runtime(
        _snapshot(entry=entry, exit_order=exit_order, sell_review=review),
        operator=operator,
        observer=observer,
    )
    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.SELL_PENDING
    assert operator.settlement_calls == [
        (
            L43EffectStage.SELL_PLACEMENT,
            exit_order.intent_id,
            exit_order.provider_order_id,
        )
    ]
    assert operator.review_calls == operator.place_sell_calls == observer_calls == 0


def test_partial_sell_without_sticky_manual_record_settles_first():
    entry = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000104",
        requested_dollars=Decimal("10.00"),
        provider_order_id="bound-entry-order",
        status=IntentStatus.FILLED,
        cumulative_quantity=Decimal("0.5"),
        cumulative_notional=Decimal("10.00"),
    )
    exit_order = OrderState(
        kind=IntentKind.EXIT,
        intent_id="00000000-0000-0000-0000-000000000105",
        requested_quantity=Decimal("0.5"),
        provider_order_id="bound-sell-order",
        status=IntentStatus.PARTIAL,
        cumulative_quantity=Decimal("0.1"),
        cumulative_notional=Decimal("2.00"),
    )
    snapshot = _snapshot(entry=entry, exit_order=exit_order)
    assert snapshot.state.manual_close is None
    assert snapshot.state.manual_close_required
    operator = _FakeOperator(
        result=_effect_result(
            L43EffectStage.SELL_PLACEMENT,
            L43EffectOutcome.MANUAL_CLOSE_REQUIRED,
            "SELL_SETTLEMENT_REQUIRES_MANUAL_CLOSE",
        )
    )
    runtime = _runtime(snapshot, operator=operator)

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED
    assert operator.settlement_calls


def test_stored_manual_close_prevents_settlement_of_pending_looking_sell():
    entry = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000106",
        requested_dollars=Decimal("10.00"),
        provider_order_id="bound-entry-order",
        status=IntentStatus.FILLED,
        cumulative_quantity=Decimal("0.5"),
        cumulative_notional=Decimal("10.00"),
    )
    exit_order = OrderState(
        kind=IntentKind.EXIT,
        intent_id="00000000-0000-0000-0000-000000000107",
        requested_quantity=Decimal("0.5"),
        provider_order_id="bound-sell-order",
        status=IntentStatus.WORKING,
    )
    manual = ManualCloseRequired(
        trigger=ManualCloseTrigger.SELL_PARTIAL,
        exact_residual_quantity=Decimal("0.4"),
        basis=ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL,
        effect_evidence_sha256="f" * 64,
    )
    operator = _FakeOperator()
    runtime = _runtime(
        _snapshot(entry=entry, exit_order=exit_order, manual_close=manual),
        operator=operator,
    )

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.MANUAL_CLOSE_REQUIRED
    assert operator.settlement_calls == []


def test_unknown_effect_blocks_before_pending_settlement():
    entry = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000108",
        requested_dollars=Decimal("10.00"),
        provider_order_id=None,
        status=IntentStatus.UNKNOWN,
    )
    operator = _FakeOperator()
    runtime = _runtime(_snapshot(entry=entry, reconciled=False), operator=operator)

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.EFFECT_UNKNOWN
    assert operator.settlement_calls == []


def test_reconciled_filled_sell_remains_truthful_on_later_cycle():
    entry = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000109",
        requested_dollars=Decimal("10.00"),
        provider_order_id="bound-entry-order",
        status=IntentStatus.FILLED,
        cumulative_quantity=Decimal("0.5"),
        cumulative_notional=Decimal("10.00"),
    )
    exit_order = OrderState(
        kind=IntentKind.EXIT,
        intent_id="00000000-0000-0000-0000-000000000110",
        requested_quantity=Decimal("0.5"),
        provider_order_id="bound-sell-order",
        status=IntentStatus.FILLED,
        cumulative_quantity=Decimal("0.5"),
        cumulative_notional=Decimal("12.00"),
    )
    runtime = _runtime(
        _snapshot(entry=entry, exit_order=exit_order, reconciled=True),
    )

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.SELL_RECONCILED
    assert result.reason_code == "SELL_FACTUALLY_RECONCILED"


def test_operator_default_deny_blocks_qualified_entry_without_reservation_or_place(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    operator = _operator(path, mcp, authorizer=l43_runtime._DefaultDenyAuthorizer())

    def observer(sink):
        result = _input_result(path)
        sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
        return result

    components = l43_runtime._RuntimeComponents(
        session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
        observer=observer,
        operator=operator,
    )
    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=lambda _effect_boundary: components,
    )

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.AUTHORIZATION_MISSING
    assert result.reason_code == "ENTRY_AUTHORIZATION_MISSING"
    assert mcp.calls == []
    assert mcp.list_calls == 1
    assert _IDENTITY == DurableStateStore.open(path, _IDENTITY).state.identity
    assert DurableStateStore.open(path, _IDENTITY).state.entry is None


def test_operator_default_deny_blocks_exact_owned_sell_review_before_review_call(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)
    operator = _operator(path, mcp, authorizer=l43_runtime._DefaultDenyAuthorizer())

    def observer(sink):
        result = _input_result(path)
        sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
        return result

    components = l43_runtime._RuntimeComponents(
        session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
        observer=observer,
        operator=operator,
    )
    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=lambda _effect_boundary: components,
    )

    result = runtime.run_cycle(threading.Event())

    assert result.status is RestrictedLiveStatus.AUTHORIZATION_MISSING
    assert result.reason_code == "SELL_REVIEW_AUTHORIZATION_MISSING"
    assert mcp.list_calls == 0
    assert mcp.calls == []
    assert DurableStateStore.open(path, _IDENTITY).state.sell_review is None


def test_stop_before_serialized_entry_boundary_denies_before_reservation_or_place(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    stop = threading.Event()
    positive_authorizer = _Authorizer()

    def delayed_reobserver(session, *, requested_entry_risk=None):
        assert session.state.entry is None
        plan = _plan_for_state(
            session,
            requested_risk=requested_entry_risk or Decimal("10.00"),
        )
        stop.set()
        return _operator_pre_effect(plan)

    def build_components(effect_boundary):
        operator = _operator(
            path,
            mcp,
            authorizer=positive_authorizer,
            reobserver=delayed_reobserver,
            effect_boundary=effect_boundary,
        )

        def observer(sink):
            result = _input_result(path)
            sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
            return result

        return l43_runtime._RuntimeComponents(
            session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
            observer=observer,
            operator=operator,
        )

    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=build_components,
    )

    result = runtime.run_cycle(stop)

    state = DurableStateStore.open(path, _IDENTITY).state
    assert result.status is RestrictedLiveStatus.BLOCKED
    assert result.reason_code == "ENTRY_STOP_REQUESTED"
    assert stop.is_set()
    assert len(positive_authorizer.requests) == len(positive_authorizer.grants) == 1
    assert state.entry is None
    assert mcp.calls == []


def test_stop_wins_after_positive_entry_grant_before_serialized_boundary(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    stop = threading.Event()
    authorizer = _PauseAfterGrantAuthorizer(L43EffectStage.ENTRY_PLACEMENT)

    def observer(sink):
        result = _input_result(path)
        sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
        return result

    def components(effect_boundary):
        return l43_runtime._RuntimeComponents(
            session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
            observer=observer,
            operator=_operator(
                path,
                mcp,
                authorizer=authorizer,
                effect_boundary=effect_boundary,
            ),
        )

    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=components,
    )
    result_box: list[l43_runtime.L43RuntimeObservation] = []
    worker = threading.Thread(
        target=lambda: result_box.append(runtime.run_cycle(stop)),
        name="rhc4-entry-boundary-test",
    )
    worker.start()
    assert authorizer.grant_returned.wait(timeout=4)
    runtime.request_stop()
    authorizer.release.set()
    worker.join(timeout=4)

    assert not worker.is_alive()
    assert len(result_box) == 1
    assert result_box[0].status is RestrictedLiveStatus.BLOCKED
    assert result_box[0].reason_code == "ENTRY_STOP_REQUESTED"
    assert stop.is_set()
    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.entry is None
    assert mcp.calls == []


def test_stop_wins_after_positive_sell_review_grant_before_serialized_boundary(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)
    stop = threading.Event()
    authorizer = _PauseAfterGrantAuthorizer(L43EffectStage.SELL_REVIEW)

    def observer(sink):
        result = _input_result(path)
        sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
        return result

    def components(effect_boundary):
        return l43_runtime._RuntimeComponents(
            session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
            observer=observer,
            operator=_operator(
                path,
                mcp,
                authorizer=authorizer,
                effect_boundary=effect_boundary,
            ),
        )

    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=components,
    )
    result_box: list[l43_runtime.L43RuntimeObservation] = []
    worker = threading.Thread(
        target=lambda: result_box.append(runtime.run_cycle(stop)),
        name="rhc4-review-boundary-test",
    )
    worker.start()
    if not authorizer.grant_returned.wait(timeout=4):
        worker.join(timeout=1)
        pytest.fail(f"runtime returned before sell review grant: {result_box!r}")
    runtime.request_stop()
    authorizer.release.set()
    worker.join(timeout=4)

    assert not worker.is_alive()
    assert len(result_box) == 1
    assert result_box[0].status is RestrictedLiveStatus.BLOCKED
    assert result_box[0].reason_code == "SELL_REVIEW_STOP_REQUESTED"
    assert stop.is_set()
    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.sell_review is None
    assert state.exit is None
    assert mcp.calls == []


def test_stop_wins_after_positive_sell_placement_grant_before_serialized_boundary(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)
    stop = threading.Event()
    authorizer = _PauseAfterGrantAuthorizer(L43EffectStage.SELL_PLACEMENT)

    async def reviewer(*, account_number, proposal):
        return _affirmative_review(proposal)

    def observer(sink):
        result = _input_result(path)
        sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
        return result

    def components(effect_boundary):
        return l43_runtime._RuntimeComponents(
            session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
            observer=observer,
            operator=_operator(
                path,
                mcp,
                authorizer=authorizer,
                effect_boundary=effect_boundary,
                review_caller=reviewer,
            ),
        )

    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=components,
    )
    result_box: list[l43_runtime.L43RuntimeObservation] = []
    worker = threading.Thread(
        target=lambda: result_box.append(runtime.run_cycle(stop)),
        name="rhc4-sell-boundary-test",
    )
    worker.start()
    if not authorizer.grant_returned.wait(timeout=4):
        worker.join(timeout=1)
        pytest.fail(f"runtime returned before sell placement grant: {result_box!r}")
    runtime.request_stop()
    authorizer.release.set()
    worker.join(timeout=4)

    assert not worker.is_alive()
    assert len(result_box) == 1
    assert result_box[0].status is RestrictedLiveStatus.BLOCKED
    assert result_box[0].reason_code == "SELL_PLACEMENT_STOP_REQUESTED"
    assert stop.is_set()
    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.sell_review is not None
    assert state.sell_review.status is L43SellReviewStatus.ACCEPTED
    assert state.exit is None
    assert mcp.calls == []


def test_real_durable_pending_sell_settles_before_review_or_replacement(tmp_path: Path):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path, provider_order_id=_EXIT_ORDER_ID)
    reconciler = _Reconciler(
        exit_status=OrderStatus.WORKING,
        exit_quantity=Decimal("0"),
    )
    review_calls: list[object] = []

    async def reviewer(*, account_number, proposal):
        review_calls.append((account_number, proposal))
        return _affirmative_review(proposal)

    operator = _operator(
        path,
        mcp,
        reconciler=reconciler,
        review_caller=reviewer,
    )
    reviewed = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )
    placed = asyncio.run(
        operator.place_sell(
            _input_result(path),
            reviewed.accepted_review,
            account_number="account-one",
        )
    )
    assert placed.outcome is L43EffectOutcome.SELL_PENDING
    before = DurableStateStore.open(path, _IDENTITY).state
    assert before.sell_review is not None
    assert before.sell_review.status is L43SellReviewStatus.ACCEPTED
    assert before.exit is not None and before.exit.status is IntentStatus.WORKING

    reconciler.exit_status = OrderStatus.FILLED
    reconciler.exit_quantity = _OWNED
    components = l43_runtime._RuntimeComponents(
        session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
        observer=lambda _sink: pytest.fail("pending sell must not observe again"),
        operator=operator,
    )
    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=lambda _effect_boundary: components,
    )

    result = runtime.run_cycle(threading.Event())

    after = DurableStateStore.open(path, _IDENTITY).state
    assert result.status is RestrictedLiveStatus.SELL_RECONCILED
    assert after.exit is not None and after.exit.status is IntentStatus.FILLED
    assert review_calls and len(review_calls) == 1
    assert reconciler.settlement_calls == 1
    assert len(mcp.calls) == 1


def test_stop_after_may_allows_one_fake_placement_and_reconciliation_to_finish(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    stop = threading.Event()
    stop_during_may: list[tuple[IntentStatus, str | None]] = []

    reconciliation_state: list[tuple[bool, IntentStatus, str | None]] = []

    class _ObserveStopReconciler(_Reconciler):
        async def reconcile(self, **kwargs):
            known_state = kwargs["known_state"]
            assert known_state.entry is not None
            reconciliation_state.append(
                (
                    stop.is_set(),
                    known_state.entry.status,
                    known_state.entry.provider_order_id,
                )
            )
            return await super().reconcile(**kwargs)

    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer()
    reconciler = _ObserveStopReconciler()

    def observer(sink):
        result = _input_result(path)
        sink(L43AccountIdentity("account-one", _IDENTITY.account_fingerprint))
        return result

    def build_components(effect_boundary):
        @contextmanager
        def boundary():
            with effect_boundary() as admitted:
                yield admitted
            if admitted:
                state = DurableStateStore.open(path, _IDENTITY).state
                assert state.entry is not None
                stop_during_may.append(
                    (state.entry.status, state.entry.provider_order_id)
                )
                runtime.request_stop()

        operator = _operator(
            path,
            mcp,
            authorizer=authorizer,
            reconciler=reconciler,
            effect_boundary=boundary,
        )
        return l43_runtime._RuntimeComponents(
            session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
            observer=observer,
            operator=operator,
        )

    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=build_components,
    )

    result = runtime.run_cycle(stop)

    state = DurableStateStore.open(path, _IDENTITY).state
    assert result.status is RestrictedLiveStatus.ENTRY_RECONCILED
    assert stop.is_set()
    assert len(mcp.calls) == 1
    assert mcp.events[0] == ("MAY_HAVE_OCCURRED", IntentKind.ENTRY)
    assert stop_during_may == [(IntentStatus.MAY_HAVE_OCCURRED, None)]
    assert reconciler.calls == 1
    assert reconciliation_state == [(True, IntentStatus.WORKING, _ENTRY_ORDER_ID)]
    assert state.entry is not None and state.entry.status is IntentStatus.FILLED
    assert authorizer.requests and len(authorizer.grants) == 1


def test_runtime_settlement_read_failure_blocks_and_preserves_durable_pending_facts(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    reconciler = _Reconciler(
        entry_status=OrderStatus.WORKING,
        entry_quantity=Decimal("0"),
    )
    operator = _operator(path, mcp, reconciler=reconciler)
    placed = asyncio.run(
        operator.place_entry(_input_result(path), account_number="account-one")
    )
    assert placed.outcome is L43EffectOutcome.ENTRY_PENDING
    reconciler.fail = True
    before = DurableStateStore.open(path, _IDENTITY).state
    provider_calls = list(mcp.calls)

    components = l43_runtime._RuntimeComponents(
        session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
        observer=lambda _sink: pytest.fail("pending state must settle before observe"),
        operator=operator,
    )
    runtime = l43_runtime.L43Runtime(
        expected_source=_CURRENT,
        source_reader=lambda: _CURRENT,
        components_factory=lambda _effect_boundary: components,
    )

    result = runtime.run_cycle(threading.Event())

    after = DurableStateStore.open(path, _IDENTITY).state
    assert result.status is RestrictedLiveStatus.BLOCKED
    assert result.reason_code == "PENDING_ORDER_SETTLEMENT_FAILED"
    assert before.entry is not None and after.entry == before.entry
    assert after.owned_quantity == before.owned_quantity
    assert reconciler.settlement_calls == 1
    assert mcp.calls == provider_calls
