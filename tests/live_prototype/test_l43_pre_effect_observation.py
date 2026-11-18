from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.desktop_paper.robinhood_read import AgenticAccountIdentity
from trading_bot.live_prototype import l43_pre_effect_observation as observer
from trading_bot.live_prototype import l43_qualification_preflight as qualification
from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    RuntimeSignalReason,
    RuntimeSignalSnapshot,
)
from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.durable_state import (
    DurableStateStore,
    IntentKind,
    IntentStatus,
    L43OriginAnchor,
    ManualCloseBasis,
    ManualCloseRequired,
    OrderObservation,
    OrderState,
    OrderStatus,
    ReconciliationSnapshot,
    RuntimeIdentity,
)
from trading_bot.live_prototype.l43_production_owner import (
    JournalReplayFacts,
    L43ProductionOwner,
    L43SourceIdentity,
    Q62JournalOrigin,
    SourceAuthorityEvidence,
)
from trading_bot.live_prototype.l43_provider_contracts import L43AccountIdentity
from trading_bot.live_prototype.l43_state import (
    L43StateSession,
    read_l43_state_snapshot,
)
from trading_bot.live_prototype.tiny_live_policy import ManualCloseTrigger
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.l43_read_adapter import (
    RobinhoodL43PreEffectReadAdapter,
)

_ACCOUNT_NUMBER = "912345678901"
_ACCOUNT = AgenticAccountIdentity(_ACCOUNT_NUMBER, 1)
_NOW = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
_ORDER_ID = "entry-provider-order-147"
_EXECUTION_ID = "entry-execution-147"
_SOURCE = L43SourceIdentity(source_head="8" * 40, source_tree="9" * 40)
_SESSIONS = NYSEPublishedRegularSessionAuthority()


class _Authority:
    def __init__(self, *, prospective_passed: bool = True) -> None:
        self.prospective_passed = prospective_passed

    def verify(self, origin, current):
        return SourceAuthorityEvidence(
            origin_head=origin.runtime_identity.source_head,
            origin_tree=origin.runtime_identity.source_tree,
            candidate_head=current.source_head,
            candidate_tree=current.source_tree,
            strict_descendant=True,
            feature_passed=True,
            prospective_develop_passed=self.prospective_passed,
            evidence_sha256="a" * 64,
        )


class _JournalReader:
    def replay(self, origin):
        return JournalReplayFacts(
            runtime_identity=origin.runtime_identity,
            journal_sha256=origin.journal_sha256,
            initialization_event_sha256=origin.initialization_event_sha256,
            consumed_observation_sha256=origin.consumed_observation_sha256,
            initialization_sequence=0,
            tail_sequence=0,
            tail_sha256=origin.initialization_event_sha256,
        )


class _ScopeVerifier:
    def __init__(self, account_fingerprint: str) -> None:
        self.account_fingerprint = account_fingerprint
        self.calls: list[tuple[str, int, int, bool]] = []
        self.order_arguments: list[dict[str, object]] = []

    def verify_account_wide_spy_orders(
        self,
        *,
        account_fingerprint: str,
        query_sha256: str,
        order_arguments: Mapping[str, object],
        pages_read: int,
        row_count: int,
        exhausted: bool,
    ):
        self.calls.append((query_sha256, pages_read, row_count, exhausted))
        self.order_arguments.append(dict(order_arguments))
        if account_fingerprint != self.account_fingerprint:
            return None
        return observer.L43OrderScopeProof(
            scope=observer.L43OrderScope.ACCOUNT_WIDE_ALL_AGENTS,
            query_sha256=query_sha256,
            pages_read=pages_read,
            row_count=row_count,
            exhausted=exhausted,
            evidence_sha256="b" * 64,
        )


class _ReadBoundary:
    def __init__(
        self,
        *,
        positions: list[dict[str, str]],
        orders: list[dict[str, object]],
        account_number: str = _ACCOUNT_NUMBER,
        order_page_cursors: tuple[str | None, ...] | None = None,
    ) -> None:
        self.positions = positions
        self.orders = orders
        self.account_number = account_number
        self.order_page_cursors = order_page_cursors
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_accounts(self):
        self.calls.append(("get_accounts", {}))
        return {
            "data": {
                "accounts": [
                    {
                        "account_number": self.account_number,
                        "agentic_allowed": True,
                    }
                ]
            }
        }

    def get_equity_positions(self, arguments):
        self.calls.append(("get_equity_positions", dict(arguments)))
        return {"data": {"positions": self.positions, "next": None}}

    def get_equity_orders(self, arguments):
        self.calls.append(("get_equity_orders", dict(arguments)))
        if self.order_page_cursors is None:
            cursor = None
        else:
            order_call_count = sum(
                name == "get_equity_orders" for name, _ in self.calls
            )
            cursor = self.order_page_cursors[order_call_count - 1]
        return {"data": {"orders": self.orders, "next": cursor}}


class _ScopedReadBoundary(_ReadBoundary):
    def __init__(self, *, scope_events: list[str], malformed_orders: bool, **kwargs):
        super().__init__(**kwargs)
        self._scope_events = scope_events
        self._scope_active = False
        self._malformed_orders = malformed_orders

    def __enter__(self):
        self._scope_events.append("open")
        self._scope_active = True
        return self

    def __exit__(self, *_args: object) -> None:
        self._scope_events.append("close")
        self._scope_active = False

    def _record(self, method: str) -> None:
        assert self._scope_active
        self._scope_events.append(method)

    def get_accounts(self):
        self._record("get_accounts")
        return super().get_accounts()

    def get_equity_positions(self, arguments):
        self._record("get_equity_positions")
        return super().get_equity_positions(arguments)

    def get_equity_orders(self, arguments):
        self._record("get_equity_orders")
        if self._malformed_orders:
            return {"data": {"orders": [], "next": False}}
        return super().get_equity_orders(arguments)


class _SignalProvider:
    def __init__(
        self,
        decision: SignalDecision,
        *,
        observation_offset: timedelta = timedelta(0),
    ) -> None:
        self.decision = decision
        self.observation_offset = observation_offset
        self.calls = 0

    def snapshot(self, as_of: datetime) -> RuntimeSignalSnapshot:
        self.calls += 1
        snapshot_as_of = as_of - self.observation_offset
        selected = observer.select_latest_completed_sessions(
            snapshot_as_of, authority=_SESSIONS
        )
        schedule = _SESSIONS.schedule_for(selected[-1])
        assert schedule is not None
        closes = _closes_for(self.decision)
        inputs = CompletedSignalInputs(
            symbol="SPY",
            selected_sessions=selected,
            sessions=selected,
            closes=closes,
            price_basis="ALPACA_ALL_ADJUSTED_PRICE_V1",
            source_digest="c" * 64,
            as_of=snapshot_as_of,
            cutoff=schedule.closes_at,
        )
        return RuntimeSignalSnapshot(
            status="READY",
            reason=RuntimeSignalReason.READY,
            observation_as_of=snapshot_as_of,
            selected_sessions=selected,
            display_inputs=inputs,
            stale=False,
            refreshed=True,
            credential_read_count=1,
            provider_call_count=1,
        )


def _closes_for(decision: SignalDecision) -> tuple[Decimal, ...]:
    if decision is SignalDecision.BUY:
        return tuple(Decimal(value) for value in range(1, 61))
    if decision is SignalDecision.SELL:
        return tuple(Decimal(value) for value in range(100, 40, -1))
    return (Decimal("100"),) * 60


def _origin() -> tuple[Q62JournalOrigin, L43OriginAnchor]:
    runtime = RuntimeIdentity(
        account_fingerprint=_ACCOUNT.fingerprint,
        source_head="1" * 40,
        source_tree="2" * 40,
        config_digest=observer.CONFIGURATION_SHA256,
        binding_digest=observer.BINDING_SHA256,
        lifecycle_id=str(UUID("00000000-0000-0000-0000-000000000147")),
    )
    q62 = Q62JournalOrigin(
        runtime_identity=runtime,
        journal_label="arch147-q62-live-state-v1",
        journal_sha256="3" * 64,
        initialization_event_sha256="4" * 64,
        consumed_observation_sha256="5" * 64,
    )
    anchor = L43OriginAnchor(
        runtime_identity=runtime,
        journal_sha256=q62.journal_sha256,
        initialization_event_sha256=q62.initialization_event_sha256,
        consumed_observation_sha256=q62.consumed_observation_sha256,
    )
    return q62, anchor


def _state_path(
    tmp_path: Path,
    *,
    owned: Decimal | None = None,
    reconcile_initial: bool = True,
    terminal_entry_status: IntentStatus | None = None,
    unknown_entry: bool = False,
) -> tuple[Path, str | None]:
    _, anchor = _origin()
    path = tmp_path / "l43-state.jsonl"
    DurableStateStore.create(path, anchor.runtime_identity, l43_origin=anchor)
    path.with_suffix(path.suffix + ".lock").write_bytes(b"\0")
    intent_id: str | None = None
    with L43StateSession.open_existing(path, anchor) as session:
        if owned is not None or reconcile_initial:
            session.reconcile(
                ReconciliationSnapshot(anchor.runtime_identity, Decimal("0"))
            )
        if owned is not None or terminal_entry_status is not None or unknown_entry:
            intent_id = session.reserve_entry(Decimal("10.00"))
            session.prepare_invocation(intent_id)
            if unknown_entry:
                session.mark_unknown(intent_id)
            else:
                session.bind_provider_order(intent_id, _ORDER_ID)
                fill_quantity = Decimal("0") if owned is None else owned
                status = terminal_entry_status or IntentStatus.FILLED
                order_status = {
                    IntentStatus.FILLED: OrderStatus.FILLED,
                    IntentStatus.CANCELED: OrderStatus.CANCELED,
                    IntentStatus.REJECTED: OrderStatus.REJECTED,
                }[status]
                price = (
                    Decimal("81")
                    if fill_quantity == Decimal("0.1234567")
                    else Decimal("20")
                )
                notional = fill_quantity * price
                session.reconcile(
                    ReconciliationSnapshot(
                        anchor.runtime_identity,
                        fill_quantity,
                        (
                            OrderObservation(
                                local_intent_id=intent_id,
                                provider_order_id=_ORDER_ID,
                                status=order_status,
                                cumulative_quantity=fill_quantity,
                                cumulative_notional=notional,
                                working_remainder=Decimal("0"),
                            ),
                        ),
                    )
                )
    return path, intent_id


def _order(owned: Decimal) -> dict[str, object]:
    price = Decimal("81") if owned == Decimal("0.1234567") else Decimal("20")
    stamp = "2026-11-10T15:00:00+00:00"
    return {
        "id": _ORDER_ID,
        "symbol": "SPY",
        "side": "buy",
        "state": "filled",
        "placed_agent": "agentic",
        "agent_initiated": True,
        "created_at": stamp,
        "last_transaction_at": stamp,
        "market_hours": "regular_hours",
        "time_in_force": "day",
        "type": "market",
        "trigger": "immediate",
        "quantity": None,
        "cumulative_quantity": str(owned),
        "average_price": str(price),
        "price": None,
        "stop_price": None,
        "fees": "0",
        "ref_id": None,
        "reject_reason": None,
        "instrument_id": "fake-spy-instrument",
        "dollar_based_amount": {"amount": "10.00", "currency_code": "USD"},
        "executions": [
            {
                "fees": "0",
                "id": _EXECUTION_ID,
                "price": str(price),
                "quantity": str(owned),
                "timestamp": stamp,
            }
        ],
    }


def _canceled_zero_fill_order() -> dict[str, object]:
    order = _order(Decimal("0.5"))
    order.update(
        {
            "state": "canceled",
            "cumulative_quantity": "0",
            "average_price": None,
            "executions": [],
        }
    )
    return order


def _dependencies(
    *,
    state_path: Path,
    as_of: datetime,
    decision: SignalDecision,
    owned: Decimal | None = None,
    order_filled: Decimal | None = None,
    order_rows: list[dict[str, object]] | None = None,
    scope_proven: bool = True,
    account_number: str = _ACCOUNT_NUMBER,
    authority_passed: bool = True,
    signal_offset: timedelta = timedelta(0),
    clock_values: tuple[datetime, ...] | None = None,
    order_page_cursors: tuple[str | None, ...] | None = None,
    read_scope_events: list[str] | None = None,
    malformed_orders: bool = False,
    order_scope_verifier_override: object | None = None,
) -> tuple[
    observer.L43PreEffectDependencies, _ReadBoundary, _SignalProvider, _ScopeVerifier
]:
    q62, anchor = _origin()
    if owned is None:
        positions: list[dict[str, str]] = []
        orders: list[dict[str, object]] = []
    else:
        positions = [
            {
                "symbol": "SPY",
                "quantity": str(owned),
                "shares_available_for_sells": str(owned),
                "type": "long",
            }
        ]
        orders = [_order(owned if order_filled is None else order_filled)]
    if order_rows is not None:
        orders = order_rows
    read_args = {
        "positions": positions,
        "orders": orders,
        "account_number": account_number,
        "order_page_cursors": order_page_cursors,
    }
    if read_scope_events is None:
        read = _ReadBoundary(**read_args)
    else:
        read = _ScopedReadBoundary(
            **read_args,
            scope_events=read_scope_events,
            malformed_orders=malformed_orders,
        )
    normalized_read = RobinhoodL43PreEffectReadAdapter(read)
    signal = _SignalProvider(decision, observation_offset=signal_offset)
    scope = _ScopeVerifier(AgenticAccountIdentity(account_number, 1).fingerprint)
    time_source = iter(clock_values or (as_of,))

    def clock() -> datetime:
        try:
            return next(time_source)
        except StopIteration:
            return clock_values[-1] if clock_values else as_of

    deps = observer.L43PreEffectDependencies(
        source_reader=lambda: _SOURCE,
        continuity_owner=L43ProductionOwner(
            authority_verifier=_Authority(prospective_passed=authority_passed),
            journal_reader=_JournalReader(),
        ),
        origin=q62,
        state_snapshot_reader=lambda: read_l43_state_snapshot(state_path, anchor),
        robinhood_builder=lambda: normalized_read,
        signal_provider_builder=lambda: signal,
        clock=clock,
        order_scope_verifier=(
            order_scope_verifier_override
            if order_scope_verifier_override is not None
            else scope
            if scope_proven
            else None
        ),
        read_operation_scope_factory=(
            (lambda boundary: boundary._operation_scope())
            if read_scope_events is not None
            else None
        ),
    )
    return deps, read, signal, scope


def _assert_no_effects(result: observer.L43PreEffectResult) -> None:
    assert result.reservation_count == 0
    assert result.review_count == 0
    assert result.placement_count == 0
    assert result.cancellation_count == 0
    assert result.provider_mutation_count == 0
    assert not result.placement_authority_granted
    assert not result.trade_authority_granted
    assert not result.live_ready


def test_flat_buy_returns_fresh_semantic_plan_without_reserving_or_authority(
    tmp_path: Path,
):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    first_deps, read, signal, scope = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    initial = read_l43_state_snapshot(state_path, _origin()[1])
    first = observer.observe_l43_pre_effect(first_deps)
    second_time = _NOW + timedelta(minutes=1)
    second_deps, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=second_time,
        decision=SignalDecision.BUY,
    )
    second = observer.observe_l43_pre_effect(second_deps)

    assert (
        first.outcome is observer.L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
    )
    assert first.plan is not None and first.plan.kind is observer.L43PlanKind.ENTRY
    assert first.plan.requested_entry_risk == Decimal("10.00")
    assert first.plan.reconciliation_snapshot.observed_position == Decimal("0")
    assert first.plan.reconciliation_snapshot.identity == _origin()[1].runtime_identity
    assert second.plan is not None
    assert second.plan.binding_sha256 == first.plan.binding_sha256
    assert second.evidence_sha256 != first.evidence_sha256
    assert second.observed_at == second_time
    assert first.robinhood_read_count == 3
    assert first.robinhood_page_count == 2
    assert first.alpaca_provider_call_count == 1
    assert first.credential_read_count == 1
    assert first.reservation_count == first.review_count == 0
    assert first.placement_count == first.cancellation_count == 0
    assert first.provider_mutation_count == 0
    assert not first.placement_authority_granted
    assert not first.trade_authority_granted
    assert not first.live_ready
    assert signal.calls == 1
    assert scope.calls[0][2] == 0
    assert scope.order_arguments == [
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"}
    ]
    assert read.calls[-1] == (
        "get_equity_orders",
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )
    assert read_l43_state_snapshot(state_path, _origin()[1]) == initial
    evidence = first.evidence_json.decode("ascii")
    assert _ACCOUNT_NUMBER not in evidence
    assert _ORDER_ID not in evidence


def test_private_account_handoff_emits_only_for_validated_ready_result(
    tmp_path: Path,
):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    selected: list[object] = []

    result = observer.observe_l43_pre_effect(
        dependencies,
        _account_identity_sink=selected.append,
    )

    assert (
        result.outcome is observer.L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
    )
    assert result.plan is not None
    assert selected == [L43AccountIdentity(_ACCOUNT_NUMBER, _ACCOUNT.fingerprint)]
    assert selected[0].account_fingerprint == result.plan.account_fingerprint
    assert _ACCOUNT_NUMBER not in result.evidence_json.decode("ascii")


@pytest.mark.parametrize(
    ("malformed_orders", "scope_proven", "expected_blocker"),
    (
        (
            False,
            False,
            observer.L43PreEffectBlocker.ORDER_SCOPE_UNPROVEN,
        ),
        (
            True,
            True,
            observer.L43PreEffectBlocker.ORDER_READ_FAILED,
        ),
    ),
)
def test_read_operation_scope_covers_all_reads_and_closes_on_block(
    tmp_path: Path,
    malformed_orders: bool,
    scope_proven: bool,
    expected_blocker: observer.L43PreEffectBlocker,
):
    state_path, _ = _state_path(tmp_path)
    events: list[str] = []
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        scope_proven=scope_proven,
        read_scope_events=events,
        malformed_orders=malformed_orders,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert result.blockers == (expected_blocker,)
    assert events[0] == "open"
    assert events[-1] == "close"
    assert events[1:-1] == [
        "get_accounts",
        "get_equity_positions",
        "get_equity_orders",
    ]
    assert result.robinhood_read_count == 3


def test_relevant_order_digest_binds_agent_initiated_without_query_filter(
    tmp_path: Path,
):
    digests: list[str] = []
    for agent_initiated, label in ((True, "true"), (False, "false")):
        variant_path = tmp_path / label
        variant_path.mkdir()
        state_path, _ = _state_path(variant_path, reconcile_initial=False)
        row = _order(Decimal("0.5"))
        row["agent_initiated"] = agent_initiated
        dependencies, read, _, _ = _dependencies(
            state_path=state_path,
            as_of=_NOW,
            decision=SignalDecision.BUY,
            order_rows=[row],
        )

        result = observer.observe_l43_pre_effect(dependencies)

        assert (
            result.outcome
            is observer.L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
        )
        assert result.plan is not None
        assert read.calls[-1] == (
            "get_equity_orders",
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
        )
        digests.append(result.plan.relevant_orders_digest)

    assert digests[0] != digests[1]


def test_relevant_order_digest_binds_requested_quantity_and_trigger(
    tmp_path: Path,
):
    digests: dict[str, str] = {}
    variants = (
        ("baseline", None, "immediate"),
        ("requested-quantity", "0.5", "immediate"),
        ("trigger", None, "stop"),
    )
    for label, requested_quantity, trigger in variants:
        variant_path = tmp_path / label
        variant_path.mkdir()
        state_path, _ = _state_path(variant_path, reconcile_initial=False)
        row = _order(Decimal("0.5"))
        row["quantity"] = requested_quantity
        row["trigger"] = trigger
        dependencies, _, _, _ = _dependencies(
            state_path=state_path,
            as_of=_NOW,
            decision=SignalDecision.BUY,
            order_rows=[row],
        )

        result = observer.observe_l43_pre_effect(dependencies)

        assert (
            result.outcome
            is observer.L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
        )
        assert result.plan is not None
        digests[label] = result.plan.relevant_orders_digest

    assert digests["baseline"] != digests["requested-quantity"]
    assert digests["baseline"] != digests["trigger"]


def test_post_entry_unrelated_spy_order_blocks_exact_owned_sell_review(
    tmp_path: Path,
):
    state_path, _ = _state_path(tmp_path, owned=Decimal("0.5"))
    entry_order = _order(Decimal("0.5"))
    unrelated = _canceled_zero_fill_order()
    unrelated.update(
        {
            "id": "customer-spy-order-147",
            "symbol": "SPY",
            "side": "sell",
            "placed_agent": "user",
            "agent_initiated": False,
            "created_at": "2026-11-10T15:01:00+00:00",
            "last_transaction_at": "2026-11-10T15:01:00+00:00",
            "quantity": "0.25",
            "dollar_based_amount": None,
        }
    )
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.SELL,
        owned=Decimal("0.5"),
        order_rows=[entry_order, unrelated],
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert result.blockers == (observer.L43PreEffectBlocker.UNRELATED_SPY_ORDER,)
    assert result.plan is None
    assert read.calls[-1] == (
        "get_equity_orders",
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )
    assert "placed_agent" not in read.calls[-1][1]
    _assert_no_effects(result)


def test_nonterminal_entry_cannot_produce_exact_owned_sell_proposal(
    tmp_path: Path,
):
    state_path, _ = _state_path(tmp_path, unknown_entry=True)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.SELL,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert result.blockers == (observer.L43PreEffectBlocker.STATE_UNRESOLVED,)
    assert result.plan is None
    _assert_no_effects(result)


def test_non_buy_ignores_invalid_entry_risk_without_side_effects(tmp_path: Path):
    state_path, _ = _state_path(tmp_path)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.HOLD,
    )
    before = read_l43_state_snapshot(state_path, _origin()[1])

    result = observer.observe_l43_pre_effect(
        dependencies, requested_entry_risk=Decimal("10.001")
    )

    assert result.outcome is observer.L43PreEffectOutcome.NO_ACTION_SIGNAL
    assert result.plan is None
    assert result.blockers == ()
    assert result.reservation_count == result.review_count == 0
    assert result.placement_count == result.cancellation_count == 0
    assert result.provider_mutation_count == 0
    assert read_l43_state_snapshot(state_path, _origin()[1]) == before


def test_unknown_all_agent_order_scope_cannot_prove_order_absence(tmp_path: Path):
    state_path, _ = _state_path(tmp_path)
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        scope_proven=False,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert result.blockers == (observer.L43PreEffectBlocker.ORDER_SCOPE_UNPROVEN,)
    assert result.plan is None
    assert result.reservation_count == result.placement_count == 0
    assert read.calls[-1] == (
        "get_equity_orders",
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )
    assert "placed_agent" not in read.calls[-1][1]


@pytest.mark.parametrize("scope_proven", (False, True))
def test_explicit_complete_order_pagination_needs_provider_scope_semantics(
    tmp_path: Path, scope_proven: bool
):
    state_path, _ = _state_path(tmp_path)
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.HOLD,
        scope_proven=scope_proven,
        order_page_cursors=("page-2", None),
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.robinhood_page_count == 3
    assert read.calls[-2:] == [
        (
            "get_equity_orders",
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
        ),
        (
            "get_equity_orders",
            {
                "account_number": _ACCOUNT_NUMBER,
                "symbol": "SPY",
                "cursor": "page-2",
            },
        ),
    ]
    if scope_proven:
        assert result.outcome is observer.L43PreEffectOutcome.NO_ACTION_SIGNAL
        assert result.blockers == ()
    else:
        assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
        assert result.blockers == (observer.L43PreEffectBlocker.ORDER_SCOPE_UNPROVEN,)


def _rhc3_production_scope_verifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    evidence_admitted: bool,
):
    from trading_bot.robinhood_mcp import l43_production_composition as composition
    from trading_bot.robinhood_mcp import order_scope_evidence_admission as admission

    q62, _ = _origin()
    owner = L43ProductionOwner(
        authority_verifier=_Authority(), journal_reader=_JournalReader()
    )
    monkeypatch.setattr(composition, "read_canonical_q62_origin", lambda: q62)
    monkeypatch.setattr(
        composition.L43ProductionOwner,
        "for_production",
        classmethod(lambda cls, *, repo_root: owner),
    )
    authority = admission.OrderScopeEvidenceAuthority(
        account_fingerprint=q62.runtime_identity.account_fingerprint,
        a2_evidence_sha256="a" * 64,
        rhc2_report_sha256="b" * 64,
        rhc2_observer_evidence_sha256="c" * 64,
        inner_b2_evidence_sha256="d" * 64,
        _seal=admission._AUTHORITY_SEAL,
    )
    monkeypatch.setattr(
        composition,
        "load_order_scope_evidence_authority",
        lambda _origin: authority if evidence_admitted else None,
    )
    built = composition.L43ProductionPreEffectComposition.for_production(
        repo_root=tmp_path,
    )
    return built.dependencies.order_scope_verifier


@pytest.mark.parametrize(
    ("order_rows", "expected_row_count"),
    [([], 0), ([_canceled_zero_fill_order()], 1)],
    ids=("empty-current-set", "nonempty-current-set"),
)
def test_rhc3_production_verifier_authenticates_source_owned_order_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    order_rows: list[dict[str, object]],
    expected_row_count: int,
):
    state_path, _ = _state_path(tmp_path)
    verifier = _rhc3_production_scope_verifier(
        monkeypatch, tmp_path, evidence_admitted=True
    )
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        order_rows=order_rows,
        order_scope_verifier_override=verifier,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert (
        result.outcome is observer.L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
    )
    assert result.blockers == ()
    assert result.plan is not None
    assert result.robinhood_page_count == 2
    query_sha256 = observer._account_wide_spy_order_query_digest(
        _ACCOUNT.fingerprint,
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )
    expected_material = (
        "ARCH147_RHC3_PRODUCTION_ORDER_SCOPE_EVIDENCE_V1",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        _ACCOUNT.fingerprint,
        query_sha256,
        1,
        expected_row_count,
        True,
    )
    expected_digest = hashlib.sha256(
        json.dumps(
            expected_material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert result.plan.order_scope_evidence_digest == expected_digest
    assert read.calls[-1] == (
        "get_equity_orders",
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )
    assert result.reservation_count == result.review_count == 0
    assert result.placement_count == result.cancellation_count == 0


def test_rhc3_tampered_evidence_chain_keeps_order_scope_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    state_path, _ = _state_path(tmp_path)
    verifier = _rhc3_production_scope_verifier(
        monkeypatch, tmp_path, evidence_admitted=False
    )
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        order_scope_verifier_override=verifier,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert result.blockers == (observer.L43PreEffectBlocker.ORDER_SCOPE_UNPROVEN,)
    assert result.plan is None
    assert "order_scope_evidence_digest" not in json.loads(result.evidence_json)
    assert read.calls[-1] == (
        "get_equity_orders",
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )


@pytest.mark.parametrize(
    ("cursors", "expected"),
    (
        (("",), observer.L43PreEffectBlocker.ORDER_INVALID),
        (("c" * 4097,), observer.L43PreEffectBlocker.ORDER_INVALID),
        (("repeat", "repeat"), observer.L43PreEffectBlocker.ORDER_INVALID),
        (("page-2", "page-3"), observer.L43PreEffectBlocker.ORDER_COVERAGE_INCOMPLETE),
    ),
)
def test_inward_order_pagination_rejects_invalid_or_incomplete_cursors(
    cursors: tuple[str | None, ...], expected: observer.L43PreEffectBlocker
):
    requests: list[dict[str, object]] = []
    pages = iter(cursors)

    def reader(arguments):
        requests.append(dict(arguments))
        return observer.L43ReadPage(rows=(), next_cursor=next(pages))

    with pytest.raises(observer._Blocked) as error:
        observer._read_pages(
            reader=reader,
            arguments={"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            max_pages=2,
            max_rows=10,
            counters=observer._Counters(),
            read_failure=observer.L43PreEffectBlocker.ORDER_READ_FAILED,
            invalid=observer.L43PreEffectBlocker.ORDER_INVALID,
        )

    assert error.value.blocker is expected
    if cursors == ("page-2", "page-3"):
        assert requests == [
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            {
                "account_number": _ACCOUNT_NUMBER,
                "symbol": "SPY",
                "cursor": "page-2",
            },
        ]


def test_review_tail_append_does_not_drift_exact_sell_proposal(tmp_path: Path):
    owned = Decimal("0.5")
    state_path, _ = _state_path(tmp_path, owned=owned)
    anchor = _origin()[1]
    first_dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.SELL,
        owned=owned,
    )
    first = observer.observe_l43_pre_effect(first_dependencies)
    assert first.plan is not None and first.plan.sell_proposal is not None
    proposal = first.plan.sell_proposal
    arguments_sha256 = "d" * 64
    with L43StateSession.open_existing(state_path, anchor) as session:
        session.begin_sell_review(
            proposal_sha256=proposal.proposal_sha256(),
            arguments_sha256=arguments_sha256,
        )
        session.accept_sell_review(
            proposal_sha256=proposal.proposal_sha256(),
            arguments_sha256=arguments_sha256,
            review_evidence_sha256="e" * 64,
        )
    after_review = read_l43_state_snapshot(state_path, anchor)
    second_dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.SELL,
        owned=owned,
    )

    second = observer.observe_l43_pre_effect(second_dependencies)

    assert second.plan is not None and second.plan.sell_proposal is not None
    assert after_review.last_sequence > first.plan.state_last_sequence
    assert second.plan.state_tail_sha256 != first.plan.state_tail_sha256
    assert second.plan.binding_sha256 != first.plan.binding_sha256
    assert second.plan.sell_proposal.proposal_sha256() == proposal.proposal_sha256()


@pytest.mark.parametrize(
    ("owned", "expected_outcome"),
    (
        (Decimal("0.5"), observer.L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW),
        (Decimal("0.1234567"), observer.L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED),
    ),
)
def test_sell_plan_or_unsupported_residual_uses_current_exact_reconciliation(
    tmp_path: Path,
    owned: Decimal,
    expected_outcome: observer.L43PreEffectOutcome,
):
    state_path, _ = _state_path(tmp_path, owned=owned)
    anchor = _origin()[1]
    before = read_l43_state_snapshot(state_path, anchor)
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.SELL,
        owned=owned,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is expected_outcome
    assert result.robinhood_read_count == 3
    assert result.provider_mutation_count == 0
    assert result.review_count == result.placement_count == 0
    assert result.reservation_count == 0
    assert read.calls[-1][1] == {
        "account_number": _ACCOUNT_NUMBER,
        "symbol": "SPY",
    }
    if (
        expected_outcome
        is observer.L43PreEffectOutcome.READY_FOR_L43_EXACT_OWNED_REVIEW
    ):
        assert result.plan is not None
        assert result.plan.sell_proposal is not None
        assert result.plan.sell_proposal.review_arguments.quantity == owned
    else:
        assert result.plan is None
        assert result.blockers == (
            observer.L43PreEffectBlocker.EXACT_RESIDUAL_UNSUPPORTED,
        )
        assert (
            result.manual_close_trigger is ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL
        )
        assert result.manual_close_residual_quantity == owned
        assert result.manual_close_state_sequence == before.last_sequence
        assert result.manual_close_state_tail_sha256 == before.journal_sha256
        assert result.manual_close_basis_sha256 is not None
        evidence = result.evidence_json.decode("ascii")
        assert (
            result.evidence_sha256 == hashlib.sha256(result.evidence_json).hexdigest()
        )
        assert _ORDER_ID not in evidence
        assert _EXECUTION_ID not in evidence
        assert _ACCOUNT_NUMBER not in evidence
        assert "q62_journal_digest" in evidence
        assert "state_tail_digest" in evidence
        assert "reconciliation_digest" in evidence
    assert read_l43_state_snapshot(state_path, anchor) == before


def test_mismatched_broker_position_never_becomes_manual_close_evidence(tmp_path: Path):
    owned = Decimal("0.1234567")
    state_path, _ = _state_path(tmp_path, owned=owned)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.SELL,
        owned=owned + Decimal("0.01"),
        order_filled=owned,
    )

    result = observer.observe_l43_pre_effect(dependencies)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert observer.L43PreEffectBlocker.RECONCILIATION_FAILED in result.blockers
    assert result.manual_close_trigger is None
    assert result.manual_close_residual_quantity is None


@pytest.mark.parametrize(
    ("scenario", "expected_blocker"),
    (
        ("continuity", observer.L43PreEffectBlocker.CONTINUITY_UNPROVEN),
        ("account_mismatch", observer.L43PreEffectBlocker.ACCOUNT_MISMATCH),
        ("account_stale", observer.L43PreEffectBlocker.ACCOUNT_STALE),
        ("signal_stale", observer.L43PreEffectBlocker.SIGNAL_STALE),
        ("session_closed", observer.L43PreEffectBlocker.SESSION_UNPROVEN),
        ("position_not_flat", observer.L43PreEffectBlocker.POSITION_NOT_FLAT),
        (
            "working_order",
            observer.L43PreEffectBlocker.WORKING_OR_UNKNOWN_ORDER,
        ),
        (
            "unknown_order",
            observer.L43PreEffectBlocker.WORKING_OR_UNKNOWN_ORDER,
        ),
        (
            "consumed_terminal_entry",
            observer.L43PreEffectBlocker.ENTRY_ALREADY_CONSUMED,
        ),
        ("unknown_entry", observer.L43PreEffectBlocker.STATE_UNRESOLVED),
        ("risk_over_limit", observer.L43PreEffectBlocker.ENTRY_RISK_INVALID),
    ),
)
def test_observation_blockers_fail_closed_without_effects(
    tmp_path: Path,
    scenario: str,
    expected_blocker: observer.L43PreEffectBlocker,
):
    options: dict[str, object] = {}
    state_path_kwargs: dict[str, object] = {}
    order_rows: list[dict[str, object]] | None = None
    account_number = _ACCOUNT_NUMBER
    signal_offset = timedelta(0)
    risk = Decimal("10.00")
    as_of = _NOW
    clock_values: tuple[datetime, ...] | None = None
    authority_passed = True

    if scenario == "continuity":
        authority_passed = False
    elif scenario == "account_mismatch":
        account_number = "712345678901"
    elif scenario == "account_stale":
        clock_values = (
            _NOW,
            _NOW,
            _NOW + timedelta(minutes=3),
            _NOW + timedelta(minutes=3),
            _NOW + timedelta(minutes=3),
        )
    elif scenario == "signal_stale":
        signal_offset = timedelta(minutes=3)
    elif scenario == "session_closed":
        close = datetime(2026, 11, 10, 21, 0, tzinfo=UTC)
        as_of = close - timedelta(minutes=1)
        clock_values = (
            as_of,
            as_of,
            close - timedelta(seconds=30),
            close - timedelta(seconds=30),
            close,
        )
    elif scenario == "position_not_flat":
        options["owned"] = Decimal("0.5")
    elif scenario in {"working_order", "unknown_order"}:
        order = _order(Decimal("0.5"))
        order["state"] = (
            "open" if scenario == "working_order" else "provider_state_unknown"
        )
        order_rows = [order]
    elif scenario == "consumed_terminal_entry":
        state_path_kwargs["terminal_entry_status"] = IntentStatus.CANCELED
        order_rows = [_canceled_zero_fill_order()]
    elif scenario == "unknown_entry":
        state_path_kwargs["unknown_entry"] = True
    elif scenario == "risk_over_limit":
        risk = Decimal("10.01")

    state_path, _ = _state_path(tmp_path, **state_path_kwargs)
    dependencies, _, signal, _ = _dependencies(
        state_path=state_path,
        as_of=as_of,
        decision=SignalDecision.BUY,
        order_rows=order_rows,
        account_number=account_number,
        authority_passed=authority_passed,
        signal_offset=signal_offset,
        clock_values=clock_values,
        **options,
    )
    before = read_l43_state_snapshot(state_path, _origin()[1])

    result = observer.observe_l43_pre_effect(dependencies, requested_entry_risk=risk)

    assert result.outcome is observer.L43PreEffectOutcome.BLOCKED
    assert expected_blocker in result.blockers
    assert result.plan is None
    _assert_no_effects(result)
    if scenario == "signal_stale":
        assert result.alpaca_provider_call_count == 1
        assert result.credential_read_count == 1
    assert read_l43_state_snapshot(state_path, _origin()[1]) == before
    if scenario == "continuity":
        assert signal.calls == 0


def _qualify(
    dependencies: observer.L43PreEffectDependencies,
    *,
    risk: Decimal = Decimal("10.00"),
):
    origin, _ = _origin()
    return qualification._evaluate_qualification(
        context=qualification._Context(origin=origin, requested_entry_usd=risk),
        dependencies=dependencies,
        root=Path("fake-repository"),
        ancestry_check=lambda _root, _source: True,
    )


def _qualification_snapshot_with_order(
    snapshot,
    *,
    kind: IntentKind,
    status: IntentStatus,
    provider_order_id: str | None = "qualification-order",
):
    if kind is IntentKind.ENTRY:
        order = OrderState(
            kind=kind,
            intent_id="qualification-entry-intent",
            requested_dollars=Decimal("10.00"),
            provider_order_id=provider_order_id,
            status=status,
            cumulative_quantity=(
                Decimal("0.1") if status is IntentStatus.PARTIAL else Decimal("0")
            ),
            cumulative_notional=(
                Decimal("2") if status is IntentStatus.PARTIAL else Decimal("0")
            ),
            working_remainder=Decimal("0.4")
            if status is IntentStatus.PARTIAL
            else Decimal("0"),
        )
        state = replace(snapshot.state, entry=order)
    else:
        order = OrderState(
            kind=kind,
            intent_id="qualification-exit-intent",
            requested_quantity=Decimal("0.5"),
            provider_order_id=provider_order_id,
            status=status,
            cumulative_quantity=(
                Decimal("0.1") if status is IntentStatus.PARTIAL else Decimal("0")
            ),
            cumulative_notional=(
                Decimal("2") if status is IntentStatus.PARTIAL else Decimal("0")
            ),
            working_remainder=Decimal("0.4")
            if status is IntentStatus.PARTIAL
            else Decimal("0.5"),
        )
        state = replace(snapshot.state, exit=order)
    return replace(
        snapshot,
        state=state,
        sell_review_pending=state.sell_review_pending,
        manual_close_required=state.manual_close_required,
        manual_follow_up_required=state.manual_follow_up_required,
    )


def test_q1_flat_buy_returns_sanitized_challenge_without_effects(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    state_bytes = state_path.read_bytes()

    result = _qualify(dependencies)
    repeated = _qualify(dependencies)

    assert (
        result["outcome"]
        == qualification.QualificationOutcome.READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW
    )
    assert result["status"] == "PASS"
    assert result["stage"] == "ENTRY_PLACEMENT"
    assert result["challenge_sha256"] and len(result["challenge_sha256"]) == 64
    assert result["account_fingerprint"] == _ACCOUNT.fingerprint
    assert result["provider_call_counts"]["robinhood_reads"] == 3
    assert result["provider_call_counts"]["credential_reads"] is None
    assert all(value == 0 for value in result["effect_counters"].values())
    assert qualification._is_sanitized_result(result)
    assert _ACCOUNT_NUMBER not in json.dumps(result)
    assert _ORDER_ID not in json.dumps(result)
    assert state_path.read_bytes() == state_bytes
    assert repeated["challenge_sha256"] == result["challenge_sha256"]
    assert len(read.calls) == 6
    assert signal.calls == 2


@pytest.mark.parametrize("decision", (SignalDecision.HOLD, SignalDecision.SELL))
def test_q1_flat_non_buy_is_no_action_without_challenge(tmp_path: Path, decision):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=decision,
    )

    result = _qualify(dependencies)

    assert result["status"] == "PASS"
    assert result["outcome"] == "NO_ACTION_SIGNAL"
    assert result["challenge_sha256"] is None
    assert result["stage"] is None
    assert qualification._is_sanitized_result(result)


@pytest.mark.parametrize(
    "risk",
    (Decimal("0"), Decimal("-0.01"), Decimal("10.01"), Decimal("1.001")),
)
def test_q1_invalid_entry_risk_blocks_before_provider_reads(tmp_path: Path, risk):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )

    result = _qualify(dependencies, risk=risk)

    assert result["outcome"] == "BLOCKED"
    assert "ENTRY_RISK_INVALID" in result["reason_codes"]
    assert result["provider_call_counts"]["robinhood_reads"] == 0
    assert read.calls == []
    assert signal.calls == 0


@pytest.mark.parametrize(
    ("kind", "status"),
    (
        (IntentKind.ENTRY, IntentStatus.WORKING),
        (IntentKind.ENTRY, IntentStatus.PARTIAL),
        (IntentKind.EXIT, IntentStatus.WORKING),
        (IntentKind.EXIT, IntentStatus.PARTIAL),
    ),
)
def test_q1_bound_pending_orders_return_settlement_required_without_reads(
    tmp_path: Path,
    kind: IntentKind,
    status: IntentStatus,
):
    state_path, _ = _state_path(
        tmp_path,
        owned=Decimal("0.5") if kind is IntentKind.EXIT else None,
    )
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    base = read_l43_state_snapshot(state_path, _origin()[1])
    pending = _qualification_snapshot_with_order(base, kind=kind, status=status)
    dependencies = replace(dependencies, state_snapshot_reader=lambda: pending)

    result = _qualify(dependencies)

    assert result["outcome"] == "PENDING_SETTLEMENT_REQUIRED"
    assert result["status"] == "BLOCKED"
    assert result["provider_call_counts"]["robinhood_reads"] == 0
    assert read.calls == []
    assert signal.calls == 0
    assert result["challenge_sha256"] is None


def test_q1_unresolved_order_precedes_pending_classification(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    base = read_l43_state_snapshot(state_path, _origin()[1])
    pending = _qualification_snapshot_with_order(
        base,
        kind=IntentKind.ENTRY,
        status=IntentStatus.WORKING,
    )
    unknown_exit = OrderState(
        kind=IntentKind.EXIT,
        intent_id="ambiguous-exit-intent",
        requested_quantity=Decimal("0.5"),
        status=IntentStatus.UNKNOWN,
    )
    mixed = replace(pending, state=replace(pending.state, exit=unknown_exit))
    dependencies = replace(dependencies, state_snapshot_reader=lambda: mixed)

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert result["reason_codes"] == ("UNRESOLVED_EFFECT",)
    assert read.calls == []
    assert signal.calls == 0


def test_q1_pending_preflight_requires_accepted_source_continuity(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        authority_passed=False,
    )
    base = read_l43_state_snapshot(state_path, _origin()[1])
    pending = _qualification_snapshot_with_order(
        base,
        kind=IntentKind.ENTRY,
        status=IntentStatus.WORKING,
    )
    dependencies = replace(dependencies, state_snapshot_reader=lambda: pending)

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert result["reason_codes"] == ("CONTINUITY_UNPROVEN",)
    assert read.calls == []
    assert signal.calls == 0


def test_q1_pending_remains_typed_without_market_or_provider_reads(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, _, _ = _dependencies(
        state_path=state_path,
        as_of=datetime(2026, 11, 10, 22, 0, tzinfo=UTC),
        decision=SignalDecision.BUY,
    )
    base = read_l43_state_snapshot(state_path, _origin()[1])
    pending = _qualification_snapshot_with_order(
        base,
        kind=IntentKind.ENTRY,
        status=IntentStatus.PARTIAL,
    )

    class BrokenSignal:
        calls = 0

        def snapshot(self, _as_of):
            self.calls += 1
            raise RuntimeError("provider unavailable")

    broken = BrokenSignal()
    dependencies = replace(
        dependencies,
        state_snapshot_reader=lambda: pending,
        signal_provider_builder=lambda: broken,
    )
    before = state_path.read_bytes()

    result = _qualify(dependencies)

    assert result["outcome"] == "PENDING_SETTLEMENT_REQUIRED"
    assert result["provider_call_counts"]["robinhood_reads"] == 0
    assert read.calls == []
    assert broken.calls == 0
    assert state_path.read_bytes() == before


def test_q1_manual_close_state_is_typed_and_read_only(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    base = read_l43_state_snapshot(state_path, _origin()[1])
    manual_close = ManualCloseRequired(
        trigger=ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL,
        exact_residual_quantity=Decimal("0.5"),
        basis=ManualCloseBasis.CONFIRMED_RECONCILED_RESIDUAL,
        effect_evidence_sha256="d" * 64,
    )
    state = replace(base.state, manual_close=manual_close)
    snapshot = replace(
        base,
        state=state,
        manual_close_required=True,
        manual_follow_up_required=True,
    )
    dependencies = replace(dependencies, state_snapshot_reader=lambda: snapshot)

    result = _qualify(dependencies)

    assert result["outcome"] == "MANUAL_CLOSE_REQUIRED"
    assert result["status"] == "BLOCKED"
    assert result["challenge_sha256"] is None
    assert read.calls == []
    assert signal.calls == 0


def test_q1_consumed_entry_never_becomes_no_action_or_ready(tmp_path: Path):
    state_path, _ = _state_path(
        tmp_path,
        terminal_entry_status=IntentStatus.CANCELED,
    )
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.HOLD,
        order_rows=[_canceled_zero_fill_order()],
    )

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert result["reason_codes"] == ("ENTRY_ALREADY_CONSUMED",)
    assert result["challenge_sha256"] is None
    assert read.calls == []
    assert signal.calls == 0


def test_q1_state_drift_after_observation_blocks_and_strips_plan(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    original_reader = dependencies.state_snapshot_reader
    reads = 0

    def changing_reader():
        nonlocal reads
        reads += 1
        snapshot = original_reader()
        if reads != 4:
            return snapshot
        state = replace(
            snapshot.state,
            last_sequence=snapshot.last_sequence + 1,
            journal_hash="e" * 64,
        )
        return replace(
            snapshot,
            state=state,
            last_sequence=state.last_sequence,
            journal_sha256=state.journal_hash,
        )

    dependencies = replace(dependencies, state_snapshot_reader=changing_reader)

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert result["reason_codes"] == ("STATE_TAIL_CHANGED",)
    assert result["plan_binding_digest"] is None
    assert result["challenge_sha256"] is None


def test_q1_challenge_is_stable_for_decimal_scale_and_binds_request(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    whole = _qualify(dependencies, risk=Decimal("10"))
    scaled = _qualify(dependencies, risk=Decimal("10.00"))
    lower = _qualify(dependencies, risk=Decimal("9.99"))
    alternate_source = L43SourceIdentity("6" * 40, "7" * 40)
    source_result = _qualify(
        replace(dependencies, source_reader=lambda: alternate_source)
    )
    alternate_root = tmp_path / "alternate-state"
    alternate_root.mkdir()
    alternate_state_path, _ = _state_path(
        alternate_root,
        reconcile_initial=True,
    )
    alternate_state, _, _, _ = _dependencies(
        state_path=alternate_state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    state_result = _qualify(alternate_state)

    assert (
        whole["outcome"]
        == scaled["outcome"]
        == "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    )
    assert whole["challenge_sha256"] == scaled["challenge_sha256"]
    assert lower["outcome"] == "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    assert lower["challenge_sha256"] != whole["challenge_sha256"]
    assert source_result["outcome"] == "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    assert state_result["outcome"] == "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    assert source_result["challenge_sha256"] != whole["challenge_sha256"]
    assert state_result["challenge_sha256"] != whole["challenge_sha256"]


@pytest.mark.parametrize("drift", ("config", "binding"))
def test_q1_source_and_runtime_binding_drift_fail_closed(tmp_path: Path, drift: str):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    origin, anchor = _origin()
    runtime = replace(
        origin.runtime_identity,
        **{f"{drift}_digest": "f" * 64},
    )
    alternate_origin = replace(origin, runtime_identity=runtime)
    alternate_anchor = replace(anchor, runtime_identity=runtime)
    base = read_l43_state_snapshot(state_path, anchor)
    state = replace(
        base.state,
        identity=runtime,
        l43_origin=alternate_anchor,
    )
    snapshot = replace(
        base,
        origin=alternate_anchor,
        state=state,
    )
    dependencies = replace(
        dependencies,
        origin=alternate_origin,
        state_snapshot_reader=lambda: snapshot,
    )
    context = qualification._Context(
        origin=alternate_origin,
        requested_entry_usd=Decimal("10.00"),
    )

    result = qualification._evaluate_qualification(
        context=context,
        dependencies=dependencies,
        root=Path("fake-repository"),
        ancestry_check=lambda _root, _source: True,
    )

    assert result["outcome"] == "BLOCKED"
    assert result["challenge_sha256"] is None
    assert read.calls == []
    assert signal.calls == 0


def test_q1_source_drift_during_observation_blocks_challenge(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    calls = 0
    changed = L43SourceIdentity("6" * 40, "7" * 40)

    def changing_source():
        nonlocal calls
        calls += 1
        return _SOURCE if calls <= 2 else changed

    dependencies = replace(dependencies, source_reader=changing_source)

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert "SOURCE_CHANGED" in result["reason_codes"]
    assert result["challenge_sha256"] is None
    assert len(read.calls) == 3
    assert signal.calls == 1


def test_q1_source_authority_and_rhc4_ancestry_fail_before_reads(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        authority_passed=False,
    )
    result = _qualify(dependencies)
    assert result["outcome"] == "BLOCKED"
    assert read.calls == []
    assert signal.calls == 0

    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    context = qualification._Context(
        origin=_origin()[0],
        requested_entry_usd=Decimal("10.00"),
    )
    rejected = qualification._evaluate_qualification(
        context=context,
        dependencies=dependencies,
        root=Path("fake-repository"),
        ancestry_check=lambda _root, _source: False,
    )
    assert rejected["reason_codes"] == ("RHC4_C2_ANCESTRY_UNPROVEN",)
    assert read.calls == []
    assert signal.calls == 0


@pytest.mark.parametrize(
    "scenario", ("account_mismatch", "manual_position", "scope_missing")
)
def test_q1_account_position_and_scope_mismatches_block(tmp_path: Path, scenario: str):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    options: dict[str, object] = {}
    if scenario == "account_mismatch":
        options["account_number"] = "712345678901"
    elif scenario == "manual_position":
        options["owned"] = Decimal("0.5")
    else:
        options["scope_proven"] = False
    dependencies, _, _, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        **options,
    )

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert result["challenge_sha256"] is None


@pytest.mark.parametrize("scenario", ("closed_session", "stale_signal"))
def test_q1_closed_session_and_stale_signal_block(tmp_path: Path, scenario: str):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    options: dict[str, object] = {}
    as_of = _NOW
    if scenario == "closed_session":
        as_of = datetime(2026, 11, 10, 22, 0, tzinfo=UTC)
    else:
        options["signal_offset"] = timedelta(minutes=3)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=as_of,
        decision=SignalDecision.BUY,
        **options,
    )

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert result["challenge_sha256"] is None
    expected_reason = (
        "SESSION_UNPROVEN" if scenario == "closed_session" else "SIGNAL_STALE"
    )
    assert expected_reason in result["reason_codes"]
    assert signal.calls == 1
    assert len(read.calls) <= 3


@pytest.mark.parametrize(
    "failure", ("account", "positions", "orders", "pagination", "alpaca")
)
def test_q1_read_failures_are_sanitized_and_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, signal, _ = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
    )
    calls: list[str] = []

    def fail_accounts():
        calls.append("account")
        read.calls.append(("get_accounts", {}))
        raise RuntimeError("raw-provider-secret")

    def fail_positions(arguments):
        calls.append("positions")
        read.calls.append(("get_equity_positions", dict(arguments)))
        raise RuntimeError("raw-provider-secret")

    def fail_orders(arguments):
        calls.append("orders")
        read.calls.append(("get_equity_orders", dict(arguments)))
        raise RuntimeError("raw-provider-secret")

    if failure == "account":
        monkeypatch.setattr(read, "get_accounts", fail_accounts)
    elif failure == "positions":
        monkeypatch.setattr(read, "get_equity_positions", fail_positions)
    elif failure == "orders":
        monkeypatch.setattr(read, "get_equity_orders", fail_orders)
    elif failure == "pagination":
        dependencies, read, signal, _ = _dependencies(
            state_path=state_path,
            as_of=_NOW,
            decision=SignalDecision.BUY,
            order_page_cursors=("repeated-page", "repeated-page"),
        )
    else:

        class BrokenSignal:
            calls = 0

            def snapshot(self, _as_of):
                self.calls += 1
                raise RuntimeError("raw-provider-secret")

        broken = BrokenSignal()
        dependencies = replace(dependencies, signal_provider_builder=lambda: broken)

    result = _qualify(dependencies)

    assert result["outcome"] == "BLOCKED"
    assert "raw-provider-secret" not in json.dumps(result)
    assert result["challenge_sha256"] is None
    if failure == "pagination":
        page_calls = [name for name, _ in read.calls if name == "get_equity_orders"]
        assert len(page_calls) == 2
    elif failure == "alpaca":
        assert broken.calls == 1
        assert result["provider_call_counts"]["alpaca_provider_calls"] is None
        assert result["provider_call_counts"]["credential_reads"] is None
    else:
        assert calls == [failure]


def test_q1_successful_multpage_order_read_stays_bounded(tmp_path: Path):
    state_path, _ = _state_path(tmp_path, reconcile_initial=False)
    dependencies, read, _, scope = _dependencies(
        state_path=state_path,
        as_of=_NOW,
        decision=SignalDecision.BUY,
        order_page_cursors=("page-2", None),
    )

    result = _qualify(dependencies)

    assert result["outcome"] == "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    assert result["provider_call_counts"]["robinhood_reads"] == 4
    assert result["provider_call_counts"]["robinhood_pages"] == 3
    assert sum(name == "get_equity_orders" for name, _ in read.calls) == 2
    assert scope.calls[0][1:] == (2, 0, True)


def test_q1_source_boundary_has_no_effect_or_authorization_imports():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(qualification))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    forbidden = {
        "trading_bot.live_prototype.l43_effect_operator",
        "trading_bot.live_prototype.l43_runtime",
    }
    source = inspect.getsource(qualification)
    assert imported.isdisjoint(forbidden)
    assert "L43StageAuthorization" not in source
    assert "L43EffectOperator" not in source
    assert "review_equity_order" not in source
    assert "place_equity_order" not in source
    assert "cancel_equity_order" not in source
    assert qualification._run_protected_preflight.__code__.co_argcount == 0


@pytest.mark.parametrize(
    ("accepted_tree", "ancestor_returncode", "expected"),
    (
        (qualification.RHC4_C2_TREE, 0, True),
        (qualification.RHC4_C2_TREE, 1, False),
        ("0" * 40, 0, False),
    ),
)
def test_q1_rhc4_ancestor_proof_binds_pinned_commit_tree(
    monkeypatch: pytest.MonkeyPatch,
    accepted_tree: str,
    ancestor_returncode: int,
    expected: bool,
):
    from types import SimpleNamespace

    git_calls: list[tuple[object, ...]] = []
    merge_calls: list[tuple[object, ...]] = []

    def fake_git_text(_root, *arguments):
        git_calls.append(arguments)
        return accepted_tree

    def fake_run(arguments, **_kwargs):
        merge_calls.append(tuple(arguments))
        return SimpleNamespace(returncode=ancestor_returncode)

    monkeypatch.setattr(qualification, "_git_text", fake_git_text)
    monkeypatch.setattr(qualification.subprocess, "run", fake_run)

    result = qualification._has_accepted_rhc4_ancestor(Path("fake-root"), _SOURCE)

    assert result is expected
    assert git_calls == [("rev-parse", f"{qualification.RHC4_C2_HEAD}^{{tree}}")]
    if accepted_tree == qualification.RHC4_C2_TREE:
        assert merge_calls == [
            (
                "git",
                "-C",
                "fake-root",
                "merge-base",
                "--is-ancestor",
                qualification.RHC4_C2_HEAD,
                _SOURCE.source_head,
            )
        ]
    else:
        assert merge_calls == []
