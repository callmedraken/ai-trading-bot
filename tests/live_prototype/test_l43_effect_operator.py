from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import (
    DurableStateStore,
    IntentKind,
    IntentStatus,
    L43OriginAnchor,
    OrderObservation,
    OrderStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)
from trading_bot.live_prototype.l43_effect_operator import (
    L43AuthorizationRequest,
    L43EffectOperator,
    L43EffectOutcome,
    L43EffectStage,
    L43PostEffectFacts,
    L43StageAuthorization,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PlanKind,
    L43PreEffectBlocker,
    L43PreEffectOutcome,
    L43PreEffectPlan,
    L43PreEffectResult,
)
from trading_bot.live_prototype.l43_production_owner import (
    ContinuityStatus,
    D34SignalFacts,
    L43ContinuityResult,
    L43Provenance,
    L43SourceIdentity,
    Q62JournalOrigin,
    RecoveryFacts,
    XnysSessionFacts,
)
from trading_bot.live_prototype.l43_state import L43StateSession
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.tiny_live_policy import (
    EXACT_SELL_REVIEW_CONTRACT_ID,
    EntryTerminalOutcome,
    ExactOwnedSellProposal,
    ManualCloseTrigger,
    NormalizedReviewOutcome,
    NormalizedReviewSemantics,
    NormalizedSellReview,
    ReconciledOwnedPosition,
    SellOrderArguments,
    SellOrderContext,
    SellOrderType,
    SellSession,
    SellSide,
    SellTimeInForce,
    TerminalEntryEvidence,
)
from trading_bot.robinhood_mcp.l43_transport import L43RobinhoodTransport

_IDENTITY = RuntimeIdentity(
    account_fingerprint=hashlib.sha256(b"account-one").hexdigest(),
    source_head="1" * 40,
    source_tree="2" * 40,
    config_digest="3" * 64,
    binding_digest="4" * 64,
    lifecycle_id=str(UUID("eb8e31b2-cb9e-46f4-845d-eab478f43d50")),
)
_ORIGIN_ANCHOR = L43OriginAnchor(
    runtime_identity=_IDENTITY,
    journal_sha256="5" * 64,
    initialization_event_sha256="6" * 64,
    consumed_observation_sha256="7" * 64,
)
_Q62_ORIGIN = Q62JournalOrigin(
    runtime_identity=_IDENTITY,
    journal_label="q62-origin-journal",
    journal_sha256="5" * 64,
    initialization_event_sha256="6" * 64,
    consumed_observation_sha256="7" * 64,
)
_CURRENT = L43SourceIdentity(source_head="8" * 40, source_tree="9" * 40)
_PROVENANCE = L43Provenance(
    config_digest=_IDENTITY.config_digest,
    binding_digest=_IDENTITY.binding_digest,
    account_fingerprint=_IDENTITY.account_fingerprint,
)
_CONTINUITY = L43ContinuityResult(
    status=ContinuityStatus.ACCEPTED,
    origin=_Q62_ORIGIN,
    current=_CURRENT,
    provenance=_PROVENANCE,
)
_SESSION = XnysSessionFacts(
    target_session="2026-11-11",
    regular_hours=True,
    session_open=True,
    authority_digest="a" * 64,
)
_ZERO = Decimal("0")
_OWNED = Decimal("0.5")
_ENTRY_ORDER_ID = "entry-provider-order"
_EXIT_ORDER_ID = "exit-provider-order"
_NOW = datetime(2026, 11, 11, 17, 0, tzinfo=UTC)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _state_path(tmp_path: Path, *, reconciled: bool = True) -> Path:
    path = tmp_path / "l43-state.jsonl"
    DurableStateStore.create(path, _IDENTITY, l43_origin=_ORIGIN_ANCHOR)
    path.with_suffix(path.suffix + ".lock").write_bytes(b"")
    if reconciled:
        with L43StateSession.open_existing(path, _ORIGIN_ANCHOR) as session:
            session.reconcile(ReconciliationSnapshot(_IDENTITY, _ZERO))
    return path


def _owned_state(path: Path) -> None:
    with L43StateSession.open_existing(path, _ORIGIN_ANCHOR) as session:
        if not session.state.reconciled:
            session.reconcile(ReconciliationSnapshot(_IDENTITY, _ZERO))
        intent_id = session.reserve_entry(Decimal("10.00"))
        session.prepare_invocation(intent_id)
        session.bind_provider_order(intent_id, _ENTRY_ORDER_ID)
        session.reconcile(
            ReconciliationSnapshot(
                _IDENTITY,
                _OWNED,
                (
                    OrderObservation(
                        local_intent_id=intent_id,
                        provider_order_id=_ENTRY_ORDER_ID,
                        status=OrderStatus.FILLED,
                        cumulative_quantity=_OWNED,
                        cumulative_notional=Decimal("10.00"),
                        working_remainder=_ZERO,
                    ),
                ),
            )
        )


def _sell_proposal(state) -> ExactOwnedSellProposal:
    entry = state.entry
    assert entry is not None and entry.provider_order_id is not None
    identity = ReadinessIdentity(
        source_head=_IDENTITY.source_head,
        source_tree=_IDENTITY.source_tree,
        config_digest=_IDENTITY.config_digest,
        account_fingerprint=_IDENTITY.account_fingerprint,
        target_session=_SESSION.target_session,
    )
    ownership = OwnershipSnapshot(
        account_fingerprint=_IDENTITY.account_fingerprint,
        symbol="SPY",
        strategy="BASE_MA35_50_V1",
        source_head=_IDENTITY.source_head,
        source_tree=_IDENTITY.source_tree,
        config_digest=_IDENTITY.config_digest,
        binding_digest=_IDENTITY.binding_digest,
        lifecycle_id=_IDENTITY.lifecycle_id,
        target_session=_SESSION.target_session,
        lifecycle=Lifecycle.RUNNING,
        effect_disposition=EffectDisposition.CONFIRMED,
        baseline_quantity=_ZERO,
        cumulative_bought=state.owned_quantity,
        cumulative_sold=_ZERO,
        cumulative_entry_filled_dollars=entry.cumulative_notional,
        entry_reserved_dollars=entry.requested_dollars,
        working_remainder=_ZERO,
        entries_used=1,
        exits_used=0,
        entry_local_intent_id=entry.intent_id,
        entry_provider_order_id=entry.provider_order_id,
    )
    position = ReconciledOwnedPosition(
        identity=identity,
        ownership_snapshot=ownership,
        broker_position_quantity=state.owned_quantity,
        broker_sellable_quantity=state.owned_quantity,
        working_order_count=0,
        unresolved_order_count=0,
        evidence_sha256=_sha("position-evidence"),
    )
    terminal = TerminalEntryEvidence(
        local_intent_id=entry.intent_id,
        provider_order_id=entry.provider_order_id,
        outcome=EntryTerminalOutcome.FILLED,
        requested_usd_cents=1000,
        reserved_usd_cents=1000,
        confirmed_filled_quantity=entry.cumulative_quantity,
        confirmed_filled_notional=entry.cumulative_notional,
    )
    arguments = SellOrderArguments(
        side=SellSide.SELL,
        symbol="SPY",
        order_type=SellOrderType.MARKET,
        session=SellSession.REGULAR_HOURS,
        time_in_force=SellTimeInForce.DAY,
        quantity=state.owned_quantity,
        context=SellOrderContext(
            identity=identity,
            binding_digest=_IDENTITY.binding_digest,
            lifecycle_id=_IDENTITY.lifecycle_id,
            entry_local_intent_id=entry.intent_id,
            entry_provider_order_id=entry.provider_order_id,
            exact_owned_remainder=state.owned_quantity,
            broker_position_quantity=state.owned_quantity,
            broker_sellable_quantity=state.owned_quantity,
            terminal_entry_outcome=EntryTerminalOutcome.FILLED,
            reserved_usd_cents=1000,
            confirmed_entry_filled_quantity=entry.cumulative_quantity,
            confirmed_entry_filled_notional=entry.cumulative_notional,
        ),
    )
    return ExactOwnedSellProposal(
        position=position,
        terminal_entry=terminal,
        review_arguments=arguments,
        placement_arguments=arguments,
    )


def _entry_observation(state) -> tuple[OrderObservation, ...]:
    order = state.entry
    if order is None or order.provider_order_id is None:
        return ()
    if order.status not in {
        IntentStatus.FILLED,
        IntentStatus.CANCELED,
        IntentStatus.REJECTED,
    }:
        return ()
    return (
        OrderObservation(
            local_intent_id=order.intent_id,
            provider_order_id=order.provider_order_id,
            status=OrderStatus(order.status.value),
            cumulative_quantity=order.cumulative_quantity,
            cumulative_notional=order.cumulative_notional,
            working_remainder=order.working_remainder,
        ),
    )


def _plan_for_state(
    session: L43StateSession,
    *,
    requested_risk: Decimal | None = None,
    observed_at: datetime = _NOW,
    observation_salt: str = "stable",
) -> L43PreEffectPlan:
    state = session.state
    snapshot = session.snapshot()
    if state.entry is None:
        kind = L43PlanKind.ENTRY
        proposal = None
        signal = D34SignalFacts(
            decision=SignalDecision.BUY,
            inputs_digest=_sha("buy-signal"),
        )
        recovery = RecoveryFacts(
            reconciled=True,
            unresolved_effects=False,
            terminal_entry=False,
            exact_owned_remainder=_ZERO,
            evidence_digest=_sha(f"recovery:{snapshot.journal_sha256}"),
        )
        reconciliation = ReconciliationSnapshot(_IDENTITY, _ZERO)
    else:
        kind = L43PlanKind.EXACT_OWNED_SELL_REVIEW
        proposal = _sell_proposal(state)
        signal = D34SignalFacts(
            decision=SignalDecision.SELL,
            inputs_digest=_sha("sell-signal"),
        )
        recovery = RecoveryFacts(
            reconciled=True,
            unresolved_effects=False,
            terminal_entry=True,
            exact_owned_remainder=state.owned_quantity,
            evidence_digest=_sha(f"recovery:{snapshot.journal_sha256}"),
        )
        reconciliation = ReconciliationSnapshot(
            _IDENTITY,
            state.owned_quantity,
            _entry_observation(state),
        )
    return L43PreEffectPlan(
        kind=kind,
        current_source=_CURRENT,
        provenance=_PROVENANCE,
        continuity=_CONTINUITY,
        state_last_sequence=snapshot.last_sequence,
        state_tail_sha256=snapshot.journal_sha256,
        state_journal_sha256=snapshot.journal_sha256,
        reconciliation_snapshot=reconciliation,
        account_fingerprint=_IDENTITY.account_fingerprint,
        positions_digest=_sha("positions"),
        relevant_orders_digest=_sha("orders"),
        order_scope_digest=_sha("scope"),
        session=_SESSION,
        signal=signal,
        recovery=recovery,
        observation_as_of=observed_at,
        signal_observation_digest=_sha(f"signal-observation:{observation_salt}"),
        positions_observation_digest=_sha(f"positions-observation:{observation_salt}"),
        orders_observation_digest=_sha(f"orders-observation:{observation_salt}"),
        order_scope_evidence_digest=_sha(f"scope-observation:{observation_salt}"),
        requested_entry_risk=(
            (Decimal("10.00") if requested_risk is None else requested_risk)
            if kind is L43PlanKind.ENTRY
            else None
        ),
        sell_proposal=proposal,
    )


def _pre_effect(plan: L43PreEffectPlan) -> L43PreEffectResult:
    outcome = (
        L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
        if plan.kind is L43PlanKind.ENTRY
        else L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW
    )
    raw = b"{}"
    return L43PreEffectResult(
        outcome=outcome,
        blockers=(),
        evidence_sha256=hashlib.sha256(raw).hexdigest(),
        evidence_json=raw,
        plan=plan,
        observed_at=plan.observation_as_of,
        robinhood_read_count=3,
        robinhood_page_count=2,
        alpaca_provider_call_count=1,
        credential_read_count=0,
    )


def _blocked_result() -> L43PreEffectResult:
    raw = b'{"outcome":"BLOCKED"}'
    return L43PreEffectResult(
        outcome=L43PreEffectOutcome.BLOCKED,
        blockers=(L43PreEffectBlocker.STATE_UNRESOLVED,),
        evidence_sha256=hashlib.sha256(raw).hexdigest(),
        evidence_json=raw,
        plan=None,
        observed_at=_NOW,
        robinhood_read_count=0,
        robinhood_page_count=0,
        alpaca_provider_call_count=0,
        credential_read_count=0,
    )


def _schemas():
    tools = []
    for name in ("review_equity_order", "place_equity_order"):
        properties = {
            key: {"type": "string"}
            for key in (
                "account_number",
                "symbol",
                "side",
                "type",
                "market_hours",
                "time_in_force",
                "quantity",
                "dollar_amount",
            )
        }
        properties["quantity"] = {
            "description": "synthetic schema description",
            "type": "string",
        }
        properties["dollar_amount"] = {
            "description": "synthetic schema description",
            "type": "string",
        }
        if name == "place_equity_order":
            properties["ref_id"] = {"type": "string"}
        tools.append(
            SimpleNamespace(
                name=name,
                input_schema={
                    "properties": properties,
                    "required": ["account_number", "symbol", "side", "type"],
                    "additionalProperties": False,
                },
            )
        )
    return tools


class _FakeMcpSession:
    def __init__(
        self,
        path: Path,
        *,
        provider_order_id: str = _ENTRY_ORDER_ID,
        cancel_call: bool = False,
        close_error: bool = False,
    ) -> None:
        self.path = path
        self.provider_order_id = provider_order_id
        self.cancel_call = cancel_call
        self.close_error = close_error
        self.list_calls = 0
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.events: list[tuple[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        if self.close_error and self.calls:
            raise RuntimeError("synthetic prepared session close failure")
        return None

    async def list_tools(self, *, cursor=None):
        self.list_calls += 1
        return SimpleNamespace(tools=_schemas(), next_cursor=None)

    async def call_tool(self, name, arguments):
        state = DurableStateStore.open(self.path, _IDENTITY).state
        self.calls.append((name, dict(arguments)))
        if name == "review_equity_order":
            assert state.sell_review is not None
            assert state.sell_review.status.value == "ATTEMPTED"
            self.events.append(("SELL_REVIEW_STARTED", state.sell_review.status))
            return SimpleNamespace(is_error=False, structured_content=None)
        target = state.exit if state.exit is not None else state.entry
        assert target is not None
        assert target.status is IntentStatus.MAY_HAVE_OCCURRED
        self.events.append(("MAY_HAVE_OCCURRED", target.kind))
        self.events.append(("provider_call", name))
        if self.cancel_call:
            raise asyncio.CancelledError
        return SimpleNamespace(
            is_error=False,
            structured_content={"data": {"order": {"id": self.provider_order_id}}},
        )


class _Authorizer:
    def __init__(self, *, deny: set[L43EffectStage] | None = None) -> None:
        self.deny = set() if deny is None else set(deny)
        self.requests: list[L43AuthorizationRequest] = []
        self.grants: list[L43StageAuthorization] = []

    def authorize(self, request: L43AuthorizationRequest):
        self.requests.append(request)
        if request.stage in self.deny:
            return None
        authority = hashlib.sha256(
            f"{request.request_sha256}:{len(self.requests)}".encode("ascii")
        ).hexdigest()
        grant = L43StageAuthorization(request, authority)
        self.grants.append(grant)
        return grant


class _Reconciler:
    def __init__(
        self,
        *,
        entry_status: OrderStatus = OrderStatus.FILLED,
        entry_quantity: Decimal = _OWNED,
        exit_status: OrderStatus = OrderStatus.FILLED,
        exit_quantity: Decimal | None = None,
        fail: bool = False,
        cancel: bool = False,
    ) -> None:
        self.entry_status = entry_status
        self.entry_quantity = entry_quantity
        self.exit_status = exit_status
        self.exit_quantity = exit_quantity
        self.fail = fail
        self.cancel = cancel
        self.calls = 0

    async def reconcile(
        self,
        *,
        stage,
        plan,
        intent_id,
        provider_order_id,
        known_state,
    ):
        self.calls += 1
        if self.cancel:
            raise asyncio.CancelledError
        if self.fail:
            raise RuntimeError("synthetic reconcile outage")
        rows: list[OrderObservation] = []
        for order in (known_state.entry, known_state.exit):
            if order is None or order.provider_order_id is None:
                continue
            if order.kind is IntentKind.ENTRY:
                status = self.entry_status
                quantity = self.entry_quantity
                notional = quantity * Decimal("20.00")
                remainder = (
                    _OWNED - quantity
                    if status in {OrderStatus.WORKING, OrderStatus.PARTIAL}
                    else _ZERO
                )
            elif self.exit_quantity is None:
                status = self.exit_status
                quantity = order.requested_quantity or _ZERO
                notional = Decimal("250.00") if quantity > _ZERO else _ZERO
                remainder = _ZERO
            else:
                status = self.exit_status
                quantity = self.exit_quantity
                notional = Decimal("100.00") if quantity > _ZERO else _ZERO
                remainder = (
                    _ZERO
                    if status
                    in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
                    else (order.requested_quantity or _ZERO) - quantity
                )
            rows.append(
                OrderObservation(
                    local_intent_id=order.intent_id,
                    provider_order_id=order.provider_order_id,
                    status=status,
                    cumulative_quantity=quantity,
                    cumulative_notional=notional,
                    working_remainder=remainder,
                )
            )
        if stage is L43EffectStage.ENTRY_PLACEMENT:
            position = self.entry_quantity
        else:
            quantity = _OWNED if self.exit_quantity is None else self.exit_quantity
            position = _OWNED - quantity
        return L43PostEffectFacts(
            account_fingerprint=plan.account_fingerprint,
            snapshot=ReconciliationSnapshot(_IDENTITY, position, tuple(rows)),
            positions_digest=_sha("post-positions"),
            orders_digest=_sha("post-orders"),
            order_scope_digest=_sha("post-scope"),
            evidence_sha256=_sha(f"post-facts:{stage.value}:{self.calls}"),
            all_relevant_orders_proven=True,
        )


def _operator(
    path: Path,
    mcp: _FakeMcpSession,
    *,
    authorizer: _Authorizer | None = None,
    reconciler: _Reconciler | None = None,
    review_caller=None,
    reobserver=None,
) -> L43EffectOperator:
    authorizer = _Authorizer() if authorizer is None else authorizer
    reconciler = _Reconciler() if reconciler is None else reconciler
    if reobserver is None:

        def reobserver(session, *, requested_entry_risk=None):
            state = session.state
            if state.entry is not None and (
                state.entry.status
                not in {
                    IntentStatus.FILLED,
                    IntentStatus.CANCELED,
                    IntentStatus.REJECTED,
                }
                or state.exit is not None
                or state.manual_close_required
            ):
                return _blocked_result()
            plan = _plan_for_state(
                session,
                requested_risk=requested_entry_risk,
            )
            return _pre_effect(plan)

    return L43EffectOperator(
        session_factory=lambda: L43StateSession.open_existing(path, _ORIGIN_ANCHOR),
        transport=L43RobinhoodTransport.for_test(lambda: mcp),
        authorizer=authorizer,
        reobserver=reobserver,
        reconciler=reconciler,
        review_caller=review_caller,
    )


def _input_result(path: Path, *, risk: Decimal = Decimal("10.00")):
    with L43StateSession.open_existing(path, _ORIGIN_ANCHOR) as session:
        return _pre_effect(_plan_for_state(session, requested_risk=risk))


def _affirmative_review(proposal: ExactOwnedSellProposal) -> NormalizedSellReview:
    eligibility_sha = proposal.proposal_sha256()
    return NormalizedSellReview(
        contract_id=EXACT_SELL_REVIEW_CONTRACT_ID,
        review_id="fake-review-1",
        evidence_sha256=_sha("normalized-review-evidence"),
        proposal_sha256=eligibility_sha,
        identity=proposal.position.identity,
        reviewed_arguments=proposal.review_arguments,
        outcome=NormalizedReviewOutcome.AFFIRMATIVE,
        semantics=NormalizedReviewSemantics.NONPLACING_PREVIEW,
        warnings=(),
        unknown_fields=(),
        rejection_code=None,
        provider_order_id=None,
    )


def test_entry_persists_may_before_one_fake_call_and_records_confirmed_fills(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer()
    reconciler = _Reconciler()
    operator = _operator(path, mcp, authorizer=authorizer, reconciler=reconciler)

    result = asyncio.run(
        operator.place_entry(_input_result(path), account_number="account-one")
    )

    assert result.outcome is L43EffectOutcome.ENTRY_RECONCILED
    assert result.confirmed_filled_quantity == _OWNED
    assert len(mcp.calls) == 1
    assert mcp.events[0][0] == "MAY_HAVE_OCCURRED"
    assert mcp.events[1][0] == "provider_call"
    assert authorizer.requests[0].stage is L43EffectStage.ENTRY_PLACEMENT
    stored = DurableStateStore.open(path, _IDENTITY).state
    assert stored.entry is not None
    assert stored.entry.status is IntentStatus.FILLED
    assert stored.entry.cumulative_quantity == _OWNED
    assert stored.entry.provider_order_id == _ENTRY_ORDER_ID
    assert stored.entry.requested_dollars == Decimal("10.00")


def test_account_fingerprint_mismatch_stops_before_any_provider_discovery_or_call(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer()
    operator = _operator(path, mcp, authorizer=authorizer)

    result = asyncio.run(
        operator.place_entry(_input_result(path), account_number="account-other")
    )

    assert result.reason_code == "ACCOUNT_FINGERPRINT_MISMATCH"
    assert mcp.list_calls == 0
    assert mcp.calls == []
    assert authorizer.requests == []
    assert DurableStateStore.open(path, _IDENTITY).state.entry is None


def test_missing_exact_plan_authorization_does_not_reserve_or_place(tmp_path: Path):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer(deny={L43EffectStage.ENTRY_PLACEMENT})
    operator = _operator(path, mcp, authorizer=authorizer)

    result = asyncio.run(
        operator.place_entry(_input_result(path), account_number="account-one")
    )

    assert result.reason_code == "ENTRY_AUTHORIZATION_MISSING"
    assert DurableStateStore.open(path, _IDENTITY).state.entry is None
    assert mcp.calls == []


def test_genesis_reconciliation_reobserves_with_advanced_time_before_authorizing(
    tmp_path: Path,
):
    path = _state_path(tmp_path, reconciled=False)
    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer()
    observations = 0

    def reobserver(session, *, requested_entry_risk=None):
        nonlocal observations
        observations += 1
        plan = _plan_for_state(
            session,
            requested_risk=requested_entry_risk,
            observed_at=_NOW + timedelta(seconds=observations),
            observation_salt=f"fresh-{observations}",
        )
        return _pre_effect(plan)

    # The submitted plan uses the same semantic facts and original journal tail.
    with L43StateSession.open_existing(path, _ORIGIN_ANCHOR) as session:
        submitted = _pre_effect(_plan_for_state(session))
    operator = _operator(
        path,
        mcp,
        authorizer=authorizer,
        reobserver=reobserver,
    )

    result = asyncio.run(operator.place_entry(submitted, account_number="account-one"))

    assert result.outcome is L43EffectOutcome.ENTRY_RECONCILED
    assert observations == 2
    assert authorizer.requests[0].state_last_sequence == 1
    assert authorizer.requests[0].plan_binding_sha256 != (submitted.plan.binding_sha256)
    assert len(mcp.calls) == 1


def test_prepare_invocation_failure_consumes_reservation_without_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)

    def fail_before_may(self, intent_id):
        raise OSError("synthetic MAY persistence failure")

    monkeypatch.setattr(L43StateSession, "prepare_invocation", fail_before_may)
    operator = _operator(path, mcp)

    result = asyncio.run(
        operator.place_entry(_input_result(path), account_number="account-one")
    )

    state = DurableStateStore.open(path, _IDENTITY).state
    assert result.reason_code == "ENTRY_MAY_PERSIST_FAILED"
    assert state.entry is not None
    assert state.entry.status is IntentStatus.RESERVED
    assert mcp.calls == []


def test_post_may_reconciliation_failure_is_consumed_unknown_and_not_retried(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    operator = _operator(path, mcp, reconciler=_Reconciler(fail=True))
    submitted = _input_result(path)

    first = asyncio.run(operator.place_entry(submitted, account_number="account-one"))
    second = asyncio.run(operator.place_entry(submitted, account_number="account-one"))

    state = DurableStateStore.open(path, _IDENTITY).state
    assert first.outcome is L43EffectOutcome.EFFECT_UNKNOWN
    assert second.outcome is L43EffectOutcome.BLOCKED
    assert state.entry is not None and state.entry.status is IntentStatus.UNKNOWN
    assert len(mcp.calls) == 1


def test_partial_entry_consumes_full_budget_owns_only_confirmed_fill_and_cannot_retry(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    reconciler = _Reconciler(
        entry_status=OrderStatus.PARTIAL,
        entry_quantity=Decimal("0.2"),
    )
    operator = _operator(path, mcp, reconciler=reconciler)
    submitted = _input_result(path)

    first = asyncio.run(operator.place_entry(submitted, account_number="account-one"))

    with L43StateSession.open_existing(path, _ORIGIN_ANCHOR) as session:
        state_after_effect = session.state
    assert first.outcome is L43EffectOutcome.ENTRY_PENDING
    assert first.confirmed_filled_quantity == Decimal("0.2")
    assert state_after_effect.entry is not None
    assert state_after_effect.entry.status is IntentStatus.PARTIAL
    assert state_after_effect.entry.requested_dollars == Decimal("10.00")
    assert state_after_effect.entry.cumulative_quantity == Decimal("0.2")
    assert state_after_effect.owned_quantity == Decimal("0.2")
    assert len(mcp.calls) == 1

    # A newly constructed operator simulates restart: the old reservation cannot
    # be reused, so the full nonreplenishing $10 entry budget stays consumed.
    restarted_mcp = _FakeMcpSession(path)
    restarted = _operator(path, restarted_mcp)
    second = asyncio.run(restarted.place_entry(submitted, account_number="account-one"))

    final_state = DurableStateStore.open(path, _IDENTITY).state
    assert second.outcome is L43EffectOutcome.BLOCKED
    assert final_state.entry == state_after_effect.entry
    assert final_state.owned_quantity == Decimal("0.2")
    assert restarted_mcp.calls == []


def test_cancelled_entry_call_persists_unknown_before_propagating_cancellation(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path, cancel_call=True)
    operator = _operator(path, mcp)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            operator.place_entry(_input_result(path), account_number="account-one")
        )

    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.entry is not None and state.entry.status is IntentStatus.UNKNOWN
    assert len(mcp.calls) == 1


def test_cancellation_after_provider_id_binding_persists_unknown_with_bound_id(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path)
    operator = _operator(path, mcp, reconciler=_Reconciler(cancel=True))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            operator.place_entry(_input_result(path), account_number="account-one")
        )

    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.entry is not None and state.entry.status is IntentStatus.UNKNOWN
    assert state.entry.provider_order_id == _ENTRY_ORDER_ID
    assert len(mcp.calls) == 1


def test_prepared_session_close_failure_preserves_completed_effect_result(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    mcp = _FakeMcpSession(path, close_error=True)
    operator = _operator(path, mcp)

    result = asyncio.run(
        operator.place_entry(_input_result(path), account_number="account-one")
    )

    state = DurableStateStore.open(path, _IDENTITY).state
    assert result.outcome is L43EffectOutcome.ENTRY_RECONCILED
    assert result.reason_code == "ENTRY_FACTUALLY_RECONCILED"
    assert state.entry is not None and state.entry.status is IntentStatus.FILLED
    assert len(mcp.calls) == 1


def test_review_stage_is_durable_nonplacing_and_sell_requires_new_grant(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer(deny={L43EffectStage.SELL_PLACEMENT})
    reviewer_calls: list[object] = []

    async def reviewer(*, account_number, proposal):
        reviewer_calls.append((account_number, proposal))
        return _affirmative_review(proposal)

    operator = _operator(
        path,
        mcp,
        authorizer=authorizer,
        review_caller=reviewer,
    )
    review_result = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )
    assert review_result.outcome is L43EffectOutcome.REVIEW_ACCEPTED
    assert review_result.accepted_review is not None
    assert len(reviewer_calls) == 1
    assert mcp.calls == []
    assert authorizer.requests[0].stage is L43EffectStage.SELL_REVIEW

    sell_plan = _input_result(path)
    result = asyncio.run(
        operator.place_sell(
            sell_plan,
            review_result.accepted_review,
            account_number="account-one",
        )
    )

    assert result.reason_code == "SELL_PLACEMENT_AUTHORIZATION_MISSING"
    assert [item.stage for item in authorizer.requests] == [
        L43EffectStage.SELL_REVIEW,
        L43EffectStage.SELL_PLACEMENT,
    ]
    assert mcp.calls == []
    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.sell_review is not None
    assert state.sell_review.status.value == "ACCEPTED"
    assert state.exit is None


def test_positive_fake_sell_uses_reviewed_quantity_and_reconciles_exact_exit(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path, provider_order_id=_EXIT_ORDER_ID)
    authorizer = _Authorizer()

    async def reviewer(*, account_number, proposal):
        assert account_number == "account-one"
        return _affirmative_review(proposal)

    operator = _operator(path, mcp, authorizer=authorizer, review_caller=reviewer)
    review_result = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )
    assert review_result.accepted_review is not None
    sell_plan = _input_result(path)

    result = asyncio.run(
        operator.place_sell(
            sell_plan,
            review_result.accepted_review,
            account_number="account-one",
        )
    )

    assert result.outcome is L43EffectOutcome.SELL_RECONCILED
    assert result.confirmed_filled_quantity == _OWNED
    assert len(mcp.calls) == 1
    assert mcp.calls[0][1]["quantity"] == "0.5"
    assert "dollar_amount" not in mcp.calls[0][1]
    state = DurableStateStore.open(path, _IDENTITY).state
    assert state.exit is not None
    assert state.exit.status is IntentStatus.FILLED
    assert state.exit.requested_quantity == _OWNED
    assert state.exit.authority_sha256 == authorizer.grants[1].authority_sha256
    assert state.owned_quantity == _ZERO
    assert not state.manual_close_required


def test_partial_sell_records_confirmed_fill_and_sticks_manual_close_no_replacement(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path, provider_order_id=_EXIT_ORDER_ID)
    authorizer = _Authorizer()

    async def reviewer(*, account_number, proposal):
        return _affirmative_review(proposal)

    operator = _operator(
        path,
        mcp,
        authorizer=authorizer,
        review_caller=reviewer,
        reconciler=_Reconciler(
            exit_status=OrderStatus.PARTIAL,
            exit_quantity=Decimal("0.2"),
        ),
    )
    reviewed = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )
    assert reviewed.accepted_review is not None
    sell_plan = _input_result(path)
    first = asyncio.run(
        operator.place_sell(
            sell_plan,
            reviewed.accepted_review,
            account_number="account-one",
        )
    )
    second = asyncio.run(
        operator.place_sell(
            sell_plan,
            reviewed.accepted_review,
            account_number="account-one",
        )
    )

    state = DurableStateStore.open(path, _IDENTITY).state
    assert first.outcome is L43EffectOutcome.MANUAL_CLOSE_REQUIRED
    assert state.exit is not None and state.exit.status is IntentStatus.PARTIAL
    assert state.exit.cumulative_quantity == Decimal("0.2")
    assert state.owned_quantity == Decimal("0.3")
    assert state.manual_close is not None
    assert state.manual_close.trigger is ManualCloseTrigger.SELL_PARTIAL
    assert state.manual_close.exact_residual_quantity == Decimal("0.3")
    assert second.outcome is L43EffectOutcome.BLOCKED
    assert len(mcp.calls) == 1


def test_review_account_mismatch_prevents_review_and_placement_discovery(
    tmp_path: Path,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)
    authorizer = _Authorizer()
    reviewer_calls: list[object] = []

    async def reviewer(**kwargs):
        reviewer_calls.append(kwargs)
        return _affirmative_review(kwargs["proposal"])

    operator = _operator(path, mcp, authorizer=authorizer, review_caller=reviewer)

    result = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-other")
    )

    assert result.reason_code == "ACCOUNT_FINGERPRINT_MISMATCH"
    assert reviewer_calls == []
    assert authorizer.requests == []
    assert mcp.list_calls == 0
    assert mcp.calls == []


@pytest.mark.parametrize(
    ("case", "expected_trigger"),
    [
        ("rejected", ManualCloseTrigger.SELL_REVIEW_REJECTED),
        ("malformed", ManualCloseTrigger.SELL_REVIEW_MALFORMED),
        ("warning", ManualCloseTrigger.SELL_REVIEW_WARNING),
        ("unknown", ManualCloseTrigger.SELL_REVIEW_UNKNOWN),
    ],
)
def test_unaccepted_review_is_sticky_manual_close_and_never_places(
    tmp_path: Path,
    case: str,
    expected_trigger: ManualCloseTrigger,
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)

    async def reviewer(*, account_number, proposal):
        review = _affirmative_review(proposal)
        if case == "rejected":
            return replace(
                review,
                outcome=NormalizedReviewOutcome.REJECTED,
                rejection_code="REJECTED",
            )
        if case == "malformed":
            return object()
        if case == "warning":
            return replace(review, warnings=("warning",))
        return replace(
            review,
            outcome=NormalizedReviewOutcome.UNKNOWN,
            semantics=NormalizedReviewSemantics.UNKNOWN,
        )

    operator = _operator(path, mcp, review_caller=reviewer)

    result = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )

    state = DurableStateStore.open(path, _IDENTITY).state
    assert result.outcome is L43EffectOutcome.MANUAL_CLOSE_REQUIRED
    assert state.manual_close is not None
    assert state.manual_close.trigger is expected_trigger
    assert mcp.calls == []
    assert dict(operator._transport.call_counts)["place_equity_order"] == 0
    assert dict(operator._transport.call_counts)["place_equity_order"] == 0


@pytest.mark.parametrize("status", [OrderStatus.REJECTED, OrderStatus.CANCELED])
def test_rejected_or_canceled_sell_is_sticky_manual_close(
    tmp_path: Path, status: OrderStatus
):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path, provider_order_id=_EXIT_ORDER_ID)

    async def reviewer(*, account_number, proposal):
        return _affirmative_review(proposal)

    operator = _operator(
        path,
        mcp,
        review_caller=reviewer,
        reconciler=_Reconciler(exit_status=status, exit_quantity=Decimal("0")),
    )
    reviewed = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )
    sell_plan = _input_result(path)
    result = asyncio.run(
        operator.place_sell(
            sell_plan,
            reviewed.accepted_review,
            account_number="account-one",
        )
    )

    state = DurableStateStore.open(path, _IDENTITY).state
    expected = (
        ManualCloseTrigger.SELL_REJECTED
        if status is OrderStatus.REJECTED
        else ManualCloseTrigger.SELL_CANCELED
    )
    assert result.outcome is L43EffectOutcome.MANUAL_CLOSE_REQUIRED
    assert state.manual_close is not None and state.manual_close.trigger is expected
    assert state.owned_quantity == _OWNED
    assert len(mcp.calls) == 1


def test_sell_account_mismatch_stops_before_prepared_discovery(tmp_path: Path):
    path = _state_path(tmp_path)
    _owned_state(path)
    mcp = _FakeMcpSession(path)

    async def reviewer(*, account_number, proposal):
        return _affirmative_review(proposal)

    operator = _operator(path, mcp, review_caller=reviewer)
    reviewed = asyncio.run(
        operator.review_sell(_input_result(path), account_number="account-one")
    )
    mcp.list_calls = 0
    before_auth_count = len(operator._authorizer.requests)

    result = asyncio.run(
        operator.place_sell(
            _input_result(path),
            reviewed.accepted_review,
            account_number="account-other",
        )
    )

    assert result.reason_code == "ACCOUNT_FINGERPRINT_MISMATCH"
    assert mcp.list_calls == 0
    assert mcp.calls == []
    assert len(operator._authorizer.requests) == before_auth_count
