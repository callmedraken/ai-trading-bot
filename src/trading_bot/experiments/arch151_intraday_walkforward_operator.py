"""One-shot, offline Arch151 development evaluation evidence operator.

Import is inert. The no-argument command is a future separately authorized
operation: it reads only the fixed accepted Arch150 D1R development source and
writes once to the fixed external F: evidence root. It has no source, candidate,
holdout, extension, or output-path selection arguments.
"""

from __future__ import annotations

import argparse
import hashlib
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
_ATTEMPT_SCHEMA = "arch151-development-operator-attempt/v1"
_SOURCE_REVISION_SCHEMA = "arch151-development-source-revision/v1"
_RESULT_SCHEMA = "arch151-development-operator-result/v3"
_SOURCE_ATTESTATION_SCHEMA = "arch151-development-source-attestation/v1"
_YEAR_EVIDENCE_SCHEMA = "arch151-development-year-evidence/v1"
_REPLAY_FAILURE_SCHEMA = "arch151-replay-integrity-failure-evidence/v1"
_INCOMPLETE_SCHEMA = "arch151-development-incomplete-evidence/v1"
_OPERATOR_FAILURE_SCHEMA = "arch151-development-operator-failure/v1"
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
    YEAR_EVALUATION_FAILED = "YEAR_EVALUATION_FAILED"
    DEVELOPMENT_COMPOSITION_FAILED = "DEVELOPMENT_COMPOSITION_FAILED"
    REPORT_SERIALIZATION_FAILED = "REPORT_SERIALIZATION_FAILED"
    REPORT_INTEGRITY_FAILED = "REPORT_INTEGRITY_FAILED"
    UNCLASSIFIED_FAILURE = "UNCLASSIFIED_FAILURE"


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
        "Runs the fixed Arch151 2016-2023 development evaluation once. "
        "The command has no source or period overrides; it refuses an existing "
        "evidence root and never retries or overwrites an attempt."
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


def _load_accepted_source_history() -> arch151.Arch150D1RSourceHistory:
    history = arch151.load_arch150_d1r_source_history()
    if type(history) is not arch151.Arch150D1RSourceHistory:
        raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    if (
        not arch151._is_sha256(history.source_digest)
        or history.dataset_id != arch151.ARCH150_D1R_DATASET_ID
    ):
        raise OperatorError(OperatorFailureCode.SOURCE_HISTORY_INVALID)
    sessions = tuple(item.session_date for item in history._session_projections)
    if not sessions or any(not 2016 <= item.year <= 2023 for item in sessions):
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


def _operator_failure_code(error: Exception) -> OperatorFailureCode:
    if isinstance(error, OperatorError):
        return error.code
    if isinstance(error, arch151.AuthorizationUnavailableError):
        return OperatorFailureCode.SOURCE_LOAD_FAILED
    if isinstance(error, evaluator.EvaluationIntegrityError):
        return OperatorFailureCode.DEVELOPMENT_COMPOSITION_FAILED
    if isinstance(error, OSError):
        return OperatorFailureCode.EVIDENCE_WRITE_FAILED
    return OperatorFailureCode.UNCLASSIFIED_FAILURE


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
    terminal = {
        "schema": _RESULT_SCHEMA,
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
    year_artifacts: tuple[dict[str, object], ...],
    source_digest: str | None = None,
    source_binding_id: UUID | None = None,
) -> OperatorOutcome:
    code = _operator_failure_code(error)
    evidence = {
        "schema": _OPERATOR_FAILURE_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id) if invocation_id is not None else None,
        "failure_code": code.value,
        "failure_type": type(error).__name__,
        "year_artifacts": list(year_artifacts),
    }
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


def run_development_evaluation_once() -> OperatorOutcome:
    """Run the fixed development-only source operation once, with no overrides."""

    root = _create_attempt_root(EVIDENCE_ROOT)
    attempt_id = uuid4()
    claim = {
        "schema": _ATTEMPT_SCHEMA,
        "status": "STARTED",
        "attempt_id": str(attempt_id),
        "invocation_id": None,
        "development_start": "2016-01-01",
        "development_end": "2023-12-31",
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "automatic_retry": "FORBIDDEN",
    }
    _write_once(root / "attempt.json", _canonical_bytes(claim), attempt_root=root)
    try:
        revision = _read_source_revision()
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=None,
            revision=None,
            error=error,
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
        "schema": _SOURCE_REVISION_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_branch": revision.branch,
        "source_origin": revision.origin,
        "source_head": revision.head,
        "source_tree": revision.tree,
    }
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
            year_artifacts=(),
        )
    year_artifacts: list[dict[str, object]] = []
    batches: list[evaluator.CanonicalYearBatch] = []
    history: arch151.Arch150D1RSourceHistory | None = None
    try:
        history = _load_accepted_source_history()
    except Exception as error:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=error,
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
            material = _year_batch_material(
                batch,
                revision=revision,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
            )
            year_bytes = _canonical_bytes(material)
        except Exception as error:
            return _persist_operator_failure(
                root=root,
                attempt_id=attempt_id,
                invocation_id=invocation_id,
                revision=revision,
                error=error,
                year_artifacts=tuple(year_artifacts),
                source_digest=history.source_digest,
            )
        year_name = f"year-{scored_year}.json"
        year_digest = _write_once(root / year_name, year_bytes, attempt_root=root)
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
            year_artifacts=tuple(year_artifacts),
            source_digest=history.source_digest,
            source_binding_id=run.source_binding.binding_id,
        )
    report_digest = _write_once(
        root / "development-report.json", report_bytes, attempt_root=root
    )
    if report_digest != report.sha256:
        return _persist_operator_failure(
            root=root,
            attempt_id=attempt_id,
            invocation_id=invocation_id,
            revision=revision,
            error=OperatorError(OperatorFailureCode.REPORT_INTEGRITY_FAILED),
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


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=operator_help())
    parser.parse_args(None if argv is None else list(argv))
    try:
        outcome = run_development_evaluation_once()
    except OperatorError as error:
        print("STATUS=FAILED")
        print("FAILURE_CODE=" + error.code.value)
        return 2
    print("STATUS=" + outcome.status.value)
    if outcome.attempt_id is not None:
        print("ATTEMPT_ID=" + str(outcome.attempt_id))
    if outcome.invocation_id is not None:
        print("INVOCATION_ID=" + str(outcome.invocation_id))
    if outcome.evidence_root is not None:
        print("EVIDENCE_ROOT=" + str(outcome.evidence_root))
    if outcome.report_sha256 is not None:
        print("REPORT_SHA256=" + outcome.report_sha256)
    if outcome.source_attestation is not None:
        print("SOURCE_ATTESTATION_ID=" + str(outcome.source_attestation.attestation_id))
        print(
            "SOURCE_ATTESTATION_DIGEST=" + outcome.source_attestation.attestation_digest
        )
    if outcome.development_evidence_handoff is not None:
        handoff = outcome.development_evidence_handoff
        print(
            "DEVELOPMENT_EVIDENCE_ID=" + str(handoff.authenticated_evidence.evidence_id)
        )
        print(
            "DEVELOPMENT_EVIDENCE_DIGEST="
            + handoff.authenticated_evidence.evidence_digest
        )
        print("CANDIDATE_SLOT_ID=" + str(handoff.final_freeze.candidate_slot_id))
        print(
            "SELECTION_BIAS_EVIDENCE_ID="
            + str(handoff.selection_bias_evidence.evidence_id)
        )
        print(
            "SELECTION_BIAS_EVIDENCE_DIGEST="
            + handoff.selection_bias_evidence.evidence_digest
        )
    if outcome.failure_code is not None:
        print("FAILURE_CODE=" + outcome.failure_code.value)
    return 0 if outcome.status is OperatorStatus.COMPLETED else 2


__all__ = (
    "EVIDENCE_ROOT",
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
    "run_development_evaluation_once",
)


if __name__ == "__main__":
    raise SystemExit(main())
