"""Manual, one-shot guarded capture-only orchestration."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.cli.checkpoint_lineage_config import read_safe_regular_file
from trading_bot.cli.daily_snapshot_config import load_daily_snapshot_capture_config
from trading_bot.cli.guarded_capture_readiness_config import ExplicitArtifactReference
from trading_bot.cli.guarded_capture_readiness_output import (
    DecisionEvidencePublicationResult,
    publish_scheduled_capture_readiness_decision,
)
from trading_bot.cli.guarded_capture_runner_config import (
    GuardedCaptureRunnerConfig,
    GuardedCaptureRunnerConfigError,
    ProductionXnysHoursAuthorityStatus,
    load_guarded_capture_runner_config,
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
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    BoundMarketCalendar,
    verify_daily_snapshot,
)
from trading_bot.market_data.alpaca_daily_snapshot import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
)
from trading_bot.runtime import (
    ArtifactEvidence,
    AttemptHistoryState,
    CaptureAllocationClassification,
    CaptureAttemptHistoryFacts,
    CaptureAttemptTerminalClassification,
    IsolatedCaptureChildClassification,
    IsolatedCaptureChildRequest,
    IsolatedCaptureLauncherConfig,
    LaunchGuardAcquisitionClassification,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
    NextEligibleAction,
    ProviderCallDisposition,
    ScheduledCaptureAttemptRecord,
    ScheduledCaptureReadinessDecision,
    ScheduledHealthInputs,
    ScheduledReadinessClassification,
    ScheduledReadinessInputs,
    ScheduledReadinessResult,
    SecretCleanupResult,
    SnapshotEvidence,
    SnapshotTerminalVerification,
    allocate_capture_attempt,
    capture_attempt_allocation_path,
    create_capture_attempt_allocation,
    create_capture_attempt_terminal,
    create_isolated_capture_child_request,
    derive_scheduled_capture_attempt_id,
    evaluate_scheduled_capture_readiness,
    launch_isolated_capture_child,
    load_capture_attempt_history_facts,
    parse_capture_policy_artifact,
    parse_market_session_hours_schedule,
    publish_capture_attempt_terminal,
    select_capture_attempt_terminal,
    serialize_capture_attempt_allocation,
)
from trading_bot.runtime.capture_attempt_authority import (
    parse_windows_market_data_credential_reference,
)
from trading_bot.runtime.guarded_capture_readiness import (
    create_scheduled_capture_readiness_decision,
)
from trading_bot.runtime.isolated_capture_artifacts import (
    evidence_for_payload,
    parse_isolated_capture_child_request,
    parse_isolated_capture_child_result,
    publish_canonical_artifact,
    serialize_child_process_creation_record,
    serialize_child_resume_authorization_record,
    serialize_child_termination_record,
    serialize_isolated_capture_child_request,
)
from trading_bot.runtime.scheduled_readiness import (
    CaptureAttemptStatus,
    SnapshotChronologyResult,
    capture_attempt_record_evidence,
    create_scheduled_snapshot_selection_record,
)


class GuardedCaptureRunnerClassification(StrEnum):
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class GuardedCaptureRunnerDiagnostic(StrEnum):
    CONFIGURATION_INVALID = "CONFIGURATION_INVALID"
    GUARD_ALREADY_HELD = "GUARD_ALREADY_HELD"
    GUARD_ABANDONED = "GUARD_ABANDONED"
    GUARD_ACCESS_DENIED = "GUARD_ACCESS_DENIED"
    GUARD_UNSUPPORTED = "GUARD_UNSUPPORTED"
    GUARD_ERROR = "GUARD_ERROR"
    HEAD_VERIFICATION_FAILED = "HEAD_VERIFICATION_FAILED"
    PRODUCTION_XNYS_HOURS_AUTHORITY_UNRESOLVED = (
        "PRODUCTION_XNYS_HOURS_AUTHORITY_UNRESOLVED"
    )
    PRODUCTION_XNYS_HOURS_AUTHORITY_INVALID = "PRODUCTION_XNYS_HOURS_AUTHORITY_INVALID"
    HOURS_ARTIFACT_INVALID = "HOURS_ARTIFACT_INVALID"
    CAPTURE_POLICY_INVALID = "CAPTURE_POLICY_INVALID"
    CREDENTIAL_REFERENCE_INVALID = "CREDENTIAL_REFERENCE_INVALID"
    CAPTURE_CONFIGURATION_INVALID = "CAPTURE_CONFIGURATION_INVALID"
    ATTEMPT_HISTORY_INVALID = "ATTEMPT_HISTORY_INVALID"
    ATTEMPT_HISTORY_AMBIGUOUS = "ATTEMPT_HISTORY_AMBIGUOUS"
    ATTEMPT_HISTORY_ALREADY_COMPLETED = "ATTEMPT_HISTORY_ALREADY_COMPLETED"
    READINESS_NOT_READY = "READINESS_NOT_READY"
    READINESS_BLOCKED = "READINESS_BLOCKED"
    READINESS_CONFLICTING = "READINESS_CONFLICTING"
    DECISION_PUBLICATION_FAILED = "DECISION_PUBLICATION_FAILED"
    ATTEMPT_ALLOCATION_FAILED = "ATTEMPT_ALLOCATION_FAILED"
    CHILD_REQUEST_PUBLICATION_FAILED = "CHILD_REQUEST_PUBLICATION_FAILED"
    CHILD_LAUNCH_FAILED = "CHILD_LAUNCH_FAILED"
    CHILD_RESULT_INVALID = "CHILD_RESULT_INVALID"
    SNAPSHOT_VERIFICATION_FAILED = "SNAPSHOT_VERIFICATION_FAILED"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    TERMINAL_PUBLICATION_FAILED = "TERMINAL_PUBLICATION_FAILED"
    SNAPSHOT_SELECTION_FAILED = "SNAPSHOT_SELECTION_FAILED"
    READINESS_REEVALUATION_FAILED = "READINESS_REEVALUATION_FAILED"
    LEASE_RELEASE_PUBLICATION_FAILED = "LEASE_RELEASE_PUBLICATION_FAILED"
    MUTEX_RELEASE_FAILED = "MUTEX_RELEASE_FAILED"


@dataclass(frozen=True, slots=True)
class GuardedCaptureRunnerResult:
    scheduled_session_id: UUID
    scheduled_launch_id: UUID
    classification: GuardedCaptureRunnerClassification
    diagnostics: tuple[str, ...]
    readiness_classification: ScheduledReadinessClassification | None = None
    readiness_diagnostics: tuple[str, ...] = ()
    allocation_record_id: UUID | None = None
    attempt_id: UUID | None = None
    attempt_ordinal: int | None = None
    child_result_id: UUID | None = None
    terminal_record_id: UUID | None = None
    selection_record_id: UUID | None = None
    post_capture_readiness_classification: ScheduledReadinessClassification | None = (
        None
    )
    lease_start_record_id: UUID | None = None
    lease_release_record_id: UUID | None = None
    default_mutex_dacl_unhardened: bool = True


@dataclass(frozen=True, slots=True)
class _LoadedInputs:
    head: Any
    hours: Any
    policy: Any
    credential_reference: Any
    capture_configuration: Any
    history: CaptureAttemptHistoryFacts
    attempts: tuple[ScheduledCaptureAttemptRecord, ...]


def run_guarded_capture_runner(
    config: GuardedCaptureRunnerConfig,
    *,
    native_api: WindowsMutexApi | None = None,
    head_verifier: Callable[[Path], LocalLineageHeadResult] = verify_local_lineage_head,
    readiness_evaluator: Callable[
        [ScheduledReadinessInputs], ScheduledReadinessResult
    ] = evaluate_scheduled_capture_readiness,
    decision_publisher: Callable[
        [Path, ScheduledCaptureReadinessDecision], DecisionEvidencePublicationResult
    ] = publish_scheduled_capture_readiness_decision,
    history_loader: Callable[
        [Path, UUID], CaptureAttemptHistoryFacts
    ] = load_capture_attempt_history_facts,
    allocator: Callable[..., Any] = allocate_capture_attempt,
    child_request_publisher: Callable[
        [Path, bytes, object], Path
    ] = publish_canonical_artifact,
    child_launcher: Callable[..., Any] = launch_isolated_capture_child,
    terminal_publisher: Callable[..., Any] = publish_capture_attempt_terminal,
    selector: Callable[..., Any] = select_capture_attempt_terminal,
) -> GuardedCaptureRunnerResult:
    """Run one guarded capture attempt, or publish no provider-call fact."""
    if type(config) is not GuardedCaptureRunnerConfig:
        raise TypeError("config must be GuardedCaptureRunnerConfig")
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
        return _nonacquired_result(config, acquired.classification)
    ownership = acquired.ownership
    base = GuardedCaptureRunnerResult(
        session_id,
        launch_id,
        GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
        (GuardedCaptureRunnerDiagnostic.GUARD_ABANDONED.value,),
        lease_start_record_id=ownership.start_record.record_id,
        default_mutex_dacl_unhardened=True,
    )
    try:
        if (
            acquired.classification
            is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
        ):
            return _release(config, ownership, base, LaunchResultClassification.NOT_RUN)
        try:
            _validate_runtime_directories(config)
            head_result = head_verifier(config.authority_root)
            if (
                head_result.classification is not LocalLineageHeadClassification.PASS
                or head_result.authority is None
                or head_result.authority.pointer.authority_epoch_id
                != config.authority_epoch_id
            ):
                raise ValueError("head did not verify")
            head = scheduled_head_input_from_verified_authority(head_result.authority)
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.BLOCKED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.HEAD_VERIFICATION_FAILED.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        try:
            hours = _load_hours(config)
        except _HoursAuthorityUnresolved:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.BLOCKED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.PRODUCTION_XNYS_HOURS_AUTHORITY_UNRESOLVED.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.BLOCKED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.HOURS_ARTIFACT_INVALID.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        try:
            policy = _load_policy(config)
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.BLOCKED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.CAPTURE_POLICY_INVALID.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        try:
            credential_payload = _verified_payload(
                config.credential_reference_artifact, "credential reference"
            )
            _parse_credential(credential_payload, config)
            capture_configuration = load_daily_snapshot_capture_config(
                config.capture_configuration_artifact.path
            )
            if (
                capture_configuration.request_id != config.snapshot_capture_request_id
                or capture_configuration.symbols != config.symbols
                or policy.configuration_evidence
                != config.capture_configuration_artifact.evidence
            ):
                raise ValueError("capture configuration does not reconcile")
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.BLOCKED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.CREDENTIAL_REFERENCE_INVALID.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        try:
            history = history_loader(config.capture_attempt_root, session_id)
            attempts = _readiness_attempts(config, policy, history)
            if (
                history.verification.head is None
                or history.verification.pointer is None
            ):
                raise ValueError("history head is missing")
            state = history.verification.head.state
            if state is AttemptHistoryState.SUCCESS_SELECTED:
                return _release(
                    config,
                    ownership,
                    replace(
                        base,
                        classification=GuardedCaptureRunnerClassification.SUCCEEDED,
                        diagnostics=(
                            GuardedCaptureRunnerDiagnostic.ATTEMPT_HISTORY_ALREADY_COMPLETED.value,
                        ),
                        readiness_classification=ScheduledReadinessClassification.ALREADY_COMPLETED,
                    ),
                    LaunchResultClassification.SUCCESS,
                )
            if state in {
                AttemptHistoryState.ALLOCATED_NOT_LAUNCHED,
                AttemptHistoryState.LAUNCH_MAY_HAVE_OCCURRED,
                AttemptHistoryState.RECOVERY_REQUIRED,
            }:
                return _release(
                    config,
                    ownership,
                    replace(
                        base,
                        classification=GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
                        diagnostics=(
                            GuardedCaptureRunnerDiagnostic.ATTEMPT_HISTORY_AMBIGUOUS.value,
                        ),
                    ),
                    LaunchResultClassification.FAILURE,
                )
            if state is AttemptHistoryState.SESSION_CLOSED:
                return _release(
                    config,
                    ownership,
                    replace(
                        base,
                        classification=GuardedCaptureRunnerClassification.BLOCKED,
                        diagnostics=(
                            GuardedCaptureRunnerDiagnostic.READINESS_BLOCKED.value,
                        ),
                    ),
                    LaunchResultClassification.FAILURE,
                )
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.BLOCKED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.ATTEMPT_HISTORY_INVALID.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        inputs = ScheduledReadinessInputs(
            authoritative_head=head,
            target_session=config.target_session,
            execution_session=config.execution_session,
            observed_at=config.observed_current_utc_timestamp,
            market_hours=hours,
            capture_policy=policy,
            capture_attempts=attempts,
            selected_snapshot=None,
            snapshot_selection=None,
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
        try:
            readiness = readiness_evaluator(inputs)
            proposed_ordinal = None
            proposed_id = None
            if readiness.classification is ScheduledReadinessClassification.READY:
                proposed_ordinal = history.verification.head.next_attempt_ordinal  # type: ignore[union-attr]
                proposed_id = derive_scheduled_capture_attempt_id(
                    session_id,
                    proposed_ordinal,
                    policy.symbols,
                    policy.timeframe,
                    policy.adjustment,
                    policy.provider,
                    policy.feed,
                    policy.currency,
                    policy.policy_version,
                    policy.configuration_evidence,
                )
            decision = create_scheduled_capture_readiness_decision(
                scheduled_session_id=session_id,
                scheduled_launch_id=launch_id,
                authority_epoch_id=config.authority_epoch_id,
                lease_start=_lease_start_evidence(ownership),
                head_record=head.head_record,
                terminal_checkpoint=head.terminal_checkpoint,
                market_hours_schedule=config.market_hours_schedule_artifact.evidence,
                capture_policy=config.capture_policy_artifact.evidence,
                capture_attempts=tuple(
                    capture_attempt_record_evidence(item) for item in attempts
                ),
                snapshot_selection=None,
                observed_at=config.observed_current_utc_timestamp,
                readiness_classification=readiness.classification,
                diagnostics=readiness.diagnostics,
                provider_invocation_permitted=readiness.classification
                is ScheduledReadinessClassification.READY,
                next_eligible_action=_next_action(readiness.classification),
                capture_attempt_ordinal=proposed_ordinal,
                capture_attempt_id=proposed_id,
                runner_policy_version=config.runner_policy_version,
            )
            publication = decision_publisher(config.scheduler_audit_root, decision)
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.FAILED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.DECISION_PUBLICATION_FAILED.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        result = replace(
            base,
            readiness_classification=readiness.classification,
            readiness_diagnostics=tuple(item.value for item in readiness.diagnostics),
            attempt_ordinal=proposed_ordinal,
            attempt_id=proposed_id,
        )
        if readiness.classification is ScheduledReadinessClassification.NOT_READY:
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.NOT_READY,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.READINESS_NOT_READY.value,
                    ),
                ),
                LaunchResultClassification.SUCCESS,
            )
        if (
            readiness.classification
            is ScheduledReadinessClassification.ALREADY_COMPLETED
        ):
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.SUCCEEDED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.ATTEMPT_HISTORY_ALREADY_COMPLETED.value,
                    ),
                ),
                LaunchResultClassification.SUCCESS,
            )
        if readiness.classification is not ScheduledReadinessClassification.READY:
            diagnostic = (
                GuardedCaptureRunnerDiagnostic.READINESS_CONFLICTING
                if readiness.classification
                is ScheduledReadinessClassification.CONFLICTING
                else GuardedCaptureRunnerDiagnostic.READINESS_BLOCKED
            )
            classification = (
                GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED
                if readiness.classification
                is ScheduledReadinessClassification.CONFLICTING
                else GuardedCaptureRunnerClassification.BLOCKED
            )
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=classification,
                    diagnostics=(diagnostic.value,),
                ),
                LaunchResultClassification.FAILURE,
            )
        allocation = _make_allocation(
            config, head, history, policy, publication, proposed_id, proposed_ordinal
        )
        try:
            allocator(config.capture_attempt_root, allocation, decision)
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.FAILED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.ATTEMPT_ALLOCATION_FAILED.value,
                    ),
                    allocation_record_id=allocation.allocation_record_id,
                ),
                LaunchResultClassification.FAILURE,
            )
        allocation_payload = serialize_capture_attempt_allocation(allocation)
        allocation_evidence = evidence_for_payload(
            allocation.allocation_record_id, allocation_payload
        )
        try:
            request, request_payload, request_path = _make_child_request(
                config, allocation, allocation_evidence
            )
            child_request_publisher(
                request_path, request_payload, parse_isolated_capture_child_request
            )
            launcher_config = IsolatedCaptureLauncherConfig(
                schema_version=1,
                child_request=evidence_for_payload(
                    request.child_request_id, request_payload
                ),
                child_request_path=request_path,
                approved_python_executable=config.approved_python_executable,
                approved_python_executable_evidence=config.approved_python_executable_evidence,
                approved_child_script=config.approved_child_script,
                approved_child_script_evidence=config.approved_child_script_evidence,
                process_evidence_directory=config.process_evidence_directory,
                controlled_temp_directory=config.controlled_temp_directory,
                environment_policy_version="isolated-python-environment-v1",
                termination_grace_seconds=config.termination_grace_seconds,
            )
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.FAILED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.CHILD_REQUEST_PUBLICATION_FAILED.value,
                    ),
                    allocation_record_id=allocation.allocation_record_id,
                    attempt_id=allocation.attempt_id,
                    attempt_ordinal=allocation.attempt_ordinal,
                ),
                LaunchResultClassification.FAILURE,
            )
        execution = None
        try:
            execution = child_launcher(launcher_config)
        except Exception:
            return _publish_failed_terminal_after_launch_error(
                config,
                ownership,
                result,
                allocation,
                allocation_evidence,
                None,
                None,
                None,
                None,
                None,
                GuardedCaptureRunnerDiagnostic.CHILD_LAUNCH_FAILED,
                terminal_publisher,
            )
        try:
            terminal, child_result_id, snapshot_evidence = _terminal_from_execution(
                config, allocation, allocation_evidence, request, execution
            )
        except _AmbiguousChildResult as error:
            terminal = _ambiguous_terminal(
                config,
                allocation,
                allocation_evidence,
                request,
                execution,
                error.diagnostic,
            )
            child_result_id = error.child_result_id
            snapshot_evidence = None
        except Exception:
            terminal = _ambiguous_terminal(
                config,
                allocation,
                allocation_evidence,
                request,
                execution,
                GuardedCaptureRunnerDiagnostic.CHILD_RESULT_INVALID.value,
            )
            child_result_id = None
            snapshot_evidence = None
        try:
            terminal_publisher(config.capture_attempt_root, terminal)
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.FAILED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.TERMINAL_PUBLICATION_FAILED.value,
                    ),
                    allocation_record_id=allocation.allocation_record_id,
                    attempt_id=allocation.attempt_id,
                    attempt_ordinal=allocation.attempt_ordinal,
                    child_result_id=child_result_id,
                    terminal_record_id=terminal.terminal_record_id,
                ),
                LaunchResultClassification.FAILURE,
            )
        result = replace(
            result,
            allocation_record_id=allocation.allocation_record_id,
            attempt_id=allocation.attempt_id,
            attempt_ordinal=allocation.attempt_ordinal,
            child_result_id=child_result_id,
            terminal_record_id=terminal.terminal_record_id,
        )
        if (
            terminal.classification
            is not CaptureAttemptTerminalClassification.SUCCEEDED
        ):
            ambiguous = terminal.classification in {
                CaptureAttemptTerminalClassification.TIMEOUT,
                CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH,
                CaptureAttemptTerminalClassification.CHILD_CRASHED,
            } or terminal.provider_call_disposition in {
                ProviderCallDisposition.MAY_HAVE_STARTED,
                ProviderCallDisposition.UNKNOWN,
            }
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.AMBIGUOUS
                    if ambiguous
                    else GuardedCaptureRunnerClassification.FAILED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.CAPTURE_AMBIGUOUS.value
                        if ambiguous
                        else GuardedCaptureRunnerDiagnostic.PROVIDER_FAILED.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        try:
            selection = selector(
                config.capture_attempt_root, session_id, config.selection_policy_version
            )
            post_attempts = attempts + (
                _scheduled_attempt_from_success(
                    allocation, terminal, snapshot_evidence
                ),
            )
            post_selection = create_scheduled_snapshot_selection_record(
                session_id,
                head.head_record,
                head.terminal_checkpoint,
                tuple(capture_attempt_record_evidence(item) for item in post_attempts),
                allocation.attempt_id,
                snapshot_evidence,
                config.selection_policy_version,
                _chronology_pass(),
            )
            post_inputs = replace(
                inputs,
                capture_attempts=post_attempts,
                selected_snapshot=snapshot_evidence,
                snapshot_selection=post_selection,
            )
            post_readiness = readiness_evaluator(post_inputs)
            if (
                post_readiness.classification
                is not ScheduledReadinessClassification.ALREADY_COMPLETED
            ):
                raise ValueError("successful capture did not reach ALREADY_COMPLETED")
        except Exception:
            return _release(
                config,
                ownership,
                replace(
                    result,
                    classification=GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
                    diagnostics=(
                        GuardedCaptureRunnerDiagnostic.SNAPSHOT_SELECTION_FAILED.value,
                    ),
                ),
                LaunchResultClassification.FAILURE,
            )
        return _release(
            config,
            ownership,
            replace(
                result,
                classification=GuardedCaptureRunnerClassification.SUCCEEDED,
                selection_record_id=selection.selection_record_id,
                post_capture_readiness_classification=post_readiness.classification,
            ),
            LaunchResultClassification.SUCCESS,
            process_exit_code=getattr(execution, "native_exit_code", 0),
        )
    except BaseException:
        if not ownership.released:
            _release(
                config,
                ownership,
                replace(
                    base,
                    classification=GuardedCaptureRunnerClassification.FAILED,
                    diagnostics=(GuardedCaptureRunnerDiagnostic.GUARD_ERROR.value,),
                ),
                LaunchResultClassification.FAILURE,
            )
        raise


def _nonacquired_result(
    config: GuardedCaptureRunnerConfig,
    classification: LaunchGuardAcquisitionClassification,
) -> GuardedCaptureRunnerResult:
    if classification is LaunchGuardAcquisitionClassification.ALREADY_HELD:
        result_classification = GuardedCaptureRunnerClassification.NOT_READY
        diagnostic = GuardedCaptureRunnerDiagnostic.GUARD_ALREADY_HELD
    elif classification is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED:
        result_classification = (
            GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED
        )
        diagnostic = GuardedCaptureRunnerDiagnostic.GUARD_ABANDONED
    elif classification is LaunchGuardAcquisitionClassification.ACCESS_DENIED:
        result_classification = GuardedCaptureRunnerClassification.BLOCKED
        diagnostic = GuardedCaptureRunnerDiagnostic.GUARD_ACCESS_DENIED
    elif classification is LaunchGuardAcquisitionClassification.UNSUPPORTED:
        result_classification = GuardedCaptureRunnerClassification.BLOCKED
        diagnostic = GuardedCaptureRunnerDiagnostic.GUARD_UNSUPPORTED
    else:
        result_classification = GuardedCaptureRunnerClassification.FAILED
        diagnostic = GuardedCaptureRunnerDiagnostic.GUARD_ERROR
    return GuardedCaptureRunnerResult(
        config.scheduled_session_id,
        config.scheduled_launch_id,
        result_classification,
        (diagnostic.value,),
        default_mutex_dacl_unhardened=True,
    )


class _HoursAuthorityUnresolved(Exception):
    pass


class _AmbiguousChildResult(Exception):
    def __init__(self, diagnostic: str, child_result_id: UUID | None = None) -> None:
        super().__init__()
        self.diagnostic = diagnostic
        self.child_result_id = child_result_id


def _validate_runtime_directories(config: GuardedCaptureRunnerConfig) -> None:
    for path in (
        config.process_evidence_directory,
        config.controlled_temp_directory,
        config.snapshot_destination.path,
    ):
        if not path.is_dir():
            raise ValueError("runner directory is unavailable")


def _verified_payload(reference: ExplicitArtifactReference, label: str) -> bytes:
    payload = read_safe_regular_file(reference.path, 512 * 1024, label)
    if (
        len(payload) != reference.evidence.byte_length
        or hashlib.sha256(payload).hexdigest() != reference.evidence.sha256
    ):
        raise ValueError(f"{label} evidence mismatch")
    return payload


def _load_hours(config: GuardedCaptureRunnerConfig):
    authority = config.production_xnys_hours_authority
    if authority.status is ProductionXnysHoursAuthorityStatus.UNRESOLVED:
        raise _HoursAuthorityUnresolved
    payload = _verified_payload(
        config.market_hours_schedule_artifact, "market-hours schedule"
    )
    schedule = parse_market_session_hours_schedule(payload)
    if schedule.authority_evidence != authority.schedule_evidence:
        raise ValueError("production hours evidence does not match schedule")
    return schedule


def _load_policy(config: GuardedCaptureRunnerConfig):
    policy = parse_capture_policy_artifact(
        _verified_payload(config.capture_policy_artifact, "capture policy")
    )
    if (
        policy.symbols != config.symbols
        or policy.provider != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
        or policy.feed != "SIP"
        or policy.currency != "USD"
    ):
        raise ValueError("capture policy does not bind fixed child contract")
    return policy


def _parse_credential(payload: bytes, config: GuardedCaptureRunnerConfig):
    credential = parse_windows_market_data_credential_reference(payload)
    if (
        credential.credential_reference_id
        != config.credential_reference_artifact.evidence.artifact_id
        or credential.credential_version != config.credential_reference_version
    ):
        raise ValueError("credential reference identity mismatch")
    return credential


def _readiness_attempts(
    config: GuardedCaptureRunnerConfig, policy: Any, history: CaptureAttemptHistoryFacts
) -> tuple[ScheduledCaptureAttemptRecord, ...]:
    terminals_by_attempt = {item.attempt_id: item for item in history.terminals}
    records: list[ScheduledCaptureAttemptRecord] = []
    for allocation in history.allocations:
        terminal = terminals_by_attempt.get(allocation.attempt_id)
        if terminal is None:
            continue
        snapshot = None
        status = CaptureAttemptStatus.FAILED
        if (
            terminal.classification is CaptureAttemptTerminalClassification.SUCCEEDED
            and terminal.snapshot is not None
        ):
            snapshot = _snapshot_evidence(
                config, allocation, terminal.snapshot, policy.currency
            )
            status = CaptureAttemptStatus.PASS
        records.append(
            ScheduledCaptureAttemptRecord(
                1,
                allocation.attempt_id,
                allocation.scheduled_session_id,
                allocation.attempt_ordinal,
                allocation.symbols,
                allocation.timeframe,
                allocation.adjustment,
                allocation.provider,
                allocation.feed,
                allocation.currency,
                allocation.capture_policy_version,
                allocation.capture_configuration,
                allocation.request_timestamp_utc,
                terminal.completed_at,
                status,
                snapshot,
                terminal.classification.value,
            )
        )
    return tuple(records)


def _snapshot_evidence(
    config: GuardedCaptureRunnerConfig,
    allocation: Any,
    evidence: ArtifactEvidence,
    currency: str,
) -> SnapshotEvidence:
    path = (
        config.snapshot_destination.path
        / f"daily-market-data-snapshot-{evidence.artifact_id}.json"
    )
    payload = _verified_payload(ExplicitArtifactReference(evidence, path), "snapshot")
    verification = verify_daily_snapshot(
        payload,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
        expected_sha256=evidence.sha256,
        expected_byte_length=evidence.byte_length,
    )
    if not verification.passed or verification.snapshot is None:
        raise ValueError("snapshot verification failed")
    snapshot = verification.snapshot
    return SnapshotEvidence(
        evidence,
        snapshot.target_session,
        snapshot.audit.captured_at,
        snapshot.request.symbols,
        snapshot.provider,
        snapshot.request.timeframe,
        snapshot.request.adjustment,
        snapshot.provider.feed,
        currency,
        True,
        True,
    )


def _make_allocation(
    config: GuardedCaptureRunnerConfig,
    head: Any,
    history: CaptureAttemptHistoryFacts,
    policy: Any,
    publication: DecisionEvidencePublicationResult,
    attempt_id: UUID | None,
    attempt_ordinal: int | None,
):
    if (
        attempt_id is None
        or attempt_ordinal is None
        or history.verification.pointer is None
    ):
        raise ValueError("READY decision has no attempt allocation")
    return create_capture_attempt_allocation(
        attempt_id=attempt_id,
        attempt_ordinal=attempt_ordinal,
        scheduled_session_id=config.scheduled_session_id,
        scheduled_launch_id=config.scheduled_launch_id,
        authority_epoch_id=config.authority_epoch_id,
        head_record=head.head_record,
        verified_lineage_evidence_id=head.verified_lineage_evidence_id,
        terminal_checkpoint=head.terminal_checkpoint,
        terminal_as_of=head.terminal_checkpoint.as_of,
        readiness_decision=publication.artifact_reference,
        market_hours_schedule=config.market_hours_schedule_artifact.evidence,
        capture_policy=config.capture_policy_artifact.evidence,
        capture_policy_version=policy.policy_version,
        capture_configuration=config.capture_configuration_artifact.evidence,
        snapshot_capture_request_id=config.snapshot_capture_request_id,
        target_session=config.target_session,
        request_timestamp_utc=config.request_timestamp_utc,
        symbols=policy.symbols,
        timeframe=policy.timeframe,
        adjustment=policy.adjustment,
        provider=policy.provider,
        feed=policy.feed,
        currency=policy.currency,
        credential_reference=config.credential_reference_artifact.evidence,
        credential_reference_version=config.credential_reference_version,
        destination_reference=config.snapshot_destination.evidence,
        software_release=config.software_release_evidence,
        observed_allocation_at=config.observed_current_utc_timestamp,
        previous_attempt_history_head=history.verification.pointer.head_record,
        allocation_classification=CaptureAllocationClassification.CAPTURE_ONLY_AUTHORIZED,
        provider_call_budget=1,
        allocation_policy_version=config.allocation_policy_version,
    )


def _make_child_request(
    config: GuardedCaptureRunnerConfig,
    allocation: Any,
    allocation_evidence: ArtifactEvidence,
):
    allocation_path = capture_attempt_allocation_path(
        config.capture_attempt_root,
        config.scheduled_session_id,
        allocation.allocation_record_id,
    )
    request_path = (
        config.process_evidence_directory
        / f"child-request-{allocation.attempt_id}.json"
    )
    result_path = (
        config.process_evidence_directory / f"child-result-{allocation.attempt_id}.json"
    )
    request = create_isolated_capture_child_request(
        allocation=allocation_evidence,
        allocation_path=allocation_path,
        attempt_id=allocation.attempt_id,
        attempt_ordinal=allocation.attempt_ordinal,
        scheduled_session_id=allocation.scheduled_session_id,
        scheduled_launch_id=allocation.scheduled_launch_id,
        credential_reference=allocation.credential_reference,
        credential_reference_path=config.credential_reference_artifact.path,
        snapshot_capture_request_id=allocation.snapshot_capture_request_id,
        capture_configuration=allocation.capture_configuration,
        capture_configuration_path=config.capture_configuration_artifact.path,
        symbols=allocation.symbols,
        calendar=XNYS_CALENDAR_DESCRIPTOR,
        timeframe=allocation.timeframe,
        adjustment=allocation.adjustment,
        provider_id=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id,
        adapter_version=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.adapter_version,
        provider_operation=ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation,
        feed=allocation.feed,
        currency=allocation.currency,
        target_session=allocation.target_session,
        request_timestamp_utc=allocation.request_timestamp_utc,
        request_new_york_date=allocation.request_timestamp_utc.astimezone(
            ZoneInfo("America/New_York")
        ).date(),
        socket_timeout_seconds=15,
        wall_timeout_seconds=config.wall_timeout_seconds,
        maximum_response_bytes=4 * 1024 * 1024,
        maximum_candidate_count=2,
        snapshot_destination_reference=allocation.destination_reference,
        snapshot_destination_path=config.snapshot_destination.path,
        child_result_path=result_path,
        software_release=allocation.software_release,
        child_operation_version="isolated-alpaca-capture-child-v1",
    )
    return request, serialize_isolated_capture_child_request(request), request_path


def _terminal_from_execution(
    config: GuardedCaptureRunnerConfig,
    allocation: Any,
    allocation_evidence: ArtifactEvidence,
    request: IsolatedCaptureChildRequest,
    execution: Any,
):
    creation_evidence = _record_evidence(
        _process_evidence_path(
            config,
            "child-process-creation",
            execution.creation_record.process_creation_record_id,
        ),
        execution.creation_record,
        serialize_child_process_creation_record,
        "creation",
    )
    resume_evidence = (
        None
        if execution.resume_record is None
        else _record_evidence(
            _process_evidence_path(
                config,
                "child-resume-authorization",
                execution.resume_record.resume_authorization_record_id,
            ),
            execution.resume_record,
            serialize_child_resume_authorization_record,
            "resume",
        )
    )
    termination_evidence = _record_evidence(
        _process_evidence_path(
            config,
            "child-termination",
            execution.termination_record.termination_record_id,
        ),
        execution.termination_record,
        serialize_child_termination_record,
        "termination",
    )
    if execution.termination_record.timed_out:
        raise _AmbiguousChildResult("WALL_TIMEOUT")
    result_payload = read_safe_regular_file(
        request.child_result_path, 512 * 1024, "child result"
    )
    result = parse_isolated_capture_child_result(result_payload)
    result_evidence = evidence_for_payload(result.child_result_id, result_payload)
    if (
        result.child_request
        != evidence_for_payload(
            request.child_request_id, serialize_isolated_capture_child_request(request)
        )
        or result.allocation != allocation_evidence
        or result.attempt_id != allocation.attempt_id
        or result.native_exit_code != execution.native_exit_code
    ):
        raise _AmbiguousChildResult(
            GuardedCaptureRunnerDiagnostic.CHILD_RESULT_INVALID.value,
            result.child_result_id,
        )
    snapshot_evidence = None
    terminal_classification = terminal_classification_for_child(result.classification)
    if result.classification is IsolatedCaptureChildClassification.SUCCEEDED:
        if (
            result.snapshot is None
            or result.snapshot_verification is not SnapshotTerminalVerification.PASS
            or result.secret_cleanup is not SecretCleanupResult.PASS
        ):
            raise _AmbiguousChildResult(
                GuardedCaptureRunnerDiagnostic.CHILD_RESULT_INVALID.value,
                result.child_result_id,
            )
        snapshot_evidence = _snapshot_evidence(
            config, allocation, result.snapshot, allocation.currency
        )
        terminal_classification = CaptureAttemptTerminalClassification.SUCCEEDED
    terminal = create_capture_attempt_terminal(
        allocation=allocation_evidence,
        attempt_id=allocation.attempt_id,
        attempt_ordinal=allocation.attempt_ordinal,
        scheduled_session_id=allocation.scheduled_session_id,
        scheduled_launch_id=allocation.scheduled_launch_id,
        child_request=evidence_for_payload(
            request.child_request_id, serialize_isolated_capture_child_request(request)
        ),
        child_launch=creation_evidence,
        resume_authorization=resume_evidence,
        credential_access=None,
        child_result=result_evidence,
        provider_call_disposition=result.provider_call_disposition,
        completed_at=config.terminal_completed_at_utc,
        classification=terminal_classification,
        diagnostics=result.diagnostics,
        native_child_exit_code=result.native_exit_code,
        timeout_termination=(
            termination_evidence if execution.termination_record.timed_out else None
        ),
        snapshot=None if snapshot_evidence is None else snapshot_evidence.artifact,
        recovery_candidate=result_evidence
        if terminal_classification is CaptureAttemptTerminalClassification.OUTPUT_FAILED
        else None,
        snapshot_verification=result.snapshot_verification
        if snapshot_evidence is not None
        else SnapshotTerminalVerification.NOT_APPLICABLE,
        secret_cleanup=result.secret_cleanup,
        terminal_policy_version=config.terminal_policy_version,
    )
    return terminal, result.child_result_id, snapshot_evidence


def _ambiguous_terminal(
    config: GuardedCaptureRunnerConfig,
    allocation: Any,
    allocation_evidence: ArtifactEvidence,
    request: IsolatedCaptureChildRequest,
    execution: Any,
    diagnostic: str,
):
    creation_evidence = _record_evidence(
        _process_evidence_path(
            config,
            "child-process-creation",
            execution.creation_record.process_creation_record_id,
        ),
        execution.creation_record,
        serialize_child_process_creation_record,
        "creation",
    )
    resume_evidence = (
        None
        if execution.resume_record is None
        else _record_evidence(
            _process_evidence_path(
                config,
                "child-resume-authorization",
                execution.resume_record.resume_authorization_record_id,
            ),
            execution.resume_record,
            serialize_child_resume_authorization_record,
            "resume",
        )
    )
    termination_evidence = _record_evidence(
        _process_evidence_path(
            config,
            "child-termination",
            execution.termination_record.termination_record_id,
        ),
        execution.termination_record,
        serialize_child_termination_record,
        "termination",
    )
    return create_capture_attempt_terminal(
        allocation=allocation_evidence,
        attempt_id=allocation.attempt_id,
        attempt_ordinal=allocation.attempt_ordinal,
        scheduled_session_id=allocation.scheduled_session_id,
        scheduled_launch_id=allocation.scheduled_launch_id,
        child_request=evidence_for_payload(
            request.child_request_id, serialize_isolated_capture_child_request(request)
        ),
        child_launch=creation_evidence,
        resume_authorization=resume_evidence,
        credential_access=None,
        child_result=None,
        provider_call_disposition=ProviderCallDisposition.MAY_HAVE_STARTED
        if resume_evidence is not None
        else ProviderCallDisposition.NOT_STARTED,
        completed_at=config.terminal_completed_at_utc,
        classification=CaptureAttemptTerminalClassification.TIMEOUT
        if execution.termination_record.timed_out
        else (
            CaptureAttemptTerminalClassification.UNKNOWN_AFTER_LAUNCH
            if resume_evidence is not None
            else CaptureAttemptTerminalClassification.CHILD_CRASHED
        ),
        diagnostics=(diagnostic,),
        native_child_exit_code=getattr(execution, "native_exit_code", None),
        timeout_termination=termination_evidence
        if execution.termination_record.timed_out
        else None,
        snapshot=None,
        recovery_candidate=None,
        snapshot_verification=SnapshotTerminalVerification.NOT_APPLICABLE,
        secret_cleanup=SecretCleanupResult.UNKNOWN
        if resume_evidence is not None
        else SecretCleanupResult.NOT_APPLICABLE,
        terminal_policy_version=config.terminal_policy_version,
    )


def _publish_failed_terminal_after_launch_error(
    config: GuardedCaptureRunnerConfig,
    ownership: Any,
    result: GuardedCaptureRunnerResult,
    allocation: Any,
    allocation_evidence: ArtifactEvidence,
    execution: Any,
    request: Any,
    *_args: Any,
):
    return _release(
        config,
        ownership,
        replace(
            result,
            classification=GuardedCaptureRunnerClassification.AMBIGUOUS,
            diagnostics=(GuardedCaptureRunnerDiagnostic.CHILD_LAUNCH_FAILED.value,),
            allocation_record_id=allocation.allocation_record_id,
            attempt_id=allocation.attempt_id,
            attempt_ordinal=allocation.attempt_ordinal,
        ),
        LaunchResultClassification.FAILURE,
    )


def _record_evidence(
    path: Path, record: Any, serializer: Callable[[Any], bytes], label: str
) -> ArtifactEvidence:
    payload = read_safe_regular_file(path, 512 * 1024, label)
    if serializer(record) != payload:
        raise ValueError(f"{label} evidence does not reconcile")
    return evidence_for_payload(
        getattr(
            record,
            next(
                name
                for name in (
                    "process_creation_record_id",
                    "resume_authorization_record_id",
                    "termination_record_id",
                )
                if hasattr(record, name)
            ),
        ),
        payload,
    )


def _process_evidence_path(
    config: GuardedCaptureRunnerConfig, prefix: str, record_id: UUID
) -> Path:
    return config.process_evidence_directory / f"{prefix}-{record_id}.json"


def terminal_classification_for_child(
    value: IsolatedCaptureChildClassification,
) -> CaptureAttemptTerminalClassification:
    return {
        IsolatedCaptureChildClassification.CREDENTIAL_REFERENCE_INVALID: (
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED
        ),
        IsolatedCaptureChildClassification.SID_MISMATCH: (
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED
        ),
        IsolatedCaptureChildClassification.CREDENTIAL_NOT_FOUND: (
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED
        ),
        IsolatedCaptureChildClassification.CREDENTIAL_INVALID: (
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED
        ),
        IsolatedCaptureChildClassification.AUTHENTICATION_FAILED: (
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED
        ),
        IsolatedCaptureChildClassification.PROVIDER_REJECTED: (
            CaptureAttemptTerminalClassification.PROVIDER_REJECTED
        ),
        IsolatedCaptureChildClassification.NETWORK_FAILED: (
            CaptureAttemptTerminalClassification.NETWORK_FAILED
        ),
        IsolatedCaptureChildClassification.TIMEOUT: (
            CaptureAttemptTerminalClassification.TIMEOUT
        ),
        IsolatedCaptureChildClassification.INCOMPLETE_RESPONSE: (
            CaptureAttemptTerminalClassification.INCOMPLETE_RESPONSE
        ),
        IsolatedCaptureChildClassification.SNAPSHOT_OUTPUT_FAILED: (
            CaptureAttemptTerminalClassification.OUTPUT_FAILED
        ),
        IsolatedCaptureChildClassification.INTERNAL_FAILED: (
            CaptureAttemptTerminalClassification.CHILD_CRASHED
        ),
        IsolatedCaptureChildClassification.SUCCEEDED: (
            CaptureAttemptTerminalClassification.SUCCEEDED
        ),
    }[value]


def _scheduled_attempt_from_success(
    allocation: Any,
    terminal: Any,
    snapshot: SnapshotEvidence | None,
) -> ScheduledCaptureAttemptRecord:
    if snapshot is None:
        raise ValueError("successful terminal has no snapshot")
    return ScheduledCaptureAttemptRecord(
        1,
        allocation.attempt_id,
        allocation.scheduled_session_id,
        allocation.attempt_ordinal,
        allocation.symbols,
        allocation.timeframe,
        allocation.adjustment,
        allocation.provider,
        allocation.feed,
        allocation.currency,
        allocation.capture_policy_version,
        allocation.capture_configuration,
        allocation.request_timestamp_utc,
        terminal.completed_at,
        CaptureAttemptStatus.PASS,
        snapshot,
        "PASS",
    )


def _chronology_pass():
    return SnapshotChronologyResult.PASS


def _lease_start_evidence(ownership: Any) -> ArtifactEvidence:
    reference = ownership.start_reference
    return ArtifactEvidence(
        reference.record_id, reference.sha256, reference.byte_length
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


def _release(
    config: GuardedCaptureRunnerConfig,
    ownership: Any,
    result: GuardedCaptureRunnerResult,
    lease_classification: LaunchResultClassification,
    *,
    process_exit_code: int | None = None,
) -> GuardedCaptureRunnerResult:
    if ownership.released:
        return result
    diagnostic = (
        result.diagnostics[0] if result.diagnostics else result.classification.value
    )
    release_input = LaunchLeaseReleaseInput(
        release_classification=LaunchLeaseReleaseClassification.NORMAL,
        release_timestamp_utc=config.release_timestamp_utc,
        monotonic_duration_nanoseconds=config.monotonic_duration_nanoseconds,
        result_classification=lease_classification,
        result_diagnostic=diagnostic,
        process_exit_code=process_exit_code,
        release_policy=config.launch_guard_policy_version,
    )
    try:
        released: LaunchGuardReleaseResult = ownership.release(release_input)
    except Exception:
        return replace(
            result,
            classification=GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
            diagnostics=tuple(
                dict.fromkeys(
                    (
                        *result.diagnostics,
                        GuardedCaptureRunnerDiagnostic.LEASE_RELEASE_PUBLICATION_FAILED.value,
                        GuardedCaptureRunnerDiagnostic.MUTEX_RELEASE_FAILED.value,
                    )
                )
            ),
        )
    diagnostics = list(result.diagnostics)
    if released.classification in {
        ReleaseOperationalClassification.EVIDENCE_PUBLICATION_FAILED,
        ReleaseOperationalClassification.EVIDENCE_AND_NATIVE_RELEASE_FAILED,
    }:
        diagnostics.append(
            GuardedCaptureRunnerDiagnostic.LEASE_RELEASE_PUBLICATION_FAILED.value
        )
    if released.classification in {
        ReleaseOperationalClassification.NATIVE_RELEASE_FAILED,
        ReleaseOperationalClassification.EVIDENCE_AND_NATIVE_RELEASE_FAILED,
    }:
        diagnostics.append(GuardedCaptureRunnerDiagnostic.MUTEX_RELEASE_FAILED.value)
    classification = (
        result.classification
        if released.classification is ReleaseOperationalClassification.RELEASED
        else GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED
    )
    return replace(
        result,
        classification=classification,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        lease_release_record_id=released.release_record.release_id,
    )


def exit_code_for_guarded_capture_runner(result: GuardedCaptureRunnerResult) -> int:
    diagnostics = set(result.diagnostics)
    if GuardedCaptureRunnerDiagnostic.GUARD_ALREADY_HELD.value in diagnostics:
        return 9
    if diagnostics & {
        GuardedCaptureRunnerDiagnostic.GUARD_ACCESS_DENIED.value,
        GuardedCaptureRunnerDiagnostic.GUARD_UNSUPPORTED.value,
    }:
        return 10
    if diagnostics & {
        GuardedCaptureRunnerDiagnostic.LEASE_RELEASE_PUBLICATION_FAILED.value,
        GuardedCaptureRunnerDiagnostic.MUTEX_RELEASE_FAILED.value,
        GuardedCaptureRunnerDiagnostic.GUARD_ERROR.value,
    }:
        return 7
    if result.classification is GuardedCaptureRunnerClassification.SUCCEEDED:
        return 0
    if result.classification is GuardedCaptureRunnerClassification.NOT_READY:
        return 3
    if result.classification is GuardedCaptureRunnerClassification.BLOCKED:
        return 4
    if result.classification is GuardedCaptureRunnerClassification.AMBIGUOUS:
        return 6
    return 5


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one manually guarded capture-only Alpaca snapshot attempt."
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = load_guarded_capture_runner_config(args.config)
    except (OSError, ValueError, GuardedCaptureRunnerConfigError):
        print(
            json.dumps(
                {
                    "classification": GuardedCaptureRunnerClassification.BLOCKED.value,
                    "diagnostics": [
                        GuardedCaptureRunnerDiagnostic.CONFIGURATION_INVALID.value
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 4
    try:
        result = run_guarded_capture_runner(config)
    except Exception:
        print(
            json.dumps(
                {
                    "classification": GuardedCaptureRunnerClassification.FAILED.value,
                    "diagnostics": [GuardedCaptureRunnerDiagnostic.GUARD_ERROR.value],
                    "default_mutex_dacl_unhardened": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 5
    output: dict[str, object] = {
        "classification": result.classification.value,
        "default_mutex_dacl_unhardened": result.default_mutex_dacl_unhardened,
        "diagnostics": list(result.diagnostics),
        "scheduled_launch_id": str(result.scheduled_launch_id),
        "scheduled_session_id": str(result.scheduled_session_id),
    }
    for name in ("readiness_classification", "post_capture_readiness_classification"):
        value = getattr(result, name)
        if value is not None:
            output[name] = value.value
    for name in ("readiness_diagnostics",):
        output[name] = list(getattr(result, name))
    for name in (
        "lease_start_record_id",
        "lease_release_record_id",
        "allocation_record_id",
        "attempt_id",
        "child_result_id",
        "terminal_record_id",
        "selection_record_id",
    ):
        value = getattr(result, name)
        if value is not None:
            output[name] = str(value)
    if result.attempt_ordinal is not None:
        output["attempt_ordinal"] = result.attempt_ordinal
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return exit_code_for_guarded_capture_runner(result)
