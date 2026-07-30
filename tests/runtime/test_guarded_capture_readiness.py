from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from uuid import UUID

import pytest

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
    CapturePolicy,
    GuardedCaptureReadinessArtifactError,
    HeadRecordEvidence,
    MarketSessionHours,
    MarketSessionHoursKind,
    MarketSessionHoursSchedule,
    NextEligibleAction,
    ScheduledReadinessClassification,
    ScheduledReadinessCode,
    TerminalCheckpointEvidence,
    create_scheduled_capture_readiness_decision,
    parse_capture_policy_artifact,
    parse_market_session_hours_schedule,
    parse_scheduled_capture_readiness_decision,
    serialize_capture_policy_artifact,
    serialize_market_session_hours_schedule,
    serialize_scheduled_capture_readiness_decision,
)

EPOCH = UUID("20000000-0000-0000-0000-000000000001")
SESSION = UUID("20000000-0000-5000-8000-000000000002")
LAUNCH = UUID("20000000-0000-5000-8000-000000000003")
LEASE = UUID("20000000-0000-0000-0000-000000000004")
HEAD = UUID("20000000-0000-0000-0000-000000000005")
CHECKPOINT = UUID("20000000-0000-0000-0000-000000000006")
HOURS = UUID("20000000-0000-0000-0000-000000000007")
POLICY = UUID("20000000-0000-0000-0000-000000000008")
CONFIG = UUID("20000000-0000-0000-0000-000000000009")
ATTEMPT = UUID("20000000-0000-0000-0000-00000000000a")

D = TradingSession(date(2026, 7, 2))
E = TradingSession(date(2026, 7, 6))
SYMBOLS = (Symbol("SPY"), Symbol("QQQ"))
PROVIDER = ProviderDescriptor("alpaca", 1, "historical-bars", "sip")


def _evidence(identity: UUID, digit: str, length: int) -> ArtifactEvidence:
    return ArtifactEvidence(identity, digit * 64, length)


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
        _evidence(HOURS, "1", 300),
    )


def _policy() -> CapturePolicy:
    return CapturePolicy(
        "capture-policy-v1",
        300,
        300,
        2,
        (60,),
        30,
        3600,
        SYMBOLS,
        Timeframe.DAY_1,
        AdjustmentType.RAW,
        PROVIDER,
        "sip",
        "USD",
        _evidence(CONFIG, "2", 400),
    )


def _decision(observed_at: datetime | None = None):
    head = HeadRecordEvidence(EPOCH, _evidence(HEAD, "4", 800), 2)
    terminal = TerminalCheckpointEvidence(
        _evidence(CHECKPOINT, "5", 700),
        2,
        datetime(2026, 7, 2, 16, 0, tzinfo=UTC),
    )
    return create_scheduled_capture_readiness_decision(
        scheduled_session_id=SESSION,
        scheduled_launch_id=LAUNCH,
        authority_epoch_id=EPOCH,
        lease_start=_evidence(LEASE, "3", 900),
        head_record=head,
        terminal_checkpoint=terminal,
        market_hours_schedule=_evidence(HOURS, "6", 1000),
        capture_policy=_evidence(POLICY, "7", 1100),
        capture_attempts=(),
        snapshot_selection=None,
        observed_at=observed_at or datetime(2026, 7, 2, 17, 10, tzinfo=UTC),
        readiness_classification=ScheduledReadinessClassification.READY,
        diagnostics=(),
        provider_invocation_permitted=True,
        next_eligible_action=NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED,
        capture_attempt_ordinal=0,
        capture_attempt_id=ATTEMPT,
        runner_policy_version="capture-readiness-dry-run-v1",
    )


def test_schedule_and_policy_artifacts_are_strict_canonical_round_trips() -> None:
    schedule_payload = serialize_market_session_hours_schedule(_schedule())
    policy_payload = serialize_capture_policy_artifact(_policy())

    assert parse_market_session_hours_schedule(schedule_payload) == _schedule()
    assert parse_capture_policy_artifact(policy_payload) == _policy()
    assert schedule_payload.endswith(b"\n")
    assert policy_payload.endswith(b"\n")

    pretty = json.dumps(json.loads(schedule_payload), indent=2).encode()
    with pytest.raises(GuardedCaptureReadinessArtifactError, match="canonical"):
        parse_market_session_hours_schedule(pretty)


def test_decision_golden_vector_and_round_trip() -> None:
    decision = _decision()
    payload = serialize_scheduled_capture_readiness_decision(decision)

    assert str(decision.decision_id) == "28768732-f993-512c-a995-6c62d9662f83"
    assert len(payload) == 1606
    assert (
        hashlib.sha256(payload).hexdigest()
        == "7c9e4ae977eee583817744b6bf1fc92a824b4ef26f60ccd9b805814f415965d3"
    )
    assert parse_scheduled_capture_readiness_decision(payload) == decision


def test_decision_identity_binds_observed_time_and_all_action_evidence() -> None:
    original = _decision()
    changed = _decision(datetime(2026, 7, 2, 17, 11, tzinfo=UTC))

    assert changed.decision_id != original.decision_id
    assert serialize_scheduled_capture_readiness_decision(
        changed
    ) != serialize_scheduled_capture_readiness_decision(original)


def test_decision_rejects_permission_without_ready_attempt() -> None:
    with pytest.raises(
        GuardedCaptureReadinessArtifactError,
        match="provider permission",
    ):
        create_scheduled_capture_readiness_decision(
            scheduled_session_id=SESSION,
            scheduled_launch_id=LAUNCH,
            authority_epoch_id=EPOCH,
            lease_start=_evidence(LEASE, "3", 900),
            head_record=HeadRecordEvidence(
                EPOCH,
                _evidence(HEAD, "4", 800),
                2,
            ),
            terminal_checkpoint=TerminalCheckpointEvidence(
                _evidence(CHECKPOINT, "5", 700),
                2,
                datetime(2026, 7, 2, 16, 0, tzinfo=UTC),
            ),
            market_hours_schedule=_evidence(HOURS, "6", 1000),
            capture_policy=_evidence(POLICY, "7", 1100),
            capture_attempts=(),
            snapshot_selection=None,
            observed_at=datetime(2026, 7, 2, 17, 10, tzinfo=UTC),
            readiness_classification=ScheduledReadinessClassification.BLOCKED,
            diagnostics=(ScheduledReadinessCode.MANUAL_DISABLE_ACTIVE,),
            provider_invocation_permitted=True,
            next_eligible_action=NextEligibleAction.NONE,
            capture_attempt_ordinal=None,
            capture_attempt_id=None,
            runner_policy_version="capture-readiness-dry-run-v1",
        )
