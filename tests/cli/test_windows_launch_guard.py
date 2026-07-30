from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID

import pytest

from trading_bot.cli.checkpoint_transition_output import OutputParent
from trading_bot.cli.windows_launch_guard import (
    EvidencePublicationClassification,
    LaunchGuardAclPolicy,
    LaunchGuardAcquireRequest,
    LaunchGuardEvidenceError,
    LaunchGuardLifecycleError,
    LaunchLeaseReleaseInput,
    NativeMutexAcquire,
    ReleaseOperationalClassification,
    acquire_windows_launch_guard,
    diagnostic_from_ownership,
    publish_launch_lease_start,
)
from trading_bot.runtime.launch_guard import (
    LaunchGuardAcquisitionClassification,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence, ScheduledPhase

EPOCH_ID = UUID("f81cf9a0-c1f6-54bd-94a6-24e56b70dbe1")
LAUNCH_ID = UUID("a753141d-5739-5995-a72c-a7aafb497de7")
MACHINE_ID = UUID("99855211-3924-531a-bfbc-a91827bcc17c")
EXECUTABLE_ID = UUID("e52f154a-3fd9-56c3-a04f-046237d97f0a")


class FakeMutexApi:
    def __init__(
        self,
        classification: LaunchGuardAcquisitionClassification,
        *,
        native_error_code: int | None = None,
        fail_release: bool = False,
        fail_close: bool = False,
        evidence_root: Path | None = None,
    ) -> None:
        self.classification = classification
        self.native_error_code = native_error_code
        self.fail_release = fail_release
        self.fail_close = fail_close
        self.evidence_root = evidence_root
        self.handle = object()
        self.calls: list[tuple[object, ...]] = []

    def acquire(self, mutex_name: str, timeout_milliseconds: int):
        self.calls.append(("acquire", mutex_name, timeout_milliseconds))
        acquired = self.classification in {
            LaunchGuardAcquisitionClassification.ACQUIRED,
            LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED,
        }
        return NativeMutexAcquire(
            self.classification,
            self.handle if acquired else None,
            self.native_error_code,
        )

    def release(self, handle: object) -> None:
        assert handle is self.handle
        if self.evidence_root is not None:
            assert list(
                (self.evidence_root / "lock-events").glob("launch-lease-release-*.json")
            )
        self.calls.append(("release",))
        if self.fail_release:
            raise OSError("release failed")

    def close(self, handle: object) -> None:
        assert handle is self.handle
        self.calls.append(("close",))
        if self.fail_close:
            raise OSError("close failed")


def _release_input() -> LaunchLeaseReleaseInput:
    return LaunchLeaseReleaseInput(
        release_classification=LaunchLeaseReleaseClassification.NORMAL,
        release_timestamp_utc="2026-07-30T18:00:02Z",
        monotonic_duration_nanoseconds=1_000_000,
        result_classification=LaunchResultClassification.NOT_RUN,
        result_diagnostic="SMOKE_RELEASE",
        process_exit_code=0,
        release_policy="windows-local-single-writer-v1",
    )


def _request(
    root: Path,
    *,
    acl_policy: LaunchGuardAclPolicy = LaunchGuardAclPolicy.ALLOW_DEFAULT_DACL,
    context: bool = False,
) -> LaunchGuardAcquireRequest:
    return LaunchGuardAcquireRequest(
        audit_root=root,
        scheduled_launch_id=LAUNCH_ID,
        authority_epoch_id=EPOCH_ID,
        scheduled_phase=ScheduledPhase.OPERATION,
        machine_authority_id=MACHINE_ID,
        boot_evidence="boot-test-001",
        process_id=991,
        process_creation_timestamp_utc="2026-07-30T18:00:00Z",
        user_sid="S-1-5-21-1-2-3-1001",
        executable_release=ArtifactEvidence(
            artifact_id=EXECUTABLE_ID,
            sha256="4" * 64,
            byte_length=123,
        ),
        acquisition_timestamp_utc="2026-07-30T18:00:01Z",
        max_runtime_seconds=600,
        launch_policy="windows-local-single-writer-v1",
        timeout_seconds=3,
        acl_policy=acl_policy,
        context_release_input=_release_input() if context else None,
    )


def test_acquisition_publishes_start_then_release_before_native_release(
    tmp_path: Path,
) -> None:
    api = FakeMutexApi(
        LaunchGuardAcquisitionClassification.ACQUIRED,
        evidence_root=tmp_path,
    )

    acquired = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert acquired.classification is LaunchGuardAcquisitionClassification.ACQUIRED
    assert acquired.ownership is not None
    assert api.calls[0][0] == "acquire"
    assert api.calls[0][2] == 3000
    start_paths = list((tmp_path / "lock-events").glob("launch-lease-start-*.json"))
    assert len(start_paths) == 1

    released = acquired.ownership.release(_release_input())

    assert released.classification is ReleaseOperationalClassification.RELEASED
    assert api.calls[-2:] == [("release",), ("close",)]
    assert released.publication is not None
    assert released.publication.path.exists()
    assert acquired.ownership.released is True
    diagnostic = diagnostic_from_ownership(acquired.ownership)
    assert diagnostic.released is True
    assert diagnostic.lease_start.record_id == acquired.ownership.start_record.record_id
    assert diagnostic.lease_release is not None
    assert diagnostic.lease_release.record_id == released.release_record.release_id


@pytest.mark.parametrize(
    ("classification", "error"),
    [
        (LaunchGuardAcquisitionClassification.ALREADY_HELD, None),
        (LaunchGuardAcquisitionClassification.ACCESS_DENIED, 5),
        (LaunchGuardAcquisitionClassification.UNSUPPORTED, None),
        (LaunchGuardAcquisitionClassification.ERROR, 87),
    ],
)
def test_nonacquired_classifications_publish_no_evidence(
    tmp_path: Path,
    classification: LaunchGuardAcquisitionClassification,
    error: int | None,
) -> None:
    api = FakeMutexApi(classification, native_error_code=error)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is classification
    assert result.ownership is None
    assert result.native_error_code == error
    assert not (tmp_path / "lock-events").exists()
    assert len(api.calls) == 1


def test_abandoned_acquisition_is_held_but_explicitly_unsafe(tmp_path: Path) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert (
        result.classification is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
    )
    assert result.diagnostic == "ABANDONED_OWNER_MANUAL_REVIEW_REQUIRED"
    assert result.ownership is not None
    assert (
        result.ownership.start_record.acquisition_classification
        is LaunchGuardAcquisitionClassification.ABANDONED_ACQUIRED
    )
    released = result.ownership.release(_release_input())
    assert released.classification is ReleaseOperationalClassification.RELEASED


def test_start_publication_failure_releases_and_closes_mutex(tmp_path: Path) -> None:
    events = tmp_path / "lock-events"
    events.mkdir()
    (events / ".crash-left.staging").write_bytes(b"preserve")
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is LaunchGuardAcquisitionClassification.ERROR
    assert result.ownership is None
    assert result.diagnostic.startswith("START_PUBLICATION_FAILED")
    assert api.calls[-2:] == [("release",), ("close",)]
    assert (events / ".crash-left.staging").read_bytes() == b"preserve"


def test_start_construction_failure_releases_and_closes_mutex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.cli.windows_launch_guard as module

    def fail_construction(**_kwargs):
        raise ValueError("injected construction failure")

    monkeypatch.setattr(module, "create_launch_lease_start", fail_construction)
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is LaunchGuardAcquisitionClassification.ERROR
    assert result.ownership is None
    assert result.diagnostic.startswith("START_CONSTRUCTION_FAILED:ValueError")
    assert api.calls[-2:] == [("release",), ("close",)]


def test_release_publication_failure_still_releases_and_closes(
    tmp_path: Path,
) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)
    acquired = acquire_windows_launch_guard(_request(tmp_path), native_api=api)
    assert acquired.ownership is not None
    (tmp_path / "lock-events" / "unexpected.entry").write_bytes(b"preserve")

    released = acquired.ownership.release(_release_input())

    assert (
        released.classification
        is ReleaseOperationalClassification.EVIDENCE_PUBLICATION_FAILED
    )
    assert released.manual_review_required is True
    assert api.calls[-2:] == [("release",), ("close",)]
    assert (tmp_path / "lock-events" / "unexpected.entry").exists()


def test_native_release_failure_is_manual_review(tmp_path: Path) -> None:
    api = FakeMutexApi(
        LaunchGuardAcquisitionClassification.ACQUIRED,
        fail_release=True,
    )
    acquired = acquire_windows_launch_guard(_request(tmp_path), native_api=api)
    assert acquired.ownership is not None

    released = acquired.ownership.release(_release_input())

    assert (
        released.classification
        is ReleaseOperationalClassification.NATIVE_RELEASE_FAILED
    )
    assert released.manual_review_required is True
    assert api.calls[-1] == ("close",)


def test_release_exactly_once_and_reject_use_after_release(tmp_path: Path) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)
    acquired = acquire_windows_launch_guard(_request(tmp_path), native_api=api)
    assert acquired.ownership is not None

    acquired.ownership.release(_release_input())

    with pytest.raises(LaunchGuardLifecycleError, match="already"):
        acquired.ownership.release(_release_input())
    with pytest.raises(LaunchGuardLifecycleError, match="already"):
        acquired.ownership.__enter__()
    assert api.calls.count(("release",)) == 1
    assert api.calls.count(("close",)) == 1


def test_public_ownership_object_is_frozen(tmp_path: Path) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)
    acquired = acquire_windows_launch_guard(_request(tmp_path), native_api=api)
    assert acquired.ownership is not None

    with pytest.raises(FrozenInstanceError):
        acquired.ownership._state = acquired.ownership._state  # type: ignore[misc]

    acquired.ownership.release(_release_input())


def test_context_manager_uses_supplied_explicit_release_evidence(
    tmp_path: Path,
) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)
    acquired = acquire_windows_launch_guard(
        _request(tmp_path, context=True),
        native_api=api,
    )
    assert acquired.ownership is not None

    with acquired.ownership as held:
        assert held.released is False

    assert acquired.ownership.released is True
    assert api.calls[-2:] == [("release",), ("close",)]


def test_publication_is_idempotent_for_identical_bytes(tmp_path: Path) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)
    acquired = acquire_windows_launch_guard(_request(tmp_path), native_api=api)
    assert acquired.ownership is not None

    second = publish_launch_lease_start(
        tmp_path,
        acquired.ownership.start_record,
    )

    assert second.classification is EvidencePublicationClassification.IDEMPOTENT
    acquired.ownership.release(_release_input())


def test_verified_acl_requirement_fails_closed_without_native_call(
    tmp_path: Path,
) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(
        _request(tmp_path, acl_policy=LaunchGuardAclPolicy.REQUIRE_VERIFIED_DACL),
        native_api=api,
    )

    assert result.classification is LaunchGuardAcquisitionClassification.UNSUPPORTED
    assert result.diagnostic == "VERIFIED_DACL_NOT_IMPLEMENTED"
    assert api.calls == []


def test_lock_events_casefold_collision_fails_closed(
    tmp_path: Path,
) -> None:
    (tmp_path / "LOCK-EVENTS").mkdir()
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is LaunchGuardAcquisitionClassification.ERROR
    assert result.ownership is None
    assert api.calls[-2:] == [("release",), ("close",)]
    assert (tmp_path / "LOCK-EVENTS").exists()


def test_simulated_reparse_staging_fails_closed_and_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.cli.windows_launch_guard as module

    monkeypatch.setattr(module, "_is_reparse", lambda _info: True)
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is LaunchGuardAcquisitionClassification.ERROR
    assert api.calls[-2:] == [("release",), ("close",)]
    assert len(list((tmp_path / "lock-events").glob(".*.staging"))) == 1


def test_conflicting_final_artifact_is_preserved_and_fails_closed(
    tmp_path: Path,
) -> None:
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)
    first = acquire_windows_launch_guard(_request(tmp_path), native_api=api)
    assert first.ownership is not None
    record = first.ownership.start_record
    first.ownership.release(_release_input())
    final = tmp_path / "lock-events" / f"launch-lease-start-{record.record_id}.json"
    final.write_bytes(b"conflicting bytes")

    with pytest.raises(LaunchGuardEvidenceError):
        publish_launch_lease_start(tmp_path, record)
    assert final.read_bytes() == b"conflicting bytes"


def test_parent_identity_change_preserves_staging_and_releases_mutex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import trading_bot.cli.windows_launch_guard as module

    original = module.validate_output_parent
    event_validations = 0

    def changing_identity(path: Path) -> OutputParent:
        nonlocal event_validations
        result = original(path)
        if path.name == "lock-events":
            event_validations += 1
            if event_validations >= 2:
                return OutputParent(result.path, result.device, result.inode + 1)
        return result

    monkeypatch.setattr(module, "validate_output_parent", changing_identity)
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is LaunchGuardAcquisitionClassification.ERROR
    assert api.calls[-2:] == [("release",), ("close",)]
    staging = list((tmp_path / "lock-events").glob(".*.staging"))
    assert len(staging) == 1
    assert staging[0].stat().st_size > 0


def test_reparse_lock_events_is_rejected_when_symlinks_are_available(
    tmp_path: Path,
) -> None:
    target = tmp_path / "real-events"
    target.mkdir()
    try:
        (tmp_path / "lock-events").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    api = FakeMutexApi(LaunchGuardAcquisitionClassification.ACQUIRED)

    result = acquire_windows_launch_guard(_request(tmp_path), native_api=api)

    assert result.classification is LaunchGuardAcquisitionClassification.ERROR
    assert api.calls[-2:] == [("release",), ("close",)]
