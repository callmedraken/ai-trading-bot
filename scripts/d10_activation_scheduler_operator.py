"""P124-5 protected operator: scheduler first, lease publication last.

Import is inert. Public host entry points accept no identities, paths, times,
credentials, or scheduler semantics. Tests inject only private fake boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol

# Authority imports must follow this source-owned bootstrap, including scripts
# imports that transitively import trading_bot. No cwd/env/Git source is used.
_OPERATOR_FILE = Path(__file__)
if not _OPERATOR_FILE.is_absolute():
    raise RuntimeError("operator_source_path_not_absolute")
_OPERATOR_REPO_ROOT = _OPERATOR_FILE.resolve(strict=True).parent.parent
_OPERATOR_SOURCE_ROOT = _OPERATOR_REPO_ROOT / "src"
_OPERATOR_SCRIPTS_ROOT = _OPERATOR_REPO_ROOT / "scripts"
sys.path.insert(0, str(_OPERATOR_REPO_ROOT))
sys.path.insert(0, str(_OPERATOR_SOURCE_ROOT))

# ruff: noqa: E402 -- fixed source bootstrap must precede authority imports.
from scripts import d10_protected_deployment as d
from scripts import d10_protected_replacement as replacement
from scripts.d10_protected_deployment_windows import (
    WindowsActivationLeaseBackend,
    WindowsCngVerifier,
)
from scripts.d10_protected_replacement_windows import (
    POWERSHELL,
    SchedulerObservation,
    WindowsD10ReadOnlyReader,
    frozen_d5_scheduler_semantics,
    observe_d5_scheduler,
)
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as schedule,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10_ACTIVATION_LEASE_PUBLICATION_CONTRACT as PUBLICATION,
)
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10ActivationLease,
    build_activation_lease_model,
    canonical_json_bytes,
    format_utc_instant,
    parse_activation_lease,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_LAUNCHER_RELATIVE_PATH,
    parse_deployment_attestation,
    parse_executable_manifest,
)

D10_GUARD_ARGUMENTS = schedule.D10_GUARD_ARGUMENTS
OneWeekSoakSchedulerDeploymentSpec = schedule.OneWeekSoakSchedulerDeploymentSpec
build_one_week_soak_scheduler_deployment_spec = (
    schedule.build_one_week_soak_scheduler_deployment_spec
)

SCHEMA = "personal-desktop-p124-5-operator/v1"
SCHEDULER_SCHEMA = "p1245-task-scheduler-com-observation/v1"
UPDATE_SCHEMA = "p1245-task-scheduler-update/v1"
OBSERVE_HELPER = Path(__file__).with_name("d10_p1245_scheduler_observe.ps1")
UPDATE_HELPER = Path(__file__).with_name("d10_p1245_scheduler_update.ps1")
MAX_TRANSPORT = 16 * 1024
MAX_LEASE = 64 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LEASE_PATHS = (
    PUBLICATION.final_path,
    PUBLICATION.installing_path,
    PUBLICATION.temporary_path,
)
_RESERVED = (
    d.D10_CACHE_PREFIX,
    d.D10_GUARD + ".installing",
    d.D10_SOURCE + ".installing",
    *d.TRUST_INSTALLING_PATHS,
)


class OperatorBlocked(RuntimeError):
    """Only source-owned stage labels may appear in operator evidence."""


# Capture the actual imported modules, including transitive contract/transport
# dependencies, so replacing sys.modules cannot hide a foreign loaded binding.
_GOVERNED_AUTHORITY_MODULES = (
    "trading_bot",
    "trading_bot.runtime",
    "trading_bot.runtime.personal_desktop_d10_activation_lease",
    "trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract",
    "trading_bot.runtime.personal_desktop_unattended_scheduler_contract",
    "trading_bot.runtime.personal_desktop_unattended_capture_warmup_scheduler_contract",
    "trading_bot.runtime.personal_desktop_d10_deployment_identity",
    "trading_bot.runtime.personal_desktop_d10_python_substrate",
    "trading_bot.runtime.personal_desktop_unattended_one_week_soak_window",
)
_SCRIPT_AUTHORITY_MODULES = (
    "scripts",
    "scripts.d10_protected_deployment",
    "scripts.d10_protected_replacement",
    "scripts.d10_protected_deployment_windows",
    "scripts.d10_protected_replacement_windows",
    "scripts.build_d10_deployment_identity",
)
_SOURCE_PROVENANCE = tuple(
    (name, sys.modules[name], root)
    for names, root in (
        (_GOVERNED_AUTHORITY_MODULES, _OPERATOR_SOURCE_ROOT),
        (_SCRIPT_AUTHORITY_MODULES, _OPERATOR_SCRIPTS_ROOT),
    )
    for name in names
)


def _require_source_provenance() -> None:
    """Reject missing, foreign, or replaced authority modules before host entry."""
    try:
        for name, module, root in _SOURCE_PROVENANCE:
            filename = getattr(module, "__file__", None)
            if sys.modules.get(name) is not module or type(filename) is not str:
                raise OperatorBlocked("operator_source_provenance_mismatch")
            path = Path(filename)
            if not path.is_absolute():
                raise OperatorBlocked("operator_source_provenance_mismatch")
            resolved = path.resolve(strict=True)
            if not resolved.is_file() or not resolved.is_relative_to(root):
                raise OperatorBlocked("operator_source_provenance_mismatch")
    except Exception:
        raise OperatorBlocked("operator_source_provenance_mismatch") from None


class Disposition(StrEnum):
    NOT_RUN = "NOT_RUN"
    NOT_CALLED = "NOT_CALLED"
    CALL_RETURNED = "CALL_RETURNED"
    INDETERMINATE = "INDETERMINATE"
    NOT_PUBLISHED = "NOT_PUBLISHED"
    PUBLISHED_VERIFIED = "PUBLISHED_VERIFIED"


class Reader(Protocol):
    def require_administrator(self) -> None: ...
    def list_directory(self, path: str) -> d.CheckedDirectory: ...
    def read_file(self, path: str, limit: int) -> d.CheckedFile: ...
    def absent(self, path: str) -> bool: ...


class LeaseWriter(Protocol):
    def require_administrator(self) -> None: ...
    def create_file(self, path: str, data: bytes) -> None: ...
    def publish_create_only(self, installing_path: str, final_path: str) -> None: ...


@dataclass(frozen=True, slots=True)
class SignedObservation:
    objects: tuple[d.NativeObject, ...]
    leases_present: tuple[bool, bool, bool]

    def evidence(self) -> dict[str, object]:
        identity = replacement.NEW_IDENTITY
        return {
            "deployment_id": identity.deployment_id,
            "attestation_sha256": identity.unsigned_attestation_sha256,
            "source_head": identity.certified_source_head,
            "source_tree": identity.certified_source_tree,
            "guard_sha256": identity.guard_sha256,
            "guard_byte_length": identity.guard_byte_length,
            "manifest_sha256": identity.manifest_sha256,
            "executable_file_count": identity.executable_file_count,
            "executable_total_bytes": identity.executable_total_bytes,
            "signing_key_id": d.D10_SIGNING_KEY_ID,
            "trading_sid": d.TRADING_SID,
            "production_python": str(
                schedule.D10_SCHEDULER_CONTRACT.production_interpreter
            ),
            "production_python_version": d.PRODUCTION_PYTHON_VERSION,
            "native_object_count": len(self.objects),
            "native_identity_sha256": hashlib.sha256(
                canonical_json_bytes([asdict(item) for item in self.objects])
            ).hexdigest(),
            "lease_final_installing_tmp_present": list(self.leases_present),
            "retired_staging_cache": "ABSENT_AND_VERIFIED",
        }


def _signed_once(reader: Reader, verifier: d.SignatureVerifier) -> SignedObservation:
    reader.require_administrator()
    objects: dict[str, d.NativeObject] = {}

    def remember(item: d.NativeObject) -> None:
        if item.path in objects and objects[item.path] != item:
            raise OperatorBlocked("native_object_drift")
        if objects and item.volume_serial != next(iter(objects.values())).volume_serial:
            raise OperatorBlocked("volume_drift")
        objects[item.path] = item

    parent = reader.list_directory(d.D10_PARENT)
    if type(parent) is not d.CheckedDirectory or parent.stable is not True:
        raise OperatorBlocked("parent_unstable")
    d.require_parent_native_object(parent.identity)
    remember(parent.identity)
    names = parent.children
    if (
        type(names) is not tuple
        or len(names) != len(set(names))
        or len(names) != len({name.casefold() for name in names})
        or "D10" not in names
        or any(name.casefold().startswith(("d10.", "d10-")) for name in names)
    ):
        raise OperatorBlocked("parent_namespace")
    for path in (replacement.RETIRED_PATH, replacement.STAGING_PATH, *_RESERVED):
        if reader.absent(path) is not True:
            raise OperatorBlocked("reserved_present_or_unknown")
    absence = tuple(reader.absent(path) for path in _LEASE_PATHS)
    # Native absent must return exact bool; access denial is an exception.
    if any(type(value) is not bool for value in absence):
        raise OperatorBlocked("lease_absence_unknown")
    present = tuple(not value for value in absence)
    root_names = {
        "source",
        "launch-guard.py",
        "deployment.attestation.json",
        "deployment.attestation.sig",
        "executable-manifest.json",
    }
    root_names.update(
        Path(path.replace("\\", "/")).name
        for path, exists in zip(_LEASE_PATHS, present, strict=True)
        if exists
    )
    root = reader.list_directory(d.D10_ROOT)
    d.require_directory(root, d.D10_ROOT, root_names)
    remember(root.identity)

    def read(path: str, limit: int) -> bytes:
        checked = reader.read_file(path, limit)
        if type(checked) is not d.CheckedFile or type(checked.data) is not bytes:
            raise OperatorBlocked("file_result_type")
        d.require_file(checked, path, checked.data)
        if len(checked.data) > limit:
            raise OperatorBlocked("file_bound")
        remember(checked.identity)
        return checked.data

    identity = replacement.NEW_IDENTITY
    manifest_bytes = read(d.D10_MANIFEST, d.MAX_MANIFEST_BYTES)
    manifest = parse_executable_manifest(manifest_bytes)
    if (
        manifest.digest != identity.manifest_sha256
        or len(manifest.entries) != identity.executable_file_count
        or sum(entry.byte_length for entry in manifest.entries)
        != identity.executable_total_bytes
    ):
        raise OperatorBlocked("manifest_identity")
    guard = read(d.D10_GUARD, d.MAX_GUARD_BYTES)
    if (
        len(guard) != identity.guard_byte_length
        or hashlib.sha256(guard).hexdigest() != identity.guard_sha256
    ):
        raise OperatorBlocked("guard_identity")
    attestation_bytes = read(d.D10_ATTESTATION, d.MAX_ATTESTATION_BYTES)
    attestation = parse_deployment_attestation(attestation_bytes)
    if (
        hashlib.sha256(attestation_bytes).hexdigest()
        != identity.unsigned_attestation_sha256
        or attestation.deployment_id != identity.deployment_id
        or attestation.certified_source_head != identity.certified_source_head
        or attestation.certified_source_tree != identity.certified_source_tree
        or attestation.launch_guard_byte_length != identity.guard_byte_length
        or attestation.launch_guard_sha256 != identity.guard_sha256
        or attestation.executable_manifest_sha256 != manifest.digest
        or attestation.executable_file_count != len(manifest.entries)
    ):
        raise OperatorBlocked("attestation_identity")
    d.verify_signature(
        verifier, attestation_bytes, read(d.D10_SIGNATURE, d.MAX_SIGNATURE_BYTES)
    )
    directories: dict[str, set[str]] = {d.D10_SOURCE: set()}
    for entry in manifest.entries:
        parts = entry.relative_path.split("/")
        directory = d.D10_SOURCE
        for component in parts[:-1]:
            directories[directory].add(component)
            directory += "\\" + component
            directories.setdefault(directory, set())
        directories[directory].add(parts[-1])
    if directories[d.D10_SOURCE] != {
        "src",
        "scripts",
    } or D10_LAUNCHER_RELATIVE_PATH not in {
        entry.relative_path for entry in manifest.entries
    }:
        raise OperatorBlocked("source_layout")
    for path, children in sorted(directories.items()):
        checked = reader.list_directory(path)
        d.require_directory(checked, path, children)
        remember(checked.identity)
    for entry in manifest.entries:
        path = d.D10_SOURCE + "\\" + entry.relative_path.replace("/", "\\")
        data = read(path, max(1, entry.byte_length))
        if (
            len(data) != entry.byte_length
            or hashlib.sha256(data).hexdigest() != entry.sha256
        ):
            raise OperatorBlocked("source_bytes")
    if (
        reader.list_directory(d.D10_PARENT) != parent
        or reader.list_directory(d.D10_ROOT) != root
    ):
        raise OperatorBlocked("namespace_changed")
    if tuple(reader.absent(path) for path in _LEASE_PATHS) != absence:
        raise OperatorBlocked("lease_absence_drift")
    return SignedObservation(tuple(objects.values()), present)


def _stable_signed(reader: Reader, verifier: d.SignatureVerifier) -> SignedObservation:
    first = _signed_once(reader, verifier)
    second = _signed_once(reader, verifier)
    if first != second:
        raise OperatorBlocked("signed_two_read_drift")
    return second


def _same_signed_deployment(
    baseline: SignedObservation,
    observed: SignedObservation,
    *,
    expected_leases: tuple[bool, bool, bool],
) -> bool:
    """Compare signed deployment identity across an admitted lease-name change."""

    if observed.leases_present != expected_leases:
        return False
    if len(baseline.objects) != len(observed.objects):
        return False

    def normalized(item: d.NativeObject) -> d.NativeObject:
        # The D10 root's directory allocation size may legitimately change when
        # one reviewed lease name is created or renamed. _signed_once() already
        # proves exact allowed children and every other native/security field.
        return replace(item, size=0) if item.path == d.D10_ROOT else item

    if sum(item.path == d.D10_ROOT for item in baseline.objects) != 1:
        return False
    if sum(item.path == d.D10_ROOT for item in observed.objects) != 1:
        return False
    return tuple(map(normalized, baseline.objects)) == tuple(
        map(normalized, observed.objects)
    )


def _expected_d10(spec: OneWeekSoakSchedulerDeploymentSpec) -> dict[str, object]:
    return {
        **frozen_d5_scheduler_semantics(),
        "action_arguments": " ".join(D10_GUARD_ARGUMENTS),
        "action_working_directory": d.D10_ROOT,
        "trigger_start_boundary": spec.task.start_boundary.isoformat(
            timespec="seconds"
        ),
        "trigger_end_boundary": spec.end_boundary.isoformat(timespec="auto"),
        "host_timezone": "Pacific Standard Time",
    }


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OperatorBlocked("duplicate_json")
        result[key] = value
    return result


def _parse_scheduler(data: bytes) -> SchedulerObservation:
    if type(data) is not bytes or not 0 < len(data) <= MAX_TRANSPORT:
        raise OperatorBlocked("scheduler_output_bound")
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    if (
        type(value) is not dict
        or set(value) != {"schema", "status", "first", "second"}
        or value["schema"] != SCHEDULER_SCHEMA
        or value["status"] != "OBSERVED"
    ):
        raise OperatorBlocked("scheduler_schema")
    expected = {
        **frozen_d5_scheduler_semantics(),
        "trigger_end_boundary": "",
        "host_timezone": "Pacific Standard Time",
    }
    observations = []
    for item in (value["first"], value["second"]):
        if type(item) is not dict or set(item) != {
            *expected,
            "xml_byte_length",
            "xml_sha256",
        }:
            raise OperatorBlocked("scheduler_fields")
        if any(
            type(item[key]) is not type(example) for key, example in expected.items()
        ):
            raise OperatorBlocked("scheduler_types")
        length, digest = item["xml_byte_length"], item["xml_sha256"]
        if (
            type(length) is not int
            or not 0 < length <= 1024 * 1024
            or type(digest) is not str
            or not _SHA256.fullmatch(digest)
        ):
            raise OperatorBlocked("scheduler_xml_bound")
        observations.append(
            SchedulerObservation(
                tuple(sorted((key, item[key]) for key in expected)), length, digest
            )
        )
    if observations[0] != observations[1]:
        raise OperatorBlocked("scheduler_two_read_drift")
    return observations[0]


def _require_semantics(
    observed: SchedulerObservation, expected: dict[str, object]
) -> None:
    if type(observed) is not SchedulerObservation:
        raise OperatorBlocked("scheduler_observation_type")
    actual = dict(observed.semantics)
    if set(actual) != set(expected) or any(
        type(actual[key]) is not type(value) or actual[key] != value
        for key, value in expected.items()
    ):
        raise OperatorBlocked("scheduler_semantic_drift")


def _lease_evidence(checked: d.CheckedFile) -> dict[str, object]:
    return {
        "bytes_sha256": hashlib.sha256(checked.data).hexdigest(),
        "native_identity_sha256": hashlib.sha256(
            canonical_json_bytes(asdict(checked.identity))
        ).hexdigest(),
        "owner_sid": checked.identity.owner_sid,
        "protected_dacl": checked.identity.dacl_protected,
        "non_reparse": not checked.identity.reparse,
        "links": checked.identity.links,
        "local_ntfs": checked.identity.drive_type == 3
        and checked.identity.filesystem == "NTFS",
    }


def _scheduler_evidence(observed: SchedulerObservation) -> dict[str, object]:
    return {
        "semantics": dict(observed.semantics),
        "xml_byte_length": observed.xml_byte_length,
        "xml_sha256": observed.xml_sha256,
    }


def _planned(
    activation: datetime,
) -> tuple[D10ActivationLease, OneWeekSoakSchedulerDeploymentSpec]:
    identity = replacement.NEW_IDENTITY
    lease = build_activation_lease_model(
        deployment_id=identity.deployment_id,
        attestation_sha256=identity.unsigned_attestation_sha256,
        accepted_activation_utc=activation,
        certified_source_head=identity.certified_source_head,
        certified_source_tree=identity.certified_source_tree,
    )
    spec = build_one_week_soak_scheduler_deployment_spec(activation)
    if (
        spec.window.activation_utc != lease.accepted_activation_utc
        or spec.end_boundary.astimezone(UTC) != lease.end_utc
    ):
        raise OperatorBlocked("seven_day_binding")
    return lease, spec


class _Operator:
    """Single-use composition; injectable boundaries exist only for fake tests."""

    def __init__(
        self,
        reader: Reader,
        verifier: d.SignatureVerifier,
        writer: LeaseWriter | None,
        d5_read: Callable[[], SchedulerObservation],
        scheduler_read: Callable[[], SchedulerObservation],
        update: Callable[[D10ActivationLease, str], Disposition] | None,
        credential: Callable[[], str] | None,
        now: Callable[[], datetime],
    ) -> None:
        self.reader, self.verifier, self.writer = reader, verifier, writer
        self.d5_read, self.scheduler_read = d5_read, scheduler_read
        self.update, self.credential, self.now = update, credential, now
        self.used = False

    def _admit(self) -> tuple[SignedObservation, SchedulerObservation]:
        first = _stable_signed(self.reader, self.verifier)
        if first.leases_present != (False, False, False):
            raise OperatorBlocked("lease_already_present")
        predecessor = (
            self.d5_read()
        )  # Accepted zero-argument Architecture-126 observer.
        _require_semantics(predecessor, frozen_d5_scheduler_semantics())
        extended = self.scheduler_read()
        _require_semantics(
            extended,
            {
                **frozen_d5_scheduler_semantics(),
                "trigger_end_boundary": "",
                "host_timezone": "Pacific Standard Time",
            },
        )
        second = _stable_signed(self.reader, self.verifier)
        reread = self.d5_read()
        _require_semantics(reread, frozen_d5_scheduler_semantics())
        if (
            first != second
            or predecessor != reread
            or self.scheduler_read() != extended
        ):
            raise OperatorBlocked("admission_two_read_drift")
        return second, extended

    def _state(
        self, signed: SignedObservation, scheduler: SchedulerObservation
    ) -> dict[str, object]:
        return {
            "signed_deployment": signed.evidence(),
            "scheduler": _scheduler_evidence(scheduler),
        }

    def _base(self, mode: str) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "mode": mode,
            "status": "BLOCKED",
            "stage": "admission",
            "pre_state": None,
            "planned": None,
            "scheduler_mutation": Disposition.NOT_RUN,
            "lease_publication": Disposition.NOT_RUN,
            "post_state": None,
            "reconciliation_required": False,
            "automatic_retry": False,
            "automatic_rollback": False,
            "source_launch": "NOT_RUN",
            "provider": "NOT_RUN",
            "Paper-v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }

    def preflight(self) -> dict[str, object]:
        result = self._base("preflight")
        try:
            signed, scheduler = self._admit()
            result.update(
                status="PASS",
                stage="read_only_complete",
                pre_state=self._state(signed, scheduler),
            )
        except Exception:
            pass  # Never serialize exception text or raw transports.
        return result

    def reconcile(self) -> dict[str, object]:
        result = self._base("reconcile")
        try:
            signed = _stable_signed(self.reader, self.verifier)
            scheduler = self.scheduler_read()
            if signed.leases_present[0]:
                checked = self.reader.read_file(PUBLICATION.final_path, MAX_LEASE)
                lease = parse_activation_lease(checked.data)
                expected_lease, spec = _planned(lease.accepted_activation_utc)
                d.require_file(
                    checked, PUBLICATION.final_path, expected_lease.canonical_bytes()
                )
                _require_semantics(scheduler, _expected_d10(spec))
                current = self.now()
                classification = (
                    "NOT_YET_ACTIVE_VERIFIED"
                    if current < lease.accepted_activation_utc
                    else "ARMED_VERIFIED"
                    if current < lease.end_utc
                    else "EXPIRED_VERIFIED"
                )
                result["planned"] = expected_lease.to_dict()
            elif dict(scheduler.semantics) == {
                **frozen_d5_scheduler_semantics(),
                "trigger_end_boundary": "",
                "host_timezone": "Pacific Standard Time",
            }:
                classification = "D5_UNARMED"
            else:
                end = datetime.fromisoformat(
                    dict(scheduler.semantics)["trigger_end_boundary"]
                )
                if end.tzinfo is None:
                    raise OperatorBlocked("scheduler_end_not_aware")
                lease, spec = _planned(end.astimezone(UTC) - timedelta(days=7))
                _require_semantics(scheduler, _expected_d10(spec))
                classification = "D10_SCHEDULER_LEASE_ABSENT"
                result["planned"] = lease.to_dict()
            if (
                _stable_signed(self.reader, self.verifier) != signed
                or self.scheduler_read() != scheduler
            ):
                raise OperatorBlocked("reconciliation_drift")
            if signed.leases_present[0]:
                lease_again = self.reader.read_file(PUBLICATION.final_path, MAX_LEASE)
                d.require_file(
                    lease_again,
                    PUBLICATION.final_path,
                    expected_lease.canonical_bytes(),
                )
                if lease_again != checked:
                    raise OperatorBlocked("reconciliation_lease_drift")
            if signed.leases_present[1:] != (False, False):
                classification = "PARTIAL_LEASE_PUBLICATION_REQUIRES_RECONCILIATION"
            result.update(
                status="PASS",
                stage="read_only_complete",
                post_state=self._state(signed, scheduler),
                classification=classification,
            )
            if signed.leases_present[0]:
                result["post_state"]["lease"] = _lease_evidence(checked)
            result["reconciliation_required"] = classification in (
                "D10_SCHEDULER_LEASE_ABSENT",
                "PARTIAL_LEASE_PUBLICATION_REQUIRES_RECONCILIATION",
            )
            if result["reconciliation_required"]:
                result["status"] = "RECONCILIATION_REQUIRED"
        except Exception:
            result.update(status="INDETERMINATE", reconciliation_required=True)
        return result

    def _admit_partial_installing(
        self,
    ) -> tuple[
        SignedObservation,
        SchedulerObservation,
        d.CheckedFile,
        D10ActivationLease,
        OneWeekSoakSchedulerDeploymentSpec,
    ]:
        signed = _stable_signed(self.reader, self.verifier)
        if signed.leases_present != (False, True, False):
            raise OperatorBlocked("recovery_lease_namespace")

        installing = self.reader.read_file(PUBLICATION.installing_path, MAX_LEASE)
        lease = parse_activation_lease(installing.data)
        expected_lease, spec = _planned(lease.accepted_activation_utc)
        data = expected_lease.canonical_bytes()
        d.require_file(installing, PUBLICATION.installing_path, data)
        if lease != expected_lease:
            raise OperatorBlocked("recovery_lease_model")

        scheduler = self.scheduler_read()
        _require_semantics(scheduler, _expected_d10(spec))
        if not lease.accepted_activation_utc <= self.now() < lease.end_utc:
            raise OperatorBlocked("recovery_window_not_active")
        if self.reader.absent(PUBLICATION.final_path) is not True:
            raise OperatorBlocked("recovery_final_collision")
        if self.reader.absent(PUBLICATION.temporary_path) is not True:
            raise OperatorBlocked("recovery_temporary_present")

        signed_again = _stable_signed(self.reader, self.verifier)
        scheduler_again = self.scheduler_read()
        installing_again = self.reader.read_file(
            PUBLICATION.installing_path, MAX_LEASE
        )
        d.require_file(installing_again, PUBLICATION.installing_path, data)
        if (
            signed_again != signed
            or scheduler_again != scheduler
            or installing_again != installing
        ):
            raise OperatorBlocked("recovery_two_read_drift")
        return signed, scheduler, installing, expected_lease, spec

    def recovery_preflight(self) -> dict[str, object]:
        result = self._base("recovery_preflight")
        result["reconciliation_required"] = True
        try:
            signed, scheduler, installing, lease, _ = self._admit_partial_installing()
            result.update(
                status="PASS",
                stage="read_only_complete",
                classification="EXACT_INSTALLING_LEASE_D10_SCHEDULER",
                planned=lease.to_dict(),
                post_state=self._state(signed, scheduler),
            )
            result["post_state"]["installing_lease"] = _lease_evidence(installing)
        except Exception:
            pass
        return result

    def recover_partial_installing(
        self, *, execute_p1245_recovery: bool = False
    ) -> dict[str, object]:
        result = self._base("recover_partial")
        result["reconciliation_required"] = True
        if execute_p1245_recovery is not True or self.used:
            result["stage"] = "recovery_switch_or_duplicate"
            return result
        self.used = True
        final_call = False
        try:
            signed, scheduler, installing, lease, spec = (
                self._admit_partial_installing()
            )
            result["planned"] = lease.to_dict()
            result["pre_state"] = self._state(signed, scheduler)
            result["pre_state"]["installing_lease"] = _lease_evidence(installing)
            if self.writer is None:
                raise OperatorBlocked("recovery_writer_missing")
            self.writer.require_administrator()
            if self.reader.absent(PUBLICATION.final_path) is not True:
                raise OperatorBlocked("recovery_final_collision")
            if self.reader.absent(PUBLICATION.temporary_path) is not True:
                raise OperatorBlocked("recovery_temporary_present")
            if not lease.accepted_activation_utc <= self.now() < lease.end_utc:
                raise OperatorBlocked("recovery_window_not_active")

            result["stage"] = "final_lease_publication_recovery"
            final_call = True
            result["lease_publication"] = Disposition.INDETERMINATE
            self.writer.publish_create_only(
                PUBLICATION.installing_path, PUBLICATION.final_path
            )

            result["stage"] = "recovery_native_reverification"
            data = lease.canonical_bytes()
            final = self.reader.read_file(PUBLICATION.final_path, MAX_LEASE)
            d.require_file(final, PUBLICATION.final_path, data)
            if (
                replace(
                    installing.identity,
                    path=PUBLICATION.final_path,
                    final_path=PUBLICATION.final_path,
                )
                != final.identity
            ):
                raise OperatorBlocked("recovery_lease_native_identity_changed")

            result["stage"] = "recovery_final_independent_reread"
            final_signed = _stable_signed(self.reader, self.verifier)
            final_scheduler = self.scheduler_read()
            _require_semantics(final_scheduler, _expected_d10(spec))
            final_again = self.reader.read_file(PUBLICATION.final_path, MAX_LEASE)
            d.require_file(final_again, PUBLICATION.final_path, data)
            if (
                not _same_signed_deployment(
                    signed,
                    final_signed,
                    expected_leases=(True, False, False),
                )
                or final_again != final
                or not lease.accepted_activation_utc <= self.now() < lease.end_utc
            ):
                raise OperatorBlocked("recovery_final_state_disagreement")

            result.update(
                status="PASS",
                stage="complete",
                lease_publication=Disposition.PUBLISHED_VERIFIED,
                reconciliation_required=False,
                post_state=self._state(final_signed, final_scheduler),
            )
            result["post_state"]["lease"] = _lease_evidence(final_again)
        except (Exception, KeyboardInterrupt):
            result.update(
                status="INDETERMINATE" if final_call else "BLOCKED",
                reconciliation_required=True,
            )
            result["post_state"] = self.reconcile()
        return result

    def execute(self, *, execute_p1245: bool = False) -> dict[str, object]:
        result = self._base("execute")
        if execute_p1245 is not True or self.used:
            result["stage"] = "execution_switch_or_duplicate"
            return result
        self.used = True
        lease: D10ActivationLease | None = None
        final_call = False
        try:
            signed, scheduler = self._admit()
            result["pre_state"] = self._state(signed, scheduler)
            if self.credential is None or self.update is None or self.writer is None:
                raise OperatorBlocked("protected_transports_missing")
            result["stage"] = "interactive_credential"
            secret = self.credential()
            if type(secret) is not str or not secret:
                raise OperatorBlocked("interactive_credential_unavailable")
            try:
                # An interactive pause never preserves old admission authority.
                result["stage"] = "fresh_admission_after_credential"
                fresh_signed, fresh_scheduler = self._admit()
                if (fresh_signed, fresh_scheduler) != (signed, scheduler):
                    raise OperatorBlocked("credential_pause_drift")
                lease, spec = _planned(
                    self.now()
                )  # Source-owned clock, never argv/env.
                result["planned"] = lease.to_dict()
                result["stage"] = "scheduler_mutation"
                result["scheduler_mutation"] = Disposition.INDETERMINATE
                disposition = self.update(lease, secret)
                if type(disposition) is not Disposition or disposition not in (
                    Disposition.NOT_CALLED,
                    Disposition.CALL_RETURNED,
                    Disposition.INDETERMINATE,
                ):
                    raise OperatorBlocked("scheduler_disposition")
                result["scheduler_mutation"] = disposition
            finally:
                # Release the reference; never persist or serialize credentials.
                secret = ""
            if disposition is not Disposition.CALL_RETURNED:
                result.update(
                    status="BLOCKED"
                    if disposition is Disposition.NOT_CALLED
                    else "INDETERMINATE",
                    reconciliation_required=True,
                )
                result["post_state"] = self.reconcile()
                return result
            result["stage"] = "scheduler_post_verification"
            post_scheduler = self.scheduler_read()
            _require_semantics(post_scheduler, _expected_d10(spec))
            if _stable_signed(self.reader, self.verifier) != signed:
                raise OperatorBlocked("signed_drift_before_publication")
            # Recheck independently immediately before the final arming action.
            _require_semantics(self.scheduler_read(), _expected_d10(spec))
            if not lease.accepted_activation_utc <= self.now() < lease.end_utc:
                raise OperatorBlocked("planned_window_not_active")
            result["post_state"] = self._state(signed, post_scheduler)
            result["stage"] = "lease_staging"
            result["lease_publication"] = Disposition.NOT_PUBLISHED
            self.writer.require_administrator()
            for path in _LEASE_PATHS:
                if self.reader.absent(path) is not True:
                    raise OperatorBlocked("lease_collision")
            data = lease.canonical_bytes()
            self.writer.create_file(PUBLICATION.temporary_path, data)
            staged = self.reader.read_file(PUBLICATION.temporary_path, MAX_LEASE)
            d.require_file(staged, PUBLICATION.temporary_path, data)
            self.writer.publish_create_only(
                PUBLICATION.temporary_path, PUBLICATION.installing_path
            )
            installing = self.reader.read_file(PUBLICATION.installing_path, MAX_LEASE)
            d.require_file(installing, PUBLICATION.installing_path, data)
            if (
                replace(
                    staged.identity,
                    path=PUBLICATION.installing_path,
                    final_path=PUBLICATION.installing_path,
                )
                != installing.identity
            ):
                raise OperatorBlocked("staging_native_identity_changed")
            # Staging may take time. Fresh signed truth and independent COM reads
            # must still agree before the final no-replace publication.
            staged_signed = _stable_signed(self.reader, self.verifier)
            if not _same_signed_deployment(
                signed,
                staged_signed,
                expected_leases=(False, True, False),
            ):
                raise OperatorBlocked("staging_deployment_drift")
            _require_semantics(self.scheduler_read(), _expected_d10(spec))
            if not lease.accepted_activation_utc <= self.now() < lease.end_utc:
                raise OperatorBlocked("window_expired_before_publication")
            if self.reader.absent(PUBLICATION.final_path) is not True:
                raise OperatorBlocked("final_lease_collision")
            result["stage"] = "final_lease_publication"
            final_call = True
            result["lease_publication"] = Disposition.INDETERMINATE
            self.writer.publish_create_only(
                PUBLICATION.installing_path, PUBLICATION.final_path
            )
            result["stage"] = "lease_native_reverification"
            final = self.reader.read_file(PUBLICATION.final_path, MAX_LEASE)
            d.require_file(final, PUBLICATION.final_path, data)
            if (
                replace(
                    installing.identity,
                    path=PUBLICATION.final_path,
                    final_path=PUBLICATION.final_path,
                )
                != final.identity
            ):
                raise OperatorBlocked("lease_native_identity_changed")
            result["stage"] = "final_independent_reread"
            final_signed = _stable_signed(self.reader, self.verifier)
            final_scheduler = self.scheduler_read()
            _require_semantics(final_scheduler, _expected_d10(spec))
            final_again = self.reader.read_file(PUBLICATION.final_path, MAX_LEASE)
            d.require_file(final_again, PUBLICATION.final_path, data)
            if (
                not _same_signed_deployment(
                    signed,
                    final_signed,
                    expected_leases=(True, False, False),
                )
                or final_again != final
                or not lease.accepted_activation_utc <= self.now() < lease.end_utc
            ):
                raise OperatorBlocked("final_state_disagreement")
            result.update(
                status="PASS",
                stage="complete",
                lease_publication=Disposition.PUBLISHED_VERIFIED,
                post_state=self._state(final_signed, final_scheduler),
            )
            result["post_state"]["lease"] = _lease_evidence(final_again)
        except (Exception, KeyboardInterrupt):
            scheduler_attempted = result["scheduler_mutation"] != Disposition.NOT_RUN
            result.update(
                status="INDETERMINATE"
                if final_call
                or result["scheduler_mutation"] == Disposition.INDETERMINATE
                else "BLOCKED",
                reconciliation_required=scheduler_attempted,
            )
            if scheduler_attempted:
                # Diagnostic only; never resume, undo, or retry from this result.
                result["post_state"] = self.reconcile()
        return result


def _command(helper: Path) -> tuple[str, ...]:
    return (
        POWERSHELL,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(helper),
    )


def _transport(helper: Path, payload: bytes | None = None) -> tuple[int, bytes, bytes]:
    import subprocess

    if helper not in (OBSERVE_HELPER, UPDATE_HELPER):
        raise OperatorBlocked("unreviewed_transport")
    # Pipe contents are never attached to exceptions or evidence. All output is
    # capped, discarded on failure, and parsed only after native exit disposition.
    with subprocess.Popen(
        _command(helper),
        stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        assert process.stdout is not None and process.stderr is not None
        with ThreadPoolExecutor(max_workers=2) as readers:
            stdout = readers.submit(process.stdout.read, MAX_TRANSPORT + 1)
            stderr = readers.submit(process.stderr.read, 257)
            try:
                if payload is not None:
                    assert process.stdin is not None
                    process.stdin.write(payload)
                    process.stdin.close()
                code = process.wait(timeout=60)
            except Exception:
                process.kill()
                process.wait()
                raise OperatorBlocked("transport_ambiguous") from None
            out, err = stdout.result(), stderr.result()
    if len(out) > MAX_TRANSPORT or len(err) > 256:
        raise OperatorBlocked("transport_bound")
    return code, out, err


def _read_scheduler() -> SchedulerObservation:
    code, out, err = _transport(OBSERVE_HELPER)
    if type(code) is not int or code != 0 or err:
        raise OperatorBlocked("scheduler_transport_failure")
    return _parse_scheduler(out)


def _update_scheduler(lease: D10ActivationLease, secret: str) -> Disposition:
    payload = (
        canonical_json_bytes(
            {
                "activation_utc": format_utc_instant(lease.accepted_activation_utc),
                "password": secret,
            }
        )
        + b"\n"
    )
    try:
        if len(payload) > MAX_TRANSPORT:
            return Disposition.NOT_CALLED
        code, out, err = _transport(UPDATE_HELPER, payload)
        if err or type(code) is not int:
            return Disposition.INDETERMINATE
        value = json.loads(out.decode("utf-8"), object_pairs_hook=_unique_pairs)
        if (
            type(value) is not dict
            or set(value) != {"schema", "disposition"}
            or value["schema"] != UPDATE_SCHEMA
        ):
            return Disposition.INDETERMINATE
        disposition = Disposition(value["disposition"])
        if (code, disposition) not in (
            (0, Disposition.CALL_RETURNED),
            (1, Disposition.NOT_CALLED),
            (2, Disposition.INDETERMINATE),
        ):
            return Disposition.INDETERMINATE
        return disposition
    except Exception:
        return Disposition.INDETERMINATE
    finally:
        payload = b""


def _interactive_credential() -> str:
    import getpass

    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise OperatorBlocked("interactive_console_required")
    # getpass on Windows uses the console without echo. No fallback to argv,
    # environment, files, redirected stdin, or other credential inputs exists.
    return getpass.getpass("Trading password for the protected P124-5 invocation: ")


def _host_operator(*, protected: bool = False) -> _Operator:
    _require_source_provenance()
    return _Operator(
        WindowsD10ReadOnlyReader(),
        WindowsCngVerifier(),
        WindowsActivationLeaseBackend() if protected else None,
        observe_d5_scheduler,
        _read_scheduler,
        _update_scheduler if protected else None,
        _interactive_credential if protected else None,
        lambda: datetime.now(UTC).replace(microsecond=0),
    )


def preflight() -> dict[str, object]:
    """Read-only admission at the fixed namespace and accepted D5 task."""
    _require_source_provenance()
    return _host_operator().preflight()


def reconcile() -> dict[str, object]:
    """Independent read-only reconstruction; no caller plan is accepted."""
    _require_source_provenance()
    return _host_operator().reconcile()


def execute(*, execute_p1245: bool = False) -> dict[str, object]:
    """Protected invocation only after separately reviewed operator approval."""
    _require_source_provenance()
    if execute_p1245 is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "stage": "execution_switch_required",
            "scheduler_mutation": "NOT_RUN",
            "lease_publication": "NOT_RUN",
            "source_launch": "NOT_RUN",
            "provider": "NOT_RUN",
            "Paper-v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }
    return _host_operator(protected=True).execute(execute_p1245=True)


def recovery_preflight() -> dict[str, object]:
    """Read-only admission for the exact partial installing-lease incident."""
    _require_source_provenance()
    return _host_operator().recovery_preflight()


def recover_partial_installing(
    *, execute_p1245_recovery: bool = False
) -> dict[str, object]:
    """One-shot recovery of the exact verified installing lease."""
    _require_source_provenance()
    if execute_p1245_recovery is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "stage": "recovery_switch_required",
            "scheduler_mutation": "NOT_RUN",
            "lease_publication": "NOT_RUN",
            "source_launch": "NOT_RUN",
            "provider": "NOT_RUN",
            "Paper-v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }
    return _host_operator(protected=True).recover_partial_installing(
        execute_p1245_recovery=True
    )


class _ClosedParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse normally echoes unknown argv values, potentially a secret.
        super().error("unsupported invocation; consult --help")


def main(argv: list[str] | None = None) -> int:
    parser = _ClosedParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=(
            "preflight",
            "execute",
            "reconcile",
            "recovery-preflight",
            "recover-partial",
        ),
    )
    parser.add_argument("--execute-p1245", action="store_true")
    parser.add_argument("--execute-p1245-recovery", action="store_true")
    args = parser.parse_args(argv)
    is_execute = args.mode == "execute"
    is_recovery = args.mode == "recover-partial"
    if (
        is_execute != args.execute_p1245
        or is_recovery != args.execute_p1245_recovery
        or (args.execute_p1245 and args.execute_p1245_recovery)
    ):
        parser.error("protected modes require their exact execution switch")
    try:
        result = (
            execute(execute_p1245=True)
            if is_execute
            else recover_partial_installing(execute_p1245_recovery=True)
            if is_recovery
            else recovery_preflight()
            if args.mode == "recovery-preflight"
            else preflight()
            if args.mode == "preflight"
            else reconcile()
        )
    except Exception:
        result = {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "stage": "native_boundary_unavailable",
            "provider": "NOT_RUN",
            "Paper-v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }
    data = canonical_json_bytes(result)
    if len(data) > 64 * 1024:
        result = {
            "schema": SCHEMA,
            "status": "INDETERMINATE",
            "stage": "evidence_bound",
            "reconciliation_required": True,
            "provider": "NOT_RUN",
            "Paper-v2": "NOT_RUN",
            "broker": "NOT_RUN",
            "live": "NOT_RUN",
        }
        data = canonical_json_bytes(result)
    print(data.decode("utf-8"))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
