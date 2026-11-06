from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    Classification,
    FactId,
    FactResult,
    OverallStatus,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.contracts import Lifecycle
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import (
    FreshProof,
    ProofKind,
    ProofStatus,
    Q62Blocker,
    Q62Status,
    ReadinessIdentity,
)
from trading_bot.live_prototype.readiness_operator import (
    Q62EvidenceBundle,
    evaluate_q62_readiness,
)
from trading_bot.live_prototype.recovery_operator import (
    RecoveryObservation,
    reconcile_read_only,
)

_NOW = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)
_EXPIRY = _NOW + timedelta(minutes=10)
_OBSERVATION_DIGEST = "1" * 64


def _identity() -> ReadinessIdentity:
    return ReadinessIdentity(
        source_head="a" * 40,
        source_tree="b" * 40,
        config_digest="c" * 64,
        account_fingerprint="d" * 64,
        target_session="2026-11-06",
    )


def _ownership(identity: ReadinessIdentity, **overrides: object) -> OwnershipSnapshot:
    values: dict[str, object] = {
        "account_fingerprint": identity.account_fingerprint,
        "source_head": identity.source_head,
        "source_tree": identity.source_tree,
        "config_digest": identity.config_digest,
        "target_session": identity.target_session,
        "lifecycle": Lifecycle.DISARMED,
    }
    values.update(overrides)
    return OwnershipSnapshot(**values)  # type: ignore[arg-type]


def _signal_inputs(
    *, basis: str = "ALPACA_ALL_ADJUSTED_PRICE_V1"
) -> CompletedSignalInputs:
    sessions = tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(60))
    return CompletedSignalInputs(
        symbol="SPY",
        selected_sessions=sessions,
        sessions=sessions,
        closes=tuple(Decimal("100.00") for _ in sessions),
        price_basis=basis,
        source_digest="e" * 64,
        as_of=_NOW,
        cutoff=_NOW,
    )


def _capability(
    *, status: OverallStatus = OverallStatus.READY_FOR_L42
) -> CapabilityReport:
    facts = tuple(
        FactResult(
            fact_id=fact_id,
            classification=(
                Classification.DEFER_TO_FIRST_OWNED_POSITION
                if fact_id is FactId.INSTANCE_REVIEW_REQUIRES_POSITION
                else Classification.PROVEN
            ),
            rationale_code="TEST_FACT_PROVEN",
            evidence_sha256=_OBSERVATION_DIGEST,
        )
        for fact_id in FactId
    )
    return CapabilityReport(
        status=status,
        facts=facts,
        account_fingerprint=_identity().account_fingerprint,
        account_type="agentic",
    )


def _bundle() -> Q62EvidenceBundle:
    identity = _identity()
    signal_inputs = _signal_inputs()
    ownership = _ownership(identity)
    observation = RecoveryObservation(
        identity=identity,
        evidence_sha256="2" * 64,
        observed_at=_NOW,
        valid_until=_EXPIRY,
        position_quantity=Decimal("0"),
        working_order_count=0,
        unresolved_effect=False,
    )
    recovery = reconcile_read_only(identity, ownership, observation, as_of=_NOW)
    digests = {
        ProofKind.SOURCE: "3" * 64,
        ProofKind.CONFIGURATION: "4" * 64,
        ProofKind.ACCOUNT: "5" * 64,
        ProofKind.CAPABILITY: _OBSERVATION_DIGEST,
        ProofKind.OWNERSHIP: "6" * 64,
        ProofKind.BUDGET: "7" * 64,
        ProofKind.SESSION: "8" * 64,
        ProofKind.SIGNAL_INPUTS: signal_inputs.digest,
        ProofKind.RECOVERY: observation.evidence_sha256,
    }
    proofs = tuple(
        FreshProof(
            kind=kind,
            status=ProofStatus.PROVEN,
            evidence_sha256=digest,
            observed_at=_NOW,
            valid_until=_EXPIRY,
            identity=identity,
        )
        for kind, digest in digests.items()
    )
    return Q62EvidenceBundle(
        identity=identity,
        proofs=proofs,
        capability=_capability(),
        ownership=ownership,
        signal_inputs=signal_inputs,
        recovery=recovery,
    )


def test_exact_fresh_prerequisites_only_prove_read_only_q62_readiness() -> None:
    report = evaluate_q62_readiness(_bundle(), as_of=_NOW)

    assert report.status is Q62Status.READY_READ_ONLY
    assert report.blockers == ()
    assert report.provider_mutation_count == 0
    assert report.live_readiness_granted is False
    assert report.trade_authority_granted is False


def test_missing_and_duplicate_proofs_fail_closed() -> None:
    bundle = _bundle()
    missing = replace(
        bundle,
        proofs=tuple(
            proof for proof in bundle.proofs if proof.kind is not ProofKind.SOURCE
        ),
    )
    duplicate_source = next(
        proof for proof in bundle.proofs if proof.kind is ProofKind.SOURCE
    )

    assert (
        Q62Blocker.MISSING_PROOF in evaluate_q62_readiness(missing, as_of=_NOW).blockers
    )
    duplicate = replace(bundle, proofs=bundle.proofs + (duplicate_source,))
    assert (
        Q62Blocker.DUPLICATE_PROOF
        in evaluate_q62_readiness(duplicate, as_of=_NOW).blockers
    )


def test_stale_future_and_mismatched_identity_proofs_fail_closed() -> None:
    bundle = _bundle()
    source = next(proof for proof in bundle.proofs if proof.kind is ProofKind.SOURCE)
    stale = replace(
        source,
        observed_at=_NOW - timedelta(seconds=2),
        valid_until=_NOW - timedelta(seconds=1),
    )
    stale_bundle = replace(
        bundle,
        proofs=tuple(stale if proof is source else proof for proof in bundle.proofs),
    )
    assert (
        Q62Blocker.PROOF_NOT_FRESH
        in evaluate_q62_readiness(stale_bundle, as_of=_NOW).blockers
    )

    future = replace(source, observed_at=_NOW + timedelta(seconds=1))
    future_bundle = replace(
        bundle,
        proofs=tuple(future if proof is source else proof for proof in bundle.proofs),
    )
    assert (
        Q62Blocker.PROOF_NOT_FRESH
        in evaluate_q62_readiness(future_bundle, as_of=_NOW).blockers
    )

    drifted = replace(source, identity=replace(_identity(), source_tree="f" * 40))
    drifted_bundle = replace(
        bundle,
        proofs=tuple(drifted if proof is source else proof for proof in bundle.proofs),
    )
    assert (
        Q62Blocker.PROOF_IDENTITY_MISMATCH
        in evaluate_q62_readiness(drifted_bundle, as_of=_NOW).blockers
    )


def test_blocked_l41_official_facts_cannot_pass_q62() -> None:
    bundle = _bundle()
    blocked = replace(bundle, capability=_capability(status=OverallStatus.BLOCKED))

    report = evaluate_q62_readiness(blocked, as_of=_NOW)

    assert report.status is Q62Status.BLOCKED
    assert Q62Blocker.CAPABILITY_UNPROVEN in report.blockers
    assert report.live_readiness_granted is False


def test_spent_or_unbound_budget_and_non_alpaca_inputs_block() -> None:
    bundle = _bundle()
    used = _ownership(
        bundle.identity,
        entries_used=1,
        entry_reserved_dollars=Decimal("10.00"),
        cumulative_bought=Decimal("0.1"),
        entry_provider_order_id="provider-order-1",
    )
    used_bundle = replace(bundle, ownership=used)
    report = evaluate_q62_readiness(used_bundle, as_of=_NOW)
    assert Q62Blocker.BUDGET_UNPROVEN in report.blockers

    mismatched_ownership = _ownership(bundle.identity, account_fingerprint="f" * 64)
    mismatched_bundle = replace(bundle, ownership=mismatched_ownership)
    assert (
        Q62Blocker.OWNERSHIP_UNPROVEN
        in evaluate_q62_readiness(mismatched_bundle, as_of=_NOW).blockers
    )

    robinhood_inputs = _signal_inputs(
        basis="ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1"
    )
    robinhood_bundle = replace(bundle, signal_inputs=robinhood_inputs)
    assert (
        Q62Blocker.SIGNAL_INPUTS_UNPROVEN
        in evaluate_q62_readiness(robinhood_bundle, as_of=_NOW).blockers
    )


def test_account_mismatch_and_ambiguous_recovery_block() -> None:
    bundle = _bundle()
    mismatched_report = replace(bundle.capability, account_fingerprint="9" * 64)
    account_bundle = replace(bundle, capability=mismatched_report)
    assert (
        Q62Blocker.ACCOUNT_MISMATCH
        in evaluate_q62_readiness(account_bundle, as_of=_NOW).blockers
    )

    ambiguous_observation = RecoveryObservation(
        identity=bundle.identity,
        evidence_sha256="a" * 64,
        observed_at=_NOW,
        valid_until=_EXPIRY,
        position_quantity=Decimal("0"),
        working_order_count=1,
        unresolved_effect=True,
    )
    recovery = reconcile_read_only(
        bundle.identity, bundle.ownership, ambiguous_observation, as_of=_NOW
    )
    recovery_bundle = replace(bundle, recovery=recovery)
    report = evaluate_q62_readiness(recovery_bundle, as_of=_NOW)
    assert Q62Blocker.RECOVERY_UNPROVEN in report.blockers
    assert report.status is Q62Status.BLOCKED


def test_non_utc_evaluation_time_blocks() -> None:
    local_time = _NOW.astimezone(timezone(timedelta(hours=-8)))

    report = evaluate_q62_readiness(_bundle(), as_of=local_time)

    assert report.status is Q62Status.BLOCKED
    assert report.blockers == (Q62Blocker.INVALID_EVALUATION_TIME,)
