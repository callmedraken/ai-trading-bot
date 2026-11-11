"""Fake-only tests for the frozen tiny-live policy and sell contracts."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import IntentKind, OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.tiny_live_policy import (
    EXACT_SELL_REVIEW_CONTRACT_ID,
    TINY_LIVE_POLICY,
    EntryTerminalOutcome,
    ExactOwnedSellProposal,
    ExactSellBlocker,
    ExactSellStatus,
    ManualCloseTrigger,
    NormalizedReviewOutcome,
    NormalizedReviewSemantics,
    NormalizedSellReview,
    ReconciledOwnedPosition,
    SellOrderArguments,
    SellOrderContext,
    SellOrderType,
    SellReviewBlocker,
    SellReviewValidationStatus,
    SellSession,
    SellSide,
    SellTimeInForce,
    TerminalEntryEvidence,
    TinyLivePolicy,
    evaluate_exact_owned_sell_proposal,
    require_manual_close,
    validate_normalized_sell_review,
)

_IDENTITY = ReadinessIdentity(
    source_head="a" * 40,
    source_tree="b" * 40,
    config_digest="c" * 64,
    account_fingerprint="d" * 64,
    target_session="2026-11-10",
)
_OWNED = Decimal("0.123456")
_NOTIONAL = Decimal("10.01")
_ENTRY_LOCAL_ID = "entry-intent-1"
_ENTRY_PROVIDER_ID = "entry-order-1"
_BINDING = "e" * 64
_LIFECYCLE_ID = "desktop-life-1"


def _owned_snapshot(**changes: object) -> OwnershipSnapshot:
    values: dict[str, object] = {
        "account_fingerprint": _IDENTITY.account_fingerprint,
        "symbol": "SPY",
        "strategy": "BASE_MA35_50_V1",
        "source_head": _IDENTITY.source_head,
        "source_tree": _IDENTITY.source_tree,
        "config_digest": _IDENTITY.config_digest,
        "binding_digest": _BINDING,
        "lifecycle_id": _LIFECYCLE_ID,
        "target_session": _IDENTITY.target_session,
        "lifecycle": Lifecycle.RUNNING,
        "effect_disposition": EffectDisposition.CONFIRMED,
        "baseline_quantity": Decimal("0"),
        "cumulative_bought": _OWNED,
        "cumulative_sold": Decimal("0"),
        "cumulative_entry_filled_dollars": _NOTIONAL,
        "entry_reserved_dollars": Decimal("10.00"),
        "working_remainder": Decimal("0"),
        "entries_used": 1,
        "exits_used": 0,
        "entry_local_intent_id": _ENTRY_LOCAL_ID,
        "entry_provider_order_id": _ENTRY_PROVIDER_ID,
    }
    values.update(changes)
    return OwnershipSnapshot(**values)  # type: ignore[arg-type]


def _position(**changes: object) -> ReconciledOwnedPosition:
    values: dict[str, object] = {
        "identity": _IDENTITY,
        "ownership_snapshot": _owned_snapshot(),
        "broker_position_quantity": _OWNED,
        "broker_sellable_quantity": _OWNED,
        "working_order_count": 0,
        "unresolved_order_count": 0,
        "evidence_sha256": "f" * 64,
    }
    values.update(changes)
    return ReconciledOwnedPosition(**values)  # type: ignore[arg-type]


def _entry() -> TerminalEntryEvidence:
    return TerminalEntryEvidence(
        local_intent_id=_ENTRY_LOCAL_ID,
        provider_order_id=_ENTRY_PROVIDER_ID,
        outcome=EntryTerminalOutcome.FILLED,
        requested_usd_cents=1000,
        reserved_usd_cents=1000,
        confirmed_filled_quantity=_OWNED,
        confirmed_filled_notional=_NOTIONAL,
    )


def _sell_arguments(quantity: Decimal = _OWNED) -> SellOrderArguments:
    return SellOrderArguments(
        side=SellSide.SELL,
        symbol="SPY",
        order_type=SellOrderType.MARKET,
        session=SellSession.REGULAR_HOURS,
        time_in_force=SellTimeInForce.DAY,
        quantity=quantity,
        context=SellOrderContext(
            identity=_IDENTITY,
            binding_digest=_BINDING,
            lifecycle_id=_LIFECYCLE_ID,
            entry_local_intent_id=_ENTRY_LOCAL_ID,
            entry_provider_order_id=_ENTRY_PROVIDER_ID,
            exact_owned_remainder=_OWNED,
            broker_position_quantity=_OWNED,
            broker_sellable_quantity=_OWNED,
            terminal_entry_outcome=EntryTerminalOutcome.FILLED,
            reserved_usd_cents=1000,
            confirmed_entry_filled_quantity=_OWNED,
            confirmed_entry_filled_notional=_NOTIONAL,
        ),
    )


def _proposal(
    *,
    review: SellOrderArguments | None = None,
    placement: SellOrderArguments | None = None,
) -> ExactOwnedSellProposal:
    review_arguments = _sell_arguments() if review is None else review
    return ExactOwnedSellProposal(
        position=_position(),
        terminal_entry=_entry(),
        review_arguments=review_arguments,
        placement_arguments=(review_arguments if placement is None else placement),
    )


def _review(
    proposal: ExactOwnedSellProposal,
    *,
    outcome: NormalizedReviewOutcome = NormalizedReviewOutcome.AFFIRMATIVE,
    semantics: NormalizedReviewSemantics = (
        NormalizedReviewSemantics.NONPLACING_PREVIEW
    ),
    **changes: object,
) -> NormalizedSellReview:
    eligibility = evaluate_exact_owned_sell_proposal(proposal)
    values: dict[str, object] = {
        "contract_id": EXACT_SELL_REVIEW_CONTRACT_ID,
        "review_id": "review-1",
        "evidence_sha256": "1" * 64,
        "proposal_sha256": eligibility.proposal_sha256,
        "identity": _IDENTITY,
        "reviewed_arguments": proposal.review_arguments,
        "outcome": outcome,
        "semantics": semantics,
        "warnings": (),
        "unknown_fields": (),
        "rejection_code": None,
        "provider_order_id": None,
    }
    values.update(changes)
    return NormalizedSellReview(**values)  # type: ignore[arg-type]


def test_policy_freezes_one_cent_denominated_ten_dollar_entry_without_replenishment():
    policy = TINY_LIVE_POLICY
    assert policy == TinyLivePolicy()
    assert policy.entry_request_unit == "USD_CENTS"
    assert policy.entry_limit_usd_cents == 1000
    assert policy.max_entry_intents == 1
    assert policy.entry_budget_replenishes is False
    assert policy.reserve_full_entry_request is True
    assert policy.no_second_entry_after_rejection is True
    assert policy.no_second_entry_after_cancellation is True
    assert policy.no_second_entry_after_partial_fill is True
    assert policy.no_second_entry_after_unknown_outcome is True
    assert policy.no_second_entry_after_restart is True
    assert policy.no_second_entry_after_date_change is True
    assert policy.no_second_entry_after_exit is True
    assert not policy.placement_authority_in_this_checkpoint

    with pytest.raises(TypeError):
        TinyLivePolicy(entry_limit_usd_cents=1001)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="full requested entry reservation"):
        TerminalEntryEvidence(
            local_intent_id=_ENTRY_LOCAL_ID,
            provider_order_id=_ENTRY_PROVIDER_ID,
            outcome=EntryTerminalOutcome.FILLED,
            requested_usd_cents=1000,
            reserved_usd_cents=999,
            confirmed_filled_quantity=_OWNED,
            confirmed_filled_notional=Decimal("10.01"),
        )
    assert _entry().confirmed_filled_notional > Decimal("10.00")


def test_manual_close_is_a_mandatory_policy_outcome_for_unsupported_residual():
    assert TINY_LIVE_POLICY.review_required_before_automated_sell
    assert TINY_LIVE_POLICY.manual_close_required_for_unsupported_residual
    assert TINY_LIVE_POLICY.no_automatic_replacement_sell
    unsupported = _proposal(
        review=_sell_arguments(Decimal("0.123457")),
        placement=_sell_arguments(Decimal("0.123457")),
    )
    result = evaluate_exact_owned_sell_proposal(unsupported)
    assert result.status is ExactSellStatus.BLOCKED
    assert result.manual_close_trigger is ManualCloseTrigger.UNSUPPORTED_EXACT_RESIDUAL


@pytest.mark.parametrize("quantity", [Decimal("0.123457"), Decimal("0.12345")])
def test_exact_sell_never_rounds_up_or_truncates_owned_quantity(quantity: Decimal):
    arguments = _sell_arguments(quantity)
    result = evaluate_exact_owned_sell_proposal(
        _proposal(review=arguments, placement=arguments)
    )
    assert result.status is ExactSellStatus.BLOCKED
    assert ExactSellBlocker.QUANTITY_NOT_EXACT_FULL_OWNED in result.blockers
    assert not result.placement_authority_granted


def test_exact_sell_rejects_unsupported_precision_and_dollar_substitution():
    too_precise = _sell_arguments(Decimal("0.1234567"))
    unsupported = evaluate_exact_owned_sell_proposal(
        _proposal(review=too_precise, placement=too_precise)
    )
    assert ExactSellBlocker.QUANTITY_SCALE_UNSUPPORTED in unsupported.blockers

    with_dollars = replace(_sell_arguments(), dollar_amount=Decimal("10.00"))
    substituted = evaluate_exact_owned_sell_proposal(
        _proposal(review=with_dollars, placement=with_dollars)
    )
    assert ExactSellBlocker.DOLLAR_SUBSTITUTION_FORBIDDEN in substituted.blockers


def test_exact_sell_requires_identical_review_and_placement_arguments():
    review = _sell_arguments()
    placement = replace(_sell_arguments(), quantity=Decimal("0.123455"))
    result = evaluate_exact_owned_sell_proposal(
        _proposal(review=review, placement=placement)
    )
    assert result.status is ExactSellStatus.BLOCKED
    assert ExactSellBlocker.ORDER_ARGUMENTS_MISMATCH in result.blockers


@pytest.mark.parametrize(
    "outcome,semantics",
    [
        (
            NormalizedReviewOutcome.REJECTED,
            NormalizedReviewSemantics.NONPLACING_PREVIEW,
        ),
        (NormalizedReviewOutcome.MALFORMED, NormalizedReviewSemantics.UNKNOWN),
        (NormalizedReviewOutcome.UNKNOWN, NormalizedReviewSemantics.UNKNOWN),
        (
            NormalizedReviewOutcome.AFFIRMATIVE,
            NormalizedReviewSemantics.PLACEMENT_POSSIBLE,
        ),
    ],
)
def test_rejected_malformed_or_unknown_review_never_grants_placement(
    outcome: NormalizedReviewOutcome,
    semantics: NormalizedReviewSemantics,
):
    proposal = _proposal()
    result = validate_normalized_sell_review(
        proposal, _review(proposal, outcome=outcome, semantics=semantics)
    )
    assert result.status is SellReviewValidationStatus.BLOCKED
    assert result.blockers
    assert result.provider_mutation_count == 0
    assert not result.placement_authority_granted
    assert not result.trade_authority_granted

    malformed = validate_normalized_sell_review(proposal, object())  # type: ignore[arg-type]
    assert malformed.status is SellReviewValidationStatus.BLOCKED
    assert SellReviewBlocker.MALFORMED_RESPONSE in malformed.blockers
    assert not malformed.placement_authority_granted


def test_affirmative_nonplacing_review_is_prospective_only():
    proposal = _proposal()
    result = validate_normalized_sell_review(proposal, _review(proposal))
    assert result.status is SellReviewValidationStatus.ACCEPTED_FOR_PROSPECTIVE_CONTRACT
    assert result.provider_mutation_count == 0
    assert not result.placement_authority_granted
    assert not result.trade_authority_granted


def test_reconciled_position_rejects_sellable_quantity_above_position():
    with pytest.raises(ValueError, match="cannot exceed position"):
        _position(broker_sellable_quantity=Decimal("0.123457"))


def _unknown_exit_snapshot() -> OwnershipSnapshot:
    return _owned_snapshot(
        lifecycle=Lifecycle.UNKNOWN,
        effect_disposition=EffectDisposition.MAY_HAVE_OCCURRED,
        exits_used=1,
        exit_local_intent_id="exit-intent-1",
        pending_intent_id="exit-intent-1",
        pending_kind=IntentKind.SAFETY_EXIT,
        pending_requested_quantity=_OWNED,
    )


def _partial_working_exit_snapshot() -> OwnershipSnapshot:
    return _owned_snapshot(
        lifecycle=Lifecycle.RECONCILING,
        effect_disposition=EffectDisposition.CONFIRMED,
        cumulative_sold=Decimal("0.023456"),
        exits_used=1,
        exit_local_intent_id="exit-intent-1",
        exit_provider_order_id="exit-order-1",
        pending_intent_id="exit-intent-1",
        pending_kind=IntentKind.SAFETY_EXIT,
        pending_requested_quantity=_OWNED,
        working_remainder=Decimal("0.1"),
    )


def test_unknown_exit_preserves_last_exact_residual_and_disables_all_orders():
    prior = _position()
    state = require_manual_close(
        last_confirmed_position=prior,
        current_ownership_snapshot=_unknown_exit_snapshot(),
        trigger=ManualCloseTrigger.SELL_UNKNOWN,
        effect_evidence_sha256="2" * 64,
    )
    assert state.exact_residual_quantity == _OWNED
    assert state.current_ownership_snapshot.pending_intent_id == "exit-intent-1"
    assert state.current_ownership_snapshot.effect_disposition is (
        EffectDisposition.MAY_HAVE_OCCURRED
    )
    assert not state.automated_entry_allowed
    assert not state.automated_sell_allowed
    assert not state.automatic_replacement_sell_allowed
    assert not state.automated_order_allowed
    assert state.read_only_reconciliation_allowed

    contradictory = replace(
        _unknown_exit_snapshot(), pending_intent_id="different-exit"
    )
    with pytest.raises(ValueError, match="contradictory exit identities"):
        require_manual_close(
            last_confirmed_position=prior,
            current_ownership_snapshot=contradictory,
            trigger=ManualCloseTrigger.SELL_UNKNOWN,
            effect_evidence_sha256="2" * 64,
        )


def test_partial_exit_latches_exact_current_residual_and_keeps_working_order_evidence():
    prior = _position()
    current = _partial_working_exit_snapshot()
    state = require_manual_close(
        last_confirmed_position=prior,
        current_ownership_snapshot=current,
        trigger=ManualCloseTrigger.SELL_PARTIAL,
        effect_evidence_sha256="3" * 64,
    )
    assert state.exact_residual_quantity == Decimal("0.1")
    assert state.exact_residual_quantity == current.owned_quantity
    assert state.current_ownership_snapshot == current
    assert state.current_ownership_snapshot.pending_intent_id == "exit-intent-1"
    assert state.current_ownership_snapshot.working_remainder == Decimal("0.1")
    assert state.current_ownership_snapshot.entries_used == 1
    assert state.current_ownership_snapshot.entry_reserved_dollars == Decimal("10.00")
    assert state.current_ownership_snapshot.entry_local_intent_id == _ENTRY_LOCAL_ID
    assert (
        state.current_ownership_snapshot.entry_provider_order_id == _ENTRY_PROVIDER_ID
    )
    assert not state.automated_entry_allowed
    assert not state.automated_sell_allowed
    assert not state.automatic_replacement_sell_allowed
    assert not state.automated_order_allowed


def test_blocked_partial_state_latches_manual_close_without_releasing_evidence():
    current = replace(_partial_working_exit_snapshot(), lifecycle=Lifecycle.BLOCKED)
    state = require_manual_close(
        last_confirmed_position=_position(),
        current_ownership_snapshot=current,
        trigger=ManualCloseTrigger.SELL_PARTIAL,
        effect_evidence_sha256="6" * 64,
    )
    assert state.current_ownership_snapshot.lifecycle is Lifecycle.BLOCKED
    assert state.exact_residual_quantity == Decimal("0.1")
    assert not state.automated_order_allowed


@pytest.mark.parametrize(
    "changes",
    [
        {"entries_used": 2},
        {"entry_reserved_dollars": Decimal("9.99")},
        {"entry_local_intent_id": "replaced-entry"},
        {"entry_provider_order_id": "replaced-order"},
    ],
)
def test_partial_exit_cannot_reset_consumed_entry_or_budget(changes: dict[str, object]):
    current = replace(_partial_working_exit_snapshot(), **changes)
    with pytest.raises(ValueError, match="entry consumption"):
        require_manual_close(
            last_confirmed_position=_position(),
            current_ownership_snapshot=current,
            trigger=ManualCloseTrigger.SELL_PARTIAL,
            effect_evidence_sha256="4" * 64,
        )


def test_partial_exit_with_contradictory_pending_exit_id_fails_closed():
    current = replace(
        _partial_working_exit_snapshot(), pending_intent_id="another-exit"
    )
    with pytest.raises(ValueError, match="contradictory exit identities"):
        require_manual_close(
            last_confirmed_position=_position(),
            current_ownership_snapshot=current,
            trigger=ManualCloseTrigger.SELL_PARTIAL,
            effect_evidence_sha256="5" * 64,
        )


def test_review_refusal_cannot_hide_previous_exit_ids_behind_unused_counter():
    current = _owned_snapshot(
        exit_local_intent_id="old-exit-intent",
        exit_provider_order_id="old-exit-order",
    )
    with pytest.raises(ValueError, match="contradictory exit identities"):
        require_manual_close(
            last_confirmed_position=_position(),
            current_ownership_snapshot=current,
            trigger=ManualCloseTrigger.SELL_REVIEW_REJECTED,
            effect_evidence_sha256="8" * 64,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"pending_requested_dollars": Decimal("0.01")},
        {
            "exit_local_intent_id": _ENTRY_LOCAL_ID,
            "pending_intent_id": _ENTRY_LOCAL_ID,
        },
        {"exit_provider_order_id": _ENTRY_PROVIDER_ID},
    ],
)
def test_partial_exit_rejects_dollar_request_or_reused_entry_order_ids(
    changes: dict[str, object],
):
    current = replace(_partial_working_exit_snapshot(), **changes)
    with pytest.raises(ValueError):
        require_manual_close(
            last_confirmed_position=_position(),
            current_ownership_snapshot=current,
            trigger=ManualCloseTrigger.SELL_PARTIAL,
            effect_evidence_sha256="7" * 64,
        )


def test_manual_close_does_not_clear_a_blocked_or_unknown_position_lifecycle():
    for lifecycle in (Lifecycle.UNKNOWN, Lifecycle.BLOCKED):
        with pytest.raises(ValueError, match="known nonblocked lifecycle"):
            _position(ownership_snapshot=_owned_snapshot(lifecycle=lifecycle))
