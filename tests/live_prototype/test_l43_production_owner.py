from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import RuntimeIdentity
from trading_bot.live_prototype.l43_production_owner import (
    EXACT_SELL_REVIEW_CONTRACT_ID,
    ContinuityStatus,
    D34SignalFacts,
    EntryConsumptionFacts,
    ExactOwnedSellProposal,
    FutureInvocationOrdering,
    JournalReplayFacts,
    L43Blocker,
    L43FreshEffectFacts,
    L43Outcome,
    L43ProductionOwner,
    L43Provenance,
    L43SourceIdentity,
    NormalizedSellReview,
    ProductionSourceAuthorityVerifier,
    Q62JournalOrigin,
    Q62ReadOnlyJournalReader,
    RecoveryFacts,
    SourceAuthorityEvidence,
    XnysSessionFacts,
    entry_consumption_valid,
    exact_owned_sell_qualified,
    sanitize_evidence,
    validate_l43_sell_review,
    verify_l43_continuity,
)
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import ReadinessIdentity
from trading_bot.live_prototype.tiny_live_policy import (
    EntryTerminalOutcome,
    ExactSellBlocker,
    ExactSellStatus,
    ManualCloseTrigger,
    NormalizedReviewOutcome,
    NormalizedReviewSemantics,
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
    evaluate_exact_owned_sell_proposal,
    validate_normalized_sell_review,
)


def _sha(char: str) -> str:
    return char * 64


def _git(char: str) -> str:
    return char * 40


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        account_fingerprint=_sha("a"),
        source_head=_git("1"),
        source_tree=_git("2"),
        config_digest=_sha("3"),
        binding_digest=_sha("4"),
        lifecycle_id="00000000-0000-0000-0000-000000000147",
    )


def _origin() -> Q62JournalOrigin:
    return Q62JournalOrigin(
        runtime_identity=_identity(),
        journal_label="q62-origin-journal",
        journal_sha256=_sha("5"),
        initialization_event_sha256=_sha("6"),
        consumed_observation_sha256=_sha("7"),
    )


def _current() -> L43SourceIdentity:
    return L43SourceIdentity(source_head=_git("8"), source_tree=_git("9"))


def _provenance() -> L43Provenance:
    identity = _identity()
    return L43Provenance(
        config_digest=identity.config_digest,
        binding_digest=identity.binding_digest,
        account_fingerprint=identity.account_fingerprint,
    )


class _Authority:
    def verify(self, origin, current):
        return SourceAuthorityEvidence(
            origin_head=origin.runtime_identity.source_head,
            origin_tree=origin.runtime_identity.source_tree,
            candidate_head=current.source_head,
            candidate_tree=current.source_tree,
            strict_descendant=True,
            feature_passed=True,
            prospective_develop_passed=True,
            evidence_sha256=_sha("b"),
        )


class _Reader:
    def __init__(self, facts=None):
        self.facts = facts

    def replay(self, origin):
        if self.facts is not None:
            return self.facts
        return JournalReplayFacts(
            runtime_identity=origin.runtime_identity,
            journal_sha256=origin.journal_sha256,
            initialization_event_sha256=origin.initialization_event_sha256,
            consumed_observation_sha256=origin.consumed_observation_sha256,
            initialization_sequence=0,
            tail_sequence=0,
            tail_sha256=origin.initialization_event_sha256,
        )


def _owner(reader=None) -> L43ProductionOwner:
    return L43ProductionOwner(
        authority_verifier=_Authority(),
        journal_reader=reader or _Reader(),
    )


def _facts(owner, *, signal=SignalDecision.BUY, risk=Decimal("5"), consumed=False):
    origin = _origin()
    current = _current()
    provenance = _provenance()
    continuity = owner.prove_continuity(
        origin=origin,
        current=current,
        provenance=provenance,
    )
    return (
        origin,
        current,
        L43FreshEffectFacts(
            provenance=provenance,
            retained_account_fingerprint=provenance.account_fingerprint,
            current_account_fingerprint=provenance.account_fingerprint,
            positions_digest=_sha("c"),
            relevant_orders_digest=_sha("d"),
            entry_consumed=consumed,
            session=XnysSessionFacts(
                target_session="2026-11-11",
                regular_hours=True,
                session_open=True,
                authority_digest=_sha("e"),
            ),
            signal=D34SignalFacts(
                decision=signal,
                inputs_digest=_sha("f"),
            ),
            recovery=RecoveryFacts(
                reconciled=True,
                unresolved_effects=False,
                terminal_entry=True,
                exact_owned_remainder=Decimal("0"),
                evidence_digest=_sha("b"),
            ),
            requested_entry_risk=risk,
            continuity=continuity,
        ),
    )


_SELL_IDENTITY = ReadinessIdentity(
    source_head=_git("a"),
    source_tree=_git("b"),
    config_digest=_sha("c"),
    account_fingerprint=_sha("d"),
    target_session="2026-11-11",
)
_SELL_OWNED = Decimal("0.123456")
_SELL_NOTIONAL = Decimal("10.00")
_SELL_BINDING = _sha("e")


def _sell_snapshot(**changes):
    values = {
        "account_fingerprint": _SELL_IDENTITY.account_fingerprint,
        "symbol": "SPY",
        "strategy": "BASE_MA35_50_V1",
        "source_head": _SELL_IDENTITY.source_head,
        "source_tree": _SELL_IDENTITY.source_tree,
        "config_digest": _SELL_IDENTITY.config_digest,
        "binding_digest": _SELL_BINDING,
        "lifecycle_id": "l43-life-1",
        "target_session": _SELL_IDENTITY.target_session,
        "lifecycle": Lifecycle.RUNNING,
        "effect_disposition": EffectDisposition.CONFIRMED,
        "baseline_quantity": Decimal("0"),
        "cumulative_bought": _SELL_OWNED,
        "cumulative_sold": Decimal("0"),
        "cumulative_entry_filled_dollars": _SELL_NOTIONAL,
        "entry_reserved_dollars": Decimal("10.00"),
        "working_remainder": Decimal("0"),
        "entries_used": 1,
        "exits_used": 0,
        "entry_local_intent_id": "entry-intent-1",
        "entry_provider_order_id": "entry-order-1",
    }
    values.update(changes)
    return OwnershipSnapshot(**values)


def _sell_position(**changes):
    values = {
        "identity": _SELL_IDENTITY,
        "ownership_snapshot": _sell_snapshot(),
        "broker_position_quantity": _SELL_OWNED,
        "broker_sellable_quantity": _SELL_OWNED,
        "working_order_count": 0,
        "unresolved_order_count": 0,
        "evidence_sha256": _sha("f"),
    }
    values.update(changes)
    return ReconciledOwnedPosition(**values)


def _sell_entry():
    return TerminalEntryEvidence(
        local_intent_id="entry-intent-1",
        provider_order_id="entry-order-1",
        outcome=EntryTerminalOutcome.FILLED,
        requested_usd_cents=1000,
        reserved_usd_cents=1000,
        confirmed_filled_quantity=_SELL_OWNED,
        confirmed_filled_notional=_SELL_NOTIONAL,
    )


def _sell_arguments(quantity=_SELL_OWNED, *, dollar_amount=None):
    return SellOrderArguments(
        side=SellSide.SELL,
        symbol="SPY",
        order_type=SellOrderType.MARKET,
        session=SellSession.REGULAR_HOURS,
        time_in_force=SellTimeInForce.DAY,
        quantity=quantity,
        context=SellOrderContext(
            identity=_SELL_IDENTITY,
            binding_digest=_SELL_BINDING,
            lifecycle_id="l43-life-1",
            entry_local_intent_id="entry-intent-1",
            entry_provider_order_id="entry-order-1",
            exact_owned_remainder=_SELL_OWNED,
            broker_position_quantity=_SELL_OWNED,
            broker_sellable_quantity=_SELL_OWNED,
            terminal_entry_outcome=EntryTerminalOutcome.FILLED,
            reserved_usd_cents=1000,
            confirmed_entry_filled_quantity=_SELL_OWNED,
            confirmed_entry_filled_notional=_SELL_NOTIONAL,
        ),
        dollar_amount=dollar_amount,
    )


def _sell_proposal(*, review=None, placement=None, position=None):
    review_arguments = _sell_arguments() if review is None else review
    return ExactOwnedSellProposal(
        position=_sell_position() if position is None else position,
        terminal_entry=_sell_entry(),
        review_arguments=review_arguments,
        placement_arguments=(review_arguments if placement is None else placement),
    )


def _sell_review(proposal, **changes):
    eligibility = evaluate_exact_owned_sell_proposal(proposal)
    values = {
        "contract_id": EXACT_SELL_REVIEW_CONTRACT_ID,
        "review_id": "review-1",
        "evidence_sha256": _sha("1"),
        "proposal_sha256": eligibility.proposal_sha256,
        "identity": _SELL_IDENTITY,
        "reviewed_arguments": proposal.review_arguments,
        "outcome": NormalizedReviewOutcome.AFFIRMATIVE,
        "semantics": NormalizedReviewSemantics.NONPLACING_PREVIEW,
        "warnings": (),
        "unknown_fields": (),
        "rejection_code": None,
        "provider_order_id": None,
    }
    values.update(changes)
    return NormalizedSellReview(**values)


def test_exact_q62_origin_and_current_source_continuity_is_additive():
    origin = _origin()
    current = _current()
    result = verify_l43_continuity(
        origin=origin,
        current=current,
        provenance=_provenance(),
        authority_verifier=_Authority(),
        journal_reader=_Reader(),
    )

    assert result.status is ContinuityStatus.ACCEPTED
    assert result.accepted
    assert result.origin.runtime_identity.source_head == _git("1")
    assert result.current.source_head == _git("8")
    assert result.origin.runtime_identity.source_head != result.current.source_head


def test_production_constructor_uses_concrete_authority_and_read_only_adapters(
    tmp_path: Path,
):
    owner = L43ProductionOwner.for_production(
        repo_root=Path(__file__).resolve().parents[2],
        journal_path=tmp_path / "q62-origin.jsonl",
        origin=_origin(),
    )

    assert isinstance(owner._authority_verifier, ProductionSourceAuthorityVerifier)
    assert isinstance(owner._journal_reader, Q62ReadOnlyJournalReader)


@pytest.mark.parametrize(
    "change, blocker",
    [
        ("source", L43Blocker.SOURCE_LINEAGE_MISMATCH),
        ("config", L43Blocker.PROVENANCE_MISMATCH),
        ("journal", L43Blocker.JOURNAL_MUTATED),
    ],
)
def test_continuity_mismatches_fail_closed(change, blocker):
    origin = _origin()
    current = _current()
    provenance = _provenance()
    reader = _Reader()
    if change == "source":
        current = L43SourceIdentity(
            source_head=origin.runtime_identity.source_head,
            source_tree=origin.runtime_identity.source_tree,
        )
    elif change == "config":
        provenance = replace(provenance, config_digest=_sha("8"))
    else:
        reader = _Reader(
            replace(
                _Reader().replay(origin),
                tail_sequence=1,
            )
        )

    result = verify_l43_continuity(
        origin=origin,
        current=current,
        provenance=provenance,
        authority_verifier=_Authority(),
        journal_reader=reader,
    )

    assert result.status is ContinuityStatus.BLOCKED
    assert blocker in result.blockers


def test_current_source_cannot_silently_migrate_runtime_identity():
    origin = _origin()
    current = _current()
    migrated = replace(
        origin.runtime_identity,
        source_head=current.source_head,
        source_tree=current.source_tree,
    )
    reader = _Reader(replace(_Reader().replay(origin), runtime_identity=migrated))

    result = verify_l43_continuity(
        origin=origin,
        current=current,
        provenance=_provenance(),
        authority_verifier=_Authority(),
        journal_reader=reader,
    )

    assert L43Blocker.JOURNAL_IDENTITY_MISMATCH in result.blockers


def test_buy_owner_is_source_only_and_grants_zero_authority():
    owner = _owner()
    origin, current, facts = _facts(owner)
    assessment = owner.assess(origin=origin, current=current, facts=facts)

    assert assessment.outcome is L43Outcome.READY_FOR_L43_PROTECTED_EFFECT_REVIEW
    assert assessment.entry_intent_count == 0
    assert assessment.review_count == 0
    assert assessment.placement_count == 0
    assert assessment.cancellation_count == 0
    assert assessment.provider_mutation_count == 0
    assert not assessment.placement_authority
    assert not assessment.trade_authority
    assert not assessment.live_ready
    assert (
        assessment.fresh_effect_facts_sha256
        == dict(assessment.evidence)["fresh_effect_facts_digest"]
    )


def test_non_buy_is_no_action_with_zero_intent_and_effects():
    owner = _owner()
    origin, current, facts = _facts(owner, signal=SignalDecision.HOLD)
    assessment = owner.assess(origin=origin, current=current, facts=facts)

    assert assessment.outcome is L43Outcome.NO_ACTION_SIGNAL
    assert assessment.entry_intent_count == 0
    assert assessment.provider_mutation_count == 0


def test_assessment_evidence_changes_when_any_material_fresh_fact_changes():
    owner = _owner()
    origin, current, facts = _facts(owner)
    baseline = owner.assess(origin=origin, current=current, facts=facts)
    variants = (
        replace(facts, retained_account_fingerprint=_sha("6")),
        replace(facts, positions_digest=_sha("0")),
        replace(facts, relevant_orders_digest=_sha("1")),
        replace(facts, signal=replace(facts.signal, inputs_digest=_sha("2"))),
        replace(facts, signal=replace(facts.signal, decision=SignalDecision.HOLD)),
        replace(
            facts,
            session=replace(
                facts.session,
                target_session="2026-11-12",
                authority_digest=_sha("3"),
            ),
        ),
        replace(facts, session=replace(facts.session, regular_hours=False)),
        replace(facts, session=replace(facts.session, session_open=False)),
        replace(
            facts,
            recovery=replace(facts.recovery, evidence_digest=_sha("4")),
        ),
        replace(facts, recovery=replace(facts.recovery, reconciled=False)),
        replace(facts, recovery=replace(facts.recovery, unresolved_effects=True)),
        replace(facts, recovery=replace(facts.recovery, terminal_entry=False)),
        replace(facts, requested_entry_risk=Decimal("6")),
        replace(facts, entry_consumed=True),
        replace(facts, fresh=False),
        replace(facts, current_account_fingerprint=_sha("5")),
        replace(
            facts,
            provenance=replace(facts.provenance, config_digest=_sha("7")),
        ),
        replace(
            facts,
            provenance=replace(facts.provenance, binding_digest=_sha("8")),
        ),
        replace(
            facts,
            provenance=replace(facts.provenance, account_fingerprint=_sha("9")),
        ),
    )

    for variant in variants:
        changed = owner.assess(origin=origin, current=current, facts=variant)
        assert changed.fresh_effect_facts_sha256 != baseline.fresh_effect_facts_sha256
        assert dict(changed.evidence)["fresh_effect_facts_digest"] == (
            changed.fresh_effect_facts_sha256
        )

    changed_origin = replace(origin, journal_sha256=_sha("0"))
    changed = owner.assess(origin=changed_origin, current=current, facts=facts)
    assert changed.fresh_effect_facts_sha256 != baseline.fresh_effect_facts_sha256

    changed_source = L43SourceIdentity(source_head=_git("0"), source_tree=_git("9"))
    changed = owner.assess(origin=origin, current=changed_source, facts=facts)
    assert changed.fresh_effect_facts_sha256 != baseline.fresh_effect_facts_sha256

    with pytest.raises(ValueError, match="exactly 60"):
        replace(facts.signal, completed_sessions=59)


def test_buy_over_ten_dollars_and_consumed_entry_are_rejected():
    owner = _owner()
    origin, current, over_limit = _facts(owner, risk=Decimal("10.01"))
    assert owner.assess(origin=origin, current=current, facts=over_limit).blockers == (
        L43Blocker.ENTRY_RISK_EXCEEDS_LIMIT,
    )

    origin, current, consumed = _facts(owner, consumed=True)
    assert owner.assess(origin=origin, current=current, facts=consumed).blockers == (
        L43Blocker.ENTRY_ALREADY_CONSUMED,
    )


def test_positive_owned_remainder_blocks_new_entry_readiness():
    owner = _owner()
    origin, current, facts = _facts(owner)
    facts = replace(
        facts,
        recovery=replace(facts.recovery, exact_owned_remainder=Decimal("0.25")),
    )

    assessment = owner.assess(origin=origin, current=current, facts=facts)

    assert assessment.outcome is L43Outcome.BLOCKED
    assert assessment.blockers == (L43Blocker.OWNED_REMAINDER_NOT_FLAT,)


def test_partial_entry_consumes_full_budget_and_never_replenishes():
    facts = EntryConsumptionFacts(
        requested_dollars=Decimal("10"),
        confirmed_fill_quantity=Decimal("0.25"),
        reservation_consumed_dollars=Decimal("10"),
        entry_attempts=1,
        restart_or_date_changed=True,
    )

    assert entry_consumption_valid(facts)
    assert not entry_consumption_valid(replace(facts, entry_attempts=2))
    assert not entry_consumption_valid(
        replace(facts, reservation_consumed_dollars=Decimal("9"))
    )


def test_may_have_occurred_ordering_is_required_and_disarmed():
    ordering = FutureInvocationOrdering("MAY_HAVE_OCCURRED")
    assert not ordering.provider_call_allowed
    with pytest.raises(ValueError, match="effect-disabled"):
        FutureInvocationOrdering("MAY_HAVE_OCCURRED", provider_call_requested=True)


def test_l43_reuses_exact_owned_sell_policy_without_manual_shares_or_rounding():
    proposal = _sell_proposal()
    assert exact_owned_sell_qualified(proposal)
    assert evaluate_exact_owned_sell_proposal(proposal).status is (
        ExactSellStatus.READY_FOR_NONPLACING_REVIEW
    )
    assert not exact_owned_sell_qualified(
        _sell_proposal(review=_sell_arguments(Decimal("0.123457")))
    )


def test_l43_cannot_accept_policy_rejections():
    with pytest.raises(ValueError, match="broker position must equal"):
        _sell_position(broker_position_quantity=Decimal("0.25"))
    with pytest.raises(ValueError, match="terminal order state"):
        _sell_position(working_order_count=1)

    cases = (
        (
            _sell_proposal(review=_sell_arguments(Decimal("0.1234567"))),
            ExactSellBlocker.QUANTITY_SCALE_UNSUPPORTED,
        ),
        (
            _sell_proposal(
                review=_sell_arguments(), placement=_sell_arguments(Decimal("0.2"))
            ),
            ExactSellBlocker.ORDER_ARGUMENTS_MISMATCH,
        ),
        (
            _sell_proposal(review=_sell_arguments(dollar_amount=Decimal("1"))),
            ExactSellBlocker.DOLLAR_SUBSTITUTION_FORBIDDEN,
        ),
        (
            _sell_proposal(
                position=_sell_position(ownership_snapshot=_sell_snapshot(exits_used=1))
            ),
            ExactSellBlocker.EXIT_ALREADY_USED,
        ),
    )
    for candidate, blocker in cases:
        result = evaluate_exact_owned_sell_proposal(candidate)
        assert result.status is ExactSellStatus.BLOCKED
        assert blocker in result.blockers


@pytest.mark.parametrize(
    "change, blocker, trigger",
    [
        (
            {"contract_id": "WRONG_CONTRACT"},
            SellReviewBlocker.CONTRACT_ID_MISMATCH,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ),
        (
            {"proposal_sha256": _sha("2")},
            SellReviewBlocker.PROPOSAL_IDENTITY_MISMATCH,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ),
        (
            {"identity": replace(_SELL_IDENTITY, source_head=_git("0"))},
            SellReviewBlocker.PROPOSAL_IDENTITY_MISMATCH,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ),
        (
            {"reviewed_arguments": _sell_arguments(Decimal("0.2"))},
            SellReviewBlocker.REVIEW_ARGUMENTS_MISMATCH,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ),
        (
            {"outcome": NormalizedReviewOutcome.REJECTED},
            SellReviewBlocker.NON_AFFIRMATIVE_OUTCOME,
            ManualCloseTrigger.SELL_REVIEW_REJECTED,
        ),
        (
            {"rejection_code": "REJECTED"},
            SellReviewBlocker.REJECTION_PRESENT,
            ManualCloseTrigger.SELL_REVIEW_REJECTED,
        ),
        (
            {"warnings": ("PROVIDER_WARNING",)},
            SellReviewBlocker.WARNINGS_PRESENT,
            ManualCloseTrigger.SELL_REVIEW_WARNING,
        ),
        (
            {"unknown_fields": ("EXTRA_FIELD",)},
            SellReviewBlocker.UNKNOWN_FIELDS_PRESENT,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ),
        (
            {"provider_order_id": "provider-order-1"},
            SellReviewBlocker.PLACEMENT_ID_PRESENT,
            ManualCloseTrigger.SELL_REVIEW_MALFORMED,
        ),
    ],
)
def test_review_failures_use_existing_typed_manual_close_contract(
    change, blocker, trigger
):
    proposal = _sell_proposal()
    validation = validate_l43_sell_review(proposal, _sell_review(proposal, **change))

    assert validation.status is SellReviewValidationStatus.BLOCKED
    assert blocker in validation.blockers
    assert validation.manual_close_trigger is trigger
    assert not validation.placement_authority_granted


def test_accepted_normalized_review_still_grants_no_placement_authority():
    proposal = _sell_proposal()
    response = _sell_review(proposal)
    validation = validate_l43_sell_review(proposal, response)

    assert (
        validation.status
        is SellReviewValidationStatus.ACCEPTED_FOR_PROSPECTIVE_CONTRACT
    )
    assert validation == validate_normalized_sell_review(proposal, response)
    assert not validation.manual_close_trigger
    assert not validation.placement_authority_granted
    assert not validation.trade_authority_granted


@pytest.mark.parametrize(
    "trigger",
    [
        ManualCloseTrigger.SELL_REJECTED,
        ManualCloseTrigger.SELL_CANCELED,
        ManualCloseTrigger.SELL_PARTIAL,
        ManualCloseTrigger.SELL_UNKNOWN,
    ],
)
def test_existing_typed_sell_failure_triggers_remain_sticky(trigger):
    assert trigger in {
        ManualCloseTrigger.SELL_REJECTED,
        ManualCloseTrigger.SELL_CANCELED,
        ManualCloseTrigger.SELL_PARTIAL,
        ManualCloseTrigger.SELL_UNKNOWN,
    }


def test_evidence_sanitization_rejects_raw_secrets_and_paths():
    with pytest.raises(ValueError):
        sanitize_evidence({"token": "secret"})
    with pytest.raises(ValueError):
        sanitize_evidence({"label": "F:\\private\\journal"})
    with pytest.raises(ValueError):
        sanitize_evidence({"label": "https://provider.invalid"})
