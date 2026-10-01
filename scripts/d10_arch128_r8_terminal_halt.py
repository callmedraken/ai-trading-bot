"""R8I-H1 exact incident halt policy; source registration grants no authority.

NOT_RUN effects describe this halt only. The failed natural child's effects
remain UNKNOWN_REQUIRES_READ_ONLY_RECONCILIATION.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from scripts import d10_arch128_r6_reactivation as r6
from scripts import d10_arch128_r7_observation as scheduler_policy
from scripts import d10_arch128_r8_readonly as r8

SCHEMA = "architecture-128-r8-terminal-halt/v1"
EXECUTE_FLAG = "--execute-reviewed-r8-terminal-halt"
AUTHORIZATION_ENV = "AI_TRADING_BOT_ARCH128_R8_HALT_AUTHORIZATION"
AUTHORIZATION_VALUE = "ARCH128_R8_TERMINAL_HALT_AUTHORIZED"
ACTIVATION = datetime(2026, 9, 30, 22, 7, 24, tzinfo=UTC)
LEASE_SHA256 = "d2bdf74cb50420acbfed6adc1c79a1d4fe291233407b0506e0d71423248b76af"
EXPECTED_EVIDENCE = {
    **r8.EXPECTED_IDENTITY,
    "evidence_byte_length": 453,
    "evidence_sha256": (
        "b2b5d5f84db2dd7d41b67d38b0449a1e701b9f1a1e0c4bac825663a0ebf36d7e"
    ),
    "record_count": 2,
    "wake_count": 0,
    "terminal": True,
    "terminal_kind": "GUARD_TERMINAL",
    "first_observed_at_utc": "2026-10-01T08:30:09.370767Z",
    "last_observed_at_utc": "2026-10-01T08:30:21.815609Z",
    "last_outcome": None,
    "last_stop_reason": None,
    "last_guard_reason": "CHILD_OUTPUT_INVALID",
    **dict.fromkeys(r8.OBSERVER_EFFECT_FIELDS, "NOT_RUN"),
}
CLOSED_EFFECTS = (
    "production_filesystem_mutation",
    "evidence_mutation",
    "lease_mutation",
    "manual_task_start",
    "task_stop",
    "task_delete",
    "task_registration",
    "source_launch",
    "decision_publication",
    "provider",
    "Paper-v2",
    "broker",
    "live",
)


class HaltBlocked(RuntimeError):
    """Exact incident or host admission failed."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    evidence: dict[str, object]
    lease: dict[str, object]
    scheduler: dict[str, object]


class ReadOnlyHost(Protocol):
    def observe(self) -> Snapshot: ...


class ProtectedHost(ReadOnlyHost, Protocol):
    def disable(self) -> dict[str, object]: ...


def expected_scheduler(enabled: bool) -> dict[str, object]:
    """Derive all accepted semantics from the current activation, never history."""
    expected = scheduler_policy.scheduler_semantics(
        r6.derive_reactivation_plan(ACTIVATION).scheduler
    )
    expected["enabled"] = enabled
    expected["task_state"] = 3 if enabled else 1
    return expected


def require_exact(value: object, expected: dict[str, object], reason: str) -> None:
    if (
        type(value) is not dict
        or set(value) != set(expected)
        or any(
            type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()
        )
    ):
        raise HaltBlocked(reason)


def require_snapshot(snapshot: Snapshot, *, enabled: bool) -> None:
    if type(snapshot) is not Snapshot:
        raise HaltBlocked("snapshot_shape_invalid")
    require_exact(snapshot.evidence, EXPECTED_EVIDENCE, "incident_evidence_drift")
    lease = snapshot.lease
    if (
        type(lease) is not dict
        or set(lease) != {"sha256", "native_identity_sha256"}
        or type(lease["sha256"]) is not str
        or lease["sha256"] != LEASE_SHA256
        or type(lease["native_identity_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", lease["native_identity_sha256"]) is None
    ):
        raise HaltBlocked("lease_identity_drift")
    require_scheduler(snapshot.scheduler, enabled=enabled)


def require_scheduler(value: dict[str, object], *, enabled: bool) -> None:
    expected = expected_scheduler(enabled)
    if type(value) is not dict or set(value) != set(expected) | {
        "xml_byte_length",
        "xml_sha256",
    }:
        raise HaltBlocked("scheduler_shape_drift")
    require_exact(
        {key: value[key] for key in expected}, expected, "scheduler_semantic_drift"
    )
    if (
        type(value["xml_byte_length"]) is not int
        or not 0 < value["xml_byte_length"] <= 1024 * 1024
        or type(value["xml_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", value["xml_sha256"]) is None
    ):
        raise HaltBlocked("scheduler_xml_invalid")


def base_result() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "call_attempted": False,
        "disposition": "NOT_CALLED",
        "scheduler_mutation": "NOT_RUN",
        "automatic_retry": False,
        "automatic_rollback": False,
        "automatic_cleanup": False,
        "failed_child_effects": "UNKNOWN_REQUIRES_READ_ONLY_RECONCILIATION",
        **dict.fromkeys(CLOSED_EFFECTS, "NOT_RUN"),
    }


def admit(host: ReadOnlyHost) -> Snapshot:
    snapshot = host.observe()
    # An exact already-disabled task is a distinct read-only outcome, never authority.
    if type(snapshot) is Snapshot and snapshot.scheduler.get("enabled") is False:
        require_snapshot(snapshot, enabled=False)
        raise HaltBlocked("already_disabled_no_mutation_authority")
    require_snapshot(snapshot, enabled=True)
    return snapshot


def preflight(host: ReadOnlyHost) -> dict[str, object]:
    """Read-only admission. Never asks for or constructs a mutation capability."""
    result = base_result()
    try:
        snapshot = admit(host)
    except HaltBlocked as exc:
        result["reason"] = str(exc)
        return result
    except Exception:
        result["reason"] = "read_only_observation_failed"
        return result
    result.update(
        status="PASS",
        incident="EXACT_TERMINAL_FIRST_WAKE",
        scheduler_pre="ENABLED_NON_RUNNING_EXACT",
        evidence=dict(snapshot.evidence),
        lease=dict(snapshot.lease),
        scheduler=dict(snapshot.scheduler),
    )
    return result


def execute(
    argv: Sequence[str],
    environment: Mapping[str, str],
    host_factory: Callable[[], ProtectedHost],
) -> dict[str, object]:
    """One protected dispatch after generic runner admission and human interlock."""
    result = base_result()
    if (
        tuple(argv) != (EXECUTE_FLAG,)
        or environment.get(AUTHORIZATION_ENV) != AUTHORIZATION_VALUE
    ):
        result["reason"] = "authorization_required"
        return result
    try:
        host = host_factory()
        before = admit(host)
    except HaltBlocked as exc:
        result["reason"] = str(exc)
        return result
    except Exception:
        result["reason"] = "pre_call_observation_failed"
        return result
    # Dispatch can lose its response after COM mutation. Until a validated native
    # result proves NOT_CALLED, an exception here is conservatively indeterminate.
    result.update(
        call_attempted=True,
        disposition="INDETERMINATE",
        scheduler_mutation="INDETERMINATE",
    )
    try:
        mutation = host.disable()
        if (
            type(mutation) is not dict
            or set(mutation)
            != {
                "schema",
                "call_attempted",
                "disposition",
                "before",
                "after",
                "xml_unchanged",
            }
            or mutation["schema"] != "arch128-r8-terminal-halt-com/v1"
        ):
            raise HaltBlocked("native_result_invalid")
        if (
            mutation["call_attempted"] is False
            and mutation["disposition"] == "NOT_CALLED"
            and mutation["after"] is None
            and mutation["xml_unchanged"] is False
        ):
            result.update(
                call_attempted=False,
                disposition="NOT_CALLED",
                scheduler_mutation="NOT_RUN",
                reason="native_pre_call_blocked",
            )
            return result
        if (
            mutation["call_attempted"] is not True
            or mutation["disposition"] != "CALL_RETURNED"
        ):
            raise HaltBlocked("native_result_indeterminate")
        result["disposition"] = "CALL_RETURNED"
        require_exact(
            mutation["before"], before.scheduler, "scheduler_changed_before_call"
        )
        require_scheduler(mutation["after"], enabled=False)
        if mutation["xml_unchanged"] is not True:
            raise HaltBlocked("unrelated_scheduler_xml_changed")
        after = host.observe()
        require_snapshot(after, enabled=False)
        require_exact(
            after.scheduler, mutation["after"], "scheduler_changed_after_call"
        )
        if after.evidence != before.evidence or after.lease != before.lease:
            raise HaltBlocked("evidence_or_lease_changed_after_call")
    except Exception:
        result.update(
            status="STOPPED",
            disposition="INDETERMINATE",
            reason="halt_requires_read_only_reconciliation",
        )
        return result
    result.update(
        status="PASS",
        incident="EXACT_TERMINAL_FIRST_WAKE",
        scheduler_pre="ENABLED_NON_RUNNING_EXACT",
        scheduler_mutation="DISABLED_VERIFIED",
        scheduler_post="DISABLED_NON_RUNNING_EXACT",
        evidence_before_after="IDENTICAL",
        lease_before_after="IDENTICAL",
        evidence=dict(after.evidence),
        lease=dict(after.lease),
        scheduler_before=dict(before.scheduler),
        scheduler_after=dict(after.scheduler),
    )
    return result
