"""Fail-closed Q62 source evaluator; it performs no provider or broker effects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    Classification,
    FactId,
    OverallStatus,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import ENTRY_BUDGET, OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import (
    FreshProof,
    ProofKind,
    ProofStatus,
    Q62Blocker,
    Q62Status,
    ReadinessIdentity,
    is_current_utc,
)
from trading_bot.live_prototype.recovery_operator import RecoveryReport, RecoveryStatus

_REQUIRED_PROOFS = tuple(ProofKind)


@dataclass(frozen=True, slots=True)
class Q62EvidenceBundle:
    identity: ReadinessIdentity
    proofs: tuple[FreshProof, ...]
    capability: CapabilityReport | None
    ownership: OwnershipSnapshot | None
    signal_inputs: CompletedSignalInputs | None
    recovery: RecoveryReport | None

    def __post_init__(self) -> None:
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("Q62 identity must be ReadinessIdentity")
        if type(self.proofs) is not tuple or any(
            type(item) is not FreshProof for item in self.proofs
        ):
            raise TypeError("Q62 proofs must be a tuple of FreshProof")


@dataclass(frozen=True, slots=True)
class Q62Report:
    status: Q62Status
    blockers: tuple[Q62Blocker, ...]
    source_head: str
    source_tree: str
    config_digest: str
    account_fingerprint: str
    target_session: str
    provider_mutation_count: int = 0
    live_readiness_granted: bool = False
    trade_authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, Q62Status):
            raise TypeError("Q62 status must be typed")
        if type(self.blockers) is not tuple or any(
            not isinstance(item, Q62Blocker) for item in self.blockers
        ):
            raise TypeError("Q62 blockers must be typed")
        if self.status is Q62Status.READY_READ_ONLY and self.blockers:
            raise ValueError("read-only-ready Q62 report cannot contain blockers")
        if (
            type(self.provider_mutation_count) is not int
            or self.provider_mutation_count != 0
            or self.live_readiness_granted
            or self.trade_authority_granted
        ):
            raise ValueError("Q62 source evaluation grants no effect authority")


def evaluate_q62_readiness(bundle: Q62EvidenceBundle, *, as_of: datetime) -> Q62Report:
    """Evaluate fresh exact prerequisites without authenticating references.

    A READY_READ_ONLY result means only that the supplied typed prerequisites
    pass this pure evaluator. It grants neither live readiness nor trade authority.
    """

    if type(bundle) is not Q62EvidenceBundle:
        raise TypeError("bundle must be Q62EvidenceBundle")
    identity = bundle.identity
    blockers: list[Q62Blocker] = []
    if (
        type(as_of) is not datetime
        or as_of.tzinfo is None
        or as_of.utcoffset() != timedelta(0)
    ):
        blockers.append(Q62Blocker.INVALID_EVALUATION_TIME)
    else:
        _check_proofs(bundle.proofs, identity, as_of, blockers)
        _check_capability(bundle.capability, identity, bundle.proofs, blockers)
        _check_ownership(bundle.ownership, identity, blockers)
        _check_budget(bundle.ownership, blockers)
        _check_signal_inputs(bundle.signal_inputs, bundle.proofs, as_of, blockers)
        _check_recovery(bundle.recovery, identity, bundle.proofs, as_of, blockers)

    unique = tuple(dict.fromkeys(blockers))
    return Q62Report(
        Q62Status.BLOCKED if unique else Q62Status.READY_READ_ONLY,
        unique,
        identity.source_head,
        identity.source_tree,
        identity.config_digest,
        identity.account_fingerprint,
        identity.target_session,
    )


def _check_proofs(
    proofs: tuple[FreshProof, ...],
    identity: ReadinessIdentity,
    as_of: datetime,
    blockers: list[Q62Blocker],
) -> None:
    by_kind: dict[ProofKind, list[FreshProof]] = {}
    for proof in proofs:
        by_kind.setdefault(proof.kind, []).append(proof)
    for kind in _REQUIRED_PROOFS:
        matches = by_kind.get(kind, [])
        if not matches:
            blockers.append(Q62Blocker.MISSING_PROOF)
            continue
        if len(matches) != 1:
            blockers.append(Q62Blocker.DUPLICATE_PROOF)
            continue
        proof = matches[0]
        if proof.status is not ProofStatus.PROVEN or proof.evidence_sha256 is None:
            blockers.append(_proof_blocker(kind))
        if proof.identity != identity:
            blockers.append(Q62Blocker.PROOF_IDENTITY_MISMATCH)
        if (
            not is_current_utc(proof.observed_at, as_of=as_of)
            or as_of > proof.valid_until
        ):
            blockers.append(Q62Blocker.PROOF_NOT_FRESH)


def _check_capability(
    capability: CapabilityReport | None,
    identity: ReadinessIdentity,
    proofs: tuple[FreshProof, ...],
    blockers: list[Q62Blocker],
) -> None:
    if type(capability) is not CapabilityReport:
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
        return
    if capability.account_fingerprint != identity.account_fingerprint:
        blockers.append(Q62Blocker.ACCOUNT_MISMATCH)
    if capability.status is not OverallStatus.READY_FOR_L42 or any(
        fact.classification is Classification.BLOCKING_L42 for fact in capability.facts
    ):
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
    if any(
        fact.classification is Classification.DEFER_TO_FIRST_OWNED_POSITION
        and fact.fact_id is not FactId.INSTANCE_REVIEW_REQUIRES_POSITION
        for fact in capability.facts
    ):
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
    capability_proof = _single_proof(proofs, ProofKind.CAPABILITY)
    digests = {fact.evidence_sha256 for fact in capability.facts}
    if (
        capability_proof is None
        or len(digests) != 1
        or None in digests
        or capability_proof.evidence_sha256 not in digests
    ):
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)


def _check_ownership(
    snapshot: OwnershipSnapshot | None,
    identity: ReadinessIdentity,
    blockers: list[Q62Blocker],
) -> None:
    if type(snapshot) is not OwnershipSnapshot:
        blockers.append(Q62Blocker.OWNERSHIP_UNPROVEN)
        return
    if (
        snapshot.account_fingerprint != identity.account_fingerprint
        or snapshot.source_head != identity.source_head
        or snapshot.source_tree != identity.source_tree
        or snapshot.config_digest != identity.config_digest
        or snapshot.target_session != identity.target_session
        or snapshot.symbol != "SPY"
        or snapshot.strategy != "BASE_MA35_50_V1"
    ):
        blockers.append(Q62Blocker.OWNERSHIP_UNPROVEN)
    if (
        snapshot.lifecycle not in (Lifecycle.DISARMED, Lifecycle.STOPPED)
        or snapshot.effect_disposition is EffectDisposition.MAY_HAVE_OCCURRED
        or snapshot.pending_intent_id is not None
        or snapshot.pending_kind is not None
        or snapshot.working_remainder != Decimal("0")
    ):
        blockers.append(Q62Blocker.OWNERSHIP_UNPROVEN)


def _check_budget(
    snapshot: OwnershipSnapshot | None, blockers: list[Q62Blocker]
) -> None:
    if type(snapshot) is not OwnershipSnapshot:
        blockers.append(Q62Blocker.BUDGET_UNPROVEN)
        return
    if (
        snapshot.entry_reserved_dollars != Decimal("0")
        or snapshot.budget_remaining != ENTRY_BUDGET
        or snapshot.entries_used != 0
        or snapshot.exits_used != 0
        or snapshot.cumulative_bought != Decimal("0")
        or snapshot.cumulative_sold != Decimal("0")
        or snapshot.entry_provider_order_id is not None
        or snapshot.exit_provider_order_id is not None
    ):
        blockers.append(Q62Blocker.BUDGET_UNPROVEN)


def _check_signal_inputs(
    inputs: CompletedSignalInputs | None,
    proofs: tuple[FreshProof, ...],
    as_of: datetime,
    blockers: list[Q62Blocker],
) -> None:
    if (
        type(inputs) is not CompletedSignalInputs
        or inputs.symbol != "SPY"
        or inputs.price_basis != "ALPACA_ALL_ADJUSTED_PRICE_V1"
        or len(inputs.sessions) != 60
        or not is_current_utc(inputs.as_of, as_of=as_of)
    ):
        blockers.append(Q62Blocker.SIGNAL_INPUTS_UNPROVEN)
        return
    proof = _single_proof(proofs, ProofKind.SIGNAL_INPUTS)
    if proof is None or proof.evidence_sha256 != inputs.digest:
        blockers.append(Q62Blocker.SIGNAL_INPUTS_UNPROVEN)


def _check_recovery(
    recovery: RecoveryReport | None,
    identity: ReadinessIdentity,
    proofs: tuple[FreshProof, ...],
    as_of: datetime,
    blockers: list[Q62Blocker],
) -> None:
    proof = _single_proof(proofs, ProofKind.RECOVERY)
    if (
        type(recovery) is not RecoveryReport
        or recovery.status is not RecoveryStatus.CLEAN
        or recovery.blockers
        or recovery.identity != identity
        or proof is None
        or proof.evidence_sha256 != recovery.evidence_sha256
        or recovery.observed_at is None
        or recovery.valid_until is None
        or not is_current_utc(recovery.observed_at, as_of=as_of)
        or as_of > recovery.valid_until
        or recovery.working_order_count != 0
        or recovery.observed_position != Decimal("0")
    ):
        blockers.append(Q62Blocker.RECOVERY_UNPROVEN)


def _single_proof(proofs: tuple[FreshProof, ...], kind: ProofKind) -> FreshProof | None:
    matches = tuple(proof for proof in proofs if proof.kind is kind)
    return matches[0] if len(matches) == 1 else None


def _proof_blocker(kind: ProofKind) -> Q62Blocker:
    return {
        ProofKind.ACCOUNT: Q62Blocker.ACCOUNT_MISMATCH,
        ProofKind.CAPABILITY: Q62Blocker.CAPABILITY_UNPROVEN,
        ProofKind.OWNERSHIP: Q62Blocker.OWNERSHIP_UNPROVEN,
        ProofKind.BUDGET: Q62Blocker.BUDGET_UNPROVEN,
        ProofKind.SESSION: Q62Blocker.SESSION_UNPROVEN,
        ProofKind.SIGNAL_INPUTS: Q62Blocker.SIGNAL_INPUTS_UNPROVEN,
        ProofKind.RECOVERY: Q62Blocker.RECOVERY_UNPROVEN,
        ProofKind.SOURCE: Q62Blocker.PROOF_NOT_PROVEN,
        ProofKind.CONFIGURATION: Q62Blocker.PROOF_NOT_PROVEN,
    }[kind]
