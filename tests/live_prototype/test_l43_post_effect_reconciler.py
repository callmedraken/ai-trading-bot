from __future__ import annotations

import asyncio
import hashlib
import threading
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.domain import OrderSide
from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import (
    DurableStateStore,
    IntentKind,
    IntentStatus,
    OrderObservation,
    OrderState,
    OrderStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)
from trading_bot.live_prototype.l43_effect_operator import L43EffectStage
from trading_bot.live_prototype.l43_post_effect_reconciler import (
    L43ExactPostEffectReconciler,
    _normalize_order,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43OrderScope,
    L43OrderScopeProof,
    L43PlanKind,
    L43PreEffectDependencies,
    L43PreEffectPlan,
    _account_wide_spy_order_query_digest,
)
from trading_bot.live_prototype.l43_production_owner import (
    ContinuityStatus,
    D34SignalFacts,
    L43ContinuityResult,
    L43ProductionOwner,
    L43Provenance,
    L43SourceIdentity,
    Q62JournalOrigin,
    RecoveryFacts,
    XnysSessionFacts,
)
from trading_bot.live_prototype.l43_provider_contracts import (
    L43AccountIdentity,
    L43DollarAmountFact,
    L43ExecutionFact,
    L43OrderFact,
    L43PositionFact,
    L43ReadPage,
    L43TransportError,
)
from trading_bot.live_prototype.l43_state import L43StateSession, origin_anchor_from_q62
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.tiny_live_policy import (
    EntryTerminalOutcome,
    ExactOwnedSellProposal,
    ReconciledOwnedPosition,
    SellOrderArguments,
    SellOrderContext,
    SellOrderType,
    SellSession,
    SellSide,
    SellTimeInForce,
    TerminalEntryEvidence,
)

_NOW = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
_ACCOUNT_NUMBER = "912345678901"
_SOURCE = L43SourceIdentity(source_head="8" * 40, source_tree="9" * 40)
_ACCOUNT_FINGERPRINT = hashlib.sha256(_ACCOUNT_NUMBER.encode("ascii")).hexdigest()


def _sha(char: str) -> str:
    return char * 64


def _origin() -> Q62JournalOrigin:
    identity = RuntimeIdentity(
        account_fingerprint=_ACCOUNT_FINGERPRINT,
        source_head="1" * 40,
        source_tree="2" * 40,
        config_digest=_sha("3"),
        binding_digest=_sha("4"),
        lifecycle_id="00000000-0000-0000-0000-000000000147",
    )
    return Q62JournalOrigin(
        runtime_identity=identity,
        journal_label="arch147-q62-live-state-v1",
        journal_sha256=_sha("5"),
        initialization_event_sha256=_sha("6"),
        consumed_observation_sha256=_sha("7"),
    )


class _UnusedOwnerBoundary:
    def verify(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("post-effect reconciliation must not re-run authority")

    def replay(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("post-effect reconciliation must not replay Q62")


class _ScopeVerifier:
    def __init__(self, origin: Q62JournalOrigin, *, mode: str = "valid") -> None:
        self.origin = origin
        self.mode = mode
        self.calls: list[tuple[dict[str, object], int, int, bool]] = []

    def verify_account_wide_spy_orders(
        self,
        *,
        account_fingerprint: str,
        query_sha256: str,
        order_arguments: dict[str, object],
        pages_read: int,
        row_count: int,
        exhausted: bool,
    ) -> L43OrderScopeProof | None:
        self.calls.append((dict(order_arguments), pages_read, row_count, exhausted))
        if self.mode == "missing":
            return None
        if account_fingerprint != self.origin.runtime_identity.account_fingerprint:
            return None
        expected = _account_wide_spy_order_query_digest(
            account_fingerprint, order_arguments
        )
        if self.mode == "tampered":
            expected = _sha("a")
        return L43OrderScopeProof(
            scope=L43OrderScope.ACCOUNT_WIDE_ALL_AGENTS,
            query_sha256=expected if self.mode == "tampered" else query_sha256,
            pages_read=pages_read,
            row_count=row_count,
            exhausted=exhausted,
            evidence_sha256=_sha("b"),
        )


class _ReadBoundary:
    def __init__(
        self,
        origin: Q62JournalOrigin,
        *,
        position_quantity: Decimal,
        orders: tuple[L43OrderFact, ...],
    ) -> None:
        self.origin = origin
        self.position_quantity = position_quantity
        self.orders = orders
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.account_thread: int | None = None

    def get_accounts(self) -> L43AccountIdentity:
        self.account_thread = threading.get_ident()
        self.calls.append(("get_accounts", {}))
        return L43AccountIdentity(_ACCOUNT_NUMBER, _ACCOUNT_FINGERPRINT)

    def get_equity_positions(self, arguments: dict[str, object]) -> L43ReadPage:
        self.calls.append(("get_equity_positions", dict(arguments)))
        rows = ()
        if self.position_quantity > 0:
            rows = (
                L43PositionFact(
                    "SPY",
                    self.position_quantity,
                    self.position_quantity,
                    "long",
                ),
            )
        return L43ReadPage(rows=rows, next_cursor=None)

    def get_equity_orders(self, arguments: dict[str, object]) -> L43ReadPage:
        self.calls.append(("get_equity_orders", dict(arguments)))
        assert arguments.get("account_number") == _ACCOUNT_NUMBER
        assert arguments.get("symbol") == "SPY"
        assert "order_id" not in arguments
        return L43ReadPage(rows=self.orders, next_cursor=None)


def _entry_order(
    *,
    provider_order_id: str = "entry-provider-147",
    status: str = "partially_filled",
    quantity: Decimal = Decimal("0.5"),
    requested_quantity: Decimal | None = Decimal("0.5"),
    price: Decimal = Decimal("20"),
    amount: Decimal = Decimal("10.00"),
    currency: str = "USD",
    trigger: str = "immediate",
    executions: tuple[L43ExecutionFact, ...] | None = None,
    agent_initiated: bool = True,
) -> L43OrderFact:
    if executions is None:
        executions = (
            () if quantity == 0 else (_execution("entry-execution-1", quantity, price),)
        )
    return L43OrderFact(
        order_id=provider_order_id,
        symbol="SPY",
        side=OrderSide.BUY,
        state=status,
        placed_agent="user-shaped-provider-value",
        agent_initiated=agent_initiated,
        created_at=_NOW,
        market_hours="regular_hours",
        time_in_force="gfd",
        order_type="market",
        trigger=trigger,
        requested_quantity=requested_quantity,
        cumulative_quantity=quantity,
        average_price=price if quantity > 0 else None,
        dollar_based_amount=L43DollarAmountFact(amount, currency),
        executions=executions,
    )


def _execution(
    execution_id: str,
    quantity: Decimal,
    price: Decimal,
) -> L43ExecutionFact:
    return L43ExecutionFact(execution_id, quantity, price, _NOW)


def _entry_plan(origin: Q62JournalOrigin, state) -> L43PreEffectPlan:
    identity = origin.runtime_identity
    provenance = L43Provenance(
        config_digest=identity.config_digest,
        binding_digest=identity.binding_digest,
        account_fingerprint=identity.account_fingerprint,
    )
    continuity = L43ContinuityResult(
        status=ContinuityStatus.ACCEPTED,
        origin=origin,
        current=_SOURCE,
        provenance=provenance,
    )
    return L43PreEffectPlan(
        kind=L43PlanKind.ENTRY,
        current_source=_SOURCE,
        provenance=provenance,
        continuity=continuity,
        state_last_sequence=state.last_sequence,
        state_tail_sha256=state.journal_hash,
        state_journal_sha256=state.journal_hash,
        reconciliation_snapshot=ReconciliationSnapshot(identity, Decimal("0")),
        account_fingerprint=identity.account_fingerprint,
        positions_digest=_sha("a"),
        relevant_orders_digest=_sha("b"),
        order_scope_digest=_sha("c"),
        session=XnysSessionFacts("2026-11-10", True, True, _sha("d")),
        signal=D34SignalFacts(SignalDecision.BUY, _sha("e")),
        recovery=RecoveryFacts(True, False, False, Decimal("0"), _sha("f")),
        observation_as_of=_NOW,
        signal_observation_digest=_sha("1"),
        positions_observation_digest=_sha("2"),
        orders_observation_digest=_sha("3"),
        order_scope_evidence_digest=_sha("4"),
        requested_entry_risk=Decimal("10.00"),
    )


def _new_entry_state(tmp_path: Path):
    origin = _origin()
    anchor = origin_anchor_from_q62(origin)
    path = tmp_path / "l43-state.jsonl"
    store = DurableStateStore.create(
        path,
        origin.runtime_identity,
        l43_origin=anchor,
    )
    path.with_suffix(path.suffix + ".lock").write_bytes(b"\0")
    with L43StateSession.open_existing(path, anchor) as session:
        session.reconcile(ReconciliationSnapshot(origin.runtime_identity, Decimal("0")))
        plan = _entry_plan(origin, session.state)
        intent_id = session.reserve_entry(Decimal("10.00"))
        session.prepare_invocation(intent_id)
        session.bind_provider_order(intent_id, "entry-provider-147")
        known_state = session.state
    assert known_state.last_sequence == plan.state_last_sequence + 3
    assert known_state.entry is not None
    assert known_state.entry.status is IntentStatus.WORKING
    assert known_state.entry.working_remainder == Decimal("0")
    del store
    return origin, plan, intent_id, known_state, path


def _dependencies(
    origin: Q62JournalOrigin,
    read: _ReadBoundary,
    *,
    scope_mode: str = "valid",
    clock_values: tuple[datetime, ...] | None = None,
    source_values: tuple[L43SourceIdentity, ...] | None = None,
) -> L43PreEffectDependencies:
    unused = _UnusedOwnerBoundary()
    scope = _ScopeVerifier(origin, mode=scope_mode)
    clock_iter = iter(clock_values or (_NOW,))
    source_iter = iter(source_values or (_SOURCE,))

    def clock() -> datetime:
        try:
            return next(clock_iter)
        except StopIteration:
            return clock_values[-1] if clock_values else _NOW

    def source_reader() -> L43SourceIdentity:
        try:
            return next(source_iter)
        except StopIteration:
            return source_values[-1] if source_values else _SOURCE

    return L43PreEffectDependencies(
        source_reader=source_reader,
        continuity_owner=L43ProductionOwner(
            authority_verifier=unused,
            journal_reader=unused,
        ),
        origin=origin,
        state_snapshot_reader=lambda _origin: None,
        robinhood_builder=lambda: read,
        signal_provider_builder=lambda: object(),
        clock=clock,
        order_scope_verifier=scope,
        read_operation_scope_factory=lambda _read: nullcontext(),
    )


def _read(
    origin: Q62JournalOrigin,
    *,
    order: L43OrderFact,
    position: Decimal,
    extra_orders: tuple[L43OrderFact, ...] = (),
) -> _ReadBoundary:
    return _ReadBoundary(
        origin,
        position_quantity=position,
        orders=(order, *extra_orders),
    )


def _run_entry_reconcile(
    *,
    origin: Q62JournalOrigin,
    plan: L43PreEffectPlan,
    intent_id: str,
    known_state,
    read: _ReadBoundary,
    dependencies: L43PreEffectDependencies | None = None,
):
    if dependencies is None:
        dependencies = _dependencies(origin, read)
    return asyncio.run(
        L43ExactPostEffectReconciler(dependencies).reconcile(
            stage=L43EffectStage.ENTRY_PLACEMENT,
            plan=plan,
            intent_id=intent_id,
            provider_order_id="entry-provider-147",
            known_state=known_state,
        )
    )


def test_entry_post_effect_uses_off_thread_read_and_ignores_provider_share_estimate(
    tmp_path: Path,
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    main_thread = threading.get_ident()
    facts_by_estimate = []
    for estimate in (Decimal("0.5"), Decimal("0.8")):
        read = _read(
            origin,
            order=_entry_order(requested_quantity=estimate, price=Decimal("19")),
            position=Decimal("0.5"),
        )
        facts = _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
        )
        facts_by_estimate.append(facts)
        assert read.account_thread != main_thread
        assert [name for name, _ in read.calls] == [
            "get_accounts",
            "get_equity_positions",
            "get_equity_orders",
        ]
        assert read.calls[-1][1] == {
            "account_number": _ACCOUNT_NUMBER,
            "symbol": "SPY",
        }
        assert facts.all_relevant_orders_proven is True
        assert len(facts.snapshot.orders) == 1
        observation = facts.snapshot.orders[0]
        assert observation.local_intent_id == intent_id
        assert observation.provider_order_id == "entry-provider-147"
        assert observation.status is OrderStatus.PARTIAL
        assert observation.cumulative_quantity == Decimal("0.5")
        assert observation.cumulative_notional == Decimal("9.5")
        assert observation.working_remainder == Decimal("0")
        assert known_state.entry_reserved_dollars == Decimal("10.00")

    first, second = facts_by_estimate
    assert first.snapshot == second.snapshot
    assert first.orders_digest != second.orders_digest
    assert first.evidence_sha256 != second.evidence_sha256


def test_entry_post_effect_working_zero_fill_has_zero_remainder_and_stays_blocked(
    tmp_path: Path,
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    read = _read(
        origin,
        order=_entry_order(
            status="pending_cancelled",
            quantity=Decimal("0"),
            requested_quantity=None,
            executions=(),
        ),
        position=Decimal("0"),
    )

    facts = _run_entry_reconcile(
        origin=origin,
        plan=plan,
        intent_id=intent_id,
        known_state=known_state,
        read=read,
    )

    observation = facts.snapshot.orders[0]
    assert observation.status is OrderStatus.WORKING
    assert observation.cumulative_quantity == Decimal("0")
    assert observation.cumulative_notional == Decimal("0")
    assert observation.working_remainder == Decimal("0")
    assert known_state.entry_reserved_dollars == Decimal("10.00")
    assert known_state.automated_order_allowed is False


@pytest.mark.parametrize(
    ("state", "quantity", "requested", "trigger", "currency", "amount", "agent"),
    (
        (
            "unknown",
            Decimal("0.5"),
            Decimal("0.5"),
            "immediate",
            "USD",
            Decimal("10"),
            True,
        ),
        (
            "filled",
            Decimal("0.5"),
            Decimal("0.5"),
            "stop",
            "USD",
            Decimal("10"),
            True,
        ),
        (
            "filled",
            Decimal("0.5"),
            Decimal("0.5"),
            "immediate",
            "USD",
            Decimal("9.99"),
            True,
        ),
        (
            "filled",
            Decimal("0.5"),
            Decimal("0.5"),
            "immediate",
            "CAD",
            Decimal("10"),
            True,
        ),
        (
            "filled",
            Decimal("0.5"),
            Decimal("0.5"),
            "immediate",
            "USD",
            Decimal("10"),
            False,
        ),
    ),
)
def test_entry_post_effect_rejects_unknown_or_mismatched_material(
    tmp_path: Path,
    state: str,
    quantity: Decimal,
    requested: Decimal,
    trigger: str,
    currency: str,
    amount: Decimal,
    agent: bool,
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    read = _read(
        origin,
        order=_entry_order(
            status=state,
            quantity=quantity,
            requested_quantity=requested,
            trigger=trigger,
            currency=currency,
            amount=amount,
            agent_initiated=agent,
        ),
        position=quantity,
    )

    with pytest.raises(L43TransportError):
        _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
        )


@pytest.mark.parametrize(
    "bad_execution",
    (
        (_execution("entry-execution-1", Decimal("0.25"), Decimal("20")),),
        (
            _execution("duplicate-execution", Decimal("0.25"), Decimal("20")),
            _execution("duplicate-execution", Decimal("0.25"), Decimal("20")),
        ),
        (_execution("entry-execution-1", Decimal("0.5"), Decimal("0")),),
        (_execution("entry-execution-1", Decimal("0.5"), Decimal("-20")),),
    ),
)
def test_entry_post_effect_rejects_inconsistent_or_malformed_executions(
    tmp_path: Path,
    bad_execution: tuple[L43ExecutionFact, ...],
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    read = _read(
        origin,
        order=_entry_order(
            status="partially_filled",
            quantity=Decimal("0.5"),
            executions=bad_execution,
        ),
        position=Decimal("0.5"),
    )

    with pytest.raises(L43TransportError):
        _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
        )


@pytest.mark.parametrize("failure", ("position", "unrelated", "missing", "duplicate"))
def test_entry_post_effect_requires_exact_complete_order_and_position_match(
    tmp_path: Path,
    failure: str,
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    order = _entry_order()
    position = Decimal("0.5")
    extras: tuple[L43OrderFact, ...] = ()
    if failure == "position":
        position = Decimal("0.4")
    elif failure == "unrelated":
        extras = (_entry_order(provider_order_id="unrelated-order"),)
    elif failure == "missing":
        order = None
    elif failure == "duplicate":
        extras = (_entry_order(),)
    read = _ReadBoundary(
        origin,
        position_quantity=position,
        orders=(() if order is None else (order, *extras)),
    )

    with pytest.raises(L43TransportError):
        _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
        )


@pytest.mark.parametrize("scope_mode", ("missing", "tampered"))
def test_entry_post_effect_fails_closed_without_exact_rhc3_scope(
    tmp_path: Path,
    scope_mode: str,
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    read = _read(
        origin,
        order=_entry_order(),
        position=Decimal("0.5"),
    )
    dependencies = _dependencies(origin, read, scope_mode=scope_mode)

    with pytest.raises(L43TransportError):
        _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
            dependencies=dependencies,
        )


def test_entry_post_effect_rejects_stale_snapshot_and_source_drift(
    tmp_path: Path,
) -> None:
    origin, plan, intent_id, known_state, _ = _new_entry_state(tmp_path)
    read = _read(origin, order=_entry_order(), position=Decimal("0.5"))
    stale = _dependencies(
        origin,
        read,
        clock_values=(
            _NOW,
            _NOW,
            _NOW + timedelta(minutes=3),
            _NOW + timedelta(minutes=3),
        ),
    )
    with pytest.raises(L43TransportError):
        _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
            dependencies=stale,
        )

    read = _read(origin, order=_entry_order(), position=Decimal("0.5"))
    changed_source = L43SourceIdentity("a" * 40, "b" * 40)
    source_drift = _dependencies(
        origin,
        read,
        source_values=(_SOURCE, changed_source),
    )
    with pytest.raises(L43TransportError):
        _run_entry_reconcile(
            origin=origin,
            plan=plan,
            intent_id=intent_id,
            known_state=known_state,
            read=read,
            dependencies=source_drift,
        )


def _sell_plan(origin: Q62JournalOrigin, state) -> L43PreEffectPlan:
    identity = origin.runtime_identity
    provenance = L43Provenance(
        config_digest=identity.config_digest,
        binding_digest=identity.binding_digest,
        account_fingerprint=identity.account_fingerprint,
    )
    continuity = L43ContinuityResult(
        status=ContinuityStatus.ACCEPTED,
        origin=origin,
        current=_SOURCE,
        provenance=provenance,
    )
    readiness_identity = ReadinessIdentity(
        source_head=_SOURCE.source_head,
        source_tree=_SOURCE.source_tree,
        config_digest=identity.config_digest,
        account_fingerprint=identity.account_fingerprint,
        target_session="2026-11-10",
    )
    entry = state.entry
    assert entry is not None and entry.provider_order_id is not None
    owned = entry.cumulative_quantity
    ownership = OwnershipSnapshot(
        account_fingerprint=identity.account_fingerprint,
        source_head=_SOURCE.source_head,
        source_tree=_SOURCE.source_tree,
        config_digest=identity.config_digest,
        binding_digest=identity.binding_digest,
        lifecycle_id=identity.lifecycle_id,
        target_session="2026-11-10",
        lifecycle=Lifecycle.RUNNING,
        effect_disposition=EffectDisposition.CONFIRMED,
        baseline_quantity=Decimal("0"),
        cumulative_bought=owned,
        cumulative_sold=Decimal("0"),
        cumulative_entry_filled_dollars=entry.cumulative_notional,
        entry_reserved_dollars=entry.requested_dollars,
        entries_used=1,
        exits_used=0,
        entry_local_intent_id=entry.intent_id,
        entry_provider_order_id=entry.provider_order_id,
    )
    position = ReconciledOwnedPosition(
        identity=readiness_identity,
        ownership_snapshot=ownership,
        broker_position_quantity=owned,
        broker_sellable_quantity=owned,
        working_order_count=0,
        unresolved_order_count=0,
        evidence_sha256=_sha("8"),
    )
    terminal = TerminalEntryEvidence(
        local_intent_id=entry.intent_id,
        provider_order_id=entry.provider_order_id,
        outcome=EntryTerminalOutcome.FILLED,
        requested_usd_cents=1000,
        reserved_usd_cents=1000,
        confirmed_filled_quantity=owned,
        confirmed_filled_notional=entry.cumulative_notional,
    )
    context = SellOrderContext(
        identity=readiness_identity,
        binding_digest=identity.binding_digest,
        lifecycle_id=identity.lifecycle_id,
        entry_local_intent_id=entry.intent_id,
        entry_provider_order_id=entry.provider_order_id,
        exact_owned_remainder=owned,
        broker_position_quantity=owned,
        broker_sellable_quantity=owned,
        terminal_entry_outcome=EntryTerminalOutcome.FILLED,
        reserved_usd_cents=1000,
        confirmed_entry_filled_quantity=owned,
        confirmed_entry_filled_notional=entry.cumulative_notional,
    )
    arguments = SellOrderArguments(
        side=SellSide.SELL,
        symbol="SPY",
        order_type=SellOrderType.MARKET,
        session=SellSession.REGULAR_HOURS,
        time_in_force=SellTimeInForce.DAY,
        quantity=owned,
        context=context,
    )
    proposal = ExactOwnedSellProposal(
        position=position,
        terminal_entry=terminal,
        review_arguments=arguments,
        placement_arguments=arguments,
    )
    return L43PreEffectPlan(
        kind=L43PlanKind.EXACT_OWNED_SELL_REVIEW,
        current_source=_SOURCE,
        provenance=provenance,
        continuity=continuity,
        state_last_sequence=state.last_sequence,
        state_tail_sha256=state.journal_hash,
        state_journal_sha256=state.journal_hash,
        reconciliation_snapshot=ReconciliationSnapshot(
            identity,
            owned,
            (
                OrderObservation(
                    local_intent_id=entry.intent_id,
                    provider_order_id=entry.provider_order_id,
                    status=OrderStatus.FILLED,
                    cumulative_quantity=entry.cumulative_quantity,
                    cumulative_notional=entry.cumulative_notional,
                    working_remainder=Decimal("0"),
                ),
            ),
        ),
        account_fingerprint=identity.account_fingerprint,
        positions_digest=_sha("a"),
        relevant_orders_digest=_sha("b"),
        order_scope_digest=_sha("c"),
        session=XnysSessionFacts("2026-11-10", True, True, _sha("d")),
        signal=D34SignalFacts(SignalDecision.SELL, _sha("e")),
        recovery=RecoveryFacts(True, False, True, owned, _sha("f")),
        observation_as_of=_NOW,
        signal_observation_digest=_sha("1"),
        positions_observation_digest=_sha("2"),
        orders_observation_digest=_sha("3"),
        order_scope_evidence_digest=_sha("4"),
        sell_proposal=proposal,
    )


def _new_sell_state(tmp_path: Path):
    origin = _origin()
    anchor = origin_anchor_from_q62(origin)
    path = tmp_path / "l43-sell-state.jsonl"
    DurableStateStore.create(path, origin.runtime_identity, l43_origin=anchor)
    path.with_suffix(path.suffix + ".lock").write_bytes(b"\0")
    with L43StateSession.open_existing(path, anchor) as session:
        session.reconcile(ReconciliationSnapshot(origin.runtime_identity, Decimal("0")))
        entry_id = session.reserve_entry(Decimal("10.00"))
        session.prepare_invocation(entry_id)
        session.bind_provider_order(entry_id, "entry-provider-147")
        session.reconcile(
            ReconciliationSnapshot(
                origin.runtime_identity,
                Decimal("0.5"),
                (
                    OrderObservation(
                        local_intent_id=entry_id,
                        provider_order_id="entry-provider-147",
                        status=OrderStatus.FILLED,
                        cumulative_quantity=Decimal("0.5"),
                        cumulative_notional=Decimal("10"),
                        working_remainder=Decimal("0"),
                    ),
                ),
            )
        )
        proposal = _sell_plan(origin, session.state).sell_proposal
        assert proposal is not None
        proposal_sha = proposal.proposal_sha256()
        arguments_sha = _sha("9")
        session.begin_sell_review(
            proposal_sha256=proposal_sha,
            arguments_sha256=arguments_sha,
        )
        session.accept_sell_review(
            proposal_sha256=proposal_sha,
            arguments_sha256=arguments_sha,
            review_evidence_sha256=_sha("8"),
        )
        plan = _sell_plan(origin, session.state)
        exit_id = session.reserve_exit(
            Decimal("0.5"),
            authority_sha256=_sha("a"),
        )
        session.prepare_invocation(exit_id)
        session.bind_provider_order(exit_id, "exit-provider-147")
        known_state = session.state
    assert known_state.last_sequence == plan.state_last_sequence + 3
    assert known_state.exit is not None
    assert known_state.exit.status is IntentStatus.WORKING
    return origin, plan, exit_id, known_state


def _exit_order(
    *,
    status: str,
    quantity: Decimal,
    requested_quantity: Decimal = Decimal("0.5"),
    executions: tuple[L43ExecutionFact, ...] | None = None,
    trigger: str = "immediate",
    dollar_amount: L43DollarAmountFact | None = None,
) -> L43OrderFact:
    if executions is None:
        executions = (
            ()
            if quantity == 0
            else (_execution("exit-execution-1", quantity, Decimal("20")),)
        )
    return L43OrderFact(
        order_id="exit-provider-147",
        symbol="SPY",
        side=OrderSide.SELL,
        state=status,
        placed_agent="human-readable-label-is-ignored",
        agent_initiated=True,
        created_at=_NOW,
        market_hours="regular_hours",
        time_in_force="gfd",
        order_type="market",
        trigger=trigger,
        requested_quantity=requested_quantity,
        cumulative_quantity=quantity,
        average_price=Decimal("20") if quantity > 0 else None,
        dollar_based_amount=dollar_amount,
        executions=executions,
    )


@pytest.mark.parametrize(
    ("provider_state", "fill", "position", "expected_status", "remainder"),
    (
        ("new", Decimal("0"), Decimal("0.5"), OrderStatus.WORKING, Decimal("0.5")),
        (
            "partially_filled",
            Decimal("0.2"),
            Decimal("0.3"),
            OrderStatus.PARTIAL,
            Decimal("0.3"),
        ),
        ("filled", Decimal("0.5"), Decimal("0"), OrderStatus.FILLED, Decimal("0")),
        (
            "canceled",
            Decimal("0.2"),
            Decimal("0.3"),
            OrderStatus.CANCELED,
            Decimal("0"),
        ),
        (
            "rejected",
            Decimal("0.2"),
            Decimal("0.3"),
            OrderStatus.REJECTED,
            Decimal("0"),
        ),
    ),
)
def test_exact_sell_reconciles_full_order_set_and_share_remainder(
    tmp_path: Path,
    provider_state: str,
    fill: Decimal,
    position: Decimal,
    expected_status: OrderStatus,
    remainder: Decimal,
) -> None:
    origin, plan, intent_id, known_state = _new_sell_state(tmp_path)
    entry = _entry_order(
        status="filled",
        quantity=Decimal("0.5"),
        requested_quantity=None,
        amount=Decimal("10"),
    )
    exit_order = _exit_order(status=provider_state, quantity=fill)
    read = _read(
        origin,
        order=entry,
        position=position,
        extra_orders=(exit_order,),
    )
    facts = asyncio.run(
        L43ExactPostEffectReconciler(_dependencies(origin, read)).reconcile(
            stage=L43EffectStage.SELL_PLACEMENT,
            plan=plan,
            intent_id=intent_id,
            provider_order_id="exit-provider-147",
            known_state=known_state,
        )
    )

    by_intent = {item.local_intent_id: item for item in facts.snapshot.orders}
    exit_observation = by_intent[intent_id]
    assert facts.all_relevant_orders_proven is True
    assert len(facts.snapshot.orders) == 2
    assert exit_observation.status is expected_status
    assert exit_observation.cumulative_quantity == fill
    assert exit_observation.cumulative_notional == fill * Decimal("20")
    assert exit_observation.working_remainder == remainder
    assert facts.snapshot.observed_position == position


@pytest.mark.parametrize(
    ("status", "quantity", "expected_status", "remainder"),
    (
        ("new", Decimal("0"), OrderStatus.WORKING, Decimal("0.5")),
        ("partially_filled", Decimal("0.2"), OrderStatus.PARTIAL, Decimal("0.3")),
        ("filled", Decimal("0.5"), OrderStatus.FILLED, Decimal("0")),
        ("canceled", Decimal("0.2"), OrderStatus.CANCELED, Decimal("0")),
        ("rejected", Decimal("0.2"), OrderStatus.REJECTED, Decimal("0")),
    ),
)
def test_exact_sell_matcher_rejects_requested_quantity_and_trigger_mismatch(
    status: str,
    quantity: Decimal,
    expected_status: OrderStatus,
    remainder: Decimal,
) -> None:
    durable = OrderState(
        kind=IntentKind.EXIT,
        intent_id="00000000-0000-0000-0000-000000000147",
        requested_quantity=Decimal("0.5"),
        provider_order_id="exit-provider-147",
        status=IntentStatus.WORKING,
    )
    fact = _exit_order(status=status, quantity=quantity)

    observation = _normalize_order(fact, durable, is_new_target=True)

    assert observation.status is expected_status
    assert observation.working_remainder == remainder
    with pytest.raises(ValueError):
        _normalize_order(
            _exit_order(
                status=status,
                quantity=quantity,
                requested_quantity=Decimal("0.4"),
            ),
            durable,
            is_new_target=True,
        )
    with pytest.raises(ValueError):
        _normalize_order(
            _exit_order(status=status, quantity=quantity, trigger="stop"),
            durable,
            is_new_target=True,
        )


def test_exact_sell_rejects_bad_request_type_or_dollars() -> None:
    durable = OrderState(
        kind=IntentKind.EXIT,
        intent_id="00000000-0000-0000-0000-000000000147",
        requested_quantity=Decimal("0.5"),
        provider_order_id="exit-provider-147",
        status=IntentStatus.WORKING,
    )
    with pytest.raises(ValueError):
        _normalize_order(
            _exit_order(
                status="new",
                quantity=Decimal("0"),
                dollar_amount=L43DollarAmountFact(Decimal("10"), "USD"),
            ),
            durable,
            is_new_target=True,
        )
    malformed = _exit_order(status="new", quantity=Decimal("0"))
    object.__setattr__(malformed, "requested_quantity", True)
    with pytest.raises(ValueError):
        _normalize_order(malformed, durable, is_new_target=True)


def test_order_execution_quantity_and_notional_cannot_regress() -> None:
    durable = OrderState(
        kind=IntentKind.ENTRY,
        intent_id="00000000-0000-0000-0000-000000000148",
        requested_dollars=Decimal("10"),
        provider_order_id="entry-provider-147",
        status=IntentStatus.PARTIAL,
        cumulative_quantity=Decimal("0.5"),
        cumulative_notional=Decimal("10"),
    )
    with pytest.raises(ValueError):
        _normalize_order(
            _entry_order(
                status="partially_filled",
                quantity=Decimal("0.4"),
                executions=(_execution("old-fill", Decimal("0.4"), Decimal("20")),),
            ),
            durable,
            is_new_target=False,
        )
