"""Deterministic offline verification of one explicit paper-account lineage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.ledger import (
    CompactPaperLedgerState,
    PaperLedger,
    restore_paper_ledger_from_compact_state,
)
from trading_bot.market_data import (
    DailySnapshotVerificationStatus,
    IdentifiedMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.runtime.checkpointed_paper_cycle_report import (
    CheckpointedPaperCycleReport,
    parse_checkpointed_paper_cycle_report,
)
from trading_bot.runtime.checkpointed_verified_snapshot_execution import (
    verified_prior_from_genesis,
    verified_prior_from_successor_edge,
)
from trading_bot.runtime.exceptions import (
    PaperAccountLineageVerificationError,
)
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountCheckpoint,
    PaperAccountCheckpointVerificationStatus,
    verify_genesis_paper_account_checkpoint,
)
from trading_bot.runtime.paper_account_successor_checkpoint import (
    PaperAccountCheckpointEdgeVerificationStatus,
    PaperAccountSuccessorCheckpoint,
    parse_successor_paper_account_checkpoint,
    verify_checkpointed_paper_cycle_successor_edge,
)

PAPER_ACCOUNT_LINEAGE_EVIDENCE_MATERIAL_VERSION = "paper-account-lineage-evidence-v1"
PAPER_ACCOUNT_LINEAGE_EVIDENCE_NAMESPACE = UUID("981a61a2-525d-5b42-aad6-20da46c93658")
MAX_PAPER_ACCOUNT_LINEAGE_ARTIFACTS = 10_000

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PaperAccountLineageArtifactKind(StrEnum):
    GENESIS_CHECKPOINT = "GENESIS_CHECKPOINT"
    SUCCESSOR_CHECKPOINT = "SUCCESSOR_CHECKPOINT"
    CYCLE_REPORT = "CYCLE_REPORT"
    DAILY_SNAPSHOT = "DAILY_SNAPSHOT"


class PaperAccountLineageVerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class PaperAccountLineageVerificationCode(StrEnum):
    """Stable failures in fixed evaluation precedence."""

    GENESIS_ARTIFACT_EVIDENCE_MISMATCH = "GENESIS_ARTIFACT_EVIDENCE_MISMATCH"
    GENESIS_VERIFICATION_FAILURE = "GENESIS_VERIFICATION_FAILURE"
    GENESIS_IDENTITY_MISMATCH = "GENESIS_IDENTITY_MISMATCH"
    ARTIFACT_EVIDENCE_MISMATCH = "ARTIFACT_EVIDENCE_MISMATCH"
    DUPLICATE_ID_CONFLICT = "DUPLICATE_ID_CONFLICT"
    DUPLICATE_BYTES_IDENTITY_CONFLICT = "DUPLICATE_BYTES_IDENTITY_CONFLICT"
    SUCCESSOR_PARSE_FAILURE = "SUCCESSOR_PARSE_FAILURE"
    REPORT_PARSE_FAILURE = "REPORT_PARSE_FAILURE"
    SNAPSHOT_VERIFICATION_FAILURE = "SNAPSHOT_VERIFICATION_FAILURE"
    ARTIFACT_IDENTITY_MISMATCH = "ARTIFACT_IDENTITY_MISMATCH"
    CHECKPOINT_REFERENCE_CONFLICT = "CHECKPOINT_REFERENCE_CONFLICT"
    REPORT_REFERENCE_CONFLICT = "REPORT_REFERENCE_CONFLICT"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
    FORK = "FORK"
    CYCLE = "CYCLE"
    REPORT_REUSE = "REPORT_REUSE"
    APPLICATION_ID_CONFLICT = "APPLICATION_ID_CONFLICT"
    TERMINAL_NOT_REACHABLE = "TERMINAL_NOT_REACHABLE"
    MISSING_CHECKPOINT = "MISSING_CHECKPOINT"
    MISSING_REPORT = "MISSING_REPORT"
    MISSING_SNAPSHOT = "MISSING_SNAPSHOT"
    EDGE_VERIFICATION_FAILURE = "EDGE_VERIFICATION_FAILURE"


@dataclass(frozen=True, slots=True)
class PaperAccountLineageArtifact:
    """One caller-supplied exact artifact and its claimed transport evidence."""

    kind: PaperAccountLineageArtifactKind
    artifact_id: UUID
    payload: bytes
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if type(self.kind) is not PaperAccountLineageArtifactKind:
            raise PaperAccountLineageVerificationError("artifact kind is invalid")
        if type(self.artifact_id) is not UUID:
            raise PaperAccountLineageVerificationError("artifact ID is invalid")
        if type(self.payload) is not bytes:
            raise PaperAccountLineageVerificationError("artifact payload is invalid")
        if (
            type(self.sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.sha256) is None
            or type(self.byte_length) is not int
            or self.byte_length < 0
        ):
            raise PaperAccountLineageVerificationError(
                "artifact transport evidence is invalid"
            )


@dataclass(frozen=True, slots=True)
class PaperAccountLineageArtifactEvidence:
    kind: PaperAccountLineageArtifactKind
    artifact_id: UUID
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if (
            type(self.kind) is not PaperAccountLineageArtifactKind
            or type(self.artifact_id) is not UUID
            or type(self.sha256) is not str
            or _SHA256_PATTERN.fullmatch(self.sha256) is None
            or type(self.byte_length) is not int
            or self.byte_length < 0
        ):
            raise PaperAccountLineageVerificationError(
                "lineage artifact evidence is invalid"
            )


@dataclass(frozen=True, slots=True)
class PaperAccountLineageEvidence:
    evidence_id: UUID
    genesis_checkpoint_id: UUID
    terminal_checkpoint_id: UUID
    lineage_id: UUID
    edge_count: int
    checkpoint_ids: tuple[UUID, ...]
    application_ids: tuple[UUID, ...]
    cycle_result_ids: tuple[UUID, ...]
    snapshot_ids: tuple[UUID, ...]
    checkpoint_artifacts: tuple[PaperAccountLineageArtifactEvidence, ...]
    report_artifacts: tuple[PaperAccountLineageArtifactEvidence, ...]
    snapshot_artifacts: tuple[PaperAccountLineageArtifactEvidence, ...]
    terminal_compact_state: CompactPaperLedgerState

    def __post_init__(self) -> None:
        if any(
            type(value) is not UUID
            for value in (
                self.evidence_id,
                self.genesis_checkpoint_id,
                self.terminal_checkpoint_id,
                self.lineage_id,
            )
        ):
            raise PaperAccountLineageVerificationError(
                "lineage evidence identities are invalid"
            )
        if type(self.edge_count) is not int or self.edge_count < 0:
            raise PaperAccountLineageVerificationError("edge count is invalid")
        checkpoints = _exact_tuple(self.checkpoint_ids, UUID, "checkpoint IDs")
        applications = _exact_tuple(self.application_ids, UUID, "application IDs")
        cycles = _exact_tuple(self.cycle_result_ids, UUID, "cycle-result IDs")
        snapshots = _exact_tuple(self.snapshot_ids, UUID, "snapshot IDs")
        checkpoint_artifacts = _exact_tuple(
            self.checkpoint_artifacts,
            PaperAccountLineageArtifactEvidence,
            "checkpoint artifacts",
        )
        report_artifacts = _exact_tuple(
            self.report_artifacts,
            PaperAccountLineageArtifactEvidence,
            "report artifacts",
        )
        snapshot_artifacts = _exact_tuple(
            self.snapshot_artifacts,
            PaperAccountLineageArtifactEvidence,
            "snapshot artifacts",
        )
        if (
            type(self.terminal_compact_state) is not CompactPaperLedgerState
            or len(checkpoints) != self.edge_count + 1
            or checkpoints[0] != self.genesis_checkpoint_id
            or checkpoints[-1] != self.terminal_checkpoint_id
            or any(
                len(values) != self.edge_count
                for values in (
                    applications,
                    cycles,
                    snapshots,
                    report_artifacts,
                    snapshot_artifacts,
                )
            )
            or len(checkpoint_artifacts) != self.edge_count + 1
        ):
            raise PaperAccountLineageVerificationError(
                "lineage evidence cardinality does not reconcile"
            )
        expected = derive_paper_account_lineage_evidence_id(
            self.genesis_checkpoint_id,
            self.terminal_checkpoint_id,
            self.lineage_id,
            checkpoints,
            applications,
            cycles,
            snapshots,
            checkpoint_artifacts,
            report_artifacts,
            snapshot_artifacts,
            self.terminal_compact_state.compact_state_id,
        )
        if self.evidence_id != expected:
            raise PaperAccountLineageVerificationError(
                "lineage evidence identity does not reconcile"
            )
        object.__setattr__(self, "checkpoint_ids", checkpoints)
        object.__setattr__(self, "application_ids", applications)
        object.__setattr__(self, "cycle_result_ids", cycles)
        object.__setattr__(self, "snapshot_ids", snapshots)
        object.__setattr__(self, "checkpoint_artifacts", checkpoint_artifacts)
        object.__setattr__(self, "report_artifacts", report_artifacts)
        object.__setattr__(self, "snapshot_artifacts", snapshot_artifacts)


@dataclass(frozen=True, slots=True)
class PaperAccountLineageVerificationDiagnostic:
    code: PaperAccountLineageVerificationCode
    detail: str

    def __post_init__(self) -> None:
        if type(self.code) is not PaperAccountLineageVerificationCode:
            raise PaperAccountLineageVerificationError("diagnostic code is invalid")
        if type(self.detail) is not str or not self.detail.strip():
            raise PaperAccountLineageVerificationError("diagnostic detail is invalid")


@dataclass(frozen=True, slots=True)
class PaperAccountLineageVerificationResult:
    status: PaperAccountLineageVerificationStatus
    evidence: PaperAccountLineageEvidence | None
    terminal_checkpoint: PaperAccountCheckpoint | PaperAccountSuccessorCheckpoint | None
    terminal_restored_ledger: PaperLedger | None
    diagnostics: tuple[PaperAccountLineageVerificationDiagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not PaperAccountLineageVerificationStatus:
            raise PaperAccountLineageVerificationError("lineage status is invalid")
        diagnostics = _exact_tuple(
            self.diagnostics,
            PaperAccountLineageVerificationDiagnostic,
            "lineage diagnostics",
        )
        complete = (
            type(self.evidence) is PaperAccountLineageEvidence
            and type(self.terminal_checkpoint)
            in (PaperAccountCheckpoint, PaperAccountSuccessorCheckpoint)
            and type(self.terminal_restored_ledger) is PaperLedger
        )
        if self.status is PaperAccountLineageVerificationStatus.PASS:
            if not complete or diagnostics:
                raise PaperAccountLineageVerificationError(
                    "PASS requires complete lineage evidence only"
                )
        elif complete or not diagnostics:
            raise PaperAccountLineageVerificationError(
                "FAIL must not expose terminal authority"
            )
        object.__setattr__(self, "diagnostics", diagnostics)


def derive_paper_account_lineage_evidence_id(
    genesis_checkpoint_id: UUID,
    terminal_checkpoint_id: UUID,
    lineage_id: UUID,
    checkpoint_ids: tuple[UUID, ...],
    application_ids: tuple[UUID, ...],
    cycle_result_ids: tuple[UUID, ...],
    snapshot_ids: tuple[UUID, ...],
    checkpoint_artifacts: tuple[PaperAccountLineageArtifactEvidence, ...],
    report_artifacts: tuple[PaperAccountLineageArtifactEvidence, ...],
    snapshot_artifacts: tuple[PaperAccountLineageArtifactEvidence, ...],
    terminal_compact_state_id: UUID,
) -> UUID:
    """Derive path-independent UUID5 identity from ordered verified evidence."""
    for value in (
        genesis_checkpoint_id,
        terminal_checkpoint_id,
        lineage_id,
        terminal_compact_state_id,
    ):
        if type(value) is not UUID:
            raise TypeError("lineage evidence identity material is invalid")
    checkpoints = _exact_tuple(checkpoint_ids, UUID, "checkpoint IDs")
    applications = _exact_tuple(application_ids, UUID, "application IDs")
    cycles = _exact_tuple(cycle_result_ids, UUID, "cycle-result IDs")
    snapshots = _exact_tuple(snapshot_ids, UUID, "snapshot IDs")
    artifact_groups = (
        _exact_tuple(
            checkpoint_artifacts,
            PaperAccountLineageArtifactEvidence,
            "checkpoint artifacts",
        ),
        _exact_tuple(
            report_artifacts,
            PaperAccountLineageArtifactEvidence,
            "report artifacts",
        ),
        _exact_tuple(
            snapshot_artifacts,
            PaperAccountLineageArtifactEvidence,
            "snapshot artifacts",
        ),
    )
    parts = [
        PAPER_ACCOUNT_LINEAGE_EVIDENCE_MATERIAL_VERSION,
        str(genesis_checkpoint_id),
        str(terminal_checkpoint_id),
        str(lineage_id),
        str(terminal_compact_state_id),
    ]
    for values in (checkpoints, applications, cycles, snapshots):
        parts.append(str(len(values)))
        parts.extend(str(value) for value in values)
    for group in artifact_groups:
        parts.append(str(len(group)))
        for item in group:
            parts.extend(
                (
                    item.kind.value,
                    str(item.artifact_id),
                    item.sha256,
                    str(item.byte_length),
                )
            )
    return uuid5(PAPER_ACCOUNT_LINEAGE_EVIDENCE_NAMESPACE, _framed(tuple(parts)))


def verify_paper_account_lineage(
    genesis_checkpoint: PaperAccountLineageArtifact,
    terminal_checkpoint_id: UUID,
    successor_checkpoints: tuple[PaperAccountLineageArtifact, ...],
    cycle_reports: tuple[PaperAccountLineageArtifact, ...],
    snapshots: tuple[PaperAccountLineageArtifact, ...],
    calendar: IdentifiedMarketCalendar,
) -> PaperAccountLineageVerificationResult:
    """Verify the unique supplied genesis-to-terminal path completely offline."""
    if (
        type(genesis_checkpoint) is not PaperAccountLineageArtifact
        or genesis_checkpoint.kind
        is not PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT
        or type(terminal_checkpoint_id) is not UUID
    ):
        raise PaperAccountLineageVerificationError(
            "lineage verification arguments are invalid"
        )
    successors = _artifacts(
        successor_checkpoints,
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
    )
    reports = _artifacts(cycle_reports, PaperAccountLineageArtifactKind.CYCLE_REPORT)
    snapshot_items = _artifacts(
        snapshots, PaperAccountLineageArtifactKind.DAILY_SNAPSHOT
    )

    if not _artifact_matches_evidence(genesis_checkpoint):
        return _failed(
            PaperAccountLineageVerificationCode.GENESIS_ARTIFACT_EVIDENCE_MISMATCH,
            "genesis bytes differ from supplied artifact evidence",
        )
    genesis_verification = verify_genesis_paper_account_checkpoint(
        genesis_checkpoint.payload,
        expected_checkpoint_sha256=genesis_checkpoint.sha256,
        expected_checkpoint_byte_length=genesis_checkpoint.byte_length,
    )
    if (
        genesis_verification.status is not PaperAccountCheckpointVerificationStatus.PASS
        or genesis_verification.checkpoint is None
        or genesis_verification.diagnostics
    ):
        return _failed(
            PaperAccountLineageVerificationCode.GENESIS_VERIFICATION_FAILURE,
            "genesis checkpoint did not fully verify",
        )
    genesis = genesis_verification.checkpoint
    if genesis.checkpoint_id != genesis_checkpoint.artifact_id:
        return _failed(
            PaperAccountLineageVerificationCode.GENESIS_IDENTITY_MISMATCH,
            "genesis claimed identity differs from canonical checkpoint identity",
        )
    prior = verified_prior_from_genesis(genesis_verification)

    all_items = (genesis_checkpoint, *successors, *reports, *snapshot_items)
    mismatch = next(
        (item for item in all_items[1:] if not _artifact_matches_evidence(item)), None
    )
    if mismatch is not None:
        return _failed(
            PaperAccountLineageVerificationCode.ARTIFACT_EVIDENCE_MISMATCH,
            "artifact bytes differ from supplied hash or byte length",
        )
    conflict = _duplicate_conflict(all_items)
    if conflict is not None:
        return _failed(conflict, "supplied artifact index contains a conflict")

    try:
        successor_models = {
            item.artifact_id: parse_successor_paper_account_checkpoint(item.payload)
            for item in successors
        }
    except Exception:
        return _failed(
            PaperAccountLineageVerificationCode.SUCCESSOR_PARSE_FAILURE,
            "a successor checkpoint is not strict canonical input",
        )
    try:
        report_models = {
            item.artifact_id: parse_checkpointed_paper_cycle_report(item.payload)
            for item in reports
        }
    except Exception:
        return _failed(
            PaperAccountLineageVerificationCode.REPORT_PARSE_FAILURE,
            "a checkpointed-cycle report is not strict canonical input",
        )
    snapshot_models = {}
    for item in snapshot_items:
        verification = verify_daily_snapshot(
            item.payload,
            calendar,
            expected_sha256=item.sha256,
            expected_byte_length=item.byte_length,
        )
        if (
            verification.status is not DailySnapshotVerificationStatus.PASS
            or verification.snapshot is None
            or verification.diagnostics
        ):
            return _failed(
                PaperAccountLineageVerificationCode.SNAPSHOT_VERIFICATION_FAILURE,
                "a daily snapshot did not fully verify",
            )
        snapshot_models[item.artifact_id] = verification.snapshot
    for item, model in (
        *((item, successor_models[item.artifact_id]) for item in successors),
        *((item, report_models[item.artifact_id]) for item in reports),
        *((item, snapshot_models[item.artifact_id]) for item in snapshot_items),
    ):
        model_id = getattr(model, "checkpoint_id", None)
        if model_id is None:
            model_id = getattr(model, "report_id", None)
        if model_id is None:
            model_id = getattr(model, "snapshot_id", None)
        if model_id != item.artifact_id:
            return _failed(
                PaperAccountLineageVerificationCode.ARTIFACT_IDENTITY_MISMATCH,
                "claimed artifact identity differs from canonical content",
            )

    successor_by_id = {item.artifact_id: item for item in successors}
    report_by_id = {item.artifact_id: item for item in reports}
    snapshot_by_id = {item.artifact_id: item for item in snapshot_items}
    checkpoint_by_id = {genesis.checkpoint_id: genesis_checkpoint, **successor_by_id}
    checkpoint_models = {genesis.checkpoint_id: genesis, **successor_models}

    structural = _structural_failure(
        successor_models,
        checkpoint_models,
        checkpoint_by_id,
        report_models,
        report_by_id,
        snapshot_by_id,
    )
    if structural is not None:
        return _failed(*structural)
    if terminal_checkpoint_id not in checkpoint_by_id:
        return _failed(
            PaperAccountLineageVerificationCode.MISSING_CHECKPOINT,
            "requested terminal checkpoint artifact is absent",
        )

    children: dict[UUID, tuple[UUID, ...]] = {}
    for successor in successor_models.values():
        parent = successor.prior_checkpoint.checkpoint_id
        children[parent] = tuple(
            sorted((*children.get(parent, ()), successor.checkpoint_id), key=str)
        )
    if any(len(values) > 1 for values in children.values()):
        return _failed(
            PaperAccountLineageVerificationCode.FORK,
            "a supplied checkpoint has more than one distinct child",
        )
    if _has_cycle(children):
        return _failed(
            PaperAccountLineageVerificationCode.CYCLE,
            "the supplied checkpoint graph contains a cycle",
        )

    checkpoint_ids = [genesis.checkpoint_id]
    application_ids: list[UUID] = []
    cycle_result_ids: list[UUID] = []
    snapshot_ids: list[UUID] = []
    checkpoint_evidence = [_evidence(genesis_checkpoint)]
    report_evidence: list[PaperAccountLineageArtifactEvidence] = []
    snapshot_evidence: list[PaperAccountLineageArtifactEvidence] = []
    terminal_model: PaperAccountCheckpoint | PaperAccountSuccessorCheckpoint = genesis
    terminal_ledger, _ = restore_paper_ledger_from_compact_state(prior.compact_state)
    current_id = genesis.checkpoint_id
    visited = {current_id}
    while current_id != terminal_checkpoint_id:
        child_ids = children.get(current_id, ())
        if not child_ids:
            return _failed(
                PaperAccountLineageVerificationCode.TERMINAL_NOT_REACHABLE,
                "requested terminal checkpoint is not reachable from genesis",
            )
        child_id = child_ids[0]
        if child_id in visited:
            return _failed(
                PaperAccountLineageVerificationCode.CYCLE,
                "the requested path revisits a checkpoint",
            )
        successor = successor_models.get(child_id)
        successor_artifact = successor_by_id.get(child_id)
        prior_artifact = checkpoint_by_id.get(current_id)
        if successor is None or successor_artifact is None or prior_artifact is None:
            return _failed(
                PaperAccountLineageVerificationCode.MISSING_CHECKPOINT,
                "a required checkpoint artifact is absent",
            )
        report_artifact = report_by_id.get(successor.producing_cycle.report_id)
        if report_artifact is None:
            return _failed(
                PaperAccountLineageVerificationCode.MISSING_REPORT,
                "a required producing cycle report is absent",
            )
        snapshot_artifact = snapshot_by_id.get(successor.snapshot_reference.snapshot_id)
        if snapshot_artifact is None:
            return _failed(
                PaperAccountLineageVerificationCode.MISSING_SNAPSHOT,
                "a required daily snapshot artifact is absent",
            )
        edge = verify_checkpointed_paper_cycle_successor_edge(
            report_artifact.payload,
            prior_artifact.payload,
            snapshot_artifact.payload,
            successor_artifact.payload,
            calendar,
            expected_successor_sha256=successor_artifact.sha256,
            expected_successor_byte_length=successor_artifact.byte_length,
            verified_prior=prior,
        )
        if (
            edge.status is not PaperAccountCheckpointEdgeVerificationStatus.PASS
            or edge.successor_checkpoint is None
            or edge.restored_successor_ledger is None
            or edge.cycle_result is None
            or edge.diagnostics
        ):
            return _failed(
                PaperAccountLineageVerificationCode.EDGE_VERIFICATION_FAILURE,
                "a required successor edge did not fully verify",
            )
        prior = verified_prior_from_successor_edge(edge)
        terminal_model = edge.successor_checkpoint
        terminal_ledger = edge.restored_successor_ledger
        checkpoint_ids.append(child_id)
        application_ids.append(successor.application_id)
        cycle_result_ids.append(successor.producing_cycle.cycle_result_id)
        snapshot_ids.append(successor.snapshot_reference.snapshot_id)
        checkpoint_evidence.append(_evidence(successor_artifact))
        report_evidence.append(_evidence(report_artifact))
        snapshot_evidence.append(_evidence(snapshot_artifact))
        visited.add(child_id)
        current_id = child_id

    terminal_compact = prior.compact_state
    evidence_id = derive_paper_account_lineage_evidence_id(
        genesis.checkpoint_id,
        terminal_checkpoint_id,
        prior.lineage_id,
        tuple(checkpoint_ids),
        tuple(application_ids),
        tuple(cycle_result_ids),
        tuple(snapshot_ids),
        tuple(checkpoint_evidence),
        tuple(report_evidence),
        tuple(snapshot_evidence),
        terminal_compact.compact_state_id,
    )
    evidence = PaperAccountLineageEvidence(
        evidence_id,
        genesis.checkpoint_id,
        terminal_checkpoint_id,
        prior.lineage_id,
        len(application_ids),
        tuple(checkpoint_ids),
        tuple(application_ids),
        tuple(cycle_result_ids),
        tuple(snapshot_ids),
        tuple(checkpoint_evidence),
        tuple(report_evidence),
        tuple(snapshot_evidence),
        terminal_compact,
    )
    return PaperAccountLineageVerificationResult(
        PaperAccountLineageVerificationStatus.PASS,
        evidence,
        terminal_model,
        terminal_ledger,
        (),
    )


def _structural_failure(
    successors: dict[UUID, PaperAccountSuccessorCheckpoint],
    checkpoints: dict[UUID, PaperAccountCheckpoint | PaperAccountSuccessorCheckpoint],
    checkpoint_artifacts: dict[UUID, PaperAccountLineageArtifact],
    reports: dict[UUID, CheckpointedPaperCycleReport],
    report_artifacts: dict[UUID, PaperAccountLineageArtifact],
    snapshots: dict[UUID, PaperAccountLineageArtifact],
) -> tuple[PaperAccountLineageVerificationCode, str] | None:
    report_uses: dict[UUID, UUID] = {}
    applications: dict[UUID, tuple[UUID, UUID, UUID]] = {}
    for successor in sorted(
        successors.values(), key=lambda item: str(item.checkpoint_id)
    ):
        prior = checkpoints.get(successor.prior_checkpoint.checkpoint_id)
        if prior is not None:
            prior_sequence = prior.sequence
            prior_lineage = prior.lineage_id
            indexed = checkpoint_artifacts[prior.checkpoint_id]
            if successor.sequence != prior_sequence + 1:
                return (
                    PaperAccountLineageVerificationCode.SEQUENCE_GAP,
                    "successor sequence is not the actual prior sequence plus one",
                )
            if successor.prior_lineage_id != prior_lineage:
                return (
                    PaperAccountLineageVerificationCode.LINEAGE_CONFLICT,
                    "successor prior lineage differs from its actual parent",
                )
            if (
                successor.prior_checkpoint.artifact_sha256 != indexed.sha256
                or successor.prior_checkpoint.artifact_byte_length
                != indexed.byte_length
            ):
                return (
                    PaperAccountLineageVerificationCode.CHECKPOINT_REFERENCE_CONFLICT,
                    "successor prior reference differs from the supplied checkpoint",
                )
        report_artifact = report_artifacts.get(successor.producing_cycle.report_id)
        if report_artifact is not None and (
            report_artifact.sha256 != successor.producing_cycle.artifact_sha256
            or report_artifact.byte_length
            != successor.producing_cycle.artifact_byte_length
        ):
            return (
                PaperAccountLineageVerificationCode.REPORT_REFERENCE_CONFLICT,
                "successor report reference differs from the supplied artifact",
            )
        snapshot_artifact = snapshots.get(successor.snapshot_reference.snapshot_id)
        if snapshot_artifact is not None and (
            snapshot_artifact.sha256 != successor.snapshot_reference.artifact_sha256
            or snapshot_artifact.byte_length
            != successor.snapshot_reference.artifact_byte_length
        ):
            return (
                PaperAccountLineageVerificationCode.SNAPSHOT_MISMATCH,
                "successor snapshot reference differs from the supplied artifact",
            )
        report = reports.get(successor.producing_cycle.report_id)
        if report is not None:
            evidence = report.evidence
            if (
                evidence.cycle_result_id != successor.producing_cycle.cycle_result_id
                or evidence.application_id != successor.application_id
                or evidence.prior_checkpoint != successor.prior_checkpoint
                or evidence.prior_lineage_id != successor.prior_lineage_id
                or evidence.request.snapshot_reference != successor.snapshot_reference
            ):
                return (
                    PaperAccountLineageVerificationCode.REPORT_REFERENCE_CONFLICT,
                    "successor and producing report retained different edge material",
                )
        previous_report_child = report_uses.get(successor.producing_cycle.report_id)
        if previous_report_child not in (None, successor.checkpoint_id):
            return (
                PaperAccountLineageVerificationCode.REPORT_REUSE,
                "one cycle report is reused by different successor edges",
            )
        report_uses[successor.producing_cycle.report_id] = successor.checkpoint_id
        material = (
            successor.prior_checkpoint.checkpoint_id,
            successor.producing_cycle.cycle_result_id,
            successor.checkpoint_id,
        )
        prior_material = applications.get(successor.application_id)
        if prior_material not in (None, material):
            return (
                PaperAccountLineageVerificationCode.APPLICATION_ID_CONFLICT,
                "one application ID is bound to different edge material",
            )
        applications[successor.application_id] = material
    return None


def _artifacts(
    value: tuple[PaperAccountLineageArtifact, ...],
    kind: PaperAccountLineageArtifactKind,
) -> tuple[PaperAccountLineageArtifact, ...]:
    items = _exact_tuple(value, PaperAccountLineageArtifact, "lineage artifacts")
    if len(items) > MAX_PAPER_ACCOUNT_LINEAGE_ARTIFACTS:
        raise PaperAccountLineageVerificationError("artifact set exceeds its bound")
    if any(item.kind is not kind for item in items):
        raise PaperAccountLineageVerificationError("artifact category is invalid")
    unique = {
        (item.artifact_id, item.sha256, item.byte_length, item.payload): item
        for item in items
    }
    return tuple(
        sorted(unique.values(), key=lambda item: (str(item.artifact_id), item.sha256))
    )


def _duplicate_conflict(
    artifacts: tuple[PaperAccountLineageArtifact, ...],
) -> PaperAccountLineageVerificationCode | None:
    by_id: dict[UUID, tuple[str, int, bytes]] = {}
    by_bytes: dict[bytes, tuple[PaperAccountLineageArtifactKind, UUID]] = {}
    for item in artifacts:
        material = (item.sha256, item.byte_length, item.payload)
        if item.artifact_id in by_id and by_id[item.artifact_id] != material:
            return PaperAccountLineageVerificationCode.DUPLICATE_ID_CONFLICT
        by_id[item.artifact_id] = material
        identity = (item.kind, item.artifact_id)
        if item.payload in by_bytes and by_bytes[item.payload] != identity:
            return PaperAccountLineageVerificationCode.DUPLICATE_BYTES_IDENTITY_CONFLICT
        by_bytes[item.payload] = identity
    return None


def _has_cycle(children: dict[UUID, tuple[UUID, ...]]) -> bool:
    visiting: set[UUID] = set()
    complete: set[UUID] = set()

    def visit(node: UUID) -> bool:
        if node in visiting:
            return True
        if node in complete:
            return False
        visiting.add(node)
        if any(visit(child) for child in children.get(node, ())):
            return True
        visiting.remove(node)
        complete.add(node)
        return False

    return any(visit(node) for node in tuple(children))


def _artifact_matches_evidence(artifact: PaperAccountLineageArtifact) -> bool:
    return (
        len(artifact.payload) == artifact.byte_length
        and sha256(artifact.payload).hexdigest() == artifact.sha256
    )


def _evidence(
    artifact: PaperAccountLineageArtifact,
) -> PaperAccountLineageArtifactEvidence:
    return PaperAccountLineageArtifactEvidence(
        artifact.kind,
        artifact.artifact_id,
        artifact.sha256,
        artifact.byte_length,
    )


def _failed(
    code: PaperAccountLineageVerificationCode,
    detail: str,
) -> PaperAccountLineageVerificationResult:
    return PaperAccountLineageVerificationResult(
        PaperAccountLineageVerificationStatus.FAIL,
        None,
        None,
        None,
        (PaperAccountLineageVerificationDiagnostic(code, detail),),
    )


def _exact_tuple(value: object, expected: type, label: str):
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise PaperAccountLineageVerificationError(
            f"{label} must be iterable"
        ) from error
    if any(type(item) is not expected for item in items):
        raise PaperAccountLineageVerificationError(f"{label} contain invalid values")
    return items


def _framed(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(item.encode('utf-8'))}:{item}" for item in parts)
