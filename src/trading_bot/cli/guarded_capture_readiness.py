"""One-shot foreground orchestration for guarded capture-readiness dry runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.guarded_capture_readiness_config import (
    ExplicitArtifactReference,
    GuardedCaptureReadinessConfig,
    GuardedCaptureReadinessConfigError,
    load_guarded_capture_readiness_config,
)
from trading_bot.cli.guarded_capture_readiness_output import (
    DecisionEvidencePublicationResult,
    publish_scheduled_capture_readiness_decision,
)
from trading_bot.cli.local_lineage_head import (
    LocalLineageHeadClassification,
    LocalLineageHeadResult,
    verify_local_lineage_head,
)
from trading_bot.cli.scheduled_readiness import (
    scheduled_head_input_from_verified_authority,
)
from trading_bot.cli.windows_launch_guard import (
    LaunchGuardAcquireRequest,
    LaunchGuardReleaseResult,
    LaunchLeaseReleaseInput,
    ReleaseOperationalClassification,
    WindowsMutexApi,
    acquire_windows_launch_guard,
)
from trading_bot.runtime import (
    MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES,
    ArtifactEvidence,
    LaunchGuardAcquisitionClassification,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
    NextEligibleAction,
    ScheduledCaptureAttemptRecord,
    ScheduledCaptureReadinessDecision,
    ScheduledHealthInputs,
    ScheduledReadinessClassification,
    ScheduledReadinessInputs,
    ScheduledReadinessResult,
    ScheduledSnapshotSelectionRecord,
    SnapshotEvidence,
    VerifiedAuthoritativeHeadInput,
    capture_attempt_record_evidence,
    create_scheduled_capture_readiness_decision,
    evaluate_scheduled_capture_readiness,
    parse_capture_policy_artifact,
    parse_market_session_hours_schedule,
    parse_scheduled_capture_attempt_record,
    parse_scheduled_snapshot_selection_record,
    proposed_capture_attempt_id,
    snapshot_selection_record_evidence,
)


class GuardedCaptureReadinessDiagnostic(StrEnum):
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"
    GUARD_ALREADY_HELD = "GUARD_ALREADY_HELD"
    GUARD_ABANDONED = "GUARD_ABANDONED"
    GUARD_ACCESS_DENIED = "GUARD_ACCESS_DENIED"
    GUARD_UNSUPPORTED = "GUARD_UNSUPPORTED"
    GUARD_ERROR = "GUARD_ERROR"
    LEASE_START_PUBLICATION_FAILED = "LEASE_START_PUBLICATION_FAILED"
    HEAD_VERIFICATION_FAILED = "HEAD_VERIFICATION_FAILED"
    HOURS_ARTIFACT_INVALID = "HOURS_ARTIFACT_INVALID"
    CAPTURE_POLICY_INVALID = "CAPTURE_POLICY_INVALID"
    ATTEMPT_HISTORY_INVALID = "ATTEMPT_HISTORY_INVALID"
    READINESS_EVALUATION_FAILED = "READINESS_EVALUATION_FAILED"
    DECISION_PUBLICATION_FAILED = "DECISION_PUBLICATION_FAILED"
    LEASE_RELEASE_PUBLICATION_FAILED = "LEASE_RELEASE_PUBLICATION_FAILED"
    MUTEX_RELEASE_FAILED = "MUTEX_RELEASE_FAILED"


@dataclass(frozen=True, slots=True)
class GuardedCaptureReadinessRunResult:
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    readiness_classification: ScheduledReadinessClassification
    diagnostics: tuple[str, ...]
    next_eligible_action: NextEligibleAction
    lease_start_record_id: UUID | None = None
    proposed_capture_attempt_ordinal: int | None = None
    proposed_capture_attempt_id: UUID | None = None
    decision: ScheduledCaptureReadinessDecision | None = None
    decision_publication: DecisionEvidencePublicationResult | None = None
    lease_release_record_id: UUID | None = None


def run_guarded_capture_readiness(
    config: GuardedCaptureReadinessConfig,
    *,
    native_api: WindowsMutexApi | None = None,
    head_verifier: Callable[[Path], LocalLineageHeadResult] = (
        verify_local_lineage_head
    ),
    head_input_adapter: Callable[
        [object], VerifiedAuthoritativeHeadInput
    ] = scheduled_head_input_from_verified_authority,
    readiness_evaluator: Callable[
        [ScheduledReadinessInputs], ScheduledReadinessResult
    ] = evaluate_scheduled_capture_readiness,
    decision_publisher: Callable[
        [Path, ScheduledCaptureReadinessDecision],
        DecisionEvidencePublicationResult,
    ] = publish_scheduled_capture_readiness_decision,
) -> GuardedCaptureReadinessRunResult:
    """Run exactly one guarded dry-run without capture or provider access."""
    if type(config) is not GuardedCaptureReadinessConfig:
        raise TypeError("config must be GuardedCaptureReadinessConfig")
    session_id = config.scheduled_session_id
    launch_id = config.scheduled_launch_id
    request = LaunchGuardAcquireRequest(
        audit_root=config.scheduler_audit_root,
        scheduled_launch_id=launch_id,
        authority_epoch_id=config.authority_epoch_id,
        scheduled_phase=config.scheduled_phase,
        machine_authority_id=config.machine_authority_id,
        boot_evidence=config.boot_session_evidence,
        process_id=config.process_id,
        process_creation_timestamp_utc=config.process_creation_timestamp_utc,
        user_sid=config.account_sid,
        executable_release=config.executable_release_evidence,
        acquisition_timestamp_utc=config.acquisition_timestamp_utc,
        max_runtime_seconds=config.maximum_runtime_seconds,
        launch_policy=config.launch_guard_policy_version,
        timeout_seconds=config.mutex_timeout_seconds,
        acl_policy=config.acl_mode,
        validate_audit_root_before_acquire=False,
    )
    acquired = acquire_windows_launch_guard(request, native_api=native_api)
    if acquired.ownership is None:
        classification, action, diagnostic = _nonacquired_result(
            acquired.classification,
            acquired.diagnostic,
        )
        return GuardedCaptureReadinessRunResult(
            session_id,
            launch_id,
            classification,
            (diagnostic.value,),
            action,
        )
    ownership = acquired.ownership
    result = GuardedCaptureReadinessRunResult(
        session_id,
        launch_id,
        ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED,
        (GuardedCaptureReadinessDiagnostic.GUARD_ABANDONED.value,),
        NextEligibleAction.MANUAL_REVIEW,
        lease_start_record_id=ownership.start_record.record_id,
    )
    try:
        if (
            acquired.classification
            is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
        ):
            return _release_and_finalize(config, ownership, result)
        try:
            head_result = head_verifier(config.authority_root)
            if (
                head_result.classification is not LocalLineageHeadClassification.PASS
                or head_result.authority is None
                or head_result.authority.pointer.authority_epoch_id
                != config.authority_epoch_id
            ):
                raise ValueError("authoritative head did not verify")
            head = head_input_adapter(head_result.authority)
        except Exception:
            result = _failure_result(
                result,
                GuardedCaptureReadinessDiagnostic.HEAD_VERIFICATION_FAILED,
            )
            return _release_and_finalize(config, ownership, result)
        try:
            hours = _load_hours(config.market_hours_schedule_artifact)
        except Exception:
            result = _failure_result(
                result,
                GuardedCaptureReadinessDiagnostic.HOURS_ARTIFACT_INVALID,
            )
            return _release_and_finalize(config, ownership, result)
        try:
            policy = _load_policy(config.capture_policy_artifact)
            if policy.symbols != config.symbols:
                raise ValueError("capture policy symbol universe differs from config")
        except Exception:
            result = _failure_result(
                result,
                GuardedCaptureReadinessDiagnostic.CAPTURE_POLICY_INVALID,
            )
            return _release_and_finalize(config, ownership, result)
        try:
            attempts = tuple(
                _load_attempt(reference)
                for reference in config.capture_attempt_artifacts
            )
            selection = (
                None
                if config.snapshot_selection_artifact is None
                else _load_selection(config.snapshot_selection_artifact)
            )
        except Exception:
            result = _failure_result(
                result,
                GuardedCaptureReadinessDiagnostic.ATTEMPT_HISTORY_INVALID,
            )
            return _release_and_finalize(config, ownership, result)
        try:
            selected_snapshot = _selected_snapshot(selection, attempts)
            inputs = ScheduledReadinessInputs(
                authoritative_head=head,
                target_session=config.target_session,
                execution_session=config.execution_session,
                observed_at=config.observed_current_utc_timestamp,
                market_hours=hours,
                capture_policy=policy,
                capture_attempts=attempts,
                selected_snapshot=selected_snapshot,
                snapshot_selection=selection,
                cycle=None,
                scheduled_session_id=session_id,
                universe_policy_version=config.universe_policy_version,
                readiness_policy_version=config.readiness_policy_version,
                selection_policy_version=config.selection_policy_version,
                manual_disable_active=config.manual_disable_active,
                head_advancement_pending=False,
                health=ScheduledHealthInputs(
                    disk_watermark_ok=config.capture_health.disk_watermark_ok,
                    audit_ok=config.capture_health.audit_ok,
                    notification_ok=config.capture_health.notification_ok,
                    backup_ok=config.capture_health.backup_ok,
                    credential_isolation_ok=True,
                    operation_credentials_present=False,
                ),
                coordinator=None,
            )
            readiness = readiness_evaluator(inputs)
            action = _next_action(readiness.classification)
            proposed_ordinal: int | None = None
            proposed_id: UUID | None = None
            if readiness.classification is ScheduledReadinessClassification.READY:
                proposed_ordinal = len(attempts)
                proposed_id = proposed_capture_attempt_id(
                    session_id,
                    proposed_ordinal,
                    policy,
                )
            lease_reference = ownership.start_reference
            decision = create_scheduled_capture_readiness_decision(
                scheduled_session_id=session_id,
                scheduled_launch_id=launch_id,
                authority_epoch_id=config.authority_epoch_id,
                lease_start=ArtifactEvidence(
                    lease_reference.record_id,
                    lease_reference.sha256,
                    lease_reference.byte_length,
                ),
                head_record=head.head_record,
                terminal_checkpoint=head.terminal_checkpoint,
                market_hours_schedule=(config.market_hours_schedule_artifact.evidence),
                capture_policy=config.capture_policy_artifact.evidence,
                capture_attempts=tuple(
                    reference.evidence for reference in config.capture_attempt_artifacts
                ),
                snapshot_selection=(
                    None
                    if config.snapshot_selection_artifact is None
                    else config.snapshot_selection_artifact.evidence
                ),
                observed_at=config.observed_current_utc_timestamp,
                readiness_classification=readiness.classification,
                diagnostics=readiness.diagnostics,
                provider_invocation_permitted=(
                    readiness.classification is ScheduledReadinessClassification.READY
                ),
                next_eligible_action=action,
                capture_attempt_ordinal=proposed_ordinal,
                capture_attempt_id=proposed_id,
                runner_policy_version=config.runner_policy_version,
            )
        except Exception:
            result = _failure_result(
                result,
                GuardedCaptureReadinessDiagnostic.READINESS_EVALUATION_FAILED,
            )
            return _release_and_finalize(config, ownership, result)
        try:
            publication = decision_publisher(
                config.scheduler_audit_root,
                decision,
            )
        except Exception:
            result = replace(
                result,
                readiness_classification=readiness.classification,
                diagnostics=(
                    GuardedCaptureReadinessDiagnostic.DECISION_PUBLICATION_FAILED.value,
                    *(item.value for item in readiness.diagnostics),
                ),
                next_eligible_action=NextEligibleAction.NONE,
                proposed_capture_attempt_ordinal=None,
                proposed_capture_attempt_id=None,
                decision=decision,
            )
            return _release_and_finalize(config, ownership, result)
        result = replace(
            result,
            readiness_classification=readiness.classification,
            diagnostics=tuple(item.value for item in readiness.diagnostics),
            next_eligible_action=action,
            proposed_capture_attempt_ordinal=proposed_ordinal,
            proposed_capture_attempt_id=proposed_id,
            decision=decision,
            decision_publication=publication,
        )
        return _release_and_finalize(config, ownership, result)
    except BaseException:
        if not ownership.released:
            emergency = _failure_result(
                result,
                GuardedCaptureReadinessDiagnostic.READINESS_EVALUATION_FAILED,
            )
            _release_and_finalize(config, ownership, emergency)
        raise


def exit_code_for_guarded_capture_readiness(
    result: GuardedCaptureReadinessRunResult,
) -> int:
    diagnostics = set(result.diagnostics)
    if GuardedCaptureReadinessDiagnostic.GUARD_ALREADY_HELD.value in diagnostics:
        return 9
    if diagnostics & {
        GuardedCaptureReadinessDiagnostic.GUARD_ACCESS_DENIED.value,
        GuardedCaptureReadinessDiagnostic.GUARD_UNSUPPORTED.value,
    }:
        return 10
    if diagnostics & {
        GuardedCaptureReadinessDiagnostic.GUARD_ERROR.value,
        GuardedCaptureReadinessDiagnostic.LEASE_START_PUBLICATION_FAILED.value,
        GuardedCaptureReadinessDiagnostic.DECISION_PUBLICATION_FAILED.value,
        GuardedCaptureReadinessDiagnostic.LEASE_RELEASE_PUBLICATION_FAILED.value,
        GuardedCaptureReadinessDiagnostic.MUTEX_RELEASE_FAILED.value,
    }:
        return 7
    if result.readiness_classification is ScheduledReadinessClassification.CONFLICTING:
        return 5
    if (
        result.readiness_classification
        is ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED
    ):
        return 8
    if result.decision_publication is not None and result.readiness_classification in {
        ScheduledReadinessClassification.READY,
        ScheduledReadinessClassification.NOT_READY,
        ScheduledReadinessClassification.ALREADY_COMPLETED,
    }:
        return 0
    return 4


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one guarded capture-readiness dry run without invoking "
            "a provider or creating a snapshot."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = load_guarded_capture_readiness_config(args.config)
    except (OSError, ValueError, GuardedCaptureReadinessConfigError):
        print(
            json.dumps(
                {
                    "diagnostics": [
                        GuardedCaptureReadinessDiagnostic.CONFIGURATION_INVALID.value
                    ],
                    "next_eligible_action": NextEligibleAction.NONE.value,
                    "readiness_classification": (
                        ScheduledReadinessClassification.BLOCKED.value
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 4
    result = run_guarded_capture_readiness(config)
    print(
        json.dumps(
            _output_tree(result),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return exit_code_for_guarded_capture_readiness(result)


def _load_hours(reference: ExplicitArtifactReference):
    payload = _verified_payload(reference, "market-hours schedule")
    return parse_market_session_hours_schedule(payload)


def _load_policy(reference: ExplicitArtifactReference):
    payload = _verified_payload(reference, "capture policy")
    return parse_capture_policy_artifact(payload)


def _load_attempt(
    reference: ExplicitArtifactReference,
) -> ScheduledCaptureAttemptRecord:
    payload = _verified_payload(reference, "capture-attempt record")
    record = parse_scheduled_capture_attempt_record(payload)
    if record.attempt_id != reference.evidence.artifact_id:
        raise ValueError("capture-attempt artifact ID does not reconcile")
    if capture_attempt_record_evidence(record) != reference.evidence:
        raise ValueError("capture-attempt artifact evidence does not reconcile")
    return record


def _load_selection(
    reference: ExplicitArtifactReference,
) -> ScheduledSnapshotSelectionRecord:
    payload = _verified_payload(reference, "snapshot-selection record")
    record = parse_scheduled_snapshot_selection_record(payload)
    if record.selection_id != reference.evidence.artifact_id:
        raise ValueError("snapshot-selection artifact ID does not reconcile")
    if snapshot_selection_record_evidence(record) != reference.evidence:
        raise ValueError("snapshot-selection artifact evidence does not reconcile")
    return record


def _verified_payload(reference: ExplicitArtifactReference, label: str) -> bytes:
    payload = read_safe_regular_file(
        reference.path,
        MAX_GUARDED_CAPTURE_READINESS_ARTIFACT_BYTES,
        label,
    )
    if (
        len(payload) != reference.evidence.byte_length
        or hashlib.sha256(payload).hexdigest() != reference.evidence.sha256
    ):
        raise ValueError(f"{label} evidence does not match its bytes")
    return payload


def _selected_snapshot(
    selection: ScheduledSnapshotSelectionRecord | None,
    attempts: tuple[ScheduledCaptureAttemptRecord, ...],
) -> SnapshotEvidence | None:
    if selection is None:
        return None
    selected = next(
        (
            attempt
            for attempt in attempts
            if attempt.attempt_id == selection.selected_attempt_id
        ),
        None,
    )
    return None if selected is None else selected.snapshot


def _release_and_finalize(
    config: GuardedCaptureReadinessConfig,
    ownership,
    result: GuardedCaptureReadinessRunResult,
) -> GuardedCaptureReadinessRunResult:
    result_classification = (
        LaunchResultClassification.SUCCESS
        if result.decision_publication is not None
        else (
            LaunchResultClassification.NOT_RUN
            if GuardedCaptureReadinessDiagnostic.GUARD_ABANDONED.value
            in result.diagnostics
            else LaunchResultClassification.FAILURE
        )
    )
    diagnostic = (
        result.readiness_classification.value
        if not result.diagnostics or result.decision_publication is not None
        else result.diagnostics[0]
    )
    release_input = LaunchLeaseReleaseInput(
        release_classification=LaunchLeaseReleaseClassification.NORMAL,
        release_timestamp_utc=config.release_timestamp_utc,
        monotonic_duration_nanoseconds=config.monotonic_duration_nanoseconds,
        result_classification=result_classification,
        result_diagnostic=diagnostic,
        process_exit_code=None,
        release_policy=config.launch_guard_policy_version,
    )
    try:
        released: LaunchGuardReleaseResult = ownership.release(release_input)
    except Exception:
        return _append_release_failure(
            result,
            evidence_failed=True,
            native_failed=True,
            release_id=None,
        )
    evidence_failed = released.classification in {
        ReleaseOperationalClassification.EVIDENCE_PUBLICATION_FAILED,
        ReleaseOperationalClassification.EVIDENCE_AND_NATIVE_RELEASE_FAILED,
    }
    native_failed = released.classification in {
        ReleaseOperationalClassification.NATIVE_RELEASE_FAILED,
        ReleaseOperationalClassification.EVIDENCE_AND_NATIVE_RELEASE_FAILED,
    }
    return _append_release_failure(
        result,
        evidence_failed=evidence_failed,
        native_failed=native_failed,
        release_id=(
            None if released.publication is None else released.release_record.release_id
        ),
    )


def _append_release_failure(
    result: GuardedCaptureReadinessRunResult,
    *,
    evidence_failed: bool,
    native_failed: bool,
    release_id: UUID | None,
) -> GuardedCaptureReadinessRunResult:
    diagnostics = list(result.diagnostics)
    if evidence_failed:
        diagnostics.append(
            GuardedCaptureReadinessDiagnostic.LEASE_RELEASE_PUBLICATION_FAILED.value
        )
    if native_failed:
        diagnostics.append(GuardedCaptureReadinessDiagnostic.MUTEX_RELEASE_FAILED.value)
    if evidence_failed or native_failed:
        return replace(
            result,
            readiness_classification=(
                ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED
            ),
            diagnostics=tuple(dict.fromkeys(diagnostics)),
            next_eligible_action=NextEligibleAction.MANUAL_REVIEW,
            lease_release_record_id=release_id,
        )
    return replace(result, lease_release_record_id=release_id)


def _failure_result(
    result: GuardedCaptureReadinessRunResult,
    diagnostic: GuardedCaptureReadinessDiagnostic,
) -> GuardedCaptureReadinessRunResult:
    return replace(
        result,
        readiness_classification=ScheduledReadinessClassification.BLOCKED,
        diagnostics=(diagnostic.value,),
        next_eligible_action=NextEligibleAction.NONE,
    )


def _nonacquired_result(
    classification: LaunchGuardAcquisitionClassification,
    guard_diagnostic: str,
) -> tuple[
    ScheduledReadinessClassification,
    NextEligibleAction,
    GuardedCaptureReadinessDiagnostic,
]:
    if classification is LaunchGuardAcquisitionClassification.ALREADY_HELD:
        return (
            ScheduledReadinessClassification.NOT_READY,
            NextEligibleAction.WAIT,
            GuardedCaptureReadinessDiagnostic.GUARD_ALREADY_HELD,
        )
    if classification is LaunchGuardAcquisitionClassification.ACCESS_DENIED:
        diagnostic = GuardedCaptureReadinessDiagnostic.GUARD_ACCESS_DENIED
    elif classification is LaunchGuardAcquisitionClassification.UNSUPPORTED:
        diagnostic = GuardedCaptureReadinessDiagnostic.GUARD_UNSUPPORTED
    elif "START_PUBLICATION_FAILED" in guard_diagnostic:
        diagnostic = GuardedCaptureReadinessDiagnostic.LEASE_START_PUBLICATION_FAILED
    else:
        diagnostic = GuardedCaptureReadinessDiagnostic.GUARD_ERROR
    return (
        ScheduledReadinessClassification.BLOCKED,
        NextEligibleAction.NONE,
        diagnostic,
    )


def _next_action(
    classification: ScheduledReadinessClassification,
) -> NextEligibleAction:
    if classification is ScheduledReadinessClassification.READY:
        return NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED
    if classification is ScheduledReadinessClassification.NOT_READY:
        return NextEligibleAction.WAIT
    if classification is ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED:
        return NextEligibleAction.MANUAL_REVIEW
    return NextEligibleAction.NONE


def _output_tree(result: GuardedCaptureReadinessRunResult) -> dict[str, object]:
    output: dict[str, object] = {
        "scheduled_session_id": str(result.scheduled_session_id),
        "scheduled_launch_id": str(result.scheduled_launch_id),
        "readiness_classification": result.readiness_classification.value,
        "diagnostics": list(result.diagnostics),
        "next_eligible_action": result.next_eligible_action.value,
    }
    if result.lease_start_record_id is not None:
        output["lease_start_record_id"] = str(result.lease_start_record_id)
    if result.proposed_capture_attempt_ordinal is not None:
        output["proposed_capture_attempt_ordinal"] = (
            result.proposed_capture_attempt_ordinal
        )
        output["proposed_capture_attempt_id"] = str(result.proposed_capture_attempt_id)
    if result.decision_publication is not None and result.decision is not None:
        output["decision_record_id"] = str(result.decision.decision_id)
        output["decision_path"] = str(result.decision_publication.path)
    if result.lease_release_record_id is not None:
        output["lease_release_record_id"] = str(result.lease_release_record_id)
    return output
