from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading_bot.cli.guarded_capture_readiness_config import (
    GuardedCaptureReadinessConfigError,
    load_guarded_capture_readiness_config,
)
from trading_bot.runtime import ScheduledPhase


def _tree(tmp_path: Path) -> dict[str, object]:
    evidence = {
        "artifact_id": "30000000-0000-0000-0000-000000000001",
        "sha256": "1" * 64,
        "byte_length": 100,
    }
    reference = {**evidence, "path": "input.json"}
    return {
        "schema_version": 1,
        "authority_root": str(tmp_path / "authority"),
        "authority_epoch_id": "30000000-0000-0000-0000-000000000002",
        "scheduler_audit_root": str(tmp_path / "audit"),
        "scheduled_phase": "CAPTURE_READINESS_DRY_RUN",
        "target_session": "2026-07-02",
        "execution_session": "2026-07-06",
        "symbols": ["SPY", "QQQ"],
        "universe_policy_version": "universe-v1",
        "readiness_policy_version": "readiness-v1",
        "selection_policy_version": "selection-v1",
        "nominal_scheduled_slot": "2026-07-02T17:05:00Z",
        "launch_retry_ordinal": 0,
        "observed_current_utc_timestamp": "2026-07-02T17:10:00Z",
        "acquisition_timestamp_utc": "2026-07-02T17:10:01Z",
        "release_timestamp_utc": "2026-07-02T17:10:02Z",
        "monotonic_duration_nanoseconds": 1_000_000_000,
        "machine_authority_id": "30000000-0000-0000-0000-000000000003",
        "boot_session_evidence": "boot-2026-07-30T00:00:00Z",
        "process_id": 4242,
        "process_creation_timestamp_utc": "2026-07-02T17:00:00Z",
        "account_sid": "S-1-5-21-111-222-333-1001",
        "executable_release_evidence": {
            "artifact_id": "30000000-0000-0000-0000-000000000004",
            "sha256": "2" * 64,
            "byte_length": 200,
        },
        "maximum_runtime_seconds": 900,
        "mutex_timeout_seconds": 0,
        "launch_guard_policy_version": "windows-launch-guard-v1",
        "acl_mode": "ALLOW_DEFAULT_DACL",
        "market_hours_schedule_artifact": reference,
        "capture_policy_artifact": {
            **reference,
            "artifact_id": "30000000-0000-0000-0000-000000000005",
            "path": "policy.json",
        },
        "capture_attempt_artifacts": [],
        "snapshot_selection_artifact": None,
        "manual_disable_active": False,
        "capture_health": {
            "audit_ok": True,
            "disk_watermark_ok": True,
            "backup_ok": True,
            "notification_ok": True,
        },
        "runner_policy_version": "capture-readiness-dry-run-v1",
    }


def _write(path: Path, tree: dict[str, object]) -> None:
    path.write_text(json.dumps(tree), encoding="utf-8")


def test_strict_config_loads_and_derives_path_independent_identities(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.json"
    first_tree = _tree(tmp_path)
    _write(first_path, first_tree)
    first = load_guarded_capture_readiness_config(first_path)

    second_path = tmp_path / "second.json"
    second_tree = _tree(tmp_path)
    second_tree["authority_root"] = str(tmp_path / "moved-authority")
    second_tree["scheduler_audit_root"] = str(tmp_path / "moved-audit")
    second_tree["market_hours_schedule_artifact"]["path"] = "moved-hours.json"  # type: ignore[index]
    second_tree["capture_policy_artifact"]["path"] = "moved-policy.json"  # type: ignore[index]
    _write(second_path, second_tree)
    second = load_guarded_capture_readiness_config(second_path)

    assert first.scheduled_phase is ScheduledPhase.CAPTURE_READINESS_DRY_RUN
    assert first.scheduled_session_id == second.scheduled_session_id
    assert first.scheduled_launch_id == second.scheduled_launch_id


@pytest.mark.parametrize(
    "mutation",
    [
        lambda tree: tree.update({"unknown": True}),
        lambda tree: tree.pop("capture_health"),
        lambda tree: tree.update({"launch_retry_ordinal": 0.5}),
        lambda tree: tree.update({"scheduled_phase": "CAPTURE"}),
        lambda tree: tree.update(
            {"observed_current_utc_timestamp": "2026-07-02T17:10:00+00:00"}
        ),
    ],
)
def test_config_rejects_unknown_missing_float_fixed_phase_and_noncanonical_time(
    tmp_path: Path,
    mutation,
) -> None:
    tree = _tree(tmp_path)
    mutation(tree)
    path = tmp_path / "config.json"
    _write(path, tree)

    with pytest.raises(GuardedCaptureReadinessConfigError):
        load_guarded_capture_readiness_config(path)


def test_config_rejects_duplicate_members_and_bom(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = json.dumps(_tree(tmp_path))
    duplicate = payload.replace(
        '"schema_version": 1',
        '"schema_version": 1, "schema_version": 1',
        1,
    )
    path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(GuardedCaptureReadinessConfigError, match="duplicate"):
        load_guarded_capture_readiness_config(path)

    path.write_bytes(b"\xef\xbb\xbf" + payload.encode())
    with pytest.raises(GuardedCaptureReadinessConfigError, match="BOM"):
        load_guarded_capture_readiness_config(path)
