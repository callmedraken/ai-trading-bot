"""Fixed read-only R8 incident observations and one protected COM transport.

Imports and factories have no production effect. Preflight constructs only the
read-only host. No source, provider, Paper-v2, broker, or live call is available.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from scripts import d10_arch128_r6_reactivation as r6
from scripts import d10_arch128_r8_terminal_halt as policy
from scripts import d10_durable_wake_evidence_observe as observer
from scripts.d10_arch128_r4_windows import WindowsArch128ReadOnlyReader
from scripts.d10_protected_deployment import require_file
from scripts.d10_protected_replacement_windows import POWERSHELL
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10_ACTIVATION_LEASE_PATH,
    parse_activation_lease,
)

OBSERVE_HELPER = Path(__file__).with_name("d10_arch128_r3_scheduler_observe.ps1")
HALT_HELPER = Path(__file__).with_name("d10_arch128_r8_terminal_halt.ps1")


def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise policy.HaltBlocked("duplicate_transport_field")
        result[key] = value
    return result


def transport(helper: Path) -> dict[str, object]:
    if helper not in (OBSERVE_HELPER, HALT_HELPER):
        raise policy.HaltBlocked("transport_not_fixed")
    arguments = () if helper == OBSERVE_HELPER else (policy.EXECUTE_FLAG,)
    completed = subprocess.run(
        (
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            *arguments,
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if (
        completed.stderr
        or not completed.stdout
        or len(completed.stdout) > 32 * 1024
        or completed.returncode not in ((0,) if helper == OBSERVE_HELPER else (0, 1, 2))
    ):
        raise policy.HaltBlocked("transport_failed_or_ambiguous")
    value = json.loads(completed.stdout.decode("utf-8"), object_pairs_hook=unique_pairs)
    if type(value) is not dict:
        raise policy.HaltBlocked("transport_shape_invalid")
    return value


class ReadOnlyWindowsHost:
    """Read only the fixed lease, accepted durable observer, and R3 COM helper."""

    def observe(self) -> policy.Snapshot:
        reader = WindowsArch128ReadOnlyReader()
        first = reader.read_file(D10_ACTIVATION_LEASE_PATH, 64 * 1024)
        require_file(first, D10_ACTIVATION_LEASE_PATH, first.data)
        plan = r6.derive_reactivation_plan(policy.ACTIVATION)
        if parse_activation_lease(first.data) != plan.lease:
            raise policy.HaltBlocked("lease_drift")
        evidence = observer.observe()
        scheduler = transport(OBSERVE_HELPER)
        if (
            set(scheduler) != {"schema", "status", "first", "second"}
            or scheduler["schema"] != "arch128-r3-scheduler-observation/v1"
            or scheduler["status"] != "OBSERVED"
            or type(scheduler["first"]) is not dict
            or scheduler["first"] != scheduler["second"]
        ):
            raise policy.HaltBlocked("scheduler_two_read_drift")
        second = reader.read_file(D10_ACTIVATION_LEASE_PATH, 64 * 1024)
        require_file(second, D10_ACTIVATION_LEASE_PATH, second.data)
        if first != second:
            raise policy.HaltBlocked("lease_two_read_drift")
        lease = {
            "sha256": hashlib.sha256(second.data).hexdigest(),
            "native_identity_sha256": hashlib.sha256(
                json.dumps(
                    asdict(second.identity),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("ascii")
            ).hexdigest(),
        }
        return policy.Snapshot(evidence, lease, scheduler["second"])


class ProtectedWindowsHost(ReadOnlyWindowsHost):
    def disable(self) -> dict[str, object]:
        return transport(HALT_HELPER)
