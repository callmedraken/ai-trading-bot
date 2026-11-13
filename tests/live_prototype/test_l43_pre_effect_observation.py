from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.desktop_paper.robinhood_read import AgenticAccountIdentity
from trading_bot.live_prototype import l43_pre_effect_observation as observer
from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    RuntimeSignalReason,
    RuntimeSignalSnapshot,
)
from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.durable_state import (
    DurableStateStore,
    IntentStatus,
    L43OriginAnchor,
    OrderObservation,
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

    def verify_account_wide_spy_orders(
        self,
        *,
        account_fingerprint: str,
        query_sha256: str,
        pages_read: int,
        row_count: int,
        exhausted: bool,
    ):
        self.calls.append((query_sha256, pages_read, row_count, exhausted))
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
    read = _ReadBoundary(
        positions=positions,
        orders=orders,
        account_number=account_number,
        order_page_cursors=order_page_cursors,
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
        order_scope_verifier=scope if scope_proven else None,
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
    assert read.calls[-1] == (
        "get_equity_orders",
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )
    assert read_l43_state_snapshot(state_path, _origin()[1]) == initial
    evidence = first.evidence_json.decode("ascii")
    assert _ACCOUNT_NUMBER not in evidence
    assert _ORDER_ID not in evidence


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
