"""Read-only native R8 halt pre-call diagnostic transport."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import d10_arch128_r8_terminal_halt as policy
from scripts.d10_protected_replacement_windows import POWERSHELL

HELPER = Path(__file__).with_name("d10_arch128_r8_terminal_halt_diagnose.ps1")
SCHEMA = "arch128-r8-terminal-halt-diagnostic/v1"
READY = "READY"
BLOCKED = "BLOCKED"
REASONS = frozenset(
    {
        "AUTHORIZATION_PRESENT",
        "ADMINISTRATOR_REQUIRED",
        "OBSERVE_HELPER_LOAD",
        "COM_CONNECT",
        "SCHEDULER_READ_FIRST",
        "SCHEDULER_READ_SECOND",
        "SCHEDULER_TWO_READ",
        "SCHEDULER_SEMANTICS",
        "TASK_REACQUIRE",
        "TASK_TARGET",
        "IMMEDIATE_XML",
        "XML_ENABLED_NODE",
    }
)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise policy.HaltBlocked("duplicate_diagnostic_field")
        result[key] = value
    return result


def observe() -> dict[str, object]:
    """Run only the fixed read-only native admission checks."""
    completed = subprocess.run(
        (
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HELPER),
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
        or completed.returncode not in (0, 1)
    ):
        raise policy.HaltBlocked("diagnostic_transport_failed_or_ambiguous")
    value = json.loads(
        completed.stdout.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
    )
    if type(value) is not dict or set(value) != {
        "schema",
        "status",
        "reason",
        "call_attempted",
        "scheduler_mutation",
        "scheduler",
    }:
        raise policy.HaltBlocked("diagnostic_shape_invalid")
    if (
        value["schema"] != SCHEMA
        or value["call_attempted"] is not False
        or value["scheduler_mutation"] != "NOT_RUN"
    ):
        raise policy.HaltBlocked("diagnostic_contract_invalid")
    if value["status"] == READY:
        if value["reason"] is not None or type(value["scheduler"]) is not dict:
            raise policy.HaltBlocked("diagnostic_ready_invalid")
    elif value["status"] == BLOCKED:
        if value["reason"] not in REASONS or (
            value["scheduler"] is not None and type(value["scheduler"]) is not dict
        ):
            raise policy.HaltBlocked("diagnostic_block_invalid")
    else:
        raise policy.HaltBlocked("diagnostic_status_invalid")
    return value
