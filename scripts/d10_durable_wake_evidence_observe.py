"""Read-only Architecture-127 observation of the exact current-soak D10 log."""

from __future__ import annotations

import hashlib
import json
import sys
from contextlib import ExitStack
from datetime import UTC, datetime

from scripts import run_personal_desktop_d10_launch_guard as guard
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10ActivationLease,
    parse_activation_lease,
)
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    MAX_D10_EVIDENCE_LOG_BYTES,
    d10_wake_evidence_path,
    summarize_d10_wake_evidence_log,
)

D10_EVIDENCE_OBSERVATION_SCHEMA = "personal-desktop-d10-evidence-observation/v1"


class D10EvidenceObservationBlocked(RuntimeError):
    """The exact current-soak durable evidence could not be proven read-only."""


def _verified_attestation(native: guard._Native) -> dict[str, object]:
    material = guard._read_fixed_trust_material(native)
    guard._verify_d10_signature(material.attestation, material.signature)
    attestation = guard._parse_attestation(material.attestation)
    entries = guard._parse_manifest(material.manifest)
    if (
        len(material.guard) != attestation["launch_guard_byte_length"]
        or hashlib.sha256(material.guard).hexdigest()
        != attestation["launch_guard_sha256"]
        or len(entries) != attestation["executable_file_count"]
        or hashlib.sha256(material.manifest).hexdigest()
        != attestation["executable_manifest_sha256"]
    ):
        raise D10EvidenceObservationBlocked("signed deployment identity differs")
    guard._verify_sealed_source(entries, native)
    if guard._read_fixed_trust_material(native) != material:
        raise D10EvidenceObservationBlocked("signed deployment drifted")
    return attestation


def _read_activation_lease(native: guard._Native) -> bytes:
    with ExitStack() as stack:
        for path in (
            guard.D10_ACTIVATION_LEASE_INSTALLING,
            guard.D10_ACTIVATION_LEASE_TEMP,
        ):
            native.require_absent(path)
        root_handle = native.open(guard.D10_ROOT, directory=True)
        stack.callback(native.close, root_handle)
        root_before = native.inspect(root_handle)
        guard._require_facts(guard.D10_ROOT, True, root_before)

        lease_handle = native.open(guard.D10_ACTIVATION_LEASE, directory=False)
        stack.callback(native.close, lease_handle)
        lease_before = native.inspect(lease_handle)
        guard._require_facts(guard.D10_ACTIVATION_LEASE, False, lease_before)
        if not 0 < lease_before.size <= guard.ACTIVATION_LEASE_LIMIT:
            raise D10EvidenceObservationBlocked("activation lease size differs")
        data = native.read_exact(lease_handle, lease_before.size)
        if type(data) is not bytes or len(data) != lease_before.size:
            raise D10EvidenceObservationBlocked("activation lease read differs")
        for path in (
            guard.D10_ACTIVATION_LEASE_INSTALLING,
            guard.D10_ACTIVATION_LEASE_TEMP,
        ):
            native.require_absent(path)

        root_after = native.inspect(root_handle)
        lease_after = native.inspect(lease_handle)
        guard._require_facts(guard.D10_ROOT, True, root_after)
        guard._require_facts(guard.D10_ACTIVATION_LEASE, False, lease_after)
        guard._stable(root_before, root_after)
        guard._stable(lease_before, lease_after)
        return data


def _read_evidence(
    native: guard._Native, lease: D10ActivationLease
) -> tuple[str, bytes]:
    path = str(d10_wake_evidence_path(lease))
    if path != guard.D10_EVIDENCE_ROOT + rf"\wake-{lease.soak_id}.jsonl":
        raise D10EvidenceObservationBlocked("derived evidence path differs")

    with ExitStack() as stack:
        root_handle = native.open(guard.D10_EVIDENCE_ROOT, directory=True)
        stack.callback(native.close, root_handle)
        root_before = native.inspect(root_handle)
        guard._require_facts(guard.D10_EVIDENCE_ROOT, True, root_before)

        file_handle = native.open_evidence_observer(path)
        stack.callback(native.close, file_handle)
        file_before = native.inspect(file_handle)
        guard._require_facts(
            path,
            False,
            file_before,
            guard.EVIDENCE_FILE_POLICY,
        )
        if file_before.size < 0 or file_before.size > MAX_D10_EVIDENCE_LOG_BYTES:
            raise D10EvidenceObservationBlocked("evidence file size differs")
        data = native.read_bounded(
            file_handle,
            file_before.size,
            MAX_D10_EVIDENCE_LOG_BYTES,
        )

        root_after = native.inspect(root_handle)
        file_after = native.inspect(file_handle)
        guard._require_facts(guard.D10_EVIDENCE_ROOT, True, root_after)
        guard._require_facts(
            path,
            False,
            file_after,
            guard.EVIDENCE_FILE_POLICY,
        )
        guard._stable(root_before, root_after)
        guard._stable(file_before, file_after)
        return path, data


def _wake_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise D10EvidenceObservationBlocked("summary timestamp differs")
    return value.isoformat().replace("+00:00", "Z")


def observe(native: guard._Native | None = None) -> dict[str, object]:
    """Return sanitized read-only evidence for the exact fixed activation lease."""

    backend = guard._Native() if native is None else native
    attestation = _verified_attestation(backend)
    lease_bytes = _read_activation_lease(backend)
    lease = parse_activation_lease(lease_bytes)
    attestation_sha256 = hashlib.sha256(
        guard._canonical_json(attestation)
    ).hexdigest()
    if (
        lease.deployment_id != attestation["deployment_id"]
        or lease.attestation_sha256 != attestation_sha256
        or lease.certified_source_head != attestation["certified_source_head"]
        or lease.certified_source_tree != attestation["certified_source_tree"]
    ):
        raise D10EvidenceObservationBlocked("lease and signed deployment differ")

    evidence_path, evidence = _read_evidence(backend, lease)
    summary = summarize_d10_wake_evidence_log(evidence, lease)
    return {
        "schema": D10_EVIDENCE_OBSERVATION_SCHEMA,
        "status": "OBSERVED",
        "deployment_id": lease.deployment_id,
        "attestation_sha256": lease.attestation_sha256,
        "soak_id": lease.soak_id,
        "activation_utc": lease.accepted_activation_utc.isoformat().replace(
            "+00:00", "Z"
        ),
        "end_utc": lease.end_utc.isoformat().replace("+00:00", "Z"),
        "evidence_path": evidence_path,
        "evidence_byte_length": len(evidence),
        "evidence_sha256": hashlib.sha256(evidence).hexdigest(),
        "record_count": summary.record_count,
        "wake_count": summary.wake_count,
        "terminal": summary.terminal,
        "terminal_kind": summary.terminal_kind,
        "first_observed_at_utc": _wake_timestamp(summary.first_observed_at_utc),
        "last_observed_at_utc": _wake_timestamp(summary.last_observed_at_utc),
        "last_outcome": (
            None if summary.last_outcome is None else summary.last_outcome.value
        ),
        "last_stop_reason": (
            None
            if summary.last_stop_reason is None
            else summary.last_stop_reason.value
        ),
        "last_guard_reason": (
            None
            if summary.last_guard_reason is None
            else summary.last_guard_reason.value
        ),
        "scheduler_mutation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def main() -> int:
    if sys.argv != [sys.argv[0]]:
        return 1
    try:
        record = observe()
    except Exception:
        print("d10_evidence_observation_blocked", file=sys.stderr)
        return 1
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
