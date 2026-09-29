"""Architecture-128 R4 pure protected-replacement contract.

This module is intentionally side-effect free. It freezes the exact halted
S5-R10 -> Architecture-127 E6 deployment lineage, fixed production namespace,
admission predicates, two ordered no-replace rename steps, and fail-closed
indeterminate-mutation state machine. Native Windows mutation belongs in a
separate adapter and remains separately authorization-gated.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

PARENT_PATH = r"F:\AITradingBot"
CANONICAL_PATH = PARENT_PATH + r"\D10"

OLD_DEPLOYMENT_ID = "9f3d111b-25bb-5ee4-9abf-f5215a32b826"
NEW_DEPLOYMENT_ID = "d2071f25-5a7c-5293-a28f-5b722c9917a2"

STAGING_PATH = PARENT_PATH + rf"\D10.replacement-{NEW_DEPLOYMENT_ID}.installing"
RETIRED_PATH = PARENT_PATH + rf"\D10.retired-{OLD_DEPLOYMENT_ID}"

HISTORICAL_S5R8_RETIRED_PATH = (
    PARENT_PATH + r"\D10.retired-2fd79986-fb50-5fe4-800a-2d4aa5e7307c"
)
NEW_EVIDENCE_ROOT = STAGING_PATH + r"\evidence"

OLD_FINAL_LEASE_PATH = CANONICAL_PATH + r"\activation.lease.json"
OLD_LEASE_SHA256 = "91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84"
OLD_ACTIVATION_UTC = "2026-09-29T00:45:22.000000Z"
OLD_END_UTC = "2026-10-06T00:45:22.000000Z"
OLD_SOAK_ID = "48f14b13-aa18-5ce8-a0e0-402c867b17b6"

R1_MATERIAL_ROOT = r"F:\AI\temp\arch128-r1-material-r2-20260929-014734"
R1_BYTE_EXACT_WORKTREE = (
    r"F:\AI\worktrees\ai-trading-bot-d10-arch128-r1-0f9551e-byteexact-r2"
)
R2_SIGNING_ROOT = r"F:\AI\temp\arch128-r2-signing-20260929-093116-923952"


@dataclass(frozen=True, slots=True)
class DeploymentIdentity:
    deployment_id: str
    manifest_sha256: str
    executable_file_count: int
    executable_total_bytes: int
    guard_byte_length: int
    guard_sha256: str
    unsigned_attestation_sha256: str
    certified_source_head: str
    certified_source_tree: str
    detached_signature_sha256: str | None = None


OLD_IDENTITY = DeploymentIdentity(
    deployment_id=OLD_DEPLOYMENT_ID,
    manifest_sha256="e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a",
    executable_file_count=306,
    executable_total_bytes=5391245,
    guard_byte_length=69259,
    guard_sha256="37d78c65800a315a12049b6c278addf609589d121e15d31dd9064dc8ec427298",
    unsigned_attestation_sha256=(
        "4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2"
    ),
    certified_source_head="c5cc0b01301600daf17f1114f4451dca2c9d7a1f",
    certified_source_tree="bfacfadaa14315d2d378abcc0f1e4bc7c42034f1",
)

NEW_IDENTITY = DeploymentIdentity(
    deployment_id=NEW_DEPLOYMENT_ID,
    manifest_sha256="080c622035c7c8492a66ba5d5aa9a48c9020933fb16f85a7604010d529bd06e2",
    executable_file_count=307,
    executable_total_bytes=5420008,
    guard_byte_length=112228,
    guard_sha256="ab80233a6ce59a579653008609753441864f74592ac52d12ec65c6dc714eabf7",
    unsigned_attestation_sha256=(
        "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
    ),
    certified_source_head="0f9551e13486ef65b35a5a9633da19081571144b",
    certified_source_tree="1186e92669af100542c055368c1b72495c36bc11",
    detached_signature_sha256=(
        "9dbd3f44f259d338903a2ed2c52512992519f1f420a5825745cc81b677d104e9"
    ),
)


class NamespaceState(StrEnum):
    PRE_STAGE = "PRE_STAGE"
    READY = "READY"
    RETIRED_WINDOW = "RETIRED_WINDOW"
    COMPLETE = "COMPLETE"
    CONFLICTING = "CONFLICTING"


@dataclass(frozen=True, slots=True)
class RootObservation:
    path: str
    present: bool | None
    identity: DeploymentIdentity | None = None


@dataclass(frozen=True, slots=True)
class NamespaceObservation:
    canonical: RootObservation
    staging: RootObservation
    retired: RootObservation
    historical_s5r8_retired_absent: bool
    unexpected_reserved_names_absent: bool


def _identity_exact(observed: DeploymentIdentity, expected: DeploymentIdentity) -> bool:
    return observed == expected and all(
        type(getattr(observed, item.name)) is type(getattr(expected, item.name))
        for item in fields(DeploymentIdentity)
    )


def _root_state(
    observed: RootObservation,
    path: str,
    *,
    old: bool = False,
    new: bool = False,
) -> str | None:
    if (
        type(observed) is not RootObservation
        or type(observed.path) is not str
        or observed.path != path
    ):
        return None
    if observed.present is False and observed.identity is None:
        return "ABSENT"
    if (
        observed.present is not True
        or type(observed.identity) is not DeploymentIdentity
    ):
        return None
    if old and _identity_exact(observed.identity, OLD_IDENTITY):
        return "OLD"
    if new and _identity_exact(observed.identity, NEW_IDENTITY):
        return "NEW"
    return None


def classify_namespace(observation: NamespaceObservation) -> NamespaceState:
    if (
        type(observation) is not NamespaceObservation
        or observation.historical_s5r8_retired_absent is not True
        or observation.unexpected_reserved_names_absent is not True
    ):
        return NamespaceState.CONFLICTING

    canonical = _root_state(
        observation.canonical,
        CANONICAL_PATH,
        old=True,
        new=True,
    )
    staging = _root_state(observation.staging, STAGING_PATH, new=True)
    retired = _root_state(observation.retired, RETIRED_PATH, old=True)

    states = (canonical, staging, retired)
    if states == ("OLD", "ABSENT", "ABSENT"):
        return NamespaceState.PRE_STAGE
    if states == ("OLD", "NEW", "ABSENT"):
        return NamespaceState.READY
    if states == ("ABSENT", "NEW", "OLD"):
        return NamespaceState.RETIRED_WINDOW
    if states == ("NEW", "ABSENT", "OLD"):
        return NamespaceState.COMPLETE
    return NamespaceState.CONFLICTING


@dataclass(frozen=True, slots=True)
class AdmissionFacts:
    administrator_exact: bool
    protected_parent_exact: bool
    old_canonical_exact: bool
    old_final_lease_exact: bool
    old_incident_identity_exact: bool
    scheduler_disabled_nonrunning_exact: bool
    new_staging_exact: bool
    new_staging_signed_trust_exact: bool
    new_evidence_root_exact_empty: bool
    new_activation_lease_absent: bool
    same_volume_exact: bool
    historical_s5r8_retired_absent: bool
    new_retired_destination_absent: bool
    unexpected_reserved_names_absent: bool

    def all_exact(self) -> bool:
        return all(
            type(getattr(self, item.name)) is bool and getattr(self, item.name) is True
            for item in fields(AdmissionFacts)
        )


class RenameStep(StrEnum):
    OLD_TO_RETIRED = "OLD_TO_RETIRED"
    STAGING_TO_CANONICAL = "STAGING_TO_CANONICAL"


class MutationOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    NOT_CALLED = "NOT_CALLED"
    INDETERMINATE = "INDETERMINATE"


class Phase(StrEnum):
    READY_TO_RETIRE_OLD = "READY_TO_RETIRE_OLD"
    READY_TO_PUBLISH_NEW = "READY_TO_PUBLISH_NEW"
    COMPLETE = "COMPLETE"
    STOPPED_INDETERMINATE = "STOPPED_INDETERMINATE"


@dataclass(frozen=True, slots=True)
class ReplacementResult:
    phase: Phase
    old_to_retired: MutationOutcome
    staging_to_canonical: MutationOutcome


def begin_replacement(
    observation: NamespaceObservation,
    facts: AdmissionFacts,
) -> ReplacementResult:
    if (
        type(facts) is not AdmissionFacts
        or not facts.all_exact()
        or classify_namespace(observation) is not NamespaceState.READY
    ):
        raise ValueError("R4 protected replacement admission is not exact")
    return ReplacementResult(
        Phase.READY_TO_RETIRE_OLD,
        MutationOutcome.NOT_CALLED,
        MutationOutcome.NOT_CALLED,
    )


def record_rename(
    result: ReplacementResult,
    step: RenameStep,
    outcome: MutationOutcome,
) -> ReplacementResult:
    if (
        type(result) is not ReplacementResult
        or type(step) is not RenameStep
        or type(outcome) is not MutationOutcome
        or result.phase in (Phase.COMPLETE, Phase.STOPPED_INDETERMINATE)
    ):
        raise ValueError("R4 rename transition is not admissible")

    if step is RenameStep.OLD_TO_RETIRED:
        if (
            result.phase is not Phase.READY_TO_RETIRE_OLD
            or result.old_to_retired is not MutationOutcome.NOT_CALLED
            or result.staging_to_canonical is not MutationOutcome.NOT_CALLED
        ):
            raise ValueError("R4 old-root rename order differs")
        if outcome is MutationOutcome.SUCCESS:
            return ReplacementResult(
                Phase.READY_TO_PUBLISH_NEW,
                MutationOutcome.SUCCESS,
                MutationOutcome.NOT_CALLED,
            )
        return ReplacementResult(
            Phase.STOPPED_INDETERMINATE,
            outcome,
            MutationOutcome.NOT_CALLED,
        )

    if (
        step is not RenameStep.STAGING_TO_CANONICAL
        or result.phase is not Phase.READY_TO_PUBLISH_NEW
        or result.old_to_retired is not MutationOutcome.SUCCESS
        or result.staging_to_canonical is not MutationOutcome.NOT_CALLED
    ):
        raise ValueError("R4 staged-root rename order differs")

    if outcome is MutationOutcome.SUCCESS:
        return ReplacementResult(
            Phase.COMPLETE,
            MutationOutcome.SUCCESS,
            MutationOutcome.SUCCESS,
        )
    return ReplacementResult(
        Phase.STOPPED_INDETERMINATE,
        MutationOutcome.SUCCESS,
        outcome,
    )


def fixed_rename_paths(step: RenameStep) -> tuple[str, str]:
    if step is RenameStep.OLD_TO_RETIRED:
        return CANONICAL_PATH, RETIRED_PATH
    if step is RenameStep.STAGING_TO_CANONICAL:
        return STAGING_PATH, CANONICAL_PATH
    raise ValueError("R4 rename step is not reviewed")
