"""Pure Architecture-125 contract for one inactive D10 replacement lineage.

This module describes observations and in-process transitions. It does not inspect
the host, perform a rename, or grant protected-operation authority.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import re
from dataclasses import dataclass, fields
from enum import StrEnum

from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    ExecutableManifest,
)

PARENT_PATH = r"F:\AITradingBot"
CANONICAL_PATH = PARENT_PATH + r"\D10"
OLD_DEPLOYMENT_ID = "2fd79986-fb50-5fe4-800a-2d4aa5e7307c"
NEW_DEPLOYMENT_ID = "9f3d111b-25bb-5ee4-9abf-f5215a32b826"
STAGING_PATH = PARENT_PATH + rf"\D10.replacement-{NEW_DEPLOYMENT_ID}.installing"
RETIRED_PATH = PARENT_PATH + rf"\D10.retired-{OLD_DEPLOYMENT_ID}"


@dataclass(frozen=True, slots=True)
class DeploymentIdentity:
    deployment_id: str
    manifest_sha256: str
    executable_file_count: int
    executable_total_bytes: int
    guard_byte_length: int
    guard_sha256: str
    unsigned_attestation_sha256: str
    detached_signature_sha256: str | None = None
    certified_source_head: str | None = None
    certified_source_tree: str | None = None
    operator_pin_head: str | None = None
    operator_pin_tree: str | None = None


OLD_IDENTITY = DeploymentIdentity(
    deployment_id=OLD_DEPLOYMENT_ID,
    manifest_sha256="e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a",
    executable_file_count=306,
    executable_total_bytes=5391245,
    guard_byte_length=68411,
    guard_sha256="3b28d0ffeede06a4785a903dbf6a48c12204651ce8a3c2f80cd6a1428efd8d1a",
    unsigned_attestation_sha256="a12ab7788120934ca928919a01b4cfc7a3f6f307fad79ab13a6bfff189aeb3f3",
    detached_signature_sha256="7ae83e28bcd8ab7cb59ab990a7f3b3191f485621aa83f5431f7f25fc32c8b4eb",
)
NEW_IDENTITY = DeploymentIdentity(
    deployment_id=NEW_DEPLOYMENT_ID,
    manifest_sha256=OLD_IDENTITY.manifest_sha256,
    executable_file_count=306,
    executable_total_bytes=5391245,
    guard_byte_length=69259,
    guard_sha256="37d78c65800a315a12049b6c278addf609589d121e15d31dd9064dc8ec427298",
    unsigned_attestation_sha256="4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2",
    certified_source_head="c5cc0b01301600daf17f1114f4451dca2c9d7a1f",
    certified_source_tree="bfacfadaa14315d2d378abcc0f1e4bc7c42034f1",
    operator_pin_head="19c585519daefad917d6326b5180177b63f8e7f0",
    operator_pin_tree="ab0dccdea1e0e6646ba3b68b3afb725a553f68cc",
)


class NamespaceState(StrEnum):
    CLEAN_INITIAL = "CLEAN_INITIAL"
    OLD_CANONICAL = "OLD_CANONICAL"
    OLD_RETIRED = "OLD_RETIRED"
    NEW_CANONICAL = "NEW_CANONICAL"
    CONFLICTING = "CONFLICTING"


@dataclass(frozen=True, slots=True)
class RootObservation:
    """A native adapter's exact path and fully verified identity, or absence.

    ``present=None`` denotes an unreadable or indeterminate observation. A
    present root without the complete frozen identity is never admitted.
    """

    path: str
    present: bool | None
    identity: DeploymentIdentity | None = None


@dataclass(frozen=True, slots=True)
class NamespaceObservation:
    canonical: RootObservation
    staging: RootObservation
    retired: RootObservation
    unexpected_reserved_names_absent: bool


def _exact_identity(observed: DeploymentIdentity, expected: DeploymentIdentity) -> bool:
    return observed == expected and all(
        type(getattr(observed, field.name)) is type(getattr(expected, field.name))
        for field in fields(DeploymentIdentity)
    )


def classify_namespace(observation: NamespaceObservation) -> NamespaceState:
    """Classify only exact path/identity triples; every other input conflicts."""
    if (
        type(observation) is not NamespaceObservation
        or observation.unexpected_reserved_names_absent is not True
    ):
        return NamespaceState.CONFLICTING
    roots = (observation.canonical, observation.staging, observation.retired)
    paths = (CANONICAL_PATH, STAGING_PATH, RETIRED_PATH)
    if any(
        type(root) is not RootObservation
        or type(root.path) is not str
        or root.path != path
        for root, path in zip(roots, paths, strict=True)
    ):
        return NamespaceState.CONFLICTING
    normalized: list[str] = []
    for root in roots:
        if root.present is False and root.identity is None:
            normalized.append("ABSENT")
        elif root.present is True and type(root.identity) is DeploymentIdentity:
            if _exact_identity(root.identity, OLD_IDENTITY):
                normalized.append("OLD")
            elif _exact_identity(root.identity, NEW_IDENTITY):
                normalized.append("NEW")
            else:
                return NamespaceState.CONFLICTING
        else:
            return NamespaceState.CONFLICTING
    return {
        ("OLD", "ABSENT", "ABSENT"): NamespaceState.CLEAN_INITIAL,
        ("OLD", "NEW", "ABSENT"): NamespaceState.OLD_CANONICAL,
        ("ABSENT", "NEW", "OLD"): NamespaceState.OLD_RETIRED,
        ("NEW", "ABSENT", "OLD"): NamespaceState.NEW_CANONICAL,
    }.get(tuple(normalized), NamespaceState.CONFLICTING)


@dataclass(frozen=True, slots=True)
class AdmissionFacts:
    administrator_exact: bool
    protected_parent_exact: bool
    old_canonical_exact: bool
    new_staging_exact: bool
    activation_and_cache_absent: bool
    unexpected_reserved_names_absent: bool
    d5_capture_only_scheduler_exact: bool
    no_prior_d10_activation_or_scheduler_mutation: bool
    same_local_ntfs_volume: bool
    staging_verified_before_old_mutation: bool
    final_revalidation_complete: bool

    def all_exact(self) -> bool:
        return all(
            value is True
            for value in (
                self.administrator_exact,
                self.protected_parent_exact,
                self.old_canonical_exact,
                self.new_staging_exact,
                self.activation_and_cache_absent,
                self.unexpected_reserved_names_absent,
                self.d5_capture_only_scheduler_exact,
                self.no_prior_d10_activation_or_scheduler_mutation,
                self.same_local_ntfs_volume,
                self.staging_verified_before_old_mutation,
                self.final_revalidation_complete,
            )
        )


@dataclass(frozen=True, slots=True)
class PostPublicationFacts:
    new_canonical_exact: bool
    staging_absent: bool
    old_retired_exact: bool
    canonical_trust_absent: bool
    activation_and_cache_absent: bool
    d5_capture_only_scheduler_exact: bool
    protected_parent_exact: bool
    same_local_ntfs_volume: bool
    unexpected_reserved_names_absent: bool

    def all_exact(self) -> bool:
        return all(
            value is True
            for value in (
                self.new_canonical_exact,
                self.staging_absent,
                self.old_retired_exact,
                self.canonical_trust_absent,
                self.activation_and_cache_absent,
                self.d5_capture_only_scheduler_exact,
                self.protected_parent_exact,
                self.same_local_ntfs_volume,
                self.unexpected_reserved_names_absent,
            )
        )


class RenameStep(StrEnum):
    OLD_TO_RETIRED = "OLD_TO_RETIRED"
    STAGING_TO_CANONICAL = "STAGING_TO_CANONICAL"


class RenameFailureStage(StrEnum):
    PRE_CALL = "PRE_CALL"
    NATIVE_FALSE = "NATIVE_FALSE"
    NATIVE_STATUS = "NATIVE_STATUS"
    POST_CALL_VERIFY = "POST_CALL_VERIFY"
    CLOSE_AMBIGUITY = "CLOSE_AMBIGUITY"


@dataclass(frozen=True, slots=True)
class RenameDiagnostic:
    """Closed failure evidence only; never mutation or retry authority."""

    step: RenameStep
    stage: RenameFailureStage
    win32_error: int | None = None
    ntstatus: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.step) is not RenameStep
            or type(self.stage) is not RenameFailureStage
            or (
                self.stage is RenameFailureStage.NATIVE_FALSE
                and (
                    type(self.win32_error) is not int
                    or not 0 <= self.win32_error <= 0xFFFFFFFF
                )
            )
            or (
                self.stage is not RenameFailureStage.NATIVE_FALSE
                and self.win32_error is not None
            )
            or (
                self.stage is RenameFailureStage.NATIVE_STATUS
                and (
                    type(self.ntstatus) is not int
                    or not 0 <= self.ntstatus <= 0xFFFFFFFF
                )
            )
            or (
                self.stage is not RenameFailureStage.NATIVE_STATUS
                and self.ntstatus is not None
            )
        ):
            raise ValueError("rename diagnostic requires closed bounded evidence")


@dataclass(frozen=True, slots=True)
class RenamePlan:
    step: RenameStep
    source_path: str
    destination_path: str
    destination_must_be_absent: bool = True
    replace_existing: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.step) is not RenameStep
            or type(self.source_path) is not str
            or type(self.destination_path) is not str
            or (self.step, self.source_path, self.destination_path)
            not in (
                (RenameStep.OLD_TO_RETIRED, CANONICAL_PATH, RETIRED_PATH),
                (RenameStep.STAGING_TO_CANONICAL, STAGING_PATH, CANONICAL_PATH),
            )
            or self.destination_must_be_absent is not True
            or self.replace_existing is not False
        ):
            raise ValueError(
                "rename plan must use the exact destination-absent lineage"
            )


class MutationOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    INDETERMINATE = "INDETERMINATE"


class Phase(StrEnum):
    READY_TO_RETIRE_OLD = "READY_TO_RETIRE_OLD"
    READY_TO_PUBLISH_NEW = "READY_TO_PUBLISH_NEW"
    VERIFY_PUBLICATION = "VERIFY_PUBLICATION"
    BLOCKED = "BLOCKED"
    PASS = "PASS"


class BlockReason(StrEnum):
    NAMESPACE_CONFLICT = "NAMESPACE_CONFLICT"
    SEPARATE_RECOVERY_REQUIRED = "SEPARATE_RECOVERY_REQUIRED"
    ADMISSION_FAILED = "ADMISSION_FAILED"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    INDETERMINATE_MUTATION = "INDETERMINATE_MUTATION"
    POST_PUBLICATION_VERIFICATION_FAILED = "POST_PUBLICATION_VERIFICATION_FAILED"
    STAGING_FAILED = "STAGING_FAILED"


@dataclass(frozen=True, slots=True)
class ReplacementResult:
    phase: Phase
    highest_definitely_completed_state: NamespaceState
    completed_renames: tuple[RenameStep, ...] = ()
    reason_code: BlockReason | None = None
    rename_diagnostic: RenameDiagnostic | None = None

    def __post_init__(self) -> None:
        if (
            type(self.phase) is not Phase
            or type(self.highest_definitely_completed_state) is not NamespaceState
            or type(self.completed_renames) is not tuple
            or any(type(step) is not RenameStep for step in self.completed_renames)
        ):
            raise ValueError("replacement result contains unrecognized evidence")
        if self.rename_diagnostic is not None and (
            type(self.rename_diagnostic) is not RenameDiagnostic
            or self.phase is not Phase.BLOCKED
            or self.reason_code is not BlockReason.INDETERMINATE_MUTATION
            or self.rename_diagnostic.step
            is not (
                RenameStep.OLD_TO_RETIRED
                if self.completed_renames == ()
                else RenameStep.STAGING_TO_CANONICAL
            )
        ):
            raise ValueError("rename diagnostic is only indeterminate-step evidence")
        expected = {
            Phase.READY_TO_RETIRE_OLD: (NamespaceState.OLD_CANONICAL, ()),
            Phase.READY_TO_PUBLISH_NEW: (
                NamespaceState.OLD_RETIRED,
                (RenameStep.OLD_TO_RETIRED,),
            ),
            Phase.VERIFY_PUBLICATION: (
                NamespaceState.NEW_CANONICAL,
                (RenameStep.OLD_TO_RETIRED, RenameStep.STAGING_TO_CANONICAL),
            ),
            Phase.PASS: (
                NamespaceState.NEW_CANONICAL,
                (RenameStep.OLD_TO_RETIRED, RenameStep.STAGING_TO_CANONICAL),
            ),
        }
        if self.phase is Phase.BLOCKED:
            if type(self.reason_code) is not BlockReason:
                raise ValueError("blocked result requires a closed reason code")
            allowed = {
                BlockReason.NAMESPACE_CONFLICT: {(NamespaceState.CONFLICTING, ())},
                BlockReason.SEPARATE_RECOVERY_REQUIRED: {
                    (NamespaceState.OLD_CANONICAL, ()),
                    (NamespaceState.OLD_RETIRED, ()),
                    (NamespaceState.NEW_CANONICAL, ()),
                },
                BlockReason.ADMISSION_FAILED: {
                    (NamespaceState.CLEAN_INITIAL, ()),
                    (NamespaceState.OLD_CANONICAL, ()),
                },
                BlockReason.INVALID_TRANSITION: {
                    (NamespaceState.CONFLICTING, ()),
                    (NamespaceState.CLEAN_INITIAL, ()),
                    (NamespaceState.OLD_CANONICAL, ()),
                    (NamespaceState.OLD_RETIRED, ()),
                    (NamespaceState.NEW_CANONICAL, ()),
                    (NamespaceState.OLD_RETIRED, (RenameStep.OLD_TO_RETIRED,)),
                    (
                        NamespaceState.NEW_CANONICAL,
                        (RenameStep.OLD_TO_RETIRED, RenameStep.STAGING_TO_CANONICAL),
                    ),
                    (
                        NamespaceState.OLD_RETIRED,
                        (RenameStep.OLD_TO_RETIRED, RenameStep.STAGING_TO_CANONICAL),
                    ),
                },
                BlockReason.INDETERMINATE_MUTATION: {
                    (NamespaceState.OLD_CANONICAL, ()),
                    (NamespaceState.OLD_RETIRED, (RenameStep.OLD_TO_RETIRED,)),
                },
                BlockReason.POST_PUBLICATION_VERIFICATION_FAILED: {
                    (
                        NamespaceState.NEW_CANONICAL,
                        (RenameStep.OLD_TO_RETIRED, RenameStep.STAGING_TO_CANONICAL),
                    ),
                },
                BlockReason.STAGING_FAILED: {
                    (NamespaceState.CLEAN_INITIAL, ()),
                    (NamespaceState.OLD_CANONICAL, ()),
                    (NamespaceState.CONFLICTING, ()),
                },
            }
            if (
                self.highest_definitely_completed_state,
                self.completed_renames,
            ) not in allowed[self.reason_code]:
                raise ValueError("invalid blocked transition evidence")
        elif (
            self.phase not in expected
            or (self.highest_definitely_completed_state, self.completed_renames)
            != expected[self.phase]
            or self.reason_code is not None
        ):
            raise ValueError("invalid replacement phase or transition evidence")

    @property
    def next_rename(self) -> RenameStep | None:
        if self.phase is Phase.READY_TO_RETIRE_OLD:
            return RenameStep.OLD_TO_RETIRED
        if self.phase is Phase.READY_TO_PUBLISH_NEW:
            return RenameStep.STAGING_TO_CANONICAL
        return None

    @property
    def rename_plan(self) -> RenamePlan | None:
        """Expose only the next fixed, destination-absent rename."""
        if self.phase is Phase.READY_TO_RETIRE_OLD:
            return RenamePlan(RenameStep.OLD_TO_RETIRED, CANONICAL_PATH, RETIRED_PATH)
        if self.phase is Phase.READY_TO_PUBLISH_NEW:
            return RenamePlan(
                RenameStep.STAGING_TO_CANONICAL, STAGING_PATH, CANONICAL_PATH
            )
        return None

    @property
    def retirement_cleanup_authority(self) -> str:
        return "NONE"

    def canonical_transcript(self) -> bytes:
        """Emit only closed enums and source-owned facts, never raw host data."""
        if self.phase not in (Phase.PASS, Phase.BLOCKED):
            raise ValueError("only terminal results have transcripts")
        value: dict[str, object] = {
            "schema": "personal-desktop-d10-protected-replacement/v1",
            "operation": "P125-R1",
            "status": "PASS" if self.phase is Phase.PASS else "BLOCKED",
            "highest_definitely_completed_namespace_state": (
                self.highest_definitely_completed_state.value
            ),
            "completed_renames": [step.value for step in self.completed_renames],
            "activation_authority": "NONE",
            "scheduler_authority": "NONE",
            "trading_authority": "NONE",
            "retirement_cleanup_authority": "NONE",
        }
        if self.phase is Phase.PASS:
            value.update(
                {
                    "old_deployment_id": OLD_DEPLOYMENT_ID,
                    "new_deployment_id": NEW_DEPLOYMENT_ID,
                    "old_guard_sha256": OLD_IDENTITY.guard_sha256,
                    "new_guard_sha256": NEW_IDENTITY.guard_sha256,
                    "manifest_sha256": NEW_IDENTITY.manifest_sha256,
                    "executable_file_count": NEW_IDENTITY.executable_file_count,
                    "executable_total_bytes": NEW_IDENTITY.executable_total_bytes,
                    "canonical_path": CANONICAL_PATH,
                    "staging_path": STAGING_PATH,
                    "retired_path": RETIRED_PATH,
                    "scheduler_disposition": "D5_CAPTURE_ONLY_PREDECESSOR",
                    "activation_lease_disposition": "ABSENT",
                    "canonical_trust_disposition": "ABSENT",
                    "post_publication_canonical_verification": "PASS",
                    "retired_tree_verification": "PASS",
                }
            )
        else:
            value["reason_code"] = self.reason_code.value
            if self.rename_diagnostic is not None:
                value["rename_diagnostic"] = {
                    "stage": self.rename_diagnostic.stage.value,
                    "step": self.rename_diagnostic.step.value,
                    **(
                        {"ntstatus": self.rename_diagnostic.ntstatus}
                        if self.rename_diagnostic.stage
                        is RenameFailureStage.NATIVE_STATUS
                        else {"win32_error": self.rename_diagnostic.win32_error}
                    ),
                }
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("ascii")


def begin_replacement(
    observation: NamespaceObservation, facts: AdmissionFacts
) -> ReplacementResult:
    """Admit only a freshly verified old canonical plus complete new staging."""
    state = classify_namespace(observation)
    if state in (NamespaceState.OLD_RETIRED, NamespaceState.NEW_CANONICAL):
        return ReplacementResult(
            Phase.BLOCKED, state, reason_code=BlockReason.SEPARATE_RECOVERY_REQUIRED
        )
    if state is NamespaceState.CONFLICTING:
        return ReplacementResult(
            Phase.BLOCKED, state, reason_code=BlockReason.NAMESPACE_CONFLICT
        )
    if (
        state is not NamespaceState.OLD_CANONICAL
        or type(facts) is not AdmissionFacts
        or not facts.all_exact()
    ):
        return ReplacementResult(
            Phase.BLOCKED, state, reason_code=BlockReason.ADMISSION_FAILED
        )
    return ReplacementResult(Phase.READY_TO_RETIRE_OLD, state)


def record_rename(
    result: ReplacementResult,
    step: RenameStep,
    outcome: MutationOutcome,
    diagnostic: RenameDiagnostic | None = None,
) -> ReplacementResult:
    """Advance only on an explicit success in this invocation; never retry."""
    if diagnostic is not None and (
        type(diagnostic) is not RenameDiagnostic
        or diagnostic.step is not step
        or outcome is not MutationOutcome.INDETERMINATE
    ):
        raise ValueError("diagnostic cannot accompany success or another step")
    if type(result) is not ReplacementResult or result.next_rename is not step:
        state = (
            result.highest_definitely_completed_state
            if type(result) is ReplacementResult
            else NamespaceState.CONFLICTING
        )
        completed = (
            result.completed_renames if type(result) is ReplacementResult else ()
        )
        return ReplacementResult(
            Phase.BLOCKED, state, completed, BlockReason.INVALID_TRANSITION
        )
    if outcome is not MutationOutcome.SUCCESS:
        return ReplacementResult(
            Phase.BLOCKED,
            result.highest_definitely_completed_state,
            result.completed_renames,
            BlockReason.INDETERMINATE_MUTATION,
            diagnostic,
        )
    if step is RenameStep.OLD_TO_RETIRED:
        return ReplacementResult(
            Phase.READY_TO_PUBLISH_NEW,
            NamespaceState.OLD_RETIRED,
            (RenameStep.OLD_TO_RETIRED,),
        )
    return ReplacementResult(
        Phase.VERIFY_PUBLICATION,
        NamespaceState.NEW_CANONICAL,
        (RenameStep.OLD_TO_RETIRED, RenameStep.STAGING_TO_CANONICAL),
    )


def verify_publication(
    result: ReplacementResult,
    observation: NamespaceObservation,
    facts: PostPublicationFacts,
) -> ReplacementResult:
    """PASS requires fresh exact post-rename verification, not just API success."""
    if (
        type(result) is not ReplacementResult
        or result.phase is not Phase.VERIFY_PUBLICATION
    ):
        state = (
            result.highest_definitely_completed_state
            if type(result) is ReplacementResult
            else NamespaceState.CONFLICTING
        )
        completed = (
            result.completed_renames if type(result) is ReplacementResult else ()
        )
        return ReplacementResult(
            Phase.BLOCKED, state, completed, BlockReason.INVALID_TRANSITION
        )
    if (
        classify_namespace(observation) is not NamespaceState.NEW_CANONICAL
        or type(facts) is not PostPublicationFacts
        or not facts.all_exact()
    ):
        return ReplacementResult(
            Phase.BLOCKED,
            result.highest_definitely_completed_state,
            result.completed_renames,
            BlockReason.POST_PUBLICATION_VERIFICATION_FAILED,
        )
    return ReplacementResult(
        Phase.PASS, NamespaceState.NEW_CANONICAL, result.completed_renames
    )


_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class CleanupState(StrEnum):
    FULL_RETIRED = "FULL_RETIRED"
    PARTIAL_RETIRED = "PARTIAL_RETIRED"
    RETIRED_ABSENT = "RETIRED_ABSENT"
    CONFLICTING = "CONFLICTING"


class CleanupPhase(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


class CleanupBlockReason(StrEnum):
    NAMESPACE_CONFLICT = "NAMESPACE_CONFLICT"
    SEPARATE_RECOVERY_REQUIRED = "SEPARATE_RECOVERY_REQUIRED"
    ADMISSION_FAILED = "ADMISSION_FAILED"
    INDETERMINATE_DELETE = "INDETERMINATE_DELETE"
    POST_CLEANUP_VERIFICATION_FAILED = "POST_CLEANUP_VERIFICATION_FAILED"


class CleanupOperation(StrEnum):
    R1E = "P125-R1E"
    R1I = "P125-R1I"


class DeleteFailureStage(StrEnum):
    PRE_CALL = "PRE_CALL"
    NATIVE_FALSE = "NATIVE_FALSE"
    TARGET_CLOSE_AMBIGUITY = "TARGET_CLOSE_AMBIGUITY"
    POST_CALL_VERIFY = "POST_CALL_VERIFY"
    PARENT_CLOSE_AMBIGUITY = "PARENT_CLOSE_AMBIGUITY"


@dataclass(frozen=True, slots=True)
class DeleteDiagnostic:
    """Closed evidence for one source-owned plan index; no retry authority."""

    target_index: int
    stage: DeleteFailureStage
    win32_error: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.target_index) is not int
            or not 0 <= self.target_index < 4096
            or type(self.stage) is not DeleteFailureStage
            or (
                self.stage is DeleteFailureStage.NATIVE_FALSE
                and (
                    type(self.win32_error) is not int
                    or not 0 <= self.win32_error <= 0xFFFFFFFF
                )
            )
            or (
                self.stage is not DeleteFailureStage.NATIVE_FALSE
                and self.win32_error is not None
            )
        ):
            raise ValueError("delete diagnostic requires closed bounded evidence")


@dataclass(frozen=True, slots=True)
class RetiredCleanupTarget:
    path: str
    directory: bool
    byte_length: int | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.path) is not str
            or (
                self.path != RETIRED_PATH
                and not self.path.startswith(RETIRED_PATH + "\\")
            )
            or ntpath.normpath(self.path) != self.path
            or type(self.directory) is not bool
            or (
                self.directory
                and (self.byte_length is not None or self.sha256 is not None)
            )
            or (
                not self.directory
                and (
                    type(self.byte_length) is not int
                    or self.byte_length < 0
                    or type(self.sha256) is not str
                    or _HEX_SHA256.fullmatch(self.sha256) is None
                )
            )
        ):
            raise ValueError("retired cleanup target is outside the fixed lineage")


@dataclass(frozen=True, slots=True)
class RetiredCleanupPlan:
    targets: tuple[RetiredCleanupTarget, ...]
    directory_children: tuple[tuple[str, tuple[str, ...]], ...]
    manifest_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.targets) is not tuple
            or not self.targets
            or any(type(target) is not RetiredCleanupTarget for target in self.targets)
            or type(self.directory_children) is not tuple
            or any(
                type(item) is not tuple or len(item) != 2
                for item in self.directory_children
            )
        ):
            raise ValueError("retired cleanup plan is not exact")
        paths = tuple(target.path for target in self.targets)
        directory_paths = {target.path for target in self.targets if target.directory}
        children = dict(self.directory_children)
        if (
            self.targets[-1] != RetiredCleanupTarget(RETIRED_PATH, True)
            or len(paths) != len(set(paths))
            or len(paths) != len({path.casefold() for path in paths})
            or len(children) != len(self.directory_children)
            or set(children) != directory_paths
            or any(
                type(names) is not tuple
                or names != tuple(sorted(names))
                or len(names) != len(set(names))
                for names in children.values()
            )
            or self.manifest_sha256 != OLD_IDENTITY.manifest_sha256
        ):
            raise ValueError("retired cleanup plan is not exact")

    def children_of(self, path: str) -> tuple[str, ...]:
        return dict(self.directory_children)[path]


def build_retired_cleanup_plan(
    manifest: ExecutableManifest,
    attestation_bytes: bytes,
    signature_bytes: bytes,
) -> RetiredCleanupPlan:
    """Freeze only the historical signed-manifest targets, in deletion order."""
    if (
        type(manifest) is not ExecutableManifest
        or manifest.digest != OLD_IDENTITY.manifest_sha256
        or len(manifest.entries) != OLD_IDENTITY.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != OLD_IDENTITY.executable_total_bytes
        or type(attestation_bytes) is not bytes
        or not attestation_bytes
        or hashlib.sha256(attestation_bytes).hexdigest()
        != OLD_IDENTITY.unsigned_attestation_sha256
        or type(signature_bytes) is not bytes
        or len(signature_bytes) != 64
        or hashlib.sha256(signature_bytes).hexdigest()
        != OLD_IDENTITY.detached_signature_sha256
    ):
        raise ValueError("historical signed manifest or trust is not exact")
    source = RETIRED_PATH + r"\source"
    directories: set[str] = set()
    targets: list[RetiredCleanupTarget] = []
    for entry in manifest.entries:
        parts = entry.relative_path.split("/")
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise ValueError("manifest path is not a fixed source target")
        parent = source
        for part in parts[:-1]:
            parent += "\\" + part
            directories.add(parent)
        targets.append(
            RetiredCleanupTarget(
                source + "\\" + entry.relative_path.replace("/", "\\"),
                False,
                entry.byte_length,
                entry.sha256,
            )
        )
    targets.extend(
        (
            RetiredCleanupTarget(
                RETIRED_PATH + r"\launch-guard.py",
                False,
                OLD_IDENTITY.guard_byte_length,
                OLD_IDENTITY.guard_sha256,
            ),
            RetiredCleanupTarget(
                RETIRED_PATH + r"\deployment.attestation.json",
                False,
                len(attestation_bytes),
                OLD_IDENTITY.unsigned_attestation_sha256,
            ),
            RetiredCleanupTarget(
                RETIRED_PATH + r"\deployment.attestation.sig",
                False,
                len(signature_bytes),
                OLD_IDENTITY.detached_signature_sha256,
            ),
            RetiredCleanupTarget(
                RETIRED_PATH + r"\executable-manifest.json",
                False,
                len(manifest.canonical_bytes()),
                OLD_IDENTITY.manifest_sha256,
            ),
        )
    )
    targets.extend(
        RetiredCleanupTarget(path, True)
        for path in sorted(directories, key=lambda path: (-path.count("\\"), path))
    )
    targets.extend(
        (RetiredCleanupTarget(source, True), RetiredCleanupTarget(RETIRED_PATH, True))
    )
    children: dict[str, list[str]] = {
        target.path: [] for target in targets if target.directory
    }
    for target in targets:
        if target.path == RETIRED_PATH:
            continue
        parent = ntpath.dirname(target.path)
        if parent not in children:
            raise ValueError("manifest target parent is not in the fixed plan")
        children[parent].append(ntpath.basename(target.path))
    return RetiredCleanupPlan(
        tuple(targets),
        tuple((path, tuple(sorted(names))) for path, names in sorted(children.items())),
        manifest.digest,
    )


R1I_PLAN_TARGET_COUNT = 337
R1I_MISSING_PREFIX_COUNT = 1
R1I_MISSING_RELATIVE_TARGET = (
    r"source\scripts\run_personal_desktop_unattended_one_week_soak.py"
)


def require_retired_recovery_plan(plan: RetiredCleanupPlan) -> None:
    """Admit only the frozen incident plan shape, never a caller-selected prefix."""
    if (
        type(plan) is not RetiredCleanupPlan
        or len(plan.targets) != R1I_PLAN_TARGET_COUNT
        or plan.targets[0].path != RETIRED_PATH + "\\" + R1I_MISSING_RELATIVE_TARGET
        or plan.targets[0].directory is not False
    ):
        raise ValueError("retired recovery plan is outside the fixed incident")


@dataclass(frozen=True, slots=True)
class CleanupResult:
    phase: CleanupPhase
    state: CleanupState
    completed_targets: int = 0
    reason_code: CleanupBlockReason | None = None
    delete_diagnostic: DeleteDiagnostic | None = None
    operation: CleanupOperation = CleanupOperation.R1E

    def __post_init__(self) -> None:
        if (
            type(self.phase) is not CleanupPhase
            or type(self.state) is not CleanupState
            or type(self.completed_targets) is not int
            or not 0 <= self.completed_targets <= 4096
            or (
                self.phase is CleanupPhase.PASS
                and (
                    self.state is not CleanupState.RETIRED_ABSENT
                    or self.reason_code is not None
                )
            )
            or (
                self.phase is CleanupPhase.BLOCKED
                and type(self.reason_code) is not CleanupBlockReason
            )
        ):
            raise ValueError("cleanup result contains unrecognized evidence")
        if type(self.operation) is not CleanupOperation or (
            self.delete_diagnostic is not None
            and (
                type(self.delete_diagnostic) is not DeleteDiagnostic
                or self.phase is not CleanupPhase.BLOCKED
                or self.reason_code is not CleanupBlockReason.INDETERMINATE_DELETE
                or self.delete_diagnostic.target_index != self.completed_targets
            )
        ):
            raise ValueError("delete diagnostic is only indeterminate-target evidence")

    def canonical_transcript(self) -> bytes:
        """Emit only closed cleanup facts; never expose native observations."""
        passed = self.phase is CleanupPhase.PASS
        value: dict[str, object] = {
            "schema": "personal-desktop-d10-retired-cleanup/v1",
            "operation": self.operation.value,
            "status": self.phase.value,
            "cleanup_state": self.state.value,
            "completed_targets": self.completed_targets,
            "old_deployment_id": OLD_DEPLOYMENT_ID,
            "new_deployment_id": NEW_DEPLOYMENT_ID,
            "retired_path": RETIRED_PATH,
            "retired_path_disposition": "ABSENT" if passed else "UNVERIFIED",
            "canonical_signed_trust_disposition": "VERIFIED"
            if passed
            else "UNVERIFIED",
            "scheduler_disposition": "D5_CAPTURE_ONLY_PREDECESSOR"
            if passed
            else "UNVERIFIED",
            "activation_disposition": "ABSENT" if passed else "UNVERIFIED",
            "activation_authority": "NONE",
            "scheduler_authority": "NONE",
            "trading_authority": "NONE",
        }
        if self.phase is CleanupPhase.BLOCKED:
            value["reason_code"] = self.reason_code.value
        if self.delete_diagnostic is not None:
            value["delete_diagnostic"] = {
                "target_index": self.delete_diagnostic.target_index,
                "stage": self.delete_diagnostic.stage.value,
                **(
                    {"win32_error": self.delete_diagnostic.win32_error}
                    if self.delete_diagnostic.stage is DeleteFailureStage.NATIVE_FALSE
                    else {}
                ),
            }
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("ascii")
