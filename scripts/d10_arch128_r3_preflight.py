"""Architecture-128 R3 read-only halted-host replacement preflight.

This module observes only fixed production paths and the one fixed Task
Scheduler task. It has no filesystem writer, rename, scheduler update,
credential, source-launch, provider, Paper-v2, broker, or live-trading path.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import subprocess
from dataclasses import asdict
from pathlib import Path

from scripts import d10_activation_scheduler_operator as activation
from scripts import d10_protected_deployment as deployment
from scripts import d10_protected_replacement as replacement
from scripts.d10_protected_deployment_windows import WindowsCngVerifier
from scripts.d10_protected_replacement_windows import WindowsD10ReadOnlyReader
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10_ACTIVATION_LEASE_PATH,
    format_utc_instant,
    parse_activation_lease,
)

SCHEMA = "arch128-r3-readonly-preflight/v1"

CURRENT_DEPLOYMENT_ID = "9f3d111b-25bb-5ee4-9abf-f5215a32b826"
CURRENT_ATTESTATION_SHA256 = (
    "4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2"
)
CURRENT_SOURCE_HEAD = "c5cc0b01301600daf17f1114f4451dca2c9d7a1f"
CURRENT_SOURCE_TREE = "bfacfadaa14315d2d378abcc0f1e4bc7c42034f1"
CURRENT_MANIFEST_SHA256 = (
    "e4aa71ebbe269837adfd277fbcd8b7ae05e1051343276de2449177587fe7b60a"
)
CURRENT_EXECUTABLE_FILE_COUNT = 306
CURRENT_EXECUTABLE_TOTAL_BYTES = 5391245
CURRENT_GUARD_SHA256 = (
    "37d78c65800a315a12049b6c278addf609589d121e15d31dd9064dc8ec427298"
)
CURRENT_GUARD_BYTE_LENGTH = 69259

OLD_LEASE_SHA256 = (
    "91106d61129dc9c11e017a7ea613ba0fd82c87fd9debfc346b265c03c49a1e84"
)
OLD_ACTIVATION = "2026-09-29T00:45:22.000000Z"
OLD_END = "2026-10-06T00:45:22.000000Z"
OLD_SOAK_ID = "48f14b13-aa18-5ce8-a0e0-402c867b17b6"

HISTORICAL_S5R8_RETIRED = (
    r"F:\AITradingBot\D10.retired-2fd79986-fb50-5fe4-800a-2d4aa5e7307c"
)
NEW_S5R10_RETIRED = (
    r"F:\AITradingBot\D10.retired-9f3d111b-25bb-5ee4-9abf-f5215a32b826"
)
NEW_STAGING = (
    r"F:\AITradingBot\D10.replacement-d2071f25-5a7c-5293-a28f-5b722c9917a2.installing"
)

SCHEDULER_HELPER = Path(__file__).with_name("d10_arch128_r3_scheduler_observe.ps1")
EXPECTED_SCHEDULER_XML_SHA256 = (
    "8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0"
)


class R3Blocked(RuntimeError):
    """Read-only R3 admission failed."""


class R3Reader(WindowsD10ReadOnlyReader):
    """Read-only native reader widened only to three exact absence probes."""

    @staticmethod
    def _allowed(path: str, *, directory: bool | None) -> bool:
        if WindowsD10ReadOnlyReader._allowed(path, directory=directory):
            return True
        return (
            type(path) is str
            and ntpath.normpath(path) == path
            and path
            in {
                HISTORICAL_S5R8_RETIRED,
                NEW_S5R10_RETIRED,
                NEW_STAGING,
            }
            and directory in (True, None)
        )


def _expected_scheduler() -> dict[str, object]:
    return {
        "task_path": r"\AITradingBot-PD4-UnattendedPaper-v1",
        "principal_sid": "S-1-5-21-1397534616-3988210162-180023805-1009",
        "logon_type": 1,
        "run_level": 0,
        "action_count": 1,
        "action_type": 0,
        "action_path": r"F:\AITradingBot\runtime\python.exe",
        "action_arguments": (
            r"-I -S -B -X pycache_prefix=F:\AITradingBot\D10\no-pycache "
            r"F:\AITradingBot\D10\launch-guard.py"
        ),
        "action_working_directory": r"F:\AITradingBot\D10",
        "trigger_count": 1,
        "trigger_type": 2,
        "trigger_enabled": True,
        "trigger_start_boundary": "2026-09-29T01:30:00-07:00",
        "trigger_end_boundary": "2026-10-05T17:45:22-07:00",
        "host_timezone": "Pacific Standard Time",
        "trigger_days_interval": 1,
        "trigger_random_delay": "",
        "repetition_interval": "",
        "repetition_duration": "",
        "repetition_stop_at_duration_end": False,
        "multiple_instances": 2,
        "disallow_start_if_on_batteries": False,
        "stop_if_going_on_batteries": False,
        "allow_demand_start": True,
        "start_when_available": True,
        "run_only_if_network_available": False,
        "run_only_if_idle": False,
        "enabled": False,
        "hidden": False,
        "wake_to_run": True,
        "execution_time_limit": "PT1H",
        "priority": 7,
        "restart_count": 0,
        "restart_interval": "",
        "task_state": 1,
    }


def _observe_scheduler() -> dict[str, object]:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCHEDULER_HELPER),
        ],
        capture_output=True,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0 or completed.stderr or not completed.stdout:
        raise R3Blocked("scheduler_observation_failed")
    try:
        value = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise R3Blocked("scheduler_output_invalid") from None
    if (
        type(value) is not dict
        or value.get("schema") != "arch128-r3-scheduler-observation/v1"
        or value.get("status") != "OBSERVED"
        or set(value) != {"schema", "status", "first", "second"}
        or value["first"] != value["second"]
    ):
        raise R3Blocked("scheduler_two_read_drift")
    expected = _expected_scheduler()
    item = value["second"]
    if type(item) is not dict:
        raise R3Blocked("scheduler_fields_invalid")
    diagnostic = {"xml_byte_length", "xml_sha256"}
    if set(item) != set(expected) | diagnostic:
        raise R3Blocked("scheduler_fields_invalid")
    for key, expected_value in expected.items():
        if type(item[key]) is not type(expected_value) or item[key] != expected_value:
            raise R3Blocked(f"scheduler_semantic_drift:{key}")
    if (
        type(item["xml_byte_length"]) is not int
        or not 0 < item["xml_byte_length"] <= 1024 * 1024
        or item["xml_sha256"] != EXPECTED_SCHEDULER_XML_SHA256
    ):
        raise R3Blocked("scheduler_xml_drift")
    return item


def _read_exact_lease(reader: R3Reader) -> dict[str, object]:
    checked = reader.read_file(str(D10_ACTIVATION_LEASE_PATH), 64 * 1024)
    deployment.require_file(checked, str(D10_ACTIVATION_LEASE_PATH), checked.data)
    if hashlib.sha256(checked.data).hexdigest() != OLD_LEASE_SHA256:
        raise R3Blocked("old_lease_digest_drift")
    try:
        lease = parse_activation_lease(checked.data)
    except Exception:
        raise R3Blocked("old_lease_invalid") from None
    if (
        lease.deployment_id != CURRENT_DEPLOYMENT_ID
        or lease.attestation_sha256 != CURRENT_ATTESTATION_SHA256
        or lease.certified_source_head != CURRENT_SOURCE_HEAD
        or lease.certified_source_tree != CURRENT_SOURCE_TREE
        or format_utc_instant(lease.accepted_activation_utc) != OLD_ACTIVATION
        or format_utc_instant(lease.end_utc) != OLD_END
        or lease.soak_id != OLD_SOAK_ID
    ):
        raise R3Blocked("old_lease_identity_drift")
    return {
        "sha256": OLD_LEASE_SHA256,
        "activation_utc": OLD_ACTIVATION,
        "end_utc": OLD_END,
        "soak_id": OLD_SOAK_ID,
        "native_identity_sha256": hashlib.sha256(
            json.dumps(
                asdict(checked.identity),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest(),
    }


def _require_signed_identity(observed: activation.SignedObservation) -> None:
    identity = replacement.NEW_IDENTITY
    if (
        identity.deployment_id != CURRENT_DEPLOYMENT_ID
        or identity.unsigned_attestation_sha256 != CURRENT_ATTESTATION_SHA256
        or identity.certified_source_head != CURRENT_SOURCE_HEAD
        or identity.certified_source_tree != CURRENT_SOURCE_TREE
        or identity.manifest_sha256 != CURRENT_MANIFEST_SHA256
        or identity.executable_file_count != CURRENT_EXECUTABLE_FILE_COUNT
        or identity.executable_total_bytes != CURRENT_EXECUTABLE_TOTAL_BYTES
        or identity.guard_sha256 != CURRENT_GUARD_SHA256
        or identity.guard_byte_length != CURRENT_GUARD_BYTE_LENGTH
        or observed.leases_present != (True, False, False)
    ):
        raise R3Blocked("signed_s5r10_identity_drift")


def _one_read() -> dict[str, object]:
    reader = R3Reader()
    verifier = WindowsCngVerifier()
    signed = activation._stable_signed(reader, verifier)
    _require_signed_identity(signed)

    for path in (HISTORICAL_S5R8_RETIRED, NEW_S5R10_RETIRED, NEW_STAGING):
        if reader.absent(path) is not True:
            raise R3Blocked(f"reserved_namespace_present:{path}")

    lease = _read_exact_lease(reader)
    scheduler = _observe_scheduler()
    evidence = signed.evidence()

    return {
        "signed_deployment": evidence,
        "old_activation_lease": lease,
        "scheduler": {
            "enabled": scheduler["enabled"],
            "task_state": scheduler["task_state"],
            "xml_sha256": scheduler["xml_sha256"],
            "xml_byte_length": scheduler["xml_byte_length"],
        },
        "historical_s5r8_retired": "ABSENT_AND_VERIFIED",
        "new_s5r10_retired_destination": "ABSENT_AND_VERIFIED",
        "new_arch128_staging_destination": "ABSENT_AND_VERIFIED",
    }


def preflight() -> dict[str, object]:
    """Two complete matching read-only admissions; no caller facts accepted."""
    first = _one_read()
    second = _one_read()
    if first != second:
        raise R3Blocked("r3_two_read_drift")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        **second,
        "signing": "NOT_RUN",
        "production_filesystem_mutation": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
    }


def main() -> int:
    try:
        result = preflight()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "BLOCKED",
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                    "signing": "NOT_RUN",
                    "production_filesystem_mutation": "NOT_RUN",
                    "scheduler_mutation": "NOT_RUN",
                    "source_launch": "NOT_RUN",
                    "provider": "NOT_RUN",
                    "Paper-v2": "NOT_RUN",
                    "broker": "NOT_RUN",
                    "live": "NOT_RUN",
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    print("D10_ARCH128_R3_READONLY_PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
