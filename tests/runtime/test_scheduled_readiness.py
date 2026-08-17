from __future__ import annotations

import builtins
import os
import socket
import time
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Context, localcontext
from uuid import UUID

import pytest

from trading_bot.cli.paper_operation_inspection import (
    PaperOperationClassification,
    PaperOperationInspectionCode,
    PaperOperationInspectionResult,
)
from trading_bot.cli.scheduled_readiness import (
    scheduled_coordinator_input_from_inspection,
)
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    AdjustmentType,
    ProviderDescriptor,
    Timeframe,
)
from trading_bot.runtime import (
    ArtifactEvidence,
    CaptureAttemptStatus,
    CapturePolicy,
    CoordinatorInspectionInput,
    HeadRecordEvidence,
    MarketSessionHours,
    MarketSessionHoursKind,
    MarketSessionHoursSchedule,
    ScheduledCycleInputs,
    ScheduledHealthInputs,
    ScheduledPhase,
    ScheduledReadinessClassification,
    ScheduledReadinessCode,
    ScheduledReadinessInputs,
    SnapshotChronologyResult,
    SnapshotEvidence,
    SnapshotReadinessClassification,
    TerminalCheckpointEvidence,
    VerifiedAuthoritativeHeadInput,
    capture_attempt_record_evidence,
    create_scheduled_capture_attempt_record,
    create_scheduled_snapshot_selection_record,
    derive_scheduled_capture_attempt_id,
    derive_scheduled_launch_id,
    derive_scheduled_paper_session_id,
    derive_scheduled_snapshot_selection_id,
    derive_scheduler_caller_idempotency_key,
    evaluate_scheduled_capture_readiness,
    evaluate_scheduled_readiness,
    evaluate_snapshot_readiness,
    parse_scheduled_capture_attempt_record,
    parse_scheduled_snapshot_selection_record,
    serialize_scheduled_capture_attempt_record,
    serialize_scheduled_snapshot_selection_record,
    snapshot_selection_record_evidence,
)

EPOCH = UUID("10000000-0000-0000-0000-000000000001")
HEAD_ID = UUID("10000000-0000-0000-0000-000000000002")
LINEAGE_ID = UUID("10000000-0000-0000-0000-000000000003")
CHECKPOINT_ID = UUID("10000000-0000-0000-0000-000000000004")
SNAPSHOT_ID = UUID("10000000-0000-0000-0000-000000000005")
CONFIG_ID = UUID("10000000-0000-0000-0000-000000000006")
REQUEST_ID = UUID("10000000-0000-0000-0000-000000000007")
TARGET_ID = UUID("10000000-0000-0000-0000-000000000008")
RELEASE_ID = UUID("10000000-0000-0000-0000-000000000009")
APPROVAL_ID = UUID("10000000-0000-0000-0000-00000000000a")
SCHEDULE_ID = UUID("10000000-0000-0000-0000-00000000000b")

D = TradingSession(date(2026, 7, 2))
E = TradingSession(date(2026, 7, 6))
SYMBOLS = (Symbol("SPY"), Symbol("QQQ"))
PROVIDER = ProviderDescriptor("alpaca", 1, "historical-bars", "sip")


def _evidence(
    artifact_id: UUID, digit: str = "a", length: int = 100
) -> ArtifactEvidence:
    return ArtifactEvidence(artifact_id, digit * 64, length)


def _policy(*, maximum_attempts: int = 2) -> CapturePolicy:
    return CapturePolicy(
        "capture-policy-v1",
        300,
        300,
        maximum_attempts,
        tuple(60 for _ in range(maximum_attempts - 1)),
        30,
        3600,
        SYMBOLS,
        Timeframe.DAY_1,
        AdjustmentType.RAW,
        PROVIDER,
        "sip",
        "USD",
        _evidence(CONFIG_ID, "c", 200),
    )


def _schedule() -> MarketSessionHoursSchedule:
    return MarketSessionHoursSchedule(
        XNYS_CALENDAR_DESCRIPTOR,
        "xnys-hours-2026-v1",
        D.session_date,
        E.session_date,
        (
            MarketSessionHours(
                D,
                datetime(2026, 7, 2, 13, 30, tzinfo=UTC),
                datetime(2026, 7, 2, 17, 0, tzinfo=UTC),
                MarketSessionHoursKind.EARLY_CLOSE,
            ),
            MarketSessionHours(
                E,
                datetime(2026, 7, 6, 13, 30, tzinfo=UTC),
                datetime(2026, 7, 6, 20, 0, tzinfo=UTC),
                MarketSessionHoursKind.REGULAR,
            ),
        ),
        (),
        _evidence(SCHEDULE_ID, "b", 300),
    )


def _head(
    *,
    generation: int = 2,
    head_id: UUID = HEAD_ID,
    checkpoint_id: UUID = CHECKPOINT_ID,
    terminal_as_of: datetime = datetime(2026, 7, 2, 16, 0, tzinfo=UTC),
) -> VerifiedAuthoritativeHeadInput:
    return VerifiedAuthoritativeHeadInput(
        HeadRecordEvidence(EPOCH, _evidence(head_id, "d", 800), generation),
        LINEAGE_ID,
        TerminalCheckpointEvidence(
            _evidence(checkpoint_id, "e", 700),
            generation,
            terminal_as_of,
        ),
        True,
    )


def _snapshot(
    *,
    artifact: ArtifactEvidence | None = None,
    target: TradingSession = D,
    captured_at: datetime = datetime(2026, 7, 2, 17, 10, tzinfo=UTC),
    symbols: tuple[Symbol, ...] = SYMBOLS,
    provider: ProviderDescriptor = PROVIDER,
) -> SnapshotEvidence:
    return SnapshotEvidence(
        artifact or _evidence(SNAPSHOT_ID, "f", 900),
        target,
        captured_at,
        symbols,
        provider,
        Timeframe.DAY_1,
        AdjustmentType.RAW,
        provider.feed,
        "USD",
        True,
        True,
    )


def _ready_inputs() -> ScheduledReadinessInputs:
    head = _head()
    policy = _policy()
    session_id = derive_scheduled_paper_session_id(
        EPOCH,
        XNYS_CALENDAR_DESCRIPTOR,
        D,
        E,
        SYMBOLS,
        "universe-v1",
        "readiness-v1",
    )
    snapshot = _snapshot()
    attempt = create_scheduled_capture_attempt_record(
        session_id,
        0,
        policy,
        datetime(2026, 7, 2, 17, 6, tzinfo=UTC),
        snapshot.captured_at,
        CaptureAttemptStatus.PASS,
        snapshot,
        "PASS",
    )
    attempt_evidence = (capture_attempt_record_evidence(attempt),)
    selection = create_scheduled_snapshot_selection_record(
        session_id,
        head.head_record,
        head.terminal_checkpoint,
        attempt_evidence,
        attempt.attempt_id,
        snapshot.artifact,
        "selection-v1",
        SnapshotChronologyResult.PASS,
    )
    selection_evidence = snapshot_selection_record_evidence(selection)
    request = _evidence(REQUEST_ID, "1", 1000)
    configuration = _evidence(CONFIG_ID, "2", 1100)
    target = _evidence(TARGET_ID, "3", 1200)
    release = _evidence(RELEASE_ID, "4", 1300)
    approval = _evidence(APPROVAL_ID, "5", 1400)
    caller_key = derive_scheduler_caller_idempotency_key(
        session_id,
        head.head_record,
        head.verified_lineage_evidence_id,
        head.terminal_checkpoint,
        selection_evidence,
        snapshot.artifact,
        request,
        configuration,
        "target-authority-v1",
        target,
        release,
        approval,
    )
    return ScheduledReadinessInputs(
        head,
        D,
        E,
        snapshot.captured_at,
        _schedule(),
        policy,
        (attempt,),
        snapshot,
        selection,
        ScheduledCycleInputs(
            request,
            configuration,
            snapshot.artifact,
            datetime(2026, 7, 6, 13, 40, tzinfo=UTC),
            datetime(2026, 7, 6, 13, 50, tzinfo=UTC),
            datetime(2026, 7, 6, 14, 0, tzinfo=UTC),
            caller_key,
            "target-authority-v1",
            target,
            release,
            True,
            True,
            approval,
        ),
        session_id,
        "universe-v1",
        "readiness-v1",
        "selection-v1",
        False,
        False,
        ScheduledHealthInputs(True, True, True, True, True, False),
        CoordinatorInspectionInput("PENDING", CHECKPOINT_ID, "PENDING"),
    )


def test_capture_only_readiness_allows_first_attempt_without_operation_inputs() -> None:
    inputs = replace(
        _ready_inputs(),
        capture_attempts=(),
        selected_snapshot=None,
        snapshot_selection=None,
        cycle=None,
        coordinator=None,
    )

    result = evaluate_scheduled_capture_readiness(inputs)

    assert result.classification is ScheduledReadinessClassification.READY
    assert result.diagnostics == ()
    assert result.caller_idempotency_key is None


def test_capture_only_readiness_maps_time_disable_and_completion() -> None:
    base = replace(_ready_inputs(), cycle=None, coordinator=None)
    too_early = replace(
        base,
        capture_attempts=(),
        selected_snapshot=None,
        snapshot_selection=None,
        observed_at=datetime(2026, 7, 2, 17, 1, tzinfo=UTC),
    )
    disabled = replace(too_early, manual_disable_active=True)

    assert (
        evaluate_scheduled_capture_readiness(too_early).classification
        is ScheduledReadinessClassification.NOT_READY
    )
    assert (
        evaluate_scheduled_capture_readiness(disabled).classification
        is ScheduledReadinessClassification.BLOCKED
    )
    assert (
        evaluate_scheduled_capture_readiness(base).classification
        is ScheduledReadinessClassification.ALREADY_COMPLETED
    )


def test_capture_only_readiness_rejects_selection_outside_attempt_history() -> None:
    ready = _ready_inputs()
    inconsistent = replace(
        ready,
        capture_attempts=(),
        selected_snapshot=None,
        cycle=None,
        coordinator=None,
    )

    result = evaluate_scheduled_capture_readiness(inconsistent)

    assert result.classification is ScheduledReadinessClassification.CONFLICTING
    assert ScheduledReadinessCode.SNAPSHOT_SELECTION_CONFLICT in result.diagnostics


def test_identity_golden_vectors_and_retry_scopes() -> None:
    inputs = _ready_inputs()
    attempt = inputs.capture_attempts[0]
    assert str(inputs.scheduled_session_id) == "8de01536-2392-55bd-b8fe-17eae04aa816"
    launch = derive_scheduled_launch_id(
        EPOCH,
        ScheduledPhase.CAPTURE,
        inputs.scheduled_session_id,
        datetime(2026, 7, 2, 17, 5, tzinfo=UTC),
        0,
        "runner-v1",
    )
    retry_launch = derive_scheduled_launch_id(
        EPOCH,
        ScheduledPhase.CAPTURE,
        inputs.scheduled_session_id,
        datetime(2026, 7, 2, 17, 5, tzinfo=UTC),
        1,
        "runner-v1",
    )
    retry_attempt = derive_scheduled_capture_attempt_id(
        inputs.scheduled_session_id,
        1,
        SYMBOLS,
        Timeframe.DAY_1,
        AdjustmentType.RAW,
        PROVIDER,
        "sip",
        "USD",
        inputs.capture_policy.policy_version,
        inputs.capture_policy.configuration_evidence,
    )
    assert str(launch) == "799b0440-a7de-51fb-bc16-743cbf4a9b48"
    assert str(attempt.attempt_id) == "81451a19-16ee-5a60-a28b-4349159d634b"
    assert str(inputs.snapshot_selection.selection_id) == (
        "a9adff87-4f36-59ad-bb91-1c4730cfefc1"
    )
    assert str(inputs.cycle.expected_caller_idempotency_key) == (
        "01bf6713-a24f-56d3-b359-8d7c4f9f55bf"
    )
    assert retry_launch != launch
    assert retry_attempt != attempt.attempt_id
    assert (
        inputs.scheduled_session_id == inputs.capture_attempts[0].scheduled_session_id
    )


def test_identities_are_path_free_context_free_and_material_sensitive() -> None:
    inputs = _ready_inputs()
    with localcontext(Context(prec=1, Emin=-1, Emax=1)):
        repeated = derive_scheduled_paper_session_id(
            EPOCH,
            XNYS_CALENDAR_DESCRIPTOR,
            D,
            E,
            SYMBOLS,
            "universe-v1",
            "readiness-v1",
        )
    assert repeated == inputs.scheduled_session_id
    cycle = inputs.cycle
    assert cycle is not None
    changed_config = derive_scheduler_caller_idempotency_key(
        inputs.scheduled_session_id,
        inputs.authoritative_head.head_record,
        LINEAGE_ID,
        inputs.authoritative_head.terminal_checkpoint,
        snapshot_selection_record_evidence(inputs.snapshot_selection),
        inputs.selected_snapshot.artifact,
        cycle.cycle_request,
        _evidence(UUID(int=99), "9", 9),
        cycle.target_authority_version,
        cycle.target_authority,
        cycle.approved_release,
        cycle.approval,
    )
    assert changed_config != cycle.expected_caller_idempotency_key
    repeated_approval = derive_scheduler_caller_idempotency_key(
        inputs.scheduled_session_id,
        inputs.authoritative_head.head_record,
        LINEAGE_ID,
        inputs.authoritative_head.terminal_checkpoint,
        snapshot_selection_record_evidence(inputs.snapshot_selection),
        inputs.selected_snapshot.artifact,
        cycle.cycle_request,
        cycle.cycle_configuration,
        cycle.target_authority_version,
        cycle.target_authority,
        cycle.approved_release,
        cycle.approval,
    )
    changed_target = derive_scheduler_caller_idempotency_key(
        inputs.scheduled_session_id,
        inputs.authoritative_head.head_record,
        LINEAGE_ID,
        inputs.authoritative_head.terminal_checkpoint,
        snapshot_selection_record_evidence(inputs.snapshot_selection),
        inputs.selected_snapshot.artifact,
        cycle.cycle_request,
        cycle.cycle_configuration,
        cycle.target_authority_version,
        _evidence(UUID(int=101), "8", 8),
        cycle.approved_release,
        cycle.approval,
    )
    changed_release = derive_scheduler_caller_idempotency_key(
        inputs.scheduled_session_id,
        inputs.authoritative_head.head_record,
        LINEAGE_ID,
        inputs.authoritative_head.terminal_checkpoint,
        snapshot_selection_record_evidence(inputs.snapshot_selection),
        inputs.selected_snapshot.artifact,
        cycle.cycle_request,
        cycle.cycle_configuration,
        cycle.target_authority_version,
        cycle.target_authority,
        _evidence(UUID(int=102), "7", 7),
        cycle.approval,
    )
    assert repeated_approval == cycle.expected_caller_idempotency_key
    assert changed_target != repeated_approval
    assert changed_release != repeated_approval
    assert not any(
        "path" in name
        for model in (
            type(inputs.capture_attempts[0]),
            type(inputs.snapshot_selection),
            type(inputs.cycle),
        )
        for name in model.__dataclass_fields__
    )


def test_attempt_and_selection_strict_canonical_round_trips() -> None:
    inputs = _ready_inputs()
    attempt_payload = serialize_scheduled_capture_attempt_record(
        inputs.capture_attempts[0]
    )
    selection_payload = serialize_scheduled_snapshot_selection_record(
        inputs.snapshot_selection
    )
    assert attempt_payload.endswith(b"\n")
    assert selection_payload.endswith(b"\n")
    assert (
        parse_scheduled_capture_attempt_record(attempt_payload)
        == (inputs.capture_attempts[0])
    )
    assert parse_scheduled_snapshot_selection_record(selection_payload) == (
        inputs.snapshot_selection
    )
    with pytest.raises(ValueError):
        parse_scheduled_capture_attempt_record(
            attempt_payload.replace(b'"schema_version":1', b'"schema_version":1.0')
        )
    with pytest.raises(ValueError):
        parse_scheduled_snapshot_selection_record(
            selection_payload.replace(
                b'"schema_version":1',
                b'"schema_version":1,"unknown":0',
            )
        )


def test_explicit_schedule_covers_holiday_and_early_close() -> None:
    schedule = _schedule()
    assert schedule.hours_for(D).kind is MarketSessionHoursKind.EARLY_CLOSE
    assert schedule.hours_for(E).kind is MarketSessionHoursKind.REGULAR
    with pytest.raises(ValueError, match="missing"):
        replace(schedule, entries=(schedule.entries[0],))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda value: replace(
                value, observed_at=datetime(2026, 7, 2, 17, 1, tzinfo=UTC)
            ),
            SnapshotReadinessClassification.CAPTURE_TOO_EARLY,
        ),
        (
            lambda value: replace(
                value, observed_at=datetime(2026, 7, 6, 13, 26, tzinfo=UTC)
            ),
            SnapshotReadinessClassification.CAPTURE_DEADLINE_PASSED,
        ),
        (
            lambda value: replace(
                value,
                capture_attempts=(),
                selected_snapshot=None,
                snapshot_selection=None,
            ),
            SnapshotReadinessClassification.NO_ATTEMPTS,
        ),
    ],
)
def test_snapshot_window_classifications(mutation, expected) -> None:
    assert (
        evaluate_snapshot_readiness(mutation(_ready_inputs())).classification
        is expected
    )


def test_snapshot_backoff_and_exhaustion() -> None:
    inputs = _ready_inputs()
    failed0 = create_scheduled_capture_attempt_record(
        inputs.scheduled_session_id,
        0,
        inputs.capture_policy,
        datetime(2026, 7, 2, 17, 6, tzinfo=UTC),
        inputs.observed_at,
        CaptureAttemptStatus.FAILED,
        None,
        "PROVIDER_FAILURE",
    )
    backoff = replace(
        inputs,
        capture_attempts=(failed0,),
        selected_snapshot=None,
        snapshot_selection=None,
    )
    assert (
        evaluate_snapshot_readiness(backoff).classification
        is SnapshotReadinessClassification.CAPTURE_BACKOFF_ACTIVE
    )
    failed1 = create_scheduled_capture_attempt_record(
        inputs.scheduled_session_id,
        1,
        inputs.capture_policy,
        inputs.observed_at,
        inputs.observed_at,
        CaptureAttemptStatus.REJECTED,
        None,
        "INCOMPLETE",
    )
    exhausted = replace(backoff, capture_attempts=(failed0, failed1))
    assert (
        evaluate_snapshot_readiness(exhausted).classification
        is SnapshotReadinessClassification.CAPTURE_ATTEMPTS_EXHAUSTED
    )
    open_window = replace(
        backoff,
        observed_at=inputs.observed_at.replace(minute=12),
    )
    assert (
        evaluate_snapshot_readiness(open_window).classification
        is SnapshotReadinessClassification.CAPTURE_WINDOW_OPEN
    )


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        (
            _snapshot(target=TradingSession(date(2026, 7, 1))),
            SnapshotReadinessClassification.SNAPSHOT_TARGET_MISMATCH,
        ),
        (
            _snapshot(symbols=(Symbol("SPY"),)),
            SnapshotReadinessClassification.SYMBOL_UNIVERSE_MISMATCH,
        ),
        (
            _snapshot(
                provider=ProviderDescriptor(
                    "other-provider", 1, "historical-bars", "sip"
                )
            ),
            SnapshotReadinessClassification.PROVIDER_POLICY_MISMATCH,
        ),
        (
            _snapshot(captured_at=datetime(2026, 7, 2, 15, 59, tzinfo=UTC)),
            SnapshotReadinessClassification.SNAPSHOT_CAPTURED_BEFORE_TERMINAL,
        ),
        (
            _snapshot(captured_at=datetime(2026, 7, 2, 17, 11, tzinfo=UTC)),
            SnapshotReadinessClassification.SNAPSHOT_FUTURE_SKEW,
        ),
        (
            _snapshot(captured_at=datetime(2026, 7, 2, 18, 1, tzinfo=UTC)),
            SnapshotReadinessClassification.SNAPSHOT_FUTURE_SKEW,
        ),
    ],
)
def test_terminal_specific_snapshot_failures(snapshot, expected) -> None:
    inputs = _ready_inputs()
    attempt = create_scheduled_capture_attempt_record(
        inputs.scheduled_session_id,
        0,
        inputs.capture_policy,
        min(snapshot.captured_at, inputs.observed_at),
        max(snapshot.captured_at, inputs.observed_at),
        CaptureAttemptStatus.PASS,
        snapshot,
        "PASS",
    )
    changed = replace(
        inputs,
        capture_attempts=(attempt,),
        selected_snapshot=snapshot,
        snapshot_selection=None,
    )
    assert evaluate_snapshot_readiness(changed).classification is expected


def test_duplicate_and_conflicting_captures_fail_closed() -> None:
    inputs = _ready_inputs()
    second = create_scheduled_capture_attempt_record(
        inputs.scheduled_session_id,
        1,
        inputs.capture_policy,
        inputs.observed_at,
        inputs.observed_at,
        CaptureAttemptStatus.PASS,
        inputs.selected_snapshot,
        "PASS",
    )
    duplicate = replace(inputs, capture_attempts=(inputs.capture_attempts[0],) * 2)
    assert (
        evaluate_snapshot_readiness(duplicate).classification
        is SnapshotReadinessClassification.DUPLICATE_ELIGIBLE_CAPTURES
    )
    conflicting = replace(inputs, capture_attempts=(second,))
    assert (
        evaluate_snapshot_readiness(conflicting).classification
        is SnapshotReadinessClassification.CONFLICTING_CAPTURE_RECORDS
    )
    attempt_evidence = tuple(
        capture_attempt_record_evidence(item)
        for item in (*inputs.capture_attempts, second)
    )
    selection = create_scheduled_snapshot_selection_record(
        inputs.scheduled_session_id,
        inputs.authoritative_head.head_record,
        inputs.authoritative_head.terminal_checkpoint,
        attempt_evidence,
        inputs.capture_attempts[0].attempt_id,
        inputs.selected_snapshot.artifact,
        inputs.selection_policy_version,
        SnapshotChronologyResult.PASS,
    )
    ordered_retries = replace(
        inputs,
        capture_attempts=(*inputs.capture_attempts, second),
        snapshot_selection=selection,
    )
    assert (
        evaluate_snapshot_readiness(ordered_retries).classification
        is SnapshotReadinessClassification.VALID_SELECTED_SNAPSHOT
    )


def test_stale_and_selection_record_mismatch() -> None:
    inputs = _ready_inputs()
    stale_snapshot = _snapshot(captured_at=datetime(2026, 7, 2, 18, 1, tzinfo=UTC))
    stale_attempt = create_scheduled_capture_attempt_record(
        inputs.scheduled_session_id,
        0,
        inputs.capture_policy,
        datetime(2026, 7, 2, 17, 59, tzinfo=UTC),
        stale_snapshot.captured_at,
        CaptureAttemptStatus.PASS,
        stale_snapshot,
        "PASS",
    )
    stale = replace(
        inputs,
        observed_at=stale_snapshot.captured_at,
        capture_attempts=(stale_attempt,),
        selected_snapshot=stale_snapshot,
        snapshot_selection=None,
    )
    assert (
        evaluate_snapshot_readiness(stale).classification
        is SnapshotReadinessClassification.STALE_SNAPSHOT
    )
    mismatched_selection = replace(
        inputs,
        snapshot_selection=create_scheduled_snapshot_selection_record(
            inputs.scheduled_session_id,
            inputs.authoritative_head.head_record,
            inputs.authoritative_head.terminal_checkpoint,
            tuple(
                capture_attempt_record_evidence(item)
                for item in inputs.capture_attempts
            ),
            inputs.capture_attempts[0].attempt_id,
            inputs.selected_snapshot.artifact,
            inputs.selection_policy_version,
            SnapshotChronologyResult.FAIL,
        ),
    )
    assert (
        evaluate_snapshot_readiness(mismatched_selection).classification
        is SnapshotReadinessClassification.SELECTION_RECORD_MISMATCH
    )


def test_ready_and_classification_precedence() -> None:
    inputs = _ready_inputs()
    result = evaluate_scheduled_readiness(inputs)
    assert result.classification is ScheduledReadinessClassification.READY
    assert result.caller_idempotency_key == inputs.cycle.expected_caller_idempotency_key
    assert result.diagnostics == (ScheduledReadinessCode.COORDINATOR_PENDING,)
    conflicting = replace(
        inputs,
        manual_disable_active=True,
        failed_receipt_verified=True,
        coordinator=CoordinatorInspectionInput(
            "CONFLICTING", CHECKPOINT_ID, "LINEAGE_CONFLICT"
        ),
    )
    result = evaluate_scheduled_readiness(conflicting)
    assert result.classification is ScheduledReadinessClassification.CONFLICTING
    assert ScheduledReadinessCode.MANUAL_DISABLE_ACTIVE in result.diagnostics
    assert ScheduledReadinessCode.FAILED_RECEIPT_REQUIRES_REVIEW in result.diagnostics


def test_review_completed_and_coordinator_pending_cases() -> None:
    inputs = _ready_inputs()
    assert (
        evaluate_scheduled_readiness(
            replace(inputs, transition_without_receipt=True)
        ).classification
        is ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED
    )
    assert (
        evaluate_scheduled_readiness(
            replace(inputs, failed_receipt_verified=True)
        ).classification
        is ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED
    )
    completed = replace(
        inputs,
        coordinator=CoordinatorInspectionInput(
            "ALREADY_APPLIED",
            CHECKPOINT_ID,
            "ALREADY_APPLIED",
            successor_checkpoint_id=CHECKPOINT_ID,
            completed_receipt_verified=True,
            transition_verified=True,
            head_advanced_to_successor=True,
        ),
    )
    assert (
        evaluate_scheduled_readiness(completed).classification
        is ScheduledReadinessClassification.ALREADY_COMPLETED
    )
    pending_without_selection = replace(
        inputs, selected_snapshot=None, snapshot_selection=None
    )
    assert (
        evaluate_scheduled_readiness(pending_without_selection).classification
        is ScheduledReadinessClassification.NOT_READY
    )
    assert (
        evaluate_scheduled_readiness(
            replace(inputs, staging_present=True)
        ).classification
        is ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED
    )


def test_credentials_and_higher_priority_health_gate_block_ready() -> None:
    inputs = _ready_inputs()
    health = replace(
        inputs.health,
        credential_isolation_ok=False,
        operation_credentials_present=True,
    )
    result = evaluate_scheduled_readiness(replace(inputs, health=health))
    assert result.classification is ScheduledReadinessClassification.BLOCKED
    assert ScheduledReadinessCode.OPERATION_CREDENTIALS_PRESENT in result.diagnostics


def test_head_change_changes_selection_and_caller_key() -> None:
    inputs = _ready_inputs()
    new_head = _head(head_id=UUID(int=200), checkpoint_id=UUID(int=201))
    attempt_evidence = tuple(
        capture_attempt_record_evidence(item) for item in inputs.capture_attempts
    )
    new_selection_id = derive_scheduled_snapshot_selection_id(
        inputs.scheduled_session_id,
        new_head.head_record,
        new_head.terminal_checkpoint,
        attempt_evidence,
        inputs.capture_attempts[0].attempt_id,
        inputs.selected_snapshot.artifact,
        inputs.selection_policy_version,
        SnapshotChronologyResult.PASS,
    )
    assert new_selection_id != inputs.snapshot_selection.selection_id
    new_selection = create_scheduled_snapshot_selection_record(
        inputs.scheduled_session_id,
        new_head.head_record,
        new_head.terminal_checkpoint,
        attempt_evidence,
        inputs.capture_attempts[0].attempt_id,
        inputs.selected_snapshot.artifact,
        inputs.selection_policy_version,
        SnapshotChronologyResult.PASS,
    )
    cycle = inputs.cycle
    new_caller = derive_scheduler_caller_idempotency_key(
        inputs.scheduled_session_id,
        new_head.head_record,
        new_head.verified_lineage_evidence_id,
        new_head.terminal_checkpoint,
        snapshot_selection_record_evidence(new_selection),
        inputs.selected_snapshot.artifact,
        cycle.cycle_request,
        cycle.cycle_configuration,
        cycle.target_authority_version,
        cycle.target_authority,
        cycle.approved_release,
        cycle.approval,
    )
    assert new_caller != cycle.expected_caller_idempotency_key


def test_missing_market_hours_and_sequence_three_chronology() -> None:
    inputs = _ready_inputs()
    missing = evaluate_scheduled_readiness(replace(inputs, market_hours=None))
    assert missing.classification is ScheduledReadinessClassification.BLOCKED
    assert ScheduledReadinessCode.MARKET_HOURS_UNAVAILABLE in missing.diagnostics
    sequence_three = _head(
        generation=3,
        head_id=UUID(int=300),
        checkpoint_id=UUID(int=301),
        terminal_as_of=datetime(2026, 7, 2, 17, 11, tzinfo=UTC),
    )
    chronology = replace(
        inputs,
        authoritative_head=sequence_three,
        snapshot_selection=None,
    )
    assert (
        evaluate_snapshot_readiness(chronology).classification
        is SnapshotReadinessClassification.SNAPSHOT_CAPTURED_BEFORE_TERMINAL
    )


def test_pure_evaluator_uses_no_external_side_effects(monkeypatch) -> None:
    inputs = _ready_inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("external access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    assert (
        evaluate_scheduled_readiness(inputs).classification
        is ScheduledReadinessClassification.READY
    )


def test_existing_coordinator_inspection_normalizes_without_io() -> None:
    inspection = PaperOperationInspectionResult(
        PaperOperationClassification.PENDING,
        UUID(int=400),
        CHECKPOINT_ID,
        UUID(int=401),
        None,
        (PaperOperationInspectionCode.PENDING,),
    )
    normalized = scheduled_coordinator_input_from_inspection(inspection)
    assert normalized.classification == "PENDING"
    assert normalized.terminal_checkpoint_id == CHECKPOINT_ID
    assert normalized.diagnostic == "PENDING"
