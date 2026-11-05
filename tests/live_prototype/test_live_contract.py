"""Focused source-only tests for the pure Arch-147 L40 live contract."""

from __future__ import annotations

from dataclasses import replace
from decimal import Context, Decimal, localcontext

import pytest

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import (
    ENTRY_BUDGET,
    AdmissionContext,
    Blocker,
    CapabilityStatus,
    ContractAdmission,
    ExitCapability,
    GateEvidence,
    GateSet,
    GateStatus,
    IntentKind,
    IntentProposal,
    OwnershipSnapshot,
    StrategySignal,
    admit_intent,
    reserve_intent,
)

DIGEST = "a" * 64
HEAD = "b" * 40
TREE = "c" * 40
SESSION = "2026-11-05"


def _gates(**changes: GateEvidence) -> GateSet:
    passed = GateEvidence(GateStatus.PASS, DIGEST)
    return replace(
        GateSet(
            source=passed,
            account=passed,
            position=passed,
            orders=passed,
            signal=passed,
            quote=passed,
            session=passed,
            readiness=passed,
            risk=passed,
            sellable=passed,
        ),
        **changes,
    )


def _capability(
    *,
    min_sell: Decimal = Decimal("0"),
    full_close_exception: bool | None = None,
    residual_close: bool | None = True,
    increment: Decimal = Decimal("0.000001"),
    max_quantity: Decimal | None = Decimal("100"),
) -> ExitCapability:
    return ExitCapability(
        status=CapabilityStatus.EVIDENCE_RECORDED,
        evidence_digest=DIGEST,
        regular_hours_market_sell=True,
        fractional_quantity=True,
        minimum_quantity=Decimal("0"),
        quantity_increment=increment,
        maximum_quantity=max_quantity,
        minimum_sell_notional=min_sell,
        exact_full_close_below_minimum_supported=full_close_exception,
        exact_residual_close_supported=residual_close,
    )


def _snapshot(**changes: object) -> OwnershipSnapshot:
    return replace(
        OwnershipSnapshot(
            account_fingerprint=DIGEST,
            source_head=HEAD,
            source_tree=TREE,
            config_digest=DIGEST,
            binding_digest=DIGEST,
            lifecycle_id="desktop-life-1",
            lifecycle=Lifecycle.RUNNING,
        ),
        **changes,
    )


def _context(
    state: OwnershipSnapshot,
    *,
    signal: StrategySignal = StrategySignal.BUY,
    position: Decimal = Decimal("0"),
    sellable: Decimal = Decimal("0"),
    price: Decimal | None = Decimal("100"),
    session: str = SESSION,
    gates: GateSet | None = None,
    capability: ExitCapability | None = None,
    **changes: object,
) -> AdmissionContext:
    return replace(
        AdmissionContext(
            account_fingerprint=state.account_fingerprint,
            symbol=state.symbol,
            strategy=state.strategy,
            source_head=state.source_head,
            source_tree=state.source_tree,
            config_digest=state.config_digest,
            binding_digest=state.binding_digest,
            lifecycle_id=state.lifecycle_id,
            target_session=session,
            lifecycle=Lifecycle.RUNNING,
            strategy_signal=signal,
            observed_position=position,
            sellable_quantity=sellable,
            current_price=price,
            working_order_count=0,
            gates=_gates() if gates is None else gates,
            exit_capability=_capability() if capability is None else capability,
        ),
        **changes,
    )


def _filled_snapshot(quantity: str = "1", **changes: object) -> OwnershipSnapshot:
    values: dict[str, object] = dict(
        target_session="2026-11-04",
        effect_disposition=EffectDisposition.CONFIRMED,
        cumulative_bought=Decimal(quantity),
        cumulative_entry_filled_dollars=Decimal("11.25"),
        entry_reserved_dollars=Decimal("10.00"),
        entries_used=1,
        entry_local_intent_id="entry-intent-1",
        entry_provider_order_id="entry-order-1",
    )
    values.update(changes)
    return _snapshot(**values)


def test_entry_admission_and_reservation_consume_budget_without_authorizing_effect():
    state = _snapshot()
    context = _context(state)
    proposal = IntentProposal(
        "entry-intent-1", SESSION, IntentKind.ENTRY, Decimal("10.00")
    )

    admission = admit_intent(state, proposal, context)
    assert admission.admissible

    with localcontext(Context(prec=2)):
        reserved = reserve_intent(
            admission, current_snapshot=state, current_context=context
        )
        assert reserved.budget_remaining == Decimal("0.00")
    assert reserved.entry_reserved_dollars == Decimal("10.00")
    assert reserved.entries_used == 1
    assert reserved.pending_intent_id == proposal.intent_id
    assert reserved.pending_kind is IntentKind.ENTRY
    assert reserved.entry_provider_order_id is None
    assert reserved.lifecycle is Lifecycle.RECONCILING
    assert reserved.effect_disposition is EffectDisposition.NO_EFFECT

    retry = admit_intent(reserved, proposal, context)
    assert not retry.admissible
    assert Blocker.INTENT_UNRESOLVED in retry.blockers
    assert Blocker.ENTRY_ALREADY_USED in retry.blockers
    with pytest.raises(ValueError, match="facts changed"):
        reserve_intent(admission, current_snapshot=reserved, current_context=context)


@pytest.mark.parametrize("amount", [Decimal("10.01"), Decimal("0.001"), Decimal("0")])
def test_entry_rejects_over_limit_invalid_precision_and_zero(amount: Decimal):
    state = _snapshot()
    proposal = IntentProposal("entry-intent-1", SESSION, IntentKind.ENTRY, amount)
    result = admit_intent(state, proposal, _context(state))
    assert not result.admissible
    if amount == Decimal("10.01"):
        assert Blocker.ENTRY_ORDER_LIMIT in result.blockers
    else:
        assert Blocker.INVALID_ENTRY_AMOUNT in result.blockers


def test_reservation_cannot_be_forged_or_reused_with_changed_context():
    state = _snapshot()
    context = _context(state)
    too_large = IntentProposal(
        "entry-intent-2", SESSION, IntentKind.ENTRY, Decimal("20.00")
    )
    forged = ContractAdmission(too_large, state, context)
    with pytest.raises(ValueError, match="not contract-admissible"):
        reserve_intent(forged, current_snapshot=state, current_context=context)

    valid = IntentProposal("entry-intent-1", SESSION, IntentKind.ENTRY, Decimal("1.00"))
    admission = admit_intent(state, valid, context)
    changed = replace(context, target_session="2026-11-06")
    with pytest.raises(ValueError, match="facts changed"):
        reserve_intent(admission, current_snapshot=state, current_context=changed)


def test_unknown_readiness_risk_or_quote_facts_fail_closed():
    state = _snapshot()
    proposal = IntentProposal(
        "entry-intent-1", SESSION, IntentKind.ENTRY, Decimal("1.00")
    )
    gates = _gates(risk=GateEvidence())
    result = admit_intent(state, proposal, _context(state, gates=gates))
    assert not result.admissible
    assert Blocker.GATE_UNKNOWN in result.blockers

    missing_quote = _context(state, price=None)
    result = admit_intent(state, proposal, missing_quote)
    assert Blocker.GATE_UNKNOWN in result.blockers


def test_entry_requires_exit_and_exact_residual_capability_proof():
    state = _snapshot()
    proposal = IntentProposal(
        "entry-intent-1", SESSION, IntentKind.ENTRY, Decimal("1.00")
    )
    unknown = admit_intent(
        state, proposal, _context(state, capability=ExitCapability())
    )
    assert Blocker.EXIT_CAPABILITY_UNPROVEN in unknown.blockers

    no_residual = admit_intent(
        state, proposal, _context(state, capability=_capability(residual_close=False))
    )
    assert Blocker.EXIT_CAPABILITY_UNPROVEN in no_residual.blockers

    unproven_minimum = _capability(min_sell=Decimal("1.00"), full_close_exception=False)
    result = admit_intent(state, proposal, _context(state, capability=unproven_minimum))
    assert Blocker.EXIT_CAPABILITY_UNPROVEN in result.blockers

    unknown_maximum = _capability(max_quantity=None)
    assert not admit_intent(
        state, proposal, _context(state, capability=unknown_maximum)
    ).admissible
    known_no_maximum = replace(unknown_maximum, no_maximum_quantity_limit=True)
    assert admit_intent(
        state, proposal, _context(state, capability=known_no_maximum)
    ).admissible
    assert not _capability(max_quantity=Decimal("0")).permits_entry


def test_safety_exit_may_bypass_hold_and_exceed_ten_dollars_only_for_owned_close():
    state = _filled_snapshot()
    capability = _capability(
        min_sell=Decimal("5.00"), full_close_exception=True, increment=Decimal("0.1")
    )
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("1"),
        sellable=Decimal("1"),
        price=Decimal("12"),
        capability=capability,
    )
    safety = IntentProposal(
        "safety-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("1"),
    )
    result = admit_intent(state, safety, context)
    assert result.admissible
    assert Decimal("1") * Decimal("12") > ENTRY_BUDGET

    ordinary = IntentProposal(
        "strategy-exit-1",
        SESSION,
        IntentKind.STRATEGY_EXIT,
        requested_quantity=Decimal("1"),
    )
    result = admit_intent(state, ordinary, context)
    assert Blocker.STRATEGY_SIGNAL_REQUIRED in result.blockers

    cannot_override_buy = _context(
        state,
        signal=StrategySignal.BUY,
        position=Decimal("1"),
        sellable=Decimal("1"),
        price=Decimal("12"),
        capability=capability,
    )
    result = admit_intent(state, safety, cannot_override_buy)
    assert Blocker.STRATEGY_SIGNAL_REQUIRED in result.blockers


def test_strategy_exit_requires_sell_signal_and_exact_owned_quantity():
    state = _filled_snapshot("2")
    capability = _capability(increment=Decimal("0.1"))
    context = _context(
        state,
        signal=StrategySignal.SELL,
        position=Decimal("2"),
        sellable=Decimal("2"),
        price=Decimal("6"),
        capability=capability,
    )
    proposal = IntentProposal(
        "strategy-exit-1",
        SESSION,
        IntentKind.STRATEGY_EXIT,
        requested_quantity=Decimal("2"),
    )
    assert admit_intent(state, proposal, context).admissible

    too_much = replace(proposal, requested_quantity=Decimal("2.1"))
    result = admit_intent(state, too_much, context)
    assert Blocker.EXIT_NOT_EXACT_OWNED_QUANTITY in result.blockers


def test_exit_requires_sellable_quantity_fresh_risk_and_proven_capability():
    state = _filled_snapshot()
    proposal = IntentProposal(
        "safety-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("1"),
    )
    base = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("1"),
        sellable=Decimal("1"),
        capability=_capability(increment=Decimal("0.1")),
    )
    assert admit_intent(state, proposal, base).admissible

    insufficient = replace(base, sellable_quantity=Decimal("0.9"))
    assert (
        Blocker.EXIT_NOT_SELLABLE
        in admit_intent(state, proposal, insufficient).blockers
    )
    no_risk = replace(base, gates=_gates(risk=GateEvidence()))
    assert Blocker.GATE_UNKNOWN in admit_intent(state, proposal, no_risk).blockers
    no_capability = replace(base, exit_capability=ExitCapability())
    assert (
        Blocker.EXIT_CAPABILITY_UNPROVEN
        in admit_intent(state, proposal, no_capability).blockers
    )


def test_six_decimal_bound_is_independent_of_advertised_increment():
    state = _filled_snapshot("1.0000001")
    capability = _capability(increment=Decimal("0.0000001"))
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("1.0000001"),
        sellable=Decimal("1.0000001"),
        price=Decimal("12"),
        capability=capability,
    )
    proposal = IntentProposal(
        "safety-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("1.0000001"),
    )
    result = admit_intent(state, proposal, context)
    assert Blocker.EXIT_SIZE_UNSUPPORTED in result.blockers


def test_nonzero_baseline_or_unbound_fills_do_not_prove_ownership():
    baseline = _snapshot(baseline_quantity=Decimal("1"))
    context = _context(baseline, position=Decimal("1"))
    proposal = IntentProposal(
        "entry-intent-1", SESSION, IntentKind.ENTRY, Decimal("1.00")
    )
    assert (
        Blocker.BASELINE_POSITION_UNPROVEN
        in admit_intent(baseline, proposal, context).blockers
    )

    unbound = _filled_snapshot(entry_provider_order_id=None)
    exit_proposal = IntentProposal(
        "safety-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("1"),
    )
    result = admit_intent(
        unbound,
        exit_proposal,
        _context(
            unbound,
            signal=StrategySignal.HOLD,
            position=Decimal("1"),
            sellable=Decimal("1"),
        ),
    )
    assert Blocker.OWNERSHIP_UNPROVEN in result.blockers


def test_may_have_occurred_working_orders_and_session_rollback_block():
    state = _filled_snapshot(effect_disposition=EffectDisposition.MAY_HAVE_OCCURRED)
    proposal = IntentProposal(
        "safety-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("1"),
    )
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("1"),
        sellable=Decimal("1"),
        capability=_capability(increment=Decimal("0.1")),
    )
    result = admit_intent(state, proposal, context)
    assert Blocker.STATE_UNKNOWN in result.blockers

    working = replace(context, working_order_count=1)
    assert (
        Blocker.WORKING_ORDER_PRESENT in admit_intent(state, proposal, working).blockers
    )
    old_session = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("1"),
        sellable=Decimal("1"),
        session="2026-11-03",
        capability=_capability(increment=Decimal("0.1")),
    )
    old_proposal = replace(proposal, target_session="2026-11-03")
    assert (
        Blocker.IDENTITY_MISMATCH
        in admit_intent(state, old_proposal, old_session).blockers
    )


def test_snapshot_rejects_inconsistent_order_identity_and_exit_usage():
    with pytest.raises(ValueError, match="market session"):
        replace(_snapshot(), target_session="11/05/2026")
    malformed = _filled_snapshot(
        exits_used=1,
        cumulative_sold=Decimal("0.1"),
        exit_local_intent_id="entry-intent-1",
        exit_provider_order_id="entry-order-1",
    )
    proposal = IntentProposal(
        "new-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("0.9"),
    )
    result = admit_intent(
        malformed,
        proposal,
        _context(
            malformed,
            signal=StrategySignal.HOLD,
            position=Decimal("0.9"),
            sellable=Decimal("0.9"),
        ),
    )
    assert Blocker.INVALID_SNAPSHOT in result.blockers


def test_filled_snapshot_requires_its_original_target_session():
    state = _filled_snapshot(target_session=None)
    proposal = IntentProposal(
        "safety-exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("1"),
    )
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("1"),
        sellable=Decimal("1"),
    )
    result = admit_intent(state, proposal, context)
    assert not result.admissible
    assert Blocker.INVALID_SNAPSHOT in result.blockers


@pytest.mark.parametrize("name", tuple(GateSet.__dataclass_fields__))
@pytest.mark.parametrize("status", [GateStatus.UNKNOWN, GateStatus.FAIL])
def test_safety_exit_never_bypasses_missing_or_failed_gate(name, status):
    state = _filled_snapshot("0.123456")
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("0.123456"),
        sellable=Decimal("0.123456"),
        gates=_gates(**{name: GateEvidence(status)}),
    )
    proposal = IntentProposal(
        "exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("0.123456"),
    )
    assert not admit_intent(state, proposal, context).admissible


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_fingerprint", "d" * 64),
        ("source_head", "d" * 40),
        ("source_tree", "e" * 40),
        ("config_digest", "f" * 64),
        ("binding_digest", "e" * 64),
        ("lifecycle_id", "unrelated-life"),
        ("symbol", "QQQ"),
        ("strategy", "UNSELECTED"),
        ("target_session", "2026-11-06"),
    ],
)
def test_exact_identity_drift_blocks_safety_exit(field, value):
    state = _filled_snapshot("0.1")
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=Decimal("0.1"),
        sellable=Decimal("0.1"),
        **{field: value},
    )
    proposal = IntentProposal(
        "exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("0.1"),
    )
    assert Blocker.IDENTITY_MISMATCH in admit_intent(state, proposal, context).blockers


@pytest.mark.parametrize("position", [Decimal("0.099999"), Decimal("0.100001")])
def test_manual_addition_or_missing_position_blocks_owned_exit(position):
    state = _filled_snapshot("0.1")
    proposal = IntentProposal(
        "exit-1",
        SESSION,
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("0.1"),
    )
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=position,
        sellable=Decimal("0.1"),
    )
    assert Blocker.POSITION_MISMATCH in admit_intent(state, proposal, context).blockers


@pytest.mark.parametrize(
    "quantity,minimum,step,allowed",
    [
        ("0.123456", "0.000001", "0.000001", True),
        ("0.123456000", "0.000001", "0.000001", True),
        ("0.000001", "0.001", "0.000001", False),
        ("0.123456", "0", "0.001", False),
    ],
)
def test_exact_fraction_or_unsupported_residual_is_never_rounded(
    quantity, minimum, step, allowed
):
    value = Decimal(quantity)
    state = _filled_snapshot(quantity)
    rules = replace(
        _capability(),
        minimum_quantity=Decimal(minimum),
        quantity_increment=Decimal(step),
    )
    context = _context(
        state,
        signal=StrategySignal.HOLD,
        position=value,
        sellable=value,
        capability=rules,
    )
    proposal = IntentProposal(
        "exit-1", SESSION, IntentKind.SAFETY_EXIT, requested_quantity=value
    )
    assert admit_intent(state, proposal, context).admissible is allowed
    assert state.owned_quantity == value


def test_partial_fill_and_new_session_do_not_refund_or_restore_attempts():
    state = _filled_snapshot("0.01", cumulative_entry_filled_dollars=Decimal("0.5"))
    assert state.budget_remaining == Decimal("0")
    entry = IntentProposal("new-entry", "2026-11-06", IntentKind.ENTRY, Decimal("1"))
    result = admit_intent(
        state, entry, _context(state, session="2026-11-06", position=Decimal("0.01"))
    )
    assert Blocker.ENTRY_ALREADY_USED in result.blockers
    assert Blocker.ENTRY_BUDGET_EXHAUSTED in result.blockers
    partial_exit = replace(
        state,
        cumulative_sold=Decimal("0.005"),
        exits_used=1,
        exit_local_intent_id="old-exit",
        exit_provider_order_id="old-exit-order",
    )
    exit_proposal = IntentProposal(
        "replacement-exit",
        "2026-11-06",
        IntentKind.SAFETY_EXIT,
        requested_quantity=Decimal("0.005"),
    )
    context = _context(
        partial_exit,
        signal=StrategySignal.HOLD,
        session="2026-11-06",
        position=Decimal("0.005"),
        sellable=Decimal("0.005"),
    )
    assert (
        Blocker.EXIT_ALREADY_USED
        in admit_intent(partial_exit, exit_proposal, context).blockers
    )
    assert partial_exit.budget_remaining == Decimal("0")


def test_unknown_reservation_survives_new_session_and_new_intent_identity():
    state = _snapshot()
    context = _context(state)
    proposal = IntentProposal("entry-1", SESSION, IntentKind.ENTRY, Decimal("10"))
    reserved = reserve_intent(
        admit_intent(state, proposal, context),
        current_snapshot=state,
        current_context=context,
    )
    unknown = replace(
        reserved,
        lifecycle=Lifecycle.UNKNOWN,
        effect_disposition=EffectDisposition.MAY_HAVE_OCCURRED,
    )
    retry = replace(proposal, intent_id="new-identity", target_session="2026-11-06")
    result = admit_intent(unknown, retry, _context(unknown, session="2026-11-06"))
    assert Blocker.STATE_UNKNOWN in result.blockers
    assert Blocker.INTENT_UNRESOLVED in result.blockers
    assert Blocker.ENTRY_ALREADY_USED in result.blockers
    assert unknown.budget_remaining == Decimal("0")


def test_ownership_and_budget_arithmetic_ignore_ambient_decimal_traps():
    from decimal import Inexact, Rounded

    state = _filled_snapshot(
        "0.123456",
        cumulative_sold=Decimal("0.003456"),
        exits_used=1,
        exit_local_intent_id="exit-1",
        exit_provider_order_id="exit-order-1",
    )
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.Emax = 2
        ambient.Emin = -2
        ambient.traps[Inexact] = True
        ambient.traps[Rounded] = True
        assert state.owned_quantity == Decimal("0.12")
        assert state.budget_remaining == Decimal("0")
