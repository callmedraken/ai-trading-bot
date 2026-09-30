"""Fixed R7 plan, evidence, and COM projection validation; no host effects."""

from __future__ import annotations

import ntpath
import re
from datetime import UTC, datetime
from uuid import UUID

from scripts import d10_arch128_r6_reactivation as r6
from scripts import run_personal_desktop_d10_launch_guard as guard
from scripts.d10_protected_deployment import (
    ADMINISTRATORS_SID,
    FILE_ALL_ACCESS,
    SYSTEM_SID,
    Ace,
    CheckedFile,
    DeploymentBlocked,
    NativeObject,
)
from trading_bot.runtime import (
    personal_desktop_unattended_one_week_soak_scheduler_contract as schedule,
)
from trading_bot.runtime.personal_desktop_d10_wake_evidence_log import (
    D10_WAKE_EVIDENCE_ROOT,
)

PREDECESSOR_XML_SHA256 = (
    "8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0"
)


def require_plan(plan: r6.ReactivationPlan) -> None:
    if type(plan) is not r6.ReactivationPlan or plan != r6.derive_reactivation_plan(
        plan.lease.accepted_activation_utc
    ):
        raise DeploymentBlocked("r7_plan_not_exact")
    require_evidence_path(plan.evidence_path)


def require_evidence_path(path: str) -> None:
    if (
        type(path) is not str
        or ntpath.normpath(path) != path
        or ntpath.dirname(path) != str(D10_WAKE_EVIDENCE_ROOT)
    ):
        raise DeploymentBlocked("r7_evidence_path_not_canonical")
    name = ntpath.basename(path)
    if (
        re.fullmatch(
            r"wake-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl",
            name,
        )
        is None
        or str(UUID(name[5:-6])) != name[5:-6]
    ):
        raise DeploymentBlocked("r7_evidence_name_not_canonical")


def require_empty_evidence(checked: CheckedFile, path: str) -> r6.EvidenceObservation:
    require_evidence_path(path)
    aces = (
        Ace(ADMINISTRATORS_SID, FILE_ALL_ACCESS),
        Ace(SYSTEM_SID, FILE_ALL_ACCESS),
        Ace(guard.TRADING_SID, guard.TRADING_EVIDENCE_FILE_ACCESS),
    )
    if type(checked) is not CheckedFile or type(checked.identity) is not NativeObject:
        raise DeploymentBlocked("r7_evidence_native_result")
    item = checked.identity
    if (
        checked.stable is not True
        or type(checked.data) is not bytes
        or checked.data != b""
        or item.path != path
        or item.final_path != path
        or item.directory is not False
        or type(item.size) is not int
        or item.size != 0
        or item.reparse is not False
        or item.drive_type != 3
        or item.volume_root != "F:" + chr(92)
        or item.filesystem != "NTFS"
        or item.links != 1
        or item.owner_sid != ADMINISTRATORS_SID
        or item.dacl_protected is not True
        or item.aces != aces
    ):
        raise DeploymentBlocked("r7_evidence_policy_or_identity_drift")
    return r6.EvidenceObservation(
        path,
        0,
        ADMINISTRATORS_SID,
        True,
        FILE_ALL_ACCESS,
        FILE_ALL_ACCESS,
        guard.TRADING_EVIDENCE_FILE_ACCESS,
        True,
        True,
        1,
    )


def scheduler_semantics(
    spec: schedule.OneWeekSoakSchedulerDeploymentSpec | None,
) -> dict[str, object]:
    old = spec is None
    if old:
        spec = schedule.build_one_week_soak_scheduler_deployment_spec(
            datetime(2026, 9, 29, 0, 45, 22, tzinfo=UTC)
        )
    if (
        type(spec) is not schedule.OneWeekSoakSchedulerDeploymentSpec
        or spec
        != schedule.build_one_week_soak_scheduler_deployment_spec(
            spec.window.activation_utc
        )
    ):
        raise DeploymentBlocked("r7_scheduler_plan_not_exact")
    task = spec.task
    if task.semantic_arguments or task.scheduler_owned_environment:
        raise DeploymentBlocked("r7_scheduler_arguments_not_zero")
    return {
        "task_path": task.task_path,
        "principal_sid": task.principal_sid,
        "logon_type": 1,
        "run_level": 0,
        "action_count": 1,
        "action_type": 0,
        "action_path": str(task.executable),
        "action_arguments": " ".join(task.arguments),
        "action_working_directory": str(task.working_directory),
        "trigger_count": 1,
        "trigger_type": 2,
        "trigger_enabled": True,
        "trigger_start_boundary": task.start_boundary.isoformat(timespec="seconds"),
        "trigger_end_boundary": spec.end_boundary.isoformat(timespec="auto"),
        "host_timezone": task.host_timezone,
        "trigger_days_interval": task.days_interval,
        "trigger_random_delay": "",
        "repetition_interval": "",
        "repetition_duration": "",
        "repetition_stop_at_duration_end": False,
        "multiple_instances": 2,
        "disallow_start_if_on_batteries": task.disallow_start_if_on_batteries,
        "stop_if_going_on_batteries": task.stop_if_going_on_batteries,
        "allow_demand_start": task.allow_start_on_demand,
        "start_when_available": task.start_when_available,
        "run_only_if_network_available": task.run_only_if_network_available,
        "run_only_if_idle": task.run_only_if_idle,
        "enabled": False if old else task.enabled,
        "hidden": task.hidden,
        "wake_to_run": task.wake_to_run,
        "execution_time_limit": task.execution_time_limit,
        "priority": task.priority,
        "restart_count": task.restart_count,
        "restart_interval": "",
        "task_state": 1 if old else 3,
    }


def require_scheduler(
    observed: dict[str, object],
    spec: schedule.OneWeekSoakSchedulerDeploymentSpec | None,
) -> None:
    expected = scheduler_semantics(spec)
    if (
        type(observed) is not dict
        or set(observed) != set(expected) | {"xml_byte_length", "xml_sha256"}
        or any(
            type(observed[key]) is not type(value) or observed[key] != value
            for key, value in expected.items()
        )
        or type(observed["xml_byte_length"]) is not int
        or not 0 < observed["xml_byte_length"] <= 1024 * 1024
        or type(observed["xml_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", observed["xml_sha256"]) is None
        or (spec is None and observed["xml_sha256"] != PREDECESSOR_XML_SHA256)
    ):
        raise DeploymentBlocked("r7_scheduler_semantic_or_xml_drift")


def require_stage(stage: str, plan: r6.ReactivationPlan | None) -> None:
    if type(stage) is not str or stage not in (
        "INITIAL",
        "AFTER_CREDENTIAL",
        "BEFORE_LEASE",
        "FINAL",
    ):
        raise DeploymentBlocked("r7_stage_unreviewed")
    if stage == "INITIAL":
        if plan is not None:
            raise DeploymentBlocked("r7_initial_plan_present")
    else:
        require_plan(plan)
