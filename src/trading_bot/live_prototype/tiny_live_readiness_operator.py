"""Effect-free Q62 evaluator for the prospective tiny-live prototype."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading_bot.live_prototype.capability_observer import CapabilityReport
from trading_bot.live_prototype.capability_rule_binding_l41r6 import (
    L41R6CompositeReport,
)
from trading_bot.live_prototype.contracts import EffectDisposition
from trading_bot.live_prototype.live_contract import OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import (
    FreshProof,
    ProofKind,
    ProofStatus,
    Q62Blocker,
    Q62Status,
    is_current_utc,
)
from trading_bot.live_prototype.readiness_operator import (
    Q62EvidenceBundle,
    Q62Report,
    evaluate_q62_readiness,
)
from trading_bot.live_prototype.tiny_live_capability_admission import (
    TinyLivePrototypeCapabilityAdmission,
    TinyLivePrototypeCapabilityStatus,
    admit_tiny_live_capabilities,
    exact_l41r6_capability_report_matches,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ZERO = Decimal("0")
_ADMISSION_REJECTED = "TINY_LIVE_CAPABILITY_ADMISSION_REJECTED"
_EXPECTED_HISTORICAL_BLOCKERS = (Q62Blocker.CAPABILITY_UNPROVEN,)


class TinyLiveReadinessStatus(StrEnum):
    READY_FOR_L43_PROTOTYPE_READ_ONLY = "READY_FOR_L43_PROTOTYPE_READ_ONLY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class TinyLiveReadinessReport:
    """Prototype readiness result; it grants no live or trading authority."""

    status: TinyLiveReadinessStatus
    blockers: tuple[Q62Blocker, ...]
    historical_report: Q62Report
    source_head: str
    source_tree: str
    config_digest: str
    account_fingerprint: str
    target_session: str
    capability_admission_digest: str | None = None
    admission_error_code: str | None = None
    provider_mutation_count: int = 0
    live_readiness_granted: bool = False
    trade_authority_granted: bool = False

    def __post_init__(self) -> None:
        if type(self.status) is not TinyLiveReadinessStatus:
            raise TypeError("tiny-live readiness status must be typed")
        if type(self.blockers) is not tuple or any(
            type(item) is not Q62Blocker for item in self.blockers
        ):
            raise TypeError("tiny-live readiness blockers must be typed")
        if type(self.historical_report) is not Q62Report:
            raise TypeError("historical Q62 report is required")
        if self.capability_admission_digest is not None and (
            type(self.capability_admission_digest) is not str
            or _SHA256.fullmatch(self.capability_admission_digest) is None
        ):
            raise ValueError("capability admission digest must be lowercase SHA-256")
        if self.admission_error_code is not None and (
            type(self.admission_error_code) is not str
            or self.admission_error_code != _ADMISSION_REJECTED
        ):
            raise ValueError("admission error code must be source-owned")
        if (
            type(self.provider_mutation_count) is not int
            or self.provider_mutation_count != 0
            or self.live_readiness_granted is not False
            or self.trade_authority_granted is not False
        ):
            raise ValueError("prototype readiness grants no effect authority")
        if self.status is TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY:
            if self.blockers:
                raise ValueError("ready prototype report cannot contain blockers")
            if self.capability_admission_digest is None:
                raise ValueError("ready prototype report requires admission evidence")
            if (
                self.historical_report.status is not Q62Status.BLOCKED
                or self.historical_report.blockers != _EXPECTED_HISTORICAL_BLOCKERS
            ):
                raise ValueError(
                    "ready prototype report requires the expected Q62 block"
                )


def evaluate_q62_tiny_live_readiness(
    bundle: Q62EvidenceBundle,
    *,
    as_of: datetime,
    composite: L41R6CompositeReport,
    consumed_l41_bytes: bytes,
    consumed_l41r5_bytes: bytes,
) -> TinyLiveReadinessReport:
    """Evaluate the additive tiny-live prerequisite policy without effects.

    The unchanged historical evaluator receives the original evidence bundle.
    Its sole accepted blocker is the known L41R6 capability gap; a fresh
    capability proof is independently bound to the prototype admission digest.
    """

    if type(bundle) is not Q62EvidenceBundle:
        raise TypeError("bundle must be Q62EvidenceBundle")

    historical = evaluate_q62_readiness(bundle, as_of=as_of)
    blockers: list[Q62Blocker] = []
    admission: TinyLivePrototypeCapabilityAdmission | None = None
    admission_error_code: str | None = None

    try:
        admission = admit_tiny_live_capabilities(
            composite,
            consumed_l41_bytes=consumed_l41_bytes,
            consumed_l41r5_bytes=consumed_l41r5_bytes,
            account_fingerprint=bundle.identity.account_fingerprint,
        )
    except (TypeError, ValueError):
        admission_error_code = _ADMISSION_REJECTED

    historical_is_expected = (
        historical.status is Q62Status.BLOCKED
        and historical.blockers == _EXPECTED_HISTORICAL_BLOCKERS
    )
    if not historical_is_expected:
        blockers.extend(historical.blockers)
        if historical.status is Q62Status.READY_READ_ONLY or not historical.blockers:
            blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)

    if admission is None:
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
    elif type(admission) is not TinyLivePrototypeCapabilityAdmission:
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
    elif (
        type(admission.status) is not TinyLivePrototypeCapabilityStatus
        or admission.status
        is not TinyLivePrototypeCapabilityStatus.ELIGIBLE_FOR_TINY_LIVE_Q62
    ):
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)

    if type(composite) is not L41R6CompositeReport:
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
    elif (
        type(composite.capability_report) is not CapabilityReport
        or composite.capability_report.account_fingerprint
        != bundle.identity.account_fingerprint
    ):
        blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
        if (
            type(composite.capability_report) is CapabilityReport
            and composite.capability_report.account_fingerprint
            != bundle.identity.account_fingerprint
        ):
            blockers.append(Q62Blocker.ACCOUNT_MISMATCH)

    admission_digest: str | None = None
    if type(admission) is TinyLivePrototypeCapabilityAdmission:
        if (
            type(admission.capability_report) is not CapabilityReport
            or type(bundle.capability) is not CapabilityReport
            or type(composite) is not L41R6CompositeReport
            or type(composite.capability_report) is not CapabilityReport
            or not exact_l41r6_capability_report_matches(
                admission.capability_report, composite.capability_report
            )
            or not exact_l41r6_capability_report_matches(
                bundle.capability, admission.capability_report
            )
        ):
            blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
        if (
            type(admission.account_fingerprint) is not str
            or admission.account_fingerprint != bundle.identity.account_fingerprint
        ):
            blockers.append(Q62Blocker.ACCOUNT_MISMATCH)
        if (
            type(composite) is L41R6CompositeReport
            and type(composite.capability_report) is CapabilityReport
            and composite.capability_report.account_fingerprint
            != bundle.identity.account_fingerprint
        ):
            blockers.append(Q62Blocker.ACCOUNT_MISMATCH)
        if (
            type(admission.admission_digest) is str
            and _SHA256.fullmatch(admission.admission_digest) is not None
        ):
            admission_digest = admission.admission_digest
        else:
            blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)
        if admission_digest is not None and not _capability_proof_matches(
            bundle, as_of=as_of, admission_digest=admission_digest
        ):
            blockers.append(Q62Blocker.CAPABILITY_UNPROVEN)

    blockers.extend(_unused_flat_baseline_blockers(bundle.ownership))
    unique_blockers = tuple(dict.fromkeys(blockers))
    status = (
        TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY
        if historical_is_expected and admission is not None and not unique_blockers
        else TinyLiveReadinessStatus.BLOCKED
    )
    return TinyLiveReadinessReport(
        status=status,
        blockers=unique_blockers,
        historical_report=historical,
        source_head=bundle.identity.source_head,
        source_tree=bundle.identity.source_tree,
        config_digest=bundle.identity.config_digest,
        account_fingerprint=bundle.identity.account_fingerprint,
        target_session=bundle.identity.target_session,
        capability_admission_digest=admission_digest,
        admission_error_code=admission_error_code,
    )


def _capability_proof_matches(
    bundle: Q62EvidenceBundle, *, as_of: datetime, admission_digest: str
) -> bool:
    proofs = tuple(
        proof
        for proof in bundle.proofs
        if type(proof) is FreshProof and proof.kind is ProofKind.CAPABILITY
    )
    if len(proofs) != 1:
        return False
    proof = proofs[0]
    return (
        proof.status is ProofStatus.PROVEN
        and proof.evidence_sha256 == admission_digest
        and proof.identity == bundle.identity
        and is_current_utc(proof.observed_at, as_of=as_of)
        and type(as_of) is datetime
        and as_of.tzinfo is not None
        and as_of.utcoffset() is not None
        and as_of <= proof.valid_until
    )


def _unused_flat_baseline_blockers(
    snapshot: OwnershipSnapshot | None,
) -> tuple[Q62Blocker, ...]:
    if type(snapshot) is not OwnershipSnapshot:
        return (Q62Blocker.OWNERSHIP_UNPROVEN, Q62Blocker.BUDGET_UNPROVEN)

    blockers: list[Q62Blocker] = []
    if (
        snapshot.baseline_quantity != _ZERO
        or snapshot.effect_disposition is not EffectDisposition.NO_EFFECT
        or snapshot.pending_requested_dollars != _ZERO
        or snapshot.pending_requested_quantity != _ZERO
    ):
        blockers.append(Q62Blocker.OWNERSHIP_UNPROVEN)

    if (
        snapshot.cumulative_entry_filled_dollars != _ZERO
        or snapshot.entry_local_intent_id is not None
        or snapshot.exit_local_intent_id is not None
    ):
        blockers.append(Q62Blocker.BUDGET_UNPROVEN)
    return tuple(blockers)
