"""Focused boundary tests for the manually invoked guarded runner."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.cli.guarded_capture_runner as guarded_runner_module
from trading_bot.cli.guarded_capture_readiness_config import (
    CaptureOnlyHealthConfig,
    ExplicitArtifactReference,
)
from trading_bot.cli.guarded_capture_runner import (
    GuardedCaptureRunnerClassification,
    GuardedCaptureRunnerDiagnostic,
    GuardedCaptureRunnerResult,
    _classify_prior_terminal_retry_policy,
    exit_code_for_guarded_capture_runner,
    run_guarded_capture_runner,
    terminal_classification_for_child,
)
from trading_bot.cli.guarded_capture_runner_config import (
    GuardedCaptureRunnerConfig,
    GuardedCaptureRunnerConfigError,
    ProductionXnysHoursAuthority,
    ProductionXnysHoursAuthorityStatus,
    load_guarded_capture_runner_config,
)
from trading_bot.cli.windows_launch_guard import (
    LaunchGuardAclPolicy,
    NativeMutexAcquire,
)
from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.runtime import (
    ArtifactEvidence,
    AttemptHistoryState,
    CaptureAttemptTerminalClassification,
    CaptureRetryClassification,
    IsolatedCaptureChildClassification,
    LaunchGuardAcquisitionClassification,
    ProviderCallDisposition,
    capture_attempt_allocation_path,
)

EPOCH = UUID("f81cf9a0-c1f6-54bd-94a6-24e56b70dbe1")
REQUEST = UUID("a753141d-5739-5995-a72c-a7aafb497de7")


def _evidence(number: int) -> dict[str, object]:
    return {
        "artifact_id": str(UUID(int=number)),
        "sha256": f"{number:064x}"[-64:],
        "byte_length": number,
    }


def _reference(number: int, path: Path) -> dict[str, object]:
    return {**_evidence(number), "path": str(path)}


def _config_payload(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "root"
    return {
        "schema_version": 1,
        "authority_root": str(root / "authority"),
        "scheduler_audit_root": str(root / "audit"),
        "capture_attempt_root": str(root / "attempts"),
        "authority_epoch_id": str(EPOCH),
        "scheduled_phase": "CAPTURE",
        "target_session": "2026-07-30",
        "execution_session": "2026-07-31",
        "symbols": ["SPY", "QQQ"],
        "universe_policy_version": "universe-v1",
        "readiness_policy_version": "readiness-v1",
        "selection_policy_version": "selection-v1",
        "nominal_scheduled_slot": "2026-07-30T18:00:00Z",
        "launch_retry_ordinal": 0,
        "observed_current_utc_timestamp": "2026-07-30T18:00:02Z",
        "acquisition_timestamp_utc": "2026-07-30T18:00:01Z",
        "release_timestamp_utc": "2026-07-30T18:00:03Z",
        "terminal_completed_at_utc": "2026-07-30T18:00:02Z",
        "request_timestamp_utc": "2026-07-30T18:00:00Z",
        "monotonic_duration_nanoseconds": 1_000_000,
        "machine_authority_id": str(UUID(int=2)),
        "boot_session_evidence": "boot-test-1",
        "process_id": 991,
        "process_creation_timestamp_utc": "2026-07-30T18:00:00Z",
        "account_sid": "S-1-5-21-1-2-3-1001",
        "executable_release_evidence": _evidence(3),
        "maximum_runtime_seconds": 600,
        "mutex_timeout_seconds": 3,
        "launch_guard_policy_version": "windows-local-single-writer-v1",
        "acl_mode": "ALLOW_DEFAULT_DACL",
        "market_hours_schedule_artifact": _reference(4, root / "hours.json"),
        "capture_policy_artifact": _reference(5, root / "policy.json"),
        "capture_configuration_artifact": _reference(6, root / "capture.json"),
        "credential_reference_artifact": _reference(7, root / "credential.json"),
        "snapshot_destination": _reference(8, root / "snapshots"),
        "software_release_evidence": _evidence(9),
        "credential_reference_version": "credential-v1",
        "snapshot_capture_request_id": str(REQUEST),
        "allocation_history_policy_version": "attempt-history-v1",
        "allocation_policy_version": "allocation-v1",
        "terminal_policy_version": "terminal-v1",
        "runner_policy_version": "guarded-capture-runner-v1",
        "approved_python_executable": str(root / "python.exe"),
        "approved_python_executable_evidence": _evidence(10),
        "approved_child_script": str(root / "child.py"),
        "approved_child_script_evidence": _evidence(11),
        "process_evidence_directory": str(root / "process"),
        "controlled_temp_directory": str(root / "temp"),
        "termination_grace_seconds": 3,
        "wall_timeout_seconds": 30,
        "manual_disable_active": False,
        "capture_health": {
            "audit_ok": True,
            "disk_watermark_ok": True,
            "backup_ok": True,
            "notification_ok": True,
        },
        "production_xnys_hours_authority": {
            "status": "UNRESOLVED",
            "provenance": None,
            "schedule_evidence": None,
        },
    }


def _load_config(tmp_path: Path) -> GuardedCaptureRunnerConfig:
    path = tmp_path / "runner.json"
    path.write_text(json.dumps(_config_payload(tmp_path)), encoding="utf-8")
    return load_guarded_capture_runner_config(path)


class _NativeMutex:
    def __init__(self, classification: LaunchGuardAcquisitionClassification) -> None:
        self.classification = classification
        self.calls: list[str] = []

    def acquire(self, mutex_name: str, timeout_milliseconds: int) -> NativeMutexAcquire:
        self.calls.append(f"acquire:{mutex_name}:{timeout_milliseconds}")
        handle = (
            object()
            if self.classification is LaunchGuardAcquisitionClassification.ACQUIRED
            else None
        )
        return NativeMutexAcquire(self.classification, handle)

    def release(self, handle: object) -> None:
        self.calls.append("release")

    def close(self, handle: object) -> None:
        self.calls.append("close")


def test_config_loader_accepts_unresolved_authority_without_opening_references(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path)
    assert (
        config.production_xnys_hours_authority.status
        is ProductionXnysHoursAuthorityStatus.UNRESOLVED
    )
    assert config.scheduled_session_id == _load_config(tmp_path).scheduled_session_id
    assert config.scheduled_launch_id == _load_config(tmp_path).scheduled_launch_id
    assert not config.market_hours_schedule_artifact.path.exists()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.update(extra=True),
        lambda value: value.update(nominal_scheduled_slot=1.5),
        lambda value: value.update(symbols=["QQQ", "SPY"]),
    ],
)
def test_config_loader_rejects_nonapproved_schema_variants(
    tmp_path: Path, mutator
) -> None:
    payload = _config_payload(tmp_path)
    mutator(payload)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(GuardedCaptureRunnerConfigError):
        load_guarded_capture_runner_config(path)


def test_config_loader_rejects_duplicate_keys_and_bom(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(GuardedCaptureRunnerConfigError):
        load_guarded_capture_runner_config(path)
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(_config_payload(tmp_path)).encode())
    with pytest.raises(GuardedCaptureRunnerConfigError):
        load_guarded_capture_runner_config(path)


def test_production_hours_authority_requires_official_provenance() -> None:
    with pytest.raises(GuardedCaptureRunnerConfigError):
        ProductionXnysHoursAuthority(
            ProductionXnysHoursAuthorityStatus.VERIFIED,
            "fixture-hours",
            ArtifactEvidence(UUID(int=12), "c" * 64, 12),
        )
    with pytest.raises(GuardedCaptureRunnerConfigError):
        ProductionXnysHoursAuthority(
            ProductionXnysHoursAuthorityStatus.UNRESOLVED,
            None,
            ArtifactEvidence(UUID(int=13), "d" * 64, 13),
        )


@pytest.mark.parametrize(
    ("child", "terminal"),
    [
        (
            IsolatedCaptureChildClassification.CREDENTIAL_REFERENCE_INVALID,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.SID_MISMATCH,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.CREDENTIAL_NOT_FOUND,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.CREDENTIAL_INVALID,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.AUTHENTICATION_FAILED,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.PROVIDER_REJECTED,
            CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
        ),
        (
            IsolatedCaptureChildClassification.NETWORK_FAILED,
            CaptureAttemptTerminalClassification.NETWORK_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.TIMEOUT,
            CaptureAttemptTerminalClassification.TIMEOUT,
        ),
        (
            IsolatedCaptureChildClassification.INCOMPLETE_RESPONSE,
            CaptureAttemptTerminalClassification.INCOMPLETE_RESPONSE,
        ),
        (
            IsolatedCaptureChildClassification.SNAPSHOT_OUTPUT_FAILED,
            CaptureAttemptTerminalClassification.OUTPUT_FAILED,
        ),
        (
            IsolatedCaptureChildClassification.INTERNAL_FAILED,
            CaptureAttemptTerminalClassification.CHILD_CRASHED,
        ),
        (
            IsolatedCaptureChildClassification.SUCCEEDED,
            CaptureAttemptTerminalClassification.SUCCEEDED,
        ),
    ],
)
def test_child_classification_mapping_is_closed(child, terminal) -> None:
    assert terminal_classification_for_child(child) is terminal


@pytest.mark.parametrize(
    "terminal_classification",
    [
        CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
        CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
    ],
)
def test_prior_terminal_retry_policy_blocks_before_readiness(
    tmp_path: Path,
    terminal_classification: CaptureAttemptTerminalClassification,
) -> None:
    config = _load_config(tmp_path)
    terminal_id = UUID(int=20)
    attempt_id = UUID(int=21)
    current_credential = config.credential_reference_artifact.evidence
    historical_credential = ArtifactEvidence(UUID(int=22), "a" * 64, 1)
    history = SimpleNamespace(
        verification=SimpleNamespace(
            head=SimpleNamespace(
                state=AttemptHistoryState.TERMINAL_SELECTED,
                latest_terminal=ArtifactEvidence(terminal_id, "b" * 64, 1),
            )
        ),
        terminals=(
            SimpleNamespace(
                terminal_record_id=terminal_id,
                attempt_id=attempt_id,
                attempt_ordinal=0,
                classification=terminal_classification,
                provider_call_disposition=ProviderCallDisposition.RESPONSE_CONFIRMED,
                completed_at=datetime(2026, 7, 30, 18, 0, tzinfo=UTC),
            ),
        ),
        allocations=(
            SimpleNamespace(
                attempt_id=attempt_id,
                credential_reference=historical_credential,
            ),
        ),
    )
    hours = SimpleNamespace(
        hours_for=lambda _session: SimpleNamespace(
            opens_at=datetime(2026, 7, 30, 19, 0, tzinfo=UTC)
        )
    )
    policy = SimpleNamespace(
        fixed_backoffs_seconds=(0,),
        maximum_attempts=2,
        capture_cutoff_guard_seconds=0,
    )
    decision = _classify_prior_terminal_retry_policy(config, hours, policy, history)
    assert decision.classification is CaptureRetryClassification.MANUAL_REVIEW_REQUIRED
    assert current_credential != historical_credential


@pytest.mark.parametrize(
    (
        "history_state",
        "terminal_classification",
        "backoff_seconds",
        "expected_diagnostic",
        "expected_classification",
    ),
    [
        (
            AttemptHistoryState.TERMINAL_SELECTED,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
            0,
            GuardedCaptureRunnerDiagnostic.RETRY_POLICY_BLOCKED,
            GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
        ),
        (
            AttemptHistoryState.TERMINAL_SELECTED,
            CaptureAttemptTerminalClassification.PROVIDER_REJECTED,
            0,
            GuardedCaptureRunnerDiagnostic.RETRY_POLICY_BLOCKED,
            GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
        ),
        (
            AttemptHistoryState.TERMINAL_SELECTED,
            CaptureAttemptTerminalClassification.AUTHENTICATION_FAILED,
            3600,
            GuardedCaptureRunnerDiagnostic.RETRY_POLICY_BLOCKED,
            GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
        ),
        (
            AttemptHistoryState.TERMINAL_SELECTED,
            CaptureAttemptTerminalClassification.SUCCEEDED,
            0,
            GuardedCaptureRunnerDiagnostic.SUCCESS_TERMINAL_UNSELECTED,
            GuardedCaptureRunnerClassification.MANUAL_REVIEW_REQUIRED,
        ),
        (
            AttemptHistoryState.SUCCESS_SELECTED,
            None,
            0,
            GuardedCaptureRunnerDiagnostic.ATTEMPT_HISTORY_ALREADY_COMPLETED,
            GuardedCaptureRunnerClassification.SUCCEEDED,
        ),
    ],
)
def test_retry_policy_gate_precedes_readiness_allocation_and_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    history_state: AttemptHistoryState,
    terminal_classification: CaptureAttemptTerminalClassification | None,
    backoff_seconds: int,
    expected_diagnostic: GuardedCaptureRunnerDiagnostic,
    expected_classification: GuardedCaptureRunnerClassification,
) -> None:
    config = _load_config(tmp_path)
    terminal_id = UUID(int=30)
    attempt_id = UUID(int=31)
    historical_credential = ArtifactEvidence(UUID(int=32), "a" * 64, 1)
    history = SimpleNamespace(
        verification=SimpleNamespace(
            pointer=SimpleNamespace(),
            head=SimpleNamespace(
                state=history_state,
                latest_terminal=ArtifactEvidence(terminal_id, "b" * 64, 1),
            ),
        ),
        terminals=(
            SimpleNamespace(
                terminal_record_id=terminal_id,
                attempt_id=attempt_id,
                attempt_ordinal=0,
                classification=terminal_classification,
                provider_call_disposition=ProviderCallDisposition.RESPONSE_CONFIRMED,
                completed_at=datetime(2026, 7, 30, 18, 0, tzinfo=UTC),
            ),
        ),
        allocations=(
            SimpleNamespace(
                attempt_id=attempt_id,
                credential_reference=historical_credential,
            ),
        ),
    )
    hours = SimpleNamespace(
        hours_for=lambda _session: SimpleNamespace(
            opens_at=datetime(2026, 7, 30, 19, 0, tzinfo=UTC)
        )
    )
    policy = SimpleNamespace(
        configuration_evidence=config.capture_configuration_artifact.evidence,
        fixed_backoffs_seconds=(backoff_seconds,),
        maximum_attempts=2,
        capture_cutoff_guard_seconds=0,
    )
    readiness_calls: list[object] = []
    allocation_calls: list[object] = []
    child_calls: list[object] = []
    decision_publications: list[object] = []

    class _Ownership:
        released = False
        start_record = SimpleNamespace(record_id=UUID(int=33))

        def release(self, _release_input: object) -> SimpleNamespace:
            self.released = True
            return SimpleNamespace(
                classification=guarded_runner_module.ReleaseOperationalClassification.RELEASED,
                release_record=SimpleNamespace(release_id=UUID(int=34)),
            )

    ownership = _Ownership()
    monkeypatch.setattr(
        guarded_runner_module,
        "acquire_windows_launch_guard",
        lambda *args, **kwargs: SimpleNamespace(
            classification=LaunchGuardAcquisitionClassification.ACQUIRED,
            ownership=ownership,
        ),
    )
    monkeypatch.setattr(
        guarded_runner_module, "_validate_runtime_directories", lambda _config: None
    )
    monkeypatch.setattr(guarded_runner_module, "_load_hours", lambda _config: hours)
    monkeypatch.setattr(guarded_runner_module, "_load_policy", lambda _config: policy)
    monkeypatch.setattr(
        guarded_runner_module, "_verified_payload", lambda *args: b"credential"
    )
    monkeypatch.setattr(
        guarded_runner_module, "_parse_credential", lambda *args: object()
    )
    monkeypatch.setattr(
        guarded_runner_module,
        "load_daily_snapshot_capture_config",
        lambda *args: SimpleNamespace(
            request_id=config.snapshot_capture_request_id,
            symbols=config.symbols,
        ),
    )
    monkeypatch.setattr(guarded_runner_module, "_readiness_attempts", lambda *args: ())
    monkeypatch.setattr(
        guarded_runner_module,
        "scheduled_head_input_from_verified_authority",
        lambda _authority: SimpleNamespace(),
    )
    result = run_guarded_capture_runner(
        config,
        head_verifier=lambda _root: SimpleNamespace(
            classification=guarded_runner_module.LocalLineageHeadClassification.PASS,
            authority=SimpleNamespace(
                pointer=SimpleNamespace(authority_epoch_id=config.authority_epoch_id)
            ),
        ),
        readiness_evaluator=lambda inputs: readiness_calls.append(inputs),
        decision_publisher=lambda *args: decision_publications.append(args),
        history_loader=lambda *args: history,
        allocator=lambda *args: allocation_calls.append(args),
        child_launcher=lambda *args: child_calls.append(args),
    )

    assert result.classification is expected_classification
    assert result.diagnostics[0] == expected_diagnostic
    assert readiness_calls == []
    assert decision_publications == []
    assert allocation_calls == []
    assert child_calls == []
    assert ownership.released is True


def test_guard_contention_returns_without_reading_artifacts(tmp_path: Path) -> None:
    config = _load_config(tmp_path)
    native = _NativeMutex(LaunchGuardAcquisitionClassification.ALREADY_HELD)
    child_calls: list[object] = []
    result = run_guarded_capture_runner(
        config,
        native_api=native,
        child_launcher=lambda *args, **kwargs: child_calls.append(args),
    )
    assert result.classification is GuardedCaptureRunnerClassification.NOT_READY
    assert result.diagnostics == (
        GuardedCaptureRunnerDiagnostic.GUARD_ALREADY_HELD.value,
    )
    assert child_calls == []
    assert not (tmp_path / "root" / "audit").exists()


def test_verified_dacl_requirement_fails_closed_before_native_call(
    tmp_path: Path,
) -> None:
    config = _load_config(tmp_path)
    config = replace(config, acl_mode=LaunchGuardAclPolicy.REQUIRE_VERIFIED_DACL)
    native = _NativeMutex(LaunchGuardAcquisitionClassification.ACQUIRED)
    result = run_guarded_capture_runner(config, native_api=native)
    assert result.classification is GuardedCaptureRunnerClassification.BLOCKED
    assert result.diagnostics == (
        GuardedCaptureRunnerDiagnostic.GUARD_UNSUPPORTED.value,
    )
    assert native.calls == []


def test_allocation_path_is_identity_addressed(tmp_path: Path) -> None:
    session_id = UUID("2e3f4bb8-7b4a-5d12-b7f3-a0b8b0e67c42")
    allocation_id = UUID("3e3f4bb8-7b4a-5d12-b7f3-a0b8b0e67c42")
    assert (
        capture_attempt_allocation_path(tmp_path, session_id, allocation_id)
        == tmp_path
        / str(session_id)
        / "allocations"
        / f"capture-attempt-allocation-{allocation_id}.json"
    )


@pytest.mark.parametrize(
    ("classification", "expected"),
    [
        (GuardedCaptureRunnerClassification.SUCCEEDED, 0),
        (GuardedCaptureRunnerClassification.NOT_READY, 3),
        (GuardedCaptureRunnerClassification.BLOCKED, 4),
        (GuardedCaptureRunnerClassification.FAILED, 5),
        (GuardedCaptureRunnerClassification.AMBIGUOUS, 6),
    ],
)
def test_runner_exit_codes_are_typed(classification, expected) -> None:
    result = GuardedCaptureRunnerResult(UUID(int=14), UUID(int=15), classification, ())
    assert exit_code_for_guarded_capture_runner(result) == expected


def test_runner_reports_unhardened_default_dacl(tmp_path: Path) -> None:
    config = _load_config(tmp_path)
    native = _NativeMutex(LaunchGuardAcquisitionClassification.ALREADY_HELD)
    result = run_guarded_capture_runner(config, native_api=native)
    assert result.default_mutex_dacl_unhardened is True


def test_capture_health_model_is_explicit() -> None:
    assert CaptureOnlyHealthConfig(True, True, True, True).audit_ok is True


def test_reference_requires_absolute_path() -> None:
    with pytest.raises(ValueError):
        ExplicitArtifactReference(
            ArtifactEvidence(UUID(int=16), "e" * 64, 16), Path("relative")
        )


def test_symbols_are_domain_values() -> None:
    assert tuple(map(str, (Symbol("SPY"), Symbol("QQQ")))) == ("SPY", "QQQ")
    assert TradingSession(date(2026, 7, 30)).session_date.isoformat() == "2026-07-30"
