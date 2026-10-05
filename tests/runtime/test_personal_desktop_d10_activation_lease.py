"""Focused Architecture-122 D10 activation-lease model tests."""

from __future__ import annotations

import json
import uuid
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    ACTIVATION_LEASE_SCHEMA,
    D10_ACTIVATION_LEASE_INSTALLING_PATH,
    D10_ACTIVATION_LEASE_PATH,
    D10_ACTIVATION_LEASE_PUBLICATION_CONTRACT,
    D10_ACTIVATION_LEASE_TEMP_PATH,
    D10_LEASE_DURATION,
    D10_SCHEDULER_CONTRACT_ID,
    D10_SOAK_ID_NAMESPACE,
    ActivationLeaseError,
    D10ActivationLease,
    build_activation_lease_model,
    canonical_json_bytes,
    parse_activation_lease,
)

ACTIVATION = datetime(2026, 9, 24, 18, 15, 30, 123456, tzinfo=UTC)


def lease(**changes: object) -> D10ActivationLease:
    values: dict[str, object] = {
        "deployment_id": "12345678-1234-5678-1234-567812345678",
        "attestation_sha256": "a" * 64,
        "accepted_activation_utc": ACTIVATION,
        "certified_source_head": "b" * 40,
        "certified_source_tree": "c" * 40,
    }
    values.update(changes)
    return build_activation_lease_model(**values)  # type: ignore[arg-type]


def test_canonical_round_trip_exact_fields_and_immutable_model() -> None:
    model = lease()
    encoded = model.canonical_bytes()
    assert encoded == canonical_json_bytes(model.to_dict())
    assert parse_activation_lease(encoded) == model
    assert list(json.loads(encoded)) == sorted(model.to_dict())
    with pytest.raises(FrozenInstanceError):
        model.soak_id = "0" * 36  # type: ignore[misc]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.update(unreviewed=True),
        lambda raw: raw.pop("deployment_id"),
        lambda raw: raw.update(accepted_activation_utc="2026-09-24T18:15:30Z"),
        lambda raw: raw.update(
            accepted_activation_utc="2026-09-24T11:15:30.123456-07:00"
        ),
        lambda raw: raw.update(accepted_activation_utc="2026-02-30T18:15:30.123456Z"),
        lambda raw: raw.update(end_utc=True),
        lambda raw: raw.update(attestation_sha256="A" * 64),
        lambda raw: raw.update(soak_id="not-a-uuid"),
    ],
)
def test_extra_missing_and_malformed_fields_are_rejected(mutate) -> None:
    raw = lease().to_dict()
    mutate(raw)
    with pytest.raises(ActivationLeaseError):
        parse_activation_lease(canonical_json_bytes(raw))


def test_duplicate_fields_and_noncanonical_bytes_are_rejected() -> None:
    encoded = lease().canonical_bytes()
    duplicate = encoded.replace(b'"schema":', b'"schema":"other","schema":', 1)
    with pytest.raises(ActivationLeaseError):
        parse_activation_lease(duplicate)
    with pytest.raises(ActivationLeaseError):
        parse_activation_lease(b" " + encoded)


def test_deterministic_soak_identity_binds_all_canonical_facts() -> None:
    original = lease()
    repeated = lease()
    changed_activation = lease(
        accepted_activation_utc=ACTIVATION + timedelta(microseconds=1)
    )
    changed_deployment = lease(deployment_id="22345678-1234-5678-1234-567812345678")
    assert original.soak_id == repeated.soak_id
    assert original.soak_id == original.expected_soak_id()
    assert original.soak_id != changed_activation.soak_id
    assert original.soak_id != changed_deployment.soak_id
    assert uuid.UUID(original.soak_id).version == 5
    assert original.expected_soak_id() == str(
        uuid.uuid5(
            D10_SOAK_ID_NAMESPACE,
            canonical_json_bytes(original.identity_material()).decode("utf-8"),
        )
    )


def test_exact_seven_day_interval_and_utc_only() -> None:
    model = lease()
    assert model.end_utc == ACTIVATION + timedelta(days=7)
    assert D10_LEASE_DURATION == timedelta(days=7)
    with pytest.raises(ActivationLeaseError):
        lease(accepted_activation_utc=datetime(2026, 9, 24, 18, 15, 30))
    with pytest.raises(ActivationLeaseError):
        lease(
            accepted_activation_utc=datetime(
                2026, 9, 24, 18, 15, 30, tzinfo=timezone(timedelta(0), "custom")
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("deployment_id", "not-a-uuid"),
        ("attestation_sha256", "d" * 63),
        ("certified_source_head", "E" * 40),
        ("certified_source_tree", "d" * 39),
        ("scheduler_contract_schema", "other/v1"),
        ("scheduler_contract_id", "0" * 64),
        ("trading_sid", "S-1-5-18"),
        ("production_python", r"F:\wrong\python.exe"),
        ("production_python_version", "3.14.4"),
        ("end_utc", ACTIVATION + timedelta(days=7, microseconds=1)),
    ],
)
def test_invalid_identity_and_runtime_facts_are_rejected(
    field: str, value: object
) -> None:
    with pytest.raises(ActivationLeaseError):
        replace(lease(), **{field: value})


def test_fixed_path_and_create_only_publication_contract() -> None:
    contract = D10_ACTIVATION_LEASE_PUBLICATION_CONTRACT
    assert ACTIVATION_LEASE_SCHEMA == "personal-desktop-d10-activation-lease/v1"
    assert D10_ACTIVATION_LEASE_PATH == (r"F:\AITradingBot\D10\activation.lease.json")
    assert D10_ACTIVATION_LEASE_INSTALLING_PATH.endswith(".installing")
    assert D10_ACTIVATION_LEASE_TEMP_PATH.endswith(".tmp")
    assert contract.final_path == D10_ACTIVATION_LEASE_PATH
    assert contract.installing_path == D10_ACTIVATION_LEASE_INSTALLING_PATH
    assert contract.temporary_path == D10_ACTIVATION_LEASE_TEMP_PATH
    assert contract.protected_dacl
    assert contract.object_kind == "regular_file"
    assert contract.file_system == "NTFS"
    assert contract.local_volume_root == "F:\\"
    assert contract.non_reparse
    assert contract.hard_link_count == 1
    assert contract.administrators_access_mask == 0x001F01FF
    assert contract.system_access_mask == 0x001F01FF
    assert contract.installing_create_disposition == "CREATE_NEW"
    assert contract.temporary_create_disposition == "CREATE_NEW"
    assert contract.final_create_disposition == "CREATE_NEW_IF_ABSENT"
    assert contract.temporary_objects_use_same_protected_dacl
    assert contract.flush_and_verify_before_publish
    assert contract.publish_with_same_directory_atomic_no_replace
    assert not contract.replace_existing_final_allowed
    assert not contract.runtime_writer_enabled
    assert not contract.in_place_renewal_allowed
    assert contract.trading_read_only_mask == 0x00120089
    assert contract.parent_trading_read_only_mask == 0x001200A9
    assert len(D10_SCHEDULER_CONTRACT_ID) == 64
