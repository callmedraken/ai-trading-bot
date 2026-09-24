"""Canonical, source-owned Architecture-122 D10 activation-lease model."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, fields
from datetime import UTC, datetime, time, timedelta
from pathlib import PureWindowsPath

from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as scheduler_contract,
)
from trading_bot.runtime.personal_desktop_d10_python_substrate import VERSION

ACTIVATION_LEASE_SCHEMA = "personal-desktop-d10-activation-lease/v1"
D10_ACTIVATION_LEASE_PATH = r"F:\AITradingBot\D10\activation.lease.json"
D10_ACTIVATION_LEASE_INSTALLING_PATH = D10_ACTIVATION_LEASE_PATH + ".installing"
D10_ACTIVATION_LEASE_TEMP_PATH = D10_ACTIVATION_LEASE_PATH + ".tmp"
D10_SOAK_ID_NAMESPACE = uuid.UUID("b33bd736-2dc4-5c7f-9f71-b38fdd392521")
D10_LEASE_DURATION = timedelta(days=7)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID = re.compile(r"[0-9a-f]{40}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z"
)
_LEASE_FIELDS = frozenset(
    {
        "schema",
        "deployment_id",
        "attestation_sha256",
        "accepted_activation_utc",
        "end_utc",
        "certified_source_head",
        "certified_source_tree",
        "scheduler_contract_schema",
        "scheduler_contract_id",
        "trading_sid",
        "production_python",
        "production_python_version",
        "soak_id",
    }
)


class ActivationLeaseError(ValueError):
    """Canonical D10 activation-lease facts violate the frozen contract."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize the exact UTF-8, sorted-key, compact D10 JSON form."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (UnicodeError, TypeError, ValueError) as exc:
        raise ActivationLeaseError(
            "lease cannot be represented as canonical JSON"
        ) from exc


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ActivationLeaseError("lease has duplicate JSON fields")
        result[key] = value
    return result


def _parse_json(data: bytes) -> dict[str, object]:
    if type(data) is not bytes:
        raise ActivationLeaseError("lease input must be bytes")
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ActivationLeaseError("lease has non-finite JSON values")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ActivationLeaseError("lease JSON is malformed") from exc
    if type(value) is not dict:
        raise ActivationLeaseError("lease JSON root must be an object")
    if frozenset(value) != _LEASE_FIELDS:
        raise ActivationLeaseError("lease field set is not exact")
    return value


def format_utc_instant(value: datetime) -> str:
    """Return the fixed six-digit UTC timestamp representation."""
    if (
        type(value) is not datetime
        or value.tzinfo is not UTC
        or value.utcoffset() != timedelta(0)
    ):
        raise ActivationLeaseError("lease timestamps must use datetime.UTC")
    return (
        f"{value.year:04d}-{value.month:02d}-{value.day:02d}T"
        f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}."
        f"{value.microsecond:06d}Z"
    )


def parse_utc_instant(value: object) -> datetime:
    """Parse one exact canonical, timezone-aware UTC instant."""
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        raise ActivationLeaseError("lease timestamp is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ActivationLeaseError("lease timestamp is invalid") from exc
    if format_utc_instant(parsed) != value:
        raise ActivationLeaseError("lease timestamp is not canonical UTC")
    return parsed


def _scheduler_contract_value(value: object) -> object:
    if type(value) is PureWindowsPath:
        return str(value)
    if type(value) is tuple:
        return [_scheduler_contract_value(item) for item in value]
    if type(value) is time:
        return value.isoformat(timespec="microseconds")
    if type(value) is timedelta:
        micros = (value.days * 86400 + value.seconds) * 1_000_000 + value.microseconds
        return {"microseconds": micros}
    if value is None or type(value) in (str, bool, int):
        return value
    raise ActivationLeaseError("scheduler contract contains an unsupported value")


def scheduler_contract_identity() -> str:
    """Hash every frozen scheduler-contract field in canonical name order."""
    if not scheduler_contract.is_frozen_one_week_soak_scheduler_contract(
        scheduler_contract.D10_SCHEDULER_CONTRACT
    ):
        raise ActivationLeaseError("D10 scheduler contract is not frozen")
    material = {
        field.name: _scheduler_contract_value(
            getattr(scheduler_contract.D10_SCHEDULER_CONTRACT, field.name)
        )
        for field in fields(scheduler_contract.D10_SCHEDULER_CONTRACT)
    }
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


D10_SCHEDULER_CONTRACT_ID = scheduler_contract_identity()


@dataclass(frozen=True, slots=True)
class D10ActivationLease:
    """Immutable deployment-bound activation authority and audit facts."""

    schema: str
    deployment_id: str
    attestation_sha256: str
    accepted_activation_utc: datetime
    end_utc: datetime
    certified_source_head: str
    certified_source_tree: str
    scheduler_contract_schema: str
    scheduler_contract_id: str
    trading_sid: str
    production_python: str
    production_python_version: str
    soak_id: str

    def __post_init__(self) -> None:
        if type(self.schema) is not str or self.schema != ACTIVATION_LEASE_SCHEMA:
            raise ActivationLeaseError("unsupported activation-lease schema")
        if (
            type(self.deployment_id) is not str
            or _UUID.fullmatch(self.deployment_id) is None
            or str(uuid.UUID(self.deployment_id)) != self.deployment_id
        ):
            raise ActivationLeaseError("deployment ID is not a canonical UUID")
        if (
            type(self.attestation_sha256) is not str
            or _SHA256.fullmatch(self.attestation_sha256) is None
        ):
            raise ActivationLeaseError("attestation digest is not lowercase SHA-256")
        format_utc_instant(self.accepted_activation_utc)
        format_utc_instant(self.end_utc)
        try:
            expected_end = self.accepted_activation_utc + D10_LEASE_DURATION
        except OverflowError as exc:
            raise ActivationLeaseError("activation timestamp is out of range") from exc
        if self.end_utc != expected_end:
            raise ActivationLeaseError("lease end is not exactly seven calendar days")
        for value in (self.certified_source_head, self.certified_source_tree):
            if type(value) is not str or _GIT_OID.fullmatch(value) is None:
                raise ActivationLeaseError("certified source identity is malformed")
        if (
            type(self.scheduler_contract_schema) is not str
            or self.scheduler_contract_schema
            != scheduler_contract.D10_SCHEDULER_CONTRACT_SCHEMA
            or type(self.scheduler_contract_id) is not str
            or self.scheduler_contract_id != D10_SCHEDULER_CONTRACT_ID
        ):
            raise ActivationLeaseError("scheduler contract identity differs")
        if (
            type(self.trading_sid) is not str
            or self.trading_sid
            != scheduler_contract.D10_SCHEDULER_CONTRACT.principal_sid
            or type(self.production_python) is not str
            or self.production_python
            != str(scheduler_contract.D10_SCHEDULER_CONTRACT.production_interpreter)
            or type(self.production_python_version) is not str
            or self.production_python_version != VERSION
        ):
            raise ActivationLeaseError("lease principal or Python identity differs")
        if (
            type(self.soak_id) is not str
            or _UUID.fullmatch(self.soak_id) is None
            or str(uuid.UUID(self.soak_id)) != self.soak_id
            or self.soak_id != self.expected_soak_id()
        ):
            raise ActivationLeaseError("soak identity differs from canonical facts")

    def identity_material(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "deployment_id": self.deployment_id,
            "attestation_sha256": self.attestation_sha256,
            "accepted_activation_utc": format_utc_instant(self.accepted_activation_utc),
            "end_utc": format_utc_instant(self.end_utc),
            "certified_source_head": self.certified_source_head,
            "certified_source_tree": self.certified_source_tree,
            "scheduler_contract_schema": self.scheduler_contract_schema,
            "scheduler_contract_id": self.scheduler_contract_id,
            "trading_sid": self.trading_sid,
            "production_python": self.production_python,
            "production_python_version": self.production_python_version,
        }

    def expected_soak_id(self) -> str:
        return str(
            uuid.uuid5(
                D10_SOAK_ID_NAMESPACE,
                canonical_json_bytes(self.identity_material()).decode("utf-8"),
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {**self.identity_material(), "soak_id": self.soak_id}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def attestation_digest(self) -> str:
        return self.attestation_sha256


def build_activation_lease_model(
    *,
    deployment_id: str,
    attestation_sha256: str,
    accepted_activation_utc: datetime,
    certified_source_head: str,
    certified_source_tree: str,
) -> D10ActivationLease:
    """Build canonical facts after A4 provenance is checked by its caller."""
    if type(accepted_activation_utc) is not datetime:
        raise ActivationLeaseError("accepted activation must be a datetime")
    try:
        end_utc = accepted_activation_utc + D10_LEASE_DURATION
    except OverflowError as exc:
        raise ActivationLeaseError("activation timestamp is out of range") from exc
    values = {
        "schema": ACTIVATION_LEASE_SCHEMA,
        "deployment_id": deployment_id,
        "attestation_sha256": attestation_sha256,
        "accepted_activation_utc": accepted_activation_utc,
        "end_utc": end_utc,
        "certified_source_head": certified_source_head,
        "certified_source_tree": certified_source_tree,
        "scheduler_contract_schema": scheduler_contract.D10_SCHEDULER_CONTRACT_SCHEMA,
        "scheduler_contract_id": D10_SCHEDULER_CONTRACT_ID,
        "trading_sid": scheduler_contract.D10_SCHEDULER_CONTRACT.principal_sid,
        "production_python": str(
            scheduler_contract.D10_SCHEDULER_CONTRACT.production_interpreter
        ),
        "production_python_version": VERSION,
    }
    identity_material = {
        **values,
        "accepted_activation_utc": format_utc_instant(accepted_activation_utc),
        "end_utc": format_utc_instant(end_utc),
    }
    soak_id = str(
        uuid.uuid5(
            D10_SOAK_ID_NAMESPACE,
            canonical_json_bytes(identity_material).decode("utf-8"),
        )
    )
    return D10ActivationLease(**values, soak_id=soak_id)


def parse_activation_lease(data: bytes) -> D10ActivationLease:
    """Parse one exact canonical lease; reject duplicate, extra, or malformed data."""
    value = _parse_json(data)
    model = D10ActivationLease(
        schema=value["schema"],
        deployment_id=value["deployment_id"],
        attestation_sha256=value["attestation_sha256"],
        accepted_activation_utc=parse_utc_instant(value["accepted_activation_utc"]),
        end_utc=parse_utc_instant(value["end_utc"]),
        certified_source_head=value["certified_source_head"],
        certified_source_tree=value["certified_source_tree"],
        scheduler_contract_schema=value["scheduler_contract_schema"],
        scheduler_contract_id=value["scheduler_contract_id"],
        trading_sid=value["trading_sid"],
        production_python=value["production_python"],
        production_python_version=value["production_python_version"],
        soak_id=value["soak_id"],
    )
    if model.canonical_bytes() != data:
        raise ActivationLeaseError("lease bytes are not canonical")
    return model


@dataclass(frozen=True, slots=True)
class D10ActivationLeasePublicationContract:
    """Protected P124-5 create-once publication rules; no writer is provided."""

    schema: str
    final_path: str
    installing_path: str
    temporary_path: str
    owner_sid: str
    protected_dacl: bool
    object_kind: str
    file_system: str
    local_volume_root: str
    non_reparse: bool
    hard_link_count: int
    administrators_access_mask: int
    system_access_mask: int
    trading_read_only_mask: int
    parent_trading_read_only_mask: int
    installing_create_disposition: str
    temporary_create_disposition: str
    final_create_disposition: str
    temporary_objects_use_same_protected_dacl: bool
    flush_and_verify_before_publish: bool
    publish_with_same_directory_atomic_no_replace: bool
    replace_existing_final_allowed: bool
    runtime_writer_enabled: bool
    in_place_renewal_allowed: bool


D10_ACTIVATION_LEASE_PUBLICATION_CONTRACT = D10ActivationLeasePublicationContract(
    schema="personal-desktop-d10-activation-lease-publication/v1",
    final_path=D10_ACTIVATION_LEASE_PATH,
    installing_path=D10_ACTIVATION_LEASE_INSTALLING_PATH,
    temporary_path=D10_ACTIVATION_LEASE_TEMP_PATH,
    owner_sid="S-1-5-32-544",
    protected_dacl=True,
    object_kind="regular_file",
    file_system="NTFS",
    local_volume_root="F:\\",
    non_reparse=True,
    hard_link_count=1,
    administrators_access_mask=0x001F01FF,
    system_access_mask=0x001F01FF,
    trading_read_only_mask=0x00120089,
    parent_trading_read_only_mask=0x001200A9,
    installing_create_disposition="CREATE_NEW",
    temporary_create_disposition="CREATE_NEW",
    final_create_disposition="CREATE_NEW_IF_ABSENT",
    temporary_objects_use_same_protected_dacl=True,
    flush_and_verify_before_publish=True,
    publish_with_same_directory_atomic_no_replace=True,
    replace_existing_final_allowed=False,
    runtime_writer_enabled=False,
    in_place_renewal_allowed=False,
)
