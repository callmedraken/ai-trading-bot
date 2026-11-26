"""One-shot, offline Arch151 development evaluation evidence operator.

Import is inert. The consumed E1 and E2 public execution routes are retired.
Neither route can load accepted custody or create another attempt. The private
execution engine remains available to synthetic tests only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from trading_bot.experiments import arch151_intraday_walkforward as arch151
from trading_bot.experiments import arch151_intraday_walkforward_evaluator as evaluator

EXPECTED_BRANCH = "feature/research-arch151-intraday-walkforward-current"
EXPECTED_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
EXPECTED_WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-arch151-intraday-walkforward-current"
)
EVIDENCE_ROOT = Path(r"F:\AI\temp\arch151-intraday-development-evidence")
SUCCESSOR_EVIDENCE_ROOT = Path(
    r"F:\AI\temp\arch151-intraday-development-evidence-e2-successor"
)
_PREDECESSOR_ATTEMPT_ID = UUID("0c0db97e-034c-4b59-97de-137d6e95359c")
_PREDECESSOR_INVOCATION_ID = UUID("7fa05c82-d0e5-508f-8e77-b508071236d0")
_PREDECESSOR_HEAD = "3bb821aa77fbad7f3177e880d64234eb66b68ec4"
_PREDECESSOR_TREE = "5e559e406d66f5a3bcbbab5155db0688b1c4c1d2"
_PREDECESSOR_ARTIFACTS = (
    (
        "attempt.json",
        381,
        "181479c21ed663f38c6df563917e767dcc4d2b11caf195d300c39d9f44661465",
    ),
    (
        "source-revision.json",
        413,
        "0c25ffa671bcfc72e9e9ac5b233b534d3e7d78847a996b76ae91ef28f7c6a68c",
    ),
    (
        "operator-failure.json",
        376,
        "7c5a76452e8811cdf9a2bfe8e75e0bd2ff44f47e51a2c1d140bc3f6df4980ee8",
    ),
    (
        "attempt-result.json",
        931,
        "0e0e5d5bfe3e8f0c6d04159c6615bccaa92a067f7e54dde42ce3b2d254a088e2",
    ),
)
_ATTEMPT_SCHEMA = "arch151-development-operator-attempt/v1"
_SUCCESSOR_ATTEMPT_SCHEMA = "arch151-development-operator-attempt/v2"
_SOURCE_REVISION_SCHEMA = "arch151-development-source-revision/v1"
_SUCCESSOR_SOURCE_REVISION_SCHEMA = "arch151-development-source-revision/v2"
_RESULT_SCHEMA = "arch151-development-operator-result/v3"
_SUCCESSOR_RESULT_SCHEMA = "arch151-development-operator-result/v4"
_SOURCE_ATTESTATION_SCHEMA = "arch151-development-source-attestation/v1"
_YEAR_EVIDENCE_SCHEMA = "arch151-development-year-evidence/v1"
_REPLAY_FAILURE_SCHEMA = "arch151-replay-integrity-failure-evidence/v1"
_INCOMPLETE_SCHEMA = "arch151-development-incomplete-evidence/v1"
_OPERATOR_FAILURE_SCHEMA = "arch151-development-operator-failure/v1"
_OPERATOR_FAILURE_SCHEMA_V2 = "arch151-development-operator-failure/v2"
_OPERATOR_FAILURE_SCHEMA_V3 = "arch151-development-operator-failure/v3"
_PREDECESSOR_BINDING_SCHEMA = "arch151-development-predecessor-binding/v1"
_INVOCATION_SCHEMA = "arch151-development-invocation/v1"
_INVOCATION_NAMESPACE = uuid5(
    arch151.CANONICAL_MANIFEST.manifest_id, "arch151-development-invocation/v1"
)
_SOURCE_REVISION_SEAL = object()
_SOURCE_ATTESTATION_NAMESPACE = uuid5(
    arch151.CANONICAL_MANIFEST.manifest_id,
    "arch151-development-source-attestation/v1",
)
_SOURCE_ATTESTATION_SEAL = object()
_ACTIVE_INVOCATION_SEAL = object()
_DEVELOPMENT_EVIDENCE_HANDOFF_SEAL = object()
_PREDECESSOR_BINDING_NAMESPACE = uuid5(
    arch151.CANONICAL_MANIFEST.manifest_id,
    "arch151-e2-consumed-predecessor-binding/v1",
)
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_WORKTREES_ROOT = Path(r"F:\AI\worktrees")


class OperatorStatus(StrEnum):
    COMPLETED = "COMPLETED"
    REPLAY_INTEGRITY_FAILURE = "REPLAY_INTEGRITY_FAILURE"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


class OperatorFailureCode(StrEnum):
    SOURCE_IDENTITY_UNAVAILABLE = "SOURCE_IDENTITY_UNAVAILABLE"
    SOURCE_BRANCH_INVALID = "SOURCE_BRANCH_INVALID"
    SOURCE_ORIGIN_INVALID = "SOURCE_ORIGIN_INVALID"
    SOURCE_DIRTY = "SOURCE_DIRTY"
    SOURCE_HISTORY_INVALID = "SOURCE_HISTORY_INVALID"
    SOURCE_LOAD_FAILED = "SOURCE_LOAD_FAILED"
    EVIDENCE_ROOT_INVALID = "EVIDENCE_ROOT_INVALID"
    EVIDENCE_ROOT_ALREADY_EXISTS = "EVIDENCE_ROOT_ALREADY_EXISTS"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    PREDECESSOR_EVIDENCE_INVALID = "PREDECESSOR_EVIDENCE_INVALID"
    PREDECESSOR_ATTEMPT_CONSUMED = "PREDECESSOR_ATTEMPT_CONSUMED"
    SUCCESSOR_ATTEMPT_CONSUMED = "SUCCESSOR_ATTEMPT_CONSUMED"
    SUCCESSOR_SOURCE_HEAD_MISMATCH = "SUCCESSOR_SOURCE_HEAD_MISMATCH"
    YEAR_EVALUATION_FAILED = "YEAR_EVALUATION_FAILED"
    DEVELOPMENT_COMPOSITION_FAILED = "DEVELOPMENT_COMPOSITION_FAILED"
    REPORT_SERIALIZATION_FAILED = "REPORT_SERIALIZATION_FAILED"
    REPORT_INTEGRITY_FAILED = "REPORT_INTEGRITY_FAILED"
    UNCLASSIFIED_FAILURE = "UNCLASSIFIED_FAILURE"


class OperatorFailureStage(StrEnum):
    SOURCE_REVISION = "SOURCE_REVISION"
    SOURCE_REVISION_EVIDENCE = "SOURCE_REVISION_EVIDENCE"
    PREDECESSOR_EVIDENCE = "PREDECESSOR_EVIDENCE"
    SOURCE_LOAD = "SOURCE_LOAD"
    ANNUAL_SIMULATION = "ANNUAL_SIMULATION"
    ANNUAL_EVIDENCE_CONSTRUCTION = "ANNUAL_EVIDENCE_CONSTRUCTION"
    ANNUAL_EVIDENCE_SERIALIZATION = "ANNUAL_EVIDENCE_SERIALIZATION"
    ANNUAL_EVIDENCE_PERSISTENCE = "ANNUAL_EVIDENCE_PERSISTENCE"
    DEVELOPMENT_COMPOSITION = "DEVELOPMENT_COMPOSITION"
    REPORT_SERIALIZATION = "REPORT_SERIALIZATION"
    REPORT_PERSISTENCE = "REPORT_PERSISTENCE"
    SOURCE_ATTESTATION = "SOURCE_ATTESTATION"
    DEVELOPMENT_EVIDENCE_ISSUANCE = "DEVELOPMENT_EVIDENCE_ISSUANCE"


class ClosedFailureReason(StrEnum):
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"
    ARITHMETIC_FAILURE = "ARITHMETIC_FAILURE"
    REPOSITORY_VALIDATION_FAILURE = "REPOSITORY_VALIDATION_FAILURE"
    IO_FAILURE = "IO_FAILURE"
    OPERATOR_GATE_FAILURE = "OPERATOR_GATE_FAILURE"
    UNEXPECTED_EXCEPTION = "UNEXPECTED_EXCEPTION"


class OperatorError(RuntimeError):
    def __init__(self, code: OperatorFailureCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True, init=False)
class SourceRevision:
    branch: str
    origin: str
    head: str
    tree: str
    _seal: object

    def __init__(
        self,
        branch: str,
        origin: str,
        head: str,
        tree: str,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _SOURCE_REVISION_SEAL:
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        if branch != EXPECTED_BRANCH or origin != EXPECTED_ORIGIN:
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        if not _is_git_object_id(head) or not _is_git_object_id(tree):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        for name, value in (
            ("branch", branch),
            ("origin", origin),
            ("head", head),
            ("tree", tree),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class OperatorOutcome:
    status: OperatorStatus
    attempt_id: UUID | None
    invocation_id: UUID | None
    evidence_root: Path | None
    report_id: UUID | None
    report_sha256: str | None
    failure_code: OperatorFailureCode | None
    source_attestation: DevelopmentSourceAttestation | None = None
    development_evidence_handoff: DevelopmentEvidenceHandoff | None = None


@dataclass(frozen=True, slots=True, init=False)
class DevelopmentSourceAttestation:
    """Operator-issued binding from one captured revision to one exact run/report."""

    attempt_id: UUID
    invocation_id: UUID
    source_revision: SourceRevision
    source_revision_digest: str
    source_kind: str
    source_binding_id: UUID
    source_digest: str
    manifest_id: UUID
    manifest_fingerprint: str
    record_count: int
    run_id: UUID
    report_id: UUID
    report_sha256: str
    year_batch_ids: tuple[UUID, ...]
    slot_batch_digests: tuple[str, ...]
    freeze_id: UUID
    freeze_fingerprint: str
    selection_bias_calculation_id: UUID
    selection_bias_population_digest: str
    canonical_json_bytes: bytes
    attestation_id: UUID
    attestation_digest: str
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        attempt_id: UUID,
        invocation_id: UUID,
        source_revision: SourceRevision,
        source_revision_digest: str,
        source_kind: str,
        source_binding_id: UUID,
        source_digest: str,
        manifest_id: UUID,
        manifest_fingerprint: str,
        record_count: int,
        run_id: UUID,
        report_id: UUID,
        report_sha256: str,
        year_batch_ids: tuple[UUID, ...],
        slot_batch_digests: tuple[str, ...],
        freeze_id: UUID,
        freeze_fingerprint: str,
        selection_bias_calculation_id: UUID,
        selection_bias_population_digest: str,
        canonical_json_bytes: bytes,
        attestation_id: UUID,
        attestation_digest: str,
    ) -> None:
        if _seal is not _SOURCE_ATTESTATION_SEAL:
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        if (
            type(attempt_id) is not UUID
            or type(invocation_id) is not UUID
            or type(source_revision) is not SourceRevision
            or getattr(source_revision, "_seal", None) is not _SOURCE_REVISION_SEAL
            or invocation_id != _invocation_id(source_revision)
            or not arch151._is_sha256(source_revision_digest)
            or source_kind not in ("ARCH150_D1R_ACCEPTED", "SYNTHETIC_TEST_ONLY")
            or type(source_binding_id) is not UUID
            or not arch151._is_sha256(source_digest)
            or manifest_id != arch151.CANONICAL_MANIFEST.manifest_id
            or manifest_fingerprint != arch151.CANONICAL_MANIFEST.fingerprint
            or not arch151._is_sha256(manifest_fingerprint)
            or type(record_count) is not int
            or record_count != 480
            or type(run_id) is not UUID
            or type(report_id) is not UUID
            or not arch151._is_sha256(report_sha256)
            or len(year_batch_ids) != len(arch151.SCORED_YEARS)
            or any(type(item) is not UUID for item in year_batch_ids)
            or len(slot_batch_digests) != len(arch151.CANONICAL_SLOTS)
            or any(not arch151._is_sha256(item) for item in slot_batch_digests)
            or type(freeze_id) is not UUID
            or not arch151._is_sha256(freeze_fingerprint)
            or type(selection_bias_calculation_id) is not UUID
            or not arch151._is_sha256(selection_bias_population_digest)
            or type(canonical_json_bytes) is not bytes
            or type(attestation_id) is not UUID
            or not arch151._is_sha256(attestation_digest)
        ):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        material = _source_attestation_material(
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            source_revision=source_revision,
            source_revision_digest=source_revision_digest,
            source_kind=source_kind,
            source_binding_id=source_binding_id,
            source_digest=source_digest,
            manifest_id=manifest_id,
            manifest_fingerprint=manifest_fingerprint,
            record_count=record_count,
            run_id=run_id,
            report_id=report_id,
            report_sha256=report_sha256,
            year_batch_ids=year_batch_ids,
            slot_batch_digests=slot_batch_digests,
            freeze_id=freeze_id,
            freeze_fingerprint=freeze_fingerprint,
            selection_bias_calculation_id=selection_bias_calculation_id,
            selection_bias_population_digest=selection_bias_population_digest,
        )
        expected_bytes = arch151._canonical_json(material)
        if (
            canonical_json_bytes != expected_bytes
            or attestation_digest != hashlib.sha256(expected_bytes).hexdigest()
            or attestation_id
            != uuid5(_SOURCE_ATTESTATION_NAMESPACE, expected_bytes.decode("utf-8"))
        ):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        for name, value in (
            ("attempt_id", attempt_id),
            ("invocation_id", invocation_id),
            ("source_revision", source_revision),
            ("source_revision_digest", source_revision_digest),
            ("source_kind", source_kind),
            ("source_binding_id", source_binding_id),
            ("source_digest", source_digest),
            ("manifest_id", manifest_id),
            ("manifest_fingerprint", manifest_fingerprint),
            ("record_count", record_count),
            ("run_id", run_id),
            ("report_id", report_id),
            ("report_sha256", report_sha256),
            ("year_batch_ids", year_batch_ids),
            ("slot_batch_digests", slot_batch_digests),
            ("freeze_id", freeze_id),
            ("freeze_fingerprint", freeze_fingerprint),
            ("selection_bias_calculation_id", selection_bias_calculation_id),
            ("selection_bias_population_digest", selection_bias_population_digest),
            ("canonical_json_bytes", canonical_json_bytes),
            ("attestation_id", attestation_id),
            ("attestation_digest", attestation_digest),
            ("_seal", _seal),
        ):
            object.__setattr__(self, name, value)


class _ActiveDevelopmentInvocation:
    """Ephemeral one-shot context retaining the exact objects composed here."""

    __slots__ = (
        "attempt_id",
        "invocation_id",
        "source_revision",
        "_run",
        "_report",
        "_seal",
    )

    def __init__(
        self,
        *,
        _seal: object = None,
        attempt_id: UUID,
        invocation_id: UUID,
        source_revision: SourceRevision,
    ) -> None:
        if (
            _seal is not _ACTIVE_INVOCATION_SEAL
            or type(attempt_id) is not UUID
            or type(invocation_id) is not UUID
            or type(source_revision) is not SourceRevision
            or getattr(source_revision, "_seal", None) is not _SOURCE_REVISION_SEAL
            or invocation_id != _invocation_id(source_revision)
        ):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        self.attempt_id = attempt_id
        self.invocation_id = invocation_id
        self.source_revision = source_revision
        self._run = None
        self._report = None
        self._seal = _seal

    def bind_run(self, run: evaluator.DevelopmentEvaluationRun) -> None:
        if (
            self._seal is not _ACTIVE_INVOCATION_SEAL
            or self._run is not None
            or type(run) is not evaluator.DevelopmentEvaluationRun
            or getattr(run, "_seal", None) is not evaluator._DEVELOPMENT_RUN_SEAL
        ):
            raise OperatorError(OperatorFailureCode.DEVELOPMENT_COMPOSITION_FAILED)
        self._run = run

    def bind_report(self, report: evaluator.DevelopmentEvaluationReport) -> None:
        if (
            self._seal is not _ACTIVE_INVOCATION_SEAL
            or self._run is None
            or self._report is not None
            or type(report) is not evaluator.DevelopmentEvaluationReport
            or getattr(report, "_seal", None) is not evaluator._DEVELOPMENT_REPORT_SEAL
            or report.run_id != self._run.run_id
        ):
            raise OperatorError(OperatorFailureCode.REPORT_INTEGRITY_FAILED)
        self._report = report


@dataclass(frozen=True, slots=True, init=False)
class DevelopmentEvidenceHandoff:
    """Non-authorizing sealed inputs needed for later reviewed holdout policy."""

    authenticated_evidence: arch151.AuthenticatedDevelopmentEvidence
    final_freeze: arch151.FinalCandidateFreeze
    selection_bias_evidence: arch151.VerifiedSelectionBiasEvidence
    source_attestation: DevelopmentSourceAttestation
    _seal: object

    def __init__(
        self,
        *,
        _seal: object = None,
        authenticated_evidence: arch151.AuthenticatedDevelopmentEvidence,
        final_freeze: arch151.FinalCandidateFreeze,
        selection_bias_evidence: arch151.VerifiedSelectionBiasEvidence,
        source_attestation: DevelopmentSourceAttestation,
    ) -> None:
        if _seal is not _DEVELOPMENT_EVIDENCE_HANDOFF_SEAL:
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        if (
            type(authenticated_evidence) is not arch151.AuthenticatedDevelopmentEvidence
            or getattr(authenticated_evidence, "_seal", None)
            is not arch151._AUTHENTICATED_DEVELOPMENT_EVIDENCE_SEAL
            or type(final_freeze) is not arch151.FinalCandidateFreeze
            or getattr(final_freeze, "_seal", None) is not arch151._FINAL_FREEZE_SEAL
            or final_freeze.status is not arch151.FinalFreezeStatus.ONE_CANDIDATE_FROZEN
            or final_freeze.candidate_slot_id is None
            or type(selection_bias_evidence)
            is not arch151.VerifiedSelectionBiasEvidence
            or getattr(selection_bias_evidence, "_seal", None)
            is not arch151._VERIFIED_SELECTION_BIAS_SEAL
            or type(source_attestation) is not DevelopmentSourceAttestation
            or getattr(source_attestation, "_seal", None)
            is not _SOURCE_ATTESTATION_SEAL
        ):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        candidate_slot_id = final_freeze.candidate_slot_id
        candidate_index = tuple(item.slot_id for item in arch151.CANONICAL_SLOTS).index(
            candidate_slot_id
        )
        if (
            authenticated_evidence.freeze_id != final_freeze.freeze_id
            or authenticated_evidence.freeze_fingerprint != final_freeze.fingerprint
            or authenticated_evidence.candidate_slot_id != candidate_slot_id
            or authenticated_evidence.batch_digests != final_freeze.batch_digests
            or authenticated_evidence.selection_bias_calculation_id
            != final_freeze.selection_bias_calculation_id
            or authenticated_evidence.selection_bias_evidence_digests
            != final_freeze.selection_bias_evidence_digests
            or selection_bias_evidence.candidate_slot_id != candidate_slot_id
            or selection_bias_evidence.population_digest
            != authenticated_evidence.selection_bias_population_digest
            or selection_bias_evidence.ledger_id
            != authenticated_evidence.selection_bias_ledger_id
            or selection_bias_evidence.effective_trial_count
            != authenticated_evidence.selection_bias_effective_trial_count
            or selection_bias_evidence.evidence_id
            != authenticated_evidence.selection_bias_evidence_ids[candidate_index]
            or selection_bias_evidence.evidence_digest
            != authenticated_evidence.selection_bias_evidence_digests[candidate_index]
            or selection_bias_evidence.development_batch_digest
            != authenticated_evidence.batch_digests[candidate_index]
            or selection_bias_evidence.evidence_id
            != final_freeze.selection_bias_evidence_ids[candidate_index]
            or selection_bias_evidence.evidence_digest
            != final_freeze.selection_bias_evidence_digests[candidate_index]
            or source_attestation.run_id != authenticated_evidence.run_id
            or source_attestation.report_id != authenticated_evidence.report_id
            or source_attestation.report_sha256 != authenticated_evidence.report_sha256
            or source_attestation.invocation_id != authenticated_evidence.invocation_id
            or source_attestation.source_revision_digest
            != authenticated_evidence.source_revision_digest
            or source_attestation.source_kind != "ARCH150_D1R_ACCEPTED"
        ):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        object.__setattr__(self, "authenticated_evidence", authenticated_evidence)
        object.__setattr__(self, "final_freeze", final_freeze)
        object.__setattr__(self, "selection_bias_evidence", selection_bias_evidence)
        object.__setattr__(self, "source_attestation", source_attestation)
        object.__setattr__(self, "_seal", _seal)


def operator_help() -> str:
    return (
        "The consumed Arch151 E1 and E2 execution routes are permanently "
        "retired. Their CLI switches fail closed without reading custody or "
        "creating another attempt. The private execution engine is reserved "
        "for synthetic tests."
    )


def _is_git_object_id(value: object) -> bool:
    return (
        type(value) is str
        and len(value) in (40, 64)
        and all(character in "0123456789abcdef" for character in value)
    )


def _git_text(repo_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ("git", "-C", str(repo_root), *arguments),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None
    if result.returncode != 0:
        raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    return result.stdout.strip()


def _read_source_revision() -> SourceRevision:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        if repo_root != EXPECTED_WORKTREE.resolve(strict=True):
            raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    except OSError:
        raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None
    branch = _git_text(repo_root, "branch", "--show-current")
    origin = _git_text(repo_root, "config", "--get", "remote.origin.url")
    head = _git_text(repo_root, "rev-parse", "--verify", "HEAD")
    tree = _git_text(repo_root, "rev-parse", "--verify", "HEAD^{tree}")
    status = _git_text(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if branch != EXPECTED_BRANCH:
        raise OperatorError(OperatorFailureCode.SOURCE_BRANCH_INVALID)
    if origin != EXPECTED_ORIGIN:
        raise OperatorError(OperatorFailureCode.SOURCE_ORIGIN_INVALID)
    if status:
        raise OperatorError(OperatorFailureCode.SOURCE_DIRTY)
    try:
        return SourceRevision(branch, origin, head, tree, _seal=_SOURCE_REVISION_SEAL)
    except ValueError:
        raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None


def _invocation_id(revision: SourceRevision) -> UUID:
    material = {
        "schema": _INVOCATION_SCHEMA,
        "source_branch": revision.branch,
        "source_origin": revision.origin,
        "source_head": revision.head,
        "source_tree": revision.tree,
        "development_start": "2016-01-01",
        "development_end": "2023-12-31",
        "scored_years": list(arch151.SCORED_YEARS),
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "cost_cases": [item.value for item in arch151.EVALUATION_ECONOMICS_ORDER],
        "automatic_retry": "FORBIDDEN",
    }
    return uuid5(_INVOCATION_NAMESPACE, arch151._canonical_json(material).decode())


def _source_revision_digest(revision: SourceRevision, invocation_id: UUID) -> str:
    material = {
        "schema": _SOURCE_REVISION_SCHEMA,
        "branch": revision.branch,
        "origin": revision.origin,
        "head": revision.head,
        "tree": revision.tree,
        "invocation_id": str(invocation_id),
    }
    return hashlib.sha256(arch151._canonical_json(material)).hexdigest()


def _source_attestation_material(
    *,
    attempt_id: UUID,
    invocation_id: UUID,
    source_revision: SourceRevision,
    source_revision_digest: str,
    source_kind: str,
    source_binding_id: UUID,
    source_digest: str,
    manifest_id: UUID,
    manifest_fingerprint: str,
    record_count: int,
    run_id: UUID,
    report_id: UUID,
    report_sha256: str,
    year_batch_ids: tuple[UUID, ...],
    slot_batch_digests: tuple[str, ...],
    freeze_id: UUID,
    freeze_fingerprint: str,
    selection_bias_calculation_id: UUID,
    selection_bias_population_digest: str,
) -> dict[str, object]:
    return {
        "schema": _SOURCE_ATTESTATION_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_revision_digest": source_revision_digest,
        "source_revision": {
            "branch": source_revision.branch,
            "origin": source_revision.origin,
            "head": source_revision.head,
            "tree": source_revision.tree,
        },
        "source_kind": source_kind,
        "source_binding_id": str(source_binding_id),
        "source_digest": source_digest,
        "manifest_id": str(manifest_id),
        "manifest_fingerprint": manifest_fingerprint,
        "record_count": record_count,
        "run_id": str(run_id),
        "report_id": str(report_id),
        "report_sha256": report_sha256,
        "year_batch_ids": [str(item) for item in year_batch_ids],
        "slot_batch_digests": list(slot_batch_digests),
        "freeze_id": str(freeze_id),
        "freeze_fingerprint": freeze_fingerprint,
        "selection_bias_calculation_id": str(selection_bias_calculation_id),
        "selection_bias_population_digest": selection_bias_population_digest,
    }


def _issue_development_source_attestation(
    context: _ActiveDevelopmentInvocation,
    run: evaluator.DevelopmentEvaluationRun,
    report: evaluator.DevelopmentEvaluationReport,
    *,
    _synthetic_test_only: bool = False,
) -> DevelopmentSourceAttestation:
    """Seal the actual one-shot run/report pair to its pre-evaluation revision.

    The optional synthetic route is private test support and always produces a
    receipt whose source kind is rejected by development authentication.
    """

    if (
        type(context) is not _ActiveDevelopmentInvocation
        or getattr(context, "_seal", None) is not _ACTIVE_INVOCATION_SEAL
        or context._run is not run
        or context._report is not report
        or type(run) is not evaluator.DevelopmentEvaluationRun
        or getattr(run, "_seal", None) is not evaluator._DEVELOPMENT_RUN_SEAL
        or type(report) is not evaluator.DevelopmentEvaluationReport
        or getattr(report, "_seal", None) is not evaluator._DEVELOPMENT_REPORT_SEAL
    ):
        raise OperatorError(OperatorFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    attempt_id = context.attempt_id
    invocation_id = context.invocation_id
    source_revision = context.source_revision
    source_kind = run.source_binding.kind.value
    if source_kind == "SYNTHETIC_TEST_ONLY":
        if not _synthetic_test_only:
            raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    elif source_kind != "ARCH150_D1R_ACCEPTED":
        raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    if (
        run.fold_evaluation_count != 480
        or not run.year_batches
        or any(not batch.complete for batch in run.year_batches)
        or tuple(batch.scored_year for batch in run.year_batches)
        != arch151.SCORED_YEARS
        or report.run_id != run.run_id
        or report.source_binding_id != run.source_binding.binding_id
        or report.manifest_id != arch151.CANONICAL_MANIFEST.manifest_id
        or report.manifest_fingerprint != arch151.CANONICAL_MANIFEST.fingerprint
        or report.record_count != 480
        or hashlib.sha256(report.canonical_json_bytes).hexdigest() != report.sha256
        or evaluator.serialize_development_evaluation(run) != report
    ):
        raise OperatorError(OperatorFailureCode.REPORT_INTEGRITY_FAILED)
    revision_digest = _source_revision_digest(source_revision, invocation_id)
    year_batch_ids = tuple(item.batch_id for item in run.year_batches)
    slot_batch_digests = tuple(item.batch_digest for item in run.slot_batches)
    material = _source_attestation_material(
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        source_revision=source_revision,
        source_revision_digest=revision_digest,
        source_kind=source_kind,
        source_binding_id=run.source_binding.binding_id,
        source_digest=run.source_digest,
        manifest_id=arch151.CANONICAL_MANIFEST.manifest_id,
        manifest_fingerprint=arch151.CANONICAL_MANIFEST.fingerprint,
        record_count=report.record_count,
        run_id=run.run_id,
        report_id=report.report_id,
        report_sha256=report.sha256,
        year_batch_ids=year_batch_ids,
        slot_batch_digests=slot_batch_digests,
        freeze_id=run.final_freeze.freeze_id,
        freeze_fingerprint=run.final_freeze.fingerprint,
        selection_bias_calculation_id=run.selection_bias.calculation_id,
        selection_bias_population_digest=run.selection_bias.population_digest,
    )
    body = arch151._canonical_json(material)
    return DevelopmentSourceAttestation(
        _seal=_SOURCE_ATTESTATION_SEAL,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        source_revision=source_revision,
        source_revision_digest=revision_digest,
        source_kind=source_kind,
        source_binding_id=run.source_binding.binding_id,
        source_digest=run.source_digest,
        manifest_id=arch151.CANONICAL_MANIFEST.manifest_id,
        manifest_fingerprint=arch151.CANONICAL_MANIFEST.fingerprint,
        record_count=report.record_count,
        run_id=run.run_id,
        report_id=report.report_id,
        report_sha256=report.sha256,
        year_batch_ids=year_batch_ids,
        slot_batch_digests=slot_batch_digests,
        freeze_id=run.final_freeze.freeze_id,
        freeze_fingerprint=run.final_freeze.fingerprint,
        selection_bias_calculation_id=run.selection_bias.calculation_id,
        selection_bias_population_digest=run.selection_bias.population_digest,
        canonical_json_bytes=body,
        attestation_id=uuid5(_SOURCE_ATTESTATION_NAMESPACE, body.decode("utf-8")),
        attestation_digest=hashlib.sha256(body).hexdigest(),
    )


def _validate_development_source_attestation(
    run: evaluator.DevelopmentEvaluationRun,
    report: evaluator.DevelopmentEvaluationReport,
    attestation: object,
    *,
    expected_revision: SourceRevision | None = None,
) -> DevelopmentSourceAttestation:
    if (
        type(attestation) is not DevelopmentSourceAttestation
        or getattr(attestation, "_seal", None) is not _SOURCE_ATTESTATION_SEAL
        or type(run) is not evaluator.DevelopmentEvaluationRun
        or type(report) is not evaluator.DevelopmentEvaluationReport
    ):
        raise arch151.AuthorizationUnavailableError(
            "authentication requires a source-issued run/report attestation"
        )
    try:
        verified = DevelopmentSourceAttestation(
            _seal=_SOURCE_ATTESTATION_SEAL,
            attempt_id=attestation.attempt_id,
            invocation_id=attestation.invocation_id,
            source_revision=attestation.source_revision,
            source_revision_digest=attestation.source_revision_digest,
            source_kind=attestation.source_kind,
            source_binding_id=attestation.source_binding_id,
            source_digest=attestation.source_digest,
            manifest_id=attestation.manifest_id,
            manifest_fingerprint=attestation.manifest_fingerprint,
            record_count=attestation.record_count,
            run_id=attestation.run_id,
            report_id=attestation.report_id,
            report_sha256=attestation.report_sha256,
            year_batch_ids=attestation.year_batch_ids,
            slot_batch_digests=attestation.slot_batch_digests,
            freeze_id=attestation.freeze_id,
            freeze_fingerprint=attestation.freeze_fingerprint,
            selection_bias_calculation_id=attestation.selection_bias_calculation_id,
            selection_bias_population_digest=attestation.selection_bias_population_digest,
            canonical_json_bytes=attestation.canonical_json_bytes,
            attestation_id=attestation.attestation_id,
            attestation_digest=attestation.attestation_digest,
        )
    except (AttributeError, OperatorError, TypeError, ValueError):
        raise arch151.AuthorizationUnavailableError(
            "source-issued run/report attestation is malformed"
        ) from None
    revision = verified.source_revision
    if (
        verified.source_kind != run.source_binding.kind.value
        or verified.source_binding_id != run.source_binding.binding_id
        or verified.source_digest != run.source_digest
        or verified.manifest_id != arch151.CANONICAL_MANIFEST.manifest_id
        or verified.manifest_fingerprint != arch151.CANONICAL_MANIFEST.fingerprint
        or verified.record_count != run.fold_evaluation_count
        or verified.run_id != run.run_id
        or verified.report_id != report.report_id
        or verified.report_sha256 != report.sha256
        or report.run_id != run.run_id
        or report.source_binding_id != run.source_binding.binding_id
        or verified.year_batch_ids != tuple(item.batch_id for item in run.year_batches)
        or verified.slot_batch_digests
        != tuple(item.batch_digest for item in run.slot_batches)
        or verified.freeze_id != run.final_freeze.freeze_id
        or verified.freeze_fingerprint != run.final_freeze.fingerprint
        or verified.selection_bias_calculation_id != run.selection_bias.calculation_id
        or verified.selection_bias_population_digest
        != run.selection_bias.population_digest
        or verified.invocation_id != _invocation_id(revision)
        or verified.source_revision_digest
        != _source_revision_digest(revision, verified.invocation_id)
        or (expected_revision is not None and revision != expected_revision)
        or evaluator.serialize_development_evaluation(run) != report
    ):
        raise arch151.AuthorizationUnavailableError(
            "source-issued attestation does not bind this run, report, or revision"
        )
    return verified


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        return path.is_symlink()
    except OSError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID) from None
    return bool(attributes & _REPARSE_ATTRIBUTE) or path.is_symlink()


def _validate_evidence_root(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_absolute():
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID)
    if path.exists():
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_ALREADY_EXISTS)
    parent = path.parent
    if not parent.is_dir():
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID)
    try:
        resolved_parent = parent.resolve(strict=True)
        repo_root = Path(__file__).resolve().parents[3]
        worktrees_root = _WORKTREES_ROOT.resolve(strict=False)
    except OSError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID) from None
    if (
        resolved_parent != parent
        or _is_within(resolved_parent, repo_root)
        or _is_within(resolved_parent, worktrees_root)
    ):
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID)
    for ancestor in (parent, *parent.parents):
        if ancestor.exists() and _is_reparse_point(ancestor):
            raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID)


def _canonical_bytes(value: object) -> bytes:
    try:
        return arch151._canonical_json(value)
    except (TypeError, ValueError):
        raise OperatorError(OperatorFailureCode.EVIDENCE_WRITE_FAILED) from None


def _write_once(path: Path, body: bytes, *, attempt_root: Path) -> str:
    if type(body) is not bytes or path.parent != attempt_root:
        raise OperatorError(OperatorFailureCode.EVIDENCE_WRITE_FAILED)
    if _is_reparse_point(attempt_root):
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID)
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_ALREADY_EXISTS) from None
    except OSError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_WRITE_FAILED) from None
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            if stream.write(body) != len(body):
                raise OperatorError(OperatorFailureCode.EVIDENCE_WRITE_FAILED)
            stream.flush()
            os.fsync(stream.fileno())
        observed = path.read_bytes()
    except OperatorError:
        raise
    except OSError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_WRITE_FAILED) from None
    digest = hashlib.sha256(body).hexdigest()
    if len(observed) != len(body) or hashlib.sha256(observed).hexdigest() != digest:
        raise OperatorError(OperatorFailureCode.EVIDENCE_WRITE_FAILED)
    return digest


def _create_attempt_root(path: Path) -> Path:
    _validate_evidence_root(path)
    try:
        path.mkdir()
        resolved = path.resolve(strict=True)
    except FileExistsError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_ALREADY_EXISTS) from None
    except OSError:
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID) from None
    if resolved != path or _is_reparse_point(path):
        raise OperatorError(OperatorFailureCode.EVIDENCE_ROOT_INVALID)
    return path


def _read_consumed_predecessor_binding() -> dict[str, object]:
    """Verify the immutable consumed E1 observation and derive its binding."""

    root = EVIDENCE_ROOT
    try:
        if (
            not root.is_dir()
            or root.is_symlink()
            or root.resolve(strict=True) != root
            or _is_reparse_point(root)
        ):
            raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
        paths = tuple(root.iterdir())
        if tuple(sorted(path.name for path in paths)) != tuple(
            sorted(name for name, _length, _digest in _PREDECESSOR_ARTIFACTS)
        ):
            raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
        records: dict[str, dict[str, object]] = {}
        for name, byte_length, expected_digest in _PREDECESSOR_ARTIFACTS:
            path = root / name
            if not path.is_file() or _is_reparse_point(path):
                raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
            raw = path.read_bytes()
            if (
                len(raw) != byte_length
                or hashlib.sha256(raw).hexdigest() != expected_digest
            ):
                raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
            value = json.loads(raw.decode("utf-8"))
            if type(value) is not dict or arch151._canonical_json(value) != raw:
                raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
            records[name] = value
    except OperatorError:
        raise
    except Exception:
        raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID) from None

    attempt = records["attempt.json"]
    revision = records["source-revision.json"]
    failure = records["operator-failure.json"]
    result = records["attempt-result.json"]
    expected_manifest_id = str(arch151.CANONICAL_MANIFEST.manifest_id)
    expected_manifest_fingerprint = arch151.CANONICAL_MANIFEST.fingerprint
    if not (
        attempt.get("schema") == _ATTEMPT_SCHEMA
        and attempt.get("status") == "STARTED"
        and attempt.get("attempt_id") == str(_PREDECESSOR_ATTEMPT_ID)
        and attempt.get("invocation_id") is None
        and attempt.get("automatic_retry") == "FORBIDDEN"
        and attempt.get("development_start") == "2016-01-01"
        and attempt.get("development_end") == "2023-12-31"
        and attempt.get("manifest_id") == expected_manifest_id
        and attempt.get("manifest_fingerprint") == expected_manifest_fingerprint
        and revision.get("schema") == _SOURCE_REVISION_SCHEMA
        and revision.get("attempt_id") == str(_PREDECESSOR_ATTEMPT_ID)
        and revision.get("invocation_id") == str(_PREDECESSOR_INVOCATION_ID)
        and revision.get("source_branch") == EXPECTED_BRANCH
        and revision.get("source_origin") == EXPECTED_ORIGIN
        and revision.get("source_head") == _PREDECESSOR_HEAD
        and revision.get("source_tree") == _PREDECESSOR_TREE
        and failure.get("schema") == _OPERATOR_FAILURE_SCHEMA
        and failure.get("attempt_id") == str(_PREDECESSOR_ATTEMPT_ID)
        and failure.get("invocation_id") == str(_PREDECESSOR_INVOCATION_ID)
        and failure.get("failure_code") == OperatorFailureCode.SOURCE_LOAD_FAILED.value
        and failure.get("failure_type") == "AuthorizationUnavailableError"
        and failure.get("source_head") == _PREDECESSOR_HEAD
        and failure.get("source_tree") == _PREDECESSOR_TREE
        and failure.get("year_artifacts") == []
        and result.get("schema") == _RESULT_SCHEMA
        and result.get("status") == OperatorStatus.FAILED.value
        and result.get("attempt_id") == str(_PREDECESSOR_ATTEMPT_ID)
        and result.get("invocation_id") == str(_PREDECESSOR_INVOCATION_ID)
        and result.get("manifest_id") == expected_manifest_id
        and result.get("manifest_fingerprint") == expected_manifest_fingerprint
        and result.get("attempted_years") == []
        and result.get("year_artifacts") == []
        and result.get("candidate_evaluation") == "NOT_EVALUATED"
        and result.get("report_id") is None
        and result.get("report_sha256") is None
        and result.get("source_binding_id") is None
        and result.get("source_digest") is None
        and result.get("failure_code") == OperatorFailureCode.SOURCE_LOAD_FAILED.value
        and result.get("failure_evidence_sha256") == _PREDECESSOR_ARTIFACTS[2][2]
        and result.get("automatic_retry") == "FORBIDDEN"
        and result.get("source_branch") == EXPECTED_BRANCH
        and result.get("source_origin") == EXPECTED_ORIGIN
        and result.get("source_head") == _PREDECESSOR_HEAD
        and result.get("source_tree") == _PREDECESSOR_TREE
    ):
        raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)

    material: dict[str, object] = {
        "schema": _PREDECESSOR_BINDING_SCHEMA,
        "attempt_id": str(_PREDECESSOR_ATTEMPT_ID),
        "invocation_id": str(_PREDECESSOR_INVOCATION_ID),
        "source": {
            "branch": EXPECTED_BRANCH,
            "origin": EXPECTED_ORIGIN,
            "head": _PREDECESSOR_HEAD,
            "tree": _PREDECESSOR_TREE,
        },
        "terminal": {
            "status": OperatorStatus.FAILED.value,
            "failure_code": OperatorFailureCode.SOURCE_LOAD_FAILED.value,
            "artifact": "attempt-result.json",
            "byte_length": _PREDECESSOR_ARTIFACTS[3][1],
            "sha256": _PREDECESSOR_ARTIFACTS[3][2],
        },
        "artifacts": [
            {"name": name, "byte_length": length, "sha256": digest}
            for name, length, digest in _PREDECESSOR_ARTIFACTS
        ],
    }
    binding_id = uuid5(
        _PREDECESSOR_BINDING_NAMESPACE,
        arch151._canonical_json(material).decode("utf-8"),
    )
    return {**material, "binding_id": str(binding_id)}


def preflight_successor_observation(expected_source_head: str) -> dict[str, object]:
    """Retired E2 route; it never revalidates mutable evidence or source."""

    del expected_source_head
    raise OperatorError(OperatorFailureCode.SUCCESSOR_ATTEMPT_CONSUMED)


def _predecessor_binding_for_root(root: Path) -> tuple[str, str] | None:
    path = root / "predecessor-binding.json"
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
        if (
            type(value) is not dict
            or value.get("schema") != _PREDECESSOR_BINDING_SCHEMA
            or arch151._canonical_json(value) != raw
        ):
            raise ValueError
        return str(value["binding_id"]), hashlib.sha256(raw).hexdigest()
    except Exception:
        raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID) from None


def _load_accepted_source_history() -> arch151.Arch150D1RSourceHistory:
    history = arch151.load_arch150_d1r_source_history()
    if type(history) is not arch151.Arch150D1RSourceHistory:
        raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    if (
        not arch151._is_sha256(history.source_digest)
        or not arch151._is_sha256(history.validated_input_digest)
        or history.dataset_id != arch151.ARCH150_D1R_DATASET_ID
    ):
        raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    sessions_by_symbol = {
        symbol: tuple(
            item.session_date
            for item in history._session_projections
            if item.symbol == symbol
        )
        for symbol in arch151.INITIAL_UNIVERSE
    }
    expected_sessions = tuple(
        session
        for session in arch151._SESSION_AUTHORITY.published.sessions
        if arch151.DEVELOPMENT_START <= session < arch151.DEVELOPMENT_END
    )
    if any(sessions != expected_sessions for sessions in sessions_by_symbol.values()):
        raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    return history


def _timestamp_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise OperatorError(OperatorFailureCode.YEAR_EVALUATION_FAILED)
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _fill_material(fill: evaluator.FillRecord | None) -> dict[str, object] | None:
    if fill is None:
        return None
    return {
        "fill_id": str(fill.fill_id),
        "side": fill.side.value,
        "timestamp": _timestamp_text(fill.timestamp),
        "reference_price": arch151._decimal_text(fill.reference_price),
        "execution_price": arch151._decimal_text(fill.execution_price),
        "quantity": arch151._decimal_text(fill.quantity),
        "adverse_cost": arch151._decimal_text(fill.adverse_cost),
        "cash_before": arch151._decimal_text(fill.cash_before),
        "cash_after": arch151._decimal_text(fill.cash_after),
    }


def _replay_failure_material(
    failure: evaluator.ReplayFailureEvidence,
) -> dict[str, object]:
    return {
        "failure_id": str(failure.failure_id),
        "kind": failure.kind.value,
        "session_date": failure.session_date.isoformat(),
        "liquidation_boundary": _timestamp_text(failure.liquidation_boundary),
        "entry_signal_timestamp": _timestamp_text(failure.entry_signal_timestamp),
        "entry_fill": _fill_material(failure.entry_fill),
        "quantity": (
            arch151._decimal_text(failure.quantity)
            if failure.quantity is not None
            else None
        ),
        "initial_stop_reference": (
            arch151._decimal_text(failure.initial_stop_reference)
            if failure.initial_stop_reference is not None
            else None
        ),
        "active_stop_reference": (
            arch151._decimal_text(failure.active_stop_reference)
            if failure.active_stop_reference is not None
            else None
        ),
        "target_reference": (
            arch151._decimal_text(failure.target_reference)
            if failure.target_reference is not None
            else None
        ),
        "pending_exit_reason": (
            failure.pending_exit_reason.value
            if failure.pending_exit_reason is not None
            else None
        ),
        "last_observed_timestamp": _timestamp_text(failure.last_observed_timestamp),
        "evidence_digest": failure.evidence_digest,
    }


def _batch_failure_records(batch: object) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for replay in getattr(batch, "evaluations", ()):
        failure = getattr(replay, "failure", None)
        if failure is None:
            continue
        if type(failure) is not evaluator.ReplayFailureEvidence:
            raise OperatorError(OperatorFailureCode.YEAR_EVALUATION_FAILED)
        records.append(
            {
                "replay_id": str(replay.replay_id),
                "replay_digest": replay.replay_digest,
                "slot_id": str(replay.slot.slot_id),
                "program_id": str(replay.slot.program_id),
                "symbol": replay.slot.symbol,
                "scored_year": replay.scored_year,
                "cost_case": replay.cost_case.value,
                "failure": _replay_failure_material(failure),
            }
        )
    return tuple(records)


def _year_batch_material(
    batch: object,
    *,
    revision: SourceRevision,
    attempt_id: UUID,
    invocation_id: UUID,
) -> dict[str, object]:
    evaluations = tuple(getattr(batch, "evaluations", ()))
    records = tuple(
        {
            "replay_id": str(item.replay_id),
            "replay_digest": item.replay_digest,
            "slot_id": str(item.slot.slot_id),
            "program_id": str(item.slot.program_id),
            "symbol": item.slot.symbol,
            "scored_year": item.scored_year,
            "economics_case": item.cost_case.value,
            "complete": item.complete,
            "failure_id": str(item.failure.failure_id)
            if item.failure is not None
            else None,
        }
        for item in evaluations
    )
    return {
        "schema": _YEAR_EVIDENCE_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_branch": revision.branch,
        "source_origin": revision.origin,
        "source_head": revision.head,
        "source_tree": revision.tree,
        "scored_year": batch.scored_year,
        "batch_id": str(batch.batch_id),
        "source_digest": batch.source_digest,
        "source_binding_id": str(batch.source_binding.binding_id),
        "manifest_id": str(batch.manifest_id),
        "manifest_fingerprint": batch.manifest_fingerprint,
        "expected_replay_count": len(arch151.CANONICAL_SLOTS)
        * len(arch151.EVALUATION_ECONOMICS_ORDER),
        "observed_replay_count": len(records),
        "complete": batch.complete,
        "records": list(records),
    }


def _root_failure(error: Exception) -> Exception:
    if isinstance(error, evaluator.AnnualReplayFailure) and isinstance(
        error.__cause__, Exception
    ):
        return error.__cause__
    return error


def _operator_failure_code(error: Exception) -> OperatorFailureCode:
    classified = _root_failure(error)
    if isinstance(classified, OperatorError):
        return classified.code
    if isinstance(classified, arch151.AuthorizationUnavailableError):
        return OperatorFailureCode.SOURCE_LOAD_FAILED
    if isinstance(classified, evaluator.EvaluationIntegrityError):
        return OperatorFailureCode.DEVELOPMENT_COMPOSITION_FAILED
    if isinstance(classified, OSError):
        return OperatorFailureCode.EVIDENCE_WRITE_FAILED
    return OperatorFailureCode.UNCLASSIFIED_FAILURE


def _source_load_reason(error: Exception) -> str | None:
    classified = _root_failure(error)
    if not isinstance(classified, arch151.AuthorizationUnavailableError):
        return None
    reason = classified.source_load_reason
    return reason.value if type(reason) is arch151.SourceLoadFailureReason else None


def _closed_failure_reason(error: Exception) -> ClosedFailureReason:
    classified = _root_failure(error)
    if isinstance(classified, arch151.AuthorizationUnavailableError):
        return ClosedFailureReason.AUTHORITY_UNAVAILABLE
    if isinstance(classified, ArithmeticError):
        return ClosedFailureReason.ARITHMETIC_FAILURE
    if isinstance(classified, evaluator.EvaluationIntegrityError):
        return ClosedFailureReason.REPOSITORY_VALIDATION_FAILURE
    if isinstance(classified, OSError):
        return ClosedFailureReason.IO_FAILURE
    if isinstance(classified, OperatorError):
        return ClosedFailureReason.OPERATOR_GATE_FAILURE
    return ClosedFailureReason.UNEXPECTED_EXCEPTION


def _failure_attribution_material(
    error: Exception,
    stage: OperatorFailureStage,
    *,
    scored_year: int | None = None,
) -> dict[str, object]:
    root_error = _root_failure(error)
    material: dict[str, object] = {
        "failure_stage": stage.value,
        "closed_failure_reason": _closed_failure_reason(root_error).value,
        "failure_type": type(root_error).__name__,
        "scored_year": scored_year,
    }
    replay_context = (
        error.context if isinstance(error, evaluator.AnnualReplayFailure) else None
    )
    if replay_context is not None:
        material.update(
            {
                "program_id": str(replay_context.program_id),
                "slot_id": str(replay_context.slot_id),
                "symbol": replay_context.symbol,
                "cost_case": replay_context.cost_case.value
                if replay_context.cost_case is not None
                else None,
                "session_date": replay_context.session_date.isoformat()
                if replay_context.session_date is not None
                else None,
                "operation_stage": replay_context.operation_stage.value,
            }
        )
        material["scored_year"] = replay_context.scored_year
    repo_root = Path(__file__).resolve().parents[3]
    frame = root_error.__traceback__
    source_frame = None
    while frame is not None:
        try:
            source_path = Path(frame.tb_frame.f_code.co_filename).relative_to(repo_root)
        except ValueError:
            frame = frame.tb_next
            continue
        if ".." in source_path.parts:
            frame = frame.tb_next
            continue
        if source_path.parts[:2] == ("src", "trading_bot"):
            source_frame = (
                source_path.as_posix(),
                frame.tb_lineno,
                frame.tb_frame.f_code.co_name,
            )
        frame = frame.tb_next
    if source_frame is not None:
        path, line, function = source_frame
        material["repository_function"] = function
        material["source_location"] = f"{path}:{line}"
    return material


def _write_terminal(
    *,
    root: Path,
    attempt_id: UUID,
    invocation_id: UUID | None,
    revision: SourceRevision | None,
    status: OperatorStatus,
    failure_code: OperatorFailureCode | None,
    year_artifacts: tuple[dict[str, object], ...],
    source_digest: str | None = None,
    source_binding_id: UUID | None = None,
    report_id: UUID | None = None,
    report_sha256: str | None = None,
    source_attestation: DevelopmentSourceAttestation | None = None,
    development_evidence_handoff: DevelopmentEvidenceHandoff | None = None,
    failure_evidence_sha256: str | None = None,
    incomplete_evidence_sha256: str | None = None,
) -> OperatorOutcome:
    predecessor_binding = _predecessor_binding_for_root(root)
    terminal = {
        "schema": (
            _SUCCESSOR_RESULT_SCHEMA
            if predecessor_binding is not None
            else _RESULT_SCHEMA
        ),
        "status": status.value,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id) if invocation_id is not None else None,
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "attempted_years": [item["scored_year"] for item in year_artifacts],
        "year_artifacts": list(year_artifacts),
        "candidate_evaluation": (
            "COMPLETED" if status is OperatorStatus.COMPLETED else "NOT_EVALUATED"
        ),
        "report_id": str(report_id) if report_id is not None else None,
        "report_sha256": report_sha256,
        "failure_code": failure_code.value if failure_code is not None else None,
        "failure_evidence_sha256": failure_evidence_sha256,
        "incomplete_evidence_sha256": incomplete_evidence_sha256,
        "automatic_retry": "FORBIDDEN",
    }
    if predecessor_binding is not None:
        terminal.update(
            {
                "predecessor_binding_id": predecessor_binding[0],
                "predecessor_binding_sha256": predecessor_binding[1],
            }
        )
    if revision is not None:
        terminal.update(
            {
                "source_branch": revision.branch,
                "source_origin": revision.origin,
                "source_head": revision.head,
                "source_tree": revision.tree,
                "source_digest": source_digest,
                "source_binding_id": str(source_binding_id)
                if source_binding_id is not None
                else None,
            }
        )
    if source_attestation is not None:
        terminal.update(
            {
                "source_attestation_id": str(source_attestation.attestation_id),
                "source_attestation_digest": source_attestation.attestation_digest,
            }
        )
    if development_evidence_handoff is not None:
        authenticated = development_evidence_handoff.authenticated_evidence
        selection = development_evidence_handoff.selection_bias_evidence
        terminal.update(
            {
                "development_evidence_id": str(authenticated.evidence_id),
                "development_evidence_digest": authenticated.evidence_digest,
                "candidate_slot_id": str(authenticated.candidate_slot_id),
                "freeze_id": str(development_evidence_handoff.final_freeze.freeze_id),
                "selection_bias_evidence_id": str(selection.evidence_id),
                "selection_bias_evidence_digest": selection.evidence_digest,
            }
        )
    _write_once(
        root / "attempt-result.json",
        _canonical_bytes(terminal),
        attempt_root=root,
    )
    return OperatorOutcome(
        status,
        attempt_id,
        invocation_id,
        root,
        report_id,
        report_sha256,
        failure_code,
        source_attestation,
        development_evidence_handoff,
    )


def _persist_operator_failure(
    *,
    root: Path,
    attempt_id: UUID,
    invocation_id: UUID | None,
    revision: SourceRevision | None,
    error: Exception,
    stage: OperatorFailureStage,
    year_artifacts: tuple[dict[str, object], ...],
    scored_year: int | None = None,
    source_digest: str | None = None,
    source_binding_id: UUID | None = None,
) -> OperatorOutcome:
    code = _operator_failure_code(error)
    predecessor_binding = _predecessor_binding_for_root(root)
    source_load_reason = _source_load_reason(error)
    evidence = {
        "schema": _OPERATOR_FAILURE_SCHEMA_V3,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id) if invocation_id is not None else None,
        "failure_code": code.value,
        "failure_type": type(_root_failure(error)).__name__,
        "failure_attribution": _failure_attribution_material(
            error, stage, scored_year=scored_year
        ),
        "year_artifacts": list(year_artifacts),
    }
    if source_load_reason is not None:
        evidence["source_load_reason"] = source_load_reason
    if predecessor_binding is not None:
        evidence.update(
            {
                "predecessor_binding_id": predecessor_binding[0],
                "predecessor_binding_sha256": predecessor_binding[1],
            }
        )
    if revision is not None:
        evidence.update({"source_head": revision.head, "source_tree": revision.tree})
    evidence_bytes = _canonical_bytes(evidence)
    evidence_digest = _write_once(
        root / "operator-failure.json", evidence_bytes, attempt_root=root
    )
    return _write_terminal(
        root=root,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        revision=revision,
        status=OperatorStatus.FAILED,
        failure_code=code,
        year_artifacts=year_artifacts,
        source_digest=source_digest,
        source_binding_id=source_binding_id,
        failure_evidence_sha256=evidence_digest,
    )


def _persist_replay_failure(
    *,
    root: Path,
    attempt_id: UUID,
    invocation_id: UUID,
    revision: SourceRevision,
    batch: object,
    failures: tuple[dict[str, object], ...],
    year_artifacts: tuple[dict[str, object], ...],
) -> OperatorOutcome:
    evidence = {
        "schema": _REPLAY_FAILURE_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_head": revision.head,
        "source_tree": revision.tree,
        "source_digest": batch.source_digest,
        "source_binding_id": str(batch.source_binding.binding_id),
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "scored_year": batch.scored_year,
        "year_batch_id": str(batch.batch_id),
        "failures": list(failures),
        "year_artifacts": list(year_artifacts),
        "candidate_evaluation": "NOT_EVALUATED",
        "automatic_retry": "FORBIDDEN",
    }
    digest = _write_once(
        root / "replay-integrity-failures.json",
        _canonical_bytes(evidence),
        attempt_root=root,
    )
    return _write_terminal(
        root=root,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        revision=revision,
        status=OperatorStatus.REPLAY_INTEGRITY_FAILURE,
        failure_code=None,
        year_artifacts=year_artifacts,
        source_digest=batch.source_digest,
        source_binding_id=batch.source_binding.binding_id,
        failure_evidence_sha256=digest,
    )


def _persist_incomplete(
    *,
    root: Path,
    attempt_id: UUID,
    invocation_id: UUID,
    revision: SourceRevision,
    batch: object,
    year_artifacts: tuple[dict[str, object], ...],
) -> OperatorOutcome:
    evidence = {
        "schema": _INCOMPLETE_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_head": revision.head,
        "source_tree": revision.tree,
        "source_digest": batch.source_digest,
        "source_binding_id": str(batch.source_binding.binding_id),
        "scored_year": batch.scored_year,
        "year_batch_id": str(batch.batch_id),
        "expected_replay_count": len(arch151.CANONICAL_SLOTS)
        * len(arch151.EVALUATION_ECONOMICS_ORDER),
        "observed_replay_count": len(batch.evaluations),
        "observed_replay_ids": [str(item.replay_id) for item in batch.evaluations],
        "year_artifacts": list(year_artifacts),
        "candidate_evaluation": "NOT_EVALUATED",
        "automatic_retry": "FORBIDDEN",
    }
    digest = _write_once(
        root / "incomplete-evaluation.json",
        _canonical_bytes(evidence),
        attempt_root=root,
    )
    return _write_terminal(
        root=root,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        revision=revision,
        status=OperatorStatus.INCOMPLETE,
        failure_code=None,
        year_artifacts=year_artifacts,
        source_digest=batch.source_digest,
        source_binding_id=batch.source_binding.binding_id,
        incomplete_evidence_sha256=digest,
    )


def _execute_development_evaluation_once(
    *,
    evidence_root: Path,
    source_revision_override: SourceRevision | None = None,
    predecessor_binding: dict[str, object] | None = None,
) -> OperatorOutcome:
    """Private fixed-contract execution engine; not a CLI override surface."""

    if predecessor_binding is not None and evidence_root != SUCCESSOR_EVIDENCE_ROOT:
        raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
    root = _create_attempt_root(evidence_root)
    attempt_id = uuid4()
    predecessor_digest = None
    if predecessor_binding is not None:
        predecessor_bytes = _canonical_bytes(predecessor_binding)
        predecessor_digest = _write_once(
            root / "predecessor-binding.json",
            predecessor_bytes,
            attempt_root=root,
        )
    claim = {
        "schema": (
            _SUCCESSOR_ATTEMPT_SCHEMA
            if predecessor_binding is not None
            else _ATTEMPT_SCHEMA
        ),
        "status": "STARTED",
        "attempt_id": str(attempt_id),
        "invocation_id": None,
        "development_start": "2016-01-01",
        "development_end": "2023-12-31",
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "automatic_retry": "FORBIDDEN",
    }
    if predecessor_binding is not None:
        claim.update(
            {
                "predecessor_binding_id": predecessor_binding["binding_id"],
                "predecessor_binding_sha256": predecessor_digest,
            }
        )
    _write_once(root / "attempt.json", _canonical_bytes(claim), attempt_root=root)
    try:
        revision = source_revision_override or _read_source_revision()
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=None,
            revision=None,
            error=error,
            stage=OperatorFailureStage.SOURCE_REVISION,
            year_artifacts=(),
        )
    invocation_id = _invocation_id(revision)
    context = _ActiveDevelopmentInvocation(
        _seal=_ACTIVE_INVOCATION_SEAL,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        source_revision=revision,
    )
    source_revision = {
        "schema": (
            _SUCCESSOR_SOURCE_REVISION_SCHEMA
            if predecessor_binding is not None
            else _SOURCE_REVISION_SCHEMA
        ),
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_branch": revision.branch,
        "source_origin": revision.origin,
        "source_head": revision.head,
        "source_tree": revision.tree,
    }
    if predecessor_binding is not None:
        source_revision.update(
            {
                "predecessor_binding_id": predecessor_binding["binding_id"],
                "predecessor_binding_sha256": predecessor_digest,
            }
        )
    try:
        _write_once(
            root / "source-revision.json",
            _canonical_bytes(source_revision),
            attempt_root=root,
        )
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
            stage=OperatorFailureStage.SOURCE_REVISION_EVIDENCE,
            year_artifacts=(),
        )
    year_artifacts: list[dict[str, object]] = []
    batches: list[evaluator.CanonicalYearBatch] = []
    history: arch151.Arch150D1RSourceHistory | None = None
    if predecessor_binding is not None:
        try:
            if _read_consumed_predecessor_binding() != predecessor_binding:
                raise OperatorError(OperatorFailureCode.PREDECESSOR_EVIDENCE_INVALID)
        except Exception as error:
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=error,
                stage=OperatorFailureStage.PREDECESSOR_EVIDENCE,
                year_artifacts=(),
            )
    try:
        history = _load_accepted_source_history()
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
            stage=OperatorFailureStage.SOURCE_LOAD,
            year_artifacts=(),
        )
    for scored_year in arch151.SCORED_YEARS:
        try:
            batch = evaluator.simulate_canonical_year(history, scored_year)
            if (
                batch.scored_year != scored_year
                or batch.source_digest != history.source_digest
            ):
                raise OperatorError(OperatorFailureCode.YEAR_EVALUATION_FAILED)
        except Exception as error:
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=error,
                stage=OperatorFailureStage.ANNUAL_SIMULATION,
                year_artifacts=tuple(year_artifacts),
                scored_year=scored_year,
                source_digest=history.source_digest,
            )
        try:
            material = _year_batch_material(
                batch,
                revision=revision,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
            )
        except Exception as error:
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=error,
                stage=OperatorFailureStage.ANNUAL_EVIDENCE_CONSTRUCTION,
                year_artifacts=tuple(year_artifacts),
                scored_year=scored_year,
                source_digest=history.source_digest,
            )
        try:
            year_bytes = _canonical_bytes(material)
        except Exception as error:
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=error,
                stage=OperatorFailureStage.ANNUAL_EVIDENCE_SERIALIZATION,
                year_artifacts=tuple(year_artifacts),
                scored_year=scored_year,
                source_digest=history.source_digest,
            )
        year_name = f"year-{scored_year}.json"
        try:
            year_digest = _write_once(root / year_name, year_bytes, attempt_root=root)
        except Exception as error:
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=error,
                stage=OperatorFailureStage.ANNUAL_EVIDENCE_PERSISTENCE,
                year_artifacts=tuple(year_artifacts),
                scored_year=scored_year,
                source_digest=history.source_digest,
            )
        batches.append(batch)
        artifact = {
            "scored_year": scored_year,
            "batch_id": str(batch.batch_id),
            "path": year_name,
            "sha256": year_digest,
            "record_count": len(batch.evaluations),
            "complete": batch.complete,
        }
        year_artifacts.append(artifact)
        failures = _batch_failure_records(batch)
        if failures:
            return _persist_replay_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                batch=batch,
                failures=failures,
                year_artifacts=tuple(year_artifacts),
            )
        if not batch.complete:
            return _persist_incomplete(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                batch=batch,
                year_artifacts=tuple(year_artifacts),
            )
    try:
        # The exact year batches are retained in memory for the single source
        # composition. No disk reader or continuation/recovery path exists.
        run = evaluator.compose_development_evaluation(tuple(batches))
        context.bind_run(run)
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
            stage=OperatorFailureStage.DEVELOPMENT_COMPOSITION,
            year_artifacts=tuple(year_artifacts),
            source_digest=history.source_digest,
        )
    try:
        report = evaluator.serialize_development_evaluation(run)
        report_bytes = report.canonical_json_bytes
        if (
            type(report_bytes) is not bytes
            or hashlib.sha256(report_bytes).hexdigest() != report.sha256
            or report.run_id != run.run_id
        ):
            raise OperatorError(OperatorFailureCode.REPORT_INTEGRITY_FAILED)
        context.bind_report(report)
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
            stage=OperatorFailureStage.REPORT_SERIALIZATION,
            year_artifacts=tuple(year_artifacts),
            source_digest=history.source_digest,
            source_binding_id=run.source_binding.binding_id,
        )
    try:
        report_digest = _write_once(
            root / "development-report.json", report_bytes, attempt_root=root
        )
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
            stage=OperatorFailureStage.REPORT_PERSISTENCE,
            year_artifacts=tuple(year_artifacts),
            source_digest=history.source_digest,
            source_binding_id=run.source_binding.binding_id,
        )
    if report_digest != report.sha256:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=OperatorError(OperatorFailureCode.REPORT_INTEGRITY_FAILED),
            stage=OperatorFailureStage.REPORT_PERSISTENCE,
            year_artifacts=tuple(year_artifacts),
            source_digest=history.source_digest,
            source_binding_id=run.source_binding.binding_id,
        )
    try:
        source_attestation = _issue_development_source_attestation(
            context,
            run,
            report,
        )
        persisted_attestation_digest = _write_once(
            root / "source-attestation.json",
            source_attestation.canonical_json_bytes,
            attempt_root=root,
        )
        if persisted_attestation_digest != source_attestation.attestation_digest:
            raise OperatorError(OperatorFailureCode.REPORT_INTEGRITY_FAILED)
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
            stage=OperatorFailureStage.SOURCE_ATTESTATION,
            year_artifacts=tuple(year_artifacts),
            source_digest=history.source_digest,
            source_binding_id=run.source_binding.binding_id,
        )
    development_evidence_handoff = None
    if (
        getattr(getattr(run, "final_freeze", None), "status", None)
        is arch151.FinalFreezeStatus.ONE_CANDIDATE_FROZEN
    ):
        try:
            authenticated_evidence = evaluator.authenticate_development_evidence(
                run, report, source_attestation
            )
            candidate_index = next(
                index
                for index, slot in enumerate(arch151.CANONICAL_SLOTS)
                if slot.slot_id == run.final_freeze.candidate_slot_id
            )
            development_evidence_handoff = DevelopmentEvidenceHandoff(
                _seal=_DEVELOPMENT_EVIDENCE_HANDOFF_SEAL,
                authenticated_evidence=authenticated_evidence,
                final_freeze=run.final_freeze,
                selection_bias_evidence=run.selection_bias.evidence[candidate_index],
                source_attestation=source_attestation,
            )
        except Exception as error:
            classified_error = (
                OperatorError(OperatorFailureCode.DEVELOPMENT_COMPOSITION_FAILED)
                if isinstance(error, arch151.AuthorizationUnavailableError)
                else error
            )
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=classified_error,
                stage=OperatorFailureStage.DEVELOPMENT_EVIDENCE_ISSUANCE,
                year_artifacts=tuple(year_artifacts),
                source_digest=history.source_digest,
                source_binding_id=run.source_binding.binding_id,
            )
    return _write_terminal(
        root=root,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        revision=revision,
        status=OperatorStatus.COMPLETED,
        failure_code=None,
        year_artifacts=tuple(year_artifacts),
        source_digest=history.source_digest,
        source_binding_id=run.source_binding.binding_id,
        report_id=report.report_id,
        report_sha256=report_digest,
        source_attestation=source_attestation,
        development_evidence_handoff=development_evidence_handoff,
    )


def run_development_evaluation_once() -> OperatorOutcome:
    """Retired E1 route; its consumed root is never a successor route."""

    raise OperatorError(OperatorFailureCode.PREDECESSOR_ATTEMPT_CONSUMED)


def run_successor_evaluation_once(expected_source_head: str) -> OperatorOutcome:
    """Retired E2 route; missing evidence roots never make it reusable."""

    del expected_source_head
    raise OperatorError(OperatorFailureCode.SUCCESSOR_ATTEMPT_CONSUMED)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=operator_help())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight-successor", action="store_true")
    modes.add_argument("--run-successor", action="store_true")
    parser.add_argument("--expected-source-head")
    arguments = parser.parse_args(None if argv is None else list(argv))
    if not (arguments.preflight_successor or arguments.run_successor) and (
        arguments.expected_source_head is not None
    ):
        parser.error("--expected-source-head requires a successor mode")
    if arguments.preflight_successor or arguments.run_successor:
        print("STATUS=FAILED")
        print("FAILURE_CODE=" + OperatorFailureCode.SUCCESSOR_ATTEMPT_CONSUMED.value)
        return 2
    else:
        print("STATUS=FAILED")
        print("FAILURE_CODE=" + OperatorFailureCode.PREDECESSOR_ATTEMPT_CONSUMED.value)
        return 2


__all__ = (
    "EVIDENCE_ROOT",
    "SUCCESSOR_EVIDENCE_ROOT",
    "EXPECTED_BRANCH",
    "EXPECTED_ORIGIN",
    "EXPECTED_WORKTREE",
    "OperatorError",
    "OperatorFailureCode",
    "OperatorOutcome",
    "OperatorStatus",
    "DevelopmentSourceAttestation",
    "DevelopmentEvidenceHandoff",
    "SourceRevision",
    "main",
    "operator_help",
    "preflight_successor_observation",
    "run_development_evaluation_once",
    "run_successor_evaluation_once",
)


if __name__ == "__main__":
    raise SystemExit(main())
