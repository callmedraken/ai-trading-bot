from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from uuid import UUID

import pytest

from trading_bot.runtime.launch_guard import (
    LaunchGuardAcquisitionClassification,
    LaunchLeaseReleaseClassification,
    LaunchResultClassification,
    create_launch_lease_release,
    create_launch_lease_start,
    derive_launch_lease_start_id,
    lease_start_artifact_reference,
    parse_launch_lease_release,
    parse_launch_lease_start,
    serialize_launch_lease_release,
    serialize_launch_lease_start,
    windows_mutex_name,
)
from trading_bot.runtime.scheduled_readiness import ArtifactEvidence, ScheduledPhase

EPOCH_ID = UUID("8a39e78a-47d8-50b9-a427-c102abc91e1e")
LAUNCH_ID = UUID("89a3184a-05ef-5228-8664-d26f31ed03c9")
MACHINE_ID = UUID("71abfbb7-ae72-54fc-b049-3ea87879dd32")
RELEASE_ARTIFACT_ID = UUID("918a8cd2-b8fd-5334-8df3-b62eab72e311")


def _start():
    return create_launch_lease_start(
        scheduled_launch_id=LAUNCH_ID,
        authority_epoch_id=EPOCH_ID,
        scheduled_phase=ScheduledPhase.OPERATION,
        acquisition_classification=LaunchGuardAcquisitionClassification.ACQUIRED,
        machine_authority_id=MACHINE_ID,
        boot_evidence="boot-2026-07-30T00:00:00Z",
        process_id=4242,
        process_creation_timestamp_utc="2026-07-30T16:00:00Z",
        user_sid="S-1-5-21-111-222-333-1001",
        executable_release=ArtifactEvidence(
            artifact_id=RELEASE_ARTIFACT_ID,
            sha256="7" * 64,
            byte_length=1200,
        ),
        acquisition_timestamp_utc="2026-07-30T16:00:01Z",
        max_runtime_seconds=900,
        launch_policy="windows-local-single-writer-v1",
    )


def _release():
    start = _start()
    return create_launch_lease_release(
        lease_start=start,
        lease_start_reference=lease_start_artifact_reference(start),
        release_classification=LaunchLeaseReleaseClassification.NORMAL,
        release_timestamp_utc="2026-07-30T16:00:02Z",
        monotonic_duration_nanoseconds=1_000_000_000,
        result_classification=LaunchResultClassification.NOT_RUN,
        result_diagnostic="SMOKE_RELEASE",
        process_exit_code=0,
        release_policy="windows-local-single-writer-v1",
    )


def test_mutex_name_is_exact_architecture_name() -> None:
    assert (
        windows_mutex_name(EPOCH_ID)
        == "Global\\AITradingBot.PaperAuthority.8a39e78a-47d8-50b9-a427-c102abc91e1e"
    )


def test_start_golden_identity_bytes_and_digest() -> None:
    start = _start()
    payload = serialize_launch_lease_start(start)

    assert str(start.record_id) == "95706ff2-56b8-5bb1-860e-9e2ac4179a3d"
    assert (
        hashlib.sha256(payload).hexdigest()
        == "d95b0ceeac22b4e9fd4b5b259bf058f6097dea03b46fe7a950465d6be3e2121a"
    )
    assert payload.endswith(b"\n")
    assert parse_launch_lease_start(payload) == start


def test_release_golden_identity_bytes_and_digest() -> None:
    release = _release()
    payload = serialize_launch_lease_release(release)

    assert str(release.release_id) == "190f1034-cd47-525e-92d4-7f89e0241dc4"
    assert (
        hashlib.sha256(payload).hexdigest()
        == "5caf0cbdefa1e0f7e183fae9631cb7dbffde3ea32f4ab36c38bb7f437c61766c"
    )
    assert parse_launch_lease_release(payload) == release


def test_start_identity_changes_when_explicit_evidence_changes() -> None:
    start = _start()
    changed = derive_launch_lease_start_id(
        scheduled_launch_id=start.scheduled_launch_id,
        authority_epoch_id=start.authority_epoch_id,
        scheduled_phase=start.scheduled_phase,
        mutex_name=start.mutex_name,
        acquisition_classification=start.acquisition_classification,
        machine_authority_id=start.machine_authority_id,
        boot_evidence=start.boot_evidence,
        process_id=start.process_id + 1,
        process_creation_timestamp_utc=start.process_creation_timestamp_utc,
        user_sid=start.user_sid,
        executable_release=start.executable_release,
        acquisition_timestamp_utc=start.acquisition_timestamp_utc,
        max_runtime_seconds=start.max_runtime_seconds,
        launch_policy=start.launch_policy,
    )

    assert changed != start.record_id


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload[:-1],
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda payload: payload.replace(b'"schema_version":1', b'"schema_version":1.0'),
        lambda payload: payload.replace(
            b'"schema_version":1',
            b'"schema_version":1,"unexpected":true',
        ),
    ],
)
def test_start_parser_rejects_noncanonical_or_unexpected_json(mutation) -> None:
    with pytest.raises(ValueError):
        parse_launch_lease_start(mutation(serialize_launch_lease_start(_start())))


def test_start_parser_rejects_duplicate_members() -> None:
    document = json.loads(serialize_launch_lease_start(_start()))
    body = json.dumps(document, sort_keys=True, separators=(",", ":"))
    duplicate = ('{"schema_version":1,' + body[1:]).encode("ascii") + b"\n"

    with pytest.raises(ValueError, match="duplicate"):
        parse_launch_lease_start(duplicate)


def test_model_rejects_mismatched_identity() -> None:
    start = _start()
    with pytest.raises(ValueError, match="record_id"):
        replace(start, record_id=UUID("b46ae17c-f0e9-5300-a9f5-e20c581d1e99"))


def test_release_reference_is_exact_start_bytes() -> None:
    start = _start()
    reference = lease_start_artifact_reference(start)

    assert reference.record_id == start.record_id
    assert (
        reference.sha256
        == hashlib.sha256(serialize_launch_lease_start(start)).hexdigest()
    )
    assert reference.byte_length == len(serialize_launch_lease_start(start))


def test_release_creation_rejects_wrong_start_reference() -> None:
    start = _start()
    reference = replace(lease_start_artifact_reference(start), sha256="0" * 64)

    with pytest.raises(ValueError, match="does not match"):
        create_launch_lease_release(
            lease_start=start,
            lease_start_reference=reference,
            release_classification=LaunchLeaseReleaseClassification.NORMAL,
            release_timestamp_utc="2026-07-30T16:00:02Z",
            monotonic_duration_nanoseconds=1,
            result_classification=LaunchResultClassification.NOT_RUN,
            result_diagnostic="SMOKE_RELEASE",
            process_exit_code=None,
            release_policy="windows-local-single-writer-v1",
        )
