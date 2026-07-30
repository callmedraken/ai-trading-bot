from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.cli.guarded_capture_readiness as runner_module
import trading_bot.cli.windows_launch_guard as guard_module
from trading_bot.cli.guarded_capture_readiness import (
    exit_code_for_guarded_capture_readiness,
    run_guarded_capture_readiness,
)
from trading_bot.cli.guarded_capture_readiness_config import (
    CaptureOnlyHealthConfig,
    ExplicitArtifactReference,
    GuardedCaptureReadinessConfig,
)
from trading_bot.cli.guarded_capture_readiness_output import (
    DecisionEvidencePublicationError,
    publish_scheduled_capture_readiness_decision,
)
from trading_bot.cli.local_lineage_head import (
    LocalLineageHeadClassification,
    LocalLineageHeadDiagnosticCode,
    LocalLineageHeadResult,
)
from trading_bot.cli.windows_launch_guard import (
    LaunchGuardAclPolicy,
    NativeMutexAcquire,
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
    CapturePolicy,
    HeadRecordEvidence,
    LaunchGuardAcquisitionClassification,
    MarketSessionHours,
    MarketSessionHoursKind,
    MarketSessionHoursSchedule,
    NextEligibleAction,
    ScheduledHealthInputs,
    ScheduledPhase,
    ScheduledReadinessClassification,
    ScheduledReadinessInputs,
    TerminalCheckpointEvidence,
    VerifiedAuthoritativeHeadInput,
    evaluate_scheduled_capture_readiness,
    serialize_capture_policy_artifact,
    serialize_market_session_hours_schedule,
    serialize_scheduled_capture_readiness_decision,
)

EPOCH = UUID("40000000-0000-0000-0000-000000000001")
MACHINE = UUID("40000000-0000-0000-0000-000000000002")
EXECUTABLE = UUID("40000000-0000-0000-0000-000000000003")
HEAD = UUID("40000000-0000-0000-0000-000000000004")
LINEAGE = UUID("40000000-0000-0000-0000-000000000005")
CHECKPOINT = UUID("40000000-0000-0000-0000-000000000006")
HOURS_AUTHORITY = UUID("40000000-0000-0000-0000-000000000007")
HOURS_ARTIFACT = UUID("40000000-0000-0000-0000-000000000008")
POLICY_CONFIG = UUID("40000000-0000-0000-0000-000000000009")
POLICY_ARTIFACT = UUID("40000000-0000-0000-0000-00000000000a")

D = TradingSession(date(2026, 7, 2))
E = TradingSession(date(2026, 7, 6))
SYMBOLS = (Symbol("SPY"), Symbol("QQQ"))
PROVIDER = ProviderDescriptor("alpaca", 1, "historical-bars", "sip")


class FakeMutexApi:
    def __init__(
        self,
        classification: LaunchGuardAcquisitionClassification = (
            LaunchGuardAcquisitionClassification.ACQUIRED
        ),
        *,
        fail_release: bool = False,
    ) -> None:
        self.classification = classification
        self.fail_release = fail_release
        self.acquire_calls = 0
        self.release_calls = 0
        self.close_calls = 0

    def acquire(self, mutex_name: str, timeout_milliseconds: int):
        del mutex_name, timeout_milliseconds
        self.acquire_calls += 1
        handle = (
            object()
            if self.classification
            in {
                LaunchGuardAcquisitionClassification.ACQUIRED,
                LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED,
            }
            else None
        )
        return NativeMutexAcquire(self.classification, handle)

    def release(self, handle: object) -> None:
        del handle
        self.release_calls += 1
        if self.fail_release:
            raise OSError("injected release failure")

    def close(self, handle: object) -> None:
        del handle
        self.close_calls += 1


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
        _evidence(HOURS_AUTHORITY, "1", 100),
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
        _evidence(POLICY_CONFIG, "2", 200),
    )


def _head() -> VerifiedAuthoritativeHeadInput:
    return VerifiedAuthoritativeHeadInput(
        HeadRecordEvidence(EPOCH, _evidence(HEAD, "3", 800), 2),
        LINEAGE,
        TerminalCheckpointEvidence(
            _evidence(CHECKPOINT, "4", 700),
            2,
            datetime(2026, 7, 2, 16, 0, tzinfo=UTC),
        ),
        True,
    )


def _reference(path: Path, identity: UUID, payload: bytes) -> ExplicitArtifactReference:
    path.write_bytes(payload)
    return ExplicitArtifactReference(
        ArtifactEvidence(
            identity,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        ),
        path,
    )


def _config(tmp_path: Path) -> GuardedCaptureReadinessConfig:
    audit = tmp_path / "audit"
    audit.mkdir(parents=True)
    hours = _reference(
        tmp_path / "hours.json",
        HOURS_ARTIFACT,
        serialize_market_session_hours_schedule(_schedule()),
    )
    policy = _reference(
        tmp_path / "policy.json",
        POLICY_ARTIFACT,
        serialize_capture_policy_artifact(_policy()),
    )
    return GuardedCaptureReadinessConfig(
        authority_root=tmp_path / "authority",
        authority_epoch_id=EPOCH,
        scheduler_audit_root=audit,
        scheduled_phase=ScheduledPhase.CAPTURE_READINESS_DRY_RUN,
        target_session=D,
        execution_session=E,
        symbols=SYMBOLS,
        universe_policy_version="universe-v1",
        readiness_policy_version="readiness-v1",
        selection_policy_version="selection-v1",
        nominal_scheduled_slot=datetime(2026, 7, 2, 17, 5, tzinfo=UTC),
        launch_retry_ordinal=0,
        observed_current_utc_timestamp=datetime(
            2026,
            7,
            2,
            17,
            10,
            tzinfo=UTC,
        ),
        acquisition_timestamp_utc="2026-07-02T17:10:01Z",
        release_timestamp_utc="2026-07-02T17:10:02Z",
        monotonic_duration_nanoseconds=1_000_000_000,
        machine_authority_id=MACHINE,
        boot_session_evidence="boot-2026-07-30T00:00:00Z",
        process_id=4242,
        process_creation_timestamp_utc="2026-07-02T17:00:00Z",
        account_sid="S-1-5-21-111-222-333-1001",
        executable_release_evidence=_evidence(EXECUTABLE, "5", 300),
        maximum_runtime_seconds=900,
        mutex_timeout_seconds=0,
        launch_guard_policy_version="windows-launch-guard-v1",
        acl_mode=LaunchGuardAclPolicy.ALLOW_DEFAULT_DACL,
        market_hours_schedule_artifact=hours,
        capture_policy_artifact=policy,
        capture_attempt_artifacts=(),
        snapshot_selection_artifact=None,
        manual_disable_active=False,
        capture_health=CaptureOnlyHealthConfig(True, True, True, True),
        runner_policy_version="capture-readiness-dry-run-v1",
    )


def _verified_head_result() -> LocalLineageHeadResult:
    authority = SimpleNamespace(pointer=SimpleNamespace(authority_epoch_id=EPOCH))
    return LocalLineageHeadResult(
        LocalLineageHeadClassification.PASS,
        LocalLineageHeadDiagnosticCode.NONE,
        authority,  # type: ignore[arg-type]
    )


def _run(config, api, **kwargs):
    return run_guarded_capture_readiness(
        config,
        native_api=api,
        head_verifier=kwargs.pop(
            "head_verifier",
            lambda _: _verified_head_result(),
        ),
        head_input_adapter=lambda _: _head(),
        **kwargs,
    )


def test_ready_dry_run_publishes_attempt_permission_without_provider_call(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi()

    result = _run(config, api)

    assert result.readiness_classification is ScheduledReadinessClassification.READY
    assert result.next_eligible_action is NextEligibleAction.CAPTURE_ATTEMPT_ALLOWED
    assert result.proposed_capture_attempt_ordinal == 0
    assert result.proposed_capture_attempt_id is not None
    assert result.decision is not None
    assert result.decision.provider_invocation_permitted
    assert result.decision_publication is not None
    assert result.lease_release_record_id is not None
    assert exit_code_for_guarded_capture_readiness(result) == 0
    assert api.release_calls == api.close_calls == 1
    assert sorted(path.name for path in config.scheduler_audit_root.iterdir()) == [
        "lock-events",
        "readiness-decisions",
    ]


def test_identical_repeated_run_reuses_byte_identical_evidence(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi()
    first = _run(config, api)
    first_payload = first.decision_publication.path.read_bytes()  # type: ignore[union-attr]

    second = _run(config, api)

    assert second.decision == first.decision
    assert second.lease_start_record_id == first.lease_start_record_id
    assert second.lease_release_record_id == first.lease_release_record_id
    assert second.decision_publication.path.read_bytes() == first_payload  # type: ignore[union-attr]
    assert api.acquire_calls == api.release_calls == api.close_calls == 2


def test_observation_and_retry_change_only_approved_identity_domains(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    observed = replace(
        config,
        observed_current_utc_timestamp=datetime(
            2026,
            7,
            2,
            17,
            11,
            tzinfo=UTC,
        ),
    )
    retried = replace(config, launch_retry_ordinal=1)

    first = _run(config, FakeMutexApi())
    second = _run(observed, FakeMutexApi())
    third = _run(retried, FakeMutexApi())

    assert observed.scheduled_launch_id == config.scheduled_launch_id
    assert second.decision.decision_id != first.decision.decision_id  # type: ignore[union-attr]
    assert retried.scheduled_launch_id != config.scheduled_launch_id
    assert third.decision.decision_id != first.decision.decision_id  # type: ignore[union-attr]


def test_guard_already_held_prevents_all_filesystem_and_readiness_work(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    calls = 0

    def head_verifier(_: Path):
        nonlocal calls
        calls += 1
        raise AssertionError("head verification must not run")

    result = _run(
        config,
        FakeMutexApi(LaunchGuardAcquisitionClassification.ALREADY_HELD),
        head_verifier=head_verifier,
    )

    assert calls == 0
    assert result.readiness_classification is ScheduledReadinessClassification.NOT_READY
    assert result.diagnostics == ("GUARD_ALREADY_HELD",)
    assert not (config.scheduler_audit_root / "lock-events").exists()
    assert exit_code_for_guarded_capture_readiness(result) == 9


def test_abandoned_guard_publishes_start_and_release_without_evaluator(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED)

    result = _run(
        config,
        api,
        head_verifier=lambda _: pytest.fail("head verifier must not run"),
        readiness_evaluator=lambda _: pytest.fail("evaluator must not run"),
    )

    assert result.readiness_classification is (
        ScheduledReadinessClassification.MANUAL_REVIEW_REQUIRED
    )
    assert result.diagnostics == ("GUARD_ABANDONED",)
    assert result.decision_publication is None
    assert result.lease_release_record_id is not None
    assert exit_code_for_guarded_capture_readiness(result) == 8
    assert len(tuple((config.scheduler_audit_root / "lock-events").iterdir())) == 2


def test_head_failure_and_start_publication_failure_prevent_evaluation(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi()
    result = _run(
        config,
        api,
        head_verifier=lambda _: LocalLineageHeadResult(
            LocalLineageHeadClassification.BLOCKED,
            LocalLineageHeadDiagnosticCode.POINTER_MISSING,
        ),
        readiness_evaluator=lambda _: pytest.fail("evaluator must not run"),
    )
    assert result.diagnostics == ("HEAD_VERIFICATION_FAILED",)
    assert result.lease_release_record_id is not None

    other = _config(tmp_path / "other")
    lock_events = other.scheduler_audit_root / "lock-events"
    lock_events.mkdir()
    (lock_events / "unexpected").write_text("hostile", encoding="utf-8")
    second_api = FakeMutexApi()
    blocked = _run(
        other,
        second_api,
        head_verifier=lambda _: pytest.fail("head verifier must not run"),
    )
    assert blocked.diagnostics == ("LEASE_START_PUBLICATION_FAILED",)
    assert second_api.release_calls == second_api.close_calls == 1
    assert exit_code_for_guarded_capture_readiness(blocked) == 7


def test_decision_publication_failure_still_publishes_release(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi()

    result = _run(
        config,
        api,
        decision_publisher=lambda *_: (_ for _ in ()).throw(
            DecisionEvidencePublicationError("injected")
        ),
    )

    assert result.diagnostics[0] == "DECISION_PUBLICATION_FAILED"
    assert result.lease_release_record_id is not None
    assert api.release_calls == api.close_calls == 1
    assert exit_code_for_guarded_capture_readiness(result) == 7


def test_release_publication_failure_still_releases_native_mutex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi()
    monkeypatch.setattr(
        guard_module,
        "publish_launch_lease_release",
        lambda *_: (_ for _ in ()).throw(OSError("injected")),
    )

    result = _run(config, api)

    assert "LEASE_RELEASE_PUBLICATION_FAILED" in result.diagnostics
    assert api.release_calls == api.close_calls == 1
    assert exit_code_for_guarded_capture_readiness(result) == 7


def test_native_release_failure_is_surfaced(tmp_path: Path) -> None:
    config = _config(tmp_path)
    api = FakeMutexApi(fail_release=True)

    result = _run(config, api)

    assert "MUTEX_RELEASE_FAILED" in result.diagnostics
    assert api.release_calls == api.close_calls == 1
    assert exit_code_for_guarded_capture_readiness(result) == 7


def test_conflicting_preexisting_decision_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    result = _run(config, FakeMutexApi())
    decision = result.decision
    publication = result.decision_publication
    assert decision is not None and publication is not None
    publication.path.write_bytes(b"{}\n")

    with pytest.raises(DecisionEvidencePublicationError):
        publish_scheduled_capture_readiness_decision(
            config.scheduler_audit_root,
            decision,
        )


def test_manual_disable_publishes_blocked_decision(tmp_path: Path) -> None:
    config = _config(tmp_path)
    disabled = replace(config, manual_disable_active=True)

    result = _run(disabled, FakeMutexApi())

    assert result.readiness_classification is ScheduledReadinessClassification.BLOCKED
    assert result.diagnostics == ("MANUAL_DISABLE_ACTIVE",)
    assert result.next_eligible_action is NextEligibleAction.NONE
    assert result.decision_publication is not None
    assert exit_code_for_guarded_capture_readiness(result) == 4


def test_runner_invokes_the_pure_evaluator_once(tmp_path: Path) -> None:
    config = _config(tmp_path)
    calls = 0

    def evaluator(inputs: ScheduledReadinessInputs):
        nonlocal calls
        calls += 1
        assert isinstance(inputs.health, ScheduledHealthInputs)
        return evaluate_scheduled_capture_readiness(inputs)

    result = _run(
        config,
        FakeMutexApi(),
        readiness_evaluator=evaluator,
    )

    assert calls == 1
    assert result.readiness_classification is ScheduledReadinessClassification.READY
    assert serialize_scheduled_capture_readiness_decision(result.decision)  # type: ignore[arg-type]


def test_runner_reads_no_clock_environment_or_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)

    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("forbidden ambient dependency")

    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    result = _run(config, FakeMutexApi())

    assert result.readiness_classification is ScheduledReadinessClassification.READY


def test_cli_emits_only_the_approved_compact_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    result = _run(config, FakeMutexApi())
    monkeypatch.setattr(
        runner_module,
        "load_guarded_capture_readiness_config",
        lambda _: config,
    )
    monkeypatch.setattr(
        runner_module,
        "run_guarded_capture_readiness",
        lambda _: result,
    )

    exit_code = runner_module.main(["--config", "ignored.json"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert set(output) == {
        "scheduled_session_id",
        "scheduled_launch_id",
        "lease_start_record_id",
        "readiness_classification",
        "diagnostics",
        "next_eligible_action",
        "proposed_capture_attempt_ordinal",
        "proposed_capture_attempt_id",
        "decision_record_id",
        "decision_path",
        "lease_release_record_id",
    }
