"""E4 read-only preflight and one-shot offline development evidence operator.

Import is inert. The consumed E1 and E2 public execution routes are retired and
cannot load custody or create attempts. E4 exposes only its fixed preflight,
smoke, and full-development campaign modes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from trading_bot.experiments import arch150_g1_discovery as arch150_d1r
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
OFFLINE_EVIDENCE_ROOT = Path(r"F:\AI\temp\arch151-offline-development")
_OFFLINE_NAMESPACE_SCHEMA = "arch151-offline-attempt-namespace/v1"
_OFFLINE_PREFLIGHT_SCHEMA = "arch151-offline-preflight/v1"
_OFFLINE_CLAIM_SCHEMA = "arch151-offline-attempt-claim/v1"
_OFFLINE_SMOKE_SCHEMA = "arch151-offline-smoke-evidence/v1"
_OFFLINE_CAMPAIGN_SCHEMA = "arch151-offline-campaign-evidence/v1"
_OFFLINE_PARTIAL_SMOKE_SCHEMA = "arch151-offline-partial-smoke/v1"
_OFFLINE_PARTIAL_YEAR_SCHEMA = "arch151-offline-partial-year/v1"
_OFFLINE_FAILURE_SCHEMA = "arch151-offline-failure/v1"
_OFFLINE_TERMINAL_SCHEMA = "arch151-offline-terminal/v1"
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
_E2_CONSUMED_ARTIFACTS = (
    (
        "attempt.json",
        541,
        "8936e301d899fe2c07178c22ee3e8c21f90ba9dd3bfd90c60cdebe3ca33f0834",
    ),
    (
        "source-revision.json",
        573,
        "f97351bc52637342bfed0e3eb707b7dc3954a77e1bb9468ca0138404509da40e",
    ),
    (
        "predecessor-binding.json",
        1156,
        "78fda36898519a1aca5f0866ba7d68fd55e1d0aa4625e0294df94d36d94e49e7",
    ),
    (
        "operator-failure.json",
        519,
        "07d7d4c266aafcb43a2b8df697ece446928f7f2738626a765ffdfc26075a316e",
    ),
    (
        "attempt-result.json",
        1155,
        "472d7d9d5c7c2dad3c07998b451b808e32d8c0f8ffa89d8074032a422897d252",
    ),
)
_E2_CONSUMED_ATTEMPT_ID = UUID("8721f462-ebeb-4f77-b5b7-4455e30cb599")
_E2_CONSUMED_INVOCATION_ID = UUID("89f2b597-3032-5502-bfd4-33608c3f234b")
_E2_SOURCE_HEAD = "fd9af8abb7a1244a8cea63c8d896765c958426b5"
_E2_SOURCE_TREE = "033b25c5bb10c7e43d655057aafc81dcd00fbb70"
_E2_SOURCE_DIGEST = "69537a0b180bf995f1e645bda5e7b25fc32f66d2f5c6104a407d57e764a7b40b"
_E2_PREDECESSOR_BINDING_ID = "5ce662be-6d80-5b6c-a626-769714cd3ca3"
_E2_PREDECESSOR_BINDING_SHA256 = (
    "78fda36898519a1aca5f0866ba7d68fd55e1d0aa4625e0294df94d36d94e49e7"
)
_OFFLINE_MANIFEST_ID = "4fdce706-4322-59e1-95d1-590a39e67978"
_OFFLINE_MANIFEST_FINGERPRINT = (
    "8a5c89c55388e8ec5d0c6384a8f69ab99587a538bd0d868cb29a108717084083"
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
    OFFLINE_PREFLIGHT = "OFFLINE_PREFLIGHT"
    OFFLINE_SOURCE_LOAD = "OFFLINE_SOURCE_LOAD"
    OFFLINE_SMOKE_SIMULATION = "OFFLINE_SMOKE_SIMULATION"
    OFFLINE_ANNUAL_SIMULATION = "OFFLINE_ANNUAL_SIMULATION"
    OFFLINE_DEVELOPMENT_COMPOSITION = "OFFLINE_DEVELOPMENT_COMPOSITION"
    OFFLINE_REPORT_SERIALIZATION = "OFFLINE_REPORT_SERIALIZATION"
    OFFLINE_SOURCE_ATTESTATION = "OFFLINE_SOURCE_ATTESTATION"
    OFFLINE_EVIDENCE_PERSISTENCE = "OFFLINE_EVIDENCE_PERSISTENCE"
    OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION = "OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION"
    OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION = "OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION"
    OFFLINE_PROGRESS_REPORTING = "OFFLINE_PROGRESS_REPORTING"


class ClosedFailureReason(StrEnum):
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"
    ARITHMETIC_FAILURE = "ARITHMETIC_FAILURE"
    REPOSITORY_VALIDATION_FAILURE = "REPOSITORY_VALIDATION_FAILURE"
    IO_FAILURE = "IO_FAILURE"
    OPERATOR_GATE_FAILURE = "OPERATOR_GATE_FAILURE"
    UNEXPECTED_EXCEPTION = "UNEXPECTED_EXCEPTION"


class OfflineMode(StrEnum):
    PREFLIGHT = "PREFLIGHT"
    SMOKE = "SMOKE"
    CAMPAIGN = "CAMPAIGN"


class OfflineStatus(StrEnum):
    READY = "READY"
    NOT_RUN = "NOT_RUN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"
    INTERRUPTED = "INTERRUPTED"
    CONSUMED_UNPERSISTED = "CONSUMED_UNPERSISTED"
    CONSUMED_UNCONFIRMED = "CONSUMED_UNCONFIRMED"


class OfflineFailureCode(StrEnum):
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    SOURCE_HEAD_INVALID = "SOURCE_HEAD_INVALID"
    SOURCE_IDENTITY_UNAVAILABLE = "SOURCE_IDENTITY_UNAVAILABLE"
    SOURCE_BRANCH_INVALID = "SOURCE_BRANCH_INVALID"
    SOURCE_ORIGIN_INVALID = "SOURCE_ORIGIN_INVALID"
    SOURCE_DIRTY = "SOURCE_DIRTY"
    SOURCE_TRACKING_MISMATCH = "SOURCE_TRACKING_MISMATCH"
    SOURCE_LIVE_REF_MISMATCH = "SOURCE_LIVE_REF_MISMATCH"
    DEVELOP_TRACKING_MISMATCH = "DEVELOP_TRACKING_MISMATCH"
    PREDECESSOR_OBSERVATION_INVALID = "PREDECESSOR_OBSERVATION_INVALID"
    CUSTODY_METADATA_INVALID = "CUSTODY_METADATA_INVALID"
    MANIFEST_LEDGER_INVALID = "MANIFEST_LEDGER_INVALID"
    ATTEMPT_ID_INVALID = "ATTEMPT_ID_INVALID"
    ATTEMPT_ALREADY_CONSUMED = "ATTEMPT_ALREADY_CONSUMED"
    EVIDENCE_ROOT_INVALID = "EVIDENCE_ROOT_INVALID"
    EVIDENCE_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"
    SOURCE_LOAD_FAILED = "SOURCE_LOAD_FAILED"
    SOURCE_HISTORY_INVALID = "SOURCE_HISTORY_INVALID"
    SMOKE_SIMULATION_FAILED = "SMOKE_SIMULATION_FAILED"
    SMOKE_EVIDENCE_CONSTRUCTION_FAILED = "SMOKE_EVIDENCE_CONSTRUCTION_FAILED"
    PROGRESS_REPORTING_FAILED = "PROGRESS_REPORTING_FAILED"
    SMOKE_INCOMPLETE = "SMOKE_INCOMPLETE"
    ANNUAL_SIMULATION_FAILED = "ANNUAL_SIMULATION_FAILED"
    YEAR_INCOMPLETE = "YEAR_INCOMPLETE"
    DEVELOPMENT_COMPOSITION_FAILED = "DEVELOPMENT_COMPOSITION_FAILED"
    REPORT_SERIALIZATION_FAILED = "REPORT_SERIALIZATION_FAILED"
    SOURCE_ATTESTATION_FAILED = "SOURCE_ATTESTATION_FAILED"
    INTERRUPTED = "INTERRUPTED"
    UNCLASSIFIED_FAILURE = "UNCLASSIFIED_FAILURE"


class OfflineError(RuntimeError):
    def __init__(self, code: OfflineFailureCode, *, attempt_reserved: bool = False):
        self.code = code
        self.attempt_reserved = attempt_reserved
        super().__init__(code.value)


class _OfflineCLIArgumentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _OfflineSourceSnapshot:
    revision: SourceRevision
    feature_tracking_head: str
    develop_tracking_head: str
    feature_live_head: str
    develop_live_head: str
    upstream: str
    fetch_url: str
    push_url: str


@dataclass(frozen=True, slots=True)
class _OfflineSmokeOutcome:
    evidence: dict[str, object] | None
    complete: bool
    error: Exception | None = None
    partial_evidence: dict[str, object] | None = None
    failed_coordinate: Mapping[str, object] | None = None
    failure_code: OfflineFailureCode | None = None
    failure_stage: OperatorFailureStage | None = None


class _OfflineLifecycleAbort(Exception):
    def __init__(
        self,
        error: Exception,
        code: OfflineFailureCode,
        stage: OperatorFailureStage,
        *,
        status: OfflineStatus = OfflineStatus.FAILED,
        scored_year: int | None = None,
        failed_coordinate: Mapping[str, object] | None = None,
    ) -> None:
        self.error = error
        self.code = code
        self.stage = stage
        self.status = status
        self.scored_year = scored_year
        self.failed_coordinate = (
            dict(failed_coordinate) if failed_coordinate is not None else None
        )
        super().__init__("offline lifecycle failed")


@dataclass(slots=True)
class _OfflineAttemptState:
    attempt_root: Path
    attempt_id: UUID
    mode: OfflineMode
    preflight: dict[str, object]
    revision: SourceRevision
    invocation_id: UUID
    started_ns: int
    stage: OperatorFailureStage = OperatorFailureStage.OFFLINE_PREFLIGHT
    scored_year: int | None = None
    mode_root: Path | None = None
    source_material: dict[str, object] | None = None
    source_artifact: dict[str, object] | None = None
    source_digest: str | None = None
    validated_input_digest: str | None = None
    smoke_artifact: dict[str, object] | None = None
    campaign_artifact: dict[str, object] | None = None
    year_artifacts: list[dict[str, object]] = field(default_factory=list)
    attempted_years: list[int] = field(default_factory=list)
    completed_years: list[int] = field(default_factory=list)
    partial_artifacts: list[dict[str, object]] = field(default_factory=list)
    run: evaluator.DevelopmentEvaluationRun | None = None
    report: evaluator.DevelopmentEvaluationReport | None = None
    report_sha256: str | None = None
    report_artifact: dict[str, object] | None = None
    source_attestation: DevelopmentSourceAttestation | None = None
    source_attestation_artifact: dict[str, object] | None = None
    development_evidence_handoff: DevelopmentEvidenceHandoff | None = None
    failure_coordinate: dict[str, object] | None = None
    active_history: arch151.Arch150D1RSourceHistory | None = None
    active_smoke_progresses: list[evaluator._SessionReplayProgress] | None = None
    active_year_progresses: list[evaluator._SessionReplayProgress] | None = None


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
        "E4 has three fixed modes: --preflight-offline with --expected-source-head; "
        "--run-offline-smoke with --expected-source-head and --attempt-id; or "
        "--run-offline-campaign with --expected-source-head and --attempt-id. "
        "Preflight is read-only. Execution creates a one-shot attempt and reads "
        "accepted development history. Review the exact source and bounds before "
        "execution. E1 and E2 public execution routes remain permanently retired."
    )


def _is_git_object_id(value: object) -> bool:
    return (
        type(value) is str
        and len(value) in (40, 64)
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_canonical_attempt_id(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        return False
    return parsed.int != 0 and str(parsed) == value


def _offline_path_present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID) from None


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
            "failure": _replay_failure_material(item.failure)
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
    if isinstance(classified, (OperatorError, OfflineError)):
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


def _offline_git_text(*arguments: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
        }
    )
    try:
        result = subprocess.run(
            ("git", "-C", str(repo_root), *arguments),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None
    if result.returncode != 0:
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    return result.stdout.strip()


def _offline_live_refs() -> tuple[str, str]:
    repo_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
        }
    )
    feature_ref = f"refs/heads/{EXPECTED_BRANCH}"
    develop_ref = "refs/heads/develop"
    try:
        result = subprocess.run(
            (
                "git",
                "-c",
                "credential.helper=",
                "-C",
                str(repo_root),
                "ls-remote",
                "--heads",
                "origin",
                feature_ref,
                develop_ref,
            ),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH) from None
    if result.returncode != 0:
        raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH)
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or parts[1] not in (feature_ref, develop_ref):
            raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH)
        if parts[1] in refs or not _is_git_object_id(parts[0]):
            raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH)
        refs[parts[1]] = parts[0]
    if set(refs) != {feature_ref, develop_ref}:
        raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH)
    return refs[feature_ref], refs[develop_ref]


def _read_offline_source_snapshot(expected_source_head: str) -> _OfflineSourceSnapshot:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        if repo_root != EXPECTED_WORKTREE.resolve(strict=True):
            raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    except OSError:
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None
    top_level = _offline_git_text("rev-parse", "--show-toplevel")
    try:
        if Path(top_level).resolve(strict=True) != EXPECTED_WORKTREE.resolve(
            strict=True
        ):
            raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    except OSError:
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None
    branch = _offline_git_text("branch", "--show-current")
    fetch_url = _offline_git_text("remote", "get-url", "origin")
    push_url = _offline_git_text("remote", "get-url", "--push", "origin")
    head = _offline_git_text("rev-parse", "--verify", "HEAD")
    tree = _offline_git_text("rev-parse", "--verify", "HEAD^{tree}")
    status = _offline_git_text("status", "--porcelain=v1", "--untracked-files=all")
    upstream = _offline_git_text(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    feature_tracking = _offline_git_text(
        "rev-parse",
        "--verify",
        f"refs/remotes/origin/{EXPECTED_BRANCH}^{{commit}}",
    )
    develop_tracking = _offline_git_text(
        "rev-parse", "--verify", "refs/remotes/origin/develop^{commit}"
    )
    if branch != EXPECTED_BRANCH:
        raise OfflineError(OfflineFailureCode.SOURCE_BRANCH_INVALID)
    if fetch_url != EXPECTED_ORIGIN or push_url != EXPECTED_ORIGIN:
        raise OfflineError(OfflineFailureCode.SOURCE_ORIGIN_INVALID)
    if status:
        raise OfflineError(OfflineFailureCode.SOURCE_DIRTY)
    if not _is_git_object_id(head) or not _is_git_object_id(tree):
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    if not _is_git_object_id(feature_tracking) or not _is_git_object_id(
        develop_tracking
    ):
        raise OfflineError(OfflineFailureCode.SOURCE_TRACKING_MISMATCH)
    if head != expected_source_head:
        raise OfflineError(OfflineFailureCode.SOURCE_HEAD_INVALID)
    if upstream != f"origin/{EXPECTED_BRANCH}" or feature_tracking != head:
        raise OfflineError(OfflineFailureCode.SOURCE_TRACKING_MISMATCH)
    feature_live, develop_live = _offline_live_refs()
    if feature_live != feature_tracking or develop_live != develop_tracking:
        raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH)
    try:
        revision = SourceRevision(
            branch, fetch_url, head, tree, _seal=_SOURCE_REVISION_SEAL
        )
    except (OperatorError, ValueError):
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE) from None
    return _OfflineSourceSnapshot(
        revision,
        feature_tracking,
        develop_tracking,
        feature_live,
        develop_live,
        upstream,
        fetch_url,
        push_url,
    )


def _offline_e1_observation_binding() -> tuple[dict[str, object], dict[str, object]]:
    try:
        binding = _read_consumed_predecessor_binding()
    except OperatorError:
        raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID) from None
    observed = {
        "schema": "arch151-consumed-observation-binding/v1",
        "observation_id": str(_PREDECESSOR_ATTEMPT_ID),
        "root_name": EVIDENCE_ROOT.name,
        "binding_id": binding["binding_id"],
        "source_head": _PREDECESSOR_HEAD,
        "source_tree": _PREDECESSOR_TREE,
        "artifact_commitments": [
            {"name": name, "byte_length": length, "sha256": digest}
            for name, length, digest in _PREDECESSOR_ARTIFACTS
        ],
        "binding_sha256": hashlib.sha256(_canonical_bytes(binding)).hexdigest(),
    }
    return binding, observed


def _offline_parse_canonical_object(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
        if type(value) is not dict or arch151._canonical_json(value) != raw:
            raise ValueError
        return value
    except Exception:
        raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID) from None


def _offline_validate_e2_observation(
    contents: Mapping[str, bytes], e1_binding: Mapping[str, object]
) -> None:
    records = {
        name: _offline_parse_canonical_object(raw) for name, raw in contents.items()
    }
    e1_binding_bytes = _canonical_bytes(e1_binding)
    e1_binding_sha = hashlib.sha256(e1_binding_bytes).hexdigest()
    predecessor = records["predecessor-binding.json"]
    claim = records["attempt.json"]
    revision = records["source-revision.json"]
    failure = records["operator-failure.json"]
    result = records["attempt-result.json"]
    expected_windows = {
        "development_start": "2016-01-01",
        "development_end": "2023-12-31",
    }
    if (
        predecessor != e1_binding
        or predecessor.get("binding_id") != e1_binding.get("binding_id")
        or hashlib.sha256(_canonical_bytes(predecessor)).hexdigest()
        != _E2_PREDECESSOR_BINDING_SHA256
        or claim.get("schema") != _SUCCESSOR_ATTEMPT_SCHEMA
        or claim.get("attempt_id") != str(_E2_CONSUMED_ATTEMPT_ID)
        or claim.get("status") != "STARTED"
        or claim.get("invocation_id") is not None
        or claim.get("automatic_retry") != "FORBIDDEN"
        or claim.get("predecessor_binding_id") != e1_binding.get("binding_id")
        or claim.get("predecessor_binding_sha256") != e1_binding_sha
        or claim.get("manifest_id") != _OFFLINE_MANIFEST_ID
        or claim.get("manifest_fingerprint") != _OFFLINE_MANIFEST_FINGERPRINT
        or any(claim.get(key) != value for key, value in expected_windows.items())
        or revision.get("schema") != _SUCCESSOR_SOURCE_REVISION_SCHEMA
        or revision.get("attempt_id") != str(_E2_CONSUMED_ATTEMPT_ID)
        or revision.get("invocation_id") != str(_E2_CONSUMED_INVOCATION_ID)
        or revision.get("predecessor_binding_id") != e1_binding.get("binding_id")
        or revision.get("predecessor_binding_sha256") != e1_binding_sha
        or revision.get("source_branch") != EXPECTED_BRANCH
        or revision.get("source_origin") != EXPECTED_ORIGIN
        or revision.get("source_head") != _E2_SOURCE_HEAD
        or revision.get("source_tree") != _E2_SOURCE_TREE
        or failure.get("schema") != _OPERATOR_FAILURE_SCHEMA_V2
        or failure.get("attempt_id") != str(_E2_CONSUMED_ATTEMPT_ID)
        or failure.get("invocation_id") != str(_E2_CONSUMED_INVOCATION_ID)
        or failure.get("failure_type") != "ValueError"
        or failure.get("predecessor_binding_id") != e1_binding.get("binding_id")
        or failure.get("predecessor_binding_sha256") != e1_binding_sha
        or failure.get("source_head") != _E2_SOURCE_HEAD
        or failure.get("source_tree") != _E2_SOURCE_TREE
        or failure.get("year_artifacts") != []
        or result.get("schema") != _SUCCESSOR_RESULT_SCHEMA
        or result.get("status") != OperatorStatus.FAILED.value
        or result.get("attempt_id") != str(_E2_CONSUMED_ATTEMPT_ID)
        or result.get("invocation_id") != str(_E2_CONSUMED_INVOCATION_ID)
        or result.get("predecessor_binding_id") != e1_binding.get("binding_id")
        or result.get("predecessor_binding_sha256") != e1_binding_sha
        or result.get("manifest_id") != _OFFLINE_MANIFEST_ID
        or result.get("manifest_fingerprint") != _OFFLINE_MANIFEST_FINGERPRINT
        or result.get("attempted_years") != []
        or result.get("year_artifacts") != []
        or result.get("failure_evidence_sha256") != _E2_CONSUMED_ARTIFACTS[3][2]
        or result.get("candidate_evaluation") != "NOT_EVALUATED"
        or result.get("report_id") is not None
        or result.get("report_sha256") is not None
        or result.get("source_binding_id") is not None
        or result.get("automatic_retry") != "FORBIDDEN"
        or result.get("source_branch") != EXPECTED_BRANCH
        or result.get("source_origin") != EXPECTED_ORIGIN
        or result.get("source_head") != _E2_SOURCE_HEAD
        or result.get("source_tree") != _E2_SOURCE_TREE
        or result.get("source_digest") != _E2_SOURCE_DIGEST
        or result.get("failure_code") != OperatorFailureCode.UNCLASSIFIED_FAILURE.value
        or failure.get("failure_code") != OperatorFailureCode.UNCLASSIFIED_FAILURE.value
    ):
        raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID)


def _offline_observation_binding(
    root: Path,
    artifacts: tuple[tuple[str, int, str], ...],
    observation_id: str,
    *,
    e1_binding: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        if (
            not root.is_dir()
            or root.is_symlink()
            or root.resolve(strict=True) != root
            or _is_reparse_point(root)
        ):
            raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID)
        actual_names = tuple(sorted(item.name for item in root.iterdir()))
        if actual_names != tuple(sorted(item[0] for item in artifacts)):
            raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID)
        contents: dict[str, bytes] = {}
        for name, expected_length, expected_digest in artifacts:
            path = root / name
            if not path.is_file() or _is_reparse_point(path):
                raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID)
            raw = path.read_bytes()
            if (
                len(raw) != expected_length
                or hashlib.sha256(raw).hexdigest() != expected_digest
            ):
                raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID)
            contents[name] = raw
        if observation_id == str(_E2_CONSUMED_ATTEMPT_ID):
            if e1_binding is None:
                raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID)
            _offline_validate_e2_observation(contents, e1_binding)
    except OfflineError:
        raise
    except Exception:
        raise OfflineError(OfflineFailureCode.PREDECESSOR_OBSERVATION_INVALID) from None
    material = {
        "schema": "arch151-consumed-observation-binding/v1",
        "observation_id": observation_id,
        "root_name": root.name,
        "predecessor_binding_id": (
            e1_binding.get("binding_id") if e1_binding is not None else None
        ),
        "predecessor_binding_sha256": (
            hashlib.sha256(_canonical_bytes(e1_binding)).hexdigest()
            if e1_binding is not None
            else None
        ),
        "artifacts": [
            {"name": name, "byte_length": length, "sha256": digest}
            for name, length, digest in artifacts
        ],
    }
    return {
        **material,
        "binding_sha256": hashlib.sha256(_canonical_bytes(material)).hexdigest(),
    }


def _offline_custody_inventory() -> dict[str, object]:
    root = arch150_d1r.ACCEPTED_INPUT_ROOT
    expected_names = set(arch150_d1r._ARTIFACT_LENGTHS)
    try:
        arch150_d1r._require_real_directory(root, "INPUT_DIRECTORY_INVALID")
        if not arch151._d1r_semantic_pins_match():
            raise OfflineError(OfflineFailureCode.CUSTODY_METADATA_INVALID)
        root_entries = {item.name: item for item in root.iterdir()}
        expected_root_entries = {
            "normalized",
            "dataset.json",
            "custody-evidence.json",
            "evidence.json",
        }
        if set(root_entries) != expected_root_entries:
            raise OfflineError(OfflineFailureCode.CUSTODY_METADATA_INVALID)
        normalized = root_entries["normalized"]
        if (
            not normalized.is_dir()
            or arch150_d1r._is_reparse_point(normalized)
            or {item.name for item in normalized.iterdir()} != {"SPY.csv", "QQQ.csv"}
        ):
            raise OfflineError(OfflineFailureCode.CUSTODY_METADATA_INVALID)
        observed: list[dict[str, object]] = []
        for name, length in sorted(arch150_d1r._ARTIFACT_LENGTHS.items()):
            if name not in expected_names:
                raise OfflineError(OfflineFailureCode.CUSTODY_METADATA_INVALID)
            path = root.joinpath(*name.split("/"))
            if (
                arch150_d1r._is_reparse_point(path)
                or not path.is_file()
                or path.stat().st_size != length
            ):
                raise OfflineError(OfflineFailureCode.CUSTODY_METADATA_INVALID)
            observed.append({"name": name, "byte_length": length})
    except OfflineError:
        raise
    except Exception:
        raise OfflineError(OfflineFailureCode.CUSTODY_METADATA_INVALID) from None
    return {
        "directory": str(root),
        "inventory": observed,
        "content_authenticated": False,
        "dataset_id": str(arch151.ARCH150_D1R_DATASET_ID),
        "dataset_semantic_sha256": arch151.ARCH150_D1R_DATASET_SHA256,
        "custody_id": str(arch151.ARCH150_D1R_CUSTODY_ID),
        "custody_semantic_sha256": arch151.ARCH150_D1R_CUSTODY_SHA256,
        "evidence_id": str(arch151.ARCH150_D1R_EVIDENCE_ID),
        "evidence_sha256": arch151.ARCH150_D1R_EVIDENCE_SHA256,
    }


def _offline_smoke_sessions() -> tuple[date, ...]:
    published = tuple(
        session
        for session in arch151._SESSION_AUTHORITY.published.sessions
        if session.year == 2019
    )
    first_ten = published[:10]
    early_closes = []
    for session in published:
        schedule = arch151._SESSION_AUTHORITY.schedule_for(session)
        if schedule is not None and schedule.closes_at - schedule.opens_at < timedelta(
            hours=6
        ):
            early_closes.append(session)
    if len(first_ten) != 10 or not early_closes:
        raise OfflineError(OfflineFailureCode.MANIFEST_LEDGER_INVALID)
    return tuple(sorted(set(first_ten + (early_closes[0],))))


def _offline_run_shape() -> dict[str, object]:
    manifest = arch151.CANONICAL_MANIFEST
    ledger = arch151.PRIOR_INTRADAY_TRIAL_LEDGER
    if (
        type(manifest) is not arch151.CanonicalManifest
        or len(arch151.CANONICAL_PROGRAMS) != 16
        or len(arch151.CANONICAL_SLOTS) != 32
        or str(manifest.manifest_id) != _OFFLINE_MANIFEST_ID
        or manifest.fingerprint != _OFFLINE_MANIFEST_FINGERPRINT
        or type(ledger) is not arch151.PriorTrialLedger
        or sum(item.distinct_trial_count for item in ledger.entries) != 29
        or ledger.documented_prior_intraday_trials != 29
        or arch151.SELECTION_BIAS_INPUT.ledger_id != ledger.ledger_id
        or arch151.SELECTION_BIAS_INPUT.effective_trial_count != 64
        or not arch151._d1r_semantic_pins_match()
    ):
        raise OfflineError(OfflineFailureCode.MANIFEST_LEDGER_INVALID)
    smoke_sessions = _offline_smoke_sessions()
    if len(smoke_sessions) != 11:
        raise OfflineError(OfflineFailureCode.MANIFEST_LEDGER_INVALID)
    expected_smoke_records = (
        len(smoke_sessions)
        * len(arch151.CANONICAL_SLOTS)
        * len(arch151.EVALUATION_ECONOMICS_ORDER)
    )
    return {
        "manifest_id": str(manifest.manifest_id),
        "manifest_fingerprint": manifest.fingerprint,
        "program_count": len(arch151.CANONICAL_PROGRAMS),
        "slot_count": len(arch151.CANONICAL_SLOTS),
        "cost_cases": [item.value for item in arch151.EVALUATION_ECONOMICS_ORDER],
        "scored_years": list(arch151.SCORED_YEARS),
        "expected_year_batches": len(arch151.SCORED_YEARS),
        "expected_replays_per_year": len(arch151.CANONICAL_SLOTS)
        * len(arch151.EVALUATION_ECONOMICS_ORDER),
        "expected_campaign_replays": len(arch151.SCORED_YEARS)
        * len(arch151.CANONICAL_SLOTS)
        * len(arch151.EVALUATION_ECONOMICS_ORDER),
        "ledger_id": str(ledger.ledger_id),
        "ledger_fingerprint": ledger.fingerprint,
        "prior_trial_count": ledger.documented_prior_intraday_trials,
        "smoke_sessions": [item.isoformat() for item in smoke_sessions],
        "expected_smoke_records": expected_smoke_records,
        "smoke_evaluation": "NOT_EVALUATED",
    }


def _offline_namespace_metadata(*, create: bool) -> dict[str, object]:
    root = OFFLINE_EVIDENCE_ROOT
    repo_root = Path(__file__).resolve().parents[3]
    try:
        if (
            not root.is_absolute()
            or _is_within(root.resolve(strict=False), repo_root)
            or _is_within(
                root.resolve(strict=False), _WORKTREES_ROOT.resolve(strict=False)
            )
        ):
            raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
        for ancestor in (root, *root.parents):
            if _offline_path_present(ancestor) and _is_reparse_point(ancestor):
                raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
        if _offline_path_present(root):
            if not root.is_dir() or root.resolve(strict=True) != root:
                raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
            names = {item.name for item in root.iterdir()}
            if names - {"attempts"}:
                raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
        elif not create:
            if (
                not root.parent.is_dir()
                or root.parent.resolve(strict=True) != root.parent
            ):
                raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
            names = set()
        else:
            try:
                root.mkdir()
            except FileExistsError:
                pass
            names = set()
        attempts = root / "attempts"
        if _offline_path_present(attempts):
            if (
                not attempts.is_dir()
                or _is_reparse_point(attempts)
                or attempts.resolve(strict=True) != attempts
            ):
                raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
            names = {item.name for item in attempts.iterdir()}
            for item in attempts.iterdir():
                if (
                    not item.is_dir()
                    or _is_reparse_point(item)
                    or item.resolve(strict=True) != item
                    or not _is_canonical_attempt_id(item.name)
                ):
                    raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
        elif create:
            try:
                attempts.mkdir()
            except FileExistsError:
                pass
            names = set()
        root_ready = (
            _offline_path_present(root)
            and root.is_dir()
            and root.resolve(strict=True) == root
            and not _is_reparse_point(root)
        )
        attempts_ready = (
            _offline_path_present(attempts)
            and attempts.is_dir()
            and attempts.resolve(strict=True) == attempts
            and not _is_reparse_point(attempts)
        )
        if (
            (create and not (root_ready and attempts_ready))
            or (_offline_path_present(root) and not root_ready)
            or (_offline_path_present(attempts) and not attempts_ready)
        ):
            raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
    except OfflineError:
        raise
    except Exception:
        raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID) from None
    return {
        "schema": _OFFLINE_NAMESPACE_SCHEMA,
        "root": str(root),
        "attempts_directory": str(root / "attempts"),
        "reserved_attempt_count": len(names),
        "reservation": "ATOMIC_CREATE_ONLY",
    }


def _offline_preflight_material(expected_source_head: str) -> dict[str, object]:
    if not _is_git_object_id(expected_source_head):
        raise OfflineError(OfflineFailureCode.SOURCE_HEAD_INVALID)
    snapshot = _read_offline_source_snapshot(expected_source_head)
    if snapshot.revision.head != expected_source_head:
        raise OfflineError(OfflineFailureCode.SOURCE_HEAD_INVALID)
    if snapshot.feature_tracking_head != expected_source_head:
        raise OfflineError(OfflineFailureCode.SOURCE_TRACKING_MISMATCH)
    if snapshot.feature_live_head != expected_source_head:
        raise OfflineError(OfflineFailureCode.SOURCE_LIVE_REF_MISMATCH)
    e1_binding, e1 = _offline_e1_observation_binding()
    e2 = _offline_observation_binding(
        SUCCESSOR_EVIDENCE_ROOT,
        _E2_CONSUMED_ARTIFACTS,
        str(_E2_CONSUMED_ATTEMPT_ID),
        e1_binding=e1_binding,
    )
    custody = _offline_custody_inventory()
    shape = _offline_run_shape()
    namespace = _offline_namespace_metadata(create=False)
    return {
        "schema": _OFFLINE_PREFLIGHT_SCHEMA,
        "status": OfflineStatus.READY.value,
        "expected_source_head": expected_source_head,
        "source": {
            "branch": snapshot.revision.branch,
            "origin_fetch_url": snapshot.fetch_url,
            "origin_push_url": snapshot.push_url,
            "head": snapshot.revision.head,
            "tree": snapshot.revision.tree,
            "upstream": snapshot.upstream,
            "feature_tracking_head": snapshot.feature_tracking_head,
            "develop_tracking_head": snapshot.develop_tracking_head,
            "feature_live_head": snapshot.feature_live_head,
            "develop_live_head": snapshot.develop_live_head,
        },
        "consumed_observations": [e1, e2],
        "custody_metadata": custody,
        "run_shape": shape,
        "attempt_namespace": namespace,
        "attempt_reuse": "FORBIDDEN",
        "resume": "FORBIDDEN",
        "custody_content_authenticated": False,
    }


def preflight_offline(expected_source_head: str) -> dict[str, object]:
    """Read-only E4 preflight; it never creates an attempt or reads custody content."""

    material = _offline_preflight_material(expected_source_head)
    digest = hashlib.sha256(_canonical_bytes(material)).hexdigest()
    return {**material, "preflight_sha256": digest}


def _offline_write_once(path: Path, body: bytes, root: Path) -> str:
    try:
        return _write_once(path, body, attempt_root=root)
    except OperatorError:
        raise OfflineError(OfflineFailureCode.EVIDENCE_WRITE_FAILED) from None


def _offline_reserve_attempt(attempt_id: UUID) -> Path:
    if type(attempt_id) is not UUID or attempt_id.int == 0:
        raise OfflineError(OfflineFailureCode.ATTEMPT_ID_INVALID)
    _offline_namespace_metadata(create=True)
    attempt_root = OFFLINE_EVIDENCE_ROOT / "attempts" / str(attempt_id)
    try:
        attempt_root.mkdir()
    except FileExistsError:
        raise OfflineError(OfflineFailureCode.ATTEMPT_ALREADY_CONSUMED) from None
    except OSError:
        raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID) from None
    try:
        if attempt_root.resolve(strict=True) != attempt_root or _is_reparse_point(
            attempt_root
        ):
            raise OfflineError(
                OfflineFailureCode.EVIDENCE_ROOT_INVALID, attempt_reserved=True
            )
    except (OSError, OperatorError):
        raise OfflineError(
            OfflineFailureCode.EVIDENCE_ROOT_INVALID, attempt_reserved=True
        ) from None
    return attempt_root


def _offline_create_mode_root(attempt_root: Path, mode: OfflineMode) -> Path:
    if mode is OfflineMode.PREFLIGHT:
        raise OfflineError(OfflineFailureCode.INVALID_ARGUMENTS)
    mode_root = attempt_root / ("smoke" if mode is OfflineMode.SMOKE else "campaign")
    try:
        mode_root.mkdir()
        if mode_root.resolve(strict=True) != mode_root or _is_reparse_point(mode_root):
            raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
    except FileExistsError:
        raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID) from None
    except OSError:
        raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID) from None
    return mode_root


def _offline_progress(
    sink: Callable[[str], None] | None,
    *,
    mode: OfflineMode,
    stage: str,
    started_ns: int,
    records: int = 0,
    slot: arch151.TrialSlot | None = None,
    scored_year: int | None = None,
    attempt_id: UUID | None = None,
    expected_records: int | None = None,
) -> None:
    if sink is None:
        return
    fields = [
        f"mode={mode.value}",
        f"stage={stage}",
        f"records={records}",
        f"elapsed_ns={time.monotonic_ns() - started_ns}",
    ]
    if attempt_id is not None:
        fields.append(f"attempt_id={attempt_id}")
    if expected_records is not None:
        fields.append(f"expected_records={expected_records}")
    if scored_year is not None:
        fields.append(f"scored_year={scored_year}")
    if slot is not None:
        fields.extend(
            (
                f"program_id={slot.program_id}",
                f"slot_id={slot.slot_id}",
                f"symbol={slot.symbol}",
            )
        )
    try:
        sink("PROGRESS=" + ";".join(fields))
    except Exception:
        raise OfflineError(OfflineFailureCode.PROGRESS_REPORTING_FAILED) from None


def _offline_session_record_material(
    progress: evaluator._SessionReplayProgress,
) -> dict[str, object]:
    record = progress.record
    cash_reconciled = False
    if record.closing_equity is not None and record.failure is None:
        evaluator._validate_session_trade_cash(record)
        cash_reconciled = True
    if (
        record.failure is not None
        and record.failure.kind is evaluator.ReplayFailureKind.CALIBRATION_UNAVAILABLE
    ):
        liquidation_status = "NOT_EVALUATED"
    elif (
        record.failure is not None
        and record.failure.kind
        is evaluator.ReplayFailureKind.MANDATORY_LIQUIDATION_UNOBSERVED
    ):
        liquidation_status = "UNOBSERVED"
    elif any(
        trade.exit_reason is evaluator.ExitReason.SESSION_LIQUIDATION
        for trade in record.trades
    ):
        liquidation_status = "OBSERVED"
    elif record.closing_equity is not None:
        liquidation_status = "SATISFIED"
    else:
        liquidation_status = "NOT_EVALUATED"
    return {
        "scored_year": progress.scored_year,
        "program_id": str(progress.slot.program_id),
        "slot_id": str(progress.slot.slot_id),
        "symbol": progress.slot.symbol,
        "cost_case": progress.cost_case.value,
        "session_date": record.session_date.isoformat(),
        "session_id": str(record.session_id),
        "starting_equity": arch151._decimal_text(record.starting_equity),
        "closing_equity": (
            arch151._decimal_text(record.closing_equity)
            if record.closing_equity is not None
            else None
        ),
        "session_return": (
            arch151._decimal_text(record.session_return)
            if record.session_return is not None
            else None
        ),
        "signal_counts": {
            "generated": record.generated_signal_count,
            "eligible": record.eligible_signal_count,
            "executed": record.executed_signal_count,
            "expired": record.expired_signal_count,
            "blocked": record.blocked_signal_count,
        },
        "fill_count": len(record.fills),
        "trade_count": len(record.trades),
        "cash_reconciled": cash_reconciled,
        "mandatory_liquidation_status": liquidation_status,
        "failure": _replay_failure_material(record.failure)
        if record.failure is not None
        else None,
        "record": evaluator._canonical_output_material(record),
    }


def _offline_progress_coordinate(
    progress: evaluator._SessionReplayProgress,
) -> dict[str, object]:
    return {
        "scored_year": progress.scored_year,
        "program_id": str(progress.slot.program_id),
        "slot_id": str(progress.slot.slot_id),
        "symbol": progress.slot.symbol,
        "cost_case": progress.cost_case.value,
        "session_date": progress.record.session_date.isoformat(),
        "session_id": str(progress.record.session_id),
    }


def _offline_failure_attribution(
    error: Exception,
    stage: OperatorFailureStage,
    *,
    scored_year: int | None = None,
) -> dict[str, object]:
    return _failure_attribution_material(error, stage, scored_year=scored_year)


def _parse_offline_attempt_id(value: object) -> UUID:
    if not _is_canonical_attempt_id(value):
        raise OfflineError(OfflineFailureCode.ATTEMPT_ID_INVALID)
    return UUID(value)


def _offline_source_material(
    history: arch151.Arch150D1RSourceHistory,
    revision: SourceRevision,
    attempt_id: UUID,
    invocation_id: UUID,
    preflight_sha256: str,
) -> dict[str, object]:
    if (
        type(history) is not arch151.Arch150D1RSourceHistory
        or history.dataset_id != arch151.ARCH150_D1R_DATASET_ID
        or history.dataset_sha256 != arch151.ARCH150_D1R_DATASET_SHA256
        or history.custody_id != arch151.ARCH150_D1R_CUSTODY_ID
        or history.custody_sha256 != arch151.ARCH150_D1R_CUSTODY_SHA256
        or history.evidence_id != arch151.ARCH150_D1R_EVIDENCE_ID
        or history.evidence_sha256 != arch151.ARCH150_D1R_EVIDENCE_SHA256
        or not arch151._is_sha256(history.source_digest)
        or not arch151._is_sha256(history.validated_input_digest)
    ):
        raise OfflineError(OfflineFailureCode.SOURCE_HISTORY_INVALID)
    commitments = history.artifact_commitments
    expected_inventory = {
        name: length for name, length in arch150_d1r._ARTIFACT_LENGTHS.items()
    }
    if (
        len(commitments) != len(expected_inventory)
        or {name: length for name, length, _digest in commitments} != expected_inventory
        or any(not arch151._is_sha256(digest) for _name, _length, digest in commitments)
    ):
        raise OfflineError(OfflineFailureCode.SOURCE_HISTORY_INVALID)
    source_binding = evaluator._development_source_binding(history)
    if source_binding.kind is not evaluator.DevelopmentSourceKind.ARCH150_D1R_ACCEPTED:
        raise OfflineError(OfflineFailureCode.SOURCE_HISTORY_INVALID)
    return {
        "schema": "arch151-offline-authenticated-source/v1",
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_revision_digest": _source_revision_digest(revision, invocation_id),
        "source_kind": source_binding.kind.value,
        "source_id": str(history.source_id),
        "source_digest": history.source_digest,
        "validated_input_digest": history.validated_input_digest,
        "source_binding_id": str(source_binding.binding_id),
        "dataset_id": str(history.dataset_id),
        "dataset_sha256": history.dataset_sha256,
        "custody_id": str(history.custody_id),
        "custody_sha256": history.custody_sha256,
        "evidence_id": str(history.evidence_id),
        "evidence_sha256": history.evidence_sha256,
        "artifact_commitments": [
            {"name": name, "byte_length": length, "sha256": digest}
            for name, length, digest in commitments
        ],
        "preflight_sha256": preflight_sha256,
        "content_authenticated": True,
    }


def _offline_persist_failure(
    *,
    attempt_root: Path,
    attempt_id: UUID,
    mode: OfflineMode,
    preflight: Mapping[str, object],
    revision: SourceRevision | None,
    invocation_id: UUID | None,
    error: Exception,
    failure_code: OfflineFailureCode,
    stage: OperatorFailureStage,
    started_ns: int,
    source_digest: str | None = None,
    validated_input_digest: str | None = None,
    source_artifact: Mapping[str, object] | None = None,
    smoke_artifact: Mapping[str, object] | None = None,
    campaign_artifact: Mapping[str, object] | None = None,
    year_artifacts: tuple[Mapping[str, object], ...] = (),
    attempted_years: tuple[int, ...] = (),
    completed_years: tuple[int, ...] = (),
    partial_artifacts: tuple[Mapping[str, object], ...] = (),
    status: OfflineStatus = OfflineStatus.FAILED,
    scored_year: int | None = None,
    run: evaluator.DevelopmentEvaluationRun | None = None,
    report: evaluator.DevelopmentEvaluationReport | None = None,
    report_sha256: str | None = None,
    report_artifact: Mapping[str, object] | None = None,
    source_attestation: DevelopmentSourceAttestation | None = None,
    source_attestation_artifact: Mapping[str, object] | None = None,
    development_evidence_handoff: DevelopmentEvidenceHandoff | None = None,
    failed_coordinate: Mapping[str, object] | None = None,
) -> dict[str, object]:
    root_error = _root_failure(error)
    attribution = _offline_failure_attribution(error, stage, scored_year=scored_year)
    if failed_coordinate is not None:
        attribution["failed_coordinate"] = dict(failed_coordinate)
    evidence: dict[str, object] = {
        "schema": _OFFLINE_FAILURE_SCHEMA,
        "attempt_id": str(attempt_id),
        "mode": mode.value,
        "failure_code": failure_code.value,
        "failure_type": type(root_error).__name__,
        "failure_attribution": attribution,
        "attempted_years": list(attempted_years),
        "completed_years": list(completed_years),
        "year_artifacts": [dict(item) for item in year_artifacts],
        "partial_artifacts": [dict(item) for item in partial_artifacts],
        "automatic_retry": "FORBIDDEN",
        "resume": "FORBIDDEN",
    }
    source_load_reason = _source_load_reason(error)
    if source_load_reason is not None:
        evidence["source_load_reason"] = source_load_reason
    if revision is not None:
        evidence["source_head"] = revision.head
        evidence["source_tree"] = revision.tree
    failure_digest = _offline_write_once(
        attempt_root / "operator-failure.json",
        _canonical_bytes(evidence),
        attempt_root,
    )
    return _offline_terminal(
        attempt_root=attempt_root,
        attempt_id=attempt_id,
        mode=mode,
        status=status,
        preflight=preflight,
        invocation_id=invocation_id,
        revision=revision,
        failure_code=failure_code,
        failure_evidence_sha256=failure_digest,
        source_digest=source_digest,
        validated_input_digest=validated_input_digest,
        source_artifact=source_artifact,
        smoke_artifact=smoke_artifact,
        campaign_artifact=campaign_artifact,
        year_artifacts=year_artifacts,
        attempted_years=attempted_years,
        completed_years=completed_years,
        partial_artifacts=partial_artifacts,
        run=run,
        report=report,
        report_sha256=report_sha256,
        report_artifact=report_artifact,
        source_attestation=source_attestation,
        source_attestation_artifact=source_attestation_artifact,
        development_evidence_handoff=development_evidence_handoff,
        elapsed_ns=time.monotonic_ns() - started_ns,
    )


def _offline_terminal(
    *,
    attempt_root: Path,
    attempt_id: UUID,
    mode: OfflineMode,
    status: OfflineStatus,
    preflight: Mapping[str, object],
    invocation_id: UUID | None,
    revision: SourceRevision | None,
    failure_code: OfflineFailureCode | None,
    failure_evidence_sha256: str | None = None,
    source_digest: str | None = None,
    validated_input_digest: str | None = None,
    source_artifact: Mapping[str, object] | None = None,
    smoke_artifact: Mapping[str, object] | None = None,
    campaign_artifact: Mapping[str, object] | None = None,
    partial_artifacts: tuple[Mapping[str, object], ...] = (),
    year_artifacts: tuple[Mapping[str, object], ...] = (),
    attempted_years: tuple[int, ...] = (),
    completed_years: tuple[int, ...] = (),
    run: evaluator.DevelopmentEvaluationRun | None = None,
    report: evaluator.DevelopmentEvaluationReport | None = None,
    report_sha256: str | None = None,
    report_artifact: Mapping[str, object] | None = None,
    source_attestation: DevelopmentSourceAttestation | None = None,
    source_attestation_artifact: Mapping[str, object] | None = None,
    development_evidence_handoff: DevelopmentEvidenceHandoff | None = None,
    elapsed_ns: int,
) -> dict[str, object]:
    terminal: dict[str, object] = {
        "schema": _OFFLINE_TERMINAL_SCHEMA,
        "mode": mode.value,
        "status": status.value,
        "attempt_id": str(attempt_id),
        "attempt_root": str(attempt_root),
        "invocation_id": str(invocation_id) if invocation_id is not None else None,
        "expected_source_head": preflight["expected_source_head"],
        "preflight_sha256": preflight["preflight_sha256"],
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "source_digest": source_digest,
        "validated_input_digest": validated_input_digest,
        "source_artifact": dict(source_artifact)
        if source_artifact is not None
        else None,
        "smoke_artifact": dict(smoke_artifact) if smoke_artifact is not None else None,
        "campaign_artifact": (
            dict(campaign_artifact) if campaign_artifact is not None else None
        ),
        "partial_artifacts": [dict(item) for item in partial_artifacts],
        "attempted_years": list(attempted_years),
        "completed_years": list(completed_years),
        "year_artifacts": [dict(item) for item in year_artifacts],
        "candidate_evaluation": (
            "COMPLETED"
            if run is not None and mode is OfflineMode.CAMPAIGN
            else "NOT_EVALUATED"
        ),
        "final_freeze_status": (
            run.final_freeze.status.value if run is not None else "NOT_EVALUATED"
        ),
        "final_freeze_id": (
            str(run.final_freeze.freeze_id) if run is not None else None
        ),
        "report_id": str(report.report_id) if report is not None else None,
        "report_sha256": report_sha256,
        "report_artifact": dict(report_artifact)
        if report_artifact is not None
        else None,
        "failure_code": failure_code.value if failure_code is not None else None,
        "failure_evidence_sha256": failure_evidence_sha256,
        "source_attestation_id": (
            str(source_attestation.attestation_id)
            if source_attestation is not None
            else None
        ),
        "source_attestation_digest": (
            source_attestation.attestation_digest
            if source_attestation is not None
            else None
        ),
        "source_attestation_artifact": (
            dict(source_attestation_artifact)
            if source_attestation_artifact is not None
            else None
        ),
        "development_evidence_id": (
            str(development_evidence_handoff.authenticated_evidence.evidence_id)
            if development_evidence_handoff is not None
            else None
        ),
        "development_evidence_digest": (
            development_evidence_handoff.authenticated_evidence.evidence_digest
            if development_evidence_handoff is not None
            else None
        ),
        "candidate_slot_id": (
            str(development_evidence_handoff.authenticated_evidence.candidate_slot_id)
            if development_evidence_handoff is not None
            else None
        ),
        "selection_bias_evidence_id": (
            str(development_evidence_handoff.selection_bias_evidence.evidence_id)
            if development_evidence_handoff is not None
            else None
        ),
        "selection_bias_evidence_digest": (
            development_evidence_handoff.selection_bias_evidence.evidence_digest
            if development_evidence_handoff is not None
            else None
        ),
        "automatic_retry": "FORBIDDEN",
        "resume": "FORBIDDEN",
        "terminal_persisted": True,
        "elapsed_ns": elapsed_ns,
    }
    if revision is not None:
        terminal["source_revision"] = {
            "branch": revision.branch,
            "origin": revision.origin,
            "head": revision.head,
            "tree": revision.tree,
        }
    if run is not None:
        terminal["run"] = {
            "run_id": str(run.run_id),
            "source_binding_id": str(run.source_binding.binding_id),
            "year_batch_ids": [str(item.batch_id) for item in run.year_batches],
            "record_count": run.fold_evaluation_count,
            "final_freeze_status": run.final_freeze.status.value,
            "final_freeze_id": str(run.final_freeze.freeze_id),
            "final_freeze_fingerprint": run.final_freeze.fingerprint,
            "selection_bias_status": run.selection_bias.status.value,
            "selection_bias_calculation_id": str(run.selection_bias.calculation_id),
            "selection_bias_population_digest": run.selection_bias.population_digest,
            "selection_bias_unavailable_reason": (
                run.selection_bias.unavailable_reason.value
                if run.selection_bias.unavailable_reason is not None
                else None
            ),
        }
    _offline_write_once(
        attempt_root / "attempt-result.json",
        _canonical_bytes(terminal),
        attempt_root,
    )
    return terminal


def _offline_attempt_claim(
    attempt_id: UUID,
    mode: OfflineMode,
    preflight: Mapping[str, object],
) -> dict[str, object]:
    source = preflight["source"]
    return {
        "schema": _OFFLINE_CLAIM_SCHEMA,
        "attempt_id": str(attempt_id),
        "mode": mode.value,
        "status": "CLAIMED",
        "invocation_id": None,
        "expected_source_head": preflight["expected_source_head"],
        "source": dict(source),
        "preflight_sha256": preflight["preflight_sha256"],
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "automatic_retry": "FORBIDDEN",
        "resume": "FORBIDDEN",
    }


def _offline_materialize_progress(
    progresses: Iterable[evaluator._SessionReplayProgress],
) -> tuple[
    list[dict[str, object]],
    dict[str, object] | None,
    Exception | None,
]:
    rows: list[dict[str, object]] = []
    for progress in progresses:
        try:
            rows.append(_offline_session_record_material(progress))
        except Exception as error:
            return rows, _offline_progress_coordinate(progress), error
    return rows, None, None


def _offline_replay_failure_coordinate(
    error: Exception,
) -> dict[str, object] | None:
    if not isinstance(error, evaluator.AnnualReplayFailure):
        return None
    context = error.context
    return {
        "scored_year": context.scored_year,
        "program_id": str(context.program_id),
        "slot_id": str(context.slot_id),
        "symbol": context.symbol,
        "cost_case": context.cost_case.value if context.cost_case is not None else None,
        "session_date": (
            context.session_date.isoformat()
            if context.session_date is not None
            else None
        ),
        "operation_stage": context.operation_stage.value,
    }


def _offline_run_smoke(
    *,
    mode: OfflineMode,
    history: arch151.Arch150D1RSourceHistory,
    source_material: Mapping[str, object],
    attempt_id: UUID,
    invocation_id: UUID,
    preflight: Mapping[str, object],
    started_ns: int,
    progress_sink: Callable[[str], None] | None,
    progress_buffer: list[evaluator._SessionReplayProgress] | None = None,
) -> _OfflineSmokeOutcome:
    run_shape = preflight["run_shape"]
    assert isinstance(run_shape, dict)
    sessions = tuple(date.fromisoformat(item) for item in run_shape["smoke_sessions"])
    expected_count = run_shape["expected_smoke_records"]
    progresses = progress_buffer if progress_buffer is not None else []
    calibrations: dict[str, bool | None] = {}
    calibration_cache = evaluator._FamilyACalibrationCache(history)
    active_program_id: UUID | None = None
    preparation_cache: evaluator._PreparationCache | None = None
    simulation_error: Exception | None = None
    observer_failed_coordinate: list[dict[str, object]] = []
    last_progress_coordinate: list[dict[str, object]] = []
    try:
        for slot in arch151.CANONICAL_SLOTS:
            if slot.program_id != active_program_id:
                active_program_id = slot.program_id
                program = evaluator._slot_program(slot)
                if program.family is arch151.StrategyFamily.CROSS_ETF_TREND_PULLBACK:
                    try:
                        preparation_cache = evaluator._PreparationCache(history)
                    except Exception as error:
                        raise evaluator.AnnualReplayFailure(
                            evaluator.AnnualReplayFailureContext(
                                2019,
                                slot.program_id,
                                slot.slot_id,
                                slot.symbol,
                                None,
                                None,
                                evaluator.AnnualReplayOperationStage.PROGRAM_FEATURE_PREPARATION,
                            )
                        ) from error
                else:
                    preparation_cache = None

            def observe(
                progress: evaluator._SessionReplayProgress, *, replay_slot=slot
            ) -> None:
                progresses.append(progress)
                last_progress_coordinate[:] = [_offline_progress_coordinate(progress)]
                per_slot_records = len(sessions) * len(
                    arch151.EVALUATION_ECONOMICS_ORDER
                )
                if len(progresses) % per_slot_records == 0:
                    try:
                        _offline_progress(
                            progress_sink,
                            mode=mode,
                            stage="slot_replay",
                            started_ns=started_ns,
                            records=len(progresses),
                            slot=replay_slot,
                            scored_year=2019,
                            attempt_id=attempt_id,
                            expected_records=expected_count,
                        )
                    except Exception:
                        observer_failed_coordinate.append(
                            _offline_progress_coordinate(progress)
                        )
                        raise

            slot_results = evaluator._simulate_diagnostic_sessions(
                history,
                slot,
                sessions,
                preparation_cache=preparation_cache,
                calibration_cache=calibration_cache,
                on_session_replay=observe,
            )
            calibrations[str(slot.slot_id)] = slot_results[0].calibration_available
            _offline_progress(
                progress_sink,
                mode=mode,
                stage="slot_complete",
                started_ns=started_ns,
                records=len(progresses),
                slot=slot,
                scored_year=2019,
                attempt_id=attempt_id,
                expected_records=expected_count,
            )
    except KeyboardInterrupt:
        simulation_error = OfflineError(OfflineFailureCode.INTERRUPTED)
    except Exception as error:
        simulation_error = error

    rows, material_failure_coordinate, material_error = _offline_materialize_progress(
        progresses
    )
    failed_coordinate = (
        material_failure_coordinate
        or (observer_failed_coordinate[0] if observer_failed_coordinate else None)
        or (
            last_progress_coordinate[0]
            if isinstance(simulation_error, OfflineError)
            and simulation_error.code is OfflineFailureCode.PROGRESS_REPORTING_FAILED
            and last_progress_coordinate
            else None
        )
        or _offline_replay_failure_coordinate(simulation_error)
    )
    if simulation_error is not None or material_error is not None:
        error = simulation_error or material_error
        assert error is not None
        partial = {
            "schema": _OFFLINE_PARTIAL_SMOKE_SCHEMA,
            "mode": mode.value,
            "attempt_id": str(attempt_id),
            "invocation_id": str(invocation_id),
            "scored_year": 2019,
            "expected_session_cost_records": expected_count,
            "observed_session_cost_records": len(progresses),
            "source_digest": source_material["source_digest"],
            "validated_input_digest": source_material["validated_input_digest"],
            "records": rows,
            "failed_coordinate": failed_coordinate,
            "last_completed_coordinate": (
                last_progress_coordinate[0] if last_progress_coordinate else None
            ),
            "failure_attribution": _offline_failure_attribution(
                error,
                OperatorFailureStage.OFFLINE_PROGRESS_REPORTING
                if observer_failed_coordinate
                or (
                    isinstance(simulation_error, OfflineError)
                    and simulation_error.code
                    is OfflineFailureCode.PROGRESS_REPORTING_FAILED
                )
                else OperatorFailureStage.OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION
                if material_error is not None
                else OperatorFailureStage.OFFLINE_SMOKE_SIMULATION,
                scored_year=2019,
            ),
            "partial_materialization_failure_type": (
                type(material_error).__name__ if material_error is not None else None
            ),
            "candidate_evaluation": "NOT_EVALUATED",
            "automatic_retry": "FORBIDDEN",
        }
        return _OfflineSmokeOutcome(
            None,
            False,
            error,
            partial,
            failed_coordinate,
            OfflineFailureCode.PROGRESS_REPORTING_FAILED
            if observer_failed_coordinate
            or (
                isinstance(simulation_error, OfflineError)
                and simulation_error.code
                is OfflineFailureCode.PROGRESS_REPORTING_FAILED
            )
            else OfflineFailureCode.SMOKE_EVIDENCE_CONSTRUCTION_FAILED
            if material_error is not None
            else OfflineFailureCode.INTERRUPTED
            if isinstance(simulation_error, OfflineError)
            and simulation_error.code is OfflineFailureCode.INTERRUPTED
            else OfflineFailureCode.SMOKE_SIMULATION_FAILED,
            OperatorFailureStage.OFFLINE_PROGRESS_REPORTING
            if observer_failed_coordinate
            or (
                isinstance(simulation_error, OfflineError)
                and simulation_error.code
                is OfflineFailureCode.PROGRESS_REPORTING_FAILED
            )
            else OperatorFailureStage.OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION
            if material_error is not None
            else OperatorFailureStage.OFFLINE_SMOKE_SIMULATION,
        )

    expected_coordinates = {
        (
            2019,
            str(slot.program_id),
            str(slot.slot_id),
            slot.symbol,
            case.value,
            session.isoformat(),
        )
        for slot in arch151.CANONICAL_SLOTS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
        for session in sessions
    }
    coordinate_for_progress = {
        (
            item.scored_year,
            str(item.slot.program_id),
            str(item.slot.slot_id),
            item.slot.symbol,
            item.cost_case.value,
            item.record.session_date.isoformat(),
        ): item
        for item in progresses
    }
    observed_coordinates = set(coordinate_for_progress)
    equity_chains_ok = (
        len(progresses) == expected_count
        and observed_coordinates == expected_coordinates
    )
    rows_by_coordinate = {
        (
            row["scored_year"],
            row["program_id"],
            row["slot_id"],
            row["symbol"],
            row["cost_case"],
            row["session_date"],
        ): row
        for row in rows
    }
    for slot in arch151.CANONICAL_SLOTS:
        for case in arch151.EVALUATION_ECONOMICS_ORDER:
            chain = [
                coordinate_for_progress.get(
                    (
                        2019,
                        str(slot.program_id),
                        str(slot.slot_id),
                        slot.symbol,
                        case.value,
                        session.isoformat(),
                    )
                )
                for session in sessions
            ]
            chain_ok = len(chain) == len(sessions) and all(
                item is not None for item in chain
            )
            previous_equity = None
            if chain_ok:
                for item in chain:
                    assert item is not None
                    expected_start = (
                        previous_equity if previous_equity is not None else Decimal(1)
                    )
                    if (
                        item.record.starting_equity != expected_start
                        or item.record.closing_equity is None
                    ):
                        chain_ok = False
                        break
                    previous_equity = item.record.closing_equity
            for session in sessions:
                row_key = (
                    2019,
                    str(slot.program_id),
                    str(slot.slot_id),
                    slot.symbol,
                    case.value,
                    session.isoformat(),
                )
                if row_key in rows_by_coordinate:
                    rows_by_coordinate[row_key]["equity_chain_reconciled"] = chain_ok
            equity_chains_ok = equity_chains_ok and chain_ok
    complete = (
        len(rows) == expected_count
        and observed_coordinates == expected_coordinates
        and equity_chains_ok
        and all(
            row["failure"] is None
            and row["closing_equity"] is not None
            and row["cash_reconciled"] is True
            and row["mandatory_liquidation_status"] in ("OBSERVED", "SATISFIED")
            for row in rows
        )
    )
    smoke = {
        "schema": _OFFLINE_SMOKE_SCHEMA,
        "mode": mode.value,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_head": preflight["source"]["head"],
        "source_tree": preflight["source"]["tree"],
        "source_digest": source_material["source_digest"],
        "validated_input_digest": source_material["validated_input_digest"],
        "source_binding_id": source_material["source_binding_id"],
        "dataset_id": source_material["dataset_id"],
        "custody_id": source_material["custody_id"],
        "evidence_id": source_material["evidence_id"],
        "manifest_id": str(arch151.CANONICAL_MANIFEST.manifest_id),
        "manifest_fingerprint": arch151.CANONICAL_MANIFEST.fingerprint,
        "sessions": [item.isoformat() for item in sessions],
        "expected_session_cost_records": expected_count,
        "observed_session_cost_records": len(progresses),
        "observed_coordinates_match_expected": observed_coordinates
        == expected_coordinates,
        "equity_chains_reconciled": equity_chains_ok,
        "calibration_available_by_slot": calibrations,
        "complete": complete,
        "candidate_evaluation": "NOT_EVALUATED",
        "qualification": "NOT_EVALUATED",
        "source_attestation": None,
        "records": rows,
        "automatic_retry": "FORBIDDEN",
    }
    return _OfflineSmokeOutcome(smoke, complete)


def _offline_not_run(
    mode: OfflineMode, attempt_id: UUID | None, code: OfflineFailureCode
) -> dict[str, object]:
    return {
        "schema": _OFFLINE_TERMINAL_SCHEMA,
        "mode": mode.value,
        "status": OfflineStatus.NOT_RUN.value,
        "attempt_id": str(attempt_id) if attempt_id is not None else None,
        "failure_code": code.value,
        "candidate_evaluation": "NOT_EVALUATED",
        "final_freeze_status": "NOT_EVALUATED",
        "automatic_retry": "FORBIDDEN",
        "resume": "FORBIDDEN",
        "terminal_persisted": False,
    }


def _offline_consumed_without_terminal(
    mode: OfflineMode,
    attempt_id: UUID,
    code: OfflineFailureCode,
    attempt_root: Path,
) -> dict[str, object]:
    terminal_path = attempt_root / "attempt-result.json"
    try:
        terminal_exists = _offline_path_present(terminal_path)
    except OfflineError:
        terminal_exists = False
    return {
        "schema": _OFFLINE_TERMINAL_SCHEMA,
        "mode": mode.value,
        "status": (
            OfflineStatus.CONSUMED_UNCONFIRMED.value
            if terminal_exists
            else OfflineStatus.CONSUMED_UNPERSISTED.value
        ),
        "attempt_id": str(attempt_id),
        "attempt_root": str(attempt_root),
        "failure_code": code.value,
        "candidate_evaluation": "NOT_EVALUATED",
        "final_freeze_status": "NOT_EVALUATED",
        "automatic_retry": "FORBIDDEN",
        "resume": "FORBIDDEN",
        "terminal_persistence_confirmed": False,
    }


def _offline_failure_code_for(
    error: Exception, stage: OperatorFailureStage
) -> OfflineFailureCode:
    if isinstance(error, OfflineError):
        return error.code
    if stage is OperatorFailureStage.OFFLINE_SOURCE_LOAD:
        return OfflineFailureCode.SOURCE_LOAD_FAILED
    if stage is OperatorFailureStage.OFFLINE_SMOKE_SIMULATION:
        return OfflineFailureCode.SMOKE_SIMULATION_FAILED
    if stage is OperatorFailureStage.OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION:
        return OfflineFailureCode.SMOKE_EVIDENCE_CONSTRUCTION_FAILED
    if stage is OperatorFailureStage.OFFLINE_PROGRESS_REPORTING:
        return OfflineFailureCode.PROGRESS_REPORTING_FAILED
    if stage is OperatorFailureStage.OFFLINE_ANNUAL_SIMULATION:
        return OfflineFailureCode.ANNUAL_SIMULATION_FAILED
    if stage is OperatorFailureStage.OFFLINE_DEVELOPMENT_COMPOSITION:
        return OfflineFailureCode.DEVELOPMENT_COMPOSITION_FAILED
    if stage is OperatorFailureStage.OFFLINE_REPORT_SERIALIZATION:
        return OfflineFailureCode.REPORT_SERIALIZATION_FAILED
    if stage in (
        OperatorFailureStage.OFFLINE_SOURCE_ATTESTATION,
        OperatorFailureStage.DEVELOPMENT_EVIDENCE_ISSUANCE,
    ):
        return OfflineFailureCode.SOURCE_ATTESTATION_FAILED
    if stage is OperatorFailureStage.OFFLINE_EVIDENCE_PERSISTENCE:
        return OfflineFailureCode.EVIDENCE_WRITE_FAILED
    return OfflineFailureCode.UNCLASSIFIED_FAILURE


def _offline_batch_population_is_exact(
    batch: object,
    history: arch151.Arch150D1RSourceHistory,
    scored_year: int,
) -> bool:
    if type(batch) is not evaluator.CanonicalYearBatch:
        return False
    expected = tuple(
        (slot.slot_id, case)
        for slot in arch151.CANONICAL_SLOTS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    )
    observed = tuple((item.slot.slot_id, item.cost_case) for item in batch.evaluations)
    expected_binding = evaluator._development_source_binding(history)
    return (
        batch.scored_year == scored_year
        and batch.source_digest == history.source_digest
        and batch.source_binding == expected_binding
        and batch.manifest_id == arch151.CANONICAL_MANIFEST.manifest_id
        and batch.manifest_fingerprint == arch151.CANONICAL_MANIFEST.fingerprint
        and observed == expected
    )


def _offline_persist_abort(
    state: _OfflineAttemptState,
    *,
    error: Exception,
    failure_code: OfflineFailureCode,
    stage: OperatorFailureStage,
    status: OfflineStatus = OfflineStatus.FAILED,
    failed_coordinate: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        return _offline_persist_failure(
            attempt_root=state.attempt_root,
            attempt_id=state.attempt_id,
            mode=state.mode,
            preflight=state.preflight,
            revision=state.revision,
            invocation_id=state.invocation_id,
            error=error,
            failure_code=failure_code,
            stage=stage,
            started_ns=state.started_ns,
            source_digest=state.source_digest,
            validated_input_digest=state.validated_input_digest,
            source_artifact=state.source_artifact,
            smoke_artifact=state.smoke_artifact,
            campaign_artifact=state.campaign_artifact,
            year_artifacts=tuple(state.year_artifacts),
            attempted_years=tuple(state.attempted_years),
            completed_years=tuple(state.completed_years),
            partial_artifacts=tuple(state.partial_artifacts),
            status=status,
            scored_year=state.scored_year,
            run=state.run,
            report=state.report,
            report_sha256=state.report_sha256,
            report_artifact=state.report_artifact,
            source_attestation=state.source_attestation,
            source_attestation_artifact=state.source_attestation_artifact,
            development_evidence_handoff=state.development_evidence_handoff,
            failed_coordinate=failed_coordinate or state.failure_coordinate,
        )
    except (Exception, KeyboardInterrupt):
        return _offline_consumed_without_terminal(
            state.mode,
            state.attempt_id,
            OfflineFailureCode.EVIDENCE_WRITE_FAILED,
            state.attempt_root,
        )


def _offline_write_partial(
    state: _OfflineAttemptState,
    *,
    filename: str,
    relative_path: str,
    material: Mapping[str, object],
) -> dict[str, object]:
    if state.mode_root is None:
        raise OfflineError(OfflineFailureCode.EVIDENCE_ROOT_INVALID)
    body = _canonical_bytes(material)
    digest = _offline_write_once(state.mode_root / filename, body, state.mode_root)
    return {"path": relative_path, "sha256": digest, "byte_length": len(body)}


def _offline_partial_year_material(
    *,
    state: _OfflineAttemptState,
    history: arch151.Arch150D1RSourceHistory,
    scored_year: int,
    progresses: list[evaluator._SessionReplayProgress],
    error: Exception,
    failure_stage: OperatorFailureStage,
    failed_coordinate: Mapping[str, object] | None,
) -> dict[str, object]:
    rows, material_coordinate, material_error = _offline_materialize_progress(
        progresses
    )
    failed = (
        material_coordinate
        or failed_coordinate
        or _offline_replay_failure_coordinate(error)
    )
    attribution = _offline_failure_attribution(
        material_error or error,
        OperatorFailureStage.OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION
        if material_error is not None
        else failure_stage,
        scored_year=scored_year,
    )
    if failed is not None:
        attribution["failed_coordinate"] = dict(failed)
    return {
        "schema": _OFFLINE_PARTIAL_YEAR_SCHEMA,
        "mode": OfflineMode.CAMPAIGN.value,
        "attempt_id": str(state.attempt_id),
        "invocation_id": str(state.invocation_id),
        "source_head": state.revision.head,
        "source_tree": state.revision.tree,
        "scored_year": scored_year,
        "expected_replay_count": len(arch151.CANONICAL_SLOTS)
        * len(arch151.EVALUATION_ECONOMICS_ORDER),
        "expected_session_cost_records": len(arch151.CANONICAL_SLOTS)
        * len(arch151._published_sessions_for_year(scored_year))
        * len(arch151.EVALUATION_ECONOMICS_ORDER),
        "observed_session_cost_records": len(progresses),
        "source_digest": history.source_digest,
        "validated_input_digest": state.validated_input_digest,
        "records": rows,
        "failed_coordinate": failed,
        "failure_attribution": attribution,
        "partial_materialization_failure_type": (
            type(material_error).__name__ if material_error is not None else None
        ),
        "candidate_evaluation": "NOT_EVALUATED",
        "automatic_retry": "FORBIDDEN",
    }


def _offline_partial_smoke_material(
    *,
    state: _OfflineAttemptState,
    progresses: list[evaluator._SessionReplayProgress],
    error: Exception,
) -> dict[str, object]:
    rows, failed_coordinate, material_error = _offline_materialize_progress(progresses)
    last_completed = (
        _offline_progress_coordinate(progresses[-1]) if progresses else None
    )
    attribution = _offline_failure_attribution(
        material_error or error,
        OperatorFailureStage.OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION
        if material_error is not None
        else state.stage,
        scored_year=2019,
    )
    if failed_coordinate is not None:
        attribution["failed_coordinate"] = dict(failed_coordinate)
    if last_completed is not None:
        attribution["last_completed_coordinate"] = last_completed
    run_shape = state.preflight["run_shape"]
    assert isinstance(run_shape, dict)
    return {
        "schema": _OFFLINE_PARTIAL_SMOKE_SCHEMA,
        "mode": state.mode.value,
        "attempt_id": str(state.attempt_id),
        "invocation_id": str(state.invocation_id),
        "source_head": state.revision.head,
        "source_tree": state.revision.tree,
        "scored_year": 2019,
        "expected_session_cost_records": run_shape["expected_smoke_records"],
        "observed_session_cost_records": len(progresses),
        "source_digest": state.source_digest,
        "validated_input_digest": state.validated_input_digest,
        "records": rows,
        "failed_coordinate": failed_coordinate,
        "last_completed_coordinate": last_completed,
        "failure_attribution": attribution,
        "partial_materialization_failure_type": (
            type(material_error).__name__ if material_error is not None else None
        ),
        "candidate_evaluation": "NOT_EVALUATED",
        "qualification": "NOT_EVALUATED",
        "source_attestation": None,
        "automatic_retry": "FORBIDDEN",
    }


def _execute_claimed_offline_attempt(
    state: _OfflineAttemptState,
    *,
    progress_sink: Callable[[str], None] | None,
) -> dict[str, object]:
    attempt_id = state.attempt_id
    invocation_id = state.invocation_id
    mode = state.mode
    preflight = state.preflight
    source = preflight["source"]
    if not isinstance(source, dict):
        raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
    state.stage = OperatorFailureStage.OFFLINE_EVIDENCE_PERSISTENCE
    claim = _offline_attempt_claim(attempt_id, mode, preflight)
    claim["invocation_id"] = str(invocation_id)
    _offline_write_once(
        state.attempt_root / "attempt.json", _canonical_bytes(claim), state.attempt_root
    )
    _offline_write_once(
        state.attempt_root / "preflight.json",
        _canonical_bytes(preflight),
        state.attempt_root,
    )
    source_revision_material = {
        "schema": "arch151-offline-source-revision/v1",
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_revision": {
            "branch": state.revision.branch,
            "origin": state.revision.origin,
            "head": state.revision.head,
            "tree": state.revision.tree,
        },
        "refs": {
            "upstream": source["upstream"],
            "feature_tracking_head": source["feature_tracking_head"],
            "feature_live_head": source["feature_live_head"],
            "develop_tracking_head": source["develop_tracking_head"],
            "develop_live_head": source["develop_live_head"],
        },
        "preflight_sha256": preflight["preflight_sha256"],
    }
    revision_body = _canonical_bytes(source_revision_material)
    revision_digest = _offline_write_once(
        state.attempt_root / "source-revision.json", revision_body, state.attempt_root
    )
    state.mode_root = _offline_create_mode_root(state.attempt_root, mode)

    state.stage = OperatorFailureStage.OFFLINE_SOURCE_LOAD
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="source_authentication_start",
        started_ns=state.started_ns,
        attempt_id=attempt_id,
    )
    history = _load_accepted_source_history()
    state.active_history = history
    state.source_material = _offline_source_material(
        history,
        state.revision,
        attempt_id,
        invocation_id,
        str(preflight["preflight_sha256"]),
    )
    state.source_digest = state.source_material["source_digest"]
    state.validated_input_digest = state.source_material["validated_input_digest"]
    source_body = _canonical_bytes(state.source_material)
    source_file_digest = _offline_write_once(
        state.attempt_root / "source.json", source_body, state.attempt_root
    )
    state.source_artifact = {
        "path": "source.json",
        "sha256": source_file_digest,
        "byte_length": len(source_body),
        "source_revision_sha256": revision_digest,
    }
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="source_authentication_complete",
        started_ns=state.started_ns,
        attempt_id=attempt_id,
    )

    state.stage = OperatorFailureStage.OFFLINE_SMOKE_SIMULATION
    state.active_smoke_progresses = []
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="smoke_start",
        started_ns=state.started_ns,
        attempt_id=attempt_id,
        expected_records=preflight["run_shape"]["expected_smoke_records"],
    )
    smoke = _offline_run_smoke(
        mode=mode,
        history=history,
        source_material=state.source_material,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        preflight=preflight,
        started_ns=state.started_ns,
        progress_sink=progress_sink,
        progress_buffer=state.active_smoke_progresses,
    )
    if smoke.error is not None:
        state.stage = smoke.failure_stage or state.stage
        state.failure_coordinate = (
            dict(smoke.failed_coordinate)
            if smoke.failed_coordinate is not None
            else None
        )
        if smoke.partial_evidence is not None:
            state.partial_artifacts.append(
                _offline_write_partial(
                    state,
                    filename="partial-smoke.json",
                    relative_path=(
                        "smoke/partial-smoke.json"
                        if mode is OfflineMode.SMOKE
                        else "campaign/partial-smoke.json"
                    ),
                    material=smoke.partial_evidence,
                )
            )
        raise _OfflineLifecycleAbort(
            smoke.error,
            smoke.failure_code or OfflineFailureCode.SMOKE_SIMULATION_FAILED,
            state.stage,
            status=(
                OfflineStatus.INTERRUPTED
                if smoke.failure_code is OfflineFailureCode.INTERRUPTED
                else OfflineStatus.FAILED
            ),
            failed_coordinate=state.failure_coordinate,
        )
    if smoke.evidence is None or state.mode_root is None:
        raise _OfflineLifecycleAbort(
            OfflineError(OfflineFailureCode.SMOKE_EVIDENCE_CONSTRUCTION_FAILED),
            OfflineFailureCode.SMOKE_EVIDENCE_CONSTRUCTION_FAILED,
            OperatorFailureStage.OFFLINE_SMOKE_EVIDENCE_CONSTRUCTION,
        )
    smoke_body = _canonical_bytes(smoke.evidence)
    smoke_digest = _offline_write_once(
        state.mode_root / "smoke.json", smoke_body, state.mode_root
    )
    mode_prefix = "smoke" if mode is OfflineMode.SMOKE else "campaign"
    state.smoke_artifact = {
        "path": f"{mode_prefix}/smoke.json",
        "sha256": smoke_digest,
        "byte_length": len(smoke_body),
        "expected_session_cost_records": smoke.evidence[
            "expected_session_cost_records"
        ],
        "observed_session_cost_records": smoke.evidence[
            "observed_session_cost_records"
        ],
    }
    state.active_smoke_progresses = None
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="smoke_complete",
        started_ns=state.started_ns,
        records=smoke.evidence["observed_session_cost_records"],
        attempt_id=attempt_id,
        expected_records=smoke.evidence["expected_session_cost_records"],
    )
    if not smoke.complete:
        raise _OfflineLifecycleAbort(
            OfflineError(OfflineFailureCode.SMOKE_INCOMPLETE),
            OfflineFailureCode.SMOKE_INCOMPLETE,
            OperatorFailureStage.OFFLINE_SMOKE_SIMULATION,
            status=OfflineStatus.INCOMPLETE,
        )
    if mode is OfflineMode.SMOKE:
        return _offline_terminal(
            attempt_root=state.attempt_root,
            attempt_id=attempt_id,
            mode=mode,
            status=OfflineStatus.COMPLETED,
            preflight=preflight,
            invocation_id=invocation_id,
            revision=state.revision,
            failure_code=None,
            source_digest=state.source_digest,
            validated_input_digest=state.validated_input_digest,
            source_artifact=state.source_artifact,
            smoke_artifact=state.smoke_artifact,
            elapsed_ns=time.monotonic_ns() - state.started_ns,
        )

    context = _ActiveDevelopmentInvocation(
        _seal=_ACTIVE_INVOCATION_SEAL,
        attempt_id=attempt_id,
        invocation_id=invocation_id,
        source_revision=state.revision,
    )
    batches: list[evaluator.CanonicalYearBatch] = []
    expected_population = tuple(
        (slot.slot_id, case)
        for slot in arch151.CANONICAL_SLOTS
        for case in arch151.EVALUATION_ECONOMICS_ORDER
    )
    for year in arch151.SCORED_YEARS:
        state.scored_year = year
        state.attempted_years.append(year)
        progresses: list[evaluator._SessionReplayProgress] = []
        state.active_year_progresses = progresses
        failed_coordinates: list[dict[str, object]] = []
        slot_span = len(arch151._published_sessions_for_year(year)) * len(
            arch151.EVALUATION_ECONOMICS_ORDER
        )
        expected_records = len(arch151.CANONICAL_SLOTS) * slot_span
        state.stage = OperatorFailureStage.OFFLINE_ANNUAL_SIMULATION
        _offline_progress(
            progress_sink,
            mode=mode,
            stage="annual_year_start",
            started_ns=state.started_ns,
            scored_year=year,
            attempt_id=attempt_id,
            expected_records=expected_records,
        )

        def observe_annual(
            progress: evaluator._SessionReplayProgress,
            *,
            year=year,
            progresses=progresses,
            slot_span=slot_span,
            expected_records=expected_records,
            failed_coordinates=failed_coordinates,
        ) -> None:
            progresses.append(progress)
            if len(progresses) % slot_span == 0:
                try:
                    _offline_progress(
                        progress_sink,
                        mode=mode,
                        stage="annual_slot_complete",
                        started_ns=state.started_ns,
                        records=len(progresses),
                        slot=progress.slot,
                        scored_year=year,
                        attempt_id=attempt_id,
                        expected_records=expected_records,
                    )
                except Exception:
                    failed_coordinates.append(_offline_progress_coordinate(progress))
                    raise

        try:
            batch = evaluator._simulate_canonical_year(
                history, year, on_session_replay=observe_annual
            )
        except Exception as error:
            stage = (
                OperatorFailureStage.OFFLINE_PROGRESS_REPORTING
                if failed_coordinates
                else OperatorFailureStage.OFFLINE_ANNUAL_SIMULATION
            )
            state.stage = stage
            coordinate = (
                failed_coordinates[0]
                if failed_coordinates
                else _offline_replay_failure_coordinate(error)
            )
            partial = _offline_partial_year_material(
                state=state,
                history=history,
                scored_year=year,
                progresses=progresses,
                error=error,
                failure_stage=stage,
                failed_coordinate=coordinate,
            )
            ref = _offline_write_partial(
                state,
                filename=f"partial-year-{year}.json",
                relative_path=f"campaign/partial-year-{year}.json",
                material=partial,
            )
            state.partial_artifacts.append(
                {
                    **ref,
                    "scored_year": year,
                    "observed_session_cost_records": len(progresses),
                }
            )
            raise _OfflineLifecycleAbort(
                error,
                OfflineFailureCode.PROGRESS_REPORTING_FAILED
                if failed_coordinates
                else OfflineFailureCode.ANNUAL_SIMULATION_FAILED,
                stage,
                scored_year=year,
                failed_coordinate=coordinate,
            ) from error
        if not _offline_batch_population_is_exact(batch, history, year):
            error = OfflineError(OfflineFailureCode.YEAR_INCOMPLETE)
            stage = OperatorFailureStage.OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION
            partial = _offline_partial_year_material(
                state=state,
                history=history,
                scored_year=year,
                progresses=progresses,
                error=error,
                failure_stage=stage,
                failed_coordinate=None,
            )
            ref = _offline_write_partial(
                state,
                filename=f"partial-year-{year}.json",
                relative_path=f"campaign/partial-year-{year}.json",
                material=partial,
            )
            state.partial_artifacts.append(
                {
                    **ref,
                    "scored_year": year,
                    "observed_session_cost_records": len(progresses),
                }
            )
            raise _OfflineLifecycleAbort(
                error,
                OfflineFailureCode.YEAR_INCOMPLETE,
                stage,
                status=OfflineStatus.INCOMPLETE,
                scored_year=year,
            )
        try:
            state.stage = OperatorFailureStage.OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION
            year_body = _canonical_bytes(
                _year_batch_material(
                    batch,
                    revision=state.revision,
                    attempt_id=attempt_id,
                    invocation_id=invocation_id,
                )
            )
        except Exception as error:
            partial = _offline_partial_year_material(
                state=state,
                history=history,
                scored_year=year,
                progresses=progresses,
                error=error,
                failure_stage=OperatorFailureStage.OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION,
                failed_coordinate=None,
            )
            ref = _offline_write_partial(
                state,
                filename=f"partial-year-{year}.json",
                relative_path=f"campaign/partial-year-{year}.json",
                material=partial,
            )
            state.partial_artifacts.append(
                {
                    **ref,
                    "scored_year": year,
                    "observed_session_cost_records": len(progresses),
                }
            )
            raise _OfflineLifecycleAbort(
                error,
                OfflineFailureCode.ANNUAL_SIMULATION_FAILED,
                OperatorFailureStage.OFFLINE_ANNUAL_EVIDENCE_CONSTRUCTION,
                scored_year=year,
            ) from error
        state.stage = OperatorFailureStage.OFFLINE_EVIDENCE_PERSISTENCE
        year_digest = _offline_write_once(
            state.mode_root / f"year-{year}.json", year_body, state.mode_root
        )
        state.year_artifacts.append(
            {
                "path": f"campaign/year-{year}.json",
                "scored_year": year,
                "sha256": year_digest,
                "byte_length": len(year_body),
                "batch_id": str(batch.batch_id),
                "complete": batch.complete,
                "expected_replay_count": len(expected_population),
                "observed_replay_count": len(batch.evaluations),
            }
        )
        if not batch.complete or _batch_failure_records(batch):
            raise _OfflineLifecycleAbort(
                OfflineError(OfflineFailureCode.YEAR_INCOMPLETE),
                OfflineFailureCode.YEAR_INCOMPLETE,
                OperatorFailureStage.OFFLINE_ANNUAL_SIMULATION,
                status=OfflineStatus.INCOMPLETE,
                scored_year=year,
            )
        batches.append(batch)
        state.completed_years.append(year)
        state.active_year_progresses = None
        _offline_progress(
            progress_sink,
            mode=mode,
            stage="annual_year_complete",
            started_ns=state.started_ns,
            records=len(batch.evaluations),
            scored_year=year,
            attempt_id=attempt_id,
            expected_records=len(expected_population),
        )

    state.scored_year = None
    state.stage = OperatorFailureStage.OFFLINE_DEVELOPMENT_COMPOSITION
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="development_composition_start",
        started_ns=state.started_ns,
        records=len(state.completed_years) * len(expected_population),
        attempt_id=attempt_id,
        expected_records=480,
    )
    try:
        state.run = evaluator.compose_development_evaluation(tuple(batches))
        context.bind_run(state.run)
        if (
            state.run.fold_evaluation_count != 480
            or tuple(item.scored_year for item in state.run.year_batches)
            != arch151.SCORED_YEARS
            or state.run.source_digest != history.source_digest
        ):
            raise OfflineError(OfflineFailureCode.DEVELOPMENT_COMPOSITION_FAILED)
    except Exception as error:
        raise _OfflineLifecycleAbort(
            error,
            OfflineFailureCode.DEVELOPMENT_COMPOSITION_FAILED,
            OperatorFailureStage.OFFLINE_DEVELOPMENT_COMPOSITION,
        ) from None

    state.stage = OperatorFailureStage.OFFLINE_REPORT_SERIALIZATION
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="report_serialization_start",
        started_ns=state.started_ns,
        records=480,
        attempt_id=attempt_id,
        expected_records=480,
    )
    try:
        state.report = evaluator.serialize_development_evaluation(state.run)
        report_body = state.report.canonical_json_bytes
        if (
            type(report_body) is not bytes
            or hashlib.sha256(report_body).hexdigest() != state.report.sha256
            or state.report.run_id != state.run.run_id
        ):
            raise OfflineError(OfflineFailureCode.REPORT_SERIALIZATION_FAILED)
        context.bind_report(state.report)
    except Exception as error:
        raise _OfflineLifecycleAbort(
            error,
            OfflineFailureCode.REPORT_SERIALIZATION_FAILED,
            OperatorFailureStage.OFFLINE_REPORT_SERIALIZATION,
        ) from None
    state.stage = OperatorFailureStage.OFFLINE_EVIDENCE_PERSISTENCE
    report_digest = _offline_write_once(
        state.mode_root / "development-report.json", report_body, state.mode_root
    )
    if report_digest != state.report.sha256:
        raise OfflineError(OfflineFailureCode.EVIDENCE_WRITE_FAILED)
    state.report_sha256 = report_digest
    state.report_artifact = {
        "path": "campaign/development-report.json",
        "sha256": report_digest,
        "byte_length": len(report_body),
    }

    state.stage = OperatorFailureStage.OFFLINE_SOURCE_ATTESTATION
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="source_attestation_start",
        started_ns=state.started_ns,
        records=480,
        attempt_id=attempt_id,
        expected_records=480,
    )
    try:
        state.source_attestation = _issue_development_source_attestation(
            context, state.run, state.report
        )
        attestation_body = state.source_attestation.canonical_json_bytes
        attestation_digest = _offline_write_once(
            state.mode_root / "source-attestation.json",
            attestation_body,
            state.mode_root,
        )
        if attestation_digest != state.source_attestation.attestation_digest:
            raise OfflineError(OfflineFailureCode.SOURCE_ATTESTATION_FAILED)
        state.source_attestation_artifact = {
            "path": "campaign/source-attestation.json",
            "sha256": attestation_digest,
            "byte_length": len(attestation_body),
        }
        if (
            state.run.final_freeze.status
            is arch151.FinalFreezeStatus.ONE_CANDIDATE_FROZEN
        ):
            authenticated = evaluator.authenticate_development_evidence(
                state.run, state.report, state.source_attestation
            )
            candidate_index = next(
                index
                for index, slot in enumerate(arch151.CANONICAL_SLOTS)
                if slot.slot_id == state.run.final_freeze.candidate_slot_id
            )
            state.development_evidence_handoff = DevelopmentEvidenceHandoff(
                _seal=_DEVELOPMENT_EVIDENCE_HANDOFF_SEAL,
                authenticated_evidence=authenticated,
                final_freeze=state.run.final_freeze,
                selection_bias_evidence=state.run.selection_bias.evidence[
                    candidate_index
                ],
                source_attestation=state.source_attestation,
            )
    except Exception as error:
        raise _OfflineLifecycleAbort(
            error,
            OfflineFailureCode.SOURCE_ATTESTATION_FAILED,
            OperatorFailureStage.DEVELOPMENT_EVIDENCE_ISSUANCE
            if isinstance(error, (arch151.AuthorizationUnavailableError, OperatorError))
            else OperatorFailureStage.OFFLINE_SOURCE_ATTESTATION,
        ) from None

    campaign = {
        "schema": _OFFLINE_CAMPAIGN_SCHEMA,
        "attempt_id": str(attempt_id),
        "invocation_id": str(invocation_id),
        "source_digest": history.source_digest,
        "validated_input_digest": state.validated_input_digest,
        "smoke_artifact": state.smoke_artifact,
        "attempted_years": list(state.attempted_years),
        "completed_years": list(state.completed_years),
        "year_artifacts": state.year_artifacts,
        "run_id": str(state.run.run_id),
        "record_count": state.run.fold_evaluation_count,
        "report_artifact": state.report_artifact,
        "source_attestation_artifact": state.source_attestation_artifact,
        "source_attestation_id": str(state.source_attestation.attestation_id),
        "source_attestation_digest": state.source_attestation.attestation_digest,
        "final_freeze_status": state.run.final_freeze.status.value,
        "final_freeze_id": str(state.run.final_freeze.freeze_id),
        "selection_bias_status": state.run.selection_bias.status.value,
        "selection_bias_calculation_id": str(state.run.selection_bias.calculation_id),
        "development_evidence_id": (
            str(state.development_evidence_handoff.authenticated_evidence.evidence_id)
            if state.development_evidence_handoff is not None
            else None
        ),
        "candidate_evaluation": "COMPLETED",
        "automatic_retry": "FORBIDDEN",
    }
    state.stage = OperatorFailureStage.OFFLINE_EVIDENCE_PERSISTENCE
    campaign_body = _canonical_bytes(campaign)
    campaign_digest = _offline_write_once(
        state.mode_root / "campaign.json", campaign_body, state.mode_root
    )
    state.campaign_artifact = {
        "path": "campaign/campaign.json",
        "sha256": campaign_digest,
        "byte_length": len(campaign_body),
    }
    _offline_progress(
        progress_sink,
        mode=mode,
        stage="terminal_persist_start",
        started_ns=state.started_ns,
        records=480,
        attempt_id=attempt_id,
        expected_records=480,
    )
    return _offline_terminal(
        attempt_root=state.attempt_root,
        attempt_id=attempt_id,
        mode=mode,
        status=OfflineStatus.COMPLETED,
        preflight=preflight,
        invocation_id=invocation_id,
        revision=state.revision,
        failure_code=None,
        source_digest=state.source_digest,
        validated_input_digest=state.validated_input_digest,
        source_artifact=state.source_artifact,
        smoke_artifact=state.smoke_artifact,
        campaign_artifact=state.campaign_artifact,
        year_artifacts=tuple(state.year_artifacts),
        attempted_years=tuple(state.attempted_years),
        completed_years=tuple(state.completed_years),
        run=state.run,
        report=state.report,
        report_sha256=state.report_sha256,
        report_artifact=state.report_artifact,
        source_attestation=state.source_attestation,
        source_attestation_artifact=state.source_attestation_artifact,
        development_evidence_handoff=state.development_evidence_handoff,
        elapsed_ns=time.monotonic_ns() - state.started_ns,
    )


def _run_offline_attempt(
    mode: OfflineMode,
    expected_source_head: str,
    attempt_id: UUID | str,
    *,
    progress_sink: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if mode not in (OfflineMode.SMOKE, OfflineMode.CAMPAIGN):
        return _offline_not_run(
            OfflineMode.PREFLIGHT, None, OfflineFailureCode.INVALID_ARGUMENTS
        )
    started_ns = time.monotonic_ns()
    try:
        parsed_id = (
            attempt_id
            if type(attempt_id) is UUID and attempt_id.int != 0
            else _parse_offline_attempt_id(attempt_id)
        )
    except OfflineError as error:
        return _offline_not_run(mode, None, error.code)
    try:
        preflight = preflight_offline(expected_source_head)
        source = preflight.get("source")
        if type(source) is not dict:
            raise OfflineError(OfflineFailureCode.SOURCE_IDENTITY_UNAVAILABLE)
        revision = SourceRevision(
            source["branch"],
            source["origin_fetch_url"],
            source["head"],
            source["tree"],
            _seal=_SOURCE_REVISION_SEAL,
        )
        invocation_id = _invocation_id(revision)
    except OfflineError as error:
        return _offline_not_run(mode, parsed_id, error.code)
    except Exception:
        return _offline_not_run(
            mode, parsed_id, OfflineFailureCode.UNCLASSIFIED_FAILURE
        )
    try:
        attempt_root = _offline_reserve_attempt(parsed_id)
    except OfflineError as error:
        if error.attempt_reserved:
            return _offline_consumed_without_terminal(
                mode,
                parsed_id,
                error.code,
                OFFLINE_EVIDENCE_ROOT / "attempts" / str(parsed_id),
            )
        return _offline_not_run(mode, parsed_id, error.code)
    state = _OfflineAttemptState(
        attempt_root=attempt_root,
        attempt_id=parsed_id,
        mode=mode,
        preflight=preflight,
        revision=revision,
        invocation_id=invocation_id,
        started_ns=started_ns,
    )
    try:
        return _execute_claimed_offline_attempt(state, progress_sink=progress_sink)
    except _OfflineLifecycleAbort as abort:
        state.stage = abort.stage
        if abort.scored_year is not None:
            state.scored_year = abort.scored_year
        state.failure_coordinate = (
            dict(abort.failed_coordinate)
            if abort.failed_coordinate is not None
            else state.failure_coordinate
        )
        return _offline_persist_abort(
            state,
            error=abort.error,
            failure_code=abort.code,
            stage=abort.stage,
            status=abort.status,
            failed_coordinate=abort.failed_coordinate,
        )
    except KeyboardInterrupt:
        error = OfflineError(OfflineFailureCode.INTERRUPTED)
        try:
            if (
                state.active_smoke_progresses
                and state.smoke_artifact is None
                and state.mode_root is not None
            ):
                partial = _offline_partial_smoke_material(
                    state=state,
                    progresses=state.active_smoke_progresses,
                    error=error,
                )
                state.partial_artifacts.append(
                    _offline_write_partial(
                        state,
                        filename="partial-smoke.json",
                        relative_path=(
                            "smoke/partial-smoke.json"
                            if mode is OfflineMode.SMOKE
                            else "campaign/partial-smoke.json"
                        ),
                        material=partial,
                    )
                )
            elif (
                state.active_year_progresses
                and state.active_history is not None
                and state.scored_year is not None
                and state.mode_root is not None
            ):
                partial = _offline_partial_year_material(
                    state=state,
                    history=state.active_history,
                    scored_year=state.scored_year,
                    progresses=state.active_year_progresses,
                    error=error,
                    failure_stage=state.stage,
                    failed_coordinate=state.failure_coordinate,
                )
                partial["last_completed_coordinate"] = _offline_progress_coordinate(
                    state.active_year_progresses[-1]
                )
                ref = _offline_write_partial(
                    state,
                    filename=f"partial-year-{state.scored_year}.json",
                    relative_path=f"campaign/partial-year-{state.scored_year}.json",
                    material=partial,
                )
                state.partial_artifacts.append(
                    {
                        **ref,
                        "scored_year": state.scored_year,
                        "observed_session_cost_records": len(
                            state.active_year_progresses
                        ),
                    }
                )
        except KeyboardInterrupt:
            return _offline_consumed_without_terminal(
                mode,
                parsed_id,
                OfflineFailureCode.EVIDENCE_WRITE_FAILED,
                attempt_root,
            )
        except Exception:
            return _offline_persist_abort(
                state,
                error=OfflineError(OfflineFailureCode.EVIDENCE_WRITE_FAILED),
                failure_code=OfflineFailureCode.EVIDENCE_WRITE_FAILED,
                stage=OperatorFailureStage.OFFLINE_EVIDENCE_PERSISTENCE,
                status=OfflineStatus.CONSUMED_UNPERSISTED,
            )
        return _offline_persist_abort(
            state,
            error=error,
            failure_code=OfflineFailureCode.INTERRUPTED,
            stage=state.stage,
            status=OfflineStatus.INTERRUPTED,
        )
    except Exception as error:
        failure_code = _offline_failure_code_for(error, state.stage)
        return _offline_persist_abort(
            state,
            error=error,
            failure_code=failure_code,
            stage=(
                OperatorFailureStage.OFFLINE_PROGRESS_REPORTING
                if failure_code is OfflineFailureCode.PROGRESS_REPORTING_FAILED
                else state.stage
            ),
        )


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _OfflineCLIArgumentError


class _RejectDuplicateAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None) -> None:
        del option_string
        if getattr(namespace, self.dest, None) is not None:
            parser.error("duplicate option")
        setattr(namespace, self.dest, values)


class _RejectDuplicateSwitchAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs) -> None:
        kwargs.setdefault("nargs", 0)
        kwargs.setdefault("default", False)
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        del values, option_string
        if getattr(namespace, self.dest, False):
            parser.error("duplicate mode")
        setattr(namespace, self.dest, True)


def _print_cli_result(result: Mapping[str, object]) -> None:
    print(f"STATUS={result.get('status', 'FAILED')}")
    print(f"FAILURE_CODE={result.get('failure_code') or 'NONE'}")
    if result.get("attempt_id") is not None:
        print(f"ATTEMPT_ID={result['attempt_id']}")
    if result.get("attempt_root") is not None:
        print(f"EVIDENCE_ROOT={result['attempt_root']}")
    if result.get("final_freeze_status") is not None:
        print(f"FINAL_FREEZE_STATUS={result['final_freeze_status']}")
    print(f"TERMINAL_PERSISTED={str(bool(result.get('terminal_persisted'))).lower()}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = _SanitizedArgumentParser(
        description=operator_help(), allow_abbrev=False, add_help=True
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight-offline", action=_RejectDuplicateSwitchAction)
    modes.add_argument("--run-offline-smoke", action=_RejectDuplicateSwitchAction)
    modes.add_argument("--run-offline-campaign", action=_RejectDuplicateSwitchAction)
    modes.add_argument("--preflight-successor", action=_RejectDuplicateSwitchAction)
    modes.add_argument("--run-successor", action=_RejectDuplicateSwitchAction)
    parser.add_argument("--expected-source-head", action=_RejectDuplicateAction)
    parser.add_argument("--attempt-id", action=_RejectDuplicateAction)
    try:
        arguments = parser.parse_args(None if argv is None else list(argv))
    except _OfflineCLIArgumentError:
        print("STATUS=FAILED")
        print("FAILURE_CODE=INVALID_ARGUMENTS")
        return 2
    except SystemExit as error:
        return int(error.code or 0)

    selected = (
        arguments.preflight_offline,
        arguments.run_offline_smoke,
        arguments.run_offline_campaign,
        arguments.preflight_successor,
        arguments.run_successor,
    )
    selected_count = sum(selected)
    if selected_count == 0:
        if (
            arguments.expected_source_head is not None
            or arguments.attempt_id is not None
        ):
            print("STATUS=FAILED")
            print("FAILURE_CODE=INVALID_ARGUMENTS")
            return 2
        print("STATUS=FAILED")
        print("FAILURE_CODE=" + OperatorFailureCode.PREDECESSOR_ATTEMPT_CONSUMED.value)
        return 2
    if arguments.preflight_successor or arguments.run_successor:
        if arguments.attempt_id is not None:
            print("STATUS=FAILED")
            print("FAILURE_CODE=INVALID_ARGUMENTS")
            return 2
        code = OperatorFailureCode.SUCCESSOR_ATTEMPT_CONSUMED
        print("STATUS=FAILED")
        print(f"FAILURE_CODE={code.value}")
        return 2

    if arguments.expected_source_head is None or not _is_git_object_id(
        arguments.expected_source_head
    ):
        print("STATUS=FAILED")
        print("FAILURE_CODE=SOURCE_HEAD_INVALID")
        return 2
    if arguments.preflight_offline:
        if arguments.attempt_id is not None:
            print("STATUS=FAILED")
            print("FAILURE_CODE=INVALID_ARGUMENTS")
            return 2
        try:
            result = preflight_offline(arguments.expected_source_head)
        except OfflineError as error:
            _print_cli_result(
                {"status": OfflineStatus.FAILED.value, "failure_code": error.code.value}
            )
            return 2
        except Exception:
            _print_cli_result(
                {
                    "status": OfflineStatus.FAILED.value,
                    "failure_code": OfflineFailureCode.UNCLASSIFIED_FAILURE.value,
                }
            )
            return 2
        print("STATUS=READY")
        print(f"EXPECTED_SOURCE_HEAD={result['expected_source_head']}")
        print(f"PREFLIGHT_SHA256={result['preflight_sha256']}")
        source = result["source"]
        if isinstance(source, dict):
            print(f"SOURCE_TREE={source['tree']}")
            print(f"FEATURE_TRACKING_HEAD={source['feature_tracking_head']}")
            print(f"FEATURE_LIVE_HEAD={source['feature_live_head']}")
            print(f"DEVELOP_TRACKING_HEAD={source['develop_tracking_head']}")
            print(f"DEVELOP_LIVE_HEAD={source['develop_live_head']}")
        print("CUSTODY_CONTENT_AUTHENTICATED=false")
        print("ATTEMPT_CREATED=false")
        return 0

    if arguments.attempt_id is None or not _is_canonical_attempt_id(
        arguments.attempt_id
    ):
        print("STATUS=FAILED")
        print("FAILURE_CODE=ATTEMPT_ID_INVALID")
        return 2
    mode = OfflineMode.SMOKE if arguments.run_offline_smoke else OfflineMode.CAMPAIGN
    result = _run_offline_attempt(
        mode,
        arguments.expected_source_head,
        arguments.attempt_id,
        progress_sink=print,
    )
    _print_cli_result(result)
    return 0 if result.get("status") == OfflineStatus.COMPLETED.value else 2


def _canonical_entrypoint_main() -> int:
    from trading_bot.experiments import (
        arch151_intraday_walkforward_operator as canonical_operator,
    )

    return canonical_operator.main()


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
    raise SystemExit(_canonical_entrypoint_main())
