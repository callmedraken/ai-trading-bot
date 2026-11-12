from dataclasses import replace
from decimal import Decimal

import pytest

from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.durable_state import RuntimeIdentity
from trading_bot.live_prototype.l43_production_owner import (
    ContinuityStatus,
    D34SignalFacts,
    EntryConsumptionFacts,
    ExactOwnedSellFacts,
    FutureInvocationOrdering,
    JournalReplayFacts,
    L43Blocker,
    L43FreshEffectFacts,
    L43Outcome,
    L43ProductionOwner,
    L43Provenance,
    L43SourceIdentity,
    NormalizedReviewFacts,
    Q62JournalOrigin,
    RecoveryFacts,
    ReviewOutcome,
    ReviewSemantics,
    SellOutcome,
    SourceAuthorityEvidence,
    XnysSessionFacts,
    entry_consumption_valid,
    exact_owned_sell_qualified,
    sanitize_evidence,
    sell_outcome_requires_manual_close,
    validate_l43_sell_review,
    verify_l43_continuity,
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


def test_non_buy_is_no_action_with_zero_intent_and_effects():
    owner = _owner()
    origin, current, facts = _facts(owner, signal=SignalDecision.HOLD)
    assessment = owner.assess(origin=origin, current=current, facts=facts)

    assert assessment.outcome is L43Outcome.NO_ACTION_SIGNAL
    assert assessment.entry_intent_count == 0
    assert assessment.provider_mutation_count == 0


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


def test_exact_owned_sell_never_adopts_manual_shares_or_rounds():
    base = ExactOwnedSellFacts(
        bot_owned_remainder=Decimal("0.25"),
        proposed_quantity=Decimal("0.25"),
        broker_position=Decimal("0.25"),
        sellable_quantity=Decimal("0.25"),
        entry_terminal=True,
        review_arguments_digest=_sha("1"),
        placement_arguments_digest=_sha("1"),
    )
    assert exact_owned_sell_qualified(base)
    assert not exact_owned_sell_qualified(
        replace(base, proposed_quantity=Decimal("0.3"))
    )
    assert not exact_owned_sell_qualified(replace(base, broker_position=Decimal("0.2")))
    assert not exact_owned_sell_qualified(replace(base, entry_terminal=False))


@pytest.mark.parametrize(
    "change",
    [
        {"outcome": ReviewOutcome.REJECTED},
        {"outcome": ReviewOutcome.MALFORMED},
        {"semantics": ReviewSemantics.UNKNOWN},
        {"warnings": ("PROVIDER_WARNING",)},
        {"unknown_fields": ("EXTRA_FIELD",)},
        {"provider_order_id_present": True},
    ],
)
def test_review_rejection_malformed_warning_unknown_or_id_requires_manual_close(change):
    facts = NormalizedReviewFacts(
        outcome=ReviewOutcome.AFFIRMATIVE,
        semantics=ReviewSemantics.NONPLACING_PREVIEW,
        review_arguments_digest=_sha("1"),
        placement_arguments_digest=_sha("1"),
    )
    validation = validate_l43_sell_review(replace(facts, **change))

    assert validation.manual_close_required
    assert not validation.placement_authority


def test_accepted_normalized_review_still_grants_no_placement_authority():
    validation = validate_l43_sell_review(
        NormalizedReviewFacts(
            outcome=ReviewOutcome.AFFIRMATIVE,
            semantics=ReviewSemantics.NONPLACING_PREVIEW,
            review_arguments_digest=_sha("1"),
            placement_arguments_digest=_sha("1"),
        )
    )

    assert validation.accepted_for_prospective_contract
    assert not validation.manual_close_required
    assert not validation.placement_authority


@pytest.mark.parametrize(
    "outcome",
    [
        SellOutcome.REJECTED,
        SellOutcome.CANCELED,
        SellOutcome.PARTIAL,
        SellOutcome.UNKNOWN,
    ],
)
def test_sell_failure_is_sticky_manual_close_with_no_replacement(outcome):
    assert sell_outcome_requires_manual_close(outcome)
    assert not sell_outcome_requires_manual_close(SellOutcome.FILLED)


def test_evidence_sanitization_rejects_raw_secrets_and_paths():
    with pytest.raises(ValueError):
        sanitize_evidence({"token": "secret"})
    with pytest.raises(ValueError):
        sanitize_evidence({"label": "F:\\private\\journal"})
    with pytest.raises(ValueError):
        sanitize_evidence({"label": "https://provider.invalid"})
